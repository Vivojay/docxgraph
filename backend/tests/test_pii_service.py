from backend.app.services.pii import detect_pii_matches, validate_case_text_fields


def test_detect_pii_matches_returns_labels_and_snippets():
    matches = detect_pii_matches("Patient name: John Smith call 555-123-4567")
    labels = {match.label for match in matches}
    assert "name" in labels
    assert "phone" in labels


def test_validate_case_text_fields_reports_field_names():
    issues = validate_case_text_fields(
        {
            "symptoms": "Fever for 2 days",
            "follow_up": "Reach at doctor@example.com",
        }
    )
    assert issues == [{"field": "follow_up", "label": "email"}]
