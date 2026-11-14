import React, { useState } from 'react'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import { EmptyState } from '../components/ui/index.js'

const EVENTS = [
  {
    ts: '2026-08-12 14:22',
    label: 'Analysis completed',
    detail: "'Residential Building — Kakkanad' flagged '3 potential issues'",
    cat: 'Analyses',
  },
  {
    ts: '2026-08-12 14:20',
    label: 'Plan uploaded',
    detail: "'plan_014.pdf'",
    cat: 'Analyses',
  },
  {
    ts: '2026-08-11 09:47',
    label: 'Analysis completed',
    detail: "'Commercial Complex — Kochi' flagged '5 potential issues'",
    cat: 'Analyses',
  },
  {
    ts: '2026-08-02 09:14',
    label: 'Ingestion complete',
    detail: '+512 chunks from KBR Amendment 2021.pdf',
    cat: 'Ingestions',
  },
  {
    ts: '2026-08-02 09:10',
    label: 'Ingestion started',
    detail: "'KBR Amendment 2021.pdf'",
    cat: 'Ingestions',
  },
  {
    ts: '2026-08-01 18:02',
    label: 'Model switched',
    detail: 'analysis model set to nvidia/nemotron-3.5-super-vl-120b-a12b',
    cat: 'System',
  },
  {
    ts: '2026-07-28 10:41',
    label: 'Report exported',
    detail: "'Apartment Block — Thiruvananthapuram (PDF)'",
    cat: 'Exports',
  },
]
const FILTERS = ['All', 'Analyses', 'Ingestions', 'Exports', 'System']

export default function Activity() {
  const [f, setF] = useState('All')
  const shown = EVENTS.filter((e) => f === 'All' || e.cat === f)

  return (
    <>
      <Header
        eyebrow="SYSTEM EVENT LOG"
        title="Activity Log"
        subtitle="Chronological log of compliance assessments, vector ingestions, and system events"
      />

      <div className="p-6 md:p-8 space-y-6 bg-bg">
        {/* Filter pills */}
        <div className="flex gap-2 flex-wrap" role="tablist" aria-label="Activity categories">
          {FILTERS.map((x) => (
            <button
              key={x}
              role="tab"
              aria-selected={f === x}
              onClick={() => setF(x)}
              className={`px-3 py-1.5 text-xs mono border transition-all cursor-pointer focus-visible:ring-1 focus-visible:ring-accent focus-visible:outline-none ${
                f === x
                  ? 'border-ink text-on-accent bg-accent font-bold'
                  : 'border-line text-ink-2 hover:text-ink hover:border-line-strong bg-surface'
              }`}
            >
              {x.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Timeline or Empty State */}
        {shown.length === 0 ? (
          <EmptyState
            icon="activity"
            eyebrow="FILTER RESULTS"
            title={`No Events in "${f}"`}
            description="There are no system activities or audit events recorded in this category."
            actionLabel="SHOW ALL ACTIVITY"
            actionIcon="rotate-ccw"
            onAction={() => setF('All')}
          />
        ) : (
          <div className="max-w-3xl bg-surface border border-line p-6 relative">
            <div className="absolute left-[34px] top-8 bottom-8 w-px bg-surface-3" />
            <div className="space-y-6">
              {shown.map((e, i) => (
                <div
                  key={i}
                  className="flex gap-4 items-start relative z-10 fade-rise"
                >
                  <div className="w-2.5 h-2.5 bg-bg border border-ink flex-shrink-0 mt-1" />
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-3 flex-wrap">
                      <span className="text-xs font-bold text-ink uppercase mono">
                        {e.label}
                      </span>
                      <span className="text-[10px] mono text-ink-3">
                        {e.ts}
                      </span>
                    </div>
                    <div className="text-xs mono text-ink-2 mt-0.5 break-words">
                      {e.detail}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <AppFooter />
    </>
  )
}
