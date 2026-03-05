/**
 * marks.js — Reusable D3 mark primitives and scale factories
 *
 * Each mark is a function that takes a D3 selection and data, returns nothing.
 * Scales are pure factory functions.
 * No side effects outside of SVG mutations.
 */

// ---------------------------------------------------------------------------
// Color / typography constants
// ---------------------------------------------------------------------------

export const BLUE = '#2563eb';
export const BLUE_RGB = [37, 99, 235];
export const TYPO = { xs: 11, sm: 13, base: 16, lg: 20, xl: 25 };

/** Produce rgba string for the single blue hue at given opacity */
export const blue = (opacity = 1) =>
  `rgba(${BLUE_RGB[0]}, ${BLUE_RGB[1]}, ${BLUE_RGB[2]}, ${opacity})`;

// ---------------------------------------------------------------------------
// Scale factories
// ---------------------------------------------------------------------------

/** Time scale for x-axis */
export function timeScale(domain, range) {
  return d3.scaleTime().domain(domain).range(range);
}

/** Linear scale for rate percentages -> pixel width */
export function rateScale(maxRate, range) {
  return d3.scaleLinear().domain([0, maxRate]).range(range).clamp(true);
}

/** Sqrt scale for certainty -> circle radius */
export function certaintyRadius() {
  return d3.scaleSqrt().domain([1, 7]).range([2, 8]).clamp(true);
}

/** Linear scale for certainty -> opacity */
export function certaintyOpacity() {
  return d3.scaleLinear().domain([1, 7]).range([0.2, 1.0]).clamp(true);
}

/** Linear scale for rate -> opacity (for matrix cells) */
export function rateOpacity(maxRate) {
  return d3.scaleLinear().domain([0, maxRate]).range([0.08, 0.85]).clamp(true);
}

/** Band scale for categories (columns) */
export function categoryBand(categories, width, padding = 0.1) {
  return d3.scaleBand()
    .domain(categories)
    .range([0, width])
    .padding(padding);
}

/** Band scale for countries (rows) */
export function countryBand(countries, height, padding = 0.15) {
  return d3.scaleBand()
    .domain(countries)
    .range([0, height])
    .padding(padding);
}

// ---------------------------------------------------------------------------
// Tooltip (singleton, shared across views)
// ---------------------------------------------------------------------------

let _tooltip = null;

export function getTooltip() {
  if (!_tooltip) {
    _tooltip = d3.select('body')
      .append('div')
      .attr('class', 'viz-tooltip')
      .style('opacity', 0);
  }
  return _tooltip;
}

export function showTooltip(html, event) {
  const tt = getTooltip();
  const x = event.clientX + 14;
  const y = event.clientY - 10;
  tt
    .html(html)
    .style('left', `${Math.min(x, window.innerWidth - 340)}px`)
    .style('top', `${y}px`)
    .classed('visible', true)
    .style('opacity', 1);
}

export function hideTooltip() {
  getTooltip().classed('visible', false).style('opacity', 0);
}

// ---------------------------------------------------------------------------
// Mark: dot (positioned circle with certainty encoding)
// ---------------------------------------------------------------------------

/**
 * Render dots into a g selection.
 * @param {d3.Selection} container - parent g element
 * @param {object[]} data - array of { cx, cy, certainty_level, ...claim }
 * @param {object} opts - { onHover, onClick }
 */
export function renderDots(container, data, opts = {}) {
  const rScale = certaintyRadius();
  const oScale = certaintyOpacity();

  const dots = container.selectAll('.dot')
    .data(data, d => d.claim_id)
    .join(
      enter => enter.append('circle').attr('class', 'dot').attr('r', 0),
      update => update,
      exit => exit.remove()
    )
    .attr('cx', d => d.cx)
    .attr('cy', d => d.cy)
    .attr('r', d => rScale(d.certainty_level))
    .attr('fill', d => blue(oScale(d.certainty_level)))
    .style('cursor', opts.onClick ? 'pointer' : 'default');

  if (opts.onHover) {
    dots.on('mousemove', (event, d) => opts.onHover(d, event))
        .on('mouseleave', () => hideTooltip());
  }
  if (opts.onClick) {
    dots.on('click', (event, d) => opts.onClick(d, event));
  }

  return dots;
}

// ---------------------------------------------------------------------------
// Mark: bar (horizontal bar with label)
// ---------------------------------------------------------------------------

/**
 * Render horizontal bars into a g selection.
 * @param {d3.Selection} container
 * @param {object[]} data - array of { country, rate_pct, certainty_level, ... }
 * @param {object} scales - { x: rateScale, y: countryBand }
 * @param {object} opts
 */
