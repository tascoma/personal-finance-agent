import { Routes, Route } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import AccountsPage from './pages/AccountsPage'
import LedgerPage from './pages/LedgerPage'
import StatementsPage from './pages/StatementsPage'
import PeriodsListPage from './pages/PeriodsListPage'
import PeriodDetailPage from './pages/PeriodDetailPage'
import TransactionsPage from './pages/TransactionsPage'
import JournalPage from './pages/JournalPage'
import ReconcilePage from './pages/ReconcilePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/accounts" element={<AccountsPage />} />
      {/* /ledger/statements must come before /ledger to avoid prefix match */}
      <Route path="/ledger/statements" element={<StatementsPage />} />
      <Route path="/ledger" element={<LedgerPage />} />
      <Route path="/periods" element={<PeriodsListPage />} />
      <Route path="/periods/:periodId" element={<PeriodDetailPage />} />
      <Route path="/periods/:periodId/transactions" element={<TransactionsPage />} />
      <Route path="/periods/:periodId/journal" element={<JournalPage />} />
      <Route path="/periods/:periodId/reconcile" element={<ReconcilePage />} />
    </Routes>
  )
}
