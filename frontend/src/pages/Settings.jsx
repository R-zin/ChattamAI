import React, { useEffect, useState } from 'react'
import { toast } from '../components/Toast.jsx'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { analysisModel, apiAvailable, embeddingModel, totpDisable, totpEnable, totpSetup, totpStatus } from '../data.js'

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
  // --- 2FA state (Security section) ---
  const [totp, setTotp] = useState(null)          // TotpStatusResponse | null
  const [enroll, setEnroll] = useState(null)       // TotpSetupResponse | null
  const [codesShown, setCodesShown] = useState(null) // recovery codes (shown once)
  const [code, setCode] = useState('')
  const [disarm, setDisarm] = useState(false)
  const [disarmPw, setDisarmPw] = useState('')
  const [disarmCode, setDisarmCode] = useState('')
  const [secBusy, setSecBusy] = useState(false)

  useEffect(() => {
    if (apiAvailable()) {
      totpStatus().then(setTotp).catch(() => setTotp(null))
    }
  }, [])

  const startEnroll = async () => {
    setSecBusy(true)
    try {
      setEnroll(await totpSetup())
      setCodesShown(null)
      setCode('')
    } catch (e) { toast(e.message || 'Setup failed', 'info') }
    finally { setSecBusy(false) }
  }
  const confirmEnroll = async () => {
    setSecBusy(true)
    try {
      const res = await totpEnable({ code })
      setCodesShown(res.recovery_codes || [])
      setEnroll(null)
      setCode('')
      toast('Two-factor authentication enabled.', 'ok')
      if (apiAvailable()) setTotp(await totpStatus())
    } catch (e) { toast(e.message || 'Invalid code', 'info') }
    finally { setSecBusy(false) }
  }
  const confirmDisable = async () => {
    setSecBusy(true)
    try {
      await totpDisable({ password: disarmPw, code: disarmCode })
      setTotp(await totpStatus())
      setDisarm(false); setDisarmPw(''); setDisarmCode('')
      toast('Two-factor authentication disabled.', 'ok')
    } catch (e) { toast(e.message || 'Disable failed', 'info') }
    finally { setSecBusy(false) }
  }
  const downloadCodes = () => {
    const blob = new Blob([(codesShown || []).join('\n')], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'chattam-recovery-codes.txt'
    a.click()
    URL.revokeObjectURL(a.href)
  }

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

        {/* Security / 2FA (plan slice A.2.4) */}
        <section className="bg-[#10151C] border border-[#222C3A] rounded p-6">
          <h3 className="text-sm font-semibold text-white uppercase tracking-wide flex items-center gap-2 mb-5"><Icon name="shield" className="text-[#22D3EE]" /> Security</h3>
          {!apiAvailable() ? (
            <div className="text-[11px] mono text-[#5B6879]">API not configured — two-factor authentication is managed by the backend. Set VITE_API_URL to enable it.</div>
          ) : !totp ? (
            <div className="text-[11px] mono text-[#5B6879]">Loading 2FA status…</div>
          ) : (
            <div className="space-y-5">
              {totp.totp_required && !totp.totp_enabled && (
                <div className="border-l-2 border-[#fbbf24] bg-[#fbbf24]/5 px-4 py-3">
                  <div className="text-[11px] mono text-[#9AA7B6] flex items-start gap-2">
                    <Icon name="alert-triangle" className="text-[#fbbf24] flex-shrink-0 mt-0.5" />
                    This server requires two-factor authentication. Enrol below to keep access.
                  </div>
                </div>
              )}

              {/* Recovery codes shown ONCE after enabling */}
              {codesShown ? (
                <div className="border border-[#22D3EE]/40 bg-[#22D3EE]/5 rounded p-4">
                  <div className="text-xs mono text-[#22D3EE] mb-2">Recovery codes — store these somewhere safe. Each works once and is never shown again.</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 mono text-sm text-white my-3">
                    {codesShown.map((c) => (<div key={c}>{c}</div>))}
                  </div>
                  <div className="flex gap-3">
                    <button onClick={downloadCodes} className="px-4 py-2 rounded text-xs font-medium text-black accent-gradient hover:brightness-110 flex items-center gap-2"><Icon name="download" /> Download</button>
                    <button onClick={() => { navigator.clipboard?.writeText(codesShown.join('\n')); toast('Recovery codes copied.', 'ok') }} className="px-4 py-2 rounded text-xs font-medium text-[#9AA7B6] bg-[#161D27] border border-[#222C3A] hover:text-white">Copy</button>
                    <button onClick={() => setCodesShown(null)} className="px-4 py-2 rounded text-xs font-medium text-[#9AA7B6] hover:text-white ml-auto">Done</button>
                  </div>
                </div>
              ) : enroll ? (
                /* Enrollment in progress: QR + manual secret + confirm code */
                <div className="space-y-4">
                  <div className="text-[11px] mono text-[#9AA7B6]">Scan this QR with your authenticator app, or enter the key manually.</div>
                  <div className="flex flex-col sm:flex-row gap-5 items-start">
                    {enroll.qr_png_data_uri ? (
                      <div className="bg-white p-3 rounded"><img src={enroll.qr_png_data_uri} alt="TOTP QR code" className="w-40 h-40" /></div>
                    ) : (
                      <div className="w-40 h-40 bg-[#0C1117] border border-[#222C3A] rounded flex items-center justify-center text-[#5B6879] text-3xl"><Icon name="qrcode" /></div>
                    )}
                    <div className="flex-1 w-full">
                      <Field label="Manual entry key" value={enroll.secret} onChange={() => {}} helper="base32" />
                      <div className="mt-4"><Field label="Enter the 6-digit code to confirm" value={code} onChange={setCode} /></div>
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={confirmEnroll} disabled={secBusy || code.length < 6} className={`px-4 py-2.5 rounded text-sm font-semibold text-black accent-gradient hover:brightness-110 ${(secBusy || code.length < 6) ? 'opacity-40 cursor-not-allowed' : ''}`}>Confirm &amp; enable</button>
                    <button onClick={() => setEnroll(null)} disabled={secBusy} className="px-4 py-2 rounded text-xs font-medium text-[#9AA7B6] bg-[#161D27] border border-[#222C3A] hover:text-white">Cancel</button>
                  </div>
                </div>
              ) : totp.totp_enabled ? (
                /* Enrolled: status + disable */
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <span className="pill pill-ok">2FA ENABLED</span>
                    <span className="text-xs mono text-[#9AA7B6]">{totp.recovery_codes_remaining} recovery code{totp.recovery_codes_remaining === 1 ? '' : 's'} remaining</span>
                  </div>
                  {disarm ? (
                    <div className="space-y-3">
                      <div className="grid sm:grid-cols-2 gap-4">
                        <Field label="Password" type="password" value={disarmPw} onChange={setDisarmPw} />
                        <Field label="Authenticator code" value={disarmCode} onChange={setDisarmCode} />
                      </div>
                      <div className="flex gap-3">
                        <button onClick={confirmDisable} disabled={secBusy} className={`px-4 py-2 rounded text-xs font-medium text-black bg-[#f87171] hover:brightness-110 ${secBusy ? 'opacity-40 cursor-not-allowed' : ''}`}>Confirm disable</button>
                        <button onClick={() => setDisarm(false)} className="px-4 py-2 rounded text-xs font-medium text-[#9AA7B6] bg-[#161D27] border border-[#222C3A] hover:text-white">Keep 2FA on</button>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => setDisarm(true)} className="px-4 py-2.5 rounded text-sm font-medium text-[#9AA7B6] bg-[#161D27] border border-[#222C3A] hover:text-white flex items-center gap-2"><Icon name="shield-alert" /> Disable two-factor authentication</button>
                  )}
                </div>
              ) : (
                /* Not enrolled: enable */
                <div>
                  <div className="text-[11px] mono text-[#9AA7B6] mb-4">Add a second layer of security with a time-based one-time code from an authenticator app.</div>
                  <button onClick={startEnroll} disabled={secBusy} className={`px-4 py-2.5 rounded text-sm font-semibold text-black accent-gradient hover:brightness-110 flex items-center gap-2 ${secBusy ? 'opacity-40 cursor-not-allowed' : ''}`}>
                    {secBusy && <Icon name="loader" className="spin-1" />} Enable two-factor authentication
                  </button>
                </div>
              )}
            </div>
          )}
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
