import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchJournalPage,
  classifyTransactions,
  postTransactions,
  createManualJournalEntry,
  deleteJournalEntry,
} from '../api/journal'
import { approveTransaction, unapproveTransaction, rejectTransaction, approveAllStaged, unapproveAll, rejectAllStaged, updateTransactionAccount } from '../api/transactions'
import { setDocumentSourceAccount } from '../api/documents'
import Layout from '../components/Layout'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import PeriodStepper from '../components/PeriodStepper'
import Banner from '../components/Banner'
import EmptyState from '../components/EmptyState'
import ConfidencePill from '../components/ConfidencePill'
import SvgIcon from '../components/SvgIcon'
import { fmtPeriod } from '../utils/format'
import type { JournalLineCreate } from '../types'

type Tab = 'staged' | 'approved' | 'posted'

function fmtAmt(v: string) {
  const n = parseFloat(v)
  return n > 0 ? `$${n.toFixed(2)}` : '—'
}

export default function JournalPage() {
  const { periodId } = useParams<{ periodId: string }>()
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('staged')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Manual journal entry form state
  const [entryDate, setEntryDate] = useState('')
  const [entryDesc, setEntryDesc] = useState('')
  const [entryType, setEntryType] = useState('manual')
  const [lines, setLines] = useState<Array<{ acct: string; debit: string; credit: string; memo: string }>>([
    { acct: '', debit: '', credit: '', memo: '' },
    { acct: '', debit: '', credit: '', memo: '' },
  ])

  const invalidate = () => qc.invalidateQueries({ queryKey: ['journal', periodId] })

  const { data, isLoading } = useQuery({
    queryKey: ['journal', periodId],
    queryFn: () => fetchJournalPage(periodId!),
    staleTime: 30_000,
    enabled: !!periodId,
  })

  const classify = useMutation({
    mutationFn: () => classifyTransactions(periodId!),
    onSuccess: (r) => { setSuccess(`Classified ${r.classified} transaction(s).`); invalidate() },
    onError: (e: Error) => setError(e.message),
  })

  const post = useMutation({
    mutationFn: () => postTransactions(periodId!),
    onSuccess: (r) => { setSuccess(`Posted ${r.posted} transaction(s).`); invalidate() },
    onError: (e: Error) => setError(e.message),
  })

  const approve = useMutation({
    mutationFn: (id: string) => approveTransaction(periodId!, id),
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  })

  const unapprove = useMutation({
    mutationFn: (id: string) => unapproveTransaction(periodId!, id),
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  })

  const reject = useMutation({
    mutationFn: (id: string) => rejectTransaction(periodId!, id),
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  })

  const approveAll = useMutation({
    mutationFn: () => approveAllStaged(periodId!),
    onSuccess: (r) => { setSuccess(`Approved ${r.updated} transaction(s).`); invalidate() },
    onError: (e: Error) => setError(e.message),
  })

  const unapproveAllMut = useMutation({
    mutationFn: () => unapproveAll(periodId!),
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  })

  const rejectAll = useMutation({
    mutationFn: () => rejectAllStaged(periodId!),
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  })

  const updateAcct = useMutation({
    mutationFn: ({ id, code }: { id: string; code: number }) => updateTransactionAccount(periodId!, id, code),
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  })

  const deleteEntry = useMutation({
    mutationFn: (id: string) => deleteJournalEntry(periodId!, id),
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  })

  const setDocSource = useMutation({
    mutationFn: ({ docId, code }: { docId: string; code: number }) =>
      setDocumentSourceAccount(periodId!, docId, code),
    onSuccess: invalidate,
  })

  const postManualEntry = useMutation({
    mutationFn: () => createManualJournalEntry(periodId!, {
      entry_date: entryDate,
      description: entryDesc,
      source_type: entryType,
      lines: lines
        .filter((l) => l.acct)
        .map((l): JournalLineCreate => ({ account_code: parseInt(l.acct, 10), debit: l.debit || '0', credit: l.credit || '0', memo: l.memo || undefined })),
    }),
    onSuccess: () => {
      setSuccess('Entry posted.')
      setEntryDate(''); setEntryDesc(''); setEntryType('manual')
      setLines([{ acct: '', debit: '', credit: '', memo: '' }, { acct: '', debit: '', credit: '', memo: '' }])
      invalidate()
    },
    onError: (e: Error) => setError(e.message),
  })

  if (isLoading || !data) return <Layout><p style={{ color: 'var(--text-3)' }}>Loading…</p></Layout>

  const { period, accounts, staged, approved, entries, has_unclassified, docs_missing_source } = data
  const accountsByCode = Object.fromEntries(accounts.map((a) => [a.account_code, a]))
  const canEdit = period.status === 'pending_close'

  const balanceIndicator = () => {
    const dr = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0)
    const cr = lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0)
    const diff = Math.abs(dr - cr)
    if (dr === 0 && cr === 0) return null
    if (diff < 0.005) return <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--green)' }}>Balanced ✓</span>
    return <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>Out of balance by ${diff.toFixed(2)}</span>
  }

  return (
    <Layout activePeriod={period}>
      <PageHeader
        title="Ledger"
        subtitle={`${fmtPeriod(period.period_start)} · Classify transactions and post to the ledger`}
        backTo={`/periods/${periodId}`}
        backLabel={fmtPeriod(period.period_start)}
        badge={<StatusBadge status={period.status} />}
        right={
          <div style={{ display: 'flex', gap: 8 }}>
            {canEdit && has_unclassified && (
              <button className="btn btn-secondary btn-sm" disabled={classify.isPending} onClick={() => classify.mutate()}>
                <SvgIcon name="brain" size={13} />
                {classify.isPending ? 'Classifying…' : 'Classify with AI'}
              </button>
            )}
            {canEdit && approved.length > 0 && (
              <button className="btn btn-primary btn-sm" disabled={post.isPending} onClick={() => post.mutate()}>
                {post.isPending ? 'Posting…' : 'Post All Approved →'}
              </button>
            )}
          </div>
        }
      />

      <PeriodStepper period={period} />

      {error && <Banner variant="red" style={{ marginTop: 16 }}>{error}</Banner>}
      {success && <Banner variant="green" style={{ marginTop: 16 }}>{success}</Banner>}

      {docs_missing_source.length > 0 && (
        <Banner variant="amber" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 10, marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <strong>{docs_missing_source.length} document{docs_missing_source.length > 1 ? 's' : ''} missing a deposit account</strong>
            — set the account that receives net proceeds before posting.
          </div>
          {docs_missing_source.map((doc) => (
            <div key={doc.document_id} style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
              <span style={{ fontSize: 12.5, color: 'var(--text-2)', minWidth: 180 }}>{doc.file_name}</span>
              <select
                className="inp"
                style={{ fontSize: 12, padding: '4px 8px', minWidth: 220 }}
                defaultValue=""
                onChange={(e) => { if (e.target.value) setDocSource.mutate({ docId: doc.document_id, code: parseInt(e.target.value, 10) }) }}
              >
                <option value="">— select account —</option>
                {accounts.map((a) => <option key={a.account_code} value={a.account_code}>{a.account_code} · {a.account_name}</option>)}
              </select>
            </div>
          ))}
        </Banner>
      )}

      <div className="tabs" style={{ marginTop: 16 }}>
        <button className={`tab-btn${activeTab === 'staged' ? ' tab-btn--active' : ''}`} onClick={() => setActiveTab('staged')}>
          Staged <span className="color-amber mono" style={{ fontSize: 12, marginLeft: 4 }}>{staged.length}</span>
        </button>
        <button className={`tab-btn${activeTab === 'approved' ? ' tab-btn--active' : ''}`} onClick={() => setActiveTab('approved')}>
          Approved <span className="color-green mono" style={{ fontSize: 12, marginLeft: 4 }}>{approved.length}</span>
        </button>
        <button className={`tab-btn${activeTab === 'posted' ? ' tab-btn--active' : ''}`} onClick={() => setActiveTab('posted')}>
          Posted <span className="color-accent mono" style={{ fontSize: 12, marginLeft: 4 }}>{entries.length}</span>
        </button>
      </div>

      {/* ── Staged ── */}
      {activeTab === 'staged' && (
        <>
          <div className="card">
            <div className="card-hd">
              <div>
                <div className="card-title">Staged Transactions</div>
                <div className="card-sub">Awaiting review and approval</div>
              </div>
              <div className="card-hd-right" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {staged.filter((t) => t.is_flagged).length > 0 && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--amber)' }}>
                    <SvgIcon name="alert" size={13} />
                    {staged.filter((t) => t.is_flagged).length} flagged
                  </span>
                )}
                {canEdit && staged.length > 0 && (
                  <>
                    <button className="btn btn-primary btn-sm" disabled={approveAll.isPending} onClick={() => approveAll.mutate()}>Approve All</button>
                    <button className="btn btn-danger btn-sm" disabled={rejectAll.isPending} onClick={() => { if (window.confirm(`Delete all ${staged.length} staged transaction(s)?`)) rejectAll.mutate() }}>Reject All</button>
                  </>
                )}
              </div>
            </div>

            {staged.length === 0 ? (
              <EmptyState icon="check" message="No staged transactions." hint="All transactions have been approved, rejected, or posted." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th><th>Description</th>
                    <th className="text-right">Amount</th>
                    <th>Suggested Account</th>
                    <th>Confidence</th>
                    {canEdit && <th />}
                  </tr>
                </thead>
                <tbody>
                  {staged.map((txn) => {
                    const n = parseFloat(txn.amount)
                    return (
                      <tr key={txn.raw_txn_id} style={txn.is_flagged ? { background: 'rgba(251,191,36,0.04)' } : undefined}>
                        <td className="mono color-text3" style={{ fontSize: 12.5 }}>{txn.txn_date}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            {txn.is_flagged && <SvgIcon name="alert" size={13} className="icon color-amber" />}
                            <span style={{ fontSize: 13 }}>{txn.description}</span>
                            {txn.is_duplicate && <span className="color-text3" style={{ fontSize: 11 }}>(dup)</span>}
                          </div>
                        </td>
                        <td className="mono text-right fw-600" style={{ fontSize: 13.5, color: n < 0 ? 'var(--red)' : 'var(--green)' }}>
                          {n < 0 ? `−$${Math.abs(n).toFixed(2)}` : `$${n.toFixed(2)}`}
                        </td>
                        <td>
                          {canEdit ? (
                            <select
                              className="inp"
                              style={{ fontSize: 12, padding: '4px 8px', minWidth: 200 }}
                              value={txn.suggested_account_code ?? ''}
                              onChange={(e) => { if (e.target.value) updateAcct.mutate({ id: txn.raw_txn_id, code: parseInt(e.target.value, 10) }) }}
                            >
                              <option value="">— unclassified —</option>
                              {accounts.map((a) => <option key={a.account_code} value={a.account_code}>{a.account_code} · {a.account_name}</option>)}
                            </select>
                          ) : (
                            txn.suggested_account_code
                              ? <span className="mono color-text2" style={{ fontSize: 12.5 }}>{txn.suggested_account_code}{accountsByCode[txn.suggested_account_code] ? ` · ${accountsByCode[txn.suggested_account_code].account_name}` : ''}</span>
                              : <span className="color-text3" style={{ fontStyle: 'italic', fontSize: 12 }}>Unclassified</span>
                          )}
                        </td>
                        <td><ConfidencePill confidence={txn.classifier_confidence} /></td>
                        {canEdit && (
                          <td>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button className="btn btn-primary btn-sm" disabled={approve.isPending} onClick={() => approve.mutate(txn.raw_txn_id)}>Approve</button>
                              <button className="btn btn-danger btn-sm" disabled={reject.isPending} onClick={() => reject.mutate(txn.raw_txn_id)}>Reject</button>
                            </div>
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* ── Approved ── */}
      {activeTab === 'approved' && (
        <div className="card">
          <div className="card-hd">
            <div>
              <div className="card-title">Approved Transactions</div>
              <div className="card-sub">Ready to post to the ledger</div>
            </div>
            {canEdit && approved.length > 0 && (
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-ghost btn-sm" disabled={unapproveAllMut.isPending} onClick={() => unapproveAllMut.mutate()}>Undo All</button>
                <button className="btn btn-primary btn-sm" disabled={post.isPending} onClick={() => post.mutate()}>Post All →</button>
              </div>
            )}
          </div>

          {approved.length === 0 ? (
            <EmptyState icon="journal" message="Nothing approved yet." hint="Approve staged transactions, then post them to the ledger." />
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>Date</th><th>Description</th><th className="text-right">Amount</th><th>Account</th><th>Confidence</th>{canEdit && <th />}</tr>
              </thead>
              <tbody>
                {approved.map((txn) => {
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
                        {txn.suggested_account_code ? `${txn.suggested_account_code}${acct ? ` · ${acct.account_name}` : ''}` : '—'}
                      </td>
                      <td><ConfidencePill confidence={txn.classifier_confidence} /></td>
                      {canEdit && (
                        <td>
                          <button className="btn btn-ghost btn-sm" disabled={unapprove.isPending} onClick={() => unapprove.mutate(txn.raw_txn_id)}>Undo</button>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Posted ── */}
      {activeTab === 'posted' && (
        <>
          {entries.length === 0 ? (
            <div className="card">
              <EmptyState icon="statements" message="No entries posted yet." hint="Approve transactions and click Post All to create journal entries." />
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {entries.map((entry) => {
                const totalDebit = entry.lines.reduce((s, l) => s + parseFloat(l.debit_amount), 0)
                const totalCredit = entry.lines.reduce((s, l) => s + parseFloat(l.credit_amount), 0)
                return (
                  <div key={entry.entry_id} className="card">
                    <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <span style={{ fontWeight: 600, fontSize: 13.5 }}>{entry.description}</span>
                        <span className="mono color-text3" style={{ fontSize: 12, marginLeft: 12 }}>{entry.entry_date}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span className="badge badge--parsed">{entry.source_type}</span>
                        {period.status !== 'closed' && (
                          <button
                            className="btn btn-ghost btn-sm"
                            style={{ padding: '3px 8px', fontSize: 11, color: 'var(--red)' }}
                            disabled={deleteEntry.isPending}
                            onClick={() => { if (window.confirm('Delete this entry?')) deleteEntry.mutate(entry.entry_id) }}
                          >
                            <SvgIcon name="trash" size={12} />
                          </button>
                        )}
                      </div>
                    </div>
                    <table className="data-table" style={{ tableLayout: 'fixed' }}>
                      <thead>
                        <tr><th>Account</th><th>Memo</th><th className="text-right" style={{ width: 130 }}>Debit</th><th className="text-right" style={{ width: 130 }}>Credit</th></tr>
                      </thead>
                      <tbody>
                        {entry.lines.map((line) => {
                          const acct = accountsByCode[line.account_code]
                          return (
                            <tr key={line.line_id}>
                              <td className="mono" style={{ fontSize: 13 }}>{line.account_code}{acct ? ` · ${acct.account_name}` : ''}</td>
                              <td className="color-text3" style={{ fontSize: 12 }}>{line.memo ?? ''}</td>
                              <td className="mono text-right" style={{ color: parseFloat(line.debit_amount) > 0 ? 'var(--text-1)' : 'var(--text-3)' }}>{fmtAmt(line.debit_amount)}</td>
                              <td className="mono text-right" style={{ color: parseFloat(line.credit_amount) > 0 ? 'var(--text-1)' : 'var(--text-3)' }}>{fmtAmt(line.credit_amount)}</td>
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
                  </div>
                )
              })}
            </div>
          )}

          {period.status !== 'closed' && (
            <div className="card mt-12">
              <div className="card-hd">
                <div>
                  <div className="card-title">New Manual Journal Entry</div>
                  <div className="card-sub">Directly post a balanced debit/credit entry — useful for adjustments, accruals, or closing entries</div>
                </div>
              </div>
              <div className="card-bd-sm">
                <div className="form-row" style={{ alignItems: 'flex-end', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label className="form-label">Date</label>
                    <input type="date" className="inp" style={{ width: 140 }} value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 220 }}>
                    <label className="form-label">Description</label>
                    <input type="text" className="inp" placeholder="e.g. Depreciation — December" value={entryDesc} onChange={(e) => setEntryDesc(e.target.value)} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <label className="form-label">Type</label>
                    <select className="inp" style={{ width: 140 }} value={entryType} onChange={(e) => setEntryType(e.target.value)}>
                      <option value="manual">Manual</option>
                      <option value="adjusting">Adjusting</option>
                      <option value="closing">Closing</option>
                    </select>
                  </div>
                </div>

                <table className="data-table" style={{ marginBottom: 8 }}>
                  <thead>
                    <tr><th>Account</th><th style={{ width: 110 }}>Debit ($)</th><th style={{ width: 110 }}>Credit ($)</th><th style={{ width: 200 }}>Memo</th><th style={{ width: 36 }} /></tr>
                  </thead>
                  <tbody>
                    {lines.map((line, i) => (
                      <tr key={i}>
                        <td>
                          <select className="inp" style={{ fontSize: 12, padding: '4px 8px', width: '100%' }} value={line.acct} onChange={(e) => setLines((ls) => ls.map((l, j) => j === i ? { ...l, acct: e.target.value } : l))}>
                            <option value="">— account —</option>
                            {accounts.map((a) => <option key={a.account_code} value={a.account_code}>{a.account_code} · {a.account_name}</option>)}
                          </select>
                        </td>
                        <td><input type="number" step="0.01" min="0" className="inp mono" style={{ fontSize: 12, padding: '4px 8px', width: '100%' }} value={line.debit} placeholder="0.00" onChange={(e) => setLines((ls) => ls.map((l, j) => j === i ? { ...l, debit: e.target.value } : l))} /></td>
                        <td><input type="number" step="0.01" min="0" className="inp mono" style={{ fontSize: 12, padding: '4px 8px', width: '100%' }} value={line.credit} placeholder="0.00" onChange={(e) => setLines((ls) => ls.map((l, j) => j === i ? { ...l, credit: e.target.value } : l))} /></td>
                        <td><input type="text" className="inp" style={{ fontSize: 12, padding: '4px 8px', width: '100%' }} value={line.memo} onChange={(e) => setLines((ls) => ls.map((l, j) => j === i ? { ...l, memo: e.target.value } : l))} /></td>
                        <td>
                          <button className="btn btn-ghost btn-sm" style={{ padding: '3px 7px', color: 'var(--red)' }} onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}>
                            <SvgIcon name="x" size={12} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => setLines((ls) => [...ls, { acct: '', debit: '', credit: '', memo: '' }])}>
                    <SvgIcon name="plus" size={12} /> Add Line
                  </button>
                  {balanceIndicator()}
                </div>

                <button className="btn btn-primary btn-sm" disabled={postManualEntry.isPending} onClick={() => postManualEntry.mutate()}>
                  {postManualEntry.isPending ? 'Posting…' : 'Post Entry'}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </Layout>
  )
}
