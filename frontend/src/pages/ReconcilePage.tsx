import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchReconcilePage,
  runReconciliation,
  analyzeReconciliation,
  postUnrealizedGl,
  postClosingEntries,
  postEquityRollup,
} from '../api/reconciliation'
import { updatePeriodStatus } from '../api/periods'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import PeriodStepper from '../components/PeriodStepper'
import Banner from '../components/Banner'
import EmptyState from '../components/EmptyState'
import SvgIcon from '../components/SvgIcon'
import { fmtPeriod } from '../utils/format'

function fmtGap(gap: string) {
  const n = parseFloat(gap)
  if (n === 0) return <span style={{ color: 'var(--green)' }}>0.00</span>
  if (Math.abs(n) > 5) return <span style={{ color: 'var(--red)', fontWeight: 600 }}>{n.toFixed(2)}</span>
  return <span style={{ color: 'var(--amber)' }}>{n.toFixed(2)}</span>
}

function fmtSigned(val: string) {
  const n = parseFloat(val)
  if (n < 0) return <span style={{ color: 'var(--red)' }}>({Math.abs(n).toFixed(2)})</span>
  return <>{n.toFixed(2)}</>
}

export default function ReconcilePage() {
  const { periodId } = useParams<{ periodId: string }>()
  const qc = useQueryClient()

  const invalidate = () => qc.invalidateQueries({ queryKey: ['reconcile', periodId] })

  const { data, isLoading, error: loadError } = useQuery({
    queryKey: ['reconcile', periodId],
    queryFn: () => fetchReconcilePage(periodId!),
    staleTime: 30_000,
    enabled: !!periodId,
  })

  const run = useMutation({
    mutationFn: () => runReconciliation(periodId!),
    onSuccess: (d) => qc.setQueryData(['reconcile', periodId], d),
  })

  const analyze = useMutation({
    mutationFn: () => analyzeReconciliation(periodId!),
    onSuccess: (d) => qc.setQueryData(['reconcile', periodId], d),
  })

  const postUnrealized = useMutation({
    mutationFn: (code: number) => postUnrealizedGl(periodId!, code),
    onSuccess: (d) => qc.setQueryData(['reconcile', periodId], d),
  })

  const postClosing = useMutation({
    mutationFn: () => postClosingEntries(periodId!),
    onSuccess: (d) => qc.setQueryData(['reconcile', periodId], d),
  })

  const postEquity = useMutation({
    mutationFn: () => postEquityRollup(periodId!),
    onSuccess: (d) => qc.setQueryData(['reconcile', periodId], d),
  })

  const advanceStatus = useMutation({
    mutationFn: (s: string) => updatePeriodStatus(periodId!, s),
    onSuccess: () => invalidate(),
  })

  if (isLoading || !data) return <Layout><p style={{ color: 'var(--text-3)' }}>Loading…</p></Layout>

  const { period, details, ran, has_gaps, has_non_investment_gaps, analysis, temp_preview, equity_preview } = data
  const canEdit = period.status === 'pending_close'

  return (
    <Layout activePeriod={period}>
      <PageHeader
        title="Reconciliation"
        subtitle={`${fmtPeriod(period.period_start)} · Verify book balances match stated account balances`}
        backTo={`/periods/${periodId}`}
        backLabel={fmtPeriod(period.period_start)}
        badge={<StatusBadge status={period.status} />}
        right={canEdit && (
          <button className="btn btn-primary btn-sm" disabled={run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? 'Running…' : 'Run Reconciliation'}
          </button>
        )}
      />

      <PeriodStepper period={period} />

      {loadError && <Banner variant="red" style={{ marginTop: 16 }}>Failed to load reconciliation data.</Banner>}

      {!ran ? (
        <div className="card mt-16">
          <div className="card-bd" style={{ textAlign: 'center', padding: '36px 24px' }}>
            <p className="color-text2" style={{ marginBottom: 16 }}>
              Click <strong>Run Reconciliation</strong> to compare your journal balances against your stated month-end balances.
            </p>
            {canEdit ? (
              <button className="btn btn-primary" disabled={run.isPending} onClick={() => run.mutate()}>
                {run.isPending ? 'Running…' : 'Run Reconciliation'}
              </button>
            ) : (
              <p className="color-text3" style={{ fontSize: 12 }}>Reconciliation is only available in Pending Close status.</p>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* Results table */}
          <div className="card mt-16">
            <div className="card-hd">
              <div>
                <div className="card-title">Account Balances</div>
                <div className="card-sub">
                  {details.filter((d) => d.status === 'reconciled').length} reconciled ·{' '}
                  {details.filter((d) => d.status !== 'reconciled').length} with gaps
                </div>
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Account</th>
                    <th className="mono" style={{ textAlign: 'right' }}>Beg. Balance</th>
                    <th className="mono" style={{ textAlign: 'right' }}>Net Change</th>
                    <th className="mono" style={{ textAlign: 'right' }}>Computed Ending</th>
                    <th className="mono" style={{ textAlign: 'right' }}>Stated Ending</th>
                    <th className="mono" style={{ textAlign: 'right' }}>Gap</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {details.map((d) => {
                    const gap = parseFloat(d.gap)
                    const bg = d.status === 'reconciled'
                      ? 'rgba(34,197,94,0.06)'
                      : Math.abs(gap) > 5 ? 'rgba(239,68,68,0.06)' : 'rgba(234,179,8,0.06)'
                    return (
                      <tr key={d.recon_id} style={{ background: bg }}>
                        <td>
                          <div style={{ fontSize: 13, fontWeight: 500 }}>{d.account_code} · {d.account_name}</div>
                          {d.is_investment && <div className="color-text3" style={{ fontSize: 11 }}>includes unrealized gains/losses</div>}
                        </td>
                        <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{parseFloat(d.beginning_balance).toFixed(2)}</td>
                        <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>
                          {parseFloat(d.period_net_change) < 0
                            ? <span style={{ color: 'var(--red)' }}>{parseFloat(d.period_net_change).toFixed(2)}</span>
                            : parseFloat(d.period_net_change).toFixed(2)}
                        </td>
                        <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{parseFloat(d.computed_balance).toFixed(2)}</td>
                        <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{parseFloat(d.stated_balance).toFixed(2)}</td>
                        <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{fmtGap(d.gap)}</td>
                        <td>
                          {d.status === 'reconciled' ? (
                            <span className="badge" style={{ background: 'rgba(34,197,94,0.12)', color: '#15803d' }}>
                              <SvgIcon name="check" size={11} /> Reconciled
                            </span>
                          ) : (
                            <span className="badge badge--staged">Pending</span>
                          )}
                        </td>
                        <td>
                          {d.is_investment && d.status !== 'reconciled' && canEdit && (
                            <button
                              className="btn btn-secondary btn-sm"
                              disabled={postUnrealized.isPending}
                              onClick={() => postUnrealized.mutate(d.account_code)}
                              title="Post an adjusting entry to account for unrealized market gain or loss"
                            >
                              Post Unrealized G/L
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {has_non_investment_gaps && !analysis && canEdit && (
            <Banner variant="accent" style={{ marginTop: 16 }}>
              Some non-investment accounts have unexplained gaps. Use AI analysis to identify likely causes.
              <button
                className="btn btn-secondary btn-sm"
                style={{ marginLeft: 'auto' }}
                disabled={analyze.isPending}
                onClick={() => analyze.mutate()}
              >
                <SvgIcon name="brain" size={13} />
                {analyze.isPending ? 'Analyzing…' : 'Analyze with AI'}
              </button>
            </Banner>
          )}

          {analysis && (
            <div className="card mt-16">
              <div className="card-hd"><div className="card-title">AI Analysis</div></div>
              <div className="card-bd-sm">
                <p style={{ marginBottom: 16, color: 'var(--text-2)' }}>{analysis.overall_summary}</p>
                {analysis.accounts.map((acctAnalysis) => {
                  const detail = details.find((d) => d.account_code === acctAnalysis.account_code)
                  return (
                    <div key={acctAnalysis.account_code} style={{ border: '1px solid var(--border)', borderRadius: 6, padding: 14, marginBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <span style={{ fontWeight: 600, fontSize: 13 }}>
                          {detail?.account_code ?? acctAnalysis.account_code} · {detail?.account_name ?? acctAnalysis.account_code}
                        </span>
                        <span className={`badge ${acctAnalysis.severity === 'high' ? 'badge--pending' : acctAnalysis.severity === 'medium' ? 'badge--staged' : 'badge--complete'}`}>
                          {acctAnalysis.severity.charAt(0).toUpperCase() + acctAnalysis.severity.slice(1)}
                        </span>
                      </div>
                      {acctAnalysis.likely_causes.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-3)', marginBottom: 4 }}>Likely Causes</div>
                          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--text-2)' }}>
                            {acctAnalysis.likely_causes.map((c, i) => <li key={i}>{c}</li>)}
                          </ul>
                        </div>
                      )}
                      {acctAnalysis.suggested_actions.length > 0 && (
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-3)', marginBottom: 4 }}>Suggested Actions</div>
                          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--text-2)' }}>
                            {acctAnalysis.suggested_actions.map((a, i) => <li key={i}>{a}</li>)}
                          </ul>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {has_gaps && (
            <Banner variant="amber" style={{ marginTop: 16 }}>
              <strong>{details.filter((d) => d.status !== 'reconciled').length} account(s) have unresolved gaps.</strong>{' '}
              Post Unrealized G/L entries for investment accounts, or add adjusting journal entries for others, then re-run reconciliation.
            </Banner>
          )}
        </>
      )}

      {/* Temporary Accounts */}
      {temp_preview && (
        <div className="card mt-16">
          <div className="card-hd">
            <div>
              <div className="card-title">Temporary Accounts — Closing Entries</div>
              <div className="card-sub">Income and expense accounts to be zeroed at period close</div>
            </div>
            {!temp_preview.closing_posted && canEdit && (temp_preview.income_accounts.length > 0 || temp_preview.expense_accounts.length > 0) && (
              <button className="btn btn-primary btn-sm" disabled={postClosing.isPending} onClick={() => postClosing.mutate()}>
                {postClosing.isPending ? 'Posting…' : 'Post Closing Entries'}
              </button>
            )}
          </div>

          {temp_preview.closing_posted && (
            <Banner variant="green" style={{ margin: '0 16px 12px' }}>Closing entries posted</Banner>
          )}

          {(temp_preview.income_accounts.length > 0 || temp_preview.expense_accounts.length > 0) ? (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr><th>Account</th><th>Type</th><th className="mono" style={{ textAlign: 'right' }}>Balance to Close</th></tr>
                </thead>
                <tbody>
                  {temp_preview.income_accounts.map((a) => (
                    <tr key={a.account_code}>
                      <td style={{ fontSize: 13, fontWeight: 500 }}>{a.account_code} · {a.account_name}</td>
                      <td><span className="badge" style={{ background: 'rgba(34,197,94,0.12)', color: '#15803d' }}>Income</span></td>
                      <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{fmtSigned(a.period_balance)}</td>
                    </tr>
                  ))}
                  {temp_preview.expense_accounts.map((a) => (
                    <tr key={a.account_code}>
                      <td style={{ fontSize: 13, fontWeight: 500 }}>{a.account_code} · {a.account_name}</td>
                      <td><span className="badge badge--staged">Expense</span></td>
                      <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{fmtSigned(a.period_balance)}</td>
                    </tr>
                  ))}
                  <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 600 }}>
                    <td colSpan={2} style={{ fontSize: 13 }}>Net Income / (Loss) → 300103</td>
                    <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{fmtSigned(temp_preview.net_income)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <div className="card-bd" style={{ textAlign: 'center', padding: 24 }}>
              <p className="color-text3" style={{ fontSize: 13 }}>No income or expense activity this period.</p>
            </div>
          )}
        </div>
      )}

      {/* Equity Rollup */}
      {equity_preview && (
        <div className="card mt-16">
          <div className="card-hd">
            <div>
              <div className="card-title">Owner's Equity Rollup</div>
              <div className="card-sub">Transfer net income from 300103 to 300102 Prior Period Net Worth</div>
            </div>
            {!equity_preview.rollup_posted && parseFloat(equity_preview.net_income_balance) !== 0 && canEdit && (
              <button className="btn btn-primary btn-sm" disabled={postEquity.isPending} onClick={() => postEquity.mutate()}>
                {postEquity.isPending ? 'Posting…' : 'Post Equity Rollup'}
              </button>
            )}
          </div>

          {equity_preview.rollup_posted && (
            <Banner variant="green" style={{ margin: '0 16px 12px' }}>
              Equity rollup posted — 300103 zeroed, balance transferred to 300102
            </Banner>
          )}

          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr><th>Account</th><th className="mono" style={{ textAlign: 'right' }}>Balance</th><th>Action</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ fontSize: 13, fontWeight: 500 }}>300103 · Current Period Net Income</td>
                  <td className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{fmtSigned(equity_preview.net_income_balance)}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-3)' }}>→ DR 300103</td>
                </tr>
                <tr>
                  <td style={{ fontSize: 13, fontWeight: 500 }}>300102 · Prior Period Net Worth</td>
                  <td className="mono" style={{ textAlign: 'right', fontSize: 13, color: 'var(--text-3)' }}>receives transfer</td>
                  <td style={{ fontSize: 12, color: 'var(--text-3)' }}>→ CR 300102</td>
                </tr>
              </tbody>
            </table>
          </div>

          {!equity_preview.rollup_posted && parseFloat(equity_preview.net_income_balance) === 0 && (
            <div className="card-bd" style={{ paddingTop: 0 }}>
              <p className="color-text3" style={{ fontSize: 12 }}>Post closing entries first to populate 300103.</p>
            </div>
          )}
        </div>
      )}

      {/* Close Period */}
      {canEdit && (
        <div className="card mt-16">
          <div className="card-hd">
            <div>
              <div className="card-title">Close Period</div>
              <div className="card-sub">Lock the period once all gaps are resolved</div>
            </div>
          </div>
          <div className="card-bd">
            <button
              className={`btn ${has_gaps ? 'btn-secondary' : 'btn-primary'}`}
              disabled={advanceStatus.isPending}
              onClick={() => { if (window.confirm('Close this period? This cannot be undone without reopening.')) advanceStatus.mutate('closed') }}
            >
              {advanceStatus.isPending ? 'Closing…' : 'Close Period →'}
            </button>
            {has_gaps && (
              <p className="color-text3" style={{ fontSize: 12, marginTop: 8 }}>
                You may close with gaps — they will remain in the ledger and can be reviewed after reopening.
              </p>
            )}
          </div>
        </div>
      )}
    </Layout>
  )
}
