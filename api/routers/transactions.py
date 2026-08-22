from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import List

from database import get_session
from ml.classifier import predict_category
from models import Transaction
from schemas.transaction import CategoryPrediction, CategoryPredictionRequest, TransactionCreate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/list", response_model=List[Transaction])
def list_transactions(user_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Transaction).where(Transaction.user_id == user_id)).all()


@router.post("/predict-category", response_model=CategoryPrediction)
def predict_transaction_category(payload: CategoryPredictionRequest):
    category, confidence = predict_category(payload.merchant)
    return CategoryPrediction(category=category, confidence=confidence)


@router.post("/create", response_model=Transaction)
def create_transaction(payload: TransactionCreate, session: Session = Depends(get_session)):
    data = payload.model_dump()
    if not data.get("category"):
        data["category"], _ = predict_category(payload.merchant)

    transaction = Transaction.model_validate(data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.get("/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: int, session: Session = Depends(get_session)):
    return session.get(Transaction, transaction_id)
