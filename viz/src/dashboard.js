/**
 * dashboard.js — Composition layer
 *
 * Wires data loading, tab navigation, and view mounting together.
 * Single entry point for the dashboard.
 */

import { loadAllAvailableData } from './data.js';
import { mount as mountAlertFeed } from './views/alert-feed.js';
import { mount as mountRateMatrix } from './views/rate-matrix.js';
import { mount as mountCountryTimeline } from './views/country-timeline.js';
import { mount as mountHorizonScanner } from './views/horizon-scanner.js';
import { mount as mountSourcingCompare } from './views/sourcing-compare.js';

// ---------------------------------------------------------------------------
// View registry
// ---------------------------------------------------------------------------

const VIEWS = [
  { id: 'alerts',   label: 'This Week',      mount: mountAlertFeed },
  { id: 'rates',    label: 'Current Rates',  mount: mountRateMatrix },
  { id: 'timeline', label: 'History',        mount: mountCountryTimeline },
  { id: 'horizon',  label: 'Horizon',        mount: mountHorizonScanner },
  { id: 'sourcing', label: 'Alternatives',   mount: mountSourcingCompare },
];

// ---------------------------------------------------------------------------
// Shell setup
// ---------------------------------------------------------------------------

function buildShell() {
  const app = document.getElementById('app');
  if (!app) return;

  // Header
  const header = document.createElement('header');
  header.className = 'app-header';
  header.innerHTML = `
    <div>
      <div class="app-title">Cavela Tariff Tracker</div>
      <div class="app-subtitle">Live tariff intelligence for sourcing teams</div>
    </div>
    <div id="data-status" style="font-size:11px;color:var(--text-secondary);">Loading data...</div>
  `;
  app.appendChild(header);

  // Tab bar
  const tabBar = document.createElement('nav');
  tabBar.className = 'tab-bar';
  VIEWS.forEach(view => {
    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.dataset.view = view.id;
    btn.textContent = view.label;
    tabBar.appendChild(btn);
  });
  app.appendChild(tabBar);

  // View container
  const viewContainer = document.createElement('div');
  viewContainer.className = 'view-container';
  VIEWS.forEach(view => {
    const panel = document.createElement('div');
    panel.className = 'view-panel';
    panel.id = `panel-${view.id}`;
    viewContainer.appendChild(panel);
  });
  app.appendChild(viewContainer);
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------

function activateView(viewId, allClaims, mountedViews) {
  // Update tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewId);
  });

  // Show/hide panels
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `panel-${viewId}`);
  });

  // Mount view if not yet mounted
  if (!mountedViews.has(viewId)) {
    const view = VIEWS.find(v => v.id === viewId);
    if (view) {
      const panel = document.getElementById(`panel-${viewId}`);
      panel.innerHTML = '<div class="loading">Rendering...</div>';
      requestAnimationFrame(() => {
        panel.innerHTML = '';
        try {
          view.mount(panel, allClaims);
        } catch (err) {
          panel.innerHTML = `<div class="empty-state"><p>Render error</p><small>${err.message}</small></div>`;
          console.error(`[dashboard] Error mounting view "${viewId}":`, err);
        }
        mountedViews.add(viewId);
      });
    }
  }
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

async function bootstrap() {
  buildShell();

  // Load data
  let allClaims = [];
  try {
    allClaims = await loadAllAvailableData();
  } catch (err) {
    console.warn('[dashboard] Data load failed:', err);
  }

  // Update status
  const statusEl = document.getElementById('data-status');
  if (statusEl) {
    if (allClaims.length === 0) {
      statusEl.textContent = 'No data yet — run the pipeline to populate.';
    } else {
      const dates = allClaims.map(c => c.published_ts).filter(Boolean);
      const latest = new Date(Math.max(...dates));
      statusEl.textContent = `${allClaims.length.toLocaleString()} claims · Last updated ${latest.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
    }
  }

  const mountedViews = new Set();

  // Wire up tab clicks
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activateView(btn.dataset.view, allClaims, mountedViews);
    });
  });

  // Activate first view
  activateView(VIEWS[0].id, allClaims, mountedViews);
}

// Entry point
document.addEventListener('DOMContentLoaded', bootstrap);
