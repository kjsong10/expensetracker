export default function TransactionSummary({ count, total }) {
  return (
    <p className="subtitle">
      {count} transaction{count === 1 ? '' : 's'} · total <strong>${total.toFixed(2)}</strong>
    </p>
  )
}
