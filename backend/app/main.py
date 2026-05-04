from datetime import datetime, timedelta
import json
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .audit import log_audit_event
from .auth import create_access_token, verify_password
from .case_types import CASE_TYPE_ED_NEURO, CASE_TYPE_GENERAL, CASE_TYPE_IMMUNO, normalize_case_type
from .config import settings
from .core.permissions import VERIFIED_ENDORSER_ROLES, can_manage_org, can_review_audit_logs
from .crud import create_case, update_case
from .db import ensure_local_schema
from .deps import get_current_user, get_current_user_api, get_db, get_optional_user, require_admin, require_admin_api, require_auditor_api
from .jobs.graph import rebuild_case_graph
from .models import (
    AuthEvent,
    AuditLog,
    AvailabilityEnum,
    Case,
    CaseRevision,
    CaseTag,
    CaseViewLog,
    DoctorProfile,
    Endorsement,
    OrganizationSettings,
    RoleEnum,
    Tag,
    TagTypeEnum,
    User,
)
from .retrieval import find_similar_cases, get_case_tags_map, match_experts, refresh_case_similarity_edges, similar_cases_for_case
from .schemas import (
    AuditLogOut,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthMeResponse,
    CaseCreateRequest,
    CaseDetail,
    CaseListItem,
    MatchRequest,
    MatchResult,
    OrgSettingsOut,
    OrgSettingsUpdate,
    ProfileOut,
    RevisionOut,
    SearchRequest,
    SearchResult,
    UserOut,
)
from .security import normalize_tag_list, validate_case_text_fields
from .services.firebase_store import firebase_enabled, get_firestore_client, list_case_documents
from .services.qdrant_store import get_qdrant_client
from .services.retrieval import sync_case_search_document, sync_user_search_document
from .template_fields import normalize_template_fields, parse_template_fields, serialize_template_fields
from .token_service import create_refresh_token, revoke_refresh_token, rotate_refresh_token

