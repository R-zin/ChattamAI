"""Offline tests for PaddleOCR via NVIDIA NIM (``app.rag.paddle_ocr``) and the
``OCR_PROVIDER`` routing in ``app.rag.ocr``. No network: httpx MockTransport."""

from __future__ import annotations

import base64
import json
import random
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from app import config
from app.rag import ocr
from app.rag import paddle_ocr
from app.rag.paddle_ocr import (
    PaddleOCRClient,
    PaddleOCRError,
    dedupe_boxes,
    parse_response,
    tile_grid,
)


def _det(text, x1, y1, x2, y2, conf=0.9, as_list=False):
    pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    points = [list(p) for p in pts] if as_list else [{"x": x, "y": y} for x, y in pts]
    return {
        "text_prediction": {"text": text, "confidence": conf},
        "bounding_box": {"points": points},
    }


def _resp(*dets):
    return {"data": [{"index": 0, "text_detections": list(dets)}]}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(paddle_ocr.time, "sleep", lambda s: None)


# -- parse_response -------------------------------------------------------------
def test_parse_scales_normalised_points_to_pixels():
    boxes = parse_response(
        _resp(_det("BEDROOM", 0.1, 0.2, 0.3, 0.25, conf=0.98)), 1000, 800
    )
    assert boxes == [
        {
            "text": "BEDROOM",
            "left": 100,
            "top": 160,
            "width": 200,
            "height": 40,
            "conf": 98.0,
        }
    ]


def test_parse_splits_lines_into_word_boxes_left_to_right():
    boxes = parse_response(
        _resp(_det("FRONT SETBACK 1.8m", 0.0, 0.0, 0.9, 0.1)), 1800, 100
    )
    assert [b["text"] for b in boxes] == ["FRONT", "SETBACK", "1.8m"]
    lefts = [b["left"] for b in boxes]
    assert lefts == sorted(lefts)
    assert boxes[-1]["left"] + boxes[-1]["width"] <= 1620 + 1


def test_parse_accepts_pixel_and_list_points_with_offset():
    payload = _resp(_det("PLOT", 10, 20, 110, 50, as_list=True))
    (box,) = parse_response(payload, 500, 500, offset=(1000, 2000))
    assert (box["left"], box["top"], box["width"], box["height"]) == (
        1010,
        2020,
        100,
        30,
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"data": "x"},
        {"data": [{"text_detections": [{"text_prediction": {"text": ""}}]}]},
        {
            "data": [
                {
                    "text_detections": [
                        {"text_prediction": {"text": "A"}, "bounding_box": {}}
                    ]
                }
            ]
        },
        {
            "data": [
                {
                    "text_detections": [
                        {"bounding_box": {"points": [{"x": "a", "y": 0}]}}
                    ]
                }
            ]
        },
    ],
)
def test_parse_skips_malformed_payloads(payload):
    assert parse_response(payload, 100, 100) == []


def test_parse_accepts_top_level_text_detections():
    payload = {"text_detections": [_det("KITCHEN", 0.0, 0.0, 0.5, 0.5)]}
    assert [b["text"] for b in parse_response(payload, 10, 10)] == ["KITCHEN"]


# -- tiling ---------------------------------------------------------------------
def test_tile_grid_covers_image_with_overlap():
    tiles = tile_grid(2000, 1000, 2)
    assert len(tiles) == 4
    assert min(t[0] for t in tiles) == 0 and max(t[2] for t in tiles) == 2000
    assert min(t[1] for t in tiles) == 0 and max(t[3] for t in tiles) == 1000
    left_col = [t for t in tiles if t[0] == 0]
    right_col = [t for t in tiles if t[0] > 0]
    assert left_col[0][2] > right_col[0][0]  # columns overlap


def test_dedupe_keeps_highest_confidence_duplicate():
    a = {"text": "WC", "left": 100, "top": 100, "width": 40, "height": 20, "conf": 80.0}
    b = dict(a, left=102, conf=95.0)
    c = dict(a, left=600)
    kept = dedupe_boxes([a, b, c])
    assert len(kept) == 2
    assert any(k["conf"] == 95.0 for k in kept)


# -- client -----------------------------------------------------------------------
def _client(handler, **kw):
    kw.setdefault("api_key", "nvapi-test")
    return PaddleOCRClient(transport=httpx.MockTransport(handler), **kw)


