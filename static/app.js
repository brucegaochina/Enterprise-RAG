"use strict";

/* ------------------------------------------------------------------ helpers */

const ICONS = {
  send: '<path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>',
  gear: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  bulb: '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
  cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
  db: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  spark: '<path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  external: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6"/><path d="M10 14 21 3"/>',
  quote: '<path d="M3 21c3 0 7-1 7-8V5H3v8h4"/><path d="M14 21c3 0 7-1 7-8V5h-7v8h4"/>',
};
const svg = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
const icon = (name) => `<i data-icon="${name}">${svg(name)}</i>`;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function hydrateIcons(root = document) {
  $$("i[data-icon]", root).forEach((el) => { if (!el.innerHTML) el.innerHTML = svg(el.dataset.icon); });
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function highlightTerms(text, terms) {
  if (!terms.length) return esc(text);
  const re = new RegExp(`\\b(${terms.map(reEsc).join("|")})\\w*`, "gi");
  let out = "", last = 0;
  for (const m of text.matchAll(re)) {
    out += esc(text.slice(last, m.index)) + `<mark>${esc(m[0])}</mark>`;
    last = m.index + m[0].length;
  }
  return out + esc(text.slice(last));
}

function fmtBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const fileIcon = (type, cls = "file-ico") => `<span class="${cls} ft-${esc(type)}">${esc(String(type).toUpperCase())}</span>`;

let toastTimer;
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3800);
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

/* ------------------------------------------------------------------ state */

const DEFAULTS = { mode: "hybrid", top_k: 5, candidates: 20, rrf_k: 60, temperature: 0.2, query_rewrite: true };
let settings = { ...DEFAULTS, ...safeParse(localStorage.getItem("rag.settings")) };

function safeParse(raw) {
  try { return JSON.parse(raw) || {}; } catch { return {}; }
}

const state = {
  turns: [],
  busy: false,
  selected: null,
  tab: "sources",
  citation: null,
  citationView: "passage",
  docCache: new Map(),
  health: null,
};

const EXAMPLES = [
  { cat: "Benefits", q: "Does my plan cover annual eye exams?" },
  { cat: "Travel", q: "What is the hotel limit per night in New York?" },
  { cat: "Finance", q: "What was our Q3 2026 revenue by region?" },
  { cat: "Security", q: "What should I do if my laptop is stolen?" },
];

/* ------------------------------------------------------------------ navigation */

function showView(name) {
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  if (name === "docs") refreshDocs();
}

/* ------------------------------------------------------------------ health */

async function refreshHealth() {
  try {
    const h = await api("/api/health");
    state.health = h;
    const pill = $("#stackPill");
    pill.classList.toggle("online", h.llm_enabled);
    pill.classList.toggle("offline", !h.llm_enabled);
    const chatLabel = h.llm_enabled ? h.chat_model : "Offline answers";
    const embedLabel = h.embeddings_enabled ? h.embedding_model : "local hashing embeddings";
    $("#stackText").textContent = `${chatLabel} · ${embedLabel} · pgvector`;
    $("#pipelineModel").textContent = `${h.embedding_model} (${h.embedding_dim}d)`;

    const kb = $("#kbStatus");
    if (!h.ready) {
      kb.innerHTML = `Knowledge base is empty — <a id="kbLoad">load the 20 sample documents</a>`;
      $("#kbLoad").onclick = loadSamples;
    } else {
      kb.textContent = `${h.ready} documents · ${h.chunks} chunks indexed · ${settings.mode} retrieval`;
    }
    const banner = $("#staleBanner");
    banner.classList.toggle("hidden", !h.stale);
    if (h.stale) {
      banner.innerHTML = `${h.stale} document(s) were embedded with a different model and are only reachable by keyword search. <a id="staleFix">Re-index now</a>`;
      $("#staleFix").onclick = reindexAll;
    }
  } catch {
    $("#stackText").textContent = "API unreachable";
  }
}

/* ------------------------------------------------------------------ markdown */

