/**
 * sourcing-compare.js — View 3: Sourcing Alternatives Comparison
 *
 * Question: If I need to move production from Country X, where should I look?
 *
 * Marks: horizontal bars (rate%), certainty underline, trend arrow, claim count.
 * export mount(container, data, options?)
 */

import { buildSourcingComparison, CATEGORIES } from '../data.js';
import {
  rateScale, countryBand, renderBars, renderAnnotations, renderBandAxis,
  showTooltip, hideTooltip, claimTooltipHtml, blue, TYPO,
} from '../marks.js';

const MARGIN = { top: 100, right: 120, bottom: 40, left: 140 };
const BAR_HEIGHT = 28;

export function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html('');

  if (!allClaims || allClaims.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No data available yet.</p>');
    return;
  }

  const header = el.append('div').attr('class', 'view-header');
  header.append('div').attr('class', 'view-title').text('Sourcing Alternatives by Tariff Rate');
  header.append('div').attr('class', 'view-subtitle')
    .text('Bar length = tariff rate. Opacity = certainty. Arrow = trend direction.');

  // Category filter
  const filterBar = el.append('div').attr('class', 'filter-bar');
  filterBar.append('span').attr('class', 'filter-label').text('Category:');
  const catSelect = filterBar.append('select').attr('class', 'filter-select');
  const allCategories = ['All', ...CATEGORIES.map(c => c.label)];
  allCategories.forEach(c => {
    catSelect.append('option').attr('value', c).text(c);
  });

  // Certainty filter toggle
  let showSpeculative = true;
  const specBtn = filterBar.append('button')
    .attr('class', 'filter-pill active')
    .style('margin-left', '16px')
    .text('Include speculative')
    .on('click', function() {
      showSpeculative = !showSpeculative;
      d3.select(this).classed('active', showSpeculative);
      renderChart(catSelect.property('value'));
    });

  catSelect.on('change', function() {
    renderChart(this.value);
  });

  // Chart container
  const chartDiv = el.append('div');

  function renderChart(category = 'All') {
    chartDiv.html('');

    let data = buildSourcingComparison(allClaims, category);
    if (!showSpeculative) {
      data = data.filter(d => d.certainty_level >= 3);
    }

    if (data.length === 0) {
      chartDiv.append('div').attr('class', 'empty-state')
        .html('<p>No rate data for this category.</p>');
      return;
    }

    const containerWidth = container.getBoundingClientRect().width || 900;
    const innerW = containerWidth - MARGIN.left - MARGIN.right;
    const innerH = data.length * BAR_HEIGHT;
    const svgH = innerH + MARGIN.top + MARGIN.bottom;

    const svg = chartDiv.append('svg')
      .attr('class', 'viz-svg')
      .attr('width', containerWidth)
      .attr('height', svgH);

    const maxRate = d3.max(data, d => d.rate_pct) || 100;
    const x = rateScale(maxRate, [0, innerW]);
    const y = d3.scaleBand()
      .domain(data.map(d => d.country))
      .range([0, innerH])
      .padding(0.2);

    const g = svg.append('g').attr('transform', `translate(${MARGIN.left}, ${MARGIN.top})`);

    // X-axis grid lines (minimal)
    const xTicks = x.ticks(5);
    g.append('g').attr('class', 'x-grid')
      .selectAll('.grid-line')
      .data(xTicks)
      .join('line')
      .attr('x1', d => x(d)).attr('x2', d => x(d))
      .attr('y1', 0).attr('y2', innerH)
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', 1);

    // X-axis labels
    g.append('g')
      .attr('transform', `translate(0, ${innerH + 8})`)
      .selectAll('.x-label')
      .data(xTicks)
      .join('text')
      .attr('x', d => x(d))
      .attr('text-anchor', 'middle')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.xs)
      .attr('fill', 'var(--text-secondary)')
      .text(d => `${d}%`);

    // Country labels (left)
    g.append('g')
      .selectAll('.country-label')
      .data(data)
      .join('text')
      .attr('class', 'country-label')
      .attr('x', -10)
      .attr('y', d => y(d.country) + y.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.sm)
      .attr('fill', 'var(--text)')
      .text(d => d.country);

    // Bars
    renderBars(g, data, { x, y }, {
      showTrend: true,
      onHover: (d, event) => {
        const html = `
          <strong>${d.country} — ${category === 'All' ? 'All Categories' : category}</strong>
          <div class="tooltip-meta">
            Rate: ${d.rate_pct}% &middot; Certainty: Level ${d.certainty_level}<br>
            Claims: ${d.claim_count} &middot; Trend: ${d.trend}<br>
            ${d.latest_claim}
          </div>
        `;
        showTooltip(html, event);
      },
    });

    // Claim count (right of bars)
    g.selectAll('.claim-count')
      .data(data)
      .join('text')
      .attr('class', 'claim-count')
      .attr('x', innerW + 8)
      .attr('y', d => y(d.country) + y.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.xs)
      .attr('fill', 'var(--text-secondary)')
      .text(d => `${d.claim_count} claim${d.claim_count !== 1 ? 's' : ''}`);
  }

  renderChart('All');
}
