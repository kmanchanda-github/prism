from celery import Celery

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "prism",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=50,  # recycle worker after 50 tasks to prevent memory leaks
)


@celery_app.task(bind=True, name="run_analysis")
def run_analysis_task(self, analysis_id: str, incident_dict: dict, context: dict, notify_channels: list[str]):
    """
    Run the full LangGraph analysis pipeline for one incident.
    Writes results to Postgres and triggers notifications on completion.
    """
    import asyncio
    asyncio.run(_run(self, analysis_id, incident_dict, context, notify_channels))


async def _run(task, analysis_id: str, incident_dict: dict, context: dict, notify_channels: list[str]):
    import uuid
    from datetime import datetime

    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.agents.orchestrator import AnalysisState, build_graph
    from src.core.config import get_settings
    from src.models.incident import Incident
    from src.models.report import AnalysisReportORM, AnalysisVersionORM

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # Mark running
        await db.execute(
            update(AnalysisReportORM)
            .where(AnalysisReportORM.id == analysis_id)
            .values(status="running")
        )
        await db.commit()

        try:
            incident = Incident(**incident_dict)
            graph = build_graph()
            initial = AnalysisState(
                incident=incident,
                context=context,
                notify_channels=notify_channels,
            )
            final: AnalysisState = await graph.ainvoke(initial)

            token_data = final.token_tracker.totals() if final.token_tracker else {}

            # Save v0 (AI-generated) version
            version = AnalysisVersionORM(
                analysis_id=analysis_id,
                incident_id=incident.id,
                version=0,
                root_cause=final.root_cause,
                workaround=final.workaround,
                recommended_actions=[a for a in final.recommended_actions],
                sub_reports=[r.model_dump() for r in final.sub_reports],
                confidence_score=final.confidence_score,
                edited_by="ai",
                edit_source="ai_generated",
            )
            db.add(version)

            await db.execute(
                update(AnalysisReportORM)
                .where(AnalysisReportORM.id == analysis_id)
                .values(status="complete", token_usage=token_data, current_version=0)
            )
            await db.commit()

            # Send notifications
            await _notify(incident, analysis_id, final, notify_channels, settings)

        except Exception as exc:
            await db.execute(
                update(AnalysisReportORM)
                .where(AnalysisReportORM.id == analysis_id)
                .values(status="failed")
            )
            await db.commit()
            raise exc
        finally:
            await engine.dispose()


async def _notify(incident, analysis_id: str, state, channels: list[str], settings):
    from src.adapters.notifications.slack import SlackAdapter

    link = f"{settings.base_url}/analysis/{analysis_id}"
    message = f"Analysis ready: {incident.title} [{incident.severity}]"
    summary = state.root_cause[:280] if state.root_cause else ""

    adapters = {"slack": SlackAdapter()}
    for channel in channels:
        adapter = adapters.get(channel)
        if adapter and adapter.is_available():
            await adapter.send(message=message, link=link, summary=summary, config={})
