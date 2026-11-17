import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Pill from '../components/Pill.jsx'
import Icon from '../components/Icon.jsx'
import { toast } from '../components/Toast.jsx'
import {
  fetchKbrDocuments,
  fetchIndexStats,
  searchKbrRules,
  askRulebook,
  ingestRules,
  uploadKbrDocument,
  ANSWER_CONFIDENCE_META,
  SEARCH_MODES,
} from '../data.js'

const STEPS = ['Loading PDF', 'Chunking', 'Embedding', 'Indexing', 'Complete']

const DOC_STATUS_PILL = { INDEXED: 'pill-ok', 'NOT INDEXED': 'pill-warn', UNKNOWN: 'pill-info' }

// Where an excerpt sits in the rulebook: "Rule 26, Table 4 · CHAPTER IV … · p. 50".
function locator(rule) {
  return [rule.section, rule.page ? `p. ${rule.page}` : null].filter(Boolean).join(' · ')
}

// The stat strip is derived from the live index, never from static numbers.
function statItems(stats) {
  if (!stats) {
    return ['Documents Indexed', 'Chunks Indexed', 'Rules Recognised', 'Embedding Model', 'Retrieval'].map((label) => ({
      label,
      value: '—',
    }))
  }
  const docs = Array.isArray(stats.documents) ? stats.documents : []
  const rules = docs.reduce((n, d) => n + (d.rules || 0), 0)
  const strategy = stats.retrieval_strategy === 'simple' ? 'Single query' : 'Topic-aware'
  return [
    { label: 'Documents Indexed', value: String(docs.length) },
    { label: 'Chunks Indexed', value: Number(stats.index_size || 0).toLocaleString() },
    { label: 'Rules Recognised', value: rules.toLocaleString() },
    { label: 'Embedding Model', value: stats.embedding_model || '—' },
    { label: 'Retrieval', value: `${strategy} · ${stats.hybrid ? 'Hybrid' : 'Semantic'}`, ok: true },
  ]
}

// Render an answer, turning each verified [n] marker into a citation chip.
function AnswerText({ text }) {
  const parts = String(text || '').split(/(\[\d{1,2}\])/g)
  return (
    <p className="text-sm text-ink leading-relaxed">
      {parts.map((part, i) =>
        /^\[\d{1,2}\]$/.test(part) ? (
          <a
            key={i}
            href={`#citation-${part.slice(1, -1)}`}
            className="mx-0.5 px-1 text-[10px] font-bold text-on-accent bg-accent align-super no-underline"
            aria-label={`Citation ${part.slice(1, -1)}`}
          >
            {part.slice(1, -1)}
          </a>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </p>
  )
}

function Citation({ c }) {
  return (
    <li id={`citation-${c.index}`} className="p-4 bg-inset border border-line space-y-2">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <span className="text-xs font-bold text-ink">
          <span className="text-on-accent bg-accent px-1.5 py-0.5 mr-2">{c.index}</span>
          {c.rule_id || 'Excerpt'}
        </span>
        <span className="text-[10px] text-ink-3">{c.source}</span>
      </div>
      {locator(c) && <div className="text-[10px] text-ink-2">{locator(c)}</div>}
      <p className="text-xs text-ink-2 leading-relaxed">{c.excerpt}</p>
    </li>
  )
}

function RulebookAnswer({ result }) {
  const meta = ANSWER_CONFIDENCE_META[result.confidence] || ANSWER_CONFIDENCE_META.none
  const citations = Array.isArray(result.citations) ? result.citations : []
  const cited = citations.filter((c) => c.cited)
  const others = citations.filter((c) => !c.cited)
  return (
    <div className="space-y-4 pt-4 border-t border-line" role="status" aria-live="polite">
      <div className="flex items-center gap-3 flex-wrap">
        <Pill kind={meta.pill}>{meta.label}</Pill>
        <span className="text-[11px] text-ink-2">{meta.hint}</span>
      </div>
      <AnswerText text={result.answer} />
      {cited.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] text-ink-3 uppercase tracking-wider font-semibold">Cited rules</h4>
          <ol className="space-y-2">
            {cited.map((c) => (
              <Citation key={c.index} c={c} />
            ))}
          </ol>
        </div>
      )}
      {others.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-ink-2 hover:text-ink">
            {result.abstained ? 'Rules that were checked' : 'Also retrieved, not cited'} ({others.length})
          </summary>
          <ol className="space-y-2 mt-2">
            {others.map((c) => (
              <Citation key={c.index} c={c} />
            ))}
          </ol>
        </details>
      )}
    </div>
  )
}

