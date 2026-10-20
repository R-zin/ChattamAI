import React, { useState, useRef } from 'react'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { checkPdfV2, exportPdfReportV2, exportKSmartV2, evaluatePlanFactsV2 } from '../data.js'

export default function VisualWorkbench() {
  const fileRef = useRef(null)
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [auditResult, setAuditResult] = useState(null)
  const [ksmartModal, setKsmartModal] = useState(null)

  // Interactive What-If slider states
  const [simFacts, setSimFacts] = useState(null)
  const [simEvaluation, setSimEvaluation] = useState(null)

  const handleFileDrop = (e) => {
    e.preventDefault()
    setDrag(false)
    const f = e.dataTransfer.files?.[0]
    if (f && /\.pdf$/i.test(f.name)) {
      setFile(f)
      setError(null)
    } else {
      setError('Please upload a valid architectural drawing PDF.')
    }
  }

  const handleFileSelect = (e) => {
    const f = e.target.files?.[0]
    if (f && /\.pdf$/i.test(f.name)) {
      setFile(f)
      setError(null)
    }
  }

  const runAudit = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const res = await checkPdfV2(file)
      setAuditResult(res)
      setSimFacts(res.plan_facts)
      setSimEvaluation({
        is_compliant: res.is_compliant,
        violations: res.violations,
        coverage_percent: ((res.plan_facts.ground_coverage_sqm / res.plan_facts.plot_area_sqm) * 100),
        max_coverage_percent: 65.0,
        fsi_actual: (res.plan_facts.built_up_area_sqm / res.plan_facts.plot_area_sqm),
        max_fsi_permitted: 2.75,
      })
    } catch (err) {
      setError(err.message || 'Audit failed')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!file) return
    try {
      await exportPdfReportV2(file)
    } catch (err) {
      alert(err.message)
    }
  }

  const handleExportKSmart = async () => {
    if (!auditResult) return
    try {
      const payload = {
        facts: auditResult.plan_facts,
        evaluation: {
          is_compliant: auditResult.is_compliant,
          summary_verdict: auditResult.verdict,
          violations: auditResult.violations,
          coverage_percent: ((auditResult.plan_facts.ground_coverage_sqm / auditResult.plan_facts.plot_area_sqm) * 100),
          max_coverage_percent: 65.0,
          fsi_actual: (auditResult.plan_facts.built_up_area_sqm / auditResult.plan_facts.plot_area_sqm),
          base_fsi: 2.75,
          max_fsi_permitted: 2.75,
          parking_required: auditResult.plan_facts.built_up_area_sqm > 150 ? 1 : 0,
          parking_slots_provided: auditResult.plan_facts.parking_slots_provided,
          concessions_eligible: auditResult.eligible_concessions,
          applied_concessions: auditResult.applied_concessions,
          rule_citations: ["KMBR/KPBR 2019 Rule 24 Table 4", "Rule 25 Table 6"],
        },
        remediations: auditResult.remediations,
      }
      const ksmartRes = await exportKSmartV2(payload)
      setKsmartModal(ksmartRes)
    } catch (err) {
      alert(err.message)
    }
  }

  const updateSimParam = async (param, value) => {
    if (!simFacts) return
    const updated = { ...simFacts, [param]: parseFloat(value) }
    setSimFacts(updated)
    try {
      const evalRes = await evaluatePlanFactsV2(updated)
      setSimEvaluation(evalRes)
    } catch (_) {}
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a] text-[#f5f5f5]">
      <Header
        title="Architectural PDF Visual Workbench"
        subtitle="Deep Area Statement Intelligence, Deterministic Symbolic Verification & Official LSGD Audit Export"
      />

      <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Upload Zone */}
        <div className="bg-[#121212] border border-[#262626] rounded-xl p-6 shadow-sm">
          <div className="flex flex-col md:flex-row items-center gap-6">
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={handleFileDrop}
              onClick={() => fileRef.current?.click()}
              className={`flex-1 w-full border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center cursor-pointer transition-all ${
                drag ? 'border-white bg-[#1a1a1a]' : 'border-[#333333] hover:border-[#555555] bg-[#0e0e0e]'
              }`}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileSelect}
              />
              <Icon name="file-text" className="text-3xl text-neutral-400 mb-2" />
              {file ? (
                <div className="text-center">
                  <div className="font-semibold text-white text-sm">{file.name}</div>
                  <div className="text-xs text-neutral-400 mt-1">{(file.size / 1024).toFixed(1)} KB — Ready to audit</div>
                </div>
              ) : (
                <div className="text-center">
                  <div className="text-sm font-medium text-white">Drop Architectural Drawing PDF here</div>
                  <div className="text-xs text-neutral-500 mt-1">Supports A4/A3/A1/A0 sheets with Area Statement schedules</div>
                </div>
              )}
            </div>

            <div className="flex flex-col gap-3 w-full md:w-64">
              <button
                disabled={!file || loading}
                onClick={runAudit}
                className="w-full py-3 px-4 bg-white text-black font-semibold rounded-lg hover:bg-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center justify-center gap-2 text-sm shadow"
              >
                {loading ? (
                  <>
                    <Icon name="loader" className="animate-spin text-base" />
                    <span>Analyzing PDF...</span>
                  </>
                ) : (
                  <>
                    <Icon name="check-circle" className="text-base" />
                    <span>Run Deep Audit</span>
                  </>
                )}
              </button>
              {file && (
                <button
                  onClick={() => { setFile(null); setAuditResult(null) }}
                  className="w-full py-2 px-3 border border-[#333333] text-neutral-400 rounded-lg hover:text-white text-xs text-center"
                >
                  Clear Selection
                </button>
              )}
            </div>
          </div>

          {error && (
            <div className="mt-4 p-3 bg-red-950/50 border border-red-800 text-red-200 text-xs rounded-lg flex items-center gap-2">
              <Icon name="alert-triangle" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Audit Results Presentation */}
        {auditResult && (
          <div className="space-y-6">
            {/* Top Status Banner */}
            <div
              className={`p-5 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 ${
                auditResult.is_compliant
                  ? 'bg-emerald-950/40 border-emerald-500/60 text-emerald-100'
                  : 'bg-rose-950/40 border-rose-500/60 text-rose-100'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                    auditResult.is_compliant ? 'bg-emerald-600' : 'bg-rose-600'
                  }`}
                >
                  <Icon name={auditResult.is_compliant ? 'check' : 'alert-circle'} className="text-white text-xl" />
                </div>
                <div>
                  <h2 className="text-lg font-bold tracking-tight">
                    {auditResult.is_compliant ? 'FULLY COMPLIANT WITH STATUTORY CODES' : 'NON-COMPLIANT: REVISIONS REQUIRED'}
                  </h2>
                  <p className="text-xs opacity-85 mt-0.5">{auditResult.executive_summary}</p>
                </div>
              </div>

              <div className="flex items-center gap-2 w-full md:w-auto">
                <button
                  onClick={handleDownloadPdf}
                  className="flex-1 md:flex-initial py-2 px-3 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                >
                  <Icon name="download" />
                  <span>Download Audit PDF</span>
                </button>
                <button
                  onClick={handleExportKSmart}
                  className="flex-1 md:flex-initial py-2 px-3 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                >
                  <Icon name="share-2" />
                  <span>K-Smart Export</span>
                </button>
              </div>
            </div>

            {/* Split Workspace */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Facts & Concessions */}
              <div className="lg:col-span-5 space-y-6">
                {/* Extracted Parameters Card */}
                <div className="bg-[#121212] border border-[#262626] rounded-xl p-5">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-4 flex items-center gap-2">
                    <Icon name="layers" />
                    <span>Certified Area Schedule Data</span>
                  </h3>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 bg-[#181818] rounded-lg border border-[#222]">
                      <div className="text-neutral-500 text-[10px] uppercase font-mono">Plot Extent</div>
                      <div className="font-semibold text-white mt-1">
                        {auditResult.plan_facts.plot_area_sqm} m²
                        <span className="text-neutral-400 font-normal ml-1">
                          ({(auditResult.plan_facts.plot_area_sqm / 40.47).toFixed(2)} cents)
                        </span>
                      </div>
                    </div>

                    <div className="p-3 bg-[#181818] rounded-lg border border-[#222]">
                      <div className="text-neutral-500 text-[10px] uppercase font-mono">Built-up Area</div>
                      <div className="font-semibold text-white mt-1">{auditResult.plan_facts.built_up_area_sqm} m²</div>
                    </div>

                    <div className="p-3 bg-[#181818] rounded-lg border border-[#222]">
                      <div className="text-neutral-500 text-[10px] uppercase font-mono">Ground Coverage</div>
                      <div className="font-semibold text-white mt-1">
                        {auditResult.plan_facts.ground_coverage_sqm} m²
                        <span className="text-neutral-400 font-normal ml-1">
                          ({((auditResult.plan_facts.ground_coverage_sqm / auditResult.plan_facts.plot_area_sqm) * 100).toFixed(1)}%)
                        </span>
                      </div>
                    </div>

                    <div className="p-3 bg-[#181818] rounded-lg border border-[#222]">
                      <div className="text-neutral-500 text-[10px] uppercase font-mono">FAR / FSI</div>
                      <div className="font-semibold text-white mt-1">
                        {(auditResult.plan_facts.built_up_area_sqm / auditResult.plan_facts.plot_area_sqm).toFixed(2)}
                      </div>
                    </div>

                    <div className="p-3 bg-[#181818] rounded-lg border border-[#222]">
                      <div className="text-neutral-500 text-[10px] uppercase font-mono">Height & Floors</div>
                      <div className="font-semibold text-white mt-1">
                        {auditResult.plan_facts.building_height_m}m ({auditResult.plan_facts.number_of_floors} Floors)
                      </div>
                    </div>

                    <div className="p-3 bg-[#181818] rounded-lg border border-[#222]">
                      <div className="text-neutral-500 text-[10px] uppercase font-mono">Access Road Width</div>
                      <div className="font-semibold text-white mt-1">{auditResult.plan_facts.road_width_m} m</div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[#222]">
                    <div className="text-neutral-500 text-[10px] uppercase font-mono mb-2">Setback Clearances</div>
                    <div className="grid grid-cols-4 gap-2 text-center text-xs">
                      <div className="p-2 bg-[#181818] rounded border border-[#222]">
                        <div className="text-[10px] text-neutral-400">Front</div>
                        <div className="font-bold text-white mt-0.5">{auditResult.plan_facts.front_setback_m}m</div>
                      </div>
                      <div className="p-2 bg-[#181818] rounded border border-[#222]">
                        <div className="text-[10px] text-neutral-400">Rear</div>
                        <div className="font-bold text-white mt-0.5">{auditResult.plan_facts.rear_setback_m}m</div>
                      </div>
                      <div className="p-2 bg-[#181818] rounded border border-[#222]">
                        <div className="text-[10px] text-neutral-400">Side 1</div>
                        <div className="font-bold text-white mt-0.5">{auditResult.plan_facts.side_setback_1_m}m</div>
                      </div>
                      <div className="p-2 bg-[#181818] rounded border border-[#222]">
                        <div className="text-[10px] text-neutral-400">Side 2</div>
                        <div className="font-bold text-white mt-0.5">{auditResult.plan_facts.side_setback_2_m}m</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Concessions Card */}
                <div className="bg-[#121212] border border-[#262626] rounded-xl p-5">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-3 flex items-center gap-2">
                    <Icon name="shield-check" />
                    <span>Statutory Concessions & Exceptions</span>
                  </h3>
                  {auditResult.applied_concessions && auditResult.applied_concessions.length > 0 ? (
                    <div className="space-y-2">
                      {auditResult.applied_concessions.map((c, i) => (
                        <div key={i} className="text-xs p-2.5 bg-emerald-950/30 border border-emerald-800/40 text-emerald-200 rounded-lg flex items-center gap-2">
                          <Icon name="check" className="text-emerald-400 shrink-0" />
                          <span>{c}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-neutral-500 italic">
                      Standard provisions applied; no statutory concessions claimed for this plot size.
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Scorecard & Remediation */}
              <div className="lg:col-span-7 space-y-6">
                {/* Parameter Scorecard Table */}
                <div className="bg-[#121212] border border-[#262626] rounded-xl overflow-hidden">
                  <div className="p-4 border-b border-[#222] bg-[#161616] flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
                      <Icon name="check-square" />
                      <span>Statutory Parameter Comparison</span>
                    </h3>
                    <span className="text-[10px] font-mono text-neutral-500">KMBR/KPBR 2019</span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#1a1a1a] text-neutral-400 font-mono text-[10px] uppercase">
                        <tr>
                          <th className="py-2.5 px-4">Parameter</th>
                          <th className="py-2.5 px-3">Plan</th>
                          <th className="py-2.5 px-3">Requirement</th>
                          <th className="py-2.5 px-3">Deficit</th>
                          <th className="py-2.5 px-4 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#222]">
                        {auditResult.violations.map((v, i) => (
                          <tr key={i} className="bg-rose-950/20 hover:bg-rose-950/30">
                            <td className="py-2.5 px-4 font-semibold text-rose-200">{v.parameter}</td>
                            <td className="py-2.5 px-3 text-neutral-300">{v.actual_value} {v.unit}</td>
                            <td className="py-2.5 px-3 text-neutral-300">{v.required_value} {v.unit}</td>
                            <td className="py-2.5 px-3 font-mono text-rose-400">-{v.deficit} {v.unit}</td>
                            <td className="py-2.5 px-4 text-right">
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-900/60 text-rose-200 border border-rose-700/50">
                                FAIL
                              </span>
                            </td>
                          </tr>
                        ))}
                        {auditResult.violations.length === 0 && (
                          <tr>
                            <td colSpan="5" className="py-4 text-center text-neutral-400 italic">
                              All measurable parameters strictly satisfy regulatory thresholds!
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Remediation Measures Card */}
                {auditResult.remediations && auditResult.remediations.length > 0 && (
                  <div className="bg-[#121212] border border-[#262626] rounded-xl p-5">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-3 flex items-center gap-2">
                      <Icon name="tool" />
                      <span>Actionable Architectural Redesign Remedies</span>
                    </h3>

                    <div className="space-y-3">
                      {auditResult.remediations.map((r, i) => (
                        <div key={i} className="p-3 bg-[#181818] border border-[#262626] rounded-lg">
                          <div className="flex items-center justify-between text-xs font-semibold text-white">
                            <span>{r.parameter}</span>
                            <span className="text-[10px] font-mono text-rose-400">{r.deficit_summary}</span>
                          </div>
                          <p className="text-xs text-neutral-300 mt-1 leading-relaxed">{r.action}</p>
                          <div className="text-[10px] font-mono text-emerald-400 mt-2 flex items-center gap-1">
                            <Icon name="target" />
                            <span>Target: {r.target_value}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* What-If Simulator */}
                {simFacts && (
                  <div className="bg-[#121212] border border-[#262626] rounded-xl p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400 flex items-center gap-2">
                        <Icon name="sliders" />
                        <span>Interactive Parameter Simulator (What-If)</span>
                      </h3>
                      {simEvaluation && (
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                            simEvaluation.is_compliant
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-600'
                              : 'bg-rose-950 text-rose-300 border-rose-600'
                          }`}
                        >
                          {simEvaluation.is_compliant ? 'SIMULATION: PASS' : 'SIMULATION: FAIL'}
                        </span>
                      )}
                    </div>

                    <div className="space-y-4 pt-2">
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-neutral-400">Front Setback</span>
                          <span className="font-mono text-white">{simFacts.front_setback_m} m</span>
                        </div>
                        <input
                          type="range"
                          min="1.0"
                          max="6.0"
                          step="0.1"
                          value={simFacts.front_setback_m}
                          onChange={(e) => updateSimParam('front_setback_m', e.target.value)}
                          className="w-full accent-white cursor-pointer"
                        />
                      </div>

                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-neutral-400">Rear Setback</span>
                          <span className="font-mono text-white">{simFacts.rear_setback_m} m</span>
                        </div>
                        <input
                          type="range"
                          min="0.8"
                          max="5.0"
                          step="0.1"
                          value={simFacts.rear_setback_m}
                          onChange={(e) => updateSimParam('rear_setback_m', e.target.value)}
                          className="w-full accent-white cursor-pointer"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* K-Smart Export Modal */}
        {ksmartModal && (
          <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
            <div className="bg-[#141414] border border-[#333] rounded-xl max-w-2xl w-full p-6 space-y-4 max-h-[85vh] flex flex-col">
              <div className="flex items-center justify-between border-b border-[#262626] pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Icon name="code" />
                  <span>Kerala LSGD K-Smart / Sanketham Export Payload</span>
                </h3>
                <button onClick={() => setKsmartModal(null)} className="text-neutral-400 hover:text-white">
                  <Icon name="x" />
                </button>
              </div>

              <div className="flex-1 overflow-auto bg-[#0a0a0a] p-3 rounded-lg border border-[#222] font-mono text-[11px] text-neutral-300">
                <pre>{JSON.stringify(ksmartModal, null, 2)}</pre>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(ksmartModal, null, 2))
                    alert('Copied K-Smart JSON to clipboard!')
                  }}
                  className="py-2 px-3 bg-white text-black text-xs font-semibold rounded-lg hover:bg-neutral-200"
                >
                  Copy JSON
                </button>
                <button
                  onClick={() => setKsmartModal(null)}
                  className="py-2 px-3 border border-[#333] text-neutral-300 text-xs rounded-lg hover:text-white"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <AppFooter />
    </div>
  )
}
