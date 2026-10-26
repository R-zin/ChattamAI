import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from '../components/Toast.jsx'
import {
  isAuthed,
  login,
  setToken,
  totpVerify,
  totpRecover,
  getGoogleAuthUrl,
  googleCallbackLogin,
} from '../data.js'

function Field({ label, helper, ...props }) {
  return (
    <div>
      <label className="block text-[10px] mono uppercase text-[#737373] mb-1.5 font-semibold">
        {label}
      </label>
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

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthed()) nav('/', { replace: true })
  }, [nav])

  // Handle incoming OAuth callback redirect (?code=...&state=...)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oauthCode = params.get('code')
    const oauthState = params.get('state')

    if (oauthCode && oauthState) {
      // Clear query params from address bar immediately to prevent replay/leakage
      window.history.replaceState({}, document.title, window.location.pathname)

      setBusy(true)
      setError(null)
      toast('Authenticating with Google OAuth 2.0…', 'info')

      googleCallbackLogin({
        code: oauthCode,
        state: oauthState,
        redirectUri: `${window.location.origin}/login`,
      })
        .then((res) => {
          if (res.access_token) {
            toast('Google authentication successful.', 'ok')
            finish(res.access_token)
          } else if (res.otp_required) {
            setOtpToken(res.otp_token)
            setSetupRequired(!!res.otp_setup_required)
            setStage('totp')
            toast('Two-factor verification required for this account.', 'info')
          }
        })
        .catch((err) => {
          const msg = err.message || 'Google authentication failed'
          setError(msg)
          toast(msg, 'danger')
        })
        .finally(() => {
          setBusy(false)
        })
    }
  }, [])

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

  const handleGoogleSignIn = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      toast('Initializing Google OAuth 2.0 flow…', 'info')
      const res = await getGoogleAuthUrl({
        redirectUri: `${window.location.origin}/login`,
      })
      if (res.url) {
        window.location.href = res.url
      }
    } catch (err) {
      const msg = err.message || 'Could not start Google sign in'
      setError(msg)
      toast(msg, 'danger')
      setBusy(false)
    }
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
          toast(
            'Two-factor authentication is required. Enroll after sign in.',
            'info'
          )
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
          <div className="text-[10px] mono uppercase tracking-widest text-[#737373] mb-1">
            CHATTAM.AI
          </div>
          <h1 className="text-xl font-bold text-white uppercase font-sans">
            {stage === 'totp' ? 'Two-Factor Verification' : 'Sign In'}
          </h1>
          <p className="text-xs text-[#a3a3a3] mt-1 mono">
            {stage === 'totp'
              ? 'Enter authentication code'
              : 'Kerala Building Rules Compliance Platform'}
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
              onChange={(e) => {
                setEmail(e.target.value)
                setError(null)
              }}
              placeholder="admin@chattamai.com"
            />
            <Field
              label="Password"
              type="password"
              required
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                setError(null)
              }}
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
              {busy ? 'AUTHENTICATING…' : 'SIGN IN WITH PASSWORD →'}
            </button>

            <div className="flex items-center gap-3 my-4">
              <div className="h-px bg-[#262626] flex-1" />
              <span className="text-[10px] mono text-[#737373] uppercase tracking-wider">
                OR
              </span>
              <div className="h-px bg-[#262626] flex-1" />
            </div>

            {/* Google OAuth Sign-in Button */}
            <button
              type="button"
              disabled={busy}
              onClick={handleGoogleSignIn}
              className="w-full bg-[#181818] text-white font-mono font-bold text-xs py-3 border border-[#333333] hover:border-white hover:bg-[#222222] transition-colors cursor-pointer flex items-center justify-center gap-2.5 disabled:opacity-40 select-none focus-visible:ring-1 focus-visible:ring-white focus-visible:outline-none"
            >
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>SIGN IN WITH GOOGLE</span>
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
                onChange={(e) => {
                  setCode(e.target.value)
                  setError(null)
                }}
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
                  onChange={(e) => {
                    setCode(e.target.value)
                    setError(null)
                  }}
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
              {busy
                ? 'VERIFYING…'
                : useRecovery
                  ? 'USE RECOVERY CODE →'
                  : 'VERIFY CODE →'}
            </button>
            <button
              type="button"
              onClick={() => {
                setUseRecovery(!useRecovery)
                setCode('')
                setError(null)
              }}
              className="w-full text-xs mono text-[#737373] hover:text-white transition-colors"
            >
              {useRecovery
                ? '← Use standard authenticator'
                : 'Lost device? Use recovery code'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
