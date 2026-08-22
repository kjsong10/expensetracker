# Expense Tracker

Minimal starter: FastAPI + Postgres backend, React frontend, containerized with Docker. Transactions come from manual entry or from a linked bank account via Plaid.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full write-up of what's here and why it's built this way.

## Run

Add your Plaid Sandbox credentials (free at [dashboard.plaid.com](https://dashboard.plaid.com)) to `.env` — see `.env.example` for the shape. Then:

```bash
docker compose up --build
```

Then visit:
- http://localhost:5173 — the React frontend
- http://localhost:8000/docs — interactive API docs
- http://localhost:8000/transactions/list?user_id=1 — list transactions for a user (raw JSON)

## What's here

- `api/main.py` — app entrypoint, CORS
- `api/database.py` — SQLModel engine/session setup
- `api/plaid_client.py` — configured `plaid-python` SDK client
- `api/models/transaction.py` — the `Transaction` table (per-user, tagged manual vs. Plaid)
- `api/models/user.py`, `api/models/plaid_item.py` — lightweight users, linked bank connections
- `api/routers/transactions.py`, `api/routers/users.py`, `api/routers/plaid.py` — endpoints
- `api/ml/classifier.py` — scikit-learn Pipeline that predicts a category for manually-entered transactions
- `frontend/src/App.jsx` — container: state + data fetching
- `frontend/src/components/` — `UserPicker`, `PlaidLinkButton`, `SyncButton`, `TransactionSummary`, `TransactionForm`, `TransactionList`
- `frontend/src/api.js` — API client used by the UI

## Next steps

- Real login (password/session/JWT auth) — today's `User` picker has no password, see [docs/ARCHITECTURE.md §3.7](docs/ARCHITECTURE.md#37-users--multi-tenancy)
- Encrypt Plaid access tokens at rest before using a non-Sandbox account
- Add nightly Airflow ETL job (data engineering layer)
- Add threat model doc
- Add edit/delete endpoints and automated tests (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#6-known-limitations--next-steps))
