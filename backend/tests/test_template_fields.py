from backend.app.case_types import CASE_TYPE_ED_NEURO, CASE_TYPE_IMMUNO
from backend.app.template_fields import (
    collect_template_fields,
    normalize_template_fields,
    parse_template_fields,
    serialize_template_fields,
    template_fields_text,
)


def test_ed_neuro_fields_roundtrip():
    fields = collect_template_fields(
        CASE_TYPE_ED_NEURO,
        {
            "ed_onset_time": "1h",
            "ed_last_known_well": "09:30",
            "ed_nihss": "5",
            "ed_transfer_avoided": "yes",
            "ed_consult_time_minutes": "12",
        },
    )
    assert fields["nihss"] == 5
    assert fields["transfer_avoided"] is True
    assert fields["consult_time_minutes"] == 12

    raw = serialize_template_fields(fields)
    parsed = parse_template_fields(raw)
    assert parsed["onset_time"] == "1h"


def test_immuno_fields_text():
    fields = collect_template_fields(
        CASE_TYPE_IMMUNO,
        {
            "im_therapy_regimen": "pembrolizumab",
            "im_cycle_number": "3",
            "im_irae_system": "gi",
            "im_icu_escalation": "no",
        },
    )
    text = template_fields_text(CASE_TYPE_IMMUNO, fields)
    assert "therapy regimen" in text
    assert "cycle number" in text


def test_normalize_template_fields():
    fields = normalize_template_fields(
        CASE_TYPE_ED_NEURO,
        {"nihss": "4", "transfer_avoided": "yes", "consult_time_minutes": "15"},
    )
    assert fields["nihss"] == 4
    assert fields["transfer_avoided"] is True
    assert fields["consult_time_minutes"] == 15
