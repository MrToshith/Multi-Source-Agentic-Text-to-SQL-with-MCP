const API_BASE = window.location.protocol === 'file:' || (window.location.port && window.location.port !== '8000')
  ? 'http://localhost:8000'
  : '';

let currentSessionId = 'sess-' + Math.random().toString(36).substring(2, 8);
let activeChart = null;

const SOURCE_LABELS = {
  sales_pg: 'PostgreSQL (sales_pg)',
  crm_mssql: 'SQL Server T-SQL (crm_mssql)',
  analytics_duckdb: 'DuckDB CSV (analytics_duckdb)',
};

function formatMarkdownBold(text) {
  if (!text) return '';
  return text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

function updateSessionBadge() {
  const el = document.getElementById('session-id-label');
  if (el) el.textContent = currentSessionId;
}

async function checkHealth() {
  const dot = document.getElementById('health-dot');
  const text = document.getElementById('health-text');
  const sourcesContainer = document.getElementById('mcp-sources-badges');

  try {
    const resp = await fetch(`${API_BASE}/health`);
    const data = await resp.json();
    dot.classList.remove('offline');
    text.textContent = `MCP Online (${data.mcp_sources_count} Sources)`;
    sourcesContainer.innerHTML = (data.mcp_sources || [])
      .map(s => `<span class="badge">${s}</span>`)
      .join('');
  } catch (err) {
    dot.classList.add('offline');
    text.textContent = 'Backend Offline (Start uvicorn on :8000)';
  }
}

function appendChatMessage(role, htmlContent, isClarification = false) {
  const stream = document.getElementById('chat-stream');
  const div = document.createElement('div');

  if (isClarification) {
    div.className = 'msg msg-clarification';
    div.innerHTML = `<div class="clarification-title">Clarification Guard Interrupt</div><div>${formatMarkdownBold(htmlContent)}</div>`;
  } else if (role === 'user') {
    div.className = 'msg msg-user';
    div.textContent = htmlContent;
  } else {
    div.className = 'msg msg-assistant';
    div.innerHTML = formatMarkdownBold(htmlContent);
  }

  stream.appendChild(div);
  stream.scrollTop = stream.scrollHeight;
}

function renderSQLQueries(sqlQueries) {
  const container = document.getElementById('sql-cards-container');
  const entries = Object.entries(sqlQueries || {});

  if (entries.length === 0) {
    container.innerHTML = `<div class="empty-placeholder">No SQL queries executed in this turn (waiting for query or clarification).</div>`;
    return;
  }

  container.innerHTML = entries
    .map(([source, sql]) => {
      const label = SOURCE_LABELS[source] || source;
      return `
        <div class="sql-card">
          <div class="sql-source-badge">
            <span>${label}</span>
            <span>READ-ONLY AST VERIFIED</span>
          </div>
          <pre class="sql-code">${sql}</pre>
        </div>
      `;
    })
    .join('');
}

function renderDataTable(rows) {
  const container = document.getElementById('table-container');
  if (!rows || rows.length === 0) {
    container.innerHTML = `<div class="empty-placeholder">No tabular rows to display yet.</div>`;
    return;
  }

  const columns = Object.keys(rows[0]);
  const thead = `<thead><tr>${columns.map(c => `<th>${c}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${rows
    .map(
      row =>
        `<tr>${columns
          .map(col => {
            const val = row[col];
            if (typeof val === 'number' && !Number.isInteger(val)) {
              return `<td>${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>`;
            }
            return `<td>${val !== null && val !== undefined ? val : ''}</td>`;
          })
          .join('')}</tr>`
    )
    .join('')}</tbody>`;

  container.innerHTML = `<div class="table-wrapper"><table>${thead}${tbody}</table></div>`;
}

function renderChart(vizConfig) {
  const wrapper = document.getElementById('chart-wrapper');
  if (!vizConfig || !vizConfig.data || vizConfig.data.length === 0 || !vizConfig.y_axes || vizConfig.y_axes.length === 0) {
    if (activeChart) {
      activeChart.destroy();
      activeChart = null;
    }
    wrapper.innerHTML = `<div class="empty-placeholder">Chart visualization will appear after query execution.</div>`;
    return;
  }

  wrapper.innerHTML = `<canvas id="results-chart"></canvas>`;
  const ctx = document.getElementById('results-chart').getContext('2d');

  const labels = vizConfig.data.map(r => String(r[vizConfig.x_axis] ?? ''));
  const palette = [
    { bg: 'rgba(59, 130, 246, 0.75)', border: '#3b82f6' },
    { bg: 'rgba(244, 63, 94, 0.75)', border: '#f43f5e' },
    { bg: 'rgba(16, 185, 129, 0.75)', border: '#10b981' },
  ];

  const datasets = vizConfig.y_axes.map((yCol, idx) => {
    const color = palette[idx % palette.length];
    return {
      label: yCol,
      data: vizConfig.data.map(r => Number(r[yCol] || 0)),
      backgroundColor: color.bg,
      borderColor: color.border,
      borderWidth: 1,
      borderRadius: 5,
      yAxisID: idx === 0 ? 'y' : 'y1',
    };
  });

  const scales = {
    x: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(55, 65, 81, 0.35)' } },
    y: {
      type: 'linear',
      position: 'left',
      ticks: { color: '#9ca3af' },
      grid: { color: 'rgba(55, 65, 81, 0.35)' },
    },
  };

  if (datasets.length > 1) {
    scales.y1 = {
      type: 'linear',
      position: 'right',
      ticks: { color: '#fda4af' },
      grid: { drawOnChartArea: false },
    };
  }

  if (activeChart) {
    activeChart.destroy();
  }

  activeChart = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#f9fafb' } },
        title: {
          display: true,
          text: vizConfig.title || 'Cross-Source Analysis',
          color: '#f9fafb',
        },
      },
      scales,
    },
  });
}

async function submitQuery(queryText) {
  const input = document.getElementById('query-input');
  const submitBtn = document.getElementById('submit-btn');
  const trimmed = (queryText || input.value).trim();
  if (!trimmed) return;

  input.value = '';
  submitBtn.disabled = true;
  submitBtn.textContent = 'Running...';

  appendChatMessage('user', trimmed);

  try {
    const resp = await fetch(`${API_BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: currentSessionId,
        query: trimmed,
      }),
    });

    const data = await resp.json();

    if (data.clarification_needed) {
      appendChatMessage('assistant', data.clarification_question, true);
      renderSQLQueries({});
      input.placeholder = 'Type your clarification answer here (e.g., Total revenue by region in Q4-2025)...';
      input.focus();
    } else {
      appendChatMessage('assistant', data.answer || 'Query completed.');
      renderSQLQueries(data.sql_queries || {});
      renderDataTable(data.data || []);
      renderChart(data.visualization);
      input.placeholder = 'Ask a question across PostgreSQL, SQL Server, and DuckDB...';
    }
  } catch (err) {
    appendChatMessage('assistant', `Error communicating with backend API: ${err.message}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Run Query';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  updateSessionBadge();
  checkHealth();

  document.getElementById('query-form').addEventListener('submit', e => {
    e.preventDefault();
    submitQuery();
  });

  document.getElementById('reset-session-btn').addEventListener('click', () => {
    currentSessionId = 'sess-' + Math.random().toString(36).substring(2, 8);
    updateSessionBadge();
    document.getElementById('chat-stream').innerHTML = `
      <div class="msg msg-assistant">
        Started new session <strong>${currentSessionId}</strong>. Select a preset benchmark query above or ask any question across Sales (PostgreSQL), CRM (SQL Server), and Inventory (DuckDB CSV).
      </div>
    `;
    renderSQLQueries({});
    renderDataTable([]);
    renderChart(null);
  });

  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.getAttribute('data-query');
      submitQuery(q);
    });
  });
});
