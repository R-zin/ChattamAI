"""Tests for the topic-aware multi-query retriever (``app.rag.retrieval``).

Two kinds of test: behaviour on a real ``RuleVectorStore`` over the fake
embedder (does decomposition actually rescue topics the single query misses?),
and exact-mechanics tests on a stub store with hand-written scores (corrective
pass, MMR, thresholding), where the ranking is fully controlled.
"""

from __future__ import annotations

from typing import List

import pytest

from app.rag.retrieval import (
    RetrievalConfig,
    RuleRetriever,
    build_query_plan,
)
from app.rag.vectorstore import QueryScores, RuleVectorStore
from tests.conftest import FakeEmbeddingProvider

FACTS = (
    "- plot area: 240 sq.m\n"
    "- front setback: 1 m\n"
    "- rear setback: 2 m\n"
    "- side setback: 1 m\n"
    "- floor space index (FSI): 1.7\n"
    "- parking provision: 1 car space\n"
    "- staircase: 1.0 m wide\n"
    "- occupancy/usage type: residential"
)

# Four setback chunks that echo the fact sheet's wording crowd out everything
# else under a single whole-facts query.
CORPUS = [
    (
        "The front setback, rear setback and side setback shall be kept open.",
        "Rule 26(1)",
    ),
    (
        "Front setback 1 m rear setback 2 m side setback 1 m for small plots.",
        "Rule 26(2)",
    ),
    (
        "Side setback and rear setback of 1 m apply to plot area below 240 sq.m.",
        "Rule 26(3)",
    ),
    (
        "Front setback of residential plot area is measured from the plot boundary.",
        "Rule 26(4)",
    ),
    (
        "The maximum floor space index FSI for residential occupancy shall be 3.",
        "Rule 27",
    ),
    ("Off-street car parking: one parking space for every dwelling unit.", "Rule 29"),
    ("Every staircase shall have a minimum width of 1.2 metres.", "Rule 35"),
    ("The Secretary shall issue the permit within thirty days.", "Rule 9"),
]


def _store(index_dir, corpus=CORPUS, **kwargs) -> RuleVectorStore:
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir, **kwargs)
    store.load_or_create()
    store.add_texts(
        [t for t, _r in corpus],
        [
            {"source": "kpbr.pdf", "rule_id": r, "chunk": i}
            for i, (_t, r) in enumerate(corpus)
        ],
    )
    return store


def _rules(hits) -> List[str]:
    return [meta["rule_id"] for _text, meta, _score in hits]


# ---------------------------------------------------------------------------
# query plan
# ---------------------------------------------------------------------------
def test_plan_has_the_full_query_plus_one_query_per_topic():
    plan = build_query_plan(FACTS)
    assert plan[0].label == "Full query" and plan[0].text == FACTS
    assert [q.topic for q in plan[1:]] == [
        "setbacks",
        "fsi",
        "parking",
        "fire_stair",
        "plot",
        "occupancy",
    ]


def test_topic_query_uses_fact_names_not_plan_values():
    setbacks = next(q for q in build_query_plan(FACTS) if q.topic == "setbacks")
    assert "front setback, rear setback, side setback" in setbacks.text
    # "1 m" in a plan says nothing about what the rule requires.
    assert "1 m" not in setbacks.text
    # Rules differ by occupancy, so it qualifies every topic query.
    assert setbacks.text.endswith("residential")


def test_unspecified_facts_produce_no_query():
    plan = build_query_plan("- parking provision: not specified\n- front setback: 1m")
    assert [q.topic for q in plan[1:]] == ["setbacks"]


def test_question_mode_detects_topics_from_free_text():
    plan = build_query_plan(
        "How many parking spaces does a flat need?", facts_mode=False
    )
    assert [q.topic for q in plan] == [None, "parking"]
    assert "How many parking spaces" in plan[1].text


def test_plan_without_any_topic_is_just_the_full_query():
    plan = build_query_plan("Who signs the completion certificate?", facts_mode=False)
    assert len(plan) == 1


