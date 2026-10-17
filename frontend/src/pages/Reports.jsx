import React, { useState, useEffect } from 'react'
import { toast } from '../components/Toast.jsx'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { fetchReports, downloadReport, STATUS_META } from '../data.js'

export default function Reports() {
  const [reportList, setReportList] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetchReports().then((data) => {
      if (active) {
        setReportList(data)
        setLoading(false)
      }
    })
    return () => {
      active = false
    }
  }, [])

  return (
    <>
      <Header
        eyebrow="ARCHIVE // OFFICIAL STATUTORY AUDITS"
        title="Compliance Reports"
        subtitle="Historical architectural compliance assessments generated under KBR 2019 provisions"
        action={
          <button
            onClick={async () => {
              if (reportList.length > 0) {
                const target = reportList[0]
                try {
                  toast(`Exporting latest report “${target.project}”…`, 'ok')
                  await downloadReport(target.id, 'pdf')
                } catch (e) {
                  toast(`Export failed: ${e.message}`, 'danger')
                }
              } else {
                toast('No reports available to export.', 'warn')
              }
            }}
            className="bg-white text-black font-mono text-xs font-bold px-4 py-2 border border-white hover:bg-[#e5e5e5] flex items-center gap-2 cursor-pointer transition-colors"
          >
            <Icon name="download" /> EXPORT LATEST PDF
          </button>
        }
      />

      <div className="p-6 md:p-8 space-y-6 bg-[#0a0a0a]">
        <div className="bg-[#121212] border border-[#262626] overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[#262626] bg-[#181818] flex items-center justify-between">
            <h3 className="text-xs font-bold text-white tracking-widest uppercase flex items-center gap-2 mono">
              <span className="w-1.5 h-1.5 bg-white inline-block" /> Assessment Archive & Review Records
            </h3>
            <span className="text-[10px] mono text-[#737373]">FORMAT // FORMAL AUDIT CERTIFICATE</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left border-collapse">
              <thead>
                <tr className="border-b border-[#262626] bg-[#0e0e0e]">
                  {['Project Ref', 'Timestamp', 'Overall Result', 'Violations', 'Engineer Review', 'Download'].map((h, i) => (
                    <th
                      key={h}
                      className={`px-4 py-3 text-[10px] mono text-[#737373] uppercase tracking-wider font-semibold ${
                        i === 5 ? 'text-right' : 'text-left'
                      }`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626]">
                {loading && reportList.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-xs mono text-[#737373]">
                      LOADING REPORTS FROM DATABASE…
                    </td>
                  </tr>
                ) : (
                  reportList.map((r, idx) => {
                    const s = STATUS_META[r.status] || STATUS_META.review
                    return (
                      <tr key={r.id || r.project || idx} className="hover:bg-[#181818] transition-colors group">
                        <td className="px-4 py-3.5">
                          <div className="text-xs font-semibold text-white">{r.project}</div>
                          <div className="text-[9px] mono text-[#737373]">AUDIT #{r.id || idx + 1}</div>
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-[#a3a3a3]">{r.date}</td>
                        <td className="px-4 py-3.5">
                          <Pill kind={s.pill}>{s.label}</Pill>
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-white">
                          {r.violations === null ? '—' : `${r.violations} FLAGGED`}
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-[#a3a3a3]">{r.reviewer}</td>
                        <td className="px-4 py-3.5 text-right">
                          <button
                            onClick={async () => {
                              try {
                                toast(`Exporting “${r.project}” as PDF…`, 'ok')
                                await downloadReport(r.id, 'pdf')
                              } catch (e) {
                                toast(`Export failed: ${e.message}`, 'danger')
                              }
                            }}
                            className="text-[10px] mono font-bold text-white hover:underline border border-[#333333] hover:border-white px-2.5 py-1 bg-[#0e0e0e] inline-flex items-center gap-1 cursor-pointer"
                          >
                            <Icon name="file-down" /> PDF ↓
                          </button>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex items-start gap-2.5 text-[10px] mono text-[#737373]">
          <span className="text-white font-bold">[NOTE]</span>
          <span>Reports are formal advisory outputs; final building permits are granted by the municipal corporation / village panchayat secretary.</span>
        </div>
      </div>

      <AppFooter extra="PDF GENERATION ENGINE ACTIVE" />
    </>
  )
}
