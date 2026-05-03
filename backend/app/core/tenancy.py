from fastapi import HTTPException, status

from ..models import User


def require_same_org(user: User, org_id: int) -> None:
    if user.role.value == "super_admin":
        return
    if user.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
