import React, { useEffect, useState } from 'react'
import { fetchHealth } from '../data.js'

// Animated circular score ring in stark monochrome
export function ScoreRing({ score = 78, max = 100, size = 120, color = '#ffffff' }) {
  const C = 2 * Math.PI * 40
  const [p, setP] = useState(0)
  useEffect(() => {
    const id = requestAnimationFrame(() => setP(Math.max(0, Math.min(1, score / max))))
    return () => cancelAnimationFrame(id)
  }, [score, max])
  const off = C * (1 - p)
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="w-full h-full" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="40" stroke="#262626" strokeWidth="4" fill="transparent" />
        <circle
          cx="50"
          cy="50"
          r="40"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="square"
          fill="transparent"
          strokeDasharray={C}
          strokeDashoffset={off}
          style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.16, 1, 0.3, 1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold mono text-white leading-none">{score}</span>
        <span className="text-[9px] mono text-[#737373] mt-1 uppercase tracking-wider">/ {max}</span>
      </div>
    </div>
  )
}

// Collapsible LangGraph analysis trace in minimalist Swiss B&W
export function AnalysisTrace({ trace = [] }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="bg-[#121212] border border-[#262626] p-5 relative">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between text-left">
        <span className="text-[10px] mono text-[#a3a3a3] uppercase tracking-widest font-semibold">Pipeline Analysis Trace</span>
        <span className="text-[#a3a3a3] text-xs mono border border-[#262626] px-2 py-0.5">{open ? 'COLLAPSE' : 'EXPAND'}</span>
      </button>
      {open && (
        <div className="mt-4 flex flex-col gap-3 relative fade-rise">
          <div className="absolute left-[7px] top-2 bottom-2 w-px bg-[#262626]" />
          {trace.map((n, i) => (
            <div key={i} className="flex gap-3 items-start relative z-10">
              <div className="w-3.5 h-3.5 bg-[#0a0a0a] border border-white flex items-center justify-center flex-shrink-0 mt-0.5">
                <div className="w-1.5 h-1.5 bg-white" />
              </div>
              <div className="min-w-0">
                <div className="text-[11px] mono text-white font-medium">{n.node}</div>
                <div className="text-[9px] mono text-[#737373] uppercase tracking-wider">{n.status?.toUpperCase()} • {n.detail} • {n.ts}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function AppFooter() {
  return (
    <footer className="mt-auto px-6 md:px-8 py-4 border-t border-[#262626] bg-[#0a0a0a] flex flex-col sm:flex-row justify-between items-center gap-3 text-[10px] mono text-[#737373]">
      <div>
        Kerala Building Rules (KBR 2019) Automated Compliance Engine
      </div>
      <div className="flex items-center gap-3">
        <span>LSGD Statutory Guidance</span>
        <span className="text-[#333333]">•</span>
        <span>Advisory Clearance</span>
      </div>
    </footer>
  )
}
