# -*- coding: utf-8 -*-
"""A 股量化分析软件。

默认提供可离线运行的演示模式，也支持通过 AkShare 获取实时 A 股数据。
本工具只做研究、回测和模拟分析，不会连接券商或自动下单。
"""

from __future__ import annotations

import argparse
import json
import os
import time
import warnings
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable

import akshare as ak
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

CONFIG = {
    "initial_capital": 50000,
    "max_positions": 5,
    "max_single_weight": 0.25,
    "min_position_value": 5000,
    "min_score": 60,
    "max_candidates": 10,
    "stop_loss": -0.08,
    "take_profit": 0.20,
    "max_volatility": 0.60,
    "exclude_st": True,
    "exclude_bj": True,
    "exclude_kc": False,
    "exclude_cyb": False,
    "ai_enabled": False,
    "ai_api_url": "",
    "ai_api_key": "",
    "ai_model": "",
}

DEMO_STOCKS = pd.DataFrame(
    [
        {"symbol": "600519", "name": "贵州茅台", "trend": 0.0009, "vol": 0.016},
        {"symbol": "000001", "name": "平安银行", "trend": 0.0003, "vol": 0.020},
        {"symbol": "300750", "name": "宁德时代", "trend": 0.0011, "vol": 0.025},
        {"symbol": "600036", "name": "招商银行", "trend": 0.0006, "vol": 0.018},
        {"symbol": "688981", "name": "中芯国际", "trend": 0.0008, "vol": 0.030},
        {"symbol": "002594", "name": "比亚迪", "trend": 0.0010, "vol": 0.026},
    ]
)


@dataclass
class AnalysisResult:
    symbol: str
    name: str
    score: int
    signal: str
    regime: str
    close: float
    momentum20: float
    momentum60: float
    rsi: float
    volatility: float
    volume_ratio: float
    distance_high20: float
    weight: float = 0.0
    position_value: float = 0.0
    ai_analysis: str = "AI分析未启用"


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def make_demo_history(symbol: str, trend: float = 0.0006, vol: float = 0.02, days: int = 260) -> pd.DataFrame:
    """生成稳定可复现的演示行情，让首次运行不依赖网络。"""
    rng = np.random.default_rng(int(symbol[-4:]) if symbol[-4:].isdigit() else 2026)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    returns = rng.normal(trend, vol, days)
    close = 20 * np.cumprod(1 + returns)
    open_ = close * (1 + rng.normal(0, vol / 3, days))
    high = np.maximum(open_, close) * (1 + rng.random(days) * vol)
    low = np.minimum(open_, close) * (1 - rng.random(days) * vol)
    volume = rng.integers(80_000, 900_000, days)
    return pd.DataFrame(
        {"date": dates, "open": open_, "close": close, "high": high, "low": low, "volume": volume, "amount": volume * close}
    )


def get_stock_list(demo: bool = False, limit: int | None = None) -> pd.DataFrame:
    if demo:
        df = DEMO_STOCKS[["symbol", "name"]].copy()
    else:
        log("正在获取A股股票列表...")
        df = ak.stock_info_a_code_name().rename(columns={"code": "symbol", "name": "name"})[["symbol", "name"]]
    return df.head(limit) if limit else df


def get_stock_history(symbol: str, demo: bool = False) -> pd.DataFrame:
    if demo:
        row = DEMO_STOCKS.loc[DEMO_STOCKS["symbol"] == symbol]
        trend = float(row["trend"].iloc[0]) if not row.empty else 0.0006
        vol = float(row["vol"].iloc[0]) if not row.empty else 0.02
        return make_demo_history(symbol, trend, vol)
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        if df.empty:
            return pd.DataFrame()
        df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount"})
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as exc:
        log(f"{symbol} 数据获取失败: {exc}")
        return pd.DataFrame()


def get_market_data(demo: bool = False) -> pd.DataFrame:
    if demo:
        return make_demo_history("000300", trend=0.0005, vol=0.014)
    try:
        df = ak.stock_zh_index_daily(symbol="sh000300")
        if df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date")
    except Exception as exc:
        log(f"市场指数获取失败: {exc}")
        return pd.DataFrame()


def validate_data(df: pd.DataFrame) -> bool:
    required = {"open", "high", "low", "close", "volume"}
    return df is not None and not df.empty and len(df) >= 120 and required.issubset(df.columns) and not df["close"].isna().any() and (df["close"] > 0).all()


