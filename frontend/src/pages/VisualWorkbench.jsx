import React, { useState, useRef } from 'react'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { toast } from '../components/Toast.jsx'
import Pill from '../components/Pill.jsx'
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  Modal,
  Slider,
  EmptyState,
} from '../components/ui/index.js'
import {
  checkPdfV2,
  exportPdfReportV2,
  exportKSmartV2,
  evaluatePlanFactsV2,
} from '../data.js'

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
  const [simulating, setSimulating] = useState(false)

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
        coverage_percent:
          (res.plan_facts.ground_coverage_sqm / res.plan_facts.plot_area_sqm) * 100,
        max_coverage_percent: 65.0,
        fsi_actual:
          res.plan_facts.built_up_area_sqm / res.plan_facts.plot_area_sqm,
        max_fsi_permitted: 2.75,
      })
      toast('Architectural drawing audit completed successfully.', 'ok')
    } catch (err) {
      setError(err.message || 'Audit failed')
      toast(`Audit failed: ${err.message}`, 'danger')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!file) return
    try {
      toast('Generating signed LSGD PDF certificate…', 'ok')
      await exportPdfReportV2(file)
      toast('PDF certificate downloaded.', 'ok')
    } catch (err) {
      toast(err.message || 'Export error', 'danger')
    }
  }

  const handleExportKSmart = async () => {
    if (!auditResult) return
    try {
      const payload = {
        facts: auditResult.plan_facts,
        evaluation: auditResult.evaluation || {
          is_compliant: auditResult.is_compliant,
          summary_verdict: auditResult.verdict,
          violations: auditResult.violations,
          coverage_percent:
            (auditResult.plan_facts.ground_coverage_sqm /
              auditResult.plan_facts.plot_area_sqm) *
            100,
          max_coverage_percent: 65.0,
          fsi_actual:
            auditResult.plan_facts.built_up_area_sqm /
            auditResult.plan_facts.plot_area_sqm,
          base_fsi: 2.75,
          max_fsi_permitted: 2.75,
          parking_required:
            auditResult.plan_facts.built_up_area_sqm > 150 ? 1 : 0,
          parking_slots_provided: auditResult.plan_facts.parking_slots_provided,
          concessions_eligible: auditResult.eligible_concessions,
          applied_concessions: auditResult.applied_concessions,
          rule_citations: [
            'KMBR/KPBR 2019 Rule 24 Table 4',
            'Rule 25 Table 6',
          ],
        },
        remediations: auditResult.remediations,
      }
      const ksmartRes = await exportKSmartV2(payload)
      setKsmartModal(ksmartRes)
      toast('Generated K-Smart LSGD submission payload.', 'ok')
    } catch (err) {
      toast(err.message || 'K-Smart generation failed', 'danger')
    }
  }

  const updateSimParam = async (param, value) => {
    if (!simFacts) return
    const updated = { ...simFacts, [param]: parseFloat(value) }
    setSimFacts(updated)
    setSimulating(true)
    try {
      const evalRes = await evaluatePlanFactsV2(updated)
      setSimEvaluation(evalRes)
    } catch (err) {
      console.error('Simulation error:', err)
    } finally {
      setSimulating(false)
    }
  }

  const resetSimulation = () => {
    if (!auditResult) return
    setSimFacts(auditResult.plan_facts)
    setSimEvaluation({
      is_compliant: auditResult.is_compliant,
      violations: auditResult.violations,
      coverage_percent:
        (auditResult.plan_facts.ground_coverage_sqm /
          auditResult.plan_facts.plot_area_sqm) *
        100,
      max_coverage_percent: 65.0,
      fsi_actual:
        auditResult.plan_facts.built_up_area_sqm /
        auditResult.plan_facts.plot_area_sqm,
      max_fsi_permitted: 2.75,
    })
    toast('Reset simulation parameters to blueprint defaults.', 'ok')
  }

  const handleDownloadKSmartJson = () => {
    if (!ksmartModal) return
    const jsonBlob = new Blob([JSON.stringify(ksmartModal, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(jsonBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = `k-smart-export-${file?.name?.replace(/\.pdf$/i, '') || 'plan'}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast('K-Smart JSON downloaded.', 'ok')
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a] text-[#f5f5f5]">
      <Header
        eyebrow="ARCHITECTURAL PDF AUDIT ENGINE"
        title="PDF Visual Workbench"
        subtitle="Deep Area Statement Intelligence, Deterministic Symbolic Verification & Official LSGD Audit Export"
      />

      <div className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full space-y-6">
        {/* Upload Zone Card */}
        <Card>
          <CardContent>
            <div className="flex flex-col md:flex-row items-center gap-6">
              {/* Accessible Drop Area */}
              <div
                role="button"
                tabIndex={0}
                aria-label="Upload Architectural Drawing PDF"
                onDragOver={(e) => {
                  e.preventDefault()
                  setDrag(true)
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={handleFileDrop}
                onClick={() => fileRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    fileRef.current?.click()
                  }
                }}
                className={`flex-1 w-full border-2 border-dashed p-6 flex flex-col items-center justify-center cursor-pointer transition-all focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none relative overflow-hidden ${
                  drag
                    ? 'border-white bg-[#181818]'
                    : 'border-[#333333] hover:border-white bg-[#0e0e0e]'
                }`}
              >
                <div className="blueprint-grid absolute inset-0 opacity-20 pointer-events-none" />
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={handleFileSelect}
                />
                <div className="w-10 h-10 border border-[#404040] bg-[#121212] flex items-center justify-center mb-3">
                  <Icon name="file-text" className="text-xl text-white" />
                </div>
                {file ? (
                  <div className="text-center relative z-10">
                    <div className="font-semibold text-white text-sm mono">
                      {file.name}
                    </div>
                    <div className="text-xs text-[#a3a3a3] mono mt-1">
                      {(file.size / 1024).toFixed(1)} KB — READY TO AUDIT
                    </div>
                  </div>
                ) : (
                  <div className="text-center relative z-10">
                    <div className="text-xs font-bold mono text-white uppercase tracking-wider">
                      DROP ARCHITECTURAL DRAWING PDF HERE
                    </div>
                    <div className="text-[11px] mono text-[#737373] mt-1">
                      Supports A4/A3/A1/A0 sheets with certified Area Statement schedules
                    </div>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-2.5 w-full md:w-64">
                <Button
                  variant="primary"
                  size="md"
                  fullWidth
                  loading={loading}
                  disabled={!file}
                  onClick={runAudit}
                  icon="check-circle"
                >
                  {loading ? 'Analyzing PDF...' : 'RUN DEEP AUDIT'}
                </Button>

                {file && (
                  <Button
                    variant="outline"
                    size="sm"
                    fullWidth
                    onClick={() => {
                      setFile(null)
                      setAuditResult(null)
                      setSimFacts(null)
                      setSimEvaluation(null)
                    }}
                    icon="x"
                  >
                    CLEAR SELECTION
                  </Button>
                )}
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="mt-4 p-3 bg-[#1e0a0a] border border-[#772222] text-[#fca5a5] text-xs mono flex items-center gap-2"
              >
                <Icon name="alert-triangle" className="text-base" />
                <span>{error}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Empty State before audit */}
        {!auditResult && !loading && (
          <EmptyState
            icon="drafting-compass"
            eyebrow="READY FOR ANALYSIS"
            title="Awaiting Architectural Blueprint"
            description="Upload an architectural drawing PDF with an Area Statement schedule to execute statutory zoning analysis, setback checks, and K-Smart LSGD compliance export."
            actionLabel="SELECT SAMPLE PDF DRAWING"
            actionIcon="file"
            onAction={() => {
              // Create demo PDF file object
              const demoBlob = new Blob(['%PDF-1.4 Mock Architectural Drawing'], {
                type: 'application/pdf',
              })
              const sampleFile = new File([demoBlob], 'Kakkanad_Residential_Plan_v2.pdf', {
                type: 'application/pdf',
              })
              setFile(sampleFile)
              setError(null)
              toast('Sample blueprint loaded. Click "Run Deep Audit" to verify.', 'ok')
            }}
          />
        )}

        {/* Audit Results Presentation */}
        {auditResult && (
          <div className="space-y-6">
            {/* Top Status Banner */}
            <div
              className={`p-5 border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 ${
                auditResult.is_compliant
                  ? 'bg-[#121212] border-white text-white'
                  : 'bg-[#141010] border-[#552222] text-[#f5f5f5]'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-9 h-9 border flex items-center justify-center shrink-0 ${
                    auditResult.is_compliant
                      ? 'border-white bg-white text-black'
                      : 'border-[#ff4444] bg-[#2a0e0e] text-[#ff6666]'
                  }`}
                >
                  <Icon
                    name={auditResult.is_compliant ? 'check' : 'alert-circle'}
                    className="text-lg"
                  />
                </div>
                <div>
                  <h2 className="text-sm md:text-base font-bold mono tracking-tight uppercase">
                    {auditResult.is_compliant
                      ? 'COMPLIANT WITH STATUTORY CODES (KBR 2019)'
                      : 'NON-COMPLIANT: STATUTORY DEFICITS IDENTIFIED'}
                  </h2>
                  <p className="text-xs text-[#a3a3a3] mt-0.5">
                    {auditResult.executive_summary}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 w-full md:w-auto">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleDownloadPdf}
                  icon="download"
                >
                  DOWNLOAD AUDIT PDF
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleExportKSmart}
                  icon="share-2"
                >
                  K-SMART EXPORT
                </Button>
              </div>
            </div>

            {/* Split Workspace */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Facts & Concessions */}
              <div className="lg:col-span-5 space-y-6">
                {/* Extracted Parameters Card */}
                <Card>
                  <CardHeader>
                    <CardTitle>
                      <Icon name="layers" />
                      <span>Certified Area Schedule Data</span>
                    </CardTitle>
                    <span className="text-[9px] mono text-[#737373]">
                      AUTO-EXTRACTED
                    </span>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="p-3 bg-[#181818] border border-[#262626]">
                        <div className="text-[#737373] text-[9px] uppercase mono">
                          Plot Extent
                        </div>
                        <div className="font-semibold text-white mt-1 mono">
                          {auditResult.plan_facts.plot_area_sqm} m²
                          <span className="text-[#a3a3a3] font-normal ml-1">
                            (
                            {(
                              auditResult.plan_facts.plot_area_sqm / 40.47
                            ).toFixed(2)}{' '}
                            cents)
                          </span>
                        </div>
                      </div>

                      <div className="p-3 bg-[#181818] border border-[#262626]">
                        <div className="text-[#737373] text-[9px] uppercase mono">
                          Built-up Area
                        </div>
                        <div className="font-semibold text-white mt-1 mono">
                          {auditResult.plan_facts.built_up_area_sqm} m²
                        </div>
                      </div>

                      <div className="p-3 bg-[#181818] border border-[#262626]">
                        <div className="text-[#737373] text-[9px] uppercase mono">
                          Ground Coverage
                        </div>
                        <div className="font-semibold text-white mt-1 mono">
                          {auditResult.plan_facts.ground_coverage_sqm} m²
                          <span className="text-[#a3a3a3] font-normal ml-1">
                            (
                            {(
                              (auditResult.plan_facts.ground_coverage_sqm /
                                auditResult.plan_facts.plot_area_sqm) *
                              100
                            ).toFixed(1)}
                            %)
                          </span>
                        </div>
                      </div>

                      <div className="p-3 bg-[#181818] border border-[#262626]">
                        <div className="text-[#737373] text-[9px] uppercase mono">
                          FAR / FSI Actual
                        </div>
                        <div className="font-semibold text-white mt-1 mono">
                          {(
                            auditResult.plan_facts.built_up_area_sqm /
                            auditResult.plan_facts.plot_area_sqm
                          ).toFixed(2)}
                        </div>
                      </div>

                      <div className="p-3 bg-[#181818] border border-[#262626]">
                        <div className="text-[#737373] text-[9px] uppercase mono">
                          Height & Floors
                        </div>
                        <div className="font-semibold text-white mt-1 mono">
                          {auditResult.plan_facts.building_height_m}m (
                          {auditResult.plan_facts.number_of_floors} Floors)
                        </div>
                      </div>

                      <div className="p-3 bg-[#181818] border border-[#262626]">
                        <div className="text-[#737373] text-[9px] uppercase mono">
                          Access Road Width
                        </div>
                        <div className="font-semibold text-white mt-1 mono">
                          {auditResult.plan_facts.road_width_m} m
                        </div>
                      </div>
                    </div>

                    <div className="pt-3 border-t border-[#262626]">
                      <div className="text-[#737373] text-[9px] uppercase mono mb-2 font-semibold">
                        Setback Clearances
                      </div>
                      <div className="grid grid-cols-4 gap-2 text-center text-xs">
                        <div className="p-2 bg-[#181818] border border-[#262626]">
                          <div className="text-[9px] mono text-[#737373]">
                            FRONT
                          </div>
                          <div className="font-bold text-white mt-0.5 mono">
                            {auditResult.plan_facts.front_setback_m}m
                          </div>
                        </div>
                        <div className="p-2 bg-[#181818] border border-[#262626]">
                          <div className="text-[9px] mono text-[#737373]">
                            REAR
                          </div>
                          <div className="font-bold text-white mt-0.5 mono">
                            {auditResult.plan_facts.rear_setback_m}m
                          </div>
                        </div>
                        <div className="p-2 bg-[#181818] border border-[#262626]">
                          <div className="text-[9px] mono text-[#737373]">
                            SIDE 1
                          </div>
                          <div className="font-bold text-white mt-0.5 mono">
                            {auditResult.plan_facts.side_setback_1_m}m
                          </div>
                        </div>
                        <div className="p-2 bg-[#181818] border border-[#262626]">
                          <div className="text-[9px] mono text-[#737373]">
                            SIDE 2
                          </div>
                          <div className="font-bold text-white mt-0.5 mono">
                            {auditResult.plan_facts.side_setback_2_m}m
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Concessions Card */}
                <Card>
                  <CardHeader>
                    <CardTitle>
                      <Icon name="shield-check" />
                      <span>Statutory Concessions & Exceptions</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {auditResult.applied_concessions &&
                    auditResult.applied_concessions.length > 0 ? (
                      <div className="space-y-2">
                        {auditResult.applied_concessions.map((c, i) => (
                          <div
                            key={i}
                            className="text-xs p-2.5 bg-[#181818] border border-[#333333] text-[#f5f5f5] flex items-center gap-2 mono"
                          >
                            <Icon name="check" className="text-white shrink-0" />
                            <span>{c}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-[#737373] italic mono">
                        Standard provisions applied; no statutory concessions claimed for this plot size.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Right Column: Scorecard & Remediation */}
              <div className="lg:col-span-7 space-y-6">
                {/* Parameter Scorecard Table */}
                <Card>
                  <CardHeader>
                    <CardTitle>
                      <Icon name="check-square" />
                      <span>Statutory Parameter Comparison</span>
                    </CardTitle>
                    <span className="text-[9px] font-mono text-[#737373]">
                      KMBR/KPBR 2019
                    </span>
                  </CardHeader>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-[#181818] text-[#737373] font-mono text-[9px] uppercase border-b border-[#262626]">
                        <tr>
                          <th className="py-2.5 px-4">Parameter</th>
                          <th className="py-2.5 px-3">Plan</th>
                          <th className="py-2.5 px-3">Requirement</th>
                          <th className="py-2.5 px-3">Deficit</th>
                          <th className="py-2.5 px-4 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#262626]">
                        {auditResult.violations.map((v, i) => (
                          <tr key={i} className="hover:bg-[#181818] transition-colors">
                            <td className="py-2.5 px-4 font-semibold text-white">
                              {v.parameter}
                            </td>
                            <td className="py-2.5 px-3 text-[#a3a3a3] mono">
                              {v.actual_value} {v.unit}
                            </td>
                            <td className="py-2.5 px-3 text-[#a3a3a3] mono">
                              {v.required_value} {v.unit}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[#fca5a5]">
                              -{v.deficit} {v.unit}
                            </td>
                            <td className="py-2.5 px-4 text-right">
                              <span className="status-pill pill-danger">
                                FAIL
                              </span>
                            </td>
                          </tr>
                        ))}
                        {auditResult.violations.length === 0 && (
                          <tr>
                            <td
                              colSpan="5"
                              className="py-6 text-center text-[#a3a3a3] mono text-xs"
                            >
                              ✓ All measurable parameters satisfy regulatory thresholds.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </Card>

                {/* Remediation Measures Card */}
                {auditResult.remediations && auditResult.remediations.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>
                        <Icon name="tool" />
                        <span>Actionable Architectural Redesign Remedies</span>
                      </CardTitle>
                      <span className="text-[9px] mono text-[#737373]">
                        SOLUTIONS
                      </span>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {auditResult.remediations.map((r, i) => (
                        <div
                          key={i}
                          className="p-3 bg-[#181818] border border-[#262626] space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-xs font-semibold text-white mono">
                            <span>{r.parameter}</span>
                            <span className="text-[9px] mono text-[#fca5a5]">
                              {r.deficit_summary}
                            </span>
                          </div>
                          <p className="text-xs text-[#a3a3a3] leading-relaxed">
                            {r.action}
                          </p>
                          <div className="text-[10px] mono text-white pt-1 flex items-center gap-1.5">
                            <Icon name="target" className="text-xs" />
                            <span>Target: {r.target_value}</span>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Interactive Parameter Simulator (What-If) */}
                {simFacts && (
                  <Card>
                    <CardHeader>
                      <CardTitle>
                        <Icon name="sliders" />
                        <span>Interactive Parameter Simulator (What-If)</span>
                      </CardTitle>
                      <div className="flex items-center gap-2">
                        {simEvaluation && (
                          <span
                            className={`status-pill ${
                              simEvaluation.is_compliant ? 'pill-ok' : 'pill-danger'
                            }`}
                          >
                            {simEvaluation.is_compliant
                              ? 'SIMULATION: PASS'
                              : 'SIMULATION: DEFICIT'}
                          </span>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={resetSimulation}
                          icon="refresh-cw"
                          aria-label="Reset simulation parameters"
                        >
                          RESET
                        </Button>
                      </div>
                    </CardHeader>

                    <CardContent className="space-y-5">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <Slider
                          label="Front Setback"
                          value={simFacts.front_setback_m}
                          min={1.0}
                          max={6.0}
                          step={0.1}
                          unit="m"
                          baseline="Req: 3.0m"
                          onChange={(v) => updateSimParam('front_setback_m', v)}
                        />

                        <Slider
                          label="Rear Setback"
                          value={simFacts.rear_setback_m}
                          min={0.8}
                          max={5.0}
                          step={0.1}
                          unit="m"
                          baseline="Req: 1.5m"
                          onChange={(v) => updateSimParam('rear_setback_m', v)}
                        />

                        <Slider
                          label="Side Setback 1"
                          value={simFacts.side_setback_1_m}
                          min={0.5}
                          max={4.0}
                          step={0.1}
                          unit="m"
                          baseline="Req: 1.0m"
                          onChange={(v) => updateSimParam('side_setback_1_m', v)}
                        />

                        <Slider
                          label="Side Setback 2"
                          value={simFacts.side_setback_2_m}
                          min={0.5}
                          max={4.0}
                          step={0.1}
                          unit="m"
                          baseline="Req: 1.0m"
                          onChange={(v) => updateSimParam('side_setback_2_m', v)}
                        />

                        <Slider
                          label="Building Height"
                          value={simFacts.building_height_m}
                          min={3.0}
                          max={20.0}
                          step={0.5}
                          unit="m"
                          baseline="Max: 16.0m"
                          onChange={(v) => updateSimParam('building_height_m', v)}
                        />

                        <Slider
                          label="Plot Area"
                          value={simFacts.plot_area_sqm}
                          min={50}
                          max={1500}
                          step={10}
                          unit="m²"
                          baseline="Max Cov: 65%"
                          onChange={(v) => updateSimParam('plot_area_sqm', v)}
                        />
                      </div>

                      {/* Live Computed Metrics Strip */}
                      <div className="pt-3 border-t border-[#262626] grid grid-cols-3 gap-3 text-center">
                        <div className="p-2.5 bg-[#181818] border border-[#262626]">
                          <div className="text-[9px] mono text-[#737373] uppercase">
                            SIMULATED COVERAGE
                          </div>
                          <div className="text-xs font-bold mono text-white mt-0.5">
                            {(
                              (simFacts.ground_coverage_sqm /
                                simFacts.plot_area_sqm) *
                              100
                            ).toFixed(1)}
                            %
                          </div>
                        </div>

                        <div className="p-2.5 bg-[#181818] border border-[#262626]">
                          <div className="text-[9px] mono text-[#737373] uppercase">
                            SIMULATED FAR / FSI
                          </div>
                          <div className="text-xs font-bold mono text-white mt-0.5">
                            {(
                              simFacts.built_up_area_sqm /
                              simFacts.plot_area_sqm
                            ).toFixed(2)}
                          </div>
                        </div>

                        <div className="p-2.5 bg-[#181818] border border-[#262626]">
                          <div className="text-[9px] mono text-[#737373] uppercase">
                            TOTAL VIOLATIONS
                          </div>
                          <div
                            className={`text-xs font-bold mono mt-0.5 ${
                              simEvaluation?.violations?.length > 0
                                ? 'text-[#fca5a5]'
                                : 'text-white'
                            }`}
                          >
                            {simEvaluation?.violations?.length || 0} ITEMS
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Accessible K-Smart Export Modal */}
        <Modal
          isOpen={Boolean(ksmartModal)}
          onClose={() => setKsmartModal(null)}
          title="KERALA LSGD K-SMART EXPORT PAYLOAD"
          subtitle="Statutory electronic submission schema formatted for Sanketham LSGD integration"
          footer={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadKSmartJson}
                icon="download"
              >
                DOWNLOAD JSON
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(
                    JSON.stringify(ksmartModal, null, 2)
                  )
                  toast('Copied K-Smart JSON schema to clipboard.', 'ok')
                }}
                icon="copy"
              >
                COPY JSON
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setKsmartModal(null)}
              >
                CLOSE
              </Button>
            </>
          }
        >
          <div className="space-y-3">
            <div className="text-[10px] mono text-[#737373] uppercase tracking-wider">
              VERIFIED JSON OUTPUT SCHEMA (LSGD 2026.04)
            </div>
            <div className="bg-[#0a0a0a] p-4 border border-[#262626] font-mono text-[11px] text-[#e5e5e5] max-h-96 overflow-auto">
              <pre>{JSON.stringify(ksmartModal, null, 2)}</pre>
            </div>
          </div>
        </Modal>
      </div>

      <AppFooter />
    </div>
  )
}
