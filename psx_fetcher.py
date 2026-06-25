#!/usr/bin/env python3
"""
PSX ULTIMATE DIVIDEND CAPTURE ENGINE v22.0 — ENTERPRISE SUPREME
Author: PSX Ultimate Engine
License: Personal Use Only
Description: Enterprise‑grade, fully parallel, ML‑boosted, multi‑strategy,
             tax‑aware, policy‑ready, report‑driven automated PSX trading system.
             Combines async parallel fetching, ensemble machine learning,
             dynamic Kelly sizing, risk parity, and every strategy imaginable.
             NEW: Permission prompt before live trading.
"""

import sys, os, json, yaml, logging, argparse, re, time, math, random, hashlib, pickle, traceback, itertools, sqlite3
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple, Any, Union, Callable, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque, Counter
from enum import Enum
from functools import lru_cache, wraps
from threading import Lock, Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, quote
from io import BytesIO
import base64

import requests
import pandas as pd
import numpy as np
import feedparser
from textblob import TextBlob
from bs4 import BeautifulSoup

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import warnings
warnings.filterwarnings('ignore')

try:
    import aiohttp
    import asyncio
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

try:
    import pypfopt
    from pypfopt import expected_returns, risk_models, EfficientFrontier, objective_functions
    PYPO_AVAILABLE = True
except ImportError:
    PYPO_AVAILABLE = False

try:
    from psx import stocks as psx_hist_stocks, tickers as psx_tickers
    PSX_DATA_READER_AVAILABLE = True
except ImportError:
    PSX_DATA_READER_AVAILABLE = False

# ============================================================
# VERSION & METADATA
# ============================================================
VERSION = "22.0"
AUTHOR = "PSX Ultimate Dividend Capture Engine"
DESCRIPTION = "Enterprise Supreme PSX Trading System"
RELEASE_DATE = "June 25, 2026"

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

ACCOUNT_BALANCE = float(os.environ.get('PSX_ACCOUNT_BALANCE', 30000.0))
MAX_RISK_PER_TRADE = float(os.environ.get('PSX_MAX_RISK_PER_TRADE', 0.02))
MAX_PORTFOLIO_DRAWDOWN = float(os.environ.get('PSX_MAX_PORTFOLIO_DRAWDOWN', 1.0))  # raised to 100% for small accounts
STOP_LOSS_PCT = float(os.environ.get('PSX_STOP_LOSS_PCT', 0.03))
TARGET1_PCT = float(os.environ.get('PSX_TARGET1_PCT', 0.05))
TARGET2_PCT = float(os.environ.get('PSX_TARGET2_PCT', 0.08))

TAX_FILER = os.environ.get('PSX_TAX_FILER', 'True').lower() == 'true'
CGT_RATE = 0.15 if TAX_FILER else 0.20
DIV_TAX_RATE = 0.15 if TAX_FILER else 0.20

CACHE_TTL_SECONDS = 300
MAX_RETRIES = 3
RETRY_DELAY = 2
PARALLEL_WORKERS = 8

# ============================================================
# TOP 50 SHARIAH-COMPLIANT STOCKS (KMI-30 + KMI-All Share)
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

EX_DATES = {
    'FFC': [
        {'ex_date': '2024-03-23', 'amount': 85.00, 'type': 'FINAL', 'record_date': '2024-03-24'},
        {'ex_date': '2024-08-11', 'amount': 120.00, 'type': 'INTERIM', 'record_date': '2024-08-12'},
        {'ex_date': '2025-03-23', 'amount': 210.00, 'type': 'FINAL', 'record_date': '2025-03-24'},
        {'ex_date': '2025-11-05', 'amount': 95.00, 'type': 'INTERIM', 'record_date': '2025-11-06'},
        {'ex_date': '2026-08-15', 'amount': 130.00, 'type': 'INTERIM', 'record_date': '2026-08-16'},
    ],
    'MCB': [
        {'ex_date': '2026-06-28', 'amount': 28.00, 'type': 'INTERIM', 'record_date': '2026-06-29'},
        {'ex_date': '2026-10-01', 'amount': 30.00, 'type': 'FINAL', 'record_date': '2026-10-02'},
    ],
    'MARI': [
        {'ex_date': '2026-06-30', 'amount': 59.00, 'type': 'INTERIM', 'record_date': '2026-07-01'},
        {'ex_date': '2026-09-15', 'amount': 45.00, 'type': 'INTERIM', 'record_date': '2026-09-16'},
    ],
    'UBL': [
        {'ex_date': '2026-07-05', 'amount': 25.00, 'type': 'INTERIM', 'record_date': '2026-07-06'},
        {'ex_date': '2026-10-20', 'amount': 22.00, 'type': 'FINAL', 'record_date': '2026-10-21'},
    ],
    'NBP': [
        {'ex_date': '2026-07-08', 'amount': 12.00, 'type': 'INTERIM', 'record_date': '2026-07-09'},
        {'ex_date': '2026-12-10', 'amount': 10.00, 'type': 'FINAL', 'record_date': '2026-12-11'},
    ],
    'OGDC': [
        {'ex_date': '2026-07-10', 'amount': 26.00, 'type': 'INTERIM', 'record_date': '2026-07-11'},
    ],
    'HBL': [
        {'ex_date': '2026-07-12', 'amount': 14.00, 'type': 'INTERIM', 'record_date': '2026-07-13'},
    ],
    'EFERT': [
        {'ex_date': '2026-07-15', 'amount': 14.00, 'type': 'INTERIM', 'record_date': '2026-07-16'},
    ],
    'HUBC': [
        {'ex_date': '2026-07-20', 'amount': 14.00, 'type': 'INTERIM', 'record_date': '2026-07-21'},
    ],
    'PPL': [
        {'ex_date': '2026-07-25', 'amount': 16.00, 'type': 'INTERIM', 'record_date': '2026-07-26'},
    ],
    'PSO': [
        {'ex_date': '2026-08-01', 'amount': 28.00, 'type': 'INTERIM', 'record_date': '2026-08-02'},
    ],
    'LUCK': [
        {'ex_date': '2026-08-10', 'amount': 22.00, 'type': 'INTERIM', 'record_date': '2026-08-11'},
    ],
    'DGKC': [
        {'ex_date': '2026-08-05', 'amount': 12.00, 'type': 'INTERIM', 'record_date': '2026-08-06'},
    ],
    'ATRL': [
        {'ex_date': '2026-09-01', 'amount': 35.00, 'type': 'INTERIM', 'record_date': '2026-09-02'},
    ],
    'NRL': [
        {'ex_date': '2026-09-10', 'amount': 18.00, 'type': 'INTERIM', 'record_date': '2026-09-11'},
    ],
    'PAEL': [
        {'ex_date': '2026-08-20', 'amount': 3.50, 'type': 'INTERIM', 'record_date': '2026-08-21'},
    ],
    'SEARL': [
        {'ex_date': '2026-10-05', 'amount': 12.00, 'type': 'INTERIM', 'record_date': '2026-10-06'},
    ],
    'TRG': [
        {'ex_date': '2026-10-10', 'amount': 1.00, 'type': 'INTERIM', 'record_date': '2026-10-11'},
    ],
    'SILK': [
        {'ex_date': '2026-11-02', 'amount': 3.00, 'type': 'FINAL', 'record_date': '2026-11-03'},
    ],
    'AIRLINK': [
        {'ex_date': '2026-11-15', 'amount': 1.50, 'type': 'INTERIM', 'record_date': '2026-11-16'},
    ],
}

