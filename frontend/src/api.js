const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json()
}

export function listTransactions() {
  return request('/transactions/list')
}

export function createTransaction(transaction) {
  return request('/transactions/create', {
    method: 'POST',
    body: JSON.stringify(transaction),
  })
}
