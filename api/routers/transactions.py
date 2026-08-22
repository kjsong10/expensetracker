from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import List

from database import get_session
from models import Transaction
from schemas.transaction import TransactionCreate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/list", response_model=List[Transaction])
def list_transactions(session: Session = Depends(get_session)):
    return session.exec(select(Transaction)).all()


@router.post("/create", response_model=Transaction)
def create_transaction(payload: TransactionCreate, session: Session = Depends(get_session)):
    transaction = Transaction.model_validate(payload)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.get("/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: int, session: Session = Depends(get_session)):
    return session.get(Transaction, transaction_id)
