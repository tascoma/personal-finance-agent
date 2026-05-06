import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '../AuthContext'

vi.mock('../../api/auth', () => ({
  refreshToken: vi.fn(),
  logoutUser: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  configureClient: vi.fn(),
}))

import { refreshToken, logoutUser } from '../../api/auth'

function TestConsumer() {
  const { token, isLoading } = useAuth()
  if (isLoading) return <div>loading</div>
  return <div>{token ?? 'no-token'}</div>
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AuthProvider', () => {
  it('shows loading state while refresh is in flight', async () => {
    vi.mocked(refreshToken).mockReturnValue(new Promise(() => {})) // never resolves
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )
    expect(screen.getByText('loading')).toBeInTheDocument()
  })

  it('sets token when refresh succeeds', async () => {
    vi.mocked(refreshToken).mockResolvedValue({ access_token: 'abc123', token_type: 'bearer' })
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByText('abc123')).toBeInTheDocument())
  })

  it('shows no-token when refresh fails', async () => {
    vi.mocked(refreshToken).mockRejectedValue(new Error('401'))
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByText('no-token')).toBeInTheDocument())
  })

  it('throws when useAuth is used outside AuthProvider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<TestConsumer />)).toThrow('useAuth must be used inside AuthProvider')
    consoleError.mockRestore()
  })
})
