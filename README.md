# A股量化选股与模拟组合工具

这是一个面向研究和模拟交易的 A 股量化选股脚本。它会通过 AkShare 获取股票和沪深 300 指数数据，计算趋势、动量、RSI、波动率、成交量等因子，识别市场环境，并输出候选股票、模拟组合和 CSV/JSON 报告。

> ⚠️ 本项目仅用于量化研究、回测思路验证和模拟交易，不会自动连接真实证券账户下单，也不构成投资建议。

## 功能

- 获取 A 股股票池和历史行情
- 过滤 ST、北交所、可选过滤科创板/创业板
- 基于多因子规则生成 0-100 分量化评分
- 根据沪深 300 判断市场状态：`BULL`、`SIDEWAYS`、`BEAR`
- 动态仓位建议，避免模拟组合总金额超过初始资金
- 涨跌停、最小持仓金额、最大持仓数量等风控约束
- 输出候选股、组合和摘要报告到 `reports/`
- 可选预留 AI 分析接口

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 快速运行

扫描全市场：

```bash
python quant_system.py
```

快速试跑前 50 只股票：

```bash
python quant_system.py --scan-limit 50
```

自定义资金、持仓数量和最低评分：

```bash
python quant_system.py --capital 100000 --max-positions 6 --min-score 65
```

启用 AI 分析：

```bash
python quant_system.py --enable-ai
```

启用前需要在 `quant_system.py` 的 `CONFIG` 中配置：

- `ai_api_url`
- `ai_api_key`
- `ai_model`

## 输出

运行后会在 `reports/` 目录生成：

- `candidates_YYYYMMDD.csv`：候选股票列表
- `portfolio_YYYYMMDD.csv`：最终模拟组合
- `summary_YYYYMMDD.json`：本次扫描摘要

## 常用参数

| 参数 | 说明 |
| --- | --- |
| `--capital` | 初始资金 |
| `--max-positions` | 最大持仓数量 |
| `--min-score` | 候选股最低评分 |
| `--scan-limit` | 仅扫描前 N 只股票，适合快速验证 |
| `--enable-ai` | 启用 AI 分析接口 |

## 风险提示

- 量化评分只基于历史数据和规则，不能预测确定收益。
- AkShare 数据接口可能因网络、数据源变化或限流失败。
- 真实交易前请自行补充严谨回测、交易制度适配、风控和合规检查。
