from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.api.deps import get_db, get_current_user
from backend.app.models.case import Case, CaseRevision, Tag, CaseTag, CaseValidation, CaseViewLog
from backend.app.schemas.case import CaseCreate, CaseOut, CaseSearchRequest, CaseSearchResult, CaseUpdate
from backend.app.services.embeddings import embed_texts
from backend.app.services.retrieval import retrieve_similar_cases, update_case_edges
from backend.app.services.validators import validate_no_phi
from backend.app.services.rate_limit import can_validate_case

router = APIRouter(prefix="/cases", tags=["cases"])


def _ensure_no_phi(payload: CaseCreate | CaseUpdate) -> None:
    fields = [
        payload.title,
        payload.demographics or "",
        payload.symptoms,
        payload.constraints or "",
        payload.suspected_dx or "",
        payload.final_dx or "",
        payload.interventions or "",
        payload.outcomes or "",
        payload.what_differently or "",
    ]
    hits = []
    for field in fields:
        hits.extend(validate_no_phi(field))
    if hits:
        raise HTTPException(
            status_code=400,
            detail=f"Potential identifiers detected: {', '.join(sorted(set(hits)))}",
        )


def _upsert_tags(db: Session, case_id: int, domain_tags: list[str], icd_tags: list[str]) -> None:
    db.query(CaseTag).where(CaseTag.case_id == case_id).delete()
    for name in domain_tags:
        tag = db.execute(
            select(Tag).where(Tag.name == name, Tag.category == "domain")
        ).scalar_one_or_none()
        if not tag:
            tag = Tag(name=name, category="domain")
            db.add(tag)
            db.flush()
        db.add(CaseTag(case_id=case_id, tag_id=tag.id))
    for name in icd_tags:
        tag = db.execute(
            select(Tag).where(Tag.name == name, Tag.category == "icd")
        ).scalar_one_or_none()
        if not tag:
            tag = Tag(name=name, category="icd")
            db.add(tag)
            db.flush()
        db.add(CaseTag(case_id=case_id, tag_id=tag.id))


@router.post("", response_model=CaseOut)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _ensure_no_phi(payload)
    text = "\n".join(
        [
            payload.title,
            payload.demographics or "",
            payload.symptoms,
            payload.constraints or "",
            payload.suspected_dx or "",
            payload.final_dx or "",
            payload.interventions or "",
            payload.outcomes or "",
            payload.what_differently or "",
        ]
    )
    embedding = embed_texts([text])[0]
    case = Case(
        org_id=user.org_id,
        author_id=user.id,
        title=payload.title,
        demographics=payload.demographics,
        symptoms=payload.symptoms,
        constraints=payload.constraints,
        suspected_dx=payload.suspected_dx,
        final_dx=payload.final_dx,
        interventions=payload.interventions,
        outcomes=payload.outcomes,
        what_differently=payload.what_differently,
        embedding=embedding,
    )
    db.add(case)
    db.flush()
    _upsert_tags(db, case.id, payload.domain_tags, payload.icd_tags)
    revision = CaseRevision(
        case_id=case.id,
        version=1,
        editor_id=user.id,
        snapshot_json=payload.model_dump(),
    )
    db.add(revision)
    update_case_edges(db, case)
    db.commit()
    db.refresh(case)
    return CaseOut(
        id=case.id,
        org_id=case.org_id,
        author_id=case.author_id,
        title=case.title,
        demographics=case.demographics,
        symptoms=case.symptoms,
        constraints=case.constraints,
        suspected_dx=case.suspected_dx,
        final_dx=case.final_dx,
        interventions=case.interventions,
        outcomes=case.outcomes,
        what_differently=case.what_differently,
        tags=payload.domain_tags + payload.icd_tags,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    case = db.get(Case, case_id)
    if not case or case.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    log = CaseViewLog(case_id=case.id, viewer_id=user.id, org_id=user.org_id)
    db.add(log)
    db.commit()
    tags = [ct.tag.name for ct in case.tags]
    return CaseOut(
        id=case.id,
        org_id=case.org_id,
        author_id=case.author_id,
        title=case.title,
        demographics=case.demographics,
        symptoms=case.symptoms,
        constraints=case.constraints,
        suspected_dx=case.suspected_dx,
        final_dx=case.final_dx,
        interventions=case.interventions,
        outcomes=case.outcomes,
        what_differently=case.what_differently,
        tags=tags,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.put("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: int,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    case = db.get(Case, case_id)
    if not case or case.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    _ensure_no_phi(payload)
    for field in [
        "title",
        "demographics",
        "symptoms",
        "constraints",
        "suspected_dx",
        "final_dx",
        "interventions",
        "outcomes",
        "what_differently",
    ]:
        setattr(case, field, getattr(payload, field))
    text = "\n".join(
        [
            payload.title,
            payload.demographics or "",
            payload.symptoms,
            payload.constraints or "",
            payload.suspected_dx or "",
            payload.final_dx or "",
            payload.interventions or "",
            payload.outcomes or "",
            payload.what_differently or "",
        ]
    )
    case.embedding = embed_texts([text])[0]
    _upsert_tags(db, case.id, payload.domain_tags, payload.icd_tags)
    latest_version = (
        db.execute(
            select(CaseRevision.version)
            .where(CaseRevision.case_id == case.id)
            .order_by(CaseRevision.version.desc())
        ).scalar_one_or_none()
        or 0
    )
    revision = CaseRevision(
        case_id=case.id,
        version=latest_version + 1,
        editor_id=user.id,
        snapshot_json=payload.model_dump(),
    )
    db.add(revision)
    update_case_edges(db, case)
    db.commit()
    db.refresh(case)
    tags = [ct.tag.name for ct in case.tags]
    return CaseOut(
        id=case.id,
        org_id=case.org_id,
        author_id=case.author_id,
        title=case.title,
        demographics=case.demographics,
        symptoms=case.symptoms,
        constraints=case.constraints,
        suspected_dx=case.suspected_dx,
        final_dx=case.final_dx,
        interventions=case.interventions,
        outcomes=case.outcomes,
        what_differently=case.what_differently,
        tags=tags,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("/search", response_model=list[CaseSearchResult])
def search_cases(
    payload: CaseSearchRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    results = retrieve_similar_cases(
        db,
        org_id=user.org_id,
        query=payload.query,
        specialty=payload.specialty,
        region=payload.region,
        tags=payload.tags,
        top_k=payload.top_k,
    )
    return results


@router.post("/{case_id}/validate")
def validate_case(
    case_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    case = db.get(Case, case_id)
    if not case or case.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Verification required")
    if case.author_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot validate own case")
    if not can_validate_case(db, user.id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    existing = db.execute(
        select(CaseValidation).where(
            CaseValidation.case_id == case_id, CaseValidation.doctor_id == user.id
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Already validated")
    validation = CaseValidation(case_id=case_id, doctor_id=user.id)
    db.add(validation)
    db.commit()
    return {"status": "ok"}
