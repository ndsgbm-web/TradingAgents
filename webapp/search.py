"""Global symbol/name search across CN A-share, HK, and US/global markets.

Backed by:
  * akshare (``ak.stock_info_a_code_name``) for CN A-share code+name list
  * yfinance ``Search`` for global tickers (US, HK, ...)
  * a curated Chinese-alias table for foreign/HK/CN companies that users
    typically search by their Chinese name (``特斯拉`` -> ``TSLA``).

Network failures and missing optional dependencies degrade gracefully to empty
results; the search endpoint never raises.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger("webapp.search")

_CN_TABLE: list[dict[str, str]] | None = None
_CN_LOCK = threading.Lock()

# Curated Chinese aliases. Limited to common names on purpose - full coverage
# would require an offline translation table.
CN_ALIASES: dict[str, str] = {
    "特斯拉": "TSLA", "苹果": "AAPL", "微软": "MSFT", "谷歌": "GOOGL",
    "阿尔法特": "GOOGL", "亚马逊": "AMZN", "英伟达": "NVDA", "超微半导体": "AMD",
    "超威半导体": "AMD", "AMD": "AMD", "英特尔": "INTC", "Meta": "META",
    "脸书": "META", "奈飞": "NFLX", "网飞": "NFLX", "迪士尼": "DIS",
    "台积电": "TSM", "阿里巴巴": "BABA", "阿里": "BABA", "京东": "JD",
    "拼多多": "PDD", "百度": "BIDU", "微博": "WB", "哔哩哔哩": "BILI",
    "蔚来": "NIO", "小鹏": "XPEV", "理想": "LI", "比亚迪": "1211.HK",
    "腾讯": "0700.HK", "美团": "3690.HK", "小米": "1810.HK",
    "汇丰": "0005.HK", "港交所": "0388.HK", "中石油": "0857.HK",
    "中移动": "0941.HK", "中联通": "0762.HK", "宁德时代": "300750.SZ",
    "茅台": "600519.SH", "贵州茅台": "600519.SH", "中国平安": "601318.SH",
    "平安": "601318.SH", "招行": "600036.SH", "招商银行": "600036.SH",
    "工商银行": "601398.SH", "建设银行": "601939.SH", "中国银行": "601988.SH",
    "农业银行": "601288.SH", "五粮液": "000858.SZ", "比亚迪股份": "002594.SZ",
    "隆基绿能": "601012.SH", "中信证券": "600030.SH",
}


def _classify_cn(code: str) -> tuple[str, str]:
    if code.startswith(("60", "68", "90", "11", "13", "5")):
        return ("A股", "上交所")
    if code.startswith(("00", "30", "20", "15")):
        return ("A股", "深交所")
    if code.startswith(("8", "43", "92")):
        return ("A股", "北交所")
    return ("A股", "—")


def _suffixed_cn(code: str) -> str:
    if code.startswith(("60", "68", "90", "11", "13", "5")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "20", "15")):
        return f"{code}.SZ"
    if code.startswith(("8", "43", "92")):
        return f"{code}.BJ"
    return code


def _load_cn_table() -> list[dict[str, str]]:
    global _CN_TABLE
    with _CN_LOCK:
        if _CN_TABLE is not None:
            return _CN_TABLE
        try:
            import akshare as ak  # noqa: WPS433 (lazy import - graceful fallback)
        except ImportError:
            logger.warning("akshare not installed - CN A-share search disabled")
            _CN_TABLE = []
            return _CN_TABLE
        try:
            df = ak.stock_info_a_code_name()
        except Exception as exc:
            logger.warning("ak.stock_info_a_code_name failed: %s", exc)
            _CN_TABLE = []
            return _CN_TABLE
        rows: list[dict[str, str]] = []
        try:
            for row in df.itertuples(index=False):
                code = str(getattr(row, "code", "")).strip()
                name = str(getattr(row, "name", "")).strip()
                if not code or not name:
                    continue
                rows.append({
                    "symbol": _suffixed_cn(code),
                    "raw_code": code,
                    "name": name,
                })
        except Exception as exc:
            logger.warning("parsing akshare table failed: %s", exc)
            rows = []
        _CN_TABLE = rows
        logger.info("loaded %d CN A-share entries", len(rows))
        return _CN_TABLE


def _search_cn(query: str, limit: int) -> list[dict[str, Any]]:
    table = _load_cn_table()
    if not table or not query:
        return []
    q = query.lower()
    code_q = query.strip()
    hits: list[dict[str, Any]] = []
    for row in table:
        code = row["raw_code"]
        name_l = row["name"].lower()
        if code == code_q:
            score = 300
        elif code.startswith(code_q) or name_l.startswith(q):
            score = 200
        elif code_q in code or q in name_l:
            score = 100
        else:
            continue
        market, exchange = _classify_cn(code)
        hits.append({
            "symbol": row["symbol"],
            "name": row["name"],
            "market": market,
            "exchange": exchange,
            "_score": score,
        })
    hits.sort(key=lambda r: (-r["_score"], r["symbol"]))
    return [
        {k: v for k, v in r.items() if k != "_score"}
        for r in hits[:limit]
    ]


def _classify_global(symbol: str, exchange: str | None) -> tuple[str, str]:
    sym = symbol.upper()
    exch = (exchange or "").upper()
    if sym.endswith(".HK") or exch in {"HKG", "HKEX"}:
        return ("港股", "港交所")
    if exch in {"SHH", "SHE", "SSE", "SZSE"} or sym.endswith((".SS", ".SH", ".SZ", ".BJ")):
        return ("A股", "上交所" if sym.endswith((".SS", ".SH")) else "深交所")
    if exch in {"NASDAQ", "NYSE", "NYQ", "NMS", "NGM", "PCX", "ASE", "BATS", "XETRA", "LSE", "JPX", "ASX"}:
        return ("全球", exch or "—")
    return ("全球", exch or "—")


def _search_global(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        from yfinance import Search  # type: ignore
    except ImportError:
        logger.warning("yfinance not installed - global search disabled")
        return []
    try:
        s = Search(query, max_results=max(limit, 5))
    except Exception as exc:
        logger.warning("yfinance Search failed for %r: %s", query, exc)
        return []
    quotes = getattr(s, "quotes", None) or []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in quotes:
        symbol = (q.get("symbol") or "").strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        name = (q.get("shortName") or q.get("longName") or "").strip() or symbol
        exch = q.get("exchange") or q.get("fullExchangeName") or ""
        market, exchange_lbl = _classify_global(symbol, exch)
        out.append({
            "symbol": symbol,
            "name": name,
            "market": market,
            "exchange": exchange_lbl,
        })
        if len(out) >= limit:
            break
    return out


def _search_aliases(query: str, limit: int) -> list[dict[str, Any]]:
    if not query:
        return []
    matches: list[tuple[str, str]] = []
    for cn_name, ticker in CN_ALIASES.items():
        if cn_name in query or query in cn_name:
            matches.append((cn_name, ticker))
    if not matches:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cn_name, ticker in matches:
        if ticker in seen:
            continue
        seen.add(ticker)
        market, exchange_lbl = _classify_global(ticker, None)
        out.append({
            "symbol": ticker,
            "name": cn_name,
            "market": market,
            "exchange": exchange_lbl,
        })
        if len(out) >= limit:
            break
    return out


def search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search symbols by code, partial code, English name, or Chinese name.

    Returns a deduplicated list ranked by source priority:
      1. Chinese aliases (deterministic, resolves ``特斯拉`` -> ``TSLA``)
      2. CN A-share code/name matches
      3. yfinance global results
    """
    query = (query or "").strip()
    if not query:
        return []
    limit = max(1, min(int(limit), 25))

    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    for hit in _search_aliases(query, limit):
        if hit["symbol"] in seen:
            continue
        seen.add(hit["symbol"])
        merged.append(hit)
    for hit in _search_cn(query, limit):
        if hit["symbol"] in seen:
            continue
        seen.add(hit["symbol"])
        merged.append(hit)
    for hit in _search_global(query, limit):
        if hit["symbol"] in seen:
            continue
        seen.add(hit["symbol"])
        merged.append(hit)

    return merged[:limit]
