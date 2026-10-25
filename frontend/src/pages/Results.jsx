import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter, ScoreRing, AnalysisTrace } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { toast } from '../components/Toast.jsx'
import { demoResponse, demoFactGrid, SEVERITY_META, STATUS_META, deriveStatus, downloadReport } from '../data.js'

function useResult() {
  const [resp, setResp] = useState(demoResponse)
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('chattam.result')
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed && Array.isArray(parsed.violations)) setResp({ ...demoResponse, ...parsed, trace: demoResponse.trace, score: demoResponse.score })
      }
    } catch {}
  }, [])
  return resp
}

function Excerpt({ text }) {
  const parts = text.split(/(minimum front setback shall not be less than 3 metres[^.]*\.)/i)
  return (
    <p className="text-xs leading-[1.8] text-[#a3a3a3] font-mono">
      {parts.map((p, i) =>
        /minimum front setback shall not be less than 3 metres/i.test(p) ? (
          <mark key={i} className="bg-white text-black px-1 font-bold">{p}</mark>
        ) : (
          <span key={i}>{p}</span>
        )
      )}
    </p>
  )
}

function EvidenceDrawer({ rule, onClose }) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  if (!rule) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="KBR Clause Evidence">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <aside className="relative w-full sm:w-[460px] h-full bg-[#0e0e0e] border-l border-[#262626] shadow-2xl flex flex-col fade-rise">
        <div className="px-6 py-4 border-b border-[#262626] flex items-center justify-between bg-[#121212]">
          <h3 className="text-xs font-bold text-white tracking-widest uppercase flex items-center gap-2 mono">
            <span className="w-1.5 h-1.5 bg-white inline-block" /> KBR Clause Evidence
          </h3>
          <button
            onClick={onClose}
            aria-label="Close evidence drawer"
            className="p-1 text-[#737373] hover:text-white border border-transparent hover:border-[#333333] transition-colors focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
          >
            <Icon name="x" className="text-base" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto scroll-mono p-6 space-y-6">
          <div className="grid grid-cols-2 gap-3 border border-[#262626] p-4 bg-[#121212]">
            {[['Rule Identifier', rule.rule_id || 'KBR-2019-SPEC'], ['Source File', rule.source], ['Section Reference', rule.page || 'Gazette Part B'], ['Cosine Score', `${rule.score >= 1 ? rule.score.toFixed(2) : rule.score}`]].map(([k, v]) => (
              <div key={k}>
                <div className="text-[9px] mono text-[#737373] uppercase tracking-wider mb-0.5">{k}</div>
                <div className="text-xs mono text-white break-words font-medium">{v}</div>
              </div>
            ))}
          </div>
          <div className="bg-[#121212] border border-[#262626] p-5">
            <div className="text-[9px] mono text-[#737373] uppercase tracking-wider mb-2 font-semibold">STATUTORY EXCERPT</div>
            <Excerpt text={rule.excerpt} />
          </div>
        </div>
        <div className="px-6 py-4 border-t border-[#262626] bg-[#121212]">
          <div className="text-[9px] mono text-[#737373] uppercase tracking-wider flex items-center gap-2">
            <span>●</span> Indexed in FAISS (NVIDIA Nemotron 1B Embeddings)
          </div>
        </div>
      </aside>
    </div>
  )
}

