# TradingAgents 本地部署与使用说明

> 项目：[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)（v0.3.1）
> 本机部署位置：`~/TradingAgents`
> 本文档基于本次实际部署验证后撰写。

TradingAgents 是一个多智能体（Multi-Agent）LLM 金融交易研究框架。它通过基本面、舆情、新闻、技术四类分析师团队 + 多空研究员 + 交易员 + 风控 + 投资组合经理来共同评估一支股票。框架本身**仅用于研究，不构成投资建议**。

---

## 1. 环境要求

- Python **3.10+**（官方 Docker 与本机部署均使用 3.12；3.14 因依赖兼容性问题建议暂避）
- macOS / Linux / WSL；Windows 直接运行交互 CLI 需在真实终端（Windows Terminal / PowerShell / cmd.exe）中执行
- 网络可访问所选 LLM 提供商的 API，以及 Yahoo Finance（`yfinance`）

依赖已通过 `uv` 在 `~/TradingAgents/.venv` 中完成安装，CLI 入口 `tradingagents` 可直接调用。

---

## 2. 安装步骤（已执行）

```bash
# 克隆
git clone https://github.com/TauricResearch/TradingAgents.git ~/TradingAgents
cd ~/TradingAgents

# 用 uv 建一个 3.12 虚拟环境
uv venv --python 3.12 .venv

# 以可编辑模式安装项目本体与所有依赖
uv pip install --python .venv/bin/python -e .
```

若用 `pip` 替代：
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> 可选：`pip install ".[bedrock]"` 可额外获得 AWS Bedrock 支持。

---

## 3. 配置 API Key（必须）

复制示例配置：
```bash
cd ~/TradingAgents
cp .env.example .env
```

打开 `.env`，**至少填一项 LLM 供应商的 Key**，以及（推荐）Alpha Vantage Key：

| 变量 | 用途 | 申请 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI（GPT-5.x 默认） | <https://platform.openai.com/api-keys> |
| `GOOGLE_API_KEY` | Google Gemini | Google AI Studio |
| `ANTHROPIC_API_KEY` | Anthropic Claude | Anthropic Console |
| `XAI_API_KEY` | xAI Grok | x.ai |
| `DEEPSEEK_API_KEY` | DeepSeek | DeepSeek Platform |
| `DASHSCOPE_API_KEY` / `DASHSCOPE_CN_API_KEY` | Qwen（国际 / 中国） | 阿里云百炼 |
| `ZHIPU_API_KEY` / `ZHIPU_CN_API_KEY` | GLM（智谱 / Z.AI） | 智谱 BigModel |
| `MINIMAX_API_KEY` / `MINIMAX_CN_API_KEY` | MiniMax（国际 / 中国） | MiniMax |
| `OPENROUTER_API_KEY` | OpenRouter 聚合 | OpenRouter |
| `GROQ_API_KEY` / `NVIDIA_API_KEY` / `MOONSHOT_API_KEY` / `MISTRAL_API_KEY` | 各自官网 | — |
| `ALPHA_VANTAGE_API_KEY` | 财务/估值数据（推荐） | <https://www.alphavantage.co/support/#api-key> |
| `FRED_API_KEY` | 宏观数据（可选） | FRED API |

最小可用配置示例（仅用 OpenAI + Alpha Vantage）：
```ini
OPENAI_API_KEY=sk-...
ALPHA_VANTAGE_API_KEY=...
TRADINGAGENTS_LLM_PROVIDER=openai
TRADINGAGENTS_DEEP_THINK_LLM=gpt-5.5
TRADINGAGENTS_QUICK_THINK_LLM=gpt-5.4-mini
```

> 不填 Key 启动 CLI 后也会交互式提示，但提前在 `.env` 写好可直接跳过对应问题。

### 3.1 可选：本地 Ollama（免 Key）

```bash
# 1. 装 Ollama 并拉模型
ollama pull qwen2.5:7b
# 2. 在 .env 里指定
TRADINGAGENTS_LLM_PROVIDER=ollama
# 远程 Ollama 用： OLLAMA_BASE_URL=http://your-host:11434/v1
```

### 3.2 可选：任意 OpenAI 兼容服务（vLLM / LM Studio / llama.cpp）

```ini
TRADINGAGENTS_LLM_PROVIDER=openai_compatible
TRADINGAGENTS_LLM_BACKEND_URL=http://localhost:8000/v1
TRADINGAGENTS_DEEP_THINK_LLM=your-model
TRADINGAGENTS_QUICK_THINK_LLM=your-model
```

---

## 4. 运行交互式 CLI

```bash
cd ~/TradingAgents
source .venv/bin/activate
tradingagents          # 或: python -m cli.main
```

执行后会出现 questionary 风格的交互面板，按提示选择：

1. **股票代码**（参见第 6 节）
2. **分析日期**（历史回看）
3. **LLM 提供商**
4. **深度思考模型 / 快速思考模型**
5. **研究员辩论轮数**（默认 1，可调到 2-3）
6. **风控讨论轮数**（默认 1）
7. **输出语言**（English / 中文 / ...）

确定后进入 rich Live 界面，左侧跑消息流，右侧实时显示各团队产出（Market / Sentiment / News / Fundamentals → Bull/Bear 辩论 → Trader → Risk → Portfolio Manager）。

常用可选参数：

```bash
tradingagents --checkpoint              # 开启断点续跑（崩溃后从上一个节点接着跑）
tradingagents --no-checkpoint           # 关闭（默认）
tradingagents --clear-checkpoints       # 跑前清空所有 checkpoint
```

