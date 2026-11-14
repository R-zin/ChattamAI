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
        eyebrow="Audit Notice"
        title="Compliance Assessment"
        subtitle="Villa Extension — Kozhikode"
      />

      <div className="flex-1 flex items-center justify-center p-6 md:p-12 bg-bg">
        <div className="max-w-2xl w-full bg-surface border border-line p-8 md:p-10 text-center shadow-2xl">
          <div className="mx-auto w-14 h-14 border border-ink bg-inset flex items-center justify-center mb-5">
            <Icon name="alert-triangle" className="text-2xl text-ink" />
          </div>

          <Pill kind="pill-insufficient">INSUFFICIENT EVIDENCE</Pill>

          <h3 className="text-xl md:text-2xl font-bold text-ink mt-4 mb-3 font-sans uppercase tracking-tight">
            Insufficient Evidence for Statutory Assessment
          </h3>
          <p className="text-xs mono text-ink-2 leading-relaxed mb-6 max-w-lg mx-auto">
            The retrieval pipeline could not locate verified statutory rule matches for the submitted plan. This occurs when building dimensions, setbacks, or occupancy categories are too sparse for extraction.
          </p>

          <div className="inline-block bg-inset border border-line px-4 py-2 mb-8">
            <span className="mono text-xs text-ink-2">KBR Rules Retrieved: <span className="text-ink font-bold">0 Rules</span></span>
          </div>

          {/* Minimalist pipeline */}
          <div className="flex items-center justify-center gap-0 mb-8">
            {PIPE.map((p, i) => (
              <React.Fragment key={p.name}>
                {i > 0 && <div className={`w-8 h-px ${PIPE[i-1].state === 'done' ? 'bg-accent' : 'bg-surface-3'}`} />}
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 flex items-center justify-center border ${
                    p.state === 'done' ? 'border-ink bg-accent text-on-accent' : p.state === 'warn' ? 'border-ink bg-inset text-ink' : 'border-line text-ink-3'
                  }`}>
                    <Icon name={p.icon} className="text-sm" />
                  </div>
                  <div className={`text-[9px] mono uppercase tracking-wider mt-2 ${p.state === 'skip' ? 'text-ink-3' : 'text-ink'}`}>{p.name}</div>
                </div>
              </React.Fragment>
            ))}
          </div>

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6">
            <Link
              to="/new-check"
              className="w-full sm:w-auto bg-accent text-on-accent font-mono text-xs font-bold px-5 py-2.5 border border-ink hover:bg-accent-strong flex items-center justify-center gap-2"
            >
              <Icon name="file-check" /> SUBMIT DETAILED BLUEPRINT
            </Link>
            <Link
              to="/kbr"
              className="w-full sm:w-auto px-5 py-2.5 text-xs mono text-ink-2 bg-inset border border-line hover:border-ink hover:text-ink flex items-center justify-center gap-2"
            >
              <Icon name="book-open" /> EXPLORE KBR RULEBOOK
            </Link>
          </div>

          <div className="border border-line bg-inset p-3 text-left mb-6">
            <div className="text-[10px] mono text-ink-2 leading-relaxed">
              Insufficient evidence does not constitute statutory approval. Re-submit with verified setbacks, plot area, and access street measurements.
            </div>
          </div>

          <div className="max-w-sm mx-auto">
            <AnalysisTrace trace={[{ node: 'retrieve', status: 'done', detail: '0 rules matched', ts: '2026-08-05 11:30:12' }]} />
          </div>
        </div>
      </div>

      <AppFooter />
    </>
  )
}
