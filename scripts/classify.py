#!/usr/bin/env python3
"""
classify.py — Ontology-based certainty classifier

Reads extracted claims from data/extracted/YYYY-MM-DD/claims.json,
calls Claude to assign each claim a certainty level per the Cavela ontology,
applies source reliability floors, and writes the enriched claims back.

Usage:
    python scripts/classify.py [--date YYYY-MM-DD]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("classify")

# ── Constants ─────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
DATA_EXTRACTED = REPO_ROOT / "data" / "extracted"

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024

# Ontology mapping
ONTOLOGY = {
    1: "SPECULATION",
    2: "REPORTED",
    3: "PROPOSED",
    4: "ANNOUNCED",
    5: "EXECUTIVE_ORDER",
    6: "RULE_PUBLISHED",
    7: "LAW",
}

ONTOLOGY_REVERSE = {v: k for k, v in ONTOLOGY.items()}

# Source category floors
SOURCE_FLOORS = {
    "official_us_gov": 3,
    "international_body": 2,
    "news_wire": 1,
    "financial_press": 1,
}


# ── Classification prompt ─────────────────────────────────────────────────────

CLASSIFICATION_SYSTEM_PROMPT = """You are a trade policy epistemologist. You classify tariff claims by their certainty level using a fixed ontology.

ONTOLOGY:
Level 1 — SPECULATION: Analyst opinion, unnamed sources, "could", "might", "considering"
Level 2 — REPORTED: Named sources, news reports, "plans to", "expected to", "intends to"
Level 3 — PROPOSED: Official proposal, NPRM, public comment period opened, "proposed rule"
Level 4 — ANNOUNCED: Official announcement by administration/agency, press release, "announced"
Level 5 — EXECUTIVE_ORDER: Signed EO or Presidential Proclamation, "executive order", "proclamation"
Level 6 — RULE_PUBLISHED: Final rule published in Federal Register, "final rule", "effective [date]"
Level 7 — LAW: Act of Congress signed into law, "Public Law", "signed into law"

Classify based on:
1. The language in the claim text (signal phrases above)
2. The source type (official sources can't go below PROPOSED)
3. The specific action described

Return JSON with exactly these fields:
{
  "certainty_level": <integer 1-7>,
  "certainty_label": <one of: SPECULATION, REPORTED, PROPOSED, ANNOUNCED, EXECUTIVE_ORDER, RULE_PUBLISHED, LAW>,
  "certainty_rationale": "<one sentence explaining why this level was assigned>"
}"""


def classify_claim_with_claude(
    client: anthropic.Anthropic,
    claim: dict,
) -> tuple[int, str, str]:
    """
    Use Claude to classify a claim's certainty level.
    Returns (certainty_level, certainty_label, certainty_rationale).
    Falls back to heuristic classification on failure.
    """
    source_category = claim.get("pedigree", {}).get("source_category", "news_wire")

    user_message = f"""Classify this tariff claim:

Claim: {claim.get('claim_text', '')}
Source: {claim.get('source_name', 'Unknown')} ({source_category})
Source URL: {claim.get('source_url', '')}
Tariff action type: {claim.get('tariff_action', 'unknown')}

Return JSON with certainty_level (1-7), certainty_label, and certainty_rationale."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=CLASSIFICATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        response_text = response.content[0].text.strip()

        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)

        level = int(result.get("certainty_level", 1))
        label = result.get("certainty_label", "SPECULATION")
        rationale = result.get("certainty_rationale", "No rationale provided.")

        # Validate level
        if level not in ONTOLOGY:
            level = 1
            label = "SPECULATION"

        # Validate label matches level
        if label not in ONTOLOGY_REVERSE:
            label = ONTOLOGY.get(level, "SPECULATION")

        return level, label, rationale

    except (json.JSONDecodeError, anthropic.APIError, KeyError, ValueError) as e:
        logger.warning(f"Claude classification failed: {e}. Using heuristic.")
        return heuristic_classify(claim)


