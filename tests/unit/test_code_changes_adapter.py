"""Unit tests for CodeChangesAdapter demo-dir resolution and fallback."""
import pytest

from src.adapters.data_sources.code_changes import CodeChangesAdapter
from src.models.incident import Incident


def _incident(**kwargs) -> Incident:
    defaults = dict(
        id="test-001",
        title="Checkout service timeout spike",
        description="504s on payment requests",
        severity="P1",
        metadata={"deploy_sha": "d9f3a1c"},
    )
    defaults.update(kwargs)
    return Incident(**defaults)


@pytest.mark.asyncio
async def test_search_demo_dir_finds_real_demo_diff_by_deploy_sha():
    """Regression test: _search_demo_dir used Path(__file__).parents[4],
    which resolves one directory above the repo root, so it always returned
    [] and silently fell back to the generic metadata-hint summary instead
    of the actual git diff — on every real submission, since no route ever
    sets context["code_changes_path"]."""
    adapter = CodeChangesAdapter()
    chunks = await adapter.fetch(_incident(), {})
    assert len(chunks) == 1
    assert chunks[0].source == "code_changes:d9f3a1c.diff"
    assert chunks[0].metadata["sha"] == "d9f3a1c"


@pytest.mark.asyncio
async def test_search_demo_dir_falls_back_to_any_diff_when_sha_unmatched():
    """No exact SHA match in the demo dir still returns *some* diff (mirrors
    DefectDbAdapter's "return all so the LLM can judge relevance" fallback)."""
    adapter = CodeChangesAdapter()
    incident = _incident(metadata={"deploy_sha": "no-such-sha"})
    chunks = await adapter.fetch(incident, {})
    assert len(chunks) == 1
    assert chunks[0].source.startswith("code_changes:")
    assert chunks[0].source != "code_changes:metadata_hint"


@pytest.mark.asyncio
async def test_fetch_falls_back_to_metadata_hints_when_no_deploy_sha():
    adapter = CodeChangesAdapter()
    incident = _incident(metadata={"service": "checkout-service"})
    chunks = await adapter.fetch(incident, {})
    assert len(chunks) == 1
    assert chunks[0].source == "code_changes:metadata_hint"


@pytest.mark.asyncio
async def test_fetch_prefers_explicit_context_path_over_demo_dir(tmp_path):
    diff_file = tmp_path / "custom.diff"
    diff_file.write_text("diff --git a/foo b/foo\n+bar\n")
    adapter = CodeChangesAdapter()
    chunks = await adapter.fetch(_incident(), {"code_changes_path": str(diff_file)})
    assert len(chunks) == 1
    assert chunks[0].source == "code_changes:custom.diff"
