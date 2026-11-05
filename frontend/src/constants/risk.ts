import type { Decision, RiskLevel, ThresholdProfile } from '../types/api'

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: 'Thấp',
  medium: 'Trung bình',
  high: 'Cao',
  critical: 'Nghiêm trọng',
}

// Màu pill theo plan FE — chỉ dựa vào risk_level BE trả, không hardcode ngưỡng điểm.
export const RISK_BADGE_CLASSES: Record<RiskLevel, string> = {
  low: 'bg-emerald-100 text-emerald-800 ring-emerald-600/20',
  medium: 'bg-amber-100 text-amber-800 ring-amber-600/20',
  high: 'bg-orange-100 text-orange-800 ring-orange-600/20',
  critical: 'bg-red-100 text-red-800 ring-red-600/20',
}

export const RISK_CHART_COLORS: Record<RiskLevel, string> = {
  low: '#10b981',
  medium: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
}

export const DECISION_LABELS: Record<Decision, string> = {
  allow: 'Cho phép',
  manual_review: 'Rà soát thủ công',
  block: 'Chặn',
}

export const DECISION_BADGE_CLASSES: Record<Decision, string> = {
  allow: 'bg-emerald-100 text-emerald-800 ring-emerald-600/20',
  manual_review: 'bg-amber-100 text-amber-800 ring-amber-600/20',
  block: 'bg-red-100 text-red-800 ring-red-600/20',
}

export const DECISION_CHART_COLORS: Record<Decision, string> = {
  allow: '#10b981',
  manual_review: '#f59e0b',
  block: '#ef4444',
}

export const THRESHOLD_PROFILE_LABELS: Record<ThresholdProfile, string> = {
  high_recall: 'High recall — bắt nhiều, dễ nhầm',
  balanced: 'Balanced — cân bằng',
  strict: 'Strict — nghiêm ngặt (có chặn)',
  cost_optimal: 'Cost optimal — tối ưu chi phí (mặc định)',
}

export const REASON_LABELS: Record<string, string> = {
  high_model_probability: 'Xác suất gian lận cao (≥ ngưỡng của profile)',
  anomalous_transaction_pattern: 'Mẫu giao dịch bất thường (Isolation Forest)',
  high_transaction_amount: 'Số tiền lớn bất thường (≥ 3.000)',
}

export const JOB_STATUS_LABELS: Record<string, string> = {
  queued: 'Đang chờ',
  processing: 'Đang xử lý',
  completed: 'Hoàn tất',
  failed: 'Lỗi',
}

const numberFormat = new Intl.NumberFormat('vi-VN')
const percentFormat = new Intl.NumberFormat('vi-VN', { style: 'percent', maximumFractionDigits: 2 })

export function formatInt(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : numberFormat.format(value)
}

export function formatAmount(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : numberFormat.format(Math.round(value * 100) / 100)
}

export function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : percentFormat.format(value)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('vi-VN')
}

export function isRiskLevel(value: string | null | undefined): value is RiskLevel {
  return value === 'low' || value === 'medium' || value === 'high' || value === 'critical'
}

export function isDecision(value: string | null | undefined): value is Decision {
  return value === 'allow' || value === 'manual_review' || value === 'block'
}
