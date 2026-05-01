import { del, get, patch, post } from './client'
import type { ManualTransactionBatch, RawTransaction } from '../types'

export function fetchTransactions(periodId: string): Promise<RawTransaction[]> {
  return get<RawTransaction[]>(`/periods/${periodId}/transactions`)
}

export function addManualTransactions(
  periodId: string,
  batch: ManualTransactionBatch,
): Promise<RawTransaction[]> {
  return post<RawTransaction[]>(`/periods/${periodId}/transactions`, batch)
}

export function approveTransaction(periodId: string, txnId: string): Promise<RawTransaction> {
  return post<RawTransaction>(`/periods/${periodId}/transactions/${txnId}/approve`)
}

export function unapproveTransaction(periodId: string, txnId: string): Promise<RawTransaction> {
  return post<RawTransaction>(`/periods/${periodId}/transactions/${txnId}/unapprove`)
}

export function rejectTransaction(periodId: string, txnId: string): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/periods/${periodId}/transactions/${txnId}`)
}

export function approveAllStaged(periodId: string): Promise<{ updated: number }> {
  return post<{ updated: number }>(`/periods/${periodId}/transactions/approve-all-staged`)
}

export function unapproveAll(periodId: string): Promise<{ updated: number }> {
  return post<{ updated: number }>(`/periods/${periodId}/transactions/unapprove-all`)
}

export function rejectAllStaged(periodId: string): Promise<{ deleted: number }> {
  return post<{ deleted: number }>(`/periods/${periodId}/transactions/reject-all-staged`)
}

export function clearAllTransactions(periodId: string): Promise<{ deleted: number }> {
  return post<{ deleted: number }>(`/periods/${periodId}/transactions/clear-all`)
}

export function updateTransactionAccount(
  periodId: string,
  txnId: string,
  accountCode: number,
): Promise<RawTransaction> {
  return patch<RawTransaction>(`/periods/${periodId}/transactions/${txnId}/account`, {
    account_code: accountCode,
  })
}
