// Frontend: collects the user's choices, calls the Python API, draws the results.
// No calculations happen here - the backend is the single source of truth.

const METHOD_HELP = {
  equal: "Every stock gets the same weight.",
  market_cap: "Bigger companies (free-float shares x price on the start date) get more weight.",
  capped_market_cap: "Market-cap weights, but no stock can go above a limit you set.",
  custom: "You type in each stock's weight.",
};
const SECTOR_COLORS = ["#0f6e6e", "#3d5a80", "#c07b1f", "#7a4f9a", "#5b8c3a", "#b0485b"];

const state = { stocks: [], selected: new Set(), custom: {}, activeSectors: new Set(), result: null, chart: null };
const $ = (id) => document.getElementById(id);
const pct = (x, dp = 2) => (x == null || isNaN(x) ? "-" : `${(x * 100).toFixed(dp)}%`);
const signed = (x, dp = 2) => (x > 0 ? "+" : "") + pct(x, dp);
const tone = (x) => (x > 0 ? "up" : x < 0 ? "down" : "");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---------------- set-up ----------------
async function init() {
  const res = await fetch("/api/universe");
  const data = await res.json();
  state.stocks = data.stocks;
  $("startDate").value = $("startDate").min = $("endDate").min = data.date_range.min;
  $("endDate").value = $("startDate").max = $("endDate").max = data.date_range.max;

  $("methods").innerHTML = data.methods.map(({ key, label }, i) => `
    <label class="method"><input type="radio" name="method" value="${key}" ${i === 0 ? "checked" : ""}>
      <span>${esc(label)}<small>${METHOD_HELP[key] || ""}</small></span></label>`).join("");

  const sectors = [...new Set(state.stocks.map((s) => s.sector))];
  $("sectorChips").innerHTML = sectors.map((s) => `<button type="button" class="chip" data-sector="${esc(s)}">${esc(s)}</button>`).join("");

  bindEvents();
  renderStockList();
  renderMethodOptions();
}

function bindEvents() {
  $("search").addEventListener("input", renderStockList);
  $("selectAll").addEventListener("click", () => { state.stocks.forEach((s) => state.selected.add(s.ticker)); refreshSelection(); });
  $("clearAll").addEventListener("click", () => { state.selected.clear(); state.activeSectors.clear(); refreshSelection(); });
  $("sectorChips").addEventListener("click", (e) => {
    const sector = e.target.dataset.sector;
    if (!sector) return;
    const on = !state.activeSectors.has(sector);
    on ? state.activeSectors.add(sector) : state.activeSectors.delete(sector);
    state.stocks.filter((s) => s.sector === sector).forEach((s) => (on ? state.selected.add(s.ticker) : state.selected.delete(s.ticker)));
    refreshSelection();
  });
  $("stockList").addEventListener("change", (e) => {
    e.target.checked ? state.selected.add(e.target.value) : state.selected.delete(e.target.value);
    refreshSelection();
  });
  $("methods").addEventListener("change", renderMethodOptions);
  $("splitEvenly").addEventListener("click", splitEvenly);
  $("customList").addEventListener("input", (e) => { state.custom[e.target.dataset.ticker] = e.target.value; renderCustomTotal(); });
  $("builder").addEventListener("submit", (e) => { e.preventDefault(); generate(); });
  $("download").addEventListener("click", downloadCsv);
}

// ---------------- builder rendering ----------------
function renderStockList() {
  const q = $("search").value.trim().toLowerCase();
  const rows = state.stocks.filter((s) => !q || s.ticker.toLowerCase().includes(q) || s.company_name.toLowerCase().includes(q));
  $("stockList").innerHTML = rows.map((s) => `
    <li><label>
      <input type="checkbox" value="${s.ticker}" ${state.selected.has(s.ticker) ? "checked" : ""}>
      <span class="tk">${esc(s.ticker)}</span><span>${esc(s.company_name)}</span><span class="sec">${esc(s.sector)}</span>
    </label></li>`).join("") || `<li style="padding:10px">No stock matches “${esc(q)}”.</li>`;
}

