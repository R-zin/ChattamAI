import React, { useState } from 'react'
import { toast } from '../components/Toast.jsx'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { analysisModel, embeddingModel } from '../data.js'

function Field({ label, value, onChange, type = 'text', helper }) {
  return (
    <div>
      <label className="block text-xs text-[#9AA7B6] mb-2">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mono text-sm bg-[#1C2531] border border-[#222C3A] rounded px-3 py-2.5 text-white outline-none focus:border-[#22D3EE]/50 transition-colors"
      />
      {helper && <div className="text-[10px] mono text-[#5B6879] mt-1.5">{helper}</div>}
    </div>
  )
}

export default function Settings() {
  const [topK, setTopK] = useState('6')
  const [chunkSize, setChunkSize] = useState('1000')
  const [overlap, setOverlap] = useState('150')
  const [provider, setProvider] = useState('Anthropic')

  return (
    <>
      <Header eyebrow="System Configuration" title="Settings" subtitle="Retrieval, model, and analysis configuration" />
      <div className="p-6 md:p-8 space-y-6 max-w-4xl">
        <div className="border-l-2 border-[#22D3EE] bg-[#22D3EE]/5 px-4 py-3">
          <div className="text-[11px] mono text-[#9AA7B6] flex items-start gap-2">
            <Icon name="info" className="text-[#22D3EE] flex-shrink-0 mt-0.5" />
            These settings affect future analyses — engineer review still required.
          </div>
        </div>

        <section className="bg-[#10151C] border border-[#222C3A] rounded p-6">
          <h3 className="text-sm font-semibold text-white uppercase tracking-wide flex items-center gap-2 mb-5"><Icon name="search" className="text-[#22D3EE]" /> Retrieval</h3>
          <div className="grid sm:grid-cols-3 gap-5">
            <Field label="top_k" value={topK} onChange={setTopK} type="number" helper="top_k — number of KBR chunks retrieved per analysis" />
            <Field label="Chunk size" value={chunkSize} onChange={setChunkSize} type="number" helper="Max token length per document segment" />
            <Field label="Chunk overlap" value={overlap} onChange={setOverlap} type="number" helper="Contextual overlap between adjacent chunks" />
          </div>
        </section>

        <section className="bg-[#10151C] border border-[#222C3A] rounded p-6">
          <h3 className="text-sm font-semibold text-white uppercase tracking-wide flex items-center gap-2 mb-5"><Icon name="cpu" className="text-[#22D3EE]" /> Model</h3>
          <div className="grid sm:grid-cols-2 gap-5 mb-5">
            <div>
              <label className="block text-xs text-[#9AA7B6] mb-2">Analysis model</label>
              <div className="mono text-sm bg-[#0C1117] border border-[#222C3A] rounded px-3 py-2.5 text-white">{analysisModel}</div>
            </div>
            <div>
              <label className="block text-xs text-[#9AA7B6] mb-2">Embedding model</label>
              <div className="mono text-sm bg-[#0C1117] border border-[#222C3A] rounded px-3 py-2.5 text-white">{embeddingModel}</div>
            </div>
          </div>
          <div>
            <label className="block text-xs text-[#9AA7B6] mb-2">Model provider</label>
            <div className="inline-flex border border-[#222C3A] rounded overflow-hidden">
              {['Anthropic', 'OpenRouter'].map((p) => (
                <button key={p} onClick={() => setProvider(p)} className={`px-4 py-2 text-xs mono transition-colors ${provider === p ? 'bg-[#22D3EE]/15 text-[#22D3EE]' : 'text-[#5B6879] hover:text-white'}`}>
                  {p}
                </button>
              ))}
            </div>
            <div className="text-[10px] mono text-[#5B6879] mt-1.5">Selected endpoint for LLM inference calls</div>
          </div>
        </section>

        <section className="bg-[#10151C] border border-[#222C3A] rounded p-6">
          <h3 className="text-sm font-semibold text-white uppercase tracking-wide flex items-center gap-2 mb-5"><Icon name="database-zap" className="text-[#22D3EE]" /> System</h3>
          <div className="flex flex-col sm:flex-row gap-4">
            <button onClick={() => toast('Re-ingesting KBR corpus — chunking + embedding over data/kbr.', 'ok')} className="px-4 py-2.5 rounded text-sm font-medium text-[#9AA7B6] bg-[#161D27] border border-[#222C3A] hover:text-white flex items-center gap-2">
              <Icon name="refresh-cw" /> Re-ingest KBR corpus
            </button>
            <button onClick={() => toast('Rebuilding FAISS IndexFlatL2 from stored embeddings.', 'ok')} className="px-4 py-2.5 rounded text-sm font-medium text-[#9AA7B6] bg-[#161D27] border border-[#222C3A] hover:text-white flex items-center gap-2">
              <Icon name="layers" /> Rebuild vector index
            </button>
          </div>
        </section>

        <button onClick={() => toast('Settings saved — applies to future analyses.', 'ok')} className="accent-gradient px-6 py-3 rounded text-sm font-semibold text-black hover:brightness-110">
          Save Changes
        </button>
      </div>
      <AppFooter />
    </>
  )
}
