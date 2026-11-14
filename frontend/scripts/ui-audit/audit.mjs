// Usage: node audit.mjs <baseUrl> <outDir> [themes=dark,light]
import { chromium } from 'playwright'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs'

const [base, out, themesArg] = process.argv.slice(2)
const themes = (themesArg || 'default').split(',')
fs.mkdirSync(out, { recursive: true })

const ROUTES = ['/login', '/register', '/', '/new-check', '/workbench', '/analysis',
  '/results/demo', '/results/insufficient', '/kbr', '/reports', '/projects', '/activity', '/settings']
const VIEWPORTS = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } }

const browser = await chromium.launch()
const report = {}
for (const theme of themes) {
  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    const ctx = await browser.newContext({
      viewport: vp,
      colorScheme: theme === 'dark' ? 'dark' : theme === 'light' ? 'light' : 'no-preference',
    })
    if (theme === 'dark' || theme === 'light') {
      await ctx.addInitScript((t) => { try { localStorage.setItem('chattam.theme', t) } catch {} }, theme)
    }
    for (const route of ROUTES) {
      const page = await ctx.newPage()
      const errors = []
      page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)) })
      page.on('pageerror', (e) => errors.push('pageerror: ' + String(e).slice(0, 200)))
      await page.goto(base + route, { waitUntil: 'networkidle' })
      await page.waitForTimeout(500)
      const key = `${theme}|${vpName}|${route}`
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      const finalPath = new URL(page.url()).pathname
      const fingerprint = await page.evaluate(() => {
        const name = (el) => (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || el.title || '').replace(/\s+/g, ' ').trim().slice(0, 60)
        const pick = (sel) => [...document.querySelectorAll(sel)].map(name).filter(Boolean)
        return {
          h: pick('h1,h2,h3'),
          buttons: pick('button,[role=button]'),
          links: [...document.querySelectorAll('a[href]')].map((a) => name(a) + ' -> ' + a.getAttribute('href')).filter((s) => !s.startsWith(' ->')),
          inputs: [...document.querySelectorAll('input,select,textarea')].map((i) => `${i.type || i.tagName}:${i.placeholder || i.name || i.id || ''}`),
        }
      })
      let axeCounts = {}
      try {
        const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
        for (const v of res.violations) axeCounts[v.id] = (axeCounts[v.id] || 0) + v.nodes.length
      } catch (e) { axeCounts = { _axe_error: String(e).slice(0, 80) } }
      await page.screenshot({ path: `${out}/${key.replace(/[|/]/g, '_')}.png`, fullPage: true })
      report[key] = { finalPath, errors, overflow, axe: axeCounts, fingerprint }
      await page.close()
    }
    await ctx.close()
  }
}
await browser.close()
fs.writeFileSync(`${out}/report.json`, JSON.stringify(report, null, 2))
const rows = Object.entries(report)
const bad = rows.filter(([, r]) => r.errors.length || r.overflow > 0)
console.log(`routes audited: ${rows.length}; with console errors or overflow: ${bad.length}`)
for (const [k, r] of bad) console.log(' ', k, 'overflow=' + r.overflow, r.errors.slice(0, 2))
const axeTotal = rows.reduce((n, [, r]) => n + Object.values(r.axe).reduce((a, b) => a + (typeof b === 'number' ? b : 0), 0), 0)
console.log('total axe WCAG A/AA violation nodes:', axeTotal)
