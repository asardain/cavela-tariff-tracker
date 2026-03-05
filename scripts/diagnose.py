#!/usr/bin/env python3
"""
diagnose.py — Data quality explorer for the Cavela Tariff Tracker pipeline.

Reads data from data/daily/*.json, data/extracted/, and data/raw/ and provides
a rich diagnostic view: summary stats, certainty distributions, source breakdowns,
quality checks, per-date drill-down, and pipeline stage presence checks.

Usage:
    python scripts/diagnose.py                        # Full diagnostic report
    python scripts/diagnose.py --date 2025-03-15      # Drill down into one day
    python scripts/diagnose.py --check-only           # Quality issues only
    python scripts/diagnose.py --verbose              # Show extra detail
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
DATA_DAILY = REPO_ROOT / "data" / "daily"
DATA_EXTRACTED = REPO_ROOT / "data" / "extracted"
DATA_RAW = REPO_ROOT / "data" / "raw"

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

# ── Terminal formatting helpers ───────────────────────────────────────────────

WIDTH = 72


def hr(char="─"):
    print(char * WIDTH)


def header(title: str, char="═"):
    bar = char * WIDTH
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def section(title: str):
    print(f"\n  {'─' * (WIDTH - 4)}")
    print(f"  {title}")
    print(f"  {'─' * (WIDTH - 4)}")


def col(label: str, value, width: int = 30):
    return f"  {label:<{width}} {value}"


def table(rows: list[list], headers: list[str], col_widths: list[int]):
    """Print a simple aligned table."""
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_widths)
    divider = "  " + "  ".join("-" * w for w in col_widths)
    print(fmt.format(*headers))
    print(divider)
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


# ── Data loading ──────────────────────────────────────────────────────────────


def load_daily_files() -> dict[str, list[dict]]:
    """
    Load all daily JSON files from data/daily/.
    Returns dict mapping date string -> list of claims.
    """
    if not DATA_DAILY.exists():
        return {}

    result = {}
    for path in sorted(DATA_DAILY.glob("*.json")):
        date_str = path.stem  # filename without .json
        # Skip .gitkeep or non-date files
        if not _looks_like_date(date_str):
            continue
        try:
            with open(path, "r") as f:
                claims = json.load(f)
            if isinstance(claims, list):
                result[date_str] = claims
            else:
                result[date_str] = []
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [WARN] Could not load {path.name}: {e}")
            result[date_str] = []

    return result


def _looks_like_date(s: str) -> bool:
    """Check if string looks like YYYY-MM-DD."""
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ── Summary stats ─────────────────────────────────────────────────────────────


def print_summary(daily: dict[str, list[dict]]):
    header("SUMMARY STATISTICS")

    dates = sorted(daily.keys())
    total_claims = sum(len(claims) for claims in daily.values())

    if not dates:
        print(col("Daily files found:", 0))
        print(col("No data available.", ""))
        return

    avg = total_claims / len(dates) if dates else 0

    print(col("Daily files found:", len(dates)))
    print(col("Date range:", f"{dates[0]}  to  {dates[-1]}"))
    print(col("Total claims (all days):", total_claims))
    print(col("Avg claims per day:", f"{avg:.1f}"))
    print()

    # Per-day breakdown table
    section("Claims Per Day")
    rows = []
    for date in dates:
        n = len(daily[date])
        bar = "#" * min(n, 40)
        rows.append([date, n, bar])
    table(rows, ["Date", "Claims", ""], [12, 8, 42])


# ── Certainty distribution ────────────────────────────────────────────────────


def print_certainty_distribution(daily: dict[str, list[dict]]):
    header("CERTAINTY DISTRIBUTION")

    all_claims = [c for claims in daily.values() for c in claims]
    total = len(all_claims)

    if total == 0:
        print("  No claims to analyze.")
        return

    level_counts: dict[int, int] = defaultdict(int)
    for claim in all_claims:
        lvl = claim.get("certainty_level")
        if isinstance(lvl, int) and 1 <= lvl <= 7:
            level_counts[lvl] += 1
        else:
            level_counts[0] += 1  # unknown/invalid

    rows = []
    for lvl in sorted(level_counts.keys()):
        count = level_counts[lvl]
        pct = 100 * count / total if total else 0
        label = ONTOLOGY.get(lvl, "UNKNOWN/INVALID")
        bar = "#" * int(pct / 2)
        rows.append([lvl if lvl > 0 else "?", label, count, f"{pct:.1f}%", bar])

    table(rows, ["Level", "Label", "Count", "Pct", ""], [6, 18, 7, 7, 30])


# ── Source breakdown ──────────────────────────────────────────────────────────


def print_source_breakdown(daily: dict[str, list[dict]], verbose: bool):
    header("SOURCE BREAKDOWN")

    all_claims = [c for claims in daily.values() for c in claims]
    total = len(all_claims)

    if total == 0:
        print("  No claims to analyze.")
        return

    source_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)

    for claim in all_claims:
        source_name = claim.get("source_name") or "(unknown)"
        source_counts[source_name] += 1
        cat = claim.get("pedigree", {}).get("source_category") or "(none)"
        category_counts[cat] += 1

    section("By Source Name")
    rows = []
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        pct = 100 * count / total if total else 0
        rows.append([source[:38], count, f"{pct:.1f}%"])
    table(rows, ["Source", "Claims", "Pct"], [40, 8, 8])

    if verbose:
        section("By Source Category")
        rows = []
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            pct = 100 * count / total if total else 0
            rows.append([cat, count, f"{pct:.1f}%"])
        table(rows, ["Category", "Claims", "Pct"], [25, 8, 8])


# ── Quality checks ────────────────────────────────────────────────────────────


def collect_quality_issues(daily: dict[str, list[dict]]) -> list[dict]:
    """
    Run all quality checks across all loaded claims.
    Returns a list of issue dicts with keys: date, claim_id, check, detail.
    """
    issues = []
    seen_texts: dict[str, str] = {}  # claim_text -> first date seen

    for date, claims in sorted(daily.items()):
        for claim in claims:
            cid = claim.get("claim_id", "(no id)")

            # Missing claim_text
            ct = claim.get("claim_text")
            if not ct or not ct.strip():
                issues.append({
                    "date": date, "claim_id": cid,
                    "check": "missing_claim_text",
                    "detail": "claim_text is null or empty",
                })

            # Missing certainty_level
            lvl = claim.get("certainty_level")
            if lvl is None:
                issues.append({
                    "date": date, "claim_id": cid,
                    "check": "missing_certainty_level",
                    "detail": "certainty_level is null",
                })
            elif not (isinstance(lvl, int) and 1 <= lvl <= 7):
                issues.append({
                    "date": date, "claim_id": cid,
                    "check": "invalid_certainty_level",
                    "detail": f"certainty_level={lvl!r} is not in range 1-7",
                })

            # Missing source_url
            url = claim.get("source_url")
            if not url or not str(url).strip():
                issues.append({
                    "date": date, "claim_id": cid,
                    "check": "missing_source_url",
                    "detail": "source_url is null or empty",
                })

            # Missing effective_date (not an error by itself, but flagged)
            if claim.get("effective_date") is None:
                issues.append({
                    "date": date, "claim_id": cid,
                    "check": "no_effective_date",
                    "detail": "effective_date is null (not specified in source)",
                })

            # certainty_level / certainty_label mismatch
            label = claim.get("certainty_label")
            if lvl and label:
                expected_label = ONTOLOGY.get(lvl)
                if expected_label and label != expected_label:
                    issues.append({
                        "date": date, "claim_id": cid,
                        "check": "certainty_mismatch",
                        "detail": (
                            f"level={lvl} maps to {expected_label!r} "
                            f"but label={label!r}"
                        ),
                    })

            # Duplicate claim_text across days
            text_key = (ct or "").strip().lower()
            if text_key:
                if text_key in seen_texts:
                    first_date = seen_texts[text_key]
                    if first_date != date:
                        issues.append({
                            "date": date, "claim_id": cid,
                            "check": "duplicate_claim_text",
                            "detail": f"Same claim_text already seen on {first_date}",
                        })
                else:
                    seen_texts[text_key] = date

    return issues


def print_quality_checks(daily: dict[str, list[dict]], verbose: bool):
    header("CLAIM QUALITY CHECKS")

    if not daily:
        print("  No data to check.")
        return

    issues = collect_quality_issues(daily)

    # Count by check type
    by_check: dict[str, list[dict]] = defaultdict(list)
    for issue in issues:
        by_check[issue["check"]].append(issue)

    # Separate structural errors from informational flags
    structural_checks = [
        "missing_claim_text", "missing_certainty_level", "invalid_certainty_level",
        "missing_source_url", "certainty_mismatch", "duplicate_claim_text",
    ]
    informational_checks = ["no_effective_date"]

    total_errors = sum(
        len(by_check[c]) for c in structural_checks if c in by_check
    )
    total_info = sum(
        len(by_check[c]) for c in informational_checks if c in by_check
    )
    total_claims = sum(len(v) for v in daily.values())

    print(col("Total claims checked:", total_claims))
    print(col("Structural issues found:", total_errors))
    print(col("Informational flags:", total_info))

    if total_errors == 0:
        print("\n  No structural quality issues detected.")
    else:
        section("Structural Issues")
        for check in structural_checks:
            if check not in by_check:
                continue
            items = by_check[check]
            print(f"\n  [{check}] — {len(items)} occurrence(s)")
            if verbose:
                for issue in items[:20]:
                    cid_short = issue["claim_id"][:8] if issue["claim_id"] != "(no id)" else "no-id"
                    print(f"    {issue['date']}  {cid_short}...  {issue['detail']}")
                if len(items) > 20:
                    print(f"    ... and {len(items) - 20} more")
            else:
                # Show first 5
                for issue in items[:5]:
                    cid_short = issue["claim_id"][:8] if issue["claim_id"] != "(no id)" else "no-id"
                    print(f"    {issue['date']}  {cid_short}...  {issue['detail']}")
                if len(items) > 5:
                    print(f"    ... and {len(items) - 5} more (use --verbose to see all)")

    if total_info > 0:
        section("Informational Flags (not errors)")
        for check in informational_checks:
            if check not in by_check:
                continue
            items = by_check[check]
            print(f"\n  [{check}] — {len(items)} occurrence(s)")
            if verbose:
                # Show per-day breakdown instead of per-claim
                date_counts: dict[str, int] = defaultdict(int)
                for issue in items:
                    date_counts[issue["date"]] += 1
                for d, n in sorted(date_counts.items()):
                    print(f"    {d}: {n} claims with no effective_date")


# ── Date drill-down ───────────────────────────────────────────────────────────


def print_date_drilldown(date: str, daily: dict[str, list[dict]], verbose: bool):
    header(f"DATE DRILL-DOWN: {date}")

    claims = daily.get(date)
    if claims is None:
        print(f"  No daily file found for {date}.")
        print(f"  (Looked in {DATA_DAILY / (date + '.json')})")
        return

    print(col("Claims in daily file:", len(claims)))

    if not claims:
        print("  File exists but contains no claims.")
        return

    # Sort by certainty descending
    sorted_claims = sorted(claims, key=lambda c: c.get("certainty_level", 0), reverse=True)

    section(f"All {len(claims)} Claims (sorted by certainty, highest first)")
    print()
    print(f"  {'#':<4}  {'Cert':<5}  {'Label':<16}  {'Source':<20}  Claim Text")
    print(f"  {'─'*4}  {'─'*5}  {'─'*16}  {'─'*20}  {'─'*30}")

    for i, claim in enumerate(sorted_claims, 1):
        lvl = claim.get("certainty_level", "?")
        label = claim.get("certainty_label", "?")[:16]
        source = (claim.get("source_name") or "?")[:20]
        text = (claim.get("claim_text") or "(no text)")[:60]
        if len(claim.get("claim_text") or "") > 60:
            text += "..."
        print(f"  {i:<4}  {str(lvl):<5}  {label:<16}  {source:<20}  {text}")

        if verbose:
            # Show extra fields
            url = claim.get("source_url") or ""
            effective = claim.get("effective_date") or "(not specified)"
            action = claim.get("tariff_action") or "?"
            print(f"         Action: {action}   Effective: {effective}")
            if url:
                print(f"         URL: {url[:70]}")
            print()


# ── Pipeline stage check ──────────────────────────────────────────────────────


def print_pipeline_stages(date: str):
    header(f"PIPELINE STAGE CHECK: {date}")

    stages = [
        ("raw",       DATA_RAW / date,             "fetch_sources.py"),
        ("extracted", DATA_EXTRACTED / date,        "extract_claims.py + classify.py"),
        ("daily",     DATA_DAILY / f"{date}.json",  "generate_daily.py"),
    ]

    for stage_name, path, script in stages:
        exists = path.exists()
        status = "PRESENT" if exists else "MISSING"
        marker = "OK" if exists else "!!"

        print(f"  [{marker}] {stage_name:<12} {status:<10}  {path}")
        print(f"       Generated by: {script}")

        if exists and path.is_dir():
            # Show what's inside
            files = list(path.iterdir())
            json_files = [f for f in files if f.suffix == ".json"]
            print(f"       Contents: {len(json_files)} JSON file(s)")

            # If extracted, check manifest
            manifest_path = path / "manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    print(f"       Manifest: {manifest.get('articles_processed', '?')} articles, "
                          f"{manifest.get('claims_saved', '?')} claims saved")
                except Exception:
                    pass
        elif exists and path.is_file():
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"       Contents: {len(data)} claims")
            except Exception:
                print("       Contents: (could not parse)")

        print()

    # Diagnosis
    raw_ok = (DATA_RAW / date).exists()
    ext_ok = (DATA_EXTRACTED / date).exists()
    daily_ok = (DATA_DAILY / f"{date}.json").exists()

    section("Diagnosis")
    if daily_ok:
        print("  Pipeline appears complete for this date.")
    elif ext_ok and not daily_ok:
        print("  Extraction done but generate_daily.py did not run (or failed).")
    elif raw_ok and not ext_ok:
        print("  Raw data fetched but extract_claims.py did not run (or failed).")
    elif not raw_ok:
        print("  No raw data — fetch_sources.py has not run for this date.")


# ── No-data message ───────────────────────────────────────────────────────────


def print_no_data_message():
    header("NO DATA FOUND")
    print("  The pipeline has not produced any daily files yet.")
    print()
    print("  Expected location: data/daily/YYYY-MM-DD.json")
    print()
    print("  To run the pipeline manually:")
    print("    1. python scripts/fetch_sources.py")
    print("    2. python scripts/extract_claims.py")
    print("    3. python scripts/classify.py")
    print("    4. python scripts/generate_daily.py")
    print()
    print("  Or check the GitHub Actions workflow:")
    print("    .github/workflows/daily_tracker.yml")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose Cavela Tariff Tracker data quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Drill down into a specific date (also runs pipeline stage check)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show more detail in quality checks and drill-down",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Print quality issues only, no summary or distribution stats",
    )
    args = parser.parse_args()

    # Validate --date if provided
    if args.date and not _looks_like_date(args.date):
        print(f"ERROR: --date must be in YYYY-MM-DD format, got: {args.date!r}")
        return 1

    # Load all daily data
    daily = load_daily_files()

    if not daily:
        if args.date:
            # Still run pipeline stage check even if no daily data
            print_pipeline_stages(args.date)
        else:
            print_no_data_message()
        return 0

    # Route based on flags
    if args.check_only:
        print_quality_checks(daily, verbose=args.verbose)

    elif args.date:
        print_date_drilldown(args.date, daily, verbose=args.verbose)
        print()
        print_pipeline_stages(args.date)

    else:
        # Full report
        print_summary(daily)
        print_certainty_distribution(daily)
        print_source_breakdown(daily, verbose=args.verbose)
        print_quality_checks(daily, verbose=args.verbose)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'─' * WIDTH}")
    print(f"  Cavela Tariff Tracker Diagnostics | {now_utc}")
    print(f"{'─' * WIDTH}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
