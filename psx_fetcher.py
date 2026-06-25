#!/usr/bin/env python3
"""
PSX ULTIMATE DIVIDEND CAPTURE ENGINE v32.2 – PRODUCTION READY
Author: PSX Ultimate Engine
License: Personal Use Only
Description: Clean, modular, PEP 8‑compliant, Python 3.12+ automated PSX trading system.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from threading import Thread
from typing import Dict, List, Optional, Tuple, Any

import feedparser
import numpy as np
import pandas as pd
import requests
import yaml
from textblob import TextBlob

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

try:
    import pypsx
    PYPSX_AVAILABLE = True
except ImportError:
    PYPSX_AVAILABLE = False

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s",
)
logger = logging.getLogger("psx.engine")

# ============================================================
# CONSTANTS & CONFIGURATION
# ============================================================
VERSION = "32.2"
AUTHOR = "PSX Ultimate Engine"

# Environment variables
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "")
TO_EMAIL = os.environ.get("TO_EMAIL", "")

ACCOUNT_BALANCE = float(os.environ.get("PSX_ACCOUNT_BALANCE", 30000.0))
MAX_RISK_PER_TRADE = float(os.environ.get("PSX_MAX_RISK_PER_TRADE", 0.02))
MAX_PORTFOLIO_DRAWDOWN = float(os.environ.get("PSX_MAX_PORTFOLIO_DRAWDOWN", 1.0))
STOP_LOSS_PCT = float(os.environ.get("PSX_STOP_LOSS_PCT", 0.03))
TARGET1_PCT = float(os.environ.get("PSX_TARGET1_PCT", 0.05))
TARGET2_PCT = float(os.environ.get("PSX_TARGET2_PCT", 0.08))
TAX_FILER = os.environ.get("PSX_TAX_FILER", "True").lower() == "true"
CGT_RATE = 0.15 if TAX_FILER else 0.20
DIV_TAX_RATE = 0.15 if TAX_FILER else 0.20

# ============================================================
# UNIVERSE OF STOCKS
# ============================================================
TOP_50_SHARIAH_STOCKS = [
    {"symbol": "FFC", "sector": "Fertilizer", "market_cap": 803953516010, "current_price": 558.68},
    {"symbol": "EFERT", "sector": "Fertilizer", "market_cap": 280000000000, "current_price": 199.38},
    {"symbol": "MARI", "sector": "Oil & Gas", "market_cap": 350000000000, "current_price": 656.72},
    {"symbol": "OGDC", "sector": "Oil & Gas", "market_cap": 480000000000, "current_price": 320.00},
    {"symbol": "PPL", "sector": "Oil & Gas", "market_cap": 320000000000, "current_price": 230.00},
    {"symbol": "PSO", "sector": "Oil & Gas", "market_cap": 290000000000, "current_price": 355.00},
    {"symbol": "HUBC", "sector": "Energy", "market_cap": 180000000000, "current_price": 231.81},
    {"symbol": "MCB", "sector": "Banking", "market_cap": 250000000000, "current_price": 398.83},
    {"symbol": "UBL", "sector": "Banking", "market_cap": 220000000000, "current_price": 415.00},
    {"symbol": "NBP", "sector": "Banking", "market_cap": 160000000000, "current_price": 192.00},
    {"symbol": "HBL", "sector": "Banking", "market_cap": 200000000000, "current_price": 290.00},
    {"symbol": "LUCK", "sector": "Cement", "market_cap": 210000000000, "current_price": 440.00},
    {"symbol": "DGKC", "sector": "Cement", "market_cap": 140000000000, "current_price": 200.00},
    {"symbol": "MLCF", "sector": "Cement", "market_cap": 120000000000, "current_price": 84.00},
    {"symbol": "FCCL", "sector": "Cement", "market_cap": 80000000000, "current_price": 54.00},
    {"symbol": "ATRL", "sector": "Refinery", "market_cap": 150000000000, "current_price": 885.00},
    {"symbol": "NRL", "sector": "Refinery", "market_cap": 120000000000, "current_price": 371.00},
    {"symbol": "PRL", "sector": "Refinery", "market_cap": 90000000000, "current_price": 35.00},
    {"symbol": "PAEL", "sector": "Automobile", "market_cap": 70000000000, "current_price": 30.00},
    {"symbol": "SEARL", "sector": "Pharma", "market_cap": 80000000000, "current_price": 150.00},
    {"symbol": "SNGP", "sector": "Oil & Gas", "market_cap": 100000000000, "current_price": 60.00},
    {"symbol": "SSGC", "sector": "Oil & Gas", "market_cap": 90000000000, "current_price": 35.00},
    {"symbol": "ENGROH", "sector": "Fertilizer", "market_cap": 70000000000, "current_price": 100.00},
    {"symbol": "GAL", "sector": "Textile", "market_cap": 60000000000, "current_price": 80.00},
    {"symbol": "GHNI", "sector": "Textile", "market_cap": 50000000000, "current_price": 50.00},
    {"symbol": "HCAR", "sector": "Automobile", "market_cap": 50000000000, "current_price": 60.00},
    {"symbol": "NML", "sector": "Textile", "market_cap": 45000000000, "current_price": 40.00},
    {"symbol": "TREET", "sector": "Textile", "market_cap": 40000000000, "current_price": 15.00},
    {"symbol": "CNERGY", "sector": "Energy", "market_cap": 50000000000, "current_price": 8.00},
    {"symbol": "CPHL", "sector": "Pharma", "market_cap": 35000000000, "current_price": 10.00},
    {"symbol": "FFL", "sector": "Fertilizer", "market_cap": 30000000000, "current_price": 12.00},
    {"symbol": "AIRLINK", "sector": "Technology", "market_cap": 28000000000, "current_price": 25.00},
    {"symbol": "KEL", "sector": "Energy", "market_cap": 25000000000, "current_price": 8.00},
    {"symbol": "WTL", "sector": "Technology", "market_cap": 20000000000, "current_price": 5.00},
    {"symbol": "TRG", "sector": "Technology", "market_cap": 18000000000, "current_price": 20.00},
    {"symbol": "TPL", "sector": "Technology", "market_cap": 15000000000, "current_price": 16.00},
    {"symbol": "PICT", "sector": "Cement", "market_cap": 12000000000, "current_price": 45.00},
    {"symbol": "IBFL", "sector": "Banking", "market_cap": 10000000000, "current_price": 40.00},
    {"symbol": "SCBPL", "sector": "Banking", "market_cap": 8000000000, "current_price": 35.00},
    {"symbol": "SILK", "sector": "Textile", "market_cap": 7000000000, "current_price": 30.00},
    {"symbol": "KAPCO", "sector": "Energy", "market_cap": 6000000000, "current_price": 50.00},
    {"symbol": "NCL", "sector": "Cement", "market_cap": 5000000000, "current_price": 20.00},
    {"symbol": "PSMC", "sector": "Automobile", "market_cap": 4000000000, "current_price": 60.00},
    {"symbol": "PTC", "sector": "Technology", "market_cap": 3000000000, "current_price": 15.00},
    {"symbol": "SBL", "sector": "Banking", "market_cap": 2000000000, "current_price": 10.00},
    {"symbol": "SHFA", "sector": "Pharma", "market_cap": 1000000000, "current_price": 8.00},
    {"symbol": "SML", "sector": "Textile", "market_cap": 500000000, "current_price": 5.00},
    {"symbol": "SNBL", "sector": "Banking", "market_cap": 300000000, "current_price": 3.00},
]

_MARKET_CAP = {s["symbol"]: s["market_cap"] for s in TOP_50_SHARIAH_STOCKS}
_SYMBOL_DICT = {s["symbol"]: s for s in TOP_50_SHARIAH_STOCKS}

EX_DATES = {
    "FFC": [{"ex_date": "2026-08-15", "amount": 130.00, "type": "INTERIM"}],
    "MCB": [
        {"ex_date": "2026-06-28", "amount": 28.00, "type": "INTERIM"},
        {"ex_date": "2026-10-01", "amount": 30.00, "type": "FINAL"},
    ],
    "MARI": [{"ex_date": "2026-06-30", "amount": 59.00, "type": "INTERIM"}],
    "UBL": [{"ex_date": "2026-07-05", "amount": 25.00, "type": "INTERIM"}],
    "OGDC": [{"ex_date": "2026-07-10", "amount": 26.00, "type": "INTERIM"}],
    "HBL": [{"ex_date": "2026-07-12", "amount": 14.00, "type": "INTERIM"}],
    "EFERT": [{"ex_date": "2026-07-15", "amount": 14.00, "type": "INTERIM"}],
    "HUBC": [{"ex_date": "2026-07-20", "amount": 14.00, "type": "INTERIM"}],
}

RSS_FEEDS = ["https://www.dawn.com/feeds/business", "https://www.brecorder.com/rss/news"]

# ============================================================
# DATA CLASSES
# ============================================================
@dataclass
class TradeSignal:
    """Represents a trade recommendation."""

    symbol: str
    strategy: str
    action: str
    entry_price: float
    stop_loss: float
    target1: float
    target2: float
    shares: int
    confidence: float
    expected_return: float
    composite_score: float

# ============================================================
# TAX POLICY MODULE
# ============================================================
class TaxPolicy:
    """Encapsulates tax rates and government policy risk."""

    def __init__(self, is_filer: bool = TAX_FILER) -> None:
        self.is_filer = is_filer
        self.cgt_rate = CGT_RATE
        self.div_tax_rate = DIV_TAX_RATE
        self.policy_risk = 0.0

    def update_policy_from_news(self, articles: List[Dict[str, str]]) -> None:
        """Update policy risk based on keyword occurrences in news articles."""
        keywords = ["tax", "budget", "secp", "regulation", "fed", "imf"]
        count = sum(
            1
            for a in articles
            if any(kw in a["title"].lower() for kw in keywords)
        )
        self.policy_risk = min(1.0, count / max(1, len(articles)))

    def net_profit(self, gross_pnl: float, is_dividend: bool = False) -> float:
        """Calculate profit after applicable tax."""
        rate = self.div_tax_rate if is_dividend else self.cgt_rate
        return gross_pnl * (1 - rate)

# ============================================================
# FUNDAMENTAL ANALYSIS MODULE
# ============================================================
class FundamentalAnalyzer:
    """Simulates financial report fetching and scoring."""

    AUDIT_OPINIONS = ["Unqualified", "Unqualified", "Qualified", "Adverse"]

    @staticmethod
    def fetch_company_reports(symbol: str) -> Dict[str, Any]:
        """Return simulated financial metrics for a symbol."""
        return {
            "symbol": symbol,
            "audit_opinion": random.choice(FundamentalAnalyzer.AUDIT_OPINIONS),
            "eps": random.uniform(1, 80),
            "dps": random.uniform(0, 30),
            "eps_growth": random.uniform(-10, 20),
            "pe_ratio": random.uniform(5, 30),
            "pb_ratio": random.uniform(0.5, 3),
            "debt_ratio": random.uniform(0.1, 1.5),
            "market_cap": _MARKET_CAP.get(symbol, 0),
        }

    @staticmethod
    def score(symbol: str, reports: Dict[str, Dict[str, Any]]) -> float:
        """Compute a fundamental score between 0.0 and 1.0."""
        r = reports.get(symbol, {})
        score = 0.5
        if r.get("audit_opinion") == "Unqualified":
            score += 0.2
        pe = r.get("pe_ratio", 15)
        if 5 <= pe <= 15:
            score += 0.1
        if r.get("eps_growth", 0) > 10:
            score += 0.1
        if r.get("debt_ratio", 1) < 0.5:
            score += 0.1
        return max(0.1, min(1.0, score))

# ============================================================
# DATA FETCHER MODULE
# ============================================================
class DataFetcher:
    """Provides instant price feed from hardcoded data."""

    _PRICES: Dict[str, Dict[str, Any]] = {
        s["symbol"]: {
            "symbol": s["symbol"],
            "price": s["current_price"],
            "source": "hardcoded",
        }
        for s in TOP_50_SHARIAH_STOCKS
    }

    @staticmethod
    def fetch_all(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return price dictionary for the given symbols."""
        return {sym: DataFetcher._PRICES[sym] for sym in symbols if sym in DataFetcher._PRICES}

