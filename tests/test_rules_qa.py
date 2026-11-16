"""Tests for rulebook question answering (``app.rag.qa``) and its endpoint
``POST /api/rules/ask``: answers must be built from retrieved excerpts, cite
them verifiably, and abstain rather than guess. Fully offline (fakes)."""

from __future__ import annotations

import pytest

from app.rag.qa import (
    ABSTAIN_EMPTY_INDEX,
    ABSTAIN_NO_EVIDENCE,
    SYSTEM_QA,
    answer_question,
    validate_question,
)
from app.rag.retrieval import RuleRetriever
from app.rag.vectorstore import RuleVectorStore
from tests.conftest import (
    QA_ANSWER_TEXT,
    FakeEmbeddingProvider,
    FakeLLM,
    build_rag_system,
)

QUESTION = "What is the minimum front setback?"


@pytest.fixture
def retriever(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    store.add_texts(
        [
            "The minimum front setback from the plot boundary shall be 3.0 metres.",
            "One car parking space shall be provided for every dwelling unit.",
        ],
        [
            {"source": "kbr.txt", "rule_id": "5.3", "section": "PART C > 5.3 Setbacks"},
            {"source": "kbr.txt", "rule_id": "Rule 29", "page": 58},
        ],
    )
    return RuleRetriever(store)


def _qa_calls(llm):
    return [c for c in llm.calls if c["system"] == SYSTEM_QA]


# -- question validation -------------------------------------------------------
def test_question_is_trimmed_and_whitespace_collapsed():
    assert validate_question("  what   is\nFSI? ") == "what is FSI?"


@pytest.mark.parametrize("bad", ["", "  ", "a", None])
def test_too_short_question_is_rejected(bad):
    with pytest.raises(ValueError, match="at least a few words"):
        validate_question(bad)


def test_overlong_question_is_rejected():
    with pytest.raises(ValueError, match="too long"):
        validate_question("why " * 400)


# -- answering -------------------------------------------------------------------
def test_cited_answer_is_returned_with_its_evidence(retriever):
    llm = FakeLLM(qa_mode="ok")
    result = answer_question(llm, retriever, QUESTION, top_k=2)

    assert result["answer"] == QA_ANSWER_TEXT
    assert result["abstained"] is False
    assert result["confidence"] == "high"
    first, second = result["citations"]
    assert first["index"] == 1 and first["cited"] is True
    assert first["rule_id"] == "5.3"
    assert first["section"] == "PART C > 5.3 Setbacks"
    assert second["cited"] is False
    assert second["page"] == 58


def test_prompt_contains_the_question_and_numbered_excerpts(retriever):
    llm = FakeLLM(qa_mode="ok")
    answer_question(llm, retriever, QUESTION, top_k=2)
    (call,) = _qa_calls(llm)
    assert QUESTION in call["user"]
    assert "[1] (kbr.txt / 5.3 / PART C > 5.3 Setbacks)" in call["user"]
    assert "[2] (kbr.txt / Rule 29 / p. 58)" in call["user"]


def test_model_saying_not_found_becomes_an_abstention(retriever):
    result = answer_question(FakeLLM(qa_mode="not_found"), retriever, QUESTION)
    assert result["abstained"] is True
    assert result["confidence"] == "none"
    assert result["answer"] == ABSTAIN_NO_EVIDENCE
    # The excerpts that were considered are still shown, none marked cited.
    assert result["citations"] and not any(c["cited"] for c in result["citations"])


@pytest.mark.parametrize(
    "raw", ["not_found", "Not Found.", "NOT_FOUND - no excerpt covers it"]
)
def test_not_found_sentinel_is_recognised_loosely(retriever, raw):
    assert answer_question(FakeLLM(qa_mode=raw), retriever, QUESTION)["abstained"]


def test_empty_model_output_is_an_abstention(retriever):
    assert answer_question(FakeLLM(qa_mode=""), retriever, QUESTION)["abstained"]


def test_answer_without_any_citation_is_low_confidence(retriever):
    result = answer_question(FakeLLM(qa_mode="uncited"), retriever, QUESTION)
    assert result["abstained"] is False
    assert result["confidence"] == "low"
    assert not any(c["cited"] for c in result["citations"])


def test_citation_of_a_nonexistent_excerpt_is_stripped(retriever):
    result = answer_question(FakeLLM(qa_mode="bad_citation"), retriever, QUESTION)
    assert "[9]" not in result["answer"]
    assert result["answer"] == "The minimum front setback is three metres."
    assert result["confidence"] == "low"  # nothing valid left to stand on


def test_valid_citations_are_kept_alongside_stripped_ones(retriever):
    llm = FakeLLM(qa_mode="Setback is 3.0 metres [1][7]. Parking is one space [2].")
    result = answer_question(llm, retriever, QUESTION, top_k=2)
    assert result["answer"] == "Setback is 3.0 metres [1]. Parking is one space [2]."
    assert [c["cited"] for c in result["citations"]] == [True, True]


def test_cited_excerpt_in_different_words_is_medium_confidence(retriever):
    # The answer cites only the parking excerpt, which shares none of the
    # question's terms ("front", "setback").
    llm = FakeLLM(qa_mode="See the cited rule [2].")
    result = answer_question(llm, retriever, QUESTION, top_k=2)
    assert result["confidence"] == "medium"


def test_empty_index_abstains_without_calling_the_model(index_dir):
    store = RuleVectorStore(FakeEmbeddingProvider(), index_dir)
    store.load_or_create()
    llm = FakeLLM()
    result = answer_question(llm, RuleRetriever(store), QUESTION, index_size=0)
    assert result["abstained"] is True
    assert result["answer"] == ABSTAIN_EMPTY_INDEX
    assert result["citations"] == []
    assert llm.calls == []  # no excerpts -> no paid call, no chance to guess


def test_retrieval_trace_is_included(retriever):
    result = answer_question(FakeLLM(), retriever, QUESTION)
    assert result["retrieval"]["strategy"] == "advanced"
    assert [q["topic"] for q in result["retrieval"]["queries"]] == [None, "setbacks"]


# -- RAGSystem.ask ---------------------------------------------------------------
def test_rag_system_ask(tmp_path):
    rag = build_rag_system(FakeEmbeddingProvider(), FakeLLM(), tmp_path / "ix")
    result = rag.ask("What is the minimum front setback?")
    assert result["abstained"] is False
    assert result["citations"][0]["rule_id"] == "Rule 5"


def test_rag_system_ask_requires_llm_and_embeddings(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.rag.system import RAGSystem

    for key in ("OPENAI_API_KEY", "NVIDIA_API_KEY", "NIM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    try:
        rag = RAGSystem(provider=None, llm=FakeLLM(), index_dir=str(tmp_path / "ix"))
        with pytest.raises(RuntimeError, match="missing"):
            rag.ask(QUESTION)
    finally:
        get_settings.cache_clear()


# -- HTTP ------------------------------------------------------------------------
def test_ask_endpoint_returns_a_cited_answer(app_client):
    resp = app_client.post("/api/rules/ask", json={"question": QUESTION})
    assert resp.status_code == 200
    body = resp.json()
    assert body["question"] == QUESTION
    assert body["answer"] == QA_ANSWER_TEXT
    assert body["abstained"] is False
    assert body["confidence"] in {"high", "medium"}
    assert body["citations"][0]["cited"] is True
    assert body["citations"][0]["rule_id"] == "Rule 5"
    assert body["retrieval"]["strategy"] == "advanced"


def test_ask_endpoint_abstains_when_rules_do_not_answer(app_client):
    app_client.fake_llm.qa_mode = "not_found"
    body = app_client.post("/api/rules/ask", json={"question": QUESTION}).json()
    assert body["abstained"] is True
    assert body["confidence"] == "none"


def test_ask_endpoint_respects_top_k(app_client):
    resp = app_client.post("/api/rules/ask", json={"question": QUESTION, "top_k": 1})
    assert len(resp.json()["citations"]) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": ""},
        {"question": "ab"},
        {"question": "x" * 601},
        {"question": QUESTION, "top_k": 0},
    ],
)
def test_ask_endpoint_validates_the_payload(app_client, payload):
    assert app_client.post("/api/rules/ask", json=payload).status_code == 422


def test_ask_endpoint_rejects_a_blank_question(app_client):
    resp = app_client.post("/api/rules/ask", json={"question": "     "})
    assert resp.status_code == 400
    assert "few words" in resp.json()["detail"]


def test_ask_endpoint_is_503_when_the_llm_is_not_configured(app_client):
    rag = app_client.app.state.rag
    rag._graph = rag._agraph = None
    rag.llm_ready = False
    resp = app_client.post("/api/rules/ask", json={"question": QUESTION})
    assert resp.status_code == 503
    assert "llm" in resp.json()["detail"]


def test_rulebook_routes_require_auth_when_auth_is_on(app_client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    assert (
        app_client.post("/api/rules/ask", json={"question": QUESTION}).status_code
        == 401
    )
    assert app_client.get("/api/rules/search?q=setback").status_code == 401
    assert app_client.get("/api/kbr/index").status_code == 401


def test_rulebook_routes_are_rate_limited(app_client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 2)
    statuses = [
        app_client.post("/api/rules/ask", json={"question": QUESTION}).status_code
        for _ in range(3)
    ]
    assert statuses == [200, 200, 429]
