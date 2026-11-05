import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { getTransactionDetail } from '../api/analyses'
import { DecisionBadge } from '../components/DecisionBadge'
import { RiskBadge } from '../components/RiskBadge'
import { ErrorState } from '../components/states/ErrorState'
import { Loading } from '../components/states/Loading'
import { REASON_LABELS, formatAmount, formatDateTime, formatPercent } from '../constants/risk'

// Cột bắt buộc hiển thị riêng ở bảng thuộc tính; phần còn lại của raw gộp xuống "Dữ liệu gốc".
const PRIMARY_FIELDS = ['transaction_id', 'user_id', 'transaction_time', 'amount', 'payment_method', 'device', 'country']

export function TransactionDetailPage() {
  const { id, txnId } = useParams<{ id: string; txnId: string }>()
  const query = useQuery({
    queryKey: ['transaction', id, txnId],
    queryFn: () => getTransactionDetail(id ?? '', txnId ?? ''),
    retry: false,
  })

  if (query.isPending) return <Loading label="Đang tải chi tiết…" />
  if (query.isError) return <ErrorState error={query.error} />

  const detail = query.data
  const rawExtras = Object.entries(detail.raw ?? {}).filter(([key]) => !PRIMARY_FIELDS.includes(key))
  const txnIdLabel = detail.transaction_id ?? '—'

  return (
    <div className="mx-auto max-w-3xl space-y-5" data-testid="transaction-detail">
      <div className="flex items-center justify-between">
        <Link to={`/analyses/${detail.analysis_id}/transactions`} className="text-sm font-medium text-sky-600 hover:underline">
          ← Về danh sách giao dịch
        </Link>
        <span className="text-xs text-slate-400">phân tích #{detail.analysis_id} · ngưỡng {detail.threshold_profile}</span>
      </div>

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <p className="text-sm text-slate-500">Điểm rủi ro</p>
          <p className="text-5xl font-bold text-slate-900" data-testid="risk-score">
            {detail.risk_score.toFixed(0)}
            <span className="text-xl font-medium text-slate-400">/100</span>
          </p>
        </div>
        <div className="ml-auto flex flex-col items-end gap-2">
          <RiskBadge level={detail.risk_level} />
          <DecisionBadge decision={detail.decision} />
          <span className="text-xs text-slate-500">{formatPercent(detail.fraud_probability)} xác suất lừa đảo · {detail.anomaly ? 'bất thường' : 'bình thường'}</span>
        </div>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700">Tại sao? (Why?)</h3>
        <ul className="mt-3 space-y-2" data-testid="reasons-list">
          {detail.reasons.length === 0 ? (
            <li className="text-sm text-slate-500">Không có cảnh báo nào — giao dịch ở mức cho phép.</li>
          ) : (
            detail.reasons.map((reason) => (
              <li key={reason} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="mt-0.5 h-4 w-4 flex-none rounded-full bg-red-100 text-center text-xs font-bold leading-4 text-red-700">!</span>
                {REASON_LABELS[reason] ?? reason}
              </li>
            ))
          )}
        </ul>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <h3 className="border-b border-slate-100 px-6 py-3 text-sm font-semibold text-slate-700">Thuộc tính giao dịch</h3>
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <tbody className="divide-y divide-slate-100">
            <tr><th className="w-1/3 px-6 py-2.5 text-left font-medium text-slate-500">Mã GD</th><td className="px-6 py-2.5 text-slate-800">{txnIdLabel}</td></tr>
            <tr><th className="px-6 py-2.5 text-left font-medium text-slate-500">User</th><td className="px-6 py-2.5 text-slate-800">{detail.user_id}</td></tr>
            <tr><th className="px-6 py-2.5 text-left font-medium text-slate-500">Thời gian</th><td className="px-6 py-2.5 text-slate-800">{formatDateTime(detail.transaction_time)}</td></tr>
            <tr><th className="px-6 py-2.5 text-left font-medium text-slate-500">Số tiền</th><td className="px-6 py-2.5 text-slate-800">{formatAmount(detail.amount)}</td></tr>
            <tr><th className="px-6 py-2.5 text-left font-medium text-slate-500">Phương thức</th><td className="px-6 py-2.5 text-slate-800">{detail.payment_method}</td></tr>
            <tr><th className="px-6 py-2.5 text-left font-medium text-slate-500">Thiết bị / Quốc gia</th><td className="px-6 py-2.5 text-slate-800">{detail.device} · {detail.country}</td></tr>
            {rawExtras.map(([key, value]) => (
              <tr key={key}>
                <th className="px-6 py-2.5 text-left font-medium text-slate-500">{key}</th>
                <td className="px-6 py-2.5 text-slate-800">{value === null || value === undefined ? '—' : String(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