# ---------------------------------------------------------------------------
# behaviour on a real store
# ---------------------------------------------------------------------------
def test_single_query_misses_topics_that_decomposition_recovers(index_dir):
    store = _store(index_dir)
    simple, simple_trace = RuleRetriever(store, RetrievalConfig("simple")).retrieve(
        FACTS, k=4
    )
    advanced, trace = RuleRetriever(store).retrieve(FACTS, k=4)

    # The whole-facts query spends its slots on setback chunks...
    assert sum(r.startswith("Rule 26") for r in _rules(simple)) >= 3
    assert simple_trace.gaps, "the single query should leave topics uncovered"
    # ...the topic-aware retriever gives each regulated subject its rule.
    assert {"Rule 27", "Rule 29", "Rule 35"} <= set(_rules(advanced))
    assert any(r.startswith("Rule 26") for r in _rules(advanced))
    assert len(trace.gaps) < len(simple_trace.gaps)


def test_all_sub_queries_share_one_embedding_call(index_dir):
    store = _store(index_dir)
    provider = store.provider
    before = len(provider.calls)
    _hits, trace = RuleRetriever(store).retrieve(FACTS, k=6)
    assert len(provider.calls) == before + 1
    assert len(provider.calls[-1]) == len(trace.queries) == 7


def test_hits_are_ordered_by_score_and_capped_at_k(index_dir):
    hits, _trace = RuleRetriever(_store(index_dir)).retrieve(FACTS, k=3)
    assert len(hits) == 3
    scores = [score for _t, _m, score in hits]
    assert scores == sorted(scores, reverse=True)


def test_k_larger_than_index_returns_every_chunk_once(index_dir):
    hits, _trace = RuleRetriever(_store(index_dir)).retrieve(FACTS, k=50)
    assert sorted(_rules(hits)) == sorted(r for _t, r in CORPUS)


def test_hits_explain_how_they_were_retrieved(index_dir):
    hits, _trace = RuleRetriever(_store(index_dir)).retrieve(FACTS, k=6)
    parking = next(m for _t, m, _s in hits if m["rule_id"] == "Rule 29")
    assert parking["retrieved_by"] == "Parking"
    assert "Parking" in parking["topics"]


def test_store_metadata_is_not_mutated(index_dir):
    store = _store(index_dir)
    RuleRetriever(store).retrieve(FACTS, k=6)
    assert all("topics" not in meta for meta in store._metas)


def test_coverage_reports_which_rule_covers_each_topic(index_dir):
    _hits, trace = RuleRetriever(_store(index_dir)).retrieve(FACTS, k=8)
    coverage = {c.topic: c for c in trace.coverage}
    assert coverage["parking"].status == "covered"
    assert coverage["parking"].rule_ids == ["Rule 29"]
    assert coverage["fire_stair"].rule_ids == ["Rule 35"]
    assert trace.gaps == [] or trace.gaps == ["Occupancy"]


def test_topic_absent_from_the_corpus_is_reported_as_a_gap(index_dir):
    corpus = [c for c in CORPUS if c[1] != "Rule 29"]  # no parking rule at all
    _hits, trace = RuleRetriever(_store(index_dir, corpus)).retrieve(FACTS, k=8)
    parking = next(c for c in trace.coverage if c.topic == "parking")
    assert parking.status == "gap"
    assert parking.reason == "not_in_index"
    assert "Parking" in trace.gaps


def test_gap_is_truncated_when_top_k_is_too_small(index_dir):
    # Six topics, two slots: the lower-priority topics have a rule in the
    # index but no slot to put it in - a different problem from "no rule".
    _hits, trace = RuleRetriever(_store(index_dir)).retrieve(FACTS, k=2)
    stairs = next(c for c in trace.coverage if c.topic == "fire_stair")
    assert stairs.status == "gap"
    assert stairs.reason == "truncated"


def test_simple_strategy_is_the_plain_hybrid_search(index_dir):
    store = _store(index_dir)
    hits, trace = RuleRetriever(store, RetrievalConfig("simple")).retrieve(FACTS, k=4)
    expected = store.similarity_search(FACTS, k=4)
    assert [(t, m["rule_id"], s) for t, m, s in hits] == [
        (t, m["rule_id"], s) for t, m, s in expected
    ]
    assert trace.strategy == "simple"


