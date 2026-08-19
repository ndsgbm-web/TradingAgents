"""Markdown → HTML renderer using markdown-it-py + Pygments.

Uses Qt's native ``QTextBrowser`` (no extra QtWebEngine dependency) with
hand-rolled CSS for clean Chinese rendering on macOS.
"""
from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.i18n import T


_CSS = """
<style>
  body {{
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
    font-size: 14px; line-height: 1.7;
    padding: 28px 36px; color: #0F172A; background: #FFFFFF;
    max-width: 920px; margin: 0 auto;
  }}
  h1, h2, h3, h4 {{ color: #1b1f27; margin-top: 1.4em; line-height: 1.3; }}
  h1 {{ border-bottom: 2px solid #e2e5ea; padding-bottom: 8px; font-size: 22px; }}
  h2 {{ border-bottom: 1px solid #e2e5ea; padding-bottom: 4px; font-size: 18px; }}
  h3 {{ font-size: 15px; }}
  p {{ margin: 0.6em 0; }}
  code {{
    background: #f3f4f6; padding: 2px 6px; border-radius: 4px;
    font-size: 13px; font-family: "SF Mono", Menlo, "Cascadia Code", monospace;
  }}
  pre {{
    background: #0d1117; color: #c9d1d9;
    padding: 14px 16px; border-radius: 6px; overflow-x: auto;
    font-size: 12.5px; line-height: 1.5;
  }}
  pre code {{ background: transparent; color: inherit; padding: 0; font-size: inherit; }}
  table {{ border-collapse: collapse; margin: 12px 0; width: 100%; }}
  th, td {{ border: 1px solid #e2e5ea; padding: 6px 12px; text-align: left; }}
  th {{ background: #f3f4f6; font-weight: 600; }}
  blockquote {{
    border-left: 4px solid #2563eb; padding: 6px 14px; color: #4b5563;
    margin: 8px 0; background: #f9fafb; border-radius: 0 4px 4px 0;
  }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  hr {{ border: none; border-top: 1px solid #e2e5ea; margin: 24px 0; }}
  ul, ol {{ padding-left: 22px; }}
  li {{ margin: 2px 0; }}
  strong {{ font-weight: 600; }}
  em {{ color: #4b5563; }}
</style>
"""


def render_markdown(text: str) -> str:
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
    md.enable("table")
    md.enable("strikethrough")

    def _highlight(code: str, lang: str, _attrs: str) -> str:
        try:
            lexer = get_lexer_by_name(lang) if lang else guess_lexer(code)
        except Exception:
            lexer = None
        if lexer is None:
            return f"<pre><code>{md.utils.escape_html(code)}</code></pre>"
        formatter = HtmlFormatter(style="github-dark", noclasses=True)
        return highlight(code, lexer, formatter)

    md.add_render_rule("fence", _highlight)
    body = md.render(text)
    return f"<html><head><meta charset=\"utf-8\">{_CSS}</head><body>{body}</body></html>"