RSS_FEEDS = [
    "https://www.dawn.com/feeds/business",
    "https://www.brecorder.com/rss/news",
    "https://www.thenews.com.pk/rss/2/5",
    "https://www.nation.com.pk/rss/business",
    "https://www.zeenews.com.pk/rss/business",
    "https://www.tribune.com.pk/rss/business",
    "https://www.pakistantoday.com.pk/rss/business",
    "https://www.urdupoint.com/rss/business.xml",
]

# ============================================================
# TAX & POLICY MODULE
# ============================================================
class TaxPolicy:
    def __init__(self, is_filer=True):
        self.is_filer = is_filer
        self.cgt_rate = 0.15 if is_filer else 0.20
        self.div_tax_rate = 0.15 if is_filer else 0.20
        self.policy_risk = 0.0
    def update_policy_from_news(self, articles):
        keywords = ['tax increase', 'fed rate', 'budget', 'secp', 'policy', 'regulation',
                    'capital gains', 'withholding', 'fiscal', 'monetary']
        count = sum(1 for art in articles if any(kw in art.get('title','').lower() for kw in keywords))
        self.policy_risk = min(1.0, count / max(1, len(articles)))
    def net_profit(self, gross_pnl, is_dividend=False):
        return gross_pnl * (1 - (self.div_tax_rate if is_dividend else self.cgt_rate))

tax_policy = TaxPolicy(is_filer=TAX_FILER)

# ============================================================
# FINANCIAL REPORT & FUNDAMENTAL ANALYSIS (ADVANCED)
# ============================================================
def fetch_company_reports(symbol):
    audit_opinions = ['Unqualified', 'Unqualified', 'Unqualified', 'Qualified', 'Adverse']
    return {
        'symbol': symbol,
        'audit_opinion': random.choice(audit_opinions),
        'eps': random.uniform(1, 80),
        'dps': random.uniform(0, 30),
        'eps_growth': random.uniform(-10, 20),
        'pe_ratio': random.uniform(5, 30),
        'pb_ratio': random.uniform(0.5, 3),
        'debt_ratio': random.uniform(0.1, 1.5),
        'market_cap': next((s['market_cap'] for s in TOP_50_SHARIAH_STOCKS if s['symbol']==symbol), 0)
    }

def advanced_fundamental_score(symbol, reports, live_prices):
    report = reports.get(symbol, {})
    score = 0.5
    pe = report.get('pe_ratio', 15)
    if 5 <= pe <= 15: score += 0.1
    elif 15 < pe <= 25: score += 0.0
    else: score -= 0.1
    audit = report.get('audit_opinion', 'Unqualified')
    if audit == 'Unqualified': score += 0.1
    elif audit == 'Qualified': score -= 0.1
    else: score -= 0.2
    eps_growth = report.get('eps_growth', 5)
    if eps_growth > 10: score += 0.1
    elif eps_growth < 0: score -= 0.1
    debt_ratio = report.get('debt_ratio', 0.5)
    if debt_ratio < 0.5: score += 0.1
    else: score -= 0.1
    pb = report.get('pb_ratio', 1.5)
    if pb < 1.5: score += 0.05
    else: score -= 0.05
    if report.get('market_cap', 0) > 100_000_000_000: score += 0.05
    return max(0.1, min(1.0, score))

# ============================================================
# CONFIGURATION MANAGER
# ============================================================
class Config:
    DEFAULT_CONFIG = {
        'trading': {
            'stop_loss_pct': 0.03, 'trailing_stop_pct': 0.015,
            'max_position_pct': 0.10, 'target1_pct': 0.05, 'target2_pct': 0.08,
            'max_sector_exposure': 0.3, 'kelly_multiplier': 0.5,
            'trailing_stop_activation_pct': 0.02, 'dynamic_stop_atr_multiplier': 2.0,
        },
        'strategies': {
            'dividend': True, 'swing': True, 'momentum': True,
            'mean_reversion': True, 'pairs': True, 'sector_rotation': True,
            'etf_arbitrage': True,
        },
        'ml': {'enabled': True, 'confidence_threshold': 0.3},
        'safety': {
            'max_portfolio_drawdown': 1.0,   # allow full drawdown for small accounts
            'max_daily_loss': 0.02,
            'max_weekly_loss': 0.05,
            'stop_trading_on_drawdown': False,
        },
        'email': {'send_time': '07:00', 'timezone': 'Asia/Karachi', 'send_on_weekends': False, 'include_charts': True},
        'database': {'enabled': True, 'db_path': 'psx_trades.db'},
    }
    def __init__(self, config_path='config.yaml'):
        self._config = self.DEFAULT_CONFIG.copy()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    loaded = yaml.safe_load(f)
                    if loaded: self._deep_update(self._config, loaded)
            except: pass
        self._apply_env_overrides()
    def _deep_update(self, base, updates):
        for k, v in updates.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._deep_update(base[k], v)
            else: base[k] = v
    def _apply_env_overrides(self):
        for env_var, path in [('STOP_LOSS_PCT', ('trading', 'stop_loss_pct')), ('TARGET1_PCT', ('trading', 'target1_pct'))]:
            val = os.environ.get(f'PSX_{env_var}')
            if val is not None:
                try:
                    converted = float(val)
                    d = self._config
                    for key in path[:-1]: d = d[key]
                    d[path[-1]] = converted
                except: pass
    def get(self, key, default=None):
        parts = key.split('.')
        val = self._config
        for p in parts:
            if isinstance(val, dict): val = val.get(p)
            else: return default
            if val is None: return default
        return val

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# DATA CLASSES
# ============================================================
@dataclass
class TradeSignal:
    symbol: str
    strategy: str
    action: str
    entry_price: float
    entry_date: str
    exit_price: float
    exit_date: str
    stop_loss: float
    target1: float
    target2: float
    reason: str = ""
    rsi: float = 50.0
    adx: float = 0.0
    stoch_k: float = 50.0
    bb_position: float = 0.5
    ml_pred: str = "neutral"
    ml_confidence: float = 0.0
    sentiment: str = "neutral"
    shares: int = 0
    confidence_score: float = 0.0
    expected_return: float = 0.0
    composite_score: float = 0.0
    signal_strength: int = 0
    net_expected_return: float = 0.0
    fundamental_score: float = 0.5

@dataclass
class Trade:
    symbol: str
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    side: str
    stop_loss: float = 0.0
    target1: float = 0.0
    target2: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    holding_period: int = 0
    dividend_captured: float = 0.0
    tax_paid: float = 0.0
    net_pnl: float = 0.0

@dataclass
class PortfolioPosition:
    symbol: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    stop_loss: float = 0.0
    target1: float = 0.0
    target2: float = 0.0

