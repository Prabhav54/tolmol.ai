"use strict";

const $ = (id) => document.getElementById(id);
const els = {
  home: $("view-home"), product: $("view-product"), form: $("search-form"), q: $("q"), go: $("go"),
  photo: $("photo"), status: $("status"), statusText: $("status-text"), error: $("error"),
  candidates: $("candidates"), interpretation: $("interpretation"), candidateGrid: $("candidate-grid"),
  recent: $("recent"), recentGrid: $("recent-grid"), health: $("health"),
};

const state = { view: null, chat: [], chart: null, busy: false };

// ---------- helpers ----------
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const money = (n) => (n == null ? "—" : "₹" + Math.round(Number(n)).toLocaleString("en-IN"));
const safeUrl = (u) => (typeof u === "string" && /^https?:\/\//i.test(u) ? u : null);
const isLink = (text) => /^https?:\/\//i.test(text.trim()) || /^(www\.)?[a-z0-9-]+\.(in|com|to|it)\//i.test(text.trim());
const initial = (title) => esc((title || "?").trim().charAt(0).toUpperCase());

async function api(path, options = {}) {
  const init = { method: options.method || "GET", headers: {} };
  if (options.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  let response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("Couldn't reach tolmol.ai. Check your connection and try again.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    let detail = data && data.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => String(d.msg || "").replace(/^Value error, /, "")).join(" ");
    throw new Error(detail || `Something went wrong (HTTP ${response.status}).`);
  }
  return data;
}

let statusTimer = null;
function showStatus(messages) {
  clearInterval(statusTimer);
  if (!messages) {
    els.status.hidden = true;
    return;
  }
  let i = 0;
  els.statusText.textContent = messages[0];
  els.status.hidden = false;
  if (messages.length > 1) {
    statusTimer = setInterval(() => {
      i = Math.min(i + 1, messages.length - 1);
      els.statusText.textContent = messages[i];
    }, 4500);
  }
}

function showError(message) {
  els.error.textContent = message || "";
  els.error.hidden = !message;
}

function setBusy(busy) {
  state.busy = busy;
  els.go.disabled = busy;
  els.q.disabled = busy;
  els.photo.disabled = busy;
}

const COMPARE_STEPS = [
  "Identifying the product…",
  "Searching Amazon, Flipkart and other stores…",
  "Matching the exact model and variant…",
  "Checking the store links still work…",
  "Almost there…",
];

// ---------- routing ----------
function goHome(push = true) {
  if (push) history.pushState({}, "", "/");
  destroyChart();
  els.product.hidden = true;
  els.product.innerHTML = "";
  els.home.hidden = false;
  document.title = "tolmol.ai — compare prices across Indian stores";
  loadRecent();
}

function showProduct(view, push = true) {
  state.view = view;
  state.chat = [];
  const id = view.product.id;
  if (push) history.pushState({ product: id }, "", id ? `/?product=${id}` : "/");
  els.home.hidden = true;
  els.product.hidden = false;
  renderProduct();
  window.scrollTo({ top: 0 });
  document.title = `${view.product.title} — tolmol.ai`;
}

async function openProduct(id, push = true) {
  els.home.hidden = false;
  els.product.hidden = true;
  showError("");
  showStatus(["Loading product…"]);
  try {
    showProduct(await api(`/api/products/${encodeURIComponent(id)}`), push);
  } catch (err) {
    showError(err.message);
  } finally {
    showStatus(null);
  }
}

window.addEventListener("popstate", () => {
  const id = new URLSearchParams(location.search).get("product");
  if (id) openProduct(id, false);
  else goHome(false);
});

// ---------- home: compare / search / photo ----------
async function runCompare(body) {
  if (state.busy) return;
  setBusy(true);
  showError("");
  els.candidates.hidden = true;
  showStatus(COMPARE_STEPS);
  try {
    showProduct(await api("/api/compare", { method: "POST", body }));
  } catch (err) {
    showError(err.message);
  } finally {
    showStatus(null);
    setBusy(false);
  }
}

function showCandidates(result) {
  els.interpretation.innerHTML = result.interpretation ? `We understood: <b>${esc(result.interpretation)}</b>` : "";
  els.candidateGrid.innerHTML = "";
  result.products.forEach((p) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "card";
    const meta = [p.brand, p.variant, p.category].filter(Boolean).map(esc).join(" · ");
    card.innerHTML = `
      ${safeUrl(p.image_url) ? `<img src="${esc(p.image_url)}" alt="" loading="lazy">` : ""}
      <span class="card-title">${esc(p.title)}</span>
      ${meta ? `<span class="card-meta">${meta}</span>` : ""}
      <span class="card-price">${p.approx_price ? "about " + money(p.approx_price) : "Compare prices →"}</span>`;
    card.addEventListener("click", () => runCompare({ product: p }));
    els.candidateGrid.appendChild(card);
  });
  els.candidates.hidden = false;
  els.candidates.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runSearch(query) {
  if (state.busy) return;
  setBusy(true);
  showError("");
  els.candidates.hidden = true;
  showStatus(["Understanding your search…", "Finding matching products sold in India…"]);
  try {
    showCandidates(await api("/api/search", { method: "POST", body: { query } }));
  } catch (err) {
    showError(err.message);
  } finally {
    showStatus(null);
    setBusy(false);
  }
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = els.q.value.trim();
  if (text.length < 2) return;
  if (isLink(text)) runCompare({ url: /^https?:\/\//i.test(text) ? text : "https://" + text });
  else runSearch(text);
});

els.q.addEventListener("input", () => {
  els.go.textContent = isLink(els.q.value) ? "Compare" : "Search";
});

document.querySelectorAll("#examples button").forEach((button) =>
  button.addEventListener("click", () => {
    els.q.value = button.textContent;
    els.go.textContent = "Search";
    runSearch(button.textContent);
  })
);

els.photo.addEventListener("change", async () => {
  const file = els.photo.files && els.photo.files[0];
  els.photo.value = "";
  if (!file || state.busy) return;
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    showError("Upload a JPEG, PNG or WebP image.");
    return;
  }
  if (file.size > 4 * 1024 * 1024) {
    showError("That photo is larger than 4 MB. Try a smaller one.");
    return;
  }
  setBusy(true);
  showError("");
  els.candidates.hidden = true;
  showStatus(["Looking at your photo…", "Working out which product it is…"]);
  try {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("The photo could not be read."));
      reader.readAsDataURL(file);
    });
    showCandidates(await api("/api/search/photo", { method: "POST", body: { image_base64: dataUrl, mime_type: file.type } }));
  } catch (err) {
    showError(err.message);
  } finally {
    showStatus(null);
    setBusy(false);
  }
});

