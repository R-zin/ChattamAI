# Task List: Nemotron-VL Blueprint Parsing & Audit Remediation

## Task 1: Enforce Upload Size Caps, Header Sanitization, and Rate Limiting on V2 Routes

**Description:** Secure `/api/v2/check/pdf` and `/api/v2/check/pdf/export-report` against resource exhaustion and denial-of-service by applying a 25MB upload limit, bounded file reads, filename sanitization on `Content-Disposition`, and including `/api/v2` in the IP rate limiting middleware.

**Acceptance criteria:**
- [ ] Uploads exceeding 25MB to `/api/v2/check/pdf` or `/api/v2/check/pdf/export-report` immediately return HTTP 413.
- [ ] `file.read()` reads at most `MAX_UPLOAD_SIZE + 1` bytes rather than unbounded streams into memory.
- [ ] `Content-Disposition` filename stem in the export endpoint is sanitized against CRLF (`\r\n`) and quotes.
- [ ] `_SENSITIVE_PREFIXES` in `app/main.py` includes `"/api/v2"`.

**Verification:**
- [ ] Tests pass: `pytest tests/test_security_audit_fixes.py tests/test_symbolic_engine.py`
- [ ] Manual check: Uploading a mock file >25MB returns HTTP 413.

**Dependencies:** None

**Files likely touched:**
- `app/routes/rag_v2.py`
- `app/main.py`
- `tests/test_symbolic_engine.py`

**Estimated scope:** Small (2 files)

---

## Task 2: Implement Authentication Gating and Persistent Report Storage for V2 Runs

**Description:** Add `require_auth` dependencies to V2 endpoints so they respect `AUTH_REQUIRED=True`, and integrate report persistence so checks run via V2 write to the SQLite `report` table and show up in `/reports` and `/activity`.

**Acceptance criteria:**
- [ ] `/api/v2/check/pdf`, `/api/v2/evaluate`, and `/api/v2/reports/ksmart` respect `get_settings().auth_required` via `Depends(require_auth)`.
- [ ] V2 check runs call `_persist_report()` with status, violations, and facts.
- [ ] Persisted V2 reports can be retrieved via `GET /api/reports`.

**Verification:**
- [ ] Tests pass: `pytest tests/test_reports_api.py tests/test_symbolic_engine.py`
- [ ] Manual check: Run a V2 check with auth enabled and verify it appears in `GET /api/reports`.

**Dependencies:** Task 1

**Files likely touched:**
- `app/routes/rag_v2.py`
- `app/routes/rag.py`
- `tests/test_symbolic_engine.py`

**Estimated scope:** Small (2-3 files)

---

## Checkpoint: Security & Gateways
- [ ] All tests pass
- [ ] Upload size capped at 25MB
- [ ] V2 endpoints guarded by auth and rate limiter
- [ ] Reports persist to SQLite

---

## Task 3: Eliminate Silent Dummy Fallbacks in PDF Normalizer & Fix Regex Defects

**Description:** Remove all hardcoded default fallbacks (`plot_area = 200.0`, `height = 7.5`, etc.) from `app/pdf_intel/normalizer.py`. If mandatory parameters cannot be extracted, raise an explicit validation error. Fix the percentage unit capture bug in `area_statement_parser.py` and enforce word boundaries in `validation.py`.

**Acceptance criteria:**
- [ ] `build_plan_facts_from_pdf` requires mandatory parameters (`plot_area_sqm`, `ground_coverage_sqm`, `front_setback_m`, etc.) and raises `ValueError` if missing without user overrides.
- [ ] `PATTERNS["ground_coverage_sqm"]` does not parse `"65%"` as `65.0` square metres.
- [ ] `app/rag/validation.py` uses word boundary checks (`\b`) so terms like "shed" and "cent" do not match words like "wished" or "incentive".

**Verification:**
- [ ] Tests pass: `pytest tests/test_pdf_intel.py tests/test_plan_validation.py`
- [ ] Unit test confirms an unparseable PDF raises `ValueError` instead of returning a dummy 200m² plan.

