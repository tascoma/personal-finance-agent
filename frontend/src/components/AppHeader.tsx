import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import SvgIcon from './SvgIcon'
import { useAuth } from '../contexts/AuthContext'
import { getMe } from '../api/auth'
import type { Period } from '../types'

interface Props {
  activePeriod?: Period | null
}

export default function AppHeader({ activePeriod }: Props) {
  const { logout, token } = useAuth()
  const { data: me } = useQuery({
    queryKey: ['auth-me'],
    queryFn: getMe,
    enabled: !!token,
    staleTime: Infinity,
  })

  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('pf-theme') === 'light' ? 'light' : 'dark'),
  )

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('pf-theme', next)
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const periodLabel = activePeriod
    ? new Date(activePeriod.period_start + 'T00:00:00').toLocaleString('default', {
        month: 'long',
        year: 'numeric',
      })
    : 'View Periods'

  return (
    <header className="app-header">
      <Link to="/" className="app-header-brand">
        <span className="app-header-logo">
          <SvgIcon name="spark" size={14} style={{ stroke: '#05080f', strokeWidth: 2.2 }} />
        </span>
        <span className="app-header-title">Personal Finance AI</span>
      </Link>

      <Link to="/periods" className="app-header-period" title="View periods">
        <span className="app-header-period-eyebrow">Workflow</span>
        <span className="app-header-period-label">{periodLabel}</span>
        {activePeriod && (
          <span className={`status-dot status-dot--${activePeriod.status}`} />
        )}
      </Link>

      <div className="app-header-right">
        <button
          className="app-header-icon-btn"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          title="Toggle theme"
        >
          <SvgIcon name="moon" size={14} className="icon theme-icon--light" />
          <SvgIcon name="sun" size={14} className="icon theme-icon--dark" />
        </button>
        {me && (
          <>
            <span className="app-header-email" title={me.email}>{me.email}</span>
            <button
              className="btn btn-secondary btn-sm app-header-signout"
              onClick={logout}
              title="Sign out"
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </header>
  )
}
