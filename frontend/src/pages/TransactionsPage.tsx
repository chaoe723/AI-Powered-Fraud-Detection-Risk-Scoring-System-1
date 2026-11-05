import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { DecisionBadge } from '../components/DecisionBadge'
import { RiskBadge } from '../components/RiskBadge'
import { ErrorState } from '../components/states/ErrorState'
import { Loading } from '../components/states/Loading'
import { DECISION_LABELS, formatAmount, formatDateTime, formatInt, formatPercent } from '../constants/risk'
import { useTransactions } from '../hooks/useTransactions'
import type { Decision, SortField } from '../types/api'

const SORT_COLUMNS: { field: SortField; label: string }[] = [
  { field: 'transaction_time', label: 'Thời gian' },
  { field: 'amount', label: 'Số tiền' },
  { field: 'risk_score', label: 'Điểm rủi ro' },
  { field: 'fraud_probability', label: 'Xác suất' },
]

export function TransactionsPage() {
  const { id } = useParams<{ id: string }>()
  const analysisId = id ?? ''
  const { query, setParam, result } = useTransactions(analysisId)
  const [searchDraft, setSearchDraft] = useState(query.q)

  // Debounce ô search 300ms rồi mới đẩy vào URL params (gọi API).
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchDraft !== query.q) setParam({ q: searchDraft || undefined })
    }, 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchDraft])

  if (result.isPending) return <Loading label="Đang tải giao dịch…" />
  if (result.isError) return <ErrorState error={result.error} />

  const data = result.data

  const toggleSort = (field: SortField) => {
    if (query.sort === field) setParam({ sort: field, order: query.order === 'desc' ? 'asc' : 'desc' })
    else setParam({ sort: field, order: 'desc' })
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size))

  return (
    <div className="space-y-4" data-testid="transactions-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Giao dịch — phân tích #{analysisId}</h2>
          <p className="text-sm text-slate-500">{formatInt(data.total)} giao dịch khớp bộ lọc</p>
        </div>
        <Link to={`/analyses/${analysisId}`} className="text-sm font-medium text-sky-600 hover:underline">
          ← Về dashboard
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <input
          type="search"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Tìm theo mã GD, user, quốc gia, thiết bị…"
          className="min-w-[240px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
          data-testid="search-input"
        />
        <select
          value={query.risk_level}
          onChange={(event) => setParam({ risk_level: event.target.value || undefined })}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          aria-label="Lọc mức rủi ro"
        >
          <option value="">Mọi mức rủi ro</option>
          <option value="low">Thấp</option>
          <option value="medium">Trung bình</option>
          <option value="high">Cao</option>
          <option value="critical">Nghiêm trọng</option>
        </select>
        <select
          value={query.decision}
          onChange={(event) => setParam({ decision: event.target.value || undefined })}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          aria-label="Lọc quyết định"
        >
          <option value="">Mọi quyết định</option>
          {(Object.entries(DECISION_LABELS) as [Decision, string][]).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Mã GD</th>
              {SORT_COLUMNS.map((column) => (
                <th key={column.field} className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => toggleSort(column.field)}
                    className="flex items-center gap-1 uppercase hover:text-slate-800"
                  >
                    {column.label}
                    {query.sort === column.field ? <span aria-hidden>{query.order === 'desc' ? '↓' : '↑'}</span> : null}
                  </button>
                </th>
              ))}
              <th className="px-4 py-3">Quốc gia / Thiết bị</th>
              <th className="px-4 py-3">Mức rủi ro</th>
              <th className="px-4 py-3">Quyết định</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.items.map((item) => (
              <tr key={item.transaction_id ?? `${item.user_id}-${item.transaction_time}`} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link
                    to={`/analyses/${analysisId}/transactions/${encodeURIComponent(item.transaction_id ?? '')}`}
                    className="font-medium text-sky-700 hover:underline"
                  >
                    {item.transaction_id ?? '—'}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-600">{formatDateTime(item.transaction_time)}</td>
                <td className="px-4 py-3 text-slate-800">{formatAmount(item.amount)}</td>
                <td className="px-4 py-3 font-semibold text-slate-900">{item.risk_score.toFixed(1)}</td>
                <td className="px-4 py-3 text-slate-600">{formatPercent(item.fraud_probability)}</td>
                <td className="px-4 py-3 text-slate-600">
                  {item.country} · {item.device}
                </td>
                <td className="px-4 py-3"><RiskBadge level={item.risk_level} /></td>
                <td className="px-4 py-3"><DecisionBadge decision={item.decision} /></td>
              </tr>
            ))}
            {data.items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-500" data-testid="transactions-empty">
                  Không có giao dịch nào khớp bộ lọc.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-600">
        <span>
          Trang {data.page} / {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={data.page <= 1}
            onClick={() => setParam({ page: data.page - 1 })}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-medium hover:bg-slate-50 disabled:opacity-40"
          >
            ← Trước
          </button>
          <button
            type="button"
            disabled={data.page >= totalPages}
            onClick={() => setParam({ page: data.page + 1 })}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-medium hover:bg-slate-50 disabled:opacity-40"
          >
            Sau →
          </button>
        </div>
      </div>
    </div>
  )
}
