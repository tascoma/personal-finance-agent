interface Props {
  confidence: string | null
}

function confColor(pct: number): string {
  if (pct >= 0.85) return 'var(--green)'
  if (pct >= 0.6) return 'var(--amber)'
  return 'var(--red)'
}

export default function ConfidencePill({ confidence }: Props) {
  if (confidence === null) return <span className="color-text3">—</span>
  const pct = parseFloat(confidence)
  const color = confColor(pct)
  return (
    <span className="conf-pill">
      <span className="conf-bar-bg">
        <span
          className="conf-bar-fill"
          style={{ width: `${Math.round(pct * 100)}%`, background: color }}
        />
      </span>
      <span className="conf-pct" style={{ color }}>
        {Math.round(pct * 100)}%
      </span>
    </span>
  )
}
