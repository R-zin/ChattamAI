// Backend-shaped payloads for page tests. The app ships no mock data; tests
// stub fetch with these and assert the UI renders exactly what the API sent.
import { vi } from 'vitest'

export const RESULT = {
  report_id: 42,
  summary: 'One high-severity front setback deficit; parking and staircase need review.',
  extracted_facts: [
    'building type: residential',
    'floors: 3',
    'building height: 12m',
    'front setback: 1m',
    'rear setback: 2m',
    'plot area: 240 sq m',
    'built-up area: 410 sq m',
  ],
  violations: [
    {
      severity: 'high',
      rule_reference: 'Rule 23(4)',
      title: 'Front Setback',
      plan_value: '1.0 m',
      required_value: '≥ 3.0 m',
      description:
        'The submitted plan indicates a 1m front setback, while the retrieved KBR requirement specifies a minimum setback of 3m for this building classification.',
    },
    {
      severity: 'medium',
      rule_reference: 'Rule 27(1)',
      title: 'Parking Provision',
      plan_value: '4 spaces',
      required_value: '≥ 6 spaces',
      description:
        'The current configuration provides 4 off-street parking slots. Based on the total built-up area of 410 m², a minimum of 6 spaces is mandated for residential multi-unit occupancy.',
    },
    {
      severity: 'low',
      rule_reference: 'Rule 31(2)',
      title: 'Staircase Width',
      plan_value: '1.0 m',
      required_value: '≥ 1.2 m',
      description:
        'The clear width of the main internal staircase is marked as 1.0m. Rule 31(2) requires a minimum clear width of 1.2m for the primary means of escape.',
    },
  ],
  retrieved_rules: [
    {
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: '23(4)',
      page: 'p. 47',
      score: 0.91,
      excerpt:
        'Every building shall have a front setback of not less than the value prescribed for its occupancy group. For a residential building of this classification, the minimum front setback shall not be less than 3 metres measured from the plot boundary abutting the street, and such setback shall be kept free of any permanent construction.',
    },
    {
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: '27(1)',
      page: 'p. 63',
      score: 0.84,
      excerpt:
        'Off-street parking shall be provided on the same plot as the building it serves. For residential buildings, one car parking space shall be provided for every 75 square metres of built-up area or part thereof in excess of the first 150 square metres.',
    },
    {
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: '31(2)',
      page: 'p. 81',
      score: 0.79,
      excerpt:
        'The minimum clear width of a staircase serving as a primary means of escape shall not be less than 1.2 metres. Handrails may project into this width by not more than 75 millimetres on each side.',
    },
  ],
  retrieval: {
    strategy: 'advanced',
    queries: [
      { label: 'Full query', text: 'extracted fact sheet', topic: null },
      { label: 'Setbacks', text: 'minimum front rear and side setback', topic: 'setbacks' },
      { label: 'Parking', text: 'off-street car parking spaces required', topic: 'parking' },
      { label: 'Fire safety & stairs', text: 'staircase width fire safety', topic: 'fire_stair' },
    ],
    coverage: [
      { topic: 'setbacks', label: 'Setbacks', status: 'covered', rule_ids: ['23(4)'], reason: null },
      { topic: 'parking', label: 'Parking', status: 'covered', rule_ids: ['27(1)'], reason: null },
      { topic: 'fire_stair', label: 'Fire safety & stairs', status: 'covered', rule_ids: ['31(2)'], reason: null },
      { topic: 'fsi', label: 'FSI / FAR', status: 'gap', rule_ids: [], reason: 'not_in_index' },
    ],
    gaps: ['FSI / FAR'],
    candidates: 24,
    corrective_hits: 0,
  },
  grounding: {
    total: 3,
    score: 0.833,
    grounded: 2,
    partial: 1,
    ungrounded: 0,
    uncited: 0,
    items: [
      { violation_index: 0, rule_reference: 'Rule 23(4)', status: 'grounded', citations: [1], value_supported: true, note: 'Cited rule was retrieved and states the required value.' },
      { violation_index: 1, rule_reference: 'Rule 27(1)', status: 'partial', citations: [2], value_supported: false, note: 'Cited rule was retrieved, but it does not state the required value.' },
      { violation_index: 2, rule_reference: 'Rule 31(2)', status: 'grounded', citations: [3], value_supported: true, note: 'Cited rule was retrieved and states the required value.' },
    ],
  },
  verification: {
    status: 'confirmed',
    verified_by_model: 'DeepSeek-R1 (Verifier)',
    confidence_score: 0.98,
    cross_check_notes:
      'All candidate violations verified against KMBR/KPBR 2019 excerpts. Front setback and parking deficit confirmed.',
    discrepancies: [],
    primary_violations_count: 3,
    final_violations_count: 3,
  },
}