async function loadRecent() {
  try {
    const { items } = await api("/api/products/recent");
    els.recentGrid.innerHTML = "";
    items.forEach((p) => {
      const card = document.createElement("a");
      card.className = "card";
      card.href = `/?product=${p.id}`;
      card.innerHTML = `
        ${safeUrl(p.image_url) ? `<img src="${esc(p.image_url)}" alt="" loading="lazy">` : ""}
        <span class="card-title">${esc(p.title)}</span>
        ${p.category ? `<span class="card-meta">${esc(p.category)}</span>` : ""}
        <span class="card-price">${p.best_price ? "from " + money(p.best_price) : "No price yet"}</span>`;
      card.addEventListener("click", (event) => {
        event.preventDefault();
        openProduct(p.id);
      });
      els.recentGrid.appendChild(card);
    });
    els.recent.hidden = items.length === 0;
  } catch {
    els.recent.hidden = true; // recent products need the database; the rest of the page still works
  }
}

// ---------- product page ----------
function renderProduct() {
  const { product, listings, analysis, insights, cached } = state.view;
  const best = analysis.best;
  const meta = [product.brand, product.model_number && `Model ${product.model_number}`, product.variant, product.category]
    .filter(Boolean).map((m) => `<span>${esc(m)}</span>`).join("");
  const checked = product.last_compared_at ? new Date(product.last_compared_at) : null;

  els.product.innerHTML = `
    <button type="button" class="back" id="back">← New search</button>
    <div class="product-head">
      ${safeUrl(product.image_url) ? `<img src="${esc(product.image_url)}" alt="">` : `<div class="ph" aria-hidden="true">${initial(product.title)}</div>`}
      <div>
        <h1 class="product-title">${esc(product.title)}</h1>
        <div class="product-meta">${meta}</div>
        <div class="product-actions">
          ${product.id ? `<button type="button" class="btn btn-ghost" id="refresh">Re-check prices</button>` : ""}
          ${safeUrl(product.source_url) ? `<a class="btn btn-ghost" href="${esc(product.source_url)}" target="_blank" rel="noopener">Your link ↗</a>` : ""}
        </div>
        <p class="muted small" style="margin:10px 0 0">
          ${checked ? `Prices checked ${esc(checked.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }))}` : ""}
          ${cached ? " · showing the recent comparison" : ""}
        </p>
      </div>
    </div>
    ${product.tracking ? "" : `<p class="note">Price history, alerts and chat are unavailable right now because the database can't be reached. Today's prices are shown below.</p>`}

    <div class="summary">
      <div class="best">
        <div class="best-label">Best price today</div>
        <div class="best-price">${best ? money(best.price) : "—"}</div>
        <div class="best-where">${best ? `on ${esc(best.platform)}` : "No store price found"}</div>
        <div class="best-extra">
          <span>Stores with a price: <b>${analysis.stores_with_price}</b></span>
          ${analysis.savings > 0 ? `<span>Save <b>${money(analysis.savings)}</b> vs the priciest store</span>` : ""}
          ${analysis.discount_pct ? `<span><b>${analysis.discount_pct}%</b> off MRP</span>` : ""}
        </div>
      </div>
      <div class="verdict" data-tone="${esc(analysis.verdict.tone)}">
        <p class="verdict-label">${esc(analysis.verdict.label)}</p>
        <p>${esc(analysis.verdict.detail)}</p>
      </div>
    </div>

    <h2 class="section-title">Prices across stores</h2>
    <div class="stores">${listings.length ? listings.map((l) => storeRow(l, best)).join("") : `<p class="muted">We couldn't find this product on other stores.</p>`}</div>
    <p class="muted small">“Search on store” links open that store's search for this product when we couldn't confirm the exact product page.</p>

    <h2 class="section-title">Price history</h2>
    <div class="panel" id="history"></div>

    ${product.id ? `
    <div class="two-col" style="margin-top:48px">
      <div>
        <h2 class="section-title" style="margin-top:0">Ask about this product</h2>
        <div class="panel" id="chat"></div>
      </div>
      <div>
        <h2 class="section-title" style="margin-top:0">Price drop alert</h2>
        <div class="panel" id="alert"></div>
      </div>
    </div>
    <h2 class="section-title">Specs and reviews</h2>
    <div id="insights"></div>` : ""}
  `;

  $("back").addEventListener("click", () => goHome());
  const refresh = $("refresh");
  if (refresh) refresh.addEventListener("click", () => recheck(refresh));
  renderHistory(analysis);
  if (product.id) {
    renderChat();
    renderAlert(best);
    renderInsights(insights);
  }
}

function storeRow(l, best) {
  const isBest = best && l.current && l.platform === best.platform && l.price === best.price;
  const url = safeUrl(l.url);
  const badges = [
    isBest ? `<span class="badge badge-best">Cheapest</span>` : "",
    l.link_type === "source" ? `<span class="badge">Your link</span>` : "",
    l.price_source === "live" ? `<span class="badge badge-live">Live price</span>` : "",
    l.in_stock === false ? `<span class="badge badge-warn">Out of stock</span>` : "",
    !l.current ? `<span class="badge">Not seen in latest check</span>` : "",
  ].join("");
  const sub = [l.title && l.title !== state.view.product.title ? l.title : null, l.variant_note].filter(Boolean).map(esc).join(" · ");
  return `
    <div class="store${isBest ? " is-best" : ""}${l.current ? "" : " stale"}">
      <div>
        <div class="store-name">${esc(l.platform)} ${badges}</div>
        ${sub ? `<div class="store-sub">${sub}</div>` : ""}
      </div>
      <div class="store-price">
        <b>${money(l.price)}</b>
        ${l.mrp && l.price && l.mrp > l.price ? `<s>${money(l.mrp)}</s>${l.discount_pct ? `<span class="off">${l.discount_pct}% off</span>` : ""}` : ""}
      </div>
      ${url ? `<a class="visit" href="${esc(url)}" target="_blank" rel="noopener nofollow">${l.link_type === "search" ? "Search on store ↗" : "Go to store ↗"}</a>` : "<span></span>"}
    </div>`;
}

async function recheck(button) {
  button.disabled = true;
  button.textContent = "Re-checking…";
  try {
    const id = state.view.product.id;
    const identity = await api(`/api/products/${id}`);
    const p = identity.product;
    const view = await api("/api/compare", {
      method: "POST",
      body: {
        refresh: true,
        product: { title: p.title, brand: p.brand, model_number: p.model_number, variant: p.variant, category: p.category, image_url: p.image_url },
      },
    });
    showProduct(view, view.product.id !== id);
  } catch (err) {
    button.disabled = false;
    button.textContent = "Re-check prices";
    alert(err.message);
  }
}

// ---------- history chart ----------
function destroyChart() {
  if (state.chart) {
    state.chart.destroy();
    state.chart = null;
  }
}

function renderHistory(analysis) {
  const box = $("history");
  const chart = analysis.chart;
  const stat = (label, value) => `<div><dt>${label}</dt><dd>${value}</dd></div>`;
  const low = analysis.lowest_recorded_at;
  box.innerHTML = `
    <dl class="stats">
      ${stat("Lowest recorded", money(analysis.lowest_recorded))}
      ${stat("Average", money(analysis.average_recorded))}
      ${stat("Highest recorded", money(analysis.highest_recorded))}
      ${stat("Days tracked", analysis.days_tracked || 0)}
    </dl>
    ${low ? `<p class="muted small" style="margin:0 0 12px">Lowest was on ${esc(low.platform)}, ${esc(low.date)}.</p>` : ""}
    <div id="chart-area"></div>`;

  const area = $("chart-area");
  destroyChart();
  if (!chart.labels || chart.labels.length < 2) {
    area.innerHTML = `<p class="muted" style="margin:0">${state.view.product.tracking
      ? "We check this product daily. The chart appears once there are two days of prices."
      : "Price history is recorded once the database is reachable."}</p>`;
    return;
  }

  const platforms = Object.keys(chart.series).slice(0, 8);
  const styles = getComputedStyle(document.documentElement);
  const color = (i) => styles.getPropertyValue(`--series-${i + 1}`).trim();
  area.innerHTML = `
    <ul class="legend">${platforms.map((p, i) => `<li><i style="background:${color(i)}"></i>${esc(p)}</li>`).join("")}</ul>
    <div class="chart-wrap"><canvas id="chart" role="img" aria-label="Daily lowest price per store"></canvas></div>
    <details class="table-view"><summary>Show as table</summary>
      <div class="table-wrap"><table>
        <thead><tr><th>Date</th>${platforms.map((p) => `<th class="num">${esc(p)}</th>`).join("")}</tr></thead>
        <tbody>${chart.labels.map((d, row) => `<tr><td>${esc(d)}</td>${platforms.map((p) => `<td class="num">${money(chart.series[p][row])}</td>`).join("")}</tr>`).join("")}</tbody>
      </table></div>
    </details>`;

  if (!window.Chart) return; // the table view still works if the chart library didn't load
  const ink = styles.getPropertyValue("--ink-soft").trim();
  const grid = styles.getPropertyValue("--line").trim();
  state.chart = new Chart($("chart"), {
    type: "line",
    data: {
      labels: chart.labels,
      datasets: platforms.map((p, i) => ({
        label: p, data: chart.series[p], borderColor: color(i), backgroundColor: color(i),
        borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, spanGaps: true, tension: 0.2,
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${money(ctx.parsed.y)}` } },
      },
      scales: {
        x: { ticks: { color: ink, maxTicksLimit: 6, maxRotation: 0 }, grid: { display: false }, border: { color: grid } },
        y: { ticks: { color: ink, callback: (v) => money(v) }, grid: { color: grid }, border: { display: false } },
      },
    },
  });
}

// Redraw the chart in the new palette when the OS theme changes.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (state.view && !els.product.hidden) renderHistory(state.view.analysis);
});

// ---------- chat ----------
const SUGGESTIONS = ["Which store is cheapest?", "Should I buy now or wait?", "What do reviews say?", "Battery kitni chalti hai?"];

function renderChat() {
  const box = $("chat");
  box.innerHTML = `
    <div class="chat-log" id="chat-log" aria-live="polite"></div>
    <div class="suggestions" id="suggestions">${SUGGESTIONS.map((s) => `<button type="button">${esc(s)}</button>`).join("")}</div>
    <form class="chat-form" id="chat-form">
      <label for="chat-q" class="sr-only">Your question</label>
      <input id="chat-q" type="text" maxlength="500" autocomplete="off" placeholder="Ask about price, specs or reviews (English or Hinglish)">
      <button class="btn btn-primary" type="submit">Ask</button>
    </form>`;
  box.querySelectorAll("#suggestions button").forEach((b) => b.addEventListener("click", () => ask(b.textContent)));
  $("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("chat-q");
    const question = input.value.trim();
    if (question) {
      input.value = "";
      ask(question);
    }
  });
}

function addMessage(role, html) {
  const log = $("chat-log");
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  div.innerHTML = html;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

const ROUTE_LABELS = { PRICE: "price tracker (SQL)", SPECS: "specs (SQL + hybrid search)", REVIEWS: "reviews (hybrid search)", GENERAL: "hybrid search" };

async function ask(question) {
  const form = $("chat-form");
  if (form.dataset.busy) return;
  form.dataset.busy = "1";
  $("suggestions").hidden = true;
  addMessage("user", esc(question));
  const pending = addMessage("assistant", `<span class="muted">Thinking… the first question about specs or reviews takes a little longer while we research the product.</span>`);
  try {
    const res = await api(`/api/products/${state.view.product.id}/chat`, {
      method: "POST",
      body: { question, history: state.chat.slice(-8) },
    });
    const ms = res.timings_ms && res.timings_ms.total;
    pending.innerHTML = `${esc(res.answer)}<div class="msg-meta">Answered from ${esc(ROUTE_LABELS[res.route] || res.route)}${ms ? ` · ${(ms / 1000).toFixed(1)} s` : ""}</div>`;
    state.chat.push({ role: "user", content: question.slice(0, 2000) }, { role: "assistant", content: String(res.answer).slice(0, 2000) });
    if (res.route !== "PRICE" && !state.view.insights.ready) refreshInsights();
  } catch (err) {
    pending.innerHTML = `<span style="color:var(--danger)">${esc(err.message)}</span>`;
  } finally {
    delete form.dataset.busy;
  }
}

// ---------- alerts ----------
function renderAlert(best) {
  const box = $("alert");
  const suggested = best ? Math.floor((best.price * 0.95) / 10) * 10 : "";
  box.innerHTML = `
    <p class="muted small" style="margin:0 0 12px">We'll email you when any store drops to your price.</p>
    <form class="alert-form" id="alert-form">
      <label for="alert-email" class="sr-only">Email</label>
      <input id="alert-email" type="email" required maxlength="254" placeholder="you@example.com" autocomplete="email">
      <label for="alert-price" class="sr-only">Target price in rupees</label>
      <input id="alert-price" type="number" required min="1" step="1" value="${suggested}" placeholder="Target ₹">
      <button class="btn btn-primary" type="submit">Set alert</button>
    </form>
    <p class="form-msg" id="alert-msg" role="status"></p>`;
  $("alert-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const msg = $("alert-msg");
    const button = event.target.querySelector("button");
    button.disabled = true;
    msg.style.color = "";
    try {
      const res = await api(`/api/products/${state.view.product.id}/alerts`, {
        method: "POST",
        body: { email: $("alert-email").value, target_price: Number($("alert-price").value) },
      });
      msg.textContent = res.message;
    } catch (err) {
      msg.textContent = err.message;
      msg.style.color = "var(--danger)";
    } finally {
      button.disabled = false;
    }
  });
}

