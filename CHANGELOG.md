# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