def heuristic_classify(claim: dict) -> tuple[int, str, str]:
    """
    Heuristic fallback classifier when Claude API is unavailable.
    Uses keyword matching on claim text.
    """
    text = claim.get("claim_text", "").lower()
    source_category = claim.get("pedigree", {}).get("source_category", "news_wire")

    # Level 7 signals
    if any(kw in text for kw in ["signed into law", "public law", "act of congress", "enacted"]):
        return 7, "LAW", "Claim references enacted legislation."

    # Level 6 signals
    if any(kw in text for kw in ["federal register", "final rule", "cfr", "code of federal regulations"]):
        return 6, "RULE_PUBLISHED", "Claim references a final rule published in the Federal Register."

    # Level 5 signals
    if any(kw in text for kw in ["executive order", "presidential proclamation", "eo ", "proclamation"]):
        return 5, "EXECUTIVE_ORDER", "Claim references a signed Executive Order or Presidential Proclamation."

    # Level 4 signals
    if any(kw in text for kw in ["announced", "press release", "official statement", "confirmed"]):
        return 4, "ANNOUNCED", "Claim describes an official announcement or press release."

    # Level 3 signals
    if any(kw in text for kw in ["proposed", "nprm", "public comment", "rulemaking", "notice of"]):
        return 3, "PROPOSED", "Claim describes a formal regulatory proposal or NPRM."

    # Level 2 signals
    if any(kw in text for kw in ["plans to", "expected to", "intends to", "will impose", "according to"]):
        return 2, "REPORTED", "Claim uses attributed reporting language suggesting planned action."

    # Default: SPECULATION
    level = 1
    label = "SPECULATION"
    rationale = "Claim uses speculative language with no official confirmation."

    # Apply floor based on source category
    floor = SOURCE_FLOORS.get(source_category, 1)
    if level < floor:
        level = floor
        label = ONTOLOGY[level]
        rationale = (
            f"Raised to {label} due to {source_category} source reliability floor."
        )

    return level, label, rationale


def apply_source_floor(
    level: int,
    label: str,
    rationale: str,
    source_category: str,
) -> tuple[int, str, str]:
    """
    Apply the source reliability floor.
    If the assigned level is below the floor, raise it to the floor.
    """
    floor = SOURCE_FLOORS.get(source_category, 1)
    if level < floor:
        original_label = label
        level = floor
        label = ONTOLOGY[floor]
        rationale = (
            f"Raised from {original_label} to {label}: "
            f"{source_category} sources have a reliability floor of {floor}."
        )
        logger.debug(f"Applied floor: {original_label} -> {label} ({source_category})")
    return level, label, rationale


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify tariff claim certainty levels")
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Date to process (YYYY-MM-DD), defaults to today UTC",
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Use heuristic classifier only (skip Claude API)",
    )
    args = parser.parse_args()

    claims_path = DATA_EXTRACTED / args.date / "claims.json"
    if not claims_path.exists():
        logger.error(f"Claims file not found: {claims_path}")
        logger.error("Run extract_claims.py first.")
        return 1

    with open(claims_path, "r") as f:
        claims = json.load(f)

    if not claims:
        logger.info("No claims to classify.")
        return 0

    logger.info(f"Classifying {len(claims)} claims for {args.date}")

    # Initialize Claude client (if using API)
    client = None
    if not args.no_api:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            env_path = Path.home() / ".env"
            if env_path.exists():
                with open(env_path) as f_env:
                    for line in f_env:
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break

        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
        else:
            logger.warning("ANTHROPIC_API_KEY not set. Falling back to heuristic classifier.")

    # Classify each claim
    classified_claims = []
    api_used = 0
    heuristic_used = 0

    for claim in claims:
        source_category = claim.get("pedigree", {}).get("source_category", "news_wire")

        try:
            if client:
                level, label, rationale = classify_claim_with_claude(client, claim)
                api_used += 1
            else:
                level, label, rationale = heuristic_classify(claim)
                heuristic_used += 1

            # Apply source floor
            level, label, rationale = apply_source_floor(
                level, label, rationale, source_category
            )

        except Exception as e:
            logger.warning(f"Classification failed for claim {claim.get('claim_id')}: {e}")
            level, label, rationale = heuristic_classify(claim)
            heuristic_used += 1

        # Update the claim
        claim["certainty_level"] = level
        claim["certainty_label"] = label
        claim["certainty_rationale"] = rationale
        claim["pedigree"]["certainty_level"] = level

        classified_claims.append(claim)

    logger.info(
        f"Classification complete: {api_used} via Claude API, "
        f"{heuristic_used} via heuristic"
    )

    # Write back
    with open(claims_path, "w") as f:
        json.dump(classified_claims, f, indent=2, default=str)
    logger.info(f"Updated {len(classified_claims)} claims in {claims_path}")

    # Log level distribution
    level_counts: dict[int, int] = {}
    for claim in classified_claims:
        lvl = claim.get("certainty_level", 0)
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    for lvl in sorted(level_counts):
        logger.info(f"  Level {lvl} ({ONTOLOGY.get(lvl, '?')}): {level_counts[lvl]} claims")

    return 0


if __name__ == "__main__":
    sys.exit(main())
