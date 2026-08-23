# Architecture & Design Notes

This document explains what the Expense Tracker project currently does and why it's built the way it is. It's meant to be read alongside the code, not instead of it — file references point at the actual source.

## 1. What this is

A minimal full-stack expense tracker:

- **Backend**: FastAPI + SQLModel + Postgres, exposing a small REST API for expense transactions.
- **Frontend**: a single-page React app that lists transactions (paginated) and connects a bank account via Plaid. There's no add-transaction UI right now — see the frontend note in [§4.2](#42-structure) — but the backend fully supports it.
- **Data sources**: transactions come from Plaid (using Plaid's own categories) or the `POST /transactions/create` API (auto-categorized by an in-house ML classifier when no category is given) — see [§3.8](#38-plaid-integration).
- **Auth**: real login via "Sign in with Google" (OAuth2/OIDC), backed by a signed session cookie. Every transaction and Plaid connection is scoped to whoever is actually logged in — see [§3.7](#37-authentication--multi-tenancy) and the detailed walkthrough in [docs/AUTHENTICATION.md](AUTHENTICATION.md).
- **Infra**: all three services (plus Postgres) run together via Docker Compose for local development.

See [§6 Known limitations](#6-known-limitations--next-steps) for what's intentionally still deferred (session revocation, a second OAuth provider, etc.).

## 2. Repo layout

```
api/
  main.py                   FastAPI app: CORS, session middleware, router registration, startup hook
  auth.py                   Google OAuth client config + get_current_user dependency
  database.py               SQLModel engine/session, DB init
  plaid_client.py           Configured plaid-python SDK client (from env vars)
  models/transaction.py     Transaction table (SQLModel) - user_id, source, plaid_transaction_id
  models/user.py            User table (id, display_name, email, oauth_provider, oauth_subject)
  models/plaid_item.py      One linked bank connection per user (item_id, access_token, cursor)
  schemas/transaction.py    TransactionCreate, CategoryPrediction (Pydantic schemas)
  schemas/user.py           UserPublic (redacts oauth_provider/oauth_subject)
  schemas/plaid.py          Link/exchange/sync request+response schemas
  routers/auth.py           /auth/* endpoints (login, callback, logout, me)
  routers/transactions.py   /transactions/* endpoints
  routers/plaid.py          /plaid/* endpoints (link-token, exchange, sync)
  ml/classifier.py          Merchant -> category scikit-learn Pipeline
  ml/data/labeled_transactions.csv   Seed training data
  requirements.txt
  Dockerfile
frontend/
  src/api.js                        Thin fetch wrapper around the API (sends session cookie)
  src/App.jsx                       Container: owns state, wires components together
  src/components/LoginButton.jsx          "Sign in with Google" link
  src/components/PlaidLinkButton.jsx      Plaid Link flow: link token -> Link -> exchange -> sync
  src/components/SyncButton.jsx           Manual re-sync of Plaid transactions
  src/components/TransactionSummary.jsx   Count + total line (of what's loaded so far)
  src/components/TransactionList.jsx      Transaction table + "Load more" pagination control
  src/App.css, index.css            Styling (light/dark aware, CSS custom properties)
  Dockerfile
docker-compose.yml           Wires db + api + frontend together for local dev
docs/ARCHITECTURE.md         This file
docs/AUTHENTICATION.md       Detailed walkthrough of the OAuth login flow
```

## 3. Backend design

### 3.1 Stack choice

**FastAPI + SQLModel** was chosen over a heavier framework (e.g. Django) because the project is a small CRUD API where the main value is speed of iteration: SQLModel lets the same class (`Transaction`) act as both the Pydantic response model *and* the SQLAlchemy table definition, so there's one source of truth for the data shape instead of three (ORM model, serializer, validator).

### 3.2 Models vs. schemas

`Transaction` (in `models/`) is the table — it has an `id`. `TransactionCreate` (in `schemas/`) is what a client sends to create one — it has no `id`, since that's server-assigned. Keeping these separate, even though SQLModel *could* let you reuse one class for both, avoids ever accepting a client-supplied `id` on create, and gives room to diverge later (e.g. once auth exists, `TransactionCreate` won't carry a `user_id` — that'll come from the session instead).

This isn't Transaction-specific, and it isn't "schemas aggregate model data for display" — a schema exists wherever the API boundary needs a shape the table doesn't provide as-is:
- **Omit a server-assigned field**, as above.
- **Describe data with no table at all** — `LinkTokenResponse` (`schemas/plaid.py`) is just `{link_token: str}`; a Plaid Link token is never persisted, so there's no model for it to "aggregate."
- **Redact a stored field** — `PlaidItem.access_token` (`models/plaid_item.py`) is a real column, but `ExchangePublicTokenResponse` (`schemas/plaid.py`) returns only `{connected: bool}`. Same reasoning behind `UserPublic` (`schemas/user.py`): `User` also stores `oauth_provider`/`oauth_subject`, but `GET /auth/me` returns only `{id, display_name, email}` — nothing about *how* someone authenticated needs to reach the frontend.

Where none of that applies, there's no schema at all — `GET /transactions/list` responds with `response_model=Transaction` directly, reusing the table shape as-is.

### 3.3 Endpoints

| Method | Path                             | Purpose                                   |
|--------|----------------------------------|---------------------------------------------|
| GET    | `/`                              | Health check                              |
| GET    | `/auth/login`                    | Redirect to Google's consent screen                        |
| GET    | `/auth/callback`                 | Google redirects here; creates/looks up the user, sets the session |
| POST   | `/auth/logout`                   | Clear the session                         |
| GET    | `/auth/me`                       | Current logged-in user, or 401            |
| GET    | `/transactions/list`             | List the logged-in user's transactions, paginated |
| POST   | `/transactions/create`           | Create a transaction for the logged-in user |
| GET    | `/transactions/{id}`             | Fetch one transaction (404 if it isn't yours) |
| POST   | `/transactions/predict-category` | Predict a category for a merchant         |
| POST   | `/plaid/link-token`              | Create a Plaid Link token for the logged-in user |
| POST   | `/plaid/exchange-public-token`   | Exchange a Link `public_token` for an access token, store it |
| POST   | `/plaid/sync-transactions`       | Pull new/updated/removed transactions from Plaid into the DB |

Every row below the `/auth/*` block requires an active session (`Depends(get_current_user)`) and operates only on the logged-in user's own data — see [§3.7](#37-authentication--multi-tenancy) and [docs/AUTHENTICATION.md](AUTHENTICATION.md) for exactly how that's enforced.

Full interactive docs (generated by FastAPI from the schemas) are always available at `/docs` when the API is running.

The list/create routes use explicit `/list` and `/create` suffixes rather than bare `GET/POST /transactions/` — a deliberate choice in this codebase (see recent commit history) to keep route intent readable at a glance rather than relying on HTTP-verb overloading of a single path.

`GET /transactions/list` takes `limit` (default 50, capped at 200) and `offset` query params rather than returning a user's entire history in one response — with Plaid sync able to backfill months of transactions in a single call, an unbounded list would grow linearly with account age instead of staying flat. Results are ordered `date desc, id desc` (a stable tiebreaker for same-day transactions) so pages stay consistent across requests. The frontend ([§4.2](#42-structure)) treats a full page as a signal there may be more and exposes a "Load more" button rather than fetching everything up front.

### 3.4 Database access

`database.py` reads `DATABASE_URL` from the environment (no default — it fails fast at import time if unset, rather than silently falling back to something like SQLite that would mask a misconfigured environment). `init_db()` runs `SQLModel.metadata.create_all()` on startup, which is fine for a single-developer project at this stage but is **not** a migration strategy — see limitations below.

The engine is created without `echo=True` — query logging at that verbosity is only worth the noise while actively debugging SQL, not as a standing default that scales with request volume.

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

### 3.7 Authentication & multi-tenancy

Every transaction and Plaid connection belongs to a specific person, and now that's actually enforced: signing in with Google is required, and `user_id` is never something a client can supply — it comes from `Depends(get_current_user)` ([api/auth.py](api/auth.py)), which reads it out of the signed session cookie. This replaced an earlier, explicitly-named gap where `user_id` was just trusted from the request body/query string ([§6 history](#6-known-limitations--next-steps) — that gap is now closed, not just documented).

For the full mechanical walkthrough of the login flow — every redirect, what's in the cookie, how logout works, what an unauthenticated request actually receives — see **[docs/AUTHENTICATION.md](AUTHENTICATION.md)**. This section only covers the *why* behind the choices:

**Why Authlib, not a hand-rolled OAuth flow**: OAuth2/OIDC involves several security-sensitive steps — a CSRF-protecting `state` parameter, a replay-protecting `nonce`, verifying Google's ID token signature against their published keys, checking `iss`/`aud`/`exp` claims. Getting any of these wrong is a real vulnerability, not a cosmetic bug. `authlib.integrations.starlette_client.OAuth` handles all of it, discovering Google's endpoints from its OIDC metadata document rather than hardcoding them — the same reasoning already applied to using `plaid-python` instead of hand-rolling Plaid's protocol.

**Why a signed session cookie, not a JWT the frontend stores**: Starlette's `SessionMiddleware` ([api/main.py](api/main.py)) signs a cookie (itsdangerous) containing just `{"user_id": ...}`, marked `httponly` so frontend JavaScript can never read it — only the browser sends it automatically. A JWT in `localStorage` would be readable (and stealable) by any script running on the page, including a compromised dependency; that's a materially bigger blast radius for the exact same login state. The trade-off, named plainly: this cookie can't be revoked server-side short of rotating `SESSION_SECRET_KEY` (which would log out everyone at once) — there's no per-session "sign out this one device" story, because that would need a server-side session table this app doesn't have. Acceptable for now since nothing else in the app has a revocation/admin story either; a `Session` table is the natural next step if that's ever needed.

**Why `User` rows are created automatically on first login, not by a form**: `api/models/user.py`'s `(oauth_provider, oauth_subject)` unique constraint means a Google account maps to exactly one `User` row, looked up or created in `POST /auth/callback` — there is no "sign up" step distinct from "first login." This replaced the old `UserPicker` (create-by-typing-a-name, zero verification) entirely; picker-created dev rows have no OAuth identity and are simply unreachable now, which is fine — they were fake data to begin with.

**CORS + credentials**: `CORSMiddleware` now sets `allow_credentials=True` ([api/main.py](api/main.py)) — cross-port cookie flow (frontend on `:5173`, API on `:8000`) requires the browser be told it's allowed to send/receive the session cookie. This only works paired with an explicit `allow_origins` list (already in place, [§3.5](#35-cors)) — credentialed CORS cannot use a wildcard origin.

### 3.8 Plaid integration

`api/plaid_client.py` configures the official `plaid-python` SDK once from `PLAID_CLIENT_ID` / `PLAID_SECRET` / `PLAID_ENV` (env vars, never sent to the frontend — see [§3.5 CORS](#35-cors) for the same never-expose-secrets posture). `api/routers/plaid.py` implements the three-step Plaid Link flow:

1. **`POST /plaid/link-token`** — asks Plaid for a short-lived `link_token` scoped to `client_user_id=str(current_user.id)` (from the session, not the request — [§3.7](#37-authentication--multi-tenancy)). The frontend never talks to Plaid's API directly with our secret; it only ever sees this token.
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

- `src/api.js` — the only place that knows the API's base URL or fetch semantics. Every call passes `credentials: 'include'` so the session cookie is sent; `listTransactions()` / `createTransaction()` no longer take a `userId` parameter at all — the backend derives it from the cookie, so there's nothing for the frontend to pass or get wrong. `listTransactions({ limit, offset })` mirrors the backend's pagination params ([§3.3](#33-endpoints)), defaulting to the same page size. If the API grows, new functions get added here rather than components calling `fetch` directly.
- `src/App.jsx` is a **container component**: it owns all state (`transactions`, `loading`, `loadingMore`, `hasMore`, `error`) and the operations that touch the API (`refresh`, `loadMore`), then hands data and callbacks down to presentational children under `src/components/`. `refresh()` fetches page one on mount; `loadMore()` fetches the next page at `offset: transactions.length` and appends it. `hasMore` is inferred from whether the last page came back full-sized (`data.length === PAGE_SIZE`) rather than a separate count endpoint — a full page means there might be more, a short page means there definitely isn't.
- **There's no add-transaction form right now** — `TransactionForm` (and the `handleCreate`/`submitting` state that drove it) was removed from the frontend by request, since nothing in this project's current use case needs manual entry from the UI. `POST /transactions/create` and its ML auto-categorization ([§3.6](#36-merchant-category-classifier)) are untouched in the backend; only the UI entry point is gone. Re-adding a form is a small, self-contained addition if manual entry becomes needed again — `createTransaction()` is still there in `src/api.js`.
- `TransactionSummary` / `TransactionList` — split out of what was originally one file once it started mixing concerns (a summary line, a data table) that don't share markup or logic.
- **Why not a custom hook (`useTransactions`) or Context instead**: both would solve a problem this app doesn't have yet — sharing transaction state across *multiple, unrelated* components. Right now exactly one component tree needs it, so passing state down as props from `App` is the simplest thing that works; a hook/Context is worth it once a second screen or a deeply nested consumer shows up.
- **Why one shared `App.css` instead of per-component stylesheets/CSS modules**: the components share the same visual language (`.card`, `.muted`, `.amount`, etc.) defined once; splitting styles per component now would mean duplicating or importing across files for zero isolation benefit at this size.
- `PlaidLinkButton` / `SyncButton` — added alongside Plaid support ([§3.8](#38-plaid-integration)). `PlaidLinkButton` uses `react-plaid-link`'s `usePlaidLink` hook rather than hand-rolling the Link iframe/script loading — Plaid Link is a hosted widget with its own internal flows (phone verification, institution search, OAuth redirects for some banks) that would be brittle and against Plaid's terms to reimplement. On a successful Link, the button chains exchange → sync → refresh itself, so connecting a bank immediately populates transactions; `SyncButton` exists separately for pulling *new* transactions on an already-linked account later, without re-running Link.
- `LoginButton` — a plain `<a href={loginUrl()}>`, not a `fetch`-driven click handler. The OAuth redirect dance (browser → Google's consent screen → back) has to happen as real page navigations in the actual address bar; a `fetch` call can't drive that. `App.jsx` decides what to render (the login screen vs. the dashboard) based on whether `GET /auth/me` succeeds on mount — there's no client-side notion of "logged in" beyond that one check.

### 4.3 Configuration

The API base URL is read from `VITE_API_URL` at build/dev-server start (`frontend/.env`, default `http://localhost:8000`), not hardcoded, so the same code works when the frontend runs outside vs. inside Docker Compose, and in a future deployed environment, by changing one env var.

The Plaid `PLAID_CLIENT_ID` / `PLAID_SECRET` and the Google `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `SESSION_SECRET_KEY` all live only in the root `.env`, read by the `api` service — never passed to the frontend build, so none of these secrets can leak into browser-shipped JS.

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

### Google OAuth credentials

Create a Google OAuth client at [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials → Create Credentials → OAuth client ID → Web application. Add `http://localhost:8000/auth/callback` as an authorized redirect URI (this must match `/auth/login`'s redirect target exactly, or Google will reject the flow). Put `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `.env`. Also set `SESSION_SECRET_KEY` — any long random string works, e.g. `openssl rand -hex 32`; this signs the session cookie, so treat it like a password, not something to commit. See [docs/AUTHENTICATION.md](AUTHENTICATION.md) for the full flow this powers.

### Resetting the dev database after a schema change

This project has no migration tool ([§6](#6-known-limitations--next-steps)) — `init_db()`'s `create_all()` only creates tables that don't already exist, it never alters an existing one. Adding a column (like `Transaction.user_id`) to a table that already exists in the Postgres volume will make every insert fail. When a model gains/changes a column, reset the local dev database:

```bash
docker compose down -v
docker compose up --build
```

This deletes all local dev data — fine for fake test rows, not something to run against anything you'd mind losing.

## 6. Known limitations / next steps

Carried over from the original README, still true:

- **Sessions can't be revoked individually** ([§3.7](#37-authentication--multi-tenancy)) — logging out just clears the browser's cookie; there's no server-side session table, so a captured cookie remains valid until it expires or `SESSION_SECRET_KEY` is rotated (which logs out everyone at once, not just one compromised session).
- **Single OAuth provider (Google only)** — no account-linking flow if someone wants to also sign in with a different provider; each provider would currently create a separate `User` row for the same person.
- **CSRF protection relies on `SameSite=Lax`, not a dedicated token** — acceptable for this app's current request patterns (no cross-site form posts to worry about yet), but named explicitly rather than assumed; a state-changing-request CSRF token would be the next layer if that changes.
- **Plaid access tokens stored in plaintext** ([§3.8](#38-plaid-integration)) — must be encrypted at rest before this touches a real (non-Sandbox) account.
- **One Plaid connection per user** — linking a second bank account isn't supported; `PlaidItem.user_id` is unique.
- **No webhook-driven or scheduled sync** — transactions only update when someone clicks "Sync"; stale data between clicks is expected, not a bug.
- **No migrations** — `create_all()` on startup means schema changes to `Transaction` require manually altering the table or dropping the dev database; a real migration tool (e.g. Alembic) is needed before this touches real data.
- **No CSV ingestion** — transactions can only be added one at a time through the API/UI.
- **No delete/edit endpoints** — the API is intentionally append-only right now (create + read); this simplified the first frontend pass by removing a category of confirm/undo UI decisions, but is an obvious near-term gap.
- **No tests** — neither side has automated test coverage yet.
- **Classifier taxonomy is fixed and static** — categories only come from `api/ml/data/labeled_transactions.csv`; the model retrains from that file at every restart, but there's no feedback loop yet feeding user corrections (e.g. someone editing a mis-predicted category) back into training data.
- **Dev-only frontend serving** — the frontend container runs the Vite dev server, not a production build; there's no static-build/nginx path yet for anything resembling a deployment.
