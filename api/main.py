from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from auth import SESSION_SECRET_KEY
from database import init_db
from ml.classifier import train_classifier
from routers import auth, plaid, transactions

app = FastAPI(title="Expense Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    same_site="lax",
    https_only=False,
)

app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(plaid.router)


@app.on_event("startup")
def on_startup():
    init_db()
    train_classifier()


@app.get("/")
def read_root():
    return {"status": "ok"}
