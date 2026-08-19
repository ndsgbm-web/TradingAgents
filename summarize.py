"""Generate a condensed Chinese executive summary for a finished run.

Usage:
    python summarize.py results/<TICKER>/<DATE>/

Reads every ``*.md`` (and ``final_decision.json``) in the given directory,
asks the configured LLM to produce a tight Chinese summary, and writes
``<dir>/摘要.md``.

The source content may itself be in English (historical runs) or Chinese
(new runs with TRADINGAGENTS_OUTPUT_LANGUAGE=中文) — the output is always
Chinese. Length target: ~1.5 printed pages, structured so the rating, key
data, bull/bear points, action, and risks are all readable in one pass.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from pathlib import Path


PROMPT_TEMPLATE = """你是 TradingAgents 多智能体框架的首席编辑。下面是这次多智能体分析产出的全套原始报告（市场技术、基本面、新闻、舆情、研究员辩论、交易员、风控最终决策），来源 ticker 是 {ticker}，分析日期是 {date}。

请用中文产出一份**精简执行摘要**，目标读者是一位只看一页纸就能拍板的投资经理。**严格遵守以下结构**，不要写无关的客套话：

# 摘要 — {{ticker}}（{{date}}）

## 1. 最终评级与动作
- 评级（如 Buy / Hold / Sell / Overweight 等）
- 建议动作（建仓 / 加仓 / 减仓 / 清仓 / 观望）
- 目标价 / 关键价位 / 止损位（如有）
- 时间窗口

## 2. 核心数据快照
用一张 Markdown 表格列出 5-8 行最重要的数字（价格、估值倍数、营收增速、利润率、现金流、行业地位等）。只挑能直接支撑结论的字段。

## 3. 多空要点（各 3 条）
**多头逻辑**（为什么买）：
- …

**空头逻辑**（为什么卖 / 不买）：
- …

## 4. 操作建议
- 仓位（百分比 / 金额）
- 入场区间、分批策略
- 止损 / 止盈触发条件

## 5. 关键风险（最多 5 条）
- …

## 6. 需要监控的催化剂（最多 5 条）
- …

## 7. 一句话总结
不超过 60 个汉字，给出最直接的判断。

约束：
- **只输出上面的 Markdown 内容**，不要解释、不要前言。
- 如果原始报告里有冲突观点，**保留冲突并标注**谁更可靠。
- 中文输出。专业术语保留英文原文 + 中文解释。
- 总长度控制在 1200 字以内（不含表格）。

---

下面是原始报告：

{body}
"""


def _gather(results_dir: Path) -> tuple[str, str, str]:
    """Return (ticker, date, concatenated body)."""
    parts: list[str] = []
    # Decision first so it carries weight in the summary.
    decision_path = results_dir / "final_decision.json"
    if decision_path.exists():
        try:
            d = json.loads(decision_path.read_text())
            parts.append("## 决策（结构化）\n```json\n" + json.dumps(d, ensure_ascii=False, indent=2) + "\n```")
        except Exception:
            pass

    # Then per-agent reports in canonical order.
    order = [
        "market_report.md",
        "fundamentals_report.md",
        "news_report.md",
        "sentiment_report.md",
        "investment_plan.md",
        "trader_investment_plan.md",
        "final_trade_decision.md",
    ]
    for fname in order:
        path = results_dir / fname
        if path.exists():
            parts.append(f"\n## {fname}\n\n" + path.read_text(encoding="utf-8").strip())

    ticker = results_dir.parts[-2] if len(results_dir.parts) >= 2 else "?"
    date = results_dir.parts[-1] if len(results_dir.parts) >= 1 else "?"
    return ticker, date, "\n\n".join(parts)


def _call_llm(prompt: str) -> str:
    """Call M3 through the framework's Anthropic client."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.llm_clients.factory import create_llm_client

    cfg = DEFAULT_CONFIG
    client = create_llm_client(
        provider=cfg["llm_provider"],
        model=cfg["deep_think_llm"],
        base_url=cfg.get("backend_url"),
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=2048,
    )
    llm = client.get_llm()
    resp = llm.invoke([{"role": "user", "content": prompt}])
    content = resp.content
    if isinstance(content, list):
        content = "\n".join(
            (item.get("text") if isinstance(item, dict) and item.get("type") == "text" else str(item))
            for item in content
        )
    return content.strip()


def summarize(results_dir: Path, *, write: bool = True) -> str:
    results_dir = results_dir.resolve()
    if not results_dir.is_dir():
        sys.exit(f"not a directory: {results_dir}")

    ticker, date, body = _gather(results_dir)
    if not body.strip():
        sys.exit(f"no reports found in {results_dir}")

    # Trim the body so we don't blow the LLM's context. 60k chars of body is
    # plenty for an executive summary.
    MAX_BODY_CHARS = 60_000
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n\n[… content truncated for brevity …]"

    prompt = PROMPT_TEMPLATE.format(ticker=ticker, date=date, body=body)
    summary = _call_llm(prompt)

    if write:
        out = results_dir / "摘要.md"
        header = (
            f"# 摘要 — {ticker}（{date}）\n\n"
            f"_由 M3 浓缩自本目录下 7 份分报告，生成时间 {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}。_\n\n"
        )
        # If the model already emitted the heading, keep its version; otherwise prefix ours.
        if not summary.lstrip().startswith(f"# 摘要"):
            summary = header + summary
        out.write_text(summary, encoding="utf-8")
        print(f"wrote {out} ({out.stat().st_size} bytes, {len(summary)} chars)")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", help="results/<TICKER>/<DATE>/ directory")
    args = ap.parse_args()
    summarize(Path(args.dir))


if __name__ == "__main__":
    main()
