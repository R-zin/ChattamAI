"""Offline tests for the geometry-aware OCR pass in ``app.rag.ocr`` (T3.1).

These tests NEVER touch a real Tesseract binary, Pillow image, or the network.
They drive the pure layout functions with *synthetic* TSV word-box dicts and
assert deterministic read-order / table->kv reconstruction, plus graceful
fallback in :func:`image_to_layout_text` (mocked TSV failure / success).

The plain-text path (``image_to_text`` / ``pdf_images_to_text``) is the default
and is untouched by this suite; we only prove the additive geometry layer works
and never crashes the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

from app.rag import ocr
from app.rag.ocr import (
    dataframe_to_word_boxes,
    group_words_into_lines,
    image_to_layout_text,
    line_to_text,
    tsv_to_word_boxes,
    word_boxes_to_text,
)


def _box(text, left, top, width=40, height=20, conf=90.0) -> Dict[str, object]:
    """Build one synthetic word box (mirrors a Tesseract TSV word row)."""
    return {
        "text": text,
        "left": left,
        "top": top,
        "width": width,
        "height": height,
        "conf": conf,
    }


def _tsv(rows: List[Dict[str, object]]) -> Dict[str, List[object]]:
    """Assemble a column-oriented Tesseract-TSV-style dict from word rows."""
    cols: Dict[str, List[object]] = {
        "text": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "conf": [],
    }
    for r in rows:
        for key in cols:
            cols[key].append(r[key])
    return cols


# ---------------------------------------------------------------------------
# tsv_to_word_boxes — TSV parsing + junk filtering
# ---------------------------------------------------------------------------
def test_tsv_parses_clean_word_rows():
    data = _tsv([_box("front", 10, 100), _box("setback", 70, 100)])
    boxes = tsv_to_word_boxes(data)
    assert [b["text"] for b in boxes] == ["front", "setback"]
    assert boxes[0]["left"] == 10 and boxes[1]["left"] == 70


def test_tsv_drops_structural_and_empty_rows():
    # conf == -1 marks Tesseract structural rows (page/block/line); empty text too.
    rows = [
        _box("", 0, 0, conf=-1.0),
        _box("   ", 0, 0, conf=5.0),
        _box("height", 10, 20, conf=88.0),
        _box("noise", 5, 5, conf=-1.0),
    ]
    boxes = tsv_to_word_boxes(_tsv(rows))
    assert [b["text"] for b in boxes] == ["height"]


def test_tsv_drops_non_string_and_malformed_rows():
    rows = [
        {"text": None, "left": 0, "top": 0, "width": 5, "height": 5, "conf": 50},
        {"text": "ok", "left": "x", "top": 0, "width": 5, "height": 5, "conf": 50},
        {"text": "good", "left": 1, "top": 2, "width": 5, "height": 5, "conf": 50},
    ]
    boxes = tsv_to_word_boxes(_tsv(rows))
    assert [b["text"] for b in boxes] == ["good"]


def test_tsv_malformed_container_returns_empty():
    assert tsv_to_word_boxes(None) == []
    assert tsv_to_word_boxes(["not", "a", "dict"]) == []
    assert tsv_to_word_boxes({"text": ["a"]}) == []  # missing geometry columns
    # Mismatched column lengths are unusable.
    bad = {
        "text": ["a", "b"],
        "left": [0],
        "top": [0, 1],
        "width": [1, 1],
        "height": [1, 1],
        "conf": [1, 1],
    }
    assert tsv_to_word_boxes(bad) == []


# ---------------------------------------------------------------------------
# group_words_into_lines — line grouping by `top` (vertical centre)
# ---------------------------------------------------------------------------
def test_words_on_same_baseline_group_into_one_line():
    boxes = [
        _box("front", 10, 100, height=20),
        _box("setback", 60, 103, height=20),  # 3px lower, still same line
        _box("1.8m", 300, 102, height=20),
    ]
    lines = group_words_into_lines(boxes)
    assert len(lines) == 1
    assert [b["text"] for b in lines[0]] == ["front", "setback", "1.8m"]


def test_words_on_different_rows_split_into_two_lines():
    boxes = [
        _box("row1", 10, 100, height=20),
        _box("row2", 10, 140, height=20),  # 40px below -> a new line
    ]
    lines = group_words_into_lines(boxes)
    assert len(lines) == 2
    assert [b["text"] for b in lines[0]] == ["row1"]
    assert [b["text"] for b in lines[1]] == ["row2"]


def test_lines_are_left_to_right_within_a_row_and_top_to_bottom_overall():
    # Feed words deliberately out of order to prove sorting is applied.
    boxes = [
        _box("c", 200, 100),
        _box("a", 10, 100),  # same row as b/c
        _box("b", 100, 100),
        _box("z", 10, 200),  # lower row
    ]
    lines = group_words_into_lines(boxes)
    assert [[b["text"] for b in line] for line in lines] == [
        ["a", "b", "c"],
        ["z"],
    ]


def test_group_words_empty_input_returns_empty():
    assert group_words_into_lines([]) == []


# ---------------------------------------------------------------------------
# line_to_text — column order + wide-gap -> ":" table hint
# ---------------------------------------------------------------------------
def test_column_gap_renders_as_key_value_separator():
    # Two clusters separated by a clear gap -> "label: value".
    line = [
        _box("setback", 10, 100, width=50),
        _box("1.8m", 400, 100, width=45),  # big horizontal gap
    ]
    assert line_to_text(line) == "setback: 1.8m"


def test_close_words_stay_space_joined_prose():
    line = [
        _box("minimum", 10, 100, width=60),
        _box("setback", 75, 100, width=50),  # small gap -> plain prose
    ]
    assert line_to_text(line) == "minimum setback"


def test_line_to_text_preserves_left_to_right_order():
    line = [_box("b", 100, 0), _box("a", 0, 0)]
    # note: line_to_text assumes already-sorted input; grouping sorts first.
    assert line_to_text(line) == "b a"


# ---------------------------------------------------------------------------
# word_boxes_to_text — full reconstruction (FSI/setback table scenario)
# ---------------------------------------------------------------------------
def test_setback_table_reconstructs_as_key_value_lines():
    # A tiny 2-row table: label column on the left, value column far right.
    boxes = [
        _box("front", 10, 100, width=45),
        _box("setback", 60, 100, width=55),
        _box("1.8m", 400, 100, width=45),
        _box("rear", 10, 140, width=40),
        _box("setback", 60, 140, width=55),
        _box("1.2m", 400, 140, width=45),
    ]
    text = word_boxes_to_text(boxes)
    assert text.split("\n") == ["front setback: 1.8m", "rear setback: 1.2m"]


def test_word_boxes_to_text_empty_returns_empty_string():
    assert word_boxes_to_text([]) == ""


def test_reconstruction_is_deterministic():
    boxes = [
        _box("b", 100, 0),
        _box("a", 10, 0),
        _box("c", 400, 0),
    ]
    first = word_boxes_to_text(boxes)
    second = word_boxes_to_text(list(reversed(boxes)))
    assert first == second == "a b: c"


# ---------------------------------------------------------------------------
# dataframe_to_word_boxes — Output.DATAFRAME adapter
# ---------------------------------------------------------------------------
class _FakeDataFrame:
    """Minimal stand-in for a pandas DataFrame (to_dict('list') only)."""

    def __init__(self, data):
        self._data = data

    def to_dict(self, orient):
        assert orient == "list"
        return self._data


def test_dataframe_adapter_round_trips():
    df = _FakeDataFrame(_tsv([_box("fsi", 10, 100), _box("1.5", 200, 100)]))
    boxes = dataframe_to_word_boxes(df)
    assert [b["text"] for b in boxes] == ["fsi", "1.5"]


def test_dataframe_adapter_non_dataframe_returns_empty():
    assert dataframe_to_word_boxes(object()) == []


# ---------------------------------------------------------------------------
# image_to_layout_text — graceful fallback (mocked, offline)
# ---------------------------------------------------------------------------
def test_layout_falls_back_to_plain_text_when_tesseract_missing(monkeypatch):
    # Simulate the heavy OCR import failing (no pytesseract on the box).
    def _boom(name):
        raise RuntimeError(f"OCR dependency '{name}' is not installed")

    monkeypatch.setattr(ocr, "_import", _boom)

    called = {}

    def _fake_plain(path):
        called["path"] = path
        return "plain words only"

    monkeypatch.setattr(ocr, "image_to_text", _fake_plain)

    text, note = image_to_layout_text(Path("plan.png"))
    assert text == "plain words only"
    assert note and note.startswith("layout_ocr_failed:")
    assert called["path"] == Path("plan.png")


def test_layout_returns_structure_when_tsv_available(monkeypatch):
    data = _tsv(
        [
            _box("setback", 10, 100, width=50),
            _box("1.8m", 400, 100, width=45),
        ]
    )

    class _FakeGray:
        def close(self):
            pass

    class _FakePytesseract:
        @staticmethod
        def image_to_data(img, output_type=None):
            return data

    class _FakeOutput:
        DICT = "dict"

    def _fake_import(name):
        if name == "pytesseract":
            return _FakePytesseract
        if name == "pytesseract.Output":
            return _FakeOutput
        raise AssertionError(f"unexpected import {name}")

    monkeypatch.setattr(ocr, "_import", _fake_import)
    monkeypatch.setattr(ocr, "_load_gray_image", lambda path: _FakeGray())

    text, note = image_to_layout_text(Path("plan.png"))
    assert note is None
    assert text == "setback: 1.8m"


def test_layout_degenerate_boxes_fall_back_to_plain(monkeypatch):
    class _FakeGray:
        def close(self):
            pass

    class _FakePytesseract:
        @staticmethod
        def image_to_data(img, output_type=None):
            return {
                "text": [],
                "left": [],
                "top": [],
                "width": [],
                "height": [],
                "conf": [],
            }

    class _FakeOutput:
        DICT = "dict"

    def _fake_import(name):
        if name == "pytesseract":
            return _FakePytesseract
        if name == "pytesseract.Output":
            return _FakeOutput
        raise AssertionError(f"unexpected import {name}")

    monkeypatch.setattr(ocr, "_import", _fake_import)
    monkeypatch.setattr(ocr, "_load_gray_image", lambda path: _FakeGray())
    monkeypatch.setattr(ocr, "image_to_text", lambda path: "fallback words")

    text, note = image_to_layout_text(Path("plan.png"))
    assert text == "fallback words"
    assert note == "layout_ocr_failed: no word boxes"


def test_layout_no_fallback_reraises(monkeypatch):
    def _boom(name):
        raise RuntimeError("no ocr here")

    monkeypatch.setattr(ocr, "_import", _boom)
    with pytest.raises(RuntimeError):
        image_to_layout_text(Path("plan.png"), fallback_to_plain=False)
