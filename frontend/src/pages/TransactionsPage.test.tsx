import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, vi } from 'vitest'
import { TransactionsPage } from './TransactionsPage'
import type { Paginated, Transaction } from '../types/api'

vi.mock('../api/analyses', () => ({
  getTransactions: vi.fn(),
}))

import { getTransactions } from '../api/analyses'

const sample: Paginated<Transaction> = {
  items: [
    {
      transaction_id: 'txn_0001', user_id: 7, transaction_time: '2025-08-01T08:13:00', amount: 4200.5,
      payment_method: 'Visa', device: 'Mobile', country: 'USA', fraud_probability: 0.87, anomaly: true,
      risk_score: 91.2, risk_level: 'critical', decision: 'manual_review',
      reasons: ['high_model_probability', 'high_transaction_amount'],
    },
    {
      transaction_id: 'txn_0002', user_id: 9, transaction_time: '2025-08-01T09:00:00', amount: 120,
      payment_method: 'PayPal', device: 'Desktop', country: 'UK', fraud_probability: 0.01, anomaly: false,
      risk_score: 4.5, risk_level: 'low', decision: 'allow', reasons: [],
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/analyses/1/transactions']}>
        <Routes>
          <Route path="/analyses/:id/transactions" element={<TransactionsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TransactionsPage', () => {
  it('render bảng giao dịch theo contract JSON mẫu', async () => {
    vi.mocked(getTransactions).mockResolvedValue(sample)
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('txn_0001')).toBeInTheDocument()
    })
    expect(screen.getByText('txn_0002')).toBeInTheDocument()
    // "Nghiêm trọng" xuất hiện ở cả badge và option trong dropdown lọc.
    expect(screen.getAllByText('Nghiêm trọng').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Rà soát thủ công').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Thấp').length).toBeGreaterThan(0)
  })

  it('hiển thị empty state khi không có giao dịch', async () => {
    vi.mocked(getTransactions).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('transactions-empty')).toBeInTheDocument()
    })
  })

  it('gọi API với sort mặc định risk_score desc', async () => {
    vi.mocked(getTransactions).mockResolvedValue(sample)
    renderPage()
    await waitFor(() => {
      expect(getTransactions).toHaveBeenCalledWith('1', expect.objectContaining({ sort: 'risk_score', order: 'desc', page: 1 }))
    })
  })

  it('search nhập liệu debounce rồi gọi lại API với q', async () => {
    vi.mocked(getTransactions).mockResolvedValue(sample)
    renderPage()
    const input = await screen.findByTestId('search-input')
    fireEvent.change(input, { target: { value: 'USA' } })
    await waitFor(() => {
      expect(getTransactions).toHaveBeenCalledWith('1', expect.objectContaining({ q: 'USA' }))
    }, { timeout: 2000 })
  })
})
