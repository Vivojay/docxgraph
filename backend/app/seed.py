from sqlalchemy.orm import Session

from .auth import get_password_hash
from .case_types import CASE_TYPE_ED_NEURO, CASE_TYPE_GENERAL, CASE_TYPE_IMMUNO
from .crud import create_case
from .db import SessionLocal, ensure_local_schema
from .jobs.graph import rebuild_case_graph
from .models import (
    AvailabilityEnum,
    Case,
    DoctorProfile,
    Organization,
    OrganizationSettings,
    RoleEnum,
    Team,
    User,
)
from .services.retrieval import sync_user_search_document
from .template_fields import serialize_template_fields


def _create_user(
    db: Session,
    org: Organization,
    team: Team,
    email: str,
    name: str,
    role: RoleEnum,
    specialty: str,
    region: str,
    years: int,
    availability: AvailabilityEnum,
    verified: bool = True,
    password: str = "DemoPass123!",
) -> User:
    user = User(
        email=email,
        full_name=name,
        hashed_password=get_password_hash(password),
        role=role,
        org_id=org.id,
        team_id=team.id,
    )
    db.add(user)
    db.flush()
    db.add(
        DoctorProfile(
            user_id=user.id,
            specialty=specialty,
            years_experience=years,
            region=region,
            verified=verified,
            availability_status=availability,
            proof_status="verified_manual" if verified else "pending_review",
        )
    )
    return user


def _case_templates() -> list[dict]:
    templates = [
        {
            "case_type": CASE_TYPE_GENERAL,
            "specialty": "Neurology",
            "specialty_domain": "neuro",
            "urgency": "medium",
            "symptoms": "Progressive facial numbness with episodic headaches and mild dizziness.",
            "demographics": "adult female",
            "age_bucket": "40-49",
            "constraints": "rural clinic limited MRI access",
            "resource_setting": "community_hospital",
            "suspected_dx": "Trigeminal neuralgia",
            "final_dx": "Vestibular schwannoma",
            "interventions": "Referral to neuro-otology and vestibular rehab",
            "outcomes": "Improved balance and symptom control",
            "follow_up": "6-week follow-up showed reduced falls",
            "what_changed": "Earlier referral for imaging",
            "specialty_tags": "neuro, cranial nerve",
            "free_tags": "dizziness, referral",
            "outcome_tags": "improved function",
            "intervention_tags": "rehab",
        },
        {
            "case_type": CASE_TYPE_GENERAL,
            "specialty": "Cardiology",
            "specialty_domain": "cardio",
            "urgency": "medium",
            "symptoms": "Intermittent chest tightness after dental procedure.",
            "demographics": "older male",
            "age_bucket": "50-59",
            "constraints": "on anticoagulation",
            "resource_setting": "ambulatory_clinic",
            "suspected_dx": "Reflux",
            "final_dx": "Atypical angina",
            "interventions": "Stress test and medication adjustment",
            "outcomes": "Symptoms resolved with beta blocker",
            "follow_up": "No recurrence at 3 months",
            "what_changed": "Earlier ECG",
            "specialty_tags": "cardio, procedure",
            "free_tags": "angina, dental",
            "outcome_tags": "symptom resolution",
            "intervention_tags": "beta blocker",
        },
        {
            "case_type": CASE_TYPE_ED_NEURO,
            "specialty": "Emergency Medicine",
            "specialty_domain": "neuro",
            "urgency": "high",
            "symptoms": "Acute right facial droop, slurred speech, and arm weakness.",
            "demographics": "older male",
            "age_bucket": "60-69",
            "constraints": "community hospital no overnight MRI",
            "resource_setting": "ed",
            "suspected_dx": "Ischemic stroke",
            "final_dx": "Left MCA occlusion",
            "interventions": "tPA administered and tele-neuro consult",
            "outcomes": "Motor function improved and no transfer required",
            "follow_up": "Discharged to home PT",
            "what_changed": "Earlier CTA to confirm occlusion",
            "specialty_tags": "stroke, neuro",
            "free_tags": "teleneuro, triage",
            "outcome_tags": "transfer avoided",
            "intervention_tags": "tele-neuro, tPA",
            "template_fields": {
                "onset_time": "2 hours prior",
                "last_known_well": "07:45",
                "nihss": 6,
                "anticoagulation": "no",
                "imaging_available": "yes",
                "deficits": "Right facial droop, slurred speech, right arm weakness.",
                "tpa_given": "yes",
                "thrombectomy_candidate": "unknown",
                "transfer_needed": True,
                "transfer_avoided": True,
                "consult_time_minutes": 12,
                "routing_notes": "Tele-neuro supported in-house management.",
            },
        },
        {
            "case_type": CASE_TYPE_IMMUNO,
            "specialty": "Oncology",
            "specialty_domain": "oncology",
            "urgency": "urgent",
            "symptoms": "Severe diarrhea and abdominal cramping after PD-1 inhibitor.",
            "demographics": "midlife female",
            "age_bucket": "50-59",
            "constraints": "recent infusion and limited outpatient labs",
            "resource_setting": "infusion_center",
            "suspected_dx": "Infectious colitis",
            "final_dx": "Immune-mediated colitis",
            "interventions": "High-dose steroids and GI consult",
            "outcomes": "Symptoms improved without ICU escalation",
            "follow_up": "Steroid taper completed in 5 weeks",
            "what_changed": "Earlier irAE recognition",
            "specialty_tags": "oncology, irae",
            "free_tags": "colitis, immunotherapy",
            "outcome_tags": "no icu",
            "intervention_tags": "steroids",
            "template_fields": {
                "therapy_regimen": "pembrolizumab",
                "cycle_number": 4,
                "days_since_infusion": 9,
                "irae_system": "gi",
                "severity_grade": 3,
                "steroid_response": "yes",
                "icu_escalation": False,
                "consult_services": "GI, oncology",
                "held_therapy": "yes",
                "rechallenged": "no",
            },
        },
    ]
    return templates


