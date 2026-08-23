from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List

from auth import get_current_user
from database import get_session
from ml.classifier import predict_category
from models import Transaction, User
from schemas.transaction import CategoryPrediction, CategoryPredictionRequest, TransactionCreate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/list", response_model=List[Transaction])
def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return session.exec(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()


@router.post("/predict-category", response_model=CategoryPrediction)
def predict_transaction_category(payload: CategoryPredictionRequest):
    category, confidence = predict_category(payload.merchant)
    return CategoryPrediction(category=category, confidence=confidence)


@router.post("/create", response_model=Transaction)
def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    data = payload.model_dump()
    if not data.get("category"):
        data["category"], _ = predict_category(payload.merchant)
    data["user_id"] = current_user.id

    transaction = Transaction.model_validate(data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.get("/{transaction_id}", response_model=Transaction)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    transaction = session.get(Transaction, transaction_id)
    if transaction is None or transaction.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction
