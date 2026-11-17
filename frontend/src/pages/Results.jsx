import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import VerificationAuditBadge from '../components/VerificationAuditBadge.jsx'
import { toast } from '../components/Toast.jsx'
import { EmptyState } from '../components/ui/index.js'
import {
  SEVERITY_META,
  STATUS_META,
  GROUNDING_META,
  COVERAGE_META,
  COVERAGE_GAP_REASON,
  deriveStatus,
  downloadReport,
  fetchReport,
} from '../data.js'

const isResult = (x) => x && Array.isArray(x.violations)

// The assessment to show: a persisted report when the URL carries an id,
// otherwise the result of the check that was just run (kept in sessionStorage).
function useResult(id) {
  const [state, setState] = useState({ loading: !!id, resp: null, error: null })
  useEffect(() => {
    let active = true
    if (id) {
      setState({ loading: true, resp: null, error: null })
      fetchReport(id)
        .then((r) => active && setState({ loading: false, resp: isResult(r) ? r : null, error: null }))
        .catch((err) => active && setState({ loading: false, resp: null, error: err.message }))
    } else {
      let resp = null
      try {
        const parsed = JSON.parse(sessionStorage.getItem('chattam.result') || 'null')
        if (isResult(parsed)) resp = parsed
      } catch {}
      setState({ loading: false, resp, error: null })
    }
    return () => {
      active = false
    }
  }, [id])
  return state
}

// "front setback: 1m" -> ["front setback", "1m"]; free text stays whole.
function splitFact(fact) {
  const s = String(fact)
  const i = s.indexOf(':')
  return i > 0 ? [s.slice(0, i).trim(), s.slice(i + 1).trim()] : [null, s]
}

// Whether the finding's cited rule was actually among the retrieved excerpts.
function GroundingBadge({ item }) {
  if (!item) return null
  const meta = GROUNDING_META[item.status]
  if (!meta) return null
  return (
    <span title={item.note || meta.hint}>
      <Pill kind={meta.pill} dot={false}>
        <span aria-hidden="true">{meta.glyph}</span> {meta.label}
      </Pill>
    </span>
  )
}

// Which regulated topics in the plan had a rule retrieved, and which did not.
function CoveragePanel({ retrieval }) {
  const coverage = Array.isArray(retrieval?.coverage) ? retrieval.coverage : []
  if (coverage.length === 0) return null
  const gaps = coverage.filter((c) => c.status === 'gap')
  return (
    <section aria-labelledby="coverage-heading">
      <div className="flex items-center justify-between border-b border-line pb-2 mb-4">
        <h4 id="coverage-heading" className="text-[10px] mono text-ink uppercase tracking-widest font-bold">
          RULE COVERAGE
        </h4>
        <span className="text-[9px] mono text-ink-3">
          {coverage.length - gaps.length}/{coverage.length} TOPICS
        </span>
      </div>
      <div className="bg-surface border border-line p-4 space-y-3">
        <ul className="divide-y divide-line">
          {coverage.map((c) => {
            const meta = COVERAGE_META[c.status] || COVERAGE_META.gap
            return (
              <li key={c.topic} className="py-2.5 space-y-1.5">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-xs text-ink font-semibold">{c.label}</span>
                  <Pill kind={meta.pill} dot={false}>
                    <span aria-hidden="true">{meta.glyph}</span> {meta.label}
                  </Pill>
                </div>
                <div className="text-[10px] mono text-ink-2">
                  {c.status === 'gap'
                    ? COVERAGE_GAP_REASON[c.reason] || 'No rule was retrieved for this topic.'
                    : (c.rule_ids || []).join(' · ')}
                </div>
              </li>
            )
          })}
        </ul>
        {gaps.length > 0 && (
          <p className="text-[11px] text-ink-2 border-t border-line pt-3">
            Topics without a retrieved rule were <strong className="text-ink">not assessed</strong>. They are not
            confirmed compliant.
          </p>
        )}
      </div>
    </section>
  )
}

