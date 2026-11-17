// Knowledge base page and the evidence shown on the Results page: rulebook
// Q&A with citations, search modes, live index statistics, citation grounding
// and rule coverage. The backend is stubbed with API-shaped fixtures.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import Knowledge from '../pages/Knowledge.jsx'
import Results from '../pages/Results.jsx'
import {
  GROUNDING_META,
  COVERAGE_META,
  ANSWER_CONFIDENCE_META,
  SEARCH_MODES,
  askRulebook,
  fetchIndexStats,
} from '../data.js'
import { ASK_ANSWER, INDEX_STATS, KBR_DOCUMENTS, RESULT, SEARCH_HITS, stubBackend } from './fixtures.js'

let fetchMock
beforeEach(() => {
  fetchMock = stubBackend({
    '/api/kbr/index': INDEX_STATS,
    '/api/kbr/documents': KBR_DOCUMENTS,
    '/api/rules/search': SEARCH_HITS,
    '/api/rules/ask': ASK_ANSWER,
  })
})
afterEach(() => {
  vi.unstubAllGlobals()
})

const renderPage = (Page) =>
  render(
    <BrowserRouter>
      <Page />
    </BrowserRouter>
  )

describe('display metadata', () => {
  it('covers every grounding status the backend emits, each with a label and a glyph', () => {
    for (const s of ['grounded', 'partial', 'ungrounded', 'uncited']) {
      expect(GROUNDING_META[s].label, s).toBeTruthy()
      expect(GROUNDING_META[s].glyph, s).toBeTruthy()
    }
  })

  it('covers every coverage status and answer confidence level', () => {
    for (const s of ['covered', 'recovered', 'gap']) expect(COVERAGE_META[s].label, s).toBeTruthy()
    for (const s of ['high', 'medium', 'low', 'none']) expect(ANSWER_CONFIDENCE_META[s].label, s).toBeTruthy()
  })

  it('offers the four search modes the API accepts', () => {
    expect(SEARCH_MODES.map((m) => m.value)).toEqual(['hybrid', 'dense', 'lexical', 'advanced'])
  })

  it('asks the backend and returns its answer unchanged', async () => {
    const result = await askRulebook('What is the front setback?', 4)
    expect(result.abstained).toBe(false)
    expect(result.citations.some((c) => c.cited)).toBe(true)
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/rules/ask')
    expect(JSON.parse(opts.body)).toEqual({ question: 'What is the front setback?', top_k: 4 })
    expect((await fetchIndexStats()).retrieval_strategy).toBe('advanced')
  })

  it('surfaces a backend failure instead of a canned answer', async () => {
    stubBackend({ '/api/rules/ask': [{ detail: 'LLM is not configured.' }, 503] })
    await expect(askRulebook('What is the front setback?')).rejects.toThrow('LLM is not configured.')
  })
})

