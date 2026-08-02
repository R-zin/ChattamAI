"""Tests for ``app.rag.vectorstore.RuleVectorStore`` backed by
:class:`~tests.conftest.FakeEmbeddingProvider` (offline, deterministic).

The fake embeds identical texts to identical unit vectors, so an exact-copy
query is always its own nearest neighbour. CURRENT SCORE SEMANTICS: the store
returns raw FAISS ``IndexFlatL2`` **squared-L2 distance** — *lower is better*,
and an exact match scores ~0.0. Agent-1 is changing this to a normalised
similarity score (higher=better) with a threshold; when that lands, the
ordering/zero-distance assertions below should be inverted accordingly.
"""

from __future__ import annotations

import numpy as np

from app.rag.vectorstore import RuleVectorStore
from tests.conftest import FakeEmbeddingProvider, make_populated_store

RULE5 = "Rule 5: The minimum front setback for a building up to 10m is 1.8m."
RULE7 = "Rule 7: The maximum floor space index (FSI) for residential use is 1.5."


def test_provider_returns_expected_shape_and_dtype(fake_provider):
    out = fake_provider.embed(["a", "b", "c"])
    assert out.shape == (3, fake_provider.dim)
    assert out.dtype == np.float32


def test_provider_is_deterministic():
    a = FakeEmbeddingProvider(dim=8)
    b = FakeEmbeddingProvider(dim=8)
    np.testing.assert_allclose(a.embed([RULE5]), b.embed([RULE5]))


def test_add_texts_increases_size(store):
    assert store.size == 0
    store.add_texts(["alpha rule", "beta rule"], [{"n": 1}, {"n": 2}])
    assert store.size == 2


def test_similarity_search_returns_exact_match_first(populated_store):
    results = populated_store.similarity_search(RULE5, k=3)
    assert results, "expected at least one result"
    top_text, top_meta, top_score = results[0]
    # Exact-copy query -> distance 0 -> ranked first (lower = better, current).
    assert top_text == RULE5
    assert top_meta["rule_id"] == "Rule 5"
    assert top_score == 0.0


def test_scores_are_ascending_distances(populated_store):
    results = populated_store.similarity_search(RULE7, k=3)
    scores = [s for _t, _m, s in results]
    assert scores == sorted(scores)
    assert scores[0] == 0.0  # self match


def test_k_is_capped_by_index_size(populated_store):
    results = populated_store.similarity_search(RULE5, k=100)
    assert len(results) <= populated_store.size


def test_empty_index_returns_empty_list(store):
    assert store.size == 0
    assert store.similarity_search("anything", k=3) == []


def test_uninitialised_store_returns_empty_list(fake_provider, index_dir):
    # No load_or_create() call -> _index is None -> search returns [].
    fresh = RuleVectorStore(fake_provider, index_dir)
    assert fresh.similarity_search("anything", k=3) == []


def test_persistence_round_trip(fake_provider, index_dir):
    # Populate, then a NEW instance over the same dir must reload identically.
    make_populated_store(fake_provider, index_dir)
    reloaded = RuleVectorStore(fake_provider, index_dir)
    reloaded.load_or_create()
    assert reloaded.size == 3

    results = reloaded.similarity_search(RULE7, k=1)
    assert results[0][1]["rule_id"] == "Rule 7"
    assert results[0][2] == 0.0


def test_index_and_meta_files_written(fake_provider, index_dir):
    make_populated_store(fake_provider, index_dir)
    assert (index_dir / "rules.faiss").exists()
    assert (index_dir / "rules_meta.json").exists()


def test_add_texts_empty_is_noop(store):
    store.add_texts([])
    assert store.size == 0


def test_add_texts_without_metas_uses_empty_dict(store):
    store.add_texts(["a lonely rule"])
    results = store.similarity_search("a lonely rule", k=1)
    assert results[0][0] == "a lonely rule"
    assert results[0][1] == {}
