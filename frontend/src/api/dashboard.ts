import { get } from './client'
import type { DashboardResponse } from '../types'

export function fetchDashboard(year?: number, periodId?: string): Promise<DashboardResponse> {
  const params = new URLSearchParams()
  if (year != null) params.set('year', String(year))
  if (periodId != null) params.set('period_id', periodId)
  const qs = params.toString()
  return get<DashboardResponse>(`/dashboard${qs ? `?${qs}` : ''}`)
}
