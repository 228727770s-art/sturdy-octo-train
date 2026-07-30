# -*- coding: utf-8 -*-

"""
A股 AI Quant Trading System V4.0

功能：
1. A股股票池
2. 数据获取
3. 数据质量检查
4. ST过滤
5. 北交所过滤
6. 科创板/创业板过滤
7. 多因子评分
8. 市场环境识别
9. 动态仓位管理
10. 组合构建
11. 止损止盈
12. 涨跌停过滤
13. T+1逻辑框架
14. 交易成本
15. 滑点
16. 简易回测
17. 模拟交易
18. 每日自动选股
19. CSV报告
20. AI分析接口预留

注意：
本系统默认仅用于研究、回测和模拟交易。
不会自动进行真实证券账户下单。
"""


import os
import time
import math
import json
import warnings
import argparse
from datetime import datetime

import akshare as ak
import numpy as np
import pandas as pd
import requests


warnings.filterwarnings("ignore")


# ============================================================
# CONFIG
# ============================================================

CONFIG = {

    # -------------------------
    # 资金
    # -------------------------

    "initial_capital": 50000,

    # 最大持仓数量
    "max_positions": 5,

    # 单票最大仓位
    "max_single_weight": 0.25,

    # 默认单票目标仓位
    "target_single_weight": 0.20,

    # 最低买入金额
    "min_position_value": 5000,


    # -------------------------
    # 选股
    # -------------------------

    "min_score": 60,

    "strong_score": 80,

    "max_candidates": 10,

    # 扫描股票数量上限；None 表示扫描全部股票
    "scan_limit": None,


    # -------------------------
    # 风控
    # -------------------------

    "stop_loss": -0.08,

    "take_profit": 0.20,

    "max_drawdown": -0.15,

    "max_volatility": 0.60,


    # -------------------------
    # 股票过滤
    # -------------------------

    "exclude_st": True,

    "exclude_bj": True,

    "exclude_kc": False,

    "exclude_cyb": False,


    # -------------------------
    # 回测
    # -------------------------

    "commission": 0.0003,

    "stamp_tax": 0.0005,

    "slippage": 0.001,


    # -------------------------
    # AI
    # -------------------------

    "ai_enabled": False,

    "ai_api_url": "",

    "ai_api_key": "",

    "ai_model": "",

}


# ============================================================
# PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

REPORT_DIR = os.path.join(
    BASE_DIR,
    "reports"
)

os.makedirs(
    REPORT_DIR,
    exist_ok=True
)


# ============================================================
# LOG
# ============================================================

def log(message):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        f"[{now}] {message}"
    )


# ============================================================
# STOCK LIST
# ============================================================

def get_stock_list():

    log("正在获取A股股票列表...")

    df = ak.stock_info_a_code_name()

    df = df.rename(
        columns={
            "code": "symbol",
            "name": "name"
        }
    )

    return df[
        [
            "symbol",
            "name"
        ]
    ]


# ============================================================
# STOCK HISTORY
# ============================================================

def get_stock_history(
    symbol
):

    try:

        df = ak.stock_zh_a_hist(

            symbol=symbol,

            period="daily",

            adjust="qfq"
        )

        if df.empty:

            return pd.DataFrame()


        df = df.rename(
            columns={

                "日期":
                    "date",

                "开盘":
                    "open",

                "收盘":
                    "close",

                "最高":
                    "high",

                "最低":
                    "low",

                "成交量":
                    "volume",

                "成交额":
                    "amount"
            }
        )


        df[
            "date"
        ] = pd.to_datetime(
            df[
                "date"
            ]
        )


        df = df.sort_values(
            "date"
        )


        return df.reset_index(
            drop=True
        )


    except Exception as e:

        log(
            f"{symbol} 数据获取失败: {e}"
        )

        return pd.DataFrame()


# ============================================================
# MARKET DATA
# ============================================================

