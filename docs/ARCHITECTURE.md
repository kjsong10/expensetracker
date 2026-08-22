# Architecture & Design Notes

This document explains what the Expense Tracker project currently does and why it's built the way it is. It's meant to be read alongside the code, not instead of it — file references point at the actual source.

## 1. What this is

A minimal full-stack expense tracker:

- **Backend**: FastAPI + SQLModel + Postgres, exposing a small REST API for expense transactions.
- **Frontend**: a single-page React app that lists transactions, lets you add new ones, and connects a bank account via Plaid.
- **Data sources**: transactions come from manual entry (auto-categorized by an in-house ML classifier) or from Plaid (using Plaid's own categories) — see [§3.7](#37-users--multi-tenancy) and [§3.8](#38-plaid-integration).
- **Users**: a lightweight `User` table + picker (create/select by display name, no password) scopes transactions and Plaid connections per user — a stepping stone toward real auth, not a replacement for it.
- **Infra**: all three services (plus Postgres) run together via Docker Compose for local development.

There is no real auth (login/passwords/sessions) yet — see [§6 Known limitations](#6-known-limitations--next-steps) for what's intentionally deferred.

## 2. Repo layout

```
api/
  main.py                   FastAPI app: CORS, router registration, startup hook
  database.py               SQLModel engine/session, DB init
  plaid_client.py           Configured plaid-python SDK client (from env vars)
  models/transaction.py     Transaction table (SQLModel) - user_id, source, plaid_transaction_id
  models/user.py            User table (id, display_name - no password)
  models/plaid_item.py      One linked bank connection per user (item_id, access_token, cursor)
  schemas/transaction.py    TransactionCreate, CategoryPrediction (Pydantic schemas)
  schemas/user.py           UserCreate
  schemas/plaid.py          Link/exchange/sync request+response schemas
  routers/transactions.py   /transactions/* endpoints
  routers/users.py          /users/* endpoints
  routers/plaid.py          /plaid/* endpoints (link-token, exchange, sync)
  ml/classifier.py          Merchant -> category scikit-learn Pipeline
  ml/data/labeled_transactions.csv   Seed training data
  requirements.txt
  Dockerfile
frontend/
  src/api.js                        Thin fetch wrapper around the API
  src/App.jsx                       Container: owns state, wires components together
  src/components/UserPicker.jsx           Select/create a user (no password)
  src/components/PlaidLinkButton.jsx      Plaid Link flow: link token -> Link -> exchange -> sync
  src/components/SyncButton.jsx           Manual re-sync of Plaid transactions
  src/components/TransactionSummary.jsx   Count + total line
  src/components/TransactionForm.jsx      Add-transaction form (owns its own field state)
  src/components/TransactionList.jsx      Transaction table
  src/App.css, index.css            Styling (light/dark aware, CSS custom properties)
  Dockerfile
docker-compose.yml           Wires db + api + frontend together for local dev
docs/ARCHITECTURE.md         This file
```

## 3. Backend design

### 3.1 Stack choice

**FastAPI + SQLModel** was chosen over a heavier framework (e.g. Django) because the project is a small CRUD API where the main value is speed of iteration: SQLModel lets the same class (`Transaction`) act as both the Pydantic response model *and* the SQLAlchemy table definition, so there's one source of truth for the data shape instead of three (ORM model, serializer, validator).

### 3.2 Models vs. schemas

`Transaction` (in `models/`) is the table — it has an `id`. `TransactionCreate` (in `schemas/`) is what a client sends to create one — it has no `id`, since that's server-assigned. Keeping these separate, even though SQLModel *could* let you reuse one class for both, avoids ever accepting a client-supplied `id` on create, and gives room to diverge later (e.g. once auth exists, `TransactionCreate` won't carry a `user_id` — that'll come from the session instead).

### 3.3 Endpoints

| Method | Path                             | Purpose                                   |
|--------|----------------------------------|---------------------------------------------|
| GET    | `/`                              | Health check                              |
| GET    | `/users/list`                    | List users                                |
| POST   | `/users/create`                  | Create a user (`display_name` only)       |
| GET    | `/transactions/list`             | List a user's transactions (`user_id` query param) |
| POST   | `/transactions/create`           | Create a transaction (`user_id` in body)  |
| GET    | `/transactions/{id}`             | Fetch one transaction                     |
| POST   | `/transactions/predict-category` | Predict a category for a merchant         |
| POST   | `/plaid/link-token`              | Create a Plaid Link token for a user      |
| POST   | `/plaid/exchange-public-token`   | Exchange a Link `public_token` for an access token, store it |
| POST   | `/plaid/sync-transactions`       | Pull new/updated/removed transactions from Plaid into the DB |

Full interactive docs (generated by FastAPI from the schemas) are always available at `/docs` when the API is running.

The list/create routes use explicit `/list` and `/create` suffixes rather than bare `GET/POST /transactions/` — a deliberate choice in this codebase (see recent commit history) to keep route intent readable at a glance rather than relying on HTTP-verb overloading of a single path.

### 3.4 Database access

`database.py` reads `DATABASE_URL` from the environment (no default — it fails fast at import time if unset, rather than silently falling back to something like SQLite that would mask a misconfigured environment). `init_db()` runs `SQLModel.metadata.create_all()` on startup, which is fine for a single-developer project at this stage but is **not** a migration strategy — see limitations below.

`get_session()` is a generator dependency (`Depends(get_session)`) so each request gets its own `Session`, opened and closed within the request lifecycle — the standard FastAPI pattern for avoiding session leakage across requests.

### 3.5 CORS

`main.py` adds `CORSMiddleware` restricted to `http://localhost:5173` (the Vite dev server's default origin). This is deliberately an allowlist of one known origin rather than `allow_origins=["*"]`, since the API also accepts cookies/credentials-adjacent requests in the future and a wildcard origin can't be combined with credentials per the CORS spec anyway. If the frontend is deployed somewhere else, its origin needs to be added here.

### 3.6 Merchant category classifier

Transactions have a free-text `category`, but requiring the client to type one for every transaction doesn't scale. `api/ml/classifier.py` auto-categorizes a transaction from its merchant string using a scikit-learn `Pipeline`:

```python
Pipeline([
    ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, sublinear_tf=True)),
    ("clf", LogisticRegression(max_iter=2000, C=5)),
])
```

**Training data**: `api/ml/data/labeled_transactions.csv`, a bundled seed set of ~150 merchant→category examples across a fixed taxonomy (Groceries, Dining, Transportation, Shopping, Entertainment, Utilities, Health, Travel, Subscriptions, Other). This file is the source of truth for what the model can predict — it's checked into the repo rather than sourced from the DB, since the DB currently holds almost no categorized transactions to learn from. Growing the taxonomy or improving accuracy means editing this CSV.

**Why character n-grams, not word tokens**: real transaction feeds look like `SQ *BLUE BOTTLE COFFEE` or `AMZN Mktp US*A19D` — short, abbreviated, often not real words. A `char_wb` analyzer captures substrings like "coffee", "mkt", "air" regardless of surrounding noise, which a word-tokenizing vectorizer would handle far worse.

**Why `LogisticRegression`, not Naive Bayes**: the first version of this pipeline used `ComplementNB` (a common default for small multi-class text problems), but empirically its `predict_proba` output was unusable for the confidence threshold below: paired with TF-IDF, probabilities came out nearly flat across all classes (~0.10–0.16, even for merchants almost identical to training examples); switched to raw `CountVectorizer` instead, NB flipped to the opposite failure mode — near-1.0 "confidence" on pure gibberish inputs it had never seen anything like. Both are known characteristics of Naive Bayes' independence assumption interacting badly with either weighting scheme. `LogisticRegression` on the same TF-IDF features directly models `P(category | merchant)` via softmax over a learned decision boundary, and empirically produces a much more usable spread — confident (0.4–1.0) on clear matches, low (<0.3) on nonsense strings — which is what the threshold below actually depends on.

**Train-at-startup, in-memory, no persistence**: `train_classifier()` is called once in `main.py`'s startup hook (alongside `init_db()`) and the fitted pipeline is kept as a module-level singleton — not serialized to disk with `joblib`. At the current data size, retraining from scratch on every restart is effectively free, and it sidesteps model-file versioning/staleness questions entirely. This is a deliberate stopgap: once training data comes from accumulated real transactions instead of (or in addition to) the seed CSV, persisting a trained model becomes worth the added complexity.

**Confidence threshold, not a forced guess**: `predict_category()` returns the top class's probability alongside its label. Below `CONFIDENCE_THRESHOLD = 0.3` it returns `"Uncategorized"` instead — silently mislabeling an unfamiliar merchant is worse than admitting the model doesn't know. With only ~15 examples per category, this threshold is a coarse instrument, not a precise one: cross-validated accuracy on the seed set alone is ~40%, and it will keep improving as the CSV grows (see limitations below).

**Where it plugs in**: `POST /transactions/create` uses the classifier to fill `category` only when the client didn't supply one — a client-provided category is never overridden. `POST /transactions/predict-category` exposes the same prediction standalone (merchant in, category + confidence out) so a client can preview or let a user correct a guess before it's ever saved.

### 3.7 Users & multi-tenancy

Adding Plaid meant deciding *whose* bank account a connection belongs to — the first point at which "single implicit user" stopped being tenable. `api/models/user.py` is deliberately bare: `id` + `display_name`, no password, no session. `Transaction.user_id` and `PlaidItem.user_id` scope data per user; every transaction and Plaid-related endpoint takes a `user_id`.

**Why not build real auth here**: the request was "implement Plaid," not "implement accounts." A password/session/JWT system touches nearly every endpoint and the whole frontend's request flow — bundling it into this change would make a Plaid bug and an auth bug indistinguishable in the diff. The `User` table exists now because Plaid *needs* a tenant boundary to be meaningful (linking a bank account has to belong to someone), but "someone" is deliberately as thin as it can be: a name you pick from a dropdown, not a login. Real auth is still tracked as a named gap (see [§6](#6-known-limitations--next-steps)), and slots in later by replacing how `user_id` is *obtained* (a JWT claim instead of a picker selection) without changing how it's *used* (every query already filters by it).

**Frontend "session"**: the selected `user_id` lives in `localStorage` ([frontend/src/App.jsx](frontend/src/App.jsx)), not a cookie or server session — there's nothing server-side to forge or expire yet, so this is just remembering a UI choice across reloads, not authentication.

### 3.8 Plaid integration

`api/plaid_client.py` configures the official `plaid-python` SDK once from `PLAID_CLIENT_ID` / `PLAID_SECRET` / `PLAID_ENV` (env vars, never sent to the frontend — see [§3.5 CORS](#35-cors) for the same never-expose-secrets posture). `api/routers/plaid.py` implements the three-step Plaid Link flow:

1. **`POST /plaid/link-token`** — asks Plaid for a short-lived `link_token` scoped to `client_user_id=str(user_id)`. The frontend never talks to Plaid's API directly with our secret; it only ever sees this token.
2. **`POST /plaid/exchange-public-token`** — after the user completes Plaid Link (their hosted widget, not code we wrote — `react-plaid-link` handles loading and rendering it), the frontend gets back a `public_token` and hands it to us. We exchange it for a real `access_token` + `item_id` and store them in a `PlaidItem` row. The access token is never returned to the frontend past this point.
3. **`POST /plaid/sync-transactions`** — uses Plaid's **`/transactions/sync`** endpoint (cursor-based) rather than the older `/transactions/get` (offset/date-range based). `sync` is Plaid's current recommendation: it returns exactly what changed (`added`/`modified`/`removed`) since the last stored `cursor`, so re-running it is naturally idempotent — verified directly: syncing the same linked account twice in a row returned `{added: 0, modified: 0, removed: 0}` the second time. `get` would require us to re-derive "what's new" ourselves by diffing date ranges.

**Why manual sync, not a webhook**: Plaid can push a webhook when new transactions are ready, but that needs a publicly reachable URL — not available for local dev, and there's no background job runner in this stack to poll on a schedule either. A "Sync transactions" button ([frontend/src/components/SyncButton.jsx](frontend/src/components/SyncButton.jsx)) is the honest fit for what this stack can actually do today; wiring up webhooks is a natural next step once the app is deployed somewhere with a stable URL.

**Why Plaid's category wins over the ML classifier**: [§3.6](#36-merchant-category-classifier)'s classifier was trained on ~150 hand-picked examples; Plaid's `personal_finance_category` comes from real merchant-level data across its whole network, and is very likely more accurate for real transactions. So `_category_for()` in `api/routers/plaid.py` takes Plaid's category directly, and the classifier is left doing what it's actually good for at this stage: filling in a best-effort guess for manually-typed merchants that have no category at all.

**One `PlaidItem` per user, not per institution**: `PlaidItem.user_id` is unique. A user can link one bank connection; linking a second would need to either replace the first or the model would need to drop that uniqueness constraint and every query would need to fan out across a user's items. Real multi-institution support is a documented follow-up, not built here, since nothing in the request implied a user needs more than one linked account yet.

**Access token storage is plaintext, on purpose named as a gap, not hidden**: `PlaidItem.access_token` sits in Postgres unencrypted, at the same trust level as every other credential this dev-stage app handles (i.e., none — see [§6](#6-known-limitations--next-steps)). A Plaid access token can read a real bank account's transaction history, which makes this a materially bigger deal than the app's other "no security yet" gaps. Before this touches a real account outside Sandbox, this needs encryption at rest (e.g. via a KMS-backed envelope) or a secrets vault — not a "someday," a precondition.

## 4. Frontend design

### 4.1 Why plain Vite + React (no TypeScript, no framework)

The brief was "a simple frontend." The app is one screen with one list and one form, so:
- **Vite + React, JS not TS** — the UI surface is small enough that TypeScript's benefit (catching shape mismatches between API and UI) is outweighed by the extra setup for a two-file app. If the API surface grows, adding TS later is a mechanical migration, not a redesign.
- **No router, no state library** — there's one view. `useState`/`useEffect` in a single `App.jsx` is the entire state management story; reaching for Redux/Zustand/React Router here would be solving a problem the app doesn't have yet.
- **No component library** — a handful of hand-written CSS rules (`App.css`, `index.css`) using CSS custom properties for colors, so light/dark mode (`prefers-color-scheme`) comes for free without a dependency.

### 4.2 Structure

- `src/api.js` — the only place that knows the API's base URL or fetch semantics. `listTransactions()` / `createTransaction()` are the two calls the UI needs; if the API grows, new functions get added here rather than components calling `fetch` directly, so there's one place to add auth headers or error handling later.
- `src/App.jsx` is a **container component**: it owns all state (`transactions`, `loading`, `submitting`, `error`) and the two operations that touch the API (`refresh`, `handleCreate`), then hands data and callbacks down to three presentational children under `src/components/`. It fetches the list on mount and re-fetches after a successful create rather than optimistically appending the new row — for a low-traffic single-user tool, the extra round-trip is cheap and it guarantees the displayed list always matches what the server actually persisted (e.g. reflects the classifier's auto-filled category), which matters more than shaving one network call.
- `TransactionSummary` / `TransactionForm` / `TransactionList` — split out of what was originally one file once the file started mixing three concerns (a summary line, a stateful form, a data table) that don't share markup or logic. `TransactionForm` deliberately keeps its own field state locally rather than lifting it into `App` — nothing outside the form cares about in-progress keystrokes, only the finished payload on submit (`onCreate(payload) -> Promise<boolean>`), and the returned boolean tells the form whether to clear itself, without `App` needing to know anything about the form's internal shape.
- **Why not a custom hook (`useTransactions`) or Context instead**: both would solve a problem this app doesn't have yet — sharing transaction state across *multiple, unrelated* components. Right now exactly one component tree needs it, so passing state down as props from `App` is the simplest thing that works; a hook/Context is worth it once a second screen or a deeply nested consumer shows up.
- **Why one shared `App.css` instead of per-component stylesheets/CSS modules**: the components share the same visual language (`.card`, `.muted`, `.amount`, etc.) defined once; splitting styles per component now would mean duplicating or importing across files for zero isolation benefit at this size.
- `UserPicker` / `PlaidLinkButton` / `SyncButton` — added alongside Plaid support ([§3.7](#37-users--multi-tenancy), [§3.8](#38-plaid-integration)). `PlaidLinkButton` uses `react-plaid-link`'s `usePlaidLink` hook rather than hand-rolling the Link iframe/script loading — Plaid Link is a hosted widget with its own internal flows (phone verification, institution search, OAuth redirects for some banks) that would be brittle and against Plaid's terms to reimplement. On a successful Link, the button chains exchange → sync → refresh itself, so connecting a bank immediately populates transactions; `SyncButton` exists separately for pulling *new* transactions on an already-linked account later, without re-running Link.

### 4.3 Configuration

The API base URL is read from `VITE_API_URL` at build/dev-server start (`frontend/.env`, default `http://localhost:8000`), not hardcoded, so the same code works when the frontend runs outside vs. inside Docker Compose, and in a future deployed environment, by changing one env var.

The Plaid `PLAID_CLIENT_ID` / `PLAID_SECRET` live only in the root `.env`, read by the `api` service — never passed to the frontend build, so the secret can't leak into browser-shipped JS.

## 5. Local development

### Everything via Docker Compose (recommended)

```bash
docker compose up --build
```

Starts three services:
- `db` — Postgres 16, healthchecked so the API waits for it to actually accept connections before starting.
- `api` — FastAPI via `uvicorn --reload`, source bind-mounted so code edits apply without a rebuild.
- `frontend` — Vite dev server via `npm run dev`, source bind-mounted the same way; an anonymous volume on `node_modules` stops the host bind mount from shadowing the dependencies installed inside the image.

Then visit:
- http://localhost:5173 — the React app
- http://localhost:8000/docs — interactive API docs
- http://localhost:8000/transactions/list — raw JSON

### Frontend only, against a locally-running API

```bash
cd frontend
npm install
npm run dev
```

Useful when iterating on UI without wanting to rebuild containers.

### Plaid Sandbox credentials

Get a free Sandbox `PLAID_CLIENT_ID` / `PLAID_SECRET` at [dashboard.plaid.com](https://dashboard.plaid.com) and put them directly in the root `.env` (never commit real values — `.env` is gitignored; `.env.example` shows the shape). `PLAID_ENV` defaults to `sandbox`, which uses fake test institutions and fabricated transaction data — no real bank account needed to develop or test against.

### Resetting the dev database after a schema change

This project has no migration tool ([§6](#6-known-limitations--next-steps)) — `init_db()`'s `create_all()` only creates tables that don't already exist, it never alters an existing one. Adding a column (like `Transaction.user_id`) to a table that already exists in the Postgres volume will make every insert fail. When a model gains/changes a column, reset the local dev database:

```bash
docker compose down -v
docker compose up --build
```

This deletes all local dev data — fine for fake test rows, not something to run against anything you'd mind losing.

## 6. Known limitations / next steps

Carried over from the original README, still true:

- **No real auth** — there's a `User` table and per-user scoping ([§3.7](#37-users--multi-tenancy)), but no password, session, or token: anyone can act as any user simply by picking their name from a dropdown. `user_id` is trusted from the request body/query string with no verification.
- **Plaid access tokens stored in plaintext** ([§3.8](#38-plaid-integration)) — must be encrypted at rest before this touches a real (non-Sandbox) account.
- **One Plaid connection per user** — linking a second bank account isn't supported; `PlaidItem.user_id` is unique.
- **No webhook-driven or scheduled sync** — transactions only update when someone clicks "Sync"; stale data between clicks is expected, not a bug.
- **No migrations** — `create_all()` on startup means schema changes to `Transaction` require manually altering the table or dropping the dev database; a real migration tool (e.g. Alembic) is needed before this touches real data.
- **No CSV ingestion** — transactions can only be added one at a time through the API/UI.
- **No delete/edit endpoints** — the API is intentionally append-only right now (create + read); this simplified the first frontend pass by removing a category of confirm/undo UI decisions, but is an obvious near-term gap.
- **No tests** — neither side has automated test coverage yet.
- **Classifier taxonomy is fixed and static** — categories only come from `api/ml/data/labeled_transactions.csv`; the model retrains from that file at every restart, but there's no feedback loop yet feeding user corrections (e.g. someone editing a mis-predicted category) back into training data.
- **Dev-only frontend serving** — the frontend container runs the Vite dev server, not a production build; there's no static-build/nginx path yet for anything resembling a deployment.
