from datetime import date
from pydantic import BaseModel
from typing import Optional


class TransactionCreate(BaseModel):
    user_id: int
    date: date
    merchant: str
    amount: float
    category: Optional[str] = None


class CategoryPredictionRequest(BaseModel):
    merchant: str


class CategoryPrediction(BaseModel):
    category: str
    confidence: float
