"""A-share (CN) data vendor backed by AkShare.

This module plugs into the framework's vendor router (see interface.py) and
provides K-line, fundamentals, financial statements, and Chinese-language news
for A-share tickers (.SZ / .SH / .SHZ / .BJ). The functions mirror the
signatures of the existing yfinance / alpha_vantage vendors so the agents do
not need to know which vendor served the call.

AkShare endpoints hit:
- K-line:        stock_zh_a_daily          (Sina — stable, full back-history)
- News:          stock_news_em             (Eastmoney — ticker-level headlines)
- Fundamentals:  stock_financial_analysis_indicator (Sina — historical ratios)
- Per-company info: stock_individual_info_em (Eastmoney — name, sector, etc.)

Tradeoffs:
- No API key needed; rate-limited and occasionally flaky on Eastmoney. The
  router falls through to the configured secondary vendor on errors, matching
  the existing fallback semantics.
- A-share news is Chinese; the framework's news analyst prompts will surface
  the original Chinese text. Set ``output_language=中文`` in .env to get
  Chinese reports end-to-end.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Annotated, Optional

import pandas as pd

from .errors import NoMarketDataError

logger = logging.getLogger(__name__)


# Exchange suffix -> AkShare prefix. Sina uses lowercase letter prefix on the
# raw 6-digit code; Eastmoney uses the bare 6 digits.
_CN_SUFFIXES = (".SZ", ".SH", ".SHZ", ".BJ")
_SINA_PREFIX = {"SZ": "sz", "SH": "sh", "BJ": "bj"}
_EM_PREFIX = {"SZ": "", "SH": "", "BJ": ""}


def is_cn_symbol(symbol: str) -> bool:
    """Return True when ``symbol`` carries an A-share exchange suffix."""
    return isinstance(symbol, str) and symbol.upper().endswith(_CN_SUFFIXES)


def _resolve_cn(symbol: str) -> tuple[str, str]:
    """Split ``300812.SZ`` -> code=``300812``, market=``SZ``."""
    s = symbol.strip()
    upper = s.upper()
    mapping = {".SZ": "SZ", ".SH": "SH", ".SHZ": "SH", ".BJ": "BJ"}
    for suf, market in mapping.items():
        if upper.endswith(suf):
            return s[: -len(suf)], market
    raise ValueError(f"Not a CN symbol: {symbol!r}")


def _sina_symbol(symbol: str) -> str:
    code, market = _resolve_cn(symbol)
    prefix = _SINA_PREFIX.get(market, "")
    return f"{prefix}{code}"


def _em_symbol(symbol: str) -> str:
    code, _ = _resolve_cn(symbol)
    return code

def _em_prefixed_symbol(symbol: str) -> str:
    """Return 'SZ300812' / 'SH600519' style for Eastmoney report endpoints."""
    code, market = _resolve_cn(symbol)
    market_full = {"SZ": "SZ", "SH": "SH", "BJ": "BJ"}[market]
    return f"{market_full}{code}"

def _fetch_kline(sina_sym: str, attempts: int = 4, sleep_s: float = 1.5):
    """Sina K-line with retries. Returns a DataFrame or raises NoMarketDataError.

    Sina occasionally returns a malformed response (e.g. an HTML error page
    parsed as a frame with no ``date`` column). Retry, and if the response
    shape is broken across every attempt, raise NoMarketDataError so the
    router does NOT silently fall through to the yfinance vendor (whose
    indicator names do not match this vendor's contract).
    """
    import akshare as ak
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            df = ak.stock_zh_a_daily(symbol=sina_sym, adjust="qfq")
            if df is None or df.empty:
                raise NoMarketDataError(sina_sym, sina_sym, "Sina K-line empty")
            if "date" not in df.columns:
                # Sina returned a malformed payload; sleep and retry.
                last_exc = ValueError("Sina K-line response has no 'date' column")
                time.sleep(sleep_s)
                continue
            return df
        except NoMarketDataError:
            raise
        except Exception as e:
            last_exc = e
            time.sleep(sleep_s)
    raise NoMarketDataError(
        sina_sym, sina_sym,
        f"Sina K-line failed after {attempts} attempts: {last_exc}"
    )


def _normalize_indicator(name: str) -> str:
    """Strip numeric suffixes (rsi14 -> rsi) so yfinance fallback is happy."""
    n = name.lower().strip()
    n = re.sub(r"\d+$", "", n)
    return n



# ---------------------------------------------------------------------------
# Core OHLCV
# ---------------------------------------------------------------------------

def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Return Sina K-line (qfq-adjusted) as a CSV-with-header string."""
    import akshare as ak

    sina_sym = _sina_symbol(symbol)
    s = datetime.strptime(start_date, "%Y-%m-%d").date()
    e = datetime.strptime(end_date, "%Y-%m-%d").date()

    # stock_zh_a_daily returns the full history; filter client-side so the
    # caller gets exactly the requested window.
    df = _fetch_kline(sina_sym)

    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[(df["date"] >= s) & (df["date"] <= e)].reset_index(drop=True)
    if df.empty:
        raise NoMarketDataError(symbol, sina_sym, f"no rows between {start_date} and {end_date}")

    # Round numerics for cleaner downstream rendering.
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = df[col].astype(float).round(2)

    header = (
        f"# A-share stock data for {symbol} (Sina qfq) "
        f"from {start_date} to {end_date}\n"
        f"# Total records: {len(df)}\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + df.to_csv(index=False)


# ---------------------------------------------------------------------------
# Technical indicators (computed locally from K-line)
# ---------------------------------------------------------------------------

def _slice_kline(symbol: str, end_date: str, look_back_days: int) -> pd.DataFrame:
    import akshare as ak

    sina_sym = _sina_symbol(symbol)
    df = _fetch_kline(sina_sym)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    e = datetime.strptime(end_date, "%Y-%m-%d").date()
    df = df[df["date"] <= e].tail(max(look_back_days, 30)).reset_index(drop=True)
    if df.empty:
        raise NoMarketDataError(symbol, sina_sym, "no K-line rows before end_date")
    return df


def _compute_indicator(df: pd.DataFrame, indicator: str) -> str:
    name = _normalize_indicator(indicator)
    closes = df["close"].astype(float)
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    vols = df["volume"].astype(float)

    if name in ("rsi", "rsi14"):
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        last = float(rsi.iloc[-1])
        return f"RSI(14) for last close: {last:.2f}\nLast 14 RSI values:\n{rsi.tail(14).round(2).to_list()}"
    if name in ("macd",):
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        hist = (dif - dea) * 2
        return (
            "MACD (12/26/9):\n"
            f"  DIF last: {float(dif.iloc[-1]):.4f}\n"
            f"  DEA last: {float(dea.iloc[-1]):.4f}\n"
            f"  HIST last: {float(hist.iloc[-1]):.4f}\n"
            f"  HIST last 10: {hist.tail(10).round(4).to_list()}"
        )
    if name in ("boll", "bollinger", "bbands"):
        mid = closes.rolling(20).mean()
        std = closes.rolling(20).std()
        upper = mid + 2 * std
        lower = mid - 2 * std
        return (
            "Bollinger Bands (20, 2):\n"
            f"  Upper: {float(upper.iloc[-1]):.2f}\n"
            f"  Mid:   {float(mid.iloc[-1]):.2f}\n"
            f"  Lower: {float(lower.iloc[-1]):.2f}\n"
            f"  Bandwidth (last): {float((upper.iloc[-1] - lower.iloc[-1])):.2f}"
        )
    if name in ("ma", "ma20", "ma50", "ma5", "ma10", "ma60"):
        m = re.findall(r"\d+", name)
        window = int(m[0]) if m else 20
        avg = closes.rolling(window).mean().iloc[-1]
        return f"MA({window}) last: {float(avg):.2f}"
    if name in ("volume", "vol"):
        return (
            f"Volume last 5 sessions: {vols.tail(5).round(0).to_list()}\n"
            f"Avg volume (full window): {float(vols.mean()):.0f}"
        )
    # Default: dump a small summary.
    return (
        f"Indicator {indicator!r} not specialised for CN — falling back to summary.\n"
        f"close last 5: {closes.tail(5).round(2).to_list()}\n"
        f"high last 5:  {highs.tail(5).round(2).to_list()}\n"
        f"low last 5:   {lows.tail(5).round(2).to_list()}"
    )


def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    df = _slice_kline(symbol, curr_date, look_back_days)
    body = _compute_indicator(df, indicator)
    return (
        f"# {indicator} for {symbol} (A-share, Sina qfq) "
        f"as of {curr_date}, lookback {look_back_days}d\n"
        f"# rows used: {len(df)} (last close {float(df['close'].iloc[-1]):.2f})\n\n"
        f"{body}\n"
    )


# ---------------------------------------------------------------------------
# Fundamentals (Sina historical financial-analysis indicators)
# ---------------------------------------------------------------------------

def _df_to_text(df: pd.DataFrame, title: str, symbol: str, curr_date: str, n_rows: int = 6) -> str:
    if df is None or df.empty:
        return f"# {title} for {symbol}\n# (no data returned)\n"
    show = df.head(n_rows)
    return (
        f"# {title} for {symbol} as of {curr_date}\n"
        f"# Latest {len(show)} reporting periods (rows: {len(df)})\n\n"
        + show.to_csv(index=False)
    )


def _fundamental_df(symbol: str):
    import akshare as ak
    return ak.stock_financial_analysis_indicator(symbol=_em_symbol(symbol), start_year="2020")


def get_fundamentals(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current trading date YYYY-mm-dd"],
) -> str:
    df = _fundamental_df(symbol)
    if df is None or df.empty:
        raise NoMarketDataError(symbol, symbol, "no financial indicator data")
    df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
    keep = [
        "日期", "摊薄每股收益(元)", "每股净资产_调整前(元)", "每股经营性现金流(元)",
        "销售毛利率(%)", "销售净利率(%)", "净资产收益率(%)", "总资产净利润率(%)",
        "主营业务收入增长率(%)", "净利润增长率(%)", "资产负债率(%)", "总资产(元)",
    ]
    cols = [c for c in keep if c in df.columns]
    return _df_to_text(df[cols], "A-share financial-analysis indicators (Sina)", symbol, curr_date, n_rows=8)


def get_balance_sheet(
    symbol: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "reporting frequency: annual | quarterly"] = "quarterly",
    curr_date: Annotated[str, "current trading date YYYY-mm-dd"] = "",
) -> str:
    # AkShare balance sheet by report (Eastmoney). Skip when offline — return
    # a short text rather than crashing the agent.
    import akshare as ak
    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=_em_prefixed_symbol(symbol))
    except Exception as e:
        return f"# Balance sheet for {symbol}\n# AkShare eastmoney endpoint failed: {e}\n"
    return _df_to_text(df, f"A-share balance sheet ({freq})", symbol, curr_date or "-")


