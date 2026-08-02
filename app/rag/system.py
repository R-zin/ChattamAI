"""Top-level RAG system: owns the embedding provider, vector store, LLM, and
the LangGraph compliance workflow, and exposes the two operations the API needs:
ingest (build the rule index) and check (run a compliance analysis).
"""

from __future__ import annotations

import os
from typing import Optional

from app.config import get_settings
from app.rag.graph import Context, build_compliance_graph
from app.rag.ingestion import (
    chunk_text,
    extract_rule_id,
    load_kbr_documents,
    load_plan_text,
)
from app.rag.vectorstore import RuleVectorStore


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
        self.score_threshold = _default_score_threshold()

        # Embeddings are required for retrieval; surface a clear error if missing.
        if provider is not None:
            self._provider = provider
            self.embeddings_ready = True
        else:
            try:
                from app.rag.embeddings import OpenAIEmbeddingProvider

                self._provider = OpenAIEmbeddingProvider(
                    model=self.settings.embedding_model,
                    dim=self.settings.embedding_dim,
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url,
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
                llm=self._llm, store=self._store, default_top_k=self.settings.top_k
            )
            self._graph = build_compliance_graph(ctx)

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
    def check(self, plan_text: str, top_k: Optional[int] = None) -> dict:
        if self._graph is None:
            missing = []
            if not self.embeddings_ready:
                missing.append("embeddings")
            if not self.llm_ready:
                missing.append("llm")
            raise RuntimeError(
                f"Compliance check unavailable — missing: {', '.join(missing)}."
            )
        result = self._graph.invoke(
            {"plan_text": plan_text, "top_k": top_k or self.settings.top_k}
        )
        return {
            "extracted_facts": [
                line.strip("- ").strip()
                for line in (result.get("facts") or "").splitlines()
                if line.strip()
            ],
            "summary": result.get("summary", ""),
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

    # ------------------------------------------------------------------
    def check_plan_file(self, path, top_k: Optional[int] = None) -> dict:
        plan_text = load_plan_text(path)
        return self.check(plan_text, top_k=top_k)

    @property
    def index_size(self) -> int:
        return self._store.size if self._store else 0
