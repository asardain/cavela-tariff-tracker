#!/usr/bin/env python3
"""
extract_claims.py — Claude-powered tariff claim extractor

Reads raw articles from data/raw/YYYY-MM-DD/, uses Claude API to extract
structured tariff claims, validates each claim against the JSON schema,
and saves valid claims to data/extracted/YYYY-MM-DD/claims.json.

Usage:
    python scripts/extract_claims.py [--date YYYY-MM-DD]
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
import jsonschema
import yaml

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("extract_claims")

# ── Constants ─────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_EXTRACTED = REPO_ROOT / "data" / "extracted"
SCHEMA_PATH = REPO_ROOT / "schema" / "claim.schema.json"

# Claude model for extraction (haiku for cost efficiency)
CLAUDE_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4096

# Maximum articles to process (cost control)
MAX_ARTICLES = 100


# ── Schema loading ─────────────────────────────────────────────────────────────


def load_claim_schema() -> dict:
    """Load the claim JSON schema."""
    with open(SCHEMA_PATH, "r") as f:
        return json.load(f)


# ── Claude extraction ─────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a trade policy analyst specializing in US tariff actions.
Your job is to extract factual tariff claims from news articles and government documents.

For each article, extract ONLY concrete factual claims about US tariff actions.
Do NOT extract opinions, predictions, or background context unless they constitute a claim.

A valid claim must describe a specific tariff action affecting specific products or countries.

For each claim, provide:
- claim_text: The claim as a complete, precise sentence
- subject: The product(s) or country/countries affected (be specific)
- tariff_action: One of: new_tariff, tariff_increase, tariff_removal, tariff_pause, investigation_opened, rule_proposed, other
- effective_date: ISO date YYYY-MM-DD if stated, null if not mentioned

Return a JSON object with a "claims" array. If no valid tariff claims exist, return {"claims": []}.

Example:
{
  "claims": [
    {
      "claim_text": "The USTR imposed a 25% tariff on steel imports from China effective March 15, 2025.",
      "subject": "Steel imports from China",
      "tariff_action": "new_tariff",
      "effective_date": "2025-03-15"
    }
  ]
}"""


