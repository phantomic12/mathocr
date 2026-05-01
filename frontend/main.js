// MathOCR Frontend with Auth + Live Progress
const API_BASE = "";
let activeJobId = null;
let currentLatex = "";
let currentFilename = "";
let currentUser = null;
let ws = null;
let viewMode = "split"; // "split" | "latex" | "rendered"
let currentResult = null; // store full result for JSON download
let darkMode = localStorage.getItem("mathocr_theme") === "dark";

// ── Toast notifications ──────────────────────────────────────────────────────
function toast(msg, type = "info", duration = 3500) {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add("fade-out");
    setTimeout(() => el.remove(), 250);
  }, duration);
}

// ── Dark mode ────────────────────────────────────────────────────────────────
function applyTheme() {
  document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "");
  document.getElementById("theme-icon").innerHTML = darkMode ? "&#9788;" : "&#9789;";
  document.getElementById("theme-toggle").setAttribute("aria-pressed", darkMode ? "true" : "false");
  localStorage.setItem("mathocr_theme", darkMode ? "dark" : "");
}

function initTheme() {
  darkMode = localStorage.getItem("mathocr_theme") === "dark";
  applyTheme();
  document.getElementById("theme-toggle").addEventListener("click", () => {
    darkMode = !darkMode;
    applyTheme();
  });
}

// ── Auth ─────────────────────────────────────────────────────────────────────
function getToken() { return localStorage.getItem("mathocr_token"); }
function setToken(t) { localStorage.setItem("mathocr_token", t); }
function clearToken() { localStorage.removeItem("mathocr_token"); }
function getAuthHeaders() {
  const t = getToken();
  return t ? { "Authorization": `Bearer ${t}` } : {};
}
function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

async function apiFetch(url, opts = {}) {
  const headers = { ...getAuthHeaders(), ...(opts.headers || {}) };
  const res = await fetch(API_BASE + url, { ...opts, headers });
  if (res.status === 401) { logout(); toast("Session expired — please sign in again.", "warning"); return null; }
  return res;
}

function showAuthModal() {
  document.getElementById("auth-modal").classList.remove("hidden");
  document.getElementById("sidebar").classList.add("hidden");
  document.getElementById("main").classList.add("hidden");
}

function showApp() {
  document.getElementById("auth-modal").classList.add("hidden");
  document.getElementById("sidebar").classList.remove("hidden");
  document.getElementById("main").classList.remove("hidden");
  document.getElementById("user-email").textContent = currentUser ? currentUser.email : "";
  if (currentUser && currentUser.is_admin) {
    document.getElementById("admin-panel").classList.remove("hidden");
    loadUsers();
  } else {
    document.getElementById("admin-panel").classList.add("hidden");
  }
}

function logout() {
  clearToken();
  currentUser = null;
  showAuthModal();
}

async function init() {
  initTheme();
  const token = getToken();
  if (token) {
    try {
      const res = await apiFetch("/api/auth/me");
      if (res && res.ok) {
        const data = await res.json();
        currentUser = data;
        showApp();
        await loadProviders();
        await loadHistory();
        wireEvents();
        wireKeyboard();
        return;
      }
    } catch (e) { /* fall through to login */ }
    clearToken();
  }
  showAuthModal();
  wireAuthEvents();
  wireKeyboard();
}

// ── Keyboard shortcuts ───────────────────────────────────────────────────────
function wireKeyboard() {
  document.addEventListener("keydown", e => {
    // Escape → close overlay / modal
    if (e.key === "Escape") {
      const status = document.getElementById("job-status");
      if (!status.classList.contains("hidden")) {
        // don't close during active job — just dismiss if done
      }
    }
    // Ctrl+V → paste from clipboard into dropzone
    if ((e.ctrlKey || e.metaKey) && e.key === "v") {
      const authModal = document.getElementById("auth-modal");
      if (!authModal.classList.contains("hidden")) return; // let browser handle auth form
      const dropzone = document.getElementById("dropzone");
      const fileInput = document.getElementById("file-input");
      if (document.activeElement === document.body || document.activeElement === dropzone) {
        e.preventDefault();
        navigator.clipboard.read().then(items => {
          for (const item of items) {
            for (const type of item.types) {
              if (type.startsWith("image/")) {
                item.getType(type).then(blob => {
                  const file = new File([blob], "clipboard.png", { type });
                  const dt = new DataTransfer();
                  dt.items.add(file);
                  fileInput.files = dt.files;
                  uploadFile(file);
                });
                return;
              }
            }
          }
          toast("No image found in clipboard", "warning");
        }).catch(() => toast("Clipboard access denied — paste an image directly", "error"));
      }
    }
  });
}

