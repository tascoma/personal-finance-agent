import { Link } from 'react-router-dom'
import type { Period } from '../types'
import SvgIcon from './SvgIcon'

const STEPS: Array<{ status: Period['status']; label: string; sub: string }> = [
  { status: 'open', label: 'Input', sub: 'Upload docs' },
  { status: 'pending_review', label: 'Parse', sub: 'Classify txns' },
  { status: 'pending_close', label: 'Journal', sub: 'Post entries' },
  { status: 'closed', label: 'Close', sub: 'Reconcile' },
]

const STATUS_ORDER: Record<Period['status'], number> = {
  open: 0,
  pending_review: 1,
  pending_close: 2,
  closed: 3,
}

interface Props {
  period: Period
}

export default function PeriodStepper({ period }: Props) {
  const current = STATUS_ORDER[period.status]

  return (
    <div className="stepper">
      {STEPS.map((step, i) => {
        const state = i < current ? 'done' : i === current ? 'active' : 'pending'
        return (
          <Link
            key={step.status}
            to={`/periods/${period.period_id}`}
            className={`step step--${state}`}
            style={{ textDecoration: 'none' }}
          >
            <div className={`step-circle step-circle--${state}`}>
              {state === 'done' ? <SvgIcon name="check" size={12} /> : i + 1}
            </div>
            <div>
              <div className="step-label">{step.label}</div>
              <div className="step-sub">{step.sub}</div>
            </div>
            {state === 'active' && <div className="step-dot" />}
          </Link>
        )
      })}
    </div>
  )
}
