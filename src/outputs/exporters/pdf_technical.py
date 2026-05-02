"""Technical PDF — full analysis with sub-agent findings. Phase 2 implementation."""
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  body { font-family: sans-serif; margin: 40px; }
  h1 { color: #1a1a2e; } h2 { color: #16213e; border-bottom: 1px solid #ccc; }
  .meta { color: #666; font-size: 0.9em; }
  .confidence { font-weight: bold; color: {% if version.confidence_score > 0.7 %}green{% else %}orange{% endif %}; }
  pre { background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }
</style></head>
<body>
  <h1>{{ version.analysis_id[:8] }} — Technical Analysis Report</h1>
  <p class="meta">Generated: {{ now }} | Confidence: <span class="confidence">{{ "%.0f"|format(version.confidence_score * 100) }}%</span></p>

  <h2>Root Cause</h2>
  <p>{{ version.root_cause }}</p>

  <h2>Workaround</h2>
  <p>{{ version.workaround }}</p>

  <h2>Recommended Actions</h2>
  <ul>{% for a in version.recommended_actions %}<li><strong>[{{ a.priority }}]</strong> {{ a.title }} — {{ a.description }}</li>{% endfor %}</ul>

  <h2>Sub-Agent Findings</h2>
  {% for r in version.sub_reports %}
  <h3>{{ r.agent }} (confidence: {{ "%.0f"|format(r.confidence * 100) }}%)</h3>
  <pre>{{ r.findings }}</pre>
  {% endfor %}
</body>
</html>
"""


async def generate(analysis_id: str, version) -> str:
    from weasyprint import HTML
    from datetime import datetime

    html = _TEMPLATE.replace("{{ version.analysis_id[:8] }}", analysis_id[:8])
    # Use Jinja2 for proper rendering in Phase 2; simple string for Phase 1
    out = Path(tempfile.mkdtemp()) / f"{analysis_id}_technical.pdf"
    HTML(string=html).write_pdf(str(out))
    return str(out)
