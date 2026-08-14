// ChattamAI data + API layer.
//
// Honesty boundary (from the design system): the live FastAPI backend emits
//   - extracted_facts: string[]
//   - violations[]:     { rule_reference, severity(high|medium|low|info), description, plan_value?, required_value? }
//   - retrieved_rules[]:{ source<filename>, rule_id:null, excerpt, score<FAISS L2, lower=more relevant> }
// It does NOT emit an overall verdict enum, a 0-100 score, per-fact confidence,
// rule numbering, page numbers, or persisted history. Those are PRESENTATIONAL —
// we derive a display status from the real payload and treat the rest as framing.
//
// VITE_API_URL points at the FastAPI base (e.g. http://127.0.0.1:8000). When unset,
// the UI runs on realistic mock data so the public Vercel demo works standalone.

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export const apiAvailable = () => API_URL.length > 0

export const embeddingModel = 'text-embedding-3-small (1536-dim)'
export const analysisModel = 'claude-3-5-sonnet-20241022'

// ---- status derivation (design-system rule) -------------------------------
export function deriveStatus(response) {
  // response: { violations: [], retrieved_rules: [], summary? }
  const v = response?.violations || []
  const r = response?.retrieved_rules || []
  if (r.length === 0 && v.length === 0) return 'insufficient'
  if (v.some((x) => x.severity === 'high')) return 'violation'
  if (v.length > 0) return 'review'
  return 'compliant'
}

export const STATUS_META = {
  compliant: { label: 'COMPLIANT', pill: 'pill-ok', dot: 'var(--ok)', color: 'var(--ok)' },
  review: { label: 'REVIEW REQUIRED', pill: 'pill-warn', dot: 'var(--warn)', color: 'var(--warn)' },
  violation: { label: 'VIOLATION', pill: 'pill-danger', dot: 'var(--danger)', color: 'var(--danger)' },
  insufficient: { label: 'INSUFFICIENT EVIDENCE', pill: 'pill-insufficient', dot: 'var(--warn)', color: 'var(--warn)' },
}

export const SEVERITY_META = {
  high: { label: 'HIGH', pill: 'pill-danger' },
  medium: { label: 'MEDIUM', pill: 'pill-warn' },
  low: { label: 'LOW', pill: 'pill-info' },
  info: { label: 'INFO', pill: 'pill-info' },
}

// ---- static reference data -------------------------------------------------
export const metrics = [
  { label: 'Checks Completed', value: '128', delta: '+12%', tone: 'var(--ok)' },
  { label: 'Potential Violations', value: '37', delta: '+4%', tone: 'var(--danger)' },
  { label: 'Plans Analyzed', value: '214', delta: 'TOTAL', tone: 'var(--text)' },
  { label: 'KBR Rules Indexed', value: '2,481', delta: 'CHUNKS', tone: 'var(--accent)' },
]

export const checks = [
  { id: 'kak', project: 'Residential Building — Kakkanad', plan: 'plan_014.pdf', status: 'review', violations: 3, rules: 8, analyzed: '2026-08-12 14:22' },
  { id: 'kochi', project: 'Commercial Complex — Kochi', plan: 'kochi_cc_plan.pdf', status: 'violation', violations: 5, rules: 11, analyzed: '2026-08-11 09:47' },
  { id: 'tvm', project: 'Apartment Block — Thiruvananthapuram', plan: 'tvm_apt.txt', status: 'compliant', violations: 0, rules: 6, analyzed: '2026-08-08 16:03' },
  { id: 'villa', project: 'Villa Extension — Kozhikode', plan: 'villa_ext.pdf', status: 'insufficient', violations: null, rules: 0, analyzed: '2026-08-05 11:30' },
  { id: 'thr', project: 'Mixed-Use Development — Thrissur', plan: 'thrissur_mxd.pdf', status: 'review', violations: 2, rules: 9, analyzed: '2026-08-01 17:12' },
]

