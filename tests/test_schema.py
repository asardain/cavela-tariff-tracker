"""
test_schema.py — Tests for claim JSON schema validation

Validates that valid claims pass and invalid claims fail schema validation.
"""

import json
import uuid
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "claim.schema.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def valid_claim():
    """A minimal valid claim."""
    now = "2025-03-15T09:00:00+00:00"
    return {
        "claim_id": str(uuid.uuid4()),
        "claim_text": "The USTR announced a 25% tariff on steel imports from China effective April 1, 2025.",
        "subject": "Steel imports from China",
        "tariff_action": "new_tariff",
        "effective_date": "2025-04-01",
        "source_url": "https://ustr.gov/press-release/12345",
        "source_name": "USTR",
        "published_date": now,
        "extracted_date": now,
        "certainty_level": 4,
        "certainty_label": "ANNOUNCED",
        "certainty_rationale": "Official USTR press release constitutes a formal announcement.",
        "pedigree": {
            "source_name": "USTR",
            "source_category": "official_us_gov",
            "source_url": "https://ustr.gov/press-release/12345",
            "published_date": now,
            "extracted_date": now,
            "certainty_level": 4,
        },
    }


def validate(instance, schema):
    """Helper: validate and return (is_valid, error)."""
    try:
        jsonschema.validate(instance=instance, schema=schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, e.message


class TestValidClaims:
    def test_valid_claim_passes(self, schema, valid_claim):
        is_valid, error = validate(valid_claim, schema)
        assert is_valid, f"Valid claim failed validation: {error}"

    def test_null_effective_date_is_valid(self, schema, valid_claim):
        valid_claim["effective_date"] = None
        is_valid, error = validate(valid_claim, schema)
        assert is_valid, f"null effective_date should be valid: {error}"

    def test_all_tariff_actions_valid(self, schema, valid_claim):
        actions = [
            "new_tariff", "tariff_increase", "tariff_removal",
            "tariff_pause", "investigation_opened", "rule_proposed", "other"
        ]
        for action in actions:
            valid_claim["tariff_action"] = action
            is_valid, error = validate(valid_claim, schema)
            assert is_valid, f"tariff_action '{action}' should be valid: {error}"

    def test_all_certainty_labels_valid(self, schema, valid_claim):
        labels_and_levels = [
            (1, "SPECULATION"),
            (2, "REPORTED"),
            (3, "PROPOSED"),
            (4, "ANNOUNCED"),
            (5, "EXECUTIVE_ORDER"),
            (6, "RULE_PUBLISHED"),
            (7, "LAW"),
        ]
        for level, label in labels_and_levels:
            valid_claim["certainty_level"] = level
            valid_claim["certainty_label"] = label
            valid_claim["pedigree"]["certainty_level"] = level
            is_valid, error = validate(valid_claim, schema)
            assert is_valid, f"Level {level}/{label} should be valid: {error}"

    def test_all_source_categories_valid(self, schema, valid_claim):
        categories = [
            "official_us_gov", "international_body", "news_wire", "financial_press"
        ]
        for cat in categories:
            valid_claim["pedigree"]["source_category"] = cat
            is_valid, error = validate(valid_claim, schema)
            assert is_valid, f"source_category '{cat}' should be valid: {error}"


class TestInvalidClaims:
    def test_missing_required_field(self, schema, valid_claim):
        del valid_claim["claim_text"]
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "Missing claim_text should fail"

    def test_invalid_tariff_action(self, schema, valid_claim):
        valid_claim["tariff_action"] = "ban"
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "Invalid tariff_action should fail"

    def test_certainty_level_too_low(self, schema, valid_claim):
        valid_claim["certainty_level"] = 0
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "certainty_level 0 should fail"

    def test_certainty_level_too_high(self, schema, valid_claim):
        valid_claim["certainty_level"] = 8
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "certainty_level 8 should fail"

    def test_invalid_certainty_label(self, schema, valid_claim):
        valid_claim["certainty_label"] = "CERTAIN"
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "Invalid certainty_label should fail"

    def test_invalid_effective_date_format(self, schema, valid_claim):
        valid_claim["effective_date"] = "March 15, 2025"
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "Non-ISO effective_date should fail"

    def test_claim_text_too_short(self, schema, valid_claim):
        valid_claim["claim_text"] = "Too short"
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "claim_text under 10 chars should fail"

    def test_missing_pedigree(self, schema, valid_claim):
        del valid_claim["pedigree"]
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "Missing pedigree should fail"

    def test_pedigree_invalid_source_category(self, schema, valid_claim):
        valid_claim["pedigree"]["source_category"] = "social_media"
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "Invalid pedigree source_category should fail"

    def test_additional_properties_rejected(self, schema, valid_claim):
        valid_claim["extra_field"] = "unexpected"
        is_valid, _ = validate(valid_claim, schema)
        assert not is_valid, "Additional properties should fail (additionalProperties: false)"
