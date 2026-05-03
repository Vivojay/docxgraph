from dataclasses import dataclass
import re


@dataclass
class PiiMatch:
    label: str
    snippet: str


PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(\+?\d{1,2}\s*)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}"),
    "address": re.compile(
        r"\b\d{1,5}\s+[A-Za-z0-9]+(\s+[A-Za-z0-9]+){0,4}\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl|Terrace|Ter)\b",
        re.IGNORECASE,
    ),
    "name": re.compile(r"\b(name|patient)[:\s]+[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "mrn": re.compile(r"\bMRN[:\s]*\d+\b", re.IGNORECASE),
}


def detect_pii_matches(text: str) -> list[PiiMatch]:
    matches: list[PiiMatch] = []
    if not text:
        return matches
    for label, pattern in PII_PATTERNS.items():
        found = pattern.search(text)
        if found:
            matches.append(PiiMatch(label=label, snippet=found.group(0)[:64]))
    return matches


def validate_case_text_fields(fields: dict[str, str | None]) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for field_name, value in fields.items():
        if not value:
            continue
        for match in detect_pii_matches(value):
            seen.setdefault(match.label, field_name)
    return [{"label": label, "field": field} for label, field in sorted(seen.items())]
