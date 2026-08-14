import React, { useState, useEffect } from 'react'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { kbrDocs, kbrStats } from '../data.js'

const STEPS = ['Loading PDF', 'Chunking', 'Embedding', 'Indexing', 'Complete']

export default function Knowledge() {
  const [ingesting, setIngesting] = useState(false)
  const [step, setStep] = useState(0)
  const [pct, setPct] = useState(0)

  useEffect(() => {
    if (!ingesting) return
    const iv = setInterval(() => setPct((p) => Math.min(100, p + 2)), 90)
    return () => clearInterval(iv)
  }, [ingesting])

  useEffect(() => {
    if (pct >= 100 && ingesting) {
      setStep(4)
      const t = setTimeout(() => { setIngesting(false); setPct(0); setStep(0) }, 1800)
      return () => clearTimeout(t)
    }
    setStep(pct < 15 ? 0 : pct < 45 ? 1 : pct < 80 ? 2 : 3)
  }, [pct, ingesting])

  return (
    <>
      <Header
        eyebrow="Kerala Building Rules"
        title="KBR Knowledge Base"
        subtitle="Indexed rule corpus powering retrieval-grounded compliance analysis"
        action={
          <button onClick={() => { setIngesting(true); setPct(0) }} className="accent-gradient px-4 py-2 rounded text-sm font-semibold text-black flex items-center gap-2 hover:brightness-110">
            <Icon name="upload-cloud" /> Ingest Rules
          </button>
        }
      />
      <div className="p-6 md:p-8 space-y-8">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-px border border-[#222C3A] bg-[#10151C] rounded overflow-hidden divide-x divide-[#222C3A]">
          {kbrStats.map((s) => (
            <div key={s.label} className="bg-[#10151C] p-5 hover:bg-[#161D27] transition-colors">
              <div className="text-[10px] mono text-[#5B6879] uppercase tracking-wider mb-2">{s.label}</div>
              <div className="text-base mono text-white tracking-tight flex items-center gap-2">
                {s.ok && <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] shadow-[0_0_6px_#34D399]" />}
                {s.value}
              </div>
            </div>
          ))}
        </div>

        <div className="bg-[#10151C] border border-[#222C3A] rounded shadow-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#222C3A] bg-[#161D27]/50">
            <h3 className="text-sm font-semibold text-white tracking-wide uppercase flex items-center gap-2"><Icon name="files" className="text-[#22D3EE]" /> Ingested Documents</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead>
                <tr className="border-b border-[#222C3A] bg-[#0C1117]">
                  {['Document', 'Type', 'Pages', 'Chunks', 'Indexed', 'Status'].map((h) => (
                    <th key={h} className="px-6 py-3 text-left text-[11px] mono text-[#5B6879] uppercase tracking-wider font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#222C3A]">
                {kbrDocs.map((d) => (
                  <tr key={d.doc} className="hover:bg-[#161D27] transition-colors">
                    <td className="px-6 py-4 text-sm text-white">{d.doc}</td>
                    <td className="px-6 py-4"><span className="text-[10px] mono px-2 py-0.5 rounded border border-[#222C3A] bg-[#161D27] text-[#9AA7B6]">{d.type}</span></td>
                    <td className="px-6 py-4 text-sm mono text-[#9AA7B6]">{d.pages}</td>
                    <td className="px-6 py-4 text-sm mono text-[#9AA7B6]">{d.chunks}</td>
                    <td className="px-6 py-4 text-xs mono text-[#5B6879]">{d.indexed}</td>
                    <td className="px-6 py-4"><Pill kind="pill-ok">{d.status}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {(ingesting || pct > 0) && (
          <div className="bg-[#10151C] border border-[#222C3A] rounded p-6 fade-rise">
            <div className="text-[11px] mono text-[#5B6879] uppercase tracking-widest mb-4">Ingestion Progress</div>
            <div className="flex items-center gap-0 mb-4">
              {STEPS.map((s, i) => (
                <React.Fragment key={s}>
                  {i > 0 && <div className={`flex-1 h-px ${i <= step ? 'bg-[#22D3EE]' : 'bg-[#222C3A]'}`} />}
                  <div className="flex flex-col items-center px-1">
                    <div className={`w-9 h-9 rounded-full flex items-center justify-center border-2 ${
                      i < step ? 'border-[#22D3EE] text-[#22D3EE]' : i === step ? 'border-[#22D3EE] text-[#22D3EE] pulse-accent' : 'border-[#222C3A] text-[#5B6879]'
                    }`}>
                      {i < step || (i === step && step === 4) ? <Icon name="check-circle" className="text-base" /> : i === step ? <Icon name="loader" className="text-base spin-1" /> : <Icon name="loader" className="text-base opacity-30" />}
                    </div>
                    <div className={`text-[9px] mono uppercase tracking-wider mt-2 whitespace-nowrap ${i <= step ? 'text-[#22D3EE]' : 'text-[#5B6879]'}`}>{s}</div>
                  </div>
                </React.Fragment>
              ))}
            </div>
            <div className="flex items-center justify-between gap-4">
              <div className="text-xs mono text-[#9AA7B6]">
                {step === 4 ? 'Ingestion complete.' : `Embedding chunk ${Math.min(2481, Math.round((pct / 100) * 2481)).toLocaleString()} / 2,481…`}
                <span className="text-[#5B6879]"> &nbsp;model: text-embedding-3-small</span>
              </div>
              <div className="text-xs mono text-[#22D3EE]">{pct}%</div>
            </div>
            <div className="mt-3 h-1.5 bg-[#1C2531] rounded-full overflow-hidden">
              <div className="h-full accent-gradient transition-all duration-150" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}

        <div className="flex items-start gap-2 text-[11px] mono text-[#5B6879]">
          <Icon name="info" className="text-[#22D3EE]/60 flex-shrink-0 mt-0.5" />
          Retrieval quality depends on corpus coverage — re-ingest after KBR amendments.
        </div>
      </div>
      <AppFooter extra="LATENCY: 420ms" />
    </>
  )
}
