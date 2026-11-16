import React from 'react'

export function AppFooter() {
  return (
    <footer className="mt-auto px-6 md:px-8 py-4 border-t border-line bg-bg flex flex-col sm:flex-row justify-between items-center gap-3 text-[10px] mono text-ink-3">
      <div>
        Kerala Building Rules (KBR 2019) Automated Compliance Engine
      </div>
      <div className="flex items-center gap-3">
        <span>LSGD Statutory Guidance</span>
        <span className="text-ink-3">•</span>
        <span>Advisory Clearance</span>
      </div>
    </footer>
  )
}
