import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["EMBEDDINGS_BACKEND"] = "hash"

from backend.app.db.base import Base
from backend.app.models.org import Org
from backend.app.models.user import User
from backend.app.models.case import Case, Tag, CaseTag
from backend.app.services.embeddings import embed_texts
from backend.app.services.retrieval import retrieve_similar_cases


def test_retrieve_similar_cases():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    org = Org(name="Test Org")
    db.add(org)
    db.flush()

    doctor = User(org_id=org.id, email="doc@example.com", hashed_password="x")
    db.add(doctor)
    db.flush()

    case1 = Case(
        org_id=org.id,
        author_id=doctor.id,
        title="Case A",
        symptoms="headache nausea",
        embedding=embed_texts(["headache nausea"])[0],
    )
    case2 = Case(
        org_id=org.id,
        author_id=doctor.id,
        title="Case B",
        symptoms="knee pain swelling",
        embedding=embed_texts(["knee pain swelling"])[0],
    )
    db.add_all([case1, case2])
    db.flush()

    tag = Tag(name="neuro", category="domain")
    db.add(tag)
    db.flush()
    db.add(CaseTag(case_id=case1.id, tag_id=tag.id))
    db.commit()

    results = retrieve_similar_cases(
        db,
        org_id=org.id,
        query="headache",
        tags=["neuro"],
        top_k=2,
    )
    assert len(results) == 1
    assert results[0]["case_id"] == case1.id
