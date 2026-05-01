import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import SvgIcon from './SvgIcon'

interface Props {
  title: string
  subtitle?: string
  backTo?: string
  backLabel?: string
  badge?: ReactNode
  right?: ReactNode
}

export default function PageHeader({ title, subtitle, backTo, backLabel, badge, right }: Props) {
  return (
    <div className="page-header">
      <div>
        {backTo && (
          <Link to={backTo} className="page-header-back">
            <SvgIcon name="back" size={12} />
            {backLabel ?? 'Back'}
          </Link>
        )}
        <div className="page-title-row">
          <h1>{title}</h1>
          {badge}
        </div>
        {subtitle && <div className="page-subtitle">{subtitle}</div>}
      </div>
      {right && <div className="page-header-right">{right}</div>}
    </div>
  )
}
