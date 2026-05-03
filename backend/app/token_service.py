import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .config import settings
from .models import RefreshToken


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, user_id: int) -> str:
    plain = secrets.token_urlsafe(48)
    token_hash = _hash_token(plain)
    expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    db.commit()
    return plain


def rotate_refresh_token(db: Session, plain_token: str) -> tuple[str, int] | None:
    token_hash = _hash_token(plain_token)
    token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not token:
        return None
    if token.revoked_at or token.expires_at < datetime.utcnow():
        return None
    token.revoked_at = datetime.utcnow()
    db.add(token)
    db.commit()
    new_token = create_refresh_token(db, token.user_id)
    return new_token, token.user_id


def revoke_refresh_token(db: Session, plain_token: str) -> None:
    token_hash = _hash_token(plain_token)
    token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not token:
        return
    if not token.revoked_at:
        token.revoked_at = datetime.utcnow()
        db.add(token)
        db.commit()
