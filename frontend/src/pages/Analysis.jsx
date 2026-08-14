import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon.jsx'
import { pipelineScript, deriveStatus, analyzePlan } from '../data.js'

const STAGES = [
  { no: '01', name: 'EXTRACT FACTS', desc: 'Extracting regulated parameters', icon: 'drafting-compass' },
  { no: '02', name: 'RETRIEVE RULES', desc: 'Searching Kerala Building Rules', icon: 'search' },
  { no: '03', name: 'ANALYZE', desc: 'Comparing plan against KBR', icon: 'sparkles' },
  { no: '04', name: 'SUMMARIZE', desc: 'Generating engineer report', icon: 'file-text' },
]
const TOTAL = pipelineScript[pipelineScript.length - 1].t // seconds

export default function Analysis() {
  const nav = useNavigate()
  const { state } = useLocation()
  const [elapsed, setElapsed] = useState(0)
  const [logCount, setLogCount] = useState(0)
  const startRef = useRef(null)
  const cancelledRef = useRef(false)
  const pendingRef = useRef(state?.pending || analyzePlan({ planText: '' }))

  // Run the api call in the background while the animation plays.
  useEffect(() => {
    pendingRef.current
      .then((resp) => {
        if (cancelledRef.current) return
        sessionStorage.setItem('chattam.result', JSON.stringify(resp))
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    startRef.current = Date.now()
    let raf
    const tick = () => {
      const t = (Date.now() - startRef.current) / 1000
      setElapsed(t)
      setLogCount(pipelineScript.filter((s) => s.t <= t).length)
      if (t < TOTAL) {
        raf = requestAnimationFrame(tick)
      } else {
        // finish → route by derived status
        setTimeout(() => {
          let to = '/results/demo'
          try {
            const raw = sessionStorage.getItem('chattam.result')
            if (raw) to = deriveStatus(JSON.parse(raw)) === 'insufficient' ? '/results/insufficient' : '/results/demo'
          } catch {}
          nav(to, { replace: true })
        }, 600)
        return
      }
      if (!cancelledRef.current) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelledRef.current = true
      cancelAnimationFrame(raf)
    }
  }, [nav])

  // current active stage index (0..3)
  const activeStage = (() => {
    let idx = 0
    for (const s of pipelineScript) if (s.t <= elapsed) idx = Math.max(idx, s.stage)
    return Math.min(idx, 3)
  })()

  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0')
  const ss = String(Math.floor(elapsed % 60)).padStart(2, '0')
  const ds = String(Math.floor((elapsed % 1) * 100)).padStart(2, '0')

  const LOGS = pipelineScript.slice(0, logCount)

  return (
    <div className="flex-1 flex flex-col relative">
      <div className="blueprint-grid blueprint-drift absolute inset-0 z-0" />

      {/* Header */}
      <header className="relative z-10 min-h-[80px] flex items-center justify-between gap-4 px-6 md:px-8 border-b border-[#222C3A] bg-[#0A0E13]/80 backdrop-blur-md sticky top-14 md:top-0">
        <div className="min-w-0">
          <div className="text-[10px] mono text-[#22D3EE] uppercase tracking-[0.2em] mb-0.5 flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500" />
            </span>
            Processing Analysis
          </div>
          <h2 className="text-xl md:text-2xl font-semibold tracking-tight text-white truncate">Analyzing Building Plan</h2>
          <p className="text-sm text-[#9AA7B6] truncate">
            Residential Building — Kakkanad · <span className="mono text-[#22D3EE]">{state?.meta?.fileName || 'plan_014.pdf'}</span>
          </p>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="text-right hidden sm:block">
            <div className="text-[10px] mono text-[#5B6879] uppercase">Elapsed Time</div>
            <div className="text-sm mono text-white">{mm}:{ss}.{ds}</div>
          </div>
          <button onClick={() => nav('/new-check')} className="px-4 py-2 border border-[#222C3A] rounded text-xs mono uppercase text-[#9AA7B6] hover:bg-[#161D27] hover:text-white transition-all">
            Abort Process
          </button>
        </div>
      </header>

      {/* Pipeline */}
      <div className="relative z-10 flex-1 flex flex-col justify-center px-6 md:px-12 py-10">
        <div className="max-w-5xl mx-auto w-full mb-14 relative">
          <div className="absolute top-1/2 left-0 w-full h-[2px] bg-[#222C3A] -translate-y-1/2 z-0" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 relative z-10">
            {STAGES.map((st, i) => {
              const state = i < activeStage ? 'done' : i === activeStage ? 'active' : 'idle'
              return (
                <div key={st.no} className="flex flex-col items-center relative">
                  {i > 0 && (
                    <div
                      className={`absolute top-1/2 left-[12.5%] w-[25%] h-[2px] -translate-y-1/2 -z-10 hidden md:block ${
                        state === 'active' ? 'flow-line-active' : state === 'done' ? 'bg-[#22D3EE]' : 'bg-[#222C3A]'
                      }`}
                    />
                  )}
                  <div
                    className={`w-16 h-16 rounded-full bg-[#0A0E13] flex items-center justify-center relative mb-4 ${
                      state === 'done'
                        ? 'border-2 border-[#22D3EE] shadow-[0_0_20px_rgba(34,211,238,0.2)]'
                        : state === 'active'
                        ? 'border-2 border-[#22D3EE] pulse-accent'
                        : 'border border-[#222C3A] opacity-40'
                    }`}
                  >
                    {state === 'done' && <Icon name="check" className="text-2xl text-[#22D3EE]" />}
                    {state === 'active' && <Icon name={st.icon} className="text-2xl text-[#22D3EE] spin-slow" />}
                    {state === 'idle' && <Icon name={st.icon} className="text-2xl text-[#5B6879]" />}
                    {state === 'active' && (
                      <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 w-48 text-center">
                        <span className="text-[9px] mono text-white bg-[#22D3EE]/20 border border-[#22D3EE]/30 px-2 py-0.5 rounded-full whitespace-nowrap">
                          {pipelineScript[logCount - 1]?.log?.replace('…','') || 'PROCESSING'}…
                        </span>
                      </div>
                    )}
                    <span className={`absolute -top-2 -right-2 text-[10px] mono font-bold px-1 rounded ${state === 'idle' ? 'bg-[#222C3A] text-[#5B6879]' : 'bg-[#22D3EE] text-black'}`}>
                      {st.no}
                    </span>
                  </div>
                  <div className={`text-center ${state === 'idle' ? 'opacity-40' : ''}`}>
                    <div className={`text-[10px] mono uppercase tracking-wider mb-1 ${state === 'idle' ? 'text-[#5B6879]' : state === 'active' ? 'text-[#E7ECF2]' : 'text-[#22D3EE]'}`}>
                      {st.name}
                    </div>
                    <div className="text-xs text-[#9AA7B6] max-w-[150px] mx-auto">{st.desc}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Live log */}
        <div className="max-w-3xl mx-auto w-full">
          <div className="bg-[#0C1117] border border-[#222C3A] rounded shadow-2xl">
            <div className="px-4 py-2 border-b border-[#222C3A] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon name="terminal" className="text-[#5B6879]" />
                <span className="text-[10px] mono text-[#5B6879] uppercase tracking-widest">Live Analysis Log</span>
              </div>
              <div className="flex gap-1">
                <div className="w-2 h-2 rounded-full bg-[#222C3A]" />
                <div className="w-2 h-2 rounded-full bg-[#222C3A]" />
              </div>
            </div>
            <div className="p-6 h-56 overflow-y-auto scroll-mono mono text-xs leading-relaxed space-y-1.5">
              {LOGS.map((s, i) => {
                const latest = i === LOGS.length - 1
                return (
                  <div key={i} className={`fade-rise ${latest ? 'text-white' : 'text-[#5B6879]'}`}>
                    <span className={latest ? 'text-[#22D3EE] mr-2' : 'opacity-50 mr-2'}>[{String(Math.floor(s.t / 60)).padStart(2,'0')}:{String(Math.floor(s.t % 60)).padStart(2,'0')}]</span>
                    <span className={latest ? 'font-medium' : ''}>{s.log}</span>
                    {latest && <span className="inline-block w-1.5 h-3.5 bg-[#22D3EE] cursor-blink ml-1 align-middle" />}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <footer className="relative z-10 px-8 py-6 flex justify-between items-center mt-auto">
        <div className="text-[10px] mono text-[#5B6879] uppercase tracking-widest">v0.1.0 • LangGraph runtime</div>
        <div className="text-[10px] mono flex items-center gap-4">
          <span className="text-[#22D3EE] animate-pulse">extract_facts → retrieve → analyze → summarize</span>
        </div>
      </footer>
    </div>
  )
}
