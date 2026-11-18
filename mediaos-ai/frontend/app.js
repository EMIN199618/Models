"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const CT = { official: "Rəsmi", media: "Media", public_opinion: "İctimai rəy" };
const SENT = { positive: "müsbət", neutral: "neytral", negative: "mənfi" };
const CAT = {
  customs_operations: "Gömrük əməliyyatları", smuggling: "Qaçaqmalçılıq", legislation: "Qanunvericilik",
  digital_services: "Rəqəmsal xidmətlər", service_quality: "Xidmət keyfiyyəti", corruption_allegation: "Korrupsiya iddiası",
  revenue_statistics: "Gəlir/statistika", international: "Beynəlxalq", management: "Rəhbərlik", other: "Digər",
};
const RISK = { low: "aşağı", medium: "orta", high: "yüksək" };

let token = "";
let me = null;
let conversationId = null;
let ct = "";

function store(k, v) { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (_) {} }
function load(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts.headers || {}) } });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    throw new Error(`${r.status}: ${typeof msg === "string" ? msg : JSON.stringify(msg)}`);
  }
  return r.status === 204 ? null : r.json();
}

async function login() {
  token = $("#token").value.trim();
  try {
    me = await api("/api/me");
  } catch (e) {
    alert("Daxil olmaq mümkün olmadı: " + e.message);
    return;
  }
  store("mos_token", token);
  $("#who").textContent = `${me.display_name} · ${me.role}`;
  $("#welcome").hidden = true;
  $("#app").hidden = false;
  const analyst = me.role !== "viewer";
  $("#reviewCard").hidden = !analyst;
  $("#metricsCard").hidden = !analyst;
  $("#edCard").hidden = me.role !== "admin";
  refresh();
}

function refresh() {
  loadStats();
  loadNews();
  if (me.role !== "viewer") { loadReview(); loadMetrics(); }
  if (me.role === "admin") loadED();
}

function kpi(v, l) { return `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`; }
function rows(obj, map) {
  return Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([k, v]) => `<div class="row"><span>${esc((map && map[k]) || k)}</span><b>${v}</b></div>`).join("") || '<div class="muted">—</div>';
}

async function loadStats() {
  const days = $("#days").value;
  const s = await api(`/api/dashboard/stats?days=${days}`);
  const neg = s.by_sentiment.negative || 0;
  $("#kpis").innerHTML = [
    kpi(s.total, `DGK xəbəri (${days} gün)`),
    kpi(s.by_content_type.official || 0, "Rəsmi"),
    kpi(s.by_content_type.media || 0, "Media"),
    kpi(s.by_content_type.public_opinion || 0, "İctimai rəy / şikayət"),
    kpi(s.total ? Math.round((100 * neg) / s.total) + "%" : "—", "Mənfi tonallıq"),
    kpi((s.by_risk.high || 0) + " / " + (s.by_risk.medium || 0), "Yüksək / orta risk"),
    kpi(s.pending_review, "İnsan yoxlaması gözləyir"),
    kpi(s.filtered_irrelevant, "Əlaqəsiz kimi süzülüb"),
  ].join("");
  const max = Math.max(1, ...s.daily.map((d) => d.total));
  $("#chart").innerHTML = s.daily.map((d) =>
    `<div class="bar" title="${esc(d.day)}: ${d.total} xəbər, ${d.negative} mənfi">
       <div class="t" style="height:${(100 * (d.total - d.negative)) / max}%"></div>
       <div class="n" style="height:${(100 * d.negative) / max}%"></div></div>`).join("") || '<div class="muted">Məlumat yoxdur</div>';
  $("#splits").innerHTML =
    `<div><h3>Kateqoriya</h3>${rows(s.by_category, CAT)}</div>` +
    `<div><h3>Sentiment</h3>${rows(s.by_sentiment, SENT)}</div>` +
    `<div><h3>Gömrük postu / yer</h3>${rows(s.by_location)}</div>`;
}

async function loadNews() {
  const items = await api(`/api/news/latest?limit=30${ct ? "&content_type=" + ct : ""}`);
  $("#news tbody").innerHTML = items.map((n) => `<tr>
    <td class="d">${esc(n.published_at.slice(0, 16).replace("T", " "))}</td>
    <td>${n.platform ? `<span class="plat ${esc(n.platform)}">${esc(n.platform)}</span>` : ""}${n.url && !n.is_synthetic ? `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` : esc(n.title)}${n.is_synthetic ? '<span class="synthetic">nümunə</span>' : ""}${engText(n.engagement)}</td>
    <td>${esc(n.source)}${n.author ? `<span class="eng">${esc(n.author)}</span>` : ""}</td>
    <td class="ct-${esc(n.content_type)}">${esc(CT[n.content_type])}</td>
    <td>${esc(CAT[n.category] || n.category || "—")}</td>
    <td class="s-${esc(n.sentiment)}">${esc(SENT[n.sentiment] || "—")}</td>
    <td class="r-${esc(n.risk_level)}">${esc(RISK[n.risk_level] || "—")}${n.risk_status === "pending_review" ? " ⏳" : n.risk_status === "confirmed" ? " ✓" : ""}</td>
  </tr>`).join("") || '<tr><td colspan="7" class="muted">Xəbər yoxdur</td></tr>';
}

