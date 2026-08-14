import React, { useState } from 'react'
import { NavLink, Link } from 'react-router-dom'
import Icon from './Icon.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'layout-dashboard', end: true },
  { to: '/new-check', label: 'New Compliance Check', icon: 'plus-square' },
  { to: '/projects', label: 'Projects', icon: 'folder' },
  { to: '/reports', label: 'Reports', icon: 'file-text' },
  { to: '/kbr', label: 'KBR Knowledge Base', icon: 'database' },
  { to: '/activity', label: 'Activity', icon: 'activity' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

const SYS = ['API Engine', 'Vector Store', 'Claude LLM', 'KBR Knowledge']

export default function AppShell({ children }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex min-h-screen relative overflow-hidden">
      <div className="blueprint-grid absolute inset-0 z-0" />

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 h-14 flex items-center justify-between px-4 bg-[#0C1117] border-b border-[#222C3A]">
        <div>
          <div className="text-[9px] mono font-semibold tracking-widest text-[#22D3EE] opacity-80">KBR COMPLIANCE ENGINE</div>
          <div className="text-sm font-bold tracking-tight text-white">CHATTAMAI</div>
        </div>
        <button onClick={() => setOpen(!open)} className="p-2 text-[#9AA7B6] hover:text-white" aria-label="Menu">
          <Icon name={open ? 'x' : 'menu'} className="text-xl" />
        </button>
      </div>

      {/* Backdrop for mobile drawer */}
      {open && <div className="md:hidden fixed inset-0 bg-black/60 z-30" onClick={() => setOpen(false)} />}

      {/* Sidebar */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-64 flex-shrink-0 bg-[#0C1117] border-r border-[#222C3A] flex flex-col transform transition-transform duration-200 md:transform-none ${
          open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-6 pt-20 md:pt-6">
          <div className="mb-8 hidden md:block">
            <div className="text-xs mono font-semibold tracking-widest text-[#22D3EE] opacity-80 mb-0.5">KBR COMPLIANCE ENGINE</div>
            <h1 className="text-xl font-bold tracking-tight text-white">CHATTAMAI</h1>
          </div>
          <nav className="space-y-1" onClick={() => setOpen(false)}>
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}>
                {({ isActive }) => (
                  <span
                    className={`group relative flex items-center px-3 py-2 text-sm font-medium rounded-md transition-all duration-150 cursor-pointer ${
                      isActive ? 'bg-[#161D27] text-white' : 'text-[#9AA7B6] hover:text-white hover:bg-[#161D27]'
                    }`}
                  >
                    {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 sidebar-rail h-4 rounded-full" />}
                    <Icon name={item.icon} className={`mr-3 text-lg ${isActive ? 'text-[#22D3EE]' : 'opacity-70 group-hover:opacity-100'}`} />
                    {item.label}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="mt-auto p-4">
          <div className="bg-[#10151C] border border-[#222C3A] rounded-md p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1.5 h-1.5 rounded-full bg-[#34D399] shadow-[0_0_8px_#34D399]" />
              <span className="text-[11px] font-bold tracking-wider uppercase text-white">System Status</span>
            </div>
            <div className="space-y-2">
              {SYS.map((s) => (
                <div key={s} className="flex items-center justify-between">
                  <span className="text-[10px] mono text-[#5B6879] uppercase tracking-wider">{s}</span>
                  <div className="w-1.5 h-1.5 rounded-full bg-[#34D399]" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col z-10 min-w-0 pt-14 md:pt-0">{children}</main>
    </div>
  )
}

export function Header({ eyebrow, title, subtitle, action, backLink }) {
  return (
    <header className="min-h-[80px] flex items-center justify-between gap-4 px-6 md:px-8 border-b border-[#222C3A] bg-[#0A0E13]/80 backdrop-blur-md sticky top-14 md:top-0 z-20">
      <div className="flex items-center gap-4 min-w-0">
        {backLink && (
          <Link to={backLink} className="text-[#5B6879] hover:text-white transition-colors flex-shrink-0">
            <Icon name="chevron-left" className="text-2xl" />
          </Link>
        )}
        <div className="min-w-0">
          {eyebrow && <div className="text-[10px] mono text-[#5B6879] uppercase tracking-[0.2em] mb-0.5 truncate">{eyebrow}</div>}
          <h2 className="text-xl md:text-2xl font-semibold tracking-tight text-white truncate">{title}</h2>
          {subtitle && <p className="text-sm text-[#9AA7B6] truncate">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </header>
  )
}
