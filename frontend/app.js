const sessionId = "sess-" + Math.random().toString(36).substring(2, 10);

const chatContainer = document.getElementById("chat-container");
const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("send-button");

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

  const textEl = document.createElement("p");
  textEl.className = "message-text";
  textEl.textContent =
    payload.clarification_question ||
    payload.answer ||
    "Completed.";
  content.appendChild(textEl);

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
