"""Tests for ``app.rag.ingestion.chunk_text``.

CURRENT (optimized) contract — agent-1 made ``chunk_text`` sentence-aware. It
splits on sentence boundaries (never cutting mid-sentence), greedily packs whole
sentences into ``size``-bounded chunks, and re-includes the trailing sentence(s)
of the previous chunk up to ``overlap`` characters so context carries across the
boundary. A single sentence longer than ``size`` falls back to a bounded
char-split. Clause numbers like "8.1.2" are NOT treated as sentence boundaries.
These tests pin the NEW behaviour (verified against the merged code).
"""

from __future__ import annotations

from app.rag.ingestion import chunk_text

PARA = (
    "Sentence one here. "
    "Sentence two is a bit longer than one. "
    "And a third sentence. "
    "A fourth one follows too."
)


def test_empty_and_whitespace_input_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_short_single_sentence_returns_single_chunk():
    text = "a short building description"
    assert chunk_text(text, size=1000, overlap=150) == [text]


def test_text_is_whitespace_normalised():
    text = "plot   area:\n\n300   sq.m\t"
    assert chunk_text(text, size=1000, overlap=0) == ["plot area: 300 sq.m"]


def test_chunks_never_exceed_size():
    chunks = chunk_text(PARA, size=60, overlap=15)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 60


def test_chunks_split_on_sentence_boundaries_only():
    # Every chunk is a run of whole sentences, so each ends with terminal
    # punctuation rather than a sliced word.
    chunks = chunk_text(PARA, size=60, overlap=15)
    for c in chunks:
        assert c.rstrip().endswith((".", "!", "?", ";"))


def test_no_sentence_is_split_across_chunks():
    chunks = chunk_text(PARA, size=60, overlap=15)
    sentences = [
        "Sentence one here.",
        "Sentence two is a bit longer than one.",
        "And a third sentence.",
        "A fourth one follows too.",
    ]
    # Each sentence must appear *whole* in at least one chunk (overlap may
    # duplicate it, but it is never truncated).
    for s in sentences:
        assert any(s in c for c in chunks), s


def test_sentences_are_packed_whole():
    chunks = chunk_text(PARA, size=60, overlap=15)
    # Verified concrete output of the greedy packer for this input.
    assert chunks[0] == "Sentence one here. Sentence two is a bit longer than one."


def test_overlap_carries_the_trailing_sentence_forward():
    chunks = chunk_text(PARA, size=60, overlap=15)
    # The next chunk re-includes the previous chunk's trailing sentence so
    # context is not lost at the boundary.
    assert chunks[1].startswith("Sentence two is a bit longer than one.")


def test_last_sentence_always_bridges_even_at_overlap_zero():
    # The immediately-preceding sentence is ALWAYS re-included as the bridge into
    # the next chunk (context is never fully dropped), even when overlap == 0;
    # `overlap` only budgets pulling in *additional* earlier sentences.
    chunks = chunk_text(PARA, size=60, overlap=0)
    assert chunks[1].startswith("Sentence two is a bit longer than one.")


def test_larger_overlap_pulls_in_additional_context():
    # A generous overlap budget re-includes MORE than just the last sentence.
    text = (
        "Alpha is short. Beta mid length here. "
        "Gamma is a medium sentence. Delta closes it."
    )
    small = chunk_text(text, size=40, overlap=0)
    big = chunk_text(text, size=40, overlap=40)
    # At overlap=40 the second chunk re-includes both "Alpha" and "Beta".
    assert "Alpha is short." in big[1]
    # ... so the bridged second chunk is longer than under overlap=0.
    assert len(big[1]) > len(small[1])


def test_clause_number_is_not_split():
    # "8.1.2" must not be treated as a sentence boundary (no cut mid-number).
    text = "Rule 8.1.2 governs setbacks. The minimum shall be three metres."
    chunks = chunk_text(text, size=1000, overlap=0)
    assert chunks == [text]
    # Even when chunked, the clause number stays intact inside some chunk.
    small = chunk_text(text, size=40, overlap=10)
    assert any("8.1.2" in c for c in small)


def test_overlong_single_sentence_is_bounded():
    long_sentence = "x" * 100 + "."
    chunks = chunk_text("Intro sentence. " + long_sentence, size=50, overlap=10)
    # Falls back to a char-window split for the over-long sentence: nothing
    # exceeds `size`.
    for c in chunks:
        assert len(c) <= 50