def get_cashflow(
    symbol: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "reporting frequency: annual | quarterly"] = "quarterly",
    curr_date: Annotated[str, "current trading date YYYY-mm-dd"] = "",
) -> str:
    import akshare as ak
    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=_em_prefixed_symbol(symbol))
    except Exception as e:
        return f"# Cash flow for {symbol}\n# AkShare eastmoney endpoint failed: {e}\n"
    return _df_to_text(df, f"A-share cash flow ({freq})", symbol, curr_date or "-")


def get_income_statement(
    symbol: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "reporting frequency: annual | quarterly"] = "quarterly",
    curr_date: Annotated[str, "current trading date YYYY-mm-dd"] = "",
) -> str:
    import akshare as ak
    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=_em_prefixed_symbol(symbol))
    except Exception as e:
        return f"# Income statement for {symbol}\n# AkShare eastmoney endpoint failed: {e}\n"
    return _df_to_text(df, f"A-share income statement ({freq})", symbol, curr_date or "-")


# ---------------------------------------------------------------------------
# News — ticker-level (Eastmoney) and macro (Eastmoney + Sina)
# ---------------------------------------------------------------------------

def get_news(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    import akshare as ak
    try:
        df = ak.stock_news_em(symbol=_em_symbol(symbol))
    except Exception as e:
        return (
            f"# Ticker news for {symbol}\n"
            f"# AkShare eastmoney endpoint failed: {e}\n"
            f"# (no fallback to yfinance for A-share tickers)\n"
        )
    if df is None or df.empty:
        return f"# Ticker news for {symbol}\n# (no news returned)\n"
    s = datetime.strptime(start_date, "%Y-%m-%d").date()
    e = datetime.strptime(end_date, "%Y-%m-%d").date()
    df["发布时间"] = pd.to_datetime(df["发布时间"]).dt.date
    df = df[(df["发布时间"] >= s) & (df["发布时间"] <= e)].reset_index(drop=True)
    if df.empty:
        return f"# Ticker news for {symbol} ({start_date}..{end_date})\n# (no news in window)\n"

    # Render compact Markdown so the agent's news prompt stays readable.
    lines = [f"# Ticker news for {symbol} ({start_date}..{end_date}), {len(df)} items\n"]
    for _, row in df.iterrows():
        title = str(row.get("新闻标题", "")).strip()
        content = str(row.get("新闻内容", "")).strip()
        ts = row.get("发布时间", "")
        src = str(row.get("文章来源", "")).strip()
        url = str(row.get("新闻链接", "")).strip()
        lines.append(f"- [{ts}] {title}  _(来源: {src})_")
        if content:
            lines.append(f"  {content[:600]}")
        if url:
            lines.append(f"  链接: {url}")
    return "\n".join(lines) + "\n"


# A-share macro headlines: pull from Eastmoney's "财经早知道"-style feed via
# the global_news endpoint, but filter for Chinese macro keywords. Falls back
# to a small static query if the upstream is unreachable.
_MACRO_QUERIES = [
    "央行 货币政策 利率",
    "中国 宏观经济 GDP CPI PMI",
    "证监会 A股 监管",
    "人民币 汇率 外汇",
    "国务院 财政 政策",
]


def get_global_news(
    curr_date: Annotated[str, "current date YYYY-mm-dd"],
    look_back_days: Annotated[int, "lookback window in days"],
    limit: Annotated[int, "max articles"] = 20,
) -> str:
    import akshare as ak

    end = datetime.strptime(curr_date, "%Y-%m-%d").date()
    start = end - timedelta(days=look_back_days)

    rows: list[dict] = []
    try:
        # Eastmoney's macro feed keyed by keyword. Walk the static query list
        # and dedupe by article URL.
        for q in _MACRO_QUERIES:
            try:
                df = ak.stock_info_global_em(symbol=q)
            except Exception:
                continue
            if df is None or df.empty:
                continue
            for _, r in df.iterrows():
                pub = pd.to_datetime(r.get("发布时间"), errors="coerce")
                if pd.isna(pub):
                    continue
                d = pub.date()
                if d < start or d > end:
                    continue
                rows.append({
                    "title": str(r.get("标题", "")).strip(),
                    "content": str(r.get("内容", "")).strip(),
                    "source": str(r.get("来源", "")).strip(),
                    "url": str(r.get("链接", "")).strip(),
                    "date": d.isoformat(),
                })
    except Exception as e:
        logger.warning("AkShare global-news endpoint failed: %s", e)

    # Dedup by URL or title.
    seen = set()
    uniq = []
    for r in rows:
        key = r["url"] or r["title"]
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    uniq.sort(key=lambda r: r["date"], reverse=True)
    uniq = uniq[:limit]

    if not uniq:
        return (
            f"# A-share global news ({start}..{end})\n"
            f"# (no A-share macro headlines returned — possibly upstream blocked)\n"
        )

    out = [f"# A-share global news ({start}..{end}), {len(uniq)} items\n"]
    for r in uniq:
        out.append(f"- [{r['date']}] {r['title']}  _(来源: {r['source']})_")
        if r["content"]:
            out.append(f"  {r['content'][:400]}")
        if r["url"]:
            out.append(f"  链接: {r['url']}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Insider transactions — A-share regulatory filings are on cninfo / SSE, not
# exposed via a single AkShare endpoint. Return a clean "unavailable" so the
# agent doesn't fabricate. The router already routes core data, so a soft
# "no data" here just skips this category cleanly.
# ---------------------------------------------------------------------------

def get_insider_transactions(symbol: str) -> str:  # noqa: D401
    return (
        f"# Insider transactions for {symbol}\n"
        "# Insider filings are on cninfo.com.cn / sse.com.cn / szse.cn.\n"
        "# This vendor does not expose them via AkShare; treating as unavailable.\n"
    )
