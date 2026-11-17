"""First-boot data setup: seed the KBR corpus and build the rule index.

A volume mounted at the data directory (Azure Container Apps EmptyDir /
AzureFile) hides whatever the image baked there, so the KBR documents are
shipped in a separate seed directory and copied in on first boot. If the
index is then empty, it is built in the background so the server can accept
liveness probes immediately while ``/api/health/ready`` reports 503 until
indexing finishes.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Optional

from app.config import BASE_DIR, get_settings

logger = logging.getLogger(__name__)

_SEED_EXTS = {".txt", ".md", ".pdf"}

# Files that earlier images seeded into the KBR data directory and that must no
# longer be indexed. Maps file name -> a marker that must appear in the file's
# opening bytes, so a user upload that merely shares the name is left alone.
# ``sample_kbr_excerpt.txt`` was a synthetic test fixture, not gazetted text.
RETIRED_KBR_FILES = {
    "sample_kbr_excerpt.txt": "SAMPLE / SUBSET -- KERALA MUNICIPALITY BUILDING RULES",
}


def _truthy(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def seed_dir() -> Path:
    """Where the image keeps its pristine copy of the KBR documents."""
    explicit = os.getenv("KBR_SEED_DIR", "").strip()
    return Path(explicit) if explicit else BASE_DIR / "seed" / "kbr"


def seed_kbr_documents(
    target_dir: Path, source_dir: Optional[Path] = None
) -> list[str]:
    """Copy seed KBR files into ``target_dir`` when it holds no documents.

    Never overwrites existing files, so user uploads and edits survive. Returns
    the names copied (empty when nothing was needed or no seed exists).
    """
    source = Path(source_dir) if source_dir is not None else seed_dir()
    target = Path(target_dir)
    if not source.is_dir():
        return []
    try:
        if source.resolve() == target.resolve():
            return []
    except OSError:
        return []

    target.mkdir(parents=True, exist_ok=True)
    if any(p.is_file() and p.suffix.lower() in _SEED_EXTS for p in target.iterdir()):
        return []

    copied: list[str] = []
    for src in sorted(source.iterdir()):
        if not src.is_file() or src.suffix.lower() not in _SEED_EXTS:
            continue
        dest = target / src.name
        if dest.exists():
            continue
        shutil.copy2(src, dest)
        copied.append(src.name)
    if copied:
        logger.info("Seeded %d KBR document(s) into %s", len(copied), target)
    return copied


def remove_retired_kbr_documents(target_dir: Path) -> list[str]:
    """Delete retired seed files (see ``RETIRED_KBR_FILES``) from ``target_dir``.

    A file is removed only when its opening bytes carry the expected marker.
    Returns the names removed. Never raises.
    """
    removed: list[str] = []
    for name, marker in RETIRED_KBR_FILES.items():
        path = Path(target_dir) / name
        try:
            if not path.is_file():
                continue
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                head = fh.read(4096)
            if marker not in head:
                logger.info("Keeping %s: content is not the retired seed file", path)
                continue
            path.unlink()
            removed.append(name)
            logger.warning("Removed retired non-official KBR file %s", path)
        except OSError:
            logger.exception("Could not remove retired KBR file %s", path)
    return removed


def auto_ingest_if_empty(rag) -> Optional[dict]:
    """Build the index when it is empty and embeddings are usable.

    Also purges retired seed files left on a persistent data volume by older
    images; when any were removed from a populated index, the index is rebuilt
    so their chunks stop being retrieved.

    Returns the ingest summary, or None when skipped. Never raises: a failure is
    logged and surfaces through ``/api/health`` (empty index).
    """
    if not _truthy("AUTO_INGEST", True):
        logger.info("AUTO_INGEST disabled; skipping startup ingest")
        return None
    removed = remove_retired_kbr_documents(get_settings().kbr_data_dir)
    if not getattr(rag, "embeddings_ready", False):
        if removed:
            logger.warning(
                "Retired KBR files removed but embeddings are not configured; "
                "call /api/ingest with rebuild=true once they are"
            )
        else:
            logger.warning("Skipping startup ingest: embeddings are not configured")
        return None
    if removed and rag.index_size > 0:
        try:
            logger.info("Rebuilding index after removing %s", ", ".join(removed))
            result = rag.ingest(rebuild=True)
            logger.info("Index rebuild complete: %s", result)
            return result
        except Exception:  # noqa: BLE001 - boot must survive a failed ingest
            logger.exception("Index rebuild failed; call /api/ingest to retry")
            return None
    if rag.index_size > 0:
        logger.info("Index already has %d chunks; skipping ingest", rag.index_size)
        return None
    try:
        seed_kbr_documents(get_settings().kbr_data_dir)
        logger.info("Index is empty; ingesting KBR documents")
        result = rag.ingest()
        logger.info("Startup ingest complete: %s", result)
        return result
    except Exception:  # noqa: BLE001 - boot must survive a failed ingest
        logger.exception("Startup ingest failed; call /api/ingest to retry")
        return None


def start_background_ingest(rag) -> threading.Thread:
    """Run :func:`auto_ingest_if_empty` without blocking server startup."""
    thread = threading.Thread(
        target=auto_ingest_if_empty,
        args=(rag,),
        name="startup-ingest",
        daemon=True,
    )
    thread.start()
    return thread
