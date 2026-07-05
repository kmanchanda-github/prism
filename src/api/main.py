from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import admin, analysis, actions, chat, evaluation, export, webhooks
from src.core.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="Prism",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(actions.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api")
app.include_router(webhooks.router)
app.include_router(admin.router)

# Serve React SPA (built output) — must be last
_ui_dist = Path(__file__).parent.parent.parent / "ui" / "dist"
if _ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_ui_dist / "assets")), name="ui-assets")

    # Client-side routes (e.g. /analysis/{id}) don't correspond to real files —
    # StaticFiles(html=True) alone 404s on direct navigation/refresh since it
    # only serves index.html for the exact root path. Fall back to index.html
    # for anything not already matched by an API route or a static asset, so
    # React Router can take over and render the right page.
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(str(_ui_dist / "index.html"))
