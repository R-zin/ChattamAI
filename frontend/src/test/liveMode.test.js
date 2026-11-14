// Live (non-demo) behaviour of the data layer: same-origin API calls and no
// silent fallback to mock data. The suite default is demo mode (see
// vitest.config.js), so each test opts out explicitly and reloads the module.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

async function loadData({ mocks = '', apiUrl = '' } = {}) {
  vi.resetModules()
  vi.stubEnv('VITE_USE_MOCKS', mocks)
  vi.stubEnv('VITE_API_URL', apiUrl)
  return import('../data.js')
}

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

describe('API availability', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('treats an empty VITE_API_URL as same-origin, not as "no API"', async () => {
    const data = await loadData()
    expect(data.USE_MOCKS).toBe(false)
    expect(data.apiAvailable()).toBe(true)
  })

  it('uses mocks only when VITE_USE_MOCKS is explicitly truthy', async () => {
    for (const v of ['true', '1', 'yes', 'on', 'TRUE']) {
      const data = await loadData({ mocks: v })
      expect(data.apiAvailable(), v).toBe(false)
    }
    for (const v of ['', 'false', '0', 'no']) {
      const data = await loadData({ mocks: v })
      expect(data.apiAvailable(), v).toBe(true)
    }
  })

  it('refuses an http API URL from an https page (mixed content)', async () => {
    const data = await loadData({ apiUrl: 'http://api.example.com' })
    const original = window.location
    Object.defineProperty(window, 'location', {
      value: { ...original, protocol: 'https:' },
      configurable: true,
    })
    try {
      expect(data.apiAvailable()).toBe(false)
    } finally {
      Object.defineProperty(window, 'location', { value: original, configurable: true })
    }
  })
})

describe('live mode requests', () => {
  let fetchMock
  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('calls relative same-origin URLs when VITE_API_URL is empty', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ status: 'ok' }))
    await data.fetchHealth()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/health')
  })

  it('prefixes VITE_API_URL (trailing slash trimmed) when set', async () => {
    const data = await loadData({ apiUrl: 'https://api.example.com/' })
    fetchMock.mockReturnValue(json({ status: 'ok' }))
    await data.fetchHealth()
    expect(fetchMock.mock.calls[0][0]).toBe('https://api.example.com/api/health')
  })

  it('does not call the network in demo mode', async () => {
    const data = await loadData({ mocks: 'true' })
    const health = await data.fetchHealth()
    expect(health.status).toBe('ok')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetchReports rejects on failure instead of returning demo reports', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ detail: 'boom' }, 500))
    await expect(data.fetchReports()).rejects.toThrow('boom')
  })

  it('fetchReports returns an empty list for an empty archive', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json([]))
    expect(await data.fetchReports()).toEqual([])
  })

  it('fetchKbrDocuments rejects on failure instead of returning demo documents', async () => {
    const data = await loadData()
    fetchMock.mockRejectedValue(new Error('Failed to fetch'))
    await expect(data.fetchKbrDocuments()).rejects.toThrow('unreachable')
  })

  it('fetchKbrDocuments returns an empty list for an empty corpus', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json([]))
    expect(await data.fetchKbrDocuments()).toEqual([])
  })

  it('checkPdfV2 never substitutes a mock assessment for a failed audit', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ detail: 'Embeddings are not configured.' }, 503))
    const file = new File(['%PDF'], 'plan.pdf', { type: 'application/pdf' })
    await expect(data.checkPdfV2(file)).rejects.toThrow('Embeddings are not configured.')
  })
})
