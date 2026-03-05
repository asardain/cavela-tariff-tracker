# Visualization Layer Design Document — Cavela Tariff Tracker

## Data Shape Summary

Every visualization starts from `TariffClaim[]` loaded from `data/daily/YYYY-MM-DD.json`. Key encodable fields:

| Field | Type | Encodes |
|-------|------|---------|
| `subject` | string | Country, product, HS code (needs parsing) |
| `tariff_action` | enum (7 values) | Action type |
| `effective_date` | date \| null | When it takes effect |
| `published_date` | datetime | When the source published |
| `certainty_level` | int 1-7 | How certain/official the claim is |
| `certainty_label` | enum (7 values) | Human label for certainty |
| `pedigree.source_category` | enum (4 values) | Source reliability tier |

### Derived fields (computed in data transforms, not viz layer)

| Derived Field | Computation |
|---------------|-------------|
| `country` | Parsed from `subject` via country name matching |
| `category` | Parsed from `subject` via product keyword matching |
| `rate_pct` | Parsed from `claim_text` via regex (e.g., "25% tariff") |
| `week` / `month` | `d3.timeWeek.floor(published_date)` |
| `days_until_effective` | `effective_date - today` |
| `claim_count` | Aggregation per group |

---

## View 1: Country-Category Rate Matrix

**Question:** Which countries are tariffed at what rates, right now, by product category?

### Marks

| Mark | Geometry | Why |
|------|----------|-----|
| **Cell** | `<rect>` | One per (country, category) pair. Fill opacity encodes tariff rate. |
| **Rate label** | `<text>` | Inside each cell: rate percentage. Direct labeling eliminates legend. |
| **Certainty dot** | `<circle>` | Corner dot, radius = certainty level. Separates rumor from law. |

### Aesthetic mapping

```
x       -> category       (d3.scaleBand)
y       -> country         (d3.scaleBand, sorted by max rate desc)
opacity -> rate_pct        (d3.scaleLinear, [0, max_rate] -> [0.05, 0.9])
fill    -> #2563eb (constant)
text    -> rate_pct + "%"  (direct label)
r       -> certainty_level (d3.scaleSqrt, [1,7] -> [2,6]px)
```

### Data flow

```
loadAllDailyFiles()
  |> filterByAction(['new_tariff', 'tariff_increase', 'tariff_removal'])
  |> parseSubject()           // adds .country, .category
  |> parseRate()              // adds .rate_pct from claim_text
  |> groupBy([country, category])
  |> keepLatest(published_date)  // one claim per cell
```

### Layout
- Title (20px): "Tariff rates by country and product category"
- Subtitle (13px): "Dot size = certainty level."
- Categories as columns, countries as rows. No gridlines — white space between cells.
- Right margin: sparkline of claim volume per country (last 90 days)

### Interaction
- **Hover cell**: Tooltip with `claim_text`, `source_name`, `published_date`, `certainty_label`
- **Click cell**: Expand to show all historical claims for that (country, category) pair as vertical timeline

---

## View 2: Country Tariff Timeline (History + Volatility)

**Question:** What has the tariff history been for a given country? Is it stable or volatile?

### Marks

| Mark | Geometry | Why |
|------|----------|-----|
| **Event dot** | `<circle>` | One per claim, positioned by date |
| **Volatility band** | `<rect>` | Background shading per month, opacity = claim count. High opacity = volatile. |
| **Certainty** | `r` + `opacity` on `<circle>` | Larger/darker dots = more certain claims |

### Aesthetic mapping

```
x       -> published_date  (d3.scaleTime)
y       -> country          (d3.scaleBand — small multiples, one row per country)
r       -> certainty_level  (d3.scaleSqrt, [1,7] -> [3,8]px)
opacity -> certainty_level  (d3.scaleLinear, [1,7] -> [0.3, 1.0])
fill    -> #2563eb
```

Volatility band:
```
x       -> month start     (d3.scaleTime)
width   -> 1 month
opacity -> claim_count     (d3.scaleLinear, [0, max] -> [0, 0.08])
fill    -> #2563eb
```

### Data flow

```
loadAllDailyFiles()
  |> parseSubject()
  |> filterByCountries(top-N or user selection)
  |> sortBy(published_date)
  |> groupBy(country)
  |> For bands: groupBy([country, month]) |> count()
```

### Layout
- Small multiples: one horizontal strip (~60px) per country (principle 7)
- Sorted by total claim count (most active on top)
- Shared x-axis across all strips
- Title (20px): "Tariff activity timeline"
- Annotate most volatile months with event context

### Interaction
- **Hover dot**: Tooltip with claim text, source, certainty label
- **Brush x-axis**: Select time range, all strips update
- **Click country label**: Expand strip to show claim detail list

---

## View 3: Sourcing Alternatives Comparison

