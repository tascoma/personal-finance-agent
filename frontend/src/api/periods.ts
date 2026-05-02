import { del, get, patch, post } from './client'
import type {
  Period,
  PeriodCreate,
  PeriodDetailResponse,
  StatedBalanceItem,
} from '../types'

export function fetchPeriods(): Promise<Period[]> {
  return get<Period[]>('/periods')
}

export function fetchPeriodDetail(periodId: string): Promise<PeriodDetailResponse> {
  return get<PeriodDetailResponse>(`/periods/${periodId}`)
}

export function createPeriod(body: PeriodCreate): Promise<Period> {
  return post<Period>('/periods', body)
}

export function updatePeriodStatus(periodId: string, newStatus: string): Promise<Period> {
  return post<Period>(`/periods/${periodId}/status`, { new_status: newStatus })
}

export function stepBackPeriod(periodId: string): Promise<Period> {
  return post<Period>(`/periods/${periodId}/step-back`)
}

export function reopenPeriod(periodId: string): Promise<Period> {
  return post<Period>(`/periods/${periodId}/reopen`)
}

export function deletePeriod(periodId: string): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/periods/${periodId}`)
}

export function parseAllDocuments(periodId: string): Promise<{ parsed: number; errors: string[] }> {
  return post<{ parsed: number; errors: string[] }>(`/periods/${periodId}/parse`)
}

export function saveBalances(periodId: string, balances: StatedBalanceItem[]): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(`/periods/${periodId}/balances`, balances)
}