function fmtN(v) { return v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? (v / 1e3).toFixed(1) + "K" : String(v); }
function engText(e) {
  if (!e) return "";
  const parts = [["views", "baxış"], ["likes", "bəyənmə"], ["comments", "şərh"], ["shares", "paylaşım"]]
    .filter(([k]) => e[k]).map(([k, l]) => `${fmtN(e[k])} ${l}`);
  return parts.length ? `<span class="eng">${parts.join(" · ")}</span>` : "";
}

const list = (id) => $(id).value.split(",").map((x) => x.trim()).filter(Boolean);
async function loadED() {
  const s = await api("/api/integrations/ensembledata");
  $("#edStatus").textContent = s.configured ? `token: ${s.token} (${s.token_source === "admin_panel" ? "admin panel" : "mühit dəyişəni"})${s.running ? " · toplama gedir…" : ""}` : "token daxil edilməyib";
  const c = s.config;
  $("#edKw").value = c.tiktok_keywords.join(", "); $("#edTags").value = c.tiktok_hashtags.join(", ");
  $("#edIgOff").value = c.instagram_official_accounts.join(", "); $("#edIgMedia").value = c.instagram_media_accounts.join(", ");
  $("#edTtOff").value = c.tiktok_official_accounts.join(", ");
  $("#edUnits").placeholder = `unit limiti (indiki: ${c.max_units_per_run})`;
  const r = s.last_result;
  if (r) {
    $("#edResult").innerHTML = r.error ? `<span class="s-negative">${esc(r.error)}</span>` :
      `Son toplama: ${r.collector.new ?? 0} yeni element, ${r.relevant} DGK-ya aid, ${r.irrelevant} əlaqəsiz, ${r.risk_pending} risk yoxlamaya, ${r.collector.units_spent} unit xərcləndi` +
      (r.collector_errors && r.collector_errors.length ? `<br><span class="r-medium">${esc(r.collector_errors.join("; "))}</span>` : "");
  } else if (s.runs[0]) {
    const x = s.runs[0];
    $("#edResult").textContent = `Son toplama ${x.started_at.slice(0, 16).replace("T", " ")}: ${x.inserted} əlavə, ${x.irrelevant} əlaqəsiz${x.error ? " · " + x.error : ""}`;
  }
  if (s.running) setTimeout(() => loadED().then(refresh), 4000);
}
$("#edTokenForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const t = $("#edToken").value.trim(); if (!t) return;
  $("#edResult").textContent = "Token yoxlanılır…";
  try { const r = await api("/api/integrations/ensembledata/token", { method: "PUT", body: JSON.stringify({ token: t }) });
    $("#edToken").value = ""; $("#edResult").textContent = `Token saxlanıldı (${r.token}). Bu gün istifadə olunan unit: ${JSON.stringify(r.used_units_today)}`; loadED();
  } catch (err) { $("#edResult").innerHTML = `<span class="s-negative">${esc(err.message)}</span>`; }
});
$("#edSave").addEventListener("click", async () => {
  try { await api("/api/integrations/ensembledata/config", { method: "PUT", body: JSON.stringify({
      tiktok_keywords: list("#edKw"), tiktok_hashtags: list("#edTags"), instagram_official_accounts: list("#edIgOff"),
      instagram_media_accounts: list("#edIgMedia"), tiktok_official_accounts: list("#edTtOff") }) });
    $("#edResult").textContent = "Parametrlər saxlanıldı."; loadED();
  } catch (err) { $("#edResult").innerHTML = `<span class="s-negative">${esc(err.message)}</span>`; }
});
$("#edRun").addEventListener("click", async () => {
  const u = Number($("#edUnits").value) || null;
  try { await api("/api/integrations/ensembledata/run", { method: "POST", body: JSON.stringify({ max_units: u }) });
    $("#edResult").textContent = "Toplama başladı…"; setTimeout(loadED, 1500);
  } catch (err) { $("#edResult").innerHTML = `<span class="s-negative">${esc(err.message)}</span>`; }
});
$("#edDiscoverForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try { const users = await api("/api/integrations/ensembledata/discover", { method: "POST", body: JSON.stringify({ query: $("#edDiscover").value }) });
    $("#edFound").innerHTML = users.map((u) => `<div>@${esc(u.username)} — ${esc(u.full_name || "")}${u.is_verified ? " ✓" : ""}</div>`).join("") || "Tapılmadı";
  } catch (err) { $("#edFound").innerHTML = `<span class="s-negative">${esc(err.message)}</span>`; }
});

