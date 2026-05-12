import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTransactions } from '../api/transactions'
import { fetchPeriodDetail } from '../api/periods'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import EmptyState from '../components/EmptyState'
import ConfidencePill from '../components/ConfidencePill'
import { fmtPeriod } from '../utils/format'

export default function TransactionsPage() {
  const { periodId } = useParams<{ periodId: string }>()

  const detailQ = useQuery({
    queryKey: ['period', periodId],
    queryFn: () => fetchPeriodDetail(periodId!),
    staleTime: 30_000,
    enabled: !!periodId,
  })

  const txnsQ = useQuery({
    queryKey: ['transactions', periodId],
    queryFn: () => fetchTransactions(periodId!),
    staleTime: 30_000,
    enabled: !!periodId,
  })

  const period = detailQ.data?.period
  const accountsByCode = Object.fromEntries((detailQ.data?.accounts ?? []).map((a) => [a.account_code, a]))
  const transactions = txnsQ.data ?? []

  return (
    <Layout activePeriod={period}>
      <PageHeader
        title="Transactions"
        subtitle={period ? `${fmtPeriod(period.period_start)} · All raw transactions` : undefined}
        backTo={`/periods/${periodId}`}
        backLabel={period ? fmtPeriod(period.period_start) : 'Period'}
        badge={period && <StatusBadge status={period.status} />}
      />

      {detailQ.isLoading || txnsQ.isLoading ? (
        <p className="color-text3">Loading…</p>
      ) : (
        <div className="card">
          <div className="card-hd">
            <div className="card-title">Raw Transactions</div>
            <span className="color-text3" style={{ fontSize: 12 }}>{transactions.length} total</span>
          </div>

          {transactions.length === 0 ? (
            <EmptyState icon="file" message="No transactions yet." hint="Parse a document on the period page to stage transactions here." />
          ) : (
            <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th className="text-right">Amount</th>
                  <th>Suggested Account</th>
                  <th>Confidence</th>
                  <th>Flags</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => {
                  const n = parseFloat(txn.amount)
                  const acct = txn.suggested_account_code ? accountsByCode[txn.suggested_account_code] : null
                  return (
                    <tr key={txn.raw_txn_id}>
                      <td className="mono color-text3" style={{ fontSize: 12.5 }}>{txn.txn_date}</td>
                      <td style={{ fontSize: 13 }}>{txn.description}</td>
                      <td className="mono text-right fw-600" style={{ fontSize: 13.5, color: n < 0 ? 'var(--red)' : 'var(--green)' }}>
                        {n < 0 ? `−$${Math.abs(n).toFixed(2)}` : `$${n.toFixed(2)}`}
                      </td>
                      <td className="mono color-text2" style={{ fontSize: 12.5 }}>
                        {txn.suggested_account_code
                          ? `${txn.suggested_account_code}${acct ? ` · ${acct.account_name}` : ''}`
                          : '—'}
                      </td>
                      <td><ConfidencePill confidence={txn.classifier_confidence} /></td>
                      <td style={{ fontSize: 11.5 }}>
                        {txn.is_flagged && <span className="color-amber">⚠ flagged</span>}
                        {txn.is_duplicate && <span className="color-text3"> ⊕ dup</span>}
                      </td>
                      <td><StatusBadge status={txn.status} /></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            </div>
          )}
        </div>
      )}
    </Layout>
  )
}
