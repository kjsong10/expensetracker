from datetime import date
from pydantic import BaseModel
from typing import Optional


class TransactionCreate(BaseModel):
    date: date
    merchant: str
    amount: float
    category: Optional[str] = None
