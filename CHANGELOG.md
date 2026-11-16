# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Structure-aware ingest** (`app/rag/structure.py`): chunks follow chapters, rules and tables, never cross a rule boundary, and carry a citable `rule_id` (`Rule 26, Table 4`), heading breadcrumb and PDF page. The breadcrumb is embedded and keyword-indexed with the text. Running page footers are stripped.
- **Topic-aware multi-query retrieval** (`app/rag/retrieval.py`): the fact sheet is split by regulated topic, each topic is queried in the rulebook's vocabulary, all queries share one embedding call, and rankings are combined with reciprocal-rank fusion and MMR. Select with `RETRIEVAL_STRATEGY` (`advanced` default, `simple` = previous behaviour).
- **Coverage grading with a corrective pass**: `retrieval.coverage` in the check response says, per regulated topic, whether a rule was retrieved. Gaps are passed to the analyst and summary prompts so an unretrieved topic is reported as not assessed instead of silently skipped.
- **Citation grounding** (`app/rag/grounding.py`): each finding's cited rule and required value are checked against the retrieved excerpts and reported in `grounding` (`grounded` / `partial` / `ungrounded` / `uncited`). Findings are never removed.
- **Rulebook Q&A**: `POST /api/rules/ask` returns an answer with server-verified `[n]` citations, or abstains when the indexed rules do not cover the question.
- **Search modes and explanations**: `GET /api/rules/search` accepts `mode=hybrid|dense|lexical|advanced` and returns per-channel scores, matched terms, section and page.
- **Index statistics**: `GET /api/kbr/index` reports chunks, rules and pages per indexed document.
- **Domain lexicon** (`app/rag/lexicon.py`): normalising BM25 tokenizer (punctuation, plurals, units, clause numbers) and query-side synonyms (setback/yard/open space, FAR/FSI).
- **Retrieval evaluation**: `scripts/eval_retrieval.py` and `tests/fixtures/retrieval_golden.json` measure recall@k and MRR offline against the bundled rulebook; a test gates the shipped configuration.
- **UI**: "Ask the Rulebook" panel, search-mode selector and live index statistics on the Knowledge page; citation badges and a rule-coverage panel on the Results page.
- **PaddleOCR on NVIDIA NIM for floor plans** (`OCR_PROVIDER=nim`, default when `NVIDIA_API_KEY` is set). Image plans and image-only PDFs are sent to `baidu/paddleocr` (hosted, or a self-hosted NIM via `PADDLEOCR_URL`). Large drawings are split into overlapping full-resolution tiles to fit the hosted payload limit. Detections feed the existing layout reconstruction (`label: value` lines), transient errors are retried, and the app falls back to Tesseract if the NIM fails. Azure now enables OCR by default (`ocrEnabled`, `ocrProvider` Bicep params), and `/api/health` reports `ocr_enabled` / `ocr_provider`.

### Removed
- **Sample data everywhere.** The synthetic `data/kbr/sample_kbr_excerpt.txt` is no longer shipped or indexed; on boot, older deployments delete it from the data volume (only when its content matches the sample) and rebuild the index.
- **Frontend mock/demo mode** (`VITE_USE_MOCKS`), the demo credentials and guest login, the sample presets on New Check, the sample PDF in the Workbench, and the Projects and Activity pages (they had no backend and only showed fixed sample records).

