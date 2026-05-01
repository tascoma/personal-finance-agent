import { del, patch, post } from './client'
import type { Document } from '../types'

export function uploadDocument(
  periodId: string,
  formData: FormData,
): Promise<Document> {
  return post<Document>(`/periods/${periodId}/documents`, formData)
}

export function deleteDocument(periodId: string, documentId: string): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/periods/${periodId}/documents/${documentId}`)
}

export function parseDocument(periodId: string, documentId: string): Promise<Document> {
  return post<Document>(`/periods/${periodId}/documents/${documentId}/parse`)
}

export function unpostDocument(
  periodId: string,
  documentId: string,
): Promise<{ unposted: number }> {
  return post<{ unposted: number }>(`/periods/${periodId}/documents/${documentId}/unpost`)
}

export function setDocumentSourceAccount(
  periodId: string,
  documentId: string,
  sourceAccountCode: number | null,
): Promise<Document> {
  return patch<Document>(`/periods/${periodId}/documents/${documentId}/source-account`, {
    source_account_code: sourceAccountCode,
  })
}
