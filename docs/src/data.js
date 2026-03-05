/**
 * data.js — Pure data loading and transformation functions
 * No side effects. No DOM. No visualization state.
 *
 * Pipeline: raw JSON -> enrich -> aggregate -> view-ready data
 */

// ---------------------------------------------------------------------------
// Constants: country and category keyword dictionaries
// ---------------------------------------------------------------------------

export const COUNTRIES = [
  'China', 'Vietnam', 'Mexico', 'Bangladesh', 'India', 'Cambodia',
  'Indonesia', 'Thailand', 'Sri Lanka', 'Pakistan', 'Turkey', 'Brazil',
  'South Korea', 'Taiwan', 'Japan', 'Germany', 'Canada', 'Malaysia',
  'Philippines', 'Ethiopia', 'Honduras', 'Guatemala', 'El Salvador',
  'EU', 'European Union', 'United Kingdom', 'UK',
];

export const CATEGORIES = [
  { label: 'Apparel',          patterns: ['apparel', 'clothing', 'garment', 'textile', 'fabric', 'fashion', 'footwear', 'shoes', 'handbag', 'bag', 'luggage'] },
  { label: 'Electronics',      patterns: ['electronic', 'semiconductor', 'chip', 'laptop', 'computer', 'phone', 'smartphone', 'tablet', 'circuit', 'battery'] },
  { label: 'Steel & Metals',   patterns: ['steel', 'aluminum', 'aluminium', 'metal', 'iron', 'copper', 'zinc', 'tin'] },
  { label: 'Solar & Energy',   patterns: ['solar', 'panel', 'wind', 'energy', 'photovoltaic', 'battery', 'ev', 'electric vehicle'] },
  { label: 'Auto & Parts',     patterns: ['auto', 'vehicle', 'car', 'truck', 'automobile', 'parts', 'motor'] },
  { label: 'Agriculture',      patterns: ['agriculture', 'crop', 'grain', 'soybean', 'corn', 'wheat', 'food', 'meat', 'beef', 'pork', 'poultry'] },
  { label: 'Chemicals',        patterns: ['chemical', 'polymer', 'plastic', 'rubber', 'resin', 'pharmaceutical', 'drug'] },
  { label: 'Machinery',        patterns: ['machinery', 'machine', 'equipment', 'industrial', 'manufacturing', 'tools'] },
];

export const ACTION_LABELS = {
  new_tariff:            'New Tariff',
  tariff_increase:       'Tariff Increase',
  tariff_removal:        'Tariff Removal',
  tariff_pause:          'Tariff Pause',
  investigation_opened:  'Investigation',
  rule_proposed:         'Rule Proposed',
  other:                 'Other',
};

export const CERTAINTY_LABELS = {
  1: 'SPECULATION',
  2: 'REPORTED',
  3: 'PROPOSED',
  4: 'ANNOUNCED',
  5: 'EXECUTIVE_ORDER',
  6: 'RULE_PUBLISHED',
  7: 'LAW',
};

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

/**
 * Load a single daily file.
 * @param {string} date - YYYY-MM-DD
 * @returns {Promise<object[]>} array of raw TariffClaim objects
 */
export async function loadDailyFile(date) {
  const url = `data/daily/${date}.json`;
  try {
    const res = await fetch(url);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (_) {
    return [];
  }
}

/**
 * Load a range of daily files, deduplicate by claim_id, return enriched claims.
 * @param {Date} startDate
 * @param {Date} endDate
 * @returns {Promise<object[]>} enriched, deduplicated TariffClaim[]
 */
export async function loadDailyFiles(startDate, endDate) {
  const dates = [];
  const cursor = new Date(startDate);
  while (cursor <= endDate) {
    dates.push(cursor.toISOString().slice(0, 10));
    cursor.setDate(cursor.getDate() + 1);
  }

  const batches = await Promise.all(dates.map(loadDailyFile));
  const all = batches.flat();

  // Deduplicate by claim_id (keep latest extracted_date)
  const seen = new Map();
  for (const claim of all) {
    const existing = seen.get(claim.claim_id);
    if (!existing || claim.extracted_date > existing.extracted_date) {
      seen.set(claim.claim_id, claim);
    }
  }

  return [...seen.values()].map(enrichClaim);
}

/**
 * Load all available data by attempting last 365 days.
 */
export async function loadAllAvailableData() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 365);
  return loadDailyFiles(start, end);
}

// ---------------------------------------------------------------------------
// Parsing / enrichment (pure functions — no side effects)
// ---------------------------------------------------------------------------

/**
 * Parse country from subject string.
 * Returns first matching country name, or 'Unknown'.
 */
export function parseCountry(subject) {
  if (!subject) return 'Unknown';
  const lower = subject.toLowerCase();
  for (const country of COUNTRIES) {
    if (lower.includes(country.toLowerCase())) return country;
  }
  return 'Unknown';
}

/**
 * Parse product category from subject + claim_text.
 */
