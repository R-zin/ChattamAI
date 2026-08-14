import React, { useEffect, useState } from 'react'

// Animated circular score ring (r=40 → C≈251.33)
export function ScoreRing({ score = 78, max = 100, size = 128, color = 'var(--warn)' }) {
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
        <circle cx="50" cy="50" r="40" stroke="#1C2531" strokeWidth="6" fill="transparent" />
        <circle
          cx="50" cy="50" r="40" stroke={color} strokeWidth="6" strokeLinecap="round" fill="transparent"
          className="score-ring-arc"
          strokeDasharray={C}
          strokeDashoffset={off}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold mono text-white leading-none">{score}</span>
        <span className="text-[10px] mono text-[#5B6879] mt-1">/ {max}</span>
      </div>
    </div>
  )
}

// Collapsible LangGraph analysis trace
export function AnalysisTrace({ trace = [] }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="bg-[#0C1117] border border-[#222C3A] rounded p-5 relative">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between text-left">
        <span className="text-[11px] mono text-[#5B6879] uppercase tracking-widest">Analysis Trace</span>
        <span className="text-[#5B6879] text-sm mono">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="mt-4 flex flex-col gap-4 relative fade-rise">
          <div className="absolute left-[9px] top-2 bottom-2 w-px bg-[#222C3A]" />
          {trace.map((n, i) => (
            <div key={i} className="flex gap-3 items-start relative z-10">
              <div className="w-[18px] h-[18px] rounded-full bg-[#0C1117] border-2 border-[#34D399] flex items-center justify-center flex-shrink-0 mt-0.5">
                <div className="w-1.5 h-1.5 rounded-full bg-[#34D399]" />
              </div>
              <div className="min-w-0">
                <div className="text-[11px] mono text-white">{n.node}</div>
                <div className="text-[9px] mono text-[#5B6879]">{n.status?.toUpperCase()} • {n.detail} • {n.ts}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function AppFooter({ extra }) {
  return (
    <footer className="mt-auto px-8 py-6 border-t border-[#222C3A] flex justify-between items-center">
      <div className="text-[10px] mono text-[#5B6879] uppercase tracking-widest">
        v0.1.0 • FAISS Index Size: 2,481 chunks {extra ? `• ${extra}` : ''}
      </div>
      <div className="text-[10px] mono text-[#5B6879] flex items-center gap-4">
        <span className="hover:text-[#22D3EE] transition-colors cursor-pointer">KBR Documentation</span>
        <span className="hover:text-[#22D3EE] transition-colors cursor-pointer">System Logs</span>
      </div>
    </footer>
  )
}
