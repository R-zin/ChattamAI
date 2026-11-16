"""Topic-aware multi-query retrieval over the rule index.

The original pipeline embedded the whole fact sheet as a single query and took
the top ``k`` chunks. A fact sheet covers many unrelated subjects (setbacks,
FSI, parking, stairs...), so one embedding of all of them is a blurry average:
whichever subject dominates the wording wins every slot and the rest are never
checked. This retriever replaces that with four deterministic steps, none of
which needs an extra model call or an extra embedding round trip:

1. **Decompose.** The facts are split by regulated topic (app/rag/lexicon.py).
   Each topic becomes its own query in the vocabulary the rules use, alongside
   the original full-facts query.
2. **Score once.** All queries are embedded in one batch and scored against
   every chunk on both channels (dense cosine + BM25) by
   ``RuleVectorStore.score_queries``.
3. **Grade and correct.** For each topic the best-ranked chunk that actually
   *contains evidence of that topic* is chosen. When the hybrid ranking has no
   such chunk, a corrective pass re-ranks the whole index on the lexical channel
   alone. A topic with no evidence anywhere is reported as a coverage **gap**
   rather than silently padded with unrelated rules.
4. **Fuse and diversify.** Remaining slots are filled by reciprocal-rank fusion
   across all queries, with maximal-marginal-relevance to avoid spending two
   slots on near-duplicate (overlapping) chunks.

The outcome is a result list in the store's ``(text, meta, score)`` shape plus a
:class:`RetrievalTrace` describing what was asked, what covers which topic, and
what is missing - surfaced to the analyst prompt and the API response.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.rag.lexicon import TOPICS, TOPICS_BY_KEY, Topic, detect_topics, parse_facts

logger = logging.getLogger(__name__)

Hit = Tuple[str, dict, float]

STRATEGIES = ("advanced", "simple")


@dataclass
class RetrievalConfig:
    #: "advanced" (multi-query, graded, fused) or "simple" (one hybrid query).
    strategy: str = "advanced"
    #: Reciprocal-rank-fusion constant; larger flattens rank differences.
    rrf_k: int = 60
    #: MMR trade-off: 1.0 = relevance only, 0.0 = diversity only.
    mmr_lambda: float = 0.75
    #: How deep into each query's ranking candidates are considered.
    candidates_per_query: int = 12
    #: Re-rank lexically when a topic has no evidence in the hybrid ranking.
    corrective: bool = True


@dataclass
class QuerySpec:
    label: str
    text: str
    topic: Optional[str] = None  # topic key; None for the full query


@dataclass
class TopicCoverage:
    topic: str
    label: str
    #: "covered" | "recovered" (found by the corrective pass) | "gap"
    status: str
    rule_ids: List[str] = field(default_factory=list)
    #: For a gap: "not_in_index" or "truncated" (evidence exists, top_k cut it).
    reason: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "topic": self.topic,
            "label": self.label,
            "status": self.status,
            "rule_ids": self.rule_ids,
            "reason": self.reason,
        }


@dataclass
class RetrievalTrace:
    strategy: str
    queries: List[QuerySpec] = field(default_factory=list)
    coverage: List[TopicCoverage] = field(default_factory=list)
    candidates: int = 0
    corrective_hits: int = 0

    @property
    def gaps(self) -> List[str]:
        return [c.label for c in self.coverage if c.status == "gap"]

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "queries": [
                {"label": q.label, "text": q.text, "topic": q.topic}
                for q in self.queries
            ],
            "coverage": [c.as_dict() for c in self.coverage],
            "gaps": self.gaps,
            "candidates": self.candidates,
            "corrective_hits": self.corrective_hits,
        }


def build_query_plan(query: str, facts_mode: bool = True) -> List[QuerySpec]:
    """The full query plus one focused query per regulated topic it touches.

    In ``facts_mode`` the text is an extracted fact sheet (``- parameter:
    value`` lines); otherwise it is a free-text question.
    """
    plan = [QuerySpec(label="Full query", text=query)]
    grouped: Dict[str, List[str]] = {}
    occupancy = ""
    if facts_mode:
        for fact in parse_facts(query):
            for key in fact.topics:
                grouped.setdefault(key, []).append(fact.parameter)
            if "occupancy" in fact.topics and fact.value and not occupancy:
                occupancy = fact.value
    else:
        for topic in detect_topics(query):
            grouped.setdefault(topic.key, [])
    for topic in TOPICS:
        if topic.key not in grouped:
            continue
        parts = [topic.query]
        # Fact names carry the plan's own wording ("front setback"); the plan's
        # values are left out, since "1m" in a plan says nothing about a rule.
        names = list(dict.fromkeys(grouped[topic.key]))[:4]
        if names:
            parts.append(", ".join(names))
        if not facts_mode:
            parts.append(query)
        elif occupancy and topic.key != "occupancy":
            parts.append(occupancy)
        plan.append(
            QuerySpec(label=topic.label, text=". ".join(parts), topic=topic.key)
        )
    return plan


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class RuleRetriever:
    """Retrieval strategy layered over a :class:`RuleVectorStore`."""

    def __init__(self, store, config: Optional[RetrievalConfig] = None) -> None:
        self.store = store
        self.config = config or RetrievalConfig()

    # -- public API ---------------------------------------------------------
    def retrieve(
        self,
        query: str,
        k: int = 6,
        facts_mode: bool = True,
        strategy: Optional[str] = None,
    ) -> Tuple[List[Hit], RetrievalTrace]:
        """Return up to ``k`` hits (best first) and the retrieval trace."""
        strategy = (strategy or self.config.strategy or "advanced").lower()
        if strategy not in STRATEGIES:
            strategy = "advanced"
        plan = build_query_plan(query, facts_mode=facts_mode)
        size = getattr(self.store, "size", 0)
        k = max(1, int(k))

        if size == 0:
            return [], RetrievalTrace(strategy=strategy, queries=plan[:1])
        if strategy == "simple" or not hasattr(self.store, "score_queries"):
            hits = self.store.similarity_search(query, k=k)
            trace = RetrievalTrace(strategy="simple", queries=plan[:1])
            trace.candidates = len(hits)
            trace.coverage = self._coverage_from_hits(plan, hits)
            return hits, trace
        return self._advanced(plan, k)

    # -- advanced strategy --------------------------------------------------
    def _advanced(
        self, plan: List[QuerySpec], k: int
    ) -> Tuple[List[Hit], RetrievalTrace]:
        store = self.store
        cfg = self.config
        n = store.size
        k = min(k, n)
        threshold = store.score_threshold
        depth = max(cfg.candidates_per_query, 2 * k)
        scored = store.score_queries([q.text for q in plan])

        def passes(score: float) -> bool:
            return threshold is None or score >= threshold

        # Per-query rankings on the hybrid score, RRF across them, and the best
        # hybrid score each chunk achieved under any query (the reported score).
        rankings: List[List[int]] = []
        rrf: Dict[int, float] = {}
        best: Dict[int, float] = {}
        best_query: Dict[int, int] = {}
        for qi, qs in enumerate(scored):
            order = sorted(range(n), key=lambda i: (-qs.fused[i], i))[:depth]
            order = [i for i in order if passes(qs.fused[i])]
            rankings.append(order)
            for rank, i in enumerate(order):
                rrf[i] = rrf.get(i, 0.0) + 1.0 / (cfg.rrf_k + rank + 1)
                if qs.fused[i] > best.get(i, float("-inf")):
                    best[i] = qs.fused[i]
                    best_query[i] = qi

        trace = RetrievalTrace(strategy="advanced", queries=plan)
        trace.candidates = len(rrf)

        # Grade: per topic, the best-ranked chunk carrying evidence of it.
        selected: List[int] = []
        corrective: Dict[int, int] = {}  # chunk id -> query index
        picks: Dict[str, Optional[int]] = {}  # topic -> its chosen chunk
        for qi, spec in enumerate(plan):
            if spec.topic is None:
                continue
            topic = TOPICS_BY_KEY[spec.topic]
            pick = self._first_with_evidence(rankings[qi], topic)
            if pick is None and cfg.corrective:
                lexical = scored[qi].lexical
                by_keyword = sorted(range(n), key=lambda i: (-lexical[i], i))[:depth]
                by_keyword = [
                    i
                    for i in by_keyword
                    if lexical[i] > 0.0 and passes(scored[qi].fused[i])
                ]
                pick = self._first_with_evidence(by_keyword, topic)
                if pick is not None and pick not in best:
                    corrective[pick] = qi
                    best[pick] = scored[qi].fused[pick]
                    best_query[pick] = qi
                    trace.corrective_hits += 1
            picks[spec.topic] = pick
            if pick is not None and pick not in selected and len(selected) < k:
                selected.append(pick)

        # Fuse + diversify: fill what is left by RRF with an MMR penalty.
        selected = self._mmr_fill(selected, rrf, k)

        selected.sort(key=lambda i: (-best[i], i))
        hits: List[Hit] = []
        for i in selected:
            text, meta = store.chunk(i)
            meta = dict(meta)
            meta["topics"] = self._topics_of(i, plan)
            meta["retrieved_by"] = plan[best_query[i]].label
            if i in corrective:
                meta["corrective"] = True
            hits.append((text, meta, float(best[i])))

        trace.coverage = self._coverage(plan, selected, picks, corrective)
        return hits, trace

    def _first_with_evidence(self, order: List[int], topic: Topic) -> Optional[int]:
        for i in order:
            if topic.evidence.search(self.store.index_text(i)):
                return i
        return None

    def _mmr_fill(
        self, selected: List[int], rrf: Dict[int, float], k: int
    ) -> List[int]:
        if len(selected) >= k or not rrf:
            return selected[:k]
        lam = self.config.mmr_lambda
        top = max(rrf.values()) or 1.0
        pool = [i for i in sorted(rrf, key=lambda i: (-rrf[i], i)) if i not in selected]
        chosen = list(selected)
        while pool and len(chosen) < k:
            best_i, best_value = pool[0], float("-inf")
            for i in pool:
                redundancy = max(
                    (
                        _jaccard(self.store.token_set(i), self.store.token_set(j))
                        for j in chosen
                    ),
                    default=0.0,
                )
                value = lam * (rrf[i] / top) - (1.0 - lam) * redundancy
                if value > best_value:
                    best_i, best_value = i, value
            chosen.append(best_i)
            pool.remove(best_i)
        return chosen

    # -- coverage reporting -------------------------------------------------
    def _topics_of(self, idx: int, plan: List[QuerySpec]) -> List[str]:
        text = self.store.index_text(idx)
        return [
            TOPICS_BY_KEY[q.topic].label
            for q in plan
            if q.topic and TOPICS_BY_KEY[q.topic].evidence.search(text)
        ]

    def _coverage(
        self,
        plan: List[QuerySpec],
        selected: List[int],
        picks: Dict[str, Optional[int]],
        corrective: Dict[int, int],
    ) -> List[TopicCoverage]:
        out: List[TopicCoverage] = []
        for qi, spec in enumerate(plan):
            if spec.topic is None:
                continue
            topic = TOPICS_BY_KEY[spec.topic]
            pick = picks.get(spec.topic)
            covering = [
                i for i in selected if topic.evidence.search(self.store.index_text(i))
            ]
            # The rule chosen *for* this topic leads; others merely mention it.
            covering.sort(key=lambda i: i != pick)
            if covering:
                only_corrective = all(corrective.get(i) == qi for i in covering)
                status = "recovered" if only_corrective else "covered"
                rule_ids = _rule_ids(self.store.chunk(i)[1] for i in covering)
                out.append(TopicCoverage(topic.key, topic.label, status, rule_ids))
            else:
                reason = "truncated" if pick is not None else "not_in_index"
                out.append(TopicCoverage(topic.key, topic.label, "gap", [], reason))
        return out

    def _coverage_from_hits(
        self, plan: List[QuerySpec], hits: List[Hit]
    ) -> List[TopicCoverage]:
        """Coverage of an arbitrary hit list (the simple strategy)."""
        out: List[TopicCoverage] = []
        for spec in plan:
            if spec.topic is None:
                continue
            topic = TOPICS_BY_KEY[spec.topic]
            covering = [
                meta
                for text, meta, _score in hits
                if topic.evidence.search(f"{meta.get('context') or ''}\n{text}")
            ]
            if covering:
                out.append(
                    TopicCoverage(
                        topic.key, topic.label, "covered", _rule_ids(covering)
                    )
                )
            else:
                out.append(TopicCoverage(topic.key, topic.label, "gap", [], None))
        return out


def _rule_ids(metas) -> List[str]:
    seen: List[str] = []
    for meta in metas:
        rule_id = meta.get("rule_id")
        if rule_id and str(rule_id) not in seen:
            seen.append(str(rule_id))
    return seen
