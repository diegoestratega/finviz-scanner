// static/app.js

const API_BASE = "https://finviz-scanner.vercel.app";

const runScanBtn = document.getElementById("runScanBtn");
const loadingEl = document.getElementById("loading");
const resultCountEl = document.getElementById("resultCount");
const finvizLinkEl = document.getElementById("finvizLink");
const resultsTableBody = document.getElementById("resultsTable").querySelector("tbody");

let currentSort = "perfytd";

function getFilterValues() {
  return {
    marketcap: document.getElementById("marketcap").value,
    pe: document.getElementById("pe").value,
    fpe: document.getElementById("fpe").value,
    epsqoq: document.getElementById("epsqoq").value,
    salesqoq: document.getElementById("salesqoq").value,
    debteq: document.getElementById("debteq").value,
    highlow52w: document.getElementById("highlow52w").value,
    optionable: document.getElementById("optionable").checked,
  };
}

function buildQueryString(params) {
  const q = new URLSearchParams();
  if (params.marketcap) q.append("marketcap", params.marketcap);
  if (params.pe) q.append("pe", params.pe);
  if (params.fpe) q.append("fpe", params.fpe);
  if (params.epsqoq) q.append("epsqoq", params.epsqoq);
  if (params.salesqoq) q.append("salesqoq", params.salesqoq);
  if (params.debteq) q.append("debteq", params.debteq);
  if (params.highlow52w) q.append("highlow52w", params.highlow52w);
  if (params.optionable) q.append("optionable", "true");
  q.append("sort", currentSort);
  return q.toString();
}

function setLoading(isLoading) {
  if (isLoading) {
    loadingEl.classList.remove("hidden");
    runScanBtn.disabled = true;
  } else {
    loadingEl.classList.add("hidden");
    runScanBtn.disabled = false;
  }
}

function updateResultCount(count) {
  resultCountEl.textContent = count === 0 ? "No results found" : `${count} stocks found`;
}

function updateFinvizLink(filters) {
  if (!filters) {
    finvizLinkEl.classList.add("hidden");
    return;
  }
  const params = new URLSearchParams();
  params.set("v", "111");
  params.set("f", filters);
  finvizLinkEl.href = `https://finviz.com/screener.ashx?${params.toString()}`;
  finvizLinkEl.classList.remove("hidden");
}

function colorPerfCell(td, value) {
  if (!value) return;
  const num = parseFloat(value.replace("%", "").replace("+", "").trim());
  if (isNaN(num)) return;
  td.classList.add(num >= 0 ? "perf-positive" : "perf-negative");
}

function renderResults(results) {
  resultsTableBody.innerHTML = "";
  results.forEach((row) => {
    const tr = document.createElement("tr");

    // Ticker cell with link
    const tickerTd = document.createElement("td");
    const link = document.createElement("a");
    link.href = `https://finviz.com/quote.ashx?t=${encodeURIComponent(row.ticker)}`;
    link.target = "_blank";
    link.textContent = row.ticker;
    tickerTd.appendChild(link);
    tr.appendChild(tickerTd);

    const fields = [
      { val: row.company },
      { val: row.sector },
      { val: row.industry },
      { val: row.marketCap },
      { val: row.pe },
      { val: row.fpe },
      { val: row.epsQoq },
      { val: row.salesQoq },
      { val: row.debtEq },
      { val: row.high52w },
      { val: row.low52w },
      { val: row.perfMonth, perf: true },
      { val: row.perfYtd, perf: true },
      { val: row.perfYear, perf: true },
    ];

    fields.forEach(({ val, perf }) => {
      const td = document.createElement("td");
      td.textContent = val || "";
      if (perf) colorPerfCell(td, val);
      tr.appendChild(td);
    });

    resultsTableBody.appendChild(tr);
  });
}

async function runScan() {
  const filters = getFilterValues();
  const qs = buildQueryString(filters);
  const url = `${API_BASE}/api/scan?${qs}`;

  setLoading(true);
  updateResultCount(0);
  updateFinvizLink(null);
  renderResults([]);

  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`API error ${resp.status}`);
    const data = await resp.json();
    updateResultCount(data.count || 0);
    updateFinvizLink(data.filters || "");
    renderResults(data.results || []);
  } catch (err) {
    console.error(err);
    resultCountEl.textContent = "Error running scan. Check console.";
  } finally {
    setLoading(false);
  }
}

document.querySelectorAll(".sort-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".sort-btn").forEach((b) => b.classList.remove("sort-btn-active"));
    btn.classList.add("sort-btn-active");
    currentSort = btn.getAttribute("data-sort");
    runScan();
  });
});

runScanBtn.addEventListener("click", runScan);