// ---------- insights ----------
async function refreshInsights() {
  try {
    const view = await api(`/api/products/${state.view.product.id}`);
    state.view.insights = view.insights;
    renderInsights(view.insights);
  } catch {
    /* keep what is on screen */
  }
}

function renderInsights(insights) {
  const box = $("insights");
  if (!insights || !insights.ready) {
    box.innerHTML = `
      <div class="panel">
        <p style="margin:0 0 12px">We research specifications and buyer reviews from across the web the first time someone asks. It takes around 20–40 seconds.</p>
        <button type="button" class="btn btn-primary" id="load-insights">Research specs and reviews</button>
        <p class="form-msg" id="insights-msg" role="status"></p>
      </div>`;
    $("load-insights").addEventListener("click", async (event) => {
      const button = event.target;
      const msg = $("insights-msg");
      button.disabled = true;
      button.textContent = "Researching…";
      msg.textContent = "";
      try {
        const result = await api(`/api/products/${state.view.product.id}/insights`, { method: "POST" });
        state.view.insights = result;
        renderInsights(result);
      } catch (err) {
        button.disabled = false;
        button.textContent = "Try again";
        msg.textContent = err.message;
        msg.style.color = "var(--danger)";
      }
    });
    return;
  }

  const r = insights.reviews || {};
  const specs = insights.specs || [];
  const groups = {};
  specs.forEach((s) => (groups[s.group] = groups[s.group] || []).push(s));
  const sources = (insights.sources || []).filter((s) => safeUrl(s.url));

  box.innerHTML = `
    <div class="insights-grid">
      <div class="panel">
        <h3>What buyers say</h3>
        ${r.overview ? `<p style="margin:0 0 8px">${esc(r.overview)}</p>` : ""}
        <div class="sentiment" role="img" aria-label="${r.positive_pct}% positive, ${r.neutral_pct}% neutral, ${r.negative_pct}% negative">
          <span class="s-pos" style="width:${Number(r.positive_pct) || 0}%"></span>
          <span class="s-neu" style="width:${Number(r.neutral_pct) || 0}%"></span>
          <span class="s-neg" style="width:${Number(r.negative_pct) || 0}%"></span>
        </div>
        <div class="sentiment-key">
          <span><b>${esc(r.positive_pct)}%</b> positive</span><span><b>${esc(r.neutral_pct)}%</b> neutral</span>
          <span><b>${esc(r.negative_pct)}%</b> negative</span>
          ${r.average_rating ? `<span><b>${esc(r.average_rating)}</b> / 5 typical rating</span>` : ""}
        </div>
        ${r.overall ? `<p style="margin:14px 0 0">${esc(r.overall)}</p>` : ""}
        ${r.best_for ? `<p class="muted small" style="margin:8px 0 0">Best for: ${esc(r.best_for)}</p>` : ""}
        <div class="proscons">
          <div><h4>Pros</h4><ul>${(r.pros || []).map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>
          <div><h4>Cons</h4><ul>${(r.cons || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ul></div>
        </div>
        <ul class="aspects">${(r.aspects || []).map((a) =>
          `<li><b>${esc(a.aspect)}</b><span class="tone-${esc(a.sentiment)}">${esc(a.sentiment)}</span> — ${esc(a.summary)}</li>`).join("")}</ul>
      </div>
      <div class="panel">
        <h3>Specifications</h3>
        ${specs.length ? `<div class="table-wrap"><table class="spec-group">${Object.entries(groups).map(([group, items]) =>
          `<tr><th colspan="2">${esc(group)}</th></tr>${items.map((s) => `<tr><td>${esc(s.name)}</td><td>${esc(s.value)}</td></tr>`).join("")}`).join("")}</table></div>`
          : `<p class="muted">No specifications found.</p>`}
      </div>
    </div>
    ${sources.length ? `<p class="sources">Sources: ${sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener nofollow">${esc(s.title || new URL(s.url).hostname)}</a>`).join("")}</p>` : ""}`;
}

// ---------- startup ----------
async function checkHealth() {
  try {
    const h = await api("/api/health");
    const searchOk = h.search === "configured";
    const state = h.status === "ok" && searchOk ? "ok" : "degraded";
    els.health.dataset.state = state;
    els.health.textContent = state === "ok" ? "All systems go" : !searchOk ? "Search not configured" : "History offline";
    els.health.title = `Database: ${h.database} · Search: ${h.search}`;
  } catch {
    els.health.dataset.state = "down";
    els.health.textContent = "Offline";
  }
}

checkHealth();
const startId = new URLSearchParams(location.search).get("product");
if (startId) openProduct(startId, false);
else loadRecent();
