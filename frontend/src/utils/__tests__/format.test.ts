import { describe, it, expect } from 'vitest'
import { fmtPeriod, fmtDate, fmtMoney, fmtStatus } from '../format'

describe('fmtPeriod', () => {
  it('formats a YYYY-MM date string to Month Year', () => {
    expect(fmtPeriod('2024-01')).toBe('January 2024')
    expect(fmtPeriod('2024-12')).toBe('December 2024')
    expect(fmtPeriod('2023-06')).toBe('June 2023')
  })
})

describe('fmtDate', () => {
  it('returns the first 10 characters of an ISO date string', () => {
    expect(fmtDate('2024-03-15T12:00:00Z')).toBe('2024-03-15')
    expect(fmtDate('2024-03-15')).toBe('2024-03-15')
  })
})

describe('fmtMoney', () => {
  it('formats positive numbers with a dollar sign', () => {
    expect(fmtMoney(100)).toBe('$100.00')
    expect(fmtMoney(0)).toBe('$0.00')
    expect(fmtMoney('42.5')).toBe('$42.50')
  })

  it('formats negative numbers with parentheses', () => {
    expect(fmtMoney(-50)).toBe('$(50.00)')
    expect(fmtMoney(-0.99)).toBe('$(0.99)')
  })
})

describe('fmtStatus', () => {
  it('replaces underscores with spaces and title-cases each word', () => {
    expect(fmtStatus('pending_review')).toBe('Pending Review')
    expect(fmtStatus('open')).toBe('Open')
    expect(fmtStatus('in_progress')).toBe('In Progress')
  })
})
