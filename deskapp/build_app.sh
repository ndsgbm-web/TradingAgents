#!/bin/bash
# Build the TradingAgents macOS .app bundle.
#
# Default mode: assemble a thin launcher .app that delegates to the existing
# venv at ~/TradingAgents/.venv. The .app is small (~5KB) and reuses the
# current setup (deps, .env, results/, webapp/).
#
# Alt mode (PY2APP=1): build a self-contained py2app bundle. This bundles
# PySide6 + TradingAgents + webapp into a single .app (~80MB). Use this
# if you want to drag the .app to another Mac without setting up the venv.
#
# Usage:
#   ./deskapp/build_app.sh           # thin launcher
#   PY2APP=1 ./deskapp/build_app.sh  # full self-contained bundle

set -e

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
APP_NAME="TradingAgents"
DIST="$ROOT/dist"
APP="$DIST/$APP_NAME.app"

echo "▶ Building $APP_NAME.app"
echo "  mode: ${PY2APP:=thin}"
echo "  source: $ROOT"

# Ensure venv is present (needed for both modes)
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    echo "✘ .venv not found. Please run: uv venv && uv pip install -e . && uv pip install PySide6 markdown-it-py pygments" >&2
    exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Always copy Info.plist
cp "$ROOT/deskapp/app_bundle/Info.plist" "$APP/Contents/Info.plist"

if [[ "${PY2APP:-}" == "1" ]]; then
    # ─── Self-contained py2app build ───
    source "$ROOT/.venv/bin/activate"
    uv pip install --quiet py2app 2>/dev/null || pip install --quiet py2app
    echo "▶ Running py2app (this may take a minute)..."
    cd "$ROOT"
    python setup.py py2app 2>&1 | tail -5
    echo "✓ Built self-contained $APP"
else
    # ─── Thin launcher .app ───
    cp "$ROOT/deskapp/app_bundle/MacOS/TradingAgents" "$APP/Contents/MacOS/TradingAgents"
    chmod +x "$APP/Contents/MacOS/TradingAgents"

    # Copy the icon (if it has been generated)
    if [[ -f "$ROOT/deskapp/app_bundle/Resources/icon.icns" ]]; then
        cp "$ROOT/deskapp/app_bundle/Resources/icon.icns" "$APP/Contents/Resources/icon.icns"
        echo "  ✓ Icon: $APP/Contents/Resources/icon.icns"
    else
        echo "  ⚠ No icon.icns found; run: python deskapp/tools/generate_icon.py"
    fi

    # Optionally copy a README into Resources (Finder shows it as a doc)
    cat > "$APP/Contents/Resources/README.txt" <<'EOF'
TradingAgents 桌面 GUI
========================

This .app is a thin launcher that activates the existing Python venv at
~/TradingAgents/.venv and runs `python -m deskapp`.

Setup (one-time):
    cd ~/TradingAgents
    uv venv
    uv pip install -e .
    uv pip install PySide6 markdown-it-py pygments

If your repo is in a different location, set:
    export TRADINGAGENTS_DIR=/path/to/TradingAgents

For self-contained .app (no venv needed), rebuild with:
    PY2APP=1 ./deskapp/build_app.sh

Or from the command line:
    source ~/TradingAgents/.venv/bin/activate
    python -m deskapp
EOF

    echo "✓ Built thin launcher $APP"
fi

echo
echo "To install:"
echo "  cp -R \"$APP\" /Applications/"
echo "  open \"$APP\""
echo
echo "Or just double-click in Finder."
