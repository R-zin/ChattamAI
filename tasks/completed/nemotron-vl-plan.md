# Implementation Plan: Multimodal Nemotron-VL Blueprint Parsing & Audit Remediation

## Overview

This plan enhances ChattamAI by implementing multimodal architectural blueprint parsing using **NVIDIA Nemotron 3.5 Super VL 120B** (`nvidia/nemotron-3.5-super-vl-120b-a12b`) for complex raster drawings and resolving all critical, security, correctness, and architectural defects identified in the codebase audit. 

Upon completion, ChattamAI will:
1. Reliably extract certified parameters from complex/raster architectural blueprints via Nemotron-3.5-VL with zero dummy fallbacks.
2. Enforce strict upload limits (25MB), IP rate-limiting, and authentication gating on `/api/v2/*` endpoints.
3. Fix statutory concession logic, report formatting, and frontend race conditions.
4. Pass all automated tests and linter checks with zero warnings or dead imports.

---

## Architecture Decisions

- **ADR-01: Multimodal Vision Seam in `NimClient`:** Extend `NimClient` with `complete_vision()` using the standard OpenAI-compatible `image_url` base64 payload format, enabling vision inference on hosted or local NIM endpoints without introducing heavy external orchestration libraries.
- **ADR-02: Strict Boundary Validation over Dummy Fallbacks:** Remove all synthetic defaults (`plot_area = 200.0`, `height = 7.5`, etc.) from `normalizer.py`. If neither local schedule parsing nor Nemotron-VL vision extraction can locate required building parameters, return a strict `422 Unprocessable Entity` with a detailed parameter deficit message.
- **ADR-03: Threaded PDF IO & Startup Graph Pre-compilation:** Run blocking PyMuPDF / rasterization operations inside `asyncio.to_thread` and pre-compile the LangGraph multi-agent compliance pipeline at server startup to prevent event loop stalls.
- **ADR-04: Full Contract Alignment for K-Smart & Reports:** Return the complete `ComplianceEvaluation` payload from `/api/v2/check/pdf` and record runs in the SQLite database via `_persist_report()`, ensuring client state and persistence parity with V1 routes.

---

## Task List

### Phase 1: Security Hardening & Gateways
- [x] Task 1: Enforce upload size caps, header sanitization, and rate limiting on V2 routes
- [x] Task 2: Implement authentication gating and persistent report storage for V2 runs

### Checkpoint: Security & Gateways
- [x] All V2 endpoints reject files >25MB with HTTP 413
- [x] V2 endpoints rate-limited under `_SENSITIVE_PREFIXES`
- [x] V2 checks persist to SQLite and reflect in `/api/reports`

### Phase 2: Correctness & Elimination of Hallucinated Fallbacks
- [x] Task 3: Remove dummy fallbacks in `normalizer.py`, fix regex unit parsing, and word boundaries
- [x] Task 4: Fix concession logic in `statutory_critic.py` and text truncation in `pdf_report_v2.py`

### Checkpoint: Correctness & Mathematical Integrity
- [x] Unparseable PDFs reject with clear HTTP 422 instead of hallucinated passes
- [x] Side Setback 1 and Side Setback 2 evaluated according to Rule 27(3) (0.9m and 0.6m)
- [x] PDF Audit Certificate renders clean multi-line remediation notes

### Phase 3: Multimodal Blueprint Parsing with NVIDIA Nemotron-3.5-VL
- [x] Task 5: Add vision inference capability to `NimClient`
- [x] Task 6: Implement raster blueprint vision extractor (`app/pdf_intel/vision_extractor.py`)
- [x] Task 7: Optimize LangGraph orchestration (pre-compilation, threaded execution, dead node removal)

### Checkpoint: Multimodal Extraction
- [x] Raster blueprint images extracted into validated `PlanFacts` via Nemotron-3.5-VL
- [x] PyMuPDF rendering executed in worker threads without event loop blocking
- [x] Multi-agent graph compiled once at boot

### Phase 4: Frontend Workbench & Codebase Hygiene
- [x] Task 8: Fix frontend animation race condition, history state, and object URL memory leak
- [x] Task 9: Synchronize Visual Workbench K-Smart payload, resolve ruff lint errors, and deprecations

### Checkpoint: Complete Verification
- [x] All 240+ backend tests pass
- [x] `ruff check .` returns 0 errors
- [x] Frontend builds and tests pass cleanly

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **NVIDIA NIM Vision Rate/Token Limits** | High | Compress/downscale rendered raster pages to 150-200 DPI JPEG/PNG before base64 encoding; cache extraction by PDF hash. |
| **Missing NVIDIA_API_KEY in Offline Dev** | Medium | Gracefully fallback to deterministic textual/table extraction when vision credentials are not configured. |
| **Breaking Existing Tests with Strict Validation** | High | Update test fixtures that relied on unparseable dummy PDFs to use well-formed synthetic Area Statements. |

---

## Open Questions

- None. All requirements and architectural specifications have been resolved.
