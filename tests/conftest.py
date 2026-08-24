"""Shared fixtures: deterministic fakes for embeddings / LLM, tmp FAISS dirs,
and a FastAPI TestClient wired to those fakes with NO network access.

Everything here is offline-safe. ``FakeEmbeddingProvider`` turns text into a
deterministic unit vector via **token feature-hashing**: each distinct token
adds ``+1`` to a hashed bucket, then the vector is L2-normalised. Texts that
share tokens therefore get a *positive* cosine similarity, an identical text
gets cosine ``1.0``, and unrelated texts sit near ``0``. That makes the
cosine ``IndexFlatIP`` store (higher = better, threshold ``score < 0.0`` drops)
retrieve semantically-related chunks — e.g. a "front setback" query ranks the
setback rule first — so retrieval tests assert meaningful nearest neighbours
without a real embedding model. ``FakeLLM`` returns scripted responses keyed on
the SYSTEM prompt so extract/analyze/summarize (and the analyze repair-retry)
get canned outputs, including a malformed-JSON case.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

# Make the repo root importable when tests run from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# app/main.py (imported by the ``app_client`` fixture / TestClient) uses top-level
# imports (``from routes import ...``, ``from rag.system import ...``), which require
# the ``app/`` directory itself on ``sys.path``. Without this the TestClient path
# errors with ``ModuleNotFoundError: No module named 'routes'``. Sibling modules use
# the absolute ``from app...`` style, so putting both the root and ``app/`` on the
# path satisfies every import style.
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

# The app's auth/DB layer (agent-4) reads DATABASE_URL at import of
# ``app.services.database`` and creates an engine pointing at
# ``sqlite:///./chattamai.db`` by default — which would write a stray DB file
# into the test working directory. Point it at a throwaway file in the system
# temp dir instead, BEFORE any app import pulls in the database module, so the
# whole suite stays offline and leaves no artifacts. (Best-effort: the app
# tolerates a missing/unreachable DB at startup via init_db_safe.)
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///" + str(Path(tempfile.gettempdir()) / "agent5_test_suite.db"),
)

from app.rag.embeddings import EmbeddingProvider  # noqa: E402
from app.rag.graph import SYSTEM_ANALYZE_REPAIR  # noqa: E402
from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY  # noqa: E402
from app.rag.vectorstore import RuleVectorStore  # noqa: E402


# ---------------------------------------------------------------------------
# Fake embedding provider
# ---------------------------------------------------------------------------
class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic token feature-hashing embeddings (no network, no randomness).

    Each text maps to a unit vector built by hashing every distinct token into
    one of ``dim`` buckets and adding ``+1`` per token (unsigned, so shared
    tokens always increase the dot product), then L2-normalising. Cosine
    similarity is therefore a lexical-overlap signal: identical text -> ``1.0``,
    topically-related text -> positive, unrelated text -> ~``0``. Deterministic
    across runs and across processes.

    A larger ``dim`` (default 256) keeps hash collisions rare so nearest-
    neighbour ranking is stable for the small test corpora. The store applies
    its own L2-normalisation, so these vectors feed cosine search directly.
    """

    _TOKEN_RE = re.compile(r"[a-z0-9.]+")

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.calls: List[List[str]] = []  # record embedded batches for assertions

    def _tokens(self, text: str) -> List[str]:
        return self._TOKEN_RE.findall(text.lower())

    def _vector_for(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype="float64")
        for tok in set(self._tokens(text)):  # set -> presence, not length-biased
            h = int.from_bytes(hashlib.sha256(tok.encode("utf-8")).digest()[:8], "big")
            vec[h % self.dim] += 1.0
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

    The graph's ``analyze`` node does ONE repair retry with
    ``SYSTEM_ANALYZE_REPAIR`` when the first analyze body can't be parsed.
    ``repair_mode`` controls that retry's body: ``"ok"`` -> a valid repaired
    payload (repair succeeds), ``"malformed"`` -> still broken (the node sets
    ``error="parse_failed: ..."``). Defaults to ``"malformed"`` so the error
    path is exercisable; set ``repair_mode="ok"`` to test repair recovery.
    """

    def __init__(
        self, analyze_mode: str = "ok", repair_mode: str = "malformed"
    ) -> None:
        self.analyze_mode = analyze_mode
        self.repair_mode = repair_mode
        self.calls: List[Dict[str, str]] = []  # (system, user) pairs seen

    def _analyze_body(self, mode: str) -> str:
        if mode == "ok":
            return ANALYZE_JSON_OK
        if mode == "malformed":
            return ANALYZE_JSON_MALFORMED
        if mode == "fenced":
            return "```json\n" + ANALYZE_JSON_OK + "\n```"
        if mode == "prose":
            return "Here is the analysis:\n" + ANALYZE_JSON_OK + "\nHope that helps."
        return mode  # treat the mode itself as the raw body

    def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if system == SYSTEM_EXTRACT:
            return FACTS_TEXT
        if system == SYSTEM_ANALYZE:
            return self._analyze_body(self.analyze_mode)
        if system == SYSTEM_ANALYZE_REPAIR:
            return self._analyze_body(self.repair_mode)
        if system == SYSTEM_SUMMARY:
            return SUMMARY_TEXT
        return "UNSCRIPTED SYSTEM PROMPT"


# ---------------------------------------------------------------------------
# Factories / fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()  # default dim=256 keeps hash collisions rare


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

    provider = FakeEmbeddingProvider()
    llm = FakeLLM(analyze_mode="ok")
    rag = build_rag_system(provider, llm, tmp_path / "index", preload=True)

    with TestClient(app) as client:
        app.state.rag = rag
        # Expose fakes on the client for per-test inspection.
        client.fake_llm = llm  # type: ignore[attr-defined]
        client.fake_provider = provider  # type: ignore[attr-defined]
        yield client
