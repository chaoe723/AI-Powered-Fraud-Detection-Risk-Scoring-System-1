import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { getTransactions } from '../api/analyses'
import type { Decision, RiskLevel, SortField, SortOrder } from '../types/api'

// Filter/sort/page giữ trong URL search params để link chia sẻ được và
// back/forward của trình duyệt hoạt động đúng.
export function useTransactions(analysisId: number | string) {
  const [searchParams, setSearchParams] = useSearchParams()

  const query = {
    page: Math.max(1, Number(searchParams.get('page')) || 1),
    page_size: Math.min(100, Math.max(1, Number(searchParams.get('page_size')) || 20)),
    risk_level: (searchParams.get('risk_level') || '') as RiskLevel | '',
    decision: (searchParams.get('decision') || '') as Decision | '',
    q: searchParams.get('q') ?? '',
    sort: (searchParams.get('sort') || 'risk_score') as SortField,
    order: (searchParams.get('order') || 'desc') as SortOrder,
  }

  const setParam = (patch: Record<string, string | number | undefined>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(patch)) {
      if (value === undefined || value === '' || value === null) next.delete(key)
      else next.set(key, String(value))
    }
    if (!('page' in patch)) next.delete('page')
    setSearchParams(next)
  }

  const result = useQuery({
    queryKey: ['transactions', String(analysisId), query],
    queryFn: () => getTransactions(analysisId, query),
    retry: 1,
  })

  return { query, setParam, result }
}