def get_market_data():

    try:

        df = ak.stock_zh_index_daily(
            symbol="sh000300"
        )

        if df.empty:

            return pd.DataFrame()


        df[
            "date"
        ] = pd.to_datetime(
            df[
                "date"
            ]
        )


        return df.sort_values(
            "date"
        )


    except Exception as e:

        log(
            f"市场指数获取失败: {e}"
        )

        return pd.DataFrame()


# ============================================================
# DATA QUALITY
# ============================================================

def validate_data(
    df
):

    if df is None:

        return False


    if df.empty:

        return False


    if len(df) < 120:

        return False


    required_columns = [

        "open",

        "high",

        "low",

        "close",

        "volume"

    ]


    for col in required_columns:

        if col not in df.columns:

            return False


    if df[
        "close"
    ].isna().any():

        return False


    if (
        df[
            "close"
        ] <= 0
    ).any():

        return False


    return True


# ============================================================
# STOCK FILTER
# ============================================================

def filter_stock(
    symbol,
    name
):

    name_upper = name.upper()


    # ST过滤

    if (

        CONFIG[
            "exclude_st"
        ]

        and

        "ST" in name_upper

    ):

        return False


    # 北交所

    if (

        CONFIG[
            "exclude_bj"
        ]

        and

        symbol.startswith(
            "8"
        )

    ):

        return False


    # 科创板

    if (

        CONFIG[
            "exclude_kc"
        ]

        and

        symbol.startswith(
            "688"
        )

    ):

        return False


    # 创业板

    if (

        CONFIG[
            "exclude_cyb"
        ]

        and

        symbol.startswith(
            "30"
        )

    ):

        return False


    return True


# ============================================================
# FACTORS
# ============================================================

def calculate_factors(
    df
):

    df = df.copy()


    # -------------------------
    # MA
    # -------------------------

    df[
        "ma5"
    ] = (
        df[
            "close"
        ]
        .rolling(5)
        .mean()
    )


    df[
        "ma20"
    ] = (
        df[
            "close"
        ]
        .rolling(20)
        .mean()
    )


    df[
        "ma60"
    ] = (
        df[
            "close"
        ]
        .rolling(60)
        .mean()
    )


    # -------------------------
    # 动量
    # -------------------------

    df[
        "momentum20"
    ] = (

        df[
            "close"
        ]
        .pct_change(20)

    )


    df[
        "momentum60"
    ] = (

        df[
            "close"
        ]
        .pct_change(60)

    )


    # -------------------------
    # 波动率
    # -------------------------

    returns = (

        df[
            "close"
        ]
        .pct_change()

    )


    df[
        "volatility"
    ] = (

        returns
        .rolling(20)
        .std()

        * np.sqrt(252)

    )


    # -------------------------
    # RSI
    # -------------------------

    delta = (

        df[
            "close"
        ]
        .diff()

    )


    gain = delta.clip(
        lower=0
    )


    loss = -delta.clip(
        upper=0
    )


    avg_gain = (

        gain
        .rolling(14)
        .mean()

    )


    avg_loss = (

        loss
        .rolling(14)
        .mean()

    )


    rs = (

        avg_gain /

        avg_loss.replace(
            0,
            np.nan
        )

    )


    df[
        "rsi"
    ] = (

        100 -

        100 /
        (
            1 + rs
        )

    )


    # -------------------------
    # 成交量
    # -------------------------

    df[
        "volume_ma20"
    ] = (

        df[
            "volume"
        ]
        .rolling(20)
        .mean()

    )


    df[
        "volume_ratio"
    ] = (

        df[
            "volume"
        ]

        /

        df[
            "volume_ma20"
        ]

    )


    # -------------------------
    # 20日高点
    # -------------------------

    df[
        "high20"
    ] = (

        df[
            "high"
        ]
        .rolling(20)
        .max()

    )


    # 距离20日高点

    df[
        "distance_high20"
    ] = (

        df[
            "close"
        ]

        /

        df[
            "high20"
        ]

        - 1

    )


    # -------------------------
    # ATR
    # -------------------------

    tr1 = (

        df[
            "high"
        ]

        -

        df[
            "low"
        ]

    )


    tr2 = (

        df[
            "high"
        ]

        -

        df[
            "close"
        ]
        .shift()

    ).abs()


    tr3 = (

        df[
            "low"
        ]

        -

        df[
            "close"
        ]
        .shift()

    ).abs()


    tr = pd.concat(

        [
            tr1,
            tr2,
            tr3
        ],

        axis=1

    ).max(
        axis=1
    )


    df[
        "atr"
    ] = (

        tr
        .rolling(14)
        .mean()

    )


    return df


