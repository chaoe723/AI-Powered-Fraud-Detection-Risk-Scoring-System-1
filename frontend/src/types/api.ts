// Mirror 100% của plan/API_CONTRACT.md (bản v1.0.0).
// Field optional luôn render được khi thiếu — component phải có fallback.

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type Decision = 'allow' | 'manual_review' | 'block'
export type ThresholdProfile = 'high_recall' | 'balanced' | 'strict' | 'cost_optimal'
export type SortField = 'amount' | 'risk_score' | 'fraud_probability' | 'transaction_time'
export type SortOrder = 'asc' | 'desc'

export type ErrorCode =
  | 'UNSUPPORTED_FORMAT'
  | 'FILE_TOO_LARGE'
  | 'ROW_LIMIT_EXCEEDED'
  | 'INVALID_FILE'
  | 'VALIDATION_ERROR'
  | 'ANALYSIS_NOT_FOUND'
  | 'TRANSACTION_NOT_FOUND'
  | 'ANALYSIS_NOT_COMPLETED'
  | 'MODEL_NOT_LOADED'
  | 'NETWORK_ERROR'
  | 'HTTP_ERROR'

export interface AnalysisSummary {
  total_transactions: number
  flagged_transactions: number
  flagged_rate: number
  labeled_fraud_rate: number | null
  fraud_probability_avg: number
  risk_score_avg: number
  amount_total: number
  risk_distribution: Record<RiskLevel, number>
  decision_distribution: Record<Decision, number>
  trends: { date: string; transactions: number; flagged: number; avg_risk_score: number }[]
  device_breakdown: { device: string; transactions: number; flagged: number; fraud_probability_avg: number }[]
  country_breakdown: { country: string; transactions: number; flagged: number; fraud_probability_avg: number }[]
}

export interface Analysis {
  id: number
  filename: string
  status: JobStatus
  row_count: number | null
  processed_rows: number
  threshold_profile: ThresholdProfile
  error: string | null
  summary: AnalysisSummary | null
  created_at: string
  completed_at: string | null
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Transaction {
  transaction_id: string | null
  user_id: number
  transaction_time: string
  amount: number
  payment_method: string
  device: string
  country: string
  fraud_probability: number
  anomaly: boolean
  risk_score: number
  risk_level: RiskLevel
  decision: Decision
  reasons: string[]
}

export interface TransactionDetail extends Transaction {
  analysis_id: number
  threshold_profile: ThresholdProfile
  raw: Record<string, unknown>
}

export interface ModelMeta {
  model_loaded: boolean
  model_version: string
  schema_version: number | null
  feature_count: number | null
  thresholds: Partial<Record<ThresholdProfile, number>>
  metrics: {
    pr_auc: number | null
    roc_auc: number | null
    recall: number | null
    precision: number | null
  }
}

export interface TransactionQuery {
  page?: number
  page_size?: number
  risk_level?: RiskLevel | ''
  decision?: Decision | ''
  q?: string
  sort?: SortField
  order?: SortOrder
}
