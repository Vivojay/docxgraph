from ..models import RoleEnum, User

ADMIN_ROLES = {RoleEnum.org_admin, RoleEnum.super_admin}
AUDIT_ROLES = {RoleEnum.org_admin, RoleEnum.auditor, RoleEnum.super_admin}
VERIFIED_ENDORSER_ROLES = {
    RoleEnum.clinician,
    RoleEnum.reviewer,
    RoleEnum.org_admin,
    RoleEnum.super_admin,
}


def can_manage_org(user: User) -> bool:
    return user.role in ADMIN_ROLES


def can_review_audit_logs(user: User) -> bool:
    return user.role in AUDIT_ROLES
