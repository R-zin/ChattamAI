import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

// Keep the real demo-mode data layer, but let tests steer the config and the
// registration call.
const cfg = vi.hoisted(() => ({ fetchAuthConfig: vi.fn(), registerUser: vi.fn() }))
vi.mock('../data.js', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchAuthConfig: cfg.fetchAuthConfig, registerUser: cfg.registerUser }
})

import Register, { passwordChecks } from '../pages/Register.jsx'
import Login from '../pages/Login.jsx'

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<Register />} />
        <Route path="/login" element={<Login />} />
      </Routes>
    </MemoryRouter>
  )
}

const fill = (email, pw, confirm = pw) => {
  fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: email } })
  fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: pw } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: confirm } })
}
const submitBtn = () => screen.getByRole('button', { name: /create account/i })

beforeEach(() => {
  cfg.fetchAuthConfig.mockReset().mockResolvedValue({ registration_open: true })
  cfg.registerUser.mockReset().mockImplementation(async ({ email }) => ({ email: email.toLowerCase() }))
})

describe('passwordChecks', () => {
  it('requires length, a letter and a digit', () => {
    const ok = (pw) => passwordChecks(pw).every((c) => c.ok)
    expect(ok('Abcdef12')).toBe(true)
    expect(ok('short1')).toBe(false)
    expect(ok('lettersonly')).toBe(false)
    expect(ok('12345678')).toBe(false)
    expect(ok('a1' + 'x'.repeat(80))).toBe(false) // > 72 bytes
  })
})

describe('Register page', () => {
  it('renders the form with submit disabled until valid', () => {
    renderRegister()
    expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument()
    expect(submitBtn()).toBeDisabled()
  })

  it('shows live password requirements', () => {
    renderRegister()
    const li = (re) => screen.getByText(re).closest('li')
    expect(li(/at least 8/i)).toHaveAttribute('data-ok', 'false')
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'Abcdef12' } })
    expect(li(/at least 8/i)).toHaveAttribute('data-ok', 'true')
    expect(li(/a number/i)).toHaveAttribute('data-ok', 'true')
  })

  it('keeps submit disabled and explains a password mismatch', () => {
    renderRegister()
    fill('a@example.com', 'Abcdef12', 'Abcdef13')
    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
    expect(submitBtn()).toBeDisabled()
  })

  it('rejects a malformed email', () => {
    renderRegister()
    fill('not-an-email', 'Abcdef12')
    expect(screen.getByText(/valid email/i)).toBeInTheDocument()
    expect(submitBtn()).toBeDisabled()
  })

  it('registers, then sends the user to sign in with the email prefilled', async () => {
    renderRegister()
    fill('New.User@Example.com', 'Abcdef12')
    expect(submitBtn()).toBeEnabled()
    fireEvent.click(submitBtn())
    await waitFor(() => expect(cfg.registerUser).toHaveBeenCalledTimes(1))
    expect(cfg.registerUser).toHaveBeenCalledWith({ email: 'New.User@Example.com', password: 'Abcdef12' })
    // Landed on /login with the confirmation and the (normalised) email filled in.
    expect(await screen.findByText(/account created for new\.user@example\.com/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^email$/i)).toHaveValue('new.user@example.com')
  })

  it('shows the server error and stays on the page', async () => {
    cfg.registerUser.mockRejectedValue(new Error('An account with this email already exists. Try signing in.'))
    renderRegister()
    fill('a@example.com', 'Abcdef12')
    fireEvent.click(submitBtn())
    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i)
    expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument()
  })

  it('does not submit twice while a request is in flight', async () => {
    let release
    cfg.registerUser.mockImplementation(() => new Promise((r) => { release = r }))
    renderRegister()
    fill('a@example.com', 'Abcdef12')
    fireEvent.click(submitBtn())
    await waitFor(() => expect(cfg.registerUser).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('button', { name: /creating account/i })).toBeDisabled()
    release({ email: 'a@example.com' })
  })

  it('explains invitation-only mode and blocks the form', async () => {
    cfg.fetchAuthConfig.mockResolvedValue({ registration_open: false })
    renderRegister()
    expect(await screen.findByText(/by invitation only/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^email$/i)).toBeDisabled()
    expect(submitBtn()).toBeDisabled()
  })

  it('still shows the form when the config cannot be read', async () => {
    cfg.fetchAuthConfig.mockResolvedValue(null)
    renderRegister()
    await waitFor(() => expect(cfg.fetchAuthConfig).toHaveBeenCalled())
    expect(screen.getByLabelText(/^email$/i)).toBeEnabled()
    expect(screen.queryByText(/by invitation only/i)).not.toBeInTheDocument()
  })
})

describe('Login <-> Register link (demo mode)', () => {
  const renderLogin = () =>
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Routes>
      </MemoryRouter>
    )

  it('offers "Create an account" and navigates to the form', async () => {
    renderLogin()
    fireEvent.click(await screen.findByRole('link', { name: /create an account/i }))
    expect(await screen.findByRole('heading', { name: /create account/i })).toBeInTheDocument()
  })

  it('hides the link when registration is closed', async () => {
    cfg.fetchAuthConfig.mockResolvedValue({ registration_open: false })
    renderLogin()
    await waitFor(() => expect(cfg.fetchAuthConfig).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: /create an account/i })).not.toBeInTheDocument()
    )
  })
})
