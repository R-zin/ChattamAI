import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from '../components/Toast.jsx'
import Icon from '../components/Icon.jsx'
import {
  apiAvailable,
  login,
  setToken,
  totpVerify,
  totpRecover,
} from '../data.js'

function Field({ label, ...props }) {
  return (
    <div>
      <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">{label}</label>
      <input
        className="w-full mono text-xs bg-[#0e0e0e] border border-[#333333] px-3 py-2.5 text-white outline-none focus:border-white transition-colors"
        {...props}
      />
    </div>
  )
}

export default function Login() {
  const nav = useNavigate()
  const [stage, setStage] = useState('credentials')
  const [busy, setBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [otpToken, setOtpToken] = useState(null)
  const [setupRequired, setSetupRequired] = useState(false)
  const [code, setCode] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)

  if (!apiAvailable()) {
    return (
      <div className="min-h-screen blueprint-grid flex items-center justify-center p-6 bg-[#0a0a0a]">
        <div className="w-full max-w-md bg-[#121212] border border-[#262626] p-8 space-y-6">
          <div>
            <div className="text-[10px] mono uppercase tracking-widest text-[#737373]">CHATTAM.AI // KBR COMPLIANCE ENGINE</div>
            <h1 className="text-xl font-bold text-white mt-1 uppercase font-sans">Auditor Sign In</h1>
          </div>

          <div className="border border-[#262626] bg-[#0e0e0e] p-3 text-xs mono text-[#a3a3a3]">
            [DEMO MODE] Running with client-side verification. Set VITE_API_URL to connect to the live FastAPI backend.
          </div>

          <button
            onClick={() => nav('/')}
            className="w-full bg-white text-black font-mono font-bold text-xs py-3 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer"
          >
            ENTER COMPLIANCE WORKSPACE →
          </button>
        </div>
      </div>
    )
  }

  const finish = (token) => {
    setToken(token, remember)
    nav('/')
  }

  const submitCredentials = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      const res = await login({ email, password })
      if (res.access_token) {
        finish(res.access_token)
      } else if (res.otp_required) {
        setOtpToken(res.otp_token)
        setSetupRequired(!!res.otp_setup_required)
        setStage('totp')
        if (res.otp_setup_required) {
          toast('Two-factor authentication is required. Enroll after sign in.', 'info')
        }
      }
    } catch (err) {
      toast(err.message || 'Sign-in failed', 'info')
    } finally {
      setBusy(false)
    }
  }

  const submitCode = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      const res = useRecovery
        ? await totpRecover({ otpToken, recoveryCode: code })
        : await totpVerify({ otpToken, code })
      finish(res.access_token)
    } catch (err) {
      toast(err.message || 'Verification failed', 'info')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen blueprint-grid flex items-center justify-center p-6 bg-[#0a0a0a]">
      <div className="w-full max-w-md bg-[#121212] border border-[#262626] p-8 space-y-6">
        <div>
          <div className="text-[10px] mono uppercase tracking-widest text-[#737373]">CHATTAM.AI // KBR ENGINE</div>
          <h1 className="text-xl font-bold text-white mt-1 uppercase font-sans">
            {stage === 'totp' ? 'Two-Factor Authentication' : 'Auditor Sign In'}
          </h1>
        </div>

        {stage === 'credentials' ? (
          <form onSubmit={submitCredentials} className="space-y-4">
            <Field label="EMAIL" type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
            <Field label="PASSWORD" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            <label className="flex items-center gap-2 text-xs mono text-[#a3a3a3] cursor-pointer select-none">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="accent-white" />
              Remember device session
            </label>
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-white text-black font-mono font-bold text-xs py-3 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer disabled:opacity-40"
            >
              {busy ? 'AUTHENTICATING…' : 'SIGN IN →'}
            </button>
          </form>
        ) : (
          <form onSubmit={submitCode} className="space-y-4">
            {setupRequired && (
              <div className="border border-white bg-[#0e0e0e] p-3 text-xs mono text-white">
                [!] 2FA required on this auditor server. Verify code to continue.
              </div>
            )}
            {useRecovery ? (
              <Field
                label="RECOVERY CODE"
                type="text"
                required
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="10-character code"
                helper="Each recovery code functions exactly once."
              />
            ) : (
              <div>
                <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">AUTHENTICATOR CODE</label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={8}
                  required
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="w-full mono text-center text-2xl tracking-[0.4em] bg-[#0e0e0e] border border-[#333333] px-3 py-2.5 text-white outline-none focus:border-white transition-colors"
                  placeholder="000000"
                />
              </div>
            )}
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-white text-black font-mono font-bold text-xs py-3 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer disabled:opacity-40"
            >
              {busy ? 'VERIFYING…' : useRecovery ? 'USE RECOVERY CODE →' : 'VERIFY CODE →'}
            </button>
            <button
              type="button"
              onClick={() => { setUseRecovery(!useRecovery); setCode('') }}
              className="w-full text-xs mono text-[#737373] hover:text-white transition-colors"
            >
              {useRecovery ? '← Use standard authenticator' : 'Lost device? Use emergency recovery code'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