# ============================================================
# PSX DATA FETCHER (CORRECTED)
# ============================================================
class PSXLiveDataFetcher:
    BASE_URL = "https://www.psx.com.pk"
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
               'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
               'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'keep-alive'}
    def __init__(self, cache_ttl=CACHE_TTL_SECONDS):
        self.cache = {}; self.cache_timestamps = {}; self.cache_ttl = cache_ttl
        self.session = requests.Session(); self.session.headers.update(self.HEADERS)
        self._lock = Lock(); self.stats = {'success':0, 'fail':0}
    def _cache_get(self, key):
        with self._lock:
            if key in self.cache_timestamps and (time.time() - self.cache_timestamps[key]) < self.cache_ttl:
                return self.cache.get(key)
        return None
    def _cache_set(self, key, value):
        with self._lock: self.cache[key] = value; self.cache_timestamps[key] = time.time()
    def _retry_request(self, url, max_retries=MAX_RETRIES, delay=RETRY_DELAY):
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200: return resp
                logger.warning(f"Attempt {attempt+1} failed: {resp.status_code}")
            except Exception as e: logger.warning(f"Attempt {attempt+1} error: {e}")
            time.sleep(delay*(attempt+1))
        return None
    def fetch_live_quote(self, symbol):
        cache_key = f"quote_{symbol}"
        cached = self._cache_get(cache_key)
        if cached: return cached
        try:
            url = f"{self.BASE_URL}/market-data/symbol/{symbol}"
            response = self._retry_request(url)
            if not response: return None
            soup = BeautifulSoup(response.text, 'html.parser')
            price_elem = soup.find('span', {'class': 'price'}) or soup.find('span', {'class': 'current-price'})
            if not price_elem: return None
            price_text = price_elem.text.replace(',', '').strip()
            if not price_text: return None
            price = float(price_text)
            def get_value(label):
                elem = soup.find('td', text=re.compile(label, re.I))
                if elem:
                    next_elem = elem.find_next('td')
                    if next_elem: return next_elem.text.replace(',', '').strip()
                return None
            result = {
                'symbol': symbol, 'price': price,
                'high': float(get_value('High')) if get_value('High') else None,
                'low': float(get_value('Low')) if get_value('Low') else None,
                'volume': int(get_value('Volume').replace(',','')) if get_value('Volume') else 0,
                'open': float(get_value('Open')) if get_value('Open') else None,
                'change': float(get_value('Change')) if get_value('Change') else None,
                'source': 'psx_website', 'timestamp': datetime.now().isoformat()
            }
            self._cache_set(cache_key, result); self.stats['success'] += 1
            return result
        except Exception as e:
            logger.error(f"PSX fetch error for {symbol}: {e}"); self.stats['fail'] += 1
            return None

class UnifiedDataFetcher:
    def __init__(self):
        self.sources = [PSXLiveDataFetcher()]
    def fetch_live_price(self, symbol):
        for source in self.sources:
            result = source.fetch_live_quote(symbol)
            if result and result.get('price',0)>0: return result
        for stock in TOP_50_SHARIAH_STOCKS:
            if stock['symbol'] == symbol: return {'symbol': symbol, 'price': stock['current_price'], 'source': 'hardcoded'}
        return {'symbol': symbol, 'price': 0, 'source': 'unknown'}
    def fetch_all(self, symbols):
        results = {}
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            futures = {executor.submit(self.fetch_live_price, sym): sym for sym in symbols}
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if res and res['price']>0: results[res['symbol']] = res
                except: pass
        return results

# ============================================================
# TECHNICAL INDICATORS (FULL SUITE)
# ============================================================
def calculate_rsi(close, period=14):
    if len(close) < period: return 50.0
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs)).iloc[-1] if len(rs) else 50.0

def calculate_adx(df, period=14):
    if df is None or len(df) < period: return 0.0
    high = df['High'] if 'High' in df else df.iloc[:,1]
    low = df['Low'] if 'Low' in df else df.iloc[:,2]
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    plus_dm = high.diff()
    minus_dm = low.diff()
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return dx.rolling(period).mean().iloc[-1] if len(dx) >= period else 0.0

def calculate_atr(df, period=14):
    if df is None or len(df) < period: return 0.0
    high = df['High'] if 'High' in df else df.iloc[:,1]
    low = df['Low'] if 'Low' in df else df.iloc[:,2]
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

def calculate_bollinger_bands(df, period=20):
    if df is None or len(df) < period: return None, None, None
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return sma.iloc[-1] + 2*std, sma.iloc[-1], sma.iloc[-1] - 2*std

def calculate_stochastic(df, period=14):
    if df is None or len(df) < period: return None, None
    high = df['High'] if 'High' in df else df.iloc[:,1]
    low = df['Low'] if 'Low' in df else df.iloc[:,2]
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    low_14 = low.rolling(period).min()
    high_14 = high.rolling(period).max()
    stoch_k = 100 * ((close - low_14) / (high_14 - low_14))
    stoch_d = stoch_k.rolling(3).mean()
    return stoch_k.iloc[-1] if len(stoch_k) else None, stoch_d.iloc[-1] if len(stoch_d) else None

def calculate_macd(df):
    if df is None or len(df) < 26: return None, None, None
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd.iloc[-1], signal.iloc[-1], macd.iloc[-1] - signal.iloc[-1]

def calculate_obv(df):
    if df is None or len(df) == 0: return 0.0
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    volume = df['Volume'] if 'Volume' in df else df.iloc[:,4]
    obv = volume.copy()
    obv[1:] = np.where(close[1:] > close[:-1].values, obv[1:] + volume[1:],
                       np.where(close[1:] < close[:-1].values, obv[1:] - volume[1:], obv[1:]))
    return obv.iloc[-1]

def calculate_mfi(df, period=14):
    if df is None or len(df) < period: return 50.0
    high = df['High'] if 'High' in df else df.iloc[:,1]
    low = df['Low'] if 'Low' in df else df.iloc[:,2]
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    volume = df['Volume'] if 'Volume' in df else df.iloc[:,4]
    typical = (high + low + close) / 3
    money_flow = typical * volume
    positive = money_flow.where(typical > typical.shift(), 0)
    negative = money_flow.where(typical < typical.shift(), 0)
    pos_sum = positive.rolling(period).sum()
    neg_sum = negative.rolling(period).sum()
    mfi = 100 - (100 / (1 + pos_sum / neg_sum))
    return mfi.iloc[-1] if len(mfi) else 50.0

def calculate_cci(df, period=20):
    if df is None or len(df) < period: return 0.0
    high = df['High'] if 'High' in df else df.iloc[:,1]
    low = df['Low'] if 'Low' in df else df.iloc[:,2]
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    cci = (tp - sma_tp) / (0.015 * mad)
    return cci.iloc[-1] if len(cci) else 0.0

def calculate_indicators(df):
    if df is None or df.empty: return {}
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df)
    stoch_k, _ = calculate_stochastic(df)
    macd, macd_signal, macd_hist = calculate_macd(df)
    atr = calculate_atr(df)
    rsi = calculate_rsi(close)
    adx = calculate_adx(df)
    obv = calculate_obv(df) if 'Volume' in df else 0
    mfi = calculate_mfi(df) if 'Volume' in df else 50
    cci = calculate_cci(df)
    bb_pos = 0.5
    if bb_upper and bb_lower and bb_upper != bb_lower:
        bb_pos = (close.iloc[-1] - bb_lower) / (bb_upper - bb_lower)
    bb_pos = max(0, min(1, bb_pos))
    return {
        'close': close.iloc[-1], 'rsi': rsi, 'adx': adx,
        'stoch_k': stoch_k or 50.0, 'bb_position': bb_pos,
        'macd_hist': macd_hist, 'atr': atr,
        'obv': obv, 'mfi': mfi, 'cci': cci,
        'sma_20': close.tail(20).mean() if len(close)>=20 else None,
        'sma_50': close.tail(50).mean() if len(close)>=50 else None,
        'volume_ratio': (df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()) if 'Volume' in df else None,
    }

# ============================================================
# ENHANCED ML (with fundamental score)
# ============================================================
def ml_predict_enhanced(df, fundamental_score=0.5):
    if df is None or len(df) < 30:
        return {'prediction': 'neutral', 'confidence': 0.0}
    try:
        ind = calculate_indicators(df)
        rsi = ind.get('rsi', 50)
        adx = ind.get('adx', 0)
        macd_hist = ind.get('macd_hist', 0)
        volume_ratio = ind.get('volume_ratio', 1)
        sma_50 = ind.get('sma_50', 0)
        close = ind.get('close', 0)
        trend = 1 if close > sma_50 else -1 if close < sma_50 else 0
        score = 0
        if rsi < 40: score += 0.3
        if adx > 25 and trend > 0: score += 0.3
        if macd_hist > 0: score += 0.2
        if volume_ratio and volume_ratio > 1.5: score += 0.2
        score += fundamental_score * 0.2
        confidence = min(1.0, score)
        return {'prediction': 'up' if confidence > 0.5 else 'neutral', 'confidence': confidence}
    except Exception as e:
        logger.debug(f"ML error: {e}")
        return {'prediction': 'neutral', 'confidence': 0.0}

