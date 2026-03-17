# api/scan.py

import re
import time
from typing import List, Optional

import cloudscraper
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FINVIZ_BASE = "https://finviz.com/screener.ashx"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    ),
}

TICKER_RE = re.compile(r"^[A-Z]{1,6}$")


def build_filter_string(
    marketcap: Optional[str],
    optionable: bool,
    pe: Optional[str],
    fpe: Optional[str],
    epsqoq: Optional[str],
    salesqoq: Optional[str],
    debteq: Optional[str],
    highlow52w: Optional[str],
) -> str:
    parts: List[str] = []
    if marketcap:
        parts.append(marketcap)
    if optionable:
        parts.append("sh_opt_option")
    if pe:
        parts.append(pe)
    if fpe:
        parts.append(fpe)
    if epsqoq:
        parts.append(epsqoq)
    if salesqoq:
        parts.append(salesqoq)
    if debteq:
        parts.append(debteq)
    if highlow52w:
        parts.append(highlow52w)
    return ",".join(parts)


def fetch_view_page(view: int, filters: str, sort: str, offset: int) -> BeautifulSoup:
    scraper = cloudscraper.create_scraper()
    params = {
        "v": str(view),
        "f": filters,
        "o": sort,
        "r": str(offset),
    }
    resp = scraper.get(FINVIZ_BASE, params=params, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Finviz returned status {resp.status_code} for view {view}.",
        )
    return BeautifulSoup(resp.text, "html.parser")


def find_screener_table(soup: BeautifulSoup):
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True) for th in t.find_all("th")]
        if "Ticker" in ths:
            return t
    return None


def extract_headers(soup: BeautifulSoup) -> List[str]:
    table = find_screener_table(soup)
    if not table:
        return []
    ths = [th.get_text(strip=True) for th in table.find_all("th")]
    if "Ticker" in ths:
        return ths
    return []


def is_valid_data_row(cells: List[str]) -> bool:
    if len(cells) < 3:
        return False
    if not cells[0].isdigit():
        return False
    if not TICKER_RE.match(cells[1]):
        return False
    return True


def parse_table_rows(soup: BeautifulSoup) -> List[List[str]]:
    table = find_screener_table(soup)
    if not table:
        return []

    rows_data: List[List[str]] = []
    for row in table.find_all("tr"):
        all_tds = row.find_all("td")
        if not all_tds:
            continue
        cells = [td.get_text(strip=True) for td in all_tds if len(td.get_text(strip=True)) <= 100]
        if not is_valid_data_row(cells):
            continue
        rows_data.append(cells[1:])  # strip leading row number
    return rows_data


def scrape_view(view: int, filters: str, sort: str, max_pages: int = 10) -> List[dict]:
    all_rows: List[List[str]] = []
    headers: List[str] = []
    offset = 1
    page = 0

    while page < max_pages:
        soup = fetch_view_page(view=view, filters=filters, sort=sort, offset=offset)

        if not headers:
            raw_headers = extract_headers(soup)
            if raw_headers and raw_headers[0] == "No.":
                headers = raw_headers[1:]
            elif raw_headers:
                headers = raw_headers
            if not headers:
                break

        rows = parse_table_rows(soup)
        if not rows:
            break

        all_rows.extend(rows)
        offset += 20
        page += 1
        time.sleep(0.5)

    result: List[dict] = []
    for row in all_rows:
        if len(row) != len(headers):
            if len(row) > len(headers):
                row = row[: len(headers)]
            else:
                row = row + [""] * (len(headers) - len(row))
        item = {headers[i]: row[i] for i in range(len(headers))}
        result.append(item)

    return result


def index_by_ticker(records: List[dict]) -> dict:
    index = {}
    for rec in records:
        ticker = rec.get("Ticker")
        if ticker:
            index[ticker] = rec
    return index


