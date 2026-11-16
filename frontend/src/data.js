// ChattamAI data + API layer.
//
// Honesty boundary: everything the UI shows about a plan, a report or the rule
// corpus comes from the FastAPI backend. There is no mock or demo mode and no
// fallback data: when a call fails, the error reaches the page and is shown.
//
// The live FastAPI backend emits
//   - extracted_facts: string[]
//   - violations[]:     { rule_reference, severity(high|medium|low|info), description, plan_value?, required_value? }
//   - retrieved_rules[]:{ source<filename>, rule_id, section?, page?, topics[], excerpt, score<higher=more relevant> }
//   - retrieval:        { strategy, queries[], coverage[{topic,label,status,rule_ids,reason}], gaps[] }
//   - grounding:        { score, grounded, partial, ungrounded, uncited, items[{violation_index,status,citations,note}] }
// It does NOT emit an overall verdict enum, so the display status is derived
// from the real payload (deriveStatus below).
//
// VITE_API_URL points at the FastAPI base (e.g. https://api.example.com). When
// empty/unset the app talks to the SAME ORIGIN that served it, which is how the
// Docker/Azure build is deployed (API and SPA share one container). In
// `npm run dev` the Vite dev server proxies /api and /auth to the backend.

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

// An HTTPS page cannot call an http:// API (the browser blocks mixed content).
// Returns a readable configuration error, or null when the API URL is usable.
export function apiConfigError() {
  if (
    typeof window !== 'undefined' &&
    window.location &&
    window.location.protocol === 'https:' &&
    API_URL.startsWith('http://')
  ) {
    return `Misconfigured API URL: this page is served over HTTPS but VITE_API_URL (${API_URL}) uses http://, which the browser blocks.`
  }
  return null
}

function endpoint(path) {
  const problem = apiConfigError()
  if (problem) throw new Error(problem)
  return `${API_URL}${path}`
}

// ---- auth token storage --------------------------------------------------------
// Stored in sessionStorage by default (closing the tab logs you out, matching the
// 1-hr JWT); localStorage only when the user opts "remember me".
const TOKEN_KEY = 'chattam.token'
export const getToken = () => {
  try {
    return (typeof sessionStorage !== 'undefined' && sessionStorage ? sessionStorage.getItem(TOKEN_KEY) : null) ||
           (typeof localStorage !== 'undefined' && localStorage ? localStorage.getItem(TOKEN_KEY) : null) || null
  } catch {
    return null
  }
}
export const setToken = (token, remember = false) => {
  clearToken()
  try {
    const storage = remember ? (typeof localStorage !== 'undefined' ? localStorage : null) : (typeof sessionStorage !== 'undefined' ? sessionStorage : null)
    storage?.setItem(TOKEN_KEY, token)
  } catch {}
}
export const clearToken = () => {
  try {
    if (typeof sessionStorage !== 'undefined' && sessionStorage) sessionStorage.removeItem(TOKEN_KEY)
    if (typeof localStorage !== 'undefined' && localStorage) localStorage.removeItem(TOKEN_KEY)
  } catch {}
}
export const isAuthed = () => !!getToken()

const authHeaders = () => {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

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

// Citation grounding of a finding (backend: app/rag/grounding.py). Colour is
// never the only signal: each status has its own label and glyph.
export const GROUNDING_META = {
  grounded: { label: 'CITATION VERIFIED', pill: 'pill-ok', glyph: '✓', hint: 'The cited rule was retrieved and supports the required value.' },
  partial: { label: 'PARTLY VERIFIED', pill: 'pill-warn', glyph: '◐', hint: 'Only the citation or the value could be matched to the retrieved rules.' },
  ungrounded: { label: 'CITATION NOT FOUND', pill: 'pill-danger', glyph: '✕', hint: 'The cited rule is not among the retrieved excerpts. Verify manually.' },
  uncited: { label: 'NO RULE CITED', pill: 'pill-info', glyph: '?', hint: 'The finding does not name an identifiable rule.' },
}

// Whether a rule was retrieved for a regulated topic (app/rag/retrieval.py).
export const COVERAGE_META = {
  covered: { label: 'RULE RETRIEVED', pill: 'pill-ok', glyph: '✓' },
  recovered: { label: 'FOUND BY KEYWORD', pill: 'pill-info', glyph: '↺' },
  gap: { label: 'NO RULE RETRIEVED', pill: 'pill-warn', glyph: '!' },
}

export const COVERAGE_GAP_REASON = {
  not_in_index: 'No indexed rule covers this topic.',
  truncated: 'A rule exists but did not fit in the retrieved set. Raise the rule count.',
}

// Evidence level of a rulebook answer (app/rag/qa.py).
export const ANSWER_CONFIDENCE_META = {
  high: { label: 'WELL SUPPORTED', pill: 'pill-ok', hint: 'Cited rules share the key terms of your question.' },
  medium: { label: 'SUPPORTED', pill: 'pill-info', hint: 'Cited, but the rules use different wording. Read the excerpt.' },
  low: { label: 'UNCITED ANSWER', pill: 'pill-warn', hint: 'The answer cites no retrieved rule. Do not rely on it.' },
  none: { label: 'NOT IN THE RULES', pill: 'pill-insufficient', hint: 'The indexed rules do not answer this question.' },
}

export const SEARCH_MODES = [
  { value: 'hybrid', label: 'Hybrid', hint: 'Meaning + keywords' },
  { value: 'dense', label: 'Semantic', hint: 'Meaning only' },
  { value: 'lexical', label: 'Keyword', hint: 'Exact words only' },
  { value: 'advanced', label: 'Topic-aware', hint: 'What the compliance check uses' },
]

// Validation for architectural building plan specifications
const BUILDING_ENTITIES = [
  'building', 'buildings', 'structure', 'structures', 'house', 'houses',
  'villa', 'villas', 'apartment', 'apartments', 'flat', 'flats',
  'residence', 'residential', 'commercial', 'office', 'hospital',
  'clinic', 'dispensary', 'school', 'college', 'institution',
  'institutional', 'mall', 'complex', 'multiplex', 'warehouse',
  'factory', 'industrial', 'educational', 'hazardous', 'mercantile',
  'assembly', 'occupancy', 'dwelling', 'shed', 'godown', 'cottage',
  'auditorium', 'lodge', 'hostel', 'hotel', 'kbr', 'kpmbr',
  'kerala building', 'lsgd', 'panchayat', 'municipality', 'corporation',
  'group a', 'group a1', 'group a2', 'group b', 'group c', 'group d',
  'group e', 'group f', 'group g', 'group h', 'group i', 'group j',
  'development', 'construction', 'blueprint', 'floor plan', 'site plan',
  'layout plan', 'architectural', 'drawing',
]

const PLANNING_PARAMETERS = [
  'floor', 'floors', 'storey', 'storeys', 'story', 'stories', 'level',
  'levels', 'height', 'tall', 'depth', 'width', 'length', 'dimension',
  'dimensions', 'meter', 'meters', 'metre', 'metres', 'centimeter',
  'centimeters', 'centimetre', 'centimetres', 'sqm', 'sq.m', 'sq m',
  'sq.metre', 'sq.metres', 'sq.meter', 'sq.meters', 'square metre',
  'square metres', 'square meter', 'square meters', 'sq ft', 'sqft',
  'square feet', 'cent', 'cents', 'plot', 'site', 'area', 'built-up',
  'builtup', 'built up', 'plinth', 'carpet area', 'fsi', 'far',
  'floor space index', 'floor area ratio', 'coverage', 'ground coverage',
  'setback', 'setbacks', 'set-back', 'set-backs', 'front setback',
  'rear setback', 'side setback', 'front distance', 'rear distance',
  'side distance', 'front open space', 'rear open space', 'side open space',
  'open space', 'open spaces', 'road width', 'street width', 'access width',
  'road', 'street', 'boundary', 'boundaries', 'abutting', 'parking',
  'car parking', 'staircase', 'stairs', 'fire escape', 'fire safety',
  'exit', 'corridor', 'passage', 'balcony', 'verandah', 'veranda',
  'terrace', 'mezzanine', 'basement', 'cantilever', 'projection',
  'canopy', 'parapet', 'ground floor', 'first floor', 'second floor',
  'living room', 'bedroom', 'kitchen',
]

export function isBuildingPlanText(text) {
  if (!text || typeof text !== 'string') return false
  const cleaned = text.trim()
  if (cleaned.length < 15) return false
  const lower = cleaned.toLowerCase()
  let entityHits = 0
  for (const term of BUILDING_ENTITIES) {
    if (lower.includes(term)) entityHits++
  }
  let paramHits = 0
  for (const term of PLANNING_PARAMETERS) {
    if (lower.includes(term)) paramHits++
  }
  return (entityHits >= 1 && paramHits >= 1) || paramHits >= 2
}

// ---- transport -----------------------------------------------------------------
const UNREACHABLE = 'Backend service is currently unreachable.'
const isNetworkError = (err) =>
  err instanceof TypeError || /Failed to fetch|Load failed|NetworkError/i.test(err?.message || '')

async function errorDetail(res) {
  try {
    const body = await res.json()
    const d = body?.detail ?? body?.message
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map((x) => String(x?.msg || '')).filter(Boolean).join('. ')
  } catch (_) {}
  return ''
}

// Authenticated fetch: adds the bearer token, maps network failures to a
// readable message and sends the user to /login on 401. Returns the Response.
async function send(path, opts = {}) {
  const headers = { ...authHeaders(), ...(opts.headers || {}) }
  let res
  try {
    res = await fetch(endpoint(path), { ...opts, headers })
  } catch (err) {
    throw new Error(isNetworkError(err) ? UNREACHABLE : err.message || 'Network request failed')
  }
  if (res.status === 401) {
    clearToken()
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.assign('/login')
    }
    throw new Error('Your session has expired. Please sign in again.')
  }
  if (!res.ok) {
    throw new Error((await errorDetail(res)) || `API ${res.status}`)
  }
  return res
}

