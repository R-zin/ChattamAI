// Guards on the design system itself: no hard-coded colours, and every token
// pair keeps WCAG AA contrast in both themes.
import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const SRC = path.resolve(__dirname, '..')
const css = fs.readFileSync(path.join(SRC, 'index.css'), 'utf8')

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    return e.isDirectory() ? walk(p) : [p]
  })
}

describe('no hard-coded colours in components', () => {
  const files = [...walk(path.join(SRC, 'pages')), ...walk(path.join(SRC, 'components'))].filter((f) => f.endsWith('.jsx'))

  it('finds the source files', () => {
    expect(files.length).toBeGreaterThan(15)
  })

  it('uses design tokens, not arbitrary hex values, in class names', () => {
    const bad = []
    for (const f of files) {
      const text = fs.readFileSync(f, 'utf8')
      for (const m of text.matchAll(/\b(?:bg|text|border|divide|ring|from|to|via|fill|stroke|outline)-\[#[0-9a-fA-F]{3,8}\]/g)) {
        bad.push(`${path.relative(SRC, f)}: ${m[0]}`)
      }
    }
    expect(bad).toEqual([])
  })

  it('does not use raw white/black/palette colour utilities (they ignore the theme)', () => {
    const bad = []
    for (const f of files) {
      const text = fs.readFileSync(f, 'utf8')
      for (const m of text.matchAll(/\b(?:bg|text|border|ring|divide)-(?:white|black|(?:neutral|gray|zinc|slate|stone|red|green|amber|yellow|blue|emerald|rose|orange|sky|indigo|violet|purple)-\d{2,3})\b/g)) {
        bad.push(`${path.relative(SRC, f)}: ${m[0]}`)
      }
    }
    expect(bad).toEqual([])
  })
})

// ---- contrast -------------------------------------------------------------
function block(selectorRe) {
  const m = css.match(selectorRe)
  if (!m) throw new Error(`block not found: ${selectorRe}`)
  return m[1]
}
function tokens(body) {
  const t = {}
  for (const m of body.matchAll(/--c-([a-z0-9-]+):\s*(\d+)\s+(\d+)\s+(\d+)\s*;/g)) {
    t[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])]
  }
  return t
}
const THEMES = {
  light: tokens(block(/:root,\s*\[data-theme='light'\]\s*\{([^}]*)\}/)),
  dark: tokens(block(/\[data-theme='dark'\]\s*\{([^}]*)\}/)),
}

const lin = (c) => {
  const s = c / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const blend = (fg, bg, alpha) => fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha)))

describe.each(Object.keys(THEMES))('%s theme tokens', (name) => {
  const t = THEMES[name]

  it('defines every token', () => {
    for (const k of ['bg', 'surface', 'surface-2', 'surface-3', 'inset', 'line', 'line-strong', 'ink', 'ink-2', 'ink-3', 'accent', 'accent-strong', 'on-accent', 'ok', 'warn', 'danger', 'info']) {
      expect(t[k], k).toBeDefined()
    }
  })

  const surfaces = ['bg', 'surface', 'surface-2', 'surface-3', 'inset']
  it.each(surfaces)('ink / ink-2 / ink-3 text reach 4.5:1 on %s', (s) => {
    for (const ink of ['ink', 'ink-2', 'ink-3']) {
      expect(ratio(t[ink], t[s]), `${ink} on ${s}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it.each(['ok', 'warn', 'danger', 'info'])('status colour %s reaches 4.5:1 on surfaces and on its own 10% tint', (c) => {
    for (const s of ['bg', 'surface', 'surface-2', 'surface-3']) {
      expect(ratio(t[c], t[s]), `${c} on ${s}`).toBeGreaterThanOrEqual(4.5)
    }
    for (const s of ['bg', 'surface', 'surface-2']) {
      expect(ratio(t[c], blend(t[c], t[s], 0.1)), `${c} on ${c}/10 over ${s}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('accent links/text reach 4.5:1 on the page surfaces', () => {
    for (const s of ['bg', 'surface', 'surface-2']) {
      expect(ratio(t.accent, t[s]), `accent on ${s}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('primary buttons (on-accent on accent and accent-strong) reach 4.5:1', () => {
    expect(ratio(t['on-accent'], t.accent)).toBeGreaterThanOrEqual(4.5)
    expect(ratio(t['on-accent'], t['accent-strong'])).toBeGreaterThanOrEqual(4.5)
  })

  it('form-control borders (line-strong) reach 3:1 against surfaces (WCAG 1.4.11)', () => {
    for (const s of ['surface', 'bg']) {
      expect(ratio(t['line-strong'], t[s]), `line-strong on ${s}`).toBeGreaterThanOrEqual(3)
    }
  })
})

describe('the two themes are distinct', () => {
  it('swaps page and ink colours', () => {
    expect(lum(THEMES.light.bg)).toBeGreaterThan(0.8)
    expect(lum(THEMES.dark.bg)).toBeLessThan(0.05)
    expect(lum(THEMES.light.ink)).toBeLessThan(0.05)
    expect(lum(THEMES.dark.ink)).toBeGreaterThan(0.8)
  })
})
