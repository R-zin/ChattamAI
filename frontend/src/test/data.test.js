import { describe, it, expect } from 'vitest'
import { deriveStatus, STATUS_META, SEVERITY_META } from '../data'

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
