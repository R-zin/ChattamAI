# ADR 0001: Production Launch Architecture, Staged Rollout, and Error Budget Gates

## Status
Accepted

## Context
ChattamAI is transitioning from active engineering development to production deployment. The system combines:
1. A containerized FastAPI backend executing LangGraph multi-agent compliance workflows, FAISS vector retrieval, and multimodal vision processing (`nvidia/nemotron-3.5-super-vl-120b-a12b`).
2. A high-performance React SPA frontend (Swiss Modernist architectural drafting visual workbench).
3. Edge proxy routing via Cloudflare Workers and static asset distribution on Vercel CDN.
4. Cryptographic authentication: JWT sessions, TOTP 2FA, and Google OAuth 2.0 / OpenID Connect federation.

Because the system is utilized by municipal LSGD engineers and architects to audit Kerala Building Rules (KBR 2019) compliance, incorrect decisions, unhandled downtime, or silent failures can directly delay permits or compromise structural verification. Every launch must be incremental, reversible, observable, and governed by strict error budgets.

## Decision

### 1. Deployment Topology
- **Production Host**: Multi-stage Docker container deployed on Fly.io / GCP Cloud Run with a persistent encrypted block volume (`/app/data`) for the FAISS index (`data/index`) and SQLite database (`data/chattamai.db`).
- **Edge Layer**: Cloudflare Worker acting as reverse proxy for `/api/*` and `/auth/*`, terminating edge TLS, enforcing rate limits, and handling dynamic CORS negotiation with Vercel preview environments.
- **Client Delivery**: Vercel Edge Network serving static SPA assets with immutable cache-control headers for fingerprinted assets (`/assets/*`).

### 2. Feature Flagging Strategy
To decouple deployment from release, new capabilities will ship behind granular, time-bound feature flags:
- `ENABLE_NVIDIA_VISION`: Controls raster architectural blueprint parsing via Nemotron-3.5-VL vs classical PyMuPDF text fallback.
- `AUTH_REQUIRED`: Enforces mandatory JWT authentication on RAG analysis endpoints.
- `TOTP_REQUIRED`: Enforces mandatory 2FA enrolment before issuing access tokens.
- `ENABLE_GOOGLE_OAUTH`: Enables federated Google Identity login in both frontend and backend.
- `VITE_ENABLE_SIMULATION_ENGINE`: UI flag enabling the reactive What-If setback slider simulator.

**Flag Rules**:
- Flags must be evaluated at the edge or middleware layer before execution.
- Flags must have a designated owner and an expiration target (max 14 days after 100% rollout).
- Dead code paths must be removed upon flag retirement.

### 3. Staged Canary Rollout Schedule
1. **Stage 0: Staging Verification (100% internal)**
   - Run end-to-end test suite against staging environment with sample KBR blueprint PDFs.
   - Verify health check (`GET /api/health`), database migrations (`alembic upgrade head`), and security headers.
2. **Stage 1: Production Dark Deploy (0% user traffic)**
   - Deploy container with flags `OFF`. Verify `/api/health` returns 200 within 500ms.
3. **Stage 2: Internal Dogfooding (Team / Beta engineers)**
   - Whitelist internal users by email domain (`@chattamai.com`, internal LSGD beta testers).
   - 24-hour observation window.
4. **Stage 3: Canary Rollout (5% traffic)**
   - Route 5% of traffic through the new pipeline.
   - Monitor error rate and P95 latency against baseline.
   - Minimum bake time: 24 hours.
5. **Stage 4: Progressive Expansion (25% -> 50% -> 100%)**
   - 25% for 12 hours.
   - 50% for 12 hours.
   - 100% full release once all metrics pass green thresholds.

### 4. Decision Thresholds & Circuit Breakers

| Metric | Green (Advance) | Yellow (Hold & Investigate) | Red (Immediate Rollback) |
| :--- | :--- | :--- | :--- |
| **API Error Rate (5xx)** | < 0.1% | 0.1% - 1.0% | > 1.0% (or 2x baseline) |
| **P95 Latency (Analysis)** | < 3,500ms | 3,500ms - 5,000ms | > 5,000ms (+50% regression) |
| **P95 Latency (Health/Auth)** | < 150ms | 150ms - 300ms | > 300ms |
| **Client JS Unhandled Errors** | 0 new types | < 0.1% sessions | > 0.1% sessions |
| **Database Connection Exhaustion**| < 40% pool | 40% - 70% pool | > 70% pool |

### 5. Error Budget & SLO Release Gates
- **Service Level Objective (SLO)**: 99.9% availability for API queries over a rolling 30-day window (Error budget = 0.1% of requests).
- **Release Gate Policy**:
  - `Remaining Budget > 20%`: Deploy normally following canary stages.
  - `Remaining Budget 0% - 20%`: Freeze feature rollouts; only hotfixes and reliability improvements permitted. Canary advancement paused.
  - `Remaining Budget Exhausted (0%)`: Strict deployment freeze until error budget recovers. Immediate post-mortem required.

### 6. Rollback Strategy & Mean Time To Recovery (MTTR)
- **Level 1 (Instant Toggle)**: Disable feature flag in environment variables (`ENABLE_NVIDIA_VISION=false`). MTTR < 60 seconds.
- **Level 2 (Container Redeployment)**: Redeploy previous Docker image tag via `fly deploy -i <previous-image-tag>` or `git revert HEAD && git push`. MTTR < 3 minutes.
- **Level 3 (Database Schema Rollback)**: Run verified Alembic downgrade `alembic downgrade -1`. SQLite additive migrations maintain backward compatibility with old code. MTTR < 5 minutes.

## Consequences
- **Positive**: Eliminates single-point-of-failure deployments; provides automated kill switches; aligns team on objective operational metrics; guarantees database backward compatibility.
- **Negative**: Requires maintaining dual code paths during the 14-day canary window; adds operational overhead of monitoring canary metrics during deployment stages.
