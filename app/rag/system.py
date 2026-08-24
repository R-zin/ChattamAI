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
    load_kbr_documents,
    load_plan_text,
)
from app.rag.vectorstore import RuleVectorStore

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
        self._entries: dict = {}
        self._order: list = []
        self._hits = 0
        self._misses = 0

    def _prune_locked(self, now: float) -> None:
        expired = [k for k in self._order if self._entries[k][1] <= now]
        for k in expired:
            self._entries.pop(k, None)
        while len(self._entries) >= self.maxsize and self._order:
            oldest = self._order.pop(0)
            self._entries.pop(oldest, None)

    def get(self, key):
        now = time.time()
        with self._lock:
            self._prune_locked(now)
            entry = self._entries.get(key)
            if entry is not None and entry[1] > now:
                self._hits += 1
                return entry[0]
            self._misses += 1
            return None

    def put(self, key, value) -> None:
        now = time.time()
        with self._lock:
            self._prune_locked(now)
            self._entries[key] = (value, now + self.ttl)
            if key not in self._order:
                self._order.append(key)

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
            self._order.clear()


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
        self._provider = None
        self._store: Optional[RuleVectorStore] = None
        self._llm = None
        self._graph = None
        self._agraph = None
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
        else:
            try:
                from app.rag.embeddings import EmbeddingCache, OpenAIEmbeddingProvider

                base = OpenAIEmbeddingProvider(
                    model=self.settings.embedding_model,
                    dim=self.settings.embedding_dim,
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url,
                )
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
            except RuntimeError as exc:
                self._embed_error = str(exc)

        # LLM is required for analysis.
        if llm is not None:
            self._llm = llm
            self.llm_ready = True
        else:
            try:
                from app.rag.llm import ClaudeClient

                self._llm = ClaudeClient()
                self.llm_ready = True
            except RuntimeError as exc:
                self._llm_error = str(exc)

        if self._provider is not None:
            self._store = RuleVectorStore(
                self._provider,
                index_dir or self.settings.index_dir,
                score_threshold=self.score_threshold,
            )
            self._store.load_or_create()

        if self._store is not None and self._llm is not None:
            ctx = Context(
                llm=self._llm,
                store=self._store,
                default_top_k=self.settings.top_k,
                analysis_cache=self._analysis_memo,
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

        docs = load_kbr_documents(data_dir)
        total_chunks = 0
        added = 0
        for text, source in docs:
            chunks = chunk_text(text)
            if not chunks:
                continue
            metas = []
            for i, chunk in enumerate(chunks):
                # Prefer a real rule/section header detected in the chunk; fall
                # back to a stable positional id so every excerpt is citable.
                rid = extract_rule_id(chunk) or f"{source}#chunk-{i + 1}"
                metas.append({"source": source, "chunk": i + 1, "rule_id": rid})
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
        return {
            "extracted_facts": [
                line.strip("- ").strip()
                for line in (result.get("facts") or "").splitlines()
                if line.strip()
            ],
            "summary": summary,
            "violations": result.get("violations", []),
            "retrieved_rules": [
                {
                    "source": meta.get("source", ""),
                    "rule_id": meta.get("rule_id"),
                    "excerpt": text,
                    "score": score,
                }
                for text, meta, score in result.get("retrieved", [])
            ],
        }

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
            "(extract=%.1f retrieve=%.1f analyze=%.1f summarize=%.1f)%s",
            facts_n,
            retrieved_n,
            violations_n,
            elapsed_ms,
            _ms("extract_facts"),
            _ms("retrieve"),
            _ms("analyze"),
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
        return await self.acheck(plan_text, top_k=top_k)

    # ------------------------------------------------------------------
    def check_plan_file(self, path, top_k: Optional[int] = None) -> dict:
        plan_text = load_plan_text(path)
        return self.check(plan_text, top_k=top_k)

    @property
    def index_size(self) -> int:
        return self._store.size if self._store else 0
