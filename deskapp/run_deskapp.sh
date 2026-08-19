#!/bin/zsh
# TradingAgents 桌面 GUI 启动脚本
# Usage: ./deskapp/run_deskapp.sh

set -e
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
    echo "✘ .venv 不存在，请先在项目根目录执行：uv venv && uv pip install -e . && uv pip install PySide6 markdown-it-py pygments" >&2
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "▶ 启动 TradingAgents 桌面 GUI"
exec python -m deskapp
