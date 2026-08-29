import { useState } from 'react'
import { syncTransactions } from '../api'

export default function SyncButton({ onSynced }) {
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleSync() {
    setSyncing(true)
    setError(null)
    const totals = { added: 0, modified: 0, removed: 0 }
    try {
      let hasMore = true
      while (hasMore) {
        const res = await syncTransactions()
        totals.added += res.added
        totals.modified += res.modified
        totals.removed += res.removed
        hasMore = res.has_more
      }
      setResult(totals)
      await onSynced()
    }

    catch (err) {
      setError(err.message)
    }

    finally {
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