async function loadReview() {
  const items = await api("/api/review?status=pending");
  $("#reviewCount").textContent = `${items.length} gözləyir`;
  $("#review").innerHTML = items.slice(0, 15).map((r) => {
    const what = r.news ? esc(r.news.title) : r.report_id ? `Hesabat #${r.report_id}: ${esc(r.payload.title || "")}` : "";
    const det = r.kind === "risk" ? `Risk: ${esc(RISK[r.payload.level])}; ${esc((r.payload.reasons || []).join("; "))}` :
      r.kind === "relevance" ? `Relevance etibarlılığı aşağıdır: ${esc(r.payload.reason)}` : "Dərc üçün admin təsdiqi";
    return `<div class="rv"><div><span class="tag">${esc(r.kind)}</span> ${what}</div><div class="muted">${det}</div>
      <div class="acts"><button data-rv="${r.id}" data-ok="1">Təsdiq et</button><button class="ghost" data-rv="${r.id}" data-ok="0">Rədd et</button></div></div>`;
  }).join("") || '<div class="muted">Gözləyən element yoxdur</div>';
}

async function decide(id, ok) {
  try {
    await api(`/api/review/${id}/decide`, { method: "POST", body: JSON.stringify({ approve: ok }) });
    refresh();
  } catch (e) { alert(e.message); }
}

async function loadMetrics() {
  const m = await api("/api/metrics?hours=24");
  const c = m.cache.process || {};
  const lat = Object.entries(m.api_latency).filter(([k]) => k.startsWith("/api")).slice(0, 5)
    .map(([k, v]) => `<div class="row"><span>${esc(k.replace("/api/", ""))}</span><b>${v.p50_ms} / ${v.p95_ms} ms</b></div>`).join("");
  const llm = Object.entries(m.llm).map(([k, v]) => `<div class="row"><span>${esc(k)}</span><b>${v.calls} · ${v.input_tokens + v.output_tokens} tok · $${v.cost_usd}</b></div>`).join("");
  const tools = Object.entries(m.tools).map(([k, v]) => `<div class="row"><span>${esc(k)}</span><b>${Math.round((v.success_rate || 0) * 100)}%</b></div>`).join("");
  $("#metrics").innerHTML =
    `<div class="box"><h3>Redis keş</h3><div class="row"><span>Hit rate</span><b>${c.hit_rate == null ? "—" : Math.round(c.hit_rate * 100) + "%"}</b></div>
      <div class="row"><span>Hit / miss</span><b>${c.hits ?? 0} / ${c.misses ?? 0}</b></div>
      <div class="row"><span>Vəziyyət</span><b>${m.cache.up ? "işləyir" : "nasaz (PostgreSQL)"}</b></div>
      <div class="row"><span>Siyasət</span><b>${esc(m.cache.maxmemory_policy || "—")}</b></div></div>` +
    `<div class="box"><h3>API p50 / p95</h3>${lat || '<div class="muted">—</div>'}</div>` +
    `<div class="box"><h3>LLM (${esc(m.llm_provider.provider)})</h3>${llm || '<div class="muted">—</div>'}</div>` +
    `<div class="box"><h3>Alət uğuru</h3>${tools || '<div class="muted">—</div>'}</div>`;
}

function addMsg(cls, html) {
  const d = document.createElement("div");
  d.className = `msg ${cls}`;
  d.innerHTML = html;
  $("#messages").appendChild(d);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return d;
}

function renderAnswer(b) {
  const text = esc(b.answer).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/_(Vaxt aralığı[^_]*)_/g, '<span class="muted">$1</span>')
    .replace(/_(Təsdiq statusu[^_]*)_/g, '<span class="muted">$1</span>');
  const tools = b.tools.map((t) => `<span class="tag">🔧 ${esc(t.tool)}${t.status !== "ok" ? " ⚠" : ""}</span>`).join("");
  const uses = [b.uses.rag && "RAG", b.uses.memory.short_term_messages && "yaddaş", b.cached && "keş"].filter(Boolean)
    .map((u) => `<span class="tag">${esc(u)}</span>`).join("");
  const cites = b.citations.length ? `<span class="tag">${b.citations.length} mənbə</span>` : "";
  return `${text}<div class="meta">${tools}${uses}${cites}<span>${b.latency_ms} ms</span></div>`;
}

async function ask(q) {
  if (!q) return;
  addMsg("me", esc(q));
  const pending = addMsg("ai", '<span class="muted">Analiz edilir…</span>');
  $("#q").value = "";
  try {
    const b = await api("/api/chat", { method: "POST", body: JSON.stringify({ question: q, conversation_id: conversationId }) });
    conversationId = b.conversation_id;
    pending.innerHTML = renderAnswer(b);
  } catch (e) {
    pending.innerHTML = `<span class="s-negative">${esc(e.message)}</span>`;
  }
}

$("#login").addEventListener("click", login);
$("#token").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });
$("#days").addEventListener("change", loadStats);
$("#tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  ct = b.dataset.ct;
  document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
  loadNews();
});
$("#review").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-rv]"); if (b) decide(b.dataset.rv, b.dataset.ok === "1");
});
$("#refreshMetrics").addEventListener("click", loadMetrics);
$("#ask").addEventListener("submit", (e) => { e.preventDefault(); ask($("#q").value.trim()); });
$("#messages").addEventListener("click", (e) => { const c = e.target.closest(".chip"); if (c) ask(c.textContent); });
$("#newchat").addEventListener("click", () => { conversationId = null; $("#messages").innerHTML = ""; });

const saved = load("mos_token");
if (saved) { $("#token").value = saved; login(); }
