from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from auth import FRONTEND_URL, get_current_user, oauth
from database import get_session
from models import User
from schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def auth_callback(request: Request, session: Session = Depends(get_session)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token["userinfo"]
    subject = userinfo["sub"]
    email = userinfo.get("email")
    name = userinfo.get("name") or email or "User"

    user = session.exec(
        select(User).where(User.oauth_provider == "google", User.oauth_subject == subject)
    ).first()
    if user is None:
        user = User(display_name=name, email=email, oauth_provider="google", oauth_subject=subject)
        session.add(user)
        session.commit()
        session.refresh(user)

    request.session["user_id"] = user.id
    return RedirectResponse(FRONTEND_URL)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"logged_out": True}


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
