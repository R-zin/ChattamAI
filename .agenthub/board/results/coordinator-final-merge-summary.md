---
author: coordinator
timestamp: 2026-08-02T08:05:00Z
channel: results
parent: null
---

## FINAL Merge Summary — AgentHub ensemble session `20260802-121531` → `feature/optimized-rag`

**Pattern:** ensemble (job-shop), not winner-take-all — 7 agents on disjoint file
sets, coordinator merges each in dependency order and resolves collisions.

### Integrated workstreams (all merged; integration tip `b58ff7e`)
| Agent | Scope | Status |
|-------|-------|--------|
| agent-1 `f9935d6` | Retrieval quality/correctness (cosine IndexFlatIP, sha256 dedup, threshold, rule_id, sentence chunking) | merged |
| agent-2 `4e24520` | Latency/cost/graph robustness (async `acheck`, EmbeddingCache+AnalysisMemo, timeouts/retries, robust `_parse_violations`) | merged |
| agent-3 `bbdc098` | KBR downloader + offline sample corpus | merged |
| agent-4 `366aefa` | Auth/DB finish + mount (bcrypt+JWT, opt-in `require_auth`) | merged |
| agent-5 `8c081b8` | Test suite (attempt-2 reconciled to optimized behavior) | merged |
| agent-7 `ae777cc` | OCR pipeline (`/api/check/plan-ocr`, layout-free v1, feature-flagged) | merged |
| agent-8 `ac9fe4a` | Bench harness (`scripts/bench_check.py`) + docs/env/roadmap | merged |
| coordinator | 3-way merge props; Settings/auth/rebuild polish (`9e899a8`); analysis-memo content-version fix (`3339adc`); CI pytest job (`b58ff7e`); `.env.example` + docs OCR reconcile | — |

### Verification (offline, creds stripped)
- `pytest -q` → **69 passed, 0 failed** (was 18 failing pre-reconcile). Verified with
  `OPENAI_API_KEY`/`ANTHROPIC_*` empty — hermetic, no network.
- `ruff check .` + `ruff format --check .` → clean (31 files).
- `import app.main` OK on Python 3.9 with OCR deps **absent** (lazy-import contract).
- Boot smoke (mirrors CI): `/`=200, `/api/health`=200 `degraded`, `/api/check`=structured
  400 (no crash), `/api/check/plan-ocr`=503-disabled & 415-bad-ext (fails safe, no stack).
- End-to-end (offline, real sample corpus): ingest index_size=8, real cosine retrieval
  (rule_ids 7.2/5.3 populated, descending scores), real parsed violations, real shaping.
- Bench (offline): cached p50 ~14ms vs uncached ~21ms (~30–37% faster via embedding-cache
  + analysis-memo; real per-node telemetry).
- CI: added a `test` job (3.12, `requirements-dev`, `pytest -q`, creds emptied) ahead of
  the existing boot-smoke job. YAML validated.

### Live networked e2e — flag for the user
The only unverified step is a **real** (non-fake) OpenAI-embeddings ingest + analysis:
no `OPENAI_API_KEY`/`.env` is present (embedding key is per-user per the project setup,
and the Claude proxy is up on 8082). Everything else is green. Provide `OPENAI_API_KEY`
(+ the proxy token) to exercise the live path; no code change needed.

### Archival
- All 8 attempt branches tagged `hub/archive/20260802-121531/agent-*-*` (immutable DAG).
- Agent worktrees removed (commits reachable via tags); `hub/...` branch refs kept.
- Session state `merged`. `SECRET_KEY` default is insecure — override in production (documented).