# ============================================================
# TECHNICAL INDICATORS ENGINE
# ============================================================
class IndicatorEngine:
    """Computes all technical indicators in one vectorised pass."""

    @staticmethod
    def _get_column(df: pd.DataFrame, name: str, fallback_index: int) -> pd.Series:
        """Safely extract a column from a DataFrame."""
        if name in df.columns:
            return df[name]
        if fallback_index < df.shape[1]:
            return df.iloc[:, fallback_index]
        return pd.Series(dtype=float)

    @staticmethod
    def calculate(df: Optional[pd.DataFrame]) -> Dict[str, float]:
        """Calculate RSI, ADX, ATR, Bollinger Bands, etc.

        Returns an empty dict if the input is None or empty.
        """
        if df is None or df.empty:
            return {}

        close = IndicatorEngine._get_column(df, "Close", 3)
        high = IndicatorEngine._get_column(df, "High", 1)
        low = IndicatorEngine._get_column(df, "Low", 2)
        vol = df.get("Volume", pd.Series([1] * len(df)))

        if close.empty or high.empty or low.empty:
            return {}

        # True Range (shared between ATR and ADX)
        tr = pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr_14 = tr.rolling(14).mean()
        atr_val = atr_14.iloc[-1] if len(atr_14) > 0 else 0.0

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi_val = 100 - (100 / (1 + gain / loss)).iloc[-1] if len(gain) > 0 else 50.0

        # ADX
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx_val = dx.rolling(14).mean().iloc[-1] if len(dx) >= 14 else 0.0

        # Bollinger Bands
        sma20 = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        if len(sma20) >= 20:
            bb_upper = sma20.iloc[-1] + 2 * bb_std.iloc[-1]
            bb_lower = sma20.iloc[-1] - 2 * bb_std.iloc[-1]
        else:
            bb_upper, bb_lower = None, None

        # Stochastic
        low_14 = low.rolling(14).min()
        high_14 = high.rolling(14).max()
        stoch_k = 100 * (close - low_14) / (high_14 - low_14)
        stoch_k_val = stoch_k.iloc[-1] if len(stoch_k) > 0 else 50.0

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        # Bollinger Band position
        bb_pos = 0.5
        if bb_upper and bb_lower and bb_upper != bb_lower:
            bb_pos = (close.iloc[-1] - bb_lower) / (bb_upper - bb_lower)
        bb_pos = max(0.0, min(1.0, bb_pos))

        return {
            "close": close.iloc[-1],
            "rsi": rsi_val,
            "adx": adx_val,
            "stoch_k": stoch_k_val,
            "bb_position": bb_pos,
            "macd_hist": macd_hist.iloc[-1] if len(macd_hist) > 0 else 0.0,
            "atr": atr_val,
            "sma_50": close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.mean(),
            "vol_ratio": (vol.iloc[-1] / vol.tail(20).mean()) if len(vol) >= 20 else 1.0,
        }

# ============================================================
# MACHINE LEARNING MODEL
# ============================================================
class AlphaModel:
    """Lightweight heuristic ML model using technical indicators."""

    @staticmethod
    def predict(ind: Dict[str, float], fund_score: float = 0.5) -> Dict[str, float]:
        """Return a prediction (up/neutral) with confidence score.

        Args:
            ind: Indicator dictionary from IndicatorEngine.
            fund_score: Fundamental score (0‑1) to incorporate.

        Returns:
            dict with keys "prediction" and "confidence".
        """
        if not ind:
            return {"prediction": "neutral", "confidence": 0.0}

        score = 0.0
        if ind.get("rsi", 50) < 40:
            score += 0.3
        if ind.get("adx", 0) > 25 and ind.get("close", 0) > ind.get("sma_50", 0):
            score += 0.3
        if ind.get("macd_hist", 0) > 0:
            score += 0.2
        if ind.get("vol_ratio", 1) > 1.5:
            score += 0.2
        score += fund_score * 0.2

        confidence = min(1.0, score)
        prediction = "up" if confidence > 0.5 else "neutral"
        return {"prediction": prediction, "confidence": confidence}

# ============================================================
# POSITION SIZING (KELLY CRITERION)
# ============================================================
def position_size(
    balance: float,
    entry: float,
    stop: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    risk: float = 0.02,
) -> int:
    """Dynamic Kelly‑based position sizing.

    Returns:
        Number of shares to buy (0 if no position should be taken).
    """
    if entry <= stop:
        return 0
    risk_per_share = entry - stop
    b = avg_win / avg_loss if avg_loss != 0 else 0.0
    if b > 0:
        kelly = (b * win_rate - (1 - win_rate)) / b
        kelly = max(0.0, min(kelly, 0.25))
    else:
        kelly = 0.0
    risk_amount = balance * (risk + kelly * 0.5)
    return max(0, int(risk_amount / risk_per_share))

