import type { Analysis, Paginated, ThresholdProfile, TransactionDetail, TransactionQuery, Transaction } from '../types/api'
import { apiFetch } from './client'

export function createAnalysis(file: File, thresholdProfile: ThresholdProfile): Promise<Analysis> {
  const form = new FormData()
  form.append('file', file)
  form.append('threshold_profile', thresholdProfile)
  return apiFetch<Analysis>('/analyses', { method: 'POST', body: form })
}

export function listAnalyses(page = 1, pageSize = 20): Promise<Paginated<Analysis>> {
  return apiFetch(`/analyses?page=${page}&page_size=${pageSize}`)
}

export function getAnalysis(id: number | string): Promise<Analysis> {
  return apiFetch(`/analyses/${id}`)
}

export function getTransactions(analysisId: number | string, query: TransactionQuery): Promise<Paginated<Transaction>> {
  const params = new URLSearchParams()
  params.set('page', String(query.page ?? 1))
  params.set('page_size', String(query.page_size ?? 20))
  if (query.risk_level) params.set('risk_level', query.risk_level)
  if (query.decision) params.set('decision', query.decision)
  if (query.q) params.set('q', query.q)
  if (query.sort) params.set('sort', query.sort)
  if (query.order) params.set('order', query.order)
  return apiFetch(`/analyses/${analysisId}/transactions?${params.toString()}`)
}

export function getTransactionDetail(analysisId: number | string, transactionId: string): Promise<TransactionDetail> {
  return apiFetch(`/analyses/${analysisId}/transactions/${encodeURIComponent(transactionId)}`)
}

export function deleteAnalysis(id: number): Promise<void> {
  return apiFetch(`/analyses/${id}`, { method: 'DELETE' })
}

export function getModelMeta() {
  return apiFetch<import('../types/api').ModelMeta>('/model/meta')
}

export function exportUrl(analysisId: number | string, format: 'csv' | 'xlsx'): string {
  return `/api/v1/analyses/${analysisId}/export?format=${format}`
}
