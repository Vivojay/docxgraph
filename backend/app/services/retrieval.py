import json
import math
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Case, CaseEmbedding, CaseSimilarityEdge, CaseTag, DoctorProfile, Endorsement, Tag, User
from .embeddings import get_embedder
from .firebase_store import list_case_documents, list_user_documents, upsert_case_document, upsert_user_document
from .keyword_search import bm25_lite_score, fuzzy_ratio, keyword_overlap_score, normalize_scores
from .qdrant_store import search_case_vectors, upsert_case_vector
from .records import case_document_payload, case_record_text


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def tag_overlap(tags_a: list[str], tags_b: list[str]) -> float:
    if not tags_a or not tags_b:
        return 0.0
    set_a = set(tags_a)
    set_b = set(tags_b)
    return len(set_a & set_b) / float(len(set_a | set_b))


def constraint_overlap(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    left_tokens = {token.strip().lower() for token in left.split() if token.strip()}
    right_tokens = {token.strip().lower() for token in right.split() if token.strip()}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / float(len(left_tokens | right_tokens))


def specialty_alignment(case: Case, specialty: str | None) -> float:
    if not specialty:
        return 0.0
    return 1.0 if specialty.lower() in case.specialty.lower() else 0.0


def hybrid_score(
    vector_sim: float,
    tag_sim: float,
    constraint_sim: float = 0.0,
    specialty_sim: float = 0.0,
) -> float:
    return (0.55 * vector_sim) + (0.2 * tag_sim) + (0.15 * constraint_sim) + (0.1 * specialty_sim)


def parse_vector(raw: str) -> list[float]:
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [float(x) for x in data]
    except Exception:
        return []
    return []


def explanation_lines(vector_sim: float, tag_sim: float, constraint_sim: float, specialty_sim: float) -> list[str]:
    lines = [f"semantic similarity {vector_sim:.2f}"]
    if tag_sim > 0:
        lines.append(f"tag overlap {tag_sim:.2f}")
    if constraint_sim > 0:
        lines.append(f"constraint overlap {constraint_sim:.2f}")
    if specialty_sim > 0:
        lines.append(f"specialty alignment {specialty_sim:.2f}")
    return lines


def keyword_explanation_lines(keyword_score: float, fuzzy_score: float, overlap_score: float) -> list[str]:
    lines = []
    if keyword_score > 0:
        lines.append(f"keyword relevance {keyword_score:.2f}")
    if fuzzy_score > 0:
        lines.append(f"fuzzy title/body match {fuzzy_score:.2f}")
    if overlap_score > 0:
        lines.append(f"query token overlap {overlap_score:.2f}")
    return lines


def upsert_case_embedding(db: Session, case_id: int, provider: str, vector: list[float]) -> None:
    payload = json.dumps(vector)
    existing = db.query(CaseEmbedding).filter(CaseEmbedding.case_id == case_id, CaseEmbedding.provider == provider).first()
    if existing:
        existing.vector = payload
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        db.flush()
        return
    db.add(CaseEmbedding(case_id=case_id, provider=provider, vector=payload))
    db.flush()


def get_case_tags_map(db: Session, case_ids: list[int]) -> dict[int, list[str]]:
    if not case_ids:
        return {}
    rows = (
        db.query(CaseTag.case_id, Tag.name)
        .join(Tag, Tag.id == CaseTag.tag_id)
        .filter(CaseTag.case_id.in_(case_ids))
        .all()
    )
    mapping: dict[int, list[str]] = {}
    for case_id, tag_name in rows:
        mapping.setdefault(case_id, []).append(tag_name)
    return mapping


def ensure_case_embedding(db: Session, case: Case, tag_names: list[str]):
    embedder = get_embedder()
    existing = db.query(CaseEmbedding).filter(CaseEmbedding.case_id == case.id, CaseEmbedding.provider == embedder.provider).first()
    if existing:
        vector = parse_vector(existing.vector)
        if vector:
            upsert_case_vector(case.id, vector, case_document_payload(case, tag_names))
        return vector
    text = case_record_text(case, tag_names)
    vector = embedder.embed([text])[0]
    upsert_case_embedding(db, case.id, embedder.provider, vector)
    upsert_case_vector(case.id, vector, case_document_payload(case, tag_names))
    return vector


def sync_case_search_document(db: Session, case: Case, tag_names: list[str]) -> None:
    payload = case_document_payload(case, tag_names)
    upsert_case_document(case.id, payload)
    vector = ensure_case_embedding(db, case, tag_names)
    upsert_case_vector(case.id, vector, payload)


def sync_user_search_document(user: User) -> None:
    payload = {
        "id": user.id,
        "org_id": user.org_id,
        "team_id": user.team_id,
        "email": user.email,
        "full_name": user.full_name,
        "hashed_password": user.hashed_password,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": bool(user.is_active),
        "specialty": user.profile.specialty if user.profile else None,
        "region": user.profile.region if user.profile else None,
        "verified": bool(user.profile.verified) if user.profile else False,
        "availability_status": user.profile.availability_status.value if user.profile and hasattr(user.profile.availability_status, "value") else None,
        "years_experience": user.profile.years_experience if user.profile else None,
        "proof_status": user.profile.proof_status if user.profile else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }
    upsert_user_document(user.id, payload)


def tag_rarity_score(db: Session, org_id: int, tags: list[str]) -> float:
    if not tags:
        return 0.0
    rows = (
        db.query(Tag.name, func.count(CaseTag.case_id))
        .join(CaseTag, CaseTag.tag_id == Tag.id)
        .join(Case, Case.id == CaseTag.case_id)
        .filter(Tag.name.in_(tags), Case.org_id == org_id)
        .group_by(Tag.name)
        .all()
    )
    counts = {name: count for name, count in rows}
    scores = []
    for name in tags:
        count = counts.get(name, 1)
        scores.append(1.0 / (1.0 + math.log1p(count)))
    return sum(scores) / len(scores)


def _document_constraint_overlap(constraint_text: str | None, document: dict) -> float:
    return constraint_overlap(constraint_text, document.get("constraints"))


def _document_specialty_alignment(document: dict, specialty: str | None) -> float:
    if not specialty:
        return 0.0
    doc_specialty = document.get("specialty") or ""
    return 1.0 if specialty.lower() in doc_specialty.lower() else 0.0


def _document_age_alignment(document: dict, age_bucket: str | None) -> float:
    if not age_bucket:
        return 0.0
    return 1.0 if (document.get("age_bucket") or "").lower() == age_bucket.lower() else 0.0


def _document_keyword_scores(query_text: str, document: dict) -> dict[str, float]:
    body = document.get("canonical_text") or ""
    keyword = bm25_lite_score(query_text, body)
    fuzzy = fuzzy_ratio(query_text, body)
    overlap = keyword_overlap_score(query_text, body)
    return {"keyword": keyword, "fuzzy": fuzzy, "overlap": overlap}


def _hybrid_document_score(
    vector_score: float,
    keyword_score: float,
    fuzzy_score: float,
    tag_sim: float,
    constraint_sim: float,
    specialty_sim: float,
    age_sim: float = 0.0,
) -> float:
    return (
        settings.hybrid_vector_weight * vector_score
        + settings.hybrid_keyword_weight * keyword_score
        + settings.hybrid_fuzzy_weight * fuzzy_score
        + settings.hybrid_tag_weight * tag_sim
        + settings.hybrid_constraint_weight * constraint_sim
        + settings.hybrid_specialty_weight * specialty_sim
        + (0.05 * age_sim)
    )


def _rank_documents(
    documents: list[dict],
    query_text: str,
    filter_specialty: str | None,
    filter_tags: list[str] | None,
    case_type: str | None,
    constraint_text: str | None,
    age_bucket: str | None,
    limit: int,
) -> list[dict]:
    filter_tags = [tag.lower() for tag in (filter_tags or [])]
    embedder = get_embedder()
    query_vector = embedder.embed([query_text])[0]
    qdrant_hits = search_case_vectors(query_vector, max(limit * 4, 20), org_id=documents[0].get("org_id") if documents else None)
    qdrant_scores = {int(hit["id"]): hit.get("vector_score", 0.0) for hit in qdrant_hits}

    prepared = []
    for document in documents:
        if case_type and document.get("case_type") != case_type:
            continue
        if filter_specialty and filter_specialty.lower() not in (document.get("specialty") or "").lower():
            continue
        if age_bucket and (document.get("age_bucket") or "").lower() != age_bucket.lower():
            continue
        doc_tags = [tag.lower() for tag in document.get("tags", [])]
        if filter_tags and not (set(filter_tags) & set(doc_tags)):
            continue
        keyword_scores = _document_keyword_scores(query_text, document)
        prepared.append(
            {
                "document": document,
                "doc_tags": doc_tags,
                "vector_raw": qdrant_scores.get(int(document["id"]), 0.0),
                "keyword_raw": keyword_scores["keyword"],
                "fuzzy_raw": max(keyword_scores["fuzzy"], keyword_scores["overlap"]),
                "constraint_sim": _document_constraint_overlap(constraint_text, document),
                "specialty_sim": _document_specialty_alignment(document, filter_specialty),
                "age_sim": _document_age_alignment(document, age_bucket),
                "tag_sim": tag_overlap(filter_tags, doc_tags),
            }
        )
    if not prepared:
        return []
    vector_scores = normalize_scores([item["vector_raw"] for item in prepared])
    keyword_scores = normalize_scores([item["keyword_raw"] for item in prepared])
    fuzzy_scores = normalize_scores([item["fuzzy_raw"] for item in prepared])
    ranked = []
    for idx, item in enumerate(prepared):
        vector_score = vector_scores[idx]
        keyword_score = keyword_scores[idx]
        fuzzy_score = fuzzy_scores[idx]
        score = _hybrid_document_score(
            vector_score=vector_score,
            keyword_score=keyword_score,
            fuzzy_score=fuzzy_score,
            tag_sim=item["tag_sim"],
            constraint_sim=item["constraint_sim"],
            specialty_sim=item["specialty_sim"],
            age_sim=item["age_sim"],
        )
        explanation = explanation_lines(vector_score, item["tag_sim"], item["constraint_sim"], item["specialty_sim"])
        explanation.extend(keyword_explanation_lines(keyword_score, fuzzy_score, item["fuzzy_raw"]))
        if item["age_sim"] > 0:
            explanation.append(f"age bucket alignment {item['age_sim']:.2f}")
        ranked.append(
            {
                "document": item["document"],
                "score": score,
                "confidence": min(0.99, max(0.1, score)),
                "score_breakdown": {
                    "vector": round(vector_score, 4),
                    "keyword": round(keyword_score, 4),
                    "fuzzy": round(fuzzy_score, 4),
                    "tags": round(item["tag_sim"], 4),
                    "constraints": round(item["constraint_sim"], 4),
                    "specialty": round(item["specialty_sim"], 4),
                    "age_bucket": round(item["age_sim"], 4),
                },
                "explanation": explanation,
            }
        )
    ranked.sort(key=lambda entry: entry["score"], reverse=True)
    return ranked[:limit]


def find_similar_cases(
    db: Session,
    org_id: int,
    query_text: str,
    filter_specialty: str | None = None,
    filter_tags: list[str] | None = None,
    case_type: str | None = None,
    constraint_text: str | None = None,
    age_bucket: str | None = None,
    limit: int = 5,
) -> list[dict]:
    firebase_documents = list_case_documents(org_id=org_id)
    if firebase_documents:
        ranked = _rank_documents(
            documents=firebase_documents,
            query_text=query_text,
            filter_specialty=filter_specialty,
            filter_tags=filter_tags,
            case_type=case_type,
            constraint_text=constraint_text,
            age_bucket=age_bucket,
            limit=limit,
        )
        case_ids = [int(item["document"]["id"]) for item in ranked]
        case_map = {case.id: case for case in db.query(Case).filter(Case.id.in_(case_ids)).all()}
        return [
            {
                "case": case_map[int(item["document"]["id"])],
                "score": item["score"],
                "confidence": item["confidence"],
                "score_breakdown": item["score_breakdown"],
                "explanation": item["explanation"],
            }
            for item in ranked
            if int(item["document"]["id"]) in case_map
        ]
    filter_tags = [tag.lower() for tag in (filter_tags or [])]
    query = db.query(Case).filter(Case.org_id == org_id)
    if filter_specialty:
        query = query.filter(Case.specialty.ilike(f"%{filter_specialty}%"))
    if case_type:
        query = query.filter(Case.case_type == case_type)
    if age_bucket:
        query = query.filter(Case.age_bucket == age_bucket)
    cases = query.all()
    case_ids = [case.id for case in cases]
    tags_map = get_case_tags_map(db, case_ids)
    embedder = get_embedder()
    query_vector = embedder.embed([query_text])[0]
    prepared = []
    for case in cases:
        case_tags = tags_map.get(case.id, [])
        if filter_tags and not (set(filter_tags) & set(case_tags)):
            continue
        case_vector = ensure_case_embedding(db, case, case_tags)
        vector_sim = cosine_similarity(query_vector, case_vector)
        keyword_scores = _document_keyword_scores(query_text, case_document_payload(case, case_tags))
        prepared.append(
            {
                "case": case,
                "case_tags": case_tags,
                "vector_raw": vector_sim,
                "keyword_raw": keyword_scores["keyword"],
                "fuzzy_raw": max(keyword_scores["fuzzy"], keyword_scores["overlap"]),
                "tag_sim": tag_overlap(filter_tags, case_tags),
                "constraint_sim": constraint_overlap(constraint_text, case.constraints),
                "specialty_sim": specialty_alignment(case, filter_specialty),
                "age_sim": 1.0 if age_bucket and (case.age_bucket or "").lower() == age_bucket.lower() else 0.0,
            }
        )
    if not prepared:
        return []
    vector_scores = normalize_scores([item["vector_raw"] for item in prepared])
    keyword_scores = normalize_scores([item["keyword_raw"] for item in prepared])
    fuzzy_scores = normalize_scores([item["fuzzy_raw"] for item in prepared])
    results = []
    for idx, item in enumerate(prepared):
        score = _hybrid_document_score(
            vector_score=vector_scores[idx],
            keyword_score=keyword_scores[idx],
            fuzzy_score=fuzzy_scores[idx],
            tag_sim=item["tag_sim"],
            constraint_sim=item["constraint_sim"],
            specialty_sim=item["specialty_sim"],
            age_sim=item["age_sim"],
        )
        breakdown = {
            "vector": round(vector_scores[idx], 4),
            "keyword": round(keyword_scores[idx], 4),
            "fuzzy": round(fuzzy_scores[idx], 4),
            "tags": round(item["tag_sim"], 4),
            "constraints": round(item["constraint_sim"], 4),
            "specialty": round(item["specialty_sim"], 4),
            "age_bucket": round(item["age_sim"], 4),
        }
        explanation = explanation_lines(vector_scores[idx], item["tag_sim"], item["constraint_sim"], item["specialty_sim"])
        explanation.extend(keyword_explanation_lines(keyword_scores[idx], fuzzy_scores[idx], item["fuzzy_raw"]))
        if item["age_sim"] > 0:
            explanation.append(f"age bucket alignment {item['age_sim']:.2f}")
        results.append(
            {
                "case": item["case"],
                "score": score,
                "confidence": min(0.99, max(0.1, score)),
                "score_breakdown": breakdown,
                "explanation": explanation,
            }
        )
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def similar_cases_for_case(db: Session, case: Case, tag_names: list[str], limit: int = 5) -> list[dict]:
    edges = (
        db.query(CaseSimilarityEdge, Case)
        .join(Case, Case.id == CaseSimilarityEdge.similar_case_id)
        .filter(CaseSimilarityEdge.case_id == case.id)
        .order_by(CaseSimilarityEdge.score.desc())
        .limit(limit)
        .all()
    )
    if edges:
        payload = []
        for edge, other_case in edges:
            payload.append(
                {
                    "case": other_case,
                    "score": edge.score,
                    "vector_sim": edge.vector_sim,
                    "tag_sim": edge.tag_sim,
                    "constraint_sim": edge.constraint_sim,
                    "confidence": min(0.99, max(0.1, edge.score)),
                    "score_breakdown": {
                        "vector": round(edge.vector_sim, 4),
                        "tags": round(edge.tag_sim, 4),
                        "constraints": round(edge.constraint_sim, 4),
                    },
                    "explanation": json.loads(edge.explanation_json) if edge.explanation_json else [],
                }
            )
        return payload
    return find_similar_cases(
        db,
        org_id=case.org_id,
        query_text=case_record_text(case, tag_names),
        filter_specialty=case.specialty,
        filter_tags=tag_names,
        case_type=case.case_type,
        constraint_text=case.constraints,
        age_bucket=case.age_bucket,
        limit=limit,
    )


def refresh_case_similarity_edges(db: Session, case: Case, tag_names: list[str], limit: int = 5) -> list[dict]:
    db.query(CaseSimilarityEdge).filter(CaseSimilarityEdge.case_id == case.id).delete()
    sync_case_search_document(db, case, tag_names)
    matches = find_similar_cases(
        db,
        org_id=case.org_id,
        query_text=case_record_text(case, tag_names),
        filter_specialty=case.specialty,
        filter_tags=tag_names,
        case_type=case.case_type,
        constraint_text=case.constraints,
        age_bucket=case.age_bucket,
        limit=limit + 1,
    )
    persisted = []
    for item in matches:
        other = item["case"]
        if other.id == case.id:
            continue
        vector_sim = item["score_breakdown"]["vector"]
        tag_sim = item["score_breakdown"]["tags"]
        constraint_sim = item["score_breakdown"]["constraints"]
        db.add(
            CaseSimilarityEdge(
                org_id=case.org_id,
                case_id=case.id,
                similar_case_id=other.id,
                score=item["score"],
                vector_sim=vector_sim,
                tag_sim=tag_sim,
                constraint_sim=constraint_sim,
                explanation_json=json.dumps(item["explanation"]),
            )
        )
        persisted.append(item)
    return persisted[:limit]


def match_experts(
    db: Session,
    org_id: int,
    summary: str,
    specialty: str | None = None,
    region: str | None = None,
    urgency: str | None = None,
    tags: list[str] | None = None,
    case_type: str | None = None,
    constraint_text: str | None = None,
    limit: int = 5,
) -> list[dict]:
    firebase_users = list_user_documents(org_id=org_id)
    similar_cases = find_similar_cases(
        db,
        org_id=org_id,
        query_text=summary,
        filter_specialty=specialty,
        filter_tags=tags,
        case_type=case_type,
        constraint_text=constraint_text,
        age_bucket=None,
        limit=25,
    )
    if not similar_cases:
        return []
    doctor_case_scores: dict[int, list[dict]] = {}
    for item in similar_cases:
        doctor_case_scores.setdefault(item["case"].author_id, []).append(item)

    doctor_ids = list(doctor_case_scores.keys())
    if firebase_users:
        firebase_user_map = {int(item["id"]): item for item in firebase_users if item.get("verified")}
    else:
        firebase_user_map = {}
    profiles = (
        db.query(User, DoctorProfile)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .filter(User.id.in_(doctor_ids), DoctorProfile.verified.is_(True))
        .all()
    )
    profile_map = {user.id: (user, profile) for user, profile in profiles}
    case_counts = dict(db.query(Case.author_id, func.count(Case.id)).filter(Case.author_id.in_(doctor_ids)).group_by(Case.author_id).all())
    endorsement_counts = dict(
        db.query(Case.author_id, func.count(Endorsement.id))
        .join(Endorsement, Endorsement.case_id == Case.id)
        .filter(Case.author_id.in_(doctor_ids))
        .group_by(Case.author_id)
        .all()
    )
    outcome_counts = dict(
        db.query(Case.author_id, func.count(Case.id))
        .filter(Case.author_id.in_(doctor_ids), Case.outcomes.isnot(None), Case.outcomes != "")
        .group_by(Case.author_id)
        .all()
    )
    rarity = tag_rarity_score(db, org_id, [tag.lower() for tag in (tags or [])])

    results = []
    for doctor_id, items in doctor_case_scores.items():
        if doctor_id not in profile_map:
            continue
        user, profile = profile_map[doctor_id]
        if firebase_user_map and doctor_id not in firebase_user_map:
            continue
        if specialty and profile.specialty and specialty.lower() not in profile.specialty.lower():
            continue
        if region and profile.region and region.lower() not in profile.region.lower():
            continue
        avg_similarity = sum(item["score"] for item in items) / len(items)
        cases_count = case_counts.get(doctor_id, 0)
        endorsements = endorsement_counts.get(doctor_id, 0)
        completeness = (outcome_counts.get(doctor_id, 0) / cases_count) if cases_count else 0.0
        expertise = math.log1p(cases_count) + (0.7 * math.log1p(endorsements)) + (0.5 * completeness) + (0.3 * rarity)
        availability_value = profile.availability_status.value if hasattr(profile.availability_status, "value") else str(profile.availability_status)
        availability_weight = {"available": 1.0, "busy": 0.7, "offline": 0.35}.get(availability_value, 0.6)
        urgency_weight = availability_weight if urgency and urgency.lower() in {"high", "urgent"} else 1.0
        final_score = (0.6 * avg_similarity) + (0.3 * expertise) + (0.1 * urgency_weight)
        explanation = [
            f"matched on similar cases avg {avg_similarity:.2f}",
            f"experience score {expertise:.2f}",
            f"peer validations {endorsements}",
            f"outcome completeness {completeness:.2f}",
            f"availability {availability_value}",
        ]
        if rarity > 0:
            explanation.append(f"rarity weighting {rarity:.2f}")
        if region and profile.region:
            explanation.append(f"region preference {profile.region}")
        results.append(
            {
                "doctor_id": user.id,
                "doctor_name": user.full_name or user.email,
                "specialty": profile.specialty,
                "region": profile.region,
                "availability": availability_value,
                "score": final_score,
                "score_breakdown": {
                    "similarity": round(avg_similarity, 4),
                    "expertise": round(expertise, 4),
                    "urgency_fit": round(urgency_weight, 4),
                    "rarity": round(rarity, 4),
                },
                "explanation": explanation,
            }
        )
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]
