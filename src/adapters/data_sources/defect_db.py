import json
from pathlib import Path

from src.adapters.base import DataChunk, DataSourceAdapter
from src.core.config import get_yaml_config
from src.models.incident import Incident

_DEMO_DB_PATH = Path(__file__).parents[4] / "demo" / "defects" / "known_issues.json"


class DefectDbAdapter(DataSourceAdapter):
    """Searches a known-issues database for defects relevant to the incident."""

    name = "defect_db"

    def is_available(self) -> bool:
        cfg = get_yaml_config()
        enabled = cfg.get("data_sources", {}).get("defect_db", {}).get("enabled", True)
        return enabled

    async def fetch(self, incident: Incident, context: dict) -> list[DataChunk]:
        db_path = Path(context.get("defect_db_path", _DEMO_DB_PATH))
        if not db_path.exists():
            return []

        all_defects: list[dict] = json.loads(db_path.read_text())
        service = incident.metadata.get("service", "")
        keywords = self._extract_keywords(incident)

        matched = self._match(all_defects, service, keywords)
        if not matched:
            matched = all_defects  # fallback: include all so LLM can judge relevance

        content = json.dumps(matched, indent=2)
        return [DataChunk(
            source=f"defect_db:{db_path.name}",
            content=content,
            metadata={"matched_count": len(matched), "total": len(all_defects)},
        )]

    def _extract_keywords(self, incident: Incident) -> set[str]:
        text = f"{incident.title} {incident.description}".lower()
        candidates = {
            "pool", "connection", "timeout", "db", "database", "hikari",
            "redis", "cache", "payment", "gateway", "memory", "leak",
            "lock", "deadlock", "index", "bloat", "vacuum", "deploy",
            "rollback", "config", "pipeline", "latency", "error", "crash",
        }
        return {kw for kw in candidates if kw in text}

    def _match(self, defects: list[dict], service: str, keywords: set[str]) -> list[dict]:
        scored = []
        for d in defects:
            score = 0
            if service and service.lower() in d.get("service", "").lower():
                score += 3
            tags = {t.lower() for t in d.get("tags", [])}
            score += len(tags & keywords)
            title_lower = d.get("title", "").lower()
            score += sum(2 for kw in keywords if kw in title_lower)
            if score > 0:
                scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:5]]
