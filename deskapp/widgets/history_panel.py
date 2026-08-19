"""History sidebar: live runs at top + saved reports below, search, delete, open."""
from __future__ import annotations

import shutil
import subprocess

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.i18n import T
from ..core.live import LiveEntry, STATUS_COMPLETE, STATUS_FAILED, STATUS_RUNNING
from ..core.reports import RESULTS, ReportEntry, scan_reports


_SECTION_LIVE = "正在运行"
_SECTION_HISTORY = "历史报告"


class HistoryPanel(QWidget):
    """Sidebar showing live runs and saved reports.

    Emit ``open_report(entry)`` when the user activates a saved report.
    """

    open_report = Signal(object)  # ReportEntry

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[ReportEntry] = []
        self._live_entries: dict[str, LiveEntry] = {}
        self._build()

        # Heartbeat: refresh elapsed time / copy of live entries every 1s
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_live_labels)
        self._timer.start()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel(T["history_title"])
        title.setProperty("role", "title")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setProperty("role", "search")
        self.search.setPlaceholderText(T["search_history"])
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._on_open)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list, stretch=1)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton(T["refresh"])
        self.refresh_btn.setProperty("role", "ghost")
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ public

    def refresh(self) -> None:
        """Re-scan the results directory and re-render."""
        self._entries = scan_reports()
        self._render()

    # live entries
    def add_live(self, entry: LiveEntry) -> None:
        self._live_entries[entry.key] = entry
        self._render()

    def update_live(self, entry: LiveEntry) -> None:
        self._live_entries[entry.key] = entry
        self._render()

    def remove_live(self, key: str) -> None:
        self._live_entries.pop(key, None)
        self._render()

    def get_live(self, key: str) -> LiveEntry | None:
        return self._live_entries.get(key)

    # ------------------------------------------------------------------ render

    def _filter(self, query: str) -> None:
        # We don't filter live entries; they should always be visible.
        query = query.strip().lower()
        self._render(filter_q=query)

    def _render(self, filter_q: str = "") -> None:
        self.list.clear()

        # ─── Live section ───
        if self._live_entries:
            header = QListWidgetItem(f"⏳ {_SECTION_LIVE} ({len(self._live_entries)})")
            header.setFlags(Qt.NoItemFlags)
            header.setData(Qt.UserRole, "section")
            self.list.addItem(header)
            for entry in self._live_entries.values():
                self.list.addItem(self._make_live_item(entry))

        # ─── Saved reports section ───
        rows = self._entries
        if filter_q:
            rows = [e for e in rows if filter_q in e.ticker.lower() or filter_q in e.date]

        header = QListWidgetItem(f"📚 {_SECTION_HISTORY} ({len(rows)})")
        header.setFlags(Qt.NoItemFlags)
        header.setData(Qt.UserRole, "section")
        self.list.addItem(header)

        if not rows:
            placeholder = QListWidgetItem(T["no_history"])
            placeholder.setFlags(Qt.NoItemFlags)
            self.list.addItem(placeholder)
            return

        for e in rows:
            icons = []
            if e.full_report:
                icons.append("📄")
            if e.summary:
                icons.append("📋")
            rating = e.final_rating
            rating_str = f"  ·  {rating}" if rating else ""
            label = f"{' '.join(icons)}  {e.ticker}  ·  {e.date}{rating_str}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ("report", e))
            self.list.addItem(item)

    def _make_live_item(self, entry: LiveEntry) -> QListWidgetItem:
        if entry.status == STATUS_COMPLETE:
            icon = "✔"
            status_str = f"完成  ·  {entry.final_decision or '—'}"
        elif entry.status == STATUS_FAILED:
            icon = "✘"
            status_str = f"失败  ·  {entry.error[:40]}"
        else:
            icon = "●"
            stage = entry.current_stage or "等待启动"
            status_str = f"进行中  ·  {stage}  ({entry.elapsed:.0f}s)"
        label = f"{icon}  {entry.ticker}  ·  {entry.date}  —  {status_str}"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, ("live", entry))
        return item

    def _refresh_live_labels(self) -> None:
        """Re-render live entry labels (elapsed counter ticks)."""
        if not self._live_entries:
            return
        # only re-render live section labels; cheap approach
        for i in range(self.list.count()):
            item = self.list.item(i)
            data = item.data(Qt.UserRole)
            if isinstance(data, tuple) and len(data) == 2 and data[0] == "live":
                entry = data[1]
                if entry.status == STATUS_RUNNING:
                    new_label = self._make_live_item(entry).text()
                    item.setText(new_label)

    # ------------------------------------------------------------------ slots

    def _on_open(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.UserRole)
        if isinstance(data, tuple) and data[0] == "report":
            self.open_report.emit(data[1])

    def _on_context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not isinstance(data, tuple):
            return
        if data[0] == "live":
            self._live_context_menu(item, data[1], pos)
        elif data[0] == "report":
            self._report_context_menu(item, data[1], pos)

    def _live_context_menu(self, item: QListWidgetItem, entry: LiveEntry, pos) -> None:
        menu = QMenu(self)
        cancel_act = menu.addAction("取消运行") if entry.status == STATUS_RUNNING else None
        reveal_act = menu.addAction(T["open_in_finder"])
        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen == cancel_act:
            self.cancel_live.emit(entry)
        elif chosen == reveal_act:
            # results dir may not exist yet
            target = RESULTS / entry.ticker / entry.date
            if target.exists():
                subprocess.run(["open", "-R", str(target)], check=False)

    def _report_context_menu(self, item: QListWidgetItem, entry: ReportEntry, pos) -> None:
        menu = QMenu(self)
        open_act = menu.addAction(T["open"])
        reveal_act = menu.addAction(T["open_in_finder"])
        menu.addSeparator()
        delete_act = menu.addAction(T["delete"])
        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen == open_act:
            self.open_report.emit(entry)
        elif chosen == reveal_act:
            self._reveal(entry)
        elif chosen == delete_act:
            self._delete(entry)

    def _reveal(self, entry: ReportEntry) -> None:
        target = RESULTS / entry.ticker / entry.date
        if not target.exists():
            return
        subprocess.run(["open", "-R", str(target)], check=False)

    def _delete(self, entry: ReportEntry) -> None:
        ans = QMessageBox.question(
            self,
            T["confirm_delete"],
            f"{entry.label}\n\n{T['confirm_delete_body']}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        target = RESULTS / entry.ticker / entry.date
        try:
            shutil.rmtree(target)
        except Exception as e:
            QMessageBox.warning(self, T["run_failed"], f"删除失败: {e}")
            return
        self.refresh()

    # ------------------------------------------------------------------ signals

    cancel_live = Signal(object)  # LiveEntry
