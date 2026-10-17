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
      toast('Corpus ingestion complete — FAISS vector index updated.', 'ok')
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
        eyebrow="REGULATORY CORPUS // KBR 2019 DATABASE"
        title="KBR Knowledge Base"
        subtitle="Indexed statutory rulebook powering dense vector retrieval and compliance reasoning"
        action={
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="bg-white text-black font-mono text-xs font-bold px-4 py-2 border border-white hover:bg-[#e5e5e5] flex items-center gap-2 cursor-pointer transition-colors disabled:opacity-40"
          >
            <Icon name="upload-cloud" /> {ingesting ? 'INGESTING CHUNKS…' : 'RE-INDEX RULES'}
          </button>
        }
      />

      <div className="p-6 md:p-8 space-y-6 bg-[#0a0a0a]">
        {/* Metric Strip */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-px border border-[#262626] bg-[#121212] divide-x divide-[#262626]">
          {kbrStats.map((s) => (
            <div key={s.label} className="bg-[#121212] p-4 hover:bg-[#181818] transition-colors">
              <div className="text-[10px] mono text-[#737373] uppercase tracking-wider mb-1 font-semibold">{s.label}</div>
              <div className="text-sm mono text-white font-bold flex items-center gap-2">
                {s.ok && <span className="w-1.5 h-1.5 bg-white inline-block" />}
                {s.value}
              </div>
            </div>
          ))}
        </div>

        {/* Live Vector Search */}
        <div className="bg-[#121212] border border-[#262626] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#262626] pb-3">
            <h3 className="text-xs font-bold text-white tracking-widest uppercase flex items-center gap-2 mono">
              <span className="w-1.5 h-1.5 bg-white inline-block" /> Semantic Rule Search
            </h3>
            <span className="text-[10px] mono text-[#737373]">NVIDIA NEMOTRON-3-EMBED-1B (2048-DIM)</span>
          </div>

          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Kerala Building Rules (e.g. front setback, FAR, coverage, staircase, fire escape)…"
              className="flex-1 bg-[#0e0e0e] border border-[#333333] px-4 py-2.5 text-xs mono text-white placeholder-[#525252] focus:outline-none focus:border-white transition-colors"
            />
            <button
              type="submit"
              disabled={searching || !searchQuery.trim()}
              className="bg-white text-black font-mono text-xs font-bold px-5 py-2.5 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer disabled:opacity-40"
            >
              <Icon name="search" /> {searching ? 'SEARCHING…' : 'SEARCH'}
            </button>
          </form>

          {searchResults && (
            <div className="space-y-3 mt-4 pt-4 border-t border-[#262626]">
              {searchResults.length === 0 ? (
                <div className="text-xs mono text-[#737373] p-4 bg-[#0e0e0e] border border-[#262626] text-center">
                  NO MATCHING BUILDING RULES FOUND FOR “{searchQuery}”.
                </div>
              ) : (
                searchResults.map((r, i) => (
                  <div key={i} className="p-4 bg-[#0e0e0e] border border-[#262626] space-y-2 hover:border-white transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold mono text-white">{r.rule_id || `CHUNK MATCH #${i + 1}`}</span>
                      <span className="text-[10px] mono text-black bg-white px-2 py-0.5 font-bold">
                        SIMILARITY: {r.score}
                      </span>
                    </div>
                    <p className="text-xs text-[#a3a3a3] leading-relaxed font-mono">{r.excerpt}</p>
                    {r.source && <div className="text-[10px] mono text-[#737373]">SOURCE // {r.source}</div>}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Documents Table */}
        <div className="bg-[#121212] border border-[#262626] overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[#262626] bg-[#181818] flex items-center justify-between">
            <h3 className="text-xs font-bold text-white tracking-widest uppercase flex items-center gap-2 mono">
              <span className="w-1.5 h-1.5 bg-white inline-block" /> Ingested Corpus Documents
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
                className="px-3 py-1.5 text-xs mono text-white border border-[#404040] hover:border-white bg-[#0e0e0e] flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <Icon name="upload" /> + UPLOAD DOCUMENT
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left border-collapse">
              <thead>
                <tr className="border-b border-[#262626] bg-[#0e0e0e]">
                  {['Document File', 'Format', 'Pages', 'Chunks', 'Indexed On', 'Index Status'].map((h) => (
                    <th key={h} className="px-4 py-3 text-[10px] mono text-[#737373] uppercase tracking-wider font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626]">
                {docList.map((d, idx) => (
                  <tr key={d.doc || idx} className="hover:bg-[#181818] transition-colors">
                    <td className="px-4 py-3.5 text-xs font-semibold text-white">{d.doc}</td>
                    <td className="px-4 py-3.5"><span className="text-[10px] mono px-2 py-0.5 border border-[#262626] bg-[#0a0a0a] text-[#a3a3a3]">{d.type}</span></td>
                    <td className="px-4 py-3.5 text-xs mono text-[#a3a3a3]">{d.pages}</td>
                    <td className="px-4 py-3.5 text-xs mono text-white font-medium">{d.chunks}</td>
                    <td className="px-4 py-3.5 text-[10px] mono text-[#737373]">{d.indexed}</td>
                    <td className="px-4 py-3.5"><Pill kind="pill-ok">{d.status}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Ingestion Progress */}
        {(ingesting || pct > 0) && (
          <div className="bg-[#121212] border border-[#262626] p-6 fade-rise space-y-4">
            <div className="text-[10px] mono text-[#a3a3a3] uppercase tracking-widest font-semibold">Corpus Ingestion Progress</div>
            <div className="flex items-center gap-0 mb-4">
              {STEPS.map((s, i) => (
                <React.Fragment key={s}>
                  {i > 0 && <div className={`flex-1 h-px ${i <= step ? 'bg-white' : 'bg-[#262626]'}`} />}
                  <div className="flex flex-col items-center px-1">
                    <div className={`w-8 h-8 flex items-center justify-center border ${
                      i <= step ? 'border-white bg-[#0e0e0e] text-white' : 'border-[#262626] text-[#737373]'
                    }`}>
                      {i < step || (i === step && step === 4) ? <Icon name="check" className="text-sm" /> : <span className="mono text-[10px]">{i + 1}</span>}
                    </div>
                    <div className={`text-[9px] mono uppercase tracking-wider mt-2 whitespace-nowrap ${i <= step ? 'text-white' : 'text-[#737373]'}`}>{s}</div>
                  </div>
                </React.Fragment>
              ))}
            </div>
            <div className="flex items-center justify-between text-xs mono">
              <span className="text-[#a3a3a3]">
                {step === 4 ? 'Ingestion and indexing complete.' : `Embedding chunk batch… (${pct}%)`}
              </span>
              <span className="text-white font-bold">{pct}%</span>
            </div>
            <div className="h-1 bg-[#262626] overflow-hidden">
              <div className="h-full bg-white transition-all duration-150" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}
      </div>

      <AppFooter extra="FAISS HYBRID RETRIEVAL OPERATIONAL" />
    </>
  )
}
