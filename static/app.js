// static/app.js

const API_BASE = "https://YOUR-VERCEL-APP.vercel.app"; // change this

const runScanBtn = document.getElementById("runScanBtn");
const loadingEl = document.getElementById("loading");
const resultCountEl = document.getElementById("resultCount");
const finvizLinkEl = document.getElementById("finvizLink");
const resultsTableBody = document
  .getElementById("resultsTable")
  .querySelector("tbody");

let currentSort = "perfytd";

function getFilterValues() {
  const marketcap = document.getElementById("marketcap").value;
  const pe = document.getElementById("pe").value;
  const fpe = document.getElementById("fpe").value;
  const epsqoq = document.getElementById("epsqoq").value;
  const salesqoq = document.getElementById("salesqoq").value;
  const debteq = document.getElementById("debteq").value;
  const highlow52w = document.getElementById("highlow52w").value;
  const optionable = document.getElementById("optionable").checked;

  return {
    marketcap,
    pe,
    fpe,
    epsqoq,
    salesqoq,
    debteq,
    highlow52w,
    optionable,
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
  if (currentSort) q.append("sort", currentSort);
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
  if (count === 0) {
    resultCountEl.textContent = "No results found";
  } else {
    resultCountEl.textContent = `${count} stocks found`;
  }
}

function updateFinvizLink(filters) {
  if (!filters) {
    finvizLinkEl.classList.add("hidden");
    return;
  }
  const params = new URLSearchParams();
  params.set("v", "131"); // performance view as default
  params.set("f", filters);
  finvizLinkEl.href = `https://finviz.com/screener.ashx?${params.toString()}`;
  finvizLinkEl.classList.remove("hidden");
}

function colorPerfCell(td, value) {
  if (!value) return;
  const s = value.replace("%", "").replace("+", "").trim();
  const num = parseFloat(s);
  if (isNaN(num)) return;
  if (num > 0) {
    td.classList.add("perf-positive");
  } else if (num < 0) {
    td.classList.add("perf-negative");
  }
}

function renderResults(results) {
  // Clear table
  resultsTableBody.innerHTML = "";

  results.forEach((row) => {
    const tr = document.createElement("tr");

    const tickerCell = document.createElement("td");
    const link = document.createElement("a");
    link.href = `https://finviz.com/quote.ashx?t=${encodeURIComponent(
      row.ticker
    )}`;
    link.target = "_blank";
    link.textContent = row.ticker;
    tickerCell.appendChild(link);
    tr.appendChild(tickerCell);

    const cells = [
      row.company,
      row.sector,
      row.industry,
      row.marketCap,
      row.pe,
      row.fpe,
      row.epsQoq,
      row.salesQoq,
      row.debtEq,
      row.high52w,
      row.low52w,
      row.perfMonth,
      row.perfYtd,
      row.perfYear,
    ];

    cells.forEach((val, idx) => {
      const td = document.createElement("td");
      td.textContent = val || "";
      // performance columns: last 3 in cells
      if (idx >= cells.length - 3) {
        colorPerfCell(td, val);
      }
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
    if (!resp.ok) {
      throw new Error(`API error ${resp.status}`);
    }
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

// Sort buttons
document.querySelectorAll(".sort-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document
      .querySelectorAll(".sort-btn")
      .forEach((b) => b.classList.remove("sort-btn-active"));
    btn.classList.add("sort-btn-active");
    currentSort = btn.getAttribute("data-sort");
    runScan();
  });
});

// Run button
runScanBtn.addEventListener("click", () => {
  runScan();
});
