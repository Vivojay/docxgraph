import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from backend.app.db.session import SessionLocal
from backend.app.db.init_db import init_db
from backend.app.models.org import Org
from backend.app.models.user import User
from backend.app.models.case import Case, Tag, CaseTag, CaseValidation
from backend.app.core.security import get_password_hash
from backend.app.services.embeddings import embed_texts


def seed():
    init_db()
    db = SessionLocal()

    org = Org(name="Northwind Health", region="Midwest")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id,
        email="admin@northwind.test",
        hashed_password=get_password_hash("adminpass"),
        role="admin",
        specialty="admin",
        region="Midwest",
        is_verified=True,
    )
    doc1 = User(
        org_id=org.id,
        email="neuro@northwind.test",
        hashed_password=get_password_hash("password"),
        role="doctor",
        specialty="neurology",
        years_experience=12,
        region="Midwest",
        is_verified=True,
    )
    doc2 = User(
        org_id=org.id,
        email="oral@northwind.test",
        hashed_password=get_password_hash("password"),
        role="doctor",
        specialty="oral surgery",
        years_experience=7,
        region="Midwest",
        is_verified=True,
    )
    db.add_all([admin, doc1, doc2])
    db.flush()

    case1_text = "lingual numbness, facial tingling, headaches"
    case1 = Case(
        org_id=org.id,
        author_id=doc1.id,
        title="Lingual numbness with headaches",
        symptoms="Lingual numbness, facial tingling, headaches",
        suspected_dx="trigeminal neuropathy",
        final_dx="trigeminal neuralgia",
        interventions="gabapentin, neurology referral",
        outcomes="symptoms improved over 3 weeks",
        embedding=embed_texts([case1_text])[0],
    )
    case2_text = "jaw pain, swelling, difficulty chewing"
    case2 = Case(
        org_id=org.id,
        author_id=doc2.id,
        title="Jaw pain post dental extraction",
        symptoms="Jaw pain, swelling, difficulty chewing",
        suspected_dx="infection",
        final_dx="dry socket",
        interventions="irrigation, antibiotics",
        outcomes="resolved in 5 days",
        embedding=embed_texts([case2_text])[0],
    )
    db.add_all([case1, case2])
    db.flush()

    tag_neuro = Tag(name="neuro", category="domain")
    tag_oral = Tag(name="oral", category="domain")
    tag_pain = Tag(name="pain", category="icd")
    db.add_all([tag_neuro, tag_oral, tag_pain])
    db.flush()
    db.add_all(
        [
            CaseTag(case_id=case1.id, tag_id=tag_neuro.id),
            CaseTag(case_id=case1.id, tag_id=tag_pain.id),
            CaseTag(case_id=case2.id, tag_id=tag_oral.id),
        ]
    )

    db.add(CaseValidation(case_id=case1.id, doctor_id=doc2.id))
    db.add(CaseValidation(case_id=case2.id, doctor_id=doc1.id))
    db.commit()
    db.close()
    print("Seeded demo data")


if __name__ == "__main__":
    seed()
