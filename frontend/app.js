const sessionId = "sess-" + Math.random().toString(36).substring(2, 10);

const chatContainer = document.getElementById("chat-container");
const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("send-button");

// Auto-resize textarea and handle Enter vs Shift+Enter
chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = chatInput.value.trim();
  if (!query || sendButton.disabled) return;

  chatInput.value = "";
  chatInput.style.height = "auto";

  appendUserMessage(query);
  sendButton.disabled = true;

  const loadingEl = appendLoadingMessage();

  try {
    const res = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        query: query,
      }),
    });

    const data = await res.json();
    loadingEl.remove();

    if (!res.ok) {
      appendAssistantMessage({
        answer: data.detail || "An error occurred while processing your query.",
      });
      return;
    }

    appendAssistantMessage(data);
  } catch (err) {
    loadingEl.remove();
    appendAssistantMessage({
      answer: `Unable to reach backend: ${err.message}`,
    });
  } finally {
    sendButton.disabled = false;
    chatInput.focus();
  }
});

function appendUserMessage(text) {
  const msg = document.createElement("div");
  msg.className = "message user";
  msg.innerHTML = `
    <div class="message-role">You</div>
    <div class="message-content">
      <p class="message-text">${escapeHtml(text)}</p>
    </div>
  `;
  chatMessages.appendChild(msg);
  scrollToBottom();
}

function appendLoadingMessage() {
  const msg = document.createElement("div");
  msg.className = "message assistant";
  msg.innerHTML = `
    <div class="message-role">Assistant</div>
    <div class="message-content">
      <p class="message-text" style="color: var(--text-muted);">Thinking...</p>
    </div>
  `;
  chatMessages.appendChild(msg);
  scrollToBottom();
  return msg;
}

function appendAssistantMessage(payload) {
  const msg = document.createElement("div");
  msg.className = "message assistant";

  const role = document.createElement("div");
  role.className = "message-role";
  role.textContent = "Assistant";

  const content = document.createElement("div");
  content.className = "message-content";

  // 1. Assistant answer or clarification question
  const textEl = document.createElement("p");
  textEl.className = "message-text";
  textEl.textContent =
    payload.clarification_question ||
    payload.answer ||
    "Completed.";
  content.appendChild(textEl);

  // 2. Simple table if tabular data is returned
  const rows = Array.isArray(payload.data) ? payload.data : [];
  if (rows.length > 0) {
    const columns = Object.keys(rows[0]);
    const tableWrap = document.createElement("div");
    tableWrap.className = "table-wrap";

    const thead = `<thead><tr>${columns
      .map((col) => `<th>${escapeHtml(col)}</th>`)
      .join("")}</tr></thead>`;

    const tbody = `<tbody>${rows
      .map(
        (row) =>
          `<tr>${columns
            .map((col) => `<td>${escapeHtml(formatCell(row[col]))}</td>`)
            .join("")}</tr>`
      )
      .join("")}</tbody>`;

    tableWrap.innerHTML = `<table class="data-table">${thead}${tbody}</table>`;
    content.appendChild(tableWrap);
  }

  // 3. Small optional chart only when chart config is provided by backend
  if (payload.chart && rows.length > 0 && typeof Chart !== "undefined") {
    const chartEl = buildChartElement(payload.chart, rows);
    if (chartEl) {
      content.appendChild(chartEl);
    }
  }

  // 4. Collapsible SQL section (closed by default)
  const sqlQueries = payload.sql_queries || {};
  const sqlEntries = Object.entries(sqlQueries);
  if (sqlEntries.length > 0) {
    const details = document.createElement("details");
    details.className = "sql-collapsible";

    const itemsHtml = sqlEntries
      .map(
        ([source, sql]) => `
        <div>
          <div class="sql-item-source">${escapeHtml(source)}</div>
          <pre class="sql-item-code">${escapeHtml(sql)}</pre>
        </div>
      `
      )
      .join("");

    details.innerHTML = `
      <summary>View generated SQL</summary>
      <div class="sql-list">${itemsHtml}</div>
    `;
    content.appendChild(details);
  }

  msg.appendChild(role);
  msg.appendChild(content);
  chatMessages.appendChild(msg);
  scrollToBottom();
}

function buildChartElement(chartConfig, rows) {
  const columns = Object.keys(rows[0]);
  const xKey =
    chartConfig.x_key && columns.includes(chartConfig.x_key)
      ? chartConfig.x_key
      : columns[0];
  const numericCols = columns.filter(
    (c) => c !== xKey && typeof rows[0][c] === "number"
  );
  if (numericCols.length === 0) return null;

  const wrap = document.createElement("div");
  wrap.className = "chart-wrap";
  const canvas = document.createElement("canvas");
  wrap.appendChild(canvas);

  const labels = rows.map((r) => String(r[xKey]));
  const datasets = numericCols.slice(0, 2).map((col, idx) => ({
    label: col,
    data: rows.map((r) => Number(r[col]) || 0),
    backgroundColor: idx === 0 ? "rgba(237, 237, 237, 0.75)" : "rgba(154, 154, 154, 0.6)",
    borderRadius: 4,
  }));

  new Chart(canvas.getContext("2d"), {
    type: chartConfig.chart_type === "line" ? "line" : "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#9a9a9a", boxWidth: 12 } },
      },
      scales: {
        x: { ticks: { color: "#9a9a9a" }, grid: { color: "#262626" } },
        y: { ticks: { color: "#9a9a9a" }, grid: { color: "#262626" } },
      },
    },
  });

  return wrap;
}

function formatCell(val) {
  if (val === null || val === undefined) return "";
  if (typeof val === "number") {
    return Number.isInteger(val)
      ? val.toLocaleString()
      : val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return String(val);
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
