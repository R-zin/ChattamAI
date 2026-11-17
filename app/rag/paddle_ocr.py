"""PaddleOCR via NVIDIA NIM: floor-plan text detection + recognition.

Sends a raster image to the PaddleOCR NIM (``baidu/paddleocr``), either the
hosted endpoint on ``ai.api.nvidia.com`` or a self-hosted NIM container
(``http://<host>:8000/v1/infer``), and converts its detections into the
:data:`app.rag.ocr.WordBox` shape so the existing geometry pipeline
(:func:`app.rag.ocr.word_boxes_to_text`) rebuilds reading-order text with
``label: value`` hints exactly as it does for Tesseract output.

Request (both endpoints)::

    {"input": [{"type": "image_url", "url": "data:image/png;base64,<b64>"}]}

Response::

    {"data": [{"index": 0, "text_detections": [
        {"text_prediction": {"text": "BEDROOM", "confidence": 0.98},
         "bounding_box": {"points": [{"x": 0.1, "y": 0.2}, ...]}}]}]}

Points are normalised to ``[0, 1]`` of the submitted image; pixel coordinates
are also accepted. The hosted endpoint caps inline base64 payloads (about
180 kB), so large drawings are split into overlapping tiles at full resolution
instead of being downscaled: floor-plan dimension text is small, and shrinking
the sheet is what loses it. Self-hosted NIMs have no such cap
(``PADDLEOCR_MAX_B64=0``).

Python 3.9 compatible. Pillow is imported lazily by the caller's image loader;
this module only needs ``httpx`` (a core dependency).
"""

from __future__ import annotations

import base64
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx

logger = logging.getLogger(__name__)

HOSTED_URL = "https://ai.api.nvidia.com/v1/cv/baidu/paddleocr"
# Inline base64 budget of the hosted endpoint (larger bodies need NVCF assets).
HOSTED_MAX_B64 = 180_000

# Tiling search: grids from 1x1 up to _MAX_GRID x _MAX_GRID at full resolution,
# then the same at reduced scales before giving up.
_MAX_GRID = 4
_SCALES = (1.0, 0.75, 0.5)
# Encodings tried per tile, smallest-loss first. Line drawings compress well as
# PNG; JPEG is the fallback for dense scans.
_ENCODINGS: Tuple[Tuple[str, Optional[int]], ...] = (
    ("PNG", None),
    ("JPEG", 90),
    ("JPEG", 80),
    ("JPEG", 70),
)
_TILE_OVERLAP_FRACTION = 0.04
_MIN_TILE_OVERLAP_PX = 64
_MAX_WORKERS = 4
_RETRY_STATUSES = {429, 500, 502, 503, 504}

WordBox = Dict[str, object]


class PaddleOCRError(RuntimeError):
    """The PaddleOCR NIM could not produce a result (config, auth, transport)."""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------
def _xy(point: Any) -> Optional[Tuple[float, float]]:
    if isinstance(point, dict):
        x, y = point.get("x"), point.get("y")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        x, y = point[0], point[1]
    else:
        return None
    try:
        return float(x), float(y)
    except (TypeError, ValueError):
        return None


def _detections(payload: Any) -> Iterable[Dict[str, Any]]:
    """Yield raw detection dicts from any of the observed response layouts."""
    if not isinstance(payload, dict):
        return
    items = payload.get("data")
    if items is None and "text_detections" in payload:
        items = [payload]
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        for det in item.get("text_detections") or []:
            if isinstance(det, dict):
                yield det


def _split_line(
    text: str, left: float, top: float, width: float, height: float, conf: float
) -> List[WordBox]:
    """Split a detected text line into word boxes, apportioning width by length.

    PaddleOCR detects lines; the shared layout code reasons about word gaps, so
    each whitespace-separated word gets a proportional slice of the line box.
    """
    words = text.split()
    if len(words) <= 1:
        return [
            {
                "text": text,
                "left": int(round(left)),
                "top": int(round(top)),
                "width": max(1, int(round(width))),
                "height": max(1, int(round(height))),
                "conf": conf,
            }
        ]
    total_chars = sum(len(w) for w in words) + (len(words) - 1)
    char_w = width / max(total_chars, 1)
    boxes: List[WordBox] = []
    cursor = left
    for w in words:
        w_width = char_w * len(w)
        boxes.append(
            {
                "text": w,
                "left": int(round(cursor)),
                "top": int(round(top)),
                "width": max(1, int(round(w_width))),
                "height": max(1, int(round(height))),
                "conf": conf,
            }
        )
        cursor += w_width + char_w
    return boxes


