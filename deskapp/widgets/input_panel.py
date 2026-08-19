"""Input form: stock code + analysis date + run/cancel buttons.

The ticker field is a QComboBox in editable mode so users can:
- type a ticker directly (e.g. ``NVDA``)
- type a Chinese name (e.g. ``特斯拉``) and pick from the dropdown
- search results are fetched asynchronously via ``webapp.search``
"""
from __future__ import annotations

from PySide6.QtCore import QDate, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ..core.i18n import T
from ..core.symbol_search import search_async
from ..core.ticker_utils import infer_a_share_exchange, normalize_ticker


_DEBOUNCE_MS = 250
_SEARCH_LIMIT = 8


class InputPanel(QWidget):
    """Emit ``run_requested(ticker, date)`` when the user clicks Run."""

    run_requested = Signal(str, str)     # (ticker, date)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._suppress_search = False
        # Tracks the symbol the user *explicitly* selected from the dropdown.
        # Set by `activated` (clicking / arrow-keys + Enter). Cleared by any
        # text edit. When empty, we use `currentText()` instead so that
        # typing a code that isn't in the dropdown (or that hasn't been
        # returned yet by search) goes through verbatim.
        self._picked_symbol: str = ""
        self._build()
        self._wire()
        self._update_button_state()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignLeft)

        # Ticker as editable QComboBox so the dropdown can host search hits
        self.ticker_combo = QComboBox()
        self.ticker_combo.setEditable(True)
        self.ticker_combo.setInsertPolicy(QComboBox.NoInsert)
        self.ticker_combo.lineEdit().setPlaceholderText(T["ticker_hint"])
        self.ticker_combo.setMinimumWidth(360)
        layout.addRow(T["ticker"], self.ticker_combo)

        # Live hint: shows the normalized ticker + inferred exchange so the
        # user can see what will actually be analyzed (e.g. "→ 002335.SZ
        # (深交所)" when they type a bare "002335").
        self.ticker_hint = QLabel("")
        self.ticker_hint.setProperty("role", "hint")
        self.ticker_hint.setWordWrap(True)
        layout.addRow("", self.ticker_hint)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate().addDays(-1))
        self.date_edit.setMaximumDate(QDate.currentDate())
        layout.addRow(T["date"], self.date_edit)

        # Buttons
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton(T["submit"])
        self.run_btn.setMinimumWidth(140)
        self.cancel_btn = QPushButton(T["cancel"])
        self.cancel_btn.setProperty("role", "secondary")
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)
        layout.addRow(btn_row)

        # Debounce timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._fire_search)

    def _wire(self) -> None:
        self.ticker_combo.lineEdit().textChanged.connect(self._on_text_changed)
        # pressing Enter inside the combobox should fire Run
        self.ticker_combo.lineEdit().returnPressed.connect(self._on_run)
        self.run_btn.clicked.connect(self._on_run)
        self.cancel_btn.clicked.connect(self.cancel_requested)
        # `activated` fires only when the user explicitly picks an item
        # (mouse click or arrow + Enter). Pure typing does NOT trigger it,
        # which is exactly what we want to disambiguate.
        self.ticker_combo.activated.connect(self._on_item_activated)

    # ------------------------------------------------------------------ search

    def _on_text_changed(self, text: str) -> None:
        # Any typing invalidates the previously-picked symbol; the user is
        # now editing, not confirming a dropdown selection.
        self._picked_symbol = ""
        self._update_hint(text)
        self._update_button_state()
        if self._suppress_search:
            return
        text = text.strip()
        if len(text) < 1:
            return
        self._search_timer.start()

    def _fire_search(self) -> None:
        query = self.ticker_combo.currentText().strip()
        if not query:
            return
        search_async(
            query,
            limit=_SEARCH_LIMIT,
            on_results=self._on_search_results,
            on_error=self._on_search_error,
        )

    def _on_search_results(self, hits: list[dict]) -> None:
        # Don't clobber a user typing if results come back slowly
        current = self.ticker_combo.currentText().strip()
        if self.ticker_combo.lineEdit().hasFocus() and current and not hits:
            return
        self._suppress_search = True
        try:
            self.ticker_combo.blockSignals(True)
            self.ticker_combo.clear()
            for hit in hits:
                display = f"{hit.get('symbol','')}  ·  {hit.get('name','')}  [{hit.get('market','')}]"
                self.ticker_combo.addItem(display, hit.get("symbol", ""))
            # restore current text
            self.ticker_combo.setCurrentText(current if current else "")
            self.ticker_combo.blockSignals(False)
        finally:
            self._suppress_search = False

    def _on_item_activated(self, index: int) -> None:
        """User explicitly picked a dropdown item — record its symbol."""
        if 0 <= index < self.ticker_combo.count():
            data = self.ticker_combo.itemData(index)
            if isinstance(data, str) and data.strip():
                self._picked_symbol = data.strip()
                # Reflect the normalized form (which may add .SH/.SZ/.BJ)
                # back into the editable text so the user sees exactly what
                # will be sent downstream.
                self._update_hint(data)

    def _on_search_error(self, msg: str) -> None:
        # Silent: search is best-effort
        pass

    def _update_hint(self, raw_text: str) -> None:
        """Refresh the suffix-inference hint under the ticker field."""
        text = (raw_text or "").strip()
        if not text:
            self.ticker_hint.setText("")
            return
        canonical, exchange = normalize_ticker(text)
        if not exchange or canonical == text:
            # No inference (already suffixed, or non-Code input) → nothing
            # useful to show. Don't add visual noise.
            self.ticker_hint.setText("")
            return
        self.ticker_hint.setText(
            T["ticker_normalized"].format(exchange=exchange, ticker=canonical)
        )

    # ------------------------------------------------------------------ slots

    def _on_run(self) -> None:
        # Use the explicit pick if the user chose from the dropdown;
        # otherwise fall back to whatever they typed verbatim.
        if self._picked_symbol:
            raw = self._picked_symbol
        else:
            raw = self.ticker_combo.currentText().strip()
        if not raw:
            return
        # Auto-suffix bare A-share codes so 002335 → 002335.SZ, 600519 →
        # 600519.SH. Already-suffixed codes and non-numeric tickers pass
        # through untouched. This guards against the silent misrouting we
        # used to see when a 6-digit prefix matched the wrong instrument.
        ticker, exchange = normalize_ticker(raw)
        if exchange:
            self.ticker_hint.setText(
                T["ticker_normalized"].format(exchange=exchange, ticker=ticker)
            )
        date = self.date_edit.date().toString("yyyy-MM-dd")
        self.run_requested.emit(ticker, date)
        # Reset for the next run
        self._picked_symbol = ""

    def _update_button_state(self) -> None:
        if self._running:
            self.run_btn.setEnabled(False)
        else:
            has_text = bool(self.ticker_combo.currentText().strip())
            self.run_btn.setEnabled(has_text)

    # ------------------------------------------------------------------ public

    def set_running(self, running: bool) -> None:
        self._running = running
        self.ticker_combo.setEnabled(not running)
        self.date_edit.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self._update_button_state()
from PySide6.QtCore import Qt as _Qt
Qt = _Qt  # re-export so widget code can use ``Qt.AlignLeft`` etc.
