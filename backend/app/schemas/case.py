from datetime import datetime
from pydantic import BaseModel


class CaseBase(BaseModel):
    title: str
    demographics: str | None = None
    symptoms: str
    constraints: str | None = None
    suspected_dx: str | None = None
    final_dx: str | None = None
    interventions: str | None = None
    outcomes: str | None = None
    what_differently: str | None = None
    domain_tags: list[str] = []
    icd_tags: list[str] = []


class CaseCreate(CaseBase):
    pass


class CaseUpdate(CaseBase):
    pass


class CaseOut(BaseModel):
    id: int
    org_id: int
    author_id: int
    title: str
    demographics: str | None
    symptoms: str
    constraints: str | None
    suspected_dx: str | None
    final_dx: str | None
    interventions: str | None
    outcomes: str | None
    what_differently: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseSearchRequest(BaseModel):
    query: str
    specialty: str | None = None
    region: str | None = None
    tags: list[str] = []
    top_k: int = 5


class CaseSearchResult(BaseModel):
    case_id: int
    score: float
    matched_on: list[str]
    title: str
