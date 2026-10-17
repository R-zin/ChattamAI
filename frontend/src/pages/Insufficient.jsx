import React from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter, AnalysisTrace } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'

const PIPE = [
  { name: 'Parse', icon: 'upload', state: 'done' },
  { name: 'Retrieve', icon: 'search', state: 'warn' },
  { name: 'Analyze', icon: 'brain-circuit', state: 'skip' },
  { name: 'Report', icon: 'file-check', state: 'skip' },
]

export default function Insufficient() {
  return (
    <>
      <Header
        eyebrow="AUDIT NOTICE // RETRIEVAL DEFICIT"
        title="Compliance Assessment"
        subtitle="Villa Extension — Kozhikode"
      />

      <div className="flex-1 flex items-center justify-center p-6 md:p-12 bg-[#0a0a0a]">
        <div className="max-w-2xl w-full bg-[#121212] border border-[#262626] p-8 md:p-10 text-center shadow-2xl">
          <div className="mx-auto w-14 h-14 border border-white bg-[#0e0e0e] flex items-center justify-center mb-5">
            <Icon name="alert-triangle" className="text-2xl text-white" />
          </div>

          <Pill kind="pill-insufficient">INSUFFICIENT EVIDENCE</Pill>

          <h3 className="text-xl md:text-2xl font-bold text-white mt-4 mb-3 font-sans uppercase tracking-tight">
            Insufficient Evidence for Statutory Assessment
          </h3>
          <p className="text-xs mono text-[#a3a3a3] leading-relaxed mb-6 max-w-lg mx-auto">
            The vector retrieval pipeline returned zero confident KBR rule nodes for the submitted plan. This occurs when building dimensions, setbacks, or occupancy categories are too sparse for extraction.
          </p>

          <div className="inline-block bg-[#0e0e0e] border border-[#262626] px-4 py-2 mb-8">
            <span className="mono text-xs text-[#a3a3a3]">KBR Rules Retrieved: <span className="text-white font-bold">0 CHUNKS</span></span>
          </div>

          {/* Minimalist pipeline */}
          <div className="flex items-center justify-center gap-0 mb-8">
            {PIPE.map((p, i) => (
              <React.Fragment key={p.name}>
                {i > 0 && <div className={`w-8 h-px ${PIPE[i-1].state === 'done' ? 'bg-white' : 'bg-[#262626]'}`} />}
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 flex items-center justify-center border ${
                    p.state === 'done' ? 'border-white bg-white text-black' : p.state === 'warn' ? 'border-white bg-[#0e0e0e] text-white' : 'border-[#262626] text-[#525252]'
                  }`}>
                    <Icon name={p.icon} className="text-sm" />
                  </div>
                  <div className={`text-[9px] mono uppercase tracking-wider mt-2 ${p.state === 'skip' ? 'text-[#525252]' : 'text-white'}`}>{p.name}</div>
                </div>
              </React.Fragment>
            ))}
          </div>

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6">
            <Link
              to="/new-check"
              className="w-full sm:w-auto bg-white text-black font-mono text-xs font-bold px-5 py-2.5 border border-white hover:bg-[#e5e5e5] flex items-center justify-center gap-2"
            >
              <Icon name="file-check" /> SUBMIT DETAILED BLUEPRINT
            </Link>
            <Link
              to="/kbr"
              className="w-full sm:w-auto px-5 py-2.5 text-xs mono text-[#a3a3a3] bg-[#0e0e0e] border border-[#333333] hover:border-white hover:text-white flex items-center justify-center gap-2"
            >
              <Icon name="book-open" /> EXPLORE KBR RULEBOOK
            </Link>
          </div>

          <div className="border border-[#262626] bg-[#0e0e0e] p-3 text-left mb-6">
            <div className="text-[10px] mono text-[#a3a3a3] leading-relaxed">
              [NOTE] Insufficient evidence does NOT constitute statutory approval. Re-submit with verified setbacks, plot area, and access street measurements.
            </div>
          </div>

          <div className="max-w-sm mx-auto">
            <AnalysisTrace trace={[{ node: 'retrieve', status: 'done', detail: '0 chunks · empty retrieval', ts: '2026-08-05 11:30:12' }]} />
          </div>
        </div>
      </div>

      <AppFooter extra="STATUS: INSUFFICIENT DATA" />
    </>
  )
}
