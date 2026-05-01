import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  className?: string
}

export function Card({ children, className }: Props) {
  return <div className={`card${className ? ` ${className}` : ''}`}>{children}</div>
}

interface CardHdProps {
  title: string
  sub?: string
  right?: ReactNode
}

export function CardHd({ title, sub, right }: CardHdProps) {
  return (
    <div className="card-hd">
      <div>
        <div className="card-title">{title}</div>
        {sub && <div className="card-sub">{sub}</div>}
      </div>
      {right && <div className="card-hd-right">{right}</div>}
    </div>
  )
}

interface CardBdProps {
  children: ReactNode
  sm?: boolean
}

export function CardBd({ children, sm }: CardBdProps) {
  return <div className={sm ? 'card-bd-sm' : 'card-bd'}>{children}</div>
}
