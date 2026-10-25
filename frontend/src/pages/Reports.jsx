import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from '../components/Toast.jsx'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import {
  Card,
  CardHeader,
  CardTitle,
  SkeletonTable,
  EmptyState,
  Button,
} from '../components/ui/index.js'
import { fetchReports, downloadReport, STATUS_META } from '../data.js'

export default function Reports() {
  const navigate = useNavigate()
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

  const handleExportLatest = async () => {
    if (reportList.length > 0) {
      const target = reportList[0]
      try {
        toast(`Exporting latest report “${target.project}”…`, 'ok')
        await downloadReport(target.id, 'pdf')
        toast('PDF report downloaded successfully.', 'ok')
      } catch (e) {
        toast(`Export failed: ${e.message}`, 'danger')
      }
    } else {
      toast('No reports available to export.', 'warn')
    }
  }

  return (
    <>
      <Header
        eyebrow="AUDIT ARCHIVE"
        title="Compliance Reports"
        subtitle="Historical architectural compliance assessments generated under KBR 2019 provisions"
        action={
          <Button
            variant="primary"
            size="md"
            icon="download"
            onClick={handleExportLatest}
          >
            EXPORT LATEST PDF
          </Button>
        }
      />

      <div className="p-6 md:p-8 space-y-6 bg-[#0a0a0a]">
        <Card>
          <CardHeader>
            <CardTitle>
              <Icon name="archive" />
              <span>Assessment Archive & Review Records</span>
            </CardTitle>
            <span className="text-[10px] mono text-[#737373]">
              {reportList.length} REPORTS
            </span>
          </CardHeader>

          {loading ? (
            <SkeletonTable rows={5} cols={6} />
          ) : reportList.length === 0 ? (
            <EmptyState
              icon="file-text"
              eyebrow="ARCHIVE EMPTY"
              title="No Historical Reports"
              description="No architectural compliance assessment reports have been archived yet. Upload and audit a building plan to generate records."
              actionLabel="START NEW COMPLIANCE CHECK"
              actionIcon="plus"
              onAction={() => navigate('/new-check')}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left border-collapse" role="table">
                <thead>
                  <tr className="border-b border-[#262626] bg-[#0e0e0e]">
                    {[
                      'Project Ref',
                      'Timestamp',
                      'Overall Result',
                      'Violations',
                      'Engineer Review',
                      'Download',
                    ].map((h, i) => (
                      <th
                        key={h}
                        scope="col"
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
                  {reportList.map((r, idx) => {
                    const s = STATUS_META[r.status] || STATUS_META.review
                    return (
                      <tr
                        key={r.id || r.project || idx}
                        className="hover:bg-[#181818] transition-colors group"
                      >
                        <td className="px-4 py-3.5">
                          <div className="text-xs font-semibold text-white">
                            {r.project}
                          </div>
                          <div className="text-[9px] mono text-[#737373]">
                            AUDIT #{r.id || idx + 1}
                          </div>
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-[#a3a3a3]">
                          {r.date}
                        </td>
                        <td className="px-4 py-3.5">
                          <Pill kind={s.pill}>{s.label}</Pill>
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-white">
                          {r.violations === null ? (
                            '—'
                          ) : r.violations > 0 ? (
                            <span className="text-[#fca5a5] font-semibold">
                              {r.violations} FLAGGED
                            </span>
                          ) : (
                            <span className="text-[#a3a3a3]">0 FLAGGED</span>
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-xs mono text-[#a3a3a3]">
                          {r.reviewer}
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <button
                            onClick={async () => {
                              try {
                                toast(`Exporting “${r.project}” as PDF…`, 'ok')
                                await downloadReport(r.id, 'pdf')
                                toast('Downloaded PDF successfully.', 'ok')
                              } catch (e) {
                                toast(`Export failed: ${e.message}`, 'danger')
                              }
                            }}
                            aria-label={`Download PDF report for ${r.project}`}
                            className="text-[10px] mono font-bold text-white hover:underline border border-[#333333] hover:border-white px-2.5 py-1 bg-[#0e0e0e] inline-flex items-center gap-1 cursor-pointer focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none transition-colors"
                          >
                            <Icon name="file-down" />
                            <span>PDF ↓</span>
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="flex items-start gap-2.5 text-[10px] mono text-[#737373]">
          <span className="text-white font-bold">[NOTE]</span>
          <span>
            Reports are formal advisory outputs; final building permits are granted by the municipal corporation / village panchayat secretary.
          </span>
        </div>
      </div>

      <AppFooter />
    </>
  )
}
