import { del, get, post } from './client'
import type { JournalEntryWithLines, JournalPageResponse, ManualJournalEntryCreate } from '../types'

export function fetchJournalPage(periodId: string): Promise<JournalPageResponse> {
  return get<JournalPageResponse>(`/periods/${periodId}/journal`)
}

export function classifyTransactions(periodId: string): Promise<{ classified: number }> {
  return post<{ classified: number }>(`/periods/${periodId}/classify`)
}

export function postTransactions(periodId: string): Promise<{ posted: number }> {
  return post<{ posted: number }>(`/periods/${periodId}/post`)
}

export function createManualJournalEntry(
  periodId: string,
  body: ManualJournalEntryCreate,
): Promise<JournalEntryWithLines> {
  return post<JournalEntryWithLines>(`/periods/${periodId}/journal/entries`, body)
}

export function deleteJournalEntry(periodId: string, entryId: string): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/periods/${periodId}/journal/entries/${entryId}`)
}
