#!/usr/bin/env python3
"""
generate_daily.py — Daily tariff claim file generator

Combines extracted + classified claims into:
  - data/daily/YYYY-MM-DD.json — full structured claim array
  - data/daily/YYYY-MM-DD.md  — human-readable summary grouped by certainty level

Also prints a PR body to stdout for use by the GitHub Actions workflow.

Usage:
    python scripts/generate_daily.py [--date YYYY-MM-DD]
    python scripts/generate_daily.py --date 2025-03-15 --pr-body   # print PR body to stdout
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("generate_daily")

# ── Constants ─────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
DATA_EXTRACTED = REPO_ROOT / "data" / "extracted"
DATA_DAILY = REPO_ROOT / "data" / "daily"

ONTOLOGY = {
    1: "SPECULATION",
    2: "REPORTED",
    3: "PROPOSED",
    4: "ANNOUNCED",
    5: "EXECUTIVE_ORDER",
    6: "RULE_PUBLISHED",
    7: "LAW",
}

ONTOLOGY_DESCRIPTIONS = {
    1: "Analyst opinion, unnamed sources, speculative language",
    2: "Named sources, news reports, attributed but unconfirmed",
    3: "Official proposal, NPRM, public comment period",
    4: "Official announcement by agency or administration",
    5: "Signed Executive Order or Presidential Proclamation",
    6: "Final rule published in the Federal Register",
    7: "Act of Congress signed into law",
}

ACTION_LABELS = {
    "new_tariff": "New Tariff",
    "tariff_increase": "Tariff Increase",
    "tariff_removal": "Tariff Removal",
    "tariff_pause": "Tariff Pause",
    "investigation_opened": "Investigation Opened",
    "rule_proposed": "Rule Proposed",
    "other": "Other",
}


# ── Markdown generation ───────────────────────────────────────────────────────


def format_claim_md(claim: dict, index: int) -> str:
    """Format a single claim as a Markdown block."""
    action = ACTION_LABELS.get(claim.get("tariff_action", "other"), "Other")
    effective = claim.get("effective_date") or "Not specified"
    rationale = claim.get("certainty_rationale", "")
    source_name = claim.get("source_name", "Unknown")
    source_url = claim.get("source_url", "")

    lines = [
        f"**{index}. {claim.get('claim_text', 'No claim text')}**",
        "",
        f"- **Subject**: {claim.get('subject', 'Unknown')}",
        f"- **Action**: {action}",
        f"- **Effective Date**: {effective}",
        f"- **Source**: [{source_name}]({source_url})",
        f"- **Certainty**: Level {claim.get('certainty_level', '?')} — {claim.get('certainty_label', '?')}",
        f"- **Rationale**: {rationale}",
        f"- **Published**: {claim.get('published_date', 'Unknown')}",
        "",
    ]
    return "\n".join(lines)


def generate_markdown(date: str, claims: list[dict]) -> str:
    """Generate a human-readable Markdown summary for the day's claims."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Group by certainty level (highest first)
    by_level: dict[int, list[dict]] = defaultdict(list)
    for claim in claims:
        level = claim.get("certainty_level", 1)
        by_level[level].append(claim)

    lines = [
        f"# Tariff Claims — {date}",
        "",
        f"_Generated: {generated_at}_",
        "",
        f"**Total claims: {len(claims)}**",
        "",
    ]

    if not claims:
        lines += [
            "> No tariff claims found for this date.",
            "",
            "This may indicate a quiet news day or a fetch/extraction issue.",
            "Check the workflow logs for details.",
        ]
        return "\n".join(lines)

    # Summary table
    lines += [
        "## Summary by Certainty Level",
        "",
        "| Level | Label | Claims | Description |",
        "|-------|-------|--------|-------------|",
    ]

    for level in sorted(ONTOLOGY.keys(), reverse=True):
        count = len(by_level.get(level, []))
        if count > 0:
            label = ONTOLOGY[level]
            desc = ONTOLOGY_DESCRIPTIONS[level]
            lines.append(f"| {level} | {label} | {count} | {desc} |")

    lines.append("")

    # Claims grouped by level (highest certainty first)
    for level in sorted(by_level.keys(), reverse=True):
        level_claims = by_level[level]
        label = ONTOLOGY.get(level, f"Level {level}")
        desc = ONTOLOGY_DESCRIPTIONS.get(level, "")

        lines += [
            f"## Level {level} — {label}",
            "",
            f"_{desc}_",
            "",
        ]

        for i, claim in enumerate(level_claims, 1):
            lines.append(format_claim_md(claim, i))

    lines += [
        "---",
        "",
        f"_Cavela Tariff Tracker | {date} | [View full data](../../../data/daily/{date}.json)_",
    ]

    return "\n".join(lines)


