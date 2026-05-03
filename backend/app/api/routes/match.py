from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user
from backend.app.schemas.match import MatchRequest, MatchResult
from backend.app.services.matching import match_experts

router = APIRouter(prefix="/match", tags=["match"])


@router.post("", response_model=list[MatchResult])
def match_endpoint(
    payload: MatchRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    results = match_experts(
        db,
        org_id=user.org_id,
        case_summary=payload.case_summary,
        specialty=payload.specialty,
        region=payload.region,
        top_k=payload.top_k,
    )
    return results