export function renderBars(container, data, scales, opts = {}) {
  const { x, y } = scales;
  const oScale = certaintyOpacity();
  const barH = y.bandwidth();

  const groups = container.selectAll('.bar-group')
    .data(data, d => d.country)
    .join('g')
    .attr('class', 'bar-group')
    .attr('transform', d => `translate(0, ${y(d.country)})`);

  // Background rect for hover area
  groups.selectAll('.bar-bg')
    .data(d => [d])
    .join('rect')
    .attr('class', 'bar-bg')
    .attr('x', 0)
    .attr('width', x.range()[1])
    .attr('height', barH)
    .attr('fill', 'transparent');

  // Main bar
  groups.selectAll('.bar-fill')
    .data(d => [d])
    .join('rect')
    .attr('class', 'bar-fill')
    .attr('x', 0)
    .attr('y', Math.floor(barH * 0.2))
    .attr('height', Math.ceil(barH * 0.6))
    .attr('width', d => x(d.rate_pct ?? 0))
    .attr('fill', d => blue(oScale(d.certainty_level)));

  // Rate label at end of bar
  groups.selectAll('.bar-label')
    .data(d => [d])
    .join('text')
    .attr('class', 'bar-label')
    .attr('x', d => x(d.rate_pct ?? 0) + 6)
    .attr('y', barH / 2)
    .attr('dy', '0.35em')
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.sm)
    .attr('fill', 'var(--text)')
    .text(d => d.rate_pct !== null ? `${d.rate_pct}%` : '—');

  // Trend arrow
  if (opts.showTrend) {
    groups.selectAll('.bar-trend')
      .data(d => [d])
      .join('text')
      .attr('class', 'bar-trend')
      .attr('x', d => x(d.rate_pct ?? 0) + (d.rate_pct !== null ? 36 : 16))
      .attr('y', barH / 2)
      .attr('dy', '0.35em')
      .attr('font-size', TYPO.sm)
      .attr('fill', d =>
        d.trend === 'up' ? '#dc2626' :
        d.trend === 'down' ? '#16a34a' : '#6b7280'
      )
      .text(d =>
        d.trend === 'up' ? '↑' : d.trend === 'down' ? '↓' : '—'
      );
  }

  // Hover / click
  if (opts.onHover) {
    groups.on('mousemove', (event, d) => opts.onHover(d, event))
          .on('mouseleave', () => hideTooltip());
  }
  if (opts.onClick) {
    groups.style('cursor', 'pointer')
          .on('click', (event, d) => opts.onClick(d, event));
  }

  return groups;
}

// ---------------------------------------------------------------------------
// Mark: matrix cell
// ---------------------------------------------------------------------------

/**
 * Render rate matrix cells.
 * @param {d3.Selection} container
 * @param {object[]} data - array of { country, category, rate_pct, certainty_level, ... }
 * @param {object} scales - { x: categoryBand, y: countryBand }
 * @param {object} opts
 */
export function renderCells(container, data, scales, opts = {}) {
  const { x, y } = scales;
  const maxRate = d3.max(data, d => d.rate_pct) || 100;
  const opScale = rateOpacity(maxRate);
  const rScale = certaintyRadius();
  const cellW = x.bandwidth();
  const cellH = y.bandwidth();

  const groups = container.selectAll('.cell-group')
    .data(data, d => `${d.country}|||${d.category}`)
    .join('g')
    .attr('class', 'cell-group')
    .attr('transform', d => `translate(${x(d.category)}, ${y(d.country)})`);

  // Cell rect
  groups.selectAll('.cell-rect')
    .data(d => [d])
    .join('rect')
    .attr('class', 'cell-rect')
    .attr('width', cellW - 2)
    .attr('height', cellH - 2)
    .attr('rx', 3)
    .attr('fill', d => blue(opScale(d.rate_pct ?? 0)));

  // Rate label
  groups.selectAll('.cell-rate')
    .data(d => [d])
    .join('text')
    .attr('class', 'cell-rate')
    .attr('x', (cellW - 2) / 2)
    .attr('y', (cellH - 2) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'middle')
    .attr('font-family', 'var(--font)')
    .attr('font-size', TYPO.xs)
    .attr('font-weight', '600')
    .attr('fill', d => d.rate_pct && d.rate_pct > 50 ? blue(1) : 'var(--text)')
    .text(d => d.rate_pct !== null ? `${d.rate_pct}%` : '');

  // Certainty dot (bottom-right corner)
  groups.selectAll('.cell-certainty')
    .data(d => [d])
    .join('circle')
    .attr('class', 'cell-certainty')
    .attr('cx', cellW - 8)
    .attr('cy', cellH - 8)
    .attr('r', d => rScale(d.certainty_level))
    .attr('fill', d => blue(0.9));

  // Trend arrow (top-right corner)
  groups.selectAll('.cell-trend')
    .data(d => [d])
    .join('text')
    .attr('class', 'cell-trend')
    .attr('x', cellW - 4)
    .attr('y', 10)
    .attr('text-anchor', 'end')
    .attr('font-size', 9)
    .attr('font-weight', '700')
    .attr('fill', d =>
      d.trend === 'up' ? '#dc2626' :
      d.trend === 'down' ? '#16a34a' : '#6b7280'
    )
    .text(d =>
      d.trend === 'up' ? '↑' : d.trend === 'down' ? '↓' : '—'
    );

  // Hover / click
  if (opts.onHover) {
    groups.style('cursor', 'pointer')
          .on('mousemove', (event, d) => opts.onHover(d, event))
          .on('mouseleave', () => hideTooltip());
  }
  if (opts.onClick) {
    groups.on('click', (event, d) => opts.onClick(d, event));
  }

  return groups;
}

