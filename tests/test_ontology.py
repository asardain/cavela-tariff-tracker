"""
test_ontology.py — Tests for the ontology classifier

Tests that classify.py correctly assigns certainty levels based on
claim text, source type, and applies source reliability floors.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from classify import (
    ONTOLOGY,
    SOURCE_FLOORS,
    apply_source_floor,
    heuristic_classify,
)


class TestOntologyConstants:
    def test_ontology_has_seven_levels(self):
        assert len(ONTOLOGY) == 7

    def test_ontology_levels_are_1_to_7(self):
        assert set(ONTOLOGY.keys()) == {1, 2, 3, 4, 5, 6, 7}

    def test_ontology_labels(self):
        assert ONTOLOGY[1] == "SPECULATION"
        assert ONTOLOGY[2] == "REPORTED"
        assert ONTOLOGY[3] == "PROPOSED"
        assert ONTOLOGY[4] == "ANNOUNCED"
        assert ONTOLOGY[5] == "EXECUTIVE_ORDER"
        assert ONTOLOGY[6] == "RULE_PUBLISHED"
        assert ONTOLOGY[7] == "LAW"

    def test_source_floors_defined(self):
        assert "official_us_gov" in SOURCE_FLOORS
        assert "international_body" in SOURCE_FLOORS
        assert "news_wire" in SOURCE_FLOORS
        assert "financial_press" in SOURCE_FLOORS

    def test_official_us_gov_floor_is_3(self):
        assert SOURCE_FLOORS["official_us_gov"] == 3

    def test_international_body_floor_is_2(self):
        assert SOURCE_FLOORS["international_body"] == 2

    def test_news_wire_floor_is_1(self):
        assert SOURCE_FLOORS["news_wire"] == 1

    def test_financial_press_floor_is_1(self):
        assert SOURCE_FLOORS["financial_press"] == 1


class TestHeuristicClassifier:
    """Test the heuristic fallback classifier."""

    def _make_claim(self, claim_text: str, source_category: str = "news_wire") -> dict:
        return {
            "claim_text": claim_text,
            "source_name": "Test Source",
            "source_url": "https://example.com/article",
            "tariff_action": "new_tariff",
            "pedigree": {
                "source_category": source_category,
            },
        }

    def test_law_signal(self):
        claim = self._make_claim("Congress signed into law a new tariff act.")
        level, label, rationale = heuristic_classify(claim)
        assert level == 7
        assert label == "LAW"

    def test_public_law_signal(self):
        claim = self._make_claim("Public Law 118-001 was enacted imposing tariffs on EVs.")
        level, label, rationale = heuristic_classify(claim)
        assert level == 7
        assert label == "LAW"

    def test_federal_register_signal(self):
        claim = self._make_claim(
            "A final rule published in the Federal Register imposes 15% duties."
        )
        level, label, rationale = heuristic_classify(claim)
        assert level == 6
        assert label == "RULE_PUBLISHED"

    def test_executive_order_signal(self):
        claim = self._make_claim(
            "The President signed Executive Order 14099 imposing tariffs."
        )
        level, label, rationale = heuristic_classify(claim)
        assert level == 5
        assert label == "EXECUTIVE_ORDER"

    def test_announced_signal(self):
        claim = self._make_claim(
            "USTR announced a 25% tariff on Chinese electric vehicles."
        )
        level, label, rationale = heuristic_classify(claim)
        assert level == 4
        assert label == "ANNOUNCED"

    def test_proposed_signal(self):
        claim = self._make_claim(
            "Commerce published an NPRM proposing antidumping duties on solar panels."
        )
        level, label, rationale = heuristic_classify(claim)
        assert level == 3
        assert label == "PROPOSED"

    def test_reported_signal(self):
        claim = self._make_claim(
            "The administration plans to impose tariffs on Canadian lumber."
        )
        level, label, rationale = heuristic_classify(claim)
        assert level == 2
        assert label == "REPORTED"

    def test_speculation_signal(self):
        claim = self._make_claim(
            "Analysts say the administration could impose tariffs on European goods."
        )
        level, label, rationale = heuristic_classify(claim)
        assert level == 1
        assert label == "SPECULATION"

    def test_rationale_is_non_empty_string(self):
        claim = self._make_claim("Tariffs might be imposed on steel imports.")
        level, label, rationale = heuristic_classify(claim)
        assert isinstance(rationale, str)
        assert len(rationale) > 0

    def test_returns_tuple_of_three(self):
        claim = self._make_claim("Tariffs could increase next year.")
        result = heuristic_classify(claim)
        assert len(result) == 3
        level, label, rationale = result
        assert isinstance(level, int)
        assert isinstance(label, str)
        assert isinstance(rationale, str)


class TestSourceFloor:
    """Test that source reliability floors are applied correctly."""

    def test_floor_raises_level(self):
        # Level 1 from official_us_gov source should be raised to 3
        level, label, rationale = apply_source_floor(
            1, "SPECULATION", "Speculative claim.", "official_us_gov"
        )
        assert level == 3
        assert label == "PROPOSED"
        assert "floor" in rationale.lower() or "raised" in rationale.lower()

    def test_floor_does_not_lower_level(self):
        # Level 5 from news_wire should stay at 5 (floor is 1)
        level, label, rationale = apply_source_floor(
            5, "EXECUTIVE_ORDER", "Signed EO.", "news_wire"
        )
        assert level == 5
        assert label == "EXECUTIVE_ORDER"

    def test_floor_at_exact_floor_level(self):
        # Level 3 from official_us_gov should stay at 3 (exactly at floor)
        level, label, rationale = apply_source_floor(
            3, "PROPOSED", "Official proposal.", "official_us_gov"
        )
        assert level == 3
        assert label == "PROPOSED"

    def test_international_body_floor(self):
        # Level 1 from international_body should raise to 2
        level, label, rationale = apply_source_floor(
            1, "SPECULATION", "WTO speculation.", "international_body"
        )
        assert level == 2
        assert label == "REPORTED"

    def test_unknown_source_category_floor_is_1(self):
        # Unknown source categories should default to floor=1 (no raise)
        level, label, rationale = apply_source_floor(
            1, "SPECULATION", "Some speculation.", "unknown_category"
        )
        assert level == 1
        assert label == "SPECULATION"

    def test_all_official_claims_at_least_proposed(self):
        """Any claim from an official US gov source must be at least Level 3."""
        for test_level in [1, 2, 3]:
            test_label = ONTOLOGY[test_level]
            level, label, _ = apply_source_floor(
                test_level, test_label, "Some rationale.", "official_us_gov"
            )
            assert level >= 3, f"Level {test_level} from official_us_gov should be raised to 3"


class TestOntologyEdgeCases:
    def test_level_boundary_minimum(self):
        """Level 1 is the minimum."""
        assert 1 in ONTOLOGY

    def test_level_boundary_maximum(self):
        """Level 7 is the maximum."""
        assert 7 in ONTOLOGY
        assert 8 not in ONTOLOGY

    def test_all_floor_values_are_valid_levels(self):
        """All floor values should be valid ontology levels."""
        for source_cat, floor in SOURCE_FLOORS.items():
            assert floor in ONTOLOGY, f"Floor {floor} for {source_cat} is not a valid level"