function renderMarkdown(text, turnIdx, nSources) {
  const citeBtn = (n) => `<button class="cite" data-turn="${turnIdx}" data-n="${n}">${n}</button>`;
  const inline = (s) => {
    let h = esc(s);
    h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
    h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    h = h.replace(/(^|[\s(])_([^_]+)_(?=[\s).,!?]|$)/g, "$1<em>$2</em>");
    h = h.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (match, group) => {
      const nums = group.split(",").map((x) => parseInt(x, 10));
      return nums.every((n) => n >= 1 && n <= nSources) ? nums.map(citeBtn).join("") : match;
    });
    return h;
  };

  let html = "";
  let para = [];
  let list = null;
  let table = [];
  const flushPara = () => { if (para.length) { html += `<p>${para.map(inline).join("<br>")}</p>`; para = []; } };
  const flushList = () => { if (list) { html += `<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`; list = null; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\|?[\s:|-]+\|?$/.test(r)).map((r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
    const [head, ...body] = rows;
    html += `<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body
      .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    table = [];
  };
  const flushAll = () => { flushPara(); flushList(); flushTable(); };

  for (const raw of text.replace(/\r/g, "").split("\n")) {
    const line = raw.trimEnd();
    let m;
    if (!line.trim()) { flushAll(); continue; }
    if (line.trim().startsWith("|")) { flushPara(); flushList(); table.push(line.trim()); continue; }
    flushTable();
    if ((m = line.match(/^#{1,6}\s+(.*)/))) { flushAll(); html += `<h4>${inline(m[1])}</h4>`; continue; }
    if ((m = line.match(/^\s*[-*•]\s+(.*)/)) || (m = line.match(/^\s*\d+[.)]\s+(.*)/))) {
      flushPara();
      const tag = /^\s*\d/.test(line) ? "ol" : "ul";
      if (list && list.tag !== tag) flushList();
      list = list || { tag, items: [] };
      list.items.push(m[1]);
      continue;
    }
    flushList();
    para.push(line);
  }
  flushAll();
  return html;
}

/* ------------------------------------------------------------------ chat */

function renderExamples() {
  $("#examples").innerHTML =
    EXAMPLES.map((e) => `<button class="example" data-q="${esc(e.q)}"><small>${esc(e.cat)}</small>${esc(e.q)}</button>`).join("") +
    `<p class="muted small" style="grid-column:1/-1;margin:6px 0 0;text-align:center">
       Tip: after the first answer, ask a follow-up such as <b>“How about hearing?”</b> to see conversational query rewriting.</p>`;
}

function turnHtml(t, idx) {
  let body;
  if (t.status === "error") {
    body = `<div class="answer error-text">Something went wrong: ${esc(t.error)}</div>`;
  } else if (!t.answer) {
    const label = t.status === "retrieving" ? "Searching the knowledge base…" : "Generating answer…";
    body = `<div class="status-line"><span class="spinner"></span>${label}</div>`;
  } else {
    body = `<div class="answer ${t.status === "generating" ? "typing" : ""}">${renderMarkdown(t.answer, idx, t.sources.length)}</div>`;
  }

  let citations = "";
  if (t.status === "done" && t.cited.length) {
    citations = `<div class="citations"><b>Citations:</b>${t.cited
      .map((n) => {
        const s = t.sources[n - 1];
        return `<button class="chip" data-turn="${idx}" data-n="${n}"><span class="n">${n}.</span>${esc(s.filename)}${s.page ? ` · p.${s.page}` : ""}</button>`;
      }).join("")}</div>`;
  }
  const meta = t.status === "done" && t.timings
    ? `<div class="meta-line">${esc(t.thought?.mode || "")} retrieval · ${t.sources.length} sources · ${(t.timings.total / 1000).toFixed(2)} s · ${esc(t.thought?.chat_model || "")}</div>`
    : "";
  const sel = state.selected === idx;

  return `
    <div class="msg-user"><div class="bubble">${esc(t.q)}</div></div>
    <div class="msg-ai ${sel ? "selected" : ""}">
      <div class="card">
        <div class="ai-head">
          <i class="spark" data-icon="spark">${svg("spark")}</i>
          <div class="ai-actions">
            <button class="icon-btn ${sel && state.tab === "thought" ? "active" : ""}" data-act="thought" data-turn="${idx}" title="Show thought process" ${t.thought ? "" : "disabled"}>${icon("bulb")}</button>
            <button class="icon-btn ${sel && state.tab === "sources" ? "active" : ""}" data-act="sources" data-turn="${idx}" title="Show supporting content" ${t.thought ? "" : "disabled"}>${icon("list")}</button>
          </div>
        </div>
        ${body}${citations}${meta}
      </div>
    </div>`;
}

function renderTurn(idx) {
  let el = $(`#turn-${idx}`);
  if (!el) {
    $("#emptyState").classList.add("hidden");
    el = document.createElement("div");
    el.id = `turn-${idx}`;
    el.className = "turn";
    el.style.cssText = "display:flex;flex-direction:column;gap:14px";
    $("#messages").appendChild(el);
  }
  el.innerHTML = turnHtml(state.turns[idx], idx);
}

function renderAllTurns() {
  $$(".turn").forEach((el) => el.remove());
  state.turns.forEach((_, i) => renderTurn(i));
  $("#emptyState").classList.toggle("hidden", state.turns.length > 0);
}

function scrollChat(force = false) {
  const box = $("#messages");
  if (force || box.scrollHeight - box.scrollTop - box.clientHeight < 160) box.scrollTop = box.scrollHeight;
}

async function ask(question) {
  question = question.trim();
  if (!question || state.busy) return;
  state.busy = true;
  $("#sendBtn").disabled = true;

  const history = state.turns
    .filter((t) => t.status === "done")
    .flatMap((t) => [{ role: "user", content: t.q }, { role: "assistant", content: t.answer }]);
  const turn = { q: question, answer: "", status: "retrieving", sources: [], thought: null, cited: [], timings: null };
  state.turns.push(turn);
  const idx = state.turns.length - 1;
  renderTurn(idx);
  scrollChat(true);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [...history, { role: "user", content: question }], settings }),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = JSON.stringify((await res.json()).detail); } catch { /* ignore */ }
      throw new Error(detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line) handleEvent(idx, JSON.parse(line));
      }
    }
    if (turn.status !== "error") turn.status = "done";
  } catch (err) {
    turn.status = "error";
    turn.error = err.message;
  }
  renderTurn(idx);
  if (state.selected === idx) renderAnalysis();
  scrollChat();
  state.busy = false;
  $("#sendBtn").disabled = false;
}

function handleEvent(idx, event) {
  const turn = state.turns[idx];
  switch (event.type) {
    case "thought":
      turn.thought = event.data;
      break;
    case "sources":
      turn.sources = event.data;
      turn.status = "generating";
      selectTurn(idx, state.selected === null ? "sources" : state.tab === "citation" ? "sources" : state.tab);
      break;
    case "delta":
      turn.answer += event.data;
      break;
    case "done":
      turn.timings = event.data.timings_ms;
      turn.cited = event.data.cited;
      turn.status = "done";
      if (state.selected === idx) renderAnalysis();
      break;
    case "error":
      turn.status = "error";
      turn.error = event.data;
      break;
  }
  renderTurn(idx);
  scrollChat();
}

function selectTurn(idx, tab) {
  const prev = state.selected;
  state.selected = idx;
  if (tab) state.tab = tab;
  if (prev !== null && prev !== idx && state.turns[prev]) renderTurn(prev);
  renderTurn(idx);
  renderAnalysis();
}

function clearChat() {
  if (state.busy) return;
  state.turns = [];
  state.selected = null;
  state.citation = null;
  renderAllTurns();
  renderAnalysis();
}

/* ------------------------------------------------------------------ analysis panel */

function renderAnalysis() {
  const panel = $("#analysis");
  const turn = state.turns[state.selected];
  const open = Boolean(turn && turn.thought);
  panel.classList.toggle("hidden", !open);
  $(".chat-layout").classList.toggle("split", open);
  if (!open) return;

  $$(".tab", panel).forEach((b) => b.classList.toggle("active", b.dataset.tab === state.tab));
  const body = $("#analysisBody");
  if (state.tab === "thought") body.innerHTML = thoughtHtml(turn);
  else if (state.tab === "sources") body.innerHTML = sourcesHtml(turn, state.selected);
  else renderCitation();
}

const TIMING_LABELS = {
  query_rewrite: "Query rewrite", embed_query: "Embed query", vector_search: "Vector search",
  keyword_search: "Keyword search", fusion: "Rank fusion", generation: "LLM generation", total: "Total",
};

function thoughtHtml(t) {
  const th = t.thought;
  const rewritten = th.search_query.trim() !== th.question.trim();
  const timings = t.timings || {};
  const maxMs = Math.max(1, ...Object.values(timings));
  const modeLabel = { hybrid: "Hybrid (vector + keyword, RRF)", vector: "Vector only", keyword: "Keyword only" }[th.mode];

  return `
  <div class="steps">
    <div class="step-item"><div class="step-num">1</div><div>
      <h4>User question</h4><div class="quote">${esc(th.question)}</div>
    </div></div>

    <div class="step-item"><div class="step-num">2</div><div>
      <h4>Search query ${rewritten ? '<span class="tag accent">rewritten with chat history</span>' : '<span class="tag">used as-is</span>'}</h4>
      <p>${esc(th.search_query)}</p>
      <dl class="kv"><dt>Full-text query</dt><dd><code class="inline">${esc(th.keyword_query || "—")}</code></dd></dl>
    </div></div>

    <div class="step-item"><div class="step-num">3</div><div>
      <h4>Retrieval</h4>
      <dl class="kv">
        <dt>Mode</dt><dd>${esc(modeLabel)}</dd>
        <dt>Vector search</dt><dd>${th.mode === "keyword" ? "skipped" : `${th.vector_candidates} candidates · cosine similarity on pgvector HNSW index`}</dd>
        <dt>Keyword search</dt><dd>${th.mode === "vector" ? "skipped" : `${th.keyword_candidates} candidates · PostgreSQL tsvector + ts_rank_cd (GIN index)`}</dd>
        <dt>Fusion</dt><dd>Reciprocal Rank Fusion, k = ${th.rrf_k} → top ${th.top_k} passages</dd>
        <dt>Embeddings</dt><dd>${esc(th.embedding_model)}</dd>
      </dl>
    </div></div>

    <div class="step-item"><div class="step-num">4</div><div>
      <h4>Grounded answer generation</h4>
      <dl class="kv">
        <dt>Model</dt><dd>${esc(th.chat_model)}</dd>
        <dt>Context</dt><dd>${t.sources.length} numbered passages, answer must cite them</dd>
        <dt>Cited</dt><dd>${t.cited.length ? t.cited.map((n) => `[${n}]`).join(" ") : t.status === "done" ? "none" : "…"}</dd>
      </dl>
    </div></div>

    <div class="step-item"><div class="step-num">5</div><div>
      <h4>Latency</h4>
      ${Object.keys(timings).length ? Object.entries(timings).map(([k, v]) => `
        <div class="timing"><span>${esc(TIMING_LABELS[k] || k)}</span>
          <div class="track"><div class="fill" style="width:${Math.max(2, (v / maxMs) * 100)}%"></div></div>
          <span class="ms">${v >= 1000 ? (v / 1000).toFixed(2) + " s" : v.toFixed(0) + " ms"}</span></div>`).join("")
        : '<p class="muted">Waiting for the answer to finish…</p>'}
    </div></div>

    <div class="step-item"><div class="step-num">6</div><div>
      <h4>Prompt sent to the model</h4>
      <details class="prompt"><summary>Show ${th.prompt.length} messages</summary>
        ${th.prompt.map((m) => `<div class="prompt-msg"><div class="role">${esc(m.role)}</div><pre>${esc(m.content)}</pre></div>`).join("")}
      </details>
    </div></div>
  </div>`;
}

function scoreBadges(s, mode) {
  const parts = [];
  if (mode !== "keyword") {
    parts.push(s.vector_rank
      ? `<span class="score vector">Vector #${s.vector_rank} · cos ${s.vector_score.toFixed(3)}</span>`
      : `<span class="score vector">Vector — not in top candidates</span>`);
  }
  if (mode !== "vector") {
    parts.push(s.keyword_rank
      ? `<span class="score keyword">Keyword #${s.keyword_rank} · rank ${s.keyword_score.toFixed(3)}</span>`
      : `<span class="score keyword">Keyword — no term match</span>`);
  }
  parts.push(`<span class="score rrf">RRF ${s.rrf_score.toFixed(4)}</span>`);
  return parts.join("");
}

function sourcesHtml(t, idx) {
  if (!t.sources.length) return `<div class="placeholder">No passages were retrieved for this question.</div>`;
  const terms = (t.thought.keyword_query || "").split(" | ").filter(Boolean);
  return `
    <div class="legend">
      <span>${t.sources.length} passages sent to the model, ranked by fused relevance.</span>
      <span>Highlighted words matched the full-text query.</span>
    </div>
    ${t.sources.map((s, i) => {
      const n = i + 1;
      const pct = Math.round(s.relevance * 100);
      return `
      <div class="source-card ${t.cited.includes(n) ? "cited" : ""}">
        <div class="source-top">
          <span class="source-n">${n}</span>
          <div class="source-file">${esc(s.filename)}${s.page ? `<span class="page"> · page ${s.page}</span>` : ""}</div>
          <div class="relevance"><b>${pct}%</b><span>relevance</span></div>
        </div>
        <div class="source-heading">${esc(s.heading || "")}${t.cited.includes(n) ? '<span class="tag accent">cited in answer</span>' : ""}</div>
        <div class="bar"><div style="width:${pct}%"></div></div>
        <div class="scores">${scoreBadges(s, t.thought.mode)}</div>
        <div class="snippet" id="snip-${n}">${highlightTerms(s.content, terms)}</div>
        <div class="source-actions">
          <button class="link-btn" data-expand="snip-${n}">Show full passage</button>
          <button class="link-btn" data-cite-turn="${idx}" data-cite-n="${n}">View in document →</button>
        </div>
      </div>`;
    }).join("")}`;
}

async function getDocument(id) {
  if (!state.docCache.has(id)) state.docCache.set(id, api(`/api/documents/${id}`));
  try {
    return await state.docCache.get(id);
  } catch (err) {
    state.docCache.delete(id);
    throw err;
  }
}

function openCitation(turnIdx, n) {
  state.citation = { turn: turnIdx, n };
  selectTurn(turnIdx, "citation");
}

async function renderCitation() {
  const body = $("#analysisBody");
  const c = state.citation;
  const turn = c && state.turns[c.turn];
  if (!turn || c.turn !== state.selected || !turn.sources[c.n - 1]) {
    body.innerHTML = `<div class="placeholder">${icon("quote")}<br>Click a citation number in an answer, or “View in document” in Supporting content,<br>to open the source document with the passage highlighted.</div>`;
    return;
  }
  const s = turn.sources[c.n - 1];
  body.innerHTML = `<div class="status-line"><span class="spinner"></span>Loading ${esc(s.filename)}…</div>`;

  let doc;
  try {
    doc = await getDocument(s.document_id);
  } catch (err) {
    body.innerHTML = `<div class="placeholder error-text">Could not load the document: ${esc(err.message)}</div>`;
    return;
  }
  if (state.tab !== "citation" || state.citation !== c) return;

  const previewable = doc.file_type !== "docx";
  const view = previewable ? state.citationView : "passage";
  const fileUrl = `/api/documents/${s.document_id}/file${doc.file_type === "pdf" && s.page ? `#page=${s.page}` : ""}`;
  const content = doc.content || "";

  body.innerHTML = `
    <div class="viewer-head">
      ${fileIcon(doc.file_type)}
      <div><h4>[${c.n}] ${esc(doc.title || doc.filename)}</h4>
        <p>${esc(doc.filename)}${s.page ? ` · page ${s.page}${doc.num_pages ? ` of ${doc.num_pages}` : ""}` : ""} · chunk #${s.chunk_index + 1} of ${doc.num_chunks}</p></div>
    </div>
    <div class="viewer-tools">
      <div class="segmented" style="width:320px">
        <button data-cview="passage" class="${view === "passage" ? "active" : ""}">Highlighted passage</button>
        <button data-cview="original" class="${view === "original" ? "active" : ""}" ${previewable ? "" : "disabled title='DOCX cannot be previewed in the browser'"}>Original file</button>
      </div>
      <a class="link-btn" href="/api/documents/${s.document_id}/file" target="_blank" rel="noopener">Open / download ${icon("external")}</a>
    </div>
    ${view === "original"
      ? `<iframe class="doc-frame" src="${fileUrl}" title="${esc(doc.filename)}"></iframe>`
      : `<div class="doc-text">${esc(content.slice(0, s.start_char))}<mark id="hl">${esc(content.slice(s.start_char, s.end_char))}</mark>${esc(content.slice(s.end_char))}</div>`}`;
  const mark = $("#hl");
  if (mark) {
    const box = mark.closest(".doc-text");
    box.scrollTop = Math.max(0, mark.offsetTop - box.clientHeight / 4);
  }
}

/* ------------------------------------------------------------------ documents */

let docsTimer = null;
const WORKING = new Set(["queued", "parsing", "chunking", "embedding"]);

async function refreshDocs() {
  clearTimeout(docsTimer);
  let docs;
  try {
    [docs] = await Promise.all([api("/api/documents"), refreshHealth()]);
  } catch (err) {
    toast(`Could not load documents: ${err.message}`);
    return;
  }
  const h = state.health || {};
  const ready = docs.filter((d) => d.status === "ready");
  const working = docs.filter((d) => WORKING.has(d.status));
  $("#docStats").innerHTML = `
    <div class="stat"><span>Documents</span><b>${docs.length}</b></div>
    <div class="stat"><span>Indexed</span><b>${ready.length}${working.length ? ` <small class="muted" style="font-size:13px">+${working.length} processing</small>` : ""}</b></div>
    <div class="stat"><span>Chunks</span><b>${ready.reduce((a, d) => a + d.num_chunks, 0)}</b></div>
    <div class="stat"><span>Embedding model</span><b class="sm">${esc(h.embedding_model || "—")}</b></div>`;

  $("#docEmpty").classList.toggle("hidden", docs.length > 0);
  $("#docRows").innerHTML = docs.map((d) => {
    const status = d.status === "ready"
      ? `<span class="badge ready">Ready</span>`
      : d.status === "failed"
        ? `<span class="badge failed" title="${esc(d.error)}">Failed</span>`
        : `<span class="badge working"><span class="spinner"></span>${esc(d.status)}</span>`;
    return `<tr>
      <td><div class="doc-name">${fileIcon(d.file_type)}<div><b>${esc(d.filename)}</b><small>${esc(d.title || "")}</small></div></div></td>
      <td>${esc(d.file_type.toUpperCase())}</td>
      <td>${d.num_pages ?? "—"}</td>
      <td>${d.status === "ready" ? d.num_chunks : "—"}</td>
      <td>${fmtBytes(d.size_bytes)}</td>
      <td>${status}</td>
      <td class="muted">${d.processing_ms ? `${(d.processing_ms / 1000).toFixed(2)} s` : "—"}</td>
      <td><div class="row-actions">
        <button class="icon-btn" title="Inspect chunks" data-chunks="${d.id}" ${d.status === "ready" ? "" : "disabled"}>${icon("layers")}</button>
        <a class="icon-btn" title="Open original" href="/api/documents/${d.id}/file" target="_blank" rel="noopener">${icon("external")}</a>
        <button class="icon-btn" title="Delete" data-delete="${d.id}">${icon("trash")}</button>
      </div></td>
    </tr>`;
  }).join("");

  if (working.length) docsTimer = setTimeout(refreshDocs, 1200);
}

async function uploadFiles(fileList) {
  const files = [...fileList];
  if (!files.length) return;
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  toast(`Uploading ${files.length} file(s)…`);
  try {
    const { results } = await api("/api/documents", { method: "POST", body: form });
    const count = (s) => results.filter((r) => r.status === s).length;
    const rejected = results.filter((r) => r.status === "rejected");
    toast(`${count("queued")} queued · ${count("duplicate")} duplicate · ${rejected.length} rejected` +
      (rejected.length ? ` (${rejected[0].filename}: ${rejected[0].error})` : ""));
  } catch (err) {
    toast(`Upload failed: ${err.message}`);
  }
  state.docCache.clear();
  refreshDocs();
}

async function loadSamples() {
  try {
    const r = await api("/api/documents/sample", { method: "POST" });
    toast(`${r.queued} sample documents queued for ingestion${r.skipped ? ` (${r.skipped} already indexed)` : ""}`);
    showView("docs");
  } catch (err) {
    toast(`Failed: ${err.message}`);
  }
}

async function reindexAll() {
  if (!confirm("Re-parse, re-chunk and re-embed every document?")) return;
  const r = await api("/api/documents/reindex", { method: "POST" });
  state.docCache.clear();
  toast(`${r.queued} documents queued for re-indexing`);
  showView("docs");
}

async function showChunks(id) {
  const [doc, chunks] = await Promise.all([getDocument(id), api(`/api/documents/${id}/chunks`)]);
  $("#chunkModalTitle").textContent = doc.filename;
  const avg = chunks.length ? Math.round(chunks.reduce((a, c) => a + c.chars, 0) / chunks.length) : 0;
  $("#chunkModalSub").textContent = `${chunks.length} chunks · average ${avg} characters · embedded with ${doc.embedding_model}`;
  $("#chunkModalBody").innerHTML = chunks.map((c) => `
    <div class="chunk">
      <div class="chunk-meta"><b>#${c.chunk_index + 1}</b>${c.page ? `<span>page ${c.page}</span>` : ""}<span>${c.chars} chars</span>
        <span>chars ${c.start_char}–${c.end_char}</span><span class="tag">${esc(c.heading || "")}</span></div>
      <pre>${esc(c.content)}</pre>
    </div>`).join("");
  $("#chunkModal").classList.remove("hidden");
}

/* ------------------------------------------------------------------ retrieval lab */

const LAB_EXAMPLES = [
  "HX-220 offline storage",
  "What happens if I lose my laptop?",
  "RB-SEC-007 severity levels",
  "money for a desk and chair at home",
  "form COI-1",
  "How long do we keep Slack messages?",
];

const LAB_MODES = [
  { mode: "vector", title: "Vector search", sub: "pgvector cosine similarity", color: "var(--vector)", score: (h) => h.vector_score, label: (h) => `cos ${h.vector_score.toFixed(3)}` },
  { mode: "keyword", title: "Keyword search", sub: "PostgreSQL full-text (ts_rank_cd)", color: "var(--keyword)", score: (h) => h.keyword_score, label: (h) => `rank ${h.keyword_score.toFixed(3)}` },
  { mode: "hybrid", title: "Hybrid (RRF)", sub: "Reciprocal Rank Fusion of both", color: "var(--accent)", score: (h) => h.relevance, label: (h) => `RRF ${h.rrf_score.toFixed(4)} · V${h.vector_rank ?? "–"} K${h.keyword_rank ?? "–"}` },
];

async function runLab(query) {
  query = query.trim();
  if (!query) return;
  const topK = parseInt($("#labTopK").value, 10);
  $("#labGrid").innerHTML = LAB_MODES.map((m) => `<div class="lab-col"><div class="lab-col-head"><div><h4><span class="sw" style="background:${m.color}"></span>${m.title}</h4><p>${m.sub}</p></div></div><div class="lab-hit"><span class="spinner"></span></div></div>`).join("");
  try {
    const responses = await Promise.all(LAB_MODES.map((m) => api("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, mode: m.mode, top_k: topK, candidates: settings.candidates, rrf_k: settings.rrf_k }),
    })));
    $("#labGrid").innerHTML = LAB_MODES.map((m, i) => {
      const { results, stats } = responses[i];
      const max = Math.max(1e-9, ...results.map(m.score));
      const ms = Object.values(stats.timings_ms).reduce((a, b) => a + b, 0);
      return `<div class="lab-col">
        <div class="lab-col-head"><div><h4><span class="sw" style="background:${m.color}"></span>${m.title}</h4><p>${m.sub}</p></div><span class="muted small">${ms.toFixed(0)} ms</span></div>
        ${results.length ? results.map((h) => `
          <div class="lab-hit" data-chunk="${h.chunk_id}">
            <span class="r">${h.rank}</span>
            <div><b>${esc(h.filename)}${h.page ? ` · p.${h.page}` : ""}</b><small>${esc(h.heading || "")}</small>
              <div class="minibar"><div style="width:${(m.score(h) / max) * 100}%;background:${m.color}"></div></div>
              <div class="sc">${m.label(h)}</div></div>
          </div>`).join("") : '<div class="lab-hit"><span></span><span class="muted">No results</span></div>'}
      </div>`;
    }).join("");
  } catch (err) {
    $("#labGrid").innerHTML = `<div class="placeholder error-text">${esc(err.message)}</div>`;
  }
}

/* ------------------------------------------------------------------ settings */

function syncSettingsUI() {
  $$("#modeSeg button").forEach((b) => b.classList.toggle("active", b.dataset.mode === settings.mode));
  $("#topK").value = settings.top_k; $("#topKVal").textContent = settings.top_k;
  $("#candidates").value = settings.candidates; $("#candVal").textContent = settings.candidates;
  $("#rrfK").value = settings.rrf_k; $("#rrfVal").textContent = settings.rrf_k;
  $("#temperature").value = settings.temperature; $("#tempVal").textContent = settings.temperature;
  $("#queryRewrite").checked = settings.query_rewrite;
}

function saveSettings() {
  localStorage.setItem("rag.settings", JSON.stringify(settings));
  syncSettingsUI();
  refreshHealth();
}

function toggleDrawer(open) {
  $("#settingsDrawer").classList.toggle("open", open);
  $("#overlay").classList.toggle("hidden", !open);
}

/* ------------------------------------------------------------------ wiring */

function init() {
  hydrateIcons();
  renderExamples();
  syncSettingsUI();
  refreshHealth();

  $$(".nav-btn").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));

  const textarea = $("#question");
  const autosize = () => { textarea.style.height = "auto"; textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`; };
  textarea.addEventListener("input", autosize);
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#composer").requestSubmit(); }
  });
  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = textarea.value;
    textarea.value = "";
    autosize();
    ask(q);
  });

  $("#messages").addEventListener("click", (e) => {
    const example = e.target.closest(".example");
    if (example) return ask(example.dataset.q);
    const cite = e.target.closest(".cite, .chip");
    if (cite) return openCitation(+cite.dataset.turn, +cite.dataset.n);
    const act = e.target.closest("[data-act]");
    if (act && !act.disabled) {
      const idx = +act.dataset.turn;
      if (state.selected === idx && state.tab === act.dataset.act && !$("#analysis").classList.contains("hidden")) {
        state.selected = null;
        renderAllTurns();
        return renderAnalysis();
      }
      selectTurn(idx, act.dataset.act);
    }
  });

  $$("#analysis .tab").forEach((b) => b.addEventListener("click", () => { state.tab = b.dataset.tab; renderTurn(state.selected); renderAnalysis(); }));
  $("#closeAnalysis").addEventListener("click", () => { const prev = state.selected; state.selected = null; if (prev !== null) renderTurn(prev); renderAnalysis(); });
  $("#analysisBody").addEventListener("click", (e) => {
    const expand = e.target.closest("[data-expand]");
    if (expand) {
      const snip = document.getElementById(expand.dataset.expand);
      snip.classList.toggle("expanded");
      expand.textContent = snip.classList.contains("expanded") ? "Collapse" : "Show full passage";
      return;
    }
    const cite = e.target.closest("[data-cite-n]");
    if (cite) return openCitation(+cite.dataset.citeTurn, +cite.dataset.citeN);
    const cview = e.target.closest("[data-cview]");
    if (cview && !cview.disabled) { state.citationView = cview.dataset.cview; renderCitation(); }
  });

  $("#clearChat").addEventListener("click", clearChat);
  $("#openSettings").addEventListener("click", () => toggleDrawer(true));
  $("#closeSettings").addEventListener("click", () => toggleDrawer(false));
  $("#saveSettings").addEventListener("click", () => { saveSettings(); toggleDrawer(false); });
  $("#overlay").addEventListener("click", () => toggleDrawer(false));
  $("#resetSettings").addEventListener("click", () => { settings = { ...DEFAULTS }; saveSettings(); });
  $$("#modeSeg button").forEach((b) => b.addEventListener("click", () => { settings.mode = b.dataset.mode; saveSettings(); }));
  const bindRange = (id, key, parse) => $(id).addEventListener("input", (e) => { settings[key] = parse(e.target.value); saveSettings(); });
  bindRange("#topK", "top_k", (v) => parseInt(v, 10));
  bindRange("#candidates", "candidates", (v) => parseInt(v, 10));
  bindRange("#rrfK", "rrf_k", (v) => parseInt(v, 10));
  bindRange("#temperature", "temperature", parseFloat);
  $("#queryRewrite").addEventListener("change", (e) => { settings.query_rewrite = e.target.checked; saveSettings(); });

  const drop = $("#dropzone");
  $("#fileInput").addEventListener("change", (e) => { uploadFiles(e.target.files); e.target.value = ""; });
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("drag"); }));
  drop.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));

  $("#loadSamples").addEventListener("click", loadSamples);
  $("#reindexAll").addEventListener("click", reindexAll);
  $("#deleteAll").addEventListener("click", async () => {
    if (!confirm("Delete every document and its chunks?")) return;
    const r = await api("/api/documents", { method: "DELETE" });
    state.docCache.clear();
    toast(`${r.deleted} documents deleted`);
    refreshDocs();
  });
  $("#docRows").addEventListener("click", async (e) => {
    const chunks = e.target.closest("[data-chunks]");
    if (chunks) return showChunks(chunks.dataset.chunks).catch((err) => toast(err.message));
    const del = e.target.closest("[data-delete]");
    if (del && confirm("Delete this document?")) {
      await api(`/api/documents/${del.dataset.delete}`, { method: "DELETE" });
      state.docCache.delete(del.dataset.delete);
      refreshDocs();
    }
  });
  $("#closeChunkModal").addEventListener("click", () => $("#chunkModal").classList.add("hidden"));
  $("#chunkModal").addEventListener("click", (e) => { if (e.target.id === "chunkModal") e.target.classList.add("hidden"); });

  $("#labExamples").innerHTML = LAB_EXAMPLES.map((q) => `<button data-q="${esc(q)}">${esc(q)}</button>`).join("");
  $("#labExamples").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) { $("#labQuery").value = b.dataset.q; runLab(b.dataset.q); }
  });
  $("#labForm").addEventListener("submit", (e) => { e.preventDefault(); runLab($("#labQuery").value); });
  $("#labGrid").addEventListener("mouseover", (e) => {
    const hit = e.target.closest("[data-chunk]");
    $$(".lab-hit.hover").forEach((el) => el.classList.remove("hover"));
    if (hit) $$(`[data-chunk="${hit.dataset.chunk}"]`).forEach((el) => el.classList.add("hover"));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { toggleDrawer(false); $("#chunkModal").classList.add("hidden"); }
  });
}

init();
