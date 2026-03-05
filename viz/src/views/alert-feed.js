/**
 * alert-feed.js — View 5: This Week's Alerts
 *
 * Question: What happened this week? Is there unusual activity?
 *
 * Marks: structured feed rows with certainty bars, action badges, sparklines.
 * export mount(container, data, options?)
 */

import { buildAlertFeed, ACTION_LABELS, CATEGORIES, uniqueValues } from '../data.js';
import { blue, TYPO, renderSparkline, showTooltip, hideTooltip, claimTooltipHtml } from '../marks.js';

const CERTAINTY_BAR_MAX = 70; // px at level 7

export function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html(''); // clear

  if (!allClaims || allClaims.length === 0) {
    el.append('div').attr('class', 'empty-state')
      .html('<p>No data available yet.</p><small>Run the pipeline to generate daily claim files.</small>');
    return;
  }

  const { claims, sparklines } = buildAlertFeed(allClaims, options.weeks || 2);

  // Filter state
  let activeCountry = 'All';
  let activeAction = 'All';
  let showAnomalyOnly = false;

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

  filterBar.append('button')
    .attr('class', 'filter-pill')
    .style('margin-left', '16px')
    .attr('id', 'anomaly-toggle')
    .text('Anomalies only')
    .on('click', function() {
      showAnomalyOnly = !showAnomalyOnly;
      d3.select(this).classed('active', showAnomalyOnly);
      renderTable();
    });

  // ---- Table container
  const tableWrap = el.append('div').style('overflow-x', 'auto');
  const table = tableWrap.append('table').attr('class', 'alert-feed-table');
  const thead = table.append('thead').append('tr');
  thead.append('th').text('Date');
  thead.append('th').text('Subject / Claim');
  thead.append('th').text('Action');
  thead.append('th').text('Certainty');
  thead.append('th').text('Activity (8w)');

  const tbody = table.append('tbody');

  function renderTable() {
    let filtered = claims;
    if (activeCountry !== 'All') filtered = filtered.filter(c => c.country === activeCountry);
    if (activeAction !== 'All') filtered = filtered.filter(c => c.tariff_action === activeAction);
    if (showAnomalyOnly) filtered = filtered.filter(c => c.is_anomaly);

    const rows = tbody.selectAll('.alert-row')
      .data(filtered.slice(0, 50), d => d.claim_id)
      .join(
        enter => {
          const tr = enter.append('tr').attr('class', 'alert-row');
          tr.classed('anomaly', d => d.is_anomaly);

          // Date
          tr.append('td').attr('class', 'alert-date')
            .text(d => d.published_ts.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));

          // Subject + claim text
          const subjectTd = tr.append('td');
          subjectTd.append('div').attr('class', 'alert-subject').text(d => d.subject || d.country);
          subjectTd.append('div').attr('class', 'alert-claim-detail').text(d => d.claim_text);

          // Action badge
          tr.append('td').append('span').attr('class', 'action-badge').text(d => d.action_label || '—');

          // Certainty bar
          const certTd = tr.append('td');
          const barWrap = certTd.append('div').attr('class', 'certainty-bar-wrap');
          barWrap.append('div')
            .attr('class', 'certainty-bar')
            .style('width', d => `${Math.round((d.certainty_level / 7) * CERTAINTY_BAR_MAX)}px`)
            .style('opacity', d => 0.3 + (d.certainty_level / 7) * 0.7);
          barWrap.append('span').attr('class', 'certainty-label-text')
            .text(d => `${d.certainty_label} (${d.certainty_level})`);

          // Sparkline
          const sparkTd = tr.append('td');
          tr.each(function(d) {
            const series = sparklines.get(d.country);
            if (!series || series.length < 2) return;
            const svg = d3.select(this).select('td:last-child')
              .append('svg')
              .attr('width', 100)
              .attr('height', 28);
            const g = svg.append('g').attr('transform', 'translate(0, 4)');
            renderSparkline(g, series, { width: 100, height: 20 });
          });

          return tr;
        },
        update => update,
        exit => exit.remove()
      )
      .classed('anomaly', d => d.is_anomaly);

    // Toggle row expansion on click
    rows.on('click', function(event, d) {
      const row = d3.select(this);
      const expanded = row.classed('expanded');
      tbody.selectAll('.alert-row').classed('expanded', false);
      row.classed('expanded', !expanded);
    });
  }

  renderTable();
}
