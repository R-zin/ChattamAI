# Deployment Guide: Option A (Vercel Frontend + Serverless Container Backend + Cloudflare Gateway)

This guide walks you through deploying **ChattamAI** using the recommended **Option A** architecture:
- **Frontend**: Deployed on **Vercel** (Vite + React SPA).
- **Backend**: Deployed as a container on **Fly.io** (or Google Cloud Run / Railway / Render) to preserve FAISS, Tesseract OCR, LangGraph, and SQLite.
- **Edge Gateway**: Deployed on **Cloudflare Workers** to provide edge routing, DDoS protection, and unified CORS.

---

## Architecture Flow

```
User Browser
   │
   ├── (Static UI) ──────> Vercel Edge CDN (chattamai.vercel.app)
   │
   └── (API Requests) ───> Cloudflare Worker (api.chattamai.com)
                                 │
                                 └── (Proxy) ──> Backend Container (Fly.io / Cloud Run)
                                                   ├── FastAPI / LangGraph
                                                   ├── FAISS Vector Store (/app/data/index)
                                                   ├── Tesseract OCR Engine
                                                   └── SQLite Database (/app/data/chattamai.db)
```

---

## Step 1: Deploy Backend Container

### Method 1: Deploy on Fly.io (Recommended with Free Persistent Volume)

Fly.io provides serverless machine sleeping (scales to 0 when idle) and persistent volume storage for your SQLite database and FAISS vector index.

1. Install Fly CLI:
   ```bash
   # macOS:
   brew install flyctl
   # Linux/Windows:
   curl -L https://fly.io/install.sh | sh
   ```
2. Log in:
   ```bash
   fly auth login
   ```
3. Create the app and persistent volume:
   ```bash
   fly launch --no-deploy
   fly volumes create chattam_data --size 1 --region iad
   ```
4. Set required secrets:
   ```bash
   fly secrets set \
     SECRET_KEY="$(openssl rand -hex 32)" \
     ADMIN_KEY="your-secure-admin-key" \
     OPENAI_API_KEY="sk-..." \
     GEMINI_API_KEY="AIza..." \
     AUTH_REQUIRED="1"
   ```
5. Deploy:
   ```bash
   fly deploy
   ```
   *Note the resulting URL: `https://chattamai-backend.fly.dev`*

---

## Step 2: Deploy Cloudflare Worker Edge Gateway

The Cloudflare Worker in `cloudflare/` proxies API traffic to your backend container, terminates SSL at the edge, handles preflight CORS for Vercel, and injects security headers.

1. Navigate to the `cloudflare` directory:
   ```bash
   cd cloudflare
   ```
2. Open `wrangler.toml` and update:
   ```toml
   [vars]
   BACKEND_ORIGIN = "https://chattamai-backend.fly.dev"
   ALLOWED_ORIGINS = "https://your-app.vercel.app,http://localhost:5173"
   ```
3. Deploy the Worker:
   ```bash
   npx wrangler deploy
   ```
   *Note your Cloudflare Worker URL, e.g.: `https://chattamai-edge-gateway.<your-subdomain>.workers.dev`*

4. Verify edge health:
   ```bash
   curl https://chattamai-edge-gateway.<your-subdomain>.workers.dev/cf-health
   ```

---

## Step 3: Deploy Frontend to Vercel

The frontend is an optimized Vite React SPA configured with `frontend/vercel.json`.

### Option 3A: Via Vercel Web Dashboard (Recommended)

1. Push your repository to GitHub.
2. Go to [vercel.com/new](https://vercel.com/new) and import the repository.
3. Configure the project:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
4. Add Environment Variable:
   - **Name**: `VITE_API_URL`
   - **Value**: `https://chattamai-edge-gateway.<your-subdomain>.workers.dev` *(your Cloudflare Worker URL)*
5. Click **Deploy**.

### Option 3B: Via Vercel CLI

```bash
npm install -g vercel
cd frontend
vercel link
vercel env add VITE_API_URL production
# When prompted, enter: https://chattamai-edge-gateway.<your-subdomain>.workers.dev
vercel --prod
```

---

## Step 4: Verification & Smoke Test

1. **Access Vercel URL**:
   Open `https://your-app.vercel.app` in your browser.
2. **Verify API Connectivity**:
   - Navigate to `/settings`.
   - Verify that 2FA status loads and model configuration is active.
3. **Run Compliance Check**:
   - Upload or paste a test building plan.
   - Confirm extraction, retrieval, and analysis verdicts stream from the backend.
