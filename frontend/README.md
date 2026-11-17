# ChattamAI — Frontend (KBR Compliance Engine)

A dark-first, blueprint-styled React app for AI-assisted verification of building plans against the **Kerala Building Rules (KBR)** for LSGD engineers. Designed on Superdesign; built with **Vite + React + Tailwind CSS + React Router**.

> **Compliance decision-support, not auto-approval.** Every screen reinforces that findings are *AI-assisted potential violations* that require engineer review, and that an empty retrieval yields an explicit **Insufficient Evidence** state — never a fabricated "compliant."

## Stack
- Vite 5 · React 18 · React Router 6 · Tailwind CSS 3
- No runtime CDN dependencies (icons are inlined, fonts via Google Fonts link)
- Deploy target: **Vercel** (static SPA)

## Run locally
```bash
cd frontend
npm install
npm run dev        # → http://localhost:5173
```

## Build / preview (production)
```bash
npm run build      # → dist/
npm run preview    # serve the prod build
```

## Deploy to Vercel
This app is a single-page app; routing is handled client-side and `frontend/vercel.json` rewrites all paths to `/index.html` so deep links (e.g. `/results/42`, `/kbr`) resolve.

**Two ways:**

1. **Vercel dashboard (recommended)**
   - New Project → import the repo.
   - **Root Directory:** `frontend`
   - Framework: `Vite` · Build Command: `npm run build` · Output Dir: `dist`
   - Deploy.

2. **Vercel CLI**
   ```bash
   cd frontend
   npx vercel            # follow prompts; root = frontend/
   npx vercel --prod
   ```

## Backend wiring
The app always talks to the FastAPI backend; there is no mock or demo mode, and API failures are shown to the user rather than replaced with placeholder data.

- Same origin (Docker/Azure image, or `npm run dev` with the Vite proxy): leave `VITE_API_URL` empty.
- Separate API origin: copy `.env.example` → `.env` and set `VITE_API_URL` (e.g. `https://api.example.com`). An HTTPS page cannot call an `http://` API; the app reports that as a configuration error.
- For a deployed Vercel build calling a remote API, add `VITE_API_URL` in the project's **Environment Variables** and ensure your frontend domain is whitelisted in the backend `CORS_ORIGINS` setting.

Used endpoints: `GET /api/health`, `POST /api/check`, `POST /api/check/upload`, `POST /api/check/plan-ocr`, `GET /api/reports`, `GET /api/reports/{id}`, `GET /api/reports/{id}/export`, `GET /api/kbr/documents`, `POST /api/kbr/upload`, `GET /api/rules/search`, `POST /api/ingest`, `POST /api/v2/check/pdf`, `POST /api/v2/evaluate`, `/auth/*`.

## Data-honesty note (matches the real API)
The backend returns `extracted_facts[]`, `violations[]` (`rule_reference`, `severity`, `description`, `plan_value`, `required_value`), and `retrieved_rules[]` (`source`, `rule_id:null`, `excerpt`, `score` = FAISS L2). It does **not** return an overall verdict, so the UI derives a display status in `src/data.js` (`deriveStatus`): `insufficient` when nothing is retrieved, `violation` on any `high` severity, otherwise `review`/`compliant`. The UI shows no score, confidence or other figure the backend did not produce.
