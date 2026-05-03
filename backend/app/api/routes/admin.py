from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.api.deps import get_db, require_role
from backend.app.models.case import CaseViewLog
from backend.app.models.user import User
from backend.app.models.team import Team, UserTeam

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/access-logs")
def access_logs(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    logs = db.execute(
        select(CaseViewLog).where(CaseViewLog.org_id == user.org_id)
    ).scalars().all()
    return [
        {
            "case_id": log.case_id,
            "viewer_id": log.viewer_id,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.post("/verify/{user_id}")
def verify_user(
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    target = db.get(User, user_id)
    if not target or target.org_id != user.org_id:
        return {"status": "not_found"}
    target.is_verified = True
    db.commit()
    return {"status": "ok"}


@router.post("/teams")
def create_team(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    name = payload.get("name")
    if not name:
        return {"status": "error", "detail": "name required"}
    team = Team(org_id=user.org_id, name=name)
    db.add(team)
    db.commit()
    return {"status": "ok", "team_id": team.id}


@router.post("/teams/{team_id}/add/{user_id}")
def add_user_to_team(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    team = db.get(Team, team_id)
    target = db.get(User, user_id)
    if not team or team.org_id != user.org_id:
        return {"status": "error", "detail": "team not found"}
    if not target or target.org_id != user.org_id:
        return {"status": "error", "detail": "user not found"}
    db.add(UserTeam(user_id=target.id, team_id=team.id))
    db.commit()
    return {"status": "ok"}
