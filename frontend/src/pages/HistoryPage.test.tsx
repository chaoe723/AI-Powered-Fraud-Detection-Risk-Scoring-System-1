import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { it, vi } from 'vitest'
import { HistoryPage } from './HistoryPage'
import { deleteAnalysis, listAnalyses } from '../api/analyses'
import type { Analysis } from '../types/api'

vi.mock('../api/analyses', () => ({ listAnalyses: vi.fn(), deleteAnalysis: vi.fn() }))

it('navigates history pages and returns to the previous page after deleting the last item', async () => {
  const analysis: Analysis = {
    id: 1, filename: 'older.csv', status: 'completed', row_count: 2, processed_rows: 2,
    threshold_profile: 'strict', error: null, summary: null,
    created_at: '2025-05-01T00:00:00', completed_at: '2025-05-01T00:01:00',
  }
  let deleted = false
  vi.mocked(listAnalyses).mockImplementation(async (page = 1) => ({
    items: page === 1 ? [{ ...analysis, id: 21, filename: 'latest.csv' }] : deleted ? [] : [analysis],
    total: deleted ? 20 : 21, page, page_size: 20,
  }))
  vi.mocked(deleteAnalysis).mockImplementation(async () => { deleted = true })
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><HistoryPage /></MemoryRouter></QueryClientProvider>)
  await screen.findByText('latest.csv')
  expect(screen.getByRole('button', { name: '← Trước' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Sau →' }))
  await screen.findByText('older.csv')
  expect(screen.getByRole('button', { name: 'Sau →' })).toBeDisabled()
  fireEvent.click(screen.getByTestId('delete-1'))
  await waitFor(() => expect(deleteAnalysis).toHaveBeenCalledWith(1))
  await screen.findByText('latest.csv')
  expect(screen.getByRole('button', { name: '← Trước' })).toBeDisabled()
  confirm.mockRestore()
})