def test_strategy_can_be_overridden_per_call(index_dir):
    retriever = RuleRetriever(_store(index_dir), RetrievalConfig("simple"))
    _hits, trace = retriever.retrieve(FACTS, k=4, strategy="advanced")
    assert trace.strategy == "advanced"


def test_unknown_strategy_falls_back_to_advanced(index_dir):
    retriever = RuleRetriever(_store(index_dir), RetrievalConfig("bogus"))
    _hits, trace = retriever.retrieve(FACTS, k=4)
    assert trace.strategy == "advanced"


def test_empty_index_returns_nothing(store):
    hits, trace = RuleRetriever(store).retrieve(FACTS, k=4)
    assert hits == []
    assert trace.coverage == [] and trace.gaps == []


def test_question_without_a_topic_still_retrieves(index_dir):
    hits, trace = RuleRetriever(_store(index_dir)).retrieve(
        "Who issues the permit and within how many days?", k=2, facts_mode=False
    )
    assert _rules(hits)[0] == "Rule 9"
    assert trace.coverage == []


def test_trace_serialises_to_the_api_shape(index_dir):
    _hits, trace = RuleRetriever(_store(index_dir)).retrieve(FACTS, k=4)
    payload = trace.as_dict()
    assert payload["strategy"] == "advanced"
    assert set(payload) == {
        "strategy",
        "queries",
        "coverage",
        "gaps",
        "candidates",
        "corrective_hits",
    }
    assert set(payload["coverage"][0]) == {
        "topic",
        "label",
        "status",
        "rule_ids",
        "reason",
    }
    assert payload["queries"][0] == {
        "label": "Full query",
        "text": FACTS,
        "topic": None,
    }


# ---------------------------------------------------------------------------
# exact mechanics on a stub store
# ---------------------------------------------------------------------------
class StubStore:
    """A store whose per-query scores are written by hand."""

    def __init__(self, texts, scores_by_query, threshold=None):
        self.texts = texts
        self.scores_by_query = scores_by_query  # query substring -> (fused, lexical)
        self.score_threshold = threshold
        self.queries_seen: List[List[str]] = []

    @property
    def size(self) -> int:
        return len(self.texts)

    def chunk(self, idx):
        return self.texts[idx], {"rule_id": f"R{idx}", "sha256": str(idx)}

    def index_text(self, idx):
        return self.texts[idx]

    def token_set(self, idx):
        return frozenset(self.texts[idx].lower().split())

    def score_queries(self, queries):
        self.queries_seen.append(list(queries))
        out = []
        for query in queries:
            fused, lexical = next(
                (v for key, v in self.scores_by_query.items() if key in query),
                ([0.0] * self.size, [0.0] * self.size),
            )
            out.append(
                QueryScores(
                    query=query,
                    dense=list(fused),
                    lexical=list(lexical),
                    fused=list(fused),
                )
            )
        return out

    def similarity_search(self, query, k=6):  # pragma: no cover - not used here
        raise AssertionError("advanced strategy must not call similarity_search")


PARKING_Q = "- parking: 1 car"


def test_corrective_pass_rescues_a_topic_the_hybrid_ranking_buried():
    # Depth is 2 (k=1 -> max(candidates, 2k) with candidates=1). The parking
    # rule (index 3) ranks 4th on the fused score, behind three chunks that say
    # nothing about parking, but it is the only keyword match.
    texts = ["alpha", "beta", "gamma", "car parking space"]
    fused = [0.9, 0.8, 0.7, 0.1]
    lexical = [0.0, 0.0, 0.0, 1.0]
    store = StubStore(texts, {"parking": (fused, lexical), PARKING_Q: (fused, lexical)})
    retriever = RuleRetriever(store, RetrievalConfig(candidates_per_query=1))

    hits, trace = retriever.retrieve(PARKING_Q, k=1)
    assert _rules(hits) == ["R3"]
    assert hits[0][1]["corrective"] is True
    assert trace.corrective_hits == 1
    assert trace.coverage[0].status == "recovered"


