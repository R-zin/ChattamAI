// Light/dark theme. Default: the saved choice, else the system preference,
// else light. The inline script in index.html applies it before first paint;
// this module keeps it in sync afterwards and persists the user's choice.
import { useCallback, useEffect, useState } from 'react'

export const THEME_KEY = 'chattam.theme'
const VALID = ['light', 'dark']

export function systemTheme() {
  try {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export function getStoredTheme() {
  try {
    const t = localStorage.getItem(THEME_KEY)
    return VALID.includes(t) ? t : null
  } catch {
    return null
  }
}

export function resolveTheme() {
  return getStoredTheme() || systemTheme()
}

export function applyTheme(theme) {
  const t = VALID.includes(theme) ? theme : 'light'
  document.documentElement.setAttribute('data-theme', t)
  return t
}

export function setTheme(theme) {
  const t = applyTheme(theme)
  try {
    localStorage.setItem(THEME_KEY, t)
  } catch {
    // Storage can be unavailable (private mode); the choice still applies this session.
  }
  window.dispatchEvent(new CustomEvent('chattam:theme', { detail: t }))
  return t
}

export function useTheme() {
  const [theme, set] = useState(() => {
    const current = document.documentElement.getAttribute('data-theme')
    return VALID.includes(current) ? current : resolveTheme()
  })

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    const onChange = (e) => set(e.detail)
    window.addEventListener('chattam:theme', onChange)
    return () => window.removeEventListener('chattam:theme', onChange)
  }, [])

  // Follow the OS only while the user has not chosen explicitly.
  useEffect(() => {
    let mq
    try {
      mq = window.matchMedia('(prefers-color-scheme: dark)')
    } catch {
      return undefined
    }
    if (!mq || !mq.addEventListener) return undefined
    const onSystem = () => {
      if (!getStoredTheme()) set(applyTheme(systemTheme()))
    }
    mq.addEventListener('change', onSystem)
    return () => mq.removeEventListener('change', onSystem)
  }, [])

  const toggle = useCallback(() => {
    set((prev) => setTheme(prev === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggle, isDark: theme === 'dark' }
}
