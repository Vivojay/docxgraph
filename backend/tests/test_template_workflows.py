from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import backend.app.db as db_module
import backend.app.deps as deps_module
import backend.app.main as main_module
from backend.app.auth import get_password_hash
from backend.app.crud import create_case
from backend.app.db import Base
from backend.app.main import app
from backend.app.models import AvailabilityEnum, Case, DoctorProfile, Organization, OrganizationSettings, RoleEnum, Team, User


def _seed_template_app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db_module.SessionLocal = SessionLocal
    deps_module.SessionLocal = SessionLocal
    main_module.engine = engine

    session = SessionLocal()
    org = Organization(name="Template Org", region="Midwest")
    session.add(org)
    session.flush()
    session.add(OrganizationSettings(org_id=org.id, retention_days=365, export_format="json"))
    team = Team(org_id=org.id, name="Core")
    session.add(team)
    session.flush()
    admin = User(
        email="admin@template.org",
        full_name="Admin Template",
        hashed_password=get_password_hash("AdminPass123!"),
        role=RoleEnum.org_admin,
        org_id=org.id,
        team_id=team.id,
    )
    clinician = User(
        email="clinician@template.org",
        full_name="Clinician Template",
        hashed_password=get_password_hash("DemoPass123!"),
        role=RoleEnum.clinician,
        org_id=org.id,
        team_id=team.id,
    )
    session.add_all([admin, clinician])
    session.flush()
    session.add_all(
        [
            DoctorProfile(
                user_id=admin.id,
                specialty="Neurology",
                years_experience=12,
                region="Midwest",
                verified=True,
                availability_status=AvailabilityEnum.available,
            ),
            DoctorProfile(
                user_id=clinician.id,
                specialty="Neurology",
                years_experience=10,
                region="Midwest",
                verified=True,
                availability_status=AvailabilityEnum.available,
            ),
        ]
    )
    case = Case(
        org_id=org.id,
        author_id=clinician.id,
        case_type="ed_neuro",
        specialty="Neurology",
        specialty_domain="neuro",
        urgency="high",
        symptoms="Acute facial droop with slurred speech",
        demographics="older male",
        age_bucket="60-69",
        constraints="community hospital",
        resource_setting="ed",
        outcomes="transfer avoided",
        record_schema="clinical_micro_case",
    )
    create_case(session, case, "stroke,neuro", "facial droop,teleneuro", "transfer avoided", "tele-neuro")
    session.commit()
    session.close()


def test_template_login_dashboard_and_search_flow():
    _seed_template_app()
    client = TestClient(app)

    login_page = client.get("/login")
    assert login_page.status_code == 200
    csrf_token = client.cookies.get("eg_csrf")
    assert csrf_token

    login = client.post(
        "/login",
        data={"email": "admin@template.org", "password": "AdminPass123!", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/dashboard"
    assert client.cookies.get("eg_session")

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Latest de-identified cases" in dashboard.text

    search = client.post(
        "/search",
        data={
            "csrf_token": client.cookies.get("eg_csrf"),
            "summary": "stroke facial droop",
            "specialty": "Neurology",
            "tags": "stroke",
            "constraints": "community hospital",
            "case_type": "ed_neuro",
            "limit": "5",
        },
    )
    assert search.status_code == 200
    assert "semantic similarity" in search.text
    assert "Score" in search.text
