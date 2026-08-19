"""QProcess wrapper around ``webapp/runner.py``.

The webapp exposes a clean JSON-line event stream on stdout; we reuse the
exact same subprocess interface here so the desktop app and the webapp stay
behaviour-identical. Each parser-parsed event is re-emitted as a Qt signal
so the UI can update in real time without touching the runner.

Event types emitted by ``webapp/runner.py``:
    run_start       {ticker, date}
    stage           {stage, field, elapsed}
    propagate_done  {elapsed}
    postprocess     {step}             ("merge_report" | "summarize")
    run_done        {out_dir, decision}
    run_error       {error, traceback}
    (non-JSON)      forwarded as ``log_line``
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


# /Users/sbb/TradingAgents
ROOT: Path = Path(__file__).resolve().parent.parent.parent
RUNNER: Path = ROOT / "webapp" / "runner.py"
PYTHON: str = sys.executable


class AnalysisRunner(QObject):
    """Spawn a single analysis run via the existing webapp runner subprocess."""

    # JSON event categories from webapp/runner.py
    run_started     = Signal(str, str)              # (ticker, date)
    stage_ready     = Signal(str, str, float)       # (stage_label, field, elapsed)
    propagate_done  = Signal(float)                 # elapsed
    postprocess_step = Signal(str)                  # "merge_report" | "summarize"
    run_done        = Signal(str, str)              # (out_dir, decision)
    run_failed      = Signal(str, str)              # (error, traceback)
    log_line        = Signal(str)                   # non-JSON log line

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._ticker = ""
        self._date = ""
        self._log_file = None  # open file handle writing the run log to disk

    # ------------------------------------------------------------------ public

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.NotRunning

    def start(self, ticker: str, date: str) -> None:
        if self.is_running():
            return
        self._ticker = ticker
        self._date = date
        # Persist a per-run log next to the (eventual) reports so a crash can
        # always be inspected after the window is closed.
        try:
            log_dir = ROOT / "results" / ticker / date
            log_dir.mkdir(parents=True, exist_ok=True)
            self._log_file = (log_dir / "runner.log").open("w", encoding="utf-8")
            self._log_file.write(
                f"# TradingAgents run log\n"
                f"# ticker={ticker} date={date} started={time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            self._log_file.flush()
        except OSError as e:
            print(f"[AnalysisRunner] could not open per-run log: {e}")
            self._log_file = None

        self._proc = QProcess(self)
        self._proc.setWorkingDirectory(str(ROOT))
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_output)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)
        self.run_started.emit(ticker, date)
        if self._log_file:
            self._log_file.write(f">>> python {RUNNER.name} {ticker} {date}\n")
            self._log_file.flush()
        self._proc.start(PYTHON, [str(RUNNER), ticker, date])

    def stop(self) -> None:
        if self._proc and self._proc.state() != QProcess.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(2000)

    # ------------------------------------------------------------------ internal

    def _on_output(self) -> None:
        if not self._proc:
            return
        raw = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        # Mirror every line to the on-disk log FIRST so even unparseable lines
        # (e.g. mid-traceback fragments) survive a window close / crash.
        if self._log_file and not self._log_file.closed:
            try:
                self._log_file.write(raw)
                self._log_file.flush()
            except OSError:
                pass
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                self.log_line.emit(line)
                continue
            t = event.get("type")
            if t == "stage":
                self.stage_ready.emit(
                    event.get("stage", ""),
                    event.get("field", ""),
                    float(event.get("elapsed", 0.0)),
                )
            elif t == "propagate_done":
                self.propagate_done.emit(float(event.get("elapsed", 0.0)))
            elif t == "postprocess":
                self.postprocess_step.emit(event.get("step", ""))
            elif t == "run_done":
                self.run_done.emit(
                    event.get("out_dir", ""),
                    event.get("decision", ""),
                )
            elif t == "run_error":
                self.run_failed.emit(
                    event.get("error", ""),
                    event.get("traceback", ""),
                )
            # run_start is redundant — we already emitted run_started on start()

    def _close_log(self) -> None:
        if self._log_file and not self._log_file.closed:
            try:
                self._log_file.write("\n# runner exited\n")
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        # If the subprocess exited without emitting run_done / run_error,
        # surface that as a failure so the UI can reset.
        if exit_status == QProcess.CrashExit:
            self.run_failed.emit("子进程崩溃", f"exit code: {exit_code}")
        elif exit_code != 0:
            self.run_failed.emit(
                f"runner 退出码 {exit_code}",
                "未收到 run_done / run_error 事件（可能被外部终止）",
            )
        self._proc = None

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if self._proc:
            self.run_failed.emit("QProcess 错误", str(error))
            self._proc = None



def _close_log_unused():  # never called, just a marker for grep
    pass
