"""FAISS-backed vector store for Kerala Building Rules chunks.

Embeddings are L2-normalised and stored in a flat inner-product index, so the
returned "score" is a true cosine similarity in [-1, 1] where *higher means
more similar*. Chunk metadata (including a stable content hash used to make
re-ingestion idempotent) is kept alongside the index as JSON.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np

from app.rag.embeddings import EmbeddingProvider, l2_normalize

# Bump when the on-disk layout or similarity semantics change. A saved index
# whose version does not match is ignored and rebuilt, so we never mix old
# L2-distance vectors with new cosine-similarity vectors.
_INDEX_VERSION = 2


def _content_hash(text: str) -> str:
    """Stable hash of the raw chunk text — the dedup key for idempotent ingest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RuleVectorStore:
    def __init__(
        self,
        provider: EmbeddingProvider,
        index_dir: Path,
        score_threshold: Optional[float] = None,
    ) -> None:
        self.provider = provider
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "rules.faiss"
        self.meta_path = self.index_dir / "rules_meta.json"
        # Minimum cosine similarity for a hit to be returned. None = no filter.
        self.score_threshold = score_threshold
        self._index: Optional[faiss.IndexFlatIP] = None
        self._texts: List[str] = []
        self._metas: List[dict] = []
        self._hashes: set[str] = set()

    # -- persistence -------------------------------------------------------
    def _load(self) -> bool:
        if not self.index_path.exists() or not self.meta_path.exists():
            return False
        try:
            with open(self.meta_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return False
        # Reject indexes written under different semantics/versions.
        if data.get("version") != _INDEX_VERSION:
            return False
        self._index = faiss.read_index(str(self.index_path))
        self._texts = data["texts"]
        self._metas = data["metas"]
        self._hashes = set(
            data.get("hashes") or [_content_hash(t) for t in self._texts]
        )
        return True

    def _save(self) -> None:
        if self._index is None:
            return
        faiss.write_index(self._index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "version": _INDEX_VERSION,
                    "model": getattr(self.provider, "model", None),
                    "dim": self.provider.dim,
                    "texts": self._texts,
                    "metas": self._metas,
                    "hashes": sorted(self._hashes),
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )

    def load_or_create(self) -> None:
        if not self._load():
            # Inner product on L2-normalised vectors == cosine similarity.
            self._index = faiss.IndexFlatIP(self.provider.dim)
            self._texts = []
            self._metas = []
            self._hashes = set()

    def reset(self) -> None:
        """Drop all vectors and metadata (used for a full rebuild of the index)."""
        self._index = faiss.IndexFlatIP(self.provider.dim)
        self._texts = []
        self._metas = []
        self._hashes = set()
        self._save()

    # -- mutation ----------------------------------------------------------
    def add_texts(
        self,
        texts: List[str],
        metas: Optional[List[dict]] = None,
        dedup: bool = True,
    ) -> int:
        """Embed and index ``texts``.

        When ``dedup`` is on, chunks whose content was already indexed are
        skipped, making re-ingestion of the same documents idempotent.
        Returns the number of *newly added* chunks.
        """
        if not texts:
            return 0
        if self._index is None:
            self.load_or_create()

        keep_texts: List[str] = []
        keep_metas: List[dict] = []
        for i, text in enumerate(texts):
            meta = metas[i] if metas else {}
            h = _content_hash(text)
            if dedup and h in self._hashes:
                continue  # already indexed
            self._hashes.add(h)
            meta = dict(meta)
            meta.setdefault("sha256", h)
            keep_texts.append(text)
            keep_metas.append(meta)

        if not keep_texts:
            return 0

        embeddings = self.provider.embed(keep_texts)
        # Normalise -> inner product ranks by cosine similarity.
        embeddings = l2_normalize(np.ascontiguousarray(embeddings, dtype="float32"))
        self._index.add(embeddings)  # type: ignore[union-attr]
        self._texts.extend(keep_texts)
        self._metas.extend(keep_metas)
        self._save()
        return len(keep_texts)

    @property
    def size(self) -> int:
        return 0 if self._index is None else int(self._index.ntotal)  # type: ignore[union-attr]

    # -- retrieval ---------------------------------------------------------
    def similarity_search(
        self,
        query: str,
        k: int = 6,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[str, dict, float]]:
        """Return up to ``k`` (text, meta, similarity_score) hits, best first.

        Score semantics changed from the original raw ``IndexFlatL2`` distance
        (lower = better): embeddings are L2-normalised and stored in
        ``IndexFlatIP``, so the returned score is a cosine similarity in
        [-1, 1] where **higher = more similar**. Results below
        ``score_threshold`` (or the store default, sourced from the ``MIN_SCORE``
        env var, default ``0.0``) are dropped.
        """
        if self._index is None or self.size == 0:
            return []
        threshold = (
            score_threshold if score_threshold is not None else self.score_threshold
        )
        k = min(k, self.size)
        q = self.provider.embed([query])
        q = l2_normalize(np.ascontiguousarray(q, dtype="float32"))
        scores, idxs = self._index.search(q, k)  # type: ignore[union-attr]
        results: List[Tuple[str, dict, float]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            score = float(score)
            if threshold is not None and score < threshold:
                continue
            results.append((self._texts[idx], self._metas[idx], score))
        return results
