import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { EmptyState } from '../components/ui/index.js'

const PROJECTS = [
  {
    id: 'proj-1',
    name: 'Residential Building — Kakkanad',
    loc: 'ERNAKULAM, KERALA',
    checks: 4,
    last: '2026-08-12',
    tags: ['2 · REVIEW', '2 · COMPLIANT'],
  },
  {
    id: 'proj-2',
    name: 'Commercial Complex — Kochi',
    loc: 'KOCHI, KERALA',
    checks: 6,
    last: '2026-08-11',
    tags: ['1 · VIOLATION', '2 · REVIEW', '3 · COMPLIANT'],
  },
  {
    id: 'proj-3',
    name: 'Apartment Block — Thiruvananthapuram',
    loc: 'TVM, KERALA',
    checks: 3,
    last: '2026-08-08',
    tags: ['3 · COMPLIANT'],
  },
  {
    id: 'proj-4',
    name: 'Villa Extension — Kozhikode',
    loc: 'KOZHIKODE, KERALA',
    checks: 1,
    last: '2026-08-05',
    tags: ['1 · PENDING'],
  },
  {
    id: 'proj-5',
    name: 'Mixed-Use Development — Thrissur',
    loc: 'THRISSUR, KERALA',
    checks: 5,
    last: '2026-08-01',
    tags: ['2 · VIOLATION', '3 · COMPLIANT'],
  },
  {
    id: 'proj-6',
    name: 'Office Building — Kannur',
    loc: 'KANNUR, KERALA',
    checks: 2,
    last: '2026-07-29',
    tags: ['2 · COMPLIANT'],
  },
]

const FILTERS = ['All', 'Active', 'Review Required', 'Violation', 'Compliant']

export default function Projects() {
  const [f, setF] = useState('All')

  const filteredProjects = PROJECTS.filter((p) => {
    if (f === 'All') return true
    if (f === 'Active') {
      return p.tags.some((t) => t.includes('PENDING') || t.includes('REVIEW'))
    }
    if (f === 'Review Required') {
      return p.tags.some((t) => t.includes('REVIEW'))
    }
    if (f === 'Violation') {
      return p.tags.some((t) => t.includes('VIOLATION'))
    }
    if (f === 'Compliant') {
      return p.tags.some((t) => t.includes('COMPLIANT'))
    }
    return true
  })

  return (
    <>
      <Header
        eyebrow="PROJECT ARCHIVE"
        title="Projects"
        subtitle="Organized architectural developments audited against Kerala Building Rules 2019"
        action={
          <Link
            to="/new-check"
            className="bg-white text-black font-mono text-xs font-bold px-4 py-2 border border-white hover:bg-[#e5e5e5] flex items-center gap-2 transition-colors focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
          >
            <Icon name="plus" />
            <span>+ NEW COMPLIANCE CHECK</span>
          </Link>
        }
      />

      <div className="p-6 md:p-8 space-y-6 bg-[#0a0a0a]">
        {/* Filters */}
        <div className="flex gap-2 flex-wrap" role="tablist" aria-label="Project filters">
          {FILTERS.map((x) => (
            <button
              key={x}
              role="tab"
              aria-selected={f === x}
              onClick={() => setF(x)}
              className={`px-3 py-1.5 text-xs mono border transition-all cursor-pointer focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none ${
                f === x
                  ? 'border-white text-black bg-white font-bold'
                  : 'border-[#262626] text-[#a3a3a3] hover:text-white hover:border-[#404040] bg-[#121212]'
              }`}
            >
              {x.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Project Cards Grid */}
        {filteredProjects.length === 0 ? (
          <EmptyState
            icon="folder"
            eyebrow="FILTER RESULTS"
            title={`No Projects Matching "${f}"`}
            description="There are no architectural developments currently indexed under this filter status."
            actionLabel="SHOW ALL PROJECTS"
            actionIcon="rotate-ccw"
            onAction={() => setF('All')}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredProjects.map((p) => (
              <Link
                to="/results/demo"
                key={p.name}
                aria-label={`Open project details for ${p.name}`}
                className="bg-[#121212] border border-[#262626] p-5 hover:border-white transition-colors group flex flex-col justify-between focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="text-sm font-bold text-white group-hover:underline leading-snug">
                      {p.name}
                    </h3>
                    <Icon
                      name="external-link"
                      className="text-[#737373] group-hover:text-white flex-shrink-0 text-sm mt-0.5 transition-colors"
                    />
                  </div>
                  <div className="text-[9px] mono text-[#737373] uppercase tracking-wider mb-4">
                    {p.loc}
                  </div>
                  <div className="flex items-center gap-4 text-xs mono text-[#a3a3a3] mb-4">
                    <span>{p.checks} CHECKS</span>
                    <span>•</span>
                    <span>{p.last}</span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#262626] flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex gap-1.5 flex-wrap">
                    {p.tags.map((t) => (
                      <span
                        key={t}
                        className="text-[9px] mono border border-[#262626] px-1.5 py-0.5 bg-[#0e0e0e] text-white"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                  <span className="text-[10px] mono text-white opacity-0 group-hover:opacity-100 transition-opacity">
                    INSPECT →
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <AppFooter />
    </>
  )
}
