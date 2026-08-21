from datetime import date
from sqlmodel import SQLModel, Field
from typing import Optional


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    merchant: str
    amount: float
    category: Optional[str] = None
