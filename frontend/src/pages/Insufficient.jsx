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
      <Header eyebrow="Operational Dashboard" title="Compliance Assessment" subtitle="Villa Extension — Kozhikode" />
      <div className="flex-1 flex items-center justify-center p-6 md:p-12">
        <div className="max-w-2xl w-full bg-[#10151C] border border-[#222C3A] rounded-lg p-10 text-center shadow-xl">
          <div className="mx-auto w-16 h-16 rounded-full border border-amber-500/40 bg-amber-500/10 flex items-center justify-center mb-6">
            <Icon name="alert-triangle" className="text-3xl text-amber-500" />
          </div>
          <Pill kind="pill-insufficient">INSUFFICIENT EVIDENCE</Pill>
          <h3 className="text-2xl font-semibold text-white mt-5 mb-3 leading-snug">
            ChattamAI could not retrieve enough relevant Kerala Building Rules to make a reliable assessment.
          </h3>
          <p className="text-sm text-[#9AA7B6] leading-relaxed mb-6">
            The vector retrieval stage returned zero relevant rule nodes for the submitted plan documents. This typically occurs when project specifications are too sparse for extraction.
          </p>

          <div className="inline-block bg-[#0A0E13] border border-[#222C3A] rounded px-5 py-2 mb-8">
            <span className="mono text-sm text-[#9AA7B6]">Rules Retrieved: <span className="text-amber-500">0</span></span>
          </div>

          {/* dimmed pipeline */}
          <div className="flex items-center justify-center gap-0 mb-8">
            {PIPE.map((p, i) => (
              <React.Fragment key={p.name}>
                {i > 0 && <div className={`w-10 h-px ${PIPE[i-1].state === 'done' && p.state === 'warn' ? 'bg-amber-500/50' : 'bg-[#222C3A]'}`} />}
                <div className="flex flex-col items-center">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
                    p.state === 'done' ? 'border-[#34D399] text-[#34D399]' : p.state === 'warn' ? 'border-amber-500 text-amber-500' : 'border-[#222C3A] text-[#5B6879] opacity-40'
                  }`}>
                    <Icon name={p.icon} className="text-lg" />
                  </div>
                  <div className={`text-[9px] mono uppercase tracking-wider mt-2 ${p.state === 'skip' ? 'text-[#5B6879] opacity-40' : p.state === 'warn' ? 'text-amber-500' : 'text-[#34D399]'}`}>{p.name}</div>
                </div>
              </React.Fragment>
            ))}
          </div>

          {/* actions */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6">
            <Link to="/new-check" className="accent-gradient px-5 py-2.5 rounded text-sm font-semibold text-black hover:brightness-110 flex items-center gap-2">
              <Icon name="file-check" /> Upload Additional Documentation
            </Link>
            <Link to="/kbr" className="px-5 py-2.5 rounded text-sm font-medium text-[#9AA7B6] bg-[#161D27] border border-[#222C3A] hover:text-white flex items-center gap-2">
              <Icon name="book-open" /> Review KBR Knowledge Base
            </Link>
            <Link to="/new-check" className="px-4 py-2.5 text-sm mono text-[#5B6879] hover:text-white flex items-center gap-2">
              <Icon name="refresh-cw" /> Run Analysis Again
            </Link>
          </div>

          <div className="border-l-2 border-amber-500 bg-amber-500/5 px-4 py-3 text-left mb-6">
            <div className="text-[11px] mono text-amber-500/90 leading-relaxed">Do not treat this result as a compliance approval — engineer review required.</div>
          </div>

          <div className="max-w-sm mx-auto">
            <AnalysisTrace trace={[{ node: 'retrieve', status: 'done', detail: '0 chunks · retrieved empty', ts: '2026-08-05 11:30:12' }]} />
          </div>
        </div>
      </div>
      <AppFooter extra="LATENCY: 18ms" />
    </>
  )
}
