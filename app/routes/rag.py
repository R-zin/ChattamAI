"""HTTP routes for ingestion, compliance checking, and health."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.rag.system import RAGSystem
from app.schemas import (
    ComplianceRequest,
    ComplianceResponse,
    HealthResponse,
    IngestResponse,
)

router = APIRouter(prefix="/api", tags=["rag"])


def get_rag() -> RAGSystem:
    from app.main import app

    rag: Optional[RAGSystem] = getattr(app.state, "rag", None)
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG system not initialised.")
    return rag


@router.get("/health", response_model=HealthResponse)
def health(rag: RAGSystem = Depends(get_rag)) -> HealthResponse:
    return HealthResponse(
        status="ok" if (rag.embeddings_ready and rag.llm_ready) else "degraded",
        index_size=rag.index_size,
        embeddings_ready=rag.embeddings_ready,
        llm_ready=rag.llm_ready,
    )


class IngestRequest(BaseModel):
    data_dir: Optional[str] = None


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    body: IngestRequest = IngestRequest(), rag: RAGSystem = Depends(get_rag)
) -> IngestResponse:
    try:
        result = rag.ingest(body.data_dir)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return IngestResponse(**result)


@router.post("/check", response_model=ComplianceResponse)
def check(
    body: ComplianceRequest, rag: RAGSystem = Depends(get_rag)
) -> ComplianceResponse:
    try:
        result = rag.check(body.plan_text, top_k=body.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ComplianceResponse(**result)


@router.post("/check/upload", response_model=ComplianceResponse)
def check_upload(
    file: UploadFile = File(...),
    top_k: Optional[int] = None,
    rag: RAGSystem = Depends(get_rag),
) -> ComplianceResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".text", ".pdf"}:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a .txt, .md, or .pdf plan.",
        )
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)
    try:
        result = rag.check_plan_file(tmp_path, top_k=top_k)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)
    return ComplianceResponse(**result)
