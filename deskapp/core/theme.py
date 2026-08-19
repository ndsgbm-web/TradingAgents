"""Design system for the TradingAgents deskapp.

Light theme + single amber accent (#F59E0B). Restrained borders and shadows;
information hierarchy carried by type weight + tracking-tight, not color
stacking. Single source of truth for every color the deskapp renders.
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

# --- Tokens ------------------------------------------------------------------

P = {
    # Surface
    "bg":          "#F7F8FA",
    "panel":       "#FFFFFF",
    "panel_alt":   "#FAFAF9",
    "line":        "#E2E5EA",
    "line_soft":   "#EEF0F3",

    # Ink (gray scale, darkest = primary text)
    "ink":         "#0F172A",   # slate-900
    "ink_2":       "#334155",   # slate-700
    "muted":       "#64748B",   # slate-500
    "muted_2":     "#94A3B8",   # slate-400
    "placeholder": "#94A3B8",

    # Single accent (amber)
    "accent":      "#F59E0B",   # amber-500
    "accent_2":    "#FBBF24",   # amber-400 (hover)
    "accent_3":    "#D97706",   # amber-600 (active)
    "accent_soft": "#FEF3C7",   # amber-100 (chip bg)
    "accent_ink":  "#FFFFFF",

    # Semantic (used sparingly: only for buy/sell/hold)
    "up":          "#DC2626",   # 红涨 (CN convention)
    "down":        "#059669",   # 绿跌 (CN convention)
    "neutral":     "#64748B",

    # Code / log surfaces
    "code_bg":     "#0D1117",
    "code_fg":     "#C9D1D9",
}


# --- QSS ---------------------------------------------------------------------

_QSS = f"""
QWidget {{
    background: {P['bg']};
    color: {P['ink']};
    font-family: -apple-system, "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}}

/* Cards / panels */
QFrame#Card,
QWidget#Card {{
    background: {P['panel']};
    border: 1px solid {P['line']};
    border-radius: 12px;
}}

/* Section title (used in panels) */
QLabel[role="section"] {{
    color: {P['muted']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding: 0 2px;
}}

QLabel[role="title"] {{
    color: {P['ink']};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.1px;
}}

QLabel[role="subtitle"] {{
    color: {P['muted']};
    font-size: 12px;
}}

QLabel[role="metric"] {{
    color: {P['ink']};
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.4px;
}}

/* Inputs */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
    background: {P['panel']};
    border: 1px solid {P['line']};
    border-radius: 8px;
    padding: 7px 10px;
    color: {P['ink']};
    selection-background-color: {P['accent']};
    selection-color: {P['accent_ink']};
    min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
    border: 1px solid {P['accent']};
}}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
    background: {P['panel_alt']};
    color: {P['muted_2']};
}}
QLineEdit[role="search"] {{
    border-radius: 999px;
    padding-left: 14px;
    padding-right: 14px;
}}

/* Combo dropdown list */
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {P['panel']};
    border: 1px solid {P['line']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {P['accent_soft']};
    selection-color: {P['ink']};
    outline: 0;
}}

/* Buttons */
QPushButton {{
    background: {P['accent']};
    color: {P['accent_ink']};
    border: 0;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
    letter-spacing: -0.1px;
}}
QPushButton:hover  {{ background: {P['accent_2']}; }}
QPushButton:pressed{{ background: {P['accent_3']}; }}
QPushButton:disabled {{
    background: {P['line_soft']};
    color: {P['muted_2']};
}}

QPushButton[role="secondary"] {{
    background: transparent;
    color: {P['ink_2']};
    border: 1px solid {P['line']};
}}
QPushButton[role="secondary"]:hover  {{ background: {P['panel_alt']}; }}
QPushButton[role="secondary"]:pressed{{ background: {P['line_soft']}; }}

QPushButton[role="ghost"] {{
    background: transparent;
    color: {P['muted']};
    padding: 6px 10px;
}}
QPushButton[role="ghost"]:hover {{ color: {P['ink']}; background: {P['line_soft']}; }}

/* Lists (history) */
QListWidget {{
    background: transparent;
    border: none;
    outline: 0;
    padding: 2px 0;
}}
QListWidget::item {{
    background: {P['panel']};
    border: 1px solid {P['line']};
    border-radius: 10px;
    padding: 10px 12px;
    margin: 4px 0;
}}
QListWidget::item:hover {{ border-color: {P['accent']}; }}
QListWidget::item:selected {{
    background: {P['accent_soft']};
    border-color: {P['accent']};
    color: {P['ink']};
}}
QListWidget::item[role="section"] {{
    background: transparent;
    border: 0;
    color: {P['muted']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding: 8px 12px 2px;
    margin: 4px 0 0;
}}
QListWidget::item[role="placeholder"] {{
    background: transparent;
    border: 1px dashed {P['line']};
    color: {P['muted']};
    padding: 14px;
}}

/* Progress stepper */
QListWidget#Stepper::item {{
    background: transparent;
    border: 0;
    padding: 4px 4px;
    margin: 0;
}}
QListWidget#Stepper::item:hover {{ background: transparent; border: 0; }}
QListWidget#Stepper::item:selected {{ background: transparent; border: 0; color: inherit; }}

/* Splitter handles */
QSplitter::handle {{
    background: {P['bg']};
}}
QSplitter::handle:horizontal {{ width: 8px; }}
QSplitter::handle:vertical   {{ height: 8px; }}
QSplitter::handle:hover {{ background: {P['line_soft']}; }}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {P['line']}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {P['muted_2']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {P['line']}; border-radius: 5px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {P['muted_2']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* Status bar */
QStatusBar {{
    background: {P['panel']};
    color: {P['muted']};
    border-top: 1px solid {P['line_soft']};
    padding: 4px 12px;
    font-size: 12px;
}}

/* Markdown report */
QTextBrowser#Report {{
    background: {P['panel']};
    border: 1px solid {P['line']};
    border-radius: 12px;
    padding: 4px;
}}

/* Note banner */
QLabel[role="note"] {{
    background: {P['accent_soft']};
    color: {P['ink_2']};
    border: 1px solid {P['accent']};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}}

/* Hint label */
QLabel[role="hint"] {{
    color: {P['muted']};
    font-size: 11px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Install the deskapp stylesheet on the given ``QApplication``."""
    app.setStyleSheet(_QSS)
