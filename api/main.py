from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from ml.classifier import train_classifier
from routers import plaid, transactions, users

app = FastAPI(title="Expense Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(plaid.router)


@app.on_event("startup")
def on_startup():
    init_db()
    train_classifier()


@app.get("/")
def read_root():
    return {"status": "ok"}