async function request(path, opts = {}) {
  const res = await send(path, opts)
  return res.json()
}

const postJson = (path, body) =>
  request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

// ---- symbolic V2 engine ----------------------------------------------------------
export async function checkPdfV2(file) {
  const fd = new FormData()
  fd.append('file', file)
  return request('/api/v2/check/pdf', { method: 'POST', body: fd })
}

export async function exportPdfReportV2(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await send('/api/v2/check/pdf/export-report', { method: 'POST', body: fd })
  saveBlob(await res.blob(), `LSGD_KBR_Audit_${file.name.replace(/\.pdf$/i, '')}.pdf`)
}

export async function evaluatePlanFactsV2(facts = {}) {
  return postJson('/api/v2/evaluate', facts)
}

export async function exportKSmartV2(payload) {
  return postJson('/api/v2/reports/ksmart', payload)
}

// ---- RAG compliance check ----------------------------------------------------------
let _pendingAnalysisPromise = null

export function setPendingAnalysis(promise) {
  _pendingAnalysisPromise = promise
}

export function getPendingAnalysis() {
  const p = _pendingAnalysisPromise
  _pendingAnalysisPromise = null
  return p
}

export async function analyzePlan({ planText, file, top_k }) {
  if (file) {
    const isImage = /\.(png|jpe?g|webp|tiff?)$/i.test(file.name || '') || file.type?.startsWith('image/')
    const fd = new FormData()
    fd.append('file', file)
    if (isImage) {
      const qs = top_k ? `&top_k=${top_k}` : ''
      return request(`/api/check/plan-ocr?layout=true${qs}`, { method: 'POST', body: fd })
    }
    const qs = top_k ? `?top_k=${top_k}` : ''
    return request(`/api/check/upload${qs}`, { method: 'POST', body: fd })
  }
  return postJson('/api/check', { plan_text: planText, top_k })
}

