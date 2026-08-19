# TradingAgents 桌面 GUI

PySide6 桌面客户端，把 `TradingAgents` 多 Agent 投研框架从命令行搬到 macOS 桌面。

## 与现有 webapp 的关系

**不重复造轮子**：直接复用 `webapp/runner.py` 的 JSON-line 事件流、`webapp/search.py` 的选股搜索、 `results/<TICKER>/<DATE>/` 的报告目录。PySide6 只是外壳。

```
deskapp/
├── core/
│   ├── runner.py         QProcess 包装 webapp/runner.py → emit Qt signals
│   ├── reports.py        扫描 results/，读取 完整报告.md / 摘要.md
│   ├── stages.py         上游 8 个阶段 → 中文显示标签
│   ├── live.py           LiveEntry dataclass（正在运行的报告）
│   ├── symbol_search.py  QThread 包装 webapp.search（异步搜索）
│   └── i18n.py           UI 中文字符串表
├── widgets/
│   ├── input_panel.py    股票代码（带搜索下拉）+ 日期 + 开始/取消
│   ├── progress_panel.py 8 阶段实时进度 + 工具调用日志
│   ├── report_viewer.py  Markdown → HTML（markdown-it-py + Pygments）
│   └── history_panel.py  正在运行 + 历史报告 + 搜索 + 删除 + 访达显示
├── app_bundle/
│   ├── Info.plist        .app 元数据
│   └── MacOS/TradingAgents  薄壳启动器
├── main_window.py        主窗口布局
├── app.py                QApplication 入口
├── __main__.py           python -m deskapp
├── run_deskapp.sh        开发期启动
└── build_app.sh          构建 .app
```

## 安装

```bash
cd /Users/sbb/TradingAgents
source .venv/bin/activate
uv pip install PySide6 markdown-it-py pygments
```

（项目本体及 akshare / fastapi 等已通过 `uv pip install -e .` 装好。）

## 启动

```bash
./deskapp/run_deskapp.sh
```

或手动：

```bash
source .venv/bin/activate
python -m deskapp
```

## 使用流程

1. **输入股票**：直接输入代码（如 `NVDA` / `600519.SH`），或输入中文名（如 `特斯拉` / `茅台`）触发下拉搜索
2. **选日期** + **点击开始分析**
3. **左侧栏实时显示** 进行中的运行（"⏳ 正在运行"区域），显示当前所处的 Agent 阶段和已用时间
4. **下方进度面板** 同步显示 8 个阶段的状态切换
5. **完成后**：报告自动渲染在右侧（Markdown + 代码高亮）
6. **左侧栏"历史报告"** 列出所有历史报告，可搜索 / 删除 / 在访达中显示

## .app 打包

构建薄壳启动器（推荐，5KB，依赖现有 venv）：

```bash
./deskapp/build_app.sh
# 输出：dist/TradingAgents.app
open dist/TradingAgents.app
```

构建自包含 .app（不依赖 venv，约 80MB）：

```bash
PY2APP=1 ./deskapp/build_app.sh
```

薄壳启动器工作原理：
- 双击 .app → `Contents/MacOS/TradingAgents` 启动器执行
- 启动器找到 `~/TradingAgents/.venv/bin/python`
- `exec` 切到 venv 的 Python 进程 → `python -m deskapp`
- 窗口由 venv 进程创建；PID 不变，dock 图标 / 菜单栏继承 .app 上下文

## 已知限制

- **内部 Agent 辩论仍为英文**。最终报告翻译为中文（进度面板顶部有徽章提示）。
- **akshare 首次加载慢**：选中股搜索如果输入中文，第一次会加载 5000+ A 股名单（10-30 秒），之后缓存命中。
- **薄壳 .app 依赖 venv**：必须先在 `~/TradingAgents` 完成安装步骤。如果换位置，设 `export TRADINGAGENTS_DIR=/path/to/TradingAgents`。

## 故障排查

- **窗口空白 / 中文方框**：通常字体问题。`app.py` 已设置 `PingFang SC`。
- **.app 双击没反应**：终端执行 `dist/TradingAgents.app/Contents/MacOS/TradingAgents` 看报错。
- **子进程无输出**：检查 `.env` 中 LLM API key 是否设置。
- **"QThread: Destroyed while thread is still running"**：仅在退出 GUI 时出现，无害。搜索仍在后台时关闭窗口会有这个 warning。
