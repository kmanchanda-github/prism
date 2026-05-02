import zipfile
from pathlib import Path

from src.adapters.base import DataChunk, DataSourceAdapter
from src.core.config import get_yaml_config
from src.models.incident import Incident

_READABLE_SUFFIXES = {".log", ".txt", ".out", ".err", ".json", ".yaml", ".yml"}


class LogBundleAdapter(DataSourceAdapter):
    """Reads a local log bundle (zip or directory) and returns text chunks."""

    name = "log_bundle"

    def is_available(self) -> bool:
        cfg = get_yaml_config()
        return cfg.get("data_sources", {}).get("log_bundle", {}).get("enabled", False)

    async def fetch(self, incident: Incident, context: dict) -> list[DataChunk]:
        bundle_path = context.get("log_bundle_path")
        if not bundle_path:
            return []

        path = Path(bundle_path)
        if path.suffix == ".zip":
            return self._read_zip(path, incident)
        elif path.is_dir():
            return self._read_dir(path, incident)
        else:
            return self._read_single_file(path)

    def _read_zip(self, path: Path, incident: Incident) -> list[DataChunk]:
        chunks = []
        cfg = get_yaml_config()
        chunk_size = cfg.get("analysis", {}).get("log_chunk_size_chars", 50000)

        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if Path(name).suffix not in _READABLE_SUFFIXES:
                    continue
                with zf.open(name) as f:
                    text = f.read().decode("utf-8", errors="replace")
                    for i, chunk in enumerate(self._chunk(text, chunk_size)):
                        chunks.append(DataChunk(
                            source=f"log_bundle:{name}:chunk{i}",
                            content=chunk,
                            metadata={"file": name, "incident_id": incident.id},
                        ))
        return chunks

    def _read_dir(self, path: Path, incident: Incident) -> list[DataChunk]:
        cfg = get_yaml_config()
        chunk_size = cfg.get("analysis", {}).get("log_chunk_size_chars", 50000)
        chunks = []
        for file in sorted(path.rglob("*")):
            if file.suffix not in _READABLE_SUFFIXES or not file.is_file():
                continue
            text = file.read_text(errors="replace")
            for i, chunk in enumerate(self._chunk(text, chunk_size)):
                chunks.append(DataChunk(
                    source=f"log_bundle:{file.name}:chunk{i}",
                    content=chunk,
                    metadata={"file": str(file), "incident_id": incident.id},
                ))
        return chunks

    def _read_single_file(self, path: Path) -> list[DataChunk]:
        cfg = get_yaml_config()
        chunk_size = cfg.get("analysis", {}).get("log_chunk_size_chars", 50000)
        text = path.read_text(errors="replace")
        return [
            DataChunk(source=f"log_bundle:{path.name}:chunk{i}", content=chunk)
            for i, chunk in enumerate(self._chunk(text, chunk_size))
        ]

    @staticmethod
    def _chunk(text: str, size: int) -> list[str]:
        return [text[i : i + size] for i in range(0, len(text), size)]
