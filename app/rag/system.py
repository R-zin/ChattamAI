"""Top-level RAG system: owns the embedding provider, vector store, LLM, and
the LangGraph compliance workflow, and exposes the two operations the API needs:
ingest (build the rule index) and check (run a compliance analysis).

The synchronous ``check`` is preserved, and an async equivalent ``acheck`` runs
the same pipeline through an async graph (blocking LLM / embedding / FAISS calls
are pushed onto worker threads) so a check never blocks a running event loop.
``check`` is robust to being called both with and without an active event loop.

Two in-process caches cut latency/cost (no external store, TTL via env):
  * ``EmbeddingCache`` wraps the provider so repeated query embeddings are
    served from memory (see app/rag/embeddings.py).
  * ``AnalysisMemo`` memos the analyze step keyed by (facts_hash, index_version)
    so an identical re-check skips the analysis LLM call.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import logging
import threading
import time
from typing import Optional

from app.config import get_settings
from app.rag.graph import (
    Context,
    build_async_compliance_graph,
    build_compliance_graph,
)
from app.rag.ingestion import (
    chunk_text,
    extract_rule_id,
    load_kbr_pages,
    load_plan_text,
)
from app.rag.lexicon import content_tokens
from app.rag.retrieval import RetrievalConfig, RuleRetriever
from app.rag.vectorstore import RuleVectorStore
from app.rag.validation import validate_building_plan_text

logger = logging.getLogger(__name__)


class AnalysisMemo:
    """Small in-process TTL memo for the analyze step.

    Keyed by ``(facts_hash, index_version)``; values are
    ``(analysis_json, violations)``. Thread-safe, best-effort. Exposes the
    minimal ``get``/``put`` interface the ``analyze`` node consumes (see
    app/rag/graph.py), plus ``stats()`` for observability. Defaults come from
    ``Settings.analysis_cache_ttl`` / ``Settings.analysis_cache_maxsize``.
    """

    def __init__(
        self, ttl: Optional[float] = None, maxsize: Optional[int] = None
    ) -> None:
        settings = get_settings()
        if ttl is None:
            ttl = settings.analysis_cache_ttl
        if maxsize is None:
            maxsize = settings.analysis_cache_maxsize
        self.ttl = ttl
        self.maxsize = max(1, maxsize)
        self._lock = threading.Lock()
        self._entries: OrderedDict = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _prune_expired_locked(self, now: float) -> None:
        expired = [k for k, (_, exp) in self._entries.items() if exp <= now]
        for k in expired:
            del self._entries[k]

    def get(self, key):
        now = time.time()
        with self._lock:
            self._prune_expired_locked(now)
            entry = self._entries.get(key)
            if entry is not None and entry[1] > now:
                self._hits += 1
                return entry[0]
            self._misses += 1
            return None

    def put(self, key, value) -> None:
        now = time.time()
        with self._lock:
            self._prune_expired_locked(now)
            if key in self._entries:
                del self._entries[key]
            self._entries[key] = (value, now + self.ttl)
            while len(self._entries) > self.maxsize:
                self._entries.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "maxsize": self.maxsize,
                "ttl": self.ttl,
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def _default_score_threshold() -> float:
    """Minimum cosine-similarity for a retrieval hit (higher score = better).

    Sourced from ``Settings.min_score`` (``MIN_SCORE`` env var, default ``0.0``
    keeps everything).
    """
    return get_settings().min_score


class RAGSystem:
    def __init__(
        self,
        provider=None,
        llm=None,
        index_dir: Optional[str] = None,
        verifier_llm: Optional[object] = None,
    ) -> None:
        """Build the system.

        Optional *test seams* (additive, backward-compatible): pass ``provider``
        (an ``EmbeddingProvider``) and/or ``llm`` (an object with
        ``complete(system, user) -> str``) to inject fakes and skip the real
        OpenAI/Anthropic construction; pass ``index_dir`` to point the FAISS
        store at a tmp dir. When any of these is omitted the real client /
        configured index dir is used exactly as before, so default startup is
        unchanged.
        """
        self.settings = get_settings()
        self.embeddings_ready = False
        self.llm_ready = False
        self.llm_provider: str = self.settings.llm_provider
        self.llm_model: str = self.settings.llm_model
        self.embedding_provider: str = getattr(
            self.settings, "embedding_provider", "nim"
        )
        self.embedding_model: str = getattr(
            self.settings, "embedding_model", "nvidia/nemotron-3-embed-1b"
        )
        self._provider = None
        self._store: Optional[RuleVectorStore] = None
        self._llm = None
        self._graph = None
        self._agraph = None
        self._retriever: Optional[RuleRetriever] = None
        self.retrieval_strategy: str = self.settings.retrieval_strategy
        self.score_threshold = _default_score_threshold()

        # Analysis memo: skip the analysis LLM on an identical re-check.
        self._analysis_memo = AnalysisMemo(
            ttl=self.settings.analysis_cache_ttl,
            maxsize=self.settings.analysis_cache_maxsize,
        )

        # Embeddings are required for retrieval; surface a clear error if missing.
        if provider is not None:
            # Test seam: a caller-supplied provider (fake) replaces real construction.
            self._provider = provider
            self.embeddings_ready = True
            self.embedding_provider = getattr(provider, "provider", "custom")
            self.embedding_model = getattr(provider, "model", "custom")
        else:
            try:
                from app.rag.embeddings import EmbeddingCache, get_embedding_provider

                base = get_embedding_provider()
                # Wrap with the query-embedding cache (transparent: same embed() API).
                self._provider = (
                    EmbeddingCache(
                        base,
                        ttl=self.settings.embedding_cache_ttl,
                        maxsize=self.settings.embedding_cache_maxsize,
                    )
                    if self.settings.embedding_cache_enabled
                    else base
                )
                self.embeddings_ready = True
                self.embedding_provider = getattr(
                    base, "provider", self.settings.embedding_provider
                )
                self.embedding_model = getattr(
                    base, "model", self.settings.embedding_model
                )
            except RuntimeError as exc:
                self._embed_error = str(exc)

        # LLM is required for analysis.
        if llm is not None:
            self._llm = llm
            self.llm_ready = True
            self.llm_provider = getattr(llm, "provider", "custom")
            self.llm_model = getattr(llm, "model", "custom")
        else:
            try:
                from app.rag.llm import get_llm_client

                self._llm = get_llm_client()
                self.llm_ready = True
                self.llm_provider = getattr(
                    self._llm, "provider", self.settings.llm_provider
                )
                self.llm_model = getattr(self._llm, "model", self.settings.llm_model)
            except Exception as exc:
                self._llm_error = str(exc)

        # Secondary verifier LLM (for double-checking and verification)
        if verifier_llm is None:
            try:
                from app.rag.llm import get_verifier_client

                self.verifier_llm = get_verifier_client()
            except Exception as exc:
                logger.warning("Failed to initialize verifier client: %s", exc)
                self.verifier_llm = None
        else:
            self.verifier_llm = verifier_llm

        self.verifier_ready = self.verifier_llm is not None
        self.verifier_provider = (
            getattr(self.verifier_llm, "provider", self.settings.verifier_provider)
            if self.verifier_llm
            else self.settings.verifier_provider
        )
        self.verifier_model = (
            getattr(self.verifier_llm, "model", self.settings.verifier_model)
            if self.verifier_llm
            else self.settings.verifier_model
        )

        if self._provider is not None:
            self._store = RuleVectorStore(
                self._provider,
                index_dir or self.settings.index_dir,
                score_threshold=self.score_threshold,
            )
            self._store.load_or_create()
            self._retriever = RuleRetriever(
                self._store,
                RetrievalConfig(
                    strategy=self.settings.retrieval_strategy,
                    mmr_lambda=self.settings.retrieval_mmr_lambda,
                    candidates_per_query=self.settings.retrieval_candidates,
                ),
            )
            self.retrieval_strategy = self._retriever.config.strategy

        if self._store is not None and self._llm is not None:
            ctx = Context(
                llm=self._llm,
                store=self._store,
                default_top_k=self.settings.top_k,
                analysis_cache=self._analysis_memo,
                verifier_llm=self.verifier_llm,
                retriever=self._retriever,
            )
            self._graph = build_compliance_graph(ctx)
            self._agraph = build_async_compliance_graph(ctx)

    # ------------------------------------------------------------------
    def ingest(self, data_dir: Optional[str] = None, rebuild: bool = False) -> dict:
        """Index the Kerala Building Rules documents.

        Idempotent by default: chunks already in the index (matched by content
        hash) are skipped, so re-running ingest does not duplicate vectors.
        Pass ``rebuild=True`` to drop the existing index and rebuild from the
        source documents.
        """
        if not self.embeddings_ready or self._store is None:
            raise RuntimeError(
                getattr(self, "_embed_error", "Embeddings are not configured.")
            )
        if rebuild:
            self._store.reset()

        docs = load_kbr_pages(data_dir)
        total_chunks = 0
        added = 0
        for source, pages, paged in docs:
            if self.settings.structured_chunking:
                # Chunks follow the rulebook's own structure and carry rule id,
                # heading breadcrumb and page (app/rag/structure.py).
                from app.rag.structure import build_chunks

                pairs = build_chunks(source, pages, paged=paged)
                chunks = [text for text, _meta in pairs]
                metas = [meta for _text, meta in pairs]
            else:
                chunks = chunk_text("\n".join(pages))
                metas = []
                for i, chunk in enumerate(chunks):
                    # Prefer a real rule/section header detected in the chunk;
                    # fall back to a stable positional id so every excerpt is
                    # citable.
                    rid = extract_rule_id(chunk) or f"{source}#chunk-{i + 1}"
                    metas.append({"source": source, "chunk": i + 1, "rule_id": rid})
            if not chunks:
                continue
            added += self._store.add_texts(chunks, metas, dedup=not rebuild)
            total_chunks += len(chunks)
        return {
            "documents": len(docs),
            "chunks": added,
            "index_size": self._store.size,
            "skipped": total_chunks - added,
        }

    # ------------------------------------------------------------------
    def _require_ready(self) -> None:
        if self._graph is None or self._agraph is None:
            missing = []
            if not self.embeddings_ready:
                missing.append("embeddings")
            if not self.llm_ready:
                missing.append("llm")
            raise RuntimeError(
                f"Compliance check unavailable — missing: {', '.join(missing)}."
            )

    @staticmethod
    def _shape_result(result: dict) -> dict:
        """Project the graph state into the public ComplianceResponse dict.

        Keys intentionally match the existing response schema; telemetry and any
        analysis error are conveyed via the log line and ``result["error"]`` is
        folded into the summary so it never silently returns zero violations.
        """
        summary = result.get("summary", "")
        error = result.get("error")
        if error:
            summary = f"{summary}\n\n[warning] {error}".strip()
        shaped = {
            "extracted_facts": [
                line.strip("- ").strip()
                for line in (result.get("facts") or "").splitlines()
                if line.strip()
            ],
            "summary": summary,
            "violations": result.get("violations", []),
            "retrieved_rules": [
                _rule_reference(text, meta, score)
                for text, meta, score in result.get("retrieved", [])
            ],
        }
        if error:
            shaped["error"] = error
        if result.get("retrieval"):
            shaped["retrieval"] = result["retrieval"]
        if result.get("grounding"):
            shaped["grounding"] = result["grounding"]
        verification_data = result.get("verification")
        if verification_data and isinstance(verification_data, dict):
            try:
                from app.schemas import VerificationResult

                shaped["verification"] = VerificationResult(
                    **verification_data
                ).model_dump()
            except Exception:
                shaped["verification"] = verification_data
        return shaped

    def _log_check(self, result: dict, elapsed_ms: float) -> None:
        """Emit one telemetry line per check: counts + timing per node."""
        telemetry = result.get("telemetry") or {}

        def _ms(node: str) -> float:
            return float(telemetry.get(node, {}).get("ms", 0.0))

        facts_n = len(
            [ln for ln in (result.get("facts") or "").splitlines() if ln.strip()]
        )
        retrieved_n = len(result.get("retrieved") or [])
        violations_n = len(result.get("violations") or [])
        logger.info(
            "check: facts=%d retrieved=%d violations=%d elapsed_ms=%.1f "
            "(extract=%.1f retrieve=%.1f analyze=%.1f verify=%.1f summarize=%.1f)%s",
            facts_n,
            retrieved_n,
            violations_n,
            elapsed_ms,
            _ms("extract_facts"),
            _ms("retrieve"),
            _ms("analyze"),
            _ms("verify_analysis"),
            _ms("summarize"),
            f" error={result.get('error')}" if result.get("error") else "",
        )

    # ------------------------------------------------------------------
    async def acheck(self, plan_text: str, top_k: Optional[int] = None) -> dict:
        """Async compliance check via the async graph (``ainvoke``).

        Blocking LLM / embedding / FAISS work runs on worker threads, so this
        never blocks a running event loop. Returns the same dict shape as
        :meth:`check`.
        """
        self._require_ready()
        validate_building_plan_text(plan_text)
        started = time.perf_counter()
        result = await self._agraph.ainvoke(
            {"plan_text": plan_text, "top_k": top_k or self.settings.top_k}
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        self._log_check(result, elapsed_ms)
        return self._shape_result(result)

    # ------------------------------------------------------------------
    def check(self, plan_text: str, top_k: Optional[int] = None) -> dict:
        """Synchronous compliance check.

        Runs the async pipeline (single source of truth for behaviour) while
        staying safe for callers both with and without an active event loop:
        FastAPI sync routes run in a threadpool (no running loop here), but a
        caller inside a running loop would break ``asyncio.run`` — so we detect
        that case and drive the coroutine on a private loop in a helper thread.
        """
        self._require_ready()
        validate_building_plan_text(plan_text)
        try:
            asyncio.get_running_loop()
            in_loop = True
        except RuntimeError:
            in_loop = False

        if not in_loop:
            return asyncio.run(self.acheck(plan_text, top_k=top_k))

        # Called from within a running event loop: run acheck on a *separate*
        # loop in a helper thread and block this (already-sync) caller until it
        # completes. Avoids "asyncio.run() cannot be called from a running loop".
        outcome: dict = {}
        error: list = []

        def _runner() -> None:
            try:
                outcome["result"] = asyncio.run(self.acheck(plan_text, top_k=top_k))
            except BaseException as exc:  # surface any failure to the caller
                error.append(exc)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if error:
            raise error[0]
        return outcome["result"]

    # ------------------------------------------------------------------
    async def acheck_plan_file(self, path, top_k: Optional[int] = None) -> dict:
        plan_text = await asyncio.to_thread(load_plan_text, path)
        validate_building_plan_text(plan_text)
        return await self.acheck(plan_text, top_k=top_k)

    # ------------------------------------------------------------------
    def check_plan_file(self, path, top_k: Optional[int] = None) -> dict:
        plan_text = load_plan_text(path)
        validate_building_plan_text(plan_text)
        return self.check(plan_text, top_k=top_k)

    @property
    def index_size(self) -> int:
        return self._store.size if self._store else 0

    # ------------------------------------------------------------------
    # Rulebook tools: question answering, search, index statistics
    # ------------------------------------------------------------------
    def ask(self, question: str, top_k: Optional[int] = None) -> dict:
        """Answer a question from the rule index with verified citations.

        See app/rag/qa.py. Raises ``RuntimeError`` when embeddings or the LLM
        are not configured and ``ValueError`` for an unusable question.
        """
        self._require_ready()
        from app.rag.qa import answer_question

        return answer_question(
            self._llm,
            self._retriever,
            question,
            top_k=top_k or self.settings.top_k,
            index_size=self.index_size,
        )

    def search(self, query: str, limit: int = 10, mode: str = "hybrid") -> list:
        """Search the rule index and explain each hit.

        ``mode``: ``hybrid`` (dense + BM25, the default), ``dense`` (embedding
        only), ``lexical`` (keywords only) or ``advanced`` (the topic-aware
        retriever). Each hit carries its dense and lexical channel scores and
        the query terms it matched, so a surprising ranking can be understood.
        """
        mode = (mode or "hybrid").lower()
        if mode not in SEARCH_MODES:
            raise ValueError(
                f"Unknown search mode '{mode}'. Use one of: {', '.join(SEARCH_MODES)}."
            )
        store = self._store
        if store is None or store.size == 0:
            return []
        limit = max(1, min(50, int(limit)))
        terms = set(content_tokens(query))

        def row(idx: int, score: float, scores, extra: Optional[dict] = None) -> dict:
            text, meta = store.chunk(idx)
            out = _rule_reference(text, {**meta, **(extra or {})}, round(score, 4))
            out["chunk"] = meta.get("chunk")
            out["dense_score"] = round(scores.dense[idx], 4)
            out["lexical_score"] = round(scores.lexical[idx], 4)
            out["matched_terms"] = sorted(terms & store.token_set(idx))
            return out

        scores = store.score_queries([query])[0]
        if mode == "advanced" and self._retriever is not None:
            hits, _trace = self._retriever.retrieve(
                query, k=limit, facts_mode=False, strategy="advanced"
            )
            by_hash = {m.get("sha256"): i for i, m in enumerate(store._metas)}
            rows = []
            for _text, meta, score in hits:
                idx = by_hash.get(meta.get("sha256"))
                if idx is not None:
                    extra = {
                        "topics": meta.get("topics"),
                        "retrieved_by": meta.get("retrieved_by"),
                    }
                    rows.append(row(idx, score, scores, extra))
            return rows

        channel = {
            "hybrid": scores.fused,
            "dense": scores.dense,
            "lexical": scores.lexical,
        }[mode]
        order = sorted(range(store.size), key=lambda i: (-channel[i], i))[:limit]
        threshold = store.score_threshold
        rows = []
        for idx in order:
            score = float(channel[idx])
            if mode == "lexical" and score <= 0.0:
                continue  # no keyword in common: not a match at all
            if mode != "lexical" and threshold is not None and score < threshold:
                continue
            rows.append(row(idx, score, scores))
        return rows

    def index_stats(self) -> dict:
        """What is actually in the index, per document, and how it is searched."""
        store = self._store
        documents = store.document_stats() if store is not None else []
        return {
            "index_size": self.index_size,
            "documents": documents,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dim": getattr(self._provider, "dim", None),
            "retrieval_strategy": self.retrieval_strategy,
            "hybrid": bool(store.hybrid_available) if store is not None else False,
            "hybrid_weight": store.hybrid_weight if store is not None else None,
            "structured_chunking": self.settings.structured_chunking,
        }


#: Modes accepted by :meth:`RAGSystem.search`.
SEARCH_MODES = ("hybrid", "dense", "lexical", "advanced")


def _rule_reference(text: str, meta: dict, score: float) -> dict:
    """Public ``RuleReference`` dict for one retrieved chunk."""
    out = {
        "source": meta.get("source", ""),
        "rule_id": meta.get("rule_id"),
        "excerpt": text,
        "score": score,
    }
    for key in ("section", "page", "retrieved_by"):
        if meta.get(key) is not None:
            out[key] = meta[key]
    if meta.get("topics"):
        out["topics"] = list(meta["topics"])
    if meta.get("corrective"):
        out["corrective"] = True
    return out