function refreshSelection() {
  $("selectedCount").textContent = `${state.selected.size} of ${state.stocks.length} selected`;
  document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", state.activeSectors.has(c.dataset.sector)));
  renderStockList();
  renderCustomList();
}

function selectedMethod() { return document.querySelector("input[name=method]:checked").value; }

function renderMethodOptions() {
  const m = selectedMethod();
  $("capField").hidden = m !== "capped_market_cap";
  $("customBox").hidden = m !== "custom";
  renderCustomList();
}

function renderCustomList() {
  if (selectedMethod() !== "custom") return;
  $("customList").innerHTML = [...state.selected].map((t) => `
    <li><span>${esc(t)}</span><span><input type="number" min="0" step="0.01" data-ticker="${t}" value="${state.custom[t] ?? ""}"> %</span></li>`).join("")
    || "<li>Select stocks in step 1 first.</li>";
  renderCustomTotal();
}

function renderCustomTotal() {
  const total = [...state.selected].reduce((sum, t) => sum + (parseFloat(state.custom[t]) || 0), 0);
  const el = $("customTotal");
  el.textContent = `Total: ${total.toFixed(2)}%`;
  el.className = "custom-total " + (Math.abs(total - 100) <= 0.01 ? "good" : "bad");
}

function splitEvenly() {
  const tickers = [...state.selected];
  if (!tickers.length) return;
  const each = Math.floor((10000 / tickers.length)) / 100;              // 2 decimals, rounded down
  tickers.forEach((t) => (state.custom[t] = each));
  state.custom[tickers[0]] = +(100 - each * (tickers.length - 1)).toFixed(2); // remainder so the total is exactly 100
  renderCustomList();
}

// ---------------- talking to the backend ----------------
function buildPayload() {
  const method = selectedMethod();
  const payload = {
    tickers: [...state.selected],
    method,
    start_date: $("startDate").value,
    end_date: $("endDate").value,
    base_level: parseFloat($("baseLevel").value),
  };
  if (method === "capped_market_cap") payload.cap_pct = parseFloat($("cap").value);
  if (method === "custom") {
    payload.custom_weights = Object.fromEntries(payload.tickers.map((t) => [t, state.custom[t] === "" || state.custom[t] == null ? null : parseFloat(state.custom[t])]));
  }
  return payload;
}

async function generate() {
  const btn = $("generate");
  btn.disabled = true; btn.textContent = "Generating…";
  try {
    const res = await fetch("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(buildPayload()),
    });
    const data = await res.json();
    renderMessages(data.errors, data.warnings);
    if (data.ok) renderResult(data);
    else $("output").hidden = true;
  } catch (err) {
    renderMessages([`Couldn't reach the server: ${err.message}`], []);
  } finally {
    btn.disabled = false; btn.textContent = "Generate index";
    $("emptyState").hidden = true;
  }
}

// ---------------- results rendering ----------------
function renderMessages(errors = [], warnings = []) {
  const block = (cls, title, items) => items.length
    ? `<div class="msg ${cls}"><h3>${title}</h3><ul>${items.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div>` : "";
  $("messages").innerHTML = block("err", "Fix these to generate the index", errors) + block("warn", "Data decisions made", warnings);
}

function renderResult(r) {
  state.result = r;
  $("output").hidden = false;
  const m = r.metrics, b = r.benchmark.metrics;
  $("headlineLabel").textContent = `${r.settings.method}, ${r.settings.constituents} stocks. Index level on ${r.settings.end_date}`;
  $("endLevel").textContent = m.end_level.toFixed(2);
  $("cumReturn").textContent = signed(m.cumulative_return);
  $("cumReturn").className = tone(m.cumulative_return);
  const excess = m.cumulative_return - b.cumulative_return;
  $("excess").textContent = `${signed(excess)}`;
  $("excess").className = tone(excess);

  renderChart(r);
  renderMetrics(m, b, r.benchmark.label);
  renderSectors(r.sectors);
  renderConstituents(r.constituents);
}

