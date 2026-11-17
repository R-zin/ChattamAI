import { describe, it, expect, vi } from 'vitest'
import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Sign-in page against a backend: no demo affordances, real Google call.
vi.mock('../data.js', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchAuthConfig: vi.fn().mockResolvedValue({ registration_open: true }),
    getGoogleAuthUrl: vi.fn().mockRejectedValue(new Error('google is not configured')),
  }
})

import Login from '../pages/Login.jsx'

describe('Login', () => {
  it('hides demo credentials and guest access, keeps sign up', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )
    expect(screen.getByRole('button', { name: /sign in with password/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /fill demo credentials/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /continue as guest/i })).not.toBeInTheDocument()
    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /create an account/i })).toBeInTheDocument()
  })

  it('Google sign-in reaches the backend call and reports its error', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )
    fireEvent.click(screen.getByRole('button', { name: /sign in with google/i }))
    expect(await screen.findByText('google is not configured')).toBeInTheDocument()
  })
})
