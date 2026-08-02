"""LangGraph workflow that turns a building plan into a compliance report.

Flow:
    extract_facts -> retrieve -> analyze -> summarize
                              |
                              +--> (no rules found) -> insufficient -> END

Nodes are plain functions closed over a `Context` so the graph stays easy to
test and the LLM / vector store can be swapped independently. An async graph
(`build_async_compliance_graph`) mirrors the same flow for `RAGSystem.acheck`,
wrapping each blocking call in `asyncio.to_thread` so it can run inside a
running event loop, and overlapping the (independent) query-embedding warm-up
with fact extraction for latency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from functools import partial
from typing import List, Optional, Tuple, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class ComplianceState(TypedDict, total=False):
    plan_text: str
    top_k: int
    facts: str
    retrieved: List[Tuple[str, dict, float]]
    analysis_json: str
    violations: List[dict]
    summary: str
    error: Optional[str]
    # Per-node observability: {node: {"ms": float, "in_chars": int, "out_chars": int}}
    telemetry: dict


@dataclass
class Context:
    llm: object  # ClaudeClient
    store: object  # RuleVectorStore
    default_top_k: int = 6
    # Optional analysis memo (RAGSystem owns it). Maps
    # (facts_hash, index_version) -> (analysis_json, violations). ``None`` = off.
    analysis_cache: object = None


# --------------------------------------------------------------------------
# Telemetry helpers
# --------------------------------------------------------------------------
def _merge_telemetry(state: ComplianceState, node: str, entry: dict) -> dict:
    """Return a telemetry dict for ``state`` with ``node``'s entry merged in."""
    telemetry = dict(state.get("telemetry") or {})
    telemetry[node] = entry
    return telemetry


