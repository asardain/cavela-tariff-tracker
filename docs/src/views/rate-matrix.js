/**
 * rate-matrix.js — View 1: Country × Category Rate Matrix
 *
 * Question: Which countries are tariffed at what rates, by product category?
 *
 * Marks: rect cells (opacity = rate), text labels (rate%), circle (certainty level).
 * export mount(container, data, options?)
 */

import { loadCurrentRates, CATEGORIES } from '../data.js';
import {
  categoryBand, countryBand, renderCells, renderAnnotations, renderBandAxis,
  showTooltip, claimTooltipHtml, TYPO, blue,
} from '../marks.js';

const MARGIN = { top: 80, right: 40, bottom: 120, left: 120 };
const CELL_MIN = 44;

export async function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html('');

  // Load the curated current-rates data (pre-calculated totals per country/sector)
  const matrix = await loadCurrentRates();

  if (matrix.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No rate data found.</p><small>Current rates data file could not be loaded.</small>');
    return;
  }

  // Derive axis domains
  const countries = [...new Set(matrix.map(d => d.country))].sort();
  const categories = [...new Set(matrix.map(d => d.category))].sort();

  const containerWidth = container.getBoundingClientRect().width || 900;
  const cellW = Math.max(CELL_MIN, Math.floor((containerWidth - MARGIN.left - MARGIN.right) / categories.length));
  const cellH = CELL_MIN;

  const width = categories.length * cellW;
  const height = countries.length * cellH;
  const svgW = width + MARGIN.left + MARGIN.right;
  const svgH = height + MARGIN.top + MARGIN.bottom;

  const svg = el.append('svg')
    .attr('class', 'viz-svg')
    .attr('width', svgW)
    .attr('height', svgH);

  const g = svg.append('g')
    .attr('transform', `translate(${MARGIN.left}, ${MARGIN.top})`);

  // Scales
  const x = d3.scaleBand().domain(categories).range([0, width]).padding(0.08);
  const y = d3.scaleBand().domain(countries).range([0, height]).padding(0.12);

  // Annotations
  renderAnnotations(svg, 'Current confirmed tariff rates by country and product',
    'Showing announced, executive order, and enacted tariffs only. Cell opacity = rate magnitude.',
    MARGIN.left, 28);

  // Column headers (categories)
  g.append('g').attr('class', 'col-headers')
    .selectAll('.col-label')
    .data(categories)
    .join('text')
    .attr('class', 'col-label')
    .attr('x', d => x(d) + x.bandwidth() / 2)
    .attr('y', -12)
    .attr('text-anchor', 'middle')
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.xs)
    .attr('font-weight', '500')
    .attr('fill', 'var(--text-secondary)')
    .text(d => d);

  // Row headers (countries) — left axis
  g.append('g').attr('class', 'row-headers')
    .selectAll('.row-label')
    .data(countries)
    .join('text')
    .attr('class', 'row-label')
    .attr('x', -10)
    .attr('y', d => y(d) + y.bandwidth() / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'end')
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.sm)
    .attr('fill', 'var(--text)')
    .text(d => d);

  // Cells
  renderCells(g, matrix, { x, y }, {
    onHover: (d, event) => showTooltip(claimTooltipHtml(d), event),
    onClick: (d) => {
      window.open(d.source_url, '_blank');
    },
  });

}
