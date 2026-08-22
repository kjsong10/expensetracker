import { useEffect, useState } from 'react'
import { listTransactions, createTransaction } from './api'
import TransactionSummary from './components/TransactionSummary'
import TransactionForm from './components/TransactionForm'
import TransactionList from './components/TransactionList'
import './App.css'

export default function App() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    refresh()
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

  async function handleCreate(payload) {
    setSubmitting(true)
    setError(null)
    try {
      await createTransaction(payload)
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
      <TransactionSummary count={transactions.length} total={total} />

      {error && <div className="error">{error}</div>}

      <TransactionForm onCreate={handleCreate} submitting={submitting} />
      <TransactionList transactions={transactions} loading={loading} />
    </>
  )
}
