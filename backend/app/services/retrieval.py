from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.case import Case, CaseEdge, CaseTag, Tag
from backend.app.models.user import User
from backend.app.services.embeddings import embed_texts


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    if not a_list or not b_list:
        return 0.0
    if len(a_list) != len(b_list):
        min_len = min(len(a_list), len(b_list))
        a_list = a_list[:min_len]
        b_list = b_list[:min_len]
    dot = sum(x * y for x, y in zip(a_list, b_list))
    norm_a = sum(x * x for x in a_list) ** 0.5
    norm_b = sum(x * x for x in b_list) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_case_text(case: Case) -> str:
    parts = [
        case.title,
        case.demographics or "",
        case.symptoms or "",
        case.constraints or "",
        case.suspected_dx or "",
        case.final_dx or "",
        case.interventions or "",
        case.outcomes or "",
        case.what_differently or "",
    ]
    return "\n".join(p for p in parts if p)


def retrieve_similar_cases(
    db: Session,
    org_id: int,
    query: str,
    specialty: str | None = None,
    region: str | None = None,
    tags: list[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    tags = tags or []
    query_vector = embed_texts([query])[0]

    stmt = select(Case).where(Case.org_id == org_id)
    cases = db.execute(stmt).scalars().all()

    results = []
    for case in cases:
        if not case.embedding:
            continue
        if specialty or region:
            author = db.get(User, case.author_id)
            if specialty and author and author.specialty != specialty:
                continue
            if region and author and author.region != region:
                continue
        case_tags = _get_case_tag_names(db, case.id)
        if tags and not set(tags).intersection(case_tags):
            continue
        score = cosine_similarity(query_vector, case.embedding)
        matched = []
        if tags:
            matched.extend(sorted(set(tags).intersection(case_tags)))
        results.append(
            {
                "case_id": case.id,
                "score": round(score, 4),
                "matched_on": matched,
                "title": case.title,
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def update_case_edges(db: Session, case: Case, top_k: int = 5) -> None:
    query_vector = case.embedding
    if not query_vector:
        return
    db.query(CaseEdge).where(CaseEdge.case_id == case.id).delete()
    stmt = select(Case).where(Case.org_id == case.org_id, Case.id != case.id)
    candidates = db.execute(stmt).scalars().all()
    scored = []
    for other in candidates:
        if not other.embedding:
            continue
        score = cosine_similarity(query_vector, other.embedding)
        scored.append((other, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    for other, score in scored[:top_k]:
        edge = CaseEdge(
            case_id=case.id,
            related_case_id=other.id,
            score=round(score, 4),
            explanation="auto-linked by similarity",
        )
        db.add(edge)


def _get_case_tag_names(db: Session, case_id: int) -> list[str]:
    stmt = (
        select(Tag.name)
        .join(CaseTag, CaseTag.tag_id == Tag.id)
        .where(CaseTag.case_id == case_id)
    )
    return [row[0] for row in db.execute(stmt).all()]