**Question:** If I need to move production from Country X, where should I look?

### Marks

| Mark | Geometry | Why |
|------|----------|-----|
| **Country bar** | `<rect>` | Horizontal bar, length = tariff rate. Primary comparison. |
| **Certainty underline** | `<line>` | Below bar, length proportional to certainty. |
| **Trend arrow** | `<text>` | Unicode arrow at bar end (up/down/stable) |
| **Claim count** | `<text>` | Right-aligned: how many claims support this assessment |

### Aesthetic mapping

```
x       -> rate_pct          (d3.scaleLinear)
y       -> country           (d3.scaleBand, sorted by rate ascending)
opacity -> certainty_level   (d3.scaleLinear, [1,7] -> [0.3, 1.0])
fill    -> #2563eb
```

### Data flow

```
loadAllDailyFiles()
  |> parseSubject() |> parseRate()
  |> filterByCategory(selectedCategory)
  |> groupBy(country)
  |> aggregate({ rate_pct: latest, certainty_level: max, claim_count: count, trend: direction })
  |> sortBy(rate_pct, ascending)
```

### Layout
- Title (20px): "Tariff rates by sourcing country for [category]"
- Horizontal bars, country labels on left
- Rate direct-labeled at bar end
- Reference line at "current country" rate for comparison

### Interaction
- **Dropdown**: Select product category
- **Hover bar**: Full claim text, source breakdown
- **Click bar**: Navigate to that country's timeline (View 2)
- **Toggle**: Show/hide speculative claims (certainty < 3)

---

## View 4: Horizon Scanner

**Question:** What tariff decisions are coming? What's the timeline?

### Marks

| Mark | Geometry | Why |
|------|----------|-----|
| **Claim dot** | `<circle>` | Per claim with future effective date |
| **Today marker** | `<line>` | Vertical dashed line at today |
| **Label** | `<text>` | Subject text, collision-avoided |
| **Certainty** | `r` + `opacity` | Larger/darker = more certain to happen |

### Aesthetic mapping

```
x       -> effective_date    (d3.scaleTime, [today - 30d, today + 180d])
y       -> stacked index     (d3.scaleBand — claims stacked per day)
r       -> certainty_level   (d3.scaleSqrt, [1,7] -> [4,10]px)
opacity -> certainty_level   (d3.scaleLinear, [1,7] -> [0.2, 1.0])
fill    -> #2563eb
```

### Data flow

```
loadAllDailyFiles()
  |> filter(effective_date != null)
  |> filter(effective_date >= today - 30 || published_date >= today - 30)
  |> sortBy(effective_date)
  |> groupBy(effective_date) |> assignStackIndex()
```

### Layout
- Horizontal timeline, today marker prominently labeled
- Past 30 days left, next 180 days right
- Claims without `effective_date` in "Unscheduled" column at far right
- Annotate date clusters (3+ claims on same date)

### Interaction
- **Hover dot**: Full claim detail
- **Brush x-axis**: Zoom into date range
- **Click dot**: Opens source URL

---

## View 5: Volatility Alert Feed

**Question:** What happened this week? Is there unusual activity?

### Marks

| Mark | Geometry | Why |
|------|----------|-----|
| **Claim row** | `<rect>` + `<text>` | Structured feed, one row per claim |
| **Certainty bar** | `<rect>` | Inline bar, width = certainty_level |
| **Action badge** | `<rect>` + `<text>` | Pill showing action type |
| **Sparkline** | `<path>` | Per-country mini line, last 30 days of claim volume |
| **Anomaly highlight** | `<rect>` | Background on rows where weekly activity > 2x baseline |

### Aesthetic mapping

```
y           -> claim index      (d3.scaleBand, newest first)
bar width   -> certainty_level  (d3.scaleLinear, [1,7] -> [10, 70]px)
bar opacity -> certainty_level  (d3.scaleLinear, [1,7] -> [0.3, 1.0])
fill        -> #2563eb
bg fill     -> #2563eb at 0.04 (anomaly rows)
sparkline y -> weekly_claim_count (d3.scaleLinear per country)
```

### Data flow

```
loadAllDailyFiles()
  |> parseSubject()
  |> computeWeeklyBaseline(country, 90 days)
  |> filterToThisWeek()
  |> flagAnomalies(threshold: 2x baseline)
  |> sortBy(published_date, desc)
  |> For sparklines: groupBy([country, week]) |> count() |> last 8 weeks
```

### Layout
- Columns: Date (80px) | Subject (flex) | Action (100px) | Certainty (80px) | Sparkline (120px)
- Max 50 rows, scrollable
- Anomalous rows get pale blue background

### Interaction
- **Filter pills**: Country, category, action type, certainty threshold
- **Click row**: Expand to full claim text + source link
- **Toggle**: "Show anomalies only"

---