def _node_span(state: ComplianceState, node: str):
    """Context manager: record elapsed ms + in/out char counts for a node."""
    started = time.perf_counter()

    class _Span:
        def __init__(self) -> None:
            self.in_chars = 0
            self.out_chars = 0
            self.toks_in = 0  # token-ish estimate (~4 chars/token)
            self.toks_out = 0

        def measure_in(self, *texts: object) -> None:
            self.in_chars = sum(len(str(t)) for t in texts)
            self.toks_in = max(1, self.in_chars // 4) if self.in_chars else 0

        def measure_out(self, *texts: object) -> None:
            self.out_chars = sum(len(str(t)) for t in texts)
            self.toks_out = max(1, self.out_chars // 4) if self.out_chars else 0

        def finish(self) -> dict:
            return _merge_telemetry(
                state,
                node,
                {
                    "ms": round((time.perf_counter() - started) * 1000, 1),
                    "in_chars": self.in_chars,
                    "out_chars": self.out_chars,
                    "toks_in": self.toks_in,
                    "toks_out": self.toks_out,
                },
            )

    return _Span()


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------
def extract_facts(state: ComplianceState, ctx: Context) -> dict:
    from app.rag.prompts import SYSTEM_EXTRACT

    span = _node_span(state, "extract_facts")
    span.measure_in(state["plan_text"])
    facts = ctx.llm.complete(SYSTEM_EXTRACT, state["plan_text"])
    span.measure_out(facts)
    return {"facts": facts, "telemetry": span.finish()}


def retrieve(state: ComplianceState, ctx: Context) -> dict:
    # Embed the extracted facts as the retrieval query for best semantic match.
    span = _node_span(state, "retrieve")
    query = state.get("facts") or state["plan_text"]
    k = state.get("top_k") or ctx.default_top_k
    span.measure_in(query)
    results = ctx.store.similarity_search(query, k=k)
    span.measure_out(*[r[0] for r in results])
    return {"retrieved": results, "telemetry": span.finish()}


def analyze(state: ComplianceState, ctx: Context) -> dict:
    from app.rag.prompts import (
        SYSTEM_ANALYZE,
        build_analyze_user,
        format_rules_for_prompt,
    )

    span = _node_span(state, "analyze")
    facts = state["facts"]
    rules_text = format_rules_for_prompt(state["retrieved"])
    user = build_analyze_user(facts, rules_text)
    span.measure_in(user)

    # Analysis memo: an identical re-check (same facts against the same index
    # contents) skips the LLM entirely. Keyed by (facts_hash, index_version).
    memo = ctx.analysis_cache
    memo_key = None
    if memo is not None:
        try:
            import hashlib

            facts_hash = hashlib.sha256(facts.encode("utf-8")).hexdigest()
            index_version = getattr(ctx.store, "size", 0)
            memo_key = (facts_hash, index_version)
            hit = memo.get(memo_key) if hasattr(memo, "get") else None
            if hit is not None:
                cached_json, cached_violations = hit
                span.measure_out(cached_json)
                logger.info("analyze: analysis-cache hit (skipping LLM)")
                return {
                    "analysis_json": cached_json,
                    "violations": cached_violations,
                    "telemetry": span.finish(),
                }
        except Exception:  # caching is best-effort; never break the node
            logger.debug("analyze: memo lookup failed", exc_info=True)
            memo_key = None

    raw = ctx.llm.complete(SYSTEM_ANALYZE, user)
    span.measure_out(raw)

    violations, err = _parse_violations(raw)
    if err is not None:
        # One repair retry: ask the model to re-emit strictly valid JSON.
        logger.warning("analyze: JSON parse failed (%s); attempting repair retry", err)
        repaired = ctx.llm.complete(SYSTEM_ANALYZE_REPAIR, raw)
        span.measure_out(raw, repaired)
        violations, err = _parse_violations(repaired)
        if err is None:
            _memo_put(memo, memo_key, repaired, violations)
            return {
                "analysis_json": repaired,
                "violations": violations,
                "telemetry": span.finish(),
            }
        # Still failing: surface the error rather than silently returning zeros.
        logger.error("analyze: repair retry failed to produce valid JSON")
        msg = err if str(err).startswith("parse_failed") else f"parse_failed: {err}"
        return {
            "analysis_json": raw,
            "violations": [],
            "error": msg,
            "telemetry": span.finish(),
        }
    _memo_put(memo, memo_key, raw, violations)
    return {"analysis_json": raw, "violations": violations, "telemetry": span.finish()}


def summarize(state: ComplianceState, ctx: Context) -> dict:
    from app.rag.prompts import SYSTEM_SUMMARY

    span = _node_span(state, "summarize")
    facts = state.get("facts", "")
    violations = state.get("violations") or []
    user = f"EXTRACTED FACTS:\n{facts}\n\nPOTENTIAL VIOLATIONS:\n{json.dumps(violations, indent=2)}"
    span.measure_in(user)
    summary = ctx.llm.complete(SYSTEM_SUMMARY, user)
    span.measure_out(summary)
    return {"summary": summary, "telemetry": span.finish()}


def insufficient(state: ComplianceState, ctx: Context) -> dict:
    span = _node_span(state, "insufficient")
    return {
        "summary": (
            "No relevant Kerala Building Rules could be retrieved for this plan. "
            "The rule index may be empty or not yet ingested. Please ingest the "
            "Kerala Building Rules documents and retry."
        ),
        "violations": [],
        "telemetry": span.finish(),
    }


# --------------------------------------------------------------------------
# Async nodes (used only by build_async_compliance_graph / RAGSystem.acheck)
# Each wraps the synchronous node body in asyncio.to_thread so blocking
# LLM / embedding / FAISS calls run off the event loop.
# --------------------------------------------------------------------------
async def aextract_facts(state: ComplianceState, ctx: Context) -> dict:
    """Extract facts while concurrently warming the plan embedding.

    The retrieval query embedding is independent of the LLM fact-extraction
    call, so we warm the embedding cache for ``plan_text`` (the fallback
    retrieval query) in parallel via ``asyncio.to_thread``. Both are blocking
    calls pushed onto worker threads; awaiting them together overlaps latency.
    """
    from app.rag.prompts import SYSTEM_EXTRACT

    span = _node_span(state, "extract_facts")
    span.measure_in(state["plan_text"])

    async def _warm_plan_embedding() -> None:
        provider = getattr(ctx.store, "provider", None)
        if provider is not None and hasattr(provider, "embed"):
            try:
                await asyncio.to_thread(provider.embed, [state["plan_text"]])
            except Exception:  # warm-up is best-effort; never fail the node
                logger.debug(
                    "extract_facts: plan embedding warm-up failed", exc_info=True
                )

    facts, _ = await asyncio.gather(
        asyncio.to_thread(ctx.llm.complete, SYSTEM_EXTRACT, state["plan_text"]),
        _warm_plan_embedding(),
    )
    span.measure_out(facts)
    return {"facts": facts, "telemetry": span.finish()}


async def aretrieve(state: ComplianceState, ctx: Context) -> dict:
    span = _node_span(state, "retrieve")
    query = state.get("facts") or state["plan_text"]
    k = state.get("top_k") or ctx.default_top_k
    span.measure_in(query)
    results = await asyncio.to_thread(ctx.store.similarity_search, query, k=k)
    span.measure_out(*[r[0] for r in results])
    return {"retrieved": results, "telemetry": span.finish()}


async def aanalyze(state: ComplianceState, ctx: Context) -> dict:
    # run the synchronous analyze body on a worker thread (it owns its own
    # span + repair-retry logic) so we stay DRY.
    return await asyncio.to_thread(analyze, state, ctx)


async def asummarize(state: ComplianceState, ctx: Context) -> dict:
    return await asyncio.to_thread(summarize, state, ctx)


async def ainsufficient(state: ComplianceState, ctx: Context) -> dict:
    return await asyncio.to_thread(insufficient, state, ctx)


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------
def route_retrieve(state: ComplianceState) -> str:
    if state.get("retrieved"):
        return "analyze"
    return "insufficient"


# Prompt used for the single repair retry when the analyzer's JSON can't be
# parsed. Lives here (not prompts.py) to keep this change additive.
SYSTEM_ANALYZE_REPAIR = (
    "You previously responded to a JSON-only request, but the response was not "
    "valid JSON. Re-emit ONLY a single valid JSON object with a top-level "
    '"violations" array (use the schema you were given). Do not include any '
    "prose, markdown fences, or commentary — return raw JSON only."
)


def _extract_json(raw: str) -> Optional[dict]:
    """Tolerantly extract the first top-level ``{...}`` object from text.

    Handles markdown fences, leading/trailing prose, and a `json` language tag.
    Returns the parsed dict, or ``None`` if no parseable object is found.
    """
    if not raw:
        return None
    text = raw.strip()
    # Strip a leading ```json / ``` fence if present.
    if text.startswith("```"):
        text = text.lstrip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    # Fast path: the whole thing is already JSON.
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: locate the first balanced {...} block and parse that.
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    data = json.loads(candidate)
                    return data if isinstance(data, dict) else None
                except (json.JSONDecodeError, ValueError):
                    return None
    return None


def _memo_put(
    memo: object, key: object, analysis_json: str, violations: List[dict]
) -> None:
    """Best-effort store of a successful analyze result into the memo cache."""
    if memo is None or key is None or not hasattr(memo, "put"):
        return
    try:
        memo.put(key, (analysis_json, violations))
    except Exception:  # caching must never break the node
        logger.debug("analyze: memo store failed", exc_info=True)


def _parse_violations(raw: str) -> Tuple[List[dict], Optional[str]]:
    """Parse the analyzer's JSON into a violations list.

    Returns ``(violations, error)``. On success ``error`` is ``None``; on
    failure ``violations`` is ``[]`` and ``error`` is a short ``parse_failed``
    description the caller can surface (rather than silently returning zeros).
    """
    data = _extract_json(raw)
    if data is None:
        snippet = (raw or "").strip().replace("\n", " ")[:120]
        return [], f"parse_failed: could not extract JSON object (got: {snippet!r})"
    violations = data.get("violations", [])
    if not isinstance(violations, list):
        return (
            [],
            f"parse_failed: 'violations' is not a list (got {type(violations).__name__})",
        )
    return violations, None


# --------------------------------------------------------------------------
# Graph builders
# --------------------------------------------------------------------------
def build_compliance_graph(ctx: Context):
    builder = StateGraph(ComplianceState)
    builder.add_node("extract_facts", partial(extract_facts, ctx=ctx))
    builder.add_node("retrieve", partial(retrieve, ctx=ctx))
    builder.add_node("analyze", partial(analyze, ctx=ctx))
    builder.add_node("summarize", partial(summarize, ctx=ctx))
    builder.add_node("insufficient", partial(insufficient, ctx=ctx))

    builder.set_entry_point("extract_facts")
    builder.add_edge("extract_facts", "retrieve")
    builder.add_conditional_edges(
        "retrieve",
        route_retrieve,
        {"analyze": "analyze", "insufficient": "insufficient"},
    )
    builder.add_edge("analyze", "summarize")
    builder.add_edge("insufficient", END)
    builder.add_edge("summarize", END)
    return builder.compile()


def build_async_compliance_graph(ctx: Context):
    """Async twin of :func:`build_compliance_graph`.

    Same nodes, edges, and the identical retrieve->insufficient short-circuit,
    but backed by ``async def`` nodes that dispatch blocking work with
    ``asyncio.to_thread``. The compiled graph supports ``ainvoke`` so
    ``RAGSystem.acheck`` can run a check without blocking the event loop, while
    ``extract_facts`` concurrently warms the independent plan embedding.
    """
    builder = StateGraph(ComplianceState)
    builder.add_node("extract_facts", partial(aextract_facts, ctx=ctx))
    builder.add_node("retrieve", partial(aretrieve, ctx=ctx))
    builder.add_node("analyze", partial(aanalyze, ctx=ctx))
    builder.add_node("summarize", partial(asummarize, ctx=ctx))
    builder.add_node("insufficient", partial(ainsufficient, ctx=ctx))

    builder.set_entry_point("extract_facts")
    builder.add_edge("extract_facts", "retrieve")
    builder.add_conditional_edges(
        "retrieve",
        route_retrieve,
        {"analyze": "analyze", "insufficient": "insufficient"},
    )
    builder.add_edge("analyze", "summarize")
    builder.add_edge("insufficient", END)
    builder.add_edge("summarize", END)
    return builder.compile()
