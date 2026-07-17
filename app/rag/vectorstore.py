"""FAISS-backed vector store for Kerala Building Rules chunks.

Stores embeddings in a flat L2 index and keeps the parallel chunk metadata on
disk (pandas-free) so the index can be reloaded without re-embedding.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np

from app.rag.embeddings import EmbeddingProvider


class RuleVectorStore:
    def __init__(self, provider: EmbeddingProvider, index_dir: Path) -> None:
        self.provider = provider
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "rules.faiss"
        self.meta_path = self.index_dir / "rules_meta.json"
        self._index: faiss.IndexFlatL2 | None = None
        self._texts: List[str] = []
        self._metas: List[dict] = []

    # -- persistence -------------------------------------------------------
    def _load(self) -> bool:
        if not self.index_path.exists() or not self.meta_path.exists():
            return False
        self._index = faiss.read_index(str(self.index_path))
        with open(self.meta_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._texts = data["texts"]
        self._metas = data["metas"]
        return True

    def _save(self) -> None:
        if self._index is None:
            return
        faiss.write_index(self._index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as fh:
            json.dump(
                {"texts": self._texts, "metas": self._metas},
                fh,
                ensure_ascii=False,
                indent=2,
            )

    def load_or_create(self) -> None:
        if not self._load():
            self._index = faiss.IndexFlatL2(self.provider.dim)

    # -- mutation ----------------------------------------------------------
    def add_texts(self, texts: List[str], metas: List[dict] | None = None) -> None:
        if not texts:
            return
        if self._index is None:
            self.load_or_create()
        embeddings = self.provider.embed(texts)
        # FAISS needs contiguous float32.
        embeddings = np.ascontiguousarray(embeddings, dtype="float32")
        self._index.add(embeddings)  # type: ignore[union-attr]
        for i, text in enumerate(texts):
            meta = metas[i] if metas else {}
            self._texts.append(text)
            self._metas.append(meta)
        self._save()

    @property
    def size(self) -> int:
        return 0 if self._index is None else int(self._index.ntotal)  # type: ignore[union-attr]

    # -- retrieval ---------------------------------------------------------
    def similarity_search(
        self, query: str, k: int = 6
    ) -> List[Tuple[str, dict, float]]:
        if self._index is None or self.size == 0:
            return []
        k = min(k, self.size)
        q = self.provider.embed([query])
        q = np.ascontiguousarray(q, dtype="float32")
        scores, idxs = self._index.search(q, k)  # type: ignore[union-attr]
        results: List[Tuple[str, dict, float]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append((self._texts[idx], self._metas[idx], float(score)))
        return results