def generate_pr_body(date: str, claims: list[dict]) -> str:
    """Generate the PR body for the daily tariff update PR."""
    by_level: dict[int, list[dict]] = defaultdict(list)
    for claim in claims:
        level = claim.get("certainty_level", 1)
        by_level[level].append(claim)

    # Top 3 most certain claims
    sorted_claims = sorted(claims, key=lambda c: c.get("certainty_level", 0), reverse=True)
    top_3 = sorted_claims[:3]

    lines = [
        f"## Tariff Update: {date}",
        "",
        f"**{len(claims)} new claim{'s' if len(claims) != 1 else ''} found**",
        "",
        "### Breakdown by Certainty Level",
        "",
    ]

    if claims:
        for level in sorted(ONTOLOGY.keys(), reverse=True):
            count = len(by_level.get(level, []))
            if count > 0:
                label = ONTOLOGY[level]
                lines.append(f"- **Level {level} ({label})**: {count} claim{'s' if count != 1 else ''}")
    else:
        lines.append("_No claims found._")

    lines += ["", "### Top 3 Most Certain Claims", ""]

    if top_3:
        for i, claim in enumerate(top_3, 1):
            level = claim.get("certainty_level", 1)
            label = claim.get("certainty_label", "SPECULATION")
            lines += [
                f"**{i}. [{label} — Level {level}]** {claim.get('claim_text', '')}",
                f"   - Source: {claim.get('source_name', 'Unknown')}",
                f"   - Action: {ACTION_LABELS.get(claim.get('tariff_action', 'other'), 'Other')}",
                "",
            ]
    else:
        lines.append("_No claims to show._")

    lines += [
        "",
        "---",
        "",
        f"- Data file: `data/daily/{date}.json`",
        f"- Summary: `data/daily/{date}.md`",
        "",
        "_Merge after reviewing claims for accuracy._",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily tariff summary files")
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Date to process (YYYY-MM-DD), defaults to today UTC",
    )
    parser.add_argument(
        "--pr-body",
        action="store_true",
        help="Print PR body to stdout instead of generating files",
    )
    args = parser.parse_args()

    # Load classified claims
    claims_path = DATA_EXTRACTED / args.date / "claims.json"
    if not claims_path.exists():
        logger.warning(f"Claims file not found: {claims_path}. Using empty claims.")
        claims = []
    else:
        with open(claims_path, "r") as f:
            claims = json.load(f)

    logger.info(f"Loaded {len(claims)} classified claims for {args.date}")

    if args.pr_body:
        # Just print PR body and exit
        print(generate_pr_body(args.date, claims))
        return 0

    # Ensure output directory exists
    DATA_DAILY.mkdir(parents=True, exist_ok=True)

    # Write JSON
    json_path = DATA_DAILY / f"{args.date}.json"
    with open(json_path, "w") as f:
        json.dump(claims, f, indent=2, default=str)
    logger.info(f"Wrote JSON: {json_path}")

    # Write Markdown
    md_path = DATA_DAILY / f"{args.date}.md"
    markdown = generate_markdown(args.date, claims)
    with open(md_path, "w") as f:
        f.write(markdown)
    logger.info(f"Wrote Markdown: {md_path}")

    # Print PR body to stdout for GitHub Actions to capture
    pr_body = generate_pr_body(args.date, claims)
    print(pr_body)

    logger.info(f"Daily generation complete for {args.date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