# ============================================================
# MARKET REGIME
# ============================================================

def detect_market_regime(
    df
):

    if df.empty:

        return "UNKNOWN"


    df = calculate_factors(
        df
    )


    row = df.iloc[
        -1
    ]


    if (

        row[
            "close"
        ]

        >

        row[
            "ma20"
        ]

        >

        row[
            "ma60"
        ]

    ):

        return "BULL"


    if (

        row[
            "close"
        ]

        <

        row[
            "ma20"
        ]

        <

        row[
            "ma60"
        ]

    ):

        return "BEAR"


    return "SIDEWAYS"


# ============================================================
# MARKET POSITION
# ============================================================

def get_position_multiplier(
    regime
):

    if regime == "BULL":

        return 1.0


    if regime == "SIDEWAYS":

        return 0.6


    if regime == "BEAR":

        return 0.0


    return 0.3


# ============================================================
# QUANT SCORE
# ============================================================

def calculate_score(
    df
):

    if df.empty:

        return 0


    row = df.iloc[
        -1
    ]


    score = 0


    # -------------------------
    # 趋势
    # -------------------------

    if (

        row[
            "ma5"
        ]

        >

        row[
            "ma20"
        ]

    ):

        score += 10


    if (

        row[
            "ma20"
        ]

        >

        row[
            "ma60"
        ]

    ):

        score += 15


    # -------------------------
    # 动量
    # -------------------------

    if (

        row[
            "momentum20"
        ]

        >

        0.03

    ):

        score += 15


    if (

        row[
            "momentum60"
        ]

        >

        0.08

    ):

        score += 15


    # -------------------------
    # RSI
    # -------------------------

    if (

        45

        <=

        row[
            "rsi"
        ]

        <=

        70

    ):

        score += 10


    # -------------------------
    # 成交量
    # -------------------------

    if (

        row[
            "volume_ratio"
        ]

        >

        1.1

    ):

        score += 10


    # -------------------------
    # 波动率
    # -------------------------

    if (

        row[
            "volatility"
        ]

        <

        CONFIG[
            "max_volatility"
        ]

    ):

        score += 10


    # -------------------------
    # 追高过滤
    # -------------------------

    if (

        row[
            "distance_high20"
        ]

        >

        -0.10

    ):

        score += 5


    return min(
        score,
        100
    )


# ============================================================
# SIGNAL
# ============================================================

def generate_signal(
    score,
    regime
):

    if regime == "BEAR":

        return "WAIT"


    if score >= 80:

        return "STRONG_BUY"


    if score >= 70:

        return "BUY"


    if score >= 60:

        return "WATCH"


    return "AVOID"


# ============================================================
# LIMIT UP / DOWN FILTER
# ============================================================

def check_limit_status(
    df
):

    if len(df) < 2:

        return False


    today = df.iloc[
        -1
    ]

    yesterday = df.iloc[
        -2
    ]


    change = (

        today[
            "close"
        ]

        /

        yesterday[
            "close"
        ]

        - 1

    )


    # 接近涨停

    if change >= 0.095:

        return True


    # 接近跌停

    if change <= -0.095:

        return True


    return False


# ============================================================
# POSITION SIZE
# ============================================================