export async function fetchHealth() {
  return request('/api/health')
}

// ---- reports ---------------------------------------------------------------------
const REPORT_STATUS = { fail: 'violation', warning: 'review', insufficient: 'insufficient', pass: 'compliant' }

export function summarizeReport(r) {
  const status = REPORT_STATUS[r.status] || deriveStatus(r)
  const plan = (r.plan_text || '').trim()
  return {
    id: r.report_id,
    project: plan ? (plan.length > 35 ? plan.slice(0, 32) + '…' : plan) : `Assessment #${r.report_id}`,
    source: r.source || null,
    date: r.created_at ? new Date(r.created_at).toISOString().slice(0, 10) : '—',
    status,
    violations: Array.isArray(r.violations) ? r.violations.length : 0,
    reviewer: r.user_id ? `User ${String(r.user_id).slice(0, 8)}` : 'Engine Check',
  }
}

export async function fetchReports() {
  const data = await request('/api/reports')
  return Array.isArray(data) ? data.map(summarizeReport) : []
}

// Full persisted report (same shape as a /api/check response plus metadata).
export async function fetchReport(id) {
  return request(`/api/reports/${encodeURIComponent(id)}`)
}

export async function downloadReport(id, format = 'pdf') {
  const res = await send(`/api/reports/${encodeURIComponent(id)}/export?format=${format}`)
  saveBlob(await res.blob(), `compliance_report_${id}.${format === 'html' ? 'html' : 'pdf'}`)
}

// ---- KBR corpus ------------------------------------------------------------------
// What is actually in the rule index (per document) and how it is searched.
export async function fetchIndexStats() {
  return request('/api/kbr/index')
}

export async function fetchKbrDocuments() {
  const data = await request('/api/kbr/documents')
  if (!Array.isArray(data) || data.length === 0) return []
  // Chunk / page counts are real numbers from the index, never estimates. If
  // the index cannot be read the documents are still listed, with the counts
  // shown as unknown rather than guessed.
  let indexed = null
  try {
    const stats = await request('/api/kbr/index')
    if (stats && Array.isArray(stats.documents)) {
      indexed = Object.fromEntries(stats.documents.map((d) => [d.source, d]))
    }
  } catch (_) {
    indexed = null
  }
  return data.map((d) => {
    const entry = indexed ? indexed[d.filename] : undefined
    const known = indexed !== null
    return {
      doc: d.filename,
      type: /\.pdf$/i.test(d.filename) ? 'KBR (PDF)' : 'KBR (TXT)',
      pages: entry?.pages ?? '—',
      chunks: known ? String(entry?.chunks ?? 0) : '—',
      rules: known ? String(entry?.rules ?? 0) : '—',
      indexed: d.modified_at ? new Date(d.modified_at).toISOString().slice(0, 10) : '—',
      status: !known ? 'UNKNOWN' : entry?.chunks > 0 ? 'INDEXED' : 'NOT INDEXED',
    }
  })
}

export async function searchKbrRules(query, limit = 5, mode = 'hybrid') {
  const qs = `q=${encodeURIComponent(query)}&limit=${limit}&mode=${encodeURIComponent(mode)}`
  return request(`/api/rules/search?${qs}`)
}

// Ask the indexed rulebook a question. The backend answers only from retrieved
// excerpts, verifies every [n] citation, and abstains when the rules do not
// cover the question. Errors propagate (never a canned answer).
export async function askRulebook(question, topK) {
  const body = { question }
  if (topK) body.top_k = topK
  return postJson('/api/rules/ask', body)
}

export async function ingestRules(rebuild = false) {
  return postJson('/api/ingest', { rebuild })
}