def extract_claims_from_article(
    client: anthropic.Anthropic,
    article: dict,
) -> list[dict]:
    """
    Call Claude to extract tariff claims from a single article.
    Returns list of raw claim dicts (pre-validation, pre-enrichment).
    """
    title = article.get("title", "")
    content = article.get("content", "")
    source_name = article.get("source_name", "Unknown")
    source_url = article.get("url", "")

    if not content and not title:
        logger.warning(f"Article has no content: {source_url}")
        return []

    # Note: article content is untrusted. We rely on the structured system prompt
    # and JSON output requirement to mitigate prompt injection risk. Content is
    # also hard-capped at 3000 chars to limit injection surface.
    user_message = f"""Source: {source_name}
URL: {source_url}
Title: {title[:500]}

Content:
{content[:3000]}

Extract all tariff claims from this article."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        response_text = response.content[0].text.strip()

        # Parse the JSON response
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)
        claims = result.get("claims", [])

        logger.info(
            f"[{source_name}] Extracted {len(claims)} claims from: {source_url[:80]}"
        )
        return claims

    except json.JSONDecodeError as e:
        logger.warning(
            f"[{source_name}] JSON parse error for {source_url}: {e}"
        )
        return []
    except anthropic.APIError as e:
        logger.warning(
            f"[{source_name}] Claude API error for {source_url}: {e}"
        )
        return []
    except Exception as e:
        logger.error(
            f"[{source_name}] Unexpected error for {source_url}: {e}",
            exc_info=True,
        )
        return []


# ── Claim enrichment ──────────────────────────────────────────────────────────


def enrich_claim(raw_claim: dict, article: dict, extracted_date: str) -> dict:
    """
    Enrich a raw extracted claim with provenance and metadata fields.
    Returns a claim dict ready for schema validation.
    """
    published_date = article.get("published_date")
    if published_date is None:
        published_date = extracted_date

    # Normalize effective_date
    effective_date = raw_claim.get("effective_date")
    if effective_date and not isinstance(effective_date, str):
        effective_date = None
    if effective_date and len(effective_date) != 10:
        # Not YYYY-MM-DD format
        effective_date = None

    # Normalize tariff_action
    valid_actions = {
        "new_tariff", "tariff_increase", "tariff_removal",
        "tariff_pause", "investigation_opened", "rule_proposed", "other"
    }
    tariff_action = raw_claim.get("tariff_action", "other")
    if tariff_action not in valid_actions:
        tariff_action = "other"

    pedigree = {
        "source_name": article.get("source_name", "Unknown"),
        "source_category": article.get("source_category", "news_wire"),
        "source_url": article.get("url", ""),
        "published_date": published_date,
        "extracted_date": extracted_date,
        "certainty_level": 1,  # placeholder — classify.py will set this
    }

    return {
        "claim_id": str(uuid.uuid4()),
        "claim_text": raw_claim.get("claim_text", ""),
        "subject": raw_claim.get("subject", ""),
        "tariff_action": tariff_action,
        "effective_date": effective_date,
        "source_url": article.get("url", ""),
        "source_name": article.get("source_name", "Unknown"),
        "published_date": published_date,
        "extracted_date": extracted_date,
        "certainty_level": 1,  # placeholder
        "certainty_label": "SPECULATION",  # placeholder
        "certainty_rationale": "Pending classification.",  # placeholder
        "pedigree": pedigree,
        "feed_exclude": article.get("feed_exclude", False),
    }


# ── Schema validation ─────────────────────────────────────────────────────────


def validate_claim(claim: dict, schema: dict) -> tuple[bool, Optional[str]]:
    """
    Validate a claim dict against the JSON schema.
    Returns (is_valid, error_message).
    """
    try:
        jsonschema.validate(instance=claim, schema=schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, e.message
    except Exception as e:
        return False, str(e)


# ── Deduplication ─────────────────────────────────────────────────────────────


def deduplicate_claims(claims: list[dict]) -> list[dict]:
    """
    Deduplicate claims by (claim_text, source_url).
    Keeps the first occurrence.
    """
    seen = set()
    unique = []
    for claim in claims:
        key = (claim.get("claim_text", ""), claim.get("source_url", ""))
        if key not in seen:
            seen.add(key)
            unique.append(claim)
    return unique


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract tariff claims")
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Date to process (YYYY-MM-DD), defaults to today UTC",
    )
    args = parser.parse_args()

    # Locate raw article directory
    raw_dir = DATA_RAW / args.date
    if not raw_dir.exists():
        logger.error(f"Raw data directory does not exist: {raw_dir}")
        logger.error("Run fetch_sources.py first.")
        return 1

    # Set up output directory
    output_dir = DATA_EXTRACTED / args.date
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load schema for validation
    schema = load_claim_schema()

    # Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Try loading from ~/.env
        env_path = Path.home() / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set. Cannot run extraction.")
        return 1

    client = anthropic.Anthropic(api_key=api_key)

    # Load all raw articles
    article_files = sorted(raw_dir.glob("*.json"))
    # Skip manifest
    article_files = [f for f in article_files if f.name != "manifest.json"]

    if not article_files:
        logger.warning(f"No article files found in {raw_dir}")
        # Write empty claims file
        output_path = output_dir / "claims.json"
        with open(output_path, "w") as f:
            json.dump([], f, indent=2)
        return 0

    # Cap at MAX_ARTICLES
    if len(article_files) > MAX_ARTICLES:
        logger.warning(
            f"Found {len(article_files)} articles, capping at {MAX_ARTICLES}"
        )
        article_files = article_files[:MAX_ARTICLES]

    logger.info(f"Processing {len(article_files)} articles from {raw_dir}")

    extracted_date = datetime.now(timezone.utc).isoformat()
    all_claims: list[dict] = []
    failed_articles = 0
    invalid_claims = 0

    for article_file in article_files:
        try:
            with open(article_file, "r") as f:
                article = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {article_file}: {e}")
            failed_articles += 1
            continue

        # Extract raw claims from article via Claude
        raw_claims = extract_claims_from_article(client, article)

        for raw_claim in raw_claims:
            # Enrich with provenance
            enriched = enrich_claim(raw_claim, article, extracted_date)

            # Validate against schema
            is_valid, error = validate_claim(enriched, schema)
            if not is_valid:
                logger.warning(
                    f"Claim failed validation (dropped): {error} | "
                    f"claim_text={enriched.get('claim_text', '')[:60]}"
                )
                invalid_claims += 1
                continue

            all_claims.append(enriched)

    # Deduplicate
    unique_claims = deduplicate_claims(all_claims)
    logger.info(
        f"Total: {len(all_claims)} claims extracted, "
        f"{len(unique_claims)} after deduplication, "
        f"{invalid_claims} dropped (invalid), "
        f"{failed_articles} articles failed"
    )

    # Save claims
    output_path = output_dir / "claims.json"
    with open(output_path, "w") as f:
        json.dump(unique_claims, f, indent=2, default=str)
    logger.info(f"Saved {len(unique_claims)} claims to {output_path}")

    # Write extraction manifest
    manifest = {
        "date": args.date,
        "articles_processed": len(article_files),
        "articles_failed": failed_articles,
        "claims_extracted": len(all_claims),
        "claims_invalid": invalid_claims,
        "claims_saved": len(unique_claims),
        "generated_at": extracted_date,
        "model": CLAUDE_MODEL,
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Manifest written to {manifest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
