# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the self-contained TradingAgents desktop app.

Build (from the repo root):
    pyinstaller deskapp/TradingAgents.spec --noconfirm --clean

Output:
    dist/TradingAgents-full.exe      (~200-300 MB, onefile, windowed)
"""
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(os.getcwd()).resolve()
RES = ROOT / "deskapp" / "app_bundle" / "Resources"
ICON_ICNS = RES / "icon.icns"
ICON_ICO = RES / "icon.ico"

if sys.platform == "win32" and ICON_ICO.exists():
    ICON = str(ICON_ICO)
elif ICON_ICNS.exists():
    ICON = str(ICON_ICNS)
else:
    ICON = None

# -----------------------------------------------------------------------------
# Hidden imports. PyInstaller's static analysis cannot see through every
# dynamic import. The analysis pipeline at runtime loads 80+ third-party
# top-level packages (see the audit script). Anything missed here will
# surface at runtime as "ModuleNotFoundError" - the user-visible failure
# mode this spec was rewritten to avoid.
# -----------------------------------------------------------------------------
hidden = [
    # Internal - PyInstaller's analysis often misses them.
    "tradingagents.dataflows._py_mini_racer_lock",
    # Big third-party packages that ship C extensions or dynamic imports.
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
    "langgraph",
    "langgraph_sdk",
    "langsmith",
    "langchain_text_splitters",
    "langchain_anthropic",
    "langchain_openai",
    "langchain_google_genai",
    "pandas",
    "numpy",
    "peewee",            # akshare uses peewee for some persistence
    "tushare",
    "pydantic",
    "pydantic_core",
    "annotated_types",
    "typing_inspection",
    "typing_extensions",
    "anyio",             # httpx dep
    "httpx",             # langchain dep
    "sniffio",
    "distro",
    "websockets",        # langgraph dep
    "tenacity",          # langchain retry dep
    "pyyaml",            # langchain dep
    "packaging",         # common
    "python_dateutil",
    "dateutil",
    "pytz",
    "six",
    "uuid_utils",        # langchain dep
    "multitasking",      # yfinance dep
    "platformdirs",
    "filetype",          # used by akshare / yfinance
    "html5lib",          # bs4 / requests_html dep
    "webencodings",
    "soupsieve",         # bs4 dep
    "requests_toolbelt", # yfinance / akshare dep
    "urllib3",
    "idna",
    "charset_normalizer",
    "certifi",
    "zstandard",         # optional, used by some
    "orjson",            # optional
    "ormsgpack",         # optional
    "rich",              # may be pulled in by langchain
    "click",             # may be pulled in
    "jsonpatch",
    "jsonpointer",
    "websockets",
    "tzdata",            # stdlib-adjacent
    "tenacity",
    "tradingagents",
    "tradingagents.dataflows",
    "tradingagents.graph",
    "tradingagents.llm_clients",
]
# Pull in every submodule of the heavy packages so dynamic imports work.
for pkg in [
    "tradingagents.dataflows",
    "tradingagents.graph",
    "tradingagents.llm_clients",
    "akshare",
    "akshare.air",
    "akshare.article",
    "akshare.bank",
    "akshare.bond",
    "akshare.futures",
    "akshare.fx",
    "akshare.fund",
    "akshare.index",
    "akshare.stock",
    "akshare.coin",
    "akshare.option",
    "akshare.pro",
    "akshare.datasets",
    "akshare.fortune",
    "akshare.futures_derivative",
    "akshare.other",
    "akshare.qhkc",
    "akshare.rate",
    "py_mini_racer",
    "curl_cffi",
    "lxml",
]:
    try:
        hidden += collect_submodules(pkg)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Data files (non-Python resources that must travel alongside the modules).
# -----------------------------------------------------------------------------
datas = []
if ICON_ICNS.exists():
    datas.append((str(ICON_ICNS), "app_bundle/Resources"))
for pkg in ("akshare", "py_mini_racer", "lxml", "curl_cffi", "yfinance", "bs4"):
    try:
        datas += collect_data_files(pkg, include_py_files=False)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Excludes - trim the bundle.
# -----------------------------------------------------------------------------
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
