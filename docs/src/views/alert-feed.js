/**
 * alert-feed.js — View 5: This Week's Alerts
 *
 * Question: What happened this week? Is there unusual activity?
 *
 * Marks: structured feed rows with certainty bars, action badges, sparklines.
 * export mount(container, data, options?)
 */

import { buildAlertFeed, ACTION_LABELS, CATEGORIES, uniqueValues } from '../data.js';
import { blue, TYPO, showTooltip, hideTooltip, claimTooltipHtml } from '../marks.js';

const CERTAINTY_BAR_MAX = 70; // px at level 7

const FLAG = {
  'China': '🇨🇳', 'Vietnam': '🇻🇳', 'Mexico': '🇲🇽', 'Bangladesh': '🇧🇩',
  'India': '🇮🇳', 'Cambodia': '🇰🇭', 'Indonesia': '🇮🇩', 'Thailand': '🇹🇭',
  'Sri Lanka': '🇱🇰', 'Pakistan': '🇵🇰', 'Turkey': '🇹🇷', 'Brazil': '🇧🇷',
  'South Korea': '🇰🇷', 'Taiwan': '🇹🇼', 'Japan': '🇯🇵', 'Germany': '🇩🇪',
  'Canada': '🇨🇦', 'Malaysia': '🇲🇾', 'Philippines': '🇵🇭', 'Ethiopia': '🇪🇹',
  'Honduras': '🇭🇳', 'Guatemala': '🇬🇹', 'El Salvador': '🇸🇻',
  'EU': '🇪🇺', 'European Union': '🇪🇺', 'United Kingdom': '🇬🇧', 'UK': '🇬🇧',
};

function countryDisplay(country) {
  if (!country || country === 'Unknown') return 'Multiple';
  const flag = FLAG[country] || '';
  return flag ? `${country}${flag}` : country;
}

function pillClass(tariff_action) {
  if (['new_tariff', 'tariff_increase'].includes(tariff_action)) return 'pill-red';
  if (['tariff_removal', 'tariff_pause'].includes(tariff_action)) return 'pill-green';
  return 'pill-gray';
}

function pillTextColor(tariff_action) {
  if (['new_tariff', 'tariff_increase'].includes(tariff_action)) return 'var(--pill-red-text)';
  if (['tariff_removal', 'tariff_pause'].includes(tariff_action)) return 'var(--pill-green-text)';
  return 'var(--text-secondary)';
}

function certDots(level, tariff_action) {
  const filled = level <= 2 ? 1 : level <= 4 ? 2 : 3;
  const label = level <= 2 ? 'Speculative' : level <= 4 ? 'Likely' : 'Confirmed';
  const color = pillTextColor(tariff_action);
  const dots = [1, 2, 3].map(i =>
    `<span style="color:${i <= filled ? color : 'var(--dot-empty)'}; font-size:10px;">●</span>`
  ).join('');
  return `<span title="${label}" style="letter-spacing:2px">${dots}</span>`;
}