### Changed
- **Index format v4**: existing indexes are discarded on start and rebuilt by the startup ingest (or `POST /api/ingest`). This re-embeds the corpus once.
- Default `TOP_K` raised from 6 to 8 so each regulated topic in a full fact sheet can keep its rule.
- The analysis memo key now includes the retrieved rule set, so a different `top_k` or strategy never replays another prompt's answer.
- `GET /api/rules/search` now honours `AUTH_REQUIRED` and is rate limited, like the other paid endpoints.
- Dashboard, Results, Knowledge Base and Settings now show only backend data: metrics come from `/api/reports` and `/api/health`, and results come from the check just run or `GET /api/reports/{id}` (new `/results/:id` route). There is no placeholder score, trace or fact grid.
- An `http://` API from an `https://` page is reported as a configuration error instead of silently switching to mock data.
- The sidebar engine status is read from `/api/health` (ONLINE / DEGRADED / OFFLINE) instead of always showing ONLINE.
- The synthetic sample excerpt moved to `tests/fixtures/kbr/`; the structure, end-to-end and retrieval-gate tests read it from there. The retrieval gate still evaluates gazette + sample (the corpus its thresholds were calibrated on); `scripts/eval_retrieval.py` alone now measures the production corpus.
- Page tests stub the backend with API-shaped fixtures (`src/test/fixtures.js`); the UI audit (`frontend/scripts/ui-audit`) runs against a real backend with `AUDIT_TOKEN`.

### Fixed
- Knowledge page showed static demo statistics and estimated page/chunk counts in live mode; it now shows real numbers from the index, and marks uploaded-but-not-ingested documents as `NOT INDEXED`.
- Knowledge page reported a failed ingestion as "Ingestion completed".
- PDF certificate export (`/api/v2/check/pdf/export-report`) now sends the bearer token, so it works when `AUTH_REQUIRED` is on.
- The Knowledge Base document table read `size`/`modified`, but the API sends `size_bytes`/`modified_at`.
- The analysis screen labelled every failure "HTTP 400 non-architectural document".

## [1.0.0] - 2026-10-27

### Added
- **Multimodal Architectural Blueprint Parsing (V2)**: Integrated `nvidia/nemotron-3.5-super-vl-120b-a12b` via NVIDIA NIM for high-resolution raster blueprint extraction, section detection, and rule parameter parsing.
- **Pre-compiled LangGraph Orchestrator**: Multi-agent compliance validation graph running asynchronously with per-node telemetry, fact extraction, FAISS rule retrieval, analysis, and repair retry loops.
- **Swiss Modernist Frontend UI**: Complete design overhaul with architectural drafting aesthetics, high-contrast monospace typographic hierarchy, accessible dialog primitives (`Modal`, `Card`, `Button`, `Skeleton`, `Slider`), and reactive What-If setback simulator.
- **Google OAuth 2.0 / OpenID Connect**: Federated sign-in support (`GET /auth/google/url`, `POST /auth/google/callback`, `POST /auth/google/token`) with tamper-proof signed CSRF state tokens.
- **Two-Factor Authentication (TOTP)**: RFC 6238 time-based one-time password enrolment, QR code provisioning, single-use recovery code generation, and step-up challenge gating.
- **Defense-in-Depth Security**: Strict HTTP security headers (`CSP`, `HSTS`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`), upload magic byte verification for `%PDF-`, and IP-based rate-limiting with memory key eviction bounding.
- **Continuous Integration Pipeline**: Multi-version Python matrix (3.10, 3.12), Vitest frontend unit testing, live NVIDIA Nemotron vision parsing verification, and automated FastAPI server smoke testing.
- **Cloudflare Edge Gateway & Multi-stage Dockerfile**: Serverless edge reverse proxy and containerized runtime with Tesseract OCR, Poppler utilities, and persistent storage mounts.

### Changed
- Migrated default CORS from wildcard `*` to strict origin whitelisting (`CORS_ORIGINS`).
- Replaced unconstrained file uploads with 25MB request body caps and format integrity checks.
- Upgraded report generation with deterministic JSON export and Sanketham / K-Smart schema compatibility.
- Additive database schema migrations via Alembic for User model OAuth federation and TOTP columns.

### Fixed
- Fixed rate limiting bucket collision across sequential test client invocations with automatic per-test bucket reset.
- Fixed frontend memory leak from unrevoked blob object URLs during PDF previews.
- Fixed race condition in visual analysis animation loops and Promise history state.
- Resolved Python `datetime.utcnow()` deprecation warnings and updated to timezone-aware UTC timestamps.
