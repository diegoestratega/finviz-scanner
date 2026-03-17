// static/app.js

const API_BASE = "https://finviz-scanner.vercel.app";

const runScanBtn     = document.getElementById("runScanBtn");
const loadingEl      = document.getElementById("loading");
const resultCountEl  = document.getElementById("resultCount");
const finvizLinkEl   = document.getElementById("finvizLink");
const tbody          = document.getElementById("resultsTable").querySelector("tbody");

let currentSort = "perfytd";

function getFilterValues() {
  return {
    marketcap: document.getElementById("marketcap").value,
    pe:        document.getElementById("pe").value,
    fpe:       document.getElementById("fpe").value,
    epsqoq:    document.getElementById("epsqoq").value,
    salesqoq:  document.getElementById("salesqoq").value,
    debteq:    document.getElementById("debteq").value,
    highlow52w:document.getElementById("highlow52w").value,
    optionable:document.getElementById("optionable").checked,
  };
}

function buildQueryString(p) {
  const q = new URLSearchParams();
  if (p.marketcap)  q.append("marketcap",  p.marketcap);
  if (p.pe)         q.append("pe",         p.pe);
  if (p.fpe)        q.append("fpe",        p.fpe);
  if (p.epsqoq)     q.append("epsqoq",     p.epsqoq);
  if (p.salesqoq)   q.append("salesqoq",   p.salesqoq);
  if (p.debteq)     q.append("debteq",     p.debteq);
  if (p.highlow52w) q.append("highlow52w", p.highlow52w);
  if (p.optionable) q.append("optionable", "true");
  q.append("sort", currentSort);
  return q.toString();
}

function setLoading(on) {
  loadingEl.classList.toggle("hidden", !on);
  runScanBtn.disabled = on;
}

function colorPerf(td, val) {
  if (!val) return;
  const n = parseFloat(val.replace("%","").replace("+","").trim());
  if (!isNaN(n)) td.classList.add(n >= 0 ? "perf-positive" : "perf-negative");
}

function renderResults(rows) {
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");

    // Ticker
    const tdTicker = document.createElement("td");
    const a = document.createElement("a");
    a.href = `https://finviz.com/quote.ashx?t=${encodeURIComponent(r.ticker)}`;
    a.target = "_blank";
    a.textContent = r.ticker;
    tdTicker.appendChild(a);
    tr.appendChild(tdTicker);

    // Company
    const tdCo = document.createElement("td");
    tdCo.className = "td-company";
    tdCo.textContent = r.company || "";
    tr.appendChild(tdCo);

    // Plain cells
    [r.marketCap, r.pe, r.fpe, r.epsQoq, r.salesQoq, r.debtEq].forEach((val) => {
      const td = document.createElement("td");
      td.textContent = val || "";
      tr.appendChild(td);
    });

    // Performance cells
    [r.perfMonth, r.perfYtd, r.perfYear].forEach((val) => {
      const td = document.createElement("td");
      td.textContent = val || "";
      colorPerf(td, val);
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });
}

async function runScan() {
  const filters = getFilterValues();
  const qs  = buildQueryString(filters);
  const url = `${API_BASE}/api/scan?${qs}`;

  setLoading(true);
  resultCountEl.textContent = "Scanning...";
  finvizLinkEl.classList.add("hidden");
  renderResults([]);

  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`API error ${resp.status}`);
    const data = await resp.json();

    resultCountEl.textContent = data.count
      ? `${data.count} stocks found`
      : "No results found";

    if (data.filters) {
      const p = new URLSearchParams();
      p.set("v", "111");
      p.set("f", data.filters);
      finvizLinkEl.href = `https://finviz.com/screener.ashx?${p.toString()}`;
      finvizLinkEl.classList.remove("hidden");
    }

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
