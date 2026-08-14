import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'

const PROJECTS = [
  { name: 'Residential Building — Kakkanad', loc: 'ERNAKULAM, KERALA', checks: 4, last: '2026-08-12', tags: [['2 · Review', 'var(--warn)'], ['2 · Compliant', 'var(--ok)']] },
  { name: 'Commercial Complex — Kochi', loc: 'KOCHI, KERALA', checks: 6, last: '2026-08-11', tags: [['1 · Violation', 'var(--danger)'], ['2 · Review', 'var(--warn)'], ['3 · Compliant', 'var(--ok)']] },
  { name: 'Apartment Block — Thiruvananthapuram', loc: 'TVM, KERALA', checks: 3, last: '2026-08-08', tags: [['3 · Compliant', 'var(--ok)']] },
  { name: 'Villa Extension — Kozhikode', loc: 'KOZHIKODE, KERALA', checks: 1, last: '2026-08-05', tags: [['1 · Pending', 'var(--text-3)']] },
  { name: 'Mixed-Use Development — Thrissur', loc: 'THRISSUR, KERALA', checks: 5, last: '2026-08-01', tags: [['2 · Violation', 'var(--danger)'], ['3 · Compliant', 'var(--ok)']] },
  { name: 'Office Building — Kannur', loc: 'KANNUR, KERALA', checks: 2, last: '2026-07-29', tags: [['2 · Compliant', 'var(--ok)']] },
]
const FILTERS = ['All', 'Active', 'Review Required', 'Violation', 'Compliant']

export default function Projects() {
  const [f, setF] = useState('All')
  return (
    <>
      <Header
        eyebrow="Operational Dashboard"
        title="Projects"
        subtitle="Building plans organized by project"
        action={
          <Link to="/new-check" className="accent-gradient px-4 py-2 rounded text-sm font-semibold text-black flex items-center gap-2 hover:brightness-110">
            <Icon name="plus" /> New Compliance Check
          </Link>
        }
      />
      <div className="p-6 md:p-8 space-y-6">
        <div className="flex gap-2 flex-wrap">
          {FILTERS.map((x) => (
            <button key={x} onClick={() => setF(x)} className={`px-3 py-1.5 rounded text-xs mono border transition-all ${f === x ? 'border-[#22D3EE] text-[#22D3EE] bg-[#22D3EE]/10' : 'border-[#222C3A] text-[#9AA7B6] hover:text-white hover:border-[#2E3B4D]'}`}>
              {x}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {PROJECTS.map((p) => (
            <Link to="/results/demo" key={p.name} className="bg-[#10151C] border border-[#222C3A] rounded p-6 hover:border-[#2E3B4D] hover:-translate-y-0.5 hover:shadow-lg transition-all group flex flex-col">
              <div className="flex items-start justify-between gap-2 mb-1">
                <h3 className="text-base font-semibold text-white leading-snug group-hover:text-[#22D3EE] transition-colors">{p.name}</h3>
                <Icon name="external-link" className="text-[#5B6879] group-hover:text-[#22D3EE] flex-shrink-0" />
              </div>
              <div className="text-[10px] mono text-[#5B6879] uppercase tracking-wider mb-4">{p.loc}</div>
              <div className="flex items-center gap-4 text-xs mono text-[#9AA7B6] mb-4">
                <span className="flex items-center gap-1.5"><Icon name="file-check-2" /> {p.checks} CHECKS</span>
                <span className="flex items-center gap-1.5"><Icon name="clock" /> {p.last}</span>
              </div>
              <div className="mt-auto flex items-center justify-between gap-2 flex-wrap">
                <div className="flex gap-2 flex-wrap">
                  {p.tags.map(([t, c]) => (
                    <span key={t} className="text-[10px] mono" style={{ color: c }}>● {t}</span>
                  ))}
                </div>
                <span className="text-[11px] mono text-[#22D3EE] opacity-0 group-hover:opacity-100 transition-opacity">OPEN →</span>
              </div>
            </Link>
          ))}
        </div>
        <div className="text-[10px] mono text-[#5B6879]">Derived from assessment records.</div>
      </div>
      <AppFooter />
    </>
  )
}
