"""UI strings for Chinese mode. Reference every label from here so swapping
to a second language later is a one-file change.

Conventions:
- ``T["key"]`` returns the Chinese string for the key.
- Keys are grouped by panel; comment them when adding new ones.
"""

T: dict[str, str] = {
    "app_title":  "TradingAgents · 中文投研面板",

    # input panel
    "ticker":            "股票代码",
    "ticker_hint":       "如 NVDA / TSLA / 600519.SH / 300812.SZ",
    "ticker_normalized": "→ 将按 {exchange} 路由：{ticker}",
    "date":              "分析日期",
    "submit":            "开始分析",
    "cancel":            "取消",
    "running":           "分析进行中…",

    # progress panel
    "progress_title": "实时进度",
    "stages":         "分析阶段",
    "tool_calls":     "运行日志",
    "internal_note":  "💡 内部 Agent 辩论为英文以保证推理质量，最终报告翻译为中文。",
    "post_process":   "后处理",
    "ready":          "就绪",
    "starting":       "启动分析…",
    "run_complete":   "分析完成",
    "run_failed":     "分析失败",
    "load_failed":    "加载失败",

    # report viewer
    "report_title":   "分析报告",
    "full_report":    "完整报告",
    "summary":        "摘要",
    "copy":           "复制",
    "export":         "导出…",
    "saved":          "已保存",
    "export_word":     "导出 Word…",

    # history panel
    "history_title":      "历史报告",
    "search_history":     "搜索代码…",
    "open":               "打开",
    "delete":             "删除",
    "confirm_delete":     "确认删除？",
    "confirm_delete_body": "将永久删除此报告及其所有子报告，且不可恢复。",
    "open_in_finder":     "在访达中显示",
    "no_history":         "尚无历史报告",
    "refresh":            "刷新",
}
