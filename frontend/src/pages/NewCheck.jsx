import React, { useRef, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { analyzePlan, isBuildingPlanText, setPendingAnalysis } from '../data.js'

const SAMPLES = [
  {
    label: 'Group A1 Residential (KBR 2019)',
    text: 'Single family residential building under Group A1 in Category-II Village Panchayat with total built-up area of 90 sq. metres, 2 storeys. The proposed front distance from the street boundary is 1.0 metre and side distance is 50 centimetres. Plot area 240 sq m.',
  },
  {
    label: 'Group F Commercial Complex',
    text: 'Commercial building under Group F Occupancy on a plot of 850 sq. metres. Abutting public street width is 6.5 metres. Proposed building height is 16 metres with 4 storeys. Front open space provided is 2.5 metres, rear setback 2.0 metres, and side setbacks 1.5 metres.',
  },
  {
    label: 'Insufficient Specification',
    text: 'Proposed small shed structure in residential plot. Details on height and exact setbacks pending surveyor measurements.',
  },
]

export default function NewCheck() {
  const nav = useNavigate()
  const fileRef = useRef(null)
  const [planText, setPlanText] = useState('')
  const [file, setFile] = useState(null)
  const [fileError, setFileError] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const ready = planText.trim().length > 0 || file

  useEffect(() => {
    if (file && /\.(png|jpe?g|webp|tiff?)$/i.test(file.name)) {
      const url = URL.createObjectURL(file)
      setPreviewUrl(url)
      return () => URL.revokeObjectURL(url)
    }
    setPreviewUrl(null)
  }, [file])

  const handleFile = async (f) => {
    setFileError(null)
    setFile(f)
    if (f && /\.(txt|md|text)$/i.test(f.name)) {
      try {
        const text = await f.text()
        if (!isBuildingPlanText(text)) {
          setFileError('The content of the file is not a building plan.')
        }
      } catch (_) {}
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDrag(false)
    const f = e.dataTransfer.files?.[0]
    if (f && /\.(pdf|txt|md|text|png|jpe?g|webp|tiff?)$/i.test(f.name)) handleFile(f)
  }

  const run = async () => {
    if (!ready || busy) return
    if (fileError) return
    if (!file && planText.trim()) {
      if (!isBuildingPlanText(planText)) {
        setFileError('The content of the file is not a building plan.')
        return
      }
    }
    setBusy(true)
    try {
      sessionStorage.setItem('chattam.pending', JSON.stringify({ planText, fileName: file?.name || null }))
    } catch {}
    const p = analyzePlan({ planText, file })
    setPendingAnalysis(p)
    sessionStorage.setItem('chattam.pendingCall', 'pending')
    nav('/analysis', { state: { meta: { fileName: file?.name || 'pasted-plan.txt' } } })
  }

  return (
    <>
      <Header
        eyebrow="KBR 2019 AUDIT"
        title="New Compliance Check"
        subtitle="Submit architectural plan specifications to execute automated compliance analysis"
      />

      <div className="p-6 md:p-8 flex-1 bg-[#0a0a0a]">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Action Ribbon & Quick Samples */}
          <div className="border border-[#262626] bg-[#121212] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="text-[10px] mono text-[#737373] uppercase tracking-wider font-semibold">
              SAMPLE PRESETS:
            </div>
            <div className="flex flex-wrap gap-2">
              {SAMPLES.map((s, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setPlanText(s.text)
                    setFile(null)
                    setFileError(null)
                  }}
                  className="text-[10px] mono border border-[#333333] hover:border-white text-[#a3a3a3] hover:text-white px-2.5 py-1 bg-[#0a0a0a] transition-colors"
                >
                  [{s.label}]
                </button>
              ))}
            </div>
          </div>

          {/* File Upload Dropzone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
            className={`relative cursor-pointer border-2 border-dashed p-10 text-center transition-all overflow-hidden bg-[#0e0e0e] ${
              fileError ? 'border-white bg-[#1a0e0e]' : drag ? 'border-white bg-[#181818]' : 'border-[#333333] hover:border-white'
            }`}
          >
            <div className="blueprint-grid absolute inset-0 opacity-40 pointer-events-none" />
            <div className="relative">
              <div className="mx-auto w-12 h-12 border border-[#404040] bg-[#121212] flex items-center justify-center mb-3">
                <Icon name="drafting-compass" className="text-xl text-white" />
              </div>
              <div className="text-sm font-bold mono text-white uppercase tracking-wider mb-1">
                {file ? file.name : 'UPLOAD ARCHITECTURAL BLUEPRINT (PDF OR IMAGE)'}
              </div>
              <div className="text-xs text-[#a3a3a3] mb-4 mono">
                {file ? `${(file.size / 1024).toFixed(0)} KB LOADED — READY TO AUDIT` : 'Drag and drop file here, or click to browse'}
              </div>

              {previewUrl && (
                <div className="mb-4 flex flex-col items-center">
                  <div className="text-[9px] mono text-[#a3a3a3] mb-1 uppercase tracking-wider">Plan Image Preview (Layout OCR)</div>
                  <img
                    src={previewUrl}
                    alt="Plan Preview"
                    className="max-h-36 max-w-full border border-[#262626] object-contain bg-[#0a0a0a]"
                  />
                </div>
              )}

              <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.text,.png,.jpg,.jpeg,.webp,.tiff" className="hidden" onChange={(e) => handleFile(e.target.files?.[0] || null)} />

              <div className="inline-flex items-center gap-6 border border-[#262626] px-4 py-2 bg-[#121212]">
                <div className="text-left">
                  <span className="text-[9px] mono text-[#737373] uppercase tracking-wider block">SUPPORTED FORMATS</span>
                  <span className="text-[11px] mono text-white">PDF, TXT, PNG, JPG</span>
                </div>
                <div className="w-px h-6 bg-[#262626]" />
                <div className="text-left">
                  <span className="text-[9px] mono text-[#737373] uppercase tracking-wider block">MAX PAYLOAD</span>
                  <span className="text-[11px] mono text-white">25 MB</span>
                </div>
              </div>
            </div>
          </div>

          {/* Validation Error Banner */}
          {fileError && (
            <div className="border border-white bg-[#121212] p-4 flex items-start gap-3 shadow-lg">
              <div className="w-5 h-5 flex-shrink-0 border border-white flex items-center justify-center font-mono font-bold text-xs bg-white text-black mt-0.5">
                !
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs mono font-bold text-white uppercase tracking-wider">
                  Validation Error: Invalid Document Content
                </div>
                <div className="text-xs mono text-[#ffffff] mt-1 font-semibold">
                  {fileError}
                </div>
                <div className="text-[10px] mono text-[#a3a3a3] mt-1 leading-relaxed">
                  The document does not contain recognizable architectural parameters, zoning classifications, or dimensional specifications required for Kerala Building Rules (KBR 2019) compliance verification.
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFileError(null)}
                className="text-xs mono text-[#737373] hover:text-white border border-[#333333] hover:border-white px-2 py-1 bg-[#0a0a0a] transition-colors"
              >
                DISMISS
              </button>
            </div>
          )}

          {/* Section Divider */}
          <div className="flex items-center gap-4">
            <div className="flex-1 h-px bg-[#262626]" />
            <span className="text-[10px] mono text-[#737373] uppercase tracking-widest font-semibold">OR ENTER SPECIFICATION TEXT</span>
            <div className="flex-1 h-px bg-[#262626]" />
          </div>

          {/* Text Editor Console */}
          <div className="border border-[#262626] bg-[#0e0e0e] overflow-hidden">
            <div className="px-4 py-2.5 border-b border-[#262626] flex items-center justify-between bg-[#121212]">
              <div className="text-xs mono text-white flex items-center gap-2 font-semibold uppercase tracking-wider">
                <span className="w-1.5 h-1.5 bg-white inline-block" />
                Plan Specification Description
              </div>
            </div>
            <textarea
              value={planText}
              onChange={(e) => {
                setPlanText(e.target.value)
                if (fileError) setFileError(null)
              }}
              placeholder="e.g. Single family residential building under Group A1 in Category-II Village Panchayat with total built-up area of 90 sq. metres, 2 storeys. Proposed front distance is 1.0m and side distance is 50cm."
              rows={7}
              className="w-full mono text-xs leading-relaxed bg-[#0e0e0e] text-[#f5f5f5] placeholder-[#525252] p-4 outline-none resize-y border-none focus:bg-[#121212] transition-colors"
            />
          </div>

          {/* Primary Action Button */}
          <div className="flex flex-col sm:flex-row items-center gap-4">
            <button
              onClick={run}
              disabled={!ready || busy}
              className={`flex-1 w-full bg-white text-black font-mono font-bold text-sm px-6 py-4 border border-white flex items-center justify-center gap-3 transition-all ${
                ready && !busy ? 'hover:bg-[#e5e5e5] cursor-pointer' : 'opacity-40 cursor-not-allowed'
              }`}
            >
              <span>{busy ? 'INITIALIZING COMPLIANCE PIPELINE…' : 'RUN COMPLIANCE CHECK →'}</span>
              <Icon name="arrow-right" className="text-lg" />
            </button>

            {(planText || file) && (
              <button
                type="button"
                onClick={() => {
                  setPlanText('')
                  setFile(null)
                  setFileError(null)
                }}
                className="w-full sm:w-auto px-4 py-4 text-xs mono text-[#a3a3a3] hover:text-white border border-[#333333] hover:border-white bg-[#0e0e0e] transition-colors"
              >
                RESET FORM
              </button>
            )}
          </div>

          <div className="flex items-start gap-2.5 text-[10px] mono text-[#737373] leading-relaxed border-t border-[#262626] pt-4">
            <span className="text-white font-bold">[NOTE]</span>
            <span>AI-assisted zoning assessments are advisory calculations based on the Kerala Panchayat Building Rules 2019. Final statutory clearances must be issued by the Secretary of the local self-government institution.</span>
          </div>
        </div>
      </div>

      <AppFooter />
    </>
  )
}
