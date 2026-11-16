import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import VisualWorkbench from '../pages/VisualWorkbench.jsx'
import Reports from '../pages/Reports.jsx'
import Dashboard from '../pages/Dashboard.jsx'
import Results from '../pages/Results.jsx'
import Login from '../pages/Login.jsx'

// Pages talk to the real data layer; only the network is stubbed. Each test
// registers backend responses by path.
const ok = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

let routes
beforeEach(() => {
  routes = {}
  vi.stubGlobal(
    'fetch',
    vi.fn((url) => {
      const path = String(url).split('?')[0]
      return path in routes ? ok(...[].concat(routes[path])) : ok({ detail: 'Not Found' }, 404)
    })
  )
  sessionStorage.clear()
})
afterEach(() => {
  vi.unstubAllGlobals()
})

const at = (path, element, pattern = path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={pattern} element={element} />
      </Routes>
    </MemoryRouter>
  )

const REPORTS = [
  { report_id: 12, status: 'fail', violations: [{ severity: 'high' }], plan_text: 'Two storey house in Kochi', source: 'text', created_at: '2026-11-10T08:00:00' },
  { report_id: 11, status: 'pass', violations: [], plan_text: 'Single storey shed', source: 'upload', created_at: '2026-11-09T08:00:00' },
]

const RESULT = {
  report_id: 12,
  summary: 'Front setback is below the minimum.',
  extracted_facts: ['front setback: 1m', 'floors: 2'],
  violations: [
    {
      rule_reference: 'Rule 23(4)',
      severity: 'high',
      description: 'Front setback 1m is below the required 3m.',
      plan_value: '1 m',
      required_value: '3 m',
    },
  ],
  retrieved_rules: [{ source: 'kbr-2019.pdf', rule_id: '23(4)', excerpt: 'Front yard shall be 3 metres.', score: 0.82 }],
}

describe('Login', () => {
  it('renders the sign-in form with no demo affordances', async () => {
    routes['/auth/config'] = { registration_open: true, google_enabled: true }
    at('/login', <Login />)
    expect(screen.getByRole('button', { name: /sign in with password/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /demo credentials/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /guest/i })).not.toBeInTheDocument()
  })

  it('hides Google sign-in when the backend has it disabled', async () => {
    routes['/auth/config'] = { registration_open: true, google_enabled: false }
    at('/login', <Login />)
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /sign in with google/i })).not.toBeInTheDocument()
    )
  })
})

describe('VisualWorkbench', () => {
  it('renders the drop zone and an empty state without sample data', () => {
    at('/workbench', <VisualWorkbench />)
    expect(screen.getByText('PDF Visual Workbench')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /upload architectural drawing pdf/i })).toBeInTheDocument()
    expect(screen.getByText(/awaiting architectural blueprint/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /sample/i })).not.toBeInTheDocument()
  })
})

describe('Reports', () => {
  it('lists persisted reports from the API, linked to their results', async () => {
    routes['/api/reports'] = [REPORTS]
    at('/reports', <Reports />)
    const link = await screen.findByRole('link', { name: /two storey house/i })
    expect(link).toHaveAttribute('href', '/results/12')
    expect(screen.getByText('2 REPORTS')).toBeInTheDocument()
  })

  it('shows the empty archive when there are no reports', async () => {
    routes['/api/reports'] = [[]]
    at('/reports', <Reports />)
    expect(await screen.findByText(/no historical reports/i)).toBeInTheDocument()
  })
})

describe('Dashboard', () => {
  it('computes metrics from real reports and health', async () => {
    routes['/api/reports'] = [REPORTS]
    routes['/api/health'] = { status: 'ok', index_size: 1234 }
    at('/', <Dashboard />)
    expect(await screen.findByText('50.0%')).toBeInTheDocument()
    expect(screen.getByText('1,234')).toBeInTheDocument()
    // Rendered twice (phone list + wide table); every copy links to the real report.
    const links = screen.getAllByRole('link', { name: /view assessment for two storey house/i })
    expect(links.length).toBeGreaterThan(0)
    for (const link of links) expect(link).toHaveAttribute('href', '/results/12')
  })

  it('shows an empty state when there are no assessments', async () => {
    routes['/api/reports'] = [[]]
    routes['/api/health'] = { status: 'ok', index_size: 0 }
    at('/', <Dashboard />)
    expect(await screen.findByText(/no recent plan checks/i)).toBeInTheDocument()
  })
})

describe('Results', () => {
  it('renders the result of the check that was just run', () => {
    sessionStorage.setItem('chattam.result', JSON.stringify(RESULT))
    at('/results', <Results />)
    expect(screen.getByText('Front setback is below the minimum.')).toBeInTheDocument()
    expect(screen.getByText('Rule 23(4)')).toBeInTheDocument()
    expect(screen.getByText('front setback')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /export audit pdf/i })).toBeInTheDocument()
  })

  it('loads a persisted report by id', async () => {
    routes['/api/reports/12'] = RESULT
    at('/results/12', <Results />, '/results/:id')
    expect(await screen.findByText('Assessment #12')).toBeInTheDocument()
    expect(screen.getByText('Front setback 1m is below the required 3m.')).toBeInTheDocument()
  })

  it('opens the clause drawer for a cited rule', async () => {
    sessionStorage.setItem('chattam.result', JSON.stringify(RESULT))
    at('/results', <Results />)
    fireEvent.click(screen.getByRole('button', { name: /inspect clause/i }))
    expect(await screen.findByRole('dialog', { name: /kbr clause evidence/i })).toBeInTheDocument()
  })

  it('shows an empty state instead of placeholder results when nothing was run', () => {
    at('/results', <Results />)
    expect(screen.getByText(/no assessment to show/i)).toBeInTheDocument()
    expect(screen.queryByText(/kakkanad/i)).not.toBeInTheDocument()
  })

  it('reports a failure to load a persisted report', async () => {
    at('/results/99', <Results />, '/results/:id')
    expect(await screen.findByText(/could not load report/i)).toBeInTheDocument()
  })
})