**Dependencies:** None

**Files likely touched:**
- `app/pdf_intel/normalizer.py`
- `app/pdf_intel/area_statement_parser.py`
- `app/rag/validation.py`
- `tests/test_pdf_intel.py`

**Estimated scope:** Medium (4 files)

---

## Task 4: Fix Concession Rule Consistency & Report Formatting

**Description:** Align concession checking in `statutory_critic.py` with Rule 27(3) so that Side Yard 1 ($\ge 0.9\text{m}$) is not falsely exonerated by a loose 0.6m check. Fix text truncation in `pdf_report_v2.py` to wrap remediation actions properly.

**Acceptance criteria:**
- [ ] `critique_violations` in `statutory_critic.py` distinguishes between Side Setback 1 ($\ge 0.9\text{m}$) and Side Setback 2 ($\ge 0.6\text{m}$) for small plots.
- [ ] Concession evaluation relies on canonical evaluator values without conflicting thresholds.
- [ ] `generate_compliance_pdf_report_v2` wraps action text across lines without cutting off words at 95 characters.

**Verification:**
- [ ] Tests pass: `pytest tests/test_symbolic_engine.py tests/test_pdf_report_v2.py`
- [ ] Visual verification: Generated PDF report contains complete multi-line remediation instructions.

**Dependencies:** Task 3

**Files likely touched:**
- `app/rag/agents/statutory_critic.py`
- `app/services/pdf_report_v2.py`
- `tests/test_symbolic_engine.py`

**Estimated scope:** Small (2-3 files)

---

## Checkpoint: Correctness & Mathematical Integrity
- [ ] All tests pass
- [ ] No dummy fallbacks exist in the extraction pipeline
- [ ] Concessions strictly match KPBR/KMBR Chapter VI rules
- [ ] PDF Audit Certificate formatting renders completely

---

## Task 5: Add Multimodal Vision Capabilities to `NimClient`

**Description:** Extend `NimClient` in `app/rag/llm.py` with `complete_vision()` to support image inputs using OpenAI-compatible multimodal message payloads (`image_url` data URI), with retry and timeout protections.

**Acceptance criteria:**
- [ ] `NimClient.complete_vision(system, prompt, image_bytes, mime_type)` accepts raw image bytes and sends base64 data URI messages.
- [ ] Honors model temperature, timeouts, and max retries.
- [ ] Unit tests verify mock multimodal request formatting.

**Verification:**
- [ ] Tests pass: `pytest tests/test_nim_llm.py`

**Dependencies:** None

**Files likely touched:**
- `app/rag/llm.py`
- `tests/test_nim_llm.py`

**Estimated scope:** Small (2 files)

---

## Task 6: Implement Raster Blueprint Vision Extractor (`app/pdf_intel/vision_extractor.py`)

**Description:** Create a vision-based architectural drawing extractor that renders PDF sheets to high-resolution images, calls `nvidia/nemotron-3.5-super-vl-120b-a12b`, and extracts certified parameters directly into `PlanFacts` Pydantic models when text parsing is insufficient.

**Acceptance criteria:**
- [x] `extract_plan_facts_with_nemotron_vl(pdf_path: Path)` renders the blueprint to an image and prompts Nemotron-3.5-VL with strict JSON schema instructions.
- [x] Extracted JSON is validated into a `PlanFacts` instance.
- [x] `build_plan_facts_from_pdf` invokes the vision extractor when regex text extraction returns incomplete mandatory fields.
- [x] Unit tests cover both successful vision extraction and fallback handling with faked/mocked responses.

**Verification:**
- [x] Tests pass: `pytest tests/test_pdf_intel.py tests/test_nim_llm.py`

**Dependencies:** Task 3, Task 5

**Files likely touched:**
- `app/pdf_intel/vision_extractor.py`
- `app/pdf_intel/normalizer.py`
- `app/pdf_intel/__init__.py`
- `tests/test_pdf_intel.py`

**Estimated scope:** Medium (4 files)

---