function renderChart(r) {
  if (typeof Chart === "undefined") { $("chart").replaceWith("Chart library couldn't load (offline?). Metrics below are still correct."); return; }
  if (state.chart) state.chart.destroy();
  state.chart = new Chart($("chart"), {
    type: "line",
    data: {
      labels: r.dates,
      datasets: [
        { label: "Your index", data: r.levels, borderColor: "#0f6e6e", borderWidth: 2, pointRadius: 0, tension: 0 },
        { label: r.benchmark.label, data: r.benchmark.levels, borderColor: "#a3adbb", borderWidth: 1.5, borderDash: [5, 4], pointRadius: 0 },
      ],
    },
    options: {
      maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(2)}` } } },
      scales: { x: { ticks: { maxTicksLimit: 8 }, grid: { display: false } }, y: { title: { display: true, text: "Index level" } } },
    },
  });
}

function renderMetrics(m, b, benchLabel) {
  const rows = [
    ["Start level", m.start_level.toFixed(2), b.start_level.toFixed(2)],
    ["End level", m.end_level.toFixed(2), b.end_level.toFixed(2)],
    ["Cumulative return", signed(m.cumulative_return), signed(b.cumulative_return)],
    ["Annualised return", signed(m.annualised_return), signed(b.annualised_return)],
    ["Annualised volatility", pct(m.annualised_volatility), pct(b.annualised_volatility)],
    ["Sharpe ratio (rf = 0)", m.sharpe_ratio.toFixed(2), b.sharpe_ratio.toFixed(2)],
    ["Max drawdown", pct(m.max_drawdown), pct(b.max_drawdown)],
    ["Best day", `${signed(m.best_day.return)} (${m.best_day.date})`, signed(b.best_day.return)],
    ["Worst day", `${signed(m.worst_day.return)} (${m.worst_day.date})`, signed(b.worst_day.return)],
    ["Trading days", m.trading_days, b.trading_days],
  ];
  $("metricsTable").innerHTML = `<tr><th></th><th>Your index</th><th title="${esc(benchLabel)}">Benchmark</th></tr>`
    + rows.map((r) => `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td></tr>`).join("");
}

function renderSectors(sectors) {
  const entries = Object.entries(sectors);
  $("sectorBar").innerHTML = entries.map(([s, w], i) => `<span title="${esc(s)} ${pct(w, 1)}" style="width:${w * 100}%;background:${SECTOR_COLORS[i % 6]}"></span>`).join("");
  $("sectorLegend").innerHTML = entries.map(([s, w], i) => `<li><span class="swatch" style="background:${SECTOR_COLORS[i % 6]}"></span>${esc(s)}<b>${pct(w, 1)}</b></li>`).join("");
}

function renderConstituents(rows) {
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.contribution)), 1e-9);
  $("constituents").innerHTML = `<tr><th>Stock</th><th>Sector</th><th>Weight</th><th>Price return</th><th>Contribution</th><th class="bar-cell"></th></tr>`
    + rows.map((r) => `<tr>
        <td><b>${esc(r.ticker)}</b> ${esc(r.company_name)}</td><td>${esc(r.sector)}</td><td>${pct(r.weight)}</td>
        <td class="${tone(r.price_return)}">${signed(r.price_return)}</td>
        <td class="${tone(r.contribution)}">${signed(r.contribution)}</td>
        <td class="bar-cell"><div class="contrib-bar ${r.contribution < 0 ? "neg" : ""}" style="width:${(Math.abs(r.contribution) / maxAbs) * 100}%"></div></td>
      </tr>`).join("");
}

function downloadCsv() {
  const r = state.result;
  if (!r) return;
  const lines = ["date,index_level,index_daily_return,benchmark_level"];
  r.dates.forEach((d, i) => lines.push([d, r.levels[i], r.daily_returns[i] ?? "", r.benchmark.levels[i]].join(",")));
  const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
  Object.assign(document.createElement("a"), { href: url, download: "custom_index.csv" }).click();
  URL.revokeObjectURL(url);
}

init();