def seed() -> None:
    ensure_local_schema()
    db: Session = SessionLocal()
    try:
        existing = db.query(Organization).filter(Organization.name == "Demo Health").first()
        if existing:
            print("Seed already present")
            return

        org_specs = [
            ("Demo Health", "Midwest"),
            ("Northwind Medical Group", "Northeast"),
        ]
        all_users: list[User] = []
        orgs: list[Organization] = []
        for org_name, region in org_specs:
            org = Organization(name=org_name, region=region)
            db.add(org)
            db.flush()
            db.add(OrganizationSettings(org_id=org.id, retention_days=365, export_format="json"))
            team = Team(org_id=org.id, name="General Care")
            db.add(team)
            db.flush()
            orgs.append(org)

            admin_email = "admin@demo.health" if org_name == "Demo Health" else "admin@northwind.health"
            admin_password = "AdminPass123!" if org_name == "Demo Health" else "NorthwindPass123!"
            admin = _create_user(
                db,
                org,
                team,
                admin_email,
                f"Dr. {org_name.split()[0]} Admin",
                RoleEnum.org_admin,
                "Emergency Medicine",
                region,
                12,
                AvailabilityEnum.available,
                password=admin_password,
            )
            reviewer = _create_user(
                db,
                org,
                team,
                f"reviewer.{org.id}@demo.health",
                f"Dr. Reviewer {org.id}",
                RoleEnum.reviewer,
                "Neurology",
                region,
                10,
                AvailabilityEnum.available,
            )
            auditor = _create_user(
                db,
                org,
                team,
                f"auditor.{org.id}@demo.health",
                f"Dr. Auditor {org.id}",
                RoleEnum.auditor,
                "Internal Medicine",
                region,
                8,
                AvailabilityEnum.busy,
            )
            clinicians = [
                _create_user(db, org, team, f"dr.lee.{org.id}@demo.health", "Dr. Priya Lee", RoleEnum.clinician, "Neurology", "West", 9, AvailabilityEnum.available),
                _create_user(db, org, team, f"dr.martinez.{org.id}@demo.health", "Dr. Isabel Martinez", RoleEnum.clinician, "Cardiology", "South", 15, AvailabilityEnum.busy),
                _create_user(db, org, team, f"dr.owen.{org.id}@demo.health", "Dr. Marcus Owen", RoleEnum.clinician, "ENT", "Northeast", 7, AvailabilityEnum.available),
                _create_user(db, org, team, f"dr.chen.{org.id}@demo.health", "Dr. Ada Chen", RoleEnum.clinician, "Endocrinology", "Midwest", 11, AvailabilityEnum.offline),
                _create_user(db, org, team, f"dr.singh.{org.id}@demo.health", "Dr. Arjun Singh", RoleEnum.clinician, "Oncology", "Northeast", 10, AvailabilityEnum.available),
            ]
            all_users.extend([admin, reviewer, auditor, *clinicians])

        db.commit()
        for user in all_users:
            sync_user_search_document(user)

        templates = _case_templates()
        for org in orgs:
            org_users = [user for user in all_users if user.org_id == org.id and user.role in {RoleEnum.clinician, RoleEnum.org_admin}]
            for idx in range(26):
                author = org_users[idx % len(org_users)]
                template = templates[idx % len(templates)]
                case = Case(
                    org_id=org.id,
                    author_id=author.id,
                    case_type=template["case_type"],
                    specialty=template["specialty"],
                    specialty_domain=template.get("specialty_domain"),
                    urgency=template.get("urgency"),
                    symptoms=f"{template['symptoms']} Cohort variation {idx + 1}.",
                    demographics=template.get("demographics"),
                    age_bucket=template.get("age_bucket"),
                    constraints=f"{template.get('constraints', '')} scenario-{idx % 4}",
                    resource_setting=template.get("resource_setting"),
                    suspected_dx=template.get("suspected_dx"),
                    final_dx=template.get("final_dx"),
                    interventions=template.get("interventions"),
                    outcomes=template.get("outcomes"),
                    follow_up=template.get("follow_up"),
                    what_changed=template.get("what_changed"),
                    template_fields=serialize_template_fields(template.get("template_fields", {})),
                    record_schema="clinical_micro_case",
                )
                create_case(
                    db,
                    case,
                    template.get("specialty_tags"),
                    template.get("free_tags"),
                    template.get("outcome_tags"),
                    template.get("intervention_tags"),
                )
            db.commit()
            rebuild_case_graph(db, org_id=org.id)
            db.commit()

        print("Seed complete: 2 orgs, 52 cases")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
