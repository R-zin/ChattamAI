import { describe, it, expect } from 'vitest'
import { deriveStatus, STATUS_META, SEVERITY_META, isBuildingPlanText, formatErrorDetail, reports } from '../data'

describe('formatErrorDetail', () => {
  it('formats string errors directly', () => {
    expect(formatErrorDetail('Invalid credentials')).toBe('Invalid credentials')
  })

  it('formats array of validation detail objects into human-readable strings', () => {
    const err = [
      { loc: ['body', 'email'], msg: 'value is not a valid email address' },
      { loc: ['body', 'password'], msg: 'field required' },
    ]
    expect(formatErrorDetail(err)).toBe(
      'email: value is not a valid email address; password: field required'
    )
  })

  it('formats object detail gracefully without [object Object]', () => {
    expect(formatErrorDetail({ message: 'Custom error occurred' })).toBe('Custom error occurred')
    expect(formatErrorDetail({ error: 'Auth failed' })).toBe('Auth failed')
    expect(formatErrorDetail({ custom: 123 })).toBe('{"custom":123}')
  })

  it('returns fallback for falsy values', () => {
    expect(formatErrorDetail(null, 'Default failure')).toBe('Default failure')
    expect(formatErrorDetail(undefined, 'Fallback')).toBe('Fallback')
  })
})

describe('reports mock data', () => {
  it('every mock report item has a defined unique id', () => {
    expect(reports.length).toBeGreaterThan(0)
    for (const r of reports) {
      expect(r.id).toBeDefined()
      expect(typeof r.id).toBe('string')
      expect(r.id.length).toBeGreaterThan(0)
    }
  })
})

describe('deriveStatus', () => {
  it('returns insufficient when there are no rules and no violations', () => {
    expect(deriveStatus({ violations: [], retrieved_rules: [] })).toBe('insufficient')
  })

  it('returns violation when any violation is high severity', () => {
    const res = {
      violations: [{ severity: 'high' }, { severity: 'low' }],
      retrieved_rules: [{ source: 'x' }],
    }
    expect(deriveStatus(res)).toBe('violation')
  })

  it('returns review when violations exist but none are high', () => {
    const res = {
      violations: [{ severity: 'medium' }],
      retrieved_rules: [{ source: 'x' }],
    }
    expect(deriveStatus(res)).toBe('review')
  })

  it('returns compliant when rules were retrieved but there are no violations', () => {
    const res = { violations: [], retrieved_rules: [{ source: 'x' }] }
    expect(deriveStatus(res)).toBe('compliant')
  })

  it('handles a missing/undefined response gracefully', () => {
    expect(deriveStatus(undefined)).toBe('insufficient')
    expect(deriveStatus({})).toBe('insufficient')
  })
})

describe('meta maps', () => {
  it('has display metadata for every derivable status', () => {
    for (const s of ['compliant', 'review', 'violation', 'insufficient']) {
      expect(STATUS_META[s], s).toBeTruthy()
      expect(STATUS_META[s].label).toBeTruthy()
    }
  })

  it('has display metadata for every backend severity', () => {
    for (const sev of ['high', 'medium', 'low', 'info']) {
      expect(SEVERITY_META[sev], sev).toBeTruthy()
    }
  })
})

describe('isBuildingPlanText', () => {
  it('rejects short or empty text', () => {
    expect(isBuildingPlanText('')).toBe(false)
    expect(isBuildingPlanText('hello')).toBe(false)
    expect(isBuildingPlanText('just short text')).toBe(false)
  })

  it('rejects non-architectural content like recipes and code', () => {
    expect(isBuildingPlanText('Recipe for chocolate cake: flour, sugar, eggs, bake for 30 minutes.')).toBe(false)
    expect(isBuildingPlanText('def main():\n    import os\n    print("running system tests")')).toBe(false)
    expect(isBuildingPlanText('John Doe Software Engineer resume with 5 years experience in React')).toBe(false)
    expect(isBuildingPlanText('Invoice #12345 for services rendered. Total: $500.00')).toBe(false)
  })

  it('accepts architectural building plans and specifications', () => {
    expect(isBuildingPlanText('3 floor building, 12m tall, 1m front setback')).toBe(true)
    expect(
      isBuildingPlanText(
        'Single family residential building under Group A1 in Category-II Village Panchayat with total built-up area of 90 sq. metres, 2 storeys. Proposed front distance 1.0m.'
      )
    ).toBe(true)
    expect(
      isBuildingPlanText(
        'Commercial building under Group F Occupancy on a plot of 850 sq. metres with height 16m.'
      )
    ).toBe(true)
    expect(
      isBuildingPlanText(
        'Proposed small shed structure in residential plot with setbacks.'
      )
    ).toBe(true)
  })
})

