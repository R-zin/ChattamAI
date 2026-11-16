"""Offline retrieval evaluation: does the retriever find the governing rule?

Builds an index from the KBR corpus, runs the golden cases in
``tests/fixtures/retrieval_golden.json`` through each retrieval strategy, and
reports, per strategy:

  * **recall@k** - share of expected subjects for which a governing rule was
    retrieved (the number that matters for a compliance check: a rule that is
    never retrieved can never be checked)
  * **MRR**      - mean reciprocal rank of the first governing rule
  * **full**     - share of cases where every expected subject was covered

Two index variants are compared as well: ``flat`` (sentence chunks, the old
ingest) and ``structured`` (rule-aware chunks carrying heading context). Flat
chunks carry no rule label of their own, so for scoring each one is assigned
the rule its text actually sits under (looked up in the structured sections);
the flat index is therefore judged on what it retrieves, not on its labels.

By default it runs with a deterministic hashed bag-of-words embedder - no keys,
no network, reproducible in CI. That embedder has no semantics, so the dense
channel behaves like a second lexical channel; the numbers measure chunking,
query decomposition and fusion, NOT the quality of a real embedding model.
Pass ``--provider configured`` to evaluate with the provider from ``.env``
(this embeds the whole corpus: it costs API calls).

Usage::

    python scripts/eval_retrieval.py
    python scripts/eval_retrieval.py --top-k 8 --json
    python scripts/eval_retrieval.py --provider configured --cases q-far q-parking
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.embeddings import EmbeddingProvider  # noqa: E402

GOLDEN_PATH = ROOT / "tests" / "fixtures" / "retrieval_golden.json"
DEFAULT_CORPUS = ROOT / "data" / "kbr"
STRATEGIES = ("simple", "advanced")
VARIANTS = ("flat", "structured")


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashed bag-of-words vectors (no model, no network)."""

    _TOKEN_RE = re.compile(r"[a-z0-9.]+")

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.model = f"hashing-bow-{dim}"

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype="float64")
        for token in set(self._TOKEN_RE.findall(text.lower())):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vec[int.from_bytes(digest[:8], "big") % self.dim] += 1.0
        norm = np.linalg.norm(vec)
        return (vec / norm if norm > 0 else vec).astype("float32")

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        return np.stack([self._vector(t) for t in texts]).astype("float32")


