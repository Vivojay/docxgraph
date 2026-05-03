from datetime import datetime

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role: str
    org_id: int
    team_id: int | None = None

    model_config = {"from_attributes": True}


class ProfileOut(BaseModel):
    specialty: str
    years_experience: int | None = None
    region: str | None = None
    verified: bool
    availability_status: str
    proof_status: str | None = None

    model_config = {"from_attributes": True}


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthMeResponse(BaseModel):
    user: UserOut
    profile: ProfileOut | None = None


class OrgSettingsOut(BaseModel):
    retention_days: int
    export_format: str
    feature_flags: dict = Field(default_factory=dict)


class OrgSettingsUpdate(BaseModel):
    retention_days: int | None = None
    export_format: str | None = None
    feature_flags: dict | None = None


class CaseCreateRequest(BaseModel):
    case_type: str | None = None
    specialty: str
    specialty_domain: str | None = None
    symptoms: str
    demographics: str | None = None
    age_bucket: str | None = None
    constraints: str | None = None
    resource_setting: str | None = None
    suspected_dx: str | None = None
    final_dx: str | None = None
    interventions: str | None = None
    outcomes: str | None = None
    follow_up: str | None = None
    what_changed: str | None = None
    template_fields: dict | None = None
    specialty_tags: list[str] | None = None
    free_tags: list[str] | None = None
    outcome_tags: list[str] | None = None
    intervention_tags: list[str] | None = None


class CaseUpdateRequest(CaseCreateRequest):
    pass


class CaseListItem(BaseModel):
    id: int
    case_type: str
    specialty: str
    specialty_domain: str | None = None
    symptoms: str
    resource_setting: str | None = None
    created_at: datetime
    tags: list[str]

    model_config = {"from_attributes": True}


class CaseDetail(BaseModel):
    id: int
    org_id: int
    author_id: int
    case_type: str
    specialty: str
    specialty_domain: str | None = None
    symptoms: str
    demographics: str | None = None
    age_bucket: str | None = None
    constraints: str | None = None
    resource_setting: str | None = None
    suspected_dx: str | None = None
    final_dx: str | None = None
    interventions: str | None = None
    outcomes: str | None = None
    follow_up: str | None = None
    what_changed: str | None = None
    template_fields: dict
    tags: list[str]
    specialty_tags: list[str]
    free_tags: list[str]
    outcome_tags: list[str]
    intervention_tags: list[str]
    record_schema: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    summary: str
    case_type: str | None = None
    specialty: str | None = None
    region: str | None = None
    age_bucket: str | None = None
    constraints: str | None = None
    tags: list[str] | None = None
    limit: int = 5


class SearchResult(BaseModel):
    case_id: int
    specialty: str
    case_type: str
    score: float
    confidence: float
    explanation: list[str]
    score_breakdown: dict[str, float]


class MatchRequest(BaseModel):
    summary: str
    case_type: str | None = None
    specialty: str | None = None
    region: str | None = None
    urgency: str | None = None
    constraints: str | None = None
    tags: list[str] | None = None


class MatchResult(BaseModel):
    doctor_id: int
    doctor_name: str
    specialty: str
    region: str | None = None
    availability: str
    score: float
    explanation: list[str]
    score_breakdown: dict[str, float]


class RevisionOut(BaseModel):
    revision_num: int
    created_at: datetime
    data_json: dict
    diff_json: dict


class AuditLogOut(BaseModel):
    action: str
    entity_type: str
    entity_id: str | None = None
    viewer_email: str | None = None
    ip_address: str | None = None
    created_at: datetime
    metadata: dict = Field(default_factory=dict)