// ---------------------------------------------------------------------------
// Mark: sparkline (mini line chart)
// ---------------------------------------------------------------------------

/**
 * Render a sparkline into a g element.
 * @param {d3.Selection} container - single g element
 * @param {object[]} data - [ { week: Date, count: number }, ... ]
 * @param {object} dims - { width, height }
 */
export function renderSparkline(container, data, dims) {
  if (!data || data.length < 2) return;

  const { width, height } = dims;
  const x = d3.scaleTime()
    .domain(d3.extent(data, d => d.week))
    .range([0, width]);
  const y = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.count) || 1])
    .range([height, 0]);

  const line = d3.line()
    .x(d => x(d.week))
    .y(d => y(d.count))
    .curve(d3.curveMonotoneX);

  container.selectAll('.sparkline-path')
    .data([data])
    .join('path')
    .attr('class', 'sparkline-path')
    .attr('d', line)
    .attr('fill', 'none')
    .attr('stroke', blue(0.5))
    .attr('stroke-width', 1.5);
}

// ---------------------------------------------------------------------------
// Axes helpers
// ---------------------------------------------------------------------------

/** Render a simple bottom time axis */
export function renderTimeAxis(g, scale, opts = {}) {
  const axis = d3.axisBottom(scale)
    .ticks(opts.ticks || 6)
    .tickSize(opts.tickSize || 4)
    .tickFormat(d3.timeFormat(opts.format || '%b %Y'));

  g.call(axis)
    .call(g => g.select('.domain').attr('stroke', 'var(--border)'))
    .call(g => g.selectAll('.tick line').attr('stroke', 'var(--border)'))
    .call(g => g.selectAll('.tick text')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.xs)
      .attr('fill', 'var(--text-secondary)'));
}

/** Render a simple left band axis */
export function renderBandAxis(g, scale, opts = {}) {
  const axis = d3.axisLeft(scale).tickSize(0);
  g.call(axis)
    .call(g => g.select('.domain').remove())
    .call(g => g.selectAll('.tick text')
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.sm)
      .attr('fill', 'var(--text)')
      .attr('dx', -8));
  if (opts.onClick) {
    g.selectAll('.tick text').style('cursor', 'pointer')
      .on('click', (event, d) => opts.onClick(d));
  }
}

/** Render a "today" reference line */
export function renderTodayMarker(g, x, height) {
  const today = new Date();
  const tx = x(today);
  g.append('line')
    .attr('x1', tx).attr('x2', tx)
    .attr('y1', 0).attr('y2', height)
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

/** Render chart title + subtitle annotations */
export function renderAnnotations(container, title, subtitle, x = 0, y = 0) {
  if (title) {
    container.append('text')
      .attr('x', x).attr('y', y)
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.lg)
      .attr('font-weight', '600')
      .attr('fill', 'var(--text)')
      .text(title);
  }
  if (subtitle) {
    container.append('text')
      .attr('x', x).attr('y', y + TYPO.lg + 4)
      .attr('font-family', 'var(--font)')
      .attr('font-size', TYPO.sm)
      .attr('fill', 'var(--text-secondary)')
      .text(subtitle);
  }
}

// ---------------------------------------------------------------------------
// Tooltip HTML builders
// ---------------------------------------------------------------------------

export function claimTooltipHtml(claim) {
  const date = claim.published_ts
    ? claim.published_ts.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '';
  return `
    <strong>${claim.claim_text}</strong>
    <div class="tooltip-meta">
      ${claim.certainty_label} (Level ${claim.certainty_level}) &middot; ${claim.source_name}<br>
      ${claim.action_label} &middot; ${claim.country} &middot; ${claim.category}<br>
      ${date}
    </div>
  `;
}
