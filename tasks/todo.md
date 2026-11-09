# Task List: OpenAI-Compatible Dual LLM Double-Checking & Verification Engine

## Task 1: Implement Configuration Settings and OpenAI-Compatible Client

**Description:** Add configuration variables to `app/config.py` for configuring an independent OpenAI-compatible verification provider (base URL, API key, model, temperature, timeout, retries, strict mode). Implement `OpenAICompatibleClient` and factory function `get_verifier_client()` in `app/rag/llm.py` using the official `openai` Python SDK with automated JSON mode fallback and retry resilience. Wire `OpenAICompatibleClient` into `get_llm_client()` so both the primary LLM provider and the secondary verifier can run against any OpenAI-compatible API.

**Acceptance criteria:**
- [x] `app/config.py` defines `verifier_enabled`, `verifier_provider`, `verifier_base_url`, `verifier_api_key`, `verifier_model`, `verifier_temperature`, `verifier_timeout`, `verifier_max_retries`, and `verifier_strict_mode` with sensible defaults.
- [x] `OpenAICompatibleClient` connects to any standard OpenAI-compatible API endpoint (e.g. OpenAI, Groq, Together, Ollama, vLLM, DeepSeek, local NIM).
- [x] `get_llm_client()` supports `provider in ("openai", "openai_compatible")` so both primary and secondary LLMs can be configured with OpenAI-compatible APIs.
- [x] If an endpoint rejects `response_format={"type": "json_object"}`, `OpenAICompatibleClient.complete()` automatically falls back to standard completions without crashing.
- [x] `get_verifier_client()` returns `None` cleanly when `VERIFIER_ENABLED` is `False`.

**Verification:**
- [x] Tests pass: `.venv/bin/pytest tests/test_verifier_llm.py`
- [x] Build succeeds: `.venv/bin/python -c "from app.rag.llm import get_verifier_client; print(get_verifier_client())"`
- [x] Manual check: Verify client instantiation with custom mock `base_url` and mock API key.

**Dependencies:** None

**Files likely touched:**
- `app/config.py`
- `app/rag/llm.py`
- `tests/test_verifier_llm.py`

**Estimated scope:** Small (2 codebase files, 1 test file)

---

## Task 2: Create Verification Prompts and Response Schemas

**Description:** Define system and user prompt templates in `app/rag/prompts.py` instructing the secondary LLM to rigorously audit the primary model's findings for hallucinations, false positives (including Rule 27 small-plot concessions), missed violations, and value mismatches. Extend `app/schemas.py` with `DiscrepancyItem`, `VerificationResult`, and updated `ComplianceResponse` and `HealthResponse` models.

**Acceptance criteria:**
- [x] `SYSTEM_DOUBLE_CHECK` and `build_verify_user(facts, rules, primary_violations)` in `app/rag/prompts.py` enforce strict JSON output with status, confidence score, cross-check notes, discrepancies, and final vetted violations.
- [x] `DiscrepancyItem` and `VerificationResult` models are defined in `app/schemas.py` with full Pydantic v2 validation.
- [x] `ComplianceResponse` includes optional `verification: Optional[VerificationResult] = None` while preserving complete backward compatibility with existing clients.
- [x] `HealthResponse` includes verifier status fields (`verifier_enabled`, `verifier_provider`, `verifier_model`, `verifier_ready`).

**Verification:**
- [x] Tests pass: `.venv/bin/pytest tests/test_verification_schemas.py`
- [x] Build succeeds: `.venv/bin/python -c "from app.schemas import ComplianceResponse, VerificationResult; print('Schemas valid')"`
- [x] Manual check: Verify that a sample JSON verification payload validates against `VerificationResult`.

**Dependencies:** Task 1

**Files likely touched:**
- `app/rag/prompts.py`
- `app/schemas.py`
- `tests/test_verification_schemas.py`

**Estimated scope:** Small (2 codebase files, 1 test file)

---

## Checkpoint: Foundation Verification
- [x] Unit tests for `OpenAICompatibleClient` pass
- [x] Verification prompt formatting and schema serialization tests pass
- [x] Configuration loads correctly with and without environment overrides
- [x] No regression in existing tests (`.venv/bin/pytest tests/test_gemini_llm.py tests/test_nim_llm.py`)

---

## Task 3: Integrate Verification Node into V1 LangGraph State Machine

**Description:** Add `primary_violations` and `verification` to `ComplianceState` in `app/rag/graph.py`. Create `verify_analysis` (sync) and `averify_analysis` (async) nodes placed between `analyze` and `summarize`. Wire `verifier_llm` through `Context` and `RAGSystem` (`app/rag/system.py`). When the verifier is disabled or encounters an error, gracefully fallback to primary violations without breaking the workflow.