def filter_stock(symbol: str, name: str) -> bool:
    name_upper = name.upper()
    if CONFIG["exclude_st"] and "ST" in name_upper:
        return False
    if CONFIG["exclude_bj"] and symbol.startswith("8"):
        return False
    if CONFIG["exclude_kc"] and symbol.startswith("688"):
        return False
    if CONFIG["exclude_cyb"] and symbol.startswith("30"):
        return False
    return True


def calculate_factors(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    df["momentum20"] = df["close"].pct_change(20)
    df["momentum60"] = df["close"].pct_change(60)
    returns = df["close"].pct_change()
    df["volatility"] = returns.rolling(20).std() * np.sqrt(252)
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    df["volume_ma20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma20"]
    df["high20"] = df["high"].rolling(20).max()
    df["distance_high20"] = df["close"] / df["high20"] - 1
    return df


def detect_market_regime(df: pd.DataFrame) -> str:
    if df.empty:
        return "UNKNOWN"
    row = calculate_factors(df).iloc[-1]
    if row["close"] > row["ma20"] > row["ma60"]:
        return "BULL"
    if row["close"] < row["ma20"] < row["ma60"]:
        return "BEAR"
    return "SIDEWAYS"


def get_position_multiplier(regime: str) -> float:
    return {"BULL": 1.0, "SIDEWAYS": 0.6, "BEAR": 0.0}.get(regime, 0.3)


def calculate_score(df: pd.DataFrame) -> int:
    row = df.iloc[-1]
    score = 0
    score += 10 if row["ma5"] > row["ma20"] else 0
    score += 15 if row["ma20"] > row["ma60"] else 0
    score += 15 if row["momentum20"] > 0.03 else 0
    score += 15 if row["momentum60"] > 0.08 else 0
    score += 10 if 45 <= row["rsi"] <= 70 else 0
    score += 10 if row["volume_ratio"] > 1.1 else 0
    score += 10 if row["volatility"] < CONFIG["max_volatility"] else 0
    score += 5 if row["distance_high20"] > -0.10 else 0
    return min(score, 100)


def generate_signal(score: int, regime: str) -> str:
    if regime == "BEAR":
        return "WAIT"
    if score >= 80:
        return "STRONG_BUY"
    if score >= 70:
        return "BUY"
    if score >= 60:
        return "WATCH"
    return "AVOID"


def check_limit_status(df: pd.DataFrame) -> bool:
    if len(df) < 2:
        return False
    change = df.iloc[-1]["close"] / df.iloc[-2]["close"] - 1
    return change >= 0.095 or change <= -0.095


def calculate_position(score: int, regime: str, capital: float) -> dict[str, float]:
    if score >= 85:
        base_weight = 0.25
    elif score >= 75:
        base_weight = 0.20
    elif score >= 60:
        base_weight = 0.15
    else:
        base_weight = 0.0
    weight = min(base_weight * get_position_multiplier(regime), CONFIG["max_single_weight"])
    return {"weight": weight, "value": capital * weight}


def ai_analysis(stock: AnalysisResult) -> str:
    if not CONFIG["ai_enabled"]:
        return "AI分析未启用"
    payload = {"model": CONFIG["ai_model"], "messages": [{"role": "user", "content": f"请分析A股{stock.name}({stock.symbol})，评分{stock.score}，信号{stock.signal}，给出风险提示。"}]}
    try:
        response = requests.post(CONFIG["ai_api_url"], headers={"Authorization": f"Bearer {CONFIG['ai_api_key']}", "Content-Type": "application/json"}, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"AI分析失败: {exc}"


def analyze_stock(symbol: str, name: str, regime: str, demo: bool = False) -> AnalysisResult | None:
    if not filter_stock(symbol, name):
        return None
    df = get_stock_history(symbol, demo=demo)
    if not validate_data(df) or check_limit_status(df):
        return None
    factors = calculate_factors(df)
    row = factors.iloc[-1]
    score = calculate_score(factors)
    signal = generate_signal(score, regime)
    return AnalysisResult(
        symbol=symbol,
        name=name,
        score=score,
        signal=signal,
        regime=regime,
        close=round(float(row["close"]), 2),
        momentum20=round(float(row["momentum20"]), 4),
        momentum60=round(float(row["momentum60"]), 4),
        rsi=round(float(row["rsi"]), 2),
        volatility=round(float(row["volatility"]), 4),
        volume_ratio=round(float(row["volume_ratio"]), 2),
        distance_high20=round(float(row["distance_high20"]), 4),
    )


def build_portfolio(candidates: Iterable[AnalysisResult], regime: str, capital: float) -> list[AnalysisResult]:
    portfolio: list[AnalysisResult] = []
    for item in sorted(candidates, key=lambda x: x.score, reverse=True)[: CONFIG["max_candidates"]]:
        position = calculate_position(item.score, regime, capital)
        if position["value"] < CONFIG["min_position_value"]:
            continue
        item.weight = position["weight"]
        item.position_value = round(position["value"], 2)
        item.ai_analysis = ai_analysis(item)
        portfolio.append(item)
        if len(portfolio) >= CONFIG["max_positions"]:
            break
    return portfolio


def scan_market(demo: bool = False, limit: int | None = None, capital: float | None = None) -> tuple[str, list[AnalysisResult], list[AnalysisResult]]:
    log("开始扫描A股..." + ("（演示模式）" if demo else ""))
    stock_list = get_stock_list(demo=demo, limit=limit)
    regime = detect_market_regime(get_market_data(demo=demo))
    log(f"当前市场状态: {regime}")
    candidates: list[AnalysisResult] = []
    for index, row in stock_list.iterrows():
        result = analyze_stock(str(row["symbol"]), str(row["name"]), regime, demo=demo)
        if result and result.score >= CONFIG["min_score"]:
            candidates.append(result)
        if not demo and index % 100 == 0:
            log(f"扫描进度: {index + 1}/{len(stock_list)}")
        if not demo:
            time.sleep(0.05)
    portfolio = build_portfolio(candidates, regime, capital or CONFIG["initial_capital"])
    return regime, candidates, portfolio


def save_report(regime: str, candidates: list[AnalysisResult], portfolio: list[AnalysisResult]) -> None:
    today = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidates_data = [asdict(item) for item in candidates]
    portfolio_data = [asdict(item) for item in portfolio]
    if candidates_data:
        pd.DataFrame(candidates_data).to_csv(os.path.join(REPORT_DIR, f"candidates_{today}.csv"), index=False, encoding="utf-8-sig")
    if portfolio_data:
        pd.DataFrame(portfolio_data).to_csv(os.path.join(REPORT_DIR, f"portfolio_{today}.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(REPORT_DIR, f"summary_{today}.json"), "w", encoding="utf-8") as file:
        json.dump({"date": today, "market_regime": regime, "candidate_count": len(candidates), "portfolio_count": len(portfolio), "portfolio": portfolio_data}, file, ensure_ascii=False, indent=2)
    log(f"报告已保存到: {REPORT_DIR}")


def print_result(regime: str, candidates: list[AnalysisResult], portfolio: list[AnalysisResult]) -> None:
    print("\n" + "=" * 72)
    print("A股量化分析软件（研究/模拟，不自动交易）")
    print("=" * 72)
    print(f"市场状态: {regime} | 候选股票: {len(candidates)} | 最终组合: {len(portfolio)}")
    if not portfolio:
        print("当前没有满足条件的股票，系统建议：等待。")
        return
    for index, stock in enumerate(portfolio, start=1):
        print(f"\n{index}. {stock.symbol} {stock.name}")
        print(f"评分/信号: {stock.score} / {stock.signal}")
        print(f"价格: {stock.close} | 建议仓位: {stock.weight:.2%} | 建议金额: {stock.position_value:.2f}")
        print(f"RSI: {stock.rsi} | 20日动量: {stock.momentum20} | 60日动量: {stock.momentum60}")
        print(f"波动率: {stock.volatility} | 距离20日高点: {stock.distance_high20}")
        print(f"止损参考: {CONFIG['stop_loss']:.2%} | 止盈参考: {CONFIG['take_profit']:.2%}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="可直接运行的A股量化分析软件")
    parser.add_argument("--demo", action="store_true", help="使用内置演示数据，离线也能立即跑通")
    parser.add_argument("--limit", type=int, default=None, help="限制扫描股票数量，便于快速试跑")
    parser.add_argument("--capital", type=float, default=CONFIG["initial_capital"], help="模拟资金")
    parser.add_argument("--min-score", type=int, default=CONFIG["min_score"], help="最低入选评分")
    parser.add_argument("--no-report", action="store_true", help="只打印结果，不保存报告")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    CONFIG["initial_capital"] = args.capital
    CONFIG["min_score"] = args.min_score
    print("\nA股量化分析软件 V5.0")
    print(f"模式: {'演示数据' if args.demo else '真实行情'} | 资金: {args.capital:.2f} | 最低评分: {args.min_score}")
    regime, candidates, portfolio = scan_market(demo=args.demo, limit=args.limit, capital=args.capital)
    print_result(regime, candidates, portfolio)
    if not args.no_report:
        save_report(regime, candidates, portfolio)


if __name__ == "__main__":
    main()
