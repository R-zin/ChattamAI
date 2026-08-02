"""Offline performance harness for the ChattamAI compliance check.

Runs N compliance checks against a *fakes-backed* ``RAGSystem`` — no OpenAI or
Anthropic keys, no network — and reports latency (p50/p95) plus the
latency/cost win from the in-process caches (query-embedding cache +
analyze-step memo).

Two arms are measured:

  * **cached**   — one ``RAGSystem`` whose provider is wrapped in
    ``EmbeddingCache``; the same plan is checked ``--checks`` times. Repeat
    calls hit the embedding cache and the analysis memo, so they are far faster
    and make far fewer embedding calls.
  * **uncached** — a baseline with no embedding cache wrapper and the analysis
    memo cleared, with a *distinct* plan per call so nothing is reused.

The delta between the two is the cache win. Everything is driven through the
async compliance graph (``rag._agraph``) — the same pipeline ``RAGSystem.check``
uses — so per-node timings are read from the returned ``telemetry`` and total
latency is wall-clocked around the call.

Usage::

    python scripts/bench_check.py --checks 5
    python scripts/bench_check.py --checks 20 --repeat --json
    python scripts/bench_check.py --no-analysis-cache --top-k 3

Standard library + the project's existing deps only (numpy/faiss/langgraph).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

# Make the repo root importable when run as ``python scripts/bench_check.py``.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.embeddings import EmbeddingCache, EmbeddingProvider  # noqa: E402
from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY  # noqa: E402

# Node names exactly as the graph records them in ``telemetry`` (see
# app/rag/graph.py:_node_span). The embedding warm-up rides on extract_facts.
NODE_ORDER = ("extract_facts", "retrieve", "analyze", "summarize")


# ---------------------------------------------------------------------------
# Fakes (inline — deliberately NOT imported from tests/, per the task rules)
# ---------------------------------------------------------------------------
class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashed-bag-of-words embeddings (no network, no randomness).

    Each token is hashed (SHA-256) to a bucket in a ``dim``-dimensional space and
    accumulated, then the vector is L2-normalised to unit length. Texts that share
    tokens therefore get a *positive* cosine similarity and unrelated texts land
    near zero — so the corpus's "setback" rule is genuinely the nearest neighbour
    of a plan/facts string that also mentions "setback", exactly as a real model
    would rank it. Identical texts embed identically (cosine ~1.0). The real store
    already L2-normalises before inner-product search, so unit vectors keep scores
    in [-1, 1] with higher = better.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        # Observability for cost accounting: count provider invocations and the
        # number of texts embedded (an "embedding-API call" is one embed()).
        self.embed_calls = 0
        self.texts_embedded = 0

    def _vector_for(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype="float64")
        for tok in text.lower().split():
            # Strip punctuation so "setback" and "setback." collide.
            token = tok.strip(".,;:!?()\"'")
            if not token:
                continue
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dim
            # Deterministic sign from the digest keeps distinct tokens spread and
            # avoids every shared term adding in the same direction.
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[bucket] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.astype("float32")

    def embed(self, texts: List[str]) -> np.ndarray:
        self.embed_calls += 1
        self.texts_embedded += len(texts)
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        return np.stack([self._vector_for(t) for t in texts]).astype("float32")


# Canned, well-formed analyze payload (valid JSON with a top-level violations
# array), so the analyze node parses cleanly with no repair retry.
_ANALYZE_JSON = json.dumps(
    {
        "violations": [
            {
                "rule_reference": "Rule 5",
                "severity": "high",
                "description": "Front setback below the permitted minimum.",
                "plan_value": "1m",
                "required_value": "1.8m",
            }
        ]
    }
)

_FACTS_BODY = (
    "- plot area: 300 sq.m\n"
    "- number of floors: 3\n"
    "- building height: 12m\n"
    "- front setback: 1m"
)

_SUMMARY_TEXT = (
    "One high-severity front-setback violation was found against Rule 5; "
    "recommend revising the front setback to at least 1.8m before approval."
)


class FakeLLM:
    """Scripted LLM returning canned payloads keyed on the SYSTEM prompt.

    Adds a tiny artificial ``latency_s`` per call so the harness has a measurable
    (and cache-dodged) cost to report. ``complete_calls`` counts LLM invocations.

    The extract answer ends with a ``plan-id`` line derived from the submitted
    plan text, so two *different* plans yield different facts strings. That makes
    the analysis memo key (``facts_hash``) differ per unique plan — which is what
    lets the harness build a genuinely cached run (identical plan => memo hit)
    versus an uncached baseline (unique plan => memo miss).
    """

    def __init__(self, latency_s: float = 0.005) -> None:
        self.latency_s = latency_s
        self.complete_calls = 0

    def complete(self, system: str, user: str) -> str:
        self.complete_calls += 1
        if self.latency_s:
            time.sleep(self.latency_s)
        if system == SYSTEM_EXTRACT:
            plan_id = hashlib.sha256(user.encode("utf-8")).hexdigest()[:12]
            return f"{_FACTS_BODY}\n- plan-id: {plan_id}"
        if system == SYSTEM_ANALYZE:
            return _ANALYZE_JSON
        if system == SYSTEM_SUMMARY:
            return _SUMMARY_TEXT
        return "UNSCRIPTED SYSTEM PROMPT"


# A small synthetic KBR corpus so ``retrieve`` always has relevant rules to find.
# Each rule is written to its OWN file during ingest so it becomes its own chunk
# (and gets its own rule_id) — giving retrieval several candidates to rank.
_KBR_RULES = [
    "Rule 5: The minimum front setback for a residential building up to 10m in "
    "height is 1.8m; a smaller front setback is not permitted.",
    "Rule 7: The maximum floor space index (FSI) for residential use is 1.5.",
    "Rule 11: Off-street parking shall be provided at one car per 100 sq.m of "
    "built-up area for a residential building.",
]

# A sample plan that conflicts with Rule 5 (front setback 1m < 1.8m). It shares
# vocabulary with Rule 5 so the hashed embeddings rank that rule as the top hit.
_PLAN_TEXT = (
    "Proposed residential building. Plot area 300 sq.m. Number of floors: 3. "
    "Building height 12m. Front setback 1m. Rear setback 1.5m. Side setback 1m. "
    "Parking for 2 cars provided."
)


# ---------------------------------------------------------------------------
# Harness plumbing
# ---------------------------------------------------------------------------
def _build_system(index_dir: Path, use_embedding_cache: bool, llm: FakeLLM):
    """Construct a fakes-backed RAGSystem and ingest the synthetic KBR corpus.

    Returns ``(rag, provider)`` where ``provider`` is the *innermost* fake so the
    caller can read embedding-call counters. When ``use_embedding_cache`` is on,
    the fake is wrapped in ``EmbeddingCache`` (mirroring production wiring).
    """
    from app.rag.system import RAGSystem

    provider = FakeEmbeddingProvider()
    wired = EmbeddingCache(provider) if use_embedding_cache else provider
    rag = RAGSystem(provider=wired, llm=llm, index_dir=str(index_dir))
    return rag, provider


def _ingest_corpus(rag, data_dir: Path) -> dict:
    """Write one file per rule (one chunk each) and ingest them into the store."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for i, rule in enumerate(_KBR_RULES, start=1):
        (data_dir / f"kbr_rule_{i}.txt").write_text(rule, encoding="utf-8")
    return rag.ingest(str(data_dir))


