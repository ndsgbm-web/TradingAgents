"""Live progress: 8-stage checklist + log stream + postprocess indicator."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.i18n import T
from ..core.stages import STAGE_ORDER, postprocess_label


class ProgressPanel(QWidget):
    """Renders live progress events emitted by ``AnalysisRunner``."""

    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()
        self._reset()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel(T["progress_title"])
        title.setProperty("role", "title")
        header.addWidget(title)
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "hint")
        header.addWidget(self.status_label, stretch=1)
        layout.addLayout(header)

        # Stages list (custom Stepper object name → transparent QSS rules)
        self.stages_list = QListWidget()
        self.stages_list.setObjectName("Stepper")
        for field_name, display_name in STAGE_ORDER.items():
            item = QListWidgetItem(f"  {display_name}")
            item.setData(Qt.UserRole, field_name)
            self.stages_list.addItem(item)
        layout.addWidget(self.stages_list, stretch=2)

        # Reminder note (amber-tinted via theme role)
        note = QLabel(T["internal_note"])
        note.setWordWrap(True)
        note.setProperty("role", "note")
        layout.addWidget(note)

        # Log stream (dark code panel; doesn't follow light theme on purpose)
        layout.addWidget(QLabel(T["tool_calls"]))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setStyleSheet(
            "QPlainTextEdit {"
            "  font-family: 'SF Mono', Menlo, 'Cascadia Code', monospace;"
            "  font-size: 12px;"
            "  background: #0D1117; color: #C9D1D9;"
            "  border: 1px solid #E2E5EA; border-radius: 10px;"
            "  padding: 8px 10px;"
            "}"
        )
        layout.addWidget(self.log_view, stretch=1)

    # ------------------------------------------------------------------ public

    def _reset(self) -> None:
        for i in range(self.stages_list.count()):
            item = self.stages_list.item(i)
            field = item.data(Qt.UserRole)
            item.setText(f"  {STAGE_ORDER[field]}")
        self.log_view.clear()
        self.status_label.setText(T["ready"])

    # ------------------------------------------------------------------ runner events

    def on_run_start(self, ticker: str, date: str) -> None:
        self._reset()
        self._append_log(f"▶ {ticker}  {date}  {T['starting']}")
        self.status_label.setText(T["running"])

    def on_stage(self, stage: str, field: str, elapsed: float) -> None:
        for i in range(self.stages_list.count()):
            item = self.stages_list.item(i)
            if item.data(Qt.UserRole) == field:
                item.setText(f"✓ {STAGE_ORDER[field]}  · {elapsed:.1f}s")
                break
        self._append_log(f"  ✓ {stage}  {elapsed:.1f}s")

    def on_propagate_done(self, elapsed: float) -> None:
        self.status_label.setText(
            f"多 Agent 推理完成 ({elapsed:.1f}s) — {T['post_process']}"
        )

    def on_postprocess(self, step: str) -> None:
        self._append_log(f"  ⋯ {T['post_process']}: {postprocess_label(step)}")

    def on_run_done(self, out_dir: str, decision: str) -> None:
        self.status_label.setText(f"✔ {T['run_complete']} · {decision}")
        self._append_log(f"✔ {T['run_complete']}: {out_dir}")
        self._append_log(f"  评级: {decision}")

    def on_run_failed(self, error: str, traceback: str) -> None:
        self.status_label.setText(f"✘ {T['run_failed']}")
        self._append_log(f"✘ {T['run_failed']}: {error}")
        # trim traceback to first 5 lines
        for line in traceback.splitlines()[:5]:
            self._append_log(f"    {line}")

    def on_log_line(self, line: str) -> None:
        # filter noisy lines from the underlying framework
        if "DEBUG" in line and "INFO" not in line:
            return
        if line.startswith("(function "):
            return
        self._append_log(line)

    # ------------------------------------------------------------------ internal

    def _append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)