// ── Auth UI ──────────────────────────────────────────────────────────────────
let authMode = "login";

function wireAuthEvents() {
  const form = document.getElementById("auth-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("auth-email").value.trim();
    const password = document.getElementById("auth-password").value;
    const btn = document.getElementById("auth-submit-btn");
    const err = document.getElementById("auth-error");
    err.classList.add("hidden");
    btn.textContent = authMode === "login" ? "Signing in..." : "Creating account...";
    btn.disabled = true;
    try {
      const res = await fetch(API_BASE + "/api/auth/" + authMode, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { err.textContent = data.detail || "Error"; err.classList.remove("hidden"); return; }
      setToken(data.access_token);
      currentUser = data.user;
      showApp();
      toast(`Welcome${authMode === "register" ? ", account created" : ""}!`, "success");
      await loadProviders();
      await loadHistory();
      wireEvents();
    } finally {
      btn.textContent = authMode === "login" ? "Sign In" : "Create Account";
      btn.disabled = false;
    }
  });

  document.getElementById("auth-switch-btn").addEventListener("click", () => {
    authMode = authMode === "login" ? "register" : "login";
    document.getElementById("auth-submit-btn").textContent = authMode === "login" ? "Sign In" : "Create Account";
    document.getElementById("auth-switch-text").textContent = authMode === "login" ? "Don't have an account?" : "Already have an account?";
    document.getElementById("auth-switch-btn").textContent = authMode === "login" ? "Register" : "Sign In";
    document.getElementById("auth-error").classList.add("hidden");
  });

  document.getElementById("logout-btn").addEventListener("click", logout);
}

// ── Providers ────────────────────────────────────────────────────────────────
async function loadProviders() {
  try {
    const res = await apiFetch("/api/settings");
    if (!res) return;
    const data = await res.json();
    const sel = document.getElementById("provider-select");
    sel.innerHTML = "";
    data.providers.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = p.name.charAt(0).toUpperCase() + p.name.slice(1);
      if (p.name === data.active_provider) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (e) { console.error(e); }
}

document.getElementById("provider-select").addEventListener("change", async () => {
  try {
    await apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_provider: document.getElementById("provider-select").value }),
    });
    toast("Provider updated", "success");
  } catch(e) { console.error(e); }
});

// ── History ──────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await apiFetch("/api/history?per_page=50");
    if (!res) return;
    const data = await res.json();
    renderHistory(data.items || []);
  } catch(e) { console.error(e); }
}

function renderHistory(jobs) {
  const el = document.getElementById("history-list");
  el.innerHTML = "";
  if (!jobs.length) { el.innerHTML = "<p style=font-size:0.75rem;opacity:0.4;padding:12px>No history yet</p>"; return; }
  // Stagger animation delay
  jobs.forEach((job, idx) => {
    const div = document.createElement("div");
    div.className = "history-item" + (job.id === activeJobId ? " active" : "");
    div.style.animationDelay = `${idx * 30}ms`;
    const t = job.created_at ? new Date(job.created_at).toLocaleString() : "";
    div.innerHTML = "<div class=hi-name>" + esc(job.filename) + "</div><div class=hi-meta><span class=hi-status " + job.status + " aria-hidden=true></span><span class=sr-only>" + job.status + "</span> " + t + "</div>";
    div.addEventListener("click", () => {
      document.querySelectorAll(".history-item").forEach(h => h.classList.remove("active"));
      div.classList.add("active");
      loadJobResult(job.id);
    });
    el.appendChild(div);
  });
}

async function loadJobResult(id) {
  try {
    const r = await apiFetch("/api/ocr/result/" + id);
    if (!r) return;
    if (!r.ok) throw new Error("not found");
    const d = await r.json();
    showResult(d);
    activeJobId = id;
    loadHistory();
  } catch(e) { toast("Failed to load result", "error"); }
}

// ── Admin ────────────────────────────────────────────────────────────────────
async function loadUsers() {
  try {
    const res = await apiFetch("/api/admin/users");
    if (!res || !res.ok) return;
    const data = await res.json();
    renderUsers(data.users || []);
  } catch(e) { console.error(e); }
}

