"""Main window: input panel + progress + history + report viewer.

Layout:
    ┌─────────────┬──────────────────────────────────────┐
    │  History    │  InputPanel (ticker / date / submit) │
    │  (live +    ├──────────────────────────────────────┤
    │   saved)    │  ProgressPanel    │                  │
    │             │                   │  ReportViewer    │
    │             │                   │                  │
    └─────────────┴───────────────────┴──────────────────┘
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .core.i18n import T
from .core.live import LiveEntry, STATUS_COMPLETE, STATUS_FAILED, STATUS_RUNNING
from .core.reports import ReportEntry, files_for_viewer
from .core.runner import AnalysisRunner
from .widgets.history_panel import HistoryPanel
from .widgets.input_panel import InputPanel
from .widgets.progress_panel import ProgressPanel
from .widgets.report_viewer import ReportViewer


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TradingAgents · 多智能体投研分析")
        self.resize(1380, 880)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet("QMainWindow { background: #F7F8FA; }")

        self._runner = AnalysisRunner(self)
        self._current_live: LiveEntry | None = None
        self._build()
        self._wire()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("Card")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(14)

        outer = QSplitter(Qt.Horizontal)
        outer.setChildrenCollapsible(False)
        outer.setHandleWidth(8)

        # Left: history
        self.history = HistoryPanel()
        self.history.setMinimumWidth(320)
        self.history.setMaximumWidth(440)
        outer.addWidget(self.history)

        # Right: main column
        main_col = QWidget()
        main_col.setObjectName("Card")
        main_layout = QVBoxLayout(main_col)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        self.input = InputPanel()
        main_layout.addWidget(self.input)

        # Inner splitter: progress | viewer
        inner = QSplitter(Qt.Vertical)
        inner.setChildrenCollapsible(False)
        inner.setHandleWidth(8)
        self.progress = ProgressPanel()
        self.progress.setMinimumHeight(180)
        inner.addWidget(self.progress)

        self.viewer = ReportViewer()
        inner.addWidget(self.viewer)

        inner.setStretchFactor(0, 1)
        inner.setStretchFactor(1, 3)
        main_layout.addWidget(inner, stretch=1)

        outer.addWidget(main_col)
        outer.setStretchFactor(0, 0)
        outer.setStretchFactor(1, 1)

        root_layout.addWidget(outer)
        self.setCentralWidget(root)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(T["ready"])

    # ------------------------------------------------------------------ wire

    def _wire(self) -> None:
        self.input.run_requested.connect(self._start_run)
        self.input.cancel_requested.connect(self._cancel_run)
        self.history.open_report.connect(self._show_entry)
        self.history.cancel_live.connect(self._cancel_live)

        # runner -> progress
        self._runner.run_started.connect(self.progress.on_run_start)
        self._runner.stage_ready.connect(self.progress.on_stage)
        self._runner.propagate_done.connect(self.progress.on_propagate_done)
        self._runner.postprocess_step.connect(self.progress.on_postprocess)
        self._runner.log_line.connect(self.progress.on_log_line)

        # runner -> live entries
        self._runner.run_started.connect(self._on_run_start)
        self._runner.stage_ready.connect(self._on_stage)
        self._runner.run_done.connect(self._on_run_done)
        self._runner.run_failed.connect(self._on_run_failed)

    # ------------------------------------------------------------------ run lifecycle

    def _start_run(self, ticker: str, date: str) -> None:
        # Hand off to the QProcess wrapper. start() will emit run_started
        # synchronously, which fans out to progress + history, then spawn
        # the webapp/runner.py subprocess.
        self._runner.start(ticker, date)
        self.input.set_running(True)
        self.statusBar().showMessage(f"{T['running']}  {ticker}  {date}")

    def _cancel_run(self) -> None:
        self._runner.stop()
        self._finalize_live(failed=True, error="已取消")
        self.input.set_running(False)
        self.statusBar().showMessage(T["ready"])

    def _cancel_live(self, entry: LiveEntry) -> None:
        if self._current_live and self._current_live.key == entry.key:
            self._cancel_run()
        else:
            # Live entry whose run is already done — nothing to cancel
            self.history.remove_live(entry.key)

    # ------------------------------------------------------------------ live entry updates

    def _on_run_start(self, ticker: str, date: str) -> None:
        live = LiveEntry(ticker=ticker, date=date)
        self._current_live = live
        self.history.add_live(live)

    def _on_stage(self, _stage: str, field: str, _elapsed: float) -> None:
        if not self._current_live:
            return
        from .core.stages import STAGE_ORDER
        display = STAGE_ORDER.get(field, field)
        self._current_live.mark_stage(field, display)
        self.history.update_live(self._current_live)

    def _on_run_done(self, out_dir: str, decision: str) -> None:
        self.input.set_running(False)
        self._finalize_live(decision=decision)
        self.statusBar().showMessage(f"{T['run_complete']} · {decision}")
        self.history.refresh()

        # Auto-open the freshly written report
        p = Path(out_dir)
        if len(p.parts) >= 3:
            ticker, date = p.parts[-2], p.parts[-1]
            for entry in self.history._entries:
                if entry.ticker == ticker and entry.date == date:
                    self._show_entry(entry)
                    return

    def _on_run_failed(self, error: str, _traceback: str) -> None:
        self.input.set_running(False)
        self._finalize_live(failed=True, error=error[:80])
        self.statusBar().showMessage(f"{T['run_failed']}: {error}")

    def _finalize_live(self, decision: str = "", failed: bool = False, error: str = "") -> None:
        if not self._current_live:
            return
        if failed:
            self._current_live.mark_failed(error)
            # keep failed entry in live list briefly so user sees the error
            self.history.update_live(self._current_live)
            # remove after 3 seconds
            from PySide6.QtCore import QTimer
            key = self._current_live.key
            QTimer.singleShot(3000, lambda: self.history.remove_live(key))
        else:
            self._current_live.mark_complete(decision)
            self.history.remove_live(self._current_live.key)
        self._current_live = None

    # ------------------------------------------------------------------ report viewing

    def _show_entry(self, entry: ReportEntry) -> None:
        files = files_for_viewer(entry)
        if not files:
            self.statusBar().showMessage(
                f"{entry.ticker} {entry.date} · 报告文件缺失"
            )
            return
        prefer = "完整报告" if "完整报告" in files else (
            "摘要" if "摘要" in files else None
        )
        self.viewer.load_files(files, prefer=prefer)
        rating = entry.final_rating
        rating_str = f" · {rating}" if rating else ""
        self.statusBar().showMessage(
            f"已加载 {entry.ticker} {entry.date}{rating_str}"
        )
