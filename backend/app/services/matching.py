from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.app.models.user import User
from backend.app.models.case import Case, CaseValidation
from backend.app.services.embeddings import embed_texts
from backend.app.services.retrieval import cosine_similarity, build_case_text


def compute_doctor_expertise(db: Session, doctor_id: int) -> float:
    cases_count = db.execute(
        select(func.count()).select_from(Case).where(Case.author_id == doctor_id)
    ).scalar_one()
    validations_count = db.execute(
        select(func.count())
        .select_from(CaseValidation)
        .join(Case, Case.id == CaseValidation.case_id)
        .where(Case.author_id == doctor_id)
    ).scalar_one()
    return float(cases_count + validations_count * 1.5)


def count_peer_validations(db: Session, doctor_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(CaseValidation)
        .join(Case, Case.id == CaseValidation.case_id)
        .where(Case.author_id == doctor_id)
    ).scalar_one()


def match_experts(
    db: Session,
    org_id: int,
    case_summary: str,
    specialty: str | None = None,
    region: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    query_vec = embed_texts([case_summary])[0]
    total_cases = db.execute(select(func.count()).select_from(Case).where(Case.org_id == org_id)).scalar_one()
    rarity_score = round(1.0 / (1.0 + total_cases), 4)
    stmt = select(User).where(User.org_id == org_id, User.role == "doctor")
    if specialty:
        stmt = stmt.where(User.specialty == specialty)
    if region:
        stmt = stmt.where(User.region == region)
    doctors = db.execute(stmt).scalars().all()
    if not doctors:
        return []

    expertise_scores = {doc.id: compute_doctor_expertise(db, doc.id) for doc in doctors}
    max_expertise = max(expertise_scores.values()) or 1.0

    results = []
    for doc in doctors:
        cases = db.execute(select(Case).where(Case.author_id == doc.id)).scalars().all()
        best_similarity = 0.0
        for case in cases:
            if case.embedding:
                similarity = cosine_similarity(query_vec, case.embedding)
            else:
                similarity = cosine_similarity(
                    embed_texts([build_case_text(case)])[0], query_vec
                )
            if similarity > best_similarity:
                best_similarity = similarity
        expertise = expertise_scores[doc.id] / max_expertise
        availability = 1.0 if doc.is_available else 0.2
        score = round((0.7 * best_similarity) + (0.2 * expertise) + (0.1 * availability), 4)
        peer_validations = count_peer_validations(db, doc.id)
        explanation = (
            f"matched on symptoms/outcome similarity {best_similarity:.2f}, "
            f"rarity score {rarity_score:.2f}, "
            f"peer validations {peer_validations:.1f}, availability {availability:.2f}"
        )
        results.append(
            {
                "doctor_id": doc.id,
                "email": doc.email,
                "specialty": doc.specialty,
                "region": doc.region,
                "score": score,
                "explanation": explanation,
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]
