import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPeriods, createPeriod } from '../api/periods'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import EmptyState from '../components/EmptyState'
import Banner from '../components/Banner'
import SvgIcon from '../components/SvgIcon'

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']

export default function PeriodsListPage() {
  const qc = useQueryClient()
  const [year, setYear] = useState<string>(String(new Date().getFullYear()))
  const [month, setMonth] = useState<string>(String(new Date().getMonth() + 1))
  const [error, setError] = useState<string | null>(null)

  const { data: periods = [], isLoading } = useQuery({
    queryKey: ['periods'],
    queryFn: fetchPeriods,
    staleTime: 30_000,
  })

  const create = useMutation({
    mutationFn: () => createPeriod({ year: parseInt(year, 10), month: parseInt(month, 10) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['periods'] })
      setError(null)
    },
    onError: (e: Error) => setError(e.message),
  })

  return (
    <Layout>
      <PageHeader title="Workflow" subtitle="Create a period and walk through the guided close process" />

      {error && (
        <Banner variant="red" style={{ marginBottom: 16 }}>
          {error}
        </Banner>
      )}

      <div className="card mb-16">
        <div className="card-hd">
          <div className="card-title">Create New Period</div>
        </div>
        <div className="card-bd-sm">
          <div className="form-row">
            <div className="field-group">
              <label htmlFor="year" className="field-label">Year</label>
              <input
                id="year"
                type="number"
                min={1900}
                max={2100}
                placeholder="2026"
                className="inp"
                style={{ width: 90 }}
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </div>
            <div className="field-group">
              <label htmlFor="month" className="field-label">Month</label>
              <select id="month" className="inp" style={{ width: 150 }} value={month} onChange={(e) => setMonth(e.target.value)}>
                {MONTHS.map((name, i) => (
                  <option key={i + 1} value={i + 1}>{name}</option>
                ))}
              </select>
            </div>
            <div className="field-group">
              <div style={{ height: 19 }} />
              <button
                className="btn btn-primary"
                disabled={create.isPending}
                onClick={() => create.mutate()}
              >
                <SvgIcon name="plus" size={13} />
                {create.isPending ? 'Creating…' : 'Create Period'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-hd">
          <div className="card-title">All Periods</div>
          <span className="color-text3" style={{ fontSize: 12 }}>{periods.length} total</span>
        </div>

        {isLoading && <p style={{ color: 'var(--text-3)', padding: '16px 20px' }}>Loading…</p>}

        {!isLoading && !periods.length && (
          <EmptyState icon="periods" message="No periods yet." hint="Create your first accounting period above to begin." />
        )}

        {periods.length > 0 && (
          <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Date Range</th>
                <th>Status</th>
                <th>Created</th>
                <th>Closed</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {periods.map((p) => (
                <tr key={p.period_id}>
                  <td style={{ fontWeight: 600 }}>{p.period_start.slice(0, 7)}</td>
                  <td className="mono color-text3" style={{ fontSize: 12 }}>
                    {p.period_start} → {p.period_end}
                  </td>
                  <td><StatusBadge status={p.status} /></td>
                  <td className="color-text3" style={{ fontSize: 12 }}>{p.created_at.slice(0, 10)}</td>
                  <td className="color-text3" style={{ fontSize: 12 }}>{p.closed_at ? p.closed_at.slice(0, 10) : '—'}</td>
                  <td>
                    <Link to={`/periods/${p.period_id}`} className="color-accent fw-600" style={{ fontSize: 13 }}>
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </Layout>
  )
}