def _plan_for(i: int, identical: bool) -> str:
    """Return the plan text for check ``i``.

    ``identical=True`` returns the same text every time (exercises the analysis
    memo + embedding cache hit path). Otherwise a per-call suffix changes the
    content hash so nothing is reused (the uncached baseline).
    """
    if identical:
        return _PLAN_TEXT
    return f"{_PLAN_TEXT} Variant marker {i}."


async def _run_one(rag, plan_text: str, top_k: int) -> Dict:
    """Drive one check via the async graph and capture telemetry + raw state.

    Returns ``(elapsed_ms, state)``. We invoke ``rag._agraph`` directly (the same
    pipeline ``RAGSystem.check`` runs) so the per-node ``telemetry`` recorded in
    the graph state is available — the public ``check()`` projects it away.
    """
    started = time.perf_counter()
    state = await rag._agraph.ainvoke({"plan_text": plan_text, "top_k": top_k})
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms, state


def _node_ms(state: Dict) -> Dict[str, float]:
    telemetry = state.get("telemetry") or {}
    return {
        node: float((telemetry.get(node) or {}).get("ms", 0.0)) for node in NODE_ORDER
    }


def _run_arm(
    checks: int,
    top_k: int,
    identical: bool,
    use_embedding_cache: bool,
    clear_memo: bool,
) -> Dict:
    """Run one arm (cached or uncached) and collect per-call timing + counters.

    Returns a dict with per-call total ms, per-node ms, embedding/LLM call
    counts, and the facts/retrieved/violations tallies from the last call.
    """
    from app.rag.system import RAGSystem  # noqa: F401  (kept explicit for clarity)

    tmp = tempfile.TemporaryDirectory(prefix="bench_check_")
    base = Path(tmp.name)
    llm = FakeLLM()
    rag, provider = _build_system(base / "index", use_embedding_cache, llm)
    _ingest_corpus(rag, base / "data")

    if clear_memo and getattr(rag, "_analysis_memo", None) is not None:
        rag._analysis_memo.clear()

    totals: List[float] = []
    nodes: List[Dict[str, float]] = []
    last_state: Dict = {}
    for i in range(checks):
        plan_text = _plan_for(i, identical)
        # Sync-safe: bench_check runs as a CLI, so no event loop is active here.
        elapsed_ms, state = asyncio.run(_run_one(rag, plan_text, top_k))
        totals.append(elapsed_ms)
        nodes.append(_node_ms(state))
        last_state = state

    embed_stats = {}
    wired = rag._provider
    if isinstance(wired, EmbeddingCache):
        embed_stats = wired.stats()

    memo_stats = {}
    memo = getattr(rag, "_analysis_memo", None)
    if memo is not None and hasattr(memo, "stats"):
        memo_stats = memo.stats()

    facts = (last_state.get("facts") or "").splitlines()
    result = {
        "checks": checks,
        "totals_ms": totals,
        "nodes_ms": nodes,
        "embedding_calls": provider.embed_calls,
        "texts_embedded": provider.texts_embedded,
        "llm_calls": llm.complete_calls,
        "embedding_cache": embed_stats,
        "analysis_memo": memo_stats,
        "facts_count": len([ln for ln in facts if ln.strip()]),
        "retrieved_count": len(last_state.get("retrieved") or []),
        "violations_count": len(last_state.get("violations") or []),
        "index_size": rag.index_size,
    }
    tmp.cleanup()
    return result