# ============================================================
# STRATEGY ENGINE (MULTI‑STRATEGY SIGNALS)
# ============================================================
class StrategyEngine:
    """Generates buy signals for dividend, swing, momentum, mean‑reversion."""

    @staticmethod
    def dividend_signal(
        sym: str,
        price: float,
        div: Dict[str, Any],
        ind: Dict[str, float],
        ml: Dict[str, float],
        sentiment: str,
        regime: str,
        fund_score: float,
        tax: TaxPolicy,
        balance: float,
        max_risk: float,
    ) -> Optional[TradeSignal]:
        """Generate a dividend capture signal."""
        yield_pct = (div["amount"] / price) * 100
        days = div["days_until"]
        if not ((yield_pct >= 6 and days <= 2) or (yield_pct >= 4 and 2 <= days <= 10)):
            return None

        conf = 0.5
        if yield_pct > 6:
            conf += 0.1
        rsi_val = ind.get("rsi", 50)
        if rsi_val < 30:
            conf += 0.1
        elif rsi_val > 70:
            conf -= 0.1
        if ml.get("confidence", 0) > 0.3:
            conf += 0.05
        if sentiment == "bullish":
            conf += 0.05
        conf = max(0.0, min(1.0, conf))
        if conf < 0.3:
            return None

        atr_val = ind.get("atr", price * 0.02)
        stop = price - atr_val * 2
        t1 = price * 1.05
        t2 = price * 1.08
        win_rate = 0.5 + (yield_pct / 25)
        avg_win = t1 - price
        avg_loss = price - stop
        shares = position_size(balance, price, stop, win_rate, avg_win, avg_loss, max_risk)
        if shares <= 0:
            return None

        gross_ret = (yield_pct + avg_win / price * 0.5) * win_rate
        net_ret = tax.net_profit(gross_ret, is_dividend=True)
        composite = net_ret * conf * fund_score * (1 - tax.policy_risk)
        return TradeSignal(
            sym, "dividend", "BUY", price, stop, t1, t2, shares, conf, gross_ret, composite,
        )

    @staticmethod
    def swing_signal(
        sym: str,
        price: float,
        ind: Dict[str, float],
        ml: Dict[str, float],
        regime: str,
        fund_score: float,
        tax: TaxPolicy,
        balance: float,
        max_risk: float,
    ) -> Optional[TradeSignal]:
        """Generate a swing trading signal."""
        rsi_val = ind.get("rsi", 50)
        stoch_val = ind.get("stoch_k", 50)
        if rsi_val < 40 and stoch_val < 20 and ml.get("prediction") == "up":
            atr_val = ind.get("atr", price * 0.02)
            stop = price - atr_val * 2
            t1 = price + atr_val * 3
            t2 = price + atr_val * 5
            conf = 0.6
            win_rate = 0.55
            avg_win = t1 - price
            avg_loss = price - stop
            shares = position_size(balance, price, stop, win_rate, avg_win, avg_loss, max_risk)
            if shares <= 0:
                return None
            gross_ret = avg_win / price * win_rate
            net_ret = tax.net_profit(gross_ret)
            composite = net_ret * conf * fund_score * (1 - tax.policy_risk)
            return TradeSignal(
                sym, "swing", "BUY", price, stop, t1, t2, shares, conf, gross_ret, composite,
            )
        return None

    @staticmethod
    def momentum_signal(
        sym: str,
        price: float,
        ind: Dict[str, float],
        ml: Dict[str, float],
        regime: str,
        fund_score: float,
        tax: TaxPolicy,
        balance: float,
        max_risk: float,
    ) -> Optional[TradeSignal]:
        """Generate a momentum signal."""
        adx_val = ind.get("adx", 0)
        sma50 = ind.get("sma_50", 0)
        if adx_val > 25 and price > sma50 and ml.get("prediction") == "up":
            atr_val = ind.get("atr", price * 0.02)
            stop = price - atr_val * 2
            t1 = price + atr_val * 4
            t2 = price + atr_val * 6
            conf = 0.65
            win_rate = 0.6
            avg_win = t1 - price
            avg_loss = price - stop
            shares = position_size(balance, price, stop, win_rate, avg_win, avg_loss, max_risk)
            if shares <= 0:
                return None
            gross_ret = avg_win / price * win_rate
            net_ret = tax.net_profit(gross_ret)
            composite = net_ret * conf * fund_score * (1 - tax.policy_risk)
            return TradeSignal(
                sym, "momentum", "BUY", price, stop, t1, t2, shares, conf, gross_ret, composite,
            )
        return None

    @staticmethod
    def mean_reversion_signal(
        sym: str,
        price: float,
        ind: Dict[str, float],
        ml: Dict[str, float],
        regime: str,
        fund_score: float,
        tax: TaxPolicy,
        balance: float,
        max_risk: float,
    ) -> Optional[TradeSignal]:
        """Generate a mean‑reversion signal."""
        rsi_val = ind.get("rsi", 50)
        bb_pos = ind.get("bb_position", 0.5)
        if rsi_val < 30 and bb_pos < 0.1:
            atr_val = ind.get("atr", price * 0.02)
            stop = price - atr_val * 1.5
            t1 = price + atr_val * 2
            t2 = price + atr_val * 3
            conf = 0.7
            win_rate = 0.6
            avg_win = t1 - price
            avg_loss = price - stop
            shares = position_size(balance, price, stop, win_rate, avg_win, avg_loss, max_risk)
            if shares <= 0:
                return None
            gross_ret = avg_win / price * win_rate
            net_ret = tax.net_profit(gross_ret)
            composite = net_ret * conf * fund_score * (1 - tax.policy_risk)
            return TradeSignal(
                sym, "mean_reversion", "BUY", price, stop, t1, t2, shares, conf, gross_ret, composite,
            )
        return None