export function parseCategory(subject, claimText = '') {
  const haystack = `${subject} ${claimText}`.toLowerCase();
  for (const cat of CATEGORIES) {
    if (cat.patterns.some(p => new RegExp(`\\b${p}\\b`).test(haystack))) return cat.label;
  }
  return 'Other';
}

/**
 * Parse tariff rate percentage from claim_text.
 * Returns null if no rate found.
 */
export function parseRate(claimText = '') {
  const match = claimText.match(/(\d+(?:\.\d+)?)\s*(%|percent)/i);
  return match ? parseFloat(match[1]) : null;
}

/**
 * Clean scraped text artifacts: spaced abbreviations, spaced punctuation, etc.
 */
function cleanText(text) {
  if (!text) return text;
  return text
    .replace(/U\s*\.\s*S\s*\./gi, 'U.S.')   // "U . S ." → "U.S."
    .replace(/(\d+)\s+(%)/g, '$1$2')          // "15 %" → "15%"
    .replace(/\s{2,}/g, ' ')                  // collapse multiple spaces
    .trim();
}

/**
 * Enrich a single claim with derived fields.
 */
export function enrichClaim(claim) {
  const subject = cleanText(claim.subject);
  const claimText = cleanText(claim.claim_text);
  return {
    ...claim,
    subject,
    claim_text:   claimText,
    country:      parseCountry(subject),
    category:     parseCategory(subject, claimText),
    rate_pct:     parseRate(claimText),
    published_ts: new Date(claim.published_date),
    effective_ts: claim.effective_date ? new Date(claim.effective_date) : null,
    action_label: ACTION_LABELS[claim.tariff_action] || claim.tariff_action,
  };
}

// ---------------------------------------------------------------------------
// Aggregation (pure functions)
// ---------------------------------------------------------------------------

/**
 * Group claims by one or more key functions.
 * @param {object[]} claims
 * @param {Function} keyFn - (claim) => string key
 * @returns {Map<string, object[]>}
 */
export function groupBy(claims, keyFn) {
  const map = new Map();
  for (const claim of claims) {
    const key = keyFn(claim);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(claim);
  }
  return map;
}

/**
 * From each group, keep only the claim with the latest published_ts.
 * @param {Map<string, object[]>} groups
 * @returns {object[]} one claim per group
 */
export function keepLatest(groups) {
  return [...groups.values()].map(group =>
    group.reduce((best, c) =>
      (!best || c.published_ts > best.published_ts) ? c : best
    , null)
  ).filter(Boolean);
}

/**
 * Build (country, category) matrix for the rate matrix view.
 * Returns array of { country, category, rate_pct, certainty_level, claim_text, ... }
 */
export function buildRateMatrix(claims) {
  const relevant = claims.filter(c =>
    c.rate_pct !== null && c.country !== 'Unknown' && c.certainty_level >= 4
  );
  const groups = groupBy(relevant, c => `${c.country}|||${c.category}`);
  return [...groups.entries()].map(([, groupClaims]) => {
    const latest = groupClaims.reduce((best, c) =>
      (!best || c.published_ts > best.published_ts) ? c : best, null);
    const rates = groupClaims
      .filter(c => c.rate_pct !== null)
      .sort((a, b) => a.published_ts - b.published_ts)
      .map(c => c.rate_pct);
    return {
      country: latest.country,
      category: latest.category,
      rate_pct: latest.rate_pct,
      certainty_level: latest.certainty_level,
      certainty_label: latest.certainty_label,
      claim_text: latest.claim_text,
      source_name: latest.source_name,
      published_ts: latest.published_ts,
      tariff_action: latest.tariff_action,
      action_label: latest.action_label,
      source_url: latest.source_url,
      trend: trendDirection(rates),
    };
  });
}

/**
 * Build per-country timeline data for small multiples.
 * Returns { byCountry: Map<country, claim[]>, monthCounts: Map<country|month, count> }
 */