export default function Knowledge() {
  const [docList, setDocList] = useState([])
  const [stats, setStats] = useState(null)
  const [ingesting, setIngesting] = useState(false)
  const [step, setStep] = useState(0)
  const [pct, setPct] = useState(0)

  // Rule Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode] = useState('hybrid')
  const [searching, setSearching] = useState(false)
  const [searchResults, setSearchResults] = useState(null)

  // Rulebook Q&A state
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [answer, setAnswer] = useState(null)

  const uploadRef = useRef(null)
  const active = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const docs = await fetchKbrDocuments()
      if (active.current && Array.isArray(docs)) setDocList(docs)
    } catch (err) {
      if (active.current) toast(`Could not load KBR documents: ${err.message}`, 'danger')
    }
    try {
      const next = await fetchIndexStats()
      if (active.current) setStats(next)
    } catch (err) {
      if (active.current) {
        setStats(null)
        toast(`Could not load index statistics: ${err.message}`, 'danger')
      }
    }
  }, [])

  useEffect(() => {
    active.current = true
    refresh()
    return () => {
      active.current = false
    }
  }, [refresh])

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
      const result = await ingestRules(false)
      const added = typeof result?.chunks === 'number' ? ` ${result.chunks.toLocaleString()} new chunks indexed.` : ''
      toast(`Corpus ingestion complete.${added}`, 'ok')
      await refresh()
    } catch (e) {
      setIngesting(false)
      setPct(0)
      toast(`Ingestion failed: ${e.message}`, 'danger')
    }
  }

  const handleUpload = async (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    try {
      toast(`Uploading “${f.name}” to KBR corpus…`, 'ok')
      await uploadKbrDocument(f)
      toast(`“${f.name}” uploaded successfully. Ingest rules to rebuild index.`, 'ok')
      await refresh()
    } catch (err) {
      toast(`Upload failed: ${err.message}`, 'danger')
    }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const results = await searchKbrRules(searchQuery.trim(), 5, searchMode)
      setSearchResults(Array.isArray(results) ? results : [])
    } catch (err) {
      toast(`Search failed: ${err.message}`, 'danger')
    } finally {
      setSearching(false)
    }
  }

  const handleAsk = async (e) => {
    e.preventDefault()
    const q = question.trim()
    if (q.length < 3) return
    setAsking(true)
    try {
      setAnswer(await askRulebook(q))
    } catch (err) {
      setAnswer(null)
      toast(`Could not answer: ${err.message}`, 'danger')
    } finally {
      setAsking(false)
    }
  }

  return (
    <>
      <Header
        eyebrow="STATUTORY CORPUS"
        title="KBR Knowledge Base"
        subtitle="Indexed statutory rulebook powering hybrid retrieval, cited answers and compliance reasoning"
        action={
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="bg-accent text-on-accent font-mono text-xs font-bold px-4 py-2 border border-ink hover:bg-accent-strong flex items-center gap-2 cursor-pointer transition-colors disabled:opacity-40"
          >
            <Icon name="upload-cloud" /> {ingesting ? 'INGESTING…' : 'RE-INDEX RULES'}
          </button>
        }
      />

      <div className="p-6 md:p-8 space-y-6 bg-bg">
        {/* Metric Strip (live index statistics) */}
        <dl className="grid grid-cols-2 md:grid-cols-5 gap-px border border-line bg-surface divide-x divide-line">
          {statItems(stats).map((s) => (
            <div key={s.label} className="bg-surface p-4 hover:bg-surface-2 transition-colors">
              <dt className="text-[10px] mono text-ink-3 uppercase tracking-wider mb-1 font-semibold">{s.label}</dt>
              <dd className="text-sm mono text-ink font-bold flex items-center gap-2 break-all">
                {s.ok && <span className="w-1.5 h-1.5 bg-accent inline-block shrink-0" aria-hidden="true" />}
                {s.value}
              </dd>
            </div>
          ))}
        </dl>

        {/* Ask the Rulebook */}
        <section aria-labelledby="ask-heading" className="bg-surface border border-line p-6 space-y-4">
          <div className="border-b border-line pb-3 space-y-1">
            <h3 id="ask-heading" className="text-xs font-bold text-ink tracking-widest uppercase flex items-center gap-2 mono">
              <span className="w-1.5 h-1.5 bg-accent inline-block" aria-hidden="true" /> Ask the Rulebook
            </h3>
            <p className="text-xs text-ink-2">
              Answers are written only from the indexed rules and every statement is cited. If the rules do not cover
              your question, you are told so instead of given a guess.
            </p>
          </div>

          <form onSubmit={handleAsk} className="flex flex-col sm:flex-row gap-3">
            <label htmlFor="ask-input" className="sr-only">
              Question for the rulebook
            </label>
            <input
              id="ask-input"
              type="text"
              value={question}
              maxLength={600}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What is the minimum front setback for a residential building?"
              className="flex-1 bg-inset border border-line-strong px-4 py-2.5 text-xs mono text-ink placeholder-ink-3 focus:outline-none focus:border-ink transition-colors"
            />
            <button
              type="submit"
              disabled={asking || question.trim().length < 3}
              className="bg-accent text-on-accent font-mono text-xs font-bold px-5 py-2.5 border border-ink hover:bg-accent-strong transition-colors cursor-pointer disabled:opacity-40"
            >
              <Icon name="book-open" /> {asking ? 'READING THE RULES…' : 'ASK'}
            </button>
          </form>

          {answer && <RulebookAnswer result={answer} />}
        </section>

        {/* Rule Search */}
        <section aria-labelledby="search-heading" className="bg-surface border border-line p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <h3 id="search-heading" className="text-xs font-bold text-ink tracking-widest uppercase flex items-center gap-2 mono">
              <span className="w-1.5 h-1.5 bg-accent inline-block" aria-hidden="true" /> Rule Search
            </h3>
          </div>

          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
            <label htmlFor="search-input" className="sr-only">
              Search the rules
            </label>
            <input
              id="search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Kerala Building Rules (e.g. front setback, FAR, coverage, staircase, fire escape)…"
              className="flex-1 bg-inset border border-line-strong px-4 py-2.5 text-xs mono text-ink placeholder-ink-3 focus:outline-none focus:border-ink transition-colors"
            />
            <label htmlFor="search-mode" className="sr-only">
              Search mode
            </label>
            <select
              id="search-mode"
              value={searchMode}
              onChange={(e) => setSearchMode(e.target.value)}
              className="bg-inset border border-line-strong px-3 py-2.5 text-xs mono text-ink focus:outline-none focus:border-ink"
            >
              {SEARCH_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label} — {m.hint}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={searching || !searchQuery.trim()}
              className="bg-accent text-on-accent font-mono text-xs font-bold px-5 py-2.5 border border-ink hover:bg-accent-strong transition-colors cursor-pointer disabled:opacity-40"
            >
              <Icon name="search" /> {searching ? 'SEARCHING…' : 'SEARCH'}
            </button>
          </form>

          {searchResults && (
            <div className="space-y-3 mt-4 pt-4 border-t border-line" aria-live="polite">
              {searchResults.length === 0 ? (
                <div className="text-xs mono text-ink-3 p-4 bg-inset border border-line text-center">
                  NO MATCHING BUILDING RULES FOUND FOR “{searchQuery}”.
                </div>
              ) : (
                searchResults.map((r, i) => (
                  <div key={i} className="p-4 bg-inset border border-line space-y-2 hover:border-ink transition-colors">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <span className="text-xs font-bold mono text-ink">{r.rule_id || `CHUNK MATCH #${i + 1}`}</span>
                      <span className="text-[10px] mono text-on-accent bg-accent px-2 py-0.5 font-bold">
                        RELEVANCE: {r.score}
                      </span>
                    </div>
                    {locator(r) && <div className="text-[10px] text-ink-2">{locator(r)}</div>}
                    <p className="text-xs text-ink-2 leading-relaxed font-mono">{r.excerpt}</p>
                    <div className="flex items-center gap-x-4 gap-y-1 flex-wrap text-[10px] mono text-ink-3">
                      {r.source && <span>SOURCE // {r.source}</span>}
                      {typeof r.dense_score === 'number' && <span>SEMANTIC {r.dense_score.toFixed(2)}</span>}
                      {typeof r.lexical_score === 'number' && <span>KEYWORD {r.lexical_score.toFixed(2)}</span>}
                      {Array.isArray(r.matched_terms) && r.matched_terms.length > 0 && (
                        <span>MATCHED: {r.matched_terms.join(', ')}</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </section>

        {/* Documents Table */}
        <div className="bg-surface border border-line overflow-hidden">
          <div className="px-5 py-3.5 border-b border-line bg-surface-2 flex items-center justify-between">
            <h3 className="text-xs font-bold text-ink tracking-widest uppercase flex items-center gap-2 mono">
              <span className="w-1.5 h-1.5 bg-accent inline-block" aria-hidden="true" /> Ingested Corpus Documents
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
                className="px-3 py-1.5 text-xs mono text-ink border border-line-strong hover:border-ink bg-inset flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <Icon name="upload" /> + UPLOAD DOCUMENT
              </button>
            </div>
          </div>
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Indexed KBR documents">
            <table className="w-full min-w-[760px] text-left border-collapse">
              <thead>
                <tr className="border-b border-line bg-inset">
                  {['Document File', 'Format', 'Pages', 'Rules', 'Chunks', 'File Updated', 'Index Status'].map((h) => (
                    <th key={h} scope="col" className="px-4 py-3 text-[10px] mono text-ink-3 uppercase tracking-wider font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {docList.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-xs mono text-ink-3 text-center">
                      No KBR documents found. Upload a document, then run ingestion.
                    </td>
                  </tr>
                )}
                {docList.map((d, idx) => (
                  <tr key={d.doc || idx} className="hover:bg-surface-2 transition-colors">
                    <td className="px-4 py-3.5 text-xs font-semibold text-ink">{d.doc}</td>
                    <td className="px-4 py-3.5"><span className="text-[10px] mono px-2 py-0.5 border border-line bg-bg text-ink-2">{d.type}</span></td>
                    <td className="px-4 py-3.5 text-xs mono text-ink-2">{d.pages}</td>
                    <td className="px-4 py-3.5 text-xs mono text-ink-2">{d.rules ?? '—'}</td>
                    <td className="px-4 py-3.5 text-xs mono text-ink font-medium">{d.chunks}</td>
                    <td className="px-4 py-3.5 text-[10px] mono text-ink-3">{d.indexed}</td>
                    <td className="px-4 py-3.5"><Pill kind={DOC_STATUS_PILL[d.status] || 'pill-info'}>{d.status}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Ingestion Progress */}
        {(ingesting || pct > 0) && (
          <div className="bg-surface border border-line p-6 fade-rise space-y-4">
            <div className="text-[10px] mono text-ink-2 uppercase tracking-widest font-semibold">Corpus Ingestion Progress</div>
            <div className="flex items-center gap-0 mb-4">
              {STEPS.map((s, i) => (
                <React.Fragment key={s}>
                  {i > 0 && <div className={`flex-1 h-px ${i <= step ? 'bg-accent' : 'bg-surface-3'}`} />}
                  <div className="flex flex-col items-center px-1">
                    <div className={`w-8 h-8 flex items-center justify-center border ${
                      i <= step ? 'border-ink bg-inset text-ink' : 'border-line text-ink-3'
                    }`}>
                      {i < step || (i === step && step === 4) ? <Icon name="check" className="text-sm" /> : <span className="mono text-[10px]">{i + 1}</span>}
                    </div>
                    <div className={`text-[9px] mono uppercase tracking-wider mt-2 whitespace-nowrap ${i <= step ? 'text-ink' : 'text-ink-3'}`}>{s}</div>
                  </div>
                </React.Fragment>
              ))}
            </div>
            <div className="flex items-center justify-between text-xs mono">
              <span className="text-ink-2">
                {step === 4 ? 'Ingestion and indexing complete.' : `Embedding chunk batch… (${pct}%)`}
              </span>
              <span className="text-ink font-bold">{pct}%</span>
            </div>
            <div className="h-1 bg-surface-3 overflow-hidden">
              <div className="h-full bg-accent transition-all duration-150" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}
      </div>

      <AppFooter />
    </>
  )
}
