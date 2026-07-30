# A股量化分析软件

这是一个可以直接运行的 A 股量化分析工具，支持：

- 离线演示模式：不依赖网络，首次安装后即可验证完整流程。
- 真实行情模式：通过 AkShare 获取 A 股股票列表、个股行情和沪深 300 指数。
- 多因子评分：趋势、动量、RSI、成交量、波动率、20 日高点距离。
- 市场状态识别：牛市、熊市、震荡市，并动态调整建议仓位。
- 风控输出：止损、止盈、限价涨跌停过滤、最大单票仓位。
- 报告导出：自动生成 CSV 和 JSON 到 `reports/` 目录。

> 重要提示：本项目仅用于学习、研究、回测和模拟分析，不构成投资建议，不会连接券商或自动下单。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python quant_system.py --demo
```

## 常用命令

### 1. 离线演示，立即跑通

```bash
python quant_system.py --demo
```

### 2. 快速扫描真实行情中的前 50 只股票

```bash
python quant_system.py --limit 50
```

### 3. 修改模拟资金和最低评分

```bash
python quant_system.py --demo --capital 100000 --min-score 55
```

### 4. 只在终端打印，不保存报告

```bash
python quant_system.py --demo --no-report
```

## 输出说明

运行结束后会显示：

- 当前市场状态：`BULL`、`BEAR`、`SIDEWAYS` 或 `UNKNOWN`。
- 候选股票数量。
- 最终模拟组合。
- 每只股票的评分、信号、价格、建议仓位、建议金额、RSI、动量、波动率、止损止盈参考。

如未使用 `--no-report`，程序会在 `reports/` 下生成：

- `candidates_*.csv`：候选股票列表。
- `portfolio_*.csv`：最终组合。
- `summary_*.json`：本次运行摘要。

## 参数

| 参数 | 说明 |
| --- | --- |
| `--demo` | 使用内置演示数据，适合首次试跑或无网络环境。 |
| `--limit N` | 限制扫描股票数量，真实行情模式下建议先用小数字测试。 |
| `--capital 金额` | 设置模拟资金，默认 50000。 |
| `--min-score 分数` | 设置最低入选评分，默认 60。 |
| `--no-report` | 不写入报告文件。 |

## 免责声明

量化评分和仓位建议只基于历史行情和规则模型，不能预测确定收益。任何交易决策都应结合自身风险承受能力，并自行承担风险。
