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

describe('registration and sign-in data layer (live mode)', () => {
  let fetchMock
  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('registerUser POSTs the JSON body to /auth/register', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ email: 'a@example.com' }, 201))
    const user = await data.registerUser({ email: 'a@example.com', password: 'Abcdef12' })
    expect(user.email).toBe('a@example.com')
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/auth/register')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ email: 'a@example.com', password: 'Abcdef12' })
  })

  it.each([
    [403, { detail: 'Registration requires a valid X-Admin-Key header' }, /by invitation only/i],
    [409, { detail: 'Email already registered' }, /already exists/i],
    [429, { detail: 'Too many requests.' }, /too many attempts/i],
    [
      422,
      { detail: [{ msg: 'Value error, Password must contain at least one letter and one digit' }] },
      /^Password must contain at least one letter and one digit$/,
    ],
  ])('registerUser maps HTTP %i to a readable message', async (status, body, expected) => {
    const data = await loadData()
    fetchMock.mockReturnValue(json(body, status))
    await expect(data.registerUser({ email: 'a@example.com', password: 'Abcdef12' })).rejects.toThrow(expected)
  })

  it('registerUser reports an unreachable backend', async () => {
    const data = await loadData()
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(data.registerUser({ email: 'a@example.com', password: 'Abcdef12' })).rejects.toThrow(
      /unreachable/i
    )
  })

  it('registerUser only simulates success in demo mode (no network)', async () => {
    const data = await loadData({ mocks: 'true' })
    const user = await data.registerUser({ email: ' A@Example.com ', password: 'x' })
    expect(user.email).toBe('a@example.com')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('login never fakes a session when the backend is unreachable', async () => {
    const data = await loadData()
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(data.login({ email: 'a@example.com', password: 'Abcdef12' })).rejects.toThrow(/unreachable/i)
  })

  it('login passes bad-credential errors through', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ detail: 'Incorrect email or password' }, 401))
    await expect(data.login({ email: 'a@example.com', password: 'nope' })).rejects.toThrow(
      'Incorrect email or password'
    )
  })

  it('fetchAuthConfig returns the flags, or null when unknown', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ registration_open: false, totp_required: false, google_enabled: true }))
    expect((await data.fetchAuthConfig()).registration_open).toBe(false)
    expect(fetchMock.mock.calls[0][0]).toBe('/auth/config')
    fetchMock.mockReturnValue(json({ detail: 'Not found' }, 404))
    expect(await data.fetchAuthConfig()).toBeNull()
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await data.fetchAuthConfig()).toBeNull()
  })
})
