import React from 'react'
import ThemeToggle from './ThemeToggle.jsx'

// Shared sign-in / sign-up frame. Asymmetric on the 12-column grid: an editorial
// panel (columns 1-7, desktop only) and the form (columns 8-12), split by a rule.
export default function AuthLayout({ title, subtitle, eyebrow = 'CHATTAM.AI', children }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-12 bg-bg text-ink">
      <aside
        aria-hidden="true"
        className="hidden lg:flex lg:col-span-7 flex-col justify-between p-12 border-r border-ink"
      >
        <div>
          <div className="text-lg font-extrabold tracking-tight uppercase leading-none">CHATTAM.AI</div>
          <div className="text-[10px] font-semibold tracking-wider text-ink-3 uppercase mt-1.5">
            KBR 2019 ENGINE
          </div>
        </div>
        <div>
          <p className="text-6xl xl:text-7xl font-extrabold tracking-[-0.03em] leading-[1.02] max-w-3xl">
            Building plans, checked against the rules.
          </p>
          <p className="text-base text-ink-2 mt-8 max-w-md leading-relaxed">
            Kerala Building Rules 2019 compliance platform for local self-government engineers.
          </p>
        </div>
      </aside>

      <main className="lg:col-span-5 bg-surface flex flex-col">
        <div className="flex items-center justify-between px-6 md:px-12 pt-6">
          <div className="lg:hidden text-base font-extrabold tracking-tight uppercase">CHATTAM.AI</div>
          <div className="ml-auto">
            <ThemeToggle variant="icon" />
          </div>
        </div>
        <div className="flex-1 flex items-center">
          <div className="w-full max-w-md mx-auto px-6 md:px-0 py-10 space-y-6">
            <div className="border-b-2 border-ink pb-5">
              <div className="text-xs uppercase tracking-widest font-bold text-ink-3 mb-2">{eyebrow}</div>
              <h1 className="text-3xl font-extrabold tracking-tight leading-tight">{title}</h1>
              {subtitle && <p className="text-sm text-ink-2 mt-2">{subtitle}</p>}
            </div>
            {children}
          </div>
        </div>
      </main>
    </div>
  )
}
