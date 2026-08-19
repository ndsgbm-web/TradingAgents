"""Mapping from upstream stage/field names to Chinese display labels.

The webapp/runner.py emits a 'stage' event for each major output produced by
the multi-agent pipeline. The 'field' attribute corresponds to a key in the
final LangGraph state; here we map it to a Chinese display label and define
the canonical order for the progress UI.
"""
from __future__ import annotations


# Ordered: how stages should appear in the progress UI (chronological order).
STAGE_ORDER: dict[str, str] = {
    "market_report":            "市场技术分析",
    "sentiment_report":         "舆情分析",
    "news_report":              "新闻与事件",
    "fundamentals_report":      "基本面分析",
    "investment_plan":          "研究团队多空辩论",
    "trader_investment_plan":   "交易员计划",
    "risk_debate_state":        "风控辩论",
    "final_trade_decision":     "投资组合经理最终决策",
}

# postprocess step Chinese
POSTPROCESS_LABELS: dict[str, str] = {
    "merge_report": "合并多 Agent 报告",
    "summarize":    "生成中文摘要",
}


def stage_label(field: str) -> str:
    """Return the Chinese display name for a state field."""
    return STAGE_ORDER.get(field, field)


def postprocess_label(step: str) -> str:
    """Return the Chinese display name for a postprocess step."""
    return POSTPROCESS_LABELS.get(step, step)
