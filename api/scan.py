# api/scan.py

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


def parse_table_rows(soup: BeautifulSoup) -> List[List[str]]:
    tables = soup.find_all("table")
    target = None
    for table in tables:
        header_row = table.find("tr")
        if not header_row:
            continue
        headers = [th.get_text(strip=True) for th in header_row.find_all("td")]
        if headers and "Ticker" in headers:
            target = table
            break
    if target is None:
        return []
    rows_data: List[List[str]] = []
    rows = target.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
        row_text = [c.get_text(strip=True) for c in cols]
        rows_data.append(row_text)
    return rows_data


def extract_headers(soup: BeautifulSoup) -> List[str]:
    tables = soup.find_all("table")
    for table in tables:
        header_row = table.find("tr")
        if not header_row:
            continue
        headers = [th.get_text(strip=True) for th in header_row.find_all("td")]
        if headers and "Ticker" in headers:
            return headers
    return []


def scrape_view(view: int, filters: str, sort: str, max_pages: int = 10) -> List[dict]:
    all_rows: List[List[str]] = []
    headers: List[str] = []
    offset = 1
    page = 0
    while page < max_pages:
        soup = fetch_view_page(view=view, filters=filters, sort=sort, offset=offset)
        if not headers:
            headers = extract_headers(soup)
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
    params = {"v": "131", "f": "", "o": "-perfytd", "r": "1"}
    resp = scraper.get(FINVIZ_BASE, params=params, headers=HEADERS, timeout=15)
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    table_info = []
    for i, t in enumerate(tables):
        first_row = t.find("tr")
        cells = [td.get_text(strip=True) for td in first_row.find_all("td")] if first_row else []
        table_info.append({"table_index": i, "first_row_cells": cells[:10]})
    return {
        "status_code": resp.status_code,
        "html_length": len(html),
        "html_snippet": html[:500],
        "tables_found": len(tables),
        "table_headers": table_info,
    }


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
    sort_map = {
        "perfmon": "-perfmon",
        "perfytd": "-perfytd",
        "perfyear": "-perfyear",
    }
    sort_param = sort_map.get(sort, "-perfytd")

    perf_records = scrape_view(view=131, filters=filters, sort=sort_param)
    fin_records = scrape_view(view=161, filters=filters, sort=sort_param)

    perf_by_ticker = index_by_ticker(perf_records)
    fin_by_ticker = index_by_ticker(fin_records)

    merged: List[dict] = []
    for ticker, perf_row in perf_by_ticker.items():
        combined = dict(perf_row)
        fin_row = fin_by_ticker.get(ticker, {})
        for key in ["EPS Q/Q", "Sales Q/Q", "Debt/Eq"]:
            if key in fin_row:
                combined[key] = fin_row[key]
        merged.append(combined)

    results = []
    for row in merged:
        ticker = row.get("Ticker")
        if not ticker:
            continue
        results.append(
            {
                "ticker": ticker,
                "company": row.get("Company"),
                "sector": row.get("Sector"),
                "industry": row.get("Industry"),
                "country": row.get("Country"),
                "marketCap": row.get("Market Cap"),
                "pe": row.get("P/E"),
                "fpe": row.get("Fwd P/E"),
                "epsQoq": row.get("EPS Q/Q"),
                "salesQoq": row.get("Sales Q/Q"),
                "debtEq": row.get("Debt/Eq"),
                "high52w": row.get("52W High"),
                "low52w": row.get("52W Low"),
                "perfMonth": row.get("Perf Month"),
                "perfYtd": row.get("Perf YTD"),
                "perfYear": row.get("Perf Year"),
            }
        )

    def perf_to_float(val: Optional[str]) -> float:
        if not val:
            return float("-inf")
        s = val.replace("%", "").replace("+", "").strip()
        try:
            return float(s)
        except ValueError:
            return float("-inf")

    if sort == "perfmon":
        results.sort(key=lambda x: perf_to_float(x["perfMonth"]), reverse=True)
    elif sort == "perfytd":
        results.sort(key=lambda x: perf_to_float(x["perfYtd"]), reverse=True)
    elif sort == "perfyear":
        results.sort(key=lambda x: perf_to_float(x["perfYear"]), reverse=True)

    return {
        "count": len(results),
        "filters": filters,
        "sort": sort,
        "results": results,
    }
