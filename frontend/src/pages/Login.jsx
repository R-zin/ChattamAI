import React, { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
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
      <label className="block text-xs text-[#9AA7B6] mb-2">{label}</label>
      <input
        className="w-full mono text-sm bg-[#1C2531] border border-[#222C3A] rounded px-3 py-2.5 text-white outline-none focus:border-[#22D3EE]/50 transition-colors"
        {...props}
      />
    </div>
  )
}

// 2FA login: a two-stage machine (credentials -> code). Rendered OUTSIDE AppShell
// (no sidebar/Header) per plan A.2.2. When the API isn't configured the demo runs
// straight through on mock data with no fake gating.
export default function Login() {
  const nav = useNavigate()
  const [stage, setStage] = useState('credentials') // 'credentials' | 'totp'
  const [busy, setBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  // challenge state (stage 'totp')
  const [otpToken, setOtpToken] = useState(null)
  const [setupRequired, setSetupRequired] = useState(false)
  const [code, setCode] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)

  if (!apiAvailable()) {
    return (
      <div className="min-h-screen blueprint-grid flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-[#10151C] border border-[#222C3A] rounded p-8">
          <div className="text-[11px] mono uppercase tracking-widest text-[#5B6879]">ChattamAI · KBR Compliance Engine</div>
          <h1 className="text-xl font-semibold text-white mt-2 mb-3">Sign in</h1>
          <div className="border-l-2 border-[#22D3EE] bg-[#22D3EE]/5 px-4 py-3 mb-6">
            <div className="text-[11px] mono text-[#9AA7B6] flex items-start gap-2">
              <Icon name="info" className="text-[#22D3EE] flex-shrink-0 mt-0.5" />
              API not configured — this build runs on demo data. Set VITE_API_URL to sign in for real.
            </div>
          </div>
          <button
            onClick={() => nav('/')}
            className="w-full accent-gradient px-6 py-3 rounded text-sm font-semibold text-black hover:brightness-110"
          >
            Continue to app
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
          toast('This server requires two-factor authentication — enrol under Settings → Security after you sign in.', 'info')
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
    <div className="min-h-screen blueprint-grid flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-[#10151C] border border-[#222C3A] rounded p-8">
        <div className="text-[11px] mono uppercase tracking-widest text-[#5B6879]">ChattamAI · KBR Compliance Engine</div>
        <h1 className="text-xl font-semibold text-white mt-2 mb-6 flex items-center gap-2">
          <Icon name={stage === 'totp' ? 'shield' : 'key'} className="text-[#22D3EE]" />
          {stage === 'totp' ? 'Two-factor authentication' : 'Sign in'}
        </h1>

        {stage === 'credentials' ? (
          <form onSubmit={submitCredentials} className="space-y-5">
            <Field label="Email" type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
            <Field label="Password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            <label className="flex items-center gap-2 text-xs mono text-[#9AA7B6] cursor-pointer select-none">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="accent-[#22D3EE]" />
              Remember me on this device
            </label>
            <button
              type="submit"
              disabled={busy}
              className={`w-full accent-gradient px-6 py-3 rounded text-sm font-semibold text-black hover:brightness-110 flex items-center justify-center gap-2 ${busy ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              {busy && <Icon name="loader" className="spin-1" />} Sign in
            </button>
          </form>
        ) : (
          <form onSubmit={submitCode} className="space-y-5">
            {setupRequired && (
              <div className="border-l-2 border-[#fbbf24] bg-[#fbbf24]/5 px-4 py-3">
                <div className="text-[11px] mono text-[#9AA7B6] flex items-start gap-2">
                  <Icon name="alert-triangle" className="text-[#fbbf24] flex-shrink-0 mt-0.5" />
                  This server requires two-factor authentication. Sign in, then complete enrolment under Settings → Security.
                </div>
              </div>
            )}
            {useRecovery ? (
              <Field
                label="Recovery code"
                type="text"
                required
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="10-character code"
                helper="Each recovery code works exactly once."
              />
            ) : (
              <div>
                <label className="block text-xs text-[#9AA7B6] mb-2">Authenticator code</label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={8}
                  required
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="w-full mono text-center text-2xl tracking-[0.5em] bg-[#1C2531] border border-[#222C3A] rounded px-3 py-2.5 text-white outline-none focus:border-[#22D3EE]/50 transition-colors"
                  placeholder="000000"
                />
                <div className="text-[10px] mono text-[#5B6879] mt-1.5">6-digit code from your authenticator app.</div>
              </div>
            )}
            <button
              type="submit"
              disabled={busy}
              className={`w-full accent-gradient px-6 py-3 rounded text-sm font-semibold text-black hover:brightness-110 flex items-center justify-center gap-2 ${busy ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              {busy && <Icon name="loader" className="spin-1" />} {useRecovery ? 'Use recovery code' : 'Verify'}
            </button>
            <button
              type="button"
              onClick={() => { setUseRecovery(!useRecovery); setCode('') }}
              className="w-full text-xs mono text-[#9AA7B6] hover:text-white transition-colors"
            >
              {useRecovery ? '← Use authenticator code instead' : 'Lost your device? Use a recovery code'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
