"""py2app config for the self-contained TradingAgents .app bundle.

Build:
    PY2APP=1 ./deskapp/build_app.sh

This is an alternative to the thin launcher; it bundles PySide6 + the
deskapp + the webapp + TradingAgents into a single .app (~80MB). The
trade-off is that the .env file must be re-created or copied into the
bundle for the LLM keys to work.
"""
from __future__ import annotations

from setuptools import setup

APP = ["deskapp/app.py"]
APP_NAME = "TradingAgents"

OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtWidgets",
        "PySide6.QtGui",
        "markdown_it",
        "markdown_it.extensions",
        "pygments",
        "pygments.lexers",
        "pygments.formatters",
        "deskapp",
        "deskapp.core",
        "deskapp.widgets",
        "webapp",
    ],
    "includes": [
        "PySide6.QtCore",
        "PySide6.QtWidgets",
        "PySide6.QtGui",
        "markdown_it",
        "pygments",
    ],
    "excludes": [
        "tkinter",
        "unittest",
        "pydoc_data",
    ],
    "plist": {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "com.local.tradingagents.desktop",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSSupportsAutomaticGraphicsSwitching": True,
    },
    "site_packages": True,
}

setup(
    app=APP,
    name=APP_NAME,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
