import { get } from './client'
import type {
  BalanceSheetPivotResponse,
  IncomeStatementResponse,
  CashflowStatementResponse,
} from '../types'

export function fetchBalanceSheet(): Promise<BalanceSheetPivotResponse> {
  return get<BalanceSheetPivotResponse>('/statements/balance-sheet')
}

export function fetchIncomeStatement(periodId?: string): Promise<IncomeStatementResponse> {
  const qs = periodId ? `?period_id=${periodId}` : ''
  return get<IncomeStatementResponse>(`/statements/income${qs}`)
}

export function fetchCashflow(periodId?: string): Promise<CashflowStatementResponse> {
  const qs = periodId ? `?period_id=${periodId}` : ''
  return get<CashflowStatementResponse>(`/statements/cashflow${qs}`)
}