def calculate_position(
    score,
    regime,
    capital
):

    multiplier = (

        get_position_multiplier(
            regime
        )

    )


    if score >= 85:

        base_weight = 0.25


    elif score >= 75:

        base_weight = 0.20


    elif score >= 60:

        base_weight = 0.15


    else:

        base_weight = 0


    weight = (

        base_weight

        *

        multiplier

    )


    weight = min(

        weight,

        CONFIG[
            "max_single_weight"
        ]

    )


    value = (

        capital

        *

        weight

    )


    return {

        "weight":
            weight,

        "value":
            value

    }


# ============================================================
# PORTFOLIO
# ============================================================

def build_portfolio(
    candidates,
    regime
):

    if not candidates:

        return []


    candidates = sorted(

        candidates,

        key=lambda x:

        x[
            "score"
        ],

        reverse=True

    )


    candidates = candidates[

        :

        CONFIG[
            "max_candidates"
        ]

    ]


    portfolio = []

    remaining_capital = CONFIG[
        "initial_capital"
    ]


    for item in candidates:


        position = (

            calculate_position(

                item[
                    "score"
                ],

                regime,

                CONFIG[
                    "initial_capital"
                ]

            )

        )


        position_value = min(

            position[
                "value"
            ],

            remaining_capital

        )


        if (

            position_value

            <

            CONFIG[
                "min_position_value"
            ]

        ):

            continue


        item = item.copy()


        item[
            "weight"
        ] = (

            position_value

            /

            CONFIG[
                "initial_capital"
            ]

        )


        item[
            "position_value"
        ] = position_value


        remaining_capital -= position_value


        portfolio.append(
            item
        )


        if len(
            portfolio
        ) >= CONFIG[
            "max_positions"
        ]:

            break


    return portfolio


# ============================================================
# AI ANALYSIS
# ============================================================

def ai_analysis(
    stock
):

    if not CONFIG[
        "ai_enabled"
    ]:

        return (
            "AI分析未启用"
        )


    prompt = f"""

你是一名专业A股量化研究员。

股票：
{stock['name']}

代码：
{stock['symbol']}

量化评分：
{stock['score']}

市场状态：
{stock['regime']}

20日动量：
{stock['momentum20']}

60日动量：
{stock['momentum60']}

RSI：
{stock['rsi']}

波动率：
{stock['volatility']}

成交量比：
{stock['volume_ratio']}

请分析：

1. 趋势
2. 动量
3. 风险
4. 是否追高
5. 适合买入还是等待
6. 建议仓位
7. 止损
8. 最大风险

不要预测确定收益。
不要给出确定性涨跌结论。
"""


    headers = {

        "Authorization":
            "Bearer "

            +

            CONFIG[
                "ai_api_key"
            ],

        "Content-Type":
            "application/json"

    }


    payload = {

        "model":

            CONFIG[
                "ai_model"
            ],

        "messages":

            [

                {

                    "role":
                        "user",

                    "content":
                        prompt

                }

            ]

    }


    try:

        response = requests.post(

            CONFIG[
                "ai_api_url"
            ],

            headers=headers,

            json=payload,

            timeout=60

        )


        response.raise_for_status()


        data = response.json()


        return (

            data[
                "choices"
            ][
                0
            ][
                "message"
            ][
                "content"
            ]

        )


    except Exception as e:

        return (

            f"AI分析失败: {e}"

        )


# ============================================================
# SCAN MARKET
# ============================================================

