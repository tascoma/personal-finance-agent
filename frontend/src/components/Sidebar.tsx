import { NavLink, Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import SvgIcon from './SvgIcon'
import type { Period } from '../types'

interface NavItem {
  to: string
  icon: 'dashboard' | 'periods' | 'journal' | 'statements' | 'accounts'
  label: string
  matchPaths?: string[]
}

const NAV: NavItem[] = [
  { to: '/', icon: 'dashboard', label: 'Dashboard' },
  { to: '/periods', icon: 'periods', label: 'Workflow', matchPaths: ['/periods'] },
  { to: '/ledger', icon: 'journal', label: 'Ledger' },
  { to: '/ledger/statements', icon: 'statements', label: 'Statements' },
  { to: '/accounts', icon: 'accounts', label: 'Accounts' },
]

interface Props {
  activePeriod?: Period | null
}

export default function Sidebar({ activePeriod }: Props) {
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('pf-theme') === 'light' ? 'light' : 'dark'),
  )

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('pf-theme', next)
  }

  function toggleCollapse() {
    const collapsed = document.documentElement.classList.toggle('nav-collapsed')
    localStorage.setItem('nav-collapsed', collapsed ? '1' : '0')
  }

  // Sync data-theme on mount in case React re-renders after the inline script ran
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
    <nav className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo-wrap">
        <div className="sidebar-logo-icon">
          <SvgIcon name="spark" size={15} style={{ stroke: '#05080f', strokeWidth: 2.2 }} />
        </div>
        <div className="nav-collapsible">
          <div className="sidebar-logo-text">Finance Agent</div>
          <div className="sidebar-logo-sub">Personal Ledger</div>
        </div>
      </div>

      {/* Active period block */}
      <div className="sidebar-period">
        <Link to="/periods" className="sidebar-period-inner">
          <div className="sidebar-period-eyebrow">Workflow</div>
          <div className="sidebar-period-label">{periodLabel}</div>
          {activePeriod && (
            <div className="sidebar-period-status">
              <span className={`status-dot status-dot--${activePeriod.status}`} />
              {activePeriod.status.replace(/_/g, ' ')}
            </div>
          )}
        </Link>
      </div>

      {/* Nav links */}
      <ul className="sidebar-nav">
        {NAV.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === '/' || item.to === '/ledger/statements' || item.to === '/ledger'}
              className={({ isActive }) =>
                `nav-link${isActive ? ' nav-link--active' : ''}`
              }
              title={item.label}
            >
              <SvgIcon name={item.icon} size={15} />
              <span className="nav-collapsible">{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>

      {/* Collapse toggle */}
      <div className="sidebar-collapse-wrap">
        <button
          className="nav-link sidebar-collapse-btn"
          onClick={toggleCollapse}
          aria-label="Collapse sidebar"
        >
          <SvgIcon name="chevron-right" size={15} className="icon sidebar-collapse-icon" />
          <span className="nav-collapsible">Collapse</span>
        </button>
      </div>

      {/* Footer / theme toggle */}
      <div className="sidebar-footer">
        <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          <SvgIcon name="moon" size={14} className="icon theme-icon--light" />
          <SvgIcon name="sun" size={14} className="icon theme-icon--dark" />
          <span className="theme-label--light nav-collapsible">Dark mode</span>
          <span className="theme-label--dark nav-collapsible">Light mode</span>
        </button>
        <div className="sidebar-version nav-collapsible">Finance Agent · v0.1</div>
      </div>
    </nav>
  )
}
