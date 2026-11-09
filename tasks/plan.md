# Implementation Plan: OpenAI-Compatible Dual LLM Double-Checking & Verification Engine

## Overview

This implementation plan adds a secondary LLM verification engine to ChattamAI to double-check compliance findings produced by the primary LLM provider. Both the primary and secondary LLM providers are configured via OpenAI-compatible APIs (supporting official OpenAI, Groq, Together AI, Ollama, vLLM, DeepSeek, and NVIDIA NIM endpoints). The secondary verifier performs an adversarial cross-examination across both compliance pipelines—V1 Semantic RAG (`/api/check`) and V2 Multi-Agent Architectural Blueprint compliance (`/api/v2/check/pdf`)—detecting hallucinated statutory rules, eliminating false positives (such as small-plot concessions under Chapter VI Rule 27), surfacing missed violations (false negatives), and verifying numerical thresholds. The resulting audit trail is persisted in the database and rendered in the frontend UI.

---

## Architecture Decisions

- **ADR-01: Provider-Agnostic `OpenAICompatibleClient` for Primary & Secondary LLMs in `app/rag/llm.py`:**
  Implement a generalized `OpenAICompatibleClient` wrapper using the official `openai` Python SDK. It accepts standard parameters (`base_url`, `api_key`, `model`, `temperature`, `timeout`, `max_retries`, `max_tokens`) and handles endpoint discrepancies (such as JSON mode fallback when an endpoint rejects `response_format={"type": "json_object"}`). Wire `OpenAICompatibleClient` into `get_llm_client()` (for primary providers: `openai`, `openai_compatible`) as well as `get_verifier_client()` (for secondary double-checker). This enables both the first provider and the second provider to connect to any OpenAI-compatible endpoint (OpenAI, Groq, Together, Ollama, vLLM, DeepSeek, or local/remote NVIDIA NIM instances).

- **ADR-02: Non-Breaking Feature Flagging & Safe Defaults:**
  Control the secondary verifier via `VERIFIER_ENABLED` (boolean, default: `False`) and dedicated `VERIFIER_*` environment variables in `app/config.py`. When disabled or unconfigured, the verification node operates as a zero-overhead passthrough (`status="skipped"`), ensuring that all 260+ existing tests and deployment environments function without requiring secondary API credentials.

- **ADR-03: LangGraph State Machine Seams for V1 and V2:**
  - In the V1 Semantic RAG workflow (`app/rag/graph.py`), place the `verify_analysis` node between `analyze` and `summarize`. The verifier cross-examines the primary model's candidate violations against the extracted facts and retrieved KBR rule chunks, updating the state with `primary_violations`, `violations` (the vetted set), and a structured `verification` audit object.
  - In the V2 Multi-Agent pipeline (`app/rag/multi_agent_graph.py`), introduce an LLM statutory cross-checker agent (`node_statutory_cross_checker`) positioned between `critic` and `remediation`, ensuring that deterministic evaluations and statutory concession critiques are audited against drawing text and legal exceptions.

- **ADR-04: Structured Audit Schema & Persistence Contract:**
  Define `VerificationResult` and `DiscrepancyItem` in `app/schemas.py`. Discrepancies classify issues into four explicit categories: `hallucination`, `false_positive`, `missed_violation`, and `value_mismatch`. Persist the verification payload in the SQLite `report` table so verification audit histories are retrievable via `/api/reports` and visible on the frontend.

- **ADR-05: Non-Blocking Graceful Degradation:**
  If the secondary verifier experiences a network timeout, rate limit, or invalid response, the workflow catches the exception, preserves the primary LLM's findings, logs an informative warning, and sets `verification.status="error"` rather than failing the user's compliance request.

---

## Task List

### Phase 1: Core Provider & Verification Foundation
- [ ] Task 1: Implement Configuration Settings and `OpenAICompatibleClient`
- [ ] Task 2: Create Verification Prompts and Response Schemas

### Checkpoint: Foundation
- [ ] Unit tests for `OpenAICompatibleClient` and config parsing pass cleanly.
- [ ] Pydantic validation for `VerificationResult` and `DiscrepancyItem` verified.

### Phase 2: V1 Semantic RAG Pipeline Integration
- [ ] Task 3: Integrate Verification Node into V1 LangGraph State Machine
- [ ] Task 4: Report Persistence, API Contract & Diagnostics Integration

### Checkpoint: V1 Compliance Pipeline
- [ ] `POST /api/check` successfully cross-examines findings when verifier is enabled.
- [ ] When verifier is disabled, pipeline executes zero-overhead passthrough.
- [ ] Audit trail persists to SQLite and shows in `GET /api/reports`.

### Phase 3: V2 Multi-Agent Pipeline & Frontend Experience
- [ ] Task 5: Integrate Statutory Verifier Node into V2 Multi-Agent Graph
- [ ] Task 6: Implement Frontend Dual-LLM Audit Badges & Discrepancy UI

### Checkpoint: Complete Verification
- [ ] All backend test suites pass (`pytest tests/`) with zero regressions.
- [ ] Frontend builds cleanly (`npm run build`) and test suites pass.
- [ ] Dual-LLM verification workflow verified end-to-end.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **Secondary LLM Latency & Timeouts** | Medium | Implement configurable timeout (`VERIFIER_TIMEOUT`, default 45s), low temperature (0.0), and non-blocking fallback that retains primary findings if the verifier times out. |
| **Incompatible Endpoint Parameters (e.g. `response_format`)** | High | Implement automatic retry loop in `OpenAICompatibleClient` that strips `response_format={"type": "json_object"}` if the upstream OpenAI-compatible proxy rejects it. |
| **Verifier Hallucinations / Over-Eager Pruning** | High | Provide a strict system prompt (`SYSTEM_DOUBLE_CHECK`) requiring factual citations; introduce `VERIFIER_STRICT_MODE` flag; preserve `primary_violations` in the response so engineers can view both findings. |
| **Breaking Existing Test Fixtures** | High | Default `VERIFIER_ENABLED=False` and `verifier_llm=None` in `RAGSystem`. Inject mock verifier clients in dedicated test suites using standard pytest fixtures. |

---

## Open Questions

- None. Both V1 and V2 compliance pipeline integration and OpenAI-compatible provider abstraction have been aligned with requirements.
