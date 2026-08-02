"""HTTP routes for ingestion, compliance checking, and health."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.rag.system import RAGSystem
from app.routes.auth import require_auth
from app.schemas import (
    ComplianceRequest,
    ComplianceResponse,
    HealthResponse,
    IngestResponse,
    SetModelRequest,
    SetModelResponse,
)

router = APIRouter(prefix="/api", tags=["rag"])

# Image suffixes accepted by the opt-in OCR endpoint (mirrors app.rag.ocr.IMAGE_EXTS;
# kept literal here so this route module needs no OCR deps to import).
_OCR_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
_OCR_ACCEPT_EXTS = _OCR_IMAGE_EXTS | {".pdf"}


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
    rebuild: bool = False


@router.post("/setmodel", response_model=SetModelResponse)
async def set_model(data: SetModelRequest) -> SetModelResponse:
    # Provider/model switching is not implemented yet; acknowledge the request.
    return SetModelResponse(status="ok")


@router.post(
    "/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(require_auth)],
)
def ingest(
    body: IngestRequest = IngestRequest(), rag: RAGSystem = Depends(get_rag)
) -> IngestResponse:
    try:
        result = rag.ingest(body.data_dir, rebuild=body.rebuild)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return IngestResponse(**result)


@router.post(
    "/check",
    response_model=ComplianceResponse,
    dependencies=[Depends(require_auth)],
)
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


@router.post(
    "/check/plan-ocr",
    response_model=ComplianceResponse,
    dependencies=[Depends(require_auth)],
)
def check_plan_ocr(
    file: UploadFile = File(...),
    top_k: Optional[int] = None,
    rag: RAGSystem = Depends(get_rag),
) -> ComplianceResponse:
    """Opt-in OCR compliance check for image / image-only-PDF floor plans.

    The plan image is OCR'd to plain text, normalised, written to a temp ``.txt``
    file, and run through the existing ``RAGSystem.check_plan_file`` path so the
    downstream ``Path -> str`` seam and the ``check`` contract are unchanged.

    Gating (in order):
      * 415 — extension is not an accepted image/image-PDF suffix.
      * 503 — OCR is disabled (``OCR_ENABLED`` unset) or the OCR deps / Tesseract
        binary are unavailable on this box.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _OCR_ACCEPT_EXTS:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. Upload a .png, .jpg, .jpeg, .tiff, .tif, "
                ".bmp, .webp, or image-only .pdf plan."
            ),
        )
    if not get_settings().ocr_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR is disabled. Set OCR_ENABLED=true and install Tesseract "
                "(see plan.md Phase 3) to check image/image-PDF plans."
            ),
        )

    from app.rag.ocr import (  # lazy: keeps this module importable without OCR deps
        image_to_text,
        normalize_ocr_text,
        ocr_available,
        pdf_images_to_text,
    )

    if not ocr_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "OCR is unavailable on this server (missing Pillow/pytesseract/"
                "PyMuPDF or the Tesseract binary)."
            ),
        )

    raw_path: Optional[Path] = None
    txt_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file.file.read())
            raw_path = Path(tmp.name)
        try:
            ocr_text = (
                pdf_images_to_text(raw_path)
                if suffix == ".pdf"
                else image_to_text(raw_path)
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:  # noqa: BLE001 - surface unreadable uploads
            raise HTTPException(status_code=400, detail=f"OCR failed: {exc}")

        normalised = normalize_ocr_text(ocr_text)
        if not normalised:
            raise HTTPException(
                status_code=422,
                detail="OCR produced no usable text from the uploaded plan.",
            )

        # Re-enter the shared Path -> str seam via a temp .txt so the existing
        # check_plan_file / load_plan_text contract is reused unchanged.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(normalised)
            txt_path = Path(tmp.name)

        try:
            result = rag.check_plan_file(txt_path, top_k=top_k)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return ComplianceResponse(**result)
    finally:
        if raw_path is not None:
            raw_path.unlink(missing_ok=True)
        if txt_path is not None:
            txt_path.unlink(missing_ok=True)
