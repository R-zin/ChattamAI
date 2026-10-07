"""HTTP routes for ingestion, compliance checking, and health."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

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
from app.schemas_reports import ReportOut

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
            status=derive_status(result.get("violations"), error=result.get("error")),
            user_id=user_id,
        )
        db = SessionLocal()
        try:
            db.add(report)
            db.commit()
            db.refresh(report)
            result["report_id"] = report.report_id
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - persistence must not break the check
        logger.warning("report persistence skipped (database unavailable): %s", exc)


@router.get("/reports", response_model=List[ReportOut])
def list_reports(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    actor: Optional["User"] = Depends(require_auth),
) -> List[ReportOut]:
    """Retrieve persisted compliance reports."""
    from app.services.database import SessionLocal
    from app.services.report_model import Report

    limit = max(1, min(100, limit))
    offset = max(0, offset)
    db = SessionLocal()
    try:
        q = db.query(Report)
        if actor is not None and get_settings().auth_required:
            q = q.filter(Report.user_id == actor.user_id)
        if status:
            q = q.filter(Report.status == status.lower())
        rows = q.order_by(Report.report_id.desc()).offset(offset).limit(limit).all()
        return [ReportOut.model_validate(r) for r in rows]
    except Exception as exc:
        logger.warning("failed to fetch reports: %s", exc)
        return []
    finally:
        db.close()


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    actor: Optional["User"] = Depends(require_auth),
) -> ReportOut:
    """Retrieve a single persisted compliance report by ID."""
    from app.services.database import SessionLocal
    from app.services.report_model import Report

    db = SessionLocal()
    try:
        q = db.query(Report).filter(Report.report_id == report_id)
        if actor is not None and get_settings().auth_required:
            q = q.filter(Report.user_id == actor.user_id)
        row = q.first()
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return ReportOut.model_validate(row)
    finally:
        db.close()


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: int,
    format: str = "pdf",
    actor: Optional["User"] = Depends(require_auth),
):
    """Export a compliance assessment as an official PDF or print-ready HTML."""
    from app.services.database import SessionLocal
    from app.services.pdf_report import (
        generate_compliance_html,
        generate_compliance_pdf,
    )
    from app.services.report_model import Report

    db = SessionLocal()
    try:
        q = db.query(Report).filter(Report.report_id == report_id)
        if actor is not None and get_settings().auth_required:
            q = q.filter(Report.user_id == actor.user_id)
        row = q.first()
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")

        fmt = format.lower().strip()
        if fmt == "html":
            html_content = generate_compliance_html(row)
            return Response(content=html_content, media_type="text/html")

        pdf_bytes = generate_compliance_pdf(row)
        filename = f"kbr_compliance_report_{report_id:06d}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


_KBR_ALLOWED_EXTS = {".pdf", ".txt", ".md", ".text"}
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MiB safety cap


@router.get("/kbr/documents", dependencies=[Depends(require_auth)])
def list_kbr_documents() -> List[Dict[str, Any]]:
    """List statutory rules documents currently present in KBR_DATA_DIR."""
    from datetime import datetime

    data_dir = get_settings().kbr_data_dir
    if not data_dir.exists():
        return []
    docs = []
    for p in sorted(data_dir.iterdir()):
        if (
            p.is_file()
            and not p.name.startswith(".")
            and p.suffix.lower() in _KBR_ALLOWED_EXTS
        ):
            docs.append(
                {
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "modified_at": datetime.fromtimestamp(
                        p.stat().st_mtime
                    ).isoformat(),
                    "ext": p.suffix.lower(),
                }
            )
    return docs


@router.post("/kbr/upload", dependencies=[Depends(require_auth)])
def upload_kbr_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a new KBR statutory rule document (PDF or TXT) into KBR_DATA_DIR."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _KBR_ALLOWED_EXTS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a .pdf, .txt, or .md rule document.",
        )
    content = file.file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum upload size is 25 MB.",
        )
    data_dir = get_settings().kbr_data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / Path(file.filename or "uploaded_rule.txt").name
    with open(target, "wb") as f:
        f.write(content)
    return {
        "filename": target.name,
        "size_bytes": len(content),
        "status": "uploaded",
        "message": "File uploaded to KBR corpus. Run /api/ingest to index it.",
    }


def get_rag() -> RAGSystem:
    from app.main import app

    rag: Optional[RAGSystem] = getattr(app.state, "rag", None)
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG system not initialised.")
    return rag


@router.get("/rules/search")
def search_rules(
    q: str,
    limit: int = 10,
    rag: RAGSystem = Depends(get_rag),
) -> List[Dict[str, Any]]:
    """Direct lexical/semantic search over the indexed Kerala Building Rules chunks."""
    limit = max(1, min(50, limit))
    store = getattr(rag, "_store", None)
    if not store or store.size == 0:
        return []
    results = store.similarity_search(q, k=limit)
    out = []
    for text, meta, score in results:
        out.append(
            {
                "rule_id": meta.get("rule_id") if isinstance(meta, dict) else None,
                "source": meta.get("source") if isinstance(meta, dict) else None,
                "chunk": meta.get("chunk") if isinstance(meta, dict) else None,
                "excerpt": text or (meta.get("text") if isinstance(meta, dict) else ""),
                "score": round(float(score), 4),
            }
        )
    return out


@router.get("/health", response_model=HealthResponse)
def health(rag: RAGSystem = Depends(get_rag)) -> HealthResponse:
    return HealthResponse(
        status="ok" if (rag.embeddings_ready and rag.llm_ready) else "degraded",
        index_size=rag.index_size,
        embeddings_ready=rag.embeddings_ready,
        llm_ready=rag.llm_ready,
        llm_provider=getattr(rag, "llm_provider", None),
        llm_model=getattr(rag, "llm_model", None),
    )


class IngestRequest(BaseModel):
    data_dir: Optional[str] = None
    rebuild: bool = False


@router.post(
    "/setmodel",
    response_model=SetModelResponse,
    dependencies=[Depends(require_auth)],
)
async def set_model(data: SetModelRequest) -> SetModelResponse:
    from app.main import app

    app.state.active_model = data.model_provider
    logger.info("Active model updated to %s", data.model_provider)
    return SetModelResponse(status=f"Active model set to {data.model_provider}")


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
    except (RuntimeError, ValueError) as exc:
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
    actor: Optional["User"] = Depends(require_auth),
) -> ComplianceResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".text", ".pdf"}:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a .txt, .md, or .pdf plan.",
        )
    content = file.file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum upload size is 25 MB.",
        )
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        result = rag.check_plan_file(tmp_path, top_k=top_k)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)
    _persist_report(
        plan_text=f"Uploaded file: {file.filename or 'plan'}",
        source="upload",
        result=result,
        user_id=actor.user_id if actor is not None else None,
    )
    return ComplianceResponse(**result)


@router.post(
    "/check/plan-ocr",
    response_model=ComplianceResponse,
    dependencies=[Depends(require_auth)],
)
def check_plan_ocr(
    file: UploadFile = File(...),
    top_k: Optional[int] = None,
    layout: bool = True,
    rag: RAGSystem = Depends(get_rag),
    actor: Optional["User"] = Depends(require_auth),
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
        image_to_layout_text,
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

    content = file.file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum upload size is 25 MB.",
        )
    raw_path: Optional[Path] = None
    txt_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            raw_path = Path(tmp.name)
        try:
            if suffix == ".pdf":
                ocr_text = pdf_images_to_text(raw_path)
            elif layout:
                ocr_text, layout_note = image_to_layout_text(
                    raw_path, fallback_to_plain=True
                )
                if layout_note:
                    logger.info("OCR layout fallback: %s", layout_note)
            else:
                ocr_text = image_to_text(raw_path)
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

        _persist_report(
            plan_text=normalised,
            source="ocr",
            result=result,
            user_id=actor.user_id if actor is not None else None,
        )
        return ComplianceResponse(**result)
    finally:
        if raw_path is not None:
            raw_path.unlink(missing_ok=True)
        if txt_path is not None:
            txt_path.unlink(missing_ok=True)
