"""Standalone analysis runner: streams progress as JSON-line events to stdout.

The web backend spawns this as a subprocess and forwards each JSON event to the
browser via SSE. Events use the shape {"type": ..., "ts": ..., ...}.

Usage:
    python webapp/runner.py <TICKER> <YYYY-MM-DD>
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

# Run from the TradingAgents repo root regardless of caller cwd.
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# MUST be installed before akshare / py_mini_racer are imported for the
# first time. AkShare modules (cninfo / air / etc.) bind ``MiniRacer`` at
# import time, so a later monkey-patch would not catch them. The desktop
# GUI also routes through this entry point (via QProcess), so without this
# line mini_racer's V8 isolate is touched from langgraph's worker thread
# pool and aborts with ``Check failed: !pool->IsInitialized()``.
from tradingagents.dataflows import _py_mini_racer_lock as _racr_lock  # noqa: E402
_racr_lock.install()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    stream=sys.stderr,
)

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402

# State-field -> (label, content_check). content_check extracts the substring
# we treat as "this stage has produced output". For string fields it's the
# string itself; for the debate TypedDicts we look at judge_decision/history
# since the parent dict is always non-empty.
STAGE_LABELS = [
    ("market_report", "Market Analyst", lambda v: isinstance(v, str) and v.strip()),
    ("sentiment_report", "Sentiment Analyst", lambda v: isinstance(v, str) and v.strip()),
    ("news_report", "News Analyst", lambda v: isinstance(v, str) and v.strip()),
    ("fundamentals_report", "Fundamentals Analyst", lambda v: isinstance(v, str) and v.strip()),
    ("investment_plan", "Research Manager", lambda v: isinstance(v, str) and v.strip()),
    ("trader_investment_plan", "Trader", lambda v: isinstance(v, str) and v.strip()),
    (
        "risk_debate_state",
        "Risk Analysts",
        lambda v: isinstance(v, dict)
        and (v.get("judge_decision") or v.get("history") or v.get("aggressive_history")),
    ),
    ("final_trade_decision", "Portfolio Manager", lambda v: isinstance(v, str) and v.strip()),
]

REPORT_KEYS = (
    "market_report",
    "fundamentals_report",
    "news_report",
    "sentiment_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
)


def _default_emit(event_type: str, **data) -> None:
    """Default emitter: write one JSON-line event to stdout."""
    payload = {"type": event_type, "ts": round(time.time(), 2), **data}
    print(json.dumps(payload, ensure_ascii=False), flush=True)


# Module-level — deskapp replaces this with a Qt-signal emitter when running
# in-process (so QProcess + relative-import footguns are sidestepped entirely).
emit = _default_emit


def run(ticker: str, date: str) -> Path:
    emit("run_start", ticker=ticker, date=date)

    cfg = DEFAULT_CONFIG.copy()
    ta = TradingAgentsGraph(debug=False, config=cfg)
    ta.ticker = ticker
    ta._resolve_pending_entries(ticker)

    past_context = ta.memory_log.get_past_context(ticker)
    instrument_context = ta.resolve_instrument_context(ticker, "stock")
    init_agent_state = ta.propagator.create_initial_state(
        ticker,
        date,
        asset_type="stock",
        past_context=past_context,
        instrument_context=instrument_context,
    )
    args = ta.propagator.get_graph_args()

    seen: set[str] = set()
    final_state: dict = {}
    t0 = time.time()

    for chunk in ta.graph.stream(init_agent_state, **args):
        if not isinstance(chunk, dict):
            continue
        # langgraph's stream may yield either {node_name: state} (updates mode)
        # or a state dict directly (values mode). Unwrap one level of node
        # names so both shapes work.
        candidates: list[dict] = []
        if "messages" in chunk:
            candidates.append(chunk)
        else:
            for v in chunk.values():
                if isinstance(v, dict):
                    candidates.append(v)
        for cand in candidates:
            for field, label, has_content in STAGE_LABELS:
                if field in cand and field not in seen and has_content(cand[field]):
                    seen.add(field)
                    emit("stage", stage=label, field=field, elapsed=round(time.time() - t0, 1))
            final_state.update(cand)

    emit("propagate_done", elapsed=round(time.time() - t0, 1))

    out_dir = ROOT / "results" / ticker / date
    out_dir.mkdir(parents=True, exist_ok=True)

    decision = ta.process_signal(final_state.get("final_trade_decision", ""))
    (out_dir / "final_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    for key in REPORT_KEYS:
        body = final_state.get(key)
        if isinstance(body, str):
            (out_dir / f"{key}.md").write_text(body, encoding="utf-8")

    emit("postprocess", step="merge_report")
    subprocess.run(
        [sys.executable, "merge_report.py", str(out_dir)],
        check=False,
        cwd=ROOT,
    )
    emit("postprocess", step="summarize")
    subprocess.run(
        [sys.executable, "summarize.py", str(out_dir)],
        check=False,
        cwd=ROOT,
    )

    emit(
        "run_done",
        out_dir=str(out_dir.relative_to(ROOT)),
        decision=decision if isinstance(decision, str) else str(decision),
    )
    return out_dir


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: python webapp/runner.py <TICKER> <YYYY-MM-DD>")
    ticker = sys.argv[1].strip()
    date = sys.argv[2].strip()
    try:
        run(ticker, date)
    except Exception as e:  # noqa: BLE001 - surface anything to the UI
        emit("run_error", error=str(e), traceback=traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
