# ChattamAI — Design System

> **KBR Compliance Engine.** An AI-assisted verification workbench for LSGD (Local Self Government Department) engineers reviewing building plans against the **Kerala Building Rules (KBR)**. It helps an engineer upload a plan, extract regulated parameters, retrieve the relevant KBR provisions, and surface *evidence-backed potential violations* for human review.
>
> **Design ethos:** *Linear × an architectural blueprint tool × a modern AI compliance engine.* Premium, restrained, technical. Dark-first. Think a government engineering portal rebuilt by a top-tier product studio — not a chatbot, not a SaaS template, not a dashboard of colorful rounded cards.

---

## 1. Product context

**What it is.** ChattamAI is a **compliance decision-support system**, not an autonomous approval authority. A Retrieval-Augmented Generation (RAG) pipeline grounds every finding in retrieved rule text. The system's cardinal honesty rule: **if relevant rules cannot be retrieved, it must say "Insufficient Evidence" — never fabricate a verdict.**

**Who it's for.** Practicing LSGD building inspectors and plan-scrutiny engineers. Secondary: engineering-department heads and gov-tech evaluators reviewing a demo. They value precision, traceability, and speed over delight.

**Jobs to be done.**
1. *Screen a plan quickly* — paste text or drop a PDF, get a prioritized list of what needs attention.
2. *Trust but verify* — for every flagged item, see the exact KBR excerpt it came from, so the engineer can confirm with their own judgment.
3. *Know the limits* — instantly recognize when the system doesn't have enough rule coverage to opine, so nothing slips through as a false "compliant."
4. *Produce a reviewable record* — a clean assessment an engineer can sign off on and export.

