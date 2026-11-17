"""End-to-end tests of the RAG features over HTTP.

Each test drives the real FastAPI app: the bundled sample rulebook is ingested
through ``POST /api/ingest`` (structure-aware chunking -> FAISS + BM25), then
checked, searched and questioned through the public endpoints. Only the two
network edges are faked - the embedding provider and the LLM - so everything in
between (chunking, indexing, multi-query retrieval, coverage grading, the
LangGraph pipeline, citation grounding, persistence, response shaping) runs for
real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.rag.prompts import SYSTEM_ANALYZE, SYSTEM_EXTRACT, SYSTEM_SUMMARY
from app.schemas import ComplianceResponse
from tests.conftest import FakeEmbeddingProvider, FakeLLM

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "tests" / "fixtures" / "kbr" / "sample_kbr_excerpt.txt"

PLAN = "Three floor residential building, 12 m tall, 1 m front setback, plot 240 sq.m."

FACTS = (
    "- plot area: 240 sq.m\n"
    "- built-up area: 410 sq.m\n"
    "- number of floors: 3\n"
    "- building height: 12 m\n"
    "- front setback: 1 m\n"
    "- parking provision: 1 car space\n"
    "- occupancy/usage type: residential (Group A1)"
)

FINDINGS = {
    "violations": [
        {
            "rule_reference": "5.3.1",
            "severity": "high",
            "description": "Front setback is below the minimum.",
            "plan_value": "1 m",
            "required_value": "3.0 m",
        },
        {
            "rule_reference": "Rule 99(2)",
            "severity": "medium",
            "description": "A rule the model made up.",
            "plan_value": "12 m",
            "required_value": "9.25 m",
        },
    ]
}


class ScriptedLLM(FakeLLM):
    """FakeLLM with a realistic fact sheet and scripted findings."""

    def complete(self, system: str, user: str) -> str:
        if system == SYSTEM_EXTRACT:
            self.calls.append({"system": system, "user": user})
            return FACTS
        if system == SYSTEM_ANALYZE:
            self.calls.append({"system": system, "user": user})
            return json.dumps(FINDINGS)
        return super().complete(system, user)


def _client_with_corpus(tmp_path, monkeypatch, corpus_text):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.rag.system import RAGSystem

    kbr_dir = tmp_path / "kbr"
    kbr_dir.mkdir()
    (kbr_dir / "sample_kbr_excerpt.txt").write_text(corpus_text, encoding="utf-8")
    monkeypatch.setattr(get_settings(), "kbr_data_dir", kbr_dir)

    llm = ScriptedLLM()
    rag = RAGSystem(
        provider=FakeEmbeddingProvider(), llm=llm, index_dir=str(tmp_path / "index")
    )
    client = TestClient(app)
    client.__enter__()
    app.state.rag = rag
    client.llm = llm  # type: ignore[attr-defined]
    return client


@pytest.fixture
def client(tmp_path, monkeypatch):
    c = _client_with_corpus(tmp_path, monkeypatch, SAMPLE.read_text(encoding="utf-8"))
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def ingested(client):
    resp = client.post("/api/ingest", json={"rebuild": True})
    assert resp.status_code == 200, resp.text
    return client


# ---------------------------------------------------------------------------
# ingest -> index
# ---------------------------------------------------------------------------
def test_ingest_builds_a_structured_index(client):
    assert client.get("/api/health").json()["index_size"] == 0

    body = client.post("/api/ingest", json={}).json()
    assert body["documents"] == 1
    assert body["chunks"] == body["index_size"] >= 6

    # Re-ingesting the same corpus adds nothing.
    again = client.post("/api/ingest", json={}).json()
    assert again["chunks"] == 0
    assert again["skipped"] == body["chunks"]
    assert again["index_size"] == body["index_size"]


def test_index_stats_describe_what_was_ingested(ingested):
    body = ingested.get("/api/kbr/index").json()
    assert body["index_size"] >= 6
    (doc,) = body["documents"]
    assert doc["source"] == "sample_kbr_excerpt.txt"
    assert doc["chunks"] == body["index_size"]
    assert doc["rules"] >= 6  # Rule 5, 7, 12, 16 and sections 5.3, 11.2
    assert doc["pages"] is None
    assert body["retrieval_strategy"] == "advanced"
    assert body["structured_chunking"] is True
    assert body["hybrid"] is True
    assert body["embedding_dim"] == 256


def test_health_reports_ready_and_the_retrieval_strategy(ingested):
    body = ingested.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["retrieval_strategy"] == "advanced"
    assert ingested.get("/api/health/ready").status_code == 200


# ---------------------------------------------------------------------------
# compliance check
# ---------------------------------------------------------------------------
def test_check_retrieves_one_governing_rule_per_topic(ingested):
    resp = ingested.post("/api/check", json={"plan_text": PLAN})
    assert resp.status_code == 200, resp.text
    body = ComplianceResponse(**resp.json())

    rule_ids = [r.rule_id for r in body.retrieved_rules]
    # Setbacks, FSI/height, parking, plot and occupancy each have their rule.
    assert {"5.3", "Rule 7", "11.2", "Rule 5", "Rule 12"} <= set(rule_ids)
    setbacks = next(r for r in body.retrieved_rules if r.rule_id == "5.3")
    assert setbacks.section.startswith("PART C SETBACKS")
    assert "Setbacks" in setbacks.topics
    assert "5.3.1 The minimum front setback" in setbacks.excerpt

    retrieval = body.retrieval
    assert retrieval.strategy == "advanced"
    assert [q.label for q in retrieval.queries][0] == "Full query"
    coverage = {c.topic: c for c in retrieval.coverage}
    assert set(coverage) == {
        "setbacks",
        "fsi",
        "height",
        "parking",
        "plot",
        "occupancy",
    }
    assert all(c.status == "covered" for c in coverage.values())
    # The rule chosen for the topic leads; rules that merely mention it follow.
    assert coverage["parking"].rule_ids[0] == "11.2"
    assert coverage["setbacks"].rule_ids[0] == "5.3"
    assert retrieval.gaps == []


def test_check_grounds_each_finding_against_the_retrieved_rules(ingested):
    body = ComplianceResponse(
        **ingested.post("/api/check", json={"plan_text": PLAN}).json()
    )

    # Findings come back exactly as the analyst wrote them...
    assert [v.rule_reference for v in body.violations] == ["5.3.1", "Rule 99(2)"]
    # ...and each is checked against what was retrieved.
    real, invented = body.grounding.items
    assert real.status == "grounded"
    assert real.value_supported is True
    cited = body.retrieved_rules[real.citations[0] - 1]
    assert cited.rule_id == "5.3"
    assert invented.status == "ungrounded"
    assert invented.citations == []
    assert (body.grounding.grounded, body.grounding.ungrounded) == (1, 1)
    assert body.grounding.score == 0.5


def test_ungrounded_citation_is_flagged_to_the_summary_writer(ingested):
    ingested.post("/api/check", json={"plan_text": PLAN})
    (summary_call,) = [c for c in ingested.llm.calls if c["system"] == SYSTEM_SUMMARY]
    assert "CITATION CHECK" in summary_call["user"]
    assert (
        "1 of 2 findings cite a rule that was not among the retrieved"
        in summary_call["user"]
    )


def test_analyst_prompt_labels_each_excerpt_with_its_place_in_the_rulebook(ingested):
    ingested.post("/api/check", json={"plan_text": PLAN})
    (analyze_call,) = [c for c in ingested.llm.calls if c["system"] == SYSTEM_ANALYZE]
    assert "(sample_kbr_excerpt.txt / 5.3 / PART C SETBACKS" in analyze_call["user"]
    assert "TOPICS WITH NO RULE RETRIEVED" not in analyze_call["user"]


def test_check_respects_top_k_and_reports_what_was_cut(ingested):
    resp = ingested.post("/api/check", json={"plan_text": PLAN, "top_k": 2})
    body = ComplianceResponse(**resp.json())
    assert len(body.retrieved_rules) == 2
    cut = [c for c in body.retrieval.coverage if c.status == "gap"]
    assert cut and all(c.reason == "truncated" for c in cut)


def test_check_is_persisted_and_readable_as_a_report(ingested):
    body = ingested.post("/api/check", json={"plan_text": PLAN}).json()
    report = ingested.get(f"/api/reports/{body['report_id']}").json()
    assert report["status"] == "fail"  # one high-severity finding
    assert len(report["violations"]) == 2
    assert {r["rule_id"] for r in report["retrieved_rules"]} >= {"5.3", "Rule 7"}


def test_upload_goes_through_the_same_pipeline(ingested):
    files = {"file": ("plan.txt", PLAN.encode("utf-8"), "text/plain")}
    body = ComplianceResponse(**ingested.post("/api/check/upload", files=files).json())
    assert body.retrieval.strategy == "advanced"
    assert body.grounding.total == 2


def test_identical_recheck_reuses_the_analysis(ingested):
    ingested.post("/api/check", json={"plan_text": PLAN})
    ingested.post("/api/check", json={"plan_text": PLAN})
    analyze_calls = [c for c in ingested.llm.calls if c["system"] == SYSTEM_ANALYZE]
    assert len(analyze_calls) == 1


def test_different_top_k_does_not_replay_another_prompts_analysis(ingested):
    # Same facts, different rule set shown to the analyst: must be re-analysed.
    ingested.post("/api/check", json={"plan_text": PLAN, "top_k": 8})
    ingested.post("/api/check", json={"plan_text": PLAN, "top_k": 2})
    analyze_calls = [c for c in ingested.llm.calls if c["system"] == SYSTEM_ANALYZE]
    assert len(analyze_calls) == 2


# ---------------------------------------------------------------------------
# a topic the rulebook does not cover
# ---------------------------------------------------------------------------
@pytest.fixture
def no_parking_client(tmp_path, monkeypatch):
    text = SAMPLE.read_text(encoding="utf-8")
    start = text.index("11.2 Parking")
    end = text.index("Rule 12  Occupancy classification")
    trimmed = text[:start] + text[end:]
    trimmed = trimmed.replace("PART D -- PARKING AND OCCUPANCY", "PART D -- OCCUPANCY")
    trimmed = trimmed.replace(
        "setback, parking and fire-safety", "setback and fire-safety"
    )
    assert "arking" not in trimmed
    c = _client_with_corpus(tmp_path, monkeypatch, trimmed)
    assert c.post("/api/ingest", json={"rebuild": True}).status_code == 200
    yield c
    c.__exit__(None, None, None)


def test_missing_topic_is_a_reported_gap_not_a_silent_omission(no_parking_client):
    client = no_parking_client
    body = ComplianceResponse(
        **client.post("/api/check", json={"plan_text": PLAN}).json()
    )

    parking = next(c for c in body.retrieval.coverage if c.topic == "parking")
    assert parking.status == "gap"
    assert parking.reason == "not_in_index"
    assert body.retrieval.gaps == ["Parking"]

    # The analyst is told not to invent a parking requirement...
    (analyze_call,) = [c for c in client.llm.calls if c["system"] == SYSTEM_ANALYZE]
    assert "TOPICS WITH NO RULE RETRIEVED: Parking" in analyze_call["user"]
    assert analyze_call["user"].rstrip().endswith("Return the JSON analysis now.")
    # ...and the summary writer is told it was not assessed.
    (summary_call,) = [c for c in client.llm.calls if c["system"] == SYSTEM_SUMMARY]
    assert "TOPICS WITH NO RULE RETRIEVED" in summary_call["user"]


# ---------------------------------------------------------------------------
# rulebook search and Q&A
# ---------------------------------------------------------------------------
def test_search_explains_each_hit(ingested):
    rows = ingested.get(
        "/api/rules/search", params={"q": "car parking space", "limit": 3}
    ).json()
    top = rows[0]
    assert top["rule_id"] == "11.2"
    assert top["section"] == "PART D PARKING AND OCCUPANCY > 11.2 Parking"
    assert {"car", "parking", "space"} <= set(top["matched_terms"])
    assert 0.0 <= top["lexical_score"] <= 1.0
    assert -1.0 <= top["dense_score"] <= 1.0
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("mode", ["hybrid", "dense", "lexical", "advanced"])
def test_every_search_mode_finds_the_parking_rule(ingested, mode):
    rows = ingested.get(
        "/api/rules/search", params={"q": "car parking space", "mode": mode, "limit": 3}
    ).json()
    assert rows[0]["rule_id"] == "11.2", mode


def test_advanced_search_bridges_plan_wording_to_rule_wording(ingested):
    rows = ingested.get(
        "/api/rules/search",
        params={"q": "What FAR is allowed?", "mode": "advanced", "limit": 2},
    ).json()
    # "FAR" appears nowhere in the sample rulebook; it says "FSI".
    assert rows[0]["rule_id"] == "Rule 7"
    assert rows[0]["retrieved_by"] == "FSI / FAR"


def test_lexical_search_returns_nothing_for_unknown_words(ingested):
    rows = ingested.get(
        "/api/rules/search", params={"q": "xylophone", "mode": "lexical"}
    ).json()
    assert rows == []


def test_search_rejects_an_unknown_mode(ingested):
    resp = ingested.get("/api/rules/search", params={"q": "parking", "mode": "psychic"})
    assert resp.status_code == 400
    assert "hybrid, dense, lexical, advanced" in resp.json()["detail"]


def test_search_with_blank_query_or_empty_index(client, ingested):
    assert ingested.get("/api/rules/search", params={"q": "   "}).json() == []


def test_search_on_an_empty_index(client):
    assert client.get("/api/rules/search", params={"q": "parking"}).json() == []


def test_search_limit_is_clamped(ingested):
    rows = ingested.get(
        "/api/rules/search", params={"q": "building", "limit": 999}
    ).json()
    assert 1 <= len(rows) <= 50
    assert (
        len(
            ingested.get(
                "/api/rules/search", params={"q": "building", "limit": 0}
            ).json()
        )
        == 1
    )


def test_ask_answers_from_the_ingested_rulebook(ingested):
    ingested.llm.qa_mode = "The minimum front setback is 3.0 metres [1]."
    body = ingested.post(
        "/api/rules/ask", json={"question": "What is the minimum front setback?"}
    ).json()
    assert body["abstained"] is False
    assert body["confidence"] == "high"
    cited = [c for c in body["citations"] if c["cited"]]
    assert [c["rule_id"] for c in cited] == ["5.3"]
    assert "3.0 metres" in cited[0]["excerpt"]


def test_ask_before_ingest_abstains(client):
    body = client.post(
        "/api/rules/ask", json={"question": "What is the minimum front setback?"}
    ).json()
    assert body["abstained"] is True
    assert "index is empty" in body["answer"]
    assert client.llm.calls == []


# ---------------------------------------------------------------------------
# configuration switches
# ---------------------------------------------------------------------------
def test_simple_strategy_can_be_selected_by_setting(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "retrieval_strategy", "simple")
    c = _client_with_corpus(tmp_path, monkeypatch, SAMPLE.read_text(encoding="utf-8"))
    try:
        c.post("/api/ingest", json={"rebuild": True})
        body = c.post("/api/check", json={"plan_text": PLAN}).json()
        assert body["retrieval"]["strategy"] == "simple"
        assert c.get("/api/health").json()["retrieval_strategy"] == "simple"
        # Coverage is still graded, whatever retrieved the rules.
        assert {c_["topic"] for c_ in body["retrieval"]["coverage"]} >= {"setbacks"}
    finally:
        c.__exit__(None, None, None)


def test_flat_chunking_can_be_selected_by_setting(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "structured_chunking", False)
    c = _client_with_corpus(tmp_path, monkeypatch, SAMPLE.read_text(encoding="utf-8"))
    try:
        c.post("/api/ingest", json={"rebuild": True})
        stats = c.get("/api/kbr/index").json()
        assert stats["structured_chunking"] is False
        rows = c.get("/api/rules/search", params={"q": "front setback"}).json()
        assert rows and all(r["section"] is None for r in rows)
    finally:
        c.__exit__(None, None, None)
