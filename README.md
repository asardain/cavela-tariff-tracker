# Cavela Tariff Tracker

A daily automated service that monitors US tariff activity, extracts structured factual claims from official and news sources, and classifies each claim's reliability using a fixed 7-level ontology.

## What It Does

Every day at 9am UTC, a GitHub Actions workflow:

1. **Fetches** new content from 10+ official and news sources (RSS feeds + web scraping)
2. **Extracts** factual tariff claims using Claude AI
3. **Classifies** each claim with a certainty level (1=Speculation → 7=Law)
4. **Commits** a structured JSON + human-readable Markdown summary
5. **Opens a PR** for human review

## Reliability Ontology

Every claim is assigned one of 7 certainty levels:

| Level | Label | Description |
|-------|-------|-------------|
| 1 | SPECULATION | Analyst opinion, unnamed sources, "could", "might" |
| 2 | REPORTED | Named sources, "plans to", "expected to" |
| 3 | PROPOSED | Official NPRM, public comment period opened |
| 4 | ANNOUNCED | Official press release or agency announcement |
| 5 | EXECUTIVE_ORDER | Signed EO or Presidential Proclamation |
| 6 | RULE_PUBLISHED | Final rule published in Federal Register |
| 7 | LAW | Act of Congress signed into law |

See [`schema/ontology.md`](schema/ontology.md) for the full specification.

## Data Sources

### Official US Government (reliability floor: Level 3)
- **USTR** — Office of the US Trade Representative (ustr.gov)
- **CBP** — Customs and Border Protection (cbp.gov)
- **Federal Register** — federalregister.gov (RSS available)
- **USITC** — International Trade Commission (usitc.gov)
- **BIS/Commerce** — Bureau of Industry and Security (bis.gov)

### International Bodies (reliability floor: Level 2)
- **WTO** — Dispute Settlement News (wto.org)

### News Wires (reliability floor: Level 1)
- **Reuters** — Trade RSS feed
- **PR Newswire** — Filtered for tariff keywords

### Financial Press (reliability floor: Level 1)
- **Politico** — Trade RSS

## Data Format

Each daily data file lives at `data/daily/YYYY-MM-DD.json` and contains an array of claim objects:

```json
[
  {
    "claim_id": "uuid",
    "claim_text": "The USTR announced a 25% tariff on steel imports from Mexico effective April 1, 2025.",
    "subject": "Steel imports from Mexico",
    "tariff_action": "new_tariff",
    "effective_date": "2025-04-01",
    "source_url": "https://ustr.gov/...",
    "source_name": "USTR",
    "published_date": "2025-03-15T14:00:00Z",
    "extracted_date": "2025-03-16T09:00:00Z",
    "certainty_level": 4,
    "certainty_label": "ANNOUNCED",
    "certainty_rationale": "Official USTR press release with named agency as source.",
    "pedigree": {
      "source_name": "USTR",
      "source_category": "official_us_gov",
      "source_url": "https://ustr.gov/...",
      "published_date": "2025-03-15T14:00:00Z",
      "extracted_date": "2025-03-16T09:00:00Z",
      "certainty_level": 4
    }
  }
]
```

A human-readable Markdown summary is also generated at `data/daily/YYYY-MM-DD.md`.

## Setup

### Prerequisites
- Python 3.11+
- `ANTHROPIC_API_KEY` environment variable

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run a manual fetch (saves to data/raw/YYYY-MM-DD/)
python scripts/fetch_sources.py

# Extract claims from today's raw data
python scripts/extract_claims.py

# Classify claims (adds certainty levels)
python scripts/classify.py

# Generate daily summary files
python scripts/generate_daily.py

# Run tests
pytest tests/
```

### GitHub Actions

The workflow runs automatically at 9am UTC daily. To trigger manually:
1. Go to **Actions** tab
2. Select **Daily Tariff Tracker**
3. Click **Run workflow**

Required secrets (configure in repo Settings → Secrets):
- `ANTHROPIC_API_KEY` — Claude API key for claim extraction

## Directory Structure

```
cavela-tariff-tracker/
├── .github/workflows/daily_tracker.yml   # Automated daily workflow
├── config/sources.yaml                   # Source registry
├── data/
│   ├── raw/YYYY-MM-DD/                   # Raw fetched articles
│   ├── extracted/YYYY-MM-DD/             # Extracted claims (pre-classify)
│   └── daily/                            # Final daily outputs
├── docs/
├── schema/
│   ├── claim.schema.json                 # JSON Schema for claims
│   └── ontology.md                       # Reliability ontology
├── scripts/
│   ├── fetch_sources.py                  # Source fetcher
│   ├── extract_claims.py                 # Claude-powered extractor
│   ├── classify.py                       # Ontology classifier
│   └── generate_daily.py                # Daily file generator
├── tests/                                # pytest test suite
├── requirements.txt
└── README.md
```

## Review Process

Each daily PR is titled `Tariff Update: YYYY-MM-DD` and includes:
- Total number of new claims
- Breakdown by certainty level
- Top 3 most certain claims (for quick scanning)

Merge the PR after reviewing the claims to incorporate them into the main data history.
