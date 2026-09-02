import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from auth import SESSION_SECRET_KEY
from ml.classifier import train_classifier
from routers import auth, plaid, transactions

# Comma-separated list of allowed frontend origins, e.g.
# "https://app.example.com,https://staging.example.com". Defaults to the
# Vite dev server so local development needs no configuration.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# Cookie security flags default to local-dev-safe values (HTTP allowed,
# SameSite=Lax) and must be overridden via env vars in production - see
# docs/ARCHITECTURE.md §3.5 for why these can't just default to "secure".
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax").lower()

if SESSION_COOKIE_SAMESITE == "none" and not SESSION_COOKIE_SECURE:
    # Browsers reject SameSite=None cookies that aren't also Secure, so this
    # combination is always a misconfiguration rather than a valid choice.
    raise RuntimeError(
        "SESSION_COOKIE_SAMESITE=none requires SESSION_COOKIE_SECURE=true"
    )

app = FastAPI(title="Expense Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    same_site=SESSION_COOKIE_SAMESITE,
    https_only=SESSION_COOKIE_SECURE,
)

app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(plaid.router)


@app.on_event("startup")
def on_startup():
    # Schema is managed by Alembic migrations (`alembic upgrade head`), run
    # before the app starts - see docs/ARCHITECTURE.md §3.4.
    train_classifier()


@app.get("/")
def read_root():
    return {"status": "ok"}
