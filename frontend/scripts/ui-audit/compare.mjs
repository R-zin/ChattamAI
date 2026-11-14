// node compare.mjs <baseline report.json> <after report.json> [theme]
import fs from 'node:fs'
const [basePath, afterPath, theme = 'light'] = process.argv.slice(2)
const base = JSON.parse(fs.readFileSync(basePath))
const after = JSON.parse(fs.readFileSync(afterPath))
const norm = (s) => s.toLowerCase().replace(/[^a-z0-9→@./ -]+/g, ' ').replace(/\s+/g, ' ').trim()
let lost = 0, gained = 0, routes = 0
for (const [k, b] of Object.entries(base)) {
  const [, vp, route] = k.split('|')
  const a = after[`${theme}|${vp}|${route}`]
  if (!a) { console.log('MISSING route in after:', k); lost++; continue }
  routes++
  for (const kind of ['h', 'buttons', 'links', 'inputs']) {
    const bs = new Set(b.fingerprint[kind].map(norm)), as = new Set(a.fingerprint[kind].map(norm))
    const missing = [...bs].filter((x) => x && !as.has(x))
    const added = [...as].filter((x) => x && !bs.has(x))
    if (missing.length) { lost += missing.length; console.log(`LOST   ${vp} ${route} [${kind}]:`, missing.slice(0, 6)) }
    gained += added.length
    if (added.length && process.env.SHOW_ADDED) console.log(`added  ${vp} ${route} [${kind}]:`, added.slice(0, 6))
  }
}
console.log(`\ncompared ${routes} route/viewport pairs: controls lost=${lost}, added=${gained}`)
