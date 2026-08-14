import React from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { metrics, checks, STATUS_META } from '../data.js'

export default function Dashboard() {
  return (
    <>
      <Header
        eyebrow="Operational Dashboard"
        title="Kerala Building Compliance"
        subtitle="AI-assisted verification against Kerala Building Rules"
        action={
          <Link
            to="/new-check"
            className="accent-gradient px-4 py-2 rounded text-sm font-semibold text-black flex items-center gap-2 hover:brightness-110 transition-all shadow-[0_0_15px_rgba(34,211,238,0.2)]"
          >
            <Icon name="plus" className="text-lg" /> New Compliance Check
          </Link>
        }
      />

      <div className="p-6 md:p-8 space-y-8">
        {/* Metrics strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-px border border-[#222C3A] bg-[#10151C] rounded overflow-hidden divide-x divide-[#222C3A]">
          {metrics.map((m) => (
            <div key={m.label} className="bg-[#10151C] p-6 hover:bg-[#161D27] transition-colors">
              <div className="text-[10px] mono text-[#5B6879] uppercase tracking-wider mb-2">{m.label}</div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl mono font-medium tracking-tighter" style={{ color: m.tone }}>{m.value}</span>
                <span className="text-xs mono" style={{ color: m.delta.startsWith('+') ? m.tone : 'var(--text-3)' }}>{m.delta}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Recent checks table */}
        <div className="bg-[#10151C] border border-[#222C3A] rounded shadow-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#222C3A] flex items-center justify-between bg-[#161D27]/50">
            <h3 className="text-sm font-semibold text-white tracking-wide uppercase flex items-center gap-2">
              <Icon name="activity" className="text-[#22D3EE]" /> Recent Compliance Checks
            </h3>
            <div className="text-[10px] mono text-[#5B6879] hidden sm:block">Showing last 5 assessments</div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px]">
              <thead>
                <tr className="border-b border-[#222C3A] bg-[#0C1117]">
                  {['Project', 'Plan File', 'Status', 'Violations', 'Rules Ref.', 'Analyzed At', 'Action'].map((h, i) => (
                    <th key={h} className={`px-6 py-3 text-[11px] mono text-[#5B6879] uppercase tracking-wider font-medium ${i === 6 ? 'text-right' : 'text-left'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#222C3A]">
                {checks.map((c) => {
                  const s = STATUS_META[c.status]
                  const to = c.status === 'insufficient' ? '/results/insufficient' : '/results/demo'
                  return (
                    <tr key={c.id} className="hover:bg-[#161D27] transition-colors group">
                      <td className="px-6 py-4"><div className="text-sm font-medium text-white">{c.project}</div></td>
                      <td className="px-6 py-4"><div className="text-xs mono text-[#9AA7B6]">{c.plan}</div></td>
                      <td className="px-6 py-4"><Pill kind={s.pill}>{s.label}</Pill></td>
                      <td className="px-6 py-4 text-sm mono" style={{ color: c.violations === null ? 'var(--text-3)' : c.violations > 0 ? s.color : 'var(--ok)' }}>
                        {c.violations === null ? '—' : c.violations}
                      </td>
                      <td className="px-6 py-4 text-sm mono text-[#9AA7B6]">{c.rules}</td>
                      <td className="px-6 py-4 text-xs mono text-[#5B6879]">{c.analyzed}</td>
                      <td className="px-6 py-4 text-right">
                        <Link to={to} className="text-[11px] mono font-medium text-[#22D3EE] opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1 hover:underline">
                          VIEW ANALYSIS <Icon name="arrow-right" />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="px-6 py-3 bg-[#0C1117] flex items-center justify-between border-t border-[#222C3A]">
            <div className="text-[10px] mono text-[#5B6879] flex items-center gap-2">
              <Icon name="info" className="text-amber-500/50" />
              Assessment results are AI-assisted potential findings and must be confirmed by a licensed LSGD engineer.
            </div>
          </div>
        </div>
      </div>
      <AppFooter extra="LATENCY: 420ms" />
    </>
  )
}
