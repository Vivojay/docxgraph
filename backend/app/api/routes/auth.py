from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.api.deps import get_db
from backend.app.core.config import settings
from backend.app.core.security import create_access_token, get_password_hash, verify_password
from backend.app.models.org import Org
from backend.app.models.user import User
from backend.app.schemas.auth import LoginRequest, RegisterRequest, Token
from backend.app.schemas.user import UserOut
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if not settings.allow_signup:
        raise HTTPException(status_code=403, detail="Signup disabled")
    org = db.execute(select(Org).where(Org.name == payload.org_name)).scalar_one_or_none()
    if not org:
        org = Org(name=payload.org_name)
        db.add(org)
        db.flush()
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        org_id=org.id,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="doctor",
        specialty=payload.specialty,
        years_experience=payload.years_experience,
        region=payload.region,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return Token(access_token=token)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user
