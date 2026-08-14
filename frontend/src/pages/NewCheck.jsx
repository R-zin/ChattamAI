import React, { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { analyzePlan } from '../data.js'

const PLACEHOLDER =
  '3-floor residential building, total height 12m, front setback 1m, rear setback 2m, plot area 240 sq m, built-up area 410 sq m, 4 parking spaces, staircase width 1.0m…'

export default function NewCheck() {
  const nav = useNavigate()
  const fileRef = useRef(null)
  const [planText, setPlanText] = useState('')
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const ready = planText.trim().length > 0 || file

  const onDrop = (e) => {
    e.preventDefault()
    setDrag(false)
    const f = e.dataTransfer.files?.[0]
    if (f && /\.(pdf|txt|md|text)$/i.test(f.name)) setFile(f)
  }

  const run = async () => {
    if (!ready || busy) return
    setBusy(true)
    // Pre-stage the submission so Analysis can call the real API if configured.
    try {
      sessionStorage.setItem('chattam.pending', JSON.stringify({ planText, fileName: file?.name || null }))
    } catch {}
    const p = analyzePlan({ planText, file })
    sessionStorage.setItem('chattam.pendingCall', 'pending')
    nav('/analysis', { state: { pending: p, meta: { fileName: file?.name || 'pasted-plan.txt' } } })
  }

  return (
    <>
      <Header
        eyebrow="Building Analysis"
        title="New Compliance Check"
        subtitle="Upload a building plan or paste its description to verify against Kerala Building Rules"
      />

      <div className="p-6 md:p-10 flex-1">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
            className={`relative cursor-pointer rounded border-2 border-dashed p-12 text-center transition-all overflow-hidden ${
              drag ? 'border-[#22D3EE] bg-[#22D3EE]/5 shadow-[0_0_30px_rgba(34,211,238,0.15)]' : 'border-[#2E3B4D] bg-[#10151C] hover:border-[#22D3EE]/50'
            }`}
          >
            <div className="blueprint-grid absolute inset-0 opacity-60" />
            <div className="relative">
              <div className="mx-auto w-14 h-14 rounded-full border border-[#222C3A] bg-[#161D27] flex items-center justify-center mb-4">
                <Icon name="drafting-compass" className="text-2xl text-[#22D3EE]" />
              </div>
              <div className="text-lg font-semibold text-white mb-1">{file ? file.name : 'Upload Building Plan'}</div>
              <div className="text-sm text-[#9AA7B6] mb-6">{file ? `${(file.size / 1024).toFixed(0)} KB selected — ready to analyze` : 'Drop a PDF here or browse files'}</div>
              <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.text" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <div className="flex items-center justify-center gap-6">
                <div>
                  <div className="text-[9px] mono text-[#5B6879] uppercase tracking-wider mb-1">Supported Formats</div>
                  <div className="text-xs mono text-white">PDF, TXT</div>
                </div>
                <div className="w-px h-8 bg-[#222C3A]" />
                <div>
                  <div className="text-[9px] mono text-[#5B6879] uppercase tracking-wider mb-1">Maximum Size</div>
                  <div className="text-xs mono text-white">25 MB</div>
                </div>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-4">
            <div className="flex-1 h-px bg-[#222C3A]" />
            <span className="text-[10px] mono text-[#5B6879] uppercase tracking-widest">OR</span>
            <div className="flex-1 h-px bg-[#222C3A]" />
          </div>

          {/* Paste description */}
          <div className="bg-[#10151C] border border-[#222C3A] rounded overflow-hidden">
            <div className="px-4 py-2 border-b border-[#222C3A] flex items-center justify-between bg-[#161D27]/50">
              <div className="text-xs mono text-white flex items-center gap-2">
                <Icon name="file-text" className="text-[#22D3EE]" /> Paste Plan Description
              </div>
              <div className="text-[9px] mono text-[#5B6879]">UTF-8 INPUT</div>
            </div>
            <textarea
              value={planText}
              onChange={(e) => setPlanText(e.target.value)}
              placeholder={PLACEHOLDER}
              rows={6}
              className="w-full mono text-sm bg-[#1C2531]/40 text-[#E7ECF2] placeholder-[#5B6879] p-4 outline-none resize-y focus:bg-[#1C2531]/70 transition-colors border-t-0 border border-transparent focus:border-[#22D3EE]/40"
            />
          </div>

          {/* CTA */}
          <button
            onClick={run}
            disabled={!ready || busy}
            className={`w-full accent-gradient px-6 py-4 rounded text-base font-semibold text-black flex items-center justify-center gap-2 transition-all shadow-[0_0_20px_rgba(34,211,238,0.2)] ${
              ready && !busy ? 'hover:brightness-110' : 'opacity-40 cursor-not-allowed shadow-none'
            }`}
          >
            {busy ? 'Queueing analysis…' : 'Analyze Building Plan'}
            <Icon name="arrow-right" className="text-xl" />
          </button>

          <div className="flex items-start gap-2 text-[11px] mono text-[#5B6879] leading-relaxed">
            <Icon name="info" className="text-[#22D3EE]/60 flex-shrink-0 mt-0.5" />
            AI-assisted assessment — findings require engineer review. Nothing here is an official compliance approval.
          </div>
        </div>
      </div>
      <AppFooter extra="READY FOR INGESTION" />
    </>
  )
}