function renderUsers(users) {
  const el = document.getElementById("user-list");
  el.innerHTML = "";
  if (!users.length) { el.innerHTML = "<p style=font-size:0.75rem;opacity:0.4;padding:12px>No users</p>"; return; }
  users.forEach(user => {
    const div = document.createElement("div");
    div.className = "history-item";
    div.style.animationDelay = "0ms";
    const isMe = user.id === (currentUser && currentUser.id);
    const adminBadge = user.is_admin ? " <span style='color:#5b7fff;font-size:0.65rem'>[admin]</span>" : "";
    div.innerHTML = `<div class=hi-name>${esc(user.email)}${adminBadge}</div>
      <div class=hi-meta>${isMe ? "you" : ""} · ${user.created_at ? new Date(user.created_at).toLocaleDateString() : ""}</div>`;

    if (!isMe) {
      const actions = document.createElement("div");
      actions.style.display = "flex";
      actions.style.gap = "4px";
      actions.style.marginTop = "4px";

      const promoteBtn = document.createElement("button");
      promoteBtn.className = "view-btn";
      promoteBtn.style.fontSize = "0.65rem";
      promoteBtn.style.padding = "2px 8px";
      promoteBtn.textContent = user.is_admin ? "Revoke Admin" : "Make Admin";
      promoteBtn.addEventListener("click", () => toggleAdmin(user.id, !user.is_admin));

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "view-btn";
      deleteBtn.style.fontSize = "0.65rem";
      deleteBtn.style.padding = "2px 8px";
      deleteBtn.style.color = "var(--error)";
      deleteBtn.textContent = "Delete";
      deleteBtn.addEventListener("click", () => deleteUser(user.id));
      actions.appendChild(promoteBtn);
      actions.appendChild(deleteBtn);
      div.appendChild(actions);
    }

    el.appendChild(div);
  });
}

async function toggleAdmin(userId, isAdmin) {
  try {
    const res = await apiFetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, is_admin: isAdmin }),
    });
    if (!res || !res.ok) { toast("Failed to update user", "error"); return; }
    toast(isAdmin ? "Admin granted" : "Admin revoked", "success");
    loadUsers();
  } catch(e) { toast("Error: " + e.message, "error"); }
}

async function deleteUser(userId) {
  if (!confirm("Delete this user and all their jobs?")) return;
  try {
    const res = await apiFetch("/api/admin/users/" + userId, { method: "DELETE" });
    if (!res || !res.ok) { toast("Failed to delete user", "error"); return; }
    toast("User deleted", "success");
    loadUsers();
  } catch(e) { toast("Error: " + e.message, "error"); }
}

// ── Upload ────────────────────────────────────────────────────────────────────
async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  showStatus("Uploading...");
  try {
    const res = await apiFetch("/api/ocr/upload", { method: "POST", body: fd });
    if (!res) { hideStatus(); return; }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "fail");
    activeJobId = data.job_id;
    currentFilename = data.filename;
    connectWS(data.job_id);
    loadHistory();
  } catch(e) { hideStatus(); toast("Upload failed: " + e.message, "error"); }
}

// ── WebSocket + seconds tracker ──────────────────────────────────────────────
function connectWS(jobId) {
  if (ws) { try { ws.close(); } catch(e) {} }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(proto + "://" + location.host + API_BASE + "/api/ocr/ws/" + jobId);

  let startTime = Date.now();
  let timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const progressEl = document.getElementById("job-progress");
    if (progressEl) progressEl.textContent = elapsed + "s elapsed";
  }, 1000);

  ws.onopen = () => showStatus("Processing...");
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === "token_progress") {
      const tokSpeed = d.tok_per_sec ? `${d.tok_per_sec} tok/s` : "";
      document.getElementById("job-progress").textContent =
        `${d.tok_per_sec} tok/s · ${d.chars} chars · ${Math.round(d.elapsed_ms/1000)}s elapsed`;
    } else if (d.type === "page_progress") {
      const percent = d.total_pages > 0 ? Math.round((d.page / d.total_pages) * 100) : 0;
      setProgress(percent);
      document.getElementById("job-progress").textContent = `Page ${d.page}/${d.total_pages} — ${percent}%`;
    } else if (d.type === "done") {
      clearInterval(timerInterval);
      hideStatus();
      showResult({ latex: d.latex, filename: currentFilename, process_time_ms: d.process_time_ms });
      ws.close();
      ws = null;
      loadHistory();
      toast(" transcription complete", "success");
    } else if (d.type === "error") {
      clearInterval(timerInterval);
      hideStatus();
      toast("Processing error: " + d.error, "error");
      if (ws) { ws.close(); ws = null; }
    }
  };
  ws.onerror = () => {
    clearInterval(timerInterval);
    pollJob(jobId);
  };
  ws.onclose = () => { clearInterval(timerInterval); ws = null; };
}

