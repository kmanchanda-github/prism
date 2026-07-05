import logging

from celery import Celery
from celery.signals import setup_logging

from src.core.config import get_settings

logger = logging.getLogger(__name__)


@setup_logging.connect
def configure_logging(**kwargs):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

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

# Single-container deployments (e.g. Hugging Face Spaces) run only the API
# process — no separate `celery worker` ever consumes the queue. Their
# CELERY_BROKER_URL is set to memory:// specifically to signal that; without
# eager mode, every task submitted there would sit as "pending" forever.
if settings.celery_broker_url.startswith("memory://"):
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


@celery_app.task(bind=True, name="run_analysis")
def run_analysis_task(self, analysis_id: str, incident_dict: dict, context: dict, notify_channels: list[str]):
    """Run the full LangGraph analysis pipeline for one incident."""
    import asyncio
    logger.info("task started analysis_id=%s", analysis_id)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Eager mode (task_always_eager, set above for memory:// deployments)
        # runs this function directly on the caller's thread — which is
        # FastAPI's already-running event loop. asyncio.run() would raise
        # here, so schedule on that loop instead and return immediately.
        loop.create_task(_run(self, analysis_id, incident_dict, context, notify_channels))
    else:
        asyncio.run(_run(self, analysis_id, incident_dict, context, notify_channels))


async def _run(task, analysis_id: str, incident_dict: dict, context: dict, notify_channels: list[str]):
    import uuid
    from datetime import datetime

    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.agents.orchestrator import AnalysisState, build_graph
    from src.core.config import get_settings
    from src.models.evaluation import ImprovementHintORM
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
            logger.info("analysis running incident_id=%s analysis_id=%s", incident.id, analysis_id)

            # Look up lessons from prior evaluated incidents on this same
            # service — this is the feedback loop: evaluation results feed
            # forward into the next matching incident's synthesis prompt.
            applied_hints: list[str] = []
            service = incident.metadata.get("service", "")
            if service:
                hints_result = await db.execute(
                    select(ImprovementHintORM)
                    .where(ImprovementHintORM.service == service)
                    .order_by(ImprovementHintORM.created_at.desc())
                    .limit(3)
                )
                applied_hints = [h.hint_summary for h in hints_result.scalars().all()]

            graph = build_graph()
            initial = AnalysisState(
                incident=incident,
                context={**context, "improvement_hints": applied_hints},
                notify_channels=notify_channels,
            )
            # graph.ainvoke() returns a plain dict of the output channels, not
            # an AnalysisState instance — rehydrate so attribute access below works.
            final = AnalysisState(**await graph.ainvoke(initial))

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
                applied_hints=applied_hints,
                langsmith_run_id=final.langsmith_run_id,
            )
            db.add(version)

            await db.execute(
                update(AnalysisReportORM)
                .where(AnalysisReportORM.id == analysis_id)
                .values(status="complete", token_usage=token_data, current_version=0)
            )
            await db.commit()
            logger.info(
                "analysis complete analysis_id=%s confidence=%.2f agents=%s tokens=%s",
                analysis_id,
                final.confidence_score,
                [r.agent for r in final.sub_reports],
                token_data,
            )

            # Send notifications
            await _notify(incident, analysis_id, final, notify_channels, settings)

        except Exception as exc:
            logger.exception("analysis failed analysis_id=%s error=%s", analysis_id, exc)
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
