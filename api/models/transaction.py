from datetime import date
from sqlmodel import SQLModel, Field
from typing import Optional


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    date: date
    merchant: str
    amount: float
    category: Optional[str] = None
    source: str = Field(default="manual")
    plaid_transaction_id: Optional[str] = Field(default=None, unique=True, index=True)
