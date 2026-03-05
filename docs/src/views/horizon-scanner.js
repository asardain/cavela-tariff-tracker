/**
 * horizon-scanner.js — View 4: Horizon Scanner (Upcoming Decisions)
 *
 * Question: What tariff decisions are coming? What's the timeline?
 *
 * Marks: dot per claim (r=certainty, opacity=certainty), today marker, labels.
 * export mount(container, data, options?)
 */

import { buildHorizonData } from '../data.js';
import {
  timeScale, certaintyRadius, certaintyOpacity,
  renderAnnotations, renderTimeAxis, renderTodayMarker,
  showTooltip, hideTooltip, claimTooltipHtml,
  blue, TYPO,
} from '../marks.js';

const MARGIN = { top: 80, right: 60, bottom: 50, left: 40 };
const DOT_ROW_HEIGHT = 28;
const MAX_ROWS = 8;

export function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html('');

  if (!allClaims || allClaims.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No data available yet.</p>');
    return;
  }

  const { scheduled, unscheduled, today, domainStart, domainEnd } = buildHorizonData(allClaims);

  const containerWidth = container.getBoundingClientRect().width || 900;
  const innerW = containerWidth - MARGIN.left - MARGIN.right - 160; // reserve space for unscheduled

  // Stack height: determine max stacks
  const maxStack = d3.max(scheduled, d => d.stack_index) ?? 0;
  const innerH = (Math.min(maxStack + 1, MAX_ROWS) + 2) * DOT_ROW_HEIGHT;
  const svgH = innerH + MARGIN.top + MARGIN.bottom;

  const svg = el.append('svg')
    .attr('class', 'viz-svg')
    .attr('width', containerWidth)
    .attr('height', svgH);

  renderAnnotations(svg, 'Upcoming & recent tariff decisions',
    'Dot size and opacity = certainty. Dashed line = today. Scroll right for unscheduled claims.',
    MARGIN.left, 28);

  const g = svg.append('g').attr('transform', `translate(${MARGIN.left}, ${MARGIN.top})`);

  const x = d3.scaleTime().domain([domainStart, domainEnd]).range([0, innerW]);
  const rScale = certaintyRadius();
  const oScale = certaintyOpacity();

  // Background: shade past vs future
  g.append('rect')
    .attr('x', 0).attr('y', 0)
    .attr('width', x(today))
    .attr('height', innerH)
    .attr('fill', blue(0.025));

  g.append('text')
    .attr('x', 4).attr('y', 12)
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.xs)
    .attr('fill', 'var(--text-tertiary)')
    .text('Past 30 days');

  g.append('text')
    .attr('x', x(today) + 6).attr('y', 12)
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.xs)
    .attr('fill', 'var(--text-secondary)')
    .text('Next 180 days');

  // Today marker
  renderTodayMarker(g, x, innerH);

  // Claim dots
  g.selectAll('.horizon-dot')
    .data(scheduled.filter(d => d.stack_index < MAX_ROWS))
    .join('circle')
    .attr('class', 'horizon-dot')
    .attr('cx', d => x(d.effective_ts))
    .attr('cy', d => (d.stack_index + 0.5) * DOT_ROW_HEIGHT)
    .attr('r', d => rScale(d.certainty_level))
    .attr('fill', d => blue(oScale(d.certainty_level)))
    .style('cursor', 'pointer')
    .on('mousemove', (event, d) => showTooltip(claimTooltipHtml(d), event))
    .on('mouseleave', () => hideTooltip())
    .on('click', (event, d) => {
      if (d.source_url) window.open(d.source_url, '_blank');
    });

  // Date cluster annotation (3+ on same date)
  const byDate = d3.rollup(scheduled, v => v.length, d => d.effective_ts?.toISOString().slice(0, 10));
  for (const [date, count] of byDate) {
    if (count >= 3) {
      g.append('text')
        .attr('x', x(new Date(date)))
        .attr('y', innerH + 4)
        .attr('text-anchor', 'middle')
        .attr('font-family', 'var(--font)')
        .attr('font-size', TYPO.xs)
        .attr('fill', blue(0.7))
        .text(`${count} decisions`);
    }
  }

  // X-axis
  const axisG = g.append('g').attr('transform', `translate(0, ${innerH})`);
  renderTimeAxis(axisG, x, { ticks: 8, format: '%b %d' });

  // Unscheduled panel (right side)
  const unscheduledX = innerW + 20;
  const upanel = g.append('g').attr('transform', `translate(${unscheduledX}, 0)`);
  upanel.append('text')
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.xs)
    .attr('font-weight', '600')
    .attr('fill', 'var(--text-secondary)')
    .text('Unscheduled');

  upanel.selectAll('.unscheduled-dot')
    .data(unscheduled.slice(0, MAX_ROWS))
    .join('g')
    .attr('transform', (d, i) => `translate(0, ${(i + 0.5) * DOT_ROW_HEIGHT})`)
    .call(g => {
      g.append('circle')
        .attr('r', d => rScale(d.certainty_level))
        .attr('fill', d => blue(oScale(d.certainty_level)));
      g.append('text')
        .attr('x', 12)
        .attr('dy', '0.35em')
        .attr('font-family', 'var(--font)')
        .attr('font-size', TYPO.xs)
        .attr('fill', 'var(--text-secondary)')
        .text(d => (d.subject || d.country || '').slice(0, 20));
    })
    .style('cursor', 'pointer')
    .on('mousemove', (event, d) => showTooltip(claimTooltipHtml(d), event))
    .on('mouseleave', () => hideTooltip());
}