**Compliance workflow (the product's spine):** `Upload Plan → Extract Facts → Retrieve KBR Rules → Analyze → Summarize`. This four-stage pipeline is the visual centerpiece of the product.

---

## 2. Architecture & data contract (drives all mock data)

**Backend:** `FastAPI → LangGraph → FAISS → OpenAI Embeddings → Claude`. The frontend calls a real API; design every screen around this true contract.

**LangGraph workflow nodes (exact):** `extract_facts → retrieve → analyze → summarize`, with a conditional short-circuit to an `insufficient` terminal state when no rules are retrieved.

**Real API endpoints:**
- `POST /api/check` — body `{ plan_text, top_k? }`
- `POST /api/check/upload` — multipart file (`.txt`/`.md`/`.text`/`.pdf`), optional `top_k`
- `POST /api/ingest` — re-index the KBR corpus
- `GET /api/health` — `{ status: "ok"|"degraded", index_size, embeddings_ready, llm_ready }`

**Response shapes — use these field names verbatim in mock data.**

`extracted_facts: string[]` — human-readable parameter lines, e.g. `"building height: 12m"`, `"front setback: 1m"`, `"plot area: 240 sq m"`. Missing values read `not specified`.

`violations[]` (findings):
```
rule_reference : string   // e.g. "Rule 23(4) — Minimum front setback"
severity       : "high" | "medium" | "low" | "info"
description    : string
plan_value     : string?  // value observed in the plan, e.g. "1.0 m"
required_value : string?  // KBR requirement, e.g. "≥ 3.0 m"
```

`retrieved_rules[]` (evidence):
```
source    : string   // filename, e.g. "Kerala_Building_Rules_2019.pdf"
rule_id   : null     // reserved; not populated today
excerpt   : string   // the raw retrieved rule text
score     : float    // FAISS L2 distance — SMALLER = more relevant
```

**Honesty boundary (crucial).** The live backend does **not** emit: an overall verdict enum, a 0–100 compliance score, per-fact confidence percentages, KBR rule numbering, page numbers, persisted projects/reports/activity, or a system-status panel. These are **presentation-layer constructs** the UI may show but must never present as authoritative backend output. In the UI, *derive display status* from the real payload:
- `INSUFFICIENT EVIDENCE` — `retrieved` empty AND `violations` empty
- `VIOLATION` — any finding with `severity: high`
- `REVIEW REQUIRED` — any finding present (no high)
- `COMPLIANT` — no findings
Score gauges, confidence badges, rule numbers and history are cosmetic framing around this real core.

**Reference/mock constants:** embedding model `text-embedding-3-small` (1536-dim); analysis LLM `claude-3-5-sonnet-20241022`; vector store FAISS `IndexFlatL2`. A representative corpus figure for the Knowledge Base UI is ~2,481 indexed chunks.

---

## 3. Principles

1. **Visual hierarchy above decoration.** Every screen has one unmistakable focal point. Generous whitespace, disciplined alignment, strong type scale.
2. **Trust through evidence.** Nothing in the UI asserts compliance without a visible rule trail. Evidence is always one click away.
3. **Engineer review is the product.** Recurring, calm cues that AI output is advisory: "AI-assisted assessment," "Potential violation," "Evidence-backed finding," "Engineer review required." Never the language of final approval.
4. **Technical credibility.** Precise monospace for measurements, rule references, timestamps, and IDs. Realistic numbers, believable excerpts, no lorem ipsum.
5. **Restraint beats flash.** Subtle, purposeful motion. No bouncy, game-like, or gimmicky animation. Flat, considered color — no gratuitous gradients.

---

## 4. Color

**Dark-first.** A deep charcoal / near-black canvas with layered slate surfaces and a faint blueprint grid. Cyan/blue is reserved for interactivity and live AI processing. Compliance status colors are the only saturated hues.

**Neutrals (canvas & surfaces)**
| Token | Value | Use |
|---|---|---|
| `--bg` | `#0A0E13` | app canvas (near-black, cool) |
| `--surface` | `#10151C` | cards, panels |
| `--surface-2` | `#161D27` | raised surfaces, drawers, hover |
| `--surface-3` | `#1C2531` | inputs, wells, code |
| `--border` | `#222C3A` | hairline borders |
| `--border-strong` | `#2E3B4D` | emphasized borders |
| `--text` | `#E7ECF2` | primary off-white text |
| `--text-2` | `#9AA7B6` | secondary text |
| `--text-3` | `#5B6879` | muted / metadata |

**Accent — AI / interactive (cyan-blue)**
| Token | Value | Use |
|---|---|---|
| `--accent` | `#22D3EE` | primary accent: active states, live AI processing, links, focus, the pipeline signal |
| `--accent-strong` | `#0EA5C9` | hover/pressed gradient stop |
| `--accent-ink` | `#0B7490` | text-on-light accent |
| `--accent-soft` | `rgba(34,211,238,0.12)` | accent fills/glows |
| A secondary cool blue `#3B82F6` may support the accent for informational states. | | |

**Status — the only other saturated hues**
| Token | Value | Meaning |
|---|---|---|
| `--ok` | `#34D399` | COMPLIANT |
| `--warn` | `#FBBF24` | REVIEW REQUIRED / WARNING / INSUFFICIENT EVIDENCE |
| `--danger` | `#F87171` | VIOLATION |
| `--info` | `#94A3B8` | INFO / neutral severity |

Each status color pairs with a soft tint (12–14% opacity of the hue) for pills/badges and a slightly brighter stroke. Severity maps: `high→danger`, `medium→warn`, `low→info`, `info→info`. Warm colors (amber/red) appear **only** as compliance semantics — never decoratively.

**Blueprint grid.** A subtle two-scale grid over the canvas: a fine grid plus a faint major grid every ~5 cells, in cool blue-grey at very low opacity (`rgba(120,150,190,0.045)` fine, `rgba(120,150,190,0.07)` major). It lives behind content, faintly drifts during AI processing, and never fights legibility.

---

## 5. Typography

Technical, engineered, and clear. A neutral grotesk for UI, a crisp monospace for data, and restrained display treatment.

- **UI / body:** `Inter` — interface text, labels, table content.
- **Technical / data (mono):** `JetBrains Mono` (fallback `IBM Plex Mono`) — measurements, rule references, IDs, timestamps, confidence %, code, excerpts, node names, numeric readouts.
- **Display (optional hero numerals):** `Space Grotesk` or tight-tracked `Inter` for large metric numbers and the compliance score.

**Scale (px):** 11 / 12 / 13 (labels, metadata) · 14 (body, tables) · 16 (emphasis) · 20–24 (section titles) · 32–40 (page headers, big score). Weights: 400 regular, 500 medium, 600 semibold. Use uppercase micro-labels (`11px`, `600`, `+0.08em` tracking) for section eyebrows and table headers.

**Type rules:** measurements & rule refs always mono; page headers semibold, generous size; body max ~14px on dense data surfaces; metadata is small, muted, mono where technical. Generous line-height (~1.5–1.6) for readable rule excerpts.

---

## 6. Spacing, radius, borders, shadow

- **Grid / spacing:** 8px base; common steps 4, 8, 12, 16, 24, 32, 48, 64. Dense but breathable; whitespace is the primary grouping mechanism.
- **Radius — restrained, minimal:** `2px` tiny, `4px` default on cards/buttons/inputs, `6px` on larger panels/drawers. No pill-shaped cards, no large rounded containers. **Avoid huge rounded cards.** Circular only for true circles (avatars, progress rings, status dots).
- **Borders:** thin `1px` hairlines (`--border`, `--border-strong`). Hairlines, not shadows, define most structure.
- **Shadow — small only:** `0 1px 2px rgba(0,0,0,0.4)` rest; `0 4px 16px rgba(0,0,0,0.5)` hover/lifted; a soft accent glow `0 0 20px rgba(34,211,238,0.18)` reserved for the active pipeline node / live AI focus. Heavy drop shadows are forbidden.
- **Surfaces:** subtle glass/metal feel via near-flat slate fills + hairline border + faint top-edge highlight (`inset 0 1px 0 rgba(255,255,255,0.03)`). Frosted-glass (`backdrop-filter: blur`) only for overlays (drawers, sheets, toasts, command palette).

---

## 7. Motion & animation

Subtle, professional, engineering-instrument feel. Standard easing `cubic-bezier(0.25, 0.1, 0.25, 1)`; durations 150–350ms for UI, longer (600–1200ms) only for the analysis pipeline.

- **Micro-interactions:** page/section fade-and-rise transitions; sidebar hover accent rail; button hover lift (1px) + press settle; cards subtly lift on hover; tables row-hover tint; smooth tab/accordion transitions; skeleton shimmer for loading; number counters that ease up; status pills that crossfade on change.
- **Blueprint grid:** faint continuous drift (~40s loop) during analysis; static otherwise.
- **Focus-visible:** crisp `2px` accent ring with subtle glow.

**The analysis pipeline (the centerpiece).** Four stages, connected left→right — **01 Extract Facts · 02 Retrieve Rules · 03 Analyze · 04 Summarize** — each with an icon, a description, and a progress ring. Animate **sequentially**:
- A **glowing cyan signal** travels along the connection lines, which **progressively illuminate** as work advances.
- The **active node**: gentle pulsing glow, a rotating technical indicator, an animated progress ring, and cycling status text.
- A **completed node** transforms into a checkmark; its connector stays lit.
- Beneath, a **live activity log** streams mono messages ("Parsing building plan…", "Extracted building height: 12m", "Searching 2,481 indexed KBR chunks…", "Retrieved 8 relevant rules", "Comparing setback requirements…", "Generating compliance assessment…").
- It must read as a **sophisticated engineering analysis system**, never a chatbot spinner. Speed is steady and confident, not frantic.

---

## 8. Core components

- **Sidebar (persistent, ~248px, collapsible on small screens):** brand block on top (`CHATTAMAI` wordmark + `KBR COMPLIANCE ENGINE` eyebrow), vertical nav with icon + label, a `2px` accent rail on the active item, and a footer **System Status** card (`● All systems operational`) with tiny status dots for **API · Vector Store · Claude · KBR Knowledge Base**.
- **Top header:** section eyebrow + page title + subtitle on the left; primary action (e.g. `+ New Compliance Check`) and contextual controls on the right; thin bottom hairline.
- **Buttons:** primary = accent gradient (cyan→deep cyan) with dark text and a crisp focus ring; secondary = surface-2 fill, hairline border; ghost/danger variants for tertiary and destructive actions. Compact (32–36px), 4px radius, mono numerals where applicable.
- **Cards / panels:** surface fill, `--border` hairline, 4px radius, small shadow; headers as uppercase mono eyebrow + thin divider. Lift slightly on hover.
- **Status pill:** compact, tinted soft fill + matching text + `1px` stroke, uppercase mono `11px`, optional leading dot — for COMPLIANT / REVIEW REQUIRED / VIOLATION / INSUFFICIENT EVIDENCE and severities.
- **Metric tiles:** large display numeral + small uppercase label + subtle delta/sparkline; hairline-separated grid.
- **Tables:** hairline row dividers, `13–14px` text, mono for measurements/counts/timestamps, uppercase mono column headers (`11px`, muted), row hover tint, horizontally scrollable on small screens. Empty/loading states use skeletons.
- **Metric progress ring (score):** animated SVG circular ring, track in `--surface-3`, arc in accent (or status color), large mono numeral in the center.
- **Pipeline nodes:** circular stage markers with icon, index (`01`–`04`), title, description, progress ring, and a lit connector segment; idle → active (glow) → done (check).
- **Evidence drawer:** right-side panel (~400px, frosted, slides in; bottom sheet on mobile) — shows `KBR Evidence` header, rule metadata (Rule ID · Document · Page · Relevance), the retrieved excerpt as a readable document panel with the key sentence highlighted in soft cyan, and a `Retrieved from KBR Knowledge Base` provenance footer.
- **Finding card:** severity pill + rule reference + requirement title; an observed-vs-required comparison (mono `plan_value` vs `required_value`); explanation body; `View KBR Source →` action.
- **Fact grid:** technical two-column data grid (label / mono value) with a small per-field confidence indicator.
- **Workflow trace:** collapsible technical panel rendering the LangGraph run vertically (`extract_facts ↓ retrieve ↓ analyze ↓ summarize`) with per-node status, duration, retrieved-chunk count, model operation, and timestamp — mono, muted, engineering-facing.
- **Drop zone:** blueprint-inspired upload area — dashed technical border, faint grid, blueprint iconography, primary label + helper + supported-format + max-size metadata; drag-over accent state.
- **Inputs:** surface-3 fill, hairline border, 4px radius, mono placeholders for technical fields, accent focus ring.
- **Toast / banner:** calm surface with status-colored left rail; used for the recurring "Engineer review required" notice.
- **Activity log:** streaming mono line feed with subtle reveal; the analysis pipeline's narration.

---

## 9. Screen inventory (the app)

Dark-first, desktop-first, responsive. Persistent left sidebar on all app screens.

1. **Dashboard** — "Kerala Building Compliance" / subtitle "AI-assisted verification against Kerala Building Rules", `+ New Compliance Check` primary action; metric tiles (Checks Completed · Potential Violations · Plans Analyzed · KBR Rules Indexed); a large **Recent Compliance Checks** table (Project · Plan · Status · Violations · Rules Referenced · Analyzed · Action) with status pills.
2. **New Compliance Check** — the upload workspace: a large blueprint drop zone (Upload Building Plan · PDF/TXT · max 25 MB) plus a "Paste Plan Description" text editor, with the prominent `Analyze Building Plan →` CTA.
3. **Analysis** — the animated 4-stage pipeline (centerpiece) with live activity log and drifting blueprint grid.
4. **Compliance Results** — assessment header (project name, `REVIEW REQUIRED` status), animated `78 / 100` score ring, "3 potential issues detected"; the findings list; the extracted-facts grid; the collapsible Analysis Trace; the KBR Evidence drawer.
5. **Insufficient Evidence** — amber warning state: "ChattamAI could not retrieve enough relevant Kerala Building Rules to make a reliable assessment", "Rules Retrieved: 0", actions (Upload Additional Documentation · Review KBR Knowledge Base · Run Analysis Again), and an explicit "Do not treat this result as a compliance approval" notice.
6. **KBR Knowledge Base** — corpus stats (Documents Indexed · Chunks Indexed · Last Ingestion · Embedding Model · Vector Store Status), `+ Ingest Rules`, a document table (Document · Type · Pages · Chunks · Indexed · Status), and an ingestion progress animation (Loading PDF → Chunking → Embedding → Indexing → Complete).
7. **Reports** — review history table (Project · Date · Overall Result · Violations · Engineer Review · Export) with a prominent `Export PDF` action.

(Projects, Activity, and Settings appear in navigation; they follow the same design language and can be generated as needed.)

---

## 10. Copy & tone

Precise, calm, institutional. Monospace for technical values. Sentence-case UI labels; uppercase mono for eyebrows/metadata. Recurring trust language: *AI-assisted assessment · Potential violation · Evidence-backed finding · Engineer review required.* The compliance status vocabulary is fixed: `COMPLIANT`, `REVIEW REQUIRED`, `VIOLATION`, `INSUFFICIENT EVIDENCE`; severities `HIGH / MEDIUM / LOW / INFO`. Absolutely no lorem ipsum — use realistic plan parameters, real-sounding KBR excerpts, and believable rule references throughout.

---

## 11. Responsive

Desktop is primary. On tablet/mobile: collapse the sidebar to icons/overlay; stack the four pipeline stages vertically; convert the evidence drawer to a bottom sheet; make tables horizontally scrollable; preserve the readability of technical/monospace data everywhere.

---

## 12. Fidelity guardrail

Generate **only** with the tokens, fonts, colors, spacing, radii, shadows, and components defined above. Do **not** introduce fonts, colors, gradients, heavy shadows, or large rounded cards that are not in this system. Stay dark-first, restrained, and technical; reserve warm colors for compliance semantics only.
