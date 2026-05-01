import { Fragment, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBalanceSheet, fetchIncomeStatement, fetchCashflow } from '../api/statements'
import { fetchPeriods } from '../api/periods'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import type { StatementSection, StatementLine } from '../types'

type Tab = 'balance_sheet' | 'income_statement' | 'cashflows'

function Money({ val }: { val: string }) {
  const n = parseFloat(val)
  if (n < 0) return <span style={{ color: 'var(--red)' }}>${Math.abs(n).toFixed(2)}</span>
  return <span>${n.toFixed(2)}</span>
}

function SectionTable({ sections, totalLabel, totalAmount }: {
  sections: StatementSection[]
  totalLabel: string
  totalAmount: string
}) {
  if (!sections.length) {
    return <div className="empty-state"><p className="empty-msg">No activity for this section.</p></div>
  }
  return (
    <table className="data-table">
      <tbody>
        {sections.map((sec) => (
          <Fragment key={sec.label}>
            <tr>
              <td colSpan={2} className="color-text3" style={{ fontSize: 11.5, textTransform: 'uppercase', letterSpacing: '0.05em', paddingTop: 14 }}>
                {sec.label}
              </td>
            </tr>
            {sec.lines.map((line) => (
              <tr key={line.account_code}>
                <td style={{ paddingLeft: 28 }}>
                  <span className="mono color-text3" style={{ fontSize: 12.5 }}>{line.account_code}</span>
                  <span style={{ marginLeft: 10 }}>{line.account_name}</span>
                </td>
                <td className="mono text-right" style={{ width: 160 }}><Money val={line.amount} /></td>
              </tr>
            ))}
            <tr>
              <td className="color-text2" style={{ paddingLeft: 28, fontStyle: 'italic', fontSize: 12.5 }}>
                Subtotal — {sec.label}
              </td>
              <td className="mono text-right" style={{ borderTop: '1px solid var(--border)' }}>
                <Money val={sec.subtotal} />
              </td>
            </tr>
          </Fragment>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td className="fw-600">{totalLabel}</td>
          <td className="mono text-right fw-600" style={{ borderTop: '1px solid var(--border-md)' }}>
            <Money val={totalAmount} />
          </td>
        </tr>
      </tfoot>
    </table>
  )
}

function LineRows({ lines }: { lines: StatementLine[] }) {
  return (
    <>
      {lines.map((line) => (
        <tr key={line.account_code}>
          <td>
            <span className="mono color-text3" style={{ fontSize: 12.5 }}>{line.account_code}</span>
            <span style={{ marginLeft: 10 }}>{line.account_name}</span>
          </td>
          <td className="mono text-right" style={{ width: 160 }}><Money val={line.amount} /></td>
        </tr>
      ))}
    </>
  )
}

export default function StatementsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('balance_sheet')
  const [periodId, setPeriodId] = useState<string>('')

  const periodsQ = useQuery({ queryKey: ['periods'], queryFn: fetchPeriods, staleTime: 30_000 })
  const bsQ = useQuery({ queryKey: ['balance-sheet'], queryFn: fetchBalanceSheet, staleTime: 30_000 })
  const incQ = useQuery({
    queryKey: ['income-statement', periodId],
    queryFn: () => fetchIncomeStatement(periodId || undefined),
    staleTime: 30_000,
  })
  const cfQ = useQuery({
    queryKey: ['cashflow', periodId],
    queryFn: () => fetchCashflow(periodId || undefined),
    staleTime: 30_000,
    enabled: activeTab === 'cashflows',
  })

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: 'balance_sheet', label: 'Balance Sheet' },
    { id: 'income_statement', label: 'Income Statement' },
    { id: 'cashflows', label: 'Cashflows' },
  ]

  const bs = bsQ.data
  const inc = incQ.data
  const cf = cfQ.data

  return (
    <Layout>
      <PageHeader title="Statements" subtitle="Balance sheet, income, and cash flow — derived from posted journal entries" />

      {activeTab !== 'balance_sheet' && (
        <div className="card mb-16">
          <div className="card-bd-sm">
            <div className="form-row" style={{ alignItems: 'center' }}>
              <label className="color-text2" style={{ fontSize: 13 }}>Period:</label>
              <select
                className="inp"
                style={{ width: 240 }}
                value={periodId}
                onChange={(e) => setPeriodId(e.target.value)}
              >
                {activeTab !== 'cashflows' && <option value="">All periods (aggregate)</option>}
                {periodsQ.data?.map((p) => (
                  <option key={p.period_id} value={p.period_id}>
                    {p.period_start.slice(0, 7)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      <div className="tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`tab-btn${activeTab === t.id ? ' tab-btn--active' : ''}`}
            onClick={() => {
              setActiveTab(t.id)
              if (t.id === 'cashflows' && !periodId && periodsQ.data?.[0]) {
                setPeriodId(periodsQ.data[0].period_id)
              }
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Balance Sheet */}
      {activeTab === 'balance_sheet' && (
        <div className="card mb-16">
          <div className="card-hd">
            <div>
              <div className="card-title">Balance Sheet</div>
              <div className="card-sub">Cumulative balances by period</div>
            </div>
          </div>
          <div className="card-bd">
            {bsQ.isLoading && <p style={{ color: 'var(--text-3)' }}>Loading…</p>}
            {bsQ.error && <p style={{ color: 'var(--red)' }}>Failed to load balance sheet.</p>}
            {bs && !bs.periods.length && <EmptyState message="No periods found." />}
            {bs && bs.periods.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ minWidth: 220 }}>Account</th>
                      {bs.periods.map((p) => (
                        <th key={p.period_id} className="mono text-right" style={{ minWidth: 120, whiteSpace: 'nowrap' }}>
                          {p.period_start.slice(0, 7)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: 'Assets', sections: bs.assets, totals: bs.total_assets },
                      { label: 'Liabilities', sections: bs.liabilities, totals: bs.total_liabilities },
                      { label: 'Equity', sections: bs.equity, totals: bs.total_equity },
                    ].map(({ label, sections, totals }) => (
                      <Fragment key={label}>
                        <tr>
                          <td colSpan={bs.periods.length + 1} className="color-text3" style={{ fontSize: 11.5, textTransform: 'uppercase', letterSpacing: '0.05em', paddingTop: 18, fontWeight: 600 }}>
                            {label}
                          </td>
                        </tr>
                        {sections.map((sec) => (
                          <Fragment key={sec.label}>
                            <tr>
                              <td colSpan={bs.periods.length + 1} className="color-text3" style={{ fontSize: 11.5, textTransform: 'uppercase', letterSpacing: '0.05em', paddingTop: 10 }}>
                                {sec.label}
                              </td>
                            </tr>
                            {sec.rows.map((row) => (
                              <tr key={row.account_code}>
                                <td style={{ paddingLeft: 28 }}>
                                  <span className="mono color-text3" style={{ fontSize: 12.5 }}>{row.account_code}</span>
                                  <span style={{ marginLeft: 10 }}>{row.account_name}</span>
                                </td>
                                {row.balances.map((bal, i) => (
                                  <td key={i} className="mono text-right" style={{ minWidth: 120 }}>
                                    {bal ? <Money val={bal} /> : null}
                                  </td>
                                ))}
                              </tr>
                            ))}
                            <tr>
                              <td className="color-text2" style={{ paddingLeft: 28, fontStyle: 'italic', fontSize: 12.5 }}>
                                Subtotal — {sec.label}
                              </td>
                              {sec.subtotals.map((st, i) => (
                                <td key={i} className="mono text-right" style={{ borderTop: '1px solid var(--border)' }}>
                                  <Money val={st} />
                                </td>
                              ))}
                            </tr>
                          </Fragment>
                        ))}
                        <tr>
                          <td className="fw-600">Total {label}</td>
                          {totals.map((t, i) => (
                            <td key={i} className="mono text-right fw-600" style={{ borderTop: '1px solid var(--border-md)' }}>
                              <Money val={t} />
                            </td>
                          ))}
                        </tr>
                      </Fragment>
                    ))}
                    <tr>
                      <td className="fw-600" style={{ paddingTop: 10 }}>Total Liabilities + Equity</td>
                      {bs.periods.map((_, i) => {
                        const liab = parseFloat(bs.total_liabilities[i] ?? '0')
                        const eq = parseFloat(bs.total_equity[i] ?? '0')
                        return (
                          <td key={i} className="mono text-right fw-600" style={{ borderTop: '1px solid var(--border-md)', paddingTop: 10 }}>
                            <Money val={(liab + eq).toFixed(2)} />
                          </td>
                        )
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Income Statement */}
      {activeTab === 'income_statement' && (
        <div className="card mb-16">
          <div className="card-hd">
            <div>
              <div className="card-title">Income Statement</div>
              <div className="card-sub">{inc?.range_label ?? ''}</div>
            </div>
          </div>
          <div className="card-bd">
            {incQ.isLoading && <p style={{ color: 'var(--text-3)' }}>Loading…</p>}
            {incQ.error && <p style={{ color: 'var(--red)' }}>Failed to load income statement.</p>}
            {inc && (
              <>
                <h3 style={{ fontSize: 14, margin: '0 0 6px 0' }}>Income</h3>
                <SectionTable sections={inc.income} totalLabel="Total Income" totalAmount={inc.total_income} />
                <h3 style={{ fontSize: 14, margin: '24px 0 6px 0' }}>Expenses</h3>
                <SectionTable sections={inc.expenses} totalLabel="Total Expenses" totalAmount={inc.total_expenses} />
                <table className="data-table" style={{ marginTop: 18 }}>
                  <tfoot>
                    <tr>
                      <td className="fw-600">Net Income</td>
                      <td className="mono text-right fw-600" style={{ width: 160 }}>
                        <Money val={inc.net_income} />
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </>
            )}
          </div>
        </div>
      )}

      {/* Cashflows */}
      {activeTab === 'cashflows' && (
        <div className="card mb-16">
          <div className="card-hd">
            <div>
              <div className="card-title">Statement of Cash Flows</div>
              <div className="card-sub">{cf?.range_label ?? ''} · indirect method</div>
            </div>
          </div>
          <div className="card-bd">
            {cfQ.isLoading && <p style={{ color: 'var(--text-3)' }}>Loading…</p>}
            {cfQ.error && <p style={{ color: 'var(--red)' }}>Failed to load cash flows.</p>}
            {cf && (
              <>
                <h3 style={{ fontSize: 14, margin: '0 0 6px 0' }}>Operating Activities</h3>
                <table className="data-table">
                  <tbody>
                    <tr>
                      <td>Net income</td>
                      <td className="mono text-right" style={{ width: 160 }}><Money val={cf.net_income} /></td>
                    </tr>
                    {cf.noncash_adjustments.length > 0 && (
                      <>
                        <tr><td colSpan={2} className="color-text3" style={{ fontSize: 11.5, textTransform: 'uppercase', letterSpacing: '0.05em', paddingTop: 12 }}>Adjustments for non-cash items</td></tr>
                        <LineRows lines={cf.noncash_adjustments} />
                      </>
                    )}
                    {cf.working_capital_changes.length > 0 && (
                      <>
                        <tr><td colSpan={2} className="color-text3" style={{ fontSize: 11.5, textTransform: 'uppercase', letterSpacing: '0.05em', paddingTop: 12 }}>Changes in working capital</td></tr>
                        <LineRows lines={cf.working_capital_changes} />
                      </>
                    )}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td className="fw-600">Net cash from operating activities</td>
                      <td className="mono text-right fw-600" style={{ borderTop: '1px solid var(--border-md)' }}>
                        <Money val={cf.operating_total} />
                      </td>
                    </tr>
                  </tfoot>
                </table>

                <h3 style={{ fontSize: 14, margin: '24px 0 6px 0' }}>Investing Activities</h3>
                <table className="data-table">
                  {cf.investing.length > 0 && <tbody><LineRows lines={cf.investing} /></tbody>}
                  <tfoot>
                    <tr>
                      <td className="fw-600">Net cash from investing activities</td>
                      <td className="mono text-right fw-600" style={{ borderTop: '1px solid var(--border-md)', width: 160 }}>
                        <Money val={cf.investing_total} />
                      </td>
                    </tr>
                  </tfoot>
                </table>

                <h3 style={{ fontSize: 14, margin: '24px 0 6px 0' }}>Financing Activities</h3>
                <table className="data-table">
                  {cf.financing.length > 0 && <tbody><LineRows lines={cf.financing} /></tbody>}
                  <tfoot>
                    <tr>
                      <td className="fw-600">Net cash from financing activities</td>
                      <td className="mono text-right fw-600" style={{ borderTop: '1px solid var(--border-md)', width: 160 }}>
                        <Money val={cf.financing_total} />
                      </td>
                    </tr>
                  </tfoot>
                </table>

                <table className="data-table" style={{ marginTop: 18 }}>
                  <tfoot>
                    <tr>
                      <td className="fw-600">Net change in cash</td>
                      <td className="mono text-right fw-600" style={{ width: 160, borderTop: '2px solid var(--border-md)' }}>
                        <Money val={cf.net_change_in_cash} />
                      </td>
                    </tr>
                  </tfoot>
                </table>

                {cf.cash_by_account.length > 0 && (
                  <>
                    <h3 style={{ fontSize: 14, margin: '24px 0 6px 0' }}>Cash change by account</h3>
                    <table className="data-table">
                      <tbody><LineRows lines={cf.cash_by_account} /></tbody>
                    </table>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </Layout>
  )
}
