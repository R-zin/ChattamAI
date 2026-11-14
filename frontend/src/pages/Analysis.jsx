import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon.jsx'
import { pipelineScript, deriveStatus, analyzePlan, getPendingAnalysis } from '../data.js'

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
  const [apiDone, setApiDone] = useState(false)
  const startRef = useRef(null)
  const cancelledRef = useRef(false)
  const navigatedRef = useRef(false)
  const pendingRef = useRef(getPendingAnalysis() || state?.pending || analyzePlan({ planText: '' }))

  // Run the api call in the background while the animation plays.
  useEffect(() => {
    pendingRef.current
      .then((resp) => {
        if (cancelledRef.current) return
        sessionStorage.setItem('chattam.result', JSON.stringify(resp))
        setApiDone(true)
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
      setElapsed(Math.min(t, TOTAL))
      setLogCount(pipelineScript.filter((s) => s.t <= t).length)
      if (t < TOTAL) {
        raf = requestAnimationFrame(tick)
      }
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelledRef.current = true
      cancelAnimationFrame(raf)
    }
  }, [error])

  // Synchronize navigation: only navigate once animation has finished AND api promise has resolved
  useEffect(() => {
    if (error || navigatedRef.current) return
    if (elapsed >= TOTAL && apiDone) {
      navigatedRef.current = true
      const timer = setTimeout(() => {
        if (cancelledRef.current) return
        let to = '/results/demo'
        try {
          const raw = sessionStorage.getItem('chattam.result')
          if (raw) to = deriveStatus(JSON.parse(raw)) === 'insufficient' ? '/results/insufficient' : '/results/demo'
        } catch {}
        nav(to, { replace: true })
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [elapsed, apiDone, error, nav])

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
    <div className="flex-1 flex flex-col relative bg-bg text-ink">

      {/* Header */}
      <header className="relative z-10 min-h-[70px] flex items-center justify-between gap-4 px-6 md:px-8 border-b border-line bg-bg/90 backdrop-blur-md sticky top-14 md:top-0">
        <div className="min-w-0">
          <div className="text-[9px] mono text-ink-2 uppercase tracking-[0.15em] mb-0.5 flex items-center gap-2 font-semibold">
            <span className={`w-1.5 h-1.5 rounded-full ${error ? 'bg-accent' : 'bg-accent animate-pulse'}`} />
            {error ? 'VALIDATION FAILED' : 'REAL-TIME VERIFICATION'}
          </div>
          <h2 className="text-lg md:text-xl font-bold tracking-tight text-ink uppercase font-sans truncate">
            {error ? 'Document Verification Failed' : 'Auditing Building Plan'}
          </h2>
          <p className="text-xs text-ink-2 truncate font-mono">
            TARGET: <span className="text-ink">{state?.meta?.fileName || 'plan_014.pdf'}</span>
          </p>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="text-right hidden sm:block border-r border-line pr-4">
            <div className="text-[9px] mono text-ink-3 uppercase tracking-wider">
              {error ? 'STATUS' : 'ELAPSED TIME'}
            </div>
            <div className="text-xs mono text-ink font-bold">
              {error ? 'HALTED' : `${mm}:${ss}.${ds}`}
            </div>
          </div>
          <button
            onClick={() => nav('/new-check')}
            className="px-3 py-1.5 border border-line hover:border-ink text-xs mono uppercase text-ink-2 hover:text-ink bg-surface transition-colors"
          >
            {error ? 'RETURN TO NEW CHECK' : 'ABORT AUDIT'}
          </button>
        </div>
      </header>

      {/* Main Content: Error Card OR Stages + Terminal */}
      {error ? (
        <div className="relative z-10 flex-1 flex flex-col justify-center px-6 md:px-12 py-10">
          <div className="max-w-2xl mx-auto w-full bg-inset border border-ink p-8 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-line pb-4 mb-6">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-accent inline-block" />
                <span className="text-[10px] mono text-ink font-bold uppercase tracking-widest">
                  VALIDATION FAILURE // HTTP 400
                </span>
              </div>
              <span className="text-[10px] mono text-ink-2 border border-line px-2 py-0.5">
                NON-ARCHITECTURAL DOCUMENT
              </span>
            </div>

            <div className="space-y-4 mb-8">
              <div className="w-12 h-12 border border-ink bg-accent text-on-accent flex items-center justify-center font-mono font-bold text-xl mb-4">
                !
              </div>
              <h3 className="text-xl font-bold mono text-ink uppercase tracking-tight">
                {error}
              </h3>
              <p className="text-xs mono text-ink-2 leading-relaxed">
                The submitted file does not contain recognizable architectural parameters, zoning classifications, or dimensional specifications required for Kerala Building Rules (KBR 2019) compliance verification.
              </p>
            </div>

            <div className="border border-line bg-surface p-4 mb-8 space-y-2">
              <div className="text-[10px] mono text-ink-3 uppercase tracking-wider font-semibold">
                MINIMUM REQUIRED CONTENT SPECIFICATIONS:
              </div>
              <ul className="text-xs mono text-ink-2 space-y-1.5 list-disc list-inside">
                <li>Occupancy Type (e.g. Group A1 Residential, Group F Commercial)</li>
                <li>Spatial Metrics (e.g. Total built-up area in sq.m, plot area)</li>
                <li>Zoning Clearances (e.g. Front/rear/side setback distances in metres)</li>
                <li>Physical Dimensions (e.g. Building height, number of storeys)</li>
              </ul>
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              <button
                onClick={() => nav('/new-check')}
                className="flex-1 bg-accent text-on-accent font-mono font-bold text-xs uppercase px-6 py-3.5 border border-ink hover:bg-accent-strong flex items-center justify-center gap-2 transition-colors cursor-pointer"
              >
                <span>← RETURN TO NEW CHECK</span>
              </button>
              <button
                onClick={() => {
                  sessionStorage.removeItem('chattam.result')
                  nav('/new-check')
                }}
                className="px-6 py-3.5 text-xs mono uppercase text-ink-2 hover:text-ink border border-line hover:border-ink bg-bg transition-colors"
              >
                UPLOAD DIFFERENT FILE
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="relative z-10 flex-1 flex flex-col justify-center px-6 md:px-12 py-10">
          <div className="max-w-5xl mx-auto w-full mb-12 relative">
            <div className="absolute top-1/2 left-0 w-full h-[1px] bg-surface-3 -translate-y-1/2 z-0" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 relative z-10">
              {STAGES.map((st, i) => {
                const state = i < activeStage ? 'done' : i === activeStage ? 'active' : 'idle'
                return (
                  <div key={st.no} className="flex flex-col items-center relative">
                    {i > 0 && (
                      <div
                        className={`absolute top-1/2 left-[12.5%] w-[25%] h-[1px] -translate-y-1/2 -z-10 hidden md:block ${
                          state === 'active' ? 'bg-accent' : state === 'done' ? 'bg-accent' : 'bg-surface-3'
                        }`}
                      />
                    )}
                    <div
                      className={`w-14 h-14 bg-bg flex items-center justify-center relative mb-3 transition-all ${
                        state === 'done'
                          ? 'border border-ink bg-surface'
                          : state === 'active'
                          ? 'border-2 border-ink pulse-accent'
                          : 'border border-dashed border-line-strong'
                      }`}
                    >
                      {state === 'done' && <Icon name="check" className="text-xl text-ink" />}
                      {state === 'active' && <Icon name={st.icon} className="text-xl text-ink spin-slow" />}
                      {state === 'idle' && <Icon name={st.icon} className="text-xl text-ink-3" />}
                      {state === 'active' && (
                        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 w-48 text-center">
                          <span className="text-[9px] mono text-ink bg-surface-2 border border-ink px-2 py-0.5 whitespace-nowrap">
                            {pipelineScript[logCount - 1]?.log?.replace('…','') || 'PROCESSING'}…
                          </span>
                        </div>
                      )}
                      <span
                        className={`absolute -top-2 -right-2 text-[9px] mono font-bold px-1 border ${
                          state === 'idle' ? 'bg-surface border-line text-ink-3' : 'bg-accent border-ink text-on-accent'
                        }`}
                      >
                        {st.no}
                      </span>
                    </div>
                    <div className="text-center">
                      <div className={`text-[10px] mono uppercase tracking-wider mb-0.5 font-bold ${state === 'idle' ? 'text-ink-3' : 'text-ink'}`}>
                        {st.name}
                      </div>
                      <div className={`text-[11px] max-w-[150px] mx-auto ${state === 'idle' ? 'text-ink-3' : 'text-ink-2'}`}>{st.desc}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Live Terminal Log */}
          <div className="max-w-3xl mx-auto w-full">
            <div className="bg-inset border border-line shadow-2xl">
              <div className="px-4 py-2.5 border-b border-line flex items-center justify-between bg-surface">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-accent inline-block" />
                  <span className="text-[10px] mono text-ink font-bold uppercase tracking-widest">
                    LIVE AUDIT TELEMETRY // LANGGRAPH WORKFLOW
                  </span>
                </div>
                <span className="text-[9px] mono text-ink-3">STREAMING</span>
              </div>
              <div className="p-5 h-56 overflow-y-auto scroll-mono mono text-xs leading-relaxed space-y-2 bg-inset">
                {LOGS.map((s, i) => {
                  const latest = i === LOGS.length - 1
                  return (
                    <div key={i} className={`fade-rise ${latest ? 'text-ink' : 'text-ink-3'}`}>
                      <span className="text-ink-2 mr-2">[{String(Math.floor(s.t / 60)).padStart(2,'0')}:{String(Math.floor(s.t % 60)).padStart(2,'0')}]</span>
                      <span className={latest ? 'font-bold' : ''}>{s.log}</span>
                      {latest && <span className="inline-block w-1.5 h-3.5 bg-accent cursor-blink ml-1 align-middle" />}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      <footer className="relative z-10 px-6 md:px-8 py-4 border-t border-line flex justify-between items-center bg-bg text-[10px] mono text-ink-3">
        <div>
          Kerala Building Rules (KBR 2019)
        </div>
        <div className="flex items-center gap-2 text-ink-2">
          <span className={`w-1.5 h-1.5 rounded-full ${error ? 'bg-accent' : 'bg-accent animate-pulse'}`} />
          <span>{error ? 'Validation Failed' : 'Facts Extraction → Rule Retrieval → Compliance Reasoning'}</span>
        </div>
      </footer>
    </div>
  )
}