def test_client_posts_inline_image_with_bearer_key():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_resp(_det("HALL", 0.1, 0.1, 0.2, 0.2)))

    boxes = _client(handler).image_word_boxes(Image.new("L", (400, 300), 255))
    assert seen["auth"] == "Bearer nvapi-test"
    assert seen["url"] == paddle_ocr.HOSTED_URL
    item = seen["body"]["input"][0]
    assert item["type"] == "image_url"
    assert item["url"].startswith("data:image/png;base64,")
    base64.b64decode(item["url"].split(",", 1)[1])
    assert boxes[0]["text"] == "HALL" and boxes[0]["left"] == 40


def test_large_plan_is_tiled_and_mapped_back_to_full_image():
    rng = random.Random(7)
    img = Image.frombytes(
        "L", (1200, 900), bytes(rng.getrandbits(8) for _ in range(1200 * 900))
    )
    calls = []

    def handler(request):
        calls.append(len(request.content))
        return httpx.Response(200, json=_resp(_det("A", 0.0, 0.0, 0.05, 0.05)))

    client = _client(handler, max_b64=400_000)
    boxes = client.image_word_boxes(img)
    assert len(calls) > 1
    for b in boxes:
        assert 0 <= b["left"] < 1200 and 0 <= b["top"] < 900
    assert len({(b["left"], b["top"]) for b in boxes}) == len(calls)


def test_self_hosted_nim_has_no_payload_cap_and_no_key_required():
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json=_resp())

    client = _client(handler, api_key=None, url="http://nim.local:8000/v1/infer")
    assert client.max_b64 == 0
    assert client.image_word_boxes(Image.new("L", (50, 50))) == []


def test_hosted_endpoint_requires_key():
    with pytest.raises(PaddleOCRError, match="NVIDIA_API_KEY"):
        PaddleOCRClient(api_key=None)


def test_retries_transient_errors_then_succeeds():
    statuses = iter([503, 429, 200])

    def handler(request):
        code = next(statuses)
        body = _resp(_det("OK", 0, 0, 0.1, 0.1)) if code == 200 else {"detail": "busy"}
        return httpx.Response(code, json=body)

    boxes = _client(handler, max_retries=2).image_word_boxes(Image.new("L", (64, 64)))
    assert boxes[0]["text"] == "OK"


def test_auth_failure_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={"detail": "bad key"})

    with pytest.raises(PaddleOCRError, match="rejected the API key"):
        _client(handler, max_retries=3).image_word_boxes(Image.new("L", (64, 64)))
    assert len(calls) == 1


def test_persistent_failure_raises_after_retry_budget():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(502, text="bad gateway")

    with pytest.raises(PaddleOCRError, match="HTTP 502"):
        _client(handler, max_retries=2).image_word_boxes(Image.new("L", (64, 64)))
    assert len(calls) == 3


# -- provider routing in app.rag.ocr ---------------------------------------------------
def _png(tmp_path, size=(300, 200)):
    p = tmp_path / "plan.png"
    Image.new("L", size, 255).save(p)
    return p


