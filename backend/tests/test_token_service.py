from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base
from backend.app.models import Organization, RoleEnum, User
from backend.app.token_service import create_refresh_token, revoke_refresh_token, rotate_refresh_token


def test_refresh_token_rotation():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    db = Session()
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()
    user = User(
        email="user@example.com",
        full_name="Test User",
        hashed_password="hashed",
        role=RoleEnum.doctor,
        org_id=org.id,
    )
    db.add(user)
    db.commit()

    token = create_refresh_token(db, user.id)
    assert token

    rotated = rotate_refresh_token(db, token)
    assert rotated is not None
    new_token, user_id = rotated
    assert user_id == user.id

    revoke_refresh_token(db, new_token)

    db.close()
