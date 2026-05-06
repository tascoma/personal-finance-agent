import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBadge from '../StatusBadge'

describe('StatusBadge', () => {
  it('renders the status with underscores replaced by spaces', () => {
    render(<StatusBadge status="pending_review" />)
    expect(screen.getByText('pending review')).toBeInTheDocument()
  })

  it('applies a CSS class based on the status prop', () => {
    render(<StatusBadge status="open" />)
    expect(screen.getByText('open')).toHaveClass('badge--open')
  })

  it('renders a plain status without transformation issues', () => {
    render(<StatusBadge status="closed" />)
    expect(screen.getByText('closed')).toBeInTheDocument()
  })
})
