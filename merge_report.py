"""Merge the per-agent markdown reports under a results dir into one Chinese report.

Usage:
    python merge_report.py results/<TICKER>/<DATE>/
    python merge_report.py results/300812.SZ/2026-08-14-cn/

Produces ``<results_dir>/完整报告.md`` with a TOC and all sections in order.
Section headers are in Chinese regardless of the source language so the
structure stays readable; the body of each section is preserved as-is.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


# (Chinese title, English filename)
SECTIONS: list[tuple[str, str]] = [
    ("一、市场技术分析",                "market_report.md"),
    ("二、公司基本面分析",              "fundamentals_report.md"),
    ("三、新闻与事件",                  "news_report.md"),
    ("四、舆情与社交媒体情绪",          "sentiment_report.md"),
    ("五、研究团队多空辩论与投资计划",  "investment_plan.md"),
    ("六、交易员执行计划",              "trader_investment_plan.md"),
    ("七、风控与最终投资决策",          "final_trade_decision.md"),
]

META = [
    ("Ticker",         lambda d: d.parts[-2] if len(d.parts) >= 2 else ""),
    ("分析日期",       lambda d: d.parts[-1]),
    ("报告生成时间",   lambda d: dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
]


def merge(results_dir: Path) -> Path:
    results_dir = results_dir.resolve()
    if not results_dir.is_dir():
        sys.exit(f"not a directory: {results_dir}")

    # Load the structured decision if available.
    decision: str | None = None
    decision_path = results_dir / "final_decision.json"
    if decision_path.exists():
        try:
            decision = json.loads(decision_path.read_text())
            if isinstance(decision, dict):
                decision = decision.get("rating") or decision.get("decision") or json.dumps(decision, ensure_ascii=False, indent=2)
            elif not isinstance(decision, str):
                decision = str(decision)
        except Exception:
            pass

    lines: list[str] = []
    ticker = results_dir.parts[-2] if len(results_dir.parts) >= 2 else results_dir.name
    lines.append(f"# 投资分析完整报告 — {ticker}\n")
    lines.append(f"_本报告由 TradingAgents 多智能体框架自动生成，模型：MiniMax-M3（深度推理）+ MiniMax-M2.7-highspeed（快速模型），通过 MiniMax Coding Plan 端点调用。_\n")

    # Header table
    lines.append("## 基本信息\n")
    lines.append("| 项目 | 值 |")
    lines.append("|---|---|")
    for label, fn in META:
        lines.append(f"| {label} | {fn(results_dir)} |")
    if decision is not None:
        lines.append(f"| **最终评级** | **{decision}** |")
    lines.append("")

    # Table of contents
    lines.append("## 目录\n")
    for title, fname in SECTIONS:
        if (results_dir / fname).exists():
            anchor = title.lstrip("一二三四五六七八九十、")
            lines.append(f"- [{title}](#{anchor.replace(' ', '-')})")
    lines.append("")

    # Sections
    for title, fname in SECTIONS:
        path = results_dir / fname
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8").strip()
        anchor = title.lstrip("一二三四五六七八九十、").replace(" ", "-")
        lines.append(f'<a id="{anchor}"></a>')
        lines.append(f"## {title}\n")
        # Strip a leading "# Title" if present so we don't double the heading.
        if body.startswith("# "):
            body = "\n".join(body.splitlines()[1:]).lstrip()
        lines.append(body)
        lines.append("\n---\n")

    # Footer
    lines.append("## 附录：数据源\n")
    lines.append(
        "- **股票行情 / 技术指标**: 美股 → yfinance；A 股 → AkShare (Sina 前复权)\n"
        "- **基本面 / 财务三表**: 美股 → yfinance；A 股 → AkShare (Sina + 东方财富)\n"
        "- **新闻**: 美股 → yfinance news；A 股 → 东方财富 stock_news_em\n"
        "- **舆情**: StockTwits、Reddit RSS\n"
        "- **宏观**: FRED（美国）\n"
    )
    lines.append(
        "\n_本框架仅用于研究目的，不构成投资建议。Trading performance may vary based on many factors._"
    )

    out = results_dir / "完整报告.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", help="results/<TICKER>/<DATE>/ directory")
    args = ap.parse_args()
    merge(Path(args.dir))


if __name__ == "__main__":
    main()
