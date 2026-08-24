import { describe, it, expect, beforeEach } from 'vitest'
import { act } from 'react'

// Smoke test: importing main.jsx mounts the real app (the module calls
// ReactDOM.createRoot(...).render(...) on import). We provide the #root node
// it expects, then assert the shell rendered something meaningful.
describe('App shell', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>'
  })

  it('mounts the app without crashing', async () => {
    await import('../main.jsx')
    // React 18 createRoot renders asynchronously; flush pending work.
    await act(async () => {})
    const root = document.getElementById('root')
    expect(root).toBeTruthy()
    expect(root.innerHTML.length).toBeGreaterThan(0)
  })
})
