"""HTTP routes for ingestion, compliance checking, and health."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

if TYPE_CHECKING:
    from app.services.dbmodel import User
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

logger = logging.getLogger(__name__)

# Image suffixes accepted by the opt-in OCR endpoint (mirrors app.rag.ocr.IMAGE_EXTS;
# kept literal here so this route module needs no OCR deps to import).
_OCR_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
_OCR_ACCEPT_EXTS = _OCR_IMAGE_EXTS | {".pdf"}


# --- Reports (T1.1/best-effort persistence) --------------------------------
def _persist_report(
    plan_text: Optional[str],
    source: str,
    result: Dict[str, Any],
    user_id: Optional[str] = None,
) -> None:
    """Best-effort write of one check result to the ``report`` table.

    Opens its own short-lived session (the existing ``SessionLocal`` pattern),
    derives status from the violations, and NEVER raises — a missing/unreachable
    DB must not break the check response. Failures are logged, not propagated.
    """
    try:
        from app.services.database import SessionLocal
        from app.services.report_model import Report, derive_status

        report = Report(
            plan_text=plan_text,
            source=source,
            summary=result.get("summary"),
            extracted_facts=result.get("extracted_facts"),
            violations=result.get("violations"),
            retrieved_rules=result.get("retrieved_rules"),
            status=derive_status(result.get("violations")),
            user_id=user_id,
        )
        db = SessionLocal()
        try:
            db.add(report)
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - persistence must not break the check
        logger.warning("report persistence skipped (database unavailable): %s", exc)


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


@router.post("/check", response_model=ComplianceResponse)
def check(
    body: ComplianceRequest,
    rag: RAGSystem = Depends(get_rag),
    # require_auth is a no-op (returns None) unless AUTH_REQUIRED is set, so this
    # both gates the endpoint when auth is on and hands us the user for the
    # persisted report's (nullable) user_id.
    actor: Optional["User"] = Depends(require_auth),
) -> ComplianceResponse:
    try:
        result = rag.check(body.plan_text, top_k=body.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _persist_report(
        plan_text=body.plan_text,
        source="check",
        result=result,
        user_id=actor.user_id if actor is not None else None,
    )
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
