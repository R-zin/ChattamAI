import React, { useEffect, useState } from 'react'
import { toast } from '../components/Toast.jsx'
import { Header } from '../components/AppShell.jsx'
import { AppFooter } from '../components/Shared.jsx'
import Icon from '../components/Icon.jsx'
import { analysisModel, apiAvailable, embeddingModel, totpDisable, totpEnable, totpSetup, totpStatus } from '../data.js'

function Field({ label, value, onChange, type = 'text', helper }) {
  return (
    <div>
      <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mono text-xs bg-[#0e0e0e] border border-[#333333] px-3 py-2 text-white outline-none focus:border-white transition-colors"
      />
      {helper && <div className="text-[9px] mono text-[#525252] mt-1">{helper}</div>}
    </div>
  )
}

export default function Settings() {
  const [topK, setTopK] = useState('6')
  const [chunkSize, setChunkSize] = useState('1000')
  const [overlap, setOverlap] = useState('150')
  const [provider, setProvider] = useState('NVIDIA NIM')
  // --- 2FA state (Security section) ---
  const [totp, setTotp] = useState(null)
  const [enroll, setEnroll] = useState(null)
  const [codesShown, setCodesShown] = useState(null)
  const [code, setCode] = useState('')
  const [enrollPw, setEnrollPw] = useState('')
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
      setEnrollPw('')
    } catch (e) { toast(e.message || 'Setup failed', 'info') }
    finally { setSecBusy(false) }
  }
  const confirmEnroll = async () => {
    setSecBusy(true)
    try {
      const res = await totpEnable({ password: enrollPw, code })
      setCodesShown(res.recovery_codes || [])
      setEnroll(null)
      setCode('')
      setEnrollPw('')
      toast('Two-factor authentication enabled.', 'ok')
      if (apiAvailable()) setTotp(await totpStatus())
    } catch (e) { toast(e.message || 'Invalid code or password', 'info') }
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
      <Header
        eyebrow="SYSTEM CONFIGURATION // MODEL & VECTOR RETRIEVAL"
        title="Settings"
        subtitle="Manage NVIDIA NIM inference endpoints, vector retrieval parameters, and account security"
      />

      <div className="p-6 md:p-8 space-y-6 max-w-4xl bg-[#0a0a0a]">
        <div className="border border-[#262626] bg-[#121212] px-4 py-3 flex items-start gap-2.5">
          <span className="text-white font-bold mono text-xs">[NOTE]</span>
          <span className="text-xs mono text-[#a3a3a3]">
            Parameter modifications take effect immediately across all newly initiated architectural plan audits.
          </span>
        </div>

        {/* Retrieval Settings */}
        <section className="bg-[#121212] border border-[#262626] p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-[#262626] pb-3">
            <span className="w-1.5 h-1.5 bg-white inline-block" />
            <h3 className="text-xs font-bold text-white uppercase tracking-widest mono">Vector Retrieval Parameters</h3>
          </div>
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="TOP_K CHUNKS" value={topK} onChange={setTopK} type="number" helper="Max KBR rule chunks passed to LLM reasoning" />
            <Field label="CHUNK SIZE" value={chunkSize} onChange={setChunkSize} type="number" helper="Character length per document split" />
            <Field label="CHUNK OVERLAP" value={overlap} onChange={setOverlap} type="number" helper="Sliding window context preservation" />
          </div>
        </section>

        {/* Model Inference Settings */}
        <section className="bg-[#121212] border border-[#262626] p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-[#262626] pb-3">
            <span className="w-1.5 h-1.5 bg-white inline-block" />
            <h3 className="text-xs font-bold text-white uppercase tracking-widest mono">AI Model Inference Configuration</h3>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">Active LLM Model</label>
              <div className="mono text-xs bg-[#0e0e0e] border border-[#333333] px-3 py-2 text-white">
                {provider === 'NVIDIA NIM' ? 'nvidia/nemotron-3.5-super-vl-120b-a12b' : analysisModel}
              </div>
            </div>
            <div>
              <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">Dense Embedding Model</label>
              <div className="mono text-xs bg-[#0e0e0e] border border-[#333333] px-3 py-2 text-white">{embeddingModel}</div>
            </div>
          </div>
          <div>
            <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">Provider Endpoint</label>
            <div className="inline-flex border border-[#333333] bg-[#0e0e0e]">
              {['NVIDIA NIM', 'Anthropic', 'OpenRouter'].map((p) => (
                <button
                  key={p}
                  onClick={() => setProvider(p)}
                  className={`px-4 py-2 text-xs mono transition-colors ${
                    provider === p ? 'bg-white text-black font-bold' : 'text-[#737373] hover:text-white'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
            <div className="text-[9px] mono text-[#525252] mt-1">Configured for active compliance reasoning</div>
          </div>
        </section>

        {/* Security / 2FA Section */}
        <section className="bg-[#121212] border border-[#262626] p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-[#262626] pb-3">
            <span className="w-1.5 h-1.5 bg-white inline-block" />
            <h3 className="text-xs font-bold text-white uppercase tracking-widest mono">Security & Authentication (TOTP 2FA)</h3>
          </div>

          {!apiAvailable() ? (
            <div className="text-xs mono text-[#737373]">API not configured — running on local mock security state.</div>
          ) : !totp ? (
            <div className="text-xs mono text-[#737373]">Checking 2FA configuration…</div>
          ) : (
            <div className="space-y-4">
              {totp.totp_required && !totp.totp_enabled && (
                <div className="border border-white p-3 bg-[#0e0e0e] text-xs mono text-white">
                  [!] This auditor terminal requires two-factor authentication. Enroll below.
                </div>
              )}

              {codesShown ? (
                <div className="border border-white bg-[#0e0e0e] p-4 space-y-3">
                  <div className="text-xs mono text-white font-bold">RECOVERY CODES — STORE SECURELY:</div>
                  <div className="grid grid-cols-2 gap-2 mono text-xs text-white bg-[#121212] p-3 border border-[#262626]">
                    {codesShown.map((c) => (<div key={c}>{c}</div>))}
                  </div>
                  <div className="flex gap-2">
                    <button onClick={downloadCodes} className="px-3 py-1.5 bg-white text-black mono text-xs font-bold hover:bg-[#e5e5e5] flex items-center gap-1">
                      <Icon name="download" /> DOWNLOAD
                    </button>
                    <button onClick={() => { navigator.clipboard?.writeText(codesShown.join('\n')); toast('Codes copied.', 'ok') }} className="px-3 py-1.5 border border-[#333333] hover:border-white text-white mono text-xs bg-[#121212]">
                      COPY
                    </button>
                    <button onClick={() => setCodesShown(null)} className="px-3 py-1.5 text-xs mono text-[#a3a3a3] hover:text-white ml-auto">
                      DONE
                    </button>
                  </div>
                </div>
              ) : enroll ? (
                <div className="space-y-4">
                  <div className="text-xs mono text-[#a3a3a3]">Scan QR with authenticator or enter key:</div>
                  <div className="flex flex-col sm:flex-row gap-5 items-start">
                    {enroll.qr_png_data_uri ? (
                      <div className="bg-white p-2 border border-white"><img src={enroll.qr_png_data_uri} alt="TOTP QR code" className="w-36 h-36" /></div>
                    ) : (
                      <div className="w-36 h-36 bg-[#0e0e0e] border border-[#262626] flex items-center justify-center text-white text-2xl"><Icon name="qrcode" /></div>
                    )}
                    <div className="flex-1 w-full space-y-3">
                      <Field label="MANUAL ENTRY SECRET" value={enroll.secret} onChange={() => {}} helper="Base32 Key" />
                      <Field label="ACCOUNT PASSWORD" type="password" value={enrollPw} onChange={setEnrollPw} />
                      <Field label="6-DIGIT VERIFICATION CODE" value={code} onChange={setCode} />
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={confirmEnroll}
                      disabled={secBusy || code.length < 6 || !enrollPw}
                      className="px-4 py-2 bg-white text-black font-mono text-xs font-bold border border-white hover:bg-[#e5e5e5] disabled:opacity-40"
                    >
                      CONFIRM &amp; ENABLE
                    </button>
                    <button onClick={() => setEnroll(null)} className="px-4 py-2 text-xs mono text-[#a3a3a3] hover:text-white border border-[#333333] bg-[#0e0e0e]">
                      CANCEL
                    </button>
                  </div>
                </div>
              ) : totp.totp_enabled ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] mono bg-white text-black font-bold px-2 py-0.5">2FA ACTIVE</span>
                    <span className="text-xs mono text-[#a3a3a3]">{totp.recovery_codes_remaining} codes remaining</span>
                  </div>
                  {disarm ? (
                    <div className="space-y-3 pt-2">
                      <div className="grid sm:grid-cols-2 gap-3">
                        <Field label="PASSWORD" type="password" value={disarmPw} onChange={setDisarmPw} />
                        <Field label="AUTHENTICATOR CODE" value={disarmCode} onChange={setDisarmCode} />
                      </div>
                      <div className="flex gap-3">
                        <button onClick={confirmDisable} disabled={secBusy} className="px-4 py-2 text-xs mono bg-white text-black font-bold hover:bg-[#e5e5e5]">CONFIRM DISABLE</button>
                        <button onClick={() => setDisarm(false)} className="px-4 py-2 text-xs mono text-[#a3a3a3] hover:text-white border border-[#333333] bg-[#0e0e0e]">CANCEL</button>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => setDisarm(true)} className="px-3 py-1.5 text-xs mono text-[#a3a3a3] hover:text-white border border-[#333333] hover:border-white bg-[#0e0e0e]">
                      DISABLE 2FA
                    </button>
                  )}
                </div>
              ) : (
                <div>
                  <button onClick={startEnroll} disabled={secBusy} className="px-4 py-2 bg-white text-black font-mono text-xs font-bold border border-white hover:bg-[#e5e5e5]">
                    + ENABLE TWO-FACTOR AUTHENTICATION
                  </button>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Save button */}
        <button
          onClick={() => toast('System configuration saved.', 'ok')}
          className="bg-white text-black font-mono text-xs font-bold px-6 py-3 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer"
        >
          SAVE CONFIGURATION CHANGES
        </button>
      </div>

      <AppFooter />
    </>
  )
}
