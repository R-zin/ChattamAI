import React, { useState, useEffect } from 'react'
import { NavLink, Link } from 'react-router-dom'
import Icon from './Icon.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'layout-dashboard', end: true },
  { to: '/workbench', label: 'PDF Visual Workbench', icon: 'eye' },
  { to: '/new-check', label: 'New Compliance Check', icon: 'plus-square' },
  { to: '/projects', label: 'Projects', icon: 'folder' },
  { to: '/reports', label: 'Reports', icon: 'file-text' },
  { to: '/kbr', label: 'KBR Knowledge Base', icon: 'database' },
  { to: '/activity', label: 'Activity', icon: 'activity' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

export default function AppShell({ children }) {
  const [open, setOpen] = useState(false)

  // Close mobile drawer on Escape key press
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open])

  return (
    <div className="flex min-h-screen relative overflow-hidden bg-[#0a0a0a] text-[#f5f5f5]">
      <div className="blueprint-grid absolute inset-0 z-0 pointer-events-none" />

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 h-14 flex items-center justify-between px-4 bg-[#0a0a0a] border-b border-[#262626]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 border border-[#404040] flex items-center justify-center bg-[#121212]">
            <span className="mono text-xs font-bold text-white">CH</span>
          </div>
          <div>
            <div className="text-[8px] mono font-semibold tracking-widest text-[#737373]">
              KBR COMPLIANCE ENGINE
            </div>
            <div className="text-xs font-bold tracking-tight text-white">
              CHATTAM.AI
            </div>
          </div>
        </div>
        <button
          onClick={() => setOpen(!open)}
          className="p-2 text-[#a3a3a3] hover:text-white focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
          aria-label={open ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={open}
          aria-controls="navigation-sidebar"
        >
          <Icon name={open ? 'x' : 'menu'} className="text-xl" />
        </button>
      </div>

      {/* Backdrop for mobile drawer */}
      {open && (
        <div
          className="md:hidden fixed inset-0 bg-black/80 z-30 transition-opacity"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Minimalist Monochrome Sidebar */}
      <aside
        id="navigation-sidebar"
        aria-label="Main Navigation"
        className={`fixed md:static inset-y-0 left-0 z-40 w-64 flex-shrink-0 bg-[#0a0a0a] border-r border-[#262626] flex flex-col transform transition-transform duration-200 md:transform-none ${
          open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-5 pt-18 md:pt-5">
          {/* Brand header */}
          <div className="mb-7 hidden md:block">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 border border-white flex items-center justify-center bg-[#121212] shrink-0">
                <span className="mono text-xs font-bold text-white">CH</span>
              </div>
              <div className="flex flex-col">
                <span className="text-base font-bold tracking-tight text-white uppercase font-sans">
                  CHATTAM.AI
                </span>
                <span className="text-[9px] mono tracking-widest text-[#737373] uppercase mt-0.5">
                  KBR 2019 ENGINE
                </span>
              </div>
            </div>
          </div>

          {/* Navigation links */}
          <nav className="space-y-1" onClick={() => setOpen(false)}>
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className="block focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
              >
                {({ isActive }) => (
                  <span
                    aria-current={isActive ? 'page' : undefined}
                    className={`group relative flex items-center px-3 py-2.5 text-xs mono tracking-wider transition-all duration-100 cursor-pointer ${
                      isActive
                        ? 'bg-[#181818] text-white border-l-2 border-white'
                        : 'text-[#a3a3a3] hover:text-white hover:bg-[#141414] border-l-2 border-transparent'
                    }`}
                  >
                    <Icon
                      name={item.icon}
                      className={`mr-3 text-base transition-opacity ${
                        isActive ? 'text-white' : 'opacity-60 group-hover:opacity-100'
                      }`}
                    />
                    <span className="font-medium">{item.label}</span>
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="mt-auto p-4 border-t border-[#262626] bg-[#0a0a0a]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
              <span className="text-[10px] mono font-semibold tracking-wider uppercase text-white">
                KBR 2019 Engine
              </span>
            </div>
            <span className="text-[9px] mono text-[#737373]">ONLINE</span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col z-10 min-w-0 pt-14 md:pt-0 bg-[#0a0a0a]">
        {children}
      </main>
    </div>
  )
}

export function Header({ eyebrow, title, subtitle, action, backLink }) {
  return (
    <header className="min-h-[70px] flex items-center justify-between gap-4 px-6 md:px-8 border-b border-[#262626] bg-[#0a0a0a]/90 backdrop-blur-md sticky top-14 md:top-0 z-20">
      <div className="flex items-center gap-4 min-w-0">
        {backLink && (
          <Link
            to={backLink}
            aria-label="Return to previous page"
            className="text-[#737373] hover:text-white transition-colors flex-shrink-0 p-1 border border-transparent hover:border-[#333333] focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
          >
            <Icon name="chevron-left" className="text-xl" />
          </Link>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <div className="text-[9px] mono text-[#737373] uppercase tracking-[0.15em] mb-0.5 truncate">
              {eyebrow}
            </div>
          )}
          <h2 className="text-lg md:text-xl font-bold tracking-tight text-white uppercase font-sans truncate">
            {title}
          </h2>
          {subtitle && (
            <p className="text-xs text-[#a3a3a3] truncate mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>

      {action && <div className="shrink-0">{action}</div>}
    </header>
  )
}
