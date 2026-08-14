import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter, ScoreRing, AnalysisTrace } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { demoResponse, demoFactGrid, SEVERITY_META, STATUS_META, deriveStatus } from '../data.js'

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

// Highlight the key sentence (the one containing "3 metres") in cyan.
function Excerpt({ text }) {
  const parts = text.split(/(minimum front setback shall not be less than 3 metres[^.]*\.)/i)
  return (
    <p className="text-sm leading-[1.7] text-[#9AA7B6]">
      {parts.map((p, i) =>
        /minimum front setback shall not be less than 3 metres/i.test(p) ? (
          <mark key={i} className="bg-[#22D3EE]/15 text-[#E7ECF2] px-1 rounded-sm">{p}</mark>
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
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <aside className="relative w-full sm:w-[420px] h-full bg-[#10151C]/95 backdrop-blur-xl border-l border-[#222C3A] shadow-2xl flex flex-col fade-rise">
        <div className="px-6 py-5 border-b border-[#222C3A] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white tracking-wide uppercase flex items-center gap-2">
            <Icon name="book-open" className="text-[#22D3EE]" /> KBR Evidence
          </h3>
          <button onClick={onClose} className="p-1.5 text-[#5B6879] hover:text-white hover:bg-[#161D27] rounded transition-colors">
            <Icon name="x" className="text-lg" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto scroll-mono p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            {[['Rule ID', rule.rule_id || '—'], ['Document', rule.source], ['Page', rule.page || 'p. —'], ['Relevance', `${rule.score >= 1 ? rule.score.toFixed(2) : rule.score}`]].map(([k, v]) => (
              <div key={k}>
                <div className="text-[9px] mono text-[#5B6879] uppercase tracking-wider mb-1">{k}</div>
                <div className="text-xs mono text-white break-words">{v}</div>
              </div>
            ))}
          </div>
          <div className="bg-[#1C2533]/50 border border-[#222C3A] rounded p-5">
            <Excerpt text={rule.excerpt} />
          </div>
        </div>
        <div className="px-6 py-4 border-t border-[#222C3A]">
          <div className="text-[10px] mono text-[#5B6879] uppercase tracking-wider flex items-center gap-2">
            <Icon name="database" className="text-[#22D3EE]" /> Retrieved from KBR Knowledge Base
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
        eyebrow={<>Compliance Assessment <span className="text-[#22D3EE]/60">— AI-ASSISTED ASSESSMENT • ENGINEER REVIEW REQUIRED</span></>}
        title="Residential Building — Kakkanad"
        action={
          <Link to="/reports" className="accent-gradient px-4 py-2 rounded text-sm font-semibold text-black hover:brightness-110 flex items-center gap-2">
            <Icon name="download" /> Download Report
          </Link>
        }
      />

      <div className="p-6 md:p-8 flex flex-col gap-6">
        {/* Top assessment */}
        <div className="bg-[#10151C] border border-[#222C3A] p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-8 rounded shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-5"><Icon name="shield-alert" className="text-8xl" /></div>
          <div>
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <Pill kind={status.pill}>{status.label}</Pill>
              <span className="text-xs text-[#5B6879] mono">ASSESSMENT ID: KBR-2026-0812-14</span>
            </div>
            <h3 className="text-3xl md:text-4xl font-light text-white mb-2 tracking-tight">Structural Compliance Results</h3>
            <p className="text-[#9AA7B6] flex items-center gap-2">
              <Icon name="alert-triangle" className="text-amber-500" />
              <span className="mono" style={{ color: status.color }}>{resp.violations.length}</span> potential issues detected in the submitted site plan.
            </p>
          </div>
          <div className="flex flex-col items-center gap-3">
            <ScoreRing score={resp.score} color={status.color} />
            <span className="text-[10px] mono text-[#5B6879] tracking-wider">OVERALL SCORE</span>
          </div>
        </div>

        {/* Findings + side rail */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 flex flex-col gap-4">
            <h4 className="text-xs mono text-[#5B6879] uppercase tracking-widest">Regulatory Findings</h4>
            <div className="space-y-4">
              {resp.violations.map((v, i) => {
                const sm = SEVERITY_META[v.severity] || SEVERITY_META.info
                return (
                  <div key={i} className={`bg-[#161D27] border border-[#222C3A] rounded-lg p-6 transition-colors group hover:border-opacity-60`} style={{}}>
                    <div className="flex justify-between items-start mb-4 gap-2">
                      <div className="flex gap-3 items-center flex-wrap">
                        <Pill kind={sm.pill}>{sm.label} SEVERITY</Pill>
                        <span className="text-xs mono text-[#9AA7B6]">{v.rule_reference}</span>
                      </div>
                      <button onClick={() => setDrawer(ruleByRef(v.rule_reference))} className="text-[10px] mono text-[#22D3EE] flex items-center gap-1 hover:underline flex-shrink-0">
                        VIEW KBR SOURCE <Icon name="external-link" />
                      </button>
                    </div>
                    <h4 className="text-lg font-medium text-white mb-4">{v.title}</h4>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="bg-[#0A0E13] p-3 rounded border border-[#222C3A]">
                        <div className="text-[10px] mono text-[#5B6879] mb-1">OBSERVED</div>
                        <div className="text-xl mono text-white">{v.plan_value || 'not specified'}</div>
                      </div>
                      <div className="bg-[#0A0E13] p-3 rounded border border-[#222C3A]">
                        <div className="text-[10px] mono text-[#5B6879] mb-1">REQUIRED</div>
                        <div className="text-xl mono text-[#34D399]">{v.required_value || '—'}</div>
                      </div>
                    </div>
                    <p className="text-sm text-[#9AA7B6] leading-relaxed">{v.description}</p>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="flex flex-col gap-6">
            <div>
              <h4 className="text-xs mono text-[#5B6879] uppercase tracking-widest mb-4">Extracted Facts</h4>
              <div className="bg-[#10151C] border border-[#222C3A] rounded-lg p-6">
                <div className="space-y-0">
                  {demoFactGrid.map((f, i) => (
                    <div key={f.label} className={`flex justify-between items-center py-2 ${i < demoFactGrid.length - 1 ? 'border-b border-[#222C3A]/50' : ''}`}>
                      <span className="text-xs text-[#9AA7B6]">{f.label}</span>
                      <div className="text-right">
                        <div className="text-xs mono text-white">{f.value}</div>
                        <div className={`text-[9px] mono ${f.conf >= 95 ? 'text-[#34D399]' : 'text-amber-500'}`}>{f.conf}% CONF</div>
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
      <AppFooter extra="LATENCY: 7240ms" />
    </>
  )
}
