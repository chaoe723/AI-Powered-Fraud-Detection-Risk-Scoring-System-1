import type { ErrorCode } from '../types/api'

// Envelope lỗi thống nhất của contract §5: {"error": {"code", "message"}}.
export class ApiError extends Error {
  readonly code: ErrorCode
  readonly status: number

  constructor(code: ErrorCode, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

const DEFAULT_TIMEOUT_MS = 60_000

export async function apiFetch<T>(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, { ...init, signal: AbortSignal.timeout(timeoutMs) })
  } catch {
    throw new ApiError('NETWORK_ERROR', 'Không kết nối được máy chủ. Kiểm tra backend đã chạy ở cổng 8000.', 0)
  }
  if (response.status === 204) return undefined as T
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) {
    const envelope = (body as { error?: { code?: string; message?: string } } | null)?.error
    throw new ApiError(
      (envelope?.code as ErrorCode) ?? 'HTTP_ERROR',
      envelope?.message ?? `Lỗi máy chủ (HTTP ${response.status}).`,
      response.status,
    )
  }
  return body as T
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}
