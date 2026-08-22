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

export function listUsers() {
  return request('/users/list')
}

export function createUser(displayName) {
  return request('/users/create', {
    method: 'POST',
    body: JSON.stringify({ display_name: displayName }),
  })
}

export function listTransactions(userId) {
  return request(`/transactions/list?user_id=${userId}`)
}

export function createTransaction(transaction) {
  return request('/transactions/create', {
    method: 'POST',
    body: JSON.stringify(transaction),
  })
}

export function createLinkToken(userId) {
  return request('/plaid/link-token', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  })
}

export function exchangePublicToken(userId, publicToken) {
  return request('/plaid/exchange-public-token', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, public_token: publicToken }),
  })
}

export function syncTransactions(userId) {
  return request('/plaid/sync-transactions', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  })
}
