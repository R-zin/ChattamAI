"""Shared fixtures: deterministic fakes for embeddings / LLM, tmp FAISS dirs,
and a FastAPI TestClient wired to those fakes with NO network access.

Everything here is offline-safe. ``FakeEmbeddingProvider`` turns text into a
deterministic unit vector derived from a SHA-256 hash, so identical texts embed
identically across runs and a query that matches a stored text returns it as the
top hit. ``FakeLLM`` returns scripted responses keyed on the SYSTEM prompt, so
extract/analyze/summarize each get a canned output (including a malformed-JSON
case for the analyze step).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

# Make the repo root importable when tests run from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.embeddings import EmbeddingProvider  # noqa: E402
from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY  # noqa: E402
from app.rag.vectorstore import RuleVectorStore  # noqa: E402


# ---------------------------------------------------------------------------
# Fake embedding provider
# ---------------------------------------------------------------------------
class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embeddings from a text hash (no network, no randomness).

    Each text maps to a reproducible ``dim``-vector built by hashing the text
    with SHA-256 and expanding the digest. Identical texts give identical
    vectors, so a query equal to a stored chunk is always its own nearest
    neighbour (L2 distance 0) — which lets retrieval tests assert exact matches
    without a real embedding model.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim
        self.calls: List[List[str]] = []  # record embedded batches for assertions

    def _vector_for(self, text: str) -> np.ndarray:
        # Expand the SHA-256 digest deterministically to fill `dim` floats.
        raw = b""
        counter = 0
        while len(raw) < self.dim * 4:
            raw += hashlib.sha256(f"{text}::{counter}".encode("utf-8")).digest()
            counter += 1
        ints = np.frombuffer(raw[: self.dim * 4], dtype=np.uint32).astype("float64")
        # Centre around 0 and normalise to a unit vector for stable L2 geometry.
        vec = ints - ints.mean()
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.astype("float32")

    def embed(self, texts: List[str]) -> np.ndarray:
        self.calls.append(list(texts))
        if not texts:
            return np.empty((0, self.dim), dtype="float32")
        return np.stack([self._vector_for(t) for t in texts]).astype("float32")


# ---------------------------------------------------------------------------
# Fake LLM
# ---------------------------------------------------------------------------
ANALYZE_PAYLOAD = {
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

#: A canned, well-formed JSON body for the analyze step.
ANALYZE_JSON_OK = json.dumps(ANALYZE_PAYLOAD)

#: A malformed analyze body that the parser must not crash on.
ANALYZE_JSON_MALFORMED = '{"violations": [ {bad json,,, }'

#: The canned extract output (bullet list, as the real prompt requests).
FACTS_TEXT = (
    "- plot area: 300 sq.m\n"
    "- number of floors: 3\n"
    "- building height: 12m\n"
    "- front setback: 1m"
)

SUMMARY_TEXT = "The plan shows one high-severity setback violation; recommend revision."


class FakeLLM:
    """Scripted LLM: returns canned responses keyed on the SYSTEM prompt.

    ``analyze_mode`` controls what the analyze step returns:
    ``"ok"`` -> well-formed violations JSON, ``"malformed"`` -> broken JSON,
    ``"fenced"`` -> JSON wrapped in ```json fences, ``"prose"`` -> JSON embedded
    in surrounding prose. Anything else falls back to a generic echo.
    """

    def __init__(self, analyze_mode: str = "ok") -> None:
        self.analyze_mode = analyze_mode
        self.calls: List[Dict[str, str]] = []  # (system, user) pairs seen

    def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if system == SYSTEM_EXTRACT:
            return FACTS_TEXT
        if system == SYSTEM_ANALYZE:
            if self.analyze_mode == "ok":
                return ANALYZE_JSON_OK
            if self.analyze_mode == "malformed":
                return ANALYZE_JSON_MALFORMED
            if self.analyze_mode == "fenced":
                return "```json\n" + ANALYZE_JSON_OK + "\n```"
            if self.analyze_mode == "prose":
                return (
                    "Here is the analysis:\n" + ANALYZE_JSON_OK + "\nHope that helps."
                )
            return self.analyze_mode  # treat the mode itself as the raw body
        if system == SYSTEM_SUMMARY:
            return SUMMARY_TEXT
        return "UNSCRIPTED SYSTEM PROMPT"


# ---------------------------------------------------------------------------
# Factories / fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider(dim=8)


@pytest.fixture
def index_dir(tmp_path):
    """A fresh tmp directory for a FAISS index."""
    d = tmp_path / "index"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def store(fake_provider, index_dir) -> RuleVectorStore:
    s = RuleVectorStore(fake_provider, index_dir)
    s.load_or_create()
    return s


def make_populated_store(
    fake_provider: FakeEmbeddingProvider, index_dir: Path
) -> RuleVectorStore:
    """A store pre-loaded with a small, deterministic KBR-like rule set."""
    s = RuleVectorStore(fake_provider, index_dir)
    s.load_or_create()
    texts = [
        "Rule 5: The minimum front setback for a building up to 10m is 1.8m.",
        "Rule 11: Off-street parking shall be provided at one car per 100 sq.m.",
        "Rule 7: The maximum floor space index (FSI) for residential use is 1.5.",
    ]
    metas = [
        {"source": "kbr.txt", "chunk": i + 1, "rule_id": rid}
        for i, rid in enumerate(["Rule 5", "Rule 11", "Rule 7"])
    ]
    s.add_texts(texts, metas)
    return s


@pytest.fixture
def populated_store(fake_provider, index_dir) -> RuleVectorStore:
    return make_populated_store(fake_provider, index_dir)


def build_rag_system(
    provider,
    llm,
    index_dir,
    preload: bool = True,
):
    """Construct a RAGSystem on fakes (no network) with an optional rule set."""
    from app.rag.system import RAGSystem

    rag = RAGSystem(provider=provider, llm=llm, index_dir=str(index_dir))
    if preload:
        make_populated_store_into(rag._store)
    return rag


def make_populated_store_into(store: RuleVectorStore) -> None:
    texts = [
        "Rule 5: The minimum front setback for a building up to 10m is 1.8m.",
        "Rule 7: The maximum floor space index (FSI) for residential use is 1.5.",
    ]
    metas = [
        {"source": "kbr.txt", "chunk": 1, "rule_id": "Rule 5"},
        {"source": "kbr.txt", "chunk": 2, "rule_id": "Rule 7"},
    ]
    store.add_texts(texts, metas)


@pytest.fixture
def app_client(tmp_path):
    """FastAPI TestClient with RAG fakes injected and no network access.

    Overriding ``app.state.rag`` after startup keeps ``get_rag`` (which reads
    ``app.state.rag``) returning our faked system.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    provider = FakeEmbeddingProvider(dim=8)
    llm = FakeLLM(analyze_mode="ok")
    rag = build_rag_system(provider, llm, tmp_path / "index", preload=True)

    with TestClient(app) as client:
        app.state.rag = rag
        # Expose fakes on the client for per-test inspection.
        client.fake_llm = llm  # type: ignore[attr-defined]
        client.fake_provider = provider  # type: ignore[attr-defined]
        yield client