class ReportViewer(QWidget):
    """Render a chosen report (完整报告 / 摘要 / 子报告) as HTML."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._files: dict[str, Path] = {}
        self._build()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        title = QLabel(T["report_title"])
        title.setProperty("role", "title")
        toolbar.addWidget(title)
        toolbar.addStretch(1)

        self.selector = QComboBox()
        self.selector.setMinimumWidth(200)
        self.selector.currentIndexChanged.connect(self._reload)
        toolbar.addWidget(self.selector)

        copy_btn = QPushButton(T["copy"])
        copy_btn.setProperty("role", "secondary")
        copy_btn.clicked.connect(self._copy)
        toolbar.addWidget(copy_btn)

        export_btn = QPushButton(T["export"])
        export_btn.setProperty("role", "secondary")
        export_btn.clicked.connect(self._export)
        toolbar.addWidget(export_btn)

        word_btn = QPushButton(T["export_word"])
        word_btn.setProperty("role", "secondary")
        word_btn.clicked.connect(self._export_word)
        toolbar.addWidget(word_btn)

        layout.addLayout(toolbar)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setObjectName("Report")
        layout.addWidget(self.browser, stretch=1)

        self._show_placeholder()

    # ------------------------------------------------------------------ public

    def load_files(self, files: dict[str, Path], prefer: str | None = None) -> None:
        """Load a set of files. ``prefer`` selects the initial dropdown item."""
        self._files = files
        self.selector.blockSignals(True)
        self.selector.clear()
        for label, path in files.items():
            self.selector.addItem(label, path)
        idx = 0
        if prefer:
            for i in range(self.selector.count()):
                if self.selector.itemText(i) == prefer:
                    idx = i
                    break
        self.selector.setCurrentIndex(idx)
        self.selector.blockSignals(False)
        self._reload()

    def _show_placeholder(self) -> None:
        self.browser.setHtml(
            f'<html><body style="font-family: -apple-system, PingFang SC, sans-serif;'
            f' padding: 32px; color: #6b7280;">{T["ready"]}</body></html>'
        )

    # ------------------------------------------------------------------ slots

    def _reload(self) -> None:
        path = self.selector.currentData()
        if not path:
            self._show_placeholder()
            return
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            self.browser.setHtml(
                f"<html><body style=\"padding:32px;color:#dc2626;\">"
                f"读取失败: {e}</body></html>"
            )
            return
        self.browser.setHtml(render_markdown(text))

    def _copy(self) -> None:
        path = self.selector.currentData()
        if not path:
            return
        try:
            QApplication.clipboard().setText(path.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.warning(self, T["load_failed"], f"复制失败: {e}")

    def _export(self) -> None:
        path = self.selector.currentData()
        if not path:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, T["export"], path.stem + ".html", "HTML (*.html)"
        )
        if not out:
            return
        try:
            Path(out).write_text(self.browser.toHtml(), encoding="utf-8")
            QMessageBox.information(self, T["saved"], Path(out).name)
        except Exception as e:
            QMessageBox.warning(self, T["load_failed"], f"导出失败: {e}")

    # --- pandoc discovery --------------------------------------------------

    def _find_pandoc(self) -> str | None:
        """Locate the pandoc executable.

        ``shutil.which`` honours ``$PATH``, but a process launched by
        double-clicking the .app bundle (macOS) or the .exe (Windows)
        inherits a *minimal* environment that doesn't include Homebrew,
        WindowsApps, or system /usr/local/bin. After the cheap PATH probe
        we therefore also check the platform-specific install paths that
        the respective installers actually drop pandoc into.
        """
        import shutil, sys
        from pathlib import Path
        found = shutil.which("pandoc")
        if found:
            return found
        extra: list[Path] = []
        home = Path.home()
        if sys.platform == "darwin":
            extra += [
                Path("/opt/homebrew/bin/pandoc"),
                Path("/usr/local/bin/pandoc"),
                Path("/opt/local/bin/pandoc"),
                home / ".local/bin/pandoc",
            ]
        elif sys.platform == "win32":
            bases = [
                Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
                Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
                Path(os.environ.get("LocalAppData", str(home / "AppData/Local"))),
            ]
            for base in bases:
                extra += [
                    base / "Pandoc" / "pandoc.exe",
                    base / "Microsoft" / "WindowsApps" / "pandoc.exe",
                    base / "chocolatey" / "bin" / "pandoc.exe",
                ]
            extra.append(home / "scoop" / "shims" / "pandoc.exe")
        else:
            extra += [
                Path("/usr/bin/pandoc"),
                Path("/usr/local/bin/pandoc"),
                home / ".local/bin/pandoc",
            ]
        for p in extra:
            if p.exists():
                return str(p)
        return None

    def _export_word(self) -> None:
        """Convert the current markdown report to .docx via pandoc.

        Pandoc handles Chinese text, headings, tables, and code blocks
        cleanly. If pandoc is missing, surface a clear install hint
        instead of failing silently.
        """
        path = self.selector.currentData()
        if not path:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, T["export_word"], path.stem + ".docx", "Word 文档 (*.docx)"
        )
        if not out:
            return
        try:
            import subprocess
            pandoc = self._find_pandoc()
            if not pandoc:
                raise RuntimeError(
                    "未检测到 pandoc，请先安装："
                    "macOS `brew install pandoc`，"
                    "Windows `winget install JohnMacFarlane.Pandoc`，"
                    "Linux `sudo apt install pandoc`"
                )
            proc = subprocess.run(
                [pandoc, str(path), "-o", out,
                 "--to=docx", "--wrap=preserve"],
                capture_output=True, text=True, check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    proc.stderr.strip() or proc.stdout.strip() or "pandoc 退出非零"
                )
            QMessageBox.information(self, T["saved"], Path(out).name)
        except Exception as e:
            QMessageBox.warning(self, T["load_failed"], f"Word 导出失败: {e}")
