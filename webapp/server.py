"""FastAPI backend: spawns analysis runs and streams progress to the browser.

Endpoints:
    GET  /                            -> static/index.html
    POST /api/run                     -> {ticker, date} -> {run_id}
    GET  /api/run/{run_id}/events     -> SSE stream of progress events
    GET  /api/run/{run_id}            -> {status, events}
    GET  /api/runs                    -> list of past runs scanned from results/
    GET  /api/runs/{ticker}/{date}/files/{name} -> markdown report content

Run:
    uvicorn webapp.server:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from webapp.search import search as search_symbols

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
STATIC = Path(__file__).resolve().parent / "static"
PYTHON = sys.executable  # venv interpreter — inherits fastapi + tradingagents

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("webapp")

app = FastAPI(title="TradingAgents Web UI")

# In-memory run registry. Runs are short-lived; persisting them isn't needed.
# Each entry: {"id": str, "ticker": str, "date": str, "status": str,
#              "events": [event_dict, ...], "started_at": float, "proc": Popen}
RUNS: dict[str, dict[str, Any]] = {}
RUNS_LOCK = threading.Lock()

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


class RunRequest(BaseModel):
    ticker: str
    date: str  # YYYY-MM-DD


def _validate_ticker(ticker: str) -> str:
    if not SAFE_NAME.match(ticker):
        raise HTTPException(400, f"invalid ticker: {ticker!r}")
    return ticker


def _validate_date(date: str) -> str:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise HTTPException(400, f"invalid date: {date!r}")
    return date


def _pump_events(run_id: str, proc: subprocess.Popen) -> None:
    """Read runner stdout line-by-line, parse JSON events, append to RUNS."""
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON output (e.g. logging) — keep as a raw log event.
                event = {"type": "log", "line": line, "ts": round(time.time(), 2)}
            with RUNS_LOCK:
                if run_id in RUNS:
                    RUNS[run_id]["events"].append(event)
                    if event.get("type") == "run_done":
                        RUNS[run_id]["status"] = "completed"
                    elif event.get("type") == "run_error":
                        RUNS[run_id]["status"] = "failed"
                        RUNS[run_id]["error"] = event.get("error", "unknown")
    finally:
        proc.wait()
        with RUNS_LOCK:
            if run_id in RUNS and RUNS[run_id]["status"] == "running":
                # Process exited without run_done / run_error.
                if proc.returncode == 0:
                    RUNS[run_id]["status"] = "completed"
                else:
                    RUNS[run_id]["status"] = "failed"
                    RUNS[run_id]["error"] = f"exited with code {proc.returncode}"


@app.post("/api/run")
def start_run(req: RunRequest) -> dict:
    ticker = _validate_ticker(req.ticker)
    date = _validate_date(req.date)
    run_id = uuid.uuid4().hex[:12]

    cmd = [PYTHON, "webapp/runner.py", ticker, date]
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr into stdout so logs land in events
        text=True,
        bufsize=1,
    )

    with RUNS_LOCK:
        RUNS[run_id] = {
            "id": run_id,
            "ticker": ticker,
            "date": date,
            "status": "running",
            "events": [],
            "started_at": time.time(),
            "proc": proc,
        }

    threading.Thread(target=_pump_events, args=(run_id, proc), daemon=True).start()
    logger.info("started run %s for %s on %s (pid=%s)", run_id, ticker, date, proc.pid)
    return {"run_id": run_id}


@app.get("/api/run/{run_id}")
def get_run(run_id: str) -> dict:
    with RUNS_LOCK:
        if run_id not in RUNS:
            raise HTTPException(404, "run not found")
        r = RUNS[run_id]
        return {
            "id": r["id"],
            "ticker": r["ticker"],
            "date": r["date"],
            "status": r["status"],
            "events": r["events"],
            "started_at": r["started_at"],
            "error": r.get("error"),
        }


@app.get("/api/run/{run_id}/events")
async def stream_events(run_id: str):
    """SSE stream of progress events for a single run."""
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")

    async def event_source():
        last_idx = 0
        while True:
            with RUNS_LOCK:
                if run_id not in RUNS:
                    return
                events = RUNS[run_id]["events"]
                status = RUNS[run_id]["status"]
                new_events = events[last_idx:]
                last_idx = len(events)

            for ev in new_events:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

            if status != "running":
                # Send a final close signal so the browser can clean up.
                yield f"data: {json.dumps({'type': 'stream_end', 'status': status})}\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _scan_runs() -> list[dict]:
    """Walk results/ and return one entry per completed (ticker, date) pair."""
    if not RESULTS.exists():
        return []
    out: list[dict] = []
    for ticker_dir in sorted(RESULTS.iterdir()):
        if not ticker_dir.is_dir():
            continue
        for date_dir in sorted(ticker_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            decision_file = date_dir / "final_decision.json"
            summary_file = date_dir / "摘要.md"
            full_file = date_dir / "完整报告.md"
            entry = {
                "ticker": ticker_dir.name,
                "date": date_dir.name,
                "has_summary": summary_file.exists(),
                "has_full": full_file.exists(),
                "has_decision": decision_file.exists(),
                "decision": None,
            }
            if decision_file.exists():
                try:
                    d = json.loads(decision_file.read_text(encoding="utf-8"))
                    if isinstance(d, str):
                        entry["decision"] = d
                    elif isinstance(d, dict):
                        entry["decision"] = d.get("decision") or d.get("action") or str(d)[:80]
                except Exception:
                    pass
            out.append(entry)
    return out


@app.get("/api/runs")
def list_runs() -> list[dict]:
    return _scan_runs()


@app.get("/api/runs/active")
def list_active_runs() -> list[dict]:
    """List in-flight runs (status == "running") so a refresh doesn't lose them."""
    now = time.time()
    with RUNS_LOCK:
        return [
            {
                "id": r["id"],
                "ticker": r["ticker"],
                "date": r["date"],
                "started_at": r["started_at"],
                "elapsed": round(now - r["started_at"], 1),
            }
            for r in RUNS.values()
            if r["status"] == "running"
        ]


@app.get("/api/runs/{ticker}/{date}/files/{name}")
def get_report_file(ticker: str, date: str, name: str):
    """Return the raw markdown for a single report file inside a run directory."""
    _validate_ticker(ticker)
    _validate_date(date)
    # Allow only safe basenames — no path traversal.
    if not re.match(r"^[\w\u4e00-\u9fff.-]+\.(md|json)$", name):
        raise HTTPException(400, f"invalid filename: {name!r}")
    p = RESULTS / ticker / date / name
    if not p.exists() or not p.is_file():
        raise HTTPException(404, f"file not found: {name}")
    return FileResponse(p, media_type="text/plain; charset=utf-8")


@app.get("/api/search")
def api_search(q: str = "", limit: int = 10) -> list[dict]:
    """Return symbol candidates matching the user's free-text query.

    Backed by CN A-share names (akshare), a curated CN-alias table, and
    yfinance Search for global/HK markets. Never raises - missing optional
    dependencies or upstream failures return an empty list.
    """
    q = q.strip()
    if not q:
        return []
    try:
        return search_symbols(q, limit=limit)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("search failed for %r: %s", q, exc)
        return []


# Static files: serve index.html at / and any other assets from /static.
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    # Disable caching so the SPA-style frontend always gets fresh JS/HTML
    # after edits. Safari will still respect ETag/Last-Modified on subresources.
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/healthz")
def healthz():
    return JSONResponse({"ok": True})
