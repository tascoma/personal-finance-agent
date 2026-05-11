import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Chart,
  BarElement, LineElement, PointElement, ArcElement,
  BarController, LineController, DoughnutController,
  CategoryScale, LinearScale,
  Tooltip, Legend, Filler,
  type Plugin,
} from 'chart.js'
import { fetchDashboard } from '../api/dashboard'
import { fetchPeriods } from '../api/periods'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import StatusBadge from '../components/StatusBadge'
import PeriodStepper from '../components/PeriodStepper'
import SvgIcon from '../components/SvgIcon'
import Tabs from '../components/Tabs'
import { fmtPeriod, fmtMoney } from '../utils/format'

Chart.register(BarElement, LineElement, PointElement, ArcElement, BarController, LineController, DoughnutController, CategoryScale, LinearScale, Tooltip, Legend, Filler)

function kpiColor(val: string, positive: string, negative: string) {
  return parseFloat(val) >= 0 ? positive : negative
}


type DashboardTab = 'overview' | 'insights'

export default function DashboardPage() {
  const [selectedYear, setSelectedYear] = useState<number | null>(null)
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<DashboardTab>('overview')
  const [trendScale, setTrendScale] = useState<'all' | 'under1k'>('all')
  const [showLifestyleTip, setShowLifestyleTip] = useState(false)
  const [showDeltaTip, setShowDeltaTip] = useState(false)

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
  const stackRef = useRef<HTMLCanvasElement>(null)
  const donutRef = useRef<HTMLCanvasElement>(null)
  const compRef = useRef<HTMLCanvasElement>(null)
  const chartRefs = useRef<Chart[]>([])
  const trendChartRef = useRef<Chart | null>(null)

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

    const catColors = [red, amber, accent, green, '#a78bfa', '#38bdf8', '#fb923c', '#34d399']

    if (ecRef.current && data.top_expense_categories.length) {
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

    if (donutRef.current && data.top_expense_categories.length) {
      const totalExpenses = parseFloat(data.total_expenses)
      const arcPctLabels: Plugin<'doughnut'> = {
        id: 'arcPctLabels',
        afterDatasetsDraw(chart) {
          const ctx = chart.ctx
          const meta = chart.getDatasetMeta(0)
          const values = chart.data.datasets[0].data as number[]
          meta.data.forEach((arc, i) => {
            const pct = totalExpenses > 0 ? (values[i] / totalExpenses) * 100 : 0
            if (pct < 4) return
            const pos = (arc as unknown as { tooltipPosition: (f: boolean) => { x: number; y: number } }).tooltipPosition(true)
            ctx.save()
            ctx.fillStyle = '#fff'
            ctx.font = 'bold 11px DM Sans, sans-serif'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillText(`${pct.toFixed(0)}%`, pos.x, pos.y)
            ctx.restore()
          })
        },
      }
      chartRefs.current.push(new Chart<'doughnut'>(donutRef.current, {
        type: 'doughnut',
        data: {
          labels: data.top_expense_categories.map((d) => d.category),
          datasets: [{
            data: data.top_expense_categories.map((d) => parseFloat(d.amount)),
            backgroundColor: data.top_expense_categories.map((_, i) => catColors[i % catColors.length] + 'cc'),
            borderColor: data.top_expense_categories.map((_, i) => catColors[i % catColors.length]),
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false, cutout: '60%',
          plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
            tooltip: { callbacks: { label: (ctx) => {
              const amt = Number(ctx.parsed ?? 0)
              const pct = totalExpenses > 0 ? (amt / totalExpenses) * 100 : 0
              return ` ${ctx.label}: $${amt.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${pct.toFixed(1)}%)`
            } } },
          },
        },
        plugins: [arcPctLabels],
      }))
    }

    if (compRef.current && data.top_expense_categories.length) {
      const comp = parseFloat(data.compensation_income)
      const pcts = data.top_expense_categories.map((d) => comp > 0 ? (parseFloat(d.amount) / comp) * 100 : 0)
      const barPctLabels: Plugin<'bar'> = {
        id: 'barPctLabels',
        afterDatasetsDraw(chart) {
          const ctx = chart.ctx
          const meta = chart.getDatasetMeta(0)
          meta.data.forEach((bar, i) => {
            const pct = pcts[i]
            if (pct <= 0) return
            const { x, y } = bar as unknown as { x: number; y: number }
            ctx.save()
            ctx.fillStyle = text3
            ctx.font = 'bold 11px DM Sans, sans-serif'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'bottom'
            ctx.fillText(`${pct.toFixed(1)}%`, x, y - 4)
            ctx.restore()
          })
        },
      }
      chartRefs.current.push(new Chart<'bar'>(compRef.current, {
        type: 'bar',
        data: {
          labels: data.top_expense_categories.map((d) => d.category),
          datasets: [{
            label: '% of salary + bonus',
            data: pcts,
            backgroundColor: data.top_expense_categories.map((_, i) => catColors[i % catColors.length] + 'bb'),
            borderColor: data.top_expense_categories.map((_, i) => catColors[i % catColors.length]),
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (ctx) => {
              const idx = ctx.dataIndex
              const amt = parseFloat(data.top_expense_categories[idx].amount)
              return ` ${(ctx.parsed.y ?? 0).toFixed(1)}% · $${amt.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
            } } },
          },
          scales: {
            x: { grid: { display: false } },
            y: { ticks: { callback: (v) => `${Number(v).toFixed(0)}%` }, grace: '10%' },
          },
        },
        plugins: [barPctLabels],
      }))
    }

    return () => { chartRefs.current.forEach((c) => c.destroy()); chartRefs.current = [] }
  }, [data, activeTab])

  useEffect(() => {
    if (!data || activeTab !== 'insights') return
    if (!stackRef.current || !data.expense_category_series.length) return

    trendChartRef.current?.destroy()

    const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
    const red    = isDark ? '#f87171' : '#dc2626'
    const accent = isDark ? '#56c8f0' : '#0284c7'
    const green  = isDark ? '#4ade80' : '#16a34a'
    const amber  = isDark ? '#fbbf24' : '#b45309'
    const catColors = [red, amber, accent, green, '#a78bfa', '#38bdf8', '#fb923c', '#34d399']
    const moneyTick = (v: number | string) => `$${Number(v).toLocaleString()}`

    const periodLabels = [...new Set(data.expense_category_series.map((p) => p.period_label))]
    const allCategories = [...new Set(data.expense_category_series.map((p) => p.category))]
    const seriesByKey = new Map<string, number>()
    for (const row of data.expense_category_series) {
      seriesByKey.set(`${row.period_label}|${row.category}`, parseFloat(row.amount))
    }
    const categories = trendScale === 'under1k'
      ? allCategories.filter((cat) => Math.max(...periodLabels.map((pl) => seriesByKey.get(`${pl}|${cat}`) ?? 0)) < 1000)
      : allCategories
    const datasets = categories.map((cat) => {
      const color = catColors[allCategories.indexOf(cat) % catColors.length]
      return {
        label: cat,
        data: periodLabels.map((pl) => seriesByKey.get(`${pl}|${cat}`) ?? 0),
        borderColor: color,
        backgroundColor: color,
        borderWidth: 1.5,
        pointRadius: 2,
        fill: false,
        tension: 0.3,
      }
    })
    trendChartRef.current = new Chart(stackRef.current, {
      type: 'line',
      data: { labels: periodLabels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } }, tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label}: $${(ctx.parsed.y ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}` } } },
        scales: { x: { grid: { display: false } }, y: { ticks: { callback: moneyTick } } },
      },
    })

    return () => { trendChartRef.current?.destroy(); trendChartRef.current = null }
  }, [data, activeTab, trendScale])

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
          <Tabs
            tabs={[
              { key: 'overview', label: 'Overview' },
              { key: 'insights', label: 'Expense Insights' },
            ]}
            active={activeTab}
            onChange={(k) => setActiveTab(k as DashboardTab)}
          />

          {activeTab === 'overview' && (
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

          {activeTab === 'insights' && (() => {
            const comp = parseFloat(data.compensation_income)
            const lifestyle = parseFloat(data.lifestyle_expenses)
            const lifestylePct = comp !== 0 ? (lifestyle / comp) * 100 : 0
            const lifestyleColor = lifestylePct > 30 ? 'var(--red)' : lifestylePct > 20 ? 'var(--amber, #b45309)' : 'var(--green)'

            const totalExp = parseFloat(data.total_expenses)
            const totalInc = parseFloat(data.total_income)
            const avgExpPerPeriod = data.period_count > 0 ? totalExp / data.period_count : 0
            const expToIncomePct = totalInc > 0 ? (totalExp / totalInc) * 100 : 0
            const topCat = data.top_expense_categories[0]
            const topCatPct = totalExp > 0 && topCat ? (parseFloat(topCat.amount) / totalExp) * 100 : 0

            const bars = data.period_bars
            const lastBar = bars[bars.length - 1]
            const prevBar = bars[bars.length - 2]
            const periodDeltaPct = prevBar && lastBar && prevBar.expenses
              ? ((parseFloat(lastBar.expenses) - parseFloat(prevBar.expenses)) / parseFloat(prevBar.expenses)) * 100
              : null
            const deltaColor = periodDeltaPct == null ? 'var(--text2)' : periodDeltaPct > 0 ? 'var(--red)' : 'var(--green)'

            return (
              <>
                <div className="kpi-grid kpi-grid-6">
                  <div
                    className="kpi-card"
                    style={{ cursor: 'help', position: 'relative' }}
                    onMouseEnter={() => setShowLifestyleTip(true)}
                    onMouseLeave={() => setShowLifestyleTip(false)}
                  >
                    <div className="kpi-label">Lifestyle Spending Rate <span style={{ opacity: 0.5 }}>ⓘ</span></div>
                    <div className="kpi-value" style={{ color: lifestyleColor, fontSize: 22 }}>{lifestylePct.toFixed(1)}%</div>
                    <div className="kpi-sub">of salary + bonus</div>
                    {showLifestyleTip && (
                      <div
                        style={{
                          position: 'absolute',
                          top: 'calc(100% + 8px)',
                          left: 0,
                          zIndex: 50,
                          minWidth: 240,
                          padding: '10px 12px',
                          background: 'var(--bg2, #1a2733)',
                          color: 'var(--text1, #e6f1f8)',
                          border: '1px solid var(--border, rgba(86,200,240,0.15))',
                          borderRadius: 6,
                          fontSize: 12,
                          lineHeight: 1.5,
                          boxShadow: '0 6px 20px rgba(0,0,0,0.35)',
                          pointerEvents: 'none',
                        }}
                      >
                        <div style={{ fontWeight: 600, marginBottom: 4 }}>Lifestyle (numerator)</div>
                        <div style={{ opacity: 0.85 }}>Travel · Entertainment · Hobbies & Recreation · Electronics & Technology · Dining Out · Alcohol</div>
                        <div style={{ fontWeight: 600, marginTop: 8, marginBottom: 2 }}>÷ Salary + Bonus (denominator)</div>
                      </div>
                    )}
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-label">Lifestyle Spending</div>
                    <div className="kpi-value" style={{ color: 'var(--red)', fontSize: 22 }}>{fmtMoney(data.lifestyle_expenses)}</div>
                    <div className="kpi-sub">{scopeLabel}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-label">Avg Expenses / Period</div>
                    <div className="kpi-value" style={{ color: 'var(--red)', fontSize: 22 }}>{fmtMoney(String(avgExpPerPeriod))}</div>
                    <div className="kpi-sub">{data.period_count} closed period{data.period_count !== 1 ? 's' : ''}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-label">Expense / Income</div>
                    <div className="kpi-value" style={{ color: expToIncomePct > 100 ? 'var(--red)' : expToIncomePct > 80 ? 'var(--amber, #b45309)' : 'var(--green)', fontSize: 22 }}>{expToIncomePct.toFixed(1)}%</div>
                    <div className="kpi-sub">spent vs earned</div>
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-label">Top Category</div>
                    <div className="kpi-value" style={{ color: 'var(--accent)', fontSize: 16, lineHeight: 1.2 }} title={topCat?.category ?? ''}>
                      {topCat ? topCat.category : '—'}
                    </div>
                    <div className="kpi-sub">{topCat ? `${fmtMoney(topCat.amount)} · ${topCatPct.toFixed(0)}% of expenses` : ''}</div>
                  </div>
                  <div
                    className="kpi-card"
                    style={{ cursor: prevBar && lastBar ? 'help' : 'default', position: 'relative' }}
                    onMouseEnter={() => setShowDeltaTip(true)}
                    onMouseLeave={() => setShowDeltaTip(false)}
                  >
                    <div className="kpi-label">
                      Expenses Δ vs Prior {prevBar && lastBar && <span style={{ opacity: 0.5 }}>ⓘ</span>}
                    </div>
                    <div className="kpi-value" style={{ color: deltaColor, fontSize: 22 }}>
                      {periodDeltaPct == null ? '—' : `${periodDeltaPct >= 0 ? '+' : ''}${periodDeltaPct.toFixed(1)}%`}
                    </div>
                    <div className="kpi-sub">{prevBar && lastBar ? `${prevBar.period_label} → ${lastBar.period_label}` : 'needs 2 periods'}</div>
                    {showDeltaTip && prevBar && lastBar && (() => {
                      const prevAmt = parseFloat(prevBar.expenses)
                      const lastAmt = parseFloat(lastBar.expenses)
                      const diff = lastAmt - prevAmt
                      return (
                        <div
                          style={{
                            position: 'absolute',
                            top: 'calc(100% + 8px)',
                            right: 0,
                            zIndex: 50,
                            minWidth: 220,
                            padding: '10px 12px',
                            background: 'var(--bg2, #1a2733)',
                            color: 'var(--text1, #e6f1f8)',
                            border: '1px solid var(--border, rgba(86,200,240,0.15))',
                            borderRadius: 6,
                            fontSize: 12,
                            lineHeight: 1.5,
                            boxShadow: '0 6px 20px rgba(0,0,0,0.35)',
                            pointerEvents: 'none',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                            <span style={{ opacity: 0.7 }}>{prevBar.period_label}</span>
                            <span className="mono">{fmtMoney(prevBar.expenses)}</span>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                            <span style={{ opacity: 0.7 }}>{lastBar.period_label}</span>
                            <span className="mono">{fmtMoney(lastBar.expenses)}</span>
                          </div>
                          <div style={{ borderTop: '1px solid var(--border, rgba(86,200,240,0.15))', marginTop: 6, paddingTop: 6, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                            <span style={{ fontWeight: 600 }}>Change</span>
                            <span className="mono" style={{ color: deltaColor, fontWeight: 600 }}>
                              {diff >= 0 ? '+' : ''}{fmtMoney(String(diff))}
                            </span>
                          </div>
                        </div>
                      )
                    })()}
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16, marginTop: 16 }}>
                  <div className="card">
                    <div className="card-hd">
                      <div><div className="card-title">Expense Trendlines</div><div className="card-sub">by sub-category · closed periods</div></div>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button
                          className={`btn btn-sm ${trendScale === 'all' ? 'btn-primary' : 'btn-ghost'}`}
                          onClick={() => setTrendScale('all')}
                        >
                          All
                        </button>
                        <button
                          className={`btn btn-sm ${trendScale === 'under1k' ? 'btn-primary' : 'btn-ghost'}`}
                          onClick={() => setTrendScale('under1k')}
                        >
                          Under $1k
                        </button>
                      </div>
                    </div>
                    <div className="card-bd" style={{ padding: '16px 20px' }}>
                      {data.expense_category_series.length
                        ? <div style={{ height: 260 }}><canvas ref={stackRef} /></div>
                        : <EmptyState message="No expenses yet." hint="Close a period to see category trends." />}
                    </div>
                  </div>
                  <div className="card">
                    <div className="card-hd"><div><div className="card-title">Expense Mix</div><div className="card-sub">top 8 · {scopeLabel}</div></div></div>
                    <div className="card-bd" style={{ padding: '16px 20px' }}>
                      {data.top_expense_categories.length
                        ? <div style={{ height: 260 }}><canvas ref={donutRef} /></div>
                        : <EmptyState message="No expenses yet." />}
                    </div>
                  </div>
                </div>

                <div className="card mt-16">
                  <div className="card-hd"><div><div className="card-title">Category Spend vs Compensation</div><div className="card-sub">each sub-category as % of salary + bonus · top 8</div></div></div>
                  <div className="card-bd" style={{ padding: '16px 20px' }}>
                    {data.top_expense_categories.length && parseFloat(data.compensation_income) > 0
                      ? <div style={{ height: 220 }}><canvas ref={compRef} /></div>
                      : <EmptyState message="No data yet." hint="Needs both expenses and compensation income." />}
                  </div>
                </div>

              </>
            )
          })()}
        </>
      )}
    </Layout>
  )
}
