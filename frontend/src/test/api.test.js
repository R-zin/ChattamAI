// Data layer: every call goes to the backend (same origin unless VITE_API_URL is
// set), failures reach the caller, and nothing is ever substituted with
// placeholder data.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

async function loadData({ apiUrl = '' } = {}) {
  vi.resetModules()
  vi.stubEnv('VITE_API_URL', apiUrl)
  return import('../data.js')
}

const json = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

let fetchMock
beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  sessionStorage.clear()
  localStorage.clear()
})
afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('API base URL', () => {
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

  it('refuses an http API URL from an https page with a clear error instead of faking data', async () => {
    const data = await loadData({ apiUrl: 'http://api.example.com' })
    const original = window.location
    Object.defineProperty(window, 'location', {
      value: { ...original, protocol: 'https:' },
      configurable: true,
    })
    try {
      expect(data.apiConfigError()).toMatch(/Misconfigured API URL/)
      await expect(data.fetchHealth()).rejects.toThrow(/Misconfigured API URL/)
      expect(fetchMock).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(window, 'location', { value: original, configurable: true })
    }
  })

  it('exposes no mock or demo switches', async () => {
    const data = await loadData()
    for (const name of ['USE_MOCKS', 'apiAvailable', 'demoResponse', 'demoFactGrid', 'checks', 'reports', 'kbrDocs', 'kbrStats', 'metrics']) {
      expect(data[name], name).toBeUndefined()
    }
  })
})

describe('authenticated requests', () => {
  it('sends the stored bearer token', async () => {
    const data = await loadData()
    data.setToken('tok-123')
    fetchMock.mockReturnValue(json([]))
    await data.fetchReports()
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer tok-123')
  })

  it('PDF certificate export sends the bearer token', async () => {
    const data = await loadData()
    data.setToken('tok-456')
    fetchMock.mockReturnValue(
      Promise.resolve({ ok: true, status: 200, blob: () => Promise.resolve(new Blob(['%PDF'])) })
    )
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    // jsdom cannot navigate to a blob: URL; the download click itself is not under test.
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await data.exportPdfReportV2(new File(['%PDF'], 'plan.pdf', { type: 'application/pdf' }))
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v2/check/pdf/export-report')
    expect(opts.headers.Authorization).toBe('Bearer tok-456')
    expect(click).toHaveBeenCalledOnce()
    click.mockRestore()
  })

  it('clears the token on 401', async () => {
    const data = await loadData()
    data.setToken('expired')
    // Already on /login, so the redirect is a no-op (jsdom cannot navigate).
    window.history.pushState({}, '', '/login')
    try {
      fetchMock.mockReturnValue(json({ detail: 'Not authenticated' }, 401))
      await expect(data.fetchReports()).rejects.toThrow(/session has expired/i)
      expect(data.getToken()).toBeNull()
    } finally {
      window.history.pushState({}, '', '/')
    }
  })
})

describe('no fallback data', () => {
  it('fetchReports rejects on failure', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ detail: 'boom' }, 500))
    await expect(data.fetchReports()).rejects.toThrow('boom')
  })

  it('fetchReports returns an empty list for an empty archive', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json([]))
    expect(await data.fetchReports()).toEqual([])
  })

  it('fetchReports maps persisted statuses', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(
      json([
        { report_id: 3, status: 'fail', violations: [{}, {}], plan_text: 'plan A', created_at: '2026-11-01T10:00:00' },
        { report_id: 2, status: 'warning', violations: [{}] },
        { report_id: 1, status: 'pass', violations: [] },
      ])
    )
    const rows = await data.fetchReports()
    expect(rows.map((r) => [r.id, r.status, r.violations])).toEqual([
      [3, 'violation', 2],
      [2, 'review', 1],
      [1, 'compliant', 0],
    ])
    expect(rows[0].date).toBe('2026-11-01')
    expect(rows[1].project).toBe('Assessment #2')
  })

  it('fetchReport loads one persisted report by id', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ report_id: 7, violations: [], retrieved_rules: [] }))
    const r = await data.fetchReport(7)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/reports/7')
    expect(r.report_id).toBe(7)
  })

  it('fetchKbrDocuments rejects when the backend is unreachable', async () => {
    const data = await loadData()
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(data.fetchKbrDocuments()).rejects.toThrow(/unreachable/i)
  })

  it('fetchKbrDocuments joins documents with real counts from the index', async () => {
    const data = await loadData()
    fetchMock.mockImplementation((url) =>
      url === '/api/kbr/index'
        ? json({ documents: [{ source: 'kbr-2019.pdf', chunks: 40, rules: 12, pages: 9 }] })
        : json([
            { filename: 'kbr-2019.pdf', size_bytes: 2048, modified_at: '2026-10-02T09:14:00', ext: '.pdf' },
            { filename: 'new-upload.txt', size_bytes: 10, modified_at: '2026-10-03T09:14:00', ext: '.txt' },
          ])
    )
    expect(await data.fetchKbrDocuments()).toEqual([
      { doc: 'kbr-2019.pdf', type: 'KBR (PDF)', pages: 9, chunks: '40', rules: '12', indexed: '2026-10-02', status: 'INDEXED' },
      { doc: 'new-upload.txt', type: 'KBR (TXT)', pages: '—', chunks: '0', rules: '0', indexed: '2026-10-03', status: 'NOT INDEXED' },
    ])
  })

  it('checkPdfV2 surfaces a failed audit', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ detail: 'Embeddings are not configured.' }, 503))
    const file = new File(['%PDF'], 'plan.pdf', { type: 'application/pdf' })
    await expect(data.checkPdfV2(file)).rejects.toThrow('Embeddings are not configured.')
  })

  it('analyzePlan posts plan text to /api/check', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ violations: [], retrieved_rules: [], extracted_facts: [], summary: '' }))
    await data.analyzePlan({ planText: '3 floor building, 12m tall' })
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/check')
    expect(JSON.parse(opts.body).plan_text).toBe('3 floor building, 12m tall')
  })
})

