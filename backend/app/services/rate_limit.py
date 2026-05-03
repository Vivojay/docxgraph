from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.app.models.case import CaseValidation


def can_validate_case(db: Session, doctor_id: int, limit_per_day: int = 5) -> bool:
    since = datetime.utcnow() - timedelta(days=1)
    count = db.execute(
        select(func.count())
        .select_from(CaseValidation)
        .where(CaseValidation.doctor_id == doctor_id, CaseValidation.created_at >= since)
    ).scalar_one()
    return count < limit_per_day