**Acceptance criteria:**
- [ ] `verify_analysis` node executes between `analyze` and `summarize` in both synchronous and asynchronous compliance graphs.
- [ ] If `verifier_llm` is not configured, `verify_analysis` returns `verification={"status": "skipped"}` with negligible overhead.
- [ ] Validated verifier outputs update `state["violations"]` with vetted violations, while retaining original `state["primary_violations"]` and populating `state["verification"]`.
- [ ] If the verifier call fails (e.g., timeout or network error), the node catches the exception, logs a warning, retains primary violations, and sets `verification={"status": "error"}`.
- [ ] `summarize` node prompt incorporates verification reconciliation context so the executive summary reflects vetted results.

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/test_double_check.py`
- [ ] Build succeeds: `.venv/bin/python -c "from app.rag.graph import build_compliance_graph, Context; g = build_compliance_graph(Context(llm=None, store=None)); print('Graph compiled')"`
- [ ] Manual check: Run a simulated compliance check with a mock verifier that flags a false positive; verify that the false positive is removed from final violations.

**Dependencies:** Task 1, Task 2

**Files likely touched:**
- `app/rag/graph.py`
- `app/rag/system.py`
- `tests/test_double_check.py`

**Estimated scope:** Medium (2 codebase files, 1 test file)

---

## Task 4: Report Persistence, API Contract & Diagnostics Integration

**Description:** Update report persistence in `app/routes/rag.py` and `app/services/report_model.py` so the `verification` audit block is stored in the SQLite database and returned in `GET /api/reports` and `GET /api/reports/{id}`. Update `GET /api/health` to report secondary verifier availability and diagnostic status.

**Acceptance criteria:**
- [ ] `_persist_report` stores `verification` dictionary in SQLite `report` table without schema breakage (using JSON column or serialized text).
- [ ] `GET /api/reports` and `GET /api/reports/{id}` return the verification audit object in the report detail payload.
- [ ] `GET /api/health` reports `verifier_enabled`, `verifier_provider`, `verifier_model`, and `verifier_ready`.
- [ ] Existing report generation endpoints continue to function for historical reports created before the verifier was added.

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/test_reports_api.py tests/test_reports_persist.py tests/test_api.py`
- [ ] Build succeeds: `.venv/bin/python -c "from app.main import app; print('App initialized')"`
- [ ] Manual check: Trigger a check with verification enabled, query `GET /api/reports/{id}`, and verify the presence of `verification` field.

**Dependencies:** Task 3

**Files likely touched:**
- `app/routes/rag.py`
- `app/services/report_model.py`
- `app/schemas_reports.py`
- `tests/test_reports_api.py`

**Estimated scope:** Small (3 codebase files, 1 test file)

---

## Checkpoint: V1 Compliance Pipeline & Persistence
- [ ] `POST /api/check` successfully verifies candidate violations when secondary LLM is enabled
- [ ] Passthrough verified when verifier is disabled
- [ ] Full persistence and retrieval of verification audit logs verified in SQLite
- [ ] All existing V1 tests pass without regression

---

## Task 5: Integrate Statutory Verifier Node into V2 Multi-Agent Graph

**Description:** Extend the V2 Multi-Agent LangGraph workflow (`app/rag/multi_agent_graph.py`) by adding an LLM-powered statutory cross-checker agent node (`node_statutory_cross_checker`) positioned between `critic` and `remediation`. This agent audits the symbolic evaluation and concession findings against drawing facts, detecting unhandled statutory nuances before generating remediation notes.

**Acceptance criteria:**
- [ ] `node_statutory_cross_checker` node added to V2 Multi-Agent graph between `critic` and `remediation`.
- [ ] If `verifier_llm` is not configured, the node seamlessly passes through the state without delaying execution.
- [ ] When active, cross-checks active violations and exonerations against plan facts and statutory notes, enriching the state with verification telemetry and discrepancies.
- [ ] V2 check responses (`POST /api/v2/check/pdf`) include the `verification` audit block in the response payload and report record.

**Verification:**
- [ ] Tests pass: `.venv/bin/pytest tests/test_v2_double_check.py tests/test_symbolic_engine.py`
- [ ] Build succeeds: `.venv/bin/python -c "from app.rag.multi_agent_graph import get_multi_agent_graph; g = get_multi_agent_graph(); print('V2 Graph compiled')"`
- [ ] Manual check: Run a V2 blueprint check and confirm verification metadata in the returned JSON.

**Dependencies:** Task 3, Task 4

**Files likely touched:**
- `app/rag/multi_agent_graph.py`
- `app/routes/rag_v2.py`
- `tests/test_v2_double_check.py`

**Estimated scope:** Medium (2 codebase files, 1 test file)

---

## Task 6: Implement Frontend Dual-LLM Audit Badges & Discrepancy UI

**Description:** Update the frontend React application (`frontend/src/pages/Results.jsx` and `frontend/src/pages/VisualWorkbench.jsx`) to display a dedicated "Dual-LLM Verification" status card/badge. Provide an expandable audit drawer/accordion showing verified status, verifier model, confidence score, cross-check notes, and a side-by-side comparison of any discrepancies resolved between the primary and secondary models.

**Acceptance criteria:**
- [ ] `Results.jsx` displays a verification badge:
  - Green "Double-Checked & Confirmed by [Model]" when status is `confirmed`.
  - Amber "Discrepancies Resolved ([N] adjusted)" when discrepancies are flagged.
  - Informative badge when verifier is inactive or in error fallback.
- [ ] An expandable drawer/card renders `cross_check_notes` and itemized `discrepancies` (rule reference, primary finding vs verifier finding, discrepancy type).
- [ ] `VisualWorkbench.jsx` reflects the verification audit status for V2 blueprint checks.
- [ ] Clean visual design matching existing Tailwind CSS color schemes and dark/light modes.

**Verification:**
- [ ] Tests pass: `cd frontend && npm test -- --run`
- [ ] Build succeeds: `cd frontend && npm run build`
- [ ] Manual check: Inspect the Results page with mock verification data to ensure smooth rendering and responsive UI.

**Dependencies:** Task 4, Task 5

**Files likely touched:**
- `frontend/src/pages/Results.jsx`
- `frontend/src/pages/VisualWorkbench.jsx`
- `frontend/src/components/VerificationAuditBadge.jsx` (new component)

**Estimated scope:** Medium (3 frontend files)

---

## Checkpoint: Final System Verification
- [ ] All backend test suites pass (`.venv/bin/pytest tests/` - all 260+ tests passing)
- [ ] Frontend builds cleanly with zero errors (`npm run build`)
- [ ] V1 and V2 verification flows tested with mock OpenAI-compatible endpoints
- [ ] Documentation updated with environment variable guidance (`.env.example`)