describe('registration and sign-in', () => {
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

describe('rulebook data layer (live mode)', () => {
  let fetchMock
  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('askRulebook POSTs the question to /api/rules/ask', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ answer: 'Three metres [1].', abstained: false, confidence: 'high', citations: [] }))
    const result = await data.askRulebook('What is the front setback?', 4)
    expect(result.answer).toBe('Three metres [1].')
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/rules/ask')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ question: 'What is the front setback?', top_k: 4 })
  })

  it('askRulebook omits top_k when not given', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ answer: 'x', abstained: false, confidence: 'low', citations: [] }))
    await data.askRulebook('What is the front setback?')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ question: 'What is the front setback?' })
  })

  it('askRulebook surfaces backend errors instead of a canned answer', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json({ detail: 'Compliance check unavailable — missing: llm.' }, 503))
    await expect(data.askRulebook('What is the front setback?')).rejects.toThrow('missing: llm')
  })

  it('searchKbrRules sends the query, limit and mode', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json([]))
    await data.searchKbrRules('front setback & yard', 7, 'lexical')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/rules/search?q=front%20setback%20%26%20yard&limit=7&mode=lexical')
  })

  it('searchKbrRules defaults to hybrid mode', async () => {
    const data = await loadData()
    fetchMock.mockReturnValue(json([]))
    await data.searchKbrRules('parking')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/rules/search?q=parking&limit=5&mode=hybrid')
  })

  it('fetchIndexStats reads /api/kbr/index and rejects on failure', async () => {
    const data = await loadData()
    fetchMock.mockReturnValueOnce(json({ index_size: 585, documents: [], retrieval_strategy: 'advanced' }))
    expect((await data.fetchIndexStats()).index_size).toBe(585)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/kbr/index')
    fetchMock.mockReturnValueOnce(json({ detail: 'boom' }, 500))
    await expect(data.fetchIndexStats()).rejects.toThrow('boom')
  })

  it('fetchKbrDocuments shows real chunk, rule and page counts from the index', async () => {
    const data = await loadData()
    fetchMock
      .mockReturnValueOnce(
        json([
          { filename: 'kpbr-2019.pdf', size_bytes: 900000, modified_at: '2026-11-02T09:14:00', ext: '.pdf' },
          { filename: 'new-upload.txt', size_bytes: 1200, modified_at: '2026-11-15T10:00:00', ext: '.txt' },
        ])
      )
      .mockReturnValueOnce(
        json({ index_size: 578, documents: [{ source: 'kpbr-2019.pdf', chunks: 578, rules: 108, pages: 179 }] })
      )
    const docs = await data.fetchKbrDocuments()
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(['/api/kbr/documents', '/api/kbr/index'])
    expect(docs[0]).toEqual({
      doc: 'kpbr-2019.pdf',
      type: 'KBR (PDF)',
      pages: 179,
      chunks: '578',
      rules: '108',
      indexed: '2026-11-02',
      status: 'INDEXED',
    })
    // Uploaded but not ingested yet: honestly reported, not shown as indexed.
    expect(docs[1].status).toBe('NOT INDEXED')
    expect(docs[1].chunks).toBe('0')
    expect(docs[1].pages).toBe('—')
  })

  it('fetchKbrDocuments lists documents with unknown counts when the index cannot be read', async () => {
    const data = await loadData()
    fetchMock
      .mockReturnValueOnce(json([{ filename: 'kpbr-2019.pdf', size_bytes: 900000, modified_at: '2026-11-02T09:14:00' }]))
      .mockReturnValueOnce(json({ detail: 'boom' }, 500))
    const docs = await data.fetchKbrDocuments()
    expect(docs).toHaveLength(1)
    expect(docs[0].status).toBe('UNKNOWN')
    expect(docs[0].chunks).toBe('—')
  })
})
