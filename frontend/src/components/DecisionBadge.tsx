import { DECISION_BADGE_CLASSES, DECISION_LABELS } from '../constants/risk'
import type { Decision } from '../types/api'

export function DecisionBadge({ decision }: { decision: Decision | string | null | undefined }) {
  if (!decision) return <span className="text-slate-400">—</span>
  const classes = DECISION_BADGE_CLASSES[decision as Decision] ?? 'bg-slate-100 text-slate-700 ring-slate-500/20'
  const label = DECISION_LABELS[decision as Decision] ?? decision
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${classes}`}>
      {label}
    </span>
  )
}
