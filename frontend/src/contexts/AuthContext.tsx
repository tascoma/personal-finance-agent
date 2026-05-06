import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { configureClient } from '../api/client'
import { logoutUser, refreshToken } from '../api/auth'

interface AuthState {
  token: string | null
  isLoading: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const tokenRef = useRef<string | null>(null)
  tokenRef.current = token

  const logout = useCallback(() => {
    logoutUser().catch(() => {})
    setToken(null)
  }, [])

  useEffect(() => {
    configureClient(() => tokenRef.current, logout)
  }, [logout])

  useEffect(() => {
    refreshToken()
      .then(({ access_token }) => setToken(access_token))
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback((t: string) => {
    setToken(t)
  }, [])

  return (
    <AuthContext.Provider value={{ token, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