async function pollJob(jobId) {
  showStatus("Waiting...");
  let startTime = Date.now();
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const progressEl = document.getElementById("job-progress");
    if (progressEl) progressEl.textContent = `${elapsed}s elapsed`;
    try {
      const r = await apiFetch("/api/ocr/status/" + jobId);
      if (!r) return;
      const d = await r.json();
      if (d.status === "done") { hideStatus(); loadJobResult(jobId); toast(" transcription complete", "success"); return; }
      if (d.status === "error") { hideStatus(); return; }
    } catch(e) {}
  }
  hideStatus();
}

// ── Result display ────────────────────────────────────────────────────────────
function showResult(d) {
  currentLatex = d.latex || "";
  currentFilename = d.filename || "result";
  currentResult = d;
  document.getElementById("result-filename").textContent = currentFilename;
  document.getElementById("result-time").textContent = d.process_time_ms ? `Done in ${(d.process_time_ms / 1000).toFixed(1)}s` : "";

  // Re-animate result panel
  const panel = document.getElementById("result-panel");
  panel.style.animation = "none";
  panel.offsetHeight; // trigger reflow
  panel.style.animation = "";
  panel.classList.remove("hidden");

  const pages = d.page_results || (d.latex ? [d.latex] : []);
  const pagesEl = document.getElementById("result-pages");
  pagesEl.innerHTML = "";

  pages.forEach((latex, i) => {
    const wrapper = document.createElement("div");
    wrapper.className = "page-result";

    const header = document.createElement("div");
    header.className = "page-result-header";
    header.textContent = `Page ${i + 1} / ${pages.length}`;
    wrapper.appendChild(header);

    const toolbar = document.createElement("div");
    toolbar.className = "view-toolbar";
    toolbar.innerHTML = `
      <button class="view-btn ${viewMode === "split" ? "active" : ""}" data-mode="split" data-page="${i}">Split</button>
      <button class="view-btn ${viewMode === "latex" ? "active" : ""}" data-mode="latex" data-page="${i}">LaTeX</button>
      <button class="view-btn ${viewMode === "rendered" ? "active" : ""}" data-mode="rendered" data-page="${i}">Rendered</button>
    `;
    wrapper.appendChild(toolbar);

    const content = document.createElement("div");
    content.className = "page-content";
    content.innerHTML = `
      <div class="pane pane-latex" id="latex-${i}"></div>
      <div class="pane pane-rendered" id="rendered-${i}"></div>
    `;
    wrapper.appendChild(content);

    pagesEl.appendChild(wrapper);

    setTimeout(() => {
      const latexEl = document.getElementById("latex-" + i);
      const renderedEl = document.getElementById("rendered-" + i);
      if (latexEl) latexEl.textContent = latex;
      if (renderedEl && window.katex) {
        try { window.katex.render(latex, renderedEl, { throwOnError: false, displayMode: true }); }
        catch(e) { renderedEl.textContent = latex; }
      } else if (renderedEl) { renderedEl.textContent = latex; }
      applyViewMode(i);
    }, 0);
  });

  pagesEl.querySelectorAll(".view-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      viewMode = btn.dataset.mode;
      const page = parseInt(btn.dataset.page);
      applyViewMode(page);
      pagesEl.querySelectorAll(".view-btn").forEach(b => b.classList.remove("active"));
      pagesEl.querySelectorAll(`.view-btn[data-mode="${viewMode}"]`).forEach(b => b.classList.add("active"));
    });
  });

  if (window.katex) {
    try { window.katex.render(currentLatex, document.getElementById("katex-output"), {throwOnError:false, displayMode:true}); } catch(e) {
      document.getElementById("katex-output").textContent = currentLatex;
    }
  }
}

function applyViewMode(page) {
  const latexEl = document.getElementById("latex-" + page);
  const renderedEl = document.getElementById("rendered-" + page);
  if (!latexEl || !renderedEl) return;
  if (viewMode === "split") {
    latexEl.classList.remove("hidden");
    renderedEl.classList.remove("hidden");
  } else if (viewMode === "latex") {
    latexEl.classList.remove("hidden");
    renderedEl.classList.add("hidden");
  } else {
    latexEl.classList.add("hidden");
    renderedEl.classList.remove("hidden");
  }
}

// ── Status overlay ────────────────────────────────────────────────────────────
function setProgress(percent) {
  const fill = document.getElementById("progress-bar-fill");
  if (!fill) return;
  fill.classList.remove("indeterminate");
  fill.style.width = Math.min(percent, 100) + "%";
}