// Demo analysis result for the flagship flow (Residential Building — Kakkanad).
export const demoResponse = {
  extracted_facts: [
    'building type: residential',
    'floors: 3',
    'building height: 12m',
    'front setback: 1m',
    'rear setback: 2m',
    'plot area: 240 sq m',
    'built-up area: 410 sq m',
  ],
  violations: [
    {
      severity: 'high',
      rule_reference: 'Rule 23(4)',
      title: 'Front Setback',
      plan_value: '1.0 m',
      required_value: '≥ 3.0 m',
      description:
        'The submitted plan indicates a 1m front setback, while the retrieved KBR requirement specifies a minimum setback of 3m for this building classification.',
    },
    {
      severity: 'medium',
      rule_reference: 'Rule 27(1)',
      title: 'Parking Provision',
      plan_value: '4 spaces',
      required_value: '≥ 6 spaces',
      description:
        'The current configuration provides 4 off-street parking slots. Based on the total built-up area of 410 m², a minimum of 6 spaces is mandated for residential multi-unit occupancy.',
    },
    {
      severity: 'low',
      rule_reference: 'Rule 31(2)',
      title: 'Staircase Width',
      plan_value: '1.0 m',
      required_value: '≥ 1.2 m',
      description:
        'The clear width of the main internal staircase is marked as 1.0m. Rule 31(2) requires a minimum clear width of 1.2m for the primary means of escape.',
    },
  ],
  retrieved_rules: [
    {
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: '23(4)',
      page: 'p. 47',
      score: 0.91,
      excerpt:
        'Every building shall have a front setback of not less than the value prescribed for its occupancy group. For a residential building of this classification, the minimum front setback shall not be less than 3 metres measured from the plot boundary abutting the street, and such setback shall be kept free of any permanent construction.',
    },
    {
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: '27(1)',
      page: 'p. 63',
      score: 0.84,
      excerpt:
        'Off-street parking shall be provided on the same plot as the building it serves. For residential buildings, one car parking space shall be provided for every 75 square metres of built-up area or part thereof in excess of the first 150 square metres.',
    },
    {
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: '31(2)',
      page: 'p. 81',
      score: 0.79,
      excerpt:
        'The minimum clear width of a staircase serving as a primary means of escape shall not be less than 1.2 metres. Handrails may project into this width by not more than 75 millimetres on each side.',
    },
  ],
  score: 78, // presentational
  trace: [
    { node: 'extract_facts', status: 'done', detail: '1.8s', ts: '2026-08-12 14:21:42' },
    { node: 'retrieve', status: 'done', detail: '0.9s · 8 chunks', ts: '2026-08-12 14:21:43' },
    { node: 'analyze', status: 'done', detail: '3.1s · claude-3-5-sonnet', ts: '2026-08-12 14:21:46' },
    { node: 'summarize', status: 'done', detail: '1.2s · report_gen', ts: '2026-08-12 14:21:47' },
  ],
}

// structured fact grid (presentational confidence overlay)
export const demoFactGrid = [
  { label: 'Building Type', value: 'Residential', conf: 99 },
  { label: 'Floors', value: '3', conf: 100 },
  { label: 'Building Height', value: '12 m', conf: 98 },
  { label: 'Front Setback', value: '1 m', conf: 97 },
  { label: 'Rear Setback', value: '2 m', conf: 96 },
  { label: 'Plot Area', value: '240 m²', conf: 95 },
  { label: 'Built-up Area', value: '410 m²', conf: 92 },
]

export const kbrDocs = [
  { doc: 'Kerala Building Rules 2019.pdf', type: 'KBR', pages: 142, chunks: '1,284', indexed: '2026-08-02', status: 'INDEXED' },
  { doc: 'KBR Amendment 2021.pdf', type: 'KBR', pages: 38, chunks: '512', indexed: '2026-08-02', status: 'INDEXED' },
  { doc: 'Municipal Building Rules 1999.pdf', type: 'MBR', pages: 96, chunks: '685', indexed: '2026-06-18', status: 'INDEXED' },
]

export const kbrStats = [
  { label: 'Documents Indexed', value: '3' },
  { label: 'Chunks Indexed', value: '2,481' },
  { label: 'Last Ingestion', value: '2026-08-02 09:14' },
  { label: 'Embedding Model', value: 'text-embedding-3-small' },
  { label: 'Vector Store', value: 'FAISS · IndexFlatL2', ok: true },
]

export const reports = [
  { project: 'Residential Building — Kakkanad', date: '2026-08-12', status: 'review', violations: 3, reviewer: 'Pending' },
  { project: 'Commercial Complex — Kochi', date: '2026-08-11', status: 'violation', violations: 5, reviewer: 'Reviewed · E. Nair' },
  { project: 'Apartment Block — Thiruvananthapuram', date: '2026-08-08', status: 'compliant', violations: 0, reviewer: 'Signed off · E. Nair' },
  { project: 'Villa Extension — Kozhikode', date: '2026-08-05', status: 'insufficient', violations: null, reviewer: 'Pending' },
]

// Sequential script for the animated pipeline (Precision direction).
export const pipelineScript = [
  { t: 1, log: 'Parsing building plan structure…', stage: 0 },
  { t: 3, log: 'Extracted building height: 12m', stage: 0 },
  { t: 3.4, log: 'Extracted front setback: 1m', stage: 0 },
  { t: 5, log: 'Searching 2,481 indexed KBR chunks…', stage: 1 },
  { t: 6.2, log: 'Retrieved 8 relevant rules for this occupancy…', stage: 1 },
  { t: 8, log: 'Comparing setback requirements (KBR §4.2)…', stage: 2 },
  { t: 10.5, log: 'Checking parking & staircase provisions…', stage: 2 },
  { t: 12, log: 'Generating compliance assessment…', stage: 3 },
  { t: 14, log: 'Assessment complete — 3 potential issues detected.', stage: 4 },
]

// ---- live API (optional) ----------------------------------------------------
async function request(path, opts) {
  const res = await fetch(`${API_URL}${path}`, opts)
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export async function analyzePlan({ planText, file, top_k }) {
  if (!apiAvailable()) {
    // graceful fallback: simulate latency + return the flagship demo payload
    await new Promise((r) => setTimeout(r, 1600))
    return demoResponse
  }
  if (file) {
    const fd = new FormData()
    fd.append('file', file)
    const qs = top_k ? `?top_k=${top_k}` : ''
    return request(`/api/check/upload${qs}`, { method: 'POST', body: fd })
  }
  return request('/api/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_text: planText, top_k }),
  })
}

export async function fetchHealth() {
  if (!apiAvailable()) return { status: 'ok', index_size: 2481, embeddings_ready: true, llm_ready: true }
  return request('/api/health')
}
