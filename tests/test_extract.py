"""
test_extract.py — Tests for the claim extractor

Tests claim extraction logic with mocked Claude API responses.
No actual API calls are made.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from extract_claims import (
    deduplicate_claims,
    enrich_claim,
    validate_claim,
)


def make_schema():
    """Load the claim schema."""
    schema_path = REPO_ROOT / "schema" / "claim.schema.json"
    with open(schema_path) as f:
        return json.load(f)


def make_article(
    url="https://ustr.gov/press-release/12345",
    source_name="USTR",
    source_category="official_us_gov",
    published_date="2025-03-15T09:00:00+00:00",
):
    return {
        "url": url,
        "title": "USTR Announces New Tariffs on Steel",
        "content": "The USTR today announced 25% tariffs on steel imports from China.",
        "published_date": published_date,
        "source_name": source_name,
        "source_category": source_category,
        "source_url": f"https://{source_name.lower().replace(' ', '')}.gov",
        "reliability_floor": 3,
        "fetched_at": "2025-03-16T09:00:00+00:00",
    }


def make_raw_claim(
    claim_text="The USTR announced a 25% tariff on steel imports from China effective April 1, 2025.",
    subject="Steel imports from China",
    tariff_action="new_tariff",
    effective_date="2025-04-01",
):
    return {
        "claim_text": claim_text,
        "subject": subject,
        "tariff_action": tariff_action,
        "effective_date": effective_date,
    }


class TestEnrichClaim:
    """Test the claim enrichment function."""

    def test_enriched_claim_has_all_required_fields(self):
        raw = make_raw_claim()
        article = make_article()
        extracted_date = datetime.now(timezone.utc).isoformat()

        enriched = enrich_claim(raw, article, extracted_date)

        required_fields = [
            "claim_id", "claim_text", "subject", "tariff_action",
            "effective_date", "source_url", "source_name",
            "published_date", "extracted_date", "certainty_level",
            "certainty_label", "certainty_rationale", "pedigree",
        ]
        for field in required_fields:
            assert field in enriched, f"Missing field: {field}"

    def test_claim_id_is_uuid(self):
        raw = make_raw_claim()
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        # Should not raise
        parsed = uuid.UUID(enriched["claim_id"])
        assert str(parsed) == enriched["claim_id"]

    def test_invalid_tariff_action_normalized_to_other(self):
        raw = make_raw_claim(tariff_action="ban_imports")
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        assert enriched["tariff_action"] == "other"

    def test_valid_tariff_actions_preserved(self):
        valid_actions = [
            "new_tariff", "tariff_increase", "tariff_removal",
            "tariff_pause", "investigation_opened", "rule_proposed", "other"
        ]
        for action in valid_actions:
            raw = make_raw_claim(tariff_action=action)
            article = make_article()
            enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
            assert enriched["tariff_action"] == action

    def test_null_effective_date_preserved(self):
        raw = make_raw_claim(effective_date=None)
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        assert enriched["effective_date"] is None

    def test_invalid_effective_date_format_becomes_null(self):
        raw = make_raw_claim(effective_date="March 15, 2025")
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        assert enriched["effective_date"] is None

    def test_pedigree_populated_correctly(self):
        article = make_article(
            url="https://ustr.gov/test",
            source_name="USTR",
            source_category="official_us_gov",
        )
        raw = make_raw_claim()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())

        pedigree = enriched["pedigree"]
        assert pedigree["source_name"] == "USTR"
        assert pedigree["source_category"] == "official_us_gov"
        assert pedigree["source_url"] == "https://ustr.gov/test"

    def test_published_date_falls_back_to_extracted(self):
        article = make_article(published_date=None)
        raw = make_raw_claim()
        extracted_date = "2025-03-16T09:00:00+00:00"
        enriched = enrich_claim(raw, article, extracted_date)
        assert enriched["published_date"] == extracted_date

    def test_placeholder_certainty_level(self):
        """Enriched claims should have placeholder certainty (classify.py sets the real one)."""
        raw = make_raw_claim()
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        assert enriched["certainty_level"] == 1  # placeholder
        assert enriched["certainty_label"] == "SPECULATION"  # placeholder


class TestValidateClaim:
    """Test schema validation for enriched claims."""

    def test_valid_claim_passes(self):
        raw = make_raw_claim()
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        schema = make_schema()
        is_valid, error = validate_claim(enriched, schema)
        assert is_valid, f"Valid enriched claim failed: {error}"

    def test_empty_claim_text_fails(self):
        raw = make_raw_claim(claim_text="")
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        schema = make_schema()
        is_valid, _ = validate_claim(enriched, schema)
        assert not is_valid

    def test_short_claim_text_fails(self):
        raw = make_raw_claim(claim_text="Too short")  # < 10 chars
        article = make_article()
        enriched = enrich_claim(raw, article, datetime.now(timezone.utc).isoformat())
        schema = make_schema()
        is_valid, _ = validate_claim(enriched, schema)
        assert not is_valid


class TestDeduplicateClaims:
    """Test claim deduplication."""

    def test_duplicate_claims_removed(self):
        now = datetime.now(timezone.utc).isoformat()
        claims = [
            {
                "claim_text": "25% tariff on steel from China",
                "source_url": "https://ustr.gov/1",
            },
            {
                "claim_text": "25% tariff on steel from China",  # same
                "source_url": "https://ustr.gov/1",  # same
            },
            {
                "claim_text": "10% tariff on aluminum from Canada",
                "source_url": "https://ustr.gov/2",
            },
        ]
        result = deduplicate_claims(claims)
        assert len(result) == 2

    def test_same_claim_different_source_kept(self):
        claims = [
            {
                "claim_text": "25% tariff on steel",
                "source_url": "https://reuters.com/1",
            },
            {
                "claim_text": "25% tariff on steel",
                "source_url": "https://bloomberg.com/1",  # different source
            },
        ]
        result = deduplicate_claims(claims)
        assert len(result) == 2

    def test_empty_list(self):
        assert deduplicate_claims([]) == []

    def test_preserves_first_occurrence(self):
        claims = [
            {"claim_text": "Claim A", "source_url": "https://example.com/1"},
            {"claim_text": "Claim A", "source_url": "https://example.com/1"},
        ]
        result = deduplicate_claims(claims)
        assert result[0]["claim_text"] == "Claim A"
        assert len(result) == 1


class TestClaudeExtractionMocked:
    """Test extract_claims_from_article with mocked Claude responses."""

    def _make_client_mock(self, response_text: str) -> MagicMock:
        """Create a mock Anthropic client that returns a specific response."""
        mock_client = MagicMock()
        mock_content = MagicMock()
        mock_content.text = response_text
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        return mock_client

    def test_valid_claude_response_returns_claims(self):
        from extract_claims import extract_claims_from_article

        response = json.dumps({
            "claims": [
                {
                    "claim_text": "The USTR imposed a 25% tariff on steel imports from China.",
                    "subject": "Steel imports from China",
                    "tariff_action": "new_tariff",
                    "effective_date": "2025-04-01",
                }
            ]
        })
        client = self._make_client_mock(response)
        article = make_article()

        claims = extract_claims_from_article(client, article)
        assert len(claims) == 1
        assert claims[0]["claim_text"] == "The USTR imposed a 25% tariff on steel imports from China."

    def test_empty_claims_response(self):
        from extract_claims import extract_claims_from_article

        response = json.dumps({"claims": []})
        client = self._make_client_mock(response)
        article = make_article()

        claims = extract_claims_from_article(client, article)
        assert claims == []

    def test_markdown_wrapped_json_parsed(self):
        from extract_claims import extract_claims_from_article

        response = '```json\n{"claims": [{"claim_text": "Test tariff claim here.", "subject": "Steel", "tariff_action": "new_tariff", "effective_date": null}]}\n```'
        client = self._make_client_mock(response)
        article = make_article()

        claims = extract_claims_from_article(client, article)
        assert len(claims) == 1

    def test_malformed_json_returns_empty(self):
        from extract_claims import extract_claims_from_article

        client = self._make_client_mock("This is not JSON at all {{{")
        article = make_article()

        claims = extract_claims_from_article(client, article)
        assert claims == []

    def test_api_error_returns_empty(self):
        from extract_claims import extract_claims_from_article
        import anthropic

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="Rate limit exceeded",
            request=MagicMock(),
            body={}
        )
        article = make_article()

        claims = extract_claims_from_article(mock_client, article)
        assert claims == []

    def test_empty_article_returns_empty(self):
        from extract_claims import extract_claims_from_article

        client = self._make_client_mock('{"claims": []}')
        article = {"url": "https://example.com", "title": "", "content": ""}

        claims = extract_claims_from_article(client, article)
        assert claims == []

    def test_multiple_claims_returned(self):
        from extract_claims import extract_claims_from_article

        response = json.dumps({
            "claims": [
                {
                    "claim_text": "The US imposed a 25% tariff on Chinese steel.",
                    "subject": "Chinese steel",
                    "tariff_action": "new_tariff",
                    "effective_date": "2025-04-01",
                },
                {
                    "claim_text": "A 10% tariff on aluminum from Canada was announced.",
                    "subject": "Canadian aluminum",
                    "tariff_action": "new_tariff",
                    "effective_date": None,
                },
            ]
        })
        client = self._make_client_mock(response)
        article = make_article()

        claims = extract_claims_from_article(client, article)
        assert len(claims) == 2
