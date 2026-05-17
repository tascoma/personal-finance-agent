import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import WorkflowHint from '../WorkflowHint'
import type { Period } from '../../types'

function makePeriod(status: Period['status']): Period {
  return {
    period_id: 'p-1',
    period_start: '2026-05-01',
    period_end: '2026-05-31',
    status,
    closed_at: null,
    created_at: '2026-05-01T00:00:00Z',
  }
}

function renderHint(status: Period['status'], page: 'detail' | 'journal' | 'reconcile') {
  return render(
    <MemoryRouter>
      <WorkflowHint period={makePeriod(status)} page={page} />
    </MemoryRouter>,
  )
}

describe('WorkflowHint', () => {
  it('shows the Step 1 phase label on an open detail page with no CTA', () => {
    renderHint('open', 'detail')
    expect(screen.getByText('Step 1 · Input')).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('renders a forward CTA pointing to the journal when pending_review on detail', () => {
    renderHint('pending_review', 'detail')
    expect(screen.getByText('Step 2 · Review')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /Review Journal/i })
    expect(link).toHaveAttribute('href', '/periods/p-1/journal')
  })

  it('renders a back CTA to the period detail when visiting reconcile too early', () => {
    renderHint('open', 'reconcile')
    const link = screen.getByRole('link', { name: /Back to Period/i })
    expect(link).toHaveAttribute('href', '/periods/p-1')
  })

  it('renders a closed-state hint with a link back to the period on the journal page', () => {
    renderHint('closed', 'journal')
    expect(screen.getByText('Closed')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /Period Detail/i })
    expect(link).toHaveAttribute('href', '/periods/p-1')
  })
})
