"""Tests for ``app.rag.system.AnalysisMemo`` and the analyze-step memoisation.

The ``AnalysisMemo`` is the in-process TTL cache that lets an identical
re-check (same facts against the same index contents) skip the analysis LLM
call. These tests cover the memo's get/put/TTL/eviction behaviour directly,
plus the integration contract that a second ``RAGSystem.check`` of the same
plan performs fewer analyze LLM calls than the first. Fully offline (fakes).
"""

from __future__ import annotations

import pytest

from app.rag.prompts import SYSTEM_ANALYZE
from app.rag.system import AnalysisMemo, RAGSystem
from tests.conftest import FakeLLM

PLAN = "3 floor building, 12m tall, 1m front setback"


# ---------------------------------------------------------------------------
# AnalysisMemo primitives
# ---------------------------------------------------------------------------
def test_memo_get_miss_then_hit():
    memo = AnalysisMemo(ttl=300, maxsize=8)
    assert memo.get("k") is None  # miss
    memo.put("k", ("json", []))
    assert memo.get("k") == ("json", [])  # hit
    stats = memo.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1


def test_memo_respects_ttl_expiry(monkeypatch):
    memo = AnalysisMemo(ttl=100, maxsize=8)
    now = [5000.0]
    monkeypatch.setattr("app.rag.system.time.time", lambda: now[0])

    memo.put("k", "v")
    assert memo.get("k") == "v"
    now[0] += 200.0  # advance past the TTL
    assert memo.get("k") is None


def test_memo_evicts_oldest_beyond_maxsize():
    memo = AnalysisMemo(ttl=300, maxsize=2)
    memo.put("a", 1)
    memo.put("b", 2)
    memo.put("c", 3)  # forces eviction of the oldest ("a")
    assert memo.get("a") is None
    assert memo.get("b") == 2
    assert memo.get("c") == 3


def test_memo_clear_empties():
    memo = AnalysisMemo(ttl=300, maxsize=8)
    memo.put("a", 1)
    memo.put("b", 2)
    memo.clear()
    assert memo.stats()["size"] == 0
    assert memo.get("a") is None


def test_memo_stats_shape():
    memo = AnalysisMemo(ttl=60, maxsize=4)
    stats = memo.stats()
    assert set(stats) == {"size", "hits", "misses", "maxsize", "ttl"}


# ---------------------------------------------------------------------------
# Integration: identical re-check skips the analyze LLM
# ---------------------------------------------------------------------------
def _count_analyze_calls(llm: FakeLLM) -> int:
    return sum(1 for c in llm.calls if c["system"] == SYSTEM_ANALYZE)


def test_identical_recheck_skips_analyze_llm(fake_provider, tmp_path):
    llm = FakeLLM(analyze_mode="ok")
    rag = RAGSystem(provider=fake_provider, llm=llm, index_dir=str(tmp_path / "ix"))
    rag._store.add_texts(
        ["Rule 5: min front setback 1.8m"],
        [{"source": "kbr.txt", "rule_id": "Rule 5"}],
    )

    first = rag.check(PLAN, top_k=1)
    analyze_after_first = _count_analyze_calls(llm)
    assert analyze_after_first == 1  # cold cache: one analyze call

    second = rag.check(PLAN, top_k=1)
    analyze_after_second = _count_analyze_calls(llm)
    # Warm cache: the analyze step is memoised, so NO new analyze LLM call.
    assert analyze_after_second == 1
    # Both checks return the same violations (the memo replays the result).
    assert second["violations"] == first["violations"]


def test_recheck_after_index_change_invalidates_memo(fake_provider, tmp_path):
    llm = FakeLLM(analyze_mode="ok")
    rag = RAGSystem(provider=fake_provider, llm=llm, index_dir=str(tmp_path / "ix"))
    rag._store.add_texts(["Rule 5: min front setback 1.8m"], [{"source": "kbr.txt"}])

    rag.check(PLAN, top_k=1)
    assert _count_analyze_calls(llm) == 1

    # Mutate the index contents -> content_version changes -> memo key changes.
    rag._store.add_texts(["Rule 9: new parking rule"], [{"source": "kbr.txt"}])
    rag.check(PLAN, top_k=1)
    # A content change busts the memo, so the analyze LLM runs again.
    assert _count_analyze_calls(llm) == 2


# ---------------------------------------------------------------------------
# RAGSystem readiness / degradation guards
# ---------------------------------------------------------------------------
def test_check_without_embeddings_raises_clear_error(tmp_path):
    llm = FakeLLM(analyze_mode="ok")
    rag = RAGSystem(provider=None, llm=llm, index_dir=str(tmp_path / "ix"))
    # No provider -> no store -> graph never built.
    with pytest.raises(RuntimeError, match="missing"):
        rag.check(PLAN)


def test_health_flags_reflect_injected_fakes(fake_provider, tmp_path):
    llm = FakeLLM(analyze_mode="ok")
    rag = RAGSystem(provider=fake_provider, llm=llm, index_dir=str(tmp_path / "ix"))
    assert rag.embeddings_ready is True
    assert rag.llm_ready is True
    assert rag.index_size == 0  # nothing ingested yet
