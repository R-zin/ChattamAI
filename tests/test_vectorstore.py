"""Tests for ``app.rag.vectorstore.RuleVectorStore`` backed by
:class:`~tests.conftest.FakeEmbeddingProvider` (offline, deterministic).

CURRENT (optimized) score semantics — agent-1 switched the store to
L2-normalised embeddings in an ``IndexFlatIP`` index, so the returned score is a
**cosine similarity in [-1, 1] where HIGHER = more similar** (an exact-copy
query scores ~1.0 and ranks FIRST; results are ordered descending). Hits below
``score_threshold`` are dropped. Our token-hash fake gives semantic structure:
an identical text scores 1.0, a topically-related query ranks the matching rule
first. On-disk metadata now also carries ``version``/``model``/``dim``/``hashes``
and each chunk meta gains a ``sha256`` content-hash for idempotent dedup.
"""

from __future__ import annotations

import json

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
    a = FakeEmbeddingProvider(dim=64)
    b = FakeEmbeddingProvider(dim=64)
    np.testing.assert_allclose(a.embed([RULE5]), b.embed([RULE5]))


def test_provider_returns_unit_vectors(fake_provider):
    out = fake_provider.embed([RULE5, RULE7])
    norms = np.linalg.norm(out.astype("float64"), axis=1)
    np.testing.assert_allclose(norms, np.ones(2), atol=1e-5)


def test_add_texts_returns_count_and_increases_size(store):
    assert store.size == 0
    added = store.add_texts(["alpha rule", "beta rule"], [{"n": 1}, {"n": 2}])
    assert added == 2
    assert store.size == 2


def test_similarity_search_returns_exact_match_first_with_score_one(populated_store):
    results = populated_store.similarity_search(RULE5, k=3)
    assert results, "expected at least one result"
    top_text, top_meta, top_score = results[0]
    # Cosine (higher = better): an exact-copy query scores ~1.0 and ranks first.
    assert top_text == RULE5
    assert top_meta["rule_id"] == "Rule 5"
    assert top_score == 1.0


def test_scores_are_descending_similarities(populated_store):
    results = populated_store.similarity_search(RULE7, k=3)
    scores = [s for _t, _m, s in results]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 1.0  # self match is the maximum


def test_topical_query_ranks_the_matching_rule_first(populated_store):
    # A query about "front setback" must retrieve the setback rule ahead of the
    # unrelated parking/FSI rules (cosine on lexical overlap, higher = better).
    results = populated_store.similarity_search("minimum front setback height", k=3)
    assert results[0][1]["rule_id"] == "Rule 5"


def test_score_threshold_filters_low_similarity_hits(populated_store):
    # All hits for this query have cosine <= ~1.0; a threshold just below 1
    # keeps only the exact match, and a threshold above it drops everything.
    only_self = populated_store.similarity_search(RULE5, k=3, score_threshold=0.99)
    assert [m["rule_id"] for _t, m, s in only_self] == ["Rule 5"]

    none = populated_store.similarity_search(RULE5, k=3, score_threshold=1.0001)
    assert none == []


def test_store_level_default_threshold_is_applied(fake_provider, index_dir):
    # Constructing with a store default threshold filters without a per-call arg.
    store = RuleVectorStore(fake_provider, index_dir, score_threshold=0.999)
    store.load_or_create()
    store.add_texts([RULE5, RULE7], [{"rule_id": "Rule 5"}, {"rule_id": "Rule 7"}])
    results = store.similarity_search(RULE5, k=2)
    assert [m["rule_id"] for _t, m, s in results] == ["Rule 5"]


def test_per_call_threshold_overrides_store_default(fake_provider, index_dir):
    store = RuleVectorStore(fake_provider, index_dir, score_threshold=0.999)
    store.load_or_create()
    store.add_texts([RULE5, RULE7], [{"rule_id": "Rule 5"}, {"rule_id": "Rule 7"}])
    # A permissive per-call threshold brings the second rule back.
    results = store.similarity_search(RULE5, k=2, score_threshold=-1.0)
    assert len(results) == 2


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
    assert results[0][2] == 1.0


def test_index_and_meta_files_written(fake_provider, index_dir):
    make_populated_store(fake_provider, index_dir)
    assert (index_dir / "rules.faiss").exists()
    assert (index_dir / "rules_meta.json").exists()


def test_meta_file_carries_version_dim_and_hashes(fake_provider, index_dir):
    make_populated_store(fake_provider, index_dir)
    with open(index_dir / "rules_meta.json", encoding="utf-8") as fh:
        meta = json.load(fh)
    assert meta["version"] == 2
    assert meta["dim"] == fake_provider.dim
    assert set(meta.keys()) >= {
        "version",
        "model",
        "dim",
        "texts",
        "metas",
        "hashes",
    }
    assert len(meta["texts"]) == 3
    assert len(meta["metas"]) == 3


def test_add_texts_empty_is_noop(store):
    assert store.add_texts([]) == 0
    assert store.size == 0


def test_add_texts_adds_sha256_hash(store):
    store.add_texts(["a lonely rule"], [{"custom": "m"}])
    results = store.similarity_search("a lonely rule", k=1)
    assert results[0][0] == "a lonely rule"
    meta = results[0][1]
    # Passed meta is preserved AND a content-hash key is added for dedup.
    assert meta["custom"] == "m"
    assert "sha256" in meta
    assert len(meta["sha256"]) == 64


def test_add_texts_without_metas_uses_sha256_only(store):
    store.add_texts(["a lonely rule"])
    results = store.similarity_search("a lonely rule", k=1)
    meta = results[0][1]
    assert set(meta.keys()) == {"sha256"}


def test_add_texts_dedups_identical_content(store):
    assert store.add_texts(["dup rule text"]) == 1
    assert store.size == 1
    # Re-adding the same content is skipped (idempotent re-ingest).
    assert store.add_texts(["dup rule text"]) == 0
    assert store.size == 1
