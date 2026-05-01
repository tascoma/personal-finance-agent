interface Tab {
  key: string
  label: string
  count?: number
}

interface Props {
  tabs: Tab[]
  active: string
  onChange: (key: string) => void
}

export default function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div className="tabs">
      {tabs.map((t) => (
        <button
          key={t.key}
          className={`tab-btn${active === t.key ? ' tab-btn--active' : ''}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
          {t.count !== undefined && (
            <span style={{ marginLeft: 5, opacity: 0.6, fontFamily: 'DM Mono, monospace', fontSize: 11 }}>
              {t.count}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