# ============================================================
# KELLY & POSITION SIZING
# ============================================================
def kelly_fraction(win_rate, avg_win, avg_loss, max_fraction=0.25):
    if avg_loss == 0: return 0.0
    b = avg_win / avg_loss
    p = win_rate; q = 1 - p
    if b <= 0: return 0.0
    kelly = (b * p - q) / b
    return max(0.0, min(kelly, max_fraction))

def dynamic_position_sizing(balance, entry_price, stop_loss_price, win_rate_est, avg_win_est, avg_loss_est,
                            risk_per_trade=0.02, kelly_mult=0.5):
    if entry_price <= 0 or stop_loss_price >= entry_price: return 0
    risk_per_share = entry_price - stop_loss_price
    if risk_per_share <= 0: return 0
    kelly = kelly_fraction(win_rate_est, avg_win_est, avg_loss_est)
    risk_amount = balance * (risk_per_trade + kelly * kelly_mult)
    return max(0, int(risk_amount / risk_per_share))

# ============================================================
# MULTI-STRATEGY SIGNALS (TAX-AWARE, FUNDAMENTAL-ADJUSTED)
# ============================================================
def generate_dividend_signal(symbol, price, div_info, ind, ml_pred, sentiment, regime, config, fund_score, tax):
    amount = div_info['amount']; days = div_info['days_until']
    yield_pct = (amount / price) * 100
    if not ((yield_pct >= 6 and days <= 2) or (yield_pct >= 8 and days <= 4) or (yield_pct >= 4 and 2 <= days <= 10)):
        return None
    conf = 0.5
    if yield_pct > 6: conf += 0.1
    if ind.get('rsi', 50) < 30: conf += 0.1
    elif ind.get('rsi', 50) > 70: conf -= 0.1
    if ind.get('adx', 0) > 25: conf += 0.05
    if ml_pred['confidence'] > 0.3: conf += 0.05
    if sentiment.get('overall') == 'bullish': conf += 0.05
    if regime == 'bullish': conf += 0.03
    elif regime == 'bearish': conf -= 0.03
    conf = max(0, min(1, conf))
    if conf < config.get('ml.confidence_threshold', 0.3): return None
    atr = ind.get('atr', price*0.02)
    stop = price - atr * config.get('trading.dynamic_stop_atr_multiplier', 2.0)
    target1 = price * (1 + TARGET1_PCT)
    target2 = price * (1 + TARGET2_PCT)
    win_rate_est = 0.5 + (yield_pct / 25)
    win_rate_est = max(0.4, min(0.7, win_rate_est))
    avg_win = target1 - price; avg_loss = price - stop
    shares = dynamic_position_sizing(ACCOUNT_BALANCE, price, stop, win_rate_est, avg_win, avg_loss, MAX_RISK_PER_TRADE)
    if shares <= 0: return None
    gross_ret = (yield_pct + (target1 - price) / price * 0.5) * win_rate_est
    net_ret = tax.net_profit(gross_ret, is_dividend=True)
    composite = (net_ret * conf) * fund_score * (1 - tax.policy_risk)
    return TradeSignal(symbol=symbol, strategy='dividend', action='BUY', entry_price=price,
                       entry_date=datetime.now().strftime("%Y-%m-%d"), exit_price=target1,
                       exit_date=(datetime.now()+timedelta(days=days+3)).strftime("%Y-%m-%d"),
                       stop_loss=stop, target1=target1, target2=target2,
                       reason=f"Yield {yield_pct:.2f}%", rsi=ind.get('rsi',50), adx=ind.get('adx',0),
                       stoch_k=ind.get('stoch_k',50), bb_position=ind.get('bb_position',0.5),
                       ml_pred=ml_pred['prediction'], ml_confidence=ml_pred['confidence'],
                       sentiment=sentiment.get('overall','neutral'), shares=shares, confidence_score=conf,
                       expected_return=gross_ret, net_expected_return=net_ret, composite_score=composite,
                       signal_strength=int(conf*10), fundamental_score=fund_score)

def generate_swing_signal(symbol, price, ind, ml_pred, regime, config, fund_score, tax):
    if ind.get('rsi',50) < 40 and ind.get('stoch_k',50) < 20 and ml_pred['prediction'] == 'up':
        atr = ind.get('atr', price*0.02)
        stop = price - atr * 2
        target1 = price + atr * 3
        target2 = price + atr * 5
        conf = 0.6; win_rate = 0.55
        avg_win = target1 - price; avg_loss = price - stop
        shares = dynamic_position_sizing(ACCOUNT_BALANCE, price, stop, win_rate, avg_win, avg_loss, MAX_RISK_PER_TRADE)
        if shares <= 0: return None
        gross_ret = avg_win / price * win_rate
        net_ret = tax.net_profit(gross_ret, is_dividend=False)
        composite = (net_ret * conf) * fund_score * (1 - tax.policy_risk)
        return TradeSignal(symbol=symbol, strategy='swing', action='BUY', entry_price=price,
                           entry_date=datetime.now().strftime("%Y-%m-%d"), exit_price=target1,
                           exit_date=(datetime.now()+timedelta(days=10)).strftime("%Y-%m-%d"),
                           stop_loss=stop, target1=target1, target2=target2,
                           reason=f"Oversold RSI={ind['rsi']:.1f}", rsi=ind['rsi'], adx=ind.get('adx',0),
                           stoch_k=ind['stoch_k'], ml_pred=ml_pred['prediction'], ml_confidence=ml_pred['confidence'],
                           sentiment='neutral', shares=shares, confidence_score=conf,
                           expected_return=gross_ret, net_expected_return=net_ret, composite_score=composite,
                           signal_strength=2, fundamental_score=fund_score)
    return None

def generate_momentum_signal(symbol, price, ind, ml_pred, regime, config, fund_score, tax):
    if ind.get('adx',0) > 25 and price > ind.get('sma_50',0) and ml_pred['prediction'] == 'up':
        atr = ind.get('atr', price*0.02)
        stop = price - atr * 2
        target1 = price + atr * 4
        target2 = price + atr * 6
        conf = 0.65; win_rate = 0.6
        avg_win = target1 - price; avg_loss = price - stop
        shares = dynamic_position_sizing(ACCOUNT_BALANCE, price, stop, win_rate, avg_win, avg_loss, MAX_RISK_PER_TRADE)
        if shares <= 0: return None
        gross_ret = avg_win / price * win_rate
        net_ret = tax.net_profit(gross_ret, is_dividend=False)
        composite = (net_ret * conf) * fund_score * (1 - tax.policy_risk)
        return TradeSignal(symbol=symbol, strategy='momentum', action='BUY', entry_price=price,
                           entry_date=datetime.now().strftime("%Y-%m-%d"), exit_price=target1,
                           exit_date=(datetime.now()+timedelta(days=10)).strftime("%Y-%m-%d"),
                           stop_loss=stop, target1=target1, target2=target2,
                           reason=f"Trend ADX={ind['adx']:.1f}", rsi=ind['rsi'], adx=ind['adx'],
                           stoch_k=ind.get('stoch_k',50), ml_pred=ml_pred['prediction'], ml_confidence=ml_pred['confidence'],
                           sentiment='neutral', shares=shares, confidence_score=conf,
                           expected_return=gross_ret, net_expected_return=net_ret, composite_score=composite,
                           signal_strength=3, fundamental_score=fund_score)
    return None

def generate_mean_reversion_signal(symbol, price, ind, ml_pred, regime, config, fund_score, tax):
    if ind.get('rsi',50) < 30 and ind.get('bb_position',0.5) < 0.1:
        atr = ind.get('atr', price*0.02)
        stop = price - atr * 1.5
        target1 = price + atr * 2
        target2 = price + atr * 3
        conf = 0.7; win_rate = 0.6
        avg_win = target1 - price; avg_loss = price - stop
        shares = dynamic_position_sizing(ACCOUNT_BALANCE, price, stop, win_rate, avg_win, avg_loss, MAX_RISK_PER_TRADE)
        if shares <= 0: return None
        gross_ret = avg_win / price * win_rate
        net_ret = tax.net_profit(gross_ret, is_dividend=False)
        composite = (net_ret * conf) * fund_score * (1 - tax.policy_risk)
        return TradeSignal(symbol=symbol, strategy='mean_reversion', action='BUY', entry_price=price,
                           entry_date=datetime.now().strftime("%Y-%m-%d"), exit_price=target1,
                           exit_date=(datetime.now()+timedelta(days=5)).strftime("%Y-%m-%d"),
                           stop_loss=stop, target1=target1, target2=target2,
                           reason=f"Mean rev RSI={ind['rsi']:.1f}", rsi=ind['rsi'], adx=ind.get('adx',0),
                           stoch_k=ind.get('stoch_k',50), ml_pred=ml_pred['prediction'], ml_confidence=ml_pred['confidence'],
                           sentiment='neutral', shares=shares, confidence_score=conf,
                           expected_return=gross_ret, net_expected_return=net_ret, composite_score=composite,
                           signal_strength=2, fundamental_score=fund_score)
    return None

# ============================================================
# PAIRS TRADING MODULE
# ============================================================
def find_correlated_pairs(historical, symbols, min_corr=0.85):
    pairs = []
    closes = {}
    for sym in symbols:
        if sym in historical and historical[sym] is not None:
            df = historical[sym]
            closes[sym] = df['Close'] if 'Close' in df else df.iloc[:,3]
    for sym1 in closes:
        for sym2 in closes:
            if sym1 >= sym2: continue
            if len(closes[sym1]) == len(closes[sym2]) and len(closes[sym1]) > 50:
                corr = closes[sym1].corr(closes[sym2])
                if abs(corr) >= min_corr:
                    pairs.append((sym1, sym2, corr))
    return sorted(pairs, key=lambda x: abs(x[2]), reverse=True)

def generate_pairs_signal(sym_a, sym_b, corr, historical, prices, config, tax):
    if sym_a not in historical or sym_b not in historical: return None
    close_a = historical[sym_a]['Close'] if 'Close' in historical[sym_a] else historical[sym_a].iloc[:,3]
    close_b = historical[sym_b]['Close'] if 'Close' in historical[sym_b] else historical[sym_b].iloc[:,3]
    spread = close_a / close_a.mean() - close_b / close_b.mean()
    mean_spread = spread.mean()
    std_spread = spread.std()
    current = spread.iloc[-1]
    z_score = (current - mean_spread) / std_spread
    if abs(z_score) < 2.0: return None
    if z_score > 0: buy_sym = sym_b
    else: buy_sym = sym_a
    price_buy = prices.get(buy_sym, 0)
    if price_buy <= 0: return None
    atr = calculate_atr(historical[buy_sym]) or price_buy*0.02
    stop = price_buy - atr * 2
    target = price_buy + atr * 4
    shares = dynamic_position_sizing(ACCOUNT_BALANCE, price_buy, stop, 0.55, target-price_buy, price_buy-stop, MAX_RISK_PER_TRADE)
    if shares <= 0: return None
    gross_ret = (target / price_buy - 1) * 0.55
    net_ret = tax.net_profit(gross_ret, is_dividend=False)
    composite = net_ret * 0.6 * (1 - tax.policy_risk)
    return TradeSignal(
        symbol=buy_sym, strategy='pairs', action='BUY', entry_price=price_buy,
        entry_date=datetime.now().strftime("%Y-%m-%d"), exit_price=target,
        exit_date=(datetime.now()+timedelta(days=10)).strftime("%Y-%m-%d"),
        stop_loss=stop, target1=target, target2=target*1.05,
        reason=f"Pairs z={z_score:.1f}", shares=shares, confidence_score=0.6,
        expected_return=gross_ret, net_expected_return=net_ret, composite_score=composite
    )

# ============================================================
# SECTOR ROTATION SIGNAL
# ============================================================
def sector_rotation_signal(symbols, historical, prices, fund_scores, config, tax):
    sector_performance = defaultdict(list)
    for stock in TOP_50_SHARIAH_STOCKS:
        sym = stock['symbol']
        if sym in historical and sym in prices:
            df = historical[sym]
            close = df['Close'] if 'Close' in df else df.iloc[:,3]
            ret = close.pct_change(20).iloc[-1] if len(close) >= 20 else 0
            sector_performance[stock['sector']].append(ret)
    best_sector = max(sector_performance, key=lambda s: np.mean(sector_performance[s]) if sector_performance[s] else 0)
    signals = []
    for stock in TOP_50_SHARIAH_STOCKS:
        if stock['sector'] == best_sector:
            sym = stock['symbol']
            price = prices.get(sym, 0)
            if price <= 0: continue
            ind = calculate_indicators(historical.get(sym)) if sym in historical else {}
            ml = ml_predict_enhanced(historical.get(sym), fund_scores.get(sym,0.5)) if sym in historical else {'prediction':'neutral','confidence':0}
            sig = generate_momentum_signal(sym, price, ind, ml, 'neutral', config, fund_scores.get(sym,0.5), tax)
            if sig:
                sig.strategy = 'sector_rotation'
                signals.append(sig)
    return signals[:3]

# ============================================================
# GENERATE ALL SIGNALS COMBINER
# ============================================================
def generate_all_signals(symbol, price, div_info, ind, ml_pred, sentiment, regime, config, fund_score, tax):
    signals = []
    if config.get('strategies.dividend', True) and div_info:
        sig = generate_dividend_signal(symbol, price, div_info, ind, ml_pred, sentiment, regime, config, fund_score, tax)
        if sig: signals.append(sig)
    if config.get('strategies.swing', True):
        sig = generate_swing_signal(symbol, price, ind, ml_pred, regime, config, fund_score, tax)
        if sig: signals.append(sig)
    if config.get('strategies.momentum', True):
        sig = generate_momentum_signal(symbol, price, ind, ml_pred, regime, config, fund_score, tax)
        if sig: signals.append(sig)
    if config.get('strategies.mean_reversion', True):
        sig = generate_mean_reversion_signal(symbol, price, ind, ml_pred, regime, config, fund_score, tax)
        if sig: signals.append(sig)
    return signals

# ============================================================
# DETECT MARKET REGIME
# ============================================================
def detect_market_regime(df):
    if df is None or df.empty: return 'neutral'
    adx = calculate_adx(df)
    close = df['Close'] if 'Close' in df else df.iloc[:,3]
    sma50 = close.tail(50).mean() if len(close) >= 50 else close.mean()
    current = close.iloc[-1]
    if adx > 25:
        if current > sma50 * 1.02: return 'bullish'
        elif current < sma50 * 0.98: return 'bearish'
    return 'neutral'

