from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.crud import create_case
from backend.app.db import Base
from backend.app.models import AvailabilityEnum, Case, DoctorProfile, Organization, RoleEnum, Team, User
from backend.app.retrieval import find_similar_cases, match_experts


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    return Session()


def test_retrieval_and_routing_return_explanations():
    db = _session()
    org = Organization(name="Test Org", region="Midwest")
    db.add(org)
    db.flush()
    team = Team(org_id=org.id, name="Core")
    db.add(team)
    db.flush()
    doctor = User(
        email="clinician@test.org",
        full_name="Dr. Example",
        hashed_password="hashed",
        role=RoleEnum.clinician,
        org_id=org.id,
        team_id=team.id,
    )
    reviewer = User(
        email="reviewer@test.org",
        full_name="Dr. Reviewer",
        hashed_password="hashed",
        role=RoleEnum.reviewer,
        org_id=org.id,
        team_id=team.id,
    )
    db.add_all([doctor, reviewer])
    db.flush()
    db.add(
        DoctorProfile(
            user_id=doctor.id,
            specialty="Neurology",
            years_experience=12,
            region="Midwest",
            verified=True,
            availability_status=AvailabilityEnum.available,
        )
    )
    db.add(
        DoctorProfile(
            user_id=reviewer.id,
            specialty="Neurology",
            years_experience=10,
            region="Midwest",
            verified=True,
            availability_status=AvailabilityEnum.available,
        )
    )
    case = Case(
        org_id=org.id,
        author_id=doctor.id,
        case_type="ed_neuro",
        specialty="Neurology",
        specialty_domain="neuro",
        symptoms="Acute facial droop and right arm weakness",
        constraints="community hospital no overnight MRI",
        outcomes="Improved after transfer avoidance",
        record_schema="clinical_micro_case",
    )
    create_case(db, case, "stroke,neuro", "facial droop", "improved function", "tele-neuro")
    db.commit()

    similar = find_similar_cases(
        db,
        org_id=org.id,
        query_text="stroke with facial droop",
        filter_specialty="Neurology",
        filter_tags=["stroke"],
        case_type="ed_neuro",
        constraint_text="community hospital",
        limit=3,
    )
    assert similar
    assert similar[0]["score_breakdown"]["vector"] >= 0
    assert "keyword" in similar[0]["score_breakdown"]
    assert "fuzzy" in similar[0]["score_breakdown"]
    assert similar[0]["explanation"]

    experts = match_experts(
        db,
        org_id=org.id,
        summary="stroke with facial droop",
        specialty="Neurology",
        tags=["stroke"],
        case_type="ed_neuro",
        constraint_text="community hospital",
        limit=3,
    )
    assert experts
    assert experts[0]["explanation"]
    assert "similarity" in experts[0]["score_breakdown"]
    db.close()
