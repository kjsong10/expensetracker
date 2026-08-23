const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options) {
  const res = await fetch(`${API_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json()
}

export function getCurrentUser() {
  return request('/auth/me')
}

export function logout() {
  return request('/auth/logout', { method: 'POST' })
}

export function loginUrl() {
  return `${API_URL}/auth/login`
}

export function listTransactions({ limit = 50, offset = 0 } = {}) {
  return request(`/transactions/list?limit=${limit}&offset=${offset}`)
}

export function createTransaction(transaction) {
  return request('/transactions/create', {
    method: 'POST',
    body: JSON.stringify(transaction),
  })
}

export function createLinkToken() {
  return request('/plaid/link-token', { method: 'POST' })
}

export function exchangePublicToken(publicToken) {
  return request('/plaid/exchange-public-token', {
    method: 'POST',
    body: JSON.stringify({ public_token: publicToken }),
  })
}

export function syncTransactions() {
  return request('/plaid/sync-transactions', { method: 'POST' })
}
