"""QApplication entry point for the TradingAgents desktop GUI.

Self-contained build (PyInstaller): the exe runs anywhere. On first launch,
if no ``.env`` is found, the user is prompted for a MiniMax API key and the
key is persisted next to the executable so subsequent launches are silent.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

from .core.theme import apply_theme
from .main_window import MainWindow


# Key under which the MiniMax API key lives. We deliberately hardcode this
# here so the setup wizard doesn't need to know about the LLM client layer.
API_KEY_ENV = "MINIMAX_CN_API_KEY"


def _candidate_env_paths() -> list[Path]:
    """Locations to look for / write a ``.env`` file, in priority order."""
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        # PyInstaller onefile / onedir: write next to the .exe so the user
        # can find it next to the binary they double-clicked.
        paths.append(Path(sys.executable).resolve().parent / ".env")
        paths.append(Path.cwd() / ".env")
    else:
        # Development (`python -m deskapp`): the project root is the right
        # home for .env, matching the rest of the CLI / webapp expectations.
        paths.append(Path(__file__).resolve().parent.parent.parent / ".env")
        paths.append(Path.cwd() / ".env")
    return paths


def _find_existing_env() -> Path | None:
    for p in _candidate_env_paths():
        if p.exists():
            return p
    return None


def _load_env_into_process(path: Path) -> None:
    """Best-effort load ``.env`` into ``os.environ`` without overwriting
    values that the user already exported on the command line."""
    try:
        from dotenv import load_dotenv
        load_dotenv(path, override=False)
        return
    except ImportError:
        pass
    # Fallback: tiny key=value parser that handles ``#`` comments and
    # quoted values, good enough for the keys this wizard writes.
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _merge_env(env_path: Path, updates: dict[str, str]) -> None:
    """Update ``env_path`` in place, preserving any keys we don't touch."""
    merged: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            merged[key.strip()] = value
    for k, v in updates.items():
        merged[k] = v
    text = "\n".join(f"{k}={v}" for k, v in merged.items()) + "\n"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(text, encoding="utf-8")


def _ensure_api_key(app: QApplication) -> None:
    """Populate ``MINIMAX_CN_API_KEY`` from .env, or prompt the user once."""
    # 1. Try to find and load an existing .env.
    env_path = _find_existing_env()
    if env_path:
        _load_env_into_process(env_path)

    # 2. If the key is already present (from .env or a shell export), done.
    if os.environ.get(API_KEY_ENV, "").strip():
        return

    # 3. Otherwise prompt. Modality is set so the dialog survives any
    #    auto-quit behavior of the freshly-created QApplication.
    app.setQuitOnLastWindowClosed(False)
    QApplication.setQuitOnLastWindowClosed(False)

    api_key, accepted = QInputDialog.getText(
        None,
        "TradingAgents · 首次配置",
        "请输入 MiniMax API Key：\n\n"
        "申请：https://api.minimaxi.com → 控制台 → API Keys\n\n"
        "保存位置（与本 exe 同目录下的 .env）：\n"
        f"{_candidate_env_paths()[0]}",
        QLineEdit.Password,
        "",
    )
    if not accepted or not api_key.strip():
        QMessageBox.warning(
            None,
            "TradingAgents",
            "未提供 API Key，分析任务无法运行。请重新启动并填写。",
        )
        sys.exit(1)

    # 4. Persist to the highest-priority .env location and load it.
    target = _candidate_env_paths()[0]
    _merge_env(target, {API_KEY_ENV: api_key.strip()})
    os.environ[API_KEY_ENV] = api_key.strip()
    QMessageBox.information(
        None,
        "TradingAgents",
        f"API Key 已保存：\n{target}\n\n后续启动会自动读取。",
    )


def main() -> int:
    QCoreApplication.setOrganizationName("TradingAgents")
    QCoreApplication.setOrganizationDomain("tradingagents.local")
    QCoreApplication.setApplicationName("TradingAgentsDeskApp")

    app = QApplication(sys.argv)
    apply_theme(app)

    # Default Chinese-friendly font on macOS. Falls back gracefully on other OSes.
    font = QFont("PingFang SC")
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    # First-run key wizard — silent when an .env (or shell export) is present.
    _ensure_api_key(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
