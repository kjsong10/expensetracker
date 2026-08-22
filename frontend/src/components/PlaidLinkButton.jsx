import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import { createLinkToken, exchangePublicToken, syncTransactions } from '../api'

export default function PlaidLinkButton({ onConnected }) {
  const [linkToken, setLinkToken] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    createLinkToken()
      .then((res) => setLinkToken(res.link_token))
      .catch((err) => setError(err.message))
  }, [])

  const onSuccess = useCallback(
    (publicToken) => {
      setConnecting(true)
      setError(null)
      exchangePublicToken(publicToken)
        .then(() => syncTransactions())
        .then(() => onConnected())
        .catch((err) => setError(err.message))
        .finally(() => setConnecting(false))
    },
    [onConnected]
  )

  const { open, ready } = usePlaidLink({ token: linkToken, onSuccess })

  return (
    <div className="plaid-action">
      <button onClick={() => open()} disabled={!ready || connecting}>
        {connecting ? 'Connecting…' : 'Connect a bank'}
      </button>
      {error && <span className="error-inline">{error}</span>}
    </div>
  )
}