def load_golden(path: Path = GOLDEN_PATH) -> List[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def _rule_base(rule_id: Optional[str]) -> str:
    """``"Rule 26, Table 4"`` / ``"Rule 26(4)"`` -> ``"rule 26"``."""
    text = str(rule_id or "").split(",")[0].split("(")[0]
    return " ".join(text.lower().split())


def _locate_rules(flat_chunks: List[str], structured) -> List[Optional[str]]:
    """Rule each flat chunk sits under, found by locating its middle passage
    inside the structured chunks (scoring aid only; never shown to the model)."""
    out: List[Optional[str]] = []
    cursor = 0
    for chunk in flat_chunks:
        mid = len(chunk) // 2
        probe = chunk[max(0, mid - 30) : mid + 30]
        found: Optional[str] = None
        order = list(range(cursor, len(structured))) + list(range(0, cursor))
        for j in order:
            if probe and probe in structured[j][0]:
                found = structured[j][1].get("rule_id")
                cursor = j
                break
        out.append(found)
    return out


def load_corpus(corpus_dir: Path):
    """``(source, pages, paged)`` for every readable document in ``corpus_dir``."""
    from app.config import get_settings
    from app.rag.ingestion import load_kbr_pages

    # ``load_kbr_pages`` only reads inside the configured KBR dir; point it at
    # the corpus for the duration of the read so any folder can be evaluated.
    settings = get_settings()
    original = settings.kbr_data_dir
    settings.kbr_data_dir = Path(corpus_dir)
    try:
        return load_kbr_pages(corpus_dir)
    finally:
        settings.kbr_data_dir = original


def build_store(provider, corpus, index_dir: Path, structured: bool):
    """Index a corpus into a fresh store, structured or flat.

    ``corpus`` is a directory, or documents already read by :func:`load_corpus`.
    """
    from app.rag.ingestion import chunk_text, extract_rule_id
    from app.rag.structure import build_chunks
    from app.rag.vectorstore import RuleVectorStore

    store = RuleVectorStore(provider, index_dir)
    store.load_or_create()
    docs = load_corpus(corpus) if isinstance(corpus, (str, Path)) else corpus
    for source, pages, paged in docs:
        if structured:
            pairs = build_chunks(source, pages, paged=paged)
            texts = [t for t, _m in pairs]
            metas = [m for _t, m in pairs]
        else:
            texts = chunk_text("\n".join(pages))
            located = _locate_rules(texts, build_chunks(source, pages, paged=paged))
            metas = [
                {
                    "source": source,
                    "chunk": i + 1,
                    "rule_id": extract_rule_id(c) or f"{source}#chunk-{i + 1}",
                    "eval_rule_id": located[i],
                }
                for i, c in enumerate(texts)
            ]
        if texts:
            store.add_texts(texts, metas)
    return store


def evaluate(store, cases: Iterable[dict], top_k: int, strategy: str) -> dict:
    """Run ``cases`` through ``strategy``; returns aggregate + per-case rows."""
    from app.rag.retrieval import RetrievalConfig, RuleRetriever

    retriever = RuleRetriever(store, RetrievalConfig(strategy=strategy))
    rows = []
    met_total = expected_total = 0
    reciprocal_ranks: List[float] = []
    full = 0
    for case in cases:
        hits, _trace = retriever.retrieve(
            case["query"], k=top_k, facts_mode=case.get("kind") != "question"
        )
        bases = [
            _rule_base(meta.get("eval_rule_id") or meta.get("rule_id"))
            for _t, meta, _s in hits
        ]
        met = []
        first_rank: Optional[int] = None
        for expectation in case["expect"]:
            wanted = {_rule_base(r) for r in expectation["rules"]}
            ranks = [i for i, base in enumerate(bases, start=1) if base in wanted]
            met.append(bool(ranks))
            if ranks and (first_rank is None or ranks[0] < first_rank):
                first_rank = ranks[0]
        met_total += sum(met)
        expected_total += len(met)
        reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)
        full += int(all(met))
        rows.append(
            {
                "id": case["id"],
                "met": sum(met),
                "expected": len(met),
                "missed": [
                    e["subject"] for e, ok in zip(case["expect"], met) if not ok
                ],
                "retrieved": [
                    meta.get("eval_rule_id") or meta.get("rule_id")
                    for _t, meta, _s in hits
                ],
            }
        )
    count = len(rows) or 1
    return {
        "strategy": strategy,
        "top_k": top_k,
        "cases": len(rows),
        "recall": round(met_total / (expected_total or 1), 3),
        "mrr": round(sum(reciprocal_ranks) / count, 3),
        "full_coverage": round(full / count, 3),
        "rows": rows,
    }


def run(
    top_k: int = 6,
    corpus_dir: Path = DEFAULT_CORPUS,
    provider=None,
    case_ids: Optional[Sequence[str]] = None,
    variants: Sequence[str] = VARIANTS,
    strategies: Sequence[str] = STRATEGIES,
) -> List[dict]:
    """Evaluate every (index variant, strategy) pair; returns one report each."""
    cases = load_golden()
    if case_ids:
        cases = [c for c in cases if c["id"] in set(case_ids)]
    provider = provider or HashingEmbeddingProvider()
    docs = load_corpus(corpus_dir)  # read (and parse PDFs) once for all variants
    reports = []
    for variant in variants:
        with tempfile.TemporaryDirectory() as tmp:
            store = build_store(provider, docs, Path(tmp), variant == "structured")
            for strategy in strategies:
                report = evaluate(store, cases, top_k, strategy)
                report["index"] = variant
                report["chunks"] = store.size
                reports.append(report)
    return reports


def _print(reports: List[dict], verbose: bool) -> None:
    print(
        f"{'index':<11} {'strategy':<9} {'chunks':>6} {'recall@k':>9} {'MRR':>6} {'full':>6}"
    )
    for r in reports:
        print(
            f"{r['index']:<11} {r['strategy']:<9} {r['chunks']:>6} "
            f"{r['recall']:>9.3f} {r['mrr']:>6.3f} {r['full_coverage']:>6.3f}"
        )
    if verbose:
        for r in reports:
            print(f"\n[{r['index']} / {r['strategy']}]")
            for row in r["rows"]:
                missed = (
                    f"  missed: {', '.join(row['missed'])}" if row["missed"] else ""
                )
                print(f"  {row['id']:<26} {row['met']}/{row['expected']}{missed}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument(
        "--provider",
        choices=("hashing", "configured"),
        default="hashing",
        help="hashing = offline deterministic; configured = provider from .env",
    )
    parser.add_argument("--cases", nargs="*", help="only these case ids")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    provider = None
    if args.provider == "configured":
        from app.rag.embeddings import get_embedding_provider

        provider = get_embedding_provider()
    reports = run(args.top_k, args.corpus, provider, args.cases)
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        _print(reports, args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