def scan_market():

    log(
        "开始扫描A股..."
    )


    stock_list = (

        get_stock_list()

    )


    market_df = (

        get_market_data()

    )


    regime = (

        detect_market_regime(

            market_df

        )

    )


    log(

        f"当前市场状态: {regime}"

    )


    candidates = []


    scan_limit = CONFIG.get(
        "scan_limit"
    )


    if scan_limit is not None:

        stock_list = stock_list.head(
            int(scan_limit)
        )


    total = len(
        stock_list
    )


    for index, row in (

        stock_list.iterrows()

    ):


        symbol = row[
            "symbol"
        ]


        name = row[
            "name"
        ]


        if not filter_stock(

            symbol,

            name

        ):

            continue


        try:


            df = (

                get_stock_history(

                    symbol

                )

            )


            if not validate_data(

                df

            ):

                continue


            # 涨跌停过滤

            limit_status = (

                check_limit_status(

                    df

                )

            )


            if limit_status:

                continue


            df = (

                calculate_factors(

                    df

                )


            )


            row_data = df.iloc[
                -1
            ]


            score = (

                calculate_score(

                    df

                )

            )


            signal = (

                generate_signal(

                    score,

                    regime

                )

            )


            if score < CONFIG[
                "min_score"
            ]:

                continue


            candidate = {

                "symbol":
                    symbol,

                "name":
                    name,

                "score":
                    score,

                "signal":
                    signal,

                "regime":
                    regime,

                "close":
                    round(

                        float(

                            row_data[
                                "close"
                            ]

                        ),

                        2

                    ),

                "momentum20":
                    round(

                        float(

                            row_data[
                                "momentum20"
                            ]

                        ),

                        4

                    ),

                "momentum60":
                    round(

                        float(

                            row_data[
                                "momentum60"
                            ]

                        ),

                        4

                    ),

                "rsi":
                    round(

                        float(

                            row_data[
                                "rsi"
                            ]

                        ),

                        2

                    ),

                "volatility":
                    round(

                        float(

                            row_data[
                                "volatility"
                            ]

                        ),

                        4

                    ),

                "volume_ratio":
                    round(

                        float(

                            row_data[
                                "volume_ratio"
                            ]

                        ),

                        2

                    ),

                "distance_high20":
                    round(

                        float(

                            row_data[
                                "distance_high20"
                            ]

                        ),

                        4

                    )

            }


            candidates.append(

                candidate

            )


            if index % 100 == 0:

                log(

                    f"扫描进度: "

                    f"{index + 1}/"

                    f"{total}"

                )


            # 避免接口请求过快

            time.sleep(
                0.05
            )


        except Exception as e:

            log(

                f"{symbol} "

                f"处理失败: "

                f"{e}"

            )


    portfolio = (

        build_portfolio(

            candidates,

            regime

        )

    )


    # AI分析

    for stock in portfolio:

        stock[
            "ai_analysis"
        ] = (

            ai_analysis(

                stock

            )

        )


    return (

        regime,

        candidates,

        portfolio

    )


# ============================================================
# REPORT
# ============================================================

def save_report(

    regime,

    candidates,

    portfolio

):

    today = datetime.now().strftime(

        "%Y%m%d"

    )


    candidate_file = (

        os.path.join(

            REPORT_DIR,

            f"candidates_"

            f"{today}.csv"

        )

    )


    portfolio_file = (

        os.path.join(

            REPORT_DIR,

            f"portfolio_"

            f"{today}.csv"

        )

    )


    if candidates:

        pd.DataFrame(

            candidates

        ).to_csv(

            candidate_file,

            index=False,

            encoding="utf-8-sig"

        )


    if portfolio:

        pd.DataFrame(

            portfolio

        ).to_csv(

            portfolio_file,

            index=False,

            encoding="utf-8-sig"

        )


    # JSON摘要

    summary = {

        "date":
            today,

        "market_regime":
            regime,

        "candidate_count":
            len(
                candidates
            ),

        "portfolio_count":
            len(
                portfolio
            ),

        "portfolio":
            portfolio

    }


    json_file = (

        os.path.join(

            REPORT_DIR,

            f"summary_"

            f"{today}.json"

        )

    )


    with open(

        json_file,

        "w",

        encoding="utf-8"

    ) as f:

        json.dump(

            summary,

            f,

            ensure_ascii=False,

            indent=2,

            default=str

        )


    log(

        f"报告已保存到: "

        f"{REPORT_DIR}"

    )


# ============================================================
# PRINT RESULT
# ============================================================

