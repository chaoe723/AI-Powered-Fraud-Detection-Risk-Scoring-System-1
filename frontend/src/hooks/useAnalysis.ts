import { useQuery } from '@tanstack/react-query'
import { getAnalysis } from '../api/analyses'
import type { JobStatus } from '../types/api'

// Polling mỗi 1.5s khi job còn queued/processing (theo plan FE).
export function useAnalysis(id: number | string) {
  return useQuery({
    queryKey: ['analysis', String(id)],
    queryFn: () => getAnalysis(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status as JobStatus | undefined
      return status === 'queued' || status === 'processing' ? 1500 : false
    },
  })
}
