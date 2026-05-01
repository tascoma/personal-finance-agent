import { get } from './client'
import type { Account } from '../types'

export function fetchAccounts(): Promise<Account[]> {
  return get<Account[]>('/accounts')
}
