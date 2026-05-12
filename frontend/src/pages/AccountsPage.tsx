import { useQuery } from '@tanstack/react-query'
import { fetchAccounts } from '../api/accounts'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import StatusBadge from '../components/StatusBadge'
import type { Account } from '../types'

const TYPE_ORDER = ['Asset', 'Liability', 'Equity', 'Income', 'Expense', 'Memo Asset*']
const TYPE_LABELS: Record<string, string> = {
  Asset: 'Assets',
  Liability: 'Liabilities',
  Equity: 'Equity',
  Income: 'Income',
  Expense: 'Expenses',
  'Memo Asset*': 'Memo (Off-Balance-Sheet)',
}

export default function AccountsPage() {
  const { data: accounts = [], isLoading, error } = useQuery({
    queryKey: ['accounts'],
    queryFn: fetchAccounts,
    staleTime: 30_000,
  })

  const grouped = accounts.reduce<Record<string, Account[]>>((acc, a) => {
    ;(acc[a.account_type] ??= []).push(a)
    return acc
  }, {})

  return (
    <Layout>
      <PageHeader title="Chart of Accounts" subtitle="All accounts in your personal ledger" />

      {isLoading && <p className="color-text3">Loading…</p>}
      {error && <p className="color-red">Failed to load accounts.</p>}

      {!isLoading && !error && (
        <>
          <div className="type-pills">
            {TYPE_ORDER.map((t) => {
              const accts = grouped[t]
              if (!accts?.length) return null
              return (
                <div key={t} className="type-pill">
                  <span className={`type-dot type-dot--${t}`} />
                  <span className="type-name">{TYPE_LABELS[t]}</span>
                  <span className={`type-count type-count--${t}`}>{accts.length}</span>
                </div>
              )
            })}
          </div>

          {TYPE_ORDER.map((t) => {
            const accts = grouped[t]
            if (!accts?.length) return null
            return (
              <div key={t} className="card mb-16">
                <div className="card-hd">
                  <div className="card-title">{TYPE_LABELS[t]}</div>
                  <span className="color-text3" style={{ fontSize: 12 }}>{accts.length} accounts</span>
                </div>
                <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Account Name</th>
                      <th>Sub-Category</th>
                      <th>Normal Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accts.map((a) => (
                      <tr key={a.account_code}>
                        <td className="mono color-text3" style={{ fontSize: 12.5, width: 70 }}>{a.account_code}</td>
                        <td style={{ fontWeight: 500 }}>{a.account_name}</td>
                        <td className="color-text3" style={{ fontSize: 13 }}>{a.sub_category}</td>
                        <td><StatusBadge status={a.normal_balance} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </div>
            )
          })}

          {!accounts.length && (
            <div className="card">
              <EmptyState icon="accounts" message="No accounts configured." hint="Add accounts to your chart of accounts." />
            </div>
          )}
        </>
      )}
    </Layout>
  )
}
