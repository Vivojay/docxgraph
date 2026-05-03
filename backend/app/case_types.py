CASE_TYPE_GENERAL = "general"
CASE_TYPE_ED_NEURO = "ed_neuro"
CASE_TYPE_IMMUNO = "immuno_toxicity"

CASE_TYPE_LABELS = {
    CASE_TYPE_GENERAL: "General micro-case",
    CASE_TYPE_ED_NEURO: "ED neuro triage",
    CASE_TYPE_IMMUNO: "Immunotherapy toxicity",
}


def normalize_case_type(value: str | None) -> str:
    if not value:
        return CASE_TYPE_GENERAL
    value = value.strip().lower()
    if value in CASE_TYPE_LABELS:
        return value
    return CASE_TYPE_GENERAL
