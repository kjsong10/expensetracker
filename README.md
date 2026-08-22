# Expense Tracker

Minimal starter: FastAPI + Postgres backend, React frontend, containerized with Docker.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full write-up of what's here and why it's built this way.

## Run

```bash
docker compose up --build
```

Then visit:
- http://localhost:5173 — the React frontend
- http://localhost:8000/docs — interactive API docs
- http://localhost:8000/transactions/list — list/create transactions (raw JSON)

## What's here

- `api/main.py` — app entrypoint, CORS
- `api/database.py` — SQLModel engine/session setup
- `api/models/transaction.py` — the `Transaction` table
- `api/routers/transactions.py` — CRUD endpoints
- `api/ml/classifier.py` — scikit-learn Pipeline that predicts a transaction's category from its merchant
- `frontend/src/App.jsx` — the UI: transaction list + add-transaction form
- `frontend/src/api.js` — API client used by the UI

## Next steps

- Add CSV upload endpoint (ingest layer)
- Add JWT auth (security layer)
- Add nightly Airflow ETL job (data engineering layer)
- Add threat model doc
- Add edit/delete endpoints and automated tests (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#6-known-limitations--next-steps))