## Task 7: Optimize LangGraph Orchestration (Async Execution, Pre-compilation & Clean Graph)

**Description:** Pre-compile the multi-agent compliance LangGraph at application boot rather than compiling per request. Run PDF reading and vision extraction inside `asyncio.to_thread` to ensure non-blocking IO. Clean up the `node_classify` node to reconcile facts properly.

**Acceptance criteria:**
- [x] `build_multi_agent_graph()` is called once during app lifespan or module load and cached.
- [x] PDF extraction in `node_intake_and_extract` executes in a thread pool worker via `asyncio.to_thread`.
- [x] `node_classify` reconciles title block classifications with `PlanFacts`.

**Verification:**
- [x] Tests pass: `pytest tests/test_multi_agent_graph.py tests/test_symbolic_engine.py`

**Dependencies:** Task 6

**Files likely touched:**
- `app/rag/multi_agent_graph.py`
- `app/routes/rag_v2.py`
- `tests/test_multi_agent_graph.py`

**Estimated scope:** Small (2-3 files)

---

## Checkpoint: Multimodal Blueprint Ingestion
- [x] All tests pass
- [x] Raster blueprints parsed via Nemotron-VL
- [x] Event loop never blocked during PDF parsing
- [x] Graph compiled once at startup

---

## Task 8: Fix Frontend Race Condition, History State, and Memory Leaks

**Description:** Fix `frontend/src/pages/Analysis.jsx` to prevent premature navigation when checks take >14s. Refactor `NewCheck.jsx` to stop passing raw Promise objects through router history state, and add `URL.revokeObjectURL()` in `data.js` to prevent blob memory leaks.

**Acceptance criteria:**
- [x] `Analysis.jsx` waits for the analysis promise to resolve before navigating to results.
- [x] `NewCheck.jsx` uses standard state keys or sessionStorage rather than non-serializable Promise instances in router state.
- [x] `exportPdfReportV2` in `frontend/src/data.js` calls `URL.revokeObjectURL(url)` after triggering the download.

**Verification:**
- [x] Tests pass: `cd frontend && npm test -- --run`
- [x] Build succeeds: `cd frontend && npm run build`

**Dependencies:** None

**Files likely touched:**
- `frontend/src/pages/Analysis.jsx`
- `frontend/src/pages/NewCheck.jsx`
- `frontend/src/data.js`

**Estimated scope:** Small (3 files)

---

## Task 9: Synchronize K-Smart Contract, Resolve Ruff Lint Errors & Deprecations

**Description:** Update `POST /api/v2/check/pdf` to return the complete `ComplianceEvaluation` model so `VisualWorkbench.jsx` does not hardcode parameters client-side. Fix all 4 ruff F401 unused imports, and update `datetime.utcnow()` to `datetime.now(timezone.utc)`.

**Acceptance criteria:**
- [x] `check_architectural_pdf` response includes full `evaluation` metrics (`coverage_percent`, `max_coverage_percent`, `fsi_actual`, `max_fsi_permitted`, `parking_required`).
- [x] `VisualWorkbench.jsx` uses the backend-provided evaluation for K-Smart export without hardcoded overrides.
- [x] `ruff check .` returns zero errors.
- [x] `datetime.utcnow()` deprecation warnings resolved across models and routes.

**Verification:**
- [x] Tests pass: `pytest` (clean run, zero F401 errors from ruff)
- [x] Build succeeds: `cd frontend && npm run build`

**Dependencies:** Task 2, Task 7, Task 8

**Files likely touched:**
- `app/routes/rag_v2.py`
- `frontend/src/pages/VisualWorkbench.jsx`
- `app/pdf_intel/area_statement_parser.py`
- `tests/test_pdf_intel.py`
- `app/routes/auth.py`
- `app/services/dbmodel.py`

**Estimated scope:** Medium (5 files)

---

## Checkpoint: Final System Verification
- [x] All backend pytest tests pass (240+)
- [x] `ruff check .` passes with 0 errors
- [x] Frontend vitest and build succeed cleanly
- [x] All audit findings and Nemotron-VL vision integration complete
