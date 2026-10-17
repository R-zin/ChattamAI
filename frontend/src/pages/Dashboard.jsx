import React from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { checks, STATUS_META } from '../data.js'

export default function Dashboard() {
  const metricCards = [
    { label: 'TOTAL CHECKS', value: '142', sub: '+18 THIS WEEK', tag: 'CH.IV' },
    { label: 'COMPLIANCE RATE', value: '88.4%', sub: '84.1% FIRST-PASS', tag: 'RATIO' },
    { label: 'OPEN VIOLATIONS', value: '12', sub: '8 SETBACK • 3 COVERAGE', tag: 'AUDIT' },
    { label: 'INDEXED KBR RULES', value: '595', sub: 'CH. IV–X • GAZETTE 2024', tag: 'FAISS' },
  ]

  return (
    <>
      <Header
        eyebrow="OPERATIONAL DASHBOARD // ARCHITECTURAL COMPLIANCE"
        title="KBR 2019 Compliance Engine"
        subtitle="Automated zoning, setback, and FAR verification against Kerala Municipality Building Rules"
        action={
          <Link
            to="/new-check"
            className="bg-white text-black px-4 py-2 text-xs mono font-bold hover:bg-[#e5e5e5] transition-all flex items-center gap-2 border border-white"
          >
            <Icon name="plus" className="text-base" />
            <span>+ NEW COMPLIANCE CHECK</span>
          </Link>
        }
      />

      <div className="p-6 md:p-8 space-y-6">
        {/* Architectural Context Banner */}
        <div className="border border-[#262626] p-6 bg-[#121212] flex flex-col lg:flex-row justify-between lg:items-center gap-6">
          <div className="max-w-3xl space-y-2">
            <div className="flex items-center gap-3">
              <span className="border border-white px-2 py-0.5 text-[9px] mono font-bold uppercase tracking-wider text-white">
                REGULATION MATRIX
              </span>
              <span className="text-[11px] mono text-[#a3a3a3]">
                KERALA GAZETTE EXTRAORDINARY // KBR 2019 (AMENDED)
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white uppercase font-sans">
              Architectural Compliance & Building Rule Audit
            </h1>
            <p className="text-xs text-[#a3a3a3] leading-relaxed max-w-2xl font-sans">
              Automated verification for setback calculations, FAR/FSI limits, access road widths, parking allocations, and fire safety provisions powered by NVIDIA Nemotron 120B reasoning and 2048-dim vector retrieval.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <Link
              to="/new-check"
              className="bg-white text-black font-mono text-xs font-bold px-4 py-2.5 border border-white hover:bg-[#e5e5e5] transition-colors flex items-center gap-2"
            >
              <Icon name="plus" />
              <span>SUBMIT PLAN TEXT</span>
            </Link>
            <Link
              to="/new-check"
              className="bg-[#0a0a0a] text-white border border-[#404040] hover:border-white font-mono text-xs px-4 py-2.5 hover:bg-[#181818] transition-colors flex items-center gap-2"
            >
              <Icon name="upload" />
              <span>UPLOAD PDF / DXF</span>
            </Link>
          </div>
        </div>

        {/* 4 Architectural Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {metricCards.map((m) => (
            <div key={m.label} className="border border-[#262626] bg-[#121212] p-5 flex flex-col justify-between">
              <div className="flex justify-between items-start">
                <span className="text-[10px] mono text-[#737373] tracking-widest uppercase font-semibold">{m.label}</span>
                <span className="text-[9px] mono text-[#a3a3a3] border border-[#262626] px-1.5 py-0.5">{m.tag}</span>
              </div>
              <div className="my-3">
                <div className="text-3xl font-bold mono text-white tracking-tight">{m.value}</div>
              </div>
              <div className="text-[10px] mono text-[#a3a3a3] pt-2 border-t border-[#262626]/80 flex items-center justify-between">
                <span>{m.sub}</span>
                <span className="text-white">→</span>
              </div>
            </div>
          ))}
        </div>

        {/* Main Split Grid: Recent Checks Table & Telemetry Side Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Recent Checks Table (8 cols) */}
          <div className="lg:col-span-8 border border-[#262626] bg-[#121212] overflow-hidden flex flex-col">
            <div className="px-5 py-3.5 border-b border-[#262626] flex items-center justify-between bg-[#181818]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-white inline-block" />
                <h3 className="text-xs mono font-bold text-white tracking-widest uppercase">
                  ACTIVE & RECENT ASSESSMENTS [05 RECORDS]
                </h3>
              </div>
              <div className="text-[10px] mono text-[#737373]">SORTED BY RECENCY</div>
            </div>

            <div className="overflow-x-auto flex-1">
              <table className="w-full min-w-[720px] text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#262626] bg-[#0e0e0e]">
                    {['Project Ref & Name', 'Plan File', 'Status', 'Violations', 'Rules', 'Timestamp', 'Action'].map((h, i) => (
                      <th
                        key={h}
                        className={`px-4 py-3 text-[10px] mono text-[#737373] uppercase tracking-wider font-semibold ${
                          i === 6 ? 'text-right' : 'text-left'
                        }`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#262626]">
                  {checks.map((c) => {
                    const s = STATUS_META[c.status]
                    const to = c.status === 'insufficient' ? '/results/insufficient' : '/results/demo'
                    return (
                      <tr key={c.id} className="hover:bg-[#181818] transition-colors group">
                        <td className="px-4 py-3.5">
                          <div className="text-xs font-semibold text-white group-hover:text-white">{c.project}</div>
                          <div className="text-[9px] mono text-[#737373] uppercase tracking-wider">REF // {c.id.toUpperCase()}-2026</div>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="text-[11px] mono text-[#a3a3a3] border border-[#262626] px-1.5 py-0.5 bg-[#0a0a0a]">
                            {c.plan}
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          <Pill kind={s.pill}>{s.label}</Pill>
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-white">
                          {c.violations === null ? (
                            <span className="text-[#737373]">—</span>
                          ) : c.violations > 0 ? (
                            <span className="font-bold underline">{c.violations} FLAGGED</span>
                          ) : (
                            <span className="text-[#a3a3a3]">0 CLEAN</span>
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-[#a3a3a3]">{c.rules} CHUNKS</td>
                        <td className="px-4 py-3.5 text-[10px] mono text-[#737373]">{c.analyzed}</td>
                        <td className="px-4 py-3.5 text-right">
                          <Link
                            to={to}
                            className="text-[10px] mono font-bold text-white hover:underline border border-[#404040] hover:border-white px-2 py-1 bg-[#0a0a0a]"
                          >
                            INSPECT →
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="px-5 py-3 bg-[#0e0e0e] flex items-center justify-between border-t border-[#262626]">
              <div className="text-[9px] mono text-[#737373] flex items-center gap-2">
                <span>[NOTE]</span>
                <span>AI-assisted zoning assessments require official confirmation by a licensed LSGD engineer.</span>
              </div>
            </div>
          </div>

          {/* Right Side Telemetry Panel (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            {/* Vector Store Telemetry */}
            <div className="border border-[#262626] bg-[#121212] p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#262626] pb-3">
                <span className="text-[10px] mono font-bold text-white tracking-widest uppercase">
                  VECTOR STORE TELEMETRY
                </span>
                <span className="text-[9px] mono text-white border border-white px-1.5 py-0.5">ACTIVE</span>
              </div>
              <div className="space-y-2.5 text-xs mono">
                <div className="flex justify-between items-center py-1 border-b border-[#262626]/60">
                  <span className="text-[#737373]">RULEBOOK</span>
                  <span className="text-white">KBR 2019 (Kerala Gazette)</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-[#262626]/60">
                  <span className="text-[#737373]">EMBED MODEL</span>
                  <span className="text-white">nvidia/nemotron-3-embed-1b</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-[#262626]/60">
                  <span className="text-[#737373]">VECTOR DIM</span>
                  <span className="text-white">2048-dim Dense Float32</span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-[#737373]">INDEXED NODES</span>
                  <span className="text-white font-bold">595 Chunks Loaded</span>
                </div>
              </div>
            </div>

            {/* Recent Regulatory Notifications */}
            <div className="border border-[#262626] bg-[#121212] p-5 space-y-3">
              <span className="text-[10px] mono font-bold text-white tracking-widest uppercase block border-b border-[#262626] pb-2">
                GAZETTE AMENDMENTS (KBR 2019)
              </span>
              <div className="space-y-3 text-xs">
                <div className="border-l-2 border-white pl-3 py-0.5">
                  <div className="text-[10px] mono text-[#a3a3a3]">S.R.O. NO. 812/2024</div>
                  <div className="text-white font-medium text-xs mt-0.5">Front open space relaxation for plots abutting &lt; 7m roads.</div>
                </div>
                <div className="border-l-2 border-[#737373] pl-3 py-0.5">
                  <div className="text-[10px] mono text-[#a3a3a3]">CHAPTER XVI REVISION</div>
                  <div className="text-[#d4d4d4] font-medium text-xs mt-0.5">Rainwater harvesting and solar rooftop mandates for built-up &gt; 300 m².</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <AppFooter extra="NVIDIA NIM INFERENCE LATENCY: 42ms" />
    </>
  )
}
