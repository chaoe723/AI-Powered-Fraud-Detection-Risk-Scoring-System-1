import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import { DashboardPage } from './pages/DashboardPage'
import { HistoryPage } from './pages/HistoryPage'
import { TransactionDetailPage } from './pages/TransactionDetailPage'
import { TransactionsPage } from './pages/TransactionsPage'
import { UploadPage } from './pages/UploadPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1 },
  },
})

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium ${isActive ? 'bg-sky-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-100 text-slate-900">
          <header className="border-b border-slate-200 bg-white">
            <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
              <Link to="/" className="text-base font-bold text-slate-900">
                Fraud Detection <span className="text-sky-600">&amp; Risk Scoring</span>
              </Link>
              <nav className="flex items-center gap-1">
                <NavLink to="/" end className={navLinkClass}>
                  Tải lên
                </NavLink>
                <NavLink to="/analyses" className={navLinkClass}>
                  Lịch sử
                </NavLink>
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">
            <Routes>
              <Route path="/" element={<UploadPage />} />
              <Route path="/analyses" element={<HistoryPage />} />
              <Route path="/analyses/:id" element={<DashboardPage />} />
              <Route path="/analyses/:id/transactions" element={<TransactionsPage />} />
              <Route path="/analyses/:id/transactions/:txnId" element={<TransactionDetailPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
