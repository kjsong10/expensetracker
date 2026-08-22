import { useState } from 'react'

const emptyForm = { date: '', merchant: '', amount: '', category: '' }

export default function TransactionForm({ onCreate, submitting }) {
  const [form, setForm] = useState(emptyForm)

  async function handleSubmit(e) {
    e.preventDefault()
    const created = await onCreate({
      date: form.date,
      merchant: form.merchant,
      amount: Number(form.amount),
      category: form.category || null,
    })
    if (created) setForm(emptyForm)
  }

  return (
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
  )
}
