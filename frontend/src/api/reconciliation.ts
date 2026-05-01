import { get, post } from './client'
import type { ReconcilePageResponse } from '../types'

export function fetchReconcilePage(periodId: string): Promise<ReconcilePageResponse> {
  return get<ReconcilePageResponse>(`/periods/${periodId}/reconcile`)
}

export function runReconciliation(periodId: string): Promise<ReconcilePageResponse> {
  return post<ReconcilePageResponse>(`/periods/${periodId}/reconcile`)
}

export function analyzeReconciliation(periodId: string): Promise<ReconcilePageResponse> {
  return post<ReconcilePageResponse>(`/periods/${periodId}/reconcile/analyze`)
}

export function postUnrealizedGl(
  periodId: string,
  accountCode: number,
): Promise<ReconcilePageResponse> {
  return post<ReconcilePageResponse>(`/periods/${periodId}/reconcile/post-unrealized`, {
    account_code: accountCode,
  })
}

export function postClosingEntries(periodId: string): Promise<ReconcilePageResponse> {
  return post<ReconcilePageResponse>(`/periods/${periodId}/reconcile/post-closing`)
}

export function postEquityRollup(periodId: string): Promise<ReconcilePageResponse> {
  return post<ReconcilePageResponse>(`/periods/${periodId}/reconcile/post-equity-rollup`)
}