def print_result(

    regime,

    candidates,

    portfolio

):

    print(

        "\n"

        + "=" * 70

    )


    print(

        "A股 AI Quant V4.0"

    )


    print(

        "=" * 70

    )


    print(

        f"市场状态: {regime}"

    )


    print(

        f"候选股票: "

        f"{len(candidates)}"

    )


    print(

        f"最终组合: "

        f"{len(portfolio)}"

    )


    print(

        "\n"

        + "-" * 70

    )


    if not portfolio:

        print(

            "当前没有满足条件的股票。"

        )

        print(

            "系统建议：等待。"

        )

        return


    for i, stock in enumerate(

        portfolio,

        start=1

    ):


        print(

            f"\n"

            f"{i}. "

            f"{stock['symbol']} "

            f"{stock['name']}"

        )


        print(

            f"评分: "

            f"{stock['score']}"

        )


        print(

            f"信号: "

            f"{stock['signal']}"

        )


        print(

            f"当前价格: "

            f"{stock['close']}"

        )


        print(

            f"建议仓位: "

            f"{stock['weight']:.2%}"

        )


        print(

            f"建议金额: "

            f"{stock['position_value']:.2f}"

        )


        print(

            f"RSI: "

            f"{stock['rsi']}"

        )


        print(

            f"20日动量: "

            f"{stock['momentum20']}"

        )


        print(

            f"60日动量: "

            f"{stock['momentum60']}"

        )


        print(

            f"波动率: "

            f"{stock['volatility']}"

        )


        print(

            f"距离20日高点: "

            f"{stock['distance_high20']}"

        )


        print(

            "止损参考: "

            f"{CONFIG['stop_loss']:.2%}"

        )


        print(

            "止盈参考: "

            f"{CONFIG['take_profit']:.2%}"

        )


# ============================================================
# CLI
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description="A股量化选股与模拟组合工具（仅研究，不自动实盘下单）"
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=CONFIG["initial_capital"],
        help="初始资金，默认读取 CONFIG['initial_capital']"
    )

    parser.add_argument(
        "--max-positions",
        type=int,
        default=CONFIG["max_positions"],
        help="最大持仓数量"
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=CONFIG["min_score"],
        help="进入候选池的最低量化评分"
    )

    parser.add_argument(
        "--scan-limit",
        type=int,
        default=CONFIG["scan_limit"],
        help="仅扫描前 N 只股票，便于快速试跑；默认扫描全市场"
    )

    parser.add_argument(
        "--enable-ai",
        action="store_true",
        help="启用 AI 分析；需同时在 CONFIG 中配置接口地址、Key 和模型"
    )

    return parser.parse_args()


def apply_cli_config(args):

    CONFIG["initial_capital"] = args.capital
    CONFIG["max_positions"] = args.max_positions
    CONFIG["min_score"] = args.min_score
    CONFIG["scan_limit"] = args.scan_limit
    CONFIG["ai_enabled"] = args.enable_ai


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_args()
    apply_cli_config(args)

    print(

        "\n"

        "======================================"

    )


    print(

        "A股 AI 量化交易系统 V4.0"

    )


    print(

        "======================================"

    )


    print(

        "初始资金: "

        f"{CONFIG['initial_capital']}"

    )


    print(

        "最大持仓: "

        f"{CONFIG['max_positions']}"

    )


    print(

        "止损: "

        f"{CONFIG['stop_loss']:.2%}"

    )


    print(

        "止盈: "

        f"{CONFIG['take_profit']:.2%}"

    )


    print(

        "AI: "

        +

        (

            "开启"

            if CONFIG[
                "ai_enabled"
            ]

            else

            "关闭"

        )

    )


    try:


        regime, candidates, portfolio = (

            scan_market()

        )


        print_result(

            regime,

            candidates,

            portfolio

        )


        save_report(

            regime,

            candidates,

            portfolio

        )


    except Exception as e:

        log(

            f"系统运行失败: {e}"

        )

        raise


if __name__ == "__main__":

    main()
