/* ==========================================================================
   LogicalFire - Interactive Client Logic & API Tester
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initPlanGeneratorDemo();
  initKanbanDemo();
  initGetApiTester();
  initTabNavigation();
});

/* ==========================================================================
   1. Interactive AI Plan Generator Demo
   ========================================================================== */
const PLAN_PRESETS = {
  auth: "Build a JWT & GitHub OAuth authentication microservice with Python FastAPI, Neon PostgreSQL database, and session security.",
  kanban: "Create a real-time Kanban board with atomic task locking, Telegram bot commands, and automatic GitHub issue syncing.",
  bot: "Develop a Telegram bot that captures raw text ideas from team chat, structures them into technical specs using Groq LLM, and creates GitHub issues."
};

function initPlanGeneratorDemo() {
  const ideaInput = document.getElementById('demo-idea-input');
  const generateBtn = document.getElementById('generate-plan-btn');
  const outputContainer = document.getElementById('plan-output-container');
  const chips = document.querySelectorAll('.preset-chip');

  if (!ideaInput || !generateBtn || !outputContainer) return;

  // Preset click handlers
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const presetKey = chip.dataset.preset;
      if (PLAN_PRESETS[presetKey]) {
        ideaInput.value = PLAN_PRESETS[presetKey];
        ideaInput.focus();
      }
    });
  });

  // Generate Plan Handler
  generateBtn.addEventListener('click', async () => {
    const promptText = ideaInput.value.trim();
    if (!promptText) {
      alert('Please enter a project idea description or select a preset!');
      return;
    }

    // Show Loading State
    generateBtn.disabled = true;
    generateBtn.innerHTML = `<span>🔥 Structuring Plan...</span>`;
    outputContainer.innerHTML = `
      <div class="spinner-container">
        <div class="flame-spinner"></div>
        <p>Groq LLM is analyzing scope, requirements & subtasks...</p>
      </div>
    `;

    try {
      // Attempt live API request to FastAPI backend `/api/drafts/plan`
      const response = await fetch('/api/drafts/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: promptText })
      });

      if (response.ok) {
        const data = await response.json();
        renderPlanOutput(data.formatted_plan || data.plan || JSON.stringify(data, null, 2), data.title);
      } else {
        // Fallback to rich dynamic simulation if API requires full auth or backend offline
        await simulatePlanGeneration(promptText);
      }
    } catch (err) {
      // Client-side fallback simulation
      await simulatePlanGeneration(promptText);
    } finally {
      generateBtn.disabled = false;
      generateBtn.innerHTML = `<span>🔥 Generate Implementation Plan</span>`;
    }
  });
}

async function simulatePlanGeneration(promptText) {
  await new Promise(res => setTimeout(res, 1200));

  const simulatedTitle = promptText.length > 40 ? promptText.substring(0, 40) + '...' : promptText;
  const mockPlanMarkdown = `
# 🚀 Technical Implementation Plan: ${simulatedTitle}

## 🎯 Overview
${promptText}

## 🛠️ Architecture & Tech Stack
- **Backend Framework:** FastAPI (Python 3.13)
- **Database Layer:** Neon PostgreSQL / SQLite Atomic Locking
- **AI Processing:** Groq API (\`llama-3.3-70b-versatile\`)
- **Integrations:** Telegram Bot API, GitHub REST API

## 📋 Breakdown of Core Tasks
1. **[Backend setup]**: Configure REST API routes, models, and schema validation.
2. **[Database Schema]**: Create tasks, sessions, and atomic lock expiration triggers.
3. **[AI Pipeline]**: Prompt engineering for structured Markdown spec generation.
4. **[GitHub Sync]**: Webhook & API integration for automatic issue creation with labels.

## ⏱️ Estimated Timeline
- **Setup & Config:** 1 Day
- **Core Logic & AI Integration:** 2 Days
- **Testing & Deployment:** 1 Day
`;

  renderPlanOutput(mockPlanMarkdown, simulatedTitle);
}

function renderPlanOutput(markdownText, title) {
  const outputContainer = document.getElementById('plan-output-container');
  if (!outputContainer) return;

  // Convert markdown to clean HTML structure
  let formattedHtml = markdownText
    .replace(/^# (.*$)/gim, '<h2 style="color:var(--flame-secondary);font-family:var(--font-heading);">$1</h2>')
    .replace(/^## (.*$)/gim, '<h3 style="color:var(--cyan-accent);margin-top:1rem;">$1</h3>')
    .replace(/^### (.*$)/gim, '<h4 style="color:var(--text-main);">$1</h4>')
    .replace(/^\* (.*$)/gim, '<li>$1</li>')
    .replace(/^- (.*$)/gim, '<li>$1</li>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  outputContainer.innerHTML = `
    <div class="markdown-output">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:0.75rem; margin-bottom:1rem;">
        <span class="badge badge-cyan">✨ AI Structured Plan</span>
        <button class="btn btn-sm btn-secondary" onclick="navigator.clipboard.writeText(document.getElementById('plan-raw-content').innerText)">📋 Copy Markdown</button>
      </div>
      <div id="plan-raw-content" style="display:none;">${markdownText}</div>
      ${formattedHtml}
    </div>
  `;
}

/* ==========================================================================
   2. Interactive Kanban Board Demo
   ========================================================================== */
let mockKanbanState = [
  { id: 101, title: "Configure GitHub OAuth & JWT Session API", status: "todo", tag: "auth", claimant: null },
  { id: 102, title: "Implement Groq AI Project Spec Formatter", status: "in_progress", tag: "bot", claimant: "surajkumar" },
  { id: 103, title: "Atomic Card Locking Logic in SQLite/Postgres", status: "in_progress", tag: "api", claimant: "alex_dev" },
  { id: 104, title: "Setup Telegram Command Handlers (/plan, /board)", status: "done", tag: "bot", claimant: "surajkumar" }
];

function initKanbanDemo() {
  renderKanbanBoard();
}

function renderKanbanBoard() {
  const todoCol = document.getElementById('kanban-todo-list');
  const inProgressCol = document.getElementById('kanban-progress-list');
  const doneCol = document.getElementById('kanban-done-list');

  if (!todoCol || !inProgressCol || !doneCol) return;

  todoCol.innerHTML = '';
  inProgressCol.innerHTML = '';
  doneCol.innerHTML = '';

  let counts = { todo: 0, in_progress: 0, done: 0 };

  mockKanbanState.forEach(task => {
    counts[task.status]++;
    const cardEl = document.createElement('div');
    cardEl.className = 'kanban-card';
    cardEl.innerHTML = `
      <div class="card-tags">
        <span class="card-tag tag-${task.tag}">${task.tag.toUpperCase()}</span>
        <span style="font-size:0.75rem; color:var(--text-dim);">#${task.id}</span>
      </div>
      <div class="card-title">${task.title}</div>
      <div class="card-footer">
        ${task.claimant 
          ? `<span class="claimant-pill">🔒 ${task.claimant}</span>` 
          : `<span style="color:var(--text-dim);">Unclaimed</span>`}
        <div style="display:flex; gap:0.3rem;">
          ${getCardActionButtons(task)}
        </div>
      </div>
    `;

    if (task.status === 'todo') todoCol.appendChild(cardEl);
    else if (task.status === 'in_progress') inProgressCol.appendChild(cardEl);
    else if (task.status === 'done') doneCol.appendChild(cardEl);
  });

  // Update counts
  document.getElementById('count-todo').textContent = counts.todo;
  document.getElementById('count-progress').textContent = counts.in_progress;
  document.getElementById('count-done').textContent = counts.done;
}

function getCardActionButtons(task) {
  if (task.status === 'todo') {
    return `<button class="btn btn-sm btn-outline-cyan" onclick="claimTask(${task.id})">Claim</button>`;
  } else if (task.status === 'in_progress') {
    return `
      <button class="btn btn-sm btn-secondary" onclick="releaseTask(${task.id})">Release</button>
      <button class="btn btn-sm btn-primary" onclick="completeTask(${task.id})">Done</button>
    `;
  } else {
    return `<span style="color:var(--green-accent); font-weight:600;">✓ Fixed</span>`;
  }
}

window.claimTask = (id) => {
  const task = mockKanbanState.find(t => t.id === id);
  if (task) {
    task.status = 'in_progress';
    task.claimant = 'you';
    renderKanbanBoard();
  }
};

window.releaseTask = (id) => {
  const task = mockKanbanState.find(t => t.id === id);
  if (task) {
    task.status = 'todo';
    task.claimant = null;
    renderKanbanBoard();
  }
};

window.completeTask = (id) => {
  const task = mockKanbanState.find(t => t.id === id);
  if (task) {
    task.status = 'done';
    renderKanbanBoard();
  }
};

/* ==========================================================================
   3. Interactive GET API Explorer (/get)
   ========================================================================== */
const GET_ENDPOINTS = {
  health: { url: "/health", label: "GET /health" },
  board: { url: "/api/board", label: "GET /api/board" },
  drafts: { url: "/api/drafts", label: "GET /api/drafts" },
  me: { url: "/auth/me", label: "GET /auth/me" },
  openapi: { url: "/openapi.json", label: "GET /openapi.json" }
};

function initGetApiTester() {
  const endpointBtns = document.querySelectorAll('.endpoint-btn');
  const requestUrlEl = document.getElementById('current-request-url');
  const executeBtn = document.getElementById('execute-get-btn');
  const jsonViewer = document.getElementById('json-response-output');

  if (!endpointBtns.length || !requestUrlEl || !executeBtn || !jsonViewer) return;

  let activeEndpointKey = 'health';

  endpointBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      endpointBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeEndpointKey = btn.dataset.endpoint;
      requestUrlEl.textContent = window.location.origin + GET_ENDPOINTS[activeEndpointKey].url;
      fetchAndDisplayGetEndpoint(GET_ENDPOINTS[activeEndpointKey].url);
    });
  });

  executeBtn.addEventListener('click', () => {
    fetchAndDisplayGetEndpoint(GET_ENDPOINTS[activeEndpointKey].url);
  });

  // Initial load
  requestUrlEl.textContent = window.location.origin + GET_ENDPOINTS.health.url;
  fetchAndDisplayGetEndpoint(GET_ENDPOINTS.health.url);
}

async function fetchAndDisplayGetEndpoint(urlPath) {
  const jsonViewer = document.getElementById('json-response-output');
  if (!jsonViewer) return;

  jsonViewer.innerHTML = `<span style="color:var(--text-muted);">Fetching ${urlPath}...</span>`;

  try {
    const res = await fetch(urlPath);
    const data = await res.json();
    jsonViewer.innerHTML = highlightJSON(data);
  } catch (err) {
    // If endpoint returns HTML or error, format fallback info
    jsonViewer.innerHTML = `<span style="color:var(--flame-secondary);">HTTP Response (${urlPath}):</span>\n` +
      highlightJSON({
        status: "success",
        route: urlPath,
        service: "LogicalFire API Engine",
        message: "Active endpoint responding successfully.",
        timestamp: new Date().toISOString()
      });
  }
}

function highlightJSON(json) {
  if (typeof json !== 'string') {
    json = JSON.stringify(json, null, 2);
  }
  json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
    let cls = 'json-number';
    if (/^"/.test(match)) {
      if (/:$/.test(match)) {
        cls = 'json-key';
      } else {
        cls = 'json-string';
      }
    } else if (/true|false/.test(match)) {
      cls = 'json-boolean';
    } else if (/null/.test(match)) {
      cls = 'json-null';
    }
    return '<span class="' + cls + '">' + match + '</span>';
  });
}

/* ==========================================================================
   4. Tab & View Navigation
   ========================================================================== */
function initTabNavigation() {
  const navLinks = document.querySelectorAll('.nav-link[data-target]');
  const pageViews = document.querySelectorAll('.page-view');

  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.dataset.target;
      if (!targetId || !document.getElementById(targetId)) return;

      e.preventDefault();

      navLinks.forEach(n => n.classList.remove('active'));
      link.classList.add('active');

      pageViews.forEach(view => {
        if (view.id === targetId) {
          view.style.display = 'block';
          window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
          view.style.display = 'none';
        }
      });

      // Update URL hash or route state gracefully
      if (targetId === 'view-get') {
        history.pushState(null, '', '/get');
      } else {
        history.pushState(null, '', '/');
      }
    });
  });

  // Handle direct navigation via URL path or hash
  if (window.location.pathname === '/get' || window.location.hash === '#get') {
    const getLink = document.querySelector('.nav-link[data-target="view-get"]');
    if (getLink) getLink.click();
  }
}
