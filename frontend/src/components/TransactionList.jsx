export default function TransactionList({ transactions, loading, hasMore, loadingMore, onLoadMore }) {
  return (
    <section className="card">
      <h2>Transactions</h2>
      {loading ? (
        <p className="muted">Loading…</p>
      ) : transactions.length === 0 ? (
        <p className="muted">No transactions yet.</p>
      ) : (
        <>
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
          {hasMore && (
            <button className="link-button" onClick={onLoadMore} disabled={loadingMore}>
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          )}
        </>
      )}
    </section>
  )
}