## Component Architecture

### File Structure

```
viz/
  index.html                  # Single-page shell, loads D3 + modules
  styles/main.css             # Typography scale, color constants, layout

  src/
    data.js                   # loadDailyFiles, parseSubject, parseRate, aggregations
    marks.js                  # Reusable mark primitives (dot, bar, cell, sparkline, row)
    dashboard.js              # Composition layer, tab navigation, view mounting

    views/
      alert-feed.js           # View 5: This week's alerts
      rate-matrix.js          # View 1: Country-category rate matrix
      country-timeline.js     # View 2: History + volatility
      horizon-scanner.js      # View 4: Upcoming decisions
      sourcing-compare.js     # View 3: Sourcing alternatives
```

### Data Transformation Functions

```javascript
// src/data.js
loadDailyFile(date)                          // fetch + parse -> TariffClaim[]
loadDailyFiles(startDate, endDate)           // load range, concat, deduplicate
parseSubject(claim)                          // -> { ...claim, country, category }
parseRate(claim)                             // -> { ...claim, rate_pct }
enrichClaim(claim)                           // parseSubject + parseRate
groupBy(claims, keys)                        // -> Map<string, TariffClaim[]>
keepLatest(group, dateField)                 // -> most recent per group
countBy(claims, key)                         // -> { [key]: count }
computeWeeklyBaseline(claims, country, windowWeeks)
flagAnomalies(claims, threshold)             // -> claims with .is_anomaly
trendDirection(rates)                        // -> 'up' | 'down' | 'stable'
```

### Scale Factories (in src/marks.js)

```javascript
const BLUE = '#2563eb';
const TYPO = { xs: 11, sm: 13, base: 16, lg: 20, xl: 25 };
const BLUE_FILL = (opacity) => `rgba(37, 99, 235, ${opacity})`;

timeScale(domain)              // d3.scaleTime
rateScale(maxRate)             // d3.scaleLinear -> [0, barWidth]
certaintyRadius()              // d3.scaleSqrt([1,7], [2,8])
certaintyOpacity()             // d3.scaleLinear([1,7], [0.2, 1.0])
categoryBand(categories, width)
countryBand(countries, height)
```

### Rendering Pattern

Every view exports a single function: `mount(container, data, options?) -> void`

```javascript
export function mount(container, data, options = {}) {
  // 1. TRANSFORM: pure pipeline
  const cells = pipe(data, filter, parse, group, latest);

  // 2. SCALES: derived from transformed data
  const x = categoryBand(...);
  const y = countryBand(...);

  // 3. BIND MARKS: D3 data join
  const sel = d3.select(container).selectAll('.cell').data(cells, key);
  const enter = sel.enter().append('g');

  // 4. ANNOTATE: title, subtitle
  // 5. INTERACT: tooltip, click handlers
  // 6. EXIT: sel.exit().remove()
}
```

### Dashboard Shell

```javascript
const VIEWS = [
  { id: 'alerts',   label: 'This Week',     module: alertFeed },
  { id: 'rates',    label: 'Current Rates',  module: rateMatrix },
  { id: 'timeline', label: 'History',        module: countryTimeline },
  { id: 'horizon',  label: 'Horizon',        module: horizonScanner },
  { id: 'sourcing', label: 'Alternatives',   module: sourcingCompare },
];
// Tab bar, one view visible at a time, data loaded once.
```

---

## Subject Parsing Strategy

`subject` is LLM-generated free text. Parse with keyword matching:

```javascript
const COUNTRIES = ['China', 'Vietnam', 'Mexico', 'Bangladesh', 'India', ...];
const CATEGORIES = [
  { label: 'Apparel', patterns: ['apparel', 'clothing', 'garment', 'textile'] },
  { label: 'Electronics', patterns: ['electronic', 'semiconductor', 'chip', 'laptop'] },
  { label: 'Steel & Metals', patterns: ['steel', 'aluminum', 'metal', 'iron'] },
];

// Rate from claim_text: /(\d+(?:\.\d+)?)\s*(%|percent)/i
```

Surface "Unknown" gracefully — never hide unparseable claims.

---

## Key Design Decisions

1. **No chart library on top of D3.** Marks composed from primitives, not templates. (Principle 1)
2. **Single blue hue.** Certainty encoded by opacity. Action type by position/text, never color. (Principle 5)
3. **Subject parsing is best-effort.** "Unknown" is shown, not hidden.
4. **Data transforms are pure functions.** No state in transform layer. (Principles 3, 10)
5. **Progressive disclosure.** Summary marks → hover tooltip → click expansion. (Principle 12)
6. **Small multiples for country comparison.** One strip per country, not overlaid. (Principle 7)
7. **Direct labeling over legends.** Rate % as text in cells/bars. Certainty encoded redundantly (size + opacity). (Principle 4)
