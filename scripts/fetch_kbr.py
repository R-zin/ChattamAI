"""Config-URL downloader for the Kerala Building Rules (KBR) corpus.

Fetches one or more KBR source documents (PDF / HTML / plain text) into the
local ``KBR_DATA_DIR`` so the ingestion pipeline (``app.rag.ingestion``) can
load and chunk them. For every saved document it also writes a small
``<name>.provenance.json`` sidecar recording origin, fetch time and size, so
chunk metadata can later cite where a rule came from.

Offline / safety contract (shared constraint for this repo):
  * This module performs **no** network access at import time.
  * Downloading only happens when you run the CLI:
    ``python -m scripts.fetch_kbr --url <URL>`` (or set ``KBR_SOURCE_URLS``).
  * Only the standard library is used -- ``urllib.request`` for fetching and
    ``html.parser`` for tag-stripping. No new dependencies are introduced.

Configuration (read from the environment, noting each for the coordinator):
  * ``KBR_SOURCE_URLS`` -- comma-separated list of document URLs. This is a
    placeholder source list; there is no single canonical machine-readable
    KBR URL, so the default is empty and you must supply real URLs via the
    env var or ``--url``. (Coordinator: wire this into ``Settings`` later.)
  * ``KBR_DATA_DIR`` -- where fetched documents are written. Default
    ``./data/kbr``, matching ``Settings.kbr_data_dir``.
  * ``KBR_FETCH_TIMEOUT`` -- per-request timeout in seconds (default 15).
  * ``KBR_FETCH_MAX_BYTES`` -- max bytes accepted per document (default
    20 MiB); larger responses are truncated and flagged in provenance.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Default fetch behaviour (overridable via env; see module docstring).
_DEFAULT_TIMEOUT_S = 15
_DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # 20 MiB safety cap per document.
_USER_AGENT = "ChattamAI-KBR-fetcher/1.0 (+offline-first; stdlib urllib)"

# Suffixes we write into the data dir based on the detected content type.
_TEXT_SUFFIX = ".txt"
_PDF_SUFFIX = ".pdf"


class _TagStripper(HTMLParser):
    """Minimal dependency-free HTML-to-text converter.

    Collects only the character data between tags and inserts newlines around
    block-level elements so the output keeps a readable, line-based structure
    for downstream chunking. Scripts/styles/tooltips are dropped.
    """

    _BLOCK_TAGS = {
        "p",
        "br",
        "div",
        "section",
        "article",
        "tr",
        "table",
        "thead",
        "tbody",
        "li",
        "ul",
        "ol",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "footer",
        "blockquote",
        "pre",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "head", "title", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buf: List[str] = []
        self._skip_depth = 0

    # -- parser callbacks ---------------------------------------------------
    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: D102
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS:
            self._newline()

    def handle_endtag(self, tag: str) -> None:  # noqa: D102
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BLOCK_TAGS:
            self._newline()

    def handle_data(self, data: str) -> None:  # noqa: D102
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._buf.append(text)

    # -- helpers ------------------------------------------------------------
    def _newline(self) -> None:
        self._buf.append("\n")

    def text(self) -> str:
        """Return the stripped plain text with tidy line breaks."""
        joined: List[str] = []
        newline_pending = False
        for part in self._buf:
            if part == "\n":
                newline_pending = True
                continue
            if newline_pending:
                joined.append("\n")
                newline_pending = False
            joined.append(part)
        out = "".join(joined)
        # Collapse 2+ blank lines to a single blank line, trim trailing space.
        cleaned: List[str] = []
        blank = 0
        for ln in (x.rstrip() for x in out.splitlines()):
            if ln.strip():
                blank = 0
                cleaned.append(ln)
            else:
                blank += 1
                if blank <= 1:
                    cleaned.append("")
        return "\n".join(cleaned).strip() + "\n"


def html_to_text(html: str) -> str:
    """Strip HTML markup to readable plain text (stdlib only)."""
    parser = _TagStripper()
    parser.feed(html)
    parser.close()
    return parser.text()


def parse_source_urls(cli_urls: Optional[Sequence[str]]) -> List[str]:
    """Resolve the list of source URLs from CLI args then the environment.

    ``--url`` arguments win; otherwise the comma-separated ``KBR_SOURCE_URLS``
    env var is used. Duplicates are removed, order preserved.
    """
    urls: List[str] = []
    for u in cli_urls or []:
        urls.extend(part for part in str(u).split(","))
    if not any(urls):
        env = os.getenv("KBR_SOURCE_URLS", "")
        urls.extend(env.split(","))

    seen = set()
    resolved: List[str] = []
    for raw in urls:
        u = raw.strip()
        if u and u not in seen and u.lower().startswith(("http://", "https://")):
            seen.add(u)
            resolved.append(u)
    return resolved


def _resolve_settings() -> Tuple[Path, float, int]:
    """Read ``KBR_DATA_DIR``/timeout/max-bytes from env with safe defaults."""
    data_dir = Path(os.getenv("KBR_DATA_DIR", "./data/kbr")).expanduser()
    try:
        timeout = float(os.getenv("KBR_FETCH_TIMEOUT") or _DEFAULT_TIMEOUT_S)
    except ValueError:
        timeout = float(_DEFAULT_TIMEOUT_S)
    try:
        max_bytes = int(os.getenv("KBR_FETCH_MAX_BYTES") or _DEFAULT_MAX_BYTES)
    except ValueError:
        max_bytes = _DEFAULT_MAX_BYTES
    return data_dir, timeout, max_bytes


def _filename_for(url: str, content_type: str) -> str:
    """Derive a stable output filename from the URL path and content type."""
    path = urlparse(url).path or ""
    base = Path(path).name or "kbr_document"
    # Strip a query/hash leftover and any existing known suffix.
    base = base.split("?")[0].split("#")[0] or "kbr_document"
    name = Path(base).stem or "kbr_document"
    safe = "".join(c if (c.isalnum() or c in "-_ .") else "_" for c in name).strip()
    if not safe:
        safe = "kbr_document"
    suffix = _PDF_SUFFIX if "pdf" in content_type.lower() else _TEXT_SUFFIX
    return f"{safe}{suffix}"


def _is_probably_pdf(url: str, content_type: str, body: bytes) -> bool:
    """Decide whether the payload is a PDF (type header, URL, or magic bytes)."""
    ct = content_type.lower()
    if "pdf" in ct:
        return True
    if urlparse(url).path.lower().endswith(_PDF_SUFFIX):
        return True
    return body.startswith(b"%PDF")


def _decode_and_maybe_strip(
    url: str, content_type: str, body: bytes
) -> Tuple[bytes, str]:
    """Return ``(payload_bytes, kind)``; HTML is converted to plain text."""
    if _is_probably_pdf(url, content_type, body):
        return body, "pdf"

    # Treat everything else as text; strip tags only when it looks like HTML.
    charset = "utf-8"
    for token in content_type.split(";"):
        token = token.strip()
        if token.lower().startswith("charset="):
            charset = token.split("=", 1)[1].strip() or "utf-8"
    decoded = body.decode(charset, errors="replace")
    if "html" in content_type.lower() or "<html" in decoded[:500].lower():
        text = html_to_text(decoded)
    else:
        text = decoded
    return text.encode("utf-8"), "text"


def _write_provenance(
    doc_path: Path,
    source_url: str,
    num_bytes: int,
    content_type: str,
    truncated: bool,
) -> Path:
    """Write/overwrite the ``<doc>.provenance.json`` sidecar for one document."""
    record = {
        "source_url": source_url,
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "bytes": num_bytes,
        "content_type": content_type,
        "file_name": doc_path.name,
        "truncated": truncated,
    }
    prov_path = doc_path.with_name(doc_path.name + ".provenance.json")
    with open(prov_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return prov_path


def fetch_one(url: str, data_dir: Path, timeout: float, max_bytes: int) -> Path:
    """Download a single source into ``data_dir`` and write its provenance.

    Returns the path of the saved document. Raises a clear ``RuntimeError``
    when the source is unreachable or yields no usable content.
    """
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as resp:  # noqa: S310
            content_type = resp.headers.get("Content-Type", "text/plain")
            # Read at most max_bytes + 1 so we can detect truncation.
            raw = resp.read(max_bytes + 1)
    except HTTPError as exc:
        raise RuntimeError(
            f"HTTP {exc.code} while fetching {url}: {exc.reason}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc
    except OSError as exc:  # network unreachable, DNS, TLS, timeout, etc.
        raise RuntimeError(f"Network error while fetching {url}: {exc}") from exc

    if raw is None or len(raw) == 0:
        raise RuntimeError(f"Empty response body from {url}")

    truncated = len(raw) > max_bytes
    if truncated:
        raw = raw[:max_bytes]

    payload, kind = _decode_and_maybe_strip(url, content_type, raw)
    if kind == "text" and not payload.strip():
        raise RuntimeError(f"No readable text extracted from {url}")

    data_dir.mkdir(parents=True, exist_ok=True)
    doc_path = data_dir / _filename_for(url, content_type)
    # Avoid clobbering earlier fetches of different types in one run.
    if doc_path.exists():
        stem, suffix = doc_path.stem, doc_path.suffix
        counter = 2
        while doc_path.exists():
            doc_path = data_dir / f"{stem}-{counter}{suffix}"
            counter += 1

    doc_path.write_bytes(payload)
    prov_path = _write_provenance(doc_path, url, len(payload), content_type, truncated)

    note = " (TRUNCATED to cap)" if truncated else ""
    print(
        f"[fetch_kbr] saved {len(payload):,} bytes -> {doc_path.name}"
        f" [{kind}]{note}; provenance -> {prov_path.name}"
    )
    return doc_path


def run(urls: Sequence[str], data_dir: Path, timeout: float, max_bytes: int) -> int:
    """Fetch every URL; continue past individual failures. Returns exit code."""
    if not urls:
        print(
            "[fetch_kbr] No source URLs provided.\n"
            "  Pass --url <URL> (repeatable) or set the KBR_SOURCE_URLS env var\n"
            "  to a comma-separated list. Nothing was downloaded.",
            file=sys.stderr,
        )
        return 2

    failures = 0
    for url in urls:
        try:
            fetch_one(url, data_dir, timeout, max_bytes)
        except RuntimeError as exc:
            failures += 1
            print(f"[fetch_kbr] ERROR: {exc}", file=sys.stderr)
    if failures:
        print(f"[fetch_kbr] {failures}/{len(urls)} source(s) failed.", file=sys.stderr)
        return 1
    print(f"[fetch_kbr] All {len(urls)} source(s) fetched into {data_dir}")
    return 0


def maybe_ingest(data_dir: Path) -> int:
    """Optionally (re)build the FAISS index after download.

    Guarded so it never runs at import and degrades gracefully when the
    embedding credentials (``OPENAI_API_KEY``) are absent.
    """
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "[fetch_kbr] --ingest requested but OPENAI_API_KEY is not set; "
            "skipping index build (documents are already saved to "
            f"{data_dir}).",
            file=sys.stderr,
        )
        return 0
    try:
        from app.rag.system import RAGSystem
    except Exception as exc:  # pragma: no cover - app optional at CLI time
        print(f"[fetch_kbr] --ingest could not load the app: {exc}", file=sys.stderr)
        return 1
    try:
        result = RAGSystem().ingest(str(data_dir))
    except RuntimeError as exc:
        print(f"[fetch_kbr] --ingest failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"[fetch_kbr] ingest complete: {result.get('documents')} documents, "
        f"{result.get('chunks')} chunks, index size {result.get('index_size')}."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser (separated for testability)."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.fetch_kbr",
        description=(
            "Download Kerala Building Rules source documents (PDF/HTML/text) "
            "into KBR_DATA_DIR and record a .provenance.json sidecar for each. "
            "Network access happens only when you run this command."
        ),
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        default=None,
        metavar="URL",
        help=(
            "Source URL to fetch (repeatable; also accepts comma-separated "
            "values). Overrides the KBR_SOURCE_URLS env var when given."
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        metavar="DIR",
        help="Output directory (default: KBR_DATA_DIR env or ./data/kbr).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Per-request timeout in seconds (default: KBR_FETCH_TIMEOUT or 15).",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        metavar="N",
        help="Max bytes per document (default: KBR_FETCH_MAX_BYTES or 20 MiB).",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help=(
            "Rebuild the FAISS index via app.rag.system after downloading. "
            "No-op (with a warning) unless OPENAI_API_KEY is set."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point. Network access occurs only from this function."""
    args = build_parser().parse_args(argv)
    env_dir, env_timeout, env_max = _resolve_settings()

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else env_dir
    timeout = args.timeout if args.timeout is not None else env_timeout
    max_bytes = args.max_bytes if args.max_bytes is not None else env_max

    urls = parse_source_urls(args.urls)
    code = run(urls, data_dir, timeout, max_bytes)
    if args.ingest and code != 2:  # still allow ingest of previously-fetched docs
        ingest_code = maybe_ingest(data_dir)
        code = code or ingest_code
    return code


if __name__ == "__main__":  # pragma: no cover - exercised via CLI
    raise SystemExit(main())
