from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .auth import decode_access_token
from .config import settings
from .core.permissions import can_manage_org, can_review_audit_logs
from .db import SessionLocal
from .models import RoleEnum, User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _user_from_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = _user_from_token(request.cookies.get(settings.session_cookie_name), db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    return _user_from_token(request.cookies.get(settings.session_cookie_name), db)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not can_manage_org(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def get_current_user_api(request: Request, db: Session = Depends(get_db)) -> User:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = _user_from_token(auth_header.split(" ", 1)[1].strip(), db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


def require_admin_api(user: User = Depends(get_current_user_api)) -> User:
    if not can_manage_org(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_auditor_api(user: User = Depends(get_current_user_api)) -> User:
    if not can_review_audit_logs(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit access required")
    return user


def require_reviewer_api(user: User = Depends(get_current_user_api)) -> User:
    if user.role not in {RoleEnum.reviewer, RoleEnum.org_admin, RoleEnum.super_admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer access required")
    return user
