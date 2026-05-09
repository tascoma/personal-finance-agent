import { type ReactNode } from 'react'
import { Navigate, Routes, Route } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import DashboardPage from './pages/DashboardPage'
import AccountsPage from './pages/AccountsPage'
import LedgerPage from './pages/LedgerPage'
import StatementsPage from './pages/StatementsPage'
import PeriodsListPage from './pages/PeriodsListPage'
import PeriodDetailPage from './pages/PeriodDetailPage'
import TransactionsPage from './pages/TransactionsPage'
import JournalPage from './pages/JournalPage'
import ReconcilePage from './pages/ReconcilePage'
import LoginPage from './pages/LoginPage'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { token, isLoading } = useAuth()
  if (isLoading) return <div style={{ padding: 24, color: 'var(--text-3)' }}>Loading…</div>
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/accounts" element={<ProtectedRoute><AccountsPage /></ProtectedRoute>} />
        {/* /ledger/statements must come before /ledger to avoid prefix match */}
        <Route path="/ledger/statements" element={<ProtectedRoute><StatementsPage /></ProtectedRoute>} />
        <Route path="/ledger" element={<ProtectedRoute><LedgerPage /></ProtectedRoute>} />
        <Route path="/periods" element={<ProtectedRoute><PeriodsListPage /></ProtectedRoute>} />
        <Route path="/periods/:periodId" element={<ProtectedRoute><PeriodDetailPage /></ProtectedRoute>} />
        <Route path="/periods/:periodId/transactions" element={<ProtectedRoute><TransactionsPage /></ProtectedRoute>} />
        <Route path="/periods/:periodId/journal" element={<ProtectedRoute><JournalPage /></ProtectedRoute>} />
        <Route path="/periods/:periodId/reconcile" element={<ProtectedRoute><ReconcilePage /></ProtectedRoute>} />
      </Routes>
    </ErrorBoundary>
  )
}
