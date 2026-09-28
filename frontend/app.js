// Multi-Source Agentic Text-to-SQL — ChatGPT-Style Frontend Logic

const API_BASE = "";

let currentSessionId = generateSessionId();

function generateSessionId() {
  return "sess-" + Math.random().toString(36).substring(2, 8);
}

document.addEventListener("DOMContentLoaded", () => {
  updateSessionBadge();
  checkHealth();
  setupSidebarAccordion();
  setupEventListeners();
});

function updateSessionBadge() {
  const el = document.getElementById("session-id-label");
  if (el) el.textContent = currentSessionId;
}

async function checkHealth() {
  const dot = document.getElementById("health-dot");
  const text = document.getElementById("health-text");

  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    if (res.ok && data.status === "ok") {
      if (dot) dot.style.backgroundColor = "#10a37f";
      if (text) {
        const count = (data.mcp_sources || []).length;
        text.textContent = `Connected (${count} MCP Sources)`;
      }
    } else {
      if (dot) dot.style.backgroundColor = "#ef4444";
      if (text) text.textContent = "Backend Error";
    }
  } catch (err) {
    if (dot) dot.style.backgroundColor = "#ef4444";
    if (text) text.textContent = "Backend Offline";
  }
}

function setupSidebarAccordion() {
  const headers = document.querySelectorAll(".source-header");
  headers.forEach((header) => {
    header.addEventListener("click", () => {
      const parentItem = header.closest(".source-item");
      if (!parentItem) return;
      parentItem.classList.toggle("active");
    });
  });
}

function setupEventListeners() {
  const form = document.getElementById("query-form");
  const input = document.getElementById("query-input");
  const resetBtn = document.getElementById("reset-session-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (!query) return;
    input.value = "";
    await sendQuery(query);
  });

  // Sidebar sample queries & Welcome starter cards
  document.querySelectorAll("[data-query]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const q = btn.getAttribute("data-query");
      if (!q) return;
      await sendQuery(q);
    });
  });

  // + New Chat button
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      currentSessionId = generateSessionId();
      updateSessionBadge();
      const stream = document.getElementById("chat-stream");
      // Remove all message rows and show welcome screen again
      stream.querySelectorAll(".message-row").forEach((row) => row.remove());
      const welcome = document.getElementById("welcome-screen");
      if (welcome) welcome.style.display = "flex";
    });
  }
}

async function sendQuery(queryText) {
  const submitBtn = document.getElementById("submit-btn");
  const input = document.getElementById("query-input");
  const welcome = document.getElementById("welcome-screen");

  if (welcome) {
    welcome.style.display = "none";
  }

  appendUserMessage(queryText);

  submitBtn.disabled = true;
  const thinkingRow = appendThinkingMessage();

  try {
    const response = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        query: queryText,
      }),
    });

    const payload = await response.json();
    thinkingRow.remove();

    if (!response.ok) {
      appendAssistantError(payload.detail || "Request failed.");
      return;
    }

    appendAssistantResponse(payload);

    if (payload.clarification_needed) {
      input.placeholder = "Reply with clarification details (e.g. 'Total revenue by region in Q4-2025')...";
      input.focus();
    } else {
      input.placeholder = "Message Multi-Source SQL Assistant...";
    }
  } catch (err) {
    thinkingRow.remove();
    appendAssistantError(`Network error: ${err.message}`);
  } finally {
    submitBtn.disabled = false;
  }
}

function appendUserMessage(text) {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row user";

  const bubble = document.createElement("div");
  bubble.className = "user-bubble";
  bubble.textContent = text;

  row.appendChild(bubble);
  stream.appendChild(row);
  scrollToBottom();
}

function appendThinkingMessage() {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row assistant";

  row.innerHTML = `
    <div class="assistant-wrap">
      <div class="assistant-avatar">✦</div>
      <div class="assistant-body">
        <div class="thinking-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>
  `;
  stream.appendChild(row);
  scrollToBottom();
  return row;
}

