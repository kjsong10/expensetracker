import { useState } from 'react'
import { syncTransactions } from '../api'

export default function SyncButton({ userId, onSynced }) {
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleSync() {
    setSyncing(true)
    setError(null)
    try {
      const res = await syncTransactions(userId)
      setResult(res)
      await onSynced()
    } catch (err) {
      setError(err.message)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="plaid-action">
      <button onClick={handleSync} disabled={syncing}>
        {syncing ? 'Syncing…' : 'Sync transactions'}
      </button>
      {result && (
        <span className="muted">
          +{result.added} / ~{result.modified} / -{result.removed}
        </span>
      )}
      {error && <span className="error-inline">{error}</span>}
    </div>
  )
}