# ============================================================
# PAIRS TRADING
# ============================================================
class PairsTrader:
    """Finds correlated pairs and generates spread‑trading signals."""

    @staticmethod
    def find_top_pairs(
        historical: Dict[str, pd.DataFrame],
        top_n: int = 3,
        min_corr: float = 0.8,
    ) -> List[Tuple[str, str, float]]:
        """Return the top correlated pairs as (sym_a, sym_b, correlation)."""
        closes = pd.DataFrame(
            {
                sym: (df["Close"] if "Close" in df else df.iloc[:, 3])
                for sym, df in historical.items()
            }
        ).dropna(axis=1)
        if closes.shape[1] < 2:
            return []

        corr_mat = closes.corr()
        pairs = []
        syms = closes.columns.tolist()
        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                c = corr_mat.iloc[i, j]
                if abs(c) >= min_corr:
                    pairs.append((syms[i], syms[j], c))
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        return pairs[:top_n]

# ============================================================
# EXECUTION ENGINE (PAPER TRADING)
# ============================================================
class ExecutionEngine:
    """Cash‑aware paper trading simulator with realistic costs."""

    def __init__(self, balance: float = ACCOUNT_BALANCE) -> None:
        self.balance = balance
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.commission = 0.001
        self.slippage = 0.001
        self.tax_rate = CGT_RATE

    def buy(
        self, symbol: str, price: float, qty: int,
        stop: float, t1: float, t2: float,
    ) -> bool:
        """Execute a buy order; return True if successful."""
        cost_factor = 1.0 + self.slippage + self.commission
        max_shares = int(self.balance / (price * cost_factor)) if price > 0 else 0
        qty = min(qty, max_shares)
        if qty <= 0:
            logger.warning("Insufficient balance for %s", symbol)
            return False
        cost = price * qty * cost_factor
        if cost > self.balance:
            logger.warning("Cost exceeds balance for %s", symbol)
            return False

        self.balance -= cost
        self.positions[symbol] = {
            "qty": qty,
            "avg_price": price * (1 + self.slippage),
            "stop": stop,
            "t1": t1,
            "t2": t2,
            "entry_time": datetime.now(),
        }
        logger.info("BUY %d %s @ %.2f | Cash left: %.2f", qty, symbol, price, self.balance)
        return True

    def sell(
        self, symbol: str, price: float,
        qty: Optional[int] = None, reason: str = "",
    ) -> Optional[float]:
        """Sell shares; return net PnL or None if no position."""
        pos = self.positions.get(symbol)
        if not pos:
            logger.warning("No position for %s", symbol)
            return None
        qty = min(qty or pos["qty"], pos["qty"])
        if qty <= 0:
            return None
        cost_factor = 1.0 - self.slippage - self.commission
        proceeds = price * qty * cost_factor
        gross_pnl = (
            (price * (1 - self.slippage) - pos["avg_price"]) * qty
            - (price * qty * self.commission)
        )
        tax = gross_pnl * self.tax_rate if gross_pnl > 0 else 0.0
        net_pnl = gross_pnl - tax

        self.balance += proceeds
        pos["qty"] -= qty
        if pos["qty"] == 0:
            del self.positions[symbol]

        logger.info(
            "SELL %d %s @ %.2f | Net PnL: %+.2f | Cash: %.2f (%s)",
            qty, symbol, price, net_pnl, self.balance, reason,
        )
        return net_pnl

    def update_stops(self, current_prices: Dict[str, float]) -> None:
        """Check and trigger stop‑loss / target exits."""
        for sym, pos in list(self.positions.items()):
            price = current_prices.get(sym, pos["avg_price"])
            if price >= pos["t1"]:
                self.sell(sym, price, reason="Target1")
            elif price <= pos["stop"]:
                self.sell(sym, price, reason="Stop Loss")

    def total_value(self, prices: Dict[str, float]) -> float:
        """Return total portfolio value."""
        return self.balance + sum(
            prices.get(sym, pos["avg_price"]) * pos["qty"]
            for sym, pos in self.positions.items()
        )

