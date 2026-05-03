import json
import json

from .case_types import CASE_TYPE_ED_NEURO, CASE_TYPE_IMMUNO


def parse_template_fields(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def serialize_template_fields(fields: dict) -> str | None:
    if not fields:
        return None
    return json.dumps(fields)


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _to_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    return None


def _coerce_int(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except ValueError:
        return None


def _coerce_bool(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _to_bool(str(value))


def collect_template_fields(case_type: str, data: dict[str, str | None]) -> dict:
    if case_type == CASE_TYPE_ED_NEURO:
        return {
            "onset_time": data.get("ed_onset_time"),
            "last_known_well": data.get("ed_last_known_well"),
            "nihss": _to_int(data.get("ed_nihss")),
            "anticoagulation": data.get("ed_anticoagulation"),
            "imaging_available": data.get("ed_imaging_available"),
            "deficits": data.get("ed_deficits"),
            "tpa_given": data.get("ed_tpa_given"),
            "thrombectomy_candidate": data.get("ed_thrombectomy_candidate"),
            "transfer_needed": _to_bool(data.get("ed_transfer_needed")),
            "transfer_avoided": _to_bool(data.get("ed_transfer_avoided")),
            "consult_time_minutes": _to_int(data.get("ed_consult_time_minutes")),
            "routing_notes": data.get("ed_routing_notes"),
        }
    if case_type == CASE_TYPE_IMMUNO:
        return {
            "therapy_regimen": data.get("im_therapy_regimen"),
            "cycle_number": _to_int(data.get("im_cycle_number")),
            "days_since_infusion": _to_int(data.get("im_days_since_infusion")),
            "irae_system": data.get("im_irae_system"),
            "severity_grade": _to_int(data.get("im_severity_grade")),
            "steroid_response": data.get("im_steroid_response"),
            "icu_escalation": _to_bool(data.get("im_icu_escalation")),
            "consult_services": data.get("im_consult_services"),
            "held_therapy": data.get("im_held_therapy"),
            "rechallenged": data.get("im_rechallenged"),
        }
    return {}


def normalize_template_fields(case_type: str, template_fields: dict) -> dict:
    if not template_fields:
        return {}
    if case_type == CASE_TYPE_ED_NEURO:
        return {
            **template_fields,
            "nihss": _coerce_int(template_fields.get("nihss")),
            "consult_time_minutes": _coerce_int(template_fields.get("consult_time_minutes")),
            "transfer_needed": _coerce_bool(template_fields.get("transfer_needed")),
            "transfer_avoided": _coerce_bool(template_fields.get("transfer_avoided")),
        }
    if case_type == CASE_TYPE_IMMUNO:
        return {
            **template_fields,
            "cycle_number": _coerce_int(template_fields.get("cycle_number")),
            "days_since_infusion": _coerce_int(template_fields.get("days_since_infusion")),
            "severity_grade": _coerce_int(template_fields.get("severity_grade")),
            "icu_escalation": _coerce_bool(template_fields.get("icu_escalation")),
        }
    return template_fields


def template_fields_text(case_type: str, template_fields: dict) -> str:
    if not template_fields:
        return ""
    lines: list[str] = []
    if case_type == CASE_TYPE_ED_NEURO:
        label_map = {
            "onset_time": "onset time",
            "last_known_well": "last known well",
            "nihss": "nihss",
            "anticoagulation": "anticoagulation",
            "imaging_available": "imaging available",
            "deficits": "deficits",
            "tpa_given": "tpa given",
            "thrombectomy_candidate": "thrombectomy candidate",
            "transfer_needed": "transfer needed",
            "transfer_avoided": "transfer avoided",
            "consult_time_minutes": "consult time minutes",
            "routing_notes": "routing notes",
        }
    elif case_type == CASE_TYPE_IMMUNO:
        label_map = {
            "therapy_regimen": "therapy regimen",
            "cycle_number": "cycle number",
            "days_since_infusion": "days since infusion",
            "irae_system": "irAE system",
            "severity_grade": "severity grade",
            "steroid_response": "steroid response",
            "icu_escalation": "icu escalation",
            "consult_services": "consult services",
            "held_therapy": "therapy held",
            "rechallenged": "rechallenged",
        }
    else:
        label_map = {}

    for key, label in label_map.items():
        value = template_fields.get(key)
        if value is None or value == "":
            continue
        lines.append(f"{label}: {value}")
    return "\n".join(lines)
