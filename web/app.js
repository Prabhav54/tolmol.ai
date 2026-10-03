"use strict";

const $ = (selector) => document.querySelector(selector);
const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const charts = {};

// ---------- helpers ----------
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

function money(value, currency = "INR") {
  if (value === null || value === undefined) return null;
  return currency === "INR" ? `₹${inr.format(value)}` : `${currency} ${inr.format(value)}`;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    /* non-JSON error page */
  }
  if (!response.ok) {
    const detail = data && data.detail;
    const message = Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail;
    throw new Error(message || `Request failed with status ${response.status}.`);
  }
  return data;
}

function showError(element, error) {
  element.textContent = error ? error.message || String(error) : "";
  element.hidden = !error;
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.classList.toggle("loading", busy);
}

// ---------- tabs ----------
const VIEWS = ["search", "add", "insights", "benchmark"];
const loaded = new Set();

function showView() {
  const name = VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "search";
  for (const view of VIEWS) $(`#view-${view}`).hidden = view !== name;
  document.querySelectorAll(".tabs a").forEach((a) => {
    if (a.dataset.tab === name) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  if (name === "insights") loadInsights();
  if (name === "add" && !loaded.has("add")) {
    loaded.add("add");
    loadRecent();
  }
}
window.addEventListener("hashchange", showView);

// ---------- health ----------
async function checkHealth() {
  const badge = $("#health");
  try {
    const health = await api("/health");
    badge.dataset.state = health.database === "ok" ? "ok" : "down";
    badge.textContent = health.database === "ok" ? "Catalog online" : "Database unreachable";
  } catch {
    badge.dataset.state = "down";
    badge.textContent = "Backend offline";
  }
}

// ---------- live parse chips ----------
const SORT_LABELS = { price_asc: "Cheapest first", price_desc: "Priciest first", rating_desc: "Best rated first" };
const AGG_LABELS = {
  count: "Count products",
  avg_price: "Average price",
  min_price: "Lowest price",
  max_price: "Highest price",
  avg_rating: "Average rating",
};

function filterChips(filters) {
  const chips = [];
  const add = (html, cls = "") => chips.push(`<span class="chip ${cls}">${html}</span>`);
  if (filters.min_price != null && filters.max_price != null) add(`Price <b>${money(filters.min_price)}–${money(filters.max_price)}</b>`);
  else if (filters.max_price != null) add(`Price <b>≤ ${money(filters.max_price)}</b>`);
  else if (filters.min_price != null) add(`Price <b>≥ ${money(filters.min_price)}</b>`);
  if (filters.min_rating != null) add(`Rating <b>≥ ${filters.min_rating}★</b>`);
  if (filters.max_rating != null) add(`Rating <b>≤ ${filters.max_rating}★</b>`);
  for (const platform of filters.platforms || []) add(`On <b>${escapeHtml(platform)}</b>`);
  if (filters.in_stock_only) add("<b>In stock</b>");
  if (filters.sort) add(`<b>${SORT_LABELS[filters.sort]}</b>`);
  if (filters.limit) add(`Top <b>${filters.limit}</b>`);
  if (filters.aggregate) add(`<b>${AGG_LABELS[filters.aggregate]}</b>`);
  if (filters.group_by) add(`By <b>${escapeHtml(filters.group_by)}</b>`);
  for (const word of filters.keywords || []) add(escapeHtml(word), "chip-word");
  return chips.join("");
}

function routeLabel(route) {
  return route === "SQL" ? "Exact filters (SQL)" : "Meaning match (vector)";
}

let parseTimer = null;
let parseSeq = 0;
function liveParse(text) {
  clearTimeout(parseTimer);
  const box = $("#parse");
  if (text.trim().length < 2) {
    box.innerHTML = "";
    return;
  }
  parseTimer = setTimeout(async () => {
    const seq = ++parseSeq;
    try {
      const result = await api(`/query/route?q=${encodeURIComponent(text)}`);
      if (seq !== parseSeq) return;
      box.innerHTML = `<span class="chip chip-route-${result.route}">${routeLabel(result.route)}</span>${filterChips(result.filters)}`;
    } catch {
      /* the live preview is best-effort */
    }
  }, 180);
}

// ---------- product tags ----------
function productTag(p) {
  const link = safeUrl(p.url);
  const image = safeUrl(p.image_url);
  const price = money(p.price, p.currency);
  const meta = [p.brand, p.category].filter(Boolean).map(escapeHtml).join(", ");
  const rating = p.rating != null
    ? `<span class="stars"><b>${Number(p.rating).toFixed(1)}★</b>${p.rating_count ? ` (${inr.format(p.rating_count)})` : ""}</span>`
    : `<span class="stars">No rating</span>`;
  return `
    <article class="tag">
      <div class="tag-img">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : `<span class="placeholder">${escapeHtml((p.title || "?")[0])}</span>`}</div>
      <span class="price ${price ? "" : "price-none"}">${price || "Price n/a"}</span>
      <div class="tag-body">
        <h3 class="tag-title">${escapeHtml(p.title)}</h3>
        ${meta ? `<span class="tag-meta">${meta}</span>` : ""}
        <span class="tag-meta">${escapeHtml(p.platform)}${p.in_stock === false ? ' <span class="oos">Out of stock</span>' : ""}</span>
        ${p.similarity != null ? `<span class="match">${Math.round(p.similarity * 100)}% match</span>` : ""}
        <div class="tag-foot">
          ${rating}
          ${link ? `<a class="visit" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">View on ${escapeHtml(p.platform.split(" (")[0])}</a>` : ""}
        </div>
      </div>
    </article>`;
}

function renderTable(rows) {
  if (!rows || !rows.length) return `<p class="empty">No rows.</p>`;
  const columns = Object.keys(rows[0]);
  const isNum = (v) => typeof v === "number";
  const fmt = (key, v) => {
    if (v === null || v === undefined) return "n/a";
    if (key.endsWith("price")) return money(v);
    if (key.endsWith("rating")) return `${Number(v).toFixed(2)}★`;
    if (isNum(v)) return inr.format(v);
    return escapeHtml(v);
  };
  return `<table><thead><tr>${columns.map((c) => `<th class="${isNum(rows[0][c]) ? "num" : ""}">${escapeHtml(c.replace(/_/g, " "))}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${columns.map((c) => `<td class="${isNum(r[c]) ? "num" : ""}">${fmt(c, r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

// ---------- charts ----------
function chartDefaults() {
  if (!window.Chart) return false;
  Chart.defaults.font.family = cssVar("--body");
  Chart.defaults.color = cssVar("--ink-soft");
  Chart.defaults.borderColor = cssVar("--line");
  return true;
}

function drawChart(id, config) {
  if (!chartDefaults()) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    ...config,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: (config.data.datasets || []).length > 1 } },
      ...(config.options || {}),
    },
  });
}

function barChart(id, labels, values, label, color, horizontal = false) {
  drawChart(id, {
    type: "bar",
    data: { labels, datasets: [{ label, data: values, backgroundColor: color, borderRadius: 4, maxBarThickness: 42 }] },
    options: { indexAxis: horizontal ? "y" : "x", scales: { x: { grid: { display: horizontal } }, y: { grid: { display: !horizontal } } } },
  });
}

// ---------- search ----------
function renderTimings(timings) {
  const stages = ["routing", "embedding", "retrieval", "synthesis"].filter((s) => timings[s] != null);
  const total = stages.reduce((sum, s) => sum + timings[s], 0) || 1;
  $("#timings").innerHTML = stages
    .map((s) => `<span class="t-${s}" style="width:${Math.max(2, (timings[s] / total) * 100)}%" title="${s}: ${timings[s]} ms">${timings[s] / total > 0.12 ? s : ""}</span>`)
    .join("");
  const legend = stages.map((s) => `${s} ${timings[s]} ms`).join(", ");
  let legendEl = $("#timing-legend");
  if (!legendEl) {
    legendEl = document.createElement("p");
    legendEl.id = "timing-legend";
    legendEl.className = "timing-legend";
    $("#timings").after(legendEl);
  }
  legendEl.textContent = `${legend}. Total ${timings.total} ms.`;
}

async function runSearch(question) {
  const button = $("#search-form button");
  setBusy(button, true);
  showError($("#search-error"), null);
  try {
    const result = await api("/query", { method: "POST", body: { question } });
    $("#results").hidden = false;
    $(".answer").dataset.route = result.route;
    const pill = $("#route-pill");
    pill.dataset.route = result.route;
    pill.textContent = routeLabel(result.route);
    $("#route-reason").textContent = result.route_reason;
    $("#answer-text").textContent = result.answer;
    renderTimings(result.timings_ms);
    $("#sql").hidden = !result.sql;
    $("#sql").textContent = result.sql || "";

    const agg = $("#agg");
    if (result.aggregates && result.aggregates.length) {
      agg.hidden = false;
      $("#agg-table").innerHTML = renderTable(result.aggregates);
      const groupKey = result.filters.group_by;
      if (groupKey) {
        const metric = Object.keys(result.aggregates[0]).find((k) => k !== groupKey);
        barChart("agg-chart", result.aggregates.map((r) => r[groupKey]), result.aggregates.map((r) => r[metric]), metric.replace(/_/g, " "), cssVar("--indigo"));
        $("#agg-chart").parentElement.hidden = false;
      } else {
        $("#agg-chart").parentElement.hidden = true;
      }
    } else {
      agg.hidden = true;
    }

    $("#grid").innerHTML = result.products.map(productTag).join("");
  } catch (error) {
    $("#results").hidden = true;
    showError($("#search-error"), error);
  } finally {
    setBusy(button, false);
  }
}

$("#q").addEventListener("input", (e) => liveParse(e.target.value));
$("#search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  runSearch($("#q").value.trim());
});
$("#examples").addEventListener("click", (e) => {
  if (e.target.tagName !== "BUTTON") return;
  $("#q").value = e.target.textContent;
  liveParse($("#q").value);
  runSearch($("#q").value);
});

// ---------- add products ----------
async function loadRecent() {
  try {
    const data = await api("/products?limit=8");
    $("#recent").innerHTML = data.items.length
      ? data.items.map(productTag).join("")
      : `<p class="empty">The catalog is empty. Add a product link above to get started.</p>`;
  } catch (error) {
    $("#recent").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

$("#add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const urls = $("#urls").value.split(/\s+/).map((u) => u.trim()).filter(Boolean);
  if (!urls.length) return;
  const button = $("#add-btn");
  setBusy(button, true);
  showError($("#add-error"), null);
  try {
    const data = await api("/ingest/batch", { method: "POST", body: { urls: urls.slice(0, 25), refresh: $("#refresh").checked } });
    const rows = data.results
      .map((r) => `<tr>
        <td class="status status-${r.status}">${escapeHtml(r.status)}</td>
        <td>${escapeHtml(r.title || r.url)}${r.detail ? `<br><span class="muted">${escapeHtml(r.detail)}</span>` : ""}</td>
        <td>${escapeHtml(r.platform || "")}</td>
        <td class="num">${r.price != null ? money(r.price) : ""}</td>
        <td><code class="hash" title="${escapeHtml(r.url_hash || "")}">${escapeHtml((r.url_hash || "").slice(0, 12))}</code></td>
      </tr>`)
      .join("");
    $("#add-results").innerHTML = `<table><thead><tr><th>Result</th><th>Product</th><th>Platform</th><th class="num">Price</th><th>URL hash</th></tr></thead><tbody>${rows}</tbody></table>`;
    loadRecent();
    loaded.delete("insights");
  } catch (error) {
    showError($("#add-error"), error);
  } finally {
    setBusy(button, false);
  }
});

// ---------- insights ----------
async function loadInsights() {
  if (loaded.has("insights")) return;
  showError($("#insights-error"), null);
  try {
    const stats = await api("/products/stats");
    loaded.add("insights");
    const t = stats.totals;
    const kpis = [
      ["Products", inr.format(t.products)],
      ["Searchable by meaning", inr.format(t.embedded)],
      ["Average price", t.average_price != null ? money(t.average_price) : "n/a"],
      ["Average rating", t.average_rating != null ? `${t.average_rating.toFixed(2)}★` : "n/a"],
      ["Platforms", inr.format(t.platforms)],
      ["Price points tracked", inr.format(t.price_points)],
    ];
    $("#kpis").innerHTML = kpis.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");

    if (!window.Chart) return;
    drawChart("chart-platform", {
      type: "bar",
      data: {
        labels: stats.by_platform.map((r) => r.platform),
        datasets: [
          { label: "Products", data: stats.by_platform.map((r) => r.products), backgroundColor: cssVar("--indigo"), borderRadius: 4, yAxisID: "y" },
          { label: "Average price (₹)", data: stats.by_platform.map((r) => r.average_price), backgroundColor: cssVar("--marigold"), borderRadius: 4, yAxisID: "y1" },
        ],
      },
      options: {
        plugins: { legend: { display: true, position: "bottom" } },
        scales: { x: { grid: { display: false } }, y: { position: "left" }, y1: { position: "right", grid: { display: false } } },
      },
    });
    barChart("chart-bands", stats.price_bands.map((r) => r.band), stats.price_bands.map((r) => r.products), "Products", cssVar("--teal"));
    barChart("chart-category", stats.by_category.map((r) => r.category), stats.by_category.map((r) => r.products), "Products", cssVar("--indigo"), true);
  } catch (error) {
    showError($("#insights-error"), error);
  }
}

$("#ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = $("#ask-form button");
  setBusy(button, true);
  showError($("#insights-error"), null);
  try {
    const result = await api("/query", { method: "POST", body: { question: $("#ask").value.trim(), synthesize: false } });
    $("#ask-result").hidden = false;
    $("#ask-answer").textContent = result.aggregates ? result.answer : `${result.products.length} matching products.`;
    const rows = result.aggregates || result.products.map(({ id, title, platform, price, rating }) => ({ id, title, platform, price, rating }));
    $("#ask-table").innerHTML = renderTable(rows);
    $("#ask-sql").hidden = !result.sql;
    $("#ask-sql").textContent = result.sql || "";
  } catch (error) {
    showError($("#insights-error"), error);
  } finally {
    setBusy(button, false);
  }
});

// ---------- benchmark ----------
$("#bench-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = $("#bench-btn");
  setBusy(button, true);
  showError($("#bench-error"), null);
  try {
    const report = await api("/benchmark", { method: "POST", body: { samples: Number($("#samples").value) || 50 } });
    $("#bench-results").hidden = false;
    const routing = report.routing;
    $("#acc").textContent = `${Math.round(routing.accuracy * 100)}%`;
    $("#acc-detail").textContent = `${routing.correct} of ${routing.total} labelled queries sent to the right engine.`;

    const lat = report.retrieval_latency_ms;
    if (lat.error) {
      $("#latency").innerHTML = `<p class="muted">${escapeHtml(lat.error)}</p>`;
    } else {
      const scale = Math.max(lat.target_ms, lat.p99) * 1.05;
      const row = (name) => `<div class="lat-row"><span>${name}</span><div class="lat-bar ${lat[name] > lat.target_ms ? "over" : ""}"><span style="width:${(lat[name] / scale) * 100}%"></span></div><span>${lat[name]} ms</span></div>`;
      $("#latency").innerHTML = `${["p50", "p95", "p99"].map(row).join("")}
        <p class="lat-target">${lat.samples} timed queries over ${inr.format(report.catalog.embedded)} embeddings. Target p95 under ${lat.target_ms} ms:
        <span class="verdict ${lat.meets_target ? "pass" : "fail"}">${lat.meets_target ? "met" : "missed"}</span>.</p>`;
    }

    $("#failures").innerHTML = routing.failures.length
      ? `<h2 class="section-title">Misrouted queries</h2>${renderTable(routing.failures)}`
      : "";
  } catch (error) {
    showError($("#bench-error"), error);
  } finally {
    setBusy(button, false);
  }
});

// ---------- boot ----------
showView();
checkHealth();
