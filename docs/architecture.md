# Cavela Tariff Tracker — Architecture

## Pipeline Overview

```
[GitHub Cron: 9am UTC]
         │
         ▼
fetch_sources.py ──► data/raw/YYYY-MM-DD/*.json
         │
         ▼
extract_claims.py ──► data/extracted/YYYY-MM-DD/claims.json
  (Claude API)
         │
         ▼
classify.py ──► enriches claims with certainty_level, certainty_label, certainty_rationale
         │
         ▼
generate_daily.py ──► data/daily/YYYY-MM-DD.json
                  └──► data/daily/YYYY-MM-DD.md
         │
         ▼
[Git: create branch tariff-update/YYYY-MM-DD]
[Git: commit data files]
[GitHub: open PR with summary]
```

## Component Responsibilities

### fetch_sources.py
- Reads `config/sources.yaml` for source definitions
- For RSS sources: uses `feedparser` to fetch and parse feed
- For web sources without RSS: uses `requests` + `BeautifulSoup` to scrape
- Filters entries to last 24 hours (by published date)
- Deduplicates by URL across sources
- Saves each article as `{hash(url)}.json` in `data/raw/YYYY-MM-DD/`
- Article format: `{url, title, content, published_date, source_name, source_category}`

### extract_claims.py
- Reads all JSON files from `data/raw/YYYY-MM-DD/`
- For each article, calls Claude API (claude-haiku) with a structured prompt
- Prompt asks Claude to extract tariff-related claims with required fields
- Validates each extracted claim against `schema/claim.schema.json`
- Drops claims that fail validation (logs warning)
- Saves all valid claims to `data/extracted/YYYY-MM-DD/claims.json`

### classify.py
- Reads `data/extracted/YYYY-MM-DD/claims.json`
- For each claim, calls Claude API with the ontology context
- Claude assigns certainty_level (1-7) and rationale
- Applies source reliability floors from `config/sources.yaml`
- Updates claims in-place with certainty fields
- Writes back to `data/extracted/YYYY-MM-DD/claims.json`

### generate_daily.py
- Reads classified claims from `data/extracted/YYYY-MM-DD/claims.json`
- Writes final `data/daily/YYYY-MM-DD.json` (full claim array)
- Writes `data/daily/YYYY-MM-DD.md` (grouped by certainty level, human-readable)
- Outputs PR body text to stdout for the workflow to capture

## Error Handling

Every script uses this pattern:
```python
try:
    result = fetch_or_process(item)
except Exception as e:
    logger.warning(f"Failed to process {item}: {e}")
    continue  # never crash the pipeline
```

The pipeline always produces output files, even if empty. An empty daily file (`[]`) is valid and will still trigger a PR (which can be closed immediately if no claims were found).

## Deduplication

Articles are deduplicated by URL hash before extraction. Claims are deduplicated by (claim_text, source_url) pair — if the same claim appears from two sources, only the higher-certainty version is kept.

## Rate Limiting

- RSS fetches: 1 second delay between sources
- Claude API calls: uses SDK's built-in retry with exponential backoff
- Web scraping: 2 second delay between requests, respects robots.txt

## Data Retention

Raw and extracted data is committed to the repo as part of the daily PR. This creates a permanent audit trail of all claims ever seen. The `data/daily/` directory is the canonical output; `data/raw/` and `data/extracted/` are preserved for debugging.
