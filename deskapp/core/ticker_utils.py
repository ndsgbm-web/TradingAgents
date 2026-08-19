"""Ticker normalization helpers.

The downstream pipeline (``TradingAgentsGraph.propagate``) and the data
vendors (yfinance, akshare) expect A-share codes to carry an exchange
suffix:

    600519  →  600519.SH   (上交所 Shanghai)
    002335  →  002335.SZ   (深交所 Shenzhen)
    830xxx  →  830xxx.BJ   (北交所 Beijing)

Without a suffix the same prefix (e.g. ``002330`` vs ``002335``) can be
silently routed to the wrong instrument, since downstream code may pad
or fall back to a default exchange. The right answer depends on the
code itself, not on heuristics.

The classification mirrors ``webapp/search.py::_suffixed_cn`` so the GUI
and the search backend agree on what a "bare" code should become.
"""
from __future__ import annotations

import re


# Prefix → exchange suffix. Order matters: longest/most-specific first.
# (Each value is checked with ``code.startswith(prefix)`` so 2-char prefixes
# like ``68`` must be listed before the 1-char ``6``.)
_CN_PREFIX_TO_SUFFIX: tuple[tuple[str, str], ...] = (
    # ─── Shanghai 上交所 ───
    ("60", ".SH"),   # A 股主板
    ("68", ".SH"),   # 科创板
    ("90", ".SH"),   # B 股
    ("11", ".SH"),   # 可转债 / 优先股
    ("13", ".SH"),   # 国债 / 基金
    ("5",  ".SH"),   # 基金 / 权证
    # ─── Shenzhen 深交所 ───
    ("00", ".SZ"),   # A 股主板
    ("30", ".SZ"),   # 创业板
    ("20", ".SZ"),   # B 股
    ("15", ".SZ"),   # 可转债 / 基金
    # ─── Beijing 北交所 ───
    ("43", ".BJ"),
    ("92", ".BJ"),
    ("8",  ".BJ"),   # 8xxxxx 老三板 / 北交所
)


_BARE_CODE = re.compile(r"^\d{6}$")


def _suffix_for_cn(code: str) -> str:
    """Return ``.SH`` / ``.SZ`` / ``.BJ`` for a 6-digit A-share code.

    Falls back to an empty string if the prefix doesn't match any known
    series — caller decides whether to leave the code unchanged.
    """
    for prefix, suffix in _CN_PREFIX_TO_SUFFIX:
        if code.startswith(prefix):
            return suffix
    return ""


def normalize_ticker(ticker: str) -> tuple[str, str]:
    """Normalize a user-entered ticker into ``(canonical, suffix_note)``.

    The canonical ticker is what the downstream runner should receive.
    ``suffix_note`` is a short Chinese annotation describing the inferred
    exchange (or empty string if no inference happened), suitable for
    showing in a UI hint.

    Examples::

        ("600519", "")           → ("600519.SH",  "上交所")
        ("002335", "")           → ("002335.SZ",  "深交所")
        ("830799", "")           → ("830799.BJ",  "北交所")
        ("NVDA",   "")           → ("NVDA",        "")
        ("600519.SH", "")        → ("600519.SH",  "")  # already suffixed
        ("tsla",   "")           → ("TSLA",        "")
    """
    raw = (ticker or "").strip()
    if not raw:
        return ("", "")

    # Already carries a recognised suffix → trust it verbatim.
    upper = raw.upper()
    if upper.endswith((".SH", ".SZ", ".SS", ".BJ", ".HK")):
        # Normalize the legacy ``.SS`` → ``.SH`` spelling for consistency
        # with what we display in search results.
        if upper.endswith(".SS"):
            return (raw[:-3] + ".SH", "上交所")
        return (raw, "")

    # HK codes: 4–5 digits, sometimes zero-padded in user input.
    if re.fullmatch(r"\d{4,5}", raw):
        return (f"{int(raw):04d}.HK", "港交所")

    # CN A-share: exactly 6 digits, no decimal, no other letters.
    if _BARE_CODE.match(raw):
        suffix = _suffix_for_cn(raw)
        if suffix:
            exchange = {
                ".SH": "上交所",
                ".SZ": "深交所",
                ".BJ": "北交所",
            }[suffix]
            return (raw + suffix, exchange)

    # Anything else (NVDA, BRK.B, BTC-USD, ...) passes through.
    # Uppercase for consistency unless it contains non-ASCII.
    return (upper if raw.isascii() else raw, "")


def infer_a_share_exchange(ticker: str) -> str:
    """Convenience: return the Chinese exchange label for a code, or ``""``.

    Used by the UI to show a hint like "→ 将按 上交所 路由".
    """
    _, note = normalize_ticker(ticker)
    return note