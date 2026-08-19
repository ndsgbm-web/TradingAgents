# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the self-contained TradingAgents desktop app.

Build (from the repo root):
    pyinstaller deskapp/TradingAgents.spec --noconfirm --clean

Output:
    dist/TradingAgents-full.exe      (~180-220 MB, onefile, windowed)

We resolve paths from ``os.getcwd()`` (the workflow's checkout root)
instead of ``Path(SPECPATH).parent.parent``: on the Windows
``windows-latest`` GitHub runner the workspace is the repo root itself
(D:\\a\\<repo>), so computing the repo root from SPECPATH would resolve
one directory too high. ``os.getcwd()`` is unambiguous in every case.
"""
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# Repo root: where `pyinstaller` was invoked from.
ROOT = Path(os.getcwd()).resolve()
RES = ROOT / "deskapp" / "app_bundle" / "Resources"
ICON_ICNS = RES / "icon.icns"
ICON_ICO = RES / "icon.ico"  # optional, only present on Windows builds

# Pick the icon appropriate to the host OS. PyInstaller errors if the icon
# path doesn't exist, so leave it None when neither format is present.
if sys.platform == "win32" and ICON_ICO.exists():
    ICON = str(ICON_ICO)
elif ICON_ICNS.exists():
    ICON = str(ICON_ICNS)
else:
    ICON = None

# Hidden imports: pull in every tradingagents submodule so PyInstaller's
# static analysis can't miss dynamic imports (akshare + langchain use plenty).
hidden = [
    "tradingagents.dataflows._py_mini_racer_lock",
    "py_mini_racer",
    "langchain",
    "langchain_community",
    "langchain_core",
    "akshare",
    "markdown_it",
    "pygments",
    "dotenv",
]
hidden += collect_submodules("tradingagents.dataflows")
hidden += collect_submodules("tradingagents.graph")
hidden += collect_submodules("tradingagents.llm_clients")
# Third-party packages PyInstaller's static analysis misses. akshare
# dynamically imports its many sub-endpoints; py_mini_racer ships native
# bits. Pulling them in explicitly avoids "module not found" at runtime.
hidden += collect_submodules("akshare")
hidden += collect_submodules("py_mini_racer")

# Data files: bundle the app icon so QApplication picks it up.
datas = []
if ICON_ICNS.exists():
    datas.append((str(ICON_ICNS), "app_bundle/Resources"))

# Modules we explicitly don't need. Keeping these out trims the bundle.
excludes = [
    "tkinter",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtPositioning",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
    "pandas.tests",
    "numpy.tests",
    "pytest",
]

# PyInstaller prefers forward slashes in script paths; use as_posix() so the
# path is consistent on every OS.
ENTRY = (ROOT / "deskapp" / "__main__.py").as_posix()
PATHEX = ROOT.as_posix()

a = Analysis(
    [ENTRY],
    pathex=[PATHEX],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TradingAgents-full",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                        # windowed app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
