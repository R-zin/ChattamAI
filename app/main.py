"""FastAPI application entrypoint.

Boots the RAG system on startup and exposes the compliance API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes import auth as auth_routes
from app.routes import rag as rag_routes

_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.rag.system import RAGSystem

    # Build the system eagerly so readiness is known at startup.
    app.state.rag = RAGSystem()

    # Create auth/DB tables on startup. Best-effort: a missing/unreachable DB is
    # logged and never breaks the RAG boot (the RAG path does not use the DB).
    from app.services.database_init import init_db_safe

    init_db_safe()

    yield


app = FastAPI(
    title="ChattamAI — Kerala Building Rules Compliance RAG",
    description=(
        "Upload building plans and compare them against the Kerala Building "
        "Rules using a LangGraph-orchestrated RAG pipeline."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_routes.router)
app.include_router(auth_routes.auth_router)

# Mount frontend assets if the built frontend distribution exists
if (_DIST_DIR / "assets").exists():
    app.mount(
        "/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="assets"
    )


@app.get("/")
def root(request: Request):
    accept = request.headers.get("accept", "")
    index_file = _DIST_DIR / "index.html"
    if "text/html" in accept and index_file.exists():
        return FileResponse(str(index_file))
    return {
        "service": "ChattamAI RAG",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "ingest": "/api/ingest",
            "check": "/api/check",
        },
    }


@app.get("/{full_path:path}")
def spa_fallback(request: Request, full_path: str):
    # Serve static root files if present (e.g. vite.svg, favicon.ico)
    target = _DIST_DIR / full_path
    if target.is_file():
        return FileResponse(str(target))
    # Otherwise fallback to index.html for SPA client-side routing
    index_file = _DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="Not found")
