"""QProcess wrapper around ``webapp/runner.py``.

Two launch paths:

* **Dev** (``python -m deskapp``): spawn ``sys.executable`` against
  ``webapp/runner.py`` via QProcess and stream its JSON-line stdout.
* **PyInstaller onefile** (frozen): ``sys.executable`` points at the bundled
  ``.exe`` itself. Re-launching it with ``webapp/runner.py`` as an argument
  makes the bootloader fall back to the default entry point
  (``__main__.py``) — which spawns a *second* deskapp window and never runs
  the analysis. We avoid that entirely by running ``webapp.runner.run`` in
  a QThread inside the existing process, with the JSON-line ``emit`` hook
  monkey-patched to a Qt signal so the rest of the UI sees the same events
  as the QProcess path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QThread, Signal


# /Users/sbb/TradingAgents
ROOT: Path = Path(__file__).resolve().parent.parent.parent
RUNNER: Path = ROOT / "webapp" / "runner.py"
PYTHON: str = sys.executable

# Detection: PyInstaller sets ``sys.frozen`` to True and ``sys.executable`` to
# the bundle path. In dev (regular python), ``frozen`` is undefined.
IS_FROZEN = getattr(sys, "frozen", False)


class AnalysisRunner(QObject):
    """Spawn a single analysis run.

    In dev: via QProcess (the original JSON-line stdout protocol).
    In PyInstaller: via an in-process QThread (no subprocess roundtrip).
    """

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
        self._thread: "_InProcessRun | None" = None
        self._ticker = ""
        self._date = ""

    # ------------------------------------------------------------------ public

    def is_running(self) -> bool:
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            return True
        if self._thread is not None and self._thread.isRunning():
            return True
        return False

    def start(self, ticker: str, date: str) -> None:
        if self.is_running():
            return
        self._ticker = ticker
        self._date = date
        self.run_started.emit(ticker, date)
        if IS_FROZEN:
            self._start_inproc(ticker, date)
        else:
            self._start_subproc(ticker, date)

    def stop(self) -> None:
        if self._proc and self._proc.state() != QProcess.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(2000)
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.wait(2000)

    # ------------------------------------------------------------------ subprocess (dev)

    def _start_subproc(self, ticker: str, date: str) -> None:
        self._proc = QProcess(self)
        self._proc.setWorkingDirectory(str(ROOT))
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_output)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)
        self._proc.start(PYTHON, [str(RUNNER), ticker, date])

    def _on_output(self) -> None:
        if not self._proc:
            return
        raw = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in raw.splitlines():
            self._dispatch_line(line)

    def _on_finished(self) -> None:
        self._proc = None

    def _on_error(self, _err) -> None:
        # Errors are already surfaced via run_failed; nothing extra to do.
        pass

    # ------------------------------------------------------------------ in-process (PyInstaller)

    def _start_inproc(self, ticker: str, date: str) -> None:
        self._thread = _InProcessRun(ticker, date, self)
        self._thread.finished.connect(self._on_inproc_finished)
        self._thread.start()

    def _on_inproc_finished(self) -> None:
        # Errors are already emitted via run_failed; nothing extra to do.
        self._thread = None

    # ------------------------------------------------------------------ shared dispatch

    def _dispatch_line(self, raw_line: str) -> None:
        line = raw_line.strip()
        if not line:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self.log_line.emit(line)
            return
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
            self.run_done.emit(event.get("out_dir", ""), event.get("decision", ""))
        elif t == "run_error":
            self.run_failed.emit(event.get("error", ""), event.get("traceback", ""))
        elif t == "run_start":
            # already emitted in start() before subprocess
            pass


class _InProcessRun(QThread):
    """QThread that runs ``webapp.runner.run()`` in-process and translates
    its ``emit()`` calls into Qt signals on the parent ``AnalysisRunner``.
    """

    def __init__(self, ticker: str, date: str, owner: "AnalysisRunner") -> None:
        super().__init__()
        self._ticker = ticker
        self._date = date
        self._owner = owner

    def run(self) -> None:  # QThread entry point
        try:
            from webapp import runner as _runner
        except Exception as e:  # pragma: no cover
            self._owner.run_failed.emit(str(e), "")
            return
        # Monkey-patch the module-level emitter to forward into Qt signals.
        _runner.emit = lambda event_type, **data: self._forward(event_type, data)
        try:
            _runner.run(self._ticker, self._date)
        except Exception as e:
            import traceback
            self._owner.run_failed.emit(str(e), traceback.format_exc())

    def _forward(self, event_type: str, data: dict) -> None:
        # Translate JSON-shape events into the same Qt signals the QProcess
        # path would have produced.
        if event_type == "stage":
            self._owner.stage_ready.emit(
                data.get("stage", ""),
                data.get("field", ""),
                float(data.get("elapsed", 0.0)),
            )
        elif event_type == "propagate_done":
            self._owner.propagate_done.emit(float(data.get("elapsed", 0.0)))
        elif event_type == "postprocess":
            self._owner.postprocess_step.emit(data.get("step", ""))
        elif event_type == "run_done":
            self._owner.run_done.emit(data.get("out_dir", ""), data.get("decision", ""))
        elif event_type == "run_error":
            self._owner.run_failed.emit(data.get("error", ""), data.get("traceback", ""))
        elif event_type == "run_start":
            pass  # already emitted by start()
        else:
            # Unknown event: surface as a log line so it isn't silently dropped.
            self._owner.log_line.emit(f"{event_type} {data}")
