# Expense Tracker

Minimal starter: FastAPI + Postgres, containerized with Docker.

## Run

```bash
docker compose up --build
```

Then visit:
- http://localhost:8000/docs — interactive API docs
- http://localhost:8000/transactions/ — list/create transactions

## What's here

- `api/main.py` — app entrypoint
- `api/database.py` — SQLModel engine/session setup
- `api/models/transaction.py` — the `Transaction` table
- `api/routers/transactions.py` — CRUD endpoints

## Next steps

- Add CSV upload endpoint (ingest layer)
- Add JWT auth (security layer)
- Add nightly Airflow ETL job (data engineering layer)
- Add threat model doc