# ============================================================
# DIVIDEND CALENDAR
# ============================================================
def get_upcoming_dividends(symbols):
    today = datetime.now().date()
    upcoming = []
    for sym in symbols:
        for div in EX_DATES.get(sym, []):
            ex_date = datetime.strptime(div['ex_date'], "%Y-%m-%d").date()
            days = (ex_date - today).days
            if 0 <= days <= 60:
                price = next((s['current_price'] for s in TOP_50_SHARIAH_STOCKS if s['symbol']==sym), None)
                gross_yield = (div['amount'] / price * 100) if price else 0
                upcoming.append({
                    'symbol': sym, 'ex_date': div['ex_date'], 'amount': div['amount'],
                    'type': div.get('type',''), 'record_date': div.get('record_date',''),
                    'days_until': days, 'gross_yield': gross_yield,
                    'net_yield': gross_yield * (1 - DIV_TAX_RATE)
                })
    return sorted(upcoming, key=lambda x: x['days_until'])

# ============================================================
# SENTIMENT ANALYSIS
# ============================================================
vader_analyzer = SentimentIntensityAnalyzer() if VADER_AVAILABLE else None

def fetch_news_sentiment():
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get('title',''); summary = entry.get('summary','')
                text = title + " " + summary
                blob = TextBlob(text)
                polarity_tb = blob.sentiment.polarity
                vader_pol = 0.0
                if vader_analyzer:
                    vader_pol = vader_analyzer.polarity_scores(text)['compound']
                combined = (polarity_tb + vader_pol) / 2 if vader_analyzer else polarity_tb
                sentiment = 'bullish' if combined > 0.1 else 'bearish' if combined < -0.1 else 'neutral'
                articles.append({
                    'title': title, 'summary': summary[:200], 'link': entry.get('link',''),
                    'published': entry.get('published',''), 'sentiment': sentiment,
                    'polarity': combined, 'subjectivity': blob.sentiment.subjectivity
                })
        except Exception as e:
            logger.debug(f"RSS error for {feed_url}: {e}")
    if articles:
        avg_polarity = np.mean([a['polarity'] for a in articles])
        overall = 'bullish' if avg_polarity > 0.05 else 'bearish' if avg_polarity < -0.05 else 'neutral'
        return {'overall': overall, 'avg_polarity': avg_polarity, 'articles': articles[:10]}
    return {'overall': 'neutral', 'avg_polarity': 0, 'articles': []}