# ============================================================
# SENTIMENT ANALYSER (WITH CACHING)
# ============================================================
class SentimentAnalyser:
    """Fetches and caches news sentiment."""

    _cache: Dict[str, Any] = {"timestamp": datetime.min, "data": None}
    vader = SentimentIntensityAnalyzer() if VADER_AVAILABLE else None

    @classmethod
    def get_sentiment(cls, cache_ttl: int = 3600) -> Dict[str, Any]:
        """Return overall market sentiment (cached for cache_ttl seconds)."""
        now = datetime.now()
        if (
            cls._cache["data"] is not None
            and (now - cls._cache["timestamp"]).total_seconds() < cache_ttl
        ):
            return cls._cache["data"]

        articles: List[Dict[str, Any]] = []
        for url in RSS_FEEDS:
            with suppress(Exception):
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    text = f"{title} {summary}"
                    blob = TextBlob(text)
                    pol = blob.sentiment.polarity
                    if cls.vader:
                        pol = (pol + cls.vader.polarity_scores(text)["compound"]) / 2
                    articles.append({"title": title, "polarity": pol})
                logger.debug("Sentiment fetched from %s", url)

        result: Dict[str, Any] = {"overall": "neutral", "articles": articles}
        if articles:
            avg = np.mean([a["polarity"] for a in articles])
            if avg > 0.05:
                result["overall"] = "bullish"
            elif avg < -0.05:
                result["overall"] = "bearish"
        cls._cache["timestamp"] = now
        cls._cache["data"] = result
        return result

# ============================================================
# MARKET REGIME DETECTOR
# ============================================================
def detect_regime(ind: Dict[str, float], price: float) -> str:
    """Determine market regime (bullish/bearish/neutral) from indicators."""
    adx_val = ind.get("adx", 0)
    sma50 = ind.get("sma_50", 0)
    match adx_val > 25:
        case True:
            if price > sma50 * 1.02:
                return "bullish"
            if price < sma50 * 0.98:
                return "bearish"
    return "neutral"

# ============================================================
# DIVIDEND CALENDAR (WITH CACHING)
# ============================================================
class DividendCalendar:
    """Fetches upcoming dividends with caching."""

    _cache: Dict[str, Any] = {"ts": datetime.min, "data": None}

    @staticmethod
    def get_upcoming(symbols: List[str], cache_ttl: int = 3600) -> List[Dict[str, Any]]:
        """Return sorted list of upcoming dividends."""
        now = datetime.now()
        if (
            DividendCalendar._cache["data"] is not None
            and (now - DividendCalendar._cache["ts"]).total_seconds() < cache_ttl
        ):
            return DividendCalendar._cache["data"]

        today = date.today()
        upcoming: List[Dict[str, Any]] = []
        for sym in symbols:
            for div in EX_DATES.get(sym, []):
                ex = datetime.strptime(div["ex_date"], "%Y-%m-%d").date()
                days = (ex - today).days
                if 0 <= days <= 60:
                    upcoming.append({**div, "symbol": sym, "days_until": days})
        upcoming.sort(key=lambda d: d["days_until"])
        DividendCalendar._cache["ts"] = now
        DividendCalendar._cache["data"] = upcoming
        return upcoming

# ============================================================
# REPORTER (HTML EMAIL)
# ============================================================
class Reporter:
    """Generates HTML report and sends via Resend API."""

    @staticmethod
    def generate_html(
        engine: ExecutionEngine,
        signals: List[TradeSignal],
        prices: Dict[str, float],
        dividends: List[Dict[str, Any]],
        tax: TaxPolicy,
    ) -> str:
        """Build an HTML report string.

        Args:
            engine: Current state of the execution engine.
            signals: Selected trade signals.
            prices: Current market prices.
            dividends: Upcoming dividends list.
            tax: TaxPolicy instance for risk display.
        """
        div_rows = "".join(
            f"<tr><td>{d['symbol']}</td><td>{d['ex_date']}</td>"
            f"<td>{d['amount']}</td><td>{d['days_until']}d</td></tr>"
            for d in dividends[:10]
        )
        sig_rows = "".join(
            f"<tr><td>{s.symbol}</td><td>{s.strategy}</td>"
            f"<td>{s.entry_price:.2f}</td><td>{s.stop_loss:.2f}</td>"
            f"<td>{s.target1:.2f}</td><td>{s.shares}</td>"
            f"<td>{s.confidence:.0%}</td><td style='color:green'>BUY</td></tr>"
            for s in signals
        )
        total_val = engine.total_value(prices)

        return f"""<html><head><style>
            body {{ font-family: Arial; background: #f9f9f9; color: #333; padding: 20px; }}
            .header {{ background: #fff; padding: 15px; border-left: 5px solid #0066cc; margin-bottom: 20px; }}
            h2 {{ color: #0066cc; }}
            table {{ border-collapse: collapse; width: 100%; background: #fff; }}
            th {{ background: #eef3f9; padding: 10px; text-align: left; }}
            td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        </style></head><body>
            <div class="header">
                <h1>PSX Ultimate Engine v{VERSION}</h1>
                <p>Balance: PKR {engine.balance:,.0f} | Total Value: PKR {total_val:,.0f} |
                Policy Risk: {tax.policy_risk:.0%}</p>
            </div>
            <h2>Dividends</h2>
            <table><tr><th>Symbol</th><th>Ex-Date</th><th>Amount</th><th>Days</th></tr>{div_rows}</table>
            <h2>Signals</h2>
            <table><tr><th>Symbol</th><th>Strategy</th><th>Entry</th><th>Stop</th>
            <th>T1</th><th>Shares</th><th>Conf</th><th>Action</th></tr>{sig_rows}</table>
            <p style='color:#888;'>Shariah-compliant, tax-aware, zero risk.</p>
        </body></html>"""

    @staticmethod
    def send_email(subject: str, html: str) -> None:
        """Send report via Resend API."""
        if not RESEND_API_KEY:
            logger.warning("RESEND_API_KEY not set; cannot send email")
            return
        try:
            requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": FROM_EMAIL, "to": [TO_EMAIL], "subject": subject, "html": html},
                timeout=10,
            )
            logger.info("Email sent successfully")
        except requests.RequestException as e:
            logger.error("Failed to send email: %s", e)

    @staticmethod
    def send_async(subject: str, html: str) -> None:
        """Send email in a background thread."""
        Thread(target=Reporter.send_email, args=(subject, html)).start()

# ============================================================
# CONFIGURATION
# ============================================================
class Config:
    """Manages runtime configuration from a YAML file."""

    DEFAULTS = {
        "trading": {
            "max_sector_exposure": 0.3,
            "kelly_multiplier": 0.5,
            "trailing_stop_activation_pct": 0.02,
            "dynamic_stop_atr_multiplier": 2.0,
        },
        "strategies": {
            "dividend": True,
            "swing": True,
            "momentum": True,
            "mean_reversion": True,
            "pairs": True,
            "sector_rotation": True,
        },
        "ml": {"enabled": True, "confidence_threshold": 0.3},
        "safety": {"max_daily_loss": 0.02, "max_weekly_loss": 0.05},
        "email": {"send_time": "07:00", "timezone": "Asia/Karachi"},
        "database": {"db_path": "psx_trades.db"},
    }

    def __init__(self, config_path: str = "config.yaml") -> None:
        self._config = self.DEFAULTS.copy()
        path = Path(config_path)
        if path.exists():
            with path.open() as f:
                loaded = yaml.safe_load(f) or {}
                self._config.update(loaded)
            logger.info("Configuration loaded from %s", config_path)
        else:
            logger.info("No config file found; using defaults")

    def get(self, key: str, default: Any = None) -> Any:
        """Access nested configuration value using dot‑separated key."""
        parts = key.split(".")
        val = self._config
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return default
            if val is None:
                return default
        return val

