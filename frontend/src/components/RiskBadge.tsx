import { RISK_BADGE_CLASSES, RISK_LABELS } from '../constants/risk'
import type { RiskLevel } from '../types/api'

export function RiskBadge({ level }: { level: RiskLevel | string | null | undefined }) {
  if (!level) return <span className="text-slate-400">—</span>
  const classes = RISK_BADGE_CLASSES[level as RiskLevel] ?? 'bg-slate-100 text-slate-700 ring-slate-500/20'
  const label = RISK_LABELS[level as RiskLevel] ?? level
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${classes}`}>
      {label}
    </span>
  )
}