function appendAssistantError(errorMsg) {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row assistant";

  row.innerHTML = `
    <div class="assistant-wrap">
      <div class="assistant-avatar" style="background-color: #ef4444;">!</div>
      <div class="assistant-body">
        <div class="assistant-text" style="color: #fca5a5;">${escapeHtml(errorMsg)}</div>
      </div>
    </div>
  `;
  stream.appendChild(row);
  scrollToBottom();
}

function appendAssistantResponse(payload) {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const isClarification = Boolean(payload.clarification_needed);
  const answerText = payload.clarification_question || payload.answer || "Query processed.";
  const dataRows = payload.data || [];
  const sqlQueries = payload.sql_queries || {};
  const sqlEntries = Object.entries(sqlQueries);

  let bodyHtml = "";

  // 1. Clarification or Natural Language Answer
  if (isClarification) {
    bodyHtml += `
      <div class="clarification-box">
        <span class="clarification-badge">Clarification Needed</span>
        <div class="assistant-text" style="margin-bottom: 0;">${escapeHtml(answerText)}</div>
      </div>
    `;
  } else {
    bodyHtml += `<div class="assistant-text">${escapeHtml(answerText)}</div>`;
  }

  // 2. Inline Data Table if rows returned
  if (dataRows.length > 0) {
    const columns = Object.keys(dataRows[0]);
    const ths = columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
    const trs = dataRows
      .map((r) => {
        const tds = columns
          .map((c) => `<td>${escapeHtml(formatValue(r[c]))}</td>`)
          .join("");
        return `<tr>${tds}</tr>`;
      })
      .join("");

    bodyHtml += `
      <div class="result-table-wrapper">
        <div class="result-table-header">
          <span>Query Result</span>
          <span>${dataRows.length} row${dataRows.length === 1 ? "" : "s"}</span>
        </div>
        <div class="result-table-scroll">
          <table class="chat-table">
            <thead><tr>${ths}</tr></thead>
            <tbody>${trs}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  // 3. Collapsible SQL Inspector Drawer (tucked cleanly under the response)
  if (sqlEntries.length > 0) {
    const dialectMap = {
      sales_pg: "PostgreSQL (sales_pg)",
      crm_mssql: "SQL Server T-SQL (crm_mssql)",
      analytics_duckdb: "DuckDB CSV SQL (analytics_duckdb)",
    };

    const snippets = sqlEntries
      .map(([source, sql]) => {
        const label = dialectMap[source] || source;
        return `
          <div class="sql-snippet-block">
            <div class="sql-snippet-meta">
              <span style="color: #93c5fd;">${escapeHtml(label)}</span>
              <span style="color: #6ee7b7;">✓ Read-Only Verified</span>
            </div>
            <div class="sql-code">${escapeHtml(sql)}</div>
          </div>
        `;
      })
      .join("");

    bodyHtml += `
      <details class="sql-drawer">
        <summary>
          <span>View Generated SQL (${sqlEntries.length} source${sqlEntries.length === 1 ? "" : "s"})</span>
          <span style="font-size: 0.72rem; color: var(--text-muted);">Click to expand</span>
        </summary>
        <div class="sql-drawer-content">
          ${snippets}
        </div>
      </details>
    `;
  }

  row.innerHTML = `
    <div class="assistant-wrap">
      <div class="assistant-avatar">✦</div>
      <div class="assistant-body">
        ${bodyHtml}
      </div>
    </div>
  `;

  stream.appendChild(row);
  scrollToBottom();
}

function scrollToBottom() {
  const feed = document.getElementById("chat-feed");
  if (feed) {
    feed.scrollTop = feed.scrollHeight;
  }
}

function formatValue(val) {
  if (val === null || val === undefined) return "—";
  if (typeof val === "number") {
    return Number.isInteger(val)
      ? val.toLocaleString()
      : val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return String(val);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