export async function uploadKbrDocument(file) {
  const fd = new FormData()
  fd.append('file', file)
  return request('/api/kbr/upload', { method: 'POST', body: fd })
}

// ---- auth / 2FA ----------------------------------------------------------------------
// Unauthenticated calls (login, register, TOTP challenge) use fetch directly so a
// 401 here means "wrong credentials", not "session expired".
async function publicPost(path, body, fallbackMessage) {
  let res
  try {
    res = await fetch(endpoint(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (err) {
    throw new Error(isNetworkError(err) ? UNREACHABLE : err.message)
  }
  if (!res.ok) throw new Error((await errorDetail(res)) || `${fallbackMessage} (${res.status})`)
  return res.json()
}

export async function login({ email, password }) {
  return publicPost('/auth/login/json', { email, password }, 'Login failed') // TokenResponse | OtpRequiredResponse
}

// Turn a FastAPI error body into one readable sentence. Validation errors (422)
// arrive as a list of {msg}; pydantic prefixes custom messages with "Value error, ".
function registrationErrorMessage(status, body) {
  const detail = body?.detail
  if (status === 403) return 'Registration is by invitation only. Contact your administrator for an account.'
  if (status === 409) return 'An account with this email already exists. Try signing in.'
  if (status === 429) return 'Too many attempts. Please wait a minute and try again.'
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => String(d?.msg || '').replace(/^Value error,\s*/i, '')).filter(Boolean)
    if (msgs.length) return msgs.join('. ')
  }
  if (typeof detail === 'string' && detail) return detail
  return `Registration failed (${status})`
}

export async function registerUser({ email, password }) {
  let res
  try {
    res = await fetch(endpoint('/auth/register'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
  } catch (err) {
    throw new Error(isNetworkError(err) ? UNREACHABLE : err.message)
  }
  let body = null
  try {
    body = await res.json()
  } catch (_) {}
  if (!res.ok) throw new Error(registrationErrorMessage(res.status, body))
  return body
}

// What the sign-in UI may offer (e.g. whether to show "Create account").
// Returns null when unknown (backend unreachable / older backend): callers then
// show the option and let the server decide.
export async function fetchAuthConfig() {
  try {
    const res = await fetch(endpoint('/auth/config'))
    if (!res.ok) return null
    return await res.json()
  } catch (_) {
    return null
  }
}

export async function totpSetup() {
  return request('/auth/totp/setup', { method: 'POST' })
}

export async function totpEnable({ password, code }) {
  return postJson('/auth/totp/enable', { password, code })
}

export async function totpDisable({ password, code }) {
  return postJson('/auth/totp/disable', { password, code })
}

export async function totpStatus() {
  return request('/auth/totp/status')
}

// Complete a 2FA login. The challenge token goes in the body, not as a bearer.
export async function totpVerify({ otpToken, code }) {
  return publicPost('/auth/totp/verify', { otp_token: otpToken, code }, 'Verification failed')
}

export async function totpRecover({ otpToken, recoveryCode }) {
  return publicPost('/auth/totp/recover', { otp_token: otpToken, recovery_code: recoveryCode }, 'Recovery failed')
}

// ---- Google OAuth 2.0 ----------------------------------------------------------------
export async function getGoogleAuthUrl({ redirectUri } = {}) {
  const query = redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ''
  let res
  try {
    res = await fetch(endpoint(`/auth/google/url${query}`))
  } catch (err) {
    throw new Error(isNetworkError(err) ? UNREACHABLE : err.message)
  }
  if (!res.ok) throw new Error((await errorDetail(res)) || `Failed to initialize Google OAuth (${res.status})`)
  return res.json()
}

export async function googleCallbackLogin({ code, state, redirectUri } = {}) {
  return publicPost('/auth/google/callback', { code, state, redirect_uri: redirectUri }, 'Google sign in failed')
}

export async function googleTokenLogin({ credential }) {
  return publicPost('/auth/google/token', { credential }, 'Google token verification failed')
}
