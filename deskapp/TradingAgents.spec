# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the self-contained TradingAgents desktop app.

Build (from the repo root):
    pyinstaller deskapp/TradingAgents.spec --noconfirm --clean

Output:
    dist/TradingAgents-full.exe      (~200-300 MB, onefile, windowed)

We resolve paths from ``os.getcwd()`` (the workflow's checkout root)
instead of ``Path(SPECPATH).parent.parent``: on the Windows
``windows-latest`` GitHub runner the workspace is the repo root itself
(D:\\a\\<repo>), so computing the repo root from SPECPATH would resolve
one directory too high. ``os.getcwd()`` is unambiguous in every case.
"""
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Repo root: where pyinstaller was invoked from.
ROOT = Path(os.getcwd()).resolve()
RES = ROOT / "deskapp" / "app_bundle" / "Resources"
ICON_ICNS = RES / "icon.icns"
ICON_ICO = RES / "icon.ico"

# Pick the icon appropriate to the host OS.
if sys.platform == "win32" and ICON_ICO.exists():
    ICON = str(ICON_ICO)
elif ICON_ICNS.exists():
    ICON = str(ICON_ICNS)
else:
    ICON = None

# Hidden imports. PyInstaller's static analysis cannot see through every
# dynamic import (akshare / langchain load endpoints via importlib). We
# pull every relevant package and every akshare sub-namespace explicitly
# so the user-visible "No module named akshare" failure does not happen.
hidden = [
    "tradingagents.dataflows._py_mini_racer_lock",
    "akshare",
    "py_mini_racer",
    "curl_cffi",
    "lxml",
    "lxml.html",
    "lxml.html.clean",
    "lxml.etree",
    "bs4",
    "requests",
    "requests_html",
    "yfinance",
    "markdown_it",
    "pygments",
    "dotenv",
    "langchain",
    "langchain_community",
    "langchain_core",
    "pandas",
    "numpy",
    "peewee",
    "tushare",
    "tradingagents",
    "tradingagents.dataflows",
    "tradingagents.graph",
    "tradingagents.llm_clients",
]
hidden += collect_submodules("tradingagents.dataflows")
hidden += collect_submodules("tradingagents.graph")
hidden += collect_submodules("tradingagents.llm_clients")
hidden += collect_submodules("akshare")
hidden += collect_submodules("akshare.air")
hidden += collect_submodules("akshare.article")
hidden += collect_submodules("akshare.bank")
hidden += collect_submodules("akshare.bond")
hidden += collect_submodules("akshare.futures")
hidden += collect_submodules("akshare.fx")
hidden += collect_submodules("akshare.fund")
hidden += collect_submodules("akshare.index")
hidden += collect_submodules("akshare.stock")
hidden += collect_submodules("akshare.coin")
hidden += collect_submodules("akshare.option")
hidden += collect_submodules("akshare.pro")
hidden += collect_submodules("py_mini_racer")
hidden += collect_submodules("curl_cffi")
hidden += collect_submodules("lxml")

# Data files (non-Python resources that must travel alongside the modules).
datas = []
if ICON_ICNS.exists():
    datas.append((str(ICON_ICNS), "app_bundle/Resources"))

# akshare ships a couple of JSON / JS resources + index files used by some
# endpoints. collect_data_files walks the package and grabs them.
try:
    datas += collect_data_files("akshare", include_py_files=False)
except Exception:
    pass
# py_mini_racer ships libmini_racer (.dylib / .dll / .so) + icudtl.dat.
# These are critical runtime files - without them mini_racer FATAL-aborts.
try:
    datas += collect_data_files("py_mini_racer", include_py_files=False)
except Exception:
    pass
# lxml has libxml2 / libxslt / libexslt shared libs.
try:
    datas += collect_data_files("lxml", include_py_files=False)
except Exception:
    pass
# curl_cffi bundles its own libcurl. PyInstaller usually catches this
# via its hook, but be explicit.
try:
    datas += collect_data_files("curl_cffi", include_py_files=False)
except Exception:
    pass

# Modules we explicitly do not need.
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
    "IPython",
    "jupyter",
    "notebook",
    "matplotlib",
    "sphinx",
    "Crypto",
    "pyOpenSSL",
]

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