def parse_response(
    payload: Any, width: int, height: int, offset: Tuple[int, int] = (0, 0)
) -> List[WordBox]:
    """Convert a PaddleOCR NIM response into word boxes in source-image pixels.

    ``width``/``height`` are the size of the image that was submitted (used to
    scale normalised points); ``offset`` shifts tile-local boxes into the full
    image. Malformed detections are skipped, never raised.
    """
    ox, oy = offset
    boxes: List[WordBox] = []
    for det in _detections(payload):
        pred = det.get("text_prediction") or {}
        text = str(pred.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(pred.get("confidence", 1.0))
        except (TypeError, ValueError):
            conf = 1.0
        pts = [
            p
            for p in (
                _xy(p) for p in (det.get("bounding_box") or {}).get("points") or []
            )
            if p
        ]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        normalised = max(xs + ys) <= 1.5
        sx, sy = (float(width), float(height)) if normalised else (1.0, 1.0)
        left, right = min(xs) * sx, max(xs) * sx
        top, bottom = min(ys) * sy, max(ys) * sy
        boxes.extend(
            _split_line(
                text,
                left + ox,
                top + oy,
                right - left,
                bottom - top,
                # WordBox confidence uses Tesseract's 0-100 scale.
                conf * 100.0 if conf <= 1.0 else conf,
            )
        )
    return boxes


# ---------------------------------------------------------------------------
# Tiling
# ---------------------------------------------------------------------------
def tile_grid(width: int, height: int, n: int) -> List[Tuple[int, int, int, int]]:
    """Split ``width`` x ``height`` into an ``n`` x ``n`` grid of overlapping
    ``(left, top, right, bottom)`` crops. ``n == 1`` is the whole image."""
    if n <= 1:
        return [(0, 0, width, height)]
    ov_x = max(_MIN_TILE_OVERLAP_PX, int(width * _TILE_OVERLAP_FRACTION))
    ov_y = max(_MIN_TILE_OVERLAP_PX, int(height * _TILE_OVERLAP_FRACTION))
    tiles = []
    for row in range(n):
        for col in range(n):
            left = max(0, width * col // n - ov_x)
            right = min(width, width * (col + 1) // n + ov_x)
            top = max(0, height * row // n - ov_y)
            bottom = min(height, height * (row + 1) // n + ov_y)
            tiles.append((left, top, right, bottom))
    return tiles


def _iou(a: WordBox, b: WordBox) -> float:
    ax1, ay1 = float(a["left"]), float(a["top"])
    ax2, ay2 = ax1 + float(a["width"]), ay1 + float(a["height"])
    bx1, by1 = float(b["left"]), float(b["top"])
    bx2, by2 = bx1 + float(b["width"]), by1 + float(b["height"])
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def dedupe_boxes(boxes: Sequence[WordBox], threshold: float = 0.5) -> List[WordBox]:
    """Drop duplicate detections of the same word from overlapping tiles."""
    kept: List[WordBox] = []
    for box in sorted(boxes, key=lambda b: -float(b["conf"])):
        if any(k["text"] == box["text"] and _iou(k, box) >= threshold for k in kept):
            continue
        kept.append(box)
    return kept


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class PaddleOCRClient:
    """Minimal synchronous client for the PaddleOCR NIM."""

    def __init__(
        self,
        api_key: Optional[str],
        url: str = HOSTED_URL,
        timeout: float = 60.0,
        max_b64: Optional[int] = None,
        max_retries: int = 2,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.hosted = "api.nvidia.com" in self.url
        if self.hosted and not api_key:
            raise PaddleOCRError(
                "PaddleOCR on the hosted NVIDIA endpoint needs NVIDIA_API_KEY."
            )
        self.api_key = api_key
        self.timeout = timeout
        # None = endpoint default; 0 = unlimited (self-hosted NIM).
        if max_b64 is None:
            max_b64 = HOSTED_MAX_B64 if self.hosted else 0
        self.max_b64 = max(0, int(max_b64))
        self.max_retries = max(0, int(max_retries))
        self._transport = transport

    # -- encoding ---------------------------------------------------------
    def _encode(self, img) -> Optional[Tuple[str, str]]:
        """Return ``(mime, b64)`` within the size budget, or None if it can't fit."""
        for fmt, quality in _ENCODINGS:
            buf = io.BytesIO()
            src = (
                img if fmt == "PNG" or img.mode in ("L", "RGB") else img.convert("RGB")
            )
            if quality is None:
                src.save(buf, format=fmt, optimize=True)
            else:
                src.save(buf, format=fmt, quality=quality, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            if not self.max_b64 or len(b64) <= self.max_b64:
                return ("image/png" if fmt == "PNG" else "image/jpeg"), b64
        return None

    def _plan(
        self, img
    ) -> Tuple[Any, List[Tuple[Tuple[int, int, int, int], str, str]], float]:
        """Choose scale + grid so every tile fits; return (image, tiles, scale)."""
        Image = __import__("PIL.Image", fromlist=["Image"])
        for scale in _SCALES:
            scaled = img
            if scale != 1.0:
                scaled = img.resize(
                    (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                    Image.LANCZOS,
                )
            for n in range(1, _MAX_GRID + 1):
                encoded = []
                for crop in tile_grid(scaled.width, scaled.height, n):
                    enc = self._encode(scaled.crop(crop) if n > 1 else scaled)
                    if enc is None:
                        break
                    encoded.append((crop, enc[0], enc[1]))
                else:
                    return scaled, encoded, scale
        raise PaddleOCRError(
            "Image is too large for the PaddleOCR endpoint's inline payload limit "
            "even after tiling; use a self-hosted NIM (PADDLEOCR_URL) or a smaller scan."
        )

    # -- transport ----------------------------------------------------------
    def _post(self, client: httpx.Client, mime: str, b64: str) -> Any:
        body = {"input": [{"type": "image_url", "url": f"data:{mime};base64,{b64}"}]}
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                res = client.post(self.url, json=body, headers=headers)
            except httpx.HTTPError as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if res.status_code in (401, 403):
                    raise PaddleOCRError(
                        f"PaddleOCR NIM rejected the API key (HTTP {res.status_code})."
                    )
                if res.status_code < 400:
                    try:
                        return res.json()
                    except ValueError as exc:
                        raise PaddleOCRError(
                            "PaddleOCR NIM returned invalid JSON."
                        ) from exc
                last = f"HTTP {res.status_code}: {res.text[:200]}"
                if res.status_code not in _RETRY_STATUSES:
                    break
            if attempt < self.max_retries:
                time.sleep(min(8.0, 0.5 * (2**attempt)))
        raise PaddleOCRError(f"PaddleOCR NIM request failed ({last}).")

    # -- public API ---------------------------------------------------------
    def image_word_boxes(self, img) -> List[WordBox]:
        """OCR a Pillow image; returns word boxes in ``img`` pixel coordinates."""
        scaled, tiles, scale = self._plan(img)
        if len(tiles) > 1:
            logger.info(
                "PaddleOCR: %dx%d image sent as %d tiles (scale %.2f)",
                img.width,
                img.height,
                len(tiles),
                scale,
            )

        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:

            def run(tile):
                (left, top, right, bottom), mime, b64 = tile
                payload = self._post(client, mime, b64)
                return parse_response(
                    payload, right - left, bottom - top, offset=(left, top)
                )

            if len(tiles) == 1:
                results = [run(tiles[0])]
            else:
                with ThreadPoolExecutor(
                    max_workers=min(_MAX_WORKERS, len(tiles))
                ) as pool:
                    results = list(pool.map(run, tiles))

        boxes = [b for r in results for b in r]
        if len(tiles) > 1:
            boxes = dedupe_boxes(boxes)
        if scale != 1.0:
            inv = 1.0 / scale
            for b in boxes:
                for k in ("left", "top", "width", "height"):
                    b[k] = int(round(float(b[k]) * inv))
        return boxes


def client_from_settings(settings=None) -> PaddleOCRClient:
    """Build a client from :func:`app.config.get_settings`."""
    if settings is None:
        from app.config import get_settings

        settings = get_settings()
    return PaddleOCRClient(
        api_key=settings.nvidia_api_key,
        url=settings.paddleocr_url,
        timeout=settings.paddleocr_timeout,
        max_b64=settings.paddleocr_max_b64,
        max_retries=settings.llm_max_retries,
    )


__all__ = [
    "HOSTED_URL",
    "HOSTED_MAX_B64",
    "PaddleOCRClient",
    "PaddleOCRError",
    "client_from_settings",
    "dedupe_boxes",
    "parse_response",
    "tile_grid",
]
