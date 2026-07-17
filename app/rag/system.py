"""Top-level RAG system: owns the embedding provider, vector store, LLM, and
the LangGraph compliance workflow, and exposes the two operations the API needs:
ingest (build the rule index) and check (run a compliance analysis).
"""

from __future__ import annotations

from typing import Optional

from app.config import get_settings
from app.rag.graph import Context, build_compliance_graph
from app.rag.ingestion import chunk_text, load_kbr_documents, load_plan_text
from app.rag.vectorstore import RuleVectorStore


class RAGSystem:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.embeddings_ready = False
        self.llm_ready = False
        self._provider = None
        self._store: Optional[RuleVectorStore] = None
        self._llm = None
        self._graph = None

        # Embeddings are required for retrieval; surface a clear error if missing.
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
        try:
            from app.rag.llm import ClaudeClient

            self._llm = ClaudeClient()
            self.llm_ready = True
        except RuntimeError as exc:
            self._llm_error = str(exc)

        if self._provider is not None:
            self._store = RuleVectorStore(self._provider, self.settings.index_dir)
            self._store.load_or_create()

        if self._store is not None and self._llm is not None:
            ctx = Context(
                llm=self._llm, store=self._store, default_top_k=self.settings.top_k
            )
            self._graph = build_compliance_graph(ctx)

    # ------------------------------------------------------------------
    def ingest(self, data_dir: Optional[str] = None) -> dict:
        if not self.embeddings_ready or self._store is None:
            raise RuntimeError(
                getattr(self, "_embed_error", "Embeddings are not configured.")
            )
        docs = load_kbr_documents(data_dir)
        total_chunks = 0
        for text, source in docs:
            chunks = chunk_text(text)
            if not chunks:
                continue
            metas = [{"source": source, "chunk": i + 1} for i in range(len(chunks))]
            self._store.add_texts(chunks, metas)
            total_chunks += len(chunks)
        return {
            "documents": len(docs),
            "chunks": total_chunks,
            "index_size": self._store.size,
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
                {"source": meta.get("source", ""), "excerpt": text, "score": score}
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
