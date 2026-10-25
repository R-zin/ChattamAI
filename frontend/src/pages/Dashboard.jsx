import React from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  EmptyState,
} from '../components/ui/index.js'
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
            className="bg-white text-black px-4 py-2 text-xs mono font-bold hover:bg-[#e5e5e5] transition-all flex items-center gap-2 border border-white focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
          >
            <Icon name="plus" className="text-base" />
            <span>+ NEW COMPLIANCE CHECK</span>
          </Link>
        }
      />

      <div className="p-6 md:p-8 space-y-6">
        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {metricCards.map((m) => (
            <div
              key={m.label}
              className="border border-[#262626] bg-[#121212] p-5 flex flex-col justify-between hover:border-[#404040] transition-colors group"
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] mono text-[#737373] tracking-widest uppercase font-semibold">
                  {m.label}
                </span>
                <Icon
                  name={m.icon}
                  className="text-xs text-[#525252] group-hover:text-white transition-colors"
                />
              </div>

              <div className="my-3">
                <div className="text-3xl font-bold mono text-white tracking-tight">
                  {m.value}
                </div>
              </div>

              <div className="text-[10px] mono text-[#a3a3a3] pt-2 border-t border-[#262626]/80 flex items-center justify-between">
                <span>{m.sub}</span>
                <span className="text-[#525252] group-hover:text-white transition-colors">
                  →
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Main Grid: Recent Assessments & Regulatory Guidelines */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Recent Checks Table (8 cols) */}
          <div className="lg:col-span-8">
            <Card>
              <CardHeader>
                <CardTitle>
                  <Icon name="activity" />
                  <span>Recent Plan Assessments</span>
                </CardTitle>
                <span className="text-[10px] mono text-[#737373]">
                  {checks.length} RECORDS
                </span>
              </CardHeader>

              {checks.length === 0 ? (
                <EmptyState
                  icon="file-text"
                  eyebrow="NO ASSESSMENTS RECORDED"
                  title="No Recent Plan Checks"
                  description="Start a new compliance assessment to populate recent activity."
                />
              ) : (
                <div className="overflow-x-auto flex-1">
                  <table className="w-full min-w-[640px] text-left border-collapse" role="table">
                    <thead>
                      <tr className="border-b border-[#262626] bg-[#0e0e0e]">
                        {['Project Name', 'Plan File', 'Status', 'Violations', 'Date', 'Action'].map(
                          (h, i) => (
                            <th
                              key={h}
                              scope="col"
                              className={`px-4 py-3 text-[10px] mono text-[#737373] uppercase tracking-wider font-semibold ${
                                i === 5 ? 'text-right' : 'text-left'
                              }`}
                            >
                              {h}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#262626]">
                      {checks.map((c) => {
                        const s = STATUS_META[c.status] || STATUS_META.review
                        const to =
                          c.status === 'insufficient'
                            ? '/results/insufficient'
                            : '/results/demo'
                        return (
                          <tr
                            key={c.id}
                            className="hover:bg-[#181818] transition-colors group"
                          >
                            <td className="px-4 py-3.5">
                              <div className="text-xs font-semibold text-white">
                                {c.project}
                              </div>
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
                                <span className="font-bold underline text-[#fca5a5]">
                                  {c.violations} Issues
                                </span>
                              ) : (
                                <span className="text-[#a3a3a3]">Compliant</span>
                              )}
                            </td>
                            <td className="px-4 py-3.5 text-[10px] mono text-[#737373]">
                              {c.analyzed}
                            </td>
                            <td className="px-4 py-3.5 text-right">
                              <Link
                                to={to}
                                aria-label={`View assessment for ${c.project}`}
                                className="text-[10px] mono font-bold text-white hover:underline border border-[#404040] hover:border-white px-2.5 py-1 bg-[#0a0a0a] inline-flex items-center gap-1 focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
                              >
                                <span>VIEW</span>
                                <span>→</span>
                              </Link>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>

          {/* Right Panel: Regulatory Guidelines (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>
                  <Icon name="book-open" />
                  <span>Statutory Guidelines</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="border-l-2 border-white pl-3 py-1">
                  <div className="text-[10px] mono text-[#a3a3a3]">
                    KBR 2019 CHAPTER IV
                  </div>
                  <div className="text-white font-medium text-xs mt-0.5 leading-relaxed">
                    Setback and open space standards for residential and commercial occupancies.
                  </div>
                </div>
                <div className="border-l-2 border-[#525252] pl-3 py-1">
                  <div className="text-[10px] mono text-[#a3a3a3]">
                    FAR & COVERAGE LIMITS
                  </div>
                  <div className="text-[#d4d4d4] font-medium text-xs mt-0.5 leading-relaxed">
                    Maximum floor area ratios based on abutting road widths and zoning classifications.
                  </div>
                </div>
                <div className="border-l-2 border-[#525252] pl-3 py-1">
                  <div className="text-[10px] mono text-[#a3a3a3]">
                    FIRE & ACCESS CLEARANCES
                  </div>
                  <div className="text-[#d4d4d4] font-medium text-xs mt-0.5 leading-relaxed">
                    Mandatory egress corridors, staircases, and vehicular turning radii.
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>
                  <Icon name="zap" />
                  <span>Quick Action</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-[#a3a3a3] mb-4 leading-relaxed">
                  Verify a new blueprint or floor plan specification against current KBR 2019 statutory provisions.
                </p>
                <Link
                  to="/new-check"
                  className="w-full bg-white text-black font-mono font-bold text-xs py-2.5 px-4 flex items-center justify-center gap-2 hover:bg-[#e5e5e5] transition-colors focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
                >
                  <span>START NEW AUDIT →</span>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <AppFooter />
    </>
  )
}
