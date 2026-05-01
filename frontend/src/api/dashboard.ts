import { get } from './client'
import type { DashboardResponse } from '../types'

export function fetchDashboard(): Promise<DashboardResponse> {
  return get<DashboardResponse>('/dashboard')
}