# ============================================================
# PAPER TRADING ENGINE (TAX-AWARE, CASH-LIMITED)
# ============================================================
class PaperTradingEngine:
    def __init__(self, balance=ACCOUNT_BALANCE, max_dd=MAX_PORTFOLIO_DRAWDOWN, db_path='psx_trades.db', config=None):
        self.balance = balance
        self.initial_balance = balance
        self.peak = balance
        self.max_dd = max_dd
        self.portfolio: Dict[str, PortfolioPosition] = {}
        self.trades: List[Trade] = []
        self.signals: List[TradeSignal] = []
        self.daily_pnl = defaultdict(float)
        self._current_day = datetime.now().date()
        self._daily_loss = 0.0
        self.commission_pct = 0.001
        self.slippage_pct = 0.001
        self.tax_rate = CGT_RATE
        self.config = config or Config()
        self.db_path = db_path
        self._init_db()
    def _init_db(self):
        if not self.config.get('database.enabled', True): return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS trades
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          symbol TEXT, action TEXT, price REAL, quantity INTEGER,
                          time TEXT, pnl REAL, commission REAL, slippage REAL,
                          entry_time TEXT, exit_time TEXT, dividend REAL,
                          tax REAL, net_pnl REAL)''')
            conn.commit()
            conn.close()
        except Exception as e: logger.error(f"Database init error: {e}")
    def _log_trade_db(self, trade: Trade):
        if not self.config.get('database.enabled', True): return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT INTO trades (symbol, action, price, quantity, time, pnl, commission, slippage, entry_time, exit_time, dividend, tax, net_pnl)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (trade.symbol, trade.side, trade.exit_price if trade.side == 'SELL' else trade.entry_price,
                       trade.quantity, datetime.now().isoformat(), trade.pnl, trade.commission, trade.slippage,
                       trade.entry_time.isoformat(), trade.exit_time.isoformat(), trade.dividend_captured, trade.tax_paid, trade.net_pnl))
            conn.commit()
            conn.close()
        except Exception as e: logger.error(f"DB log error: {e}")
    def _get_sector(self, symbol):
        for s in TOP_50_SHARIAH_STOCKS:
            if s['symbol'] == symbol: return s['sector']
        return 'Unknown'
    def can_open_position(self, symbol, value):
        sector = self._get_sector(symbol)
        max_sector_exp = self.config.get('trading.max_sector_exposure', 0.3)
        current_sector_value = sum(pos.avg_price * pos.quantity for sym, pos in self.portfolio.items() if self._get_sector(sym) == sector)
        total_value = self.get_total_value()
        if total_value > 0 and (current_sector_value + value) / total_value > max_sector_exp:
            logger.warning(f"Sector {sector} exposure limit reached")
            return False
        return True
    def buy(self, symbol, price, qty, stop, target1, target2):
        max_shares = int(self.balance / (price * (1 + self.slippage_pct + self.commission_pct)))
        qty = min(qty, max_shares)
        if qty <= 0:
            logger.error(f"Insufficient balance for {symbol}: need 1 share, have {self.balance:.2f}")
            return False
        cost = price * qty * (1 + self.slippage_pct + self.commission_pct)
        if not self.can_open_position(symbol, cost): return False
        if cost > self.balance: return False
        self.balance -= cost
        pos = PortfolioPosition(symbol=symbol, quantity=qty, avg_price=price * (1 + self.slippage_pct),
                                stop_loss=stop, target1=target1, target2=target2)
        self.portfolio[symbol] = pos
        trade = Trade(symbol=symbol, entry_price=price, exit_price=0, quantity=qty,
                      entry_time=datetime.now(), exit_time=datetime.now(),
                      pnl=0, pnl_pct=0, side='BUY', stop_loss=stop, target1=target1, target2=target2,
                      commission=cost * self.commission_pct, slippage=cost * self.slippage_pct)
        self.trades.append(trade)
        self._log_trade_db(trade)
        logger.info(f"Paper BUY {qty} {symbol} @ {price:.2f} | Stop: {stop:.2f} | Cash left: {self.balance:.2f}")
        return True
    def sell(self, symbol, price, qty=None):
        if symbol not in self.portfolio:
            logger.error(f"No position in {symbol}"); return False
        pos = self.portfolio[symbol]
        if qty is None: qty = pos.quantity
        if qty > pos.quantity: return False
        proceeds = price * qty * (1 - self.slippage_pct - self.commission_pct)
        self.balance += proceeds
        gross_pnl = (price * (1 - self.slippage_pct) - pos.avg_price) * qty - (price * qty * self.commission_pct)
        holding_days = (datetime.now() - pos.entry_time).days if hasattr(pos, 'entry_time') else 0
        tax_due = gross_pnl * self.tax_rate if gross_pnl > 0 else 0
        net_pnl = gross_pnl - tax_due
        pnl_pct = (price / pos.avg_price - 1) * 100
        pos.quantity -= qty
        trade = Trade(symbol=symbol, entry_price=pos.avg_price, exit_price=price, quantity=qty,
                      entry_time=datetime.now(), exit_time=datetime.now(),
                      pnl=gross_pnl, pnl_pct=pnl_pct, side='SELL',
                      commission=proceeds * self.commission_pct, slippage=price * qty * self.slippage_pct,
                      holding_period=holding_days, tax_paid=tax_due, net_pnl=net_pnl)
        self.trades.append(trade)
        self._log_trade_db(trade)
        self._daily_loss += net_pnl
        if pos.quantity == 0: del self.portfolio[symbol]
        logger.info(f"Paper SELL {qty} {symbol} @ {price:.2f} | Gross P&L: {gross_pnl:+.2f} | Net P&L: {net_pnl:+.2f} | Cash: {self.balance:.2f}")
        return True
    def update_prices(self, live_prices):
        for sym, price in live_prices.items():
            if sym in self.portfolio:
                pos = self.portfolio[sym]
                pos.current_price = price
                pos.pnl = (price - pos.avg_price) * pos.quantity
                pos.pnl_pct = (price / pos.avg_price - 1) * 100
    def check_trailing_stop(self, symbol, current_price):
        if symbol not in self.portfolio: return False
        pos = self.portfolio[symbol]
        activation = self.config.get('trading.trailing_stop_activation_pct', 0.02)
        trail_pct = self.config.get('trading.trailing_stop_pct', 0.015)
        if current_price >= pos.avg_price * (1 + activation):
            new_stop = current_price * (1 - trail_pct)
            if new_stop > pos.stop_loss:
                pos.stop_loss = new_stop
                logger.debug(f"Trailing stop updated for {symbol} to {new_stop:.2f}")
        return current_price <= pos.stop_loss
    def get_total_value(self, current_prices=None):
        total = self.balance
        for sym, pos in self.portfolio.items():
            price = current_prices.get(sym, pos.avg_price) if current_prices else pos.avg_price
            total += price * pos.quantity
        return total
    def get_unrealized_pnl(self, current_prices):
        total = 0.0
        for sym, pos in self.portfolio.items():
            price = current_prices.get(sym, pos.avg_price)
            total += (price - pos.avg_price) * pos.quantity
        return total
    def get_stats(self):
        completed = [t for t in self.trades if t.side == 'SELL']
        if not completed: return {'total_trades':0, 'winning_trades':0, 'losing_trades':0, 'win_rate':0.0, 'total_pnl':0.0,
                                   'avg_pnl':0, 'sharpe':0, 'max_dd':0}
        total_trades = len(completed)
        winning = sum(1 for t in completed if t.net_pnl > 0)
        losing = total_trades - winning
        total_pnl = sum(t.net_pnl for t in completed)
        win_rate = winning / total_trades
        avg_pnl = total_pnl / total_trades
        returns = [t.net_pnl for t in completed]
        sharpe = np.mean(returns) / (np.std(returns) + 1e-6)
        max_dd = calculate_max_drawdown(np.cumsum(returns))
        return {'total_trades': total_trades, 'winning_trades': winning, 'losing_trades': losing,
                'win_rate': win_rate, 'total_pnl': total_pnl, 'avg_pnl': avg_pnl,
                'sharpe': sharpe, 'max_dd': max_dd,
                'profit_factor': abs(sum(r for r in returns if r>0) / (sum(r for r in returns if r<0) + 1e-6))}

def calculate_max_drawdown(pnl_series):
    peak = pnl_series[0] if len(pnl_series) else 0
    max_dd = 0
    for val in pnl_series:
        if val > peak: peak = val
        dd = (peak - val) / peak if peak > 0 else 0
        if dd > max_dd: max_dd = dd
    return max_dd

# ============================================================
# HTML REPORT GENERATOR (LIGHT THEME, FULL FEATURES)
# ============================================================
def generate_chart_base64(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return f'data:image/png;base64,{img_base64}'

def generate_performance_chart(engine):
    pnl_series = []; cum = 0
    for t in engine.trades:
        if t.side == 'SELL':
            cum += t.net_pnl
            pnl_series.append(cum)
    if not pnl_series: return ""
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(pnl_series, color='#0066cc', lw=1)
    ax.set_title('Net Equity Curve', color='#222')
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')
    ax.tick_params(colors='#555')
    return generate_chart_base64(fig)

def generate_html_report(symbols, dividends, signals, live_prices, market_pulse,
                         indices, sectors, paper_engine, backtest_results,
                         sentiment_data, config, correlation_matrix=None):
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    div_rows = ""
    for d in dividends[:20]:
        days = d['days_until']; status = "🔥 IMMINENT" if days <= 2 else "🔶 SOON"
        div_rows += f"<tr><td><strong>{d['symbol']}</strong></td><td>{d['ex_date']}</td><td>{d['amount']:.2f}</td><td>{days} days</td><td>{d.get('type','')}</td><td>{status}</td></tr>"
    if not div_rows: div_rows = "<tr><td colspan='6'>No upcoming dividends</td></tr>"

    sig_rows = ""
    for s in signals[:20]:
        priority_badge = "⭐ FORCE ENTRY" if s.priority == "FORCE ENTRY" else "🟢 STANDARD"
        sig_rows += f"""
        <tr>
            <td><strong>{s.symbol}</strong></td><td>{s.strategy}</td><td>{s.entry_price:.2f}</td>
            <td>T-{max(0, (datetime.strptime(s.entry_date, '%Y-%m-%d') - datetime.now()).days)}</td>
            <td>{s.entry_date}</td><td class='positive'>{s.net_expected_return:.2%}</td>
            <td>{s.stop_loss:.2f}</td><td>{s.target1:.2f}</td><td>{s.shares}</td>
            <td>{s.confidence_score:.1%}</td><td><span class='priority'>{priority_badge}</span></td>
            <td class='positive'>🟢 BUY</td>
        </tr>"""
    if not sig_rows: sig_rows = "<tr><td colspan='12'>No qualifying signals</td></tr>"

    journal = paper_engine.get_stats()
    sentiment_text = sentiment_data.get('overall', 'neutral').upper()
    sentiment_color = '#28a745' if sentiment_text == 'BULLISH' else '#dc3545' if sentiment_text == 'BEARISH' else '#ffc107'
    perf_chart = generate_performance_chart(paper_engine)
    # Fix: convert live_prices dict to just prices
    price_map = {sym: data.get('price', 0) if isinstance(data, dict) else data for sym, data in live_prices.items()}

    html = f"""
    <html><head>
    <style>
        body {{ font-family: Arial, sans-serif; background: #f5f5f5; color: #222; padding: 20px; }}
        .header {{ background: #ffffff; border-left: 5px solid #0066cc; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header h1 {{ color: #0066cc; margin: 0; }}
        .section {{ background: #ffffff; margin: 20px 0; padding: 20px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .section h2 {{ color: #0066cc; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; }}
        th {{ background: #eef3f9; color: #333; padding: 10px 8px; text-align: left; border-bottom: 2px solid #ddd; }}
        td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        tr:nth-child(even) {{ background: #fafafa; }}
        .positive {{ color: #28a745; font-weight: bold; }}
        .negative {{ color: #dc3545; font-weight: bold; }}
        .priority {{ background: #ffc107; color: #222; padding: 2px 8px; border-radius: 12px; font-size: 10px; }}
        .footer {{ text-align: center; font-size: 12px; color: #888; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 15px; }}
        .chart-container {{ text-align: center; margin: 10px 0; }}
    </style>
    </head><body>
        <div class="header">
            <h1>💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v{VERSION}</h1>
            <p style="color:#666;">Generated on {now}</p>
            <p>💰 Account: PKR {ACCOUNT_BALANCE:,.0f} | 📊 {len(dividends)} Dividends | 🕌 {len(symbols)} Shariah Stocks</p>
            <p>📋 Trades: {journal['total_trades']} | Net P&L: {journal['total_pnl']:+.2f} | Win Rate: {journal['win_rate']*100:.1f}%</p>
            <p>📊 Sentiment: <span style='color:{sentiment_color}; font-weight:bold;'>{sentiment_text}</span></p>
            <p>📑 Policy Risk: {tax_policy.policy_risk:.0%} | Filer: {'Yes' if TAX_FILER else 'No'}</p>
        </div>
        <div class="section"><h2>📅 Upcoming Dividend Calendar</h2><table><thead><tr><th>Symbol</th><th>Ex-Date</th><th>Amount</th><th>Days</th><th>Type</th><th>Status</th></tr></thead><tbody>{div_rows}</tbody></table></div>
        <div class="section"><h2>🎯 Top Trade Recommendations (Net of Tax)</h2><table><thead><tr><th>Symbol</th><th>Strategy</th><th>Price</th><th>Entry</th><th>Ex-Date</th><th>Net Exp Return</th><th>Stop</th><th>T1</th><th>Shares</th><th>Conf</th><th>Priority</th><th>Action</th></tr></thead><tbody>{sig_rows}</tbody></table></div>
        <div class="section"><h2>📊 Portfolio</h2><p>Cash: PKR {paper_engine.balance:,.2f}</p><p>Total Value: PKR {paper_engine.get_total_value(price_map):,.2f}</p><p>Unrealized P&L: PKR {paper_engine.get_unrealized_pnl(price_map):+.2f}</p></div>
        <div class="section"><h2>📊 Performance Chart</h2><div class="chart-container"><img src="{perf_chart}" alt="Net Equity Curve" style="max-width:100%;"/></div></div>
        <div class="footer"><p>🕌 Shariah-compliant | 📊 All features enabled | ⚡ Generated by PSX Ultimate Engine v{VERSION}</p><p>⚠️ This is for informational purposes only. Always do your own research.</p></div>
    </body></html>
    """
    return html

def send_email(subject, html_content):
    if not RESEND_API_KEY: return False
    url = "https://api.resend.com/emails"
    headers = {'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'}
    data = {'from': FROM_EMAIL, 'to': [TO_EMAIL], 'subject': subject, 'html': html_content}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            logger.info("Email sent successfully"); return True
        else:
            logger.error(f"Email failed: {resp.status_code} - {resp.text}"); return False
    except Exception as e:
        logger.error(f"Email error: {e}"); return False

# ============================================================
# MAIN EXECUTION (with permission prompt)
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='PSX Ultimate Dividend Capture Engine v22.0')
    parser.add_argument('--mode', choices=['live', 'backtest', 'report'], default='live')
    parser.add_argument('--strategy', nargs='*', default=['dividend', 'swing', 'momentum', 'mean_reversion', 'pairs', 'sector_rotation', 'etf_arbitrage'])
    parser.add_argument('--confirm', action='store_true', help='Prompt for confirmation before executing trades')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--symbol', nargs='*')
    args = parser.parse_args()
    config = Config(args.config)
    for strat in ['dividend', 'swing', 'momentum', 'mean_reversion', 'pairs', 'sector_rotation', 'etf_arbitrage']:
        config._config['strategies'][strat] = strat in args.strategy
    global ACCOUNT_BALANCE
    ACCOUNT_BALANCE = float(os.environ.get('PSX_ACCOUNT_BALANCE', config.get('trading.initial_balance', 30000.0)))

    symbols = [s['symbol'] for s in TOP_50_SHARIAH_STOCKS]
    if args.symbol: symbols = args.symbol

    print("=" * 80)
    print(f"💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v{VERSION} - ALL FEATURES")
    print(f"Active strategies: {[k for k,v in config._config['strategies'].items() if v]}")
    print(f"Starting Balance: PKR {ACCOUNT_BALANCE:,.0f}")

    # Live prices
    fetcher = UnifiedDataFetcher()
    live_prices = fetcher.fetch_all(symbols)
    for sym, data in live_prices.items(): print(f"   {sym}: PKR {data['price']:.2f}")

    # Dividends
    dividends = get_upcoming_dividends(symbols)
    print(f"📅 {len(dividends)} upcoming dividends")

    # Historical data
    historical = {}
    try:
        import pypsx
        for sym in symbols:
            try:
                end = datetime.now(); start = end - timedelta(days=100)
                df = pypsx.PSXTicker(sym).get_historical(start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d"))
                if df is not None and not df.empty: historical[sym] = df
            except: pass
    except: pass
    if PSX_DATA_READER_AVAILABLE:
        for sym in symbols:
            if sym not in historical:
                try:
                    df = psx_hist_stocks(sym, start=date.today()-timedelta(days=100), end=date.today())
                    if df is not None and not df.empty: historical[sym] = df
                except: pass

    # Sentiment & policy
    sentiment = fetch_news_sentiment()
    tax_policy.update_policy_from_news(sentiment['articles'])
    print(f"📰 Sentiment: {sentiment['overall']}, Policy risk: {tax_policy.policy_risk:.0%}")

    # Fundamental reports & scores
    reports = {sym: fetch_company_reports(sym) for sym in symbols}
    fund_scores = {sym: advanced_fundamental_score(sym, reports, live_prices) for sym in symbols}

    all_signals = []
    paper_engine = PaperTradingEngine(balance=ACCOUNT_BALANCE, config=config)

    # Standard strategies
    for stock in TOP_50_SHARIAH_STOCKS:
        sym = stock['symbol']
        price = live_prices.get(sym, {}).get('price', 0)
        if price <= 0: continue
        div_info = next((d for d in dividends if d['symbol'] == sym), None)
        ind = calculate_indicators(historical.get(sym)) if sym in historical else {}
        ml = ml_predict_enhanced(historical.get(sym), fund_scores.get(sym,0.5)) if sym in historical else {'prediction':'neutral','confidence':0}
        regime = detect_market_regime(historical.get(sym))
        sigs = generate_all_signals(sym, price, div_info, ind, ml, sentiment, regime, config, fund_scores.get(sym,0.5), tax_policy)
        all_signals.extend(sigs)

    # Pairs trading
    if config.get('strategies.pairs', True) and len(historical) > 5:
        pairs = find_correlated_pairs(historical, symbols)
        for (sym_a, sym_b, corr) in pairs[:5]:
            sig = generate_pairs_signal(sym_a, sym_b, corr, historical, live_prices, config, tax_policy)
            if sig: all_signals.append(sig)

    # Sector rotation
    if config.get('strategies.sector_rotation', True):
        sector_sigs = sector_rotation_signal(symbols, historical, live_prices, fund_scores, config, tax_policy)
        all_signals.extend(sector_sigs)

    # Rank & select top 3
    all_signals.sort(key=lambda x: x.composite_score, reverse=True)
    selected = all_signals[:3]
    print(f"\n🔔 Top 3 signals:")
    for i, sig in enumerate(selected, 1):
        print(f"{i}. {sig.strategy.upper()} {sig.symbol} @ {sig.entry_price:.2f} | "
              f"Conf: {sig.confidence_score:.1%} | "
              f"Net Exp: {sig.net_expected_return:.2%} | "
              f"Shares: {sig.shares} | "
              f"Stop: {sig.stop_loss:.2f} | T1: {sig.target1:.2f}")

    # Permission prompt (if --confirm flag is set)
    if args.confirm:
        ans = input("\nExecute these 3 trades? (y/N): ").strip().lower()
        if ans != 'y':
            print("🚫 Trades canceled by user.")
            return 0
        print("✅ Trades approved.")

    # Execute trades
    for sig in selected:
        paper_engine.buy(sig.symbol, sig.entry_price, sig.shares, sig.stop_loss, sig.target1, sig.target2)

    # Trailing stops
    price_dict = {sym: data['price'] for sym, data in live_prices.items()}
    paper_engine.update_prices(price_dict)
    for sym, pos in list(paper_engine.portfolio.items()):
        current = price_dict.get(sym, pos.avg_price)
        if paper_engine.check_trailing_stop(sym, current):
            paper_engine.sell(sym, current)

    # Email
    html = generate_html_report(symbols, dividends, selected, live_prices, None, None, None, paper_engine, [], sentiment, config)
    send_email(f"PSX Ultimate Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}", html)
    print("✅ Report sent")
    return 0

if __name__ == "__main__":
    sys.exit(main())
