import React, { useState } from 'react'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'

const EVENTS = [
  { ts: '2026-08-12 14:22', label: 'Analysis completed', detail: "'Residential Building — Kakkanad' flagged '3 potential issues'", tone: 'var(--warn)', cat: 'Analyses' },
  { ts: '2026-08-12 14:20', label: 'Plan uploaded', detail: "'plan_014.pdf'", tone: 'var(--accent)', cat: 'Analyses' },
  { ts: '2026-08-11 09:47', label: 'Analysis completed', detail: "'Commercial Complex — Kochi' flagged '5 potential issues'", tone: 'var(--warn)', cat: 'Analyses' },
  { ts: '2026-08-02 09:14', label: 'Ingestion complete', detail: '+512 chunks from KBR Amendment 2021.pdf', tone: 'var(--ok)', cat: 'Ingestions' },
  { ts: '2026-08-02 09:10', label: 'Ingestion started', detail: "'KBR Amendment 2021.pdf'", tone: 'var(--accent)', cat: 'Ingestions' },
  { ts: '2026-08-01 18:02', label: 'Model switched', detail: 'analysis model set to claude-3-5-sonnet-20241022', tone: 'var(--info)', cat: 'System' },
  { ts: '2026-07-28 10:41', label: 'Report exported', detail: "'Apartment Block — Thiruvananthapuram (PDF)'", tone: 'var(--ok)', cat: 'Exports' },
]
const FILTERS = ['All', 'Analyses', 'Ingestions', 'Exports', 'System']

export default function Activity() {
  const [f, setF] = useState('All')
  const shown = EVENTS.filter((e) => f === 'All' || e.cat === f)
  return (
    <>
      <Header eyebrow="Operational Logs" title="Activity" subtitle="System and analysis events across your workspace" />
      <div className="p-6 md:p-8 space-y-6">
        <div className="flex gap-2 flex-wrap">
          {FILTERS.map((x) => (
            <button key={x} onClick={() => setF(x)} className={`px-3 py-1.5 rounded text-xs mono border transition-all ${f === x ? 'border-[#22D3EE] text-[#22D3EE] bg-[#22D3EE]/10' : 'border-[#222C3A] text-[#9AA7B6] hover:text-white'}`}>
              {x}
            </button>
          ))}
        </div>
        <div className="max-w-3xl bg-[#10151C] border border-[#222C3A] rounded p-6 relative">
          <div className="absolute left-[37px] top-8 bottom-8 w-px bg-[#222C3A]" />
          <div className="space-y-6">
            {shown.map((e, i) => (
              <div key={i} className="flex gap-5 items-start relative z-10 fade-rise">
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1 border-2 border-[#10151C]" style={{ background: e.tone, boxShadow: `0 0 8px ${e.tone}` }} />
                <div className="min-w-0">
                  <div className="flex items-baseline gap-3 flex-wrap">
                    <span className="text-sm text-white">{e.label}</span>
                    <span className="text-[10px] mono text-[#5B6879]">{e.ts}</span>
                  </div>
                  <div className="text-xs mono text-[#9AA7B6] mt-0.5 break-words">{e.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="text-[10px] mono text-[#5B6879]">Derived from session events — not persisted server-side.</div>
      </div>
      <AppFooter extra="LATENCY: 420ms" />
    </>
  )
}
