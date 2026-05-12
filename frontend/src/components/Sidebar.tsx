import { NavLink } from 'react-router-dom'
import SvgIcon from './SvgIcon'

interface NavItem {
  to: string
  icon: 'dashboard' | 'periods' | 'journal' | 'statements' | 'accounts'
  label: string
}

const NAV: NavItem[] = [
  { to: '/', icon: 'dashboard', label: 'Dashboard' },
  { to: '/periods', icon: 'periods', label: 'Workflow' },
  { to: '/ledger', icon: 'journal', label: 'Ledger' },
  { to: '/ledger/statements', icon: 'statements', label: 'Statements' },
  { to: '/accounts', icon: 'accounts', label: 'Accounts' },
]

export default function Sidebar() {
  return (
    <nav className="sidebar">
      <ul className="sidebar-nav">
        {NAV.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === '/' || item.to === '/ledger/statements' || item.to === '/ledger'}
              className={({ isActive }) =>
                `nav-link${isActive ? ' nav-link--active' : ''}`
              }
              data-tooltip={item.label}
              aria-label={item.label}
            >
              <SvgIcon name={item.icon} size={18} />
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
