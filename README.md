# Expense Tracker

Minimal starter: FastAPI + Postgres backend, React frontend, containerized with Docker. Sign in with Google to see your own transactions, entered manually or synced from a linked bank account via Plaid.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full write-up of what's here and why it's built this way, and [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for exactly how the login flow works.

## Run

Add your credentials to `.env` — see `.env.example` for the shape:
- Plaid Sandbox: free at [dashboard.plaid.com](https://dashboard.plaid.com)
- Google OAuth client: free at [console.cloud.google.com](https://console.cloud.google.com) (redirect URI: `http://localhost:8000/auth/callback`)
- `SESSION_SECRET_KEY`: any long random string, e.g. `openssl rand -hex 32`
- `TOKEN_ENCRYPTION_KEY`: encrypts Plaid access tokens at rest, e.g. `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Then:

```bash
docker compose up --build
```

Then visit:
- http://localhost:5173 — the React frontend
- http://localhost:8000/docs — interactive API docs

## What's here

- `api/main.py` — app entrypoint, CORS, session middleware
- `api/auth.py` — Google OAuth client config + `get_current_user` dependency
- `api/database.py` — SQLModel engine/session setup
- `api/plaid_client.py` — configured `plaid-python` SDK client
- `api/crypto.py` — Fernet encrypt/decrypt helpers for Plaid access tokens at rest
- `api/models/transaction.py` — the `Transaction` table (per-user, tagged manual vs. Plaid)
- `api/models/user.py`, `api/models/plaid_item.py` — users (Google-linked), linked bank connections
- `api/routers/auth.py`, `api/routers/transactions.py`, `api/routers/plaid.py` — endpoints
- `api/ml/classifier.py` — scikit-learn Pipeline that predicts a category for manually-entered transactions
- `frontend/src/App.jsx` — container: state + data fetching
- `frontend/src/components/` — `LoginButton`, `PlaidLinkButton`, `SyncButton`, `TransactionSummary`, `TransactionForm`, `TransactionList`
- `frontend/src/api.js` — API client used by the UI (sends the session cookie on every call)

## Next steps

- Per-session revocation (a server-side session table) instead of an all-or-nothing signing-secret rotation
- A second OAuth provider + account linking
- Add nightly Airflow ETL job (data engineering layer)
- Add threat model doc
- Add edit/delete endpoints and automated tests (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#6-known-limitations--next-steps))
