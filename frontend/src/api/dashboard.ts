import { get } from './client'
import type { DashboardResponse } from '../types'

export function fetchDashboard(fromPeriodId?: string, toPeriodId?: string): Promise<DashboardResponse> {
  const params = new URLSearchParams()
  if (fromPeriodId != null) params.set('from_period_id', fromPeriodId)
  if (toPeriodId != null) params.set('to_period_id', toPeriodId)
  const qs = params.toString()
  return get<DashboardResponse>(`/dashboard${qs ? `?${qs}` : ''}`)
}
