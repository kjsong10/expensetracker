import { useEffect, useState } from 'react'
import { getCurrentUser, listTransactions, createTransaction, logout } from './api'
import LoginButton from './components/LoginButton'
import PlaidLinkButton from './components/PlaidLinkButton'
import SyncButton from './components/SyncButton'
import TransactionSummary from './components/TransactionSummary'
import TransactionForm from './components/TransactionForm'
import TransactionList from './components/TransactionList'
import './App.css'

export default function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getCurrentUser()
      .then((user) => {
        setCurrentUser(user)
        return refresh()
      })
      .catch(() => setCurrentUser(null))
      .finally(() => setCheckingAuth(false))
  }, [])

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const data = await listTransactions()
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
      await createTransaction(fields)
      await refresh()
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setSubmitting(false)
    }
  }

  async function handleLogout() {
    await logout()
    setCurrentUser(null)
    setTransactions([])
  }

  const total = transactions.reduce((sum, t) => sum + t.amount, 0)

  if (checkingAuth) {
    return <h1>Expense Tracker</h1>
  }

  return (
    <>
      <h1>Expense Tracker</h1>

      {!currentUser ? (
        <LoginButton />
      ) : (
        <>
          <p className="subtitle">
            Signed in as <strong>{currentUser.display_name}</strong> ·{' '}
            <button className="link-button" onClick={handleLogout}>
              Log out
            </button>
          </p>

          {error && <div className="error">{error}</div>}

          <section className="card plaid-actions">
            <PlaidLinkButton onConnected={refresh} />
            <SyncButton onSynced={refresh} />
          </section>

          <TransactionSummary count={transactions.length} total={total} />
          <TransactionForm onCreate={handleCreate} submitting={submitting} />
          <TransactionList transactions={transactions} loading={loading} />
        </>
      )}
    </>
  )
}