export default function Results() {
  const resp = useResult()
  const status = STATUS_META[deriveStatus(resp)]
  const [drawer, setDrawer] = useState(null)
  const ruleByRef = (ref) => resp.retrieved_rules.find((r) => (r.rule_id && ref.includes(r.rule_id)) || ref.includes(r.rule_id || '::')) || resp.retrieved_rules[0]

  return (
    <>
      <Header
        backLink="/"
        eyebrow="COMPLIANCE ASSESSMENT"
        title="Residential Building — Kakkanad"
        action={
          <div className="flex items-center gap-3">
            <button
              onClick={async () => {
                const id = resp.report_id || 1
                try {
                  toast('Generating official PDF assessment report…', 'ok')
                  await downloadReport(id, 'pdf')
                } catch (e) {
                  toast(`Export failed: ${e.message}`, 'danger')
                }
              }}
              className="bg-white text-black font-mono text-xs font-bold px-4 py-2 hover:bg-[#e5e5e5] flex items-center gap-2 border border-white cursor-pointer"
            >
              <Icon name="download" /> EXPORT AUDIT PDF
            </button>
            <Link
              to="/reports"
              className="px-3 py-2 text-xs mono text-[#a3a3a3] hover:text-white bg-[#0e0e0e] border border-[#333333] hover:border-white transition-colors flex items-center gap-1.5"
            >
              <Icon name="archive" /> ALL REPORTS
            </Link>
          </div>
        }
      />

      <div className="p-6 md:p-8 flex flex-col gap-6 bg-[#0a0a0a]">
        {/* Top Verdict Banner */}
        <div className="bg-[#121212] border border-[#262626] p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <Pill kind={status.pill}>{status.label}</Pill>
            </div>
            <h3 className="text-2xl md:text-3xl font-bold text-white uppercase tracking-tight font-sans">
              Structural & Zoning Compliance Results
            </h3>
            <p className="text-xs mono text-[#a3a3a3] flex items-center gap-2">
              <span className="text-white font-bold">[!]</span>
              <span>{resp.violations.length} regulatory deviations flagged against Kerala Panchayat Building Rules.</span>
            </p>
          </div>

          <div className="flex flex-col items-center gap-2 shrink-0 border border-[#262626] p-4 bg-[#0e0e0e]">
            <ScoreRing score={resp.score} color="#ffffff" />
            <span className="text-[9px] mono text-[#737373] tracking-widest uppercase font-semibold">OVERALL SCORE</span>
          </div>
        </div>

        {/* Findings + Extracted Facts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Findings (2 cols) */}
          <div className="lg:col-span-2 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-[#262626] pb-2">
              <h4 className="text-[10px] mono text-white uppercase tracking-widest font-bold">
                REGULATORY FINDINGS & VIOLATIONS ({resp.violations.length})
              </h4>
              <span className="text-[9px] mono text-[#737373]">AUDITED BY NEMOTRON 120B</span>
            </div>

            <div className="space-y-4">
              {resp.violations.map((v, i) => {
                const sm = SEVERITY_META[v.severity] || SEVERITY_META.info
                return (
                  <div key={i} className="bg-[#121212] border border-[#262626] p-5 space-y-4">
                    <div className="flex justify-between items-start gap-2">
                      <div className="flex gap-2.5 items-center flex-wrap">
                        <Pill kind={sm.pill}>{sm.label}</Pill>
                        <span className="text-xs mono text-white font-semibold">{v.rule_reference}</span>
                      </div>
                      <button
                        onClick={() => setDrawer(ruleByRef(v.rule_reference))}
                        className="text-[10px] mono text-white hover:underline flex items-center gap-1 border border-[#333333] px-2 py-1 bg-[#0a0a0a]"
                      >
                        INSPECT CLAUSE <Icon name="external-link" />
                      </button>
                    </div>

                    <h4 className="text-sm font-bold text-white font-sans">{v.title}</h4>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-[#0e0e0e] p-3 border border-[#262626]">
                        <div className="text-[9px] mono text-[#737373] uppercase tracking-wider mb-1">OBSERVED VALUE</div>
                        <div className="text-base mono text-white font-bold">{v.plan_value || 'not specified'}</div>
                      </div>
                      <div className="bg-[#0e0e0e] p-3 border border-[#262626]">
                        <div className="text-[9px] mono text-[#737373] uppercase tracking-wider mb-1">MANDATED BY KBR</div>
                        <div className="text-base mono text-white font-bold underline">{v.required_value || '—'}</div>
                      </div>
                    </div>

                    <p className="text-xs text-[#a3a3a3] leading-relaxed font-sans">{v.description}</p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right Rail: Extracted Facts & Trace (1 col) */}
          <div className="flex flex-col gap-6">
            <div>
              <div className="flex items-center justify-between border-b border-[#262626] pb-2 mb-4">
                <h4 className="text-[10px] mono text-white uppercase tracking-widest font-bold">
                  EXTRACTED FACTS
                </h4>
                <span className="text-[9px] mono text-[#737373]">PARAMETERS</span>
              </div>
              <div className="bg-[#121212] border border-[#262626] p-4">
                <div className="divide-y divide-[#262626]">
                  {demoFactGrid.map((f) => (
                    <div key={f.label} className="flex justify-between items-center py-2 text-xs mono">
                      <span className="text-[#a3a3a3]">{f.label}</span>
                      <div className="text-right">
                        <span className="text-white font-semibold">{f.value}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <AnalysisTrace trace={resp.trace} />
          </div>
        </div>
      </div>

      {drawer && <EvidenceDrawer rule={drawer} onClose={() => setDrawer(null)} />}
      <AppFooter />
    </>
  )
}