app = FastAPI(title="ExperienceGraph Enterprise", version="0.2.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

CASE_TYPE_LABELS = {
    CASE_TYPE_GENERAL: "General clinician case",
    CASE_TYPE_ED_NEURO: "ED neuro referral",
    CASE_TYPE_IMMUNO: "Immunotherapy toxicity",
}
CASE_PROGRAM_SLUGS = {
    "general": CASE_TYPE_GENERAL,
    "ed-neuro": CASE_TYPE_ED_NEURO,
    "immunotherapy": CASE_TYPE_IMMUNO,
}


def parse_frontend_origins() -> list[str]:
    return [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'",
    )
    if settings.env != "local":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.on_event("startup")
def on_startup() -> None:
    if settings.bootstrap_schema and settings.env == "local":
        ensure_local_schema()


def validate_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        if settings.env == "local":
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing origin")
    if origin not in parse_frontend_origins():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")


def refresh_cookie_settings() -> dict:
    if settings.env == "local":
        return {"secure": False, "samesite": "lax"}
    return {"secure": True, "samesite": "none"}


def get_or_create_csrf_token(request: Request) -> str:
    existing = request.cookies.get(settings.csrf_cookie_name)
    if existing:
        return existing
    return secrets.token_urlsafe(24)


def attach_browser_cookies(response, access_token: str | None = None, refresh_token: str | None = None, csrf_token: str | None = None) -> None:
    cookie_settings = refresh_cookie_settings()
    if access_token is not None:
        response.set_cookie(
            settings.session_cookie_name,
            access_token,
            httponly=True,
            samesite=cookie_settings["samesite"],
            secure=cookie_settings["secure"],
            max_age=settings.access_token_expire_minutes * 60,
            path="/",
        )
    if refresh_token is not None:
        response.set_cookie(
            settings.refresh_cookie_name,
            refresh_token,
            httponly=True,
            samesite=cookie_settings["samesite"],
            secure=cookie_settings["secure"],
            max_age=settings.refresh_token_expire_days * 86400,
            path="/api/auth",
        )
    if csrf_token is not None:
        response.set_cookie(
            settings.csrf_cookie_name,
            csrf_token,
            httponly=False,
            samesite=cookie_settings["samesite"],
            secure=cookie_settings["secure"],
            max_age=settings.refresh_token_expire_days * 86400,
            path="/",
        )


def clear_browser_cookies(response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path="/api/auth")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def verify_csrf(request: Request, submitted_token: str | None) -> None:
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not cookie_token or not submitted_token or cookie_token != submitted_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def render_page(request: Request, template_name: str, *, user: User | None = None, **context):
    csrf_token = get_or_create_csrf_token(request)
    response = templates.TemplateResponse(
        request,
        template_name,
        {
            "request": request,
            "user": user,
            "csrf_token": csrf_token,
            "case_type_labels": CASE_TYPE_LABELS,
            **context,
        },
    )
    attach_browser_cookies(response, csrf_token=csrf_token)
    return response


def bool_from_form(value: str | None) -> bool | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if cleaned in {"yes", "true", "1"}:
        return True
    if cleaned in {"no", "false", "0"}:
        return False
    return None


def int_from_form(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def tag_string(value: str | None) -> str:
    return value.strip() if value else ""


def build_case_payload_from_form(form: dict, case_type: str) -> CaseCreateRequest:
    template_fields = {}
    if case_type == CASE_TYPE_ED_NEURO:
        template_fields = {
            "onset_time": form.get("ed_onset_time") or None,
            "last_known_well": form.get("ed_last_known_well") or None,
            "nihss": int_from_form(form.get("ed_nihss")),
            "anticoagulation": form.get("ed_anticoagulation") or None,
            "imaging_available": form.get("ed_imaging_available") or None,
            "deficits": form.get("ed_deficits") or None,
            "tpa_given": form.get("ed_tpa_given") or None,
            "thrombectomy_candidate": form.get("ed_thrombectomy_candidate") or None,
            "transfer_needed": bool_from_form(form.get("ed_transfer_needed")),
            "transfer_avoided": bool_from_form(form.get("ed_transfer_avoided")),
            "consult_time_minutes": int_from_form(form.get("ed_consult_time_minutes")),
            "routing_notes": form.get("ed_routing_notes") or None,
        }
    elif case_type == CASE_TYPE_IMMUNO:
        template_fields = {
            "therapy_regimen": form.get("im_therapy_regimen") or None,
            "cycle_number": int_from_form(form.get("im_cycle_number")),
            "days_since_infusion": int_from_form(form.get("im_days_since_infusion")),
            "irae_system": form.get("im_irae_system") or None,
            "severity_grade": int_from_form(form.get("im_severity_grade")),
            "steroid_response": form.get("im_steroid_response") or None,
            "icu_escalation": bool_from_form(form.get("im_icu_escalation")),
            "consult_services": form.get("im_consult_services") or None,
            "held_therapy": form.get("im_held_therapy") or None,
            "rechallenged": form.get("im_rechallenged") or None,
        }
    return CaseCreateRequest(
        case_type=case_type,
        specialty=form.get("specialty") or "",
        specialty_domain=form.get("specialty_domain") or None,
        urgency=form.get("urgency") or None,
        symptoms=form.get("symptoms") or "",
        demographics=form.get("demographics") or None,
        age_bucket=form.get("age_bucket") or None,
        constraints=form.get("constraints") or None,
        resource_setting=form.get("resource_setting") or None,
        suspected_dx=form.get("suspected_dx") or None,
        final_dx=form.get("final_dx") or None,
        interventions=form.get("interventions") or None,
        outcomes=form.get("outcomes") or None,
        follow_up=form.get("follow_up") or None,
        what_changed=form.get("what_changed") or None,
        template_fields={key: value for key, value in template_fields.items() if value not in (None, "")},
        specialty_tags=[tag.strip() for tag in tag_string(form.get("specialty_tags")).split(",") if tag.strip()],
        free_tags=[tag.strip() for tag in tag_string(form.get("free_tags")).split(",") if tag.strip()],
        outcome_tags=[tag.strip() for tag in tag_string(form.get("outcome_tags")).split(",") if tag.strip()],
        intervention_tags=[tag.strip() for tag in tag_string(form.get("intervention_tags")).split(",") if tag.strip()],
    )


def is_login_rate_limited(db: Session, email: str, ip_address: str | None) -> bool:
    cutoff = datetime.utcnow() - timedelta(minutes=settings.login_rate_limit_window_minutes)
    filters = []
    if email:
        filters.append(AuthEvent.email == email)
    if ip_address:
        filters.append(AuthEvent.ip_address == ip_address)
    if not filters:
        return False
    return (
        db.query(AuthEvent)
        .filter(AuthEvent.event_type == "login_failed", AuthEvent.created_at >= cutoff, or_(*filters))
        .count()
        >= settings.login_rate_limit_max_attempts
    )


def parse_tag_groups(db: Session, case_id: int) -> dict[str, list[str]]:
    from .models import CaseTag

    actual_rows = (
        db.query(Tag.name, Tag.tag_type)
        .join(CaseTag, CaseTag.tag_id == Tag.id)
        .filter(CaseTag.case_id == case_id)
        .all()
    )
    groups = {
        "specialty_tags": [],
        "free_tags": [],
        "outcome_tags": [],
        "intervention_tags": [],
    }
    for name, tag_type in actual_rows:
        if tag_type == TagTypeEnum.specialty:
            groups["specialty_tags"].append(name)
        elif tag_type == TagTypeEnum.free:
            groups["free_tags"].append(name)
        elif tag_type == TagTypeEnum.outcome:
            groups["outcome_tags"].append(name)
        elif tag_type == TagTypeEnum.intervention:
            groups["intervention_tags"].append(name)
    return groups


def case_to_detail(db: Session, case: Case) -> CaseDetail:
    tags_map = get_case_tags_map(db, [case.id])
    grouped = parse_tag_groups(db, case.id)
    return CaseDetail(
        id=case.id,
        org_id=case.org_id,
        author_id=case.author_id,
        case_type=case.case_type,
        specialty=case.specialty,
        specialty_domain=case.specialty_domain,
        urgency=case.urgency,
        symptoms=case.symptoms,
        demographics=case.demographics,
        age_bucket=case.age_bucket,
        constraints=case.constraints,
        resource_setting=case.resource_setting,
        suspected_dx=case.suspected_dx,
        final_dx=case.final_dx,
        interventions=case.interventions,
        outcomes=case.outcomes,
        follow_up=case.follow_up,
        what_changed=case.what_changed,
        template_fields=parse_template_fields(case.template_fields),
        tags=tags_map.get(case.id, []),
        specialty_tags=grouped["specialty_tags"],
        free_tags=grouped["free_tags"],
        outcome_tags=grouped["outcome_tags"],
        intervention_tags=grouped["intervention_tags"],
        record_schema=case.record_schema,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def case_list_item_from_document(document: dict) -> CaseListItem:
    return CaseListItem(
        id=int(document["id"]),
        case_type=document["case_type"],
        specialty=document["specialty"],
        specialty_domain=document.get("specialty_domain"),
        urgency=document.get("urgency"),
        symptoms=document["symptoms"],
        resource_setting=document.get("resource_setting"),
        created_at=datetime.fromisoformat(document["created_at"]) if document.get("created_at") else datetime.utcnow(),
        tags=document.get("tags", []),
    )


def case_detail_from_document(document: dict) -> CaseDetail:
    tags = document.get("tags", [])
    template_fields = document.get("template_fields") or {}
    return CaseDetail(
        id=int(document["id"]),
        org_id=int(document["org_id"]),
        author_id=int(document["author_id"]),
        case_type=document["case_type"],
        specialty=document["specialty"],
        specialty_domain=document.get("specialty_domain"),
        urgency=document.get("urgency"),
        symptoms=document["symptoms"],
        demographics=document.get("demographics"),
        age_bucket=document.get("age_bucket"),
        constraints=document.get("constraints"),
        resource_setting=document.get("resource_setting"),
        suspected_dx=document.get("suspected_dx"),
        final_dx=document.get("final_dx"),
        interventions=document.get("interventions"),
        outcomes=document.get("outcomes"),
        follow_up=document.get("follow_up"),
        what_changed=document.get("what_changed"),
        template_fields=template_fields,
        tags=tags,
        specialty_tags=document.get("specialty_tags", []),
        free_tags=document.get("free_tags", tags),
        outcome_tags=document.get("outcome_tags", []),
        intervention_tags=document.get("intervention_tags", []),
        record_schema=document.get("record_schema", "clinical_micro_case"),
        created_at=datetime.fromisoformat(document["created_at"]) if document.get("created_at") else datetime.utcnow(),
        updated_at=datetime.fromisoformat(document["updated_at"]) if document.get("updated_at") else datetime.utcnow(),
    )


def apply_case_payload(case: Case, payload: CaseCreateRequest) -> None:
    normalized_case_type = normalize_case_type(payload.case_type)
    case.case_type = normalized_case_type
    case.specialty = payload.specialty
    case.specialty_domain = payload.specialty_domain
    case.urgency = payload.urgency
    case.symptoms = payload.symptoms
    case.demographics = payload.demographics
    case.age_bucket = payload.age_bucket
    case.constraints = payload.constraints
    case.resource_setting = payload.resource_setting
    case.suspected_dx = payload.suspected_dx
    case.final_dx = payload.final_dx
    case.interventions = payload.interventions
    case.outcomes = payload.outcomes
    case.follow_up = payload.follow_up
    case.what_changed = payload.what_changed
    case.template_fields = serialize_template_fields(normalize_template_fields(normalized_case_type, payload.template_fields or {}))


def validate_case_payload(payload: CaseCreateRequest) -> list[dict[str, str]]:
    fields = {
        "symptoms": payload.symptoms,
        "demographics": payload.demographics,
        "constraints": payload.constraints,
        "suspected_dx": payload.suspected_dx,
        "final_dx": payload.final_dx,
        "interventions": payload.interventions,
        "outcomes": payload.outcomes,
        "follow_up": payload.follow_up,
        "what_changed": payload.what_changed,
    }
    for key, value in (payload.template_fields or {}).items():
        if isinstance(value, str):
            fields[f"template_{key}"] = value
    return validate_case_text_fields(fields)


def ensure_org_settings(db: Session, org_id: int) -> OrganizationSettings:
    settings_row = db.query(OrganizationSettings).filter(OrganizationSettings.org_id == org_id).first()
    if settings_row:
        return settings_row
    settings_row = OrganizationSettings(org_id=org_id, retention_days=settings.default_retention_days, export_format="json")
    db.add(settings_row)
    db.flush()
    return settings_row


def render_case_form(
    request: Request,
    user: User,
    *,
    action: str,
    case_type: str,
    case: Case | None = None,
    errors: str | None = None,
    form_action: str | None = None,
    specialty_tags: str = "",
    free_tags: str = "",
    outcome_tags: str = "",
    intervention_tags: str = "",
):
    template_name = {
        CASE_TYPE_ED_NEURO: "case_form_ed_neuro.html",
        CASE_TYPE_IMMUNO: "case_form_immuno.html",
    }.get(case_type, "case_form.html")
    return render_page(
        request,
        template_name,
        user=user,
        action=action,
        case=case,
        case_type=case_type,
        case_type_label=CASE_TYPE_LABELS.get(case_type, case_type),
        errors=errors,
        form_action=form_action,
        template_fields=parse_template_fields(case.template_fields) if case and case.template_fields else {},
        specialty_tags=specialty_tags,
        free_tags=free_tags,
        outcome_tags=outcome_tags,
        intervention_tags=intervention_tags,
    )


@app.get("/", response_class=HTMLResponse)
def index(user: User | None = Depends(get_optional_user)):
    return RedirectResponse(url="/dashboard" if user else "/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render_page(request, "login.html", user=None)


@app.post("/login")
async def login_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    email_normalized = (form.get("email") or "").lower().strip()
    password = form.get("password") or ""
    ip_address = request.client.host if request.client else None
    if is_login_rate_limited(db, email_normalized, ip_address):
        return render_page(request, "login.html", user=None, error="Too many attempts. Please try again shortly.")
    user = db.query(User).filter(User.email == email_normalized).first()
    if not user or not verify_password(password, user.hashed_password):
        db.add(AuthEvent(email=email_normalized, ip_address=ip_address, event_type="login_failed"))
        log_audit_event(db, "login_failed", "auth", entity_id=email_normalized, request=request, metadata={"email": email_normalized})
        db.commit()
        return render_page(request, "login.html", user=None, error="Invalid credentials.")
    if not user.is_active:
        return render_page(request, "login.html", user=None, error="Account disabled.")
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token(db, user.id)
    csrf_token = get_or_create_csrf_token(request)
    user.last_login_at = datetime.utcnow()
    db.add(user)
    sync_user_search_document(user)
    db.add(AuthEvent(email=email_normalized, ip_address=ip_address, event_type="login_success"))
    log_audit_event(db, "login_success", "auth", entity_id=user.id, user=user, request=request)
    db.commit()
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    attach_browser_cookies(response, access_token=access_token, refresh_token=refresh_token, csrf_token=csrf_token)
    return response


@app.post("/logout")
async def logout_submit(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    log_audit_event(db, "logout", "auth", entity_id=user.id, user=user, request=request)
    db.commit()
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_browser_cookies(response)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cases = db.query(Case).filter(Case.org_id == user.org_id).order_by(Case.created_at.desc()).limit(12).all()
    top_tags = (
        db.query(Tag.name, func.count(CaseTag.case_id))
        .join(CaseTag, CaseTag.tag_id == Tag.id)
        .join(Case, Case.id == CaseTag.case_id)
        .filter(Case.org_id == user.org_id)
        .group_by(Tag.name)
        .order_by(func.count(CaseTag.case_id).desc())
        .limit(8)
        .all()
    )
    roi_metrics = api_roi_metrics(user=user, db=db)
    return render_page(
        request,
        "dashboard.html",
        user=user,
        cases=cases,
        top_tags=top_tags,
        case_type_counts=roi_metrics["case_type_counts"],
        ed_metrics=roi_metrics["ed_metrics"],
        immuno_metrics=roi_metrics["immuno_metrics"],
    )


@app.get("/cases/new", response_class=HTMLResponse)
def case_program_select_page(request: Request, user: User = Depends(get_current_user)):
    return render_page(request, "case_select.html", user=user)


@app.get("/cases/new/{program_slug}", response_class=HTMLResponse)
def case_new_page(program_slug: str, request: Request, user: User = Depends(get_current_user)):
    case_type = CASE_PROGRAM_SLUGS.get(program_slug)
    if not case_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return render_case_form(request, user, action="Create", case_type=case_type, form_action=f"/cases/new/{program_slug}")


@app.post("/cases/new/{program_slug}")
async def case_new_submit(program_slug: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case_type = CASE_PROGRAM_SLUGS.get(program_slug)
    if not case_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    payload = build_case_payload_from_form(dict(form), case_type)
    issues = validate_case_payload(payload)
    if issues:
        return render_case_form(
            request,
            user,
            action="Create",
            case_type=case_type,
            errors="Potential identifiers detected. Remove names, phone numbers, emails, addresses, MRNs, or similar identifiers.",
            form_action=f"/cases/new/{program_slug}",
            specialty_tags=form.get("specialty_tags", ""),
            free_tags=form.get("free_tags", ""),
            outcome_tags=form.get("outcome_tags", ""),
            intervention_tags=form.get("intervention_tags", ""),
        )
    case = Case(org_id=user.org_id, author_id=user.id, record_schema="clinical_micro_case")
    apply_case_payload(case, payload)
    tag_names = create_case(
        db,
        case,
        ",".join(payload.specialty_tags or []),
        ",".join(payload.free_tags or []),
        ",".join(payload.outcome_tags or []),
        ",".join(payload.intervention_tags or []),
    )
    refresh_case_similarity_edges(db, case, tag_names)
    log_audit_event(db, "case_created", "case", entity_id=case.id, user=user, request=request)
    db.commit()
    return RedirectResponse(url=f"/cases/{case.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail_page(case_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    db.add(
        CaseViewLog(
            case_id=case.id,
            user_id=user.id,
            org_id=user.org_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    log_audit_event(db, "case_viewed", "case", entity_id=case.id, user=user, request=request)
    tags = get_case_tags_map(db, [case.id]).get(case.id, [])
    similar_cases = similar_cases_for_case(db, case, tags, limit=settings.embedding_similarity_limit)
    grouped_tags = parse_tag_groups(db, case.id)
    endorsements = db.query(Endorsement).filter(Endorsement.case_id == case.id).count()
    has_endorsed = db.query(Endorsement).filter(Endorsement.case_id == case.id, Endorsement.doctor_id == user.id).first() is not None
    specialties: dict[str, int] = {}
    for item in similar_cases:
        specialties[item["case"].specialty] = specialties.get(item["case"].specialty, 0) + 1
    db.commit()
    return render_page(
        request,
        "case_detail.html",
        user=user,
        case=case,
        tags=tags,
        specialty_tags=grouped_tags["specialty_tags"],
        free_tags=grouped_tags["free_tags"],
        outcome_tags=grouped_tags["outcome_tags"],
        intervention_tags=grouped_tags["intervention_tags"],
        template_fields=parse_template_fields(case.template_fields),
        similar_cases=similar_cases,
        specialties=specialties,
        endorsements=endorsements,
        has_endorsed=has_endorsed,
        case_type_label=CASE_TYPE_LABELS.get(case.case_type, case.case_type),
    )


@app.get("/cases/{case_id}/edit", response_class=HTMLResponse)
def case_edit_page(case_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.author_id != user.id and not can_manage_org(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    grouped_tags = parse_tag_groups(db, case.id)
    return render_case_form(
        request,
        user,
        action="Update",
        case=case,
        case_type=case.case_type,
        form_action=f"/cases/{case.id}/edit",
        specialty_tags=", ".join(grouped_tags["specialty_tags"]),
        free_tags=", ".join(grouped_tags["free_tags"]),
        outcome_tags=", ".join(grouped_tags["outcome_tags"]),
        intervention_tags=", ".join(grouped_tags["intervention_tags"]),
    )


@app.post("/cases/{case_id}/edit")
async def case_edit_submit(case_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.author_id != user.id and not can_manage_org(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    payload = build_case_payload_from_form(dict(form), case.case_type)
    issues = validate_case_payload(payload)
    if issues:
        return render_case_form(
            request,
            user,
            action="Update",
            case=case,
            case_type=case.case_type,
            errors="Potential identifiers detected. Remove names, phone numbers, emails, addresses, MRNs, or similar identifiers.",
            form_action=f"/cases/{case.id}/edit",
            specialty_tags=form.get("specialty_tags", ""),
            free_tags=form.get("free_tags", ""),
            outcome_tags=form.get("outcome_tags", ""),
            intervention_tags=form.get("intervention_tags", ""),
        )
    apply_case_payload(case, payload)
    tag_names = update_case(
        db,
        case,
        user.id,
        ",".join(payload.specialty_tags or []),
        ",".join(payload.free_tags or []),
        ",".join(payload.outcome_tags or []),
        ",".join(payload.intervention_tags or []),
    )
    refresh_case_similarity_edges(db, case, tag_names)
    log_audit_event(db, "case_updated", "case", entity_id=case.id, user=user, request=request)
    db.commit()
    return RedirectResponse(url=f"/cases/{case.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/cases/{case_id}/endorse")
async def endorse_case_submit(case_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if user.role not in VERIFIED_ENDORSER_ROLES or not user.profile or not user.profile.verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification required to endorse")
    if case.author_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot endorse your own case")
    cutoff = datetime.utcnow() - timedelta(days=1)
    recent_count = db.query(Endorsement).filter(Endorsement.doctor_id == user.id, Endorsement.created_at >= cutoff).count()
    if recent_count >= settings.endorsement_daily_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily endorsement limit reached")
    already = db.query(Endorsement).filter(Endorsement.case_id == case.id, Endorsement.doctor_id == user.id).first()
    if not already:
        db.add(Endorsement(case_id=case.id, doctor_id=user.id))
        log_audit_event(db, "case_endorsed", "case", entity_id=case.id, user=user, request=request)
        db.commit()
    return RedirectResponse(url=f"/cases/{case.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, user: User = Depends(get_current_user)):
    return render_page(request, "search.html", user=user, results=[])


@app.post("/search", response_class=HTMLResponse)
async def search_submit(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    summary = (form.get("summary") or "").strip()
    if not summary:
        return render_page(request, "search.html", user=user, results=[], error="Case summary is required.")
    tags = [tag.strip() for tag in tag_string(form.get("tags")).split(",") if tag.strip()]
    limit = int_from_form(form.get("limit")) or 5
    results = find_similar_cases(
        db,
        org_id=user.org_id,
        query_text=summary,
        filter_specialty=form.get("specialty") or None,
        filter_tags=tags,
        case_type=normalize_case_type(form.get("case_type")) if form.get("case_type") else None,
        constraint_text=form.get("constraints") or None,
        age_bucket=form.get("age_bucket") or None,
        limit=limit,
    )
    return render_page(
        request,
        "search.html",
        user=user,
        results=results,
        summary=summary,
        specialty=form.get("specialty") or "",
        tags=form.get("tags") or "",
        constraints=form.get("constraints") or "",
        age_bucket=form.get("age_bucket") or "",
        case_type=form.get("case_type") or "",
        limit=limit,
    )


@app.get("/match", response_class=HTMLResponse)
def match_page(request: Request, user: User = Depends(get_current_user)):
    return render_page(request, "match.html", user=user, results=[])


@app.post("/match", response_class=HTMLResponse)
async def match_submit(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    summary = (form.get("summary") or "").strip()
    if not summary:
        return render_page(request, "match.html", user=user, results=[], error="Case summary is required.")
    tags = [tag.strip() for tag in tag_string(form.get("tags")).split(",") if tag.strip()]
    results = match_experts(
        db,
        org_id=user.org_id,
        summary=summary,
        specialty=form.get("specialty") or None,
        region=form.get("region") or None,
        urgency=form.get("urgency") or None,
        tags=tags,
        case_type=normalize_case_type(form.get("case_type")) if form.get("case_type") else None,
        constraint_text=form.get("constraints") or None,
        limit=8,
    )
    return render_page(
        request,
        "match.html",
        user=user,
        results=results,
        summary=summary,
        specialty=form.get("specialty") or "",
        region=form.get("region") or "",
        urgency=form.get("urgency") or "",
        tags=form.get("tags") or "",
        case_type=form.get("case_type") or "",
        constraints=form.get("constraints") or "",
    )


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, user: User = Depends(get_current_user)):
    return render_page(request, "profile.html", user=user)


@app.post("/profile", response_class=HTMLResponse)
async def profile_submit(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    if not user.profile:
        db.add(
            DoctorProfile(
                user_id=user.id,
                specialty=form.get("specialty") or "General",
                years_experience=int_from_form(form.get("years_experience")),
                region=form.get("region") or None,
                availability_status=AvailabilityEnum(form.get("availability_status") or "available"),
                verified=False,
            )
        )
    else:
        user.profile.specialty = form.get("specialty") or user.profile.specialty
        user.profile.years_experience = int_from_form(form.get("years_experience"))
        user.profile.region = form.get("region") or None
        user.profile.availability_status = AvailabilityEnum(form.get("availability_status") or "available")
        db.add(user.profile)
    db.add(user)
    sync_user_search_document(user)
    log_audit_event(db, "profile_updated", "clinician_profile", entity_id=user.id, user=user, request=request)
    db.commit()
    db.refresh(user)
    return render_page(request, "profile.html", user=user, success="Profile updated.")


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    doctors = (
        db.query(User, DoctorProfile)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .filter(User.org_id == user.org_id)
        .order_by(User.full_name.asc())
        .all()
    )
    return render_page(request, "admin.html", user=user, doctors=doctors)


@app.post("/admin/verify/{user_id}")
async def admin_toggle_verify(user_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token"))
    target = (
        db.query(User, DoctorProfile)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .filter(User.id == user_id, User.org_id == user.org_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinician not found")
    account, profile = target
    profile.verified = not profile.verified
    profile.proof_status = "verified_manual" if profile.verified else "pending_review"
    db.add(profile)
    sync_user_search_document(account)
    log_audit_event(db, "clinician_verification_toggled", "clinician_profile", entity_id=account.id, user=user, request=request, metadata={"verified": profile.verified})
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/logs", response_class=HTMLResponse)
def admin_logs_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not can_review_audit_logs(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit access required")
    audit_logs = db.query(AuditLog).filter(AuditLog.org_id == user.org_id).order_by(AuditLog.created_at.desc()).limit(150).all()
    view_logs = (
        db.query(CaseViewLog, Case, User)
        .join(Case, Case.id == CaseViewLog.case_id)
        .join(User, User.id == CaseViewLog.user_id)
        .filter(CaseViewLog.org_id == user.org_id)
        .order_by(CaseViewLog.viewed_at.desc())
        .limit(75)
        .all()
    )
    return render_page(request, "admin_logs.html", user=user, audit_logs=audit_logs, logs=view_logs)


@app.get("/admin/revisions/{case_id}", response_class=HTMLResponse)
def admin_revisions_page(case_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not can_review_audit_logs(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit access required")
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    revisions = db.query(CaseRevision).filter(CaseRevision.case_id == case_id).order_by(CaseRevision.revision_num.desc()).all()
    return render_page(request, "admin_revisions.html", user=user, case_id=case_id, revisions=revisions)


@app.get("/api/health")
def api_health():
    return {
        "status": "ok",
        "app": "ExperienceGraph Enterprise",
        "storage_backend": settings.storage_backend,
        "firebase_ready": bool(get_firestore_client()) if firebase_enabled() else False,
        "qdrant_ready": bool(get_qdrant_client()),
    }


@app.post("/api/auth/login", response_model=AuthLoginResponse)
def api_login(payload: AuthLoginRequest, request: Request, db: Session = Depends(get_db)):
    validate_origin(request)
    email_normalized = payload.email.lower().strip()
    ip_address = request.client.host if request.client else None
    if is_login_rate_limited(db, email_normalized, ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")
    user = db.query(User).filter(User.email == email_normalized).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        db.add(AuthEvent(email=email_normalized, ip_address=ip_address, event_type="login_failed"))
        log_audit_event(db, "login_failed", "auth", entity_id=email_normalized, request=request, metadata={"email": email_normalized})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token(db, user.id)
    user.last_login_at = datetime.utcnow()
    db.add(user)
    sync_user_search_document(user)
    db.add(AuthEvent(email=email_normalized, ip_address=ip_address, event_type="login_success"))
    log_audit_event(db, "login_success", "auth", entity_id=user.id, user=user, request=request)
    db.commit()
    response = JSONResponse(content=AuthLoginResponse(access_token=access_token).model_dump())
    attach_browser_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
        csrf_token=get_or_create_csrf_token(request),
    )
    return response


@app.post("/api/auth/refresh", response_model=AuthLoginResponse)
def api_refresh(request: Request, db: Session = Depends(get_db)):
    validate_origin(request)
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    rotated = rotate_refresh_token(db, refresh_token)
    if not rotated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    new_refresh, user_id = rotated
    access_token = create_access_token({"sub": str(user_id)})
    response = JSONResponse(content=AuthLoginResponse(access_token=access_token).model_dump())
    attach_browser_cookies(response, access_token=access_token, refresh_token=new_refresh, csrf_token=get_or_create_csrf_token(request))
    return response


@app.post("/api/auth/logout")
def api_logout(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user_api)):
    validate_origin(request)
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    log_audit_event(db, "logout", "auth", entity_id=user.id, user=user, request=request)
    db.commit()
    response = JSONResponse(content={"status": "ok"})
    clear_browser_cookies(response)
    return response


@app.get("/api/auth/me", response_model=AuthMeResponse)
def api_me(user: User = Depends(get_current_user_api)):
    profile = ProfileOut.model_validate(user.profile) if user.profile else None
    return {"user": UserOut.model_validate(user), "profile": profile}


@app.get("/api/org/settings", response_model=OrgSettingsOut)
def api_get_org_settings(user: User = Depends(require_admin_api), db: Session = Depends(get_db)):
    settings_row = ensure_org_settings(db, user.org_id)
    feature_flags = json.loads(settings_row.feature_flags_json) if settings_row.feature_flags_json else {}
    return {
        "retention_days": settings_row.retention_days,
        "export_format": settings_row.export_format,
        "feature_flags": feature_flags,
    }


@app.put("/api/org/settings", response_model=OrgSettingsOut)
def api_update_org_settings(
    payload: OrgSettingsUpdate,
    request: Request,
    user: User = Depends(require_admin_api),
    db: Session = Depends(get_db),
):
    settings_row = ensure_org_settings(db, user.org_id)
    if payload.retention_days is not None:
        settings_row.retention_days = payload.retention_days
    if payload.export_format is not None:
        settings_row.export_format = payload.export_format
    if payload.feature_flags is not None:
        settings_row.feature_flags_json = json.dumps(payload.feature_flags)
    db.add(settings_row)
    log_audit_event(db, "org_settings_updated", "organization_settings", entity_id=settings_row.id, user=user, request=request)
    db.commit()
    feature_flags = json.loads(settings_row.feature_flags_json) if settings_row.feature_flags_json else {}
    return {"retention_days": settings_row.retention_days, "export_format": settings_row.export_format, "feature_flags": feature_flags}


@app.get("/api/cases", response_model=list[CaseListItem])
def api_cases(case_type: str | None = None, user: User = Depends(get_current_user_api), db: Session = Depends(get_db)):
    firebase_documents = list_case_documents(org_id=user.org_id) if firebase_enabled() else []
    if firebase_documents:
        if case_type:
            firebase_documents = [doc for doc in firebase_documents if doc.get("case_type") == normalize_case_type(case_type)]
        firebase_documents.sort(key=lambda doc: doc.get("created_at") or "", reverse=True)
        return [case_list_item_from_document(document) for document in firebase_documents]
    query = db.query(Case).filter(Case.org_id == user.org_id)
    if case_type:
        query = query.filter(Case.case_type == normalize_case_type(case_type))
    cases = query.order_by(Case.created_at.desc()).all()
    tags_map = get_case_tags_map(db, [case.id for case in cases])
    return [
        CaseListItem(
            id=case.id,
            case_type=case.case_type,
            specialty=case.specialty,
            specialty_domain=case.specialty_domain,
            urgency=case.urgency,
            symptoms=case.symptoms,
            resource_setting=case.resource_setting,
            created_at=case.created_at,
            tags=tags_map.get(case.id, []),
        )
        for case in cases
    ]


@app.post("/api/cases", response_model=CaseDetail)
def api_create_case(
    payload: CaseCreateRequest,
    request: Request,
    user: User = Depends(get_current_user_api),
    db: Session = Depends(get_db),
):
    issues = validate_case_payload(payload)
    if issues:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Potential identifiers detected", "issues": issues})
    case = Case(org_id=user.org_id, author_id=user.id, record_schema="clinical_micro_case")
    apply_case_payload(case, payload)
    tag_names = create_case(
        db,
        case,
        ",".join(payload.specialty_tags or []),
        ",".join(payload.free_tags or []),
        ",".join(payload.outcome_tags or []),
        ",".join(payload.intervention_tags or []),
    )
    refresh_case_similarity_edges(db, case, tag_names)
    log_audit_event(db, "case_created", "case", entity_id=case.id, user=user, request=request)
    db.commit()
    firebase_documents = list_case_documents(org_id=user.org_id) if firebase_enabled() else []
    firebase_case = next((doc for doc in firebase_documents if int(doc.get("id", 0)) == case.id), None)
    if firebase_case:
        return case_detail_from_document(firebase_case)
    return case_to_detail(db, case)


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
def api_case_detail(
    case_id: int,
    request: Request,
    user: User = Depends(get_current_user_api),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    db.add(
        CaseViewLog(
            case_id=case.id,
            user_id=user.id,
            org_id=user.org_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    log_audit_event(db, "case_viewed", "case", entity_id=case.id, user=user, request=request)
    db.commit()
    firebase_documents = list_case_documents(org_id=user.org_id) if firebase_enabled() else []
    firebase_case = next((doc for doc in firebase_documents if int(doc.get("id", 0)) == case.id), None)
    if firebase_case:
        return case_detail_from_document(firebase_case)
    return case_to_detail(db, case)


@app.put("/api/cases/{case_id}", response_model=CaseDetail)
def api_update_case(
    case_id: int,
    payload: CaseCreateRequest,
    request: Request,
    user: User = Depends(get_current_user_api),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.author_id != user.id and not can_manage_org(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    issues = validate_case_payload(payload)
    if issues:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Potential identifiers detected", "issues": issues})
    apply_case_payload(case, payload)
    tag_names = update_case(
        db,
        case,
        user.id,
        ",".join(payload.specialty_tags or []),
        ",".join(payload.free_tags or []),
        ",".join(payload.outcome_tags or []),
        ",".join(payload.intervention_tags or []),
    )
    refresh_case_similarity_edges(db, case, tag_names)
    log_audit_event(db, "case_updated", "case", entity_id=case.id, user=user, request=request)
    db.commit()
    firebase_documents = list_case_documents(org_id=user.org_id) if firebase_enabled() else []
    firebase_case = next((doc for doc in firebase_documents if int(doc.get("id", 0)) == case.id), None)
    if firebase_case:
        return case_detail_from_document(firebase_case)
    return case_to_detail(db, case)


@app.post("/api/cases/{case_id}/endorse")
def api_endorse_case(case_id: int, request: Request, user: User = Depends(get_current_user_api), db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if user.role not in VERIFIED_ENDORSER_ROLES or not user.profile or not user.profile.verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification required to endorse")
    if case.author_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot endorse your own case")
    cutoff = datetime.utcnow() - timedelta(days=1)
    recent_count = db.query(Endorsement).filter(Endorsement.doctor_id == user.id, Endorsement.created_at >= cutoff).count()
    if recent_count >= settings.endorsement_daily_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily endorsement limit reached")
    already = db.query(Endorsement).filter(Endorsement.case_id == case.id, Endorsement.doctor_id == user.id).first()
    if not already:
        db.add(Endorsement(case_id=case.id, doctor_id=user.id))
        log_audit_event(db, "case_endorsed", "case", entity_id=case.id, user=user, request=request)
        db.commit()
    return {"status": "ok"}


@app.get("/api/cases/{case_id}/similar", response_model=list[SearchResult])
def api_case_similar(case_id: int, user: User = Depends(get_current_user_api), db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    tags_map = get_case_tags_map(db, [case.id])
    similar = similar_cases_for_case(db, case, tags_map.get(case.id, []), limit=settings.embedding_similarity_limit)
    return [
        SearchResult(
            case_id=item["case"].id,
            specialty=item["case"].specialty,
            case_type=item["case"].case_type,
            score=item["score"],
            confidence=item.get("confidence", min(0.99, max(0.1, item["score"]))),
            explanation=item.get("explanation", []),
            score_breakdown=item.get("score_breakdown", {}),
        )
        for item in similar
    ]


@app.post("/api/search/cases", response_model=list[SearchResult])
def api_search_cases(payload: SearchRequest, user: User = Depends(get_current_user_api), db: Session = Depends(get_db)):
    results = find_similar_cases(
        db,
        org_id=user.org_id,
        query_text=payload.summary,
        filter_specialty=payload.specialty,
        filter_tags=payload.tags,
        case_type=normalize_case_type(payload.case_type) if payload.case_type else None,
        constraint_text=payload.constraints,
        age_bucket=payload.age_bucket,
        limit=payload.limit,
    )
    return [
        SearchResult(
            case_id=item["case"].id,
            specialty=item["case"].specialty,
            case_type=item["case"].case_type,
            score=item["score"],
            confidence=item["confidence"],
            explanation=item["explanation"],
            score_breakdown=item["score_breakdown"],
        )
        for item in results
    ]


@app.post("/api/routing/experts", response_model=list[MatchResult])
def api_route_experts(payload: MatchRequest, user: User = Depends(get_current_user_api), db: Session = Depends(get_db)):
    results = match_experts(
        db,
        org_id=user.org_id,
        summary=payload.summary,
        specialty=payload.specialty,
        region=payload.region,
        urgency=payload.urgency,
        tags=payload.tags,
        case_type=normalize_case_type(payload.case_type) if payload.case_type else None,
        constraint_text=payload.constraints,
        limit=8,
    )
    return results


@app.post("/api/match", response_model=list[MatchResult])
def api_match_alias(payload: MatchRequest, user: User = Depends(get_current_user_api), db: Session = Depends(get_db)):
    return api_route_experts(payload, user, db)


@app.get("/api/admin/logs", response_model=list[AuditLogOut])
def api_admin_logs(user: User = Depends(require_auditor_api), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).filter(or_(AuditLog.org_id == user.org_id, user.role == RoleEnum.super_admin)).order_by(AuditLog.created_at.desc()).limit(250).all()
    user_ids = [log.user_id for log in logs if log.user_id]
    users = {u.id: u.email for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return [
        AuditLogOut(
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            viewer_email=users.get(log.user_id),
            ip_address=log.ip_address,
            created_at=log.created_at,
            metadata=json.loads(log.metadata_json) if log.metadata_json else {},
        )
        for log in logs
    ]


@app.get("/api/admin/revisions/{case_id}", response_model=list[RevisionOut])
def api_admin_revisions(case_id: int, user: User = Depends(require_auditor_api), db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.org_id == user.org_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    revisions = db.query(CaseRevision).filter(CaseRevision.case_id == case_id).order_by(CaseRevision.revision_num.desc()).all()
    return [
        RevisionOut(
            revision_num=revision.revision_num,
            created_at=revision.created_at,
            data_json=json.loads(revision.data_json),
            diff_json=json.loads(revision.diff_json) if revision.diff_json else {},
        )
        for revision in revisions
    ]


@app.get("/api/admin/exports/cases")
def api_admin_export_cases(request: Request, user: User = Depends(require_admin_api), db: Session = Depends(get_db)):
    firebase_documents = list_case_documents(org_id=user.org_id) if firebase_enabled() else []
    if firebase_documents:
        firebase_documents.sort(key=lambda doc: doc.get("created_at") or "", reverse=True)
        payload = [case_detail_from_document(document).model_dump(mode="json") for document in firebase_documents]
    else:
        cases = db.query(Case).filter(Case.org_id == user.org_id).order_by(Case.created_at.desc()).all()
        payload = [case_to_detail(db, case).model_dump(mode="json") for case in cases]
    log_audit_event(db, "cases_exported", "case_export", entity_id=user.org_id, user=user, request=request, metadata={"count": len(payload)})
    db.commit()
    return payload


@app.get("/api/metrics/roi")
def api_roi_metrics(user: User = Depends(get_current_user_api), db: Session = Depends(get_db)):
    cases = db.query(Case).filter(Case.org_id == user.org_id).all()
    case_type_counts = {CASE_TYPE_GENERAL: 0, CASE_TYPE_ED_NEURO: 0, CASE_TYPE_IMMUNO: 0}
    ed_transfer_avoided = 0
    ed_consult_times: list[int] = []
    immuno_icu_escalations = 0
    immuno_steroid_response = 0
    for case in cases:
        case_type = normalize_case_type(case.case_type)
        case_type_counts[case_type] = case_type_counts.get(case_type, 0) + 1
        fields = parse_template_fields(case.template_fields)
        if case_type == CASE_TYPE_ED_NEURO and fields.get("transfer_avoided") is True:
            ed_transfer_avoided += 1
        if case_type == CASE_TYPE_ED_NEURO and isinstance(fields.get("consult_time_minutes"), int):
            ed_consult_times.append(fields["consult_time_minutes"])
        if case_type == CASE_TYPE_IMMUNO and fields.get("icu_escalation") is True:
            immuno_icu_escalations += 1
        if case_type == CASE_TYPE_IMMUNO and fields.get("steroid_response") in {"yes", "partial"}:
            immuno_steroid_response += 1
    return {
        "case_type_counts": case_type_counts,
        "ed_metrics": {
            "transfer_avoided": ed_transfer_avoided,
            "avg_consult_time": round(sum(ed_consult_times) / len(ed_consult_times)) if ed_consult_times else None,
        },
        "immuno_metrics": {
            "icu_escalations": immuno_icu_escalations,
            "steroid_response": immuno_steroid_response,
        },
    }


@app.get("/api/metrics/system")
def api_system_metrics(user: User = Depends(require_auditor_api), db: Session = Depends(get_db)):
    total_cases = db.query(Case).filter(Case.org_id == user.org_id).count()
    total_users = db.query(User).filter(User.org_id == user.org_id).count()
    total_verified = (
        db.query(DoctorProfile).join(User, User.id == DoctorProfile.user_id).filter(User.org_id == user.org_id, DoctorProfile.verified.is_(True)).count()
    )
    total_audit_events = db.query(AuditLog).filter(AuditLog.org_id == user.org_id).count()
    return {
        "status": "ok",
        "database_url": settings.database_url,
        "embedding_provider": settings.embedding_provider,
        "storage_backend": settings.storage_backend,
        "firebase_ready": bool(get_firestore_client()) if firebase_enabled() else False,
        "qdrant_ready": bool(get_qdrant_client()),
        "totals": {
            "cases": total_cases,
            "users": total_users,
            "verified_profiles": total_verified,
            "audit_events": total_audit_events,
        },
    }


@app.post("/api/jobs/rebuild-graph")
def api_rebuild_graph(request: Request, user: User = Depends(require_admin_api), db: Session = Depends(get_db)):
    updated = rebuild_case_graph(db, org_id=user.org_id)
    log_audit_event(db, "graph_rebuilt", "graph_job", entity_id=user.org_id, user=user, request=request, metadata={"updated_cases": updated})
    db.commit()
    return {"updated_cases": updated}


@app.post("/api/admin/sync/search-docs")
def api_sync_search_docs(request: Request, user: User = Depends(require_admin_api), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.org_id == user.org_id).all()
    for account in users:
        sync_user_search_document(account)
    cases = db.query(Case).filter(Case.org_id == user.org_id).all()
    tags_map = get_case_tags_map(db, [case.id for case in cases])
    for case in cases:
        sync_case_search_document(db, case, tags_map.get(case.id, []))
    log_audit_event(
        db,
        "search_docs_synced",
        "search_index",
        entity_id=user.org_id,
        user=user,
        request=request,
        metadata={"users": len(users), "cases": len(cases)},
    )
    db.commit()
    return {"status": "ok", "users": len(users), "cases": len(cases)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