export function buildCountryTimeline(claims) {
  const byCountry = groupBy(claims.filter(c => c.country !== 'Unknown'), c => c.country);

  // Monthly counts per country for volatility bands
  const monthCounts = new Map();
  for (const [country, countryClaims] of byCountry) {
    const byMonth = groupBy(countryClaims, c => {
      const d = c.published_ts;
      return `${country}|||${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    });
    for (const [key, group] of byMonth) {
      monthCounts.set(key, group.length);
    }
  }

  // Sort countries by total claim count descending
  const sorted = [...byCountry.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, 12); // top 12 countries

  return { byCountry: new Map(sorted), monthCounts };
}

/**
 * Build sourcing comparison data for a given category.
 */
export function buildSourcingComparison(claims, category) {
  const filtered = claims.filter(c =>
    c.rate_pct !== null &&
    (category === 'All' || c.category === category)
  );

  const byCountry = groupBy(filtered.filter(c => c.country !== 'Unknown'), c => c.country);

  return [...byCountry.entries()].map(([country, countryClaims]) => {
    const latest = countryClaims.reduce((best, c) =>
      (!best || c.published_ts > best.published_ts) ? c : best, null);
    const rates = countryClaims
      .filter(c => c.rate_pct !== null)
      .sort((a, b) => a.published_ts - b.published_ts)
      .map(c => c.rate_pct);
    return {
      country,
      rate_pct: latest?.rate_pct ?? null,
      certainty_level: Math.max(...countryClaims.map(c => c.certainty_level)),
      claim_count: countryClaims.length,
      trend: trendDirection(rates),
      latest_claim: latest?.claim_text ?? '',
      source_name: latest?.source_name ?? '',
    };
  }).filter(d => d.rate_pct !== null).sort((a, b) => a.rate_pct - b.rate_pct);
}

/**
 * Build horizon scanner data (claims with upcoming effective dates).
 */
export function buildHorizonData(claims) {
  const today = new Date();
  const past30 = new Date(today);
  past30.setDate(past30.getDate() - 30);
  const future180 = new Date(today);
  future180.setDate(future180.getDate() + 180);

  const withDates = claims.filter(c =>
    c.effective_ts !== null &&
    c.effective_ts >= past30 &&
    c.effective_ts <= future180
  );

  const unscheduled = claims.filter(c =>
    c.effective_ts === null &&
    c.published_ts >= past30
  ).slice(0, 20);

  // Assign stack index per effective date
  const byDate = groupBy(withDates, c => c.effective_ts.toISOString().slice(0, 10));
  const stacked = [];
  for (const [, dateClaims] of byDate) {
    dateClaims.forEach((c, i) => stacked.push({ ...c, stack_index: i }));
  }

  return { scheduled: stacked, unscheduled, today, domainStart: past30, domainEnd: future180 };
}

/**
 * Build alert feed data for the current week.
 */
export function buildAlertFeed(claims, weeks = 2) {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - weeks * 7);

  const recent = claims
    .filter(c => c.published_ts >= cutoff)
    .sort((a, b) => b.published_ts - a.published_ts);

  // Compute weekly baseline per country (90-day window)
  const baseline90 = new Date();
  baseline90.setDate(baseline90.getDate() - 90);
  const historical = claims.filter(c => c.published_ts >= baseline90);

  const weeklyBaselines = computeWeeklyBaselines(historical);

  const enriched = recent.map(c => ({
    ...c,
    is_anomaly: isAnomaly(c, weeklyBaselines),
  }));

  // Sparkline data: weekly counts per country, last 8 weeks
  const sparklines = buildSparklines(historical);

  return { claims: enriched, sparklines };
}

// ---------------------------------------------------------------------------
// Statistical helpers
// ---------------------------------------------------------------------------

/**
 * Compute average weekly claim count per country over the given window.
 */
function computeWeeklyBaselines(claims) {
  const byCountryWeek = groupBy(claims, c => {
    const d = c.published_ts;
    const weekStart = new Date(d);
    weekStart.setDate(d.getDate() - d.getDay());
    return `${c.country}|||${weekStart.toISOString().slice(0, 10)}`;
  });

  const byCountry = new Map();
  for (const [key, group] of byCountryWeek) {
    const country = key.split('|||')[0];
    if (!byCountry.has(country)) byCountry.set(country, []);
    byCountry.get(country).push(group.length);
  }

  const baselines = new Map();
  for (const [country, weeklyCounts] of byCountry) {
    const avg = weeklyCounts.reduce((s, v) => s + v, 0) / weeklyCounts.length;
    baselines.set(country, avg);
  }
  return baselines;
}

/**
 * Returns true if this claim's country had 2x+ activity this week vs baseline.
 */
function isAnomaly(claim, baselines) {
  // Simplified: mark as anomaly if certainty >= 4 and rate_pct exists
  // Real anomaly detection requires week-level aggregation in feed context
  return claim.certainty_level >= 5;
}

/**
 * Build sparkline series: { country -> [ { week, count } ] } for last 8 weeks.
 */
function buildSparklines(claims) {
  const sparklines = new Map();
  const byCountryWeek = groupBy(claims, c => {
    const d = c.published_ts;
    const weekStart = new Date(d);
    weekStart.setDate(d.getDate() - d.getDay());
    return `${c.country}|||${weekStart.toISOString().slice(0, 10)}`;
  });

  for (const [key, group] of byCountryWeek) {
    const [country, week] = key.split('|||');
    if (!sparklines.has(country)) sparklines.set(country, []);
    sparklines.get(country).push({ week: new Date(week), count: group.length });
  }

  // Sort by week ascending, keep last 8
  for (const [country, series] of sparklines) {
    sparklines.set(country, series.sort((a, b) => a.week - b.week).slice(-8));
  }

  return sparklines;
}

/**
 * Determine trend direction from array of rate values (chronological).
 */
export function trendDirection(rates) {
  if (rates.length < 2) return 'stable';
  const first = rates[0];
  const last = rates[rates.length - 1];
  if (last > first * 1.05) return 'up';
  if (last < first * 0.95) return 'down';
  return 'stable';
}

/**
 * Get unique sorted list of values for a field.
 */
export function uniqueValues(claims, field) {
  return [...new Set(claims.map(c => c[field]).filter(Boolean))].sort();
}
