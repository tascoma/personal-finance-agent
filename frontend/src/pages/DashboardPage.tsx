import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Chart,
  BarElement, LineElement, PointElement,
  BarController, LineController,
  CategoryScale, LinearScale,
  Tooltip, Legend,
} from 'chart.js'
import { fetchDashboard } from '../api/dashboard'
import { fetchPeriods } from '../api/periods'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import StatusBadge from '../components/StatusBadge'
import PeriodStepper from '../components/PeriodStepper'
import SvgIcon from '../components/SvgIcon'
import { fmtPeriod, fmtMoney } from '../utils/format'

Chart.register(BarElement, LineElement, PointElement, BarController, LineController, CategoryScale, LinearScale, Tooltip, Legend)

function kpiColor(val: string, positive: string, negative: string) {
  return parseFloat(val) >= 0 ? positive : negative
}


export default function DashboardPage() {
  const [selectedYear, setSelectedYear] = useState<number | null>(null)
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | null>(null)

  const { data: allPeriods } = useQuery({
    queryKey: ['periods'],
    queryFn: fetchPeriods,
    staleTime: 60_000,
  })

  const closedPeriods = useMemo(
    () => (allPeriods ?? []).filter((p) => p.status === 'closed'),
    [allPeriods],
  )

  const availableYears = useMemo(
    () => [...new Set(closedPeriods.map((p) => parseInt(p.period_start.slice(0, 4), 10)))].sort((a, b) => b - a),
    [closedPeriods],
  )

  const periodsForYear = useMemo(
    () => selectedYear == null ? [] : closedPeriods.filter((p) => parseInt(p.period_start.slice(0, 4), 10) === selectedYear),
    [closedPeriods, selectedYear],
  )

  function handleYearChange(year: number | null) {
    setSelectedYear(year)
    setSelectedPeriodId(null)
  }

  const scopeLabel = useMemo(() => {
    if (selectedPeriodId) {
      const p = closedPeriods.find((p) => p.period_id === selectedPeriodId)
      return p ? fmtPeriod(p.period_start) : fmtPeriod(selectedPeriodId)
    }
    if (selectedYear) return String(selectedYear)
    return 'all periods'
  }, [selectedPeriodId, selectedYear, closedPeriods])

  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', selectedYear, selectedPeriodId],
    queryFn: () => fetchDashboard(selectedYear ?? undefined, selectedPeriodId ?? undefined),
    staleTime: 30_000,
  })

  const ieRef = useRef<HTMLCanvasElement>(null)
  const nwRef = useRef<HTMLCanvasElement>(null)
  const ecRef = useRef<HTMLCanvasElement>(null)
  const chartRefs = useRef<Chart[]>([])

  useEffect(() => {
    if (!data) return

    chartRefs.current.forEach((c) => c.destroy())
    chartRefs.current = []

    const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
    const text3  = isDark ? '#6a9bb8' : '#4a7a96'
    const border = isDark ? 'rgba(86,200,240,0.08)' : 'rgba(2,132,199,0.12)'
    const green  = isDark ? '#4ade80' : '#16a34a'
    const red    = isDark ? '#f87171' : '#dc2626'
    const accent = isDark ? '#56c8f0' : '#0284c7'
    const amber  = isDark ? '#fbbf24' : '#b45309'

    Chart.defaults.color = text3
    Chart.defaults.borderColor = border
    Chart.defaults.font.family = "'DM Sans', sans-serif"
    Chart.defaults.font.size = 12

    const moneyTick = (v: number | string) => `$${Number(v).toLocaleString()}`
    const moneyTip  = (ctx: { parsed: { y?: number | null; x?: number | null } }) => {
      const n = ctx.parsed.y ?? ctx.parsed.x ?? 0
      return ` $${n.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
    }

    if (ieRef.current && data.period_bars.length) {
      chartRefs.current.push(new Chart(ieRef.current, {
        type: 'bar',
        data: {
          labels: data.period_bars.map((d) => d.period_label),
          datasets: [
            { label: 'Income', data: data.period_bars.map((d) => parseFloat(d.income)), backgroundColor: green + '99', borderColor: green, borderWidth: 1, borderRadius: 4 },
            { label: 'Expenses', data: data.period_bars.map((d) => parseFloat(d.expenses)), backgroundColor: red + '99', borderColor: red, borderWidth: 1, borderRadius: 4 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: true,
          plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 16 } }, tooltip: { callbacks: { label: moneyTip } } },
          scales: { x: { grid: { display: false } }, y: { ticks: { callback: moneyTick } } },
        },
      }))
    }

    if (nwRef.current && data.net_worth_series.length) {
      const ctx2d = nwRef.current.getContext('2d')!
      const gradient = ctx2d.createLinearGradient(0, 0, 0, nwRef.current.clientHeight || 180)
      gradient.addColorStop(0, accent + '55')
      gradient.addColorStop(1, accent + '00')
      chartRefs.current.push(new Chart(nwRef.current, {
        type: 'line',
        data: {
          labels: data.net_worth_series.map((d) => d.period_label),
          datasets: [{ label: 'Net Worth', data: data.net_worth_series.map((d) => parseFloat(d.net_worth)), borderColor: accent, backgroundColor: gradient, borderWidth: 2, pointBackgroundColor: accent, pointRadius: 4, fill: true, tension: 0.35 }],
        },
        options: {
          responsive: true, maintainAspectRatio: true,
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: moneyTip } } },
          scales: { x: { grid: { display: false } }, y: { ticks: { callback: moneyTick } } },
        },
      }))
    }

    if (ecRef.current && data.top_expense_categories.length) {
      const catColors = [red, amber, accent, green, '#a78bfa', '#38bdf8', '#fb923c', '#34d399']
      chartRefs.current.push(new Chart(ecRef.current, {
        type: 'bar',
        data: {
          labels: data.top_expense_categories.map((d) => d.category),
          datasets: [{ label: 'Expenses', data: data.top_expense_categories.map((d) => parseFloat(d.amount)), backgroundColor: catColors.map((c) => c + 'bb'), borderColor: catColors, borderWidth: 1, borderRadius: 4 }],
        },
        options: {
          indexAxis: 'y', responsive: true, maintainAspectRatio: true,
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => ` $${(ctx.parsed.x ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}` } } },
          scales: { x: { ticks: { callback: moneyTick } }, y: { grid: { display: false } } },
        },
      }))
    }

    return () => { chartRefs.current.forEach((c) => c.destroy()); chartRefs.current = [] }
  }, [data])

  if (isLoading) return <Layout><p className="color-text3">Loading…</p></Layout>
  if (error || !data) return <Layout><p className="color-red">Failed to load dashboard.</p></Layout>

  return (
    <Layout activePeriod={data.active_period}>
      <PageHeader
        title="Dashboard"
        subtitle={`Financial overview · ${data.period_count} period${data.period_count !== 1 ? 's' : ''} tracked`}
        right={data.active_period && (
          <Link to={`/periods/${data.active_period.period_id}`} className="btn btn-primary btn-sm">
            <SvgIcon name="periods" size={13} />
            {fmtPeriod(data.active_period.period_start)}
          </Link>
        )}
      />

      {availableYears.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <select
            className="inp"
            style={{ width: 130 }}
            value={selectedYear ?? ''}
            onChange={(e) => handleYearChange(e.target.value ? parseInt(e.target.value, 10) : null)}
          >
            <option value="">All years</option>
            {availableYears.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <select
            className="inp"
            style={{ width: 160 }}
            value={selectedPeriodId ?? ''}
            disabled={selectedYear == null}
            onChange={(e) => setSelectedPeriodId(e.target.value || null)}
          >
            <option value="">All periods</option>
            {periodsForYear.map((p) => (
              <option key={p.period_id} value={p.period_id}>{fmtPeriod(p.period_start)}</option>
            ))}
          </select>
          {(selectedYear != null || selectedPeriodId != null) && (
            <button className="btn btn-ghost btn-sm" onClick={() => { setSelectedYear(null); setSelectedPeriodId(null) }}>
              Clear ×
            </button>
          )}
        </div>
      )}

      {!data.has_data && !data.active_period ? (
        <div className="card">
          <EmptyState icon="periods" message="No open period yet." hint="Create a period to start tracking your finances.">
            <Link to="/periods" className="btn btn-primary" style={{ marginTop: 8 }}>Go to Workflow</Link>
          </EmptyState>
        </div>
      ) : (
        <>
          <div className="kpi-grid kpi-grid-6">
            <div className="kpi-card">
              <div className="kpi-label">Total Income</div>
              <div className="kpi-value" style={{ color: 'var(--green)', fontSize: 22 }}>{fmtMoney(data.total_income)}</div>
              <div className="kpi-sub">{scopeLabel}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Total Expenses</div>
              <div className="kpi-value" style={{ color: 'var(--red)', fontSize: 22 }}>{fmtMoney(data.total_expenses)}</div>
              <div className="kpi-sub">{scopeLabel}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Net Income</div>
              <div className="kpi-value" style={{ color: kpiColor(data.net_income, 'var(--green)', 'var(--red)'), fontSize: 22 }}>{fmtMoney(data.net_income)}</div>
              <div className="kpi-sub">{scopeLabel}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Total Assets</div>
              <div className="kpi-value" style={{ color: 'var(--accent)', fontSize: 22 }}>{fmtMoney(data.total_assets)}</div>
              <div className="kpi-sub">{scopeLabel}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Net Worth</div>
              <div className="kpi-value" style={{ color: kpiColor(data.net_worth, 'var(--accent)', 'var(--red)'), fontSize: 22 }}>{fmtMoney(data.net_worth)}</div>
              <div className="kpi-sub">{scopeLabel}</div>
            </div>
            {(() => {
              const comp = parseFloat(data.compensation_income)
              const contrib = parseFloat(data.retirement_contributions)
              const pct = comp !== 0 ? (contrib / comp) * 100 : 0
              const color = pct >= 0 ? 'var(--green)' : 'var(--red)'
              return (
                <div className="kpi-card">
                  <div className="kpi-label">Retirement Savings Rate</div>
                  <div className="kpi-value" style={{ color, fontSize: 22 }}>{pct.toFixed(1)}%</div>
                  <div className="kpi-sub">of salary + bonus</div>
                </div>
              )
            })()}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16, marginBottom: 16 }}>
            <div className="card">
              <div className="card-hd"><div><div className="card-title">Income vs Expenses</div><div className="card-sub">by period</div></div></div>
              <div className="card-bd" style={{ padding: '16px 20px' }}>
                {data.period_bars.length ? <canvas ref={ieRef} height={180} /> : <EmptyState message="No data yet." hint="Post journal entries to see charts." />}
              </div>
            </div>
            <div className="card">
              <div className="card-hd"><div><div className="card-title">Net Worth Trend</div><div className="card-sub">cumulative, per period</div></div></div>
              <div className="card-bd" style={{ padding: '16px 20px' }}>
                {data.net_worth_series.length ? <canvas ref={nwRef} height={180} /> : <EmptyState message="No data yet." />}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 16 }}>
            <div className="card">
              <div className="card-hd"><div><div className="card-title">Expenses by Category</div><div className="card-sub">all time · top 8</div></div></div>
              <div className="card-bd" style={{ padding: '16px 20px' }}>
                {data.top_expense_categories.length ? <canvas ref={ecRef} height={260} /> : <EmptyState message="No expenses yet." />}
              </div>
            </div>
            <div className="card">
              <div className="card-hd">
                <div><div className="card-title">Recent Journal Entries</div><div className="card-sub">latest 6 posted</div></div>
                <Link to="/ledger" className="btn btn-ghost btn-sm">View all →</Link>
              </div>
              {data.recent_entries.length ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Description</th>
                      <th>Period</th>
                      <th>Date</th>
                      <th>Type</th>
                      <th className="text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_entries.map((e, i) => (
                      <tr key={i}>
                        <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.description}</td>
                        <td className="color-text3" style={{ fontSize: 12 }}>{e.period_label}</td>
                        <td className="mono color-text3" style={{ fontSize: 12 }}>{e.entry_date}</td>
                        <td><span className="badge badge--parsed" style={{ fontSize: 11 }}>{e.source_type}</span></td>
                        <td className="mono text-right">${parseFloat(e.total_debit).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState icon="journal" message="No entries posted yet." hint="Complete a period workflow to post entries." />
              )}
            </div>
          </div>

          {data.active_period && (
            <div className="card mt-16">
              <div className="card-hd">
                <div>
                  <div className="card-title">Active Period — {fmtPeriod(data.active_period.period_start)}</div>
                  <div className="card-sub">{data.active_period.period_start} → {data.active_period.period_end}</div>
                </div>
                <StatusBadge status={data.active_period.status} />
              </div>
              <div className="card-bd">
                <PeriodStepper period={data.active_period} />
                <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                  <Link to={`/periods/${data.active_period.period_id}/journal`} className="btn btn-primary btn-sm" style={{ flex: 1, justifyContent: 'center' }}>Review Journal</Link>
                  <Link to={`/periods/${data.active_period.period_id}`} className="btn btn-secondary btn-sm" style={{ flex: 1, justifyContent: 'center' }}>Period Detail</Link>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </Layout>
  )
}
