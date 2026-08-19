"""Scan the ``results/`` directory and read finished reports.

Layout produced by ``webapp/runner.py`` (and ``run.py``):
    results/<TICKER>/<DATE>/
        完整报告.md
        摘要.md
        final_decision.json
        market_report.md
        fundamentals_report.md
        news_report.md
        sentiment_report.md
        investment_plan.md
        trader_investment_plan.md
        final_trade_decision.md
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


ROOT: Path = Path(__file__).resolve().parent.parent.parent
RESULTS: Path = ROOT / "results"

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


@dataclass
class ReportEntry:
    """One saved report = ``results/<TICKER>/<DATE>/`` directory."""

    ticker: str
    date: str
    full_report: Path | None = None
    summary: Path | None = None
    final_decision: Path | None = None
    agent_reports: dict[str, Path] = field(default_factory=dict)
    # Per-agent reports keyed by state field (e.g. "market_report").

    @property
    def label(self) -> str:
        return f"{self.ticker} · {self.date}"

    @property
    def sort_key(self) -> str:
        # descending by date then ticker
        return f"{self.date}_{self.ticker}"

    @property
    def final_rating(self) -> str:
        """Read final_decision.json and return the rating string, if any.

        The file is normally a bare JSON string (e.g. ``"Underweight"``) but
        older runs may have produced a dict with ``rating`` / ``decision``.
        """
        if not self.final_decision:
            return ""
        try:
            data = json.loads(self.final_decision.read_text(encoding="utf-8"))
        except Exception:
            return ""
        if isinstance(data, str):
            return data.strip()
        if isinstance(data, dict):
            for key in ("rating", "decision", "signal", "final_decision"):
                if data.get(key):
                    return str(data[key])
        return ""


def _safe_subdir(path: Path) -> bool:
    return path.is_dir() and bool(SAFE_NAME.match(path.name))


def scan_reports(results_dir: Path = RESULTS) -> list[ReportEntry]:
    """Walk ``results/<TICKER>/<DATE>/`` and return a sorted list of entries."""
    if not results_dir.exists():
        return []
    entries: list[ReportEntry] = []
    try:
        ticker_dirs = sorted(results_dir.iterdir(), reverse=True)
    except OSError:
        return []
    for ticker_dir in ticker_dirs:
        if not _safe_subdir(ticker_dir):
            continue
        try:
            date_dirs = sorted(ticker_dir.iterdir(), reverse=True)
        except OSError:
            continue
        for date_dir in date_dirs:
            if not _safe_subdir(date_dir):
                continue
            entry = ReportEntry(ticker=ticker_dir.name, date=date_dir.name)
            full = date_dir / "完整报告.md"
            if full.exists():
                entry.full_report = full
            summary = date_dir / "摘要.md"
            if summary.exists():
                entry.summary = summary
            decision = date_dir / "final_decision.json"
            if decision.exists():
                entry.final_decision = decision
            # per-agent reports
            for md in date_dir.glob("*.md"):
                if md.name in ("完整报告.md", "摘要.md"):
                    continue
                entry.agent_reports[md.stem] = md
            entries.append(entry)

    # newest first
    entries.sort(key=lambda e: e.sort_key, reverse=True)
    return entries


def files_for_viewer(entry: ReportEntry) -> dict[str, Path]:
    """Return ``{label: Path}`` for the report viewer, ordered.

    Order: 完整报告 → 摘要 → 子报告 (按 STAGE_ORDER).
    """
    # local import to avoid circular dependency with stages.py
    from .stages import STAGE_ORDER

    out: dict[str, Path] = {}
    if entry.full_report:
        out["完整报告"] = entry.full_report
    if entry.summary:
        out["摘要"] = entry.summary
    for field_name, display_name in STAGE_ORDER.items():
        path = entry.agent_reports.get(field_name)
        if path:
            out[display_name] = path
    return out


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""