function EvidenceDrawer({ rule, onClose }) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  if (!rule) return null
  const section = [rule.section, rule.page ? (typeof rule.page === 'number' ? `p. ${rule.page}` : rule.page) : null]
    .filter(Boolean)
    .join(' · ')
  const score = typeof rule.score === 'number' ? rule.score.toFixed(2) : '—'
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="KBR Clause Evidence">
      <div className="absolute inset-0 bg-scrim backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <aside className="relative w-full sm:w-[460px] h-full bg-inset border-l border-line shadow-2xl flex flex-col fade-rise">
        <div className="px-6 py-4 border-b border-line flex items-center justify-between bg-surface">
          <h3 className="text-xs font-bold text-ink tracking-widest uppercase flex items-center gap-2 mono">
            <span className="w-1.5 h-1.5 bg-accent inline-block" /> KBR Clause Evidence
          </h3>
          <button
            onClick={onClose}
            aria-label="Close evidence drawer"
            className="p-1 text-ink-3 hover:text-ink border border-transparent hover:border-line transition-colors focus-visible:ring-1 focus-visible:ring-accent focus-visible:outline-none"
          >
            <Icon name="x" className="text-base" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto scroll-mono p-6 space-y-6">
          <div className="grid grid-cols-2 gap-3 border border-line p-4 bg-surface">
            {[
              ['Rule Identifier', rule.rule_id || '—'],
              ['Source File', rule.source || '—'],
              ['Section Reference', section || '—'],
              ['Relevance Score', score],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="text-[9px] mono text-ink-3 uppercase tracking-wider mb-0.5">{k}</div>
                <div className="text-xs mono text-ink break-words font-medium">{v}</div>
              </div>
            ))}
          </div>
          <div className="bg-surface border border-line p-5">
            <div className="text-[9px] mono text-ink-3 uppercase tracking-wider mb-2 font-semibold">STATUTORY EXCERPT</div>
            <p className="text-xs leading-[1.8] text-ink-2 font-mono whitespace-pre-wrap">{rule.excerpt}</p>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-line bg-surface">
          <div className="text-[9px] mono text-ink-3 uppercase tracking-wider">
            Retrieved from the indexed KBR corpus. Verify against the gazetted rules before acting.
          </div>
        </div>
      </aside>
    </div>
  )
}

