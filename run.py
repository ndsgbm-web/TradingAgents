"""End-to-end wrapper: run a multi-agent analysis and emit a merged Chinese report.

Usage:
    python run.py 300812.SZ 2026-08-14
    python run.py TSLA 2026-08-14
    python run.py SPCX 2026-08-14
    python run.py 600519.SH 2026-08-14       # CN ticker routes to AkShare automatically

Outputs go to ``results/<TICKER>/<DATE>/``:
    - final_decision.json
    - <agent>.md            (7 per-agent reports)
    - 完整报告.md           (merged Chinese report — primary deliverable)
"""
from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from pathlib import Path

# MUST be installed before akshare / py_mini_racer are imported for the
# first time. AkShare modules (cninfo / air / etc.) bind ``MiniRacer`` at
# import time, so a later monkey-patch would not catch them.
from tradingagents.dataflows import _py_mini_racer_lock as _racr_lock
_racr_lock.install()

# Quiet the framework's verbose library warnings; keep our own progress visible.
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402

REPORT_KEYS = (
    "market_report",
    "fundamentals_report",
    "news_report",
    "sentiment_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
)


def run(ticker: str, date: str) -> Path:
    """Run the analysis and return the results directory."""
    cfg = DEFAULT_CONFIG.copy()
    print(f"[run] ticker={ticker} date={date}")
    print(f"[run] provider={cfg['llm_provider']} deep={cfg['deep_think_llm']} quick={cfg['quick_think_llm']}")
    print(f"[run] backend_url={cfg.get('backend_url')}")

    ta = TradingAgentsGraph(debug=False, config=cfg)
    t0 = time.time()
    try:
        final_state, decision = ta.propagate(ticker, date)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    elapsed = time.time() - t0
    print(f"[run] propagate done in {elapsed:.0f}s — decision={decision}")

    out_dir = Path("results") / ticker / date
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Structured decision
    (out_dir / "final_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # 2) Per-agent markdown
    state = final_state or {}
    for key in REPORT_KEYS:
        body = state.get(key)
        if isinstance(body, str):
            (out_dir / f"{key}.md").write_text(body, encoding="utf-8")

    # 3) Merged Chinese report
    import subprocess
    subprocess.run(
        [sys.executable, "merge_report.py", str(out_dir)],
        check=True,
        cwd=Path(__file__).parent,
    )

    # 4) Condensed Chinese executive summary (via M3)
    try:
        subprocess.run(
            [sys.executable, "summarize.py", str(out_dir)],
            check=True,
            cwd=Path(__file__).parent,
        )
    except subprocess.CalledProcessError as e:
        print(f"[run] WARNING: summarize.py failed (exit {e.returncode}); continuing", file=sys.stderr)

    print(f"[run] saved under {out_dir.resolve()}")
    print(f"[run] deliverables:")
    print(f"[run]   - 完整报告.md   (full Chinese TOC + concatenated sections)")
    print(f"[run]   - 摘要.md        (condensed Chinese executive summary)")
    return out_dir


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: python run.py <TICKER> <YYYY-MM-DD>")
    ticker = sys.argv[1].strip()
    date = sys.argv[2].strip()
    run(ticker, date)


if __name__ == "__main__":
    main()
