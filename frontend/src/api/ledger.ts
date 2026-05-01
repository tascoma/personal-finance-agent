import { get } from './client'
import type { LedgerResponse } from '../types'

export function fetchLedger(): Promise<LedgerResponse> {
  return get<LedgerResponse>('/ledger')
}
