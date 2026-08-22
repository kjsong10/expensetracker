import { useEffect, useState } from 'react'
import { listTransactions, createTransaction } from './api'
import UserPicker from './components/UserPicker'
import PlaidLinkButton from './components/PlaidLinkButton'
import SyncButton from './components/SyncButton'
import TransactionSummary from './components/TransactionSummary'
import TransactionForm from './components/TransactionForm'
import TransactionList from './components/TransactionList'
import './App.css'

const USER_ID_KEY = 'expense-tracker-user-id'

export default function App() {
  const [userId, setUserId] = useState(() => {
    const stored = localStorage.getItem(USER_ID_KEY)
    return stored ? Number(stored) : null
  })
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (userId) {
      localStorage.setItem(USER_ID_KEY, String(userId))
      refresh()
    } else {
      setTransactions([])
    }
  }, [userId])

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const data = await listTransactions(userId)
      data.sort((a, b) => (a.date < b.date ? 1 : -1))
      setTransactions(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(fields) {
    setSubmitting(true)
    setError(null)
    try {
      await createTransaction({ ...fields, user_id: userId })
      await refresh()
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setSubmitting(false)
    }
  }

  const total = transactions.reduce((sum, t) => sum + t.amount, 0)

  return (
    <>
      <h1>Expense Tracker</h1>

      <UserPicker userId={userId} onSelectUser={setUserId} />

      {error && <div className="error">{error}</div>}

      {userId && (
        <>
          <section className="card plaid-actions">
            <PlaidLinkButton userId={userId} onConnected={refresh} />
            <SyncButton userId={userId} onSynced={refresh} />
          </section>

          <TransactionSummary count={transactions.length} total={total} />
          <TransactionForm onCreate={handleCreate} submitting={submitting} />
          <TransactionList transactions={transactions} loading={loading} />
        </>
      )}
    </>
  )
}
