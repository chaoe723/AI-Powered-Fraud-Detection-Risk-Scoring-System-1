import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createAnalysis } from '../api/analyses'
import { ErrorState } from '../components/states/ErrorState'
import { THRESHOLD_PROFILE_LABELS } from '../constants/risk'
import type { ThresholdProfile } from '../types/api'

const MAX_BYTES = 20 * 1024 * 1024
const PROFILES: ThresholdProfile[] = ['cost_optimal', 'high_recall', 'balanced', 'strict']

function validateFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!name.endsWith('.csv') && !name.endsWith('.xlsx')) return 'Chỉ nhận file .csv hoặc .xlsx.'
  if (file.size > MAX_BYTES) return 'File vượt giới hạn 20MB.'
  return null
}

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [profile, setProfile] = useState<ThresholdProfile>('cost_optimal')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (selected: File) => createAnalysis(selected, profile),
    onSuccess: (analysis) => {
      queryClient.invalidateQueries({ queryKey: ['analyses'] })
      navigate(`/analyses/${analysis.id}`)
    },
  })

  const pickFile = (selected: File | undefined | null) => {
    setLocalError(null)
    if (!selected) return
    const problem = validateFile(selected)
    if (problem) {
      setFile(null)
      setLocalError(problem)
      return
    }
    setFile(selected)
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!file) {
      setLocalError('Hãy chọn file dữ liệu giao dịch trước.')
      return
    }
    mutation.mutate(file)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h2 className="text-xl font-semibold text-slate-900">Phân tích dữ liệu giao dịch</h2>
      <p className="mt-1 text-sm text-slate-500">
        Tải lên file giao dịch (.csv/.xlsx, tối đa 20MB / 100.000 dòng). Hệ thống sẽ chấm điểm rủi ro từng giao
        dịch và tổng hợp dashboard.
      </p>
      <form onSubmit={submit} className="mt-6 space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => event.key === 'Enter' && inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            pickFile(event.dataTransfer.files?.[0])
          }}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-12 text-center transition ${
            dragging ? 'border-sky-500 bg-sky-50' : 'border-slate-300 hover:border-sky-400 hover:bg-slate-50'
          }`}
          data-testid="dropzone"
        >
          <svg className="h-10 w-10 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 16.5V6m0 0l-4 4m4-4l4 4M4 20h16" />
          </svg>
          {file ? (
            <>
              <p className="font-medium text-slate-800" data-testid="picked-filename">{file.name}</p>
              <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB — bấm để đổi file</p>
            </>
          ) : (
            <>
              <p className="font-medium text-slate-700">Kéo thả file vào đây hoặc bấm để chọn</p>
              <p className="text-xs text-slate-400">Hỗ trợ .csv và .xlsx · ví dụ: fraud_dashboard_dataset.csv</p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            className="hidden"
            onChange={(event) => pickFile(event.target.files?.[0])}
          />
        </div>

        <div>
          <label htmlFor="threshold_profile" className="block text-sm font-medium text-slate-700">
            Ngưỡng quyết định
          </label>
          <select
            id="threshold_profile"
            value={profile}
            onChange={(event) => setProfile(event.target.value as ThresholdProfile)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
          >
            {PROFILES.map((value) => (
              <option key={value} value={value}>
                {THRESHOLD_PROFILE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>

        {localError ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="local-error">
            {localError}
          </p>
        ) : null}
        {mutation.isError ? <ErrorState error={mutation.error} /> : null}

        <button
          type="submit"
          disabled={mutation.isPending || !file}
          className="w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="submit-upload"
        >
          {mutation.isPending ? 'Đang tải lên…' : 'Bắt đầu phân tích'}
        </button>
      </form>
    </div>
  )
}
