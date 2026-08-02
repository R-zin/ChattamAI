"""Tests for the LangGraph compliance workflow with faked LLM + store.

These drive ``build_compliance_graph`` over a ``FakeLLM`` (scripted per SYSTEM
prompt) and a ``RuleVectorStore`` on ``FakeEmbeddingProvider`` — fully offline.
The empty-index short-circuit to ``insufficient`` is a contract other agents
(agent-2) must preserve, so it is asserted explicitly.
"""

from __future__ import annotations

from app.rag.graph import Context, build_compliance_graph, route_retrieve
from app.rag.system import RAGSystem
from tests.conftest import (
    ANALYZE_PAYLOAD,
    FACTS_TEXT,
    SUMMARY_TEXT,
    FakeLLM,
    make_populated_store,
)

PLAN = "3 floor building, 12m tall, 1m front setback"


def _graph(store, llm):
    return build_compliance_graph(Context(llm=llm, store=store, default_top_k=6))


# -- routing ---------------------------------------------------------------
def test_route_retrieve_short_circuits_on_empty():
    assert route_retrieve({"retrieved": []}) == "insufficient"
    assert route_retrieve({}) == "insufficient"


def test_route_retrieve_proceeds_when_rules_found():
    assert route_retrieve({"retrieved": [("t", {}, 0.1)]}) == "analyze"


# -- full run --------------------------------------------------------------
def test_full_run_produces_scripted_violations_and_summary(fake_provider, index_dir):
    store = make_populated_store(fake_provider, index_dir)
    llm = FakeLLM(analyze_mode="ok")
    out = _graph(store, llm).invoke({"plan_text": PLAN, "top_k": 3})

    assert out["violations"] == ANALYZE_PAYLOAD["violations"]
    assert out["summary"] == SUMMARY_TEXT
    assert out["facts"] == FACTS_TEXT
    assert len(out["retrieved"]) == 3


def test_full_run_calls_extract_analyze_summarize_in_order(fake_provider, index_dir):
    store = make_populated_store(fake_provider, index_dir)
    llm = FakeLLM(analyze_mode="ok")
    out = _graph(store, llm).invoke({"plan_text": PLAN, "top_k": 3})

    from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY

    systems = [c["system"] for c in llm.calls]
    assert systems == [SYSTEM_EXTRACT, SYSTEM_ANALYZE, SYSTEM_SUMMARY]
    assert out["analysis_json"]  # raw analyzer output preserved


def test_analyze_malformed_json_yields_no_violations_but_still_summarizes(
    fake_provider, index_dir
):
    # CURRENT: malformed analyze JSON -> violations=[] (silently) and the
    # summarize step still runs. Phase-2 (agent-2) will instead record an error.
    store = make_populated_store(fake_provider, index_dir)
    llm = FakeLLM(analyze_mode="malformed")
    out = _graph(store, llm).invoke({"plan_text": PLAN, "top_k": 3})
    assert out["violations"] == []
    assert out["summary"] == SUMMARY_TEXT
    assert "error" not in out  # current silent behaviour


# -- empty index / insufficient path ---------------------------------------
def test_empty_index_short_circuits_to_insufficient(fake_provider, index_dir):
    from app.rag.vectorstore import RuleVectorStore

    store = RuleVectorStore(fake_provider, index_dir)
    store.load_or_create()  # empty index
    llm = FakeLLM()
    out = _graph(store, llm).invoke({"plan_text": PLAN, "top_k": 3})

    assert out["violations"] == []
    assert "No relevant Kerala Building Rules" in out["summary"]
    # extract still runs once; analyze/summarize are skipped.
    from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY

    systems = [c["system"] for c in llm.calls]
    assert SYSTEM_EXTRACT in systems
    assert SYSTEM_ANALYZE not in systems
    assert SYSTEM_SUMMARY not in systems


# -- RAGSystem.check() integration on fakes ---------------------------------
def test_rag_system_check_shapes_response(fake_provider, index_dir, tmp_path):
    llm = FakeLLM(analyze_mode="ok")
    rag = RAGSystem(provider=fake_provider, llm=llm, index_dir=str(tmp_path / "ix"))
    rag._store.add_texts(
        ["Rule 5: min front setback 1.8m"],
        [{"source": "kbr.txt", "rule_id": "Rule 5"}],
    )
    result = rag.check(PLAN, top_k=1)

    assert isinstance(result["extracted_facts"], list)
    assert result["extracted_facts"]
    assert result["summary"] == SUMMARY_TEXT
    assert result["violations"] == ANALYZE_PAYLOAD["violations"]
    assert isinstance(result["retrieved_rules"], list)
    assert {
        "source",
        "excerpt",
        "score",
    } <= set(result["retrieved_rules"][0].keys())


def test_rag_system_check_extracts_facts_as_bullet_lines(
    fake_provider, index_dir, tmp_path
):
    llm = FakeLLM(analyze_mode="ok")
    rag = RAGSystem(provider=fake_provider, llm=llm, index_dir=str(tmp_path / "ix"))
    # Add a rule so we take the analyze path; bullets strip leading '- '.
    rag._store.add_texts(["r"], [{"source": "kbr.txt"}])
    result = rag.check(PLAN, top_k=1)
    # FACTS_TEXT is a "- key: value" bullet list; check() strips the dashes.
    assert "plot area: 300 sq.m" in result["extracted_facts"]
    assert all(not f.startswith("-") for f in result["extracted_facts"])
