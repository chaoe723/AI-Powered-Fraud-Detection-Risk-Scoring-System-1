import { ApiError, apiFetch } from './client'

const okResponse = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })

afterEach(() => vi.restoreAllMocks())

test('apiFetch trả dữ liệu khi 200', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => okResponse({ id: 1, status: 'queued' })))
  const data = await apiFetch<{ id: number; status: string }>('/analyses/1')
  expect(data.id).toBe(1)
  expect(fetch).toHaveBeenCalledWith('/api/v1/analyses/1', expect.anything())
})

test('apiFetch parse envelope lỗi contract §5 thành ApiError', async () => {
  const errorResponse = (body: unknown, status: number) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  vi.stubGlobal('fetch', vi.fn(async () =>
    errorResponse({ error: { code: 'ANALYSIS_NOT_FOUND', message: 'Analysis 99 does not exist' } }, 404),
  ))
  await expect(apiFetch('/analyses/99')).rejects.toMatchObject({
    code: 'ANALYSIS_NOT_FOUND',
    status: 404,
    message: 'Analysis 99 does not exist',
  })
})

test('lỗi mạng trở thành NETWORK_ERROR, không crash', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => {
    throw new TypeError('Failed to fetch')
  }))
  let error: ApiError | undefined
  try {
    await apiFetch('/analyses')
  } catch (caught) {
    error = caught as ApiError
  }
  expect(error).toBeInstanceOf(ApiError)
  expect(error?.code).toBe('NETWORK_ERROR')
})

test('response 204 trả undefined mà không parse JSON', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
  await expect(apiFetch('/analyses/1', { method: 'DELETE' })).resolves.toBeUndefined()
})
