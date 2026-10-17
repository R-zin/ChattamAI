import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon.jsx'
import { pipelineScript, deriveStatus, analyzePlan } from '../data.js'

const STAGES = [
  { no: '01', name: 'EXTRACT FACTS', desc: 'Extracting architectural parameters', icon: 'drafting-compass' },
  { no: '02', name: 'RETRIEVE RULES', desc: 'Searching KBR 2019 vector store', icon: 'search' },
  { no: '03', name: 'REGULATORY AUDIT', desc: 'Reasoning with Nemotron 120B', icon: 'sparkles' },
  { no: '04', name: 'GENERATE REPORT', desc: 'Synthesizing compliance verdict', icon: 'file-text' },
]
const TOTAL = pipelineScript[pipelineScript.length - 1].t // seconds

export default function Analysis() {
  const nav = useNavigate()
  const { state } = useLocation()
  const [elapsed, setElapsed] = useState(0)
  const [logCount, setLogCount] = useState(0)
  const [error, setError] = useState(null)
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
      .catch((err) => {
        if (cancelledRef.current) return
        setError(err?.message || 'The content of the file is not a building plan.')
      })
  }, [])

  useEffect(() => {
    if (error) return
    startRef.current = Date.now()
    let raf
    const tick = () => {
      if (cancelledRef.current) return
      const t = (Date.now() - startRef.current) / 1000
      setElapsed(t)
      setLogCount(pipelineScript.filter((s) => s.t <= t).length)
      if (t < TOTAL) {
        raf = requestAnimationFrame(tick)
      } else {
        setTimeout(() => {
          if (cancelledRef.current) return
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
  }, [nav, error])

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
    <div className="flex-1 flex flex-col relative bg-[#0a0a0a] text-[#f5f5f5]">
      <div className="blueprint-grid absolute inset-0 z-0 pointer-events-none" />

      {/* Header */}
      <header className="relative z-10 min-h-[76px] flex items-center justify-between gap-4 px-6 md:px-8 border-b border-[#262626] bg-[#0a0a0a]/90 backdrop-blur-md sticky top-14 md:top-0">
        <div className="min-w-0">
          <div className="text-[10px] mono text-[#a3a3a3] uppercase tracking-[0.2em] mb-0.5 flex items-center gap-2 font-semibold">
            <span className={`w-1.5 h-1.5 rounded-full ${error ? 'bg-white' : 'bg-white animate-pulse'}`} />
            {error ? 'PROCESSING PIPELINE // VALIDATION ABORTED' : 'PROCESSING PIPELINE // REAL-TIME INFERENCE'}
          </div>
          <h2 className="text-lg md:text-xl font-bold tracking-tight text-white uppercase font-sans truncate">
            {error ? 'Document Verification Failed' : 'Auditing Building Plan'}
          </h2>
          <p className="text-xs text-[#a3a3a3] truncate font-mono">
            FILE TARGET: <span className="text-white">{state?.meta?.fileName || 'plan_014.pdf'}</span>
          </p>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="text-right hidden sm:block border-r border-[#262626] pr-4">
            <div className="text-[9px] mono text-[#737373] uppercase tracking-wider">
              {error ? 'STATUS' : 'ELAPSED TIME'}
            </div>
            <div className="text-xs mono text-white font-bold">
              {error ? 'HALTED' : `${mm}:${ss}.${ds}`}
            </div>
          </div>
          <button
            onClick={() => nav('/new-check')}
            className="px-3 py-1.5 border border-[#333333] hover:border-white text-xs mono uppercase text-[#a3a3a3] hover:text-white bg-[#121212] transition-colors"
          >
            {error ? 'RETURN TO NEW CHECK' : 'ABORT AUDIT'}
          </button>
        </div>
      </header>

      {/* Main Content: Error Card OR Stages + Terminal */}
      {error ? (
        <div className="relative z-10 flex-1 flex flex-col justify-center px-6 md:px-12 py-10">
          <div className="max-w-2xl mx-auto w-full bg-[#0e0e0e] border border-white p-8 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-[#262626] pb-4 mb-6">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-white inline-block" />
                <span className="text-[10px] mono text-white font-bold uppercase tracking-widest">
                  VALIDATION FAILURE // HTTP 400
                </span>
              </div>
              <span className="text-[10px] mono text-[#a3a3a3] border border-[#333333] px-2 py-0.5">
                NON-ARCHITECTURAL DOCUMENT
              </span>
            </div>

            <div className="space-y-4 mb-8">
              <div className="w-12 h-12 border border-white bg-white text-black flex items-center justify-center font-mono font-bold text-xl mb-4">
                !
              </div>
              <h3 className="text-xl font-bold mono text-white uppercase tracking-tight">
                {error}
              </h3>
              <p className="text-xs mono text-[#a3a3a3] leading-relaxed">
                The submitted file does not contain recognizable architectural parameters, zoning classifications, or dimensional specifications required for Kerala Building Rules (KBR 2019) compliance verification.
              </p>
            </div>

            <div className="border border-[#262626] bg-[#121212] p-4 mb-8 space-y-2">
              <div className="text-[10px] mono text-[#737373] uppercase tracking-wider font-semibold">
                MINIMUM REQUIRED CONTENT SPECIFICATIONS:
              </div>
              <ul className="text-xs mono text-[#d4d4d4] space-y-1.5 list-disc list-inside">
                <li>Occupancy Type (e.g. Group A1 Residential, Group F Commercial)</li>
                <li>Spatial Metrics (e.g. Total built-up area in sq.m, plot area)</li>
                <li>Zoning Clearances (e.g. Front/rear/side setback distances in metres)</li>
                <li>Physical Dimensions (e.g. Building height, number of storeys)</li>
              </ul>
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              <button
                onClick={() => nav('/new-check')}
                className="flex-1 bg-white text-black font-mono font-bold text-xs uppercase px-6 py-3.5 border border-white hover:bg-[#e5e5e5] flex items-center justify-center gap-2 transition-colors cursor-pointer"
              >
                <span>← RETURN TO NEW CHECK</span>
              </button>
              <button
                onClick={() => {
                  sessionStorage.removeItem('chattam.result')
                  nav('/new-check')
                }}
                className="px-6 py-3.5 text-xs mono uppercase text-[#a3a3a3] hover:text-white border border-[#333333] hover:border-white bg-[#0a0a0a] transition-colors"
              >
                UPLOAD DIFFERENT FILE
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="relative z-10 flex-1 flex flex-col justify-center px-6 md:px-12 py-10">
          <div className="max-w-5xl mx-auto w-full mb-12 relative">
            <div className="absolute top-1/2 left-0 w-full h-[1px] bg-[#262626] -translate-y-1/2 z-0" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 relative z-10">
              {STAGES.map((st, i) => {
                const state = i < activeStage ? 'done' : i === activeStage ? 'active' : 'idle'
                return (
                  <div key={st.no} className="flex flex-col items-center relative">
                    {i > 0 && (
                      <div
                        className={`absolute top-1/2 left-[12.5%] w-[25%] h-[1px] -translate-y-1/2 -z-10 hidden md:block ${
                          state === 'active' ? 'bg-white' : state === 'done' ? 'bg-white' : 'bg-[#262626]'
                        }`}
                      />
                    )}
                    <div
                      className={`w-14 h-14 bg-[#0a0a0a] flex items-center justify-center relative mb-3 transition-all ${
                        state === 'done'
                          ? 'border border-white bg-[#121212]'
                          : state === 'active'
                          ? 'border-2 border-white pulse-accent'
                          : 'border border-[#262626] opacity-40'
                      }`}
                    >
                      {state === 'done' && <Icon name="check" className="text-xl text-white" />}
                      {state === 'active' && <Icon name={st.icon} className="text-xl text-white spin-slow" />}
                      {state === 'idle' && <Icon name={st.icon} className="text-xl text-[#737373]" />}
                      {state === 'active' && (
                        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 w-48 text-center">
                          <span className="text-[9px] mono text-white bg-[#181818] border border-white px-2 py-0.5 whitespace-nowrap">
                            {pipelineScript[logCount - 1]?.log?.replace('…','') || 'PROCESSING'}…
                          </span>
                        </div>
                      )}
                      <span
                        className={`absolute -top-2 -right-2 text-[9px] mono font-bold px-1 border ${
                          state === 'idle' ? 'bg-[#121212] border-[#262626] text-[#737373]' : 'bg-white border-white text-black'
                        }`}
                      >
                        {st.no}
                      </span>
                    </div>
                    <div className={`text-center ${state === 'idle' ? 'opacity-40' : ''}`}>
                      <div className={`text-[10px] mono uppercase tracking-wider mb-0.5 font-bold ${state === 'idle' ? 'text-[#737373]' : 'text-white'}`}>
                        {st.name}
                      </div>
                      <div className="text-[11px] text-[#a3a3a3] max-w-[150px] mx-auto">{st.desc}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Live Terminal Log */}
          <div className="max-w-3xl mx-auto w-full">
            <div className="bg-[#0e0e0e] border border-[#262626] shadow-2xl">
              <div className="px-4 py-2.5 border-b border-[#262626] flex items-center justify-between bg-[#121212]">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-white inline-block" />
                  <span className="text-[10px] mono text-white font-bold uppercase tracking-widest">
                    LIVE AUDIT TELEMETRY // LANGGRAPH WORKFLOW
                  </span>
                </div>
                <span className="text-[9px] mono text-[#737373]">STREAMING</span>
              </div>
              <div className="p-5 h-56 overflow-y-auto scroll-mono mono text-xs leading-relaxed space-y-2 bg-[#0e0e0e]">
                {LOGS.map((s, i) => {
                  const latest = i === LOGS.length - 1
                  return (
                    <div key={i} className={`fade-rise ${latest ? 'text-white' : 'text-[#737373]'}`}>
                      <span className="text-[#a3a3a3] mr-2">[{String(Math.floor(s.t / 60)).padStart(2,'0')}:{String(Math.floor(s.t % 60)).padStart(2,'0')}]</span>
                      <span className={latest ? 'font-bold' : ''}>{s.log}</span>
                      {latest && <span className="inline-block w-1.5 h-3.5 bg-white cursor-blink ml-1 align-middle" />}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      <footer className="relative z-10 px-8 py-4 border-t border-[#262626] flex justify-between items-center bg-[#0a0a0a]">
        <div className="text-[10px] mono text-[#737373] uppercase tracking-widest">
          CHATTAM.AI // LANGGRAPH VERIFICATION RUNTIME
        </div>
        <div className="text-[10px] mono text-[#a3a3a3] flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full ${error ? 'bg-white' : 'bg-white animate-pulse'}`} />
          <span>{error ? 'PIPELINE ABORTED // NON-ARCHITECTURAL DOCUMENT' : 'extract_facts → retrieve_kbr_rules → analyze → summarize'}</span>
        </div>
      </footer>
    </div>
  )
}
