"""FAISS-backed vector store for Kerala Building Rules chunks.

Embeddings are L2-normalised and stored in a flat inner-product index, so the
returned "score" is a true cosine similarity in [-1, 1] where *higher means
more similar*. Chunk metadata (including a stable content hash used to make
re-ingestion idempotent) is kept alongside the index as JSON.

Hybrid retrieval (T3.3): alongside the dense cosine index the store keeps a
BM25 lexical index over the same chunks. ``similarity_search`` (hybrid, the
default) fuses the two signals — a min-max-normalised dense cosine score and a
non-negative, bounded BM25 score — into a single deterministic score weighted
toward the dense path (``hybrid_weight``). Dense-only retrieval (the previous
behaviour) is preserved via ``dense_only_search`` and by passing
``use_hybrid=False``. An optional approximate-nearest-neighbour (ANN) dense
index (IVF flat / HNSW) is selectable behind ``ann_backend``; the exact
``IndexFlatIP`` flat index stays the default.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np

from app.rag.embeddings import EmbeddingProvider, l2_normalize

# Bump when the on-disk layout or similarity semantics change. A saved index
# whose version does not match is ignored and rebuilt, so we never mix old
# L2-distance vectors with new cosine-similarity vectors. 2 -> 3 introduces
# hybrid (BM25 + cosine) retrieval and the optional ANN dense index.
_INDEX_VERSION = 3

# BM25 is a pure-python optional dependency. If it is not installed we degrade
# gracefully to dense-only retrieval (``hybrid_available`` is False).
try:  # pragma: no cover - exercised indirectly when rank_bm25 is absent
    from rank_bm25 import BM25Okapi
except Exception:  # noqa: BLE001 - any import failure -> dense-only fallback
    BM25Okapi = None  # type: ignore[assignment]

# Whitespace tokenizer for the BM25 lexical index (case-insensitive).
_TOKEN_SPLIT = str.split


def _tokenize(text: str) -> List[str]:
    """Lower-cased whitespace tokens for the BM25 lexical index."""
    return _TOKEN_SPLIT(text.lower())


def _minmax_normalize(scores: List[float]) -> List[float]:
    """Scale scores to [0, 1]; a constant series maps to all-ones (all equal).

    Used for the dense cosine contribution so it is comparable in scale to the
    bounded BM25 contribution before fusion.
    """
    if not scores:
        return []
    lo = min(scores)
    hi = max(scores)
    if hi - lo < 1e-9:
        return [1.0] * len(scores)
    span = hi - lo
    return [(s - lo) / span for s in scores]


def _max_normalize(scores: List[float]) -> List[float]:
    """Shift to non-negative, then scale to [0, 1] by the max (0.0 if ~0).

    BM25 (``BM25Okapi``) can yield small negative scores for very common terms,
    so we first subtract the per-query minimum to make every score >= 0 while
    preserving relative order, then divide by the max. Dividing by the max keeps
    a hard top score near 1.0 even when only a single chunk is indexed (where
    min-max would collapse to 0).
    """
    if not scores:
        return []
    lo = min(scores)
    shifted = [s - lo for s in scores]
    hi = max(shifted)
    if hi < 1e-9:
        return [0.0] * len(scores)
    return [s / hi for s in shifted]


def default_hybrid_weight() -> float:
    """Dense-vs-BM25 fusion weight, overridable via ``RAG_HYBRID_WEIGHT``.

    The returned weight is the fraction of the fused score contributed by the
    dense cosine signal; the remainder is the BM25 (lexical) signal. Defaults
    to 0.7 (dense weighted higher), clamped to [0, 1].
    """
    raw = os.getenv("RAG_HYBRID_WEIGHT", "0.7")
    try:
        value = float(raw)
    except ValueError:
        return 0.7
    return max(0.0, min(1.0, value))


def default_ann_backend() -> Optional[str]:
    """Optional ANN backend from ``RAG_ANN_BACKEND``: ``None``/``"flat"`` (exact,
    the default), ``"ivf"`` (IndexIVFFlat), or ``"hnsw"`` (IndexHNSWFlat)."""
    raw = os.getenv("RAG_ANN_BACKEND", "").strip().lower()
    return raw or None


def _content_hash(text: str) -> str:
    """Stable hash of the raw chunk text — the dedup key for idempotent ingest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RuleVectorStore:
    def __init__(
        self,
        provider: EmbeddingProvider,
        index_dir: Path,
        score_threshold: Optional[float] = None,
        *,
        hybrid_weight: Optional[float] = None,
        ann_backend: Optional[str] = None,
        ann_nlist: int = 8,
        ann_nprobe: int = 1,
        ann_hnsw_m: int = 32,
    ) -> None:
        self.provider = provider
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "rules.faiss"
        self.meta_path = self.index_dir / "rules_meta.json"
        # Minimum cosine similarity for a hit to be returned. None = no filter.
        self.score_threshold = score_threshold
        # --- Hybrid retrieval (T3.3) -------------------------------------
        # Dense-vs-lexical fusion weight (dense share of the fused score).
        self.hybrid_weight = (
            default_hybrid_weight() if hybrid_weight is None else hybrid_weight
        )
        # Optional ANN dense index: None/"flat" keeps the exact IndexFlatIP;
        # "ivf"/"hnsw" select an approximate index trained on add.
        self.ann_backend = (ann_backend or "flat").strip().lower() or "flat"
        if self.ann_backend in ("flat", "exact", "none"):
            self.ann_backend = "flat"
        self.ann_nlist = max(1, int(ann_nlist))
        self.ann_nprobe = max(1, int(ann_nprobe))
        self.ann_hnsw_m = max(2, int(ann_hnsw_m))
        self._index: Optional[faiss.Index] = None
        self._texts: List[str] = []
        self._metas: List[dict] = []
        self._hashes: set[str] = set()
        self._bm25: Optional[object] = None  # BM25Okapi instance, rebuilt lazily

    # -- lexical (BM25) index ---------------------------------------------
    @property
    def hybrid_available(self) -> bool:
        """True when the BM25 dependency is importable (else dense-only)."""
        return BM25Okapi is not None

    def _rebuild_bm25(self) -> None:
        """(Re)build the BM25 index over the current chunk texts.

        Deterministic and offline. A no-op when the dependency is missing
        (store falls back to dense-only retrieval).
        """
        if not self.hybrid_available:
            self._bm25 = None
            return
        if not self._texts:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi([_tokenize(t) for t in self._texts])

    def content_version(self) -> str:
        """Fingerprint of the index contents (changes on any add/reset/rebuild).

        Derived from the set of per-chunk content hashes, so it reflects WHAT is
        indexed, not just HOW MANY items (unlike ``size``). Used as part of the
        analysis-memo key so a rebuild that swaps content but keeps the same
        count still invalidates cached analyses. Falls back to "size:N" when a
        store has no hashes (empty index).
        """
        if not self._hashes:
            return f"size:{len(self._texts)}"
        joined = "|".join(sorted(self._hashes))
        return f"content:{_content_hash(joined)}"

    # -- persistence -------------------------------------------------------
    def _new_dense_index(self) -> faiss.Index:
        """Build the dense inner-product index for the configured backend.

        ``flat`` (default) is the exact ``IndexFlatIP`` cosine index; ``ivf``
        and ``hnsw`` are approximate (ANN) variants with a flat IP coarse
        quantizer / HNSW graph. The approximate indexes are trained on first
        add. Returned untrained; training happens in ``_train_if_needed``.
        """
        dim = self.provider.dim
        if self.ann_backend == "ivf":
            quantizer = faiss.IndexFlatIP(dim)
            index = faiss.IndexIVFFlat(
                quantizer, dim, self.ann_nlist, faiss.METRIC_INNER_PRODUCT
            )
            index.nprobe = self.ann_nprobe
            return index
        if self.ann_backend == "hnsw":
            index = faiss.IndexHNSWFlat(
                dim, self.ann_hnsw_m, faiss.METRIC_INNER_PRODUCT
            )
            return index
        # Exact inner product on L2-normalised vectors == cosine similarity.
        return faiss.IndexFlatIP(dim)

    def _train_if_needed(self, embeddings: np.ndarray) -> None:
        """Train the dense index if it requires training (IVF) and is not yet.

        ``IndexIVFFlat`` needs training vectors before ``add``. We train on the
        first batch (capping clusters to the available sample count so small
        corpora still train) and request a warning-free quiet train. Flat/HNSW
        indexes need no training and are returned untouched.
        """
        index = self._index
        if index is None or getattr(index, "is_trained", True):
            return
        n = int(embeddings.shape[0])
        if n == 0:
            return
        # IVF with more clusters than samples cannot assign every centroid;
        # shrink nlist to the sample count so training succeeds on tiny corpora.
        if isinstance(index, faiss.IndexIVFFlat) and index.nlist > n:
            index.nlist = max(1, n)
        index.train(embeddings)

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
        try:
            self._index = faiss.read_index(str(self.index_path))
        except Exception:  # noqa: BLE001 - unreadable index -> rebuild
            return False
        self._texts = data["texts"]
        self._metas = data["metas"]
        self._hashes = set(
            data.get("hashes") or [_content_hash(t) for t in self._texts]
        )
        self._rebuild_bm25()
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
            self._index = self._new_dense_index()
            self._texts = []
            self._metas = []
            self._hashes = set()
            self._bm25 = None

    def reset(self) -> None:
        """Drop all vectors and metadata (used for a full rebuild of the index)."""
        self._index = self._new_dense_index()
        self._texts = []
        self._metas = []
        self._hashes = set()
        self._bm25 = None
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
        self._train_if_needed(embeddings)
        self._index.add(embeddings)  # type: ignore[union-attr]
        self._texts.extend(keep_texts)
        self._metas.extend(keep_metas)
        self._rebuild_bm25()
        self._save()
        return len(keep_texts)

    @property
    def size(self) -> int:
        return 0 if self._index is None else int(self._index.ntotal)  # type: ignore[union-attr]

    # -- retrieval ---------------------------------------------------------
    def _dense_cosine_scores(self, query: str) -> List[float]:
        """Cosine similarity of ``query`` against every indexed chunk.

        With the exact flat index this queries all ``ntotal`` vectors; with an
        ANN index it returns approximate scores (still aligned by chunk id).
        An all-``-inf`` row would make min-max fusion degenerate, so ANN misses
        are floored below.
        """
        assert self._index is not None
        q = self.provider.embed([query])
        q = l2_normalize(np.ascontiguousarray(q, dtype="float32"))
        n = self.size
        scores, idxs = self._index.search(q, n)  # type: ignore[union-attr]
        dense = [float("-inf")] * n
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            dense[int(idx)] = float(score)
        return dense

    def _bm25_scores(self, query: str) -> List[float]:
        """Raw BM25 scores (>= 0) for every indexed chunk, or all-zeros when the
        lexical index is unavailable (dense-only fallback)."""
        if not self.hybrid_available or self._bm25 is None:
            return [0.0] * self.size
        return [float(s) for s in self._bm25.get_scores(_tokenize(query))]  # type: ignore[union-attr]

    def similarity_search(
        self,
        query: str,
        k: int = 6,
        score_threshold: Optional[float] = None,
        use_hybrid: bool = True,
    ) -> List[Tuple[str, dict, float]]:
        """Return up to ``k`` (text, meta, score) hits, best first.

        By default this fuses the dense cosine signal with the BM25 lexical
        signal (hybrid retrieval, T3.3): both are normalised to comparable
        scales and summed with the dense path weighted ``hybrid_weight``
        (default 0.7). Fused scores retain the dense-only contract (higher =
        more similar, ``score == 1.0`` for an exact-copy query, below-threshold
        hits dropped), so existing thresholding keeps working.

        Pass ``use_hybrid=False`` (or run without the ``rank_bm25`` dependency)
        for dense-only retrieval — the previous cosine-only behaviour. The
        scoring/ordering are deterministic for a given corpus and query.

        Score semantics changed from the original raw ``IndexFlatL2`` distance
        (lower = better): embeddings are L2-normalised and stored in an inner-
        product index, so the dense score is a cosine similarity in [-1, 1]
        where **higher = more similar**. Results below ``score_threshold``
        (or the store default, sourced from the ``MIN_SCORE`` env var, default
        ``0.0``) are dropped.
        """
        if self._index is None or self.size == 0:
            return []
        if not use_hybrid or not self.hybrid_available:
            return self.dense_only_search(query, k=k, score_threshold=score_threshold)
        return self._hybrid_search(query, k=k, score_threshold=score_threshold)

    def _hybrid_search(
        self,
        query: str,
        k: int = 6,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[str, dict, float]]:
        """Fuse dense cosine + BM25 into a single deterministic ranking."""
        threshold = (
            score_threshold if score_threshold is not None else self.score_threshold
        )
        n = self.size
        k = min(k, n)

        dense_raw = self._dense_cosine_scores(query)
        # Floor ANN misses (-inf) at the current minimum so min-max works.
        finite = [s for s in dense_raw if s != float("-inf")]
        floor = min(finite) if finite else 0.0
        dense_raw = [s if s != float("-inf") else floor for s in dense_raw]
        dense_norm = _minmax_normalize(dense_raw)
        bm25_norm = _max_normalize(self._bm25_scores(query))

        alpha = self.hybrid_weight
        fused = [alpha * dense_norm[i] + (1.0 - alpha) * bm25_norm[i] for i in range(n)]
        # Deterministic descending sort; ties broken by index (stable).
        order = sorted(range(n), key=lambda i: (-fused[i], i))
        results: List[Tuple[str, dict, float]] = []
        for i in order[:k]:
            score = float(fused[i])
            if threshold is not None and score < threshold:
                continue
            results.append((self._texts[i], self._metas[i], score))
        return results

    def dense_only_search(
        self,
        query: str,
        k: int = 6,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[str, dict, float]]:
        """Dense-only cosine retrieval (the pre-hybrid behaviour).

        Score is the raw cosine similarity in [-1, 1] from the inner-product
        index (an exact-copy query scores ~1.0), threshold-filtered as before.
        Used when hybrid retrieval is disabled or BM25 is unavailable.
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