@app.get("/api/debug")
def debug():
    scraper = cloudscraper.create_scraper()
    results = {}
    for view in [111, 140, 161]:
        params = {"v": str(view), "f": "", "o": "perfytd", "r": "1"}
        resp = scraper.get(FINVIZ_BASE, params=params, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        raw_headers = extract_headers(soup)
        headers = raw_headers[1:] if raw_headers and raw_headers[0] == "No." else raw_headers
        rows = parse_table_rows(soup)
        results[f"v{view}"] = {
            "headers": headers,
            "first_row": rows[0] if rows else [],
            "total_rows": len(rows),
        }
    return results


@app.get("/api/scan")
def scan(
    marketcap: Optional[str] = Query(None),
    pe: Optional[str] = Query(None),
    fpe: Optional[str] = Query(None),
    epsqoq: Optional[str] = Query(None),
    salesqoq: Optional[str] = Query(None),
    debteq: Optional[str] = Query(None),
    highlow52w: Optional[str] = Query(None),
    optionable: bool = Query(False),
    sort: str = Query("perfytd"),
):
    filters = build_filter_string(
        marketcap=marketcap,
        optionable=optionable,
        pe=pe,
        fpe=fpe,
        epsqoq=epsqoq,
        salesqoq=salesqoq,
        debteq=debteq,
        highlow52w=highlow52w,
    )

    # Ascending sort (no dash prefix)
    sort_map = {
        "perfmon": "perfmon",
        "perfytd": "perfytd",
        "perfyear": "perfyear",
    }
    sort_param = sort_map.get(sort, "perfytd")

    # v=111 Overview  → Company, Sector, Industry, Market Cap, P/E, Fwd P/E
    # v=161 Financial → EPS Q/Q, Sales Q/Q, Debt/Eq
    # v=140 Performance → Perf Month, Perf YTD, Perf Year, etc.
    overview_records = scrape_view(view=111, filters=filters, sort=sort_param)
    fin_records = scrape_view(view=161, filters=filters, sort=sort_param)
    perf_records = scrape_view(view=140, filters=filters, sort=sort_param)

    overview_by_ticker = index_by_ticker(overview_records)
    fin_by_ticker = index_by_ticker(fin_records)
    perf_by_ticker = index_by_ticker(perf_records)

    # Build merged result keyed from overview (has company/sector/industry)
    all_tickers = set(overview_by_ticker.keys()) | set(perf_by_ticker.keys())

    results = []
    for ticker in all_tickers:
        ov = overview_by_ticker.get(ticker, {})
        fin = fin_by_ticker.get(ticker, {})
        perf = perf_by_ticker.get(ticker, {})

        results.append(
            {
                "ticker": ticker,
                "company": ov.get("Company", ""),
                "sector": ov.get("Sector", ""),
                "industry": ov.get("Industry", ""),
                "country": ov.get("Country", ""),
                "marketCap": ov.get("Market Cap", ""),
                "pe": ov.get("P/E", ""),
                "fpe": ov.get("Fwd P/E", ""),
                "epsQoq": fin.get("EPS Q/Q", ""),
                "salesQoq": fin.get("Sales Q/Q", ""),
                "debtEq": fin.get("Debt/Eq", fin.get("LT Debt/Eq", "")),
                "high52w": perf.get("52W High", ov.get("52W High", "")),
                "low52w": perf.get("52W Low", ov.get("52W Low", "")),
                "perfMonth": perf.get("Perf Month", ""),
                "perfYtd": perf.get("Perf YTD", ""),
                "perfYear": perf.get("Perf Year", ""),
            }
        )

    def perf_to_float(val: Optional[str]) -> float:
        if not val:
            return float("inf")  # push blanks to end on ascending sort
        s = val.replace("%", "").replace("+", "").strip()
        try:
            return float(s)
        except ValueError:
            return float("inf")

    # Ascending sort: lowest performance first
    if sort == "perfmon":
        results.sort(key=lambda x: perf_to_float(x["perfMonth"]))
    elif sort == "perfytd":
        results.sort(key=lambda x: perf_to_float(x["perfYtd"]))
    elif sort == "perfyear":
        results.sort(key=lambda x: perf_to_float(x["perfYear"]))

    return {
        "count": len(results),
        "filters": filters,
        "sort": sort,
        "results": results,
    }
