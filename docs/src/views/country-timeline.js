/**
 * country-timeline.js — View 2: Country Tariff History + Volatility
 *
 * Question: What has the tariff history been? Is a country stable or volatile?
 *
 * Marks: small multiples (one strip per country), event dots (uniform size,
 *        color = action type, opacity = certainty level),
 *        volatility bands (month rect opacity = claim count).
 * export mount(container, data, options?)
 */

import { buildCountryTimeline } from '../data.js';
import {
  timeScale, certaintyRadius, certaintyOpacity,
  renderAnnotations, renderTimeAxis, renderTodayMarker,
  showTooltip, hideTooltip, claimTooltipHtml,
  blue, TYPO,
} from '../marks.js';

const MARGIN = { top: 80, right: 40, bottom: 40, left: 130 };
const STRIP_HEIGHT = 56;
const STRIP_GAP = 4;

// Action type -> color mapping (matches feed view pills)
const ACTION_COLOR = {
  new_tariff:           '#dc2626',
  tariff_increase:      '#dc2626',
  tariff_removal:       '#16a34a',
  tariff_pause:         '#16a34a',
  investigation_opened: '#6b7280',
  rule_proposed:        '#6b7280',
  other:                '#6b7280',
};

function actionColor(action) {
  return ACTION_COLOR[action] || '#6b7280';
}

// Certainty level (1–7) -> 3-tier opacity
function certaintyOpacityLinear(level) {
  if (level <= 2) return 0.3;  // Speculative
  if (level <= 4) return 0.65; // Likely
  return 1.0;                  // Confirmed
}

export function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html('');

  if (!allClaims || allClaims.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No data available yet.</p>');
    return;
  }

  const { byCountry, monthCounts } = buildCountryTimeline(
    allClaims.filter(c => !c.research_claim)
  );
  const countries = [...byCountry.keys()];

  if (countries.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No country data parsed from claims.</p>');
    return;
  }

  const containerWidth = container.getBoundingClientRect().width || 900;
  const innerW = containerWidth - MARGIN.left - MARGIN.right;
  const totalH = countries.length * (STRIP_HEIGHT + STRIP_GAP) + MARGIN.top + MARGIN.bottom + 32;

  // Normalize today to local time (midnight) for consistent today marker + domain
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Fixed 3-month window ending today
  const threeMonthsAgo = new Date(today);
  threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);

  const xDomain = [
    d3.timeMonth.floor(threeMonthsAgo),
    d3.timeMonth.ceil(today),
  ];

  // Filter claims to the 3-month window
  const windowStart = xDomain[0];

  const x = d3.scaleTime().domain(xDomain).range([0, innerW]);

  const svg = el.append('svg')
    .attr('class', 'viz-svg')
    .attr('width', containerWidth)
    .attr('height', totalH);

  renderAnnotations(svg, 'Tariff activity timeline by country',
    'Each dot is a claim. Color = action type. Opacity = certainty level. Background band opacity = activity volume (volatility).',
    MARGIN.left, 28);

  const g = svg.append('g').attr('transform', `translate(${MARGIN.left}, ${MARGIN.top})`);

  // Draw each country strip
  countries.forEach((country, i) => {
    const claims = byCountry.get(country);
    const gy = i * (STRIP_HEIGHT + STRIP_GAP);
    const strip = g.append('g').attr('class', 'country-strip')
      .attr('transform', `translate(0, ${gy})`);

    // Strip background
    strip.append('rect')
      .attr('width', innerW)
      .attr('height', STRIP_HEIGHT)
      .attr('fill', i % 2 === 0 ? 'transparent' : blue(0.015))
      .attr('rx', 2);

    // Volatility bands (one per month)
    const months = d3.timeMonths(xDomain[0], xDomain[1]);
    const maxMonthCount = d3.max(months, m => {
      const key = `${country}|||${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, '0')}`;
      return monthCounts.get(key) || 0;
    }) || 1;
    const bandOpacity = d3.scaleLinear().domain([0, maxMonthCount]).range([0, 0.1]);

    months.forEach(m => {
      const key = `${country}|||${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, '0')}`;
      const count = monthCounts.get(key) || 0;
      const x0 = x(m);
      const x1 = x(d3.timeMonth.offset(m, 1));
      strip.append('rect')
        .attr('x', x0)
        .attr('y', 0)
        .attr('width', Math.max(0, x1 - x0))
        .attr('height', STRIP_HEIGHT)
        .attr('fill', blue(bandOpacity(count)));
    });

    // Event dots — uniform radius, color = action type, opacity = certainty level
    const DOT_R = 5;
    const dotY = STRIP_HEIGHT / 2;
    strip.selectAll('.event-dot')
      .data(claims.filter(d => d.published_ts >= windowStart))
      .join('circle')
      .attr('class', 'event-dot')
      .attr('cx', d => x(d.published_ts))
      .attr('cy', dotY)
      .attr('r', DOT_R)
      .attr('fill', d => actionColor(d.tariff_action))
      .attr('opacity', d => certaintyOpacityLinear(d.certainty_level || 1))
      .style('cursor', 'pointer')
      .on('mousemove', (event, d) => showTooltip(claimTooltipHtml(d), event))
      .on('mouseleave', () => hideTooltip());

    // Country label (left)
    strip.append('text')
      .attr('x', -10)
      .attr('y', STRIP_HEIGHT / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.sm)
      .attr('font-weight', '500')
      .attr('fill', 'var(--text)')
      .text(country);

    // Claim count
    strip.append('text')
      .attr('x', innerW + 8)
      .attr('y', STRIP_HEIGHT / 2)
      .attr('dy', '0.35em')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.xs)
      .attr('fill', 'var(--text-secondary)')
      .text(`${claims.length}`);
  });

  // Shared x-axis at bottom — one tick per month, month-name only (no duplicates)
  const axisG = g.append('g')
    .attr('transform', `translate(0, ${countries.length * (STRIP_HEIGHT + STRIP_GAP) + 8})`);
  const timeAxis = d3.axisBottom(x)
    .ticks(d3.timeMonth.every(1))
    .tickSize(4)
    .tickFormat(d3.timeFormat('%b'));
  axisG.call(timeAxis)
    .call(ag => ag.select('.domain').attr('stroke', 'var(--border)'))
    .call(ag => ag.selectAll('.tick line').attr('stroke', 'var(--border)'))
    .call(ag => ag.selectAll('.tick text')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.xs)
      .attr('fill', 'var(--text-secondary)'));

  // Today marker — use same normalized local-time today as the domain calculation
  const tx = x(today);
  g.append('line')
    .attr('x1', tx).attr('x2', tx)
    .attr('y1', 0).attr('y2', countries.length * (STRIP_HEIGHT + STRIP_GAP))
    .attr('stroke', blue(0.4))
    .attr('stroke-dasharray', '4,3')
    .attr('stroke-width', 1);
  g.append('text')
    .attr('x', tx + 4)
    .attr('y', -4)
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.xs)
    .attr('fill', blue(0.7))
    .text('Today');
}
