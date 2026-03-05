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

function actionPillStyle(tariff_action) {
  if (['new_tariff', 'tariff_increase'].includes(tariff_action)) {
    return { background: '#fee2e2', color: '#991b1b' };
  }
  if (['tariff_removal', 'tariff_pause'].includes(tariff_action)) {
    return { background: '#dcfce7', color: '#166534' };
  }
  return { background: '#f3f4f6', color: '#374151' };
}

function certBucket(level) {
  if (level <= 2) return { label: 'Speculative', bg: '#f3f4f6', color: '#6b7280' };
  if (level <= 4) return { label: 'Likely',      bg: '#fef3c7', color: '#92400e' };
  return              { label: 'Confirmed',    bg: '#dbeafe', color: '#1e40af' };
}

export function mount(container, allClaims, options = {}) {
  const el = d3.select(container);
  el.html(''); // clear

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
          tr.classed('anomaly', d => d.is_anomaly);

          // Date
          tr.append('td').attr('class', 'alert-date')
            .text(d => d.published_ts.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));

          // Subject + claim text
          const subjectTd = tr.append('td');
          subjectTd.append('div').attr('class', 'alert-subject').text(d => d.subject || d.country);
          subjectTd.append('div').attr('class', 'alert-claim-detail').text(d => d.claim_text);

          // Action badge
          tr.append('td').append('span').attr('class', 'action-badge')
            .text(d => d.action_label || '—')
            .each(function(d) {
              const s = actionPillStyle(d.tariff_action);
              d3.select(this).style('background', s.background).style('color', s.color);
            });

          // Certainty bucket badge
          const certTd = tr.append('td');
          certTd.append('span').attr('class', 'certainty-label-text')
            .each(function(d) {
              const b = certBucket(d.certainty_level);
              d3.select(this)
                .text(b.label)
                .style('background', b.bg)
                .style('color', b.color)
                .style('padding', '2px 8px')
                .style('border-radius', '9999px')
                .style('font-size', '0.75em')
                .style('font-weight', '500');
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
