import re


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d{1,3})?[\s.-]?(\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4}")
ADDRESS_RE = re.compile(r"\b(address|street|st\.|road|rd\.|ave|avenue|lane|ln\.|zip|postal|city)\b", re.IGNORECASE)
NAME_RE = re.compile(r"\b(name|mr\.|mrs\.|ms\.|patient name)\b", re.IGNORECASE)


def validate_no_phi(text: str) -> list[str]:
    hits = []
    if not text:
        return hits
    if EMAIL_RE.search(text):
        hits.append("email")
    if PHONE_RE.search(text):
        hits.append("phone")
    if ADDRESS_RE.search(text):
        hits.append("address")
    if NAME_RE.search(text):
        hits.append("name")
    return hits
