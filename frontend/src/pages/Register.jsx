import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from '../components/Toast.jsx'
import Field from '../components/Field.jsx'
import { fetchAuthConfig, isAuthed, registerUser } from '../data.js'

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

// Mirrors the server's rules (app/schemas.py RegisterRequest) so users get
// instant feedback; the server remains the authority.
export function passwordChecks(password) {
  return [
    { id: 'len', label: 'At least 8 characters', ok: password.length >= 8 },
    { id: 'letter', label: 'A letter', ok: /[A-Za-z]/.test(password) },
    { id: 'digit', label: 'A number', ok: /\d/.test(password) },
    {
      id: 'max',
      label: 'No more than 72 bytes',
      ok: new TextEncoder().encode(password).length <= 72,
    },
  ]
}

export default function Register() {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // null = not known yet / unreachable: show the form and let the server decide.
  const [registrationOpen, setRegistrationOpen] = useState(null)

  useEffect(() => {
    if (isAuthed()) nav('/', { replace: true })
  }, [nav])

  useEffect(() => {
    let active = true
    fetchAuthConfig().then((cfg) => {
      if (active && cfg) setRegistrationOpen(!!cfg.registration_open)
    })
    return () => {
      active = false
    }
  }, [])

  const checks = useMemo(() => passwordChecks(password), [password])
  const emailOk = EMAIL_RE.test(email.trim())
  const passwordOk = checks.every((c) => c.ok)
  const matches = password.length > 0 && password === confirm
  const canSubmit = emailOk && passwordOk && matches && !busy && registrationOpen !== false

  const submit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    try {
      const user = await registerUser({ email: email.trim(), password })
      toast('Account created. Sign in to continue.', 'ok')
      nav('/login', { replace: true, state: { registeredEmail: user?.email || email.trim() } })
    } catch (err) {
      const msg = err.message || 'Registration failed'
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
          <h1 className="text-xl font-bold text-white uppercase font-sans">Create Account</h1>
          <p className="text-xs text-[#a3a3a3] mt-1 mono">
            Kerala Building Rules Compliance Platform
          </p>
        </div>

        {registrationOpen === false && (
          <div
            role="status"
            className="border border-[#404040] bg-[#0e0e0e] p-3 text-xs mono text-[#d4d4d4]"
          >
            Registration is by invitation only. Contact your administrator for an account.
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="border border-white bg-[#1a0a0a] p-3 text-xs mono text-white flex items-center gap-2.5"
          >
            <span className="w-4 h-4 flex-shrink-0 border border-white flex items-center justify-center font-bold bg-white text-black text-[10px]">
              !
            </span>
            <span className="flex-1">{error}</span>
          </div>
        )}

        <form onSubmit={submit} className="space-y-4" noValidate>
          <Field
            label="Email"
            type="email"
            autoComplete="email"
            autoFocus
            required
            disabled={registrationOpen === false}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value)
              setError(null)
            }}
            placeholder="you@example.com"
            helper={email && !emailOk ? 'Enter a valid email address.' : undefined}
          />
          <Field
            label="Password"
            type="password"
            autoComplete="new-password"
            required
            disabled={registrationOpen === false}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              setError(null)
            }}
            placeholder="••••••••••••"
          />
          <ul className="space-y-1 text-[10px] mono" aria-label="Password requirements">
            {checks.map((c) => (
              <li
                key={c.id}
                data-ok={c.ok}
                className={c.ok ? 'text-white' : 'text-[#737373]'}
              >
                {c.ok ? '✓' : '○'} {c.label}
              </li>
            ))}
          </ul>
          <Field
            label="Confirm Password"
            type="password"
            autoComplete="new-password"
            required
            disabled={registrationOpen === false}
            value={confirm}
            onChange={(e) => {
              setConfirm(e.target.value)
              setError(null)
            }}
            placeholder="••••••••••••"
            helper={confirm && !matches ? 'Passwords do not match.' : undefined}
          />

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full bg-white text-black font-mono font-bold text-xs py-3 border border-white hover:bg-[#e5e5e5] transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy ? 'CREATING ACCOUNT…' : 'CREATE ACCOUNT →'}
          </button>
        </form>

        <div className="pt-2 border-t border-[#262626] text-center text-xs mono text-[#737373]">
          Already have an account?{' '}
          <Link to="/login" className="text-white underline hover:text-[#e5e5e5]">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  )
}
