from backend.app.core.permissions import can_manage_org, can_review_audit_logs
from backend.app.models import RoleEnum, User


def _user(role: RoleEnum) -> User:
    return User(email=f"{role.value}@demo.health", hashed_password="x", role=role, org_id=1)


def test_org_admin_can_manage_org():
    assert can_manage_org(_user(RoleEnum.org_admin)) is True
    assert can_manage_org(_user(RoleEnum.clinician)) is False


def test_auditor_can_review_logs():
    assert can_review_audit_logs(_user(RoleEnum.auditor)) is True
    assert can_review_audit_logs(_user(RoleEnum.reviewer)) is False
