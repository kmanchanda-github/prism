"""Executive PDF — plain-language summary for leadership. Phase 2 implementation."""
import tempfile
from pathlib import Path


async def generate(analysis_id: str, version) -> str:
    from weasyprint import HTML

    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><style>
      body {{ font-family: Georgia, serif; margin: 60px; color: #222; }}
      h1 {{ font-size: 1.8em; }} h2 {{ color: #444; margin-top: 2em; }}
      .impact {{ background: #fff3cd; padding: 16px; border-radius: 4px; }}
    </style></head><body>
      <h1>Incident Analysis Summary</h1>
      <h2>What Happened</h2>
      <div class="impact"><p>{version.root_cause}</p></div>
      <h2>Immediate Resolution</h2>
      <p>{version.workaround}</p>
      <h2>Next Steps</h2>
      <ul>{"".join(f"<li>{a['title']}</li>" for a in version.recommended_actions)}</ul>
    </body></html>
    """
    out = Path(tempfile.mkdtemp()) / f"{analysis_id}_executive.pdf"
    HTML(string=html).write_pdf(str(out))
    return str(out)
