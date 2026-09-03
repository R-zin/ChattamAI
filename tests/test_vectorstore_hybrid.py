"""Tests for hybrid (BM25 + cosine) retrieval in ``RuleVectorStore`` (T3.3).

Offline and deterministic, backed by ``tests.conftest.FakeEmbeddingProvider``
(token feature-hashing, no network) and the ``index_dir``/``make_populated_store``
helpers. BM25 is pure-python (``rank_bm25``) and needs no model.

The store now fuses two signals: the dense cosine similarity (L2-normalised,
``IndexFlatIP``) and a BM25 lexical score, normalised to comparable scales and
summed with the dense path weighted ~0.7 (``RAG_HYBRID_WEIGHT``). Dense-only
retrieval (the previous behaviour) is preserved via ``dense_only_search`` and
``similarity_search(use_hybrid=False)``. ``_INDEX_VERSION`` was bumped 2 -> 3 so
old on-disk indexes are ignored and rebuilt.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.rag import vectorstore as vs
from app.rag.vectorstore import _INDEX_VERSION, RuleVectorStore
from tests.conftest import FakeEmbeddingProvider, make_populated_store

RULE5 = "Rule 5: The minimum front setback for a building up to 10m is 1.8m."
RULE7 = "Rule 7: The maximum floor space index (FSI) for residential use is 1.5."

# Two chunks sharing every query token identically (a dense tie), where B
# repeats the rare token "smoke" -> a BM25 term-frequency boost. This isolates
# the lexical channel: dense cannot separate them, BM25 does.
TIE_QUERY = "visible smoke coverage plume detection zone occupancy alarm sensor"
TIE_TEXTS = [
    "visible smoke coverage plume detection zone occupancy alarm sensor",
    "visible smoke coverage plume detection zone occupancy alarm sensor smoke smoke",
]
TIE_METAS = [{"rule_id": "A"}, {"rule_id": "B"}]


def _tie_store(index_dir) -> RuleVectorStore:
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    store.add_texts(TIE_TEXTS, TIE_METAS)
    return store


# ---------------------------------------------------------------------------
# hybrid ranking
# ---------------------------------------------------------------------------
def test_hybrid_ranks_related_chunk_first(populated_store):
    # A topical "front setback" query retrieves the setback rule ahead of the
    # unrelated parking/FSI rules (the dense-only contract, preserved under
    # fusion by a meaningful margin).
    results = populated_store.similarity_search("minimum front setback height", k=3)
    assert results[0][1]["rule_id"] == "Rule 5"


def test_hybrid_exact_copy_scores_one_and_ranks_first(populated_store):
    results = populated_store.similarity_search(RULE5, k=3)
    top_text, top_meta, top_score = results[0]
    assert top_text == RULE5
    assert top_meta["rule_id"] == "Rule 5"
    assert top_score == pytest.approx(1.0)


def test_hybrid_scores_are_descending(populated_store):
    results = populated_store.similarity_search(RULE7, k=3)
    scores = [s for _t, _m, s in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_lexical_channel_breaks_dense_tie(index_dir):
    # Dense-only cannot separate the two chunks (identical token sets -> cosine
    # tie). The lexical (BM25) channel boosts the chunk that repeats the rare
    # token, breaking the tie deterministically in its favour.
    store = _tie_store(index_dir)
    dense = store.dense_only_search(TIE_QUERY, k=2)
    assert [m["rule_id"] for _t, m, s in dense][0] in {"A", "B"}
    assert dense[0][2] == pytest.approx(dense[1][2])  # dense tie

    hybrid = store.similarity_search(TIE_QUERY, k=2)
    assert hybrid[0][1]["rule_id"] == "B"  # keyword-heavy chunk wins on BM25
    assert hybrid[0][2] > hybrid[1][2]  # fusion separates the tied pair


# ---------------------------------------------------------------------------
# dense-only path stays intact
# ---------------------------------------------------------------------------
def test_dense_only_search_matches_previous_cosine_behaviour(populated_store):
    results = populated_store.dense_only_search(RULE5, k=3)
    assert results[0][1]["rule_id"] == "Rule 5"
    assert results[0][2] == pytest.approx(1.0)  # raw cosine self-match


def test_use_hybrid_false_reproduces_dense_only(index_dir):
    store = _tie_store(index_dir)
    flagged = store.similarity_search(TIE_QUERY, k=2, use_hybrid=False)
    dense = store.dense_only_search(TIE_QUERY, k=2)
    assert [(t, m["rule_id"], round(s, 6)) for t, m, s in flagged] == [
        (t, m["rule_id"], round(s, 6)) for t, m, s in dense
    ]


def test_hybrid_differs_from_dense_only(index_dir):
    # Fusion actually engages: hybrid scores are not the raw cosine scores.
    store = _tie_store(index_dir)
    hybrid = {m["rule_id"]: s for _t, m, s in store.similarity_search(TIE_QUERY, k=2)}
    dense = {m["rule_id"]: s for _t, m, s in store.dense_only_search(TIE_QUERY, k=2)}
    assert hybrid != dense


def test_score_threshold_still_filters(populated_store):
    only_self = populated_store.similarity_search(RULE5, k=3, score_threshold=0.99)
    assert [m["rule_id"] for _t, m, s in only_self] == ["Rule 5"]
    none = populated_store.similarity_search(RULE5, k=3, score_threshold=1.0001)
    assert none == []


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------
def test_hybrid_search_is_deterministic(index_dir):
    # Build fresh stores over separate tmp dirs and compare full rankings.
    outs = []
    for _ in range(3):
        d = Path(tempfile.mkdtemp())
        s = RuleVectorStore(FakeEmbeddingProvider(), d)
        s.load_or_create()
        s.add_texts(TIE_TEXTS, TIE_METAS)
        outs.append(
            [
                (m["rule_id"], round(sc, 6))
                for _t, m, sc in s.similarity_search(TIE_QUERY, k=2)
            ]
        )
    assert outs[0] == outs[1] == outs[2]


# ---------------------------------------------------------------------------
# version bump ignores old-format indexes
# ---------------------------------------------------------------------------
def test_version_is_bumped_to_3():
    assert _INDEX_VERSION == 3


def test_old_version_index_is_ignored_and_rebuilt(index_dir):
    # Populate and persist under the current version, then doctor the on-disk
    # metadata to claim a stale version. A fresh store must ignore the index
    # (size 0) and rebuild on next add.
    make_populated_store(FakeEmbeddingProvider(), index_dir)
    with open(index_dir / "rules_meta.json", encoding="utf-8") as fh:
        data = json.load(fh)
    data["version"] = 2  # pretend the index was written by the old format
    with open(index_dir / "rules_meta.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh)

    stale = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    stale.load_or_create()
    assert stale.size == 0  # old-format index ignored, not mis-read


def test_persistence_round_trip_under_new_version(index_dir):
    make_populated_store(FakeEmbeddingProvider(), index_dir)
    reloaded = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    reloaded.load_or_create()
    assert reloaded.size == 3
    results = reloaded.similarity_search(RULE7, k=1)
    assert results[0][1]["rule_id"] == "Rule 7"


# ---------------------------------------------------------------------------
# graceful degradation when BM25 is unavailable
# ---------------------------------------------------------------------------
def test_missing_bm25_falls_back_to_dense_only(index_dir, monkeypatch):
    # Simulate the optional dependency being absent: similarity_search must
    # silently degrade to (and identically match) dense-only retrieval.
    monkeypatch.setattr(vs, "BM25Okapi", None)
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    store.add_texts(TIE_TEXTS, TIE_METAS)
    assert store.hybrid_available is False

    hybrid = store.similarity_search(TIE_QUERY, k=2)
    dense = store.dense_only_search(TIE_QUERY, k=2)
    assert [(t, m["rule_id"]) for t, m, s in hybrid] == [
        (t, m["rule_id"]) for t, m, s in dense
    ]


# ---------------------------------------------------------------------------
# optional ANN dense index (behind a flag)
# ---------------------------------------------------------------------------
def test_ann_ivf_backend_searches(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir, ann_backend="ivf")
    store.load_or_create()
    store.add_texts(TIE_TEXTS + [RULE5], TIE_METAS + [{"rule_id": "Rule 5"}])
    assert store.size == 3
    results = store.similarity_search(TIE_QUERY, k=3)
    assert results, "ANN index should return results"
    assert all(r[1]["rule_id"] in {"A", "B", "Rule 5"} for r in results)


def test_ann_hnsw_backend_searches(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir, ann_backend="hnsw")
    store.load_or_create()
    store.add_texts(
        TIE_TEXTS + [RULE5, RULE7],
        TIE_METAS + [{"rule_id": "Rule 5"}, {"rule_id": "Rule 7"}],
    )
    results = store.dense_only_search(RULE5, k=4)
    assert results[0][1]["rule_id"] == "Rule 5"


def test_flat_backend_remains_default_and_exact(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    store.add_texts(TIE_TEXTS, TIE_METAS)
    assert store.ann_backend == "flat"
    # Exact flat index: every chunk is retrievable with an exact-copy query.
    assert store.dense_only_search(TIE_TEXTS[0], k=2)[0][2] == pytest.approx(1.0)
