import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from '../components/Toast.jsx'
import {
  isAuthed,
  login,
  setToken,
  totpVerify,
  totpRecover,
} from '../data.js'

function Field({ label, helper, ...props }) {
  return (
    <div>
      <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">{label}</label>
      <input
        className="w-full mono text-xs bg-[#0e0e0e] border border-[#333333] px-3 py-2.5 text-white outline-none focus:border-white transition-colors"
        {...props}
      />
      {helper && <p className="text-[10px] mono text-[#737373] mt-1">{helper}</p>}
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
  const [error, setError] = useState(null)

  useEffect(() => {
    if (isAuthed()) nav('/', { replace: true })
  }, [nav])

  const finish = (token) => {
    setToken(token, remember)
    nav('/')
  }

  const fillDemoCredentials = () => {
    setEmail('admin@chattamai.com')
    setPassword('ChattamAI@2026')
    setError(null)
  }

  const continueAsGuest = () => {
    finish('guest-auditor-session')
  }

  const submitCredentials = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
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
      const msg = err.message || 'Invalid email or password'
      setError(msg)
      toast(msg, 'danger')
    } finally {
      setBusy(false)
    }
  }

  const submitCode = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const res = useRecovery
        ? await totpRecover({ otpToken, recoveryCode: code })
        : await totpVerify({ otpToken, code })
      finish(res.access_token)
    } catch (err) {
      const msg = err.message || 'Verification failed'
      setError(msg)
      toast(msg, 'danger')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen blueprint-grid flex items-center justify-center p-6 bg-[#0a0a0a]">
      <div className="w-full max-w-md bg-[#121212] border border-[#262626] p-8 space-y-6 shadow-2xl">
        <div className="border-b border-[#262626] pb-4">
          <div className="text-[10px] mono uppercase tracking-widest text-[#737373] mb-1">CHATTAM.AI</div>
          <h1 className="text-xl font-bold text-white uppercase font-sans">
            {stage === 'totp' ? 'Two-Factor Verification' : 'Sign In'}
          </h1>
          <p className="text-xs text-[#a3a3a3] mt-1 mono">
            {stage === 'totp' ? 'Enter authentication code' : 'Kerala Building Rules Compliance Platform'}
          </p>
        </div>

        {error && (
          <div className="border border-white bg-[#1a0a0a] p-3 text-xs mono text-white flex items-center gap-2.5">
            <span className="w-4 h-4 flex-shrink-0 border border-white flex items-center justify-center font-bold bg-white text-black text-[10px]">
              !
            </span>
            <span className="flex-1">{error}</span>
          </div>
        )}

        {stage === 'credentials' ? (
          <form onSubmit={submitCredentials} className="space-y-4">
            <Field
              label="Email"
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => { setEmail(e.target.value); setError(null) }}
              placeholder="admin@chattamai.com"
            />
            <Field
              label="Password"
              type="password"
              required
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(null) }}
              placeholder="••••••••••••"
            />

            <div className="flex items-center justify-between text-xs mono">
              <label className="flex items-center gap-2 text-[#a3a3a3] cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="accent-white"
                />
                Remember me
              </label>
              <button
                type="button"
                onClick={fillDemoCredentials}
                className="text-[#a3a3a3] hover:text-white underline cursor-pointer transition-colors"
              >
                Fill Demo Credentials
              </button>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="w-full bg-white text-black font-mono font-bold text-xs py-3 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer disabled:opacity-40"
            >
              {busy ? 'AUTHENTICATING…' : 'SIGN IN →'}
            </button>

            <div className="pt-2 border-t border-[#262626]">
              <button
                type="button"
                onClick={continueAsGuest}
                className="w-full text-xs mono text-[#737373] hover:text-white py-2.5 border border-[#262626] hover:border-[#404040] bg-[#0e0e0e] transition-colors cursor-pointer text-center block"
              >
                CONTINUE AS GUEST / DEMO →
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={submitCode} className="space-y-4">
            {setupRequired && (
              <div className="border border-white bg-[#0e0e0e] p-3 text-xs mono text-white">
                Two-factor authentication is required. Enter code to proceed.
              </div>
            )}
            {useRecovery ? (
              <Field
                label="Recovery Code"
                type="text"
                required
                autoFocus
                value={code}
                onChange={(e) => { setCode(e.target.value); setError(null) }}
                placeholder="10-character code"
                helper="Each recovery code functions once."
              />
            ) : (
              <div>
                <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">
                  Authenticator Code
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={8}
                  required
                  autoFocus
                  value={code}
                  onChange={(e) => { setCode(e.target.value); setError(null) }}
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
              onClick={() => { setUseRecovery(!useRecovery); setCode(''); setError(null) }}
              className="w-full text-xs mono text-[#737373] hover:text-white transition-colors"
            >
              {useRecovery ? '← Use standard authenticator' : 'Lost device? Use recovery code'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
