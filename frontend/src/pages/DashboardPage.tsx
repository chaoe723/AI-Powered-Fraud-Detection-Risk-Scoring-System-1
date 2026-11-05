import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { exportUrl, getModelMeta } from '../api/analyses'
import { ChartCard } from '../components/ChartCard'
import { StatCard } from '../components/StatCard'
import { ErrorState } from '../components/states/ErrorState'
import { Loading, SkeletonBlock } from '../components/states/Loading'
import {
  DECISION_CHART_COLORS, DECISION_LABELS, RISK_CHART_COLORS, RISK_LABELS,
  formatInt, formatPercent,
} from '../constants/risk'
import { useAnalysis } from '../hooks/useAnalysis'
import type { Decision, RiskLevel } from '../types/api'

export function DashboardPage() {
  const { id } = useParams<{ id: string }>()
  const analysisQuery = useAnalysis(id ?? '')
  const metaQuery = useQuery({ queryKey: ['model-meta'], queryFn: getModelMeta })

  if (analysisQuery.isPending) return <Loading label="Đang tải phân tích…" />
  if (analysisQuery.isError) return <ErrorState error={analysisQuery.error} />

  const analysis = analysisQuery.data

  if (analysis.status === 'queued' || analysis.status === 'processing') {
    return (
      <div className="space-y-4" data-testid="dashboard-processing">
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-800">
          <p className="font-medium">
            {analysis.status === 'queued' ? 'Đang chờ xử lý…' : 'Đang xử lý…'}
          </p>
          <p className="mt-1">
            {formatInt(analysis.processed_rows)} / {formatInt(analysis.row_count)} dòng — trang tự cập nhật.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <SkeletonBlock key={index} className="h-24" />
          ))}
        </div>
        <SkeletonBlock className="h-72" />
      </div>
    )
  }

  if (analysis.status === 'failed') {
    return (
      <div className="space-y-4">
        <ErrorState error={new Error(analysis.error ?? 'Job phân tích thất bại.')} />
        <Link to="/analyses" className="text-sm font-medium text-sky-600 hover:underline">← Về lịch sử</Link>
      </div>
    )
  }

  const summary = analysis.summary
  if (!summary) return <ErrorState error={new Error('Phân tích hoàn tất nhưng thiếu dữ liệu tổng hợp.')} />

  const riskData = (Object.entries(summary.risk_distribution) as [RiskLevel, number][]).map(([level, count]) => ({
    name: RISK_LABELS[level],
    level,
    value: count,
  }))
  const decisionData = (Object.entries(summary.decision_distribution) as [Decision, number][]).map(([decision, count]) => ({
    name: DECISION_LABELS[decision],
    decision,
    value: count,
  }))

  return (
    <div className="space-y-5" data-testid="dashboard-completed">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">{analysis.filename}</h2>
          <p className="text-sm text-slate-500">
            Phân tích #{analysis.id} · {formatInt(summary.total_transactions)} giao dịch · ngưỡng{' '}
            <span className="font-medium">{analysis.threshold_profile}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={exportUrl(analysis.id, 'csv')}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            data-testid="export-csv"
          >
            Export CSV
          </a>
          <a
            href={exportUrl(analysis.id, 'xlsx')}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            data-testid="export-xlsx"
          >
            Export XLSX
          </a>
          <Link
            to={`/analyses/${analysis.id}/transactions?sort=risk_score&order=desc`}
            className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-700"
            data-testid="cta-high-risk"
          >
            Giao dịch rủi ro cao →
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="Tổng giao dịch" value={formatInt(summary.total_transactions)} />
        <StatCard label="Tỷ lệ bị gắn cờ" value={formatPercent(summary.flagged_rate)} hint={`${formatInt(summary.flagged_transactions)} giao dịch`} />
        <StatCard label="Điểm rủi ro TB" value={summary.risk_score_avg.toFixed(2)} hint="thang 0–100" />
        <StatCard label="Xác suất lừa đảo TB" value={formatPercent(summary.fraud_probability_avg)} />
        <StatCard
          label="Tỷ lệ lừa đảo (nhãn)"
          value={summary.labeled_fraud_rate === null ? '—' : formatPercent(summary.labeled_fraud_rate)}
          hint={summary.labeled_fraud_rate === null ? 'file không có cột is_fraud' : 'từ cột nhãn trong file'}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Phân bố mức rủi ro">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={riskData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={2}>
                {riskData.map((entry) => (
                  <Cell key={entry.level} fill={RISK_CHART_COLORS[entry.level]} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => formatInt(value)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Phân bố quyết định">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={decisionData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value: number) => formatInt(value)} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {decisionData.map((entry) => (
                  <Cell key={entry.decision} fill={DECISION_CHART_COLORS[entry.decision]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard title="Xu hướng giao dịch theo ngày">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={summary.trends}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="transactions" name="Giao dịch" stroke="#0ea5e9" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="flagged" name="Bị gắn cờ" stroke="#ef4444" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        {([
          ['Giao dịch theo thiết bị (top 10)', summary.device_breakdown, 'device'],
          ['Giao dịch theo quốc gia (top 10)', summary.country_breakdown, 'country'],
        ] as const).map(([title, rows, key]) => (
          <ChartCard key={key} title={title}>
            <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 36 + 40)}>
              <BarChart data={rows} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey={key} width={90} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="transactions" name="Giao dịch" fill="#0ea5e9" radius={[0, 6, 6, 0]} />
                <Bar dataKey="flagged" name="Bị gắn cờ" fill="#ef4444" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        ))}
      </div>

      {metaQuery.data && !metaQuery.data.model_loaded ? (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
          Cảnh báo: model chưa được nạp — kết quả có thể không chính xác.
        </p>
      ) : null}
    </div>
  )
}
