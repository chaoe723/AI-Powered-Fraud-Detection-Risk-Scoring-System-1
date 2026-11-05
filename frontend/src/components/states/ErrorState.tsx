import { isApiError } from '../../api/client'

const CODE_HINTS: Record<string, string> = {
  NETWORK_ERROR: 'Backend chưa chạy hoặc sai cổng. Thử: python -m uvicorn backend.app:app --reload',
  ANALYSIS_NOT_FOUND: 'Phân tích không tồn tại hoặc đã bị xóa.',
  ANALYSIS_NOT_COMPLETED: 'Phân tích chưa hoàn tất, hãy chờ rồi thử lại.',
  MODEL_NOT_LOADED: 'Model chưa được nạp — chạy scripts/train_model.py trước.',
  UNSUPPORTED_FORMAT: 'Chỉ nhận file .csv hoặc .xlsx.',
  FILE_TOO_LARGE: 'File vượt giới hạn 20MB.',
  ROW_LIMIT_EXCEEDED: 'File vượt giới hạn 100.000 dòng.',
  INVALID_FILE: 'File không đọc được hoặc thiếu cột bắt buộc (amount, transaction_time).',
}

export function ErrorState({ error }: { error: unknown }) {
  const code = isApiError(error) ? error.code : undefined
  const message = error instanceof Error ? error.message : 'Đã xảy ra lỗi không xác định.'
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6" role="alert" data-testid="error-state">
      <p className="font-semibold text-red-800">{code ? `Lỗi ${code}` : 'Đã xảy ra lỗi'}</p>
      <p className="mt-1 text-sm text-red-700">{message}</p>
      {code && CODE_HINTS[code] ? <p className="mt-2 text-xs text-red-500">{CODE_HINTS[code]}</p> : null}
    </div>
  )
}
