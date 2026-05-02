import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchLedger } from '../api/ledger'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import EmptyState from '../components/EmptyState'
import { fmtPeriod, fmtDate } from '../utils/format'

function fmtAmt(v: string) {
  const n = parseFloat(v)
  return n > 0 ? `$${n.toFixed(2)}` : '—'
}

export default function LedgerPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['ledger'],
    queryFn: fetchLedger,
    staleTime: 30_000,
  })

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const toggle = (id: string) => setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }))

  return (
    <Layout>
      <PageHeader title="Ledger" subtitle="All journal entries, grouped by period" />

      {isLoading && <p style={{ color: 'var(--text-3)' }}>Loading…</p>}
      {error && <p style={{ color: 'var(--red)' }}>Failed to load ledger.</p>}

      {!isLoading && !error && !data?.periods.length && (
        <div className="card">
          <EmptyState icon="journal" message="No periods yet." hint="Create a period under Workflow to begin recording entries." />
        </div>
      )}

      {data?.periods.map((period) => {
        const entries = data.entries_by_period[period.period_id] ?? []
        const isCollapsed = collapsed[period.period_id]

        return (
          <div key={period.period_id} className="card mb-16">
            <div className="card-hd">
              <div>
                <div className="page-title-row" style={{ gap: 10 }}>
                  <div className="card-title">{fmtPeriod(period.period_start)}</div>
                  <StatusBadge status={period.status} />
                </div>
                <div className="card-sub">
                  {period.period_start} → {period.period_end} · {entries.length}{' '}
                  {entries.length === 1 ? 'entry' : 'entries'}
                </div>
              </div>
              <div className="card-hd-right" style={{ gap: 8 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => toggle(period.period_id)}
                  aria-expanded={!isCollapsed}
                >
                  <svg
                    width={14}
                    height={14}
                    viewBox="0 0 14 14"
                    style={{ transition: 'transform .2s', transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}
                  >
                    <path d="M2 4.5 7 9.5 12 4.5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span>{isCollapsed ? 'Expand' : 'Collapse'}</span>
                </button>
                <Link to={`/periods/${period.period_id}/journal`} className="btn btn-ghost btn-sm">
                  Open Journal →
                </Link>
              </div>
            </div>

            {!isCollapsed && (
              entries.length ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px 20px' }}>
                  {entries.map((entry) => {
                    const totalDebit = entry.lines.reduce((s, l) => s + parseFloat(l.debit_amount), 0)
                    const totalCredit = entry.lines.reduce((s, l) => s + parseFloat(l.credit_amount), 0)
                    return (
                      <div key={entry.entry_id} className="card" style={{ margin: 0 }}>
                        <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <span style={{ fontWeight: 600, fontSize: 13.5 }}>{entry.description}</span>
                            <span className="mono color-text3" style={{ fontSize: 12, marginLeft: 12 }}>{fmtDate(entry.entry_date)}</span>
                          </div>
                          <span className="badge badge--parsed">{entry.source_type}</span>
                        </div>
                        {entry.lines.length > 0 && (
                          <table className="data-table" style={{ tableLayout: 'fixed' }}>
                            <thead>
                              <tr>
                                <th>Account</th>
                                <th>Memo</th>
                                <th className="text-right" style={{ width: 130 }}>Debit</th>
                                <th className="text-right" style={{ width: 130 }}>Credit</th>
                              </tr>
                            </thead>
                            <tbody>
                              {entry.lines.map((line) => {
                                const acct = data.accounts_by_code[line.account_code]
                                return (
                                  <tr key={line.line_id}>
                                    <td className="mono" style={{ fontSize: 13 }}>
                                      {line.account_code}{acct ? ` · ${acct.account_name}` : ''}
                                    </td>
                                    <td className="color-text3" style={{ fontSize: 12 }}>{line.memo ?? ''}</td>
                                    <td className="mono text-right" style={{ color: parseFloat(line.debit_amount) > 0 ? 'var(--text-1)' : 'var(--text-3)' }}>
                                      {fmtAmt(line.debit_amount)}
                                    </td>
                                    <td className="mono text-right" style={{ color: parseFloat(line.credit_amount) > 0 ? 'var(--text-1)' : 'var(--text-3)' }}>
                                      {fmtAmt(line.credit_amount)}
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                            <tfoot>
                              <tr>
                                <td className="color-text3" style={{ fontSize: 12 }} colSpan={2}>Total</td>
                                <td className="mono text-right fw-600">${totalDebit.toFixed(2)}</td>
                                <td className="mono text-right fw-600">${totalCredit.toFixed(2)}</td>
                              </tr>
                            </tfoot>
                          </table>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <p className="empty-msg">No entries posted yet.</p>
                  <p className="empty-hint">Approve transactions and post them, or upload an opening-balances file.</p>
                </div>
              )
            )}
          </div>
        )
      })}
    </Layout>
  )
}
