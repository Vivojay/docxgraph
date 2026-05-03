from .services.pii import detect_pii_matches, validate_case_text_fields


def detect_pii(text: str) -> list[str]:
    return [match.label for match in detect_pii_matches(text)]


def normalize_tag_list(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    tags = [tag.strip().lower() for tag in raw_tags.split(",")]
    return [tag for tag in tags if tag]
