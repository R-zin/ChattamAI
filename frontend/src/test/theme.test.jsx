import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import ThemeToggle from '../components/ThemeToggle.jsx'
import { THEME_KEY, applyTheme, getStoredTheme, resolveTheme, setTheme } from '../theme.js'

function mockSystem(dark) {
  const listeners = new Set()
  window.matchMedia = vi.fn().mockImplementation(() => ({
    matches: dark,
    addEventListener: (_, fn) => listeners.add(fn),
    removeEventListener: (_, fn) => listeners.delete(fn),
  }))
  return listeners
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})
afterEach(() => vi.restoreAllMocks())

describe('theme resolution', () => {
  it('defaults to light when nothing is saved and the system is light', () => {
    mockSystem(false)
    expect(resolveTheme()).toBe('light')
  })

  it('follows a dark system preference on first visit', () => {
    mockSystem(true)
    expect(resolveTheme()).toBe('dark')
  })

  it('a saved choice beats the system preference', () => {
    mockSystem(true)
    localStorage.setItem(THEME_KEY, 'light')
    expect(resolveTheme()).toBe('light')
  })

  it('ignores a corrupted saved value', () => {
    mockSystem(false)
    localStorage.setItem(THEME_KEY, 'purple')
    expect(getStoredTheme()).toBeNull()
    expect(resolveTheme()).toBe('light')
  })

  it('applyTheme sets data-theme and falls back to light for junk', () => {
    expect(applyTheme('dark')).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(applyTheme('nope')).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('setTheme persists the choice', () => {
    setTheme('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('still applies the theme when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => setTheme('dark')).not.toThrow()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})

describe('ThemeToggle', () => {
  it('rail variant toggles light <-> dark, labels the action and persists', () => {
    mockSystem(false)
    render(<ThemeToggle />)
    const btn = screen.getByRole('button', { name: /switch to dark theme/i })
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    fireEvent.click(btn)
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(screen.getByRole('button', { name: /switch to light theme/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /switch to light theme/i }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
  })

  it('icon variant shows the theme it will switch to', () => {
    mockSystem(false)
    render(<ThemeToggle variant="icon" />)
    expect(screen.getByRole('button', { name: /switch to dark theme/i })).toHaveTextContent(/dark/i)
  })

  it('two toggles stay in sync', () => {
    mockSystem(false)
    render(
      <>
        <ThemeToggle />
        <ThemeToggle variant="icon" />
      </>
    )
    fireEvent.click(screen.getAllByRole('button', { name: /switch to dark theme/i })[0])
    expect(screen.getAllByRole('button', { name: /switch to light theme/i })).toHaveLength(2)
  })

  it('follows the OS only until the user chooses', () => {
    const listeners = mockSystem(false)
    render(<ThemeToggle />)
    window.matchMedia = vi.fn().mockImplementation(() => ({ matches: true }))
    act(() => listeners.forEach((fn) => fn()))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')

    fireEvent.click(screen.getByRole('button', { name: /switch to light theme/i }))
    window.matchMedia = vi.fn().mockImplementation(() => ({ matches: true }))
    act(() => listeners.forEach((fn) => fn()))
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })
})
