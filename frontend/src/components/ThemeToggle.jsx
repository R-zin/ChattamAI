import React from 'react'
import { useTheme } from '../theme.js'

// Accessible light/dark switch. `variant="rail"` is the full-width sidebar row;
// `variant="icon"` is the compact mobile-bar button.
export default function ThemeToggle({ variant = 'rail' }) {
  const { isDark, toggle } = useTheme()
  const next = isDark ? 'light' : 'dark'
  const label = `Switch to ${next} theme`

  if (variant === 'icon') {
    return (
      <button
        type="button"
        onClick={toggle}
        aria-label={label}
        title={label}
        className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-2 hover:text-ink border border-line hover:border-ink"
      >
        {isDark ? 'Light' : 'Dark'}
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-2 hover:text-ink hover:bg-surface-2 transition-colors"
    >
      <span>Theme</span>
      <span aria-hidden="true" className="flex items-center gap-1.5 normal-case tracking-normal font-medium">
        <span className={!isDark ? 'text-ink font-semibold' : 'text-ink-3'}>Light</span>
        <span className="text-ink-3">/</span>
        <span className={isDark ? 'text-ink font-semibold' : 'text-ink-3'}>Dark</span>
      </span>
    </button>
  )
}
