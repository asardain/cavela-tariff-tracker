/**
 * country-timeline.js — View 2: Country Tariff History + Volatility
 *
 * Question: What has the tariff history been? Is a country stable or volatile?
 *
 * Marks: small multiples (one strip per country), event dots (r=certainty),
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

export function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html('');

  if (!allClaims || allClaims.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No data available yet.</p>');
    return;
  }

  const { byCountry, monthCounts } = buildCountryTimeline(allClaims);
  const countries = [...byCountry.keys()];

  if (countries.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No country data parsed from claims.</p>');
    return;
  }

  const containerWidth = container.getBoundingClientRect().width || 900;
  const innerW = containerWidth - MARGIN.left - MARGIN.right;
  const totalH = countries.length * (STRIP_HEIGHT + STRIP_GAP) + MARGIN.top + MARGIN.bottom + 32;

  // Time domain: all published dates
  const allDates = allClaims.map(c => c.published_ts).filter(Boolean);
  const [minDate, maxDate] = d3.extent(allDates);
  const xDomain = [
    d3.timeMonth.floor(minDate || new Date(Date.now() - 90 * 864e5)),
    d3.timeMonth.ceil(maxDate || new Date()),
  ];

  const x = d3.scaleTime().domain(xDomain).range([0, innerW]);
  const rScale = certaintyRadius();
  const oScale = certaintyOpacity();

  const svg = el.append('svg')
    .attr('class', 'viz-svg')
    .attr('width', containerWidth)
    .attr('height', totalH);

  renderAnnotations(svg, 'Tariff activity timeline by country',
    'Each dot is a claim. Size and opacity = certainty. Background band opacity = activity volume (volatility).',
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

    // Event dots
    const dotY = STRIP_HEIGHT / 2;
    strip.selectAll('.event-dot')
      .data(claims)
      .join('circle')
      .attr('class', 'event-dot')
      .attr('cx', d => x(d.published_ts))
      .attr('cy', dotY)
      .attr('r', d => rScale(d.certainty_level))
      .attr('fill', d => blue(oScale(d.certainty_level)))
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

  // Shared x-axis at bottom
  const axisG = g.append('g')
    .attr('transform', `translate(0, ${countries.length * (STRIP_HEIGHT + STRIP_GAP) + 8})`);
  renderTimeAxis(axisG, x, { ticks: 8 });

  // Today marker (drawn over all strips)
  renderTodayMarker(g, x, countries.length * (STRIP_HEIGHT + STRIP_GAP));
}
