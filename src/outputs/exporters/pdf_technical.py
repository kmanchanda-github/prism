"""Technical PDF — full analysis with sub-agent findings."""
import tempfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment

_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  body { font-family: Arial, sans-serif; margin: 48px; color: #1a1a2e; }
  h1 { color: #1a1a2e; font-size: 1.5em; margin-bottom: 4px; }
  h2 { color: #16213e; font-size: 1.1em; border-bottom: 1px solid #dde; padding-bottom: 4px; margin-top: 28px; }
  h3 { color: #333; font-size: 0.95em; margin-bottom: 4px; }
  .meta { color: #666; font-size: 0.85em; margin-bottom: 24px; }
  .confidence-bar { display: inline-block; height: 8px; border-radius: 4px; vertical-align: middle; margin-right: 6px; }
  .high { background: #22c55e; } .med { background: #f59e0b; } .low { background: #ef4444; }
  .badge { display: inline-block; padding: 1px 7px; border-radius: 3px; font-size: 0.75em; font-weight: bold; margin-right: 6px; }
  .high-badge { background: #fee2e2; color: #b91c1c; }
  .medium-badge { background: #fef9c3; color: #92400e; }
  .low-badge { background: #f3f4f6; color: #374151; }
  pre { background: #f6f8fa; padding: 12px; border-radius: 4px; font-size: 0.78em;
        white-space: pre-wrap; word-break: break-word; border-left: 3px solid #6366f1; }
  .agent-block { margin-bottom: 24px; }
  .conf-label { font-size: 0.8em; color: #555; }
  ul { padding-left: 20px; }
  li { margin-bottom: 6px; font-size: 0.9em; }
  footer { margin-top: 48px; font-size: 0.75em; color: #aaa; border-top: 1px solid #eee; padding-top: 8px; }
</style></head>
<body>
  <h1>{{ analysis_id }} — Technical Incident Analysis</h1>
  <p class="meta">
    Generated: {{ now }} &nbsp;|&nbsp;
    Overall Confidence:
    <span class="confidence-bar {{ 'high' if confidence_pct >= 70 else ('med' if confidence_pct >= 40 else 'low') }}"
          style="width:{{ confidence_pct }}px"></span>
    {{ confidence_pct }}%
  </p>

  <h2>Root Cause</h2>
  <p>{{ root_cause }}</p>

  <h2>Workaround / Immediate Resolution</h2>
  <p>{{ workaround }}</p>

  <h2>Recommended Actions</h2>
  <ul>
  {% for a in recommended_actions %}
    <li>
      <span class="badge {{ a.priority }}-badge">{{ a.priority | upper }}</span>
      <strong>{{ a.title }}</strong> — {{ a.description }}
    </li>
  {% endfor %}
  </ul>

  <h2>Sub-Agent Findings</h2>
  {% for r in sub_reports %}
  <div class="agent-block">
    <h3>{{ r.agent }}</h3>
    <p class="conf-label">
      Confidence:
      <span class="confidence-bar {{ 'high' if r.conf_pct >= 70 else ('med' if r.conf_pct >= 40 else 'low') }}"
            style="width:{{ r.conf_pct }}px"></span>
      {{ r.conf_pct }}%
      &nbsp;|&nbsp; Sources: {{ r.sources }}
    </p>
    <pre>{{ r.findings }}</pre>
  </div>
  {% endfor %}

  <footer>Prism AI Incident Analysis &nbsp;|&nbsp; {{ analysis_id }}</footer>
</body>
</html>
"""


async def generate(analysis_id: str, version) -> str:
    from weasyprint import HTML

    env = Environment(autoescape=True)
    tmpl = env.from_string(_TEMPLATE)

    sub_reports = []
    for r in (version.sub_reports or []):
        conf = r.get("confidence", 0) if isinstance(r, dict) else getattr(r, "confidence", 0)
        sub_reports.append({
            "agent": r.get("agent") if isinstance(r, dict) else r.agent,
            "findings": r.get("findings") if isinstance(r, dict) else r.findings,
            "conf_pct": round(conf * 100),
            "sources": ", ".join(r.get("sources_used", []) if isinstance(r, dict) else r.sources_used) or "—",
        })

    actions = version.recommended_actions or []

    html = tmpl.render(
        analysis_id=analysis_id[:8],
        now=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        confidence_pct=round(version.confidence_score * 100),
        root_cause=version.root_cause or "—",
        workaround=version.workaround or "—",
        recommended_actions=actions,
        sub_reports=sub_reports,
    )

    out = Path(tempfile.mkdtemp()) / f"{analysis_id}_technical.pdf"
    HTML(string=html).write_pdf(str(out))
    return str(out)
