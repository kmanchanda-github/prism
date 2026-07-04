"""Unit tests for LogBundleAdapter demo-bundle fallback and real file reads."""
import zipfile

import pytest

from src.adapters.data_sources.log_bundle import _DEMO_BUNDLE_PATH, LogBundleAdapter
from src.models.incident import Incident


def _incident(**kwargs) -> Incident:
    defaults = dict(
        id="test-001",
        title="Checkout service timeout spike",
        description="504s on payment requests",
        severity="P1",
        metadata={},
    )
    defaults.update(kwargs)
    return Incident(**defaults)


def test_demo_bundle_path_resolves_to_real_file():
    """Regression test: previously there was no demo fallback at all, so
    log_agent always returned 'No log data available' on real submissions
    since the API route never sets context["log_bundle_path"]."""
    assert _DEMO_BUNDLE_PATH.exists()
    assert _DEMO_BUNDLE_PATH.suffix == ".zip"


@pytest.mark.asyncio
async def test_fetch_uses_demo_bundle_by_default_when_no_context_path_given():
    adapter = LogBundleAdapter()
    chunks = await adapter.fetch(_incident(), {})
    assert len(chunks) > 0
    assert all(c.source.startswith("log_bundle:") for c in chunks)


@pytest.mark.asyncio
async def test_fetch_prefers_explicit_context_path_over_demo_bundle(tmp_path):
    bundle = tmp_path / "custom.zip"
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.writestr("app.log", "2026-01-01 ERROR something broke\n")

    adapter = LogBundleAdapter()
    chunks = await adapter.fetch(_incident(), {"log_bundle_path": str(bundle)})
    assert len(chunks) == 1
    assert "something broke" in chunks[0].content
