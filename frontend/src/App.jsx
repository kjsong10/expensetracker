import { useEffect, useState } from 'react'
import { getCurrentUser, listTransactions, logout } from './api'
import LoginButton from './components/LoginButton'
import PlaidLinkButton from './components/PlaidLinkButton'
import SyncButton from './components/SyncButton'
import TransactionSummary from './components/TransactionSummary'
import TransactionList from './components/TransactionList'
import './App.css'

const PAGE_SIZE = 50

export default function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
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
      const data = await listTransactions({ limit: PAGE_SIZE, offset: 0 })
      setTransactions(data)
      setHasMore(data.length === PAGE_SIZE)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadMore() {
    setLoadingMore(true)
    setError(null)
    try {
      const data = await listTransactions({ limit: PAGE_SIZE, offset: transactions.length })
      setTransactions((prev) => [...prev, ...data])
      setHasMore(data.length === PAGE_SIZE)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingMore(false)
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
          <TransactionList
            transactions={transactions}
            loading={loading}
            hasMore={hasMore}
            loadingMore={loadingMore}
            onLoadMore={loadMore}
          />
        </>
      )}
    </>
  )
}
