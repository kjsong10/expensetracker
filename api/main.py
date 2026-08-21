from fastapi import FastAPI

from database import init_db
from routers import transactions

app = FastAPI(title="Expense Tracker API")

app.include_router(transactions.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def read_root():
    return {"status": "ok"}