describe('Knowledge page', () => {
  it('shows index statistics derived from the index, not static numbers', async () => {
    renderPage(Knowledge)
    await waitFor(() => expect(screen.getByText('Topic-aware · Hybrid')).toBeInTheDocument())
    expect(screen.getByText('2,481')).toBeInTheDocument()
    expect(screen.getByText('Rules Recognised')).toBeInTheDocument()
    expect(screen.getByText('214')).toBeInTheDocument() // 109 + 31 + 74
  })

  it('lists documents with their rule and chunk counts', async () => {
    renderPage(Knowledge)
    const table = screen.getByRole('table')
    expect(await within(table).findByText('Kerala Building Rules 2019.pdf')).toBeInTheDocument()
    expect(within(table).getByText('Rules')).toBeInTheDocument()
    expect(within(table).getAllByText(/INDEXED/).length).toBeGreaterThan(0)
  })

  it('keeps Ask disabled until a real question is typed', () => {
    renderPage(Knowledge)
    const ask = screen.getByRole('button', { name: /^ask$/i })
    expect(ask).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/question for the rulebook/i), { target: { value: 'ab' } })
    expect(ask).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/question for the rulebook/i), {
      target: { value: 'What is the minimum front setback?' },
    })
    expect(ask).toBeEnabled()
  })

  it('answers a question with a confidence label and the cited rule', async () => {
    renderPage(Knowledge)
    fireEvent.change(screen.getByLabelText(/question for the rulebook/i), {
      target: { value: 'What is the minimum front setback?' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    await waitFor(() => expect(screen.getByText(/WELL SUPPORTED/)).toBeInTheDocument(), { timeout: 3000 })
    expect(screen.getByText(/shall not be less than 3 metres, measured from/i)).toBeInTheDocument()
    // The [1] marker becomes a link to the cited excerpt.
    expect(screen.getByRole('link', { name: 'Citation 1' })).toHaveAttribute('href', '#citation-1')
    expect(screen.getByText('Cited rules')).toBeInTheDocument()
    expect(screen.getByText('Rule 23(4)')).toBeInTheDocument()
    expect(screen.getByText(/CHAPTER IV OCCUPANCY > 23\. Open spaces · p\. 47/)).toBeInTheDocument()
    // Retrieved-but-uncited excerpts are kept apart from the evidence.
    expect(screen.getByText(/Also retrieved, not cited \(1\)/)).toBeInTheDocument()
  })

  it('searches in the chosen mode and explains the hit', async () => {
    renderPage(Knowledge)
    fireEvent.change(screen.getByLabelText(/search mode/i), { target: { value: 'lexical' } })
    expect(screen.getByLabelText(/search mode/i)).toHaveValue('lexical')
    fireEvent.change(screen.getByLabelText(/search the rules/i), { target: { value: 'front setback' } })
    fireEvent.click(screen.getByRole('button', { name: /^search$/i }))

    await waitFor(() => expect(screen.getByText(/RELEVANCE: 0\.91/)).toBeInTheDocument(), { timeout: 3000 })
    expect(screen.getByText('SEMANTIC 0.84')).toBeInTheDocument()
    expect(screen.getByText('KEYWORD 1.00')).toBeInTheDocument()
    expect(screen.getByText('MATCHED: front, setback')).toBeInTheDocument()
  })
})

describe('Results page evidence', () => {
  afterEach(() => sessionStorage.clear())

  it('labels each finding with whether its citation was verified', () => {
    sessionStorage.setItem('chattam.result', JSON.stringify(RESULT))
    renderPage(Results)
    expect(screen.getAllByText(/CITATION VERIFIED/)).toHaveLength(2)
    expect(screen.getAllByText(/PARTLY VERIFIED/)).toHaveLength(1)
  })

  it('shows which topics had a rule retrieved and says gaps were not assessed', () => {
    sessionStorage.setItem('chattam.result', JSON.stringify(RESULT))
    renderPage(Results)
    const panel = screen.getByRole('region', { name: /rule coverage/i })
    expect(within(panel).getByText('3/4 TOPICS')).toBeInTheDocument()
    expect(within(panel).getAllByText(/RULE RETRIEVED/).length).toBeGreaterThanOrEqual(3)
    expect(within(panel).getByText(/NO RULE RETRIEVED/)).toBeInTheDocument()
    expect(within(panel).getByText('No indexed rule covers this topic.')).toBeInTheDocument()
    expect(within(panel).getByText(/not assessed/i)).toBeInTheDocument()
  })

  it('shows no evidence panels for a result that has none', async () => {
    const stored = { ...RESULT, retrieval: undefined, grounding: undefined }
    sessionStorage.setItem('chattam.result', JSON.stringify(stored))
    renderPage(Results)
    await waitFor(() => expect(screen.queryByText(/CITATION VERIFIED/)).not.toBeInTheDocument())
    expect(screen.queryByRole('region', { name: /rule coverage/i })).not.toBeInTheDocument()
  })

  it('flags a citation the retrieved rules do not contain', async () => {
    const stored = {
      ...RESULT,
      grounding: {
        total: 3,
        score: 0,
        items: [{ violation_index: 0, status: 'ungrounded', citations: [], note: 'The cited rule is not among the retrieved excerpts.' }],
      },
    }
    sessionStorage.setItem('chattam.result', JSON.stringify(stored))
    renderPage(Results)
    await waitFor(() => expect(screen.getByText(/CITATION NOT FOUND/)).toBeInTheDocument())
  })
})
