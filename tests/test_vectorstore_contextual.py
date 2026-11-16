"""Tests for the vector store additions behind the multi-query retriever:
contextual indexing, the normalising tokenizer + synonym expansion, batch
``score_queries``, keyword-only search and per-document statistics."""

from __future__ import annotations

import pytest

from app.rag.vectorstore import RuleVectorStore
from tests.conftest import FakeEmbeddingProvider

YARDS = "Front 3 2 5 7.5 Rear 1.5 1 2 3"
YARDS_META = {
    "source": "kpbr.pdf",
    "rule_id": "Rule 26, Table 4",
    "context": "CHAPTER IV OCCUPANCY > 26. Open air spaces > TABLE 4 YARDS",
    "page": 50,
}
PARKING = "One car parking space shall be provided for every dwelling unit."
PARKING_META = {"source": "kpbr.pdf", "rule_id": "Rule 29(1)", "page": 58}
FSI = "The maximum floor space index (F.S.I.) for residential use is 3."
FSI_META = {"source": "sample.txt", "rule_id": "Rule 7"}


@pytest.fixture
def ctx_store(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    store.add_texts([YARDS, PARKING, FSI], [YARDS_META, PARKING_META, FSI_META])
    return store


# -- contextual indexing -----------------------------------------------------
def test_chunk_is_found_by_the_words_of_its_headings(ctx_store):
    # The table body is only numbers; "yards" exists only in its heading.
    top_text, top_meta, _score = ctx_store.similarity_search("yards", k=1)[0]
    assert top_meta["rule_id"] == "Rule 26, Table 4"
    # The returned excerpt is the bare text, without the breadcrumb.
    assert top_text == YARDS


def test_context_is_part_of_what_gets_embedded(index_dir):
    provider = FakeEmbeddingProvider()
    store = RuleVectorStore(provider, index_dir)
    store.load_or_create()
    store.add_texts([YARDS], [YARDS_META])
    assert provider.calls[-1] == [f"{YARDS_META['context']}\n{YARDS}"]


def test_same_text_under_two_headings_is_two_chunks(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    text = "The minimum shall be 3 metres."
    added = store.add_texts(
        [text, text],
        [{"context": "Rule 26 Yards"}, {"context": "Rule 28 Access"}],
    )
    assert added == 2
    # ... while an exact repeat (same heading) is still de-duplicated.
    assert store.add_texts([text], [{"context": "Rule 26 Yards"}]) == 0


def test_context_survives_a_reload(ctx_store, index_dir):
    reloaded = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    reloaded.load_or_create()
    assert reloaded.similarity_search("yards", k=1)[0][1]["rule_id"] == (
        "Rule 26, Table 4"
    )
    assert reloaded.index_text(0).startswith("CHAPTER IV OCCUPANCY")


# -- tokenizer / synonyms in the lexical channel ------------------------------
def test_lexical_channel_ignores_punctuation_and_plurals(ctx_store):
    hits = ctx_store.lexical_search("parking spaces?", k=3)
    assert hits[0][1]["rule_id"] == "Rule 29(1)"


def test_lexical_channel_bridges_setback_and_yard(ctx_store):
    # "setback" appears nowhere in the corpus; the rulebook says "yards".
    hits = ctx_store.lexical_search("front setback", k=3)
    assert hits and hits[0][1]["rule_id"] == "Rule 26, Table 4"


def test_lexical_channel_bridges_far_and_fsi(ctx_store):
    hits = ctx_store.lexical_search("maximum FAR", k=3)
    assert hits[0][1]["rule_id"] == "Rule 7"


def test_lexical_search_returns_nothing_without_a_keyword_match(ctx_store):
    assert ctx_store.lexical_search("xylophone zebra", k=3) == []


def test_lexical_search_on_empty_store(store):
    assert store.lexical_search("anything") == []


# -- score_queries ------------------------------------------------------------
def test_score_queries_embeds_all_queries_in_one_call(index_dir):
    provider = FakeEmbeddingProvider()
    store = RuleVectorStore(provider, index_dir)
    store.load_or_create()
    store.add_texts([YARDS, PARKING, FSI], [YARDS_META, PARKING_META, FSI_META])
    before = len(provider.calls)
    scored = store.score_queries(["parking space", "floor space index", "yards"])
    assert len(provider.calls) == before + 1
    assert len(provider.calls[-1]) == 3
    assert [s.query for s in scored] == ["parking space", "floor space index", "yards"]


def test_score_queries_is_aligned_with_chunk_ids(ctx_store):
    parking, fsi = ctx_store.score_queries(["car parking space", "floor space index"])
    assert len(parking.fused) == len(parking.dense) == len(parking.lexical) == 3
    assert max(range(3), key=lambda i: parking.fused[i]) == 1
    assert max(range(3), key=lambda i: fsi.fused[i]) == 2


def test_score_queries_fused_matches_similarity_search(ctx_store):
    query = "car parking space for dwelling"
    (scores,) = ctx_store.score_queries([query])
    ranked = ctx_store.similarity_search(query, k=3)
    by_rule = {m["rule_id"]: s for _t, m, s in ranked}
    for idx in range(3):
        _text, meta = ctx_store.chunk(idx)
        assert scores.fused[idx] == pytest.approx(by_rule[meta["rule_id"]])


def test_score_queries_channels_are_bounded(ctx_store):
    (scores,) = ctx_store.score_queries(["parking"])
    assert all(-1.0001 <= s <= 1.0001 for s in scores.dense)
    assert all(0.0 <= s <= 1.0 for s in scores.lexical)
    assert max(scores.lexical) == pytest.approx(1.0)


def test_score_queries_on_empty_store_or_no_queries(store, ctx_store):
    assert store.score_queries(["anything"]) == []
    assert ctx_store.score_queries([]) == []


def test_score_queries_without_bm25_is_dense_only(index_dir, monkeypatch):
    from app.rag import vectorstore as vs

    monkeypatch.setattr(vs, "BM25Okapi", None)
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    store.add_texts([YARDS, PARKING], [YARDS_META, PARKING_META])
    (scores,) = store.score_queries(["car parking space"])
    assert scores.fused == scores.dense
    assert scores.lexical == [0.0, 0.0]


# -- introspection -------------------------------------------------------------
def test_token_set_includes_heading_words(ctx_store):
    assert "yard" in ctx_store.token_set(0)
    assert "parking" in ctx_store.token_set(1)


def test_document_stats_summarise_each_source(ctx_store):
    stats = {d["source"]: d for d in ctx_store.document_stats()}
    assert stats["kpbr.pdf"] == {
        "source": "kpbr.pdf",
        "chunks": 2,
        "rules": 2,  # Rule 26 and Rule 29 (sub-rules and tables fold in)
        "pages": 58,
    }
    assert stats["sample.txt"]["chunks"] == 1
    assert stats["sample.txt"]["pages"] is None


def test_document_stats_do_not_count_positional_ids_as_rules(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    store.add_texts(
        ["alpha text", "beta text"],
        [
            {"source": "n.txt", "rule_id": "n.txt#chunk-1"},
            {"source": "n.txt", "rule_id": "n.txt#chunk-2"},
        ],
    )
    assert store.document_stats() == [
        {"source": "n.txt", "chunks": 2, "rules": 0, "pages": None}
    ]


def test_document_stats_empty(store):
    assert store.document_stats() == []
