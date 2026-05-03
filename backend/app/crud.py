import json
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Case, CaseRevision, CaseTag, Tag, TagTypeEnum
from .security import normalize_tag_list
from .services.records import case_record_snapshot


def _normalize_tag_name(name: str) -> str:
    return name.strip().lower()


def get_or_create_tag(db: Session, name: str, tag_type: TagTypeEnum) -> Tag:
    normalized = _normalize_tag_name(name)
    tag = db.query(Tag).filter(Tag.name == normalized, Tag.tag_type == tag_type).first()
    if tag:
        return tag
    tag = Tag(name=normalized, tag_type=tag_type)
    db.add(tag)
    db.flush()
    return tag


def assign_tags(
    db: Session,
    case: Case,
    specialty_tags: str | None,
    free_tags: str | None,
    outcome_tags: str | None = None,
    intervention_tags: str | None = None,
) -> list[str]:
    db.query(CaseTag).filter(CaseTag.case_id == case.id).delete()
    tag_names = []
    mapping = [
        (specialty_tags, TagTypeEnum.specialty),
        (free_tags, TagTypeEnum.free),
        (outcome_tags, TagTypeEnum.outcome),
        (intervention_tags, TagTypeEnum.intervention),
    ]
    for raw_value, tag_type in mapping:
        for raw in normalize_tag_list(raw_value):
            tag = get_or_create_tag(db, raw, tag_type)
            db.add(CaseTag(case_id=case.id, tag_id=tag.id))
            tag_names.append(tag.name)
    return tag_names


def case_snapshot(case: Case, tag_names: list[str]) -> dict:
    return case_record_snapshot(case, tag_names)


def snapshot_diff(previous: dict | None, current: dict) -> dict:
    previous = previous or {}
    diff = {}
    for key, value in current.items():
        if previous.get(key) != value:
            diff[key] = {"before": previous.get(key), "after": value}
    return diff


def record_revision(db: Session, case: Case, editor_id: int, tag_names: list[str]) -> None:
    last = db.query(CaseRevision).filter(CaseRevision.case_id == case.id).order_by(CaseRevision.revision_num.desc()).first()
    revision_num = (last.revision_num if last else 0) + 1
    current_snapshot = case_snapshot(case, tag_names)
    previous_snapshot = json.loads(last.data_json) if last else {}
    revision = CaseRevision(
        case_id=case.id,
        editor_id=editor_id,
        revision_num=revision_num,
        data_json=json.dumps(current_snapshot),
        diff_json=json.dumps(snapshot_diff(previous_snapshot, current_snapshot)),
    )
    db.add(revision)


def create_case(
    db: Session,
    case: Case,
    specialty_tags: str | None,
    free_tags: str | None,
    outcome_tags: str | None = None,
    intervention_tags: str | None = None,
) -> list[str]:
    db.add(case)
    db.flush()
    tag_names = assign_tags(db, case, specialty_tags, free_tags, outcome_tags, intervention_tags)
    record_revision(db, case, case.author_id, tag_names)
    return tag_names


def update_case(
    db: Session,
    case: Case,
    editor_id: int,
    specialty_tags: str | None,
    free_tags: str | None,
    outcome_tags: str | None = None,
    intervention_tags: str | None = None,
) -> list[str]:
    case.updated_at = datetime.utcnow()
    db.add(case)
    db.flush()
    tag_names = assign_tags(db, case, specialty_tags, free_tags, outcome_tags, intervention_tags)
    record_revision(db, case, editor_id, tag_names)
    return tag_names
