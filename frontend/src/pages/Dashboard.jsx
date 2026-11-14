import React from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import { EmptyState } from '../components/ui/index.js'
import { checks, STATUS_META } from '../data.js'

export default function Dashboard() {
  const metricCards = [
    { label: 'TOTAL ASSESSMENTS', value: '142', sub: '+18 this week', icon: 'file-text' },
    { label: 'COMPLIANCE RATE', value: '88.4%', sub: 'First-pass compliance', icon: 'check-circle' },
    { label: 'FLAGGED ISSUES', value: '12', sub: 'Setback & coverage items', icon: 'alert-triangle' },
    { label: 'STATUTORY RULES', value: '595', sub: 'KBR 2019 indexed rules', icon: 'book-open' },
  ]

  return (
    <>
      <Header
        eyebrow="KERALA BUILDING RULES 2019"
        title="Compliance Dashboard"
        subtitle="Automated architectural zoning, setback, and FAR verification engine"
        action={
          <Link
            to="/new-check"
            className="bg-accent text-on-accent px-5 py-2.5 text-xs font-semibold uppercase tracking-wider hover:bg-accent-strong transition-colors flex items-center gap-2"
          >
            <span>+ NEW COMPLIANCE CHECK</span>
          </Link>
        }
      />

      <div className="px-6 md:px-8 py-8 space-y-10 max-w-[1400px] w-full">
        {/* Key figures: an open row separated by hairlines, no boxes */}
        <section
          aria-label="Key figures"
          className="grid grid-cols-2 lg:grid-cols-4 border-y border-line"
        >
          {metricCards.map((m, i) => (
            <div
              key={m.label}
              className={`py-5 px-0 sm:px-6 first:pl-0 ${i % 2 === 1 ? 'border-l border-line pl-4 sm:pl-6' : ''} ${
                i >= 2 ? 'border-t border-line lg:border-t-0' : ''
              } ${i > 0 ? 'lg:border-l lg:border-line lg:pl-6' : ''}`}
            >
              <div className="text-[11px] text-ink-3 tracking-wider uppercase font-bold mb-3">
                {m.label}
              </div>
              <div className="text-4xl lg:text-5xl font-extrabold text-ink tracking-tight tabular-nums leading-none">
                {m.value}
              </div>
              <div className="text-xs text-ink-2 mt-3">{m.sub}</div>
            </div>
          ))}
        </section>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-x-10 gap-y-10">
          {/* Recent assessments (8 cols on wide screens) */}
          <section className="xl:col-span-8 min-w-0" aria-labelledby="recent-assessments">
            <div className="flex items-baseline justify-between pb-2">
              <h2 id="recent-assessments" className="text-base font-bold text-ink">
                Recent Plan Assessments
              </h2>
              <span className="text-xs text-ink-2 tabular-nums font-semibold uppercase tracking-wider">
                {checks.length} RECORDS
              </span>
            </div>

            {checks.length === 0 ? (
              <EmptyState
                icon="file-text"
                eyebrow="NO ASSESSMENTS RECORDED"
                title="No Recent Plan Checks"
                description="Start a new compliance assessment to populate recent activity."
              />
            ) : (
              <>
              {/* Phones: a stacked list (a wide table would clip the status column) */}
              <ul className="md:hidden border-t-2 border-ink divide-y divide-line" aria-label="Recent plan assessments">
                {checks.map((c) => {
                  const s = STATUS_META[c.status] || STATUS_META.review
                  const to = c.status === 'insufficient' ? '/results/insufficient' : '/results/demo'
                  return (
                    <li key={c.id} className="py-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-ink">{c.project}</div>
                          <div className="text-xs text-ink-2 mt-0.5 tabular-nums">{c.plan}</div>
                        </div>
                        <Link
                          to={to}
                          aria-label={`View assessment for ${c.project}`}
                          className="text-xs font-semibold text-accent hover:underline inline-flex items-center gap-1 whitespace-nowrap shrink-0"
                        >
                          <span>VIEW</span>
                          <span aria-hidden="true">→</span>
                        </Link>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
                        <Pill kind={s.pill}>{s.label}</Pill>
                        {c.violations !== null && c.violations > 0 && (
                          <span className="text-xs font-bold text-danger tabular-nums">{c.violations} Issues</span>
                        )}
                        <span className="text-xs text-ink-2 tabular-nums">{c.analyzed}</span>
                      </div>
                    </li>
                  )
                })}
              </ul>

              <div
                className="hidden md:block overflow-x-auto"
                tabIndex={0}
                role="region"
                aria-label="Recent plan assessments table"
              >
                <table className="w-full min-w-[620px] text-left border-collapse" role="table">
                  <thead>
                    <tr className="border-b-2 border-ink">
                      {['Project Name', 'Plan File', 'Status', 'Violations', 'Date', 'Action'].map(
                        (h, i) => (
                          <th
                            key={h}
                            scope="col"
                            className={`py-3 pr-4 text-[11px] text-ink uppercase tracking-wider font-bold ${
                              i === 3 || i === 5 ? 'text-right' : 'text-left'
                            } ${i === 5 ? 'pr-0' : ''}`}
                          >
                            {h}
                          </th>
                        )
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {checks.map((c) => {
                      const s = STATUS_META[c.status] || STATUS_META.review
                      const to =
                        c.status === 'insufficient' ? '/results/insufficient' : '/results/demo'
                      return (
                        <tr key={c.id} className="hover:bg-surface-2 transition-colors">
                          <td className="py-3.5 pr-4 text-sm font-semibold text-ink">{c.project}</td>
                          <td className="py-3.5 pr-4 text-xs text-ink-2 tabular-nums">{c.plan}</td>
                          <td className="py-3.5 pr-4">
                            <Pill kind={s.pill}>{s.label}</Pill>
                          </td>
                          <td className="py-3.5 pr-4 text-xs text-right tabular-nums">
                            {c.violations === null ? (
                              <span className="text-ink-3">—</span>
                            ) : c.violations > 0 ? (
                              <span className="font-bold text-danger">{c.violations} Issues</span>
                            ) : (
                              <span className="text-ink-2">Compliant</span>
                            )}
                          </td>
                          <td className="py-3.5 pr-4 text-xs text-ink-2 tabular-nums whitespace-nowrap">{c.analyzed}</td>
                          <td className="py-3.5 text-right">
                            <Link
                              to={to}
                              aria-label={`View assessment for ${c.project}`}
                              className="text-xs font-semibold text-accent hover:underline inline-flex items-center gap-1 whitespace-nowrap"
                            >
                              <span>VIEW</span>
                              <span aria-hidden="true">→</span>
                            </Link>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              </>
            )}
          </section>

          {/* Guidance + quick action (4 cols on wide screens) */}
          <aside className="xl:col-span-4 space-y-10 min-w-0">
            <section aria-labelledby="statutory-guidelines">
              <h2
                id="statutory-guidelines"
                className="text-base font-bold text-ink pb-2 border-b-2 border-ink"
              >
                Statutory Guidelines
              </h2>
              <div className="divide-y divide-line">
                {[
                  ['KBR 2019 CHAPTER IV', 'Setback and open space standards for residential and commercial occupancies.'],
                  ['FAR & COVERAGE LIMITS', 'Maximum floor area ratios based on abutting road widths and zoning classifications.'],
                  ['FIRE & ACCESS CLEARANCES', 'Mandatory egress corridors, staircases, and vehicular turning radii.'],
                ].map(([label, text]) => (
                  <div key={label} className="py-4">
                    <div className="text-[11px] uppercase tracking-wider font-bold text-ink-3 mb-1.5">
                      {label}
                    </div>
                    <p className="text-sm text-ink leading-relaxed">{text}</p>
                  </div>
                ))}
              </div>
            </section>

            <section aria-labelledby="quick-action" className="bg-surface border border-line p-5">
              <h2
                id="quick-action"
                className="text-[11px] uppercase tracking-wider font-bold text-ink-3 mb-2"
              >
                Quick Action
              </h2>
              <p className="text-sm text-ink-2 mb-4 leading-relaxed">
                Verify a new blueprint or floor plan specification against current KBR 2019 statutory provisions.
              </p>
              <Link
                to="/new-check"
                className="w-full border border-ink text-ink font-semibold text-xs uppercase tracking-wider py-2.5 px-4 flex items-center justify-between hover:bg-surface-2 transition-colors"
              >
                <span>START NEW AUDIT</span>
                <span aria-hidden="true">→</span>
              </Link>
            </section>
          </aside>
        </div>
      </div>

      <AppFooter />
    </>
  )
}