def test_nim_provider_routes_image_ocr_to_paddle(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_provider", lambda: "nim")
    monkeypatch.setattr(
        ocr,
        "_paddle_boxes",
        lambda img: [
            {
                "text": "FRONT",
                "left": 10,
                "top": 10,
                "width": 50,
                "height": 20,
                "conf": 99.0,
            },
            {
                "text": "SETBACK",
                "left": 70,
                "top": 10,
                "width": 70,
                "height": 20,
                "conf": 99.0,
            },
            {
                "text": "3.0m",
                "left": 600,
                "top": 12,
                "width": 40,
                "height": 20,
                "conf": 99.0,
            },
        ],
    )
    assert ocr.image_to_text(_png(tmp_path)) == "FRONT SETBACK: 3.0m"
    text, note = ocr.image_to_layout_text(_png(tmp_path))
    assert text == "FRONT SETBACK: 3.0m" and note is None


def test_nim_failure_falls_back_to_tesseract_when_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_provider", lambda: "nim")

    def boom(img):
        raise PaddleOCRError("PaddleOCR NIM request failed (HTTP 503)")

    monkeypatch.setattr(ocr, "_paddle_boxes", boom)
    monkeypatch.setattr(ocr, "tesseract_available", lambda: True)
    monkeypatch.setattr(ocr, "_tesseract_image_text", lambda path: "tesseract words")
    assert ocr.image_to_text(_png(tmp_path)) == "tesseract words"


def test_nim_failure_without_tesseract_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_provider", lambda: "nim")

    def boom(img):
        raise PaddleOCRError("PaddleOCR NIM request failed (HTTP 503)")

    monkeypatch.setattr(ocr, "_paddle_boxes", boom)
    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    with pytest.raises(PaddleOCRError):
        ocr.image_to_text(_png(tmp_path))
    with pytest.raises(PaddleOCRError):
        ocr.image_to_layout_text(_png(tmp_path))


def _settings(**kw):
    base = dict(
        ocr_provider="nim",
        paddleocr_url=paddle_ocr.HOSTED_URL,
        nvidia_api_key=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_nim_availability_needs_key_for_hosted_endpoint(monkeypatch):
    monkeypatch.setattr(config, "get_settings", lambda: _settings())
    assert "NVIDIA_API_KEY" in ocr.ocr_unavailable_reason()
    monkeypatch.setattr(config, "get_settings", lambda: _settings(nvidia_api_key="k"))
    assert ocr.ocr_available()
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: _settings(paddleocr_url="http://nim:8000/v1/infer"),
    )
    assert ocr.ocr_available()


def test_unknown_provider_is_reported(monkeypatch):
    monkeypatch.setattr(config, "get_settings", lambda: _settings(ocr_provider="abbyy"))
    assert "Unknown OCR_PROVIDER" in ocr.ocr_unavailable_reason()


# -- config defaults --------------------------------------------------------------
@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, "tesseract"),
        ({"NVIDIA_API_KEY": "nvapi-x"}, "nim"),
        ({"NVIDIA_API_KEY": "nvapi-x", "OCR_PROVIDER": "tesseract"}, "tesseract"),
        ({"OCR_PROVIDER": "PaddleOCR"}, "nim"),
        ({"OCR_PROVIDER": "none", "NVIDIA_API_KEY": "nvapi-x"}, "nim"),
    ],
)
def test_default_ocr_provider(monkeypatch, env, expected):
    for k in ("OCR_PROVIDER", "NVIDIA_API_KEY", "NIM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert config._default_ocr_provider() == expected


# -- API route ------------------------------------------------------------------------
def test_plan_ocr_endpoint_uses_paddleocr(monkeypatch, app_client, tmp_path):
    from app.config import get_settings

    monkeypatch.setenv("OCR_ENABLED", "1")
    monkeypatch.setenv("OCR_PROVIDER", "nim")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    get_settings.cache_clear()
    seen = []

    def fake_boxes(img):
        seen.append(img.size)
        return [
            {
                "text": "Residential",
                "left": 10,
                "top": 10,
                "width": 90,
                "height": 20,
                "conf": 99.0,
            },
            {
                "text": "building",
                "left": 110,
                "top": 10,
                "width": 70,
                "height": 20,
                "conf": 99.0,
            },
            {
                "text": "front",
                "left": 10,
                "top": 60,
                "width": 40,
                "height": 20,
                "conf": 99.0,
            },
            {
                "text": "setback",
                "left": 55,
                "top": 60,
                "width": 60,
                "height": 20,
                "conf": 99.0,
            },
            {
                "text": "1m",
                "left": 500,
                "top": 60,
                "width": 20,
                "height": 20,
                "conf": 99.0,
            },
        ]

    monkeypatch.setattr(ocr, "_paddle_boxes", fake_boxes)
    try:
        with open(_png(tmp_path), "rb") as fh:
            res = app_client.post(
                "/api/check/plan-ocr", files={"file": ("plan.png", fh, "image/png")}
            )
        assert res.status_code == 200, res.text
        assert seen, "PaddleOCR path was not used"
        health = app_client.get("/api/health").json()
        assert health["ocr_enabled"] is True and health["ocr_provider"] == "nim"
    finally:
        get_settings.cache_clear()


def test_plan_ocr_endpoint_reports_missing_key(monkeypatch, app_client, tmp_path):
    from app.config import get_settings

    monkeypatch.setenv("OCR_ENABLED", "1")
    monkeypatch.setenv("OCR_PROVIDER", "nim")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with open(_png(tmp_path), "rb") as fh:
            res = app_client.post(
                "/api/check/plan-ocr", files={"file": ("plan.png", fh, "image/png")}
            )
        assert res.status_code == 503
        assert "NVIDIA_API_KEY" in res.json()["detail"]
    finally:
        get_settings.cache_clear()
