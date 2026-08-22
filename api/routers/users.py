from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import List

from database import get_session
from models import User
from schemas.user import UserCreate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/list", response_model=List[User])
def list_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()


@router.post("/create", response_model=User)
def create_user(payload: UserCreate, session: Session = Depends(get_session)):
    user = User.model_validate(payload)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
