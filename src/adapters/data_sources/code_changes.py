import json
from pathlib import Path

from src.adapters.base import DataChunk, DataSourceAdapter
from src.core.config import get_yaml_config
from src.models.incident import Incident

_READABLE_SUFFIXES = {".diff", ".patch", ".txt", ".json", ".yaml", ".yml"}


class CodeChangesAdapter(DataSourceAdapter):
    """Reads code change artifacts (git diffs, patch files) for a given deploy SHA."""

    name = "code_changes"

    def is_available(self) -> bool:
        cfg = get_yaml_config()
        return cfg.get("data_sources", {}).get("code_changes", {}).get("enabled", True)

    async def fetch(self, incident: Incident, context: dict) -> list[DataChunk]:
        chunks: list[DataChunk] = []

        deploy_sha = (
            incident.metadata.get("deploy_sha")
            or context.get("deploy_sha")
        )
        code_path = context.get("code_changes_path")

        if code_path:
            chunks.extend(self._read_path(Path(code_path), deploy_sha))
        elif deploy_sha:
            chunks.extend(self._search_demo_dir(deploy_sha))

        if not chunks:
            chunks.extend(self._read_metadata_hints(incident))

        return chunks

    def _read_path(self, path: Path, sha: str | None) -> list[DataChunk]:
        chunks = []
        if path.is_file() and path.suffix in _READABLE_SUFFIXES:
            chunks.append(DataChunk(
                source=f"code_changes:{path.name}",
                content=path.read_text(errors="replace"),
                metadata={"file": str(path), "sha": sha or "unknown"},
            ))
        elif path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file() and f.suffix in _READABLE_SUFFIXES:
                    chunks.append(DataChunk(
                        source=f"code_changes:{f.name}",
                        content=f.read_text(errors="replace"),
                        metadata={"file": str(f), "sha": sha or "unknown"},
                    ))
        return chunks

    def _search_demo_dir(self, sha: str) -> list[DataChunk]:
        """Look for a .diff file matching the deploy SHA in the demo/code directory."""
        demo_dir = Path(__file__).parents[4] / "demo" / "code"
        if not demo_dir.exists():
            return []
        for f in demo_dir.glob(f"{sha}*"):
            if f.suffix in _READABLE_SUFFIXES:
                return [DataChunk(
                    source=f"code_changes:{f.name}",
                    content=f.read_text(errors="replace"),
                    metadata={"file": str(f), "sha": sha},
                )]
        for f in demo_dir.glob("*.diff"):
            return [DataChunk(
                source=f"code_changes:{f.name}",
                content=f.read_text(errors="replace"),
                metadata={"file": str(f), "sha": sha},
            )]
        return []

    def _read_metadata_hints(self, incident: Incident) -> list[DataChunk]:
        """Synthesise a minimal change summary from incident metadata when no diff file exists."""
        meta = incident.metadata
        if not meta:
            return []
        lines = ["=== Change Summary from Incident Metadata ==="]
        for key in ("deploy_sha", "service", "environment", "on_call_engineer"):
            if key in meta:
                lines.append(f"{key}: {meta[key]}")
        return [DataChunk(
            source="code_changes:metadata_hint",
            content="\n".join(lines),
            metadata={"source": "incident_metadata"},
        )]
