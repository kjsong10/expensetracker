# Expense Tracker — Frontend

A minimal React UI for the Expense Tracker API: lists transactions and lets you add new ones.

## Run standalone

```bash
npm install
npm run dev
```

Visit http://localhost:5173. Requires the API (see `../api`) running at the URL in `VITE_API_URL` (default `http://localhost:8000`, set in `.env`).

## Run via Docker Compose

From the repo root: `docker compose up --build` — this starts the frontend alongside the API and database. See the root [README](../README.md) and [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for details.
