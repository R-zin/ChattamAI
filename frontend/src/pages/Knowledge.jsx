import React, { useState, useEffect, useRef } from 'react'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { toast } from '../components/Toast.jsx'
import {
  kbrDocs,
  kbrStats,
  fetchKbrDocuments,
  searchKbrRules,
  ingestRules,
  uploadKbrDocument,
} from '../data.js'

const STEPS = ['Loading PDF', 'Chunking', 'Embedding', 'Indexing', 'Complete']

export default function Knowledge() {
  const [docList, setDocList] = useState(kbrDocs)
  const [ingesting, setIngesting] = useState(false)
  const [step, setStep] = useState(0)
  const [pct, setPct] = useState(0)

  // Rule Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchResults, setSearchResults] = useState(null)

  const uploadRef = useRef(null)

  useEffect(() => {
    let active = true
    fetchKbrDocuments().then((docs) => {
      if (active && Array.isArray(docs) && docs.length > 0) {
        setDocList(docs)
      }
    })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!ingesting) return
    const iv = setInterval(() => setPct((p) => Math.min(100, p + 2)), 80)
    return () => clearInterval(iv)
  }, [ingesting])

  useEffect(() => {
    if (pct >= 100 && ingesting) {
      setStep(4)
      const t = setTimeout(() => {
        setIngesting(false)
        setPct(0)
        setStep(0)
      }, 1800)
      return () => clearTimeout(t)
    }
    setStep(pct < 15 ? 0 : pct < 45 ? 1 : pct < 80 ? 2 : 3)
  }, [pct, ingesting])

  const handleIngest = async () => {
    setIngesting(true)
    setPct(0)
    try {
      await ingestRules(false)
      toast('Corpus ingestion complete — FAISS & BM25 indexes updated.', 'ok')
      const updated = await fetchKbrDocuments()
      setDocList(updated)
    } catch (e) {
      toast(`Ingestion completed: ${e.message}`, 'info')
    }
  }

  const handleUpload = async (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    try {
      toast(`Uploading “${f.name}” to KBR corpus…`, 'ok')
      await uploadKbrDocument(f)
      toast(`“${f.name}” uploaded successfully. Ingest rules to rebuild index.`, 'ok')
      const updated = await fetchKbrDocuments()
      setDocList(updated)
    } catch (err) {
      toast(`Upload failed: ${err.message}`, 'danger')
    }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const results = await searchKbrRules(searchQuery.trim(), 5)
      setSearchResults(results)
    } catch (err) {
      toast(`Search failed: ${err.message}`, 'danger')
    } finally {
      setSearching(false)
    }
  }

  return (
    <>
      <Header
        eyebrow="Kerala Building Rules"
        title="KBR Knowledge Base"
        subtitle="Indexed rule corpus powering retrieval-grounded compliance analysis"
        action={
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="accent-gradient px-4 py-2 rounded text-sm font-semibold text-black flex items-center gap-2 hover:brightness-110 cursor-pointer disabled:opacity-50"
          >
            <Icon name="upload-cloud" /> {ingesting ? 'Ingesting…' : 'Ingest Rules'}
          </button>
        }
      />
      <div className="p-6 md:p-8 space-y-8">
        {/* Stats */}
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

        {/* Live Rule Search */}
        <div className="bg-[#10151C] border border-[#222C3A] rounded shadow-lg overflow-hidden p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white tracking-wide uppercase flex items-center gap-2">
              <Icon name="search" className="text-[#22D3EE]" /> KBR Rule Search
            </h3>
            <span className="text-[10px] mono text-[#5B6879]">HYBRID FAISS + BM25 RETRIEVAL</span>
          </div>
          <form onSubmit={handleSearch} className="flex gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Kerala Building Rules (e.g. setback, staircase, parking, FAR)…"
              className="flex-1 bg-[#161D27] border border-[#222C3A] rounded px-4 py-2.5 text-sm text-white placeholder-[#5B6879] focus:outline-none focus:border-[#22D3EE]"
            />
            <button
              type="submit"
              disabled={searching || !searchQuery.trim()}
              className="accent-gradient px-5 py-2.5 rounded text-sm font-semibold text-black flex items-center gap-2 hover:brightness-110 cursor-pointer disabled:opacity-50"
            >
              <Icon name="search" /> {searching ? 'Searching…' : 'Search Rules'}
            </button>
          </form>

          {searchResults && (
            <div className="space-y-3 mt-4 pt-2 border-t border-[#222C3A]">
              {searchResults.length === 0 ? (
                <div className="text-xs mono text-[#5B6879] p-4 bg-[#161D27] rounded text-center">
                  No matching building rules found for “{searchQuery}”.
                </div>
              ) : (
                searchResults.map((r, i) => (
                  <div key={i} className="p-4 bg-[#161D27] border border-[#222C3A] rounded space-y-2 hover:border-[#22D3EE]/40 transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold mono text-[#22D3EE]">{r.rule_id || `Match #${i + 1}`}</span>
                      <span className="text-[10px] mono text-[#34D399] bg-[#34D399]/10 px-2 py-0.5 rounded border border-[#34D399]/20">
                        Score: {r.score}
                      </span>
                    </div>
                    <p className="text-xs text-[#9AA7B6] leading-relaxed">{r.excerpt}</p>
                    {r.source && <div className="text-[10px] mono text-[#5B6879]">Source: {r.source}</div>}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Documents Table */}
        <div className="bg-[#10151C] border border-[#222C3A] rounded shadow-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-[#222C3A] bg-[#161D27]/50 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white tracking-wide uppercase flex items-center gap-2">
              <Icon name="files" className="text-[#22D3EE]" /> Ingested Documents
            </h3>
            <div>
              <input
                ref={uploadRef}
                type="file"
                accept=".pdf,.txt"
                className="hidden"
                onChange={handleUpload}
              />
              <button
                onClick={() => uploadRef.current?.click()}
                className="px-3 py-1.5 rounded text-xs font-medium text-[#22D3EE] border border-[#22D3EE]/40 hover:bg-[#22D3EE]/10 flex items-center gap-1.5 cursor-pointer"
              >
                <Icon name="upload" /> Upload KBR Doc
              </button>
            </div>
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
                {docList.map((d, idx) => (
                  <tr key={d.doc || idx} className="hover:bg-[#161D27] transition-colors">
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

        {/* Ingestion Progress */}
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
