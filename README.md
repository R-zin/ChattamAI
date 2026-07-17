# ChattamAI — Kerala Building Rules Compliance RAG

A Retrieval-Augmented Generation system that helps LSGD engineers compare an
uploaded building plan against the **Kerala Building Rules (KBR)** and surface
potential violations. Built with **FastAPI** (API), **LangGraph** (compliance
workflow orchestration), **FAISS** (vector store), **OpenAI embeddings**, and
**Anthropic Claude** (analysis LLM, via the local proxy).

## How it works

```
building plan (text/PDF)
        │
        ▼
┌──────────────── LangGraph workflow ────────────────┐
│ 1. extract_facts  → pull regulated parameters        │
│ 2. retrieve       → semantic search KBR chunks (FAISS)│
│ 3. analyze        → Claude compares facts vs rules    │
│ 4. summarize      → engineer-friendly report          │
└──────────────────────────────────────────────────────┘
```

If no rules are retrieved, the workflow short-circuits to an `insufficient`
branch rather than guessing.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then set OPENAI_API_KEY
```

Required env vars (see `.env.example`):
- `OPENAI_API_KEY` — embeddings (`text-embedding-3-small`)
- `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` — Claude (already set for the local proxy)
- `KBR_DATA_DIR` — folder of KBR PDFs/text (default `./data/kbr`)

## Run

```bash
uvicorn app.main:app --reload
# docs at http://127.0.0.1:8000/docs
```

## Usage

1. **Ingest the rules** (reads every `.pdf`/`.txt` in `KBR_DATA_DIR`, chunks, embeds, builds the FAISS index):
   ```bash
   curl -X POST http://127.0.0.1:8000/api/ingest
   ```
2. **Check a plan** (text):
   ```bash
   curl -X POST http://127.0.0.1:8000/api/check \
     -H "Content-Type: application/json" \
     -d '{"plan_text": "3-floor building, 12m tall, 1m front setback"}'
   ```
   Or upload a file:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/check/upload -F "file=@plan.pdf"
   ```
3. **Health**: `GET /api/health`

## Layout

```
app/
  main.py            FastAPI app + lifespan init
  config.py          env-based settings
  schemas.py         request/response models
  routes/rag.py      /api/ingest, /api/check, /api/health
  rag/
    embeddings.py    EmbeddingProvider + OpenAI impl
    vectorstore.py   FAISS-backed rule store
    ingestion.py     KBR + plan loaders / chunking
    llm.py           Anthropic Claude client
    prompts.py       prompt templates
    graph.py         LangGraph compliance workflow
    system.py        RAGSystem (wires it all together)
data/kbr/            drop Kerala Building Rules documents here
```

## Limitations

- Plan parsing supports **text-based** PDFs/txt. Image-only floor plans need
  OCR/layout analysis (see plan.md Phase 2).
- Analysis depends on what rules were ingested and retrieved; always have an
  engineer review the output before acting on it.