function showStatus(t) {
  document.getElementById("job-status-text").textContent = t;
  document.getElementById("job-progress").textContent = "";
  const fill = document.getElementById("progress-bar-fill");
  if (fill) { fill.classList.add("indeterminate"); fill.style.width = "0%"; }
  const el = document.getElementById("job-status");
  el.style.animation = "none";
  el.offsetHeight;
  el.style.animation = "";
  el.classList.remove("hidden");
}
function hideStatus() {
  const fill = document.getElementById("progress-bar-fill");
  if (fill) { fill.classList.remove("indeterminate"); fill.style.width = "0%"; }
  document.getElementById("job-status").classList.add("hidden");
}

// ── Event wiring ─────────────────────────────────────────────────────────────
function wireEvents() {
  const dz = document.getElementById("dropzone");
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("drag-over"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag-over"));
  dz.addEventListener("drop", e => { e.preventDefault(); dz.classList.remove("drag-over"); const f = e.dataTransfer.files[0]; if (f) uploadFile(f); });
  dz.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      document.getElementById("file-input").click();
    }
  });
  dz.addEventListener("click", () => document.getElementById("file-input").click());
  document.getElementById("browse-btn").addEventListener("click", e => { e.stopPropagation(); document.getElementById("file-input").click(); });
  document.getElementById("file-input").addEventListener("change", () => { const f = document.getElementById("file-input").files[0]; if (f) uploadFile(f); });

  // Paste button (clipboard image)
  document.getElementById("paste-btn").addEventListener("click", async e => {
    e.stopPropagation();
    try {
      const items = await navigator.clipboard.read();
      for (const item of items) {
        for (const type of item.types) {
          if (type.startsWith("image/")) {
            const blob = await item.getType(type);
            const file = new File([blob], "clipboard.png", { type });
            uploadFile(file);
            return;
          }
        }
      }
      toast("No image in clipboard", "warning");
    } catch(err) {
      toast("Clipboard access denied — paste an image directly", "error");
    }
  });

  // Copy LaTeX
  document.getElementById("copy-btn").addEventListener("click", () => {
    navigator.clipboard.writeText(currentLatex).then(() => {
      toast("LaTeX copied to clipboard", "success");
    }).catch(() => toast("Copy failed", "error"));
  });

  // Download .tex
  document.getElementById("download-tex-btn").addEventListener("click", () => {
    downloadBlob(new Blob([currentLatex], {type:"text/plain"}), baseName() + ".tex");
    toast("Downloaded .tex", "success");
  });

  // Download .txt
  document.getElementById("download-txt-btn").addEventListener("click", () => {
    downloadBlob(new Blob([currentLatex], {type:"text/plain"}), baseName() + ".txt");
    toast("Downloaded .txt", "success");
  });

  // Download .json
  document.getElementById("download-json-btn").addEventListener("click", () => {
    if (!currentResult) return;
    downloadBlob(new Blob([JSON.stringify(currentResult, null, 2)], {type:"application/json"}), baseName() + ".json");
    toast("Downloaded .json", "success");
  });

  // Download .docx
  document.getElementById("download-docx-btn").addEventListener("click", async () => {
    if (!currentResult) return;
    try {
      const res = await apiFetch("/api/ocr/export/docx/" + activeJobId, { method: "POST" });
      if (!res || !res.ok) { toast("DOCX export failed", "error"); return; }
      const blob = await res.blob();
      downloadBlob(blob, baseName() + ".docx");
      toast("Downloaded .docx", "success");
    } catch(e) { toast("DOCX export failed: " + e.message, "error"); }
  });

  // Download .pdf
  document.getElementById("download-pdf-btn").addEventListener("click", async () => {
    if (!currentResult) return;
    try {
      const res = await apiFetch("/api/ocr/export/pdf/" + activeJobId, { method: "POST" });
      if (!res || !res.ok) { toast("PDF export failed", "error"); return; }
      const blob = await res.blob();
      downloadBlob(blob, baseName() + ".pdf");
      toast("Downloaded .pdf", "success");
    } catch(e) { toast("PDF export failed: " + e.message, "error"); }
  });

  // Download .epub
  document.getElementById("download-epub-btn").addEventListener("click", async () => {
    if (!currentResult) return;
    try {
      const res = await apiFetch("/api/ocr/export/epub/" + activeJobId, { method: "POST" });
      if (!res || !res.ok) { toast("EPUB export failed", "error"); return; }
      const blob = await res.blob();
      downloadBlob(blob, baseName() + ".epub");
      toast("Downloaded .epub", "success");
    } catch(e) { toast("EPUB export failed: " + e.message, "error"); }
  });

  document.getElementById("logout-btn").addEventListener("click", logout);
}

function baseName() {
  return (document.getElementById("result-filename").textContent || "result").replace(/\.[^.]+$/, "");
}

function downloadBlob(blob, filename) {
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(u);
}

init();