# ---------------------------------------------------------------------------
# Statistics + reporting
# ---------------------------------------------------------------------------
def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile; ``sorted_vals`` must be ascending, non-empty."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_vals) - 1)
    frac = rank - low
    return float(sorted_vals[low] + (sorted_vals[high] - sorted_vals[low]) * frac)


def _summarize_arm(arm: Dict) -> Dict:
    totals = sorted(arm["totals_ms"])
    node_means = {
        node: statistics.fmean(n[node] for n in arm["nodes_ms"]) for node in NODE_ORDER
    }
    return {
        "checks": arm["checks"],
        "p50_ms": round(_percentile(totals, 50), 3),
        "p95_ms": round(_percentile(totals, 95), 3),
        "mean_ms": round(statistics.fmean(totals), 3),
        "min_ms": round(totals[0], 3),
        "max_ms": round(totals[-1], 3),
        "first_ms": round(arm["totals_ms"][0], 3),
        "node_mean_ms": {k: round(v, 3) for k, v in node_means.items()},
        "embedding_calls": arm["embedding_calls"],
        "texts_embedded": arm["texts_embedded"],
        "llm_calls": arm["llm_calls"],
        "embedding_cache": arm["embedding_cache"],
        "analysis_memo": arm["analysis_memo"],
        "facts_count": arm["facts_count"],
        "retrieved_count": arm["retrieved_count"],
        "violations_count": arm["violations_count"],
        "index_size": arm["index_size"],
    }


def _fmt_pct_gain(baseline: float, optimized: float) -> str:
    if baseline <= 0:
        return "n/a"
    gain = (baseline - optimized) / baseline * 100.0
    return f"{gain:.0f}%"


def build_report(args: argparse.Namespace) -> Dict:
    """Run both arms and assemble the machine-readable report."""
    # Cached arm: identical repeats hit the embedding cache + analysis memo.
    use_embedding_cache = not args.no_embedding_cache
    identical = args.repeat
    cached_arm = _run_arm(
        checks=args.checks,
        top_k=args.top_k,
        identical=identical,
        use_embedding_cache=use_embedding_cache,
        clear_memo=args.no_analysis_cache,
    )
    # Uncached baseline: no embedding cache, memo cleared, distinct plan per call.
    baseline_arm = _run_arm(
        checks=args.checks,
        top_k=args.top_k,
        identical=False,
        use_embedding_cache=False,
        clear_memo=True,
    )

    cached = _summarize_arm(cached_arm)
    baseline = _summarize_arm(baseline_arm)

    comparison = {
        "p50_speedup_ms": round(baseline["p50_ms"] - cached["p50_ms"], 3),
        "p50_faster_pct": _fmt_pct_gain(baseline["p50_ms"], cached["p50_ms"]),
        "repeat_vs_first_ms": {
            "first": cached["first_ms"],
            # Representative steady-state repeat latency (p50 of the cached arm).
            "repeat": cached["p50_ms"],
            "faster_pct": _fmt_pct_gain(cached["first_ms"], cached["p50_ms"]),
        },
        "embedding_calls_delta": baseline["embedding_calls"]
        - cached["embedding_calls"],
        "llm_calls_delta": baseline["llm_calls"] - cached["llm_calls"],
    }

    return {
        "config": {
            "checks": args.checks,
            "repeat": args.repeat,
            "top_k": args.top_k,
            "embedding_cache": use_embedding_cache,
            "analysis_cache": not args.no_analysis_cache,
            "offline": True,
        },
        "cached": cached,
        "uncached_baseline": baseline,
        "comparison": comparison,
    }