export default function Results() {
  const { id } = useParams()
  const nav = useNavigate()
  const { loading, resp, error } = useResult(id)
  const [drawer, setDrawer] = useState(null)

  if (loading || error || !resp) {
    return (
      <>
        <Header backLink="/" eyebrow="COMPLIANCE ASSESSMENT" title="Assessment Results" />
        <div className="p-6 md:p-8 bg-bg">
          {loading ? (
            <div className="text-xs mono text-ink-3">Loading assessment…</div>
          ) : (
            <EmptyState
              icon="file-text"
              eyebrow={error ? 'COULD NOT LOAD REPORT' : 'NO ASSESSMENT'}
              title={error ? error : 'No assessment to show'}
              description={
                error
                  ? 'The report could not be retrieved. It may have been removed, or belong to another account.'
                  : 'Run a compliance check, or open a past assessment from Reports.'
              }
              actionLabel="START NEW COMPLIANCE CHECK"
              actionIcon="plus"
              onAction={() => nav('/new-check')}
            />
          )}
        </div>
        <AppFooter />
      </>
    )
  }

  const status = STATUS_META[deriveStatus(resp)]
  const rules = resp.retrieved_rules || []
  const facts = resp.extracted_facts || []
  const reportId = resp.report_id ?? id ?? null
  const groundingByIndex = Object.fromEntries(
    (resp.grounding?.items || []).map((item) => [item.violation_index, item])
  )
  // Prefer the excerpt the grounding check matched to this finding; fall back
  // to matching the rule id in the reference text. No match -> no drawer.
  const ruleForFinding = (v, i) => {
    const cited = groundingByIndex[i]?.citations?.[0]
    if (cited && rules[cited - 1]) return rules[cited - 1]
    const ref = v.rule_reference || ''
    return rules.find((r) => r.rule_id && ref.includes(r.rule_id)) || null
  }

  return (
    <>
      <Header
        backLink="/"
        eyebrow="COMPLIANCE ASSESSMENT"
        title={reportId ? `Assessment #${reportId}` : 'Assessment Results'}
        action={
          <div className="flex items-center gap-3">
            {reportId && (
              <button
                onClick={async () => {
                  try {
                    toast('Generating PDF assessment report…', 'ok')
                    await downloadReport(reportId, 'pdf')
                  } catch (e) {
                    toast(`Export failed: ${e.message}`, 'danger')
                  }
                }}
                className="bg-accent text-on-accent font-mono text-xs font-bold px-4 py-2 hover:bg-accent-strong flex items-center gap-2 border border-ink cursor-pointer"
              >
                <Icon name="download" /> EXPORT AUDIT PDF
              </button>
            )}
            <Link
              to="/reports"
              className="px-3 py-2 text-xs mono text-ink-2 hover:text-ink bg-inset border border-line hover:border-ink transition-colors flex items-center gap-1.5"
            >
              <Icon name="archive" /> ALL REPORTS
            </Link>
          </div>
        }
      />

      <div className="p-6 md:p-8 flex flex-col gap-6 bg-bg">
        {/* Verdict Banner */}
        <div className="bg-surface border border-line p-6 md:p-8 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <Pill kind={status.pill}>{status.label}</Pill>
            {resp.verification && <VerificationAuditBadge verification={resp.verification} />}
          </div>
          <h3 className="text-2xl md:text-3xl font-bold text-ink uppercase tracking-tight font-sans">
            Structural & Zoning Compliance Results
          </h3>
          <p className="text-xs mono text-ink-2">
            {resp.violations.length} potential deviation{resp.violations.length === 1 ? '' : 's'} flagged against the
            retrieved Kerala Building Rules.
          </p>
          {resp.summary && (
            <p className="text-sm text-ink leading-relaxed font-sans whitespace-pre-wrap">{resp.summary}</p>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Findings (2 cols) */}
          <div className="lg:col-span-2 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-line pb-2">
              <h4 className="text-[10px] mono text-ink uppercase tracking-widest font-bold">
                REGULATORY FINDINGS ({resp.violations.length})
              </h4>
            </div>

            {resp.violations.length === 0 && (
              <div className="bg-surface border border-line p-5 text-xs mono text-ink-2">
                No violations were found against the rules retrieved for this plan.
              </div>
            )}

            <div className="space-y-4">
              {resp.violations.map((v, i) => {
                const sm = SEVERITY_META[v.severity] || SEVERITY_META.info
                const rule = ruleForFinding(v, i)
                return (
                  <div key={i} className="bg-surface border border-line p-5 space-y-4">
                    <div className="flex justify-between items-start gap-2">
                      <div className="flex gap-2.5 items-center flex-wrap">
                        <Pill kind={sm.pill}>{sm.label}</Pill>
                        <span className="text-xs mono text-ink font-semibold">{v.rule_reference}</span>
                        <GroundingBadge item={groundingByIndex[i]} />
                      </div>
                      {rule && (
                        <button
                          onClick={() => setDrawer(rule)}
                          className="text-[10px] mono text-ink hover:underline flex items-center gap-1 border border-line px-2 py-1 bg-bg"
                        >
                          INSPECT CLAUSE <Icon name="external-link" />
                        </button>
                      )}
                    </div>

                    {v.title && <h4 className="text-sm font-bold text-ink font-sans">{v.title}</h4>}

                    {(v.plan_value || v.required_value) && (
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-inset p-3 border border-line">
                          <div className="text-[9px] mono text-ink-3 uppercase tracking-wider mb-1">OBSERVED VALUE</div>
                          <div className="text-base mono text-ink font-bold">{v.plan_value || 'not specified'}</div>
                        </div>
                        <div className="bg-inset p-3 border border-line">
                          <div className="text-[9px] mono text-ink-3 uppercase tracking-wider mb-1">REQUIRED BY KBR</div>
                          <div className="text-base mono text-ink font-bold underline">{v.required_value || '—'}</div>
                        </div>
                      </div>
                    )}

                    <p className="text-xs text-ink-2 leading-relaxed font-sans">{v.description}</p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right rail: extracted facts, coverage, retrieved rules */}
          <div className="flex flex-col gap-6">
            <div>
              <div className="flex items-center justify-between border-b border-line pb-2 mb-4">
                <h4 className="text-[10px] mono text-ink uppercase tracking-widest font-bold">EXTRACTED FACTS</h4>
                <span className="text-[9px] mono text-ink-3">{facts.length}</span>
              </div>
              <div className="bg-surface border border-line p-4">
                {facts.length === 0 ? (
                  <div className="text-xs mono text-ink-3">No facts were extracted from the plan.</div>
                ) : (
                  <div className="divide-y divide-line">
                    {facts.map((f, i) => {
                      const [label, value] = splitFact(f)
                      return (
                        <div key={i} className="flex justify-between items-center gap-3 py-2 text-xs mono">
                          {label && <span className="text-ink-2 capitalize">{label}</span>}
                          <span className={`text-ink font-semibold ${label ? 'text-right' : ''}`}>{value}</span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            <CoveragePanel retrieval={resp.retrieval} />

            <div>
              <div className="flex items-center justify-between border-b border-line pb-2 mb-4">
                <h4 className="text-[10px] mono text-ink uppercase tracking-widest font-bold">RETRIEVED RULES</h4>
                <span className="text-[9px] mono text-ink-3">{rules.length}</span>
              </div>
              <div className="space-y-2">
                {rules.length === 0 && (
                  <div className="bg-surface border border-line p-4 text-xs mono text-ink-3">
                    No rules were retrieved for this plan.
                  </div>
                )}
                {rules.map((r, i) => (
                  <button
                    key={i}
                    onClick={() => setDrawer(r)}
                    className="w-full text-left bg-surface border border-line hover:border-ink p-3 transition-colors"
                  >
                    <div className="flex justify-between gap-2 text-[10px] mono">
                      <span className="text-ink font-bold">{r.rule_id || r.source}</span>
                      {typeof r.score === 'number' && <span className="text-ink-3">{r.score.toFixed(2)}</span>}
                    </div>
                    <div className="text-[11px] text-ink-2 mt-1 line-clamp-2">{r.excerpt}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {drawer && <EvidenceDrawer rule={drawer} onClose={() => setDrawer(null)} />}
      <AppFooter />
    </>
  )
}
