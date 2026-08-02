"""Tests for ``app.rag.ingestion.chunk_text``.

NOTE (reconciliation): these tests pin the CURRENT character-window behaviour.
``chunk_text`` normalises whitespace and then slices fixed ``size`` windows with
``step = size - overlap``; it does NOT respect sentence/word boundaries and may
cut mid-word. The coordinator (agent-1) is landing sentence-aware chunking that
never cuts mid-token — when that lands, the boundary/mid-word assertions here
should be revisited. The empty-input and overlap-invariant tests are stable
across both implementations.
"""

from __future__ import annotations

from app.rag.ingestion import chunk_text


def test_empty_and_whitespace_input_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_short_text_returns_single_chunk():
    text = "a short building description"
    assert chunk_text(text, size=1000, overlap=150) == [text]


def test_text_is_whitespace_normalised():
    # Newlines/tabs/runs of spaces collapse to single spaces before chunking.
    text = "plot   area:\n\n300   sq.m\t"
    chunks = chunk_text(text, size=1000, overlap=0)
    assert chunks == ["plot area: 300 sq.m"]


def test_chunk_lengths_respect_size():
    text = "abcdefghij" * 30  # 300 chars, no spaces
    size = 100
    chunks = chunk_text(text, size=size, overlap=0)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= size


def test_overlap_produces_shared_characters():
    text = "".join(chr(ord("a") + (i % 26)) for i in range(50))
    size, overlap = 20, 5
    chunks = chunk_text(text, size=size, overlap=overlap)
    assert len(chunks) >= 3
    # Consecutive chunks share `overlap` trailing/leading characters (current
    # fixed-step slicing guarantees this except at the tail).
    for first, second in zip(chunks, chunks[1:]):
        assert first[-overlap:] == second[:overlap]


def test_step_is_size_minus_overlap():
    # With no whitespace, chunk starts land on multiples of (size - overlap).
    text = "x" * 97
    size, overlap = 20, 6
    step = size - overlap  # 14
    chunks = chunk_text(text, size=size, overlap=overlap)
    # Reconstruct the window boundaries: chunk[i] == text[i*step : i*step + size].
    for i, chunk in enumerate(chunks):
        assert chunk == text[i * step : i * step + size]


def test_full_coverage_of_source_text():
    import re

    raw = "The quick brown fox jumps over the lazy dog. " * 8
    # chunk_text normalises whitespace first; coverage is over the normalised
    # body it actually splits.
    text = re.sub(r"\s+", " ", raw).strip()
    size, overlap = 64, 16
    chunks = chunk_text(raw, size=size, overlap=overlap)
    step = max(1, size - overlap)

    covered = [False] * len(text)
    for i, chunk in enumerate(chunks):
        start = i * step
        assert chunk == text[start : start + size]  # current fixed-step slicing
        for j in range(len(chunk)):
            covered[start + j] = True
    assert all(covered)
