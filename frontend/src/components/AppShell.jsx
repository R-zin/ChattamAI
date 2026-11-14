import React, { useState, useEffect } from 'react'
import { NavLink, Link } from 'react-router-dom'
import Icon from './Icon.jsx'
import ThemeToggle from './ThemeToggle.jsx'

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
    <div className="flex min-h-screen relative bg-bg text-ink">
      {/* Skip link: first focus stop for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-accent focus:text-on-accent focus:px-3 focus:py-2 text-xs font-semibold"
      >
        Skip to content
      </a>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 h-14 flex items-center justify-between px-5 bg-bg border-b-2 border-ink">
        <div className="leading-none">
          <div className="text-base font-extrabold tracking-tight text-ink uppercase">CHATTAM.AI</div>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle variant="icon" />
          <button
            onClick={() => setOpen(!open)}
            className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-2 hover:text-ink border border-line hover:border-ink"
            aria-label={open ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={open}
            aria-controls="navigation-sidebar"
          >
            {open ? 'Close' : 'Menu'}
          </button>
        </div>
      </div>

      {/* Backdrop for mobile drawer */}
      {open && (
        <div
          className="md:hidden fixed inset-0 bg-scrim z-30 transition-opacity"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Left rail: 240px, text-first navigation */}
      <aside
        id="navigation-sidebar"
        aria-label="Main Navigation"
        className={`fixed md:sticky md:top-0 md:h-screen inset-y-0 left-0 z-40 w-60 flex-shrink-0 bg-bg border-r border-line flex flex-col transform transition-transform duration-200 md:transform-none ${
          open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-4 pt-20 md:pt-6 flex-1 overflow-y-auto">
          {/* Wordmark */}
          <div className="mb-8 px-3 hidden md:block">
            <div className="text-lg font-extrabold tracking-tight text-ink uppercase leading-none">
              CHATTAM.AI
            </div>
            <div className="text-[10px] font-semibold tracking-wider text-ink-3 uppercase mt-1.5">
              KBR 2019 ENGINE
            </div>
          </div>

          {/* Navigation links */}
          <nav className="space-y-0.5" onClick={() => setOpen(false)}>
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className="block">
                {({ isActive }) => (
                  <span
                    aria-current={isActive ? 'page' : undefined}
                    className={`group relative flex items-center pl-3 pr-3 py-2.5 text-[13px] transition-colors duration-100 cursor-pointer border-l-[3px] ${
                      isActive
                        ? 'bg-surface-2 text-ink font-bold border-accent'
                        : 'text-ink-2 font-medium hover:text-ink hover:bg-surface-2 border-transparent'
                    }`}
                  >
                    <Icon
                      name={item.icon}
                      className={`mr-3 text-base ${isActive ? 'text-accent' : 'text-ink-3 group-hover:text-ink'}`}
                    />
                    <span>{item.label}</span>
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Rail footer: engine status + theme switch */}
        <div className="border-t border-line p-4 space-y-2">
          <div className="flex items-center justify-between px-3">
            <div className="flex items-center gap-2">
              <span aria-hidden="true" className="inline-block w-2 h-2 rounded-full bg-ok" />
              <span className="text-[11px] font-semibold tracking-wider uppercase text-ink-2">
                KBR 2019 Engine
              </span>
            </div>
            <span className="text-[10px] font-semibold text-ink-3">ONLINE</span>
          </div>
          <ThemeToggle />
        </div>
      </aside>

      {/* Main content */}
      <main id="main-content" className="flex-1 flex flex-col min-w-0 pt-14 md:pt-0 bg-bg">
        {children}
      </main>
    </div>
  )
}

// Page header: small eyebrow, large flush-left title, one-line description, primary
// action at the right, closed by a 2px rule.
export function Header({ eyebrow, title, subtitle, action, backLink }) {
  return (
    <header className="px-6 md:px-8 pt-8 pb-6 border-b-2 border-ink flex flex-col md:flex-row md:items-end justify-between gap-4">
      <div className="flex items-start gap-4 min-w-0">
        {backLink && (
          <Link
            to={backLink}
            aria-label="Return to previous page"
            className="text-ink-2 hover:text-ink transition-colors flex-shrink-0 p-1 mt-1 border border-transparent hover:border-line-strong"
          >
            <Icon name="chevron-left" className="text-xl" />
          </Link>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <div className="text-xs text-ink-3 uppercase tracking-widest font-bold mb-1.5">{eyebrow}</div>
          )}
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-ink leading-[1.05] break-words">
            {title}
          </h1>
          {subtitle && <p className="text-sm text-ink-2 mt-2 max-w-3xl">{subtitle}</p>}
        </div>
      </div>

      {action && <div className="shrink-0">{action}</div>}
    </header>
  )
}
