from pydantic import BaseModel


class MatchRequest(BaseModel):
    case_summary: str
    specialty: str | None = None
    region: str | None = None
    urgency: str | None = None
    top_k: int = 5


class MatchResult(BaseModel):
    doctor_id: int
    email: str
    specialty: str | None
    region: str | None
    score: float
    explanation: str