export const INDEX_STATS = {
  index_size: 2481,
  documents: [
    { source: 'Kerala Building Rules 2019.pdf', chunks: 1284, rules: 109, pages: 142 },
    { source: 'KBR Amendment 2021.pdf', chunks: 512, rules: 31, pages: 38 },
    { source: 'Municipal Building Rules 1999.pdf', chunks: 685, rules: 74, pages: 96 },
  ],
  embedding_provider: 'nim',
  embedding_model: 'nvidia/nemotron-3-embed-1b',
  embedding_dim: 2048,
  retrieval_strategy: 'advanced',
  hybrid: true,
  hybrid_weight: 0.7,
  structured_chunking: true,
}

// GET /api/kbr/documents
export const KBR_DOCUMENTS = INDEX_STATS.documents.map((d) => ({
  filename: d.source,
  size_bytes: 1000000,
  modified_at: '2026-08-02T09:14:00',
  ext: '.pdf',
}))

export const SEARCH_HITS = [
  {
    rule_id: 'Rule 23(4)',
    source: 'Kerala_Building_Rules_2019.pdf',
    section: 'CHAPTER IV OCCUPANCY > 23. Open spaces',
    page: 47,
    chunk: 47,
    excerpt: 'Every building shall have a front setback not less than prescribed for its occupancy group.',
    score: 0.91,
    dense_score: 0.84,
    lexical_score: 1,
    matched_terms: ['front', 'setback'],
  },
]

export const ASK_ANSWER = {
  question: 'What is the minimum front setback?',
  answer:
    'For a residential building of this classification the front setback shall not be less than 3 metres, measured from the plot boundary abutting the street [1].',
  abstained: false,
  confidence: 'high',
  citations: [
    {
      index: 1,
      cited: true,
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: 'Rule 23(4)',
      section: 'CHAPTER IV OCCUPANCY > 23. Open spaces',
      page: 47,
      excerpt:
        'Every building shall have a front setback of not less than the value prescribed for its occupancy group. For a residential building of this classification, the minimum front setback shall not be less than 3 metres measured from the plot boundary abutting the street.',
      score: 0.91,
    },
    {
      index: 2,
      cited: false,
      source: 'Kerala_Building_Rules_2019.pdf',
      rule_id: 'Rule 27(1)',
      section: 'CHAPTER IV OCCUPANCY > 27. Parking',
      page: 63,
      excerpt: 'Off-street parking shall be provided on the same plot as the building it serves.',
      score: 0.42,
    },
  ],
  retrieval: { strategy: 'advanced', queries: [], coverage: [], gaps: [] },
}

const respond = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

// Stub global fetch with a {path: body | [body, status]} table; unknown paths 404.
// Returns the mock so tests can inspect calls.
export function stubBackend(routes) {
  const mock = vi.fn((url) => {
    const path = String(url).split('?')[0]
    if (!(path in routes)) return respond({ detail: 'Not Found' }, 404)
    const entry = routes[path]
    return Array.isArray(entry) && entry.length === 2 && typeof entry[1] === 'number'
      ? respond(entry[0], entry[1])
      : respond(entry)
  })
  vi.stubGlobal('fetch', mock)
  return mock
}
