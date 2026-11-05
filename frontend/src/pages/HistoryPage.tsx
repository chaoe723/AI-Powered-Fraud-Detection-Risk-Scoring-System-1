import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { deleteAnalysis, listAnalyses } from '../api/analyses'
import { ErrorState } from '../components/states/ErrorState'
import { Loading } from '../components/states/Loading'
import { JOB_STATUS_LABELS, formatDateTime, formatInt } from '../constants/risk'
import type { Analysis } from '../types/api'

const STATUS_CLASSES: Record<string, string> = {
  queued: 'bg-slate-100 text-slate-700',
  processing: 'bg-sky-100 text-sky-800',
  completed: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-red-100 text-red-800',
}

export function HistoryPage() {
  const [page, setPage] = useState(1)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const query = useQuery({ queryKey: ['analyses', page], queryFn: () => listAnalyses(page) })
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / (query.data?.page_size ?? 20)))

  useEffect(() => {
    if (query.data && page > totalPages) setPage(totalPages)
  }, [query.data, page, totalPages])

  const remove = useMutation({
    mutationFn: (id: number) => deleteAnalysis(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['analyses'] }),
  })

  if (query.isPending) return <Loading label="Đang tải lịch sử…" />
  if (query.isError) return <ErrorState error={query.error} />

  const data = query.data
  if (data.total === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center" data-testid="empty-history">
        <p className="text-base font-medium text-slate-700">Chưa có phân tích nào</p>
        <p className="mt-1 text-sm text-slate-500">Tải lên file giao dịch đầu tiên để bắt đầu.</p>
        <Link to="/" className="mt-4 inline-block rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700">
          Tải file lên
        </Link>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="history-table">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">File</th>
            <th className="px-4 py-3">Trạng thái</th>
            <th className="px-4 py-3">Số dòng</th>
            <th className="px-4 py-3">Ngưỡng</th>
            <th className="px-4 py-3">Tạo lúc</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.items.map((analysis: Analysis) => (
            <tr
              key={analysis.id}
              onClick={() => navigate(`/analyses/${analysis.id}`)}
              className="cursor-pointer hover:bg-slate-50"
              data-testid={`history-row-${analysis.id}`}
            >
              <td className="px-4 py-3 font-medium text-slate-800">{analysis.filename}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASSES[analysis.status] ?? 'bg-slate-100'}`}>
                  {JOB_STATUS_LABELS[analysis.status] ?? analysis.status}
                </span>
                {analysis.status === 'processing' ? (
                  <span className="ml-2 text-xs text-slate-400">{formatInt(analysis.processed_rows)}/{formatInt(analysis.row_count)}</span>
                ) : null}
              </td>
              <td className="px-4 py-3 text-slate-600">{formatInt(analysis.row_count)}</td>
              <td className="px-4 py-3 text-slate-600">{analysis.threshold_profile}</td>
              <td className="px-4 py-3 text-slate-600">{formatDateTime(analysis.created_at)}</td>
              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  disabled={remove.isPending}
                  onClick={(event) => {
                    event.stopPropagation()
                    if (window.confirm(`Xóa phân tích #${analysis.id} (${analysis.filename})?`)) remove.mutate(analysis.id)
                  }}
                  className="rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                  data-testid={`delete-${analysis.id}`}
                >
                  Xóa
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {remove.isError ? <ErrorState error={remove.error} /> : null}
      <div className="flex items-center justify-between border-t border-slate-200 p-4 text-sm text-slate-600">
        <span>Trang {data.page} / {totalPages} · {formatInt(data.total)} phiên phân tích</span>
        <div className="flex gap-2">
          <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-40">← Trước</button>
          <button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-40">Sau →</button>
        </div>
      </div>
    </div>
  )
}
