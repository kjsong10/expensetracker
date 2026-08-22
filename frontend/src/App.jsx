import { useEffect, useState } from 'react'
import { listTransactions, createTransaction } from './api'
import './App.css'

const emptyForm = { date: '', merchant: '', amount: '', category: '' }

export default function App() {
  const [transactions, setTransactions] = useState([])
  const [form, setForm] = useState(emptyForm)
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

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await createTransaction({
        date: form.date,
        merchant: form.merchant,
        amount: Number(form.amount),
        category: form.category || null,
      })
      setForm(emptyForm)
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const total = transactions.reduce((sum, t) => sum + t.amount, 0)

  return (
    <>
      <h1>Expense Tracker</h1>
      <p className="subtitle">
        {transactions.length} transaction{transactions.length === 1 ? '' : 's'} · total{' '}
        <strong>${total.toFixed(2)}</strong>
      </p>

      {error && <div className="error">{error}</div>}

      <section className="card">
        <h2>Add a transaction</h2>
        <form onSubmit={handleSubmit} className="form">
          <input
            type="date"
            required
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
          />
          <input
            type="text"
            placeholder="Merchant"
            required
            value={form.merchant}
            onChange={(e) => setForm({ ...form, merchant: e.target.value })}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            required
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
          />
          <input
            type="text"
            placeholder="Category (optional)"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          />
          <button type="submit" disabled={submitting}>
            {submitting ? 'Adding…' : 'Add'}
          </button>
        </form>
      </section>

      <section className="card">
        <h2>Transactions</h2>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : transactions.length === 0 ? (
          <p className="muted">No transactions yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Merchant</th>
                <th>Category</th>
                <th className="amount">Amount</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id}>
                  <td>{t.date}</td>
                  <td>{t.merchant}</td>
                  <td className="muted">{t.category || '—'}</td>
                  <td className="amount">${t.amount.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