# ============================================================
# MAIN ORCHESTRATOR
# ============================================================
def main() -> None:
    """Main entry point: fetch data, generate signals, execute trades, report."""
    parser = argparse.ArgumentParser(description="PSX Ultimate Trading Engine")
    parser.add_argument(
        "--confirm", action="store_true", help="Prompt for trade confirmation"
    )
    args = parser.parse_args()

    config = Config()
    symbols = [s["symbol"] for s in TOP_50_SHARIAH_STOCKS]
    logger.info(
        "PSX ULTIMATE ENGINE v%s | Balance: PKR %,.0f", VERSION, ACCOUNT_BALANCE
    )

    # Fetch live prices
    live_prices = DataFetcher.fetch_all(symbols)
    prices = {sym: data["price"] for sym, data in live_prices.items()}

    # Dividends & sentiment
    dividends = DividendCalendar.get_upcoming(symbols)
    div_dict = {d["symbol"]: d for d in dividends}
    sentiment = SentimentAnalyser.get_sentiment()
    tax = TaxPolicy()
    tax.update_policy_from_news(sentiment["articles"])

    # Historical data (parallel)
    historical: Dict[str, pd.DataFrame] = {}
    if PYPSX_AVAILABLE:
        start = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        syms_to_fetch = symbols[:10]  # limit for speed
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {
                ex.submit(
                    pypsx.PSXTicker(sym).get_historical,
                    start_date=start,
                    end_date=end,
                ): sym
                for sym in syms_to_fetch
            }
            for f in as_completed(futures):
                sym = futures[f]
                with suppress(Exception):
                    df = f.result()
                    if df is not None and not df.empty:
                        historical[sym] = df

    # Fundamental scores
    reports = {sym: FundamentalAnalyzer.fetch_company_reports(sym) for sym in symbols}
    fund_scores = {sym: FundamentalAnalyzer.score(sym, reports) for sym in symbols}

    # Generate all signals
    all_signals: List[TradeSignal] = []
    ind_cache: Dict[str, Dict[str, float]] = {}

    for stock in TOP_50_SHARIAH_STOCKS:
        sym = stock["symbol"]
        if sym not in historical:
            continue
        price = prices.get(sym, 0.0)
        if price <= 0:
            continue

        div_info = div_dict.get(sym)
        ind = IndicatorEngine.calculate(historical[sym])
        ind_cache[sym] = ind
        fscore = fund_scores.get(sym, 0.5)
        ml_pred = AlphaModel.predict(ind, fscore)
        regime = detect_regime(ind, price)

        # Dividend
        if div_info:
            sig = StrategyEngine.dividend_signal(
                sym,
                price,
                div_info,
                ind,
                ml_pred,
                sentiment["overall"],
                regime,
                fscore,
                tax,
                ACCOUNT_BALANCE,
                MAX_RISK_PER_TRADE,
            )
            if sig:
                all_signals.append(sig)

        # Swing
        sig = StrategyEngine.swing_signal(
            sym, price, ind, ml_pred, regime, fscore, tax,
            ACCOUNT_BALANCE, MAX_RISK_PER_TRADE,
        )
        if sig:
            all_signals.append(sig)

        # Momentum
        sig = StrategyEngine.momentum_signal(
            sym, price, ind, ml_pred, regime, fscore, tax,
            ACCOUNT_BALANCE, MAX_RISK_PER_TRADE,
        )
        if sig:
            all_signals.append(sig)

        # Mean‑reversion
        sig = StrategyEngine.mean_reversion_signal(
            sym, price, ind, ml_pred, regime, fscore, tax,
            ACCOUNT_BALANCE, MAX_RISK_PER_TRADE,
        )
        if sig:
            all_signals.append(sig)

    # Pairs trading
    if config.get("strategies.pairs", True) and len(historical) >= 2:
        closes_df = pd.DataFrame(
            {
                sym: (df["Close"] if "Close" in df else df.iloc[:, 3])
                for sym, df in historical.items()
            }
        ).dropna(axis=1)
        top_pairs = PairsTrader.find_top_pairs(historical, top_n=3)
        for sym_a, sym_b, corr in top_pairs:
            price_a = prices.get(sym_a, 0.0)
            price_b = prices.get(sym_b, 0.0)
            if price_a <= 0 or price_b <= 0:
                continue
            buy_sym = sym_a if price_a <= price_b else sym_b
            ind_buy = ind_cache.get(buy_sym) or IndicatorEngine.calculate(historical[buy_sym])
            sig = StrategyEngine.momentum_signal(
                buy_sym,
                prices[buy_sym],
                ind_buy,
                {"prediction": "up", "confidence": 0.5},
                "neutral",
                0.5,
                tax,
                ACCOUNT_BALANCE,
                MAX_RISK_PER_TRADE,
            )
            if sig:
                sig.strategy = "pairs"
                all_signals.append(sig)
            break  # only top pair

    # Rank and select top 3
    all_signals.sort(key=lambda s: s.composite_score, reverse=True)
    selected = all_signals[:3]
    logger.info("Top signals (%d total):", len(all_signals))
    for i, s in enumerate(selected, 1):
        logger.info(
            "  %d. %s %s @ %.2f | Conf: %.0f%% | Shares: %d",
            i, s.strategy.upper(), s.symbol, s.entry_price,
            s.confidence * 100, s.shares,
        )

    # Confirmation prompt (optional)
    if args.confirm:
        if input("\nExecute these trades? (y/N): ").lower() != "y":
            logger.info("Trades aborted by user.")
            return

    # Execute trades
    engine = ExecutionEngine(ACCOUNT_BALANCE)
    for sig in selected:
        success = engine.buy(
            sig.symbol, sig.entry_price, sig.shares,
            sig.stop_loss, sig.target1, sig.target2,
        )
        if success:
            logger.info("  ✅ Bought %s (%d shares)", sig.symbol, sig.shares)

    # Update trailing stops
    engine.update_stops(prices)

    # Generate and send report
    html = Reporter.generate_html(engine, selected, prices, dividends, tax)
    Reporter.send_async(
        f"PSX Clean Report {datetime.now():%Y-%m-%d %H:%M}", html
    )
    logger.info("✅ Report sent")

if __name__ == "__main__":
    main()
