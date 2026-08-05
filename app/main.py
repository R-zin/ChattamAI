"""FastAPI application entrypoint.

Boots the RAG system on startup and exposes the compliance API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import auth as auth_routes
from routes import rag as rag_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    from rag.system import RAGSystem

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


@app.get("/")
def root():
    return {
        "service": "ChattamAI RAG",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "ingest": "/api/ingest",
            "check": "/api/check",
        },
    }
