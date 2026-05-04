from dataclasses import asdict, dataclass

from ..models import Case
from ..template_fields import parse_template_fields, template_fields_text


@dataclass
class CaseRecord:
    schema: str
    case_type: str
    specialty: str
    specialty_domain: str | None
    urgency: str | None
    symptoms: str
    demographics: str | None
    age_bucket: str | None
    constraints: str | None
    resource_setting: str | None
    suspected_dx: str | None
    final_dx: str | None
    interventions: str | None
    outcomes: str | None
    follow_up: str | None
    what_changed: str | None
    tags: list[str]
    template_fields: dict


def build_case_record(case: Case, tags: list[str]) -> CaseRecord:
    return CaseRecord(
        schema=case.record_schema,
        case_type=case.case_type,
        specialty=case.specialty,
        specialty_domain=case.specialty_domain,
        urgency=case.urgency,
        symptoms=case.symptoms,
        demographics=case.demographics,
        age_bucket=case.age_bucket,
        constraints=case.constraints,
        resource_setting=case.resource_setting,
        suspected_dx=case.suspected_dx,
        final_dx=case.final_dx,
        interventions=case.interventions,
        outcomes=case.outcomes,
        follow_up=case.follow_up,
        what_changed=case.what_changed,
        tags=tags,
        template_fields=parse_template_fields(case.template_fields),
    )


def case_record_text(case: Case, tags: list[str]) -> str:
    record = build_case_record(case, tags)
    parts = [
        record.schema,
        record.case_type,
        record.specialty,
        record.specialty_domain or "",
        record.urgency or "",
        record.symptoms,
        record.demographics or "",
        record.age_bucket or "",
        record.constraints or "",
        record.resource_setting or "",
        record.suspected_dx or "",
        record.final_dx or "",
        record.interventions or "",
        record.outcomes or "",
        record.follow_up or "",
        record.what_changed or "",
        template_fields_text(case.case_type, record.template_fields),
        " ".join(tags),
    ]
    return "\n".join(part for part in parts if part)


def case_record_snapshot(case: Case, tags: list[str]) -> dict:
    return asdict(build_case_record(case, tags))


def case_document_payload(case: Case, tags: list[str]) -> dict:
    record = build_case_record(case, tags)
    return {
        "id": case.id,
        "org_id": case.org_id,
        "author_id": case.author_id,
        "record_schema": case.record_schema,
        "case_type": case.case_type,
        "specialty": case.specialty,
        "specialty_domain": case.specialty_domain,
        "urgency": case.urgency,
        "symptoms": case.symptoms,
        "demographics": case.demographics,
        "age_bucket": case.age_bucket,
        "constraints": case.constraints,
        "resource_setting": case.resource_setting,
        "suspected_dx": case.suspected_dx,
        "final_dx": case.final_dx,
        "interventions": case.interventions,
        "outcomes": case.outcomes,
        "follow_up": case.follow_up,
        "what_changed": case.what_changed,
        "template_fields": record.template_fields,
        "tags": tags,
        "canonical_text": case_record_text(case, tags),
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }
