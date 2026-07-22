"use strict";

const state = {
  ticker: "BBCA",
  missionFilter: "ALL",
  feed: "announcements",
  evidence: null,
  missions: [],
  localLogs: [],
  mobileTab: "dossier",
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function escapeHTML(value) {
  const el = document.createElement("span");
  el.textContent = value == null ? "" : String(value);
  return el.innerHTML;
}

function safeURL(value) {
  try {
    const url = new URL(String(value || ""), window.location.origin);
    const officialIDX = url.protocol === "https:" && url.hostname === "www.idx.co.id";
    const safeAuthority = !(url.username || url.password) && !(url.port && url.port !== "443");
    return officialIDX && safeAuthority ? escapeHTML(url.href) : "#";
  } catch {
    return "#";
  }
}

function fmtDate(value, short = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHTML(value);
  return new Intl.DateTimeFormat("en-GB", short
    ? { day: "2-digit", month: "short", year: "numeric" }
    : { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
  ).format(date);
}

function fmtPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : "—";
}

function toast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  $("#toast-region").append(node);
  setTimeout(() => node.remove(), 3400);
}

function localLog(message, level = "INFO") {
  state.localLogs.unshift({ ts: new Date().toISOString(), level, msg: message });
  state.localLogs = state.localLogs.slice(0, 30);
  renderLogs();
}

async function request(path, options) {
  const response = await fetch(path, options);
  let payload;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) throw new Error(payload?.error || `${response.status} ${response.statusText}`);
  return payload;
}

function setSourceStatus(name, info = {}) {
  const root = $(`.source-status[data-source="${name}"]`);
  if (!root) return;
  root.classList.remove("error", "warning");
  const status = info.status || "unknown";
  if (status === "error") root.classList.add("error");
  if (status === "missing_api_key" || status === "unknown") root.classList.add("warning");
  $(`#${name.toLowerCase()}-health`).textContent = status.replaceAll("_", " ").toUpperCase();
  const latency = $(`#${name.toLowerCase()}-latency`);
  if (latency) latency.textContent = info.latency_ms != null ? `${info.latency_ms} MS` : "—";
}

async function loadHealth() {
  try {
    const payload = await request("/api/health");
    Object.entries(payload.sources || {}).forEach(([name, info]) => setSourceStatus(name, info));
    $("#last-check").textContent = fmtDate(payload.checked_at);
  } catch (error) {
    ["IDX", "BPS", "KSEI"].forEach(name => setSourceStatus(name, { status: "error" }));
    localLog(`Source health failed: ${error.message}`, "WARN");
  }
}

const universeState = { BBCA: "active", BBRI: "review", TLKM: "quiet", ASII: "stale", BMRI: "quiet" };

async function loadUniverse() {
  const container = $("#watchlist-container");
  container.innerHTML = '<div class="loading-state">Retrieving issuer universe…</div>';
  try {
    const rows = await request("/api/watchlist");
    container.innerHTML = rows.map(row => {
      const signal = universeState[row.ticker] || "quiet";
      return `<button class="issuer-button ${row.ticker === state.ticker ? "active" : ""}" data-ticker="${escapeHTML(row.ticker)}" type="button">
        <span class="issuer-code">${escapeHTML(row.ticker)}</span>
        <span class="issuer-copy"><b>${escapeHTML(row.name)}</b><small>${escapeHTML(row.sector || "IDX issuer")}</small></span>
        <span class="state-word ${signal}">${signal}</span>
      </button>`;
    }).join("");
    $$("[data-ticker]", container).forEach(button => button.addEventListener("click", () => selectTicker(button.dataset.ticker)));
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Universe unavailable: ${escapeHTML(error.message)}</div>`;
  }
}

function renderMissions() {
  const rows = state.missionFilter === "ALL" ? state.missions : state.missions.filter(row => row.state === state.missionFilter);
  $("#mission-container").innerHTML = rows.length ? rows.map(row => `<article class="mission-card">
    <div class="mission-top"><span class="state-badge ${escapeHTML(row.state)}">${escapeHTML(row.state)}</span><span class="mission-ticker">${escapeHTML(row.ticker || "GENERAL")}</span></div>
    <h3>${escapeHTML(row.title)}</h3>
    <p>${fmtDate(row.created_at)} · DEMO WORKFLOW</p>
  </article>`).join("") : '<div class="empty-state">No missions in this state.</div>';
}

async function loadMissions() {
  try { state.missions = await request("/api/missions"); renderMissions(); }
  catch (error) { $("#mission-container").innerHTML = `<div class="empty-state">Mission queue unavailable: ${escapeHTML(error.message)}</div>`; }
}

async function loadEvidence() {
  state.evidence = null;
  $("#data-mode").textContent = "OFFICIAL IDX · LOADING";
  try {
    const payload = await request(`/api/evidence/${encodeURIComponent(state.ticker)}?year=2025&period=audit`);
    state.evidence = payload;
    renderDossier(payload);
    renderEvidence(payload);
    renderFeed();
    localLog(`${state.ticker} official evidence synchronized`);
  } catch (error) {
    renderDossier({ ticker: state.ticker, channels: {}, official_only: false, error: error.message });
    $("#feed-content").innerHTML = `<div class="empty-state">Official evidence unavailable: ${escapeHTML(error.message)}. No replacement data was fabricated.</div>`;
    localLog(`${state.ticker} evidence unavailable: ${error.message}`, "WARN");
  }
}

function companyRecord(payload) {
  const envelope = payload.channels?.profile || {};
  return envelope.data || {};
}

function renderDossier(payload) {
  const profile = companyRecord(payload);
  const ticker = payload.ticker || state.ticker;
  $("#selected-ticker").textContent = ticker;
  $("#ticker-monogram").textContent = ticker.slice(0, 2);
  $("#company-name").textContent = profile.name || "Official profile unavailable";
  $("#company-sector").textContent = [profile.sector, profile.subsector, "IDX"].filter(Boolean).join(" · ") || "IDX official profile";
  $("#listing-board").textContent = profile.listing_board ? `${profile.listing_board} board` : "BOARD —";
  $("#business-activity").textContent = profile.business_activity || "No official business activity returned.";
  $("#listing-date").textContent = fmtDate(profile.listing_date, true);
  const controller = (profile.shareholders || []).find(row => row.controlling) || (profile.shareholders || [])[0];
  $("#controller-name").textContent = controller?.name || "Not returned";
  $("#controller-stake").textContent = controller ? `${fmtPercent(controller.percentage)} disclosed stake` : "—";
  const leadership = (profile.directors || []).length + (profile.commissioners || []).length;
  $("#leadership-count").textContent = leadership ? `${leadership} people` : "Not returned";
  const channels = Object.values(payload.channels || {}).filter(channel => channel.official && !channel.error).length;
  $("#evidence-channel-count").textContent = channels;
  $("#channel-progress").style.width = `${Math.min(100, channels / 3 * 100)}%`;
  $("#data-mode").textContent = payload.official_only ? "OFFICIAL IDX · VERIFIED" : "SOURCE CHANNEL DEGRADED";
  $("#data-mode").classList.toggle("warning", !payload.official_only);
}

function renderFeed() {
  const container = $("#feed-content");
  if (!state.evidence) return;
  const envelope = state.evidence.channels?.[state.feed] || {};
  const rows = Array.isArray(envelope.data) ? envelope.data : [];
  if (!rows.length) {
    container.innerHTML = `<div class="empty-state">No official ${escapeHTML(state.feed)} returned for ${escapeHTML(state.ticker)}.</div>`;
    return;
  }
  if (state.feed === "announcements") {
    container.innerHTML = rows.map(row => `<article class="feed-item">
      <time class="feed-date">${fmtDate(row.date, true)}</time>
      <div><h3 class="feed-title">${escapeHTML(row.title || row.subject || "IDX announcement")}</h3><p class="feed-subject">${escapeHTML(row.number || row.type || "Official disclosure")} · ${escapeHTML(row.subject || "")}</p></div>
      <div class="feed-actions">${(row.attachments || []).slice(0, 2).map((doc, index) => `<a class="document-link" href="${safeURL(doc.download_url)}" target="_blank" rel="noopener noreferrer">PDF ${index + 1}</a>`).join("")}</div>
    </article>`).join("");
  } else {
    container.innerHTML = rows.map(row => `<article class="feed-item">
      <div class="feed-date">${escapeHTML(row.year)}<br>${escapeHTML(row.period)}</div>
      <div><h3 class="feed-title">${escapeHTML(row.name || row.ticker)} — ${escapeHTML(row.period)} ${escapeHTML(row.year)}</h3><p class="feed-subject">${(row.attachments || []).length} original IDX attachments · no normalized comparison</p></div>
      <div class="feed-actions">${(row.attachments || []).filter(doc => ["pdf", "xlsx", "zip"].includes(doc.format)).slice(0, 3).map(doc => `<a class="document-link" href="${safeURL(doc.download_url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(doc.format.toUpperCase())}</a>`).join("")}</div>
    </article>`).join("");
  }
}

function renderEvidence(payload) {
  const content = $("#drawer-content");
  const groups = Object.entries(payload.channels || {}).map(([name, envelope]) => {
    const provenance = envelope.provenance || [];
    return `<section class="evidence-group"><h3>${escapeHTML(name.toUpperCase())} CHANNEL</h3>
      ${provenance.length ? provenance.map(source => `<div class="evidence-card"><b>${escapeHTML(source.provider || "IDX")} · ${source.official ? "OFFICIAL" : "UNVERIFIED"}</b><p>Format: ${escapeHTML(source.source_format || "unknown")}<br>Retrieved: ${fmtDate(source.retrieved_at)}<br><a href="${safeURL(source.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.source_url)}</a></p></div>`).join("") : `<div class="evidence-card"><b>No provenance returned</b><p>${escapeHTML(envelope.error || "This channel returned no source record.")}</p></div>`}
    </section>`;
  });
  content.innerHTML = `<div class="evidence-card"><b>${escapeHTML(payload.ticker)} evidence contract</b><p>Official-only: ${payload.official_only ? "YES" : "NO"}<br>Generated: ${fmtDate(payload.generated_at)}<br>No market price or recommendation included.</p></div>${groups.join("")}`;
}

async function loadOperations() {
  try {
    const rows = await request("/api/operations");
    $("#ops-content").innerHTML = rows.map(row => `<article class="operation-card">
      <div class="operation-head"><span class="operation-type">${escapeHTML(row.type).replaceAll("_", " ").toUpperCase()}</span><span class="operation-status">${escapeHTML(row.status).toUpperCase()}</span></div>
      <h3>${escapeHTML(row.description)}</h3>
      <div class="progress-track"><i style="width:${Math.round(Number(row.progress || 0) * 100)}%"></i></div>
      <div class="operation-foot"><span>${Math.round(Number(row.progress || 0) * 100)}%</span><span>DEMO SIGNAL</span></div>
    </article>`).join("");
  } catch (error) { $("#ops-content").innerHTML = `<div class="empty-state">Operations unavailable: ${escapeHTML(error.message)}</div>`; }
}

async function loadServerLogs() {
  try { state.serverLogs = await request("/api/log"); renderLogs(); }
  catch { state.serverLogs = []; renderLogs(); }
}

function renderLogs() {
  const rows = [...state.localLogs, ...(state.serverLogs || []).slice().reverse()].slice(0, 45);
  $("#log-container").innerHTML = rows.map(row => `<div class="log-row"><time class="log-time">${new Date(row.ts).toLocaleTimeString("en-GB", { hour12: false }).slice(0, 8)}</time><span class="log-level ${escapeHTML(row.level)}">${escapeHTML(row.level)}</span><span class="log-message">${escapeHTML(row.msg)}</span></div>`).join("");
}

async function selectTicker(ticker) {
  state.ticker = ticker;
  $("#mission-ticker").value = ticker;
  await loadUniverse();
  await loadEvidence();
}

function setFeed(name) {
  state.feed = name;
  $$(`[data-feed]`).forEach(button => button.classList.toggle("active", button.dataset.feed === name));
  renderFeed();
}

function openDrawer() {
  $("#evidence-drawer").setAttribute("aria-hidden", "false");
  $(".close-button", $("#evidence-drawer")).focus();
}
function closeDrawer() { $("#evidence-drawer").setAttribute("aria-hidden", "true"); }
function openModal() {
  $("#mission-modal").setAttribute("aria-hidden", "false");
  $("#mission-name").focus();
}
function closeModal() { $("#mission-modal").setAttribute("aria-hidden", "true"); }

function setMobileTab(tab) {
  state.mobileTab = tab;
  $$('[data-mobile-tab]').forEach(button => button.classList.toggle("active", button.dataset.mobileTab === tab));
  $$(".module").forEach(module => module.classList.remove("mobile-active"));
  if (tab === "dossier") {
    $(".situation-module").classList.add("mobile-active");
    $(".intelligence-module").classList.add("mobile-active");
  } else if (tab === "universe") $(".universe-module").classList.add("mobile-active");
  else if (tab === "missions") $(".mission-module").classList.add("mobile-active");
  else if (tab === "operations") $(".operations-module").classList.add("mobile-active");
  else $(".command-log-module").classList.add("mobile-active");
}

async function createMission(event) {
  event.preventDefault();
  const title = $("#mission-name").value.trim();
  const ticker = $("#mission-ticker").value.trim().toUpperCase();
  try {
    await request("/api/missions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, ticker }) });
    closeModal();
    event.target.reset();
    $("#mission-ticker").value = state.ticker;
    await loadMissions();
    await loadServerLogs();
    toast("Demo mission queued. No autonomous agent was started.");
  } catch (error) { toast(`Mission not created: ${error.message}`); }
}

function bindEvents() {
  $("#create-mission").addEventListener("click", openModal);
  $("#open-evidence").addEventListener("click", openDrawer);
  $$('[data-close-drawer]').forEach(node => node.addEventListener("click", closeDrawer));
  $$('[data-close-modal]').forEach(node => node.addEventListener("click", closeModal));
  $("#mission-form").addEventListener("submit", createMission);
  $$('[data-filter]').forEach(button => button.addEventListener("click", () => {
    state.missionFilter = button.dataset.filter;
    $$('[data-filter]').forEach(item => item.classList.toggle("active", item === button));
    renderMissions();
  }));
  $$('[data-feed]').forEach(button => button.addEventListener("click", () => setFeed(button.dataset.feed)));
  $$('[data-mobile-tab]').forEach(button => button.addEventListener("click", () => setMobileTab(button.dataset.mobileTab)));
  $("#clear-local-log").addEventListener("click", () => { state.localLogs = []; renderLogs(); });
  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "m") { event.preventDefault(); openModal(); }
    if (event.key === "Escape") { closeDrawer(); closeModal(); }
  });
}

async function init() {
  bindEvents();
  setMobileTab("dossier");
  localLog("Mission Control interface initialized");
  await Promise.all([loadHealth(), loadUniverse(), loadMissions(), loadOperations(), loadServerLogs()]);
  await loadEvidence();
  setInterval(loadHealth, 60_000);
}

document.addEventListener("DOMContentLoaded", init);
