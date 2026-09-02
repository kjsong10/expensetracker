import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from auth import SESSION_SECRET_KEY
from database import get_session
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
    """Liveness check: is the process up and serving requests at all.
    Deliberately has no dependencies of its own - see /healthz for that."""
    return {"status": "ok"}


@app.get("/healthz")
def health_check(session: Session = Depends(get_session)):
    """Readiness check: is the app actually able to serve real requests.
    Deployment platforms should route traffic / restart on this, not on
    `/`, since a process that's up but can't reach Postgres isn't ready."""
    try:
        session.exec(select(1))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok"}