---

## 5. Python 代码内调用

最小示例（`main.py` 已提供等价写法）：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"]     = "openai"        # openai / google / anthropic / deepseek / ollama / openai_compatible ...
config["deep_think_llm"]   = "gpt-5.5"
config["quick_think_llm"]  = "gpt-5.4-mini"
config["max_debate_rounds"]= 2
config["max_risk_discuss_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

返回的 `decision` 是结构化交易决策；`final_state` 包含各分析师报告、辩论历史、风控报告等完整中间状态。

---

## 6. 支持的标的代码

通过 Yahoo Finance（`yfinance`）的交易所后缀自动识别市场：

| 市场 | 写法示例 |
|---|---|
| 美股 | `AAPL`, `NVDA`, `SPY` |
| 港股 | `0700.HK` |
| 日股 | `7203.T` |
| 伦敦 | `AZN.L` |
| 印度 NSE/BSE | `RELIANCE.NS`, `RELIANCE.BO` |
| 加/澳 | `.TO`, `.AX` |
| A 股 | `600519.SS`（沪）, `000001.SZ`（深） |
| 加密 | `BTC-USD`, `ETH-USD` |

公司身份与基准（默认 SPY）会按市场自动匹配。

---

## 7. 重要的 `TRADINGAGENTS_*` 环境变量（写入 `.env` 即可免去交互）

| 变量 | 作用 | 默认 |
|---|---|---|
| `TRADINGAGENTS_LLM_PROVIDER` | 供应商（`openai` / `google` / `anthropic` / `deepseek` / `groq` / `ollama` / `openai_compatible` / `bedrock` ...） | `openai` |
| `TRADINGAGENTS_DEEP_THINK_LLM` | 深度推理模型 | `gpt-5.5` |
| `TRADINGAGENTS_QUICK_THINK_LLM` | 快速模型 | `gpt-5.4-mini` |
| `TRADINGAGENTS_LLM_BACKEND_URL` | 自定义端点（配合 `openai_compatible`） | — |
| `TRADINGAGENTS_OUTPUT_LANGUAGE` | 报告语言 | `English` |
| `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | 研究员辩论轮数 | `1` |
| `TRADINGAGENTS_MAX_RISK_ROUNDS` | 风控讨论轮数 | `1` |
| `TRADINGAGENTS_CHECKPOINT_ENABLED` | 是否启用断点续跑 | `false` |
| `TRADINGAGENTS_TEMPERATURE` | 采样温度（推理模型基本忽略） | — |
| `TRADINGAGENTS_LLM_MAX_RETRIES` | LLM SDK 重试预算（默认 2，Azure 可拉到 6） | `2` |
| `TRADINGAGENTS_OPENAI_REASONING_EFFORT` | OpenAI 推理深度 | `medium` |
| `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` | Gemini 思考深度 | `high` |
| `TRADINGAGENTS_ANTHROPIC_EFFORT` | Claude 思考努力度 | `high` |
| `TRADINGAGENTS_MEMORY_LOG_PATH` | 决策日志位置 | `~/.tradingagents/memory/trading_memory.md` |
| `TRADINGAGENTS_CACHE_DIR` | checkpoint 缓存根目录 | `~/.tradingagents/cache/checkpoints` |

完整可调项见 `tradingagents/default_config.py`。

---

## 8. 持久化与恢复

- **决策日志**（默认开启）：每次跑完会追加到 `~/.tradingagents/memory/trading_memory.md`，下次同标的跑分析时会把最近几期的反思喂给 Portfolio Manager。
- **检查点续跑**：`--checkpoint` 开启，崩溃后再跑会自动从最后一个完成的节点恢复（命令行提示 `Resuming from step N`）。检查点存在 `~/.tradingagents/cache/checkpoints/<TICKER>.db`。

---

## 9. Docker（备选）

不想用本地 venv 时：
```bash
cd ~/TradingAgents
cp .env.example .env   # 填 Key
docker compose run --rm tradingagents
```
配 Ollama：`docker compose --profile ollama run --rm tradingagents-ollama`

---

## 10. 常见问题

1. **首次运行很慢**：要拉取行情/新闻/情绪数据；只有后续同 ticker 的运行会显著变快。
2. **报 `ModuleNotFoundError: No module named 'tradingagents'`**：忘了 `source .venv/bin/activate` 或没用 `.venv/bin/tradingagents` 绝对路径。
3. **OpenAI 429 错误**：把 `TRADINGAGENTS_LLM_MAX_RETRIES` 调到 6，或换更便宜的 quick 模型。
4. **Windows 下提示 `no Windows console available`**：必须在 Windows Terminal / PowerShell / cmd.exe 里跑，不要在 IDE 嵌入式终端或被 pipe 的终端里跑。
5. **想完全可复现**：把模型换成非推理模型，并把 `TRADINGAGENTS_TEMPERATURE=0.0`（推理模型会忽略温度）。
6. **A股 ticker 报错**：确认是 `600519.SS` / `000001.SZ` 形式，且当前环境能直连 Yahoo Finance。

---

## 11. 验证记录（本次部署）

```
git clone  → ~/TradingAgents        ✅
uv venv 3.12 → .venv                ✅
uv pip install -e .                  ✅（tradingagents 0.3.1 + 全部依赖）
tradingagents --help                 ✅（输出 Usage + Options）
python -c "from tradingagents..."    ✅（包导入正常，DEFAULT_CONFIG 生效）
cp .env.example .env                 ✅（待填 Key）
```

填好 Key 后即可 `tradingagents` 开始交互式分析。