def print_human(report: Dict) -> None:
    cfg = report["config"]
    cached = report["cached"]
    baseline = report["uncached_baseline"]
    cmp = report["comparison"]

    arms = (
        f"embedding_cache={'on' if cfg['embedding_cache'] else 'off'} "
        f"analysis_cache={'on' if cfg['analysis_cache'] else 'off'} "
        f"repeat={'identical' if cfg['repeat'] else 'unique'}"
    )
    print(f"bench_check: {cfg['checks']} checks (offline, fakes) — {arms}")
    print(
        f"  cached   : p50={cached['p50_ms']:.1f}ms p95={cached['p95_ms']:.1f}ms "
        f"mean={cached['mean_ms']:.1f}ms "
        f"(emb_calls={cached['embedding_calls']} llm_calls={cached['llm_calls']})"
    )
    print(
        f"  uncached : p50={baseline['p50_ms']:.1f}ms p95={baseline['p95_ms']:.1f}ms "
        f"mean={baseline['mean_ms']:.1f}ms "
        f"(emb_calls={baseline['embedding_calls']} "
        f"llm_calls={baseline['llm_calls']})"
    )
    nodes = " ".join(f"{k}={v:.1f}" for k, v in cached["node_mean_ms"].items())
    print(f"  node mean ms (cached): {nodes}")
    print(
        f"  retrieval: facts={cached['facts_count']} "
        f"retrieved={cached['retrieved_count']} "
        f"violations={cached['violations_count']} "
        f"index_size={cached['index_size']}"
    )

    active = []
    if cfg["embedding_cache"]:
        active.append("embedding-cache")
    if cfg["analysis_cache"]:
        active.append("analysis-memo")
    via = "+".join(active) if active else "no caches"

    rvf = cmp["repeat_vs_first_ms"]
    print(
        f"  cache win: repeat {rvf['repeat']:.1f}ms vs first {rvf['first']:.1f}ms "
        f"({rvf['faster_pct']} faster via {via}); "
        f"vs uncached p50 {cmp['p50_faster_pct']} faster "
        f"(emb_calls saved {cmp['embedding_calls_delta']}, "
        f"llm_calls saved {cmp['llm_calls_delta']})"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/bench_check.py",
        description=(
            "Offline perf harness for the ChattamAI compliance check. Runs N "
            "checks against a fakes-backed RAGSystem (no API keys / network) and "
            "reports p50/p95 latency plus the embedding-cache + analysis-memo "
            "win versus an uncached baseline."
        ),
    )
    parser.add_argument(
        "--checks",
        type=int,
        default=20,
        metavar="N",
        help="Number of compliance checks per arm (default: 20).",
    )
    parser.add_argument(
        "--repeat",
        "--identical",
        dest="repeat",
        action="store_true",
        help=(
            "Re-use the identical plan text every call in the cached arm, "
            "exercising the analysis-memo + embedding-cache hit path (default "
            "for a meaningful cache-win readout; see --unique to disable)."
        ),
    )
    parser.add_argument(
        "--unique",
        dest="repeat",
        action="store_false",
        help="Use a distinct plan text per call in the cached arm (no memo hits).",
    )
    parser.set_defaults(repeat=True)
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        metavar="K",
        help="Rules retrieved per check (default: Settings.top_k).",
    )
    parser.add_argument(
        "--no-embedding-cache",
        action="store_true",
        help="Disable the query-embedding cache in the cached arm.",
    )
    parser.add_argument(
        "--no-analysis-cache",
        action="store_true",
        help="Disable/clear the analyze-step memo in the cached arm.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full report as a machine-readable JSON blob.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.checks < 1:
        print("error: --checks must be >= 1", file=sys.stderr)
        return 2
    from app.config import get_settings

    top_k = args.top_k if args.top_k is not None else int(get_settings().top_k)
    args.top_k = top_k

    report = build_report(args)
    print_human(report)
    if args.json:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via CLI
    raise SystemExit(main())