def test_without_the_corrective_pass_the_topic_is_a_gap():
    texts = ["alpha", "beta", "gamma", "car parking space"]
    fused = [0.9, 0.8, 0.7, 0.1]
    lexical = [0.0, 0.0, 0.0, 1.0]
    store = StubStore(texts, {"parking": (fused, lexical)})
    retriever = RuleRetriever(
        store, RetrievalConfig(candidates_per_query=1, corrective=False)
    )
    hits, trace = retriever.retrieve(PARKING_Q, k=1)
    assert _rules(hits) == ["R0"]
    assert trace.coverage[0].status == "gap"


def test_corrective_pass_requires_a_real_keyword_match():
    # Nothing in the index mentions parking: no lexical score, no rescue.
    texts = ["alpha", "beta", "gamma"]
    store = StubStore(texts, {"parking": ([0.9, 0.8, 0.7], [0.0, 0.0, 0.0])})
    _hits, trace = RuleRetriever(
        store, RetrievalConfig(candidates_per_query=1)
    ).retrieve(PARKING_Q, k=1)
    assert trace.corrective_hits == 0
    assert trace.coverage[0].reason == "not_in_index"


def test_mmr_skips_a_near_duplicate_when_something_else_is_available():
    # 0 and 1 are near-identical (overlapping chunks); 2 is different and only
    # slightly less relevant. With two slots, take 0 and 2 - not 0 and 1.
    texts = [
        "the yard shall be three metres wide at the front",
        "the yard shall be three metres wide at the front side",
        "permit fees are payable to the secretary",
    ]
    fused = [0.9, 0.89, 0.6]
    store = StubStore(texts, {"": (fused, [0.0, 0.0, 0.0])})
    hits, _trace = RuleRetriever(store).retrieve(
        "anything at all", k=2, facts_mode=False
    )
    assert _rules(hits) == ["R0", "R2"]


def test_mmr_lambda_one_is_pure_relevance():
    texts = [
        "the yard shall be three metres wide at the front",
        "the yard shall be three metres wide at the front side",
        "permit fees are payable to the secretary",
    ]
    store = StubStore(texts, {"": ([0.9, 0.89, 0.6], [0.0, 0.0, 0.0])})
    retriever = RuleRetriever(store, RetrievalConfig(mmr_lambda=1.0))
    hits, _trace = retriever.retrieve("anything at all", k=2, facts_mode=False)
    assert _rules(hits) == ["R0", "R1"]


def test_score_threshold_drops_weak_candidates():
    texts = ["alpha", "beta", "gamma"]
    store = StubStore(texts, {"": ([0.9, 0.4, 0.1], [0.0, 0.0, 0.0])}, threshold=0.5)
    hits, _trace = RuleRetriever(store).retrieve("anything", k=3, facts_mode=False)
    assert _rules(hits) == ["R0"]


def test_reported_score_is_the_best_across_sub_queries():
    # Chunk 1 is mediocre for the full query but the top hit for parking.
    texts = ["general provisions", "car parking space"]
    store = StubStore(
        texts,
        {
            "off-street": ([0.2, 0.95], [0.0, 1.0]),  # the parking topic query
            PARKING_Q: ([0.8, 0.3], [0.0, 0.0]),  # the full query
        },
    )
    hits, _trace = RuleRetriever(store).retrieve(PARKING_Q, k=2)
    assert dict((m["rule_id"], s) for _t, m, s in hits) == {"R1": 0.95, "R0": 0.8}
    assert hits[0][1]["retrieved_by"] == "Parking"
    assert hits[1][1]["retrieved_by"] == "Full query"


def test_store_without_score_queries_degrades_to_simple(index_dir):
    class LegacyStore:
        size = 1
        score_threshold = None

        def similarity_search(self, query, k=6):
            return [("Parking rule text", {"rule_id": "R1"}, 0.5)]

    hits, trace = RuleRetriever(LegacyStore()).retrieve(PARKING_Q, k=3)
    assert _rules(hits) == ["R1"]
    assert trace.strategy == "simple"
    assert trace.coverage[0].status == "covered"


@pytest.mark.parametrize("k", [0, -3])
def test_non_positive_k_is_treated_as_one(index_dir, k):
    hits, _trace = RuleRetriever(_store(index_dir)).retrieve(FACTS, k=k)
    assert len(hits) == 1