export function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html(''); // clear

  // ---- Hover tooltip
  let tooltipTimeout = null;
  const tooltip = d3.select('body').append('div')
    .attr('id', 'feed-tooltip')
    .style('position', 'fixed')
    .style('display', 'none')
    .style('border-radius', '4px')
    .style('padding', '12px 16px')
    .style('max-width', '360px')
    .style('font-size', '13px')
    .style('line-height', '1.5')
    .style('z-index', '100')
    .style('pointer-events', 'auto');

  let hideTimeout = null;
  tooltip
    .on('mouseenter', () => clearTimeout(hideTimeout))
    .on('mouseleave', () => { hideTimeout = setTimeout(() => tooltip.style('display', 'none'), 150); });

  if (!allClaims || allClaims.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No data available yet.</p><small>Run the pipeline to generate daily claim files.</small>');
    return;
  }

  const { claims } = buildAlertFeed(allClaims, options.weeks || 2);

  // Filter state
  let activeCountry = 'All';
  let activeAction = 'All';

  // ---- Header
  const header = el.append('div').attr('class', 'view-header');
  header.append('div').attr('class', 'view-title').text('This Week in Tariffs');
  header.append('div').attr('class', 'view-subtitle')
    .text('Sorted by date, newest first. Highlighted rows show elevated activity.');

  // ---- Filter bar
  const filterBar = el.append('div').attr('class', 'filter-bar');
  filterBar.append('span').attr('class', 'filter-label').text('Country:');

  const countries = ['All', ...uniqueValues(claims, 'country').filter(c => c !== 'Unknown')];
  countries.forEach(c => {
    filterBar.append('button')
      .attr('class', `filter-pill${c === activeCountry ? ' active' : ''}`)
      .attr('data-country', c)
      .text(c)
      .on('click', function() {
        activeCountry = c;
        d3.selectAll('[data-country]').classed('active', false);
        d3.select(this).classed('active', true);
        renderTable();
      });
  });

  filterBar.append('span').attr('class', 'filter-label').style('margin-left', '16px').text('Action:');
  const actions = ['All', ...Object.keys(ACTION_LABELS)];
  const actionSelect = filterBar.append('select').attr('class', 'filter-select')
    .on('change', function() {
      activeAction = this.value;
      renderTable();
    });
  actions.forEach(a => {
    actionSelect.append('option').attr('value', a).text(a === 'All' ? 'All actions' : ACTION_LABELS[a]);
  });

  // ---- Table container
  const tableWrap = el.append('div').style('overflow-x', 'auto');
  const table = tableWrap.append('table').attr('class', 'alert-feed-table');
  const thead = table.append('thead').append('tr');
  thead.append('th').text('Date');
  thead.append('th').text('Subject / Claim');
  thead.append('th').text('Country');
  thead.append('th').text('Action');
  thead.append('th').text('Certainty');

  const tbody = table.append('tbody');

  function renderTable() {
    let filtered = claims;
    if (activeCountry !== 'All') filtered = filtered.filter(c => c.country === activeCountry);
    if (activeAction !== 'All') filtered = filtered.filter(c => c.tariff_action === activeAction);

    const rows = tbody.selectAll('.alert-row')
      .data(filtered.slice(0, 50), d => d.claim_id)
      .join(
        enter => {
          const tr = enter.append('tr').attr('class', 'alert-row');

          // Date
          tr.append('td').attr('class', 'alert-date')
            .text(d => d.published_ts.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));

          // Subject + claim text
          const subjectTd = tr.append('td');
          subjectTd.append('div').attr('class', 'alert-subject').text(d => d.subject || d.country);
          subjectTd.append('div').attr('class', 'alert-claim-detail').text(d => d.claim_text);

          // Country
          tr.append('td').attr('class', 'alert-country-col')
            .text(d => countryDisplay(d.country));

          // Action badge
          tr.append('td').append('span')
            .attr('class', d => `action-badge ${pillClass(d.tariff_action)}`)
            .text(d => d.action_label || '—');

          // Certainty dot indicators
          const certTd = tr.append('td');
          certTd.append('span').attr('class', 'certainty-dots')
            .each(function(d) {
              d3.select(this).html(certDots(d.certainty_level, d.tariff_action));
            });

          return tr;
        },
        update => update,
        exit => exit.remove()
      )
      .classed('anomaly', d => d.is_anomaly);

    // Hover tooltip (replaces click-expand)
    rows.on('mouseenter', function(event, d) {
      clearTimeout(tooltipTimeout);
      const rect = this.getBoundingClientRect();
      tooltipTimeout = setTimeout(() => {
        const sourceLine = d.source_name
          ? (d.source_url
              ? `<a href="${d.source_url}" target="_blank">${d.source_name}</a>`
              : d.source_name)
          : '—';
        const dateLine = d.effective_date
          ? `<div style="margin-top:6px;color:var(--text-secondary);font-size:12px">Effective: ${d.effective_date}</div>`
          : '';
        tooltip
          .style('display', 'block')
          .style('left', `${Math.min(rect.left, window.innerWidth - 380)}px`)
          .style('top', `${rect.bottom + 8}px`)
          .html(`
            <div style="font-weight:500;margin-bottom:4px;color:var(--text-body)">${d.claim_text || '—'}</div>
            <div style="color:var(--text-secondary);font-size:12px">Source: ${sourceLine}</div>
            ${dateLine}
          `);
      }, 300);
    }).on('mouseleave', function() {
      clearTimeout(tooltipTimeout);
      hideTimeout = setTimeout(() => tooltip.style('display', 'none'), 150);
    });
  }

  renderTable();
}
