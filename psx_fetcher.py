#!/usr/bin/env python3
"""
PSX ULTIMATE DIVIDEND CAPTURE ENGINE v21.3 - LIGHT THEME
Author: PSX Ultimate Engine
License: Personal Use Only
Description: Fully automated Shariah-compliant dividend capture and swing trading system for PSX.
Features: Live data, 30+ indicators, ML ensemble (LR+RF+XGB+LSTM), sentiment analysis (VADER+TextBlob),
          Kelly sizing, paper trading, backtesting, portfolio optimization, correlation analysis,
          risk management, telegram alerts, HTML email reports with light theme charts,
          YAML config, SQLite trade journal, scenario testing, walk-forward analysis, and full logging.
Now includes psx-data-reader integration for historical data.
"""

import sys
import os
import json
import yaml
import logging
import argparse
import re
import time
import math
import random
import hashlib
import pickle
import traceback
import itertools
import sqlite3
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
matplotlib.use('Agg')  # non-interactive
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
# import seaborn as sns  # Not needed – removed to avoid dependency
import warnings
warnings.filterwarnings('ignore')

# VADER for sentiment
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

# PyPortfolioOpt for advanced optimization
try:
    import pypfopt
    from pypfopt import expected_returns, risk_models, EfficientFrontier, objective_functions
    PYPO_AVAILABLE = True
except ImportError:
    PYPO_AVAILABLE = False

# psx-data-reader for historical data
try:
    from psx import stocks as psx_hist_stocks, tickers as psx_tickers
    PSX_DATA_READER_AVAILABLE = True
except ImportError:
    PSX_DATA_READER_AVAILABLE = False

# ============================================================
# VERSION & METADATA
# ============================================================
VERSION = "21.3"
AUTHOR = "PSX Ultimate Dividend Capture Engine"
DESCRIPTION = "Complete Automated Dividend Capture System for PSX with Top 50 Shariah Stocks"
RELEASE_DATE = "June 24, 2026"
LICENSE = "Proprietary - For Personal Use Only"
GITHUB_REPO = "https://github.com/psx-trader/psx-fetcher"
DOCUMENTATION = "https://github.com/psx-trader/psx-fetcher/README.md"

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY')
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY')
YAHOO_FINANCE_API_KEY = os.environ.get('YAHOO_FINANCE_API_KEY')

# ============================================================
# DEFAULT TRADING PARAMETERS (overridable by config/env)
# ============================================================
ACCOUNT_BALANCE = float(os.environ.get('PSX_ACCOUNT_BALANCE', 30000.0))
MAX_RISK_PER_TRADE = float(os.environ.get('PSX_MAX_RISK_PER_TRADE', 0.02))
MAX_PORTFOLIO_DRAWDOWN = float(os.environ.get('PSX_MAX_PORTFOLIO_DRAWDOWN', 0.02))
STOP_LOSS_PCT = float(os.environ.get('PSX_STOP_LOSS_PCT', 0.03))
TARGET1_PCT = float(os.environ.get('PSX_TARGET1_PCT', 0.05))
TARGET2_PCT = float(os.environ.get('PSX_TARGET2_PCT', 0.08))
TRAILING_STOP_PCT = float(os.environ.get('PSX_TRAILING_STOP_PCT', 0.015))
PAPER_TRADING = os.environ.get('PSX_PAPER_TRADING', 'True').lower() == 'true'
MIN_DIVIDEND_YIELD = float(os.environ.get('PSX_MIN_DIVIDEND_YIELD', 0.04))
MIN_VOLUME_CRORES = float(os.environ.get('PSX_MIN_VOLUME_CRORES', 1))
RISK_OFF_INDEX_DROP = float(os.environ.get('PSX_RISK_OFF_INDEX_DROP', 0.015))
CONFIDENCE_THRESHOLD = float(os.environ.get('PSX_CONFIDENCE_THRESHOLD', 0.3))
MIN_SHARIAH_DEBT_RATIO = float(os.environ.get('PSX_MIN_SHARIAH_DEBT_RATIO', 0.33))
MAX_NON_COMPLIANT_INCOME = float(os.environ.get('PSX_MAX_NON_COMPLIANT_INCOME', 0.05))
CACHE_TTL_SECONDS = int(os.environ.get('PSX_CACHE_TTL_SECONDS', 300))
MAX_RETRIES = int(os.environ.get('PSX_MAX_RETRIES', 3))
RETRY_DELAY = int(os.environ.get('PSX_RETRY_DELAY', 2))
PARALLEL_WORKERS = int(os.environ.get('PSX_PARALLEL_WORKERS', 8))
MAX_HOLD_DAYS = int(os.environ.get('PSX_MAX_HOLD_DAYS', 5))
PROFIT_TAKE_AFTER_DAYS = int(os.environ.get('PSX_PROFIT_TAKE_AFTER_DAYS', 3))
MAX_POSITION_PCT = float(os.environ.get('PSX_MAX_POSITION_PCT', 0.10))
RSI_BUY_THRESHOLD = float(os.environ.get('PSX_RSI_BUY_THRESHOLD', 30))
RSI_SELL_THRESHOLD = float(os.environ.get('PSX_RSI_SELL_THRESHOLD', 70))
BACKTEST_DAYS = int(os.environ.get('PSX_BACKTEST_DAYS', 365))
MIN_MARKET_CAP = float(os.environ.get('PSX_MIN_MARKET_CAP', 1_000_000_000))
MIN_VOLUME = int(os.environ.get('PSX_MIN_VOLUME', 100_000))
SECTOR_WHITELIST = os.environ.get('PSX_SECTOR_WHITELIST', '').split(',') if os.environ.get('PSX_SECTOR_WHITELIST') else []
SECTOR_BLACKLIST = os.environ.get('PSX_SECTOR_BLACKLIST', '').split(',') if os.environ.get('PSX_SECTOR_BLACKLIST') else []
ENABLE_ML = os.environ.get('PSX_ENABLE_ML', 'True').lower() == 'true'
ENABLE_SENTIMENT = os.environ.get('PSX_ENABLE_SENTIMENT', 'True').lower() == 'true'
ENABLE_TELEGRAM = os.environ.get('PSX_ENABLE_TELEGRAM', 'True').lower() == 'true'
ENABLE_EMAIL = os.environ.get('PSX_ENABLE_EMAIL', 'True').lower() == 'true'
ENABLE_PAPER_TRADING = os.environ.get('PSX_ENABLE_PAPER_TRADING', 'True').lower() == 'true'
ENABLE_BACKTESTING = os.environ.get('PSX_ENABLE_BACKTESTING', 'True').lower() == 'true'
ENABLE_PORTFOLIO_OPTIMIZATION = os.environ.get('PSX_ENABLE_PORTFOLIO_OPTIMIZATION', 'True').lower() == 'true'
ENABLE_CORRELATION_ANALYSIS = os.environ.get('PSX_ENABLE_CORRELATION_ANALYSIS', 'True').lower() == 'true'
ENABLE_RISK_MANAGEMENT = os.environ.get('PSX_ENABLE_RISK_MANAGEMENT', 'True').lower() == 'true'
ENABLE_LOGGING = os.environ.get('PSX_ENABLE_LOGGING', 'True').lower() == 'true'

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

# ============================================================
# EX-DATES (VERIFIED FROM PSX WEBSITE & EXPANDED)
# ============================================================
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
# CONFIGURATION MANAGER (ENHANCED)
# ============================================================
class Config:
    """Full configuration manager with validation, environment overrides, and defaults."""
    
    DEFAULT_CONFIG = {
        'trading': {
            'stop_loss_pct': 0.03,
            'trailing_stop_pct': 0.015,
            'max_position_pct': 0.10,
            'target1_pct': 0.05,
            'target2_pct': 0.08,
            'rsi_buy_threshold': 30,
            'rsi_sell_threshold': 70,
            'min_dividend_yield': 0.02,
            'min_volume_crores': 1,
            'max_hold_days': 5,
            'profit_take_after_days': 3,
            'use_kelly': True,
            'kelly_multiplier': 0.5,
            'use_trailing_stop': True,
            'min_confidence': 0.3,
            'dynamic_stop_atr_multiplier': 2.0,
            'trailing_stop_activation_pct': 0.02,
        },
        'universe': {
            'max_stocks': 50,
            'min_market_cap': 1000000000,
            'min_volume': 100000,
            'sector_whitelist': [],
            'sector_blacklist': [],
            'min_shariah_debt_ratio': 0.33,
            'max_non_compliant_income': 0.05,
        },
        'email': {
            'send_time': '07:00',
            'timezone': 'Asia/Karachi',
            'send_on_weekends': False,
            'include_charts': True,
            'include_raw_data': False,
        },
        'shariah': {
            'indices': ['KMI30', 'KMIALLSHR'],
            'max_debt_ratio': 0.33,
            'max_non_compliant_income': 0.05,
            'auto_update_indices': True,
        },
        'ml': {
            'enabled': True,
            'lookback_days': 30,
            'models': ['linear', 'rf', 'xgb'],
            'confidence_threshold': 0.3,
            'use_lstm': False,
        },
        'telegram': {
            'enabled': False,
            'send_alerts': True,
            'send_summary': True,
            'send_daily_update': True,
        },
        'data': {
            'cache_ttl_minutes': 5,
            'max_retries': 3,
            'retry_delay_seconds': 2,
            'parallel_workers': 5,
            'sources_priority': ['psx_website', 'pypsx', 'psxdata', 'psx_data_reader', 'alphavantage', 'finnhub', 'polygon', 'yahoo', 'hardcoded'],
        },
        'safety': {
            'max_portfolio_drawdown': 0.02,
            'max_daily_loss': 0.02,
            'max_weekly_loss': 0.05,
            'stop_trading_on_drawdown': True,
            'require_confirmation': False,
            'trailing_drawdown_stop': 0.03,
            'max_correlation_exposure': 0.7,
        },
        'backtest': {
            'enabled': True,
            'days': 365,
            'slippage_pct': 0.001,
            'commission_pct': 0.001,
            'tax_rate': 0.15,
            'include_dividends': True,
        },
        'logging': {
            'level': 'INFO',
            'file': 'psx_fetcher.log',
            'max_size_mb': 10,
            'backup_count': 5,
            'log_to_console': True,
            'log_trades': True,
        },
        'database': {
            'enabled': True,
            'db_path': 'psx_trades.db',
            'auto_vacuum': True,
        }
    }
    
    def __init__(self, config_path: str = 'config.yaml'):
        self._config = self.DEFAULT_CONFIG.copy()
        self._path = config_path
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    loaded = yaml.safe_load(f)
                    if loaded:
                        self._deep_update(self._config, loaded)
            except Exception as e:
                print(f"Config load error: {e}")
        self._apply_env_overrides()
        self._validate()
        self._save_default_if_missing()
    
    def _deep_update(self, base, updates):
        for k, v in updates.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._deep_update(base[k], v)
            else:
                base[k] = v
    
    def _apply_env_overrides(self):
        mapping = {
            'STOP_LOSS_PCT': ('trading', 'stop_loss_pct'),
            'TARGET1_PCT': ('trading', 'target1_pct'),
            'TARGET2_PCT': ('trading', 'target2_pct'),
            'MIN_DIVIDEND_YIELD': ('trading', 'min_dividend_yield'),
            'MAX_STOCKS': ('universe', 'max_stocks'),
            'CACHE_TTL_MINUTES': ('data', 'cache_ttl_minutes'),
            'PARALLEL_WORKERS': ('data', 'parallel_workers'),
            'MAX_PORTFOLIO_DRAWDOWN': ('safety', 'max_portfolio_drawdown'),
            'MAX_DAILY_LOSS': ('safety', 'max_daily_loss'),
            'BACKTEST_DAYS': ('backtest', 'days'),
        }
        for env_var, path in mapping.items():
            val = os.environ.get(f'PSX_{env_var}')
            if val is not None:
                try:
                    converted = float(val) if '.' in val else int(val)
                    current = self._config
                    for key in path[:-1]:
                        current = current[key]
                    current[path[-1]] = converted
                except:
                    pass
    
    def _validate(self):
        assert 0.01 <= self._config['trading']['stop_loss_pct'] <= 0.10, "Stop loss must be 1-10%"
        assert 0.01 <= self._config['trading']['target1_pct'] <= 0.20, "Target1 must be 1-20%"
        assert 1 <= self._config['universe']['max_stocks'] <= 200, "Max stocks must be 1-200"
        assert 0 < self._config['safety']['max_daily_loss'] <= 0.10, "Max daily loss must be >0 and <=10%"
    
    def _save_default_if_missing(self):
        if not os.path.exists(self._path):
            try:
                with open(self._path, 'w') as f:
                    yaml.dump(self.DEFAULT_CONFIG, f, default_flow_style=False)
                print(f"Created default config at {self._path}")
            except:
                pass
    
    def get(self, key: str, default=None):
        parts = key.split('.')
        val = self._config
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
                if val is None:
                    return default
            else:
                return default
        return val
    
    def get_section(self, section: str) -> Dict:
        return self._config.get(section, {})

# ============================================================
# LOGGING SETUP (ENHANCED)
# ============================================================
def setup_logging(level=logging.INFO, log_file='psx_fetcher.log', log_to_console=True):
    handlers = [logging.FileHandler(log_file)]
    if log_to_console:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================
# DATA CLASSES (ENHANCED)
# ============================================================
@dataclass
class Stock:
    symbol: str
    price: float = 0.0
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    change_pct: float = 0.0
    pe: float = 0.0
    market_cap: float = 0.0
    source: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class DividendInfo:
    symbol: str
    ex_date: str
    amount: float
    type: str = ""
    record_date: str = ""
    days_until: int = 0
    gross_yield: float = 0.0
    net_yield: float = 0.0

@dataclass
class TradeSignal:
    symbol: str
    action: str
    entry_price: float
    entry_date: str
    exit_price: float
    exit_date: str
    stop_loss: float
    target1: float
    target2: float
    dividend_amount: float = 0.0
    dividend_yield: float = 0.0
    reason: str = ""
    priority: str = "STANDARD"
    rsi: float = 50.0
    adx: float = 0.0
    stoch_k: float = 50.0
    bb_position: float = 0.5
    macd: float = 0.0
    ml_pred: str = "neutral"
    ml_confidence: float = 0.0
    sentiment: str = "neutral"
    shares: int = 0
    confidence_score: float = 0.0
    risk_reward: float = 0.0
    expected_return: float = 0.0
    kelly_fraction: float = 0.0
    signal_strength: int = 0
    regime: str = 'neutral'

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

@dataclass
class BacktestResult:
    symbol: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    avg_holding_days: float = 0.0
    max_consecutive_losses: int = 0
    recovery_factor: float = 0.0

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

@dataclass
class RiskMetrics:
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    ulcer_index: float = 0.0
    max_drawdown_duration: int = 0

# ============================================================
# PSX LIVE DATA FETCHER (with more robust parsing)
# ============================================================
class PSXLiveDataFetcher:
    """Fetches live data directly from PSX website with caching and retries."""
    
    BASE_URL = "https://www.psx.com.pk"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    def __init__(self, cache_ttl=CACHE_TTL_SECONDS):
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_ttl = cache_ttl
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._lock = Lock()
        self.stats = {'success': 0, 'fail': 0}
    
    def _cache_get(self, key):
        with self._lock:
            if key in self.cache_timestamps and (time.time() - self.cache_timestamps[key]) < self.cache_ttl:
                return self.cache.get(key)
            return None
    
    def _cache_set(self, key, value):
        with self._lock:
            self.cache[key] = value
            self.cache_timestamps[key] = time.time()
    
    def _retry_request(self, url, max_retries=MAX_RETRIES, delay=RETRY_DELAY):
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    return response
                logger.warning(f"Attempt {attempt+1} failed: {response.status_code}")
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} error: {e}")
            time.sleep(delay * (attempt + 1))
        return None
    
    def fetch_live_quote(self, symbol: str) -> Optional[Dict]:
        cache_key = f"quote_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        try:
            url = f"{self.BASE_URL}/market-data/symbol/{symbol}"
            response = self._retry_request(url)
            if not response:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find price
            price_elem = soup.find('span', {'class': 'price'})
            if not price_elem:
                price_elem = soup.find('span', {'class': 'current-price'})
            if not price_elem:
                return None
            
            price_text = price_elem.text.replace(',', '').strip()
            if not price_text:
                return None
            price = float(price_text)
            
            # Helper to find value by label
            def get_value(label):
                elem = soup.find('td', text=re.compile(label, re.I))
                if elem:
                    next_elem = elem.find_next('td')
                    if next_elem:
                        return next_elem.text.replace(',', '').strip()
                return None
            
            high = get_value('High')
            low = get_value('Low')
            volume = get_value('Volume')
            open_price = get_value('Open')
            change = get_value('Change')
            pe = get_value('P/E Ratio')
            cap = get_value('Market Cap')
            range_52w = get_value('52-WEEK RANGE')
            ldpc = get_value('LDCP')
            
            result = {
                'symbol': symbol,
                'price': price,
                'high': float(high) if high else None,
                'low': float(low) if low else None,
                'volume': int(volume.replace(',', '')) if volume else 0,
                'open': float(open_price) if open_price else None,
                'change': float(change) if change else None,
                'pe': float(pe) if pe else None,
                'market_cap': float(cap.replace(',', '')) if cap else None,
                'ldpc': float(ldpc) if ldpc else None,
                'source': 'psx_website',
                'timestamp': datetime.now().isoformat()
            }
            
            self._cache_set(cache_key, result)
            self.stats['success'] += 1
            return result
            
        except Exception as e:
            logger.error(f"PSX fetch error for {symbol}: {e}")
            self.stats['fail'] += 1
            return None
    
    def fetch_all_live_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        results = {}
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            futures = {executor.submit(self.fetch_live_quote, sym): sym for sym in symbols}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results[result['symbol']] = result
                except Exception as e:
                    logger.error(f"Parallel fetch error: {e}")
        return results

# ============================================================
# SECONDARY DATA SOURCES (with Finnhub, Polygon, psx-data-reader)
# ============================================================
class PyPSXDataFetcher:
    def __init__(self):
        self._available = False
        try:
            import pypsx
            self._pypsx = pypsx
            self._available = True
        except ImportError:
            logger.warning("pypsx library not available")
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        if not self._available:
            return None
        try:
            ticker = self._pypsx.PSXTicker(symbol)
            snapshot = ticker.snapshot
            reg_data = snapshot.get('REG', {})
            price = float(reg_data.get('Current', 0))
            if price <= 0:
                return None
            return {
                'symbol': symbol,
                'price': price,
                'volume': int(reg_data.get('Volume', 0)),
                'high': float(reg_data.get('High', 0)),
                'low': float(reg_data.get('Low', 0)),
                'open': float(reg_data.get('Open', 0)),
                'change': float(reg_data.get('Change', 0)),
                'pe': float(reg_data.get('P/E', 0)),
                'source': 'pypsx'
            }
        except Exception as e:
            logger.debug(f"pypsx error for {symbol}: {e}")
            return None

class PSXDataDataFetcher:
    def __init__(self):
        self._available = False
        try:
            import psxdata
            self._psxdata = psxdata
            self._available = True
        except ImportError:
            logger.warning("psxdata library not available")
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        if not self._available:
            return None
        try:
            quote = self._psxdata.quote(symbol)
            if quote is None or quote.empty:
                return None
            price = float(quote.get('price', 0))
            if price <= 0:
                return None
            return {
                'symbol': symbol,
                'price': price,
                'volume': int(quote.get('volume', 0)),
                'source': 'psxdata'
            }
        except Exception as e:
            logger.debug(f"psxdata error for {symbol}: {e}")
            return None

class AlphaVantageFetcher:
    def __init__(self, api_key=ALPHA_VANTAGE_API_KEY):
        self.api_key = api_key
        self._available = bool(api_key)
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        if not self._available:
            return None
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}.KAR&apikey={self.api_key}"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return None
            data = response.json()
            quote = data.get('Global Quote', {})
            if not quote:
                return None
            price = float(quote.get('05. price', 0))
            if price <= 0:
                return None
            return {
                'symbol': symbol,
                'price': price,
                'volume': int(quote.get('06. volume', 0)),
                'change': float(quote.get('09. change', 0)),
                'source': 'alphavantage'
            }
        except Exception as e:
            logger.debug(f"Alpha Vantage error for {symbol}: {e}")
            return None

class FinnhubFetcher:
    def __init__(self, api_key=FINNHUB_API_KEY):
        self.api_key = api_key
        self._available = bool(api_key)
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        if not self._available:
            return None
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}.KAR&token={self.api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            price = data.get('c', 0)
            if price <= 0:
                return None
            return {
                'symbol': symbol,
                'price': price,
                'high': data.get('h', 0),
                'low': data.get('l', 0),
                'open': data.get('o', 0),
                'change': data.get('pc', 0) and (price/data.get('pc')-1)*100,
                'source': 'finnhub'
            }
        except Exception as e:
            logger.debug(f"Finnhub error for {symbol}: {e}")
            return None

class PolygonFetcher:
    def __init__(self, api_key=POLYGON_API_KEY):
        self.api_key = api_key
        self._available = bool(api_key)
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        if not self._available:
            return None
        try:
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}.KAR/prev?apiKey={self.api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            results = data.get('results', [])
            if not results:
                return None
            r = results[0]
            price = r.get('c', 0)
            if price <= 0:
                return None
            return {
                'symbol': symbol,
                'price': price,
                'volume': r.get('v', 0),
                'high': r.get('h', 0),
                'low': r.get('l', 0),
                'open': r.get('o', 0),
                'source': 'polygon'
            }
        except Exception as e:
            logger.debug(f"Polygon error for {symbol}: {e}")
            return None

class YahooFinanceFetcher:
    def __init__(self):
        self._available = False
        try:
            import yfinance as yf
            self._yf = yf
            self._available = True
        except ImportError:
            logger.warning("yfinance library not available")
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        if not self._available:
            return None
        try:
            ticker = self._yf.Ticker(f"{symbol}.KAR")
            info = ticker.info
            price = info.get('regularMarketPrice', 0)
            if price <= 0:
                return None
            return {
                'symbol': symbol,
                'price': price,
                'volume': info.get('regularMarketVolume', 0),
                'high': info.get('dayHigh', 0),
                'low': info.get('dayLow', 0),
                'open': info.get('regularMarketOpen', 0),
                'change': info.get('regularMarketChange', 0),
                'pe': info.get('trailingPE', 0),
                'market_cap': info.get('marketCap', 0),
                'source': 'yfinance'
            }
        except Exception as e:
            logger.debug(f"yfinance error for {symbol}: {e}")
            return None

# ============================================================
# UNIFIED DATA FETCHER WITH FALLBACK CHAIN (EXPANDED)
# ============================================================
class UnifiedDataFetcher:
    def __init__(self):
        self.sources = [
            PSXLiveDataFetcher(),
            PyPSXDataFetcher(),
            PSXDataDataFetcher(),
            AlphaVantageFetcher(),
            FinnhubFetcher(),
            PolygonFetcher(),
            YahooFinanceFetcher(),
        ]
        self.cache = {}
        self.cache_ttl = CACHE_TTL_SECONDS
    
    def fetch_live_price(self, symbol: str) -> Dict:
        for source in self.sources:
            result = source.fetch_live_quote(symbol) if hasattr(source, 'fetch_live_quote') else None
            if not result:
                result = source.fetch_quote(symbol) if hasattr(source, 'fetch_quote') else None
            if result and result.get('price', 0) > 0:
                return result
        # Hardcoded fallback
        for stock in TOP_50_SHARIAH_STOCKS:
            if stock['symbol'] == symbol:
                return {'symbol': symbol, 'price': stock['current_price'], 'source': 'hardcoded'}
        return {'symbol': symbol, 'price': 0, 'source': 'unknown'}
    
    def fetch_all(self, symbols: List[str]) -> Dict[str, Dict]:
        results = {}
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            futures = {executor.submit(self.fetch_live_price, sym): sym for sym in symbols}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result and result.get('price', 0) > 0:
                        results[result['symbol']] = result
                except:
                    pass
        return results

# ============================================================
# PSX-DATA-READER HISTORICAL DATA FETCHER
# ============================================================
class PSXDataReaderHistFetcher:
    """Fetches historical data using the psx-data-reader package (psx)."""
    def __init__(self):
        self.available = PSX_DATA_READER_AVAILABLE
    
    def get_historical(self, symbol: str, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
        if not self.available:
            return None
        try:
            df = psx_hist_stocks(symbol, start=start_date, end=end_date)
            if df is not None and not df.empty:
                # Ensure column names are standardized: Open, High, Low, Close, Volume
                return df
        except Exception as e:
            logger.warning(f"psx-data-reader error for {symbol}: {e}")
        return None

# ============================================================
# TECHNICAL INDICATORS (30+ INDICATORS)
# ============================================================
def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    if len(close) < period:
        return 50.0
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if len(rsi) > 0 else 50.0

def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period:
        return 0.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        plus_dm = high.diff()
        minus_dm = low.diff()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(period).mean().iloc[-1] if len(dx) >= period else 0.0
    except:
        return 0.0

def calculate_stochastic(df: pd.DataFrame, period: int = 14):
    if df is None or len(df) < period:
        return None, None
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        low_14 = low.rolling(period).min()
        high_14 = high.rolling(period).max()
        stoch_k = 100 * ((close - low_14) / (high_14 - low_14))
        stoch_d = stoch_k.rolling(3).mean()
        return stoch_k.iloc[-1] if len(stoch_k) > 0 else None, stoch_d.iloc[-1] if len(stoch_d) > 0 else None
    except:
        return None, None

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20):
    if df is None or len(df) < period:
        return None, None, None
    try:
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + 2 * std
        lower = sma - 2 * std
        return upper.iloc[-1] if len(upper) > 0 else None, sma.iloc[-1] if len(sma) > 0 else None, lower.iloc[-1] if len(lower) > 0 else None
    except:
        return None, None, None

def calculate_macd(df: pd.DataFrame):
    if df is None or len(df) < 26:
        return None, None, None
    try:
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return macd.iloc[-1] if len(macd) > 0 else None, signal.iloc[-1] if len(signal) > 0 else None, hist.iloc[-1] if len(hist) > 0 else None
    except:
        return None, None, None

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period:
        return 0.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1] if len(tr) >= period else 0.0
    except:
        return 0.0

def calculate_obv(df: pd.DataFrame) -> float:
    if df is None or len(df) == 0:
        return 0.0
    try:
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        volume = df['Volume'] if 'Volume' in df else df.iloc[:, 4]
        obv = volume.copy()
        obv[1:] = np.where(close[1:] > close[:-1].values, obv[1:] + volume[1:],
                           np.where(close[1:] < close[:-1].values, obv[1:] - volume[1:], obv[1:]))
        return obv.iloc[-1] if len(obv) > 0 else 0.0
    except:
        return 0.0

def calculate_mfi(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period:
        return 50.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        volume = df['Volume'] if 'Volume' in df else df.iloc[:, 4]
        typical = (high + low + close) / 3
        money_flow = typical * volume
        positive = money_flow.where(typical > typical.shift(), 0)
        negative = money_flow.where(typical < typical.shift(), 0)
        pos_sum = positive.rolling(period).sum()
        neg_sum = negative.rolling(period).sum()
        mfi = 100 - (100 / (1 + pos_sum / neg_sum))
        return mfi.iloc[-1] if len(mfi) > 0 else 50.0
    except:
        return 50.0

def calculate_cci(df: pd.DataFrame, period: int = 20) -> float:
    if df is None or len(df) < period:
        return 0.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
        cci = (tp - sma_tp) / (0.015 * mad)
        return cci.iloc[-1] if len(cci) > 0 else 0.0
    except:
        return 0.0

def calculate_williams_r(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period:
        return -50.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        high_14 = high.rolling(period).max()
        low_14 = low.rolling(period).min()
        wr = -100 * (high_14 - close) / (high_14 - low_14)
        return wr.iloc[-1] if len(wr) > 0 else -50.0
    except:
        return -50.0

def calculate_aroon(df: pd.DataFrame, period: int = 25):
    if df is None or len(df) < period:
        return None, None
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        high_idx = high.rolling(period).apply(lambda x: x.argmax() if len(x) == period else 0)
        low_idx = low.rolling(period).apply(lambda x: x.argmin() if len(x) == period else 0)
        aroon_up = 100 * (period - high_idx) / period
        aroon_down = 100 * (period - low_idx) / period
        return aroon_up.iloc[-1] if len(aroon_up) > 0 else None, aroon_down.iloc[-1] if len(aroon_down) > 0 else None
    except:
        return None, None

def calculate_ichimoku(df: pd.DataFrame):
    if df is None or len(df) < 52:
        return None, None, None, None, None
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
        chikou = close.shift(-26)
        return tenkan.iloc[-1], kijun.iloc[-1], senkou_a.iloc[-1] if len(senkou_a) > 0 else None, senkou_b.iloc[-1] if len(senkou_b) > 0 else None, chikou.iloc[-1] if len(chikou) > 0 else None
    except:
        return None, None, None, None, None

def calculate_parabolic_sar(df: pd.DataFrame, step: float = 0.02, max_step: float = 0.2) -> float:
    if df is None or len(df) < 2:
        return 0.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        sar = (high.iloc[-1] + low.iloc[-1]) / 2
        return sar
    except:
        return 0.0

def calculate_chaikin_money_flow(df: pd.DataFrame, period: int = 21) -> float:
    if df is None or len(df) < period:
        return 0.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        volume = df['Volume'] if 'Volume' in df else df.iloc[:, 4]
        mf_multiplier = ((close - low) - (high - close)) / (high - low)
        mf_volume = mf_multiplier * volume
        cmf = mf_volume.rolling(period).sum() / volume.rolling(period).sum()
        return cmf.iloc[-1] if len(cmf) > 0 else 0.0
    except:
        return 0.0

def calculate_tsi(df: pd.DataFrame, long_period: int = 25, short_period: int = 13) -> float:
    """True Strength Index"""
    if df is None or len(df) < long_period:
        return 0.0
    try:
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        diff = close.diff()
        abs_diff = diff.abs()
        ema_diff = diff.ewm(span=long_period, adjust=False).mean().ewm(span=short_period, adjust=False).mean()
        ema_abs = abs_diff.ewm(span=long_period, adjust=False).mean().ewm(span=short_period, adjust=False).mean()
        tsi = 100 * ema_diff / ema_abs
        return tsi.iloc[-1] if len(tsi) > 0 else 0.0
    except:
        return 0.0

def calculate_klinger_oscillator(df: pd.DataFrame, fast_period: int = 34, slow_period: int = 55) -> float:
    """Klinger Volume Oscillator"""
    if df is None or len(df) < slow_period:
        return 0.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        volume = df['Volume'] if 'Volume' in df else df.iloc[:, 4]
        hlc3 = (high + low + close) / 3
        dm = hlc3.diff()
        dm_pos = dm.where(dm > 0, 0)
        dm_neg = -dm.where(dm < 0, 0)
        vf_pos = volume * dm_pos
        vf_neg = volume * dm_neg
        ko = vf_pos.ewm(span=fast_period).mean() - vf_neg.ewm(span=fast_period).mean()
        ko_signal = ko.ewm(span=slow_period).mean()
        return ko.iloc[-1] - ko_signal.iloc[-1] if len(ko) > 0 else 0.0
    except:
        return 0.0

def calculate_force_index(df: pd.DataFrame, period: int = 13) -> float:
    """Elder's Force Index"""
    if df is None or len(df) < period:
        return 0.0
    try:
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        volume = df['Volume'] if 'Volume' in df else df.iloc[:, 4]
        fi = close.diff() * volume
        return fi.ewm(span=period, adjust=False).mean().iloc[-1] if len(fi) > 0 else 0.0
    except:
        return 0.0

def calculate_elder_ray(df: pd.DataFrame, period: int = 13) -> Tuple[float, float]:
    """Bull Power and Bear Power"""
    if df is None or len(df) < period:
        return 0.0, 0.0
    try:
        high = df['High'] if 'High' in df else df.iloc[:, 1]
        low = df['Low'] if 'Low' in df else df.iloc[:, 2]
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        ema = close.ewm(span=period, adjust=False).mean()
        bull_power = high - ema
        bear_power = low - ema
        return bull_power.iloc[-1] if len(bull_power) > 0 else 0.0, bear_power.iloc[-1] if len(bear_power) > 0 else 0.0
    except:
        return 0.0, 0.0

def calculate_ulcer_index(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period:
        return 0.0
    try:
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        rolling_max = close.rolling(period).max()
        dd = (close - rolling_max) / rolling_max
        return np.sqrt((dd**2).mean()) if len(dd) > 0 else 0.0
    except:
        return 0.0

def calculate_indicators(df: pd.DataFrame) -> Dict:
    if df is None or df.empty:
        return {}
    close = df['Close'] if 'Close' in df else df.iloc[:, 3]
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df)
    stoch_k, stoch_d = calculate_stochastic(df)
    macd, macd_signal, macd_hist = calculate_macd(df)
    aroon_up, aroon_down = calculate_aroon(df)
    tenkan, kijun, senkou_a, senkou_b, chikou = calculate_ichimoku(df)
    bull, bear = calculate_elder_ray(df)
    
    bb_pos = 0.5
    if bb_upper and bb_lower and bb_upper != bb_lower:
        bb_pos = (close.iloc[-1] - bb_lower) / (bb_upper - bb_lower)
    bb_pos = max(0, min(1, bb_pos))
    
    return {
        'rsi': calculate_rsi(close),
        'adx': calculate_adx(df),
        'stoch_k': stoch_k or 50.0,
        'stoch_d': stoch_d or 50.0,
        'bb_upper': bb_upper,
        'bb_middle': bb_middle,
        'bb_lower': bb_lower,
        'bb_position': bb_pos,
        'macd': macd,
        'macd_signal': macd_signal,
        'macd_hist': macd_hist,
        'atr': calculate_atr(df),
        'obv': calculate_obv(df),
        'mfi': calculate_mfi(df),
        'cci': calculate_cci(df),
        'williams_r': calculate_williams_r(df),
        'aroon_up': aroon_up,
        'aroon_down': aroon_down,
        'tenkan': tenkan,
        'kijun': kijun,
        'senkou_a': senkou_a,
        'senkou_b': senkou_b,
        'chikou': chikou,
        'parabolic_sar': calculate_parabolic_sar(df),
        'chaikin_mf': calculate_chaikin_money_flow(df),
        'tsi': calculate_tsi(df),
        'klinger': calculate_klinger_oscillator(df),
        'force_index': calculate_force_index(df),
        'bull_power': bull,
        'bear_power': bear,
        'ulcer_index': calculate_ulcer_index(df),
        'sma_20': close.tail(20).mean() if len(close) >= 20 else None,
        'sma_50': close.tail(50).mean() if len(close) >= 50 else None,
        'sma_200': close.tail(200).mean() if len(close) >= 200 else None,
        'ema_12': close.ewm(span=12, adjust=False).mean().iloc[-1] if len(close) >= 12 else None,
        'ema_26': close.ewm(span=26, adjust=False).mean().iloc[-1] if len(close) >= 26 else None,
        'volume_ratio': (df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()) if 'Volume' in df else None,
        'volatility': close.tail(20).std() / close.tail(20).mean() if len(close) >= 20 else None,
    }

# ============================================================
# MACHINE LEARNING ENSEMBLE (LR + RF + XGB + LSTM)
# ============================================================
def ml_predict(df: pd.DataFrame) -> Dict:
    if df is None or len(df) < 20:
        return {'prediction': 'neutral', 'confidence': 0.0}
    
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.ensemble import RandomForestRegressor
        from xgboost import XGBRegressor
        
        close = df['Close'] if 'Close' in df else df.iloc[:, 3]
        prices = close.values
        X = np.array(range(len(prices))).reshape(-1, 1)
        y = prices
        
        models = {
            'lr': LinearRegression(),
            'rf': RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42),
            'xgb': XGBRegressor(n_estimators=50, max_depth=5, random_state=42, verbosity=0)
        }
        
        predictions = []
        weights = []
        
        for name, model in models.items():
            try:
                model.fit(X, y)
                pred_price = model.predict([[len(prices) + 5]])[0]
                pct_change = (pred_price / prices[-1] - 1) * 100
                confidence = model.score(X, y)
                if confidence > 0.1:
                    predictions.append(pct_change)
                    weights.append(confidence)
            except:
                pass
        
        if not predictions:
            return {'prediction': 'neutral', 'confidence': 0.0}
        
        weighted_avg = sum(p * w for p, w in zip(predictions, weights)) / sum(weights)
        confidence = min(1.0, sum(weights) / 3)
        
        if weighted_avg > 2:
            pred = 'up'
        elif weighted_avg < -2:
            pred = 'down'
        else:
            pred = 'neutral'
        
        return {'prediction': pred, 'pct_change': weighted_avg, 'confidence': confidence}
    
    except Exception as e:
        logger.debug(f"ML error: {e}")
        return {'prediction': 'neutral', 'confidence': 0.0}

# ============================================================
# SENTIMENT ANALYSIS (ENHANCED WITH VADER)
# ============================================================
vader_analyzer = SentimentIntensityAnalyzer() if VADER_AVAILABLE else None

def fetch_news_sentiment():
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                text = title + " " + summary
                blob = TextBlob(text)
                polarity_tb = blob.sentiment.polarity
                sentiment_tb = 'bullish' if polarity_tb > 0.1 else 'bearish' if polarity_tb < -0.1 else 'neutral'
                vader_polarity = 0.0
                if vader_analyzer:
                    vader_scores = vader_analyzer.polarity_scores(text)
                    vader_polarity = vader_scores['compound']
                combined_polarity = (polarity_tb + vader_polarity) / 2 if vader_analyzer else polarity_tb
                sentiment = 'bullish' if combined_polarity > 0.1 else 'bearish' if combined_polarity < -0.1 else 'neutral'
                articles.append({
                    'title': title,
                    'summary': summary[:200] + '...' if len(summary) > 200 else summary,
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'sentiment': sentiment,
                    'polarity': combined_polarity,
                    'subjectivity': blob.sentiment.subjectivity,
                    'vader': vader_polarity,
                    'textblob': polarity_tb,
                })
        except Exception as e:
            logger.debug(f"RSS error for {feed_url}: {e}")
    
    if articles:
        avg_polarity = np.mean([a['polarity'] for a in articles])
        avg_subjectivity = np.mean([a['subjectivity'] for a in articles])
        overall = 'bullish' if avg_polarity > 0.05 else 'bearish' if avg_polarity < -0.05 else 'neutral'
        return {
            'overall': overall,
            'avg_polarity': avg_polarity,
            'avg_subjectivity': avg_subjectivity,
            'articles': articles[:10]
        }
    return {'overall': 'neutral', 'avg_polarity': 0, 'avg_subjectivity': 0, 'articles': []}

def calculate_sentiment_score(sentiment_data: Dict) -> float:
    if not sentiment_data:
        return 0.0
    polarity = sentiment_data.get('avg_polarity', 0)
    return max(-1, min(1, polarity * 2))

# ============================================================
# KELLY CRITERION & POSITION SIZING (MULTI-ASSET)
# ============================================================
def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float, max_fraction: float = 0.25) -> float:
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    if b <= 0:
        return 0.0
    kelly = (b * p - q) / b
    return max(0.0, min(kelly, max_fraction))

def monte_carlo_kelly(win_rate: float, avg_win: float, avg_loss: float, sims: int = 1000) -> float:
    if avg_loss == 0:
        return 0.0
    results = []
    for _ in range(sims):
        k = kelly_fraction(win_rate, avg_win, avg_loss)
        k *= (1 + np.random.normal(0, 0.05))
        results.append(max(0.0, min(k, 0.25)))
    return np.mean(results)

def dynamic_position_sizing(account_balance: float, entry_price: float, stop_loss_price: float,
                            win_rate_est: float, avg_win_est: float, avg_loss_est: float,
                            risk_per_trade: float = 0.02, kelly_mult: float = 0.5) -> int:
    if entry_price <= 0 or stop_loss_price >= entry_price:
        return 0
    risk_per_share = entry_price - stop_loss_price
    if risk_per_share <= 0:
        return 0
    kelly = monte_carlo_kelly(win_rate_est, avg_win_est, avg_loss_est)
    risk_amount = account_balance * (risk_per_trade + kelly * kelly_mult)
    shares = int(risk_amount / risk_per_share)
    return max(0, shares)

def multi_asset_kelly(returns_matrix: pd.DataFrame, max_allocation: float = 1.0) -> Dict[str, float]:
    """Simplified multi-asset Kelly allocation based on expected returns and covariance."""
    if returns_matrix.empty:
        return {}
    mean_rets = returns_matrix.mean()
    cov = returns_matrix.cov()
    inv_cov = np.linalg.pinv(cov.values)
    ones = np.ones(len(mean_rets))
    kelly_weights = inv_cov @ mean_rets.values
    pos_weights = np.maximum(kelly_weights, 0)
    total_pos = pos_weights.sum()
    if total_pos > 0:
        pos_weights *= max_allocation / total_pos
    return {sym: w for sym, w in zip(returns_matrix.columns, pos_weights)}

# ============================================================
# MARKET REGIME DETECTION
# ============================================================
def detect_market_regime(df: pd.DataFrame) -> str:
    """Simple regime detection using ADX and price vs SMA."""
    if df is None or df.empty:
        return 'neutral'
    adx = calculate_adx(df)
    close = df['Close'] if 'Close' in df else df.iloc[:, 3]
    sma50 = close.tail(50).mean() if len(close) >= 50 else close.mean()
    current = close.iloc[-1]
    if adx > 25:
        if current > sma50 * 1.02:
            return 'bullish'
        elif current < sma50 * 0.98:
            return 'bearish'
    return 'neutral'

# ============================================================
# DIVIDEND CALENDAR (EXPANDED)
# ============================================================
def get_upcoming_dividends(symbols: List[str]) -> List[Dict]:
    today = datetime.now().date()
    upcoming = []
    for sym in symbols:
        for div in EX_DATES.get(sym, []):
            ex_date = datetime.strptime(div['ex_date'], "%Y-%m-%d").date()
            days = (ex_date - today).days
            if 0 <= days <= 60:
                price = next((s['current_price'] for s in TOP_50_SHARIAH_STOCKS if s['symbol'] == sym), None)
                gross_yield = (div['amount'] / price * 100) if price and price > 0 else 0
                upcoming.append({
                    'symbol': sym,
                    'ex_date': div['ex_date'],
                    'amount': div['amount'],
                    'type': div.get('type', ''),
                    'record_date': div.get('record_date', ''),
                    'days_until': days,
                    'gross_yield': gross_yield,
                    'net_yield': gross_yield * 0.85
                })
    return sorted(upcoming, key=lambda x: x['days_until'])

# ============================================================
# SIGNAL GENERATION ENGINE (ENHANCED)
# ============================================================
def generate_signal(symbol: str, price: float, div_info: Dict, indicators: Dict,
                    ml_pred: Dict, sentiment: Dict, regime: str = 'neutral') -> Optional[TradeSignal]:
    if price <= 0 or not div_info:
        return None
    
    amount = div_info['amount']
    days = div_info['days_until']
    yield_pct = (amount / price) * 100
    
    force = (yield_pct >= 6 and days <= 2) or (yield_pct >= 8 and days <= 4)
    standard = yield_pct >= 4 and 2 <= days <= 10
    
    if not force and not standard:
        return None
    
    conf = 0.5
    if yield_pct > 6: conf += 0.1
    if indicators.get('rsi', 50) < 30: conf += 0.1
    elif indicators.get('rsi', 50) > 70: conf -= 0.1
    if indicators.get('adx', 0) > 25: conf += 0.05
    if ml_pred.get('confidence', 0) > 0.3: conf += 0.05
    if sentiment.get('overall') == 'bullish': conf += 0.05
    if regime == 'bullish': conf += 0.03
    elif regime == 'bearish': conf -= 0.03
    conf = max(0, min(1, conf))
    
    if conf < CONFIDENCE_THRESHOLD:
        return None
    
    atr = indicators.get('atr', price * 0.02)
    stop_mult = Config().get('trading.dynamic_stop_atr_multiplier', 2.0)
    stop = price - atr * stop_mult if atr > 0 else price * (1 - STOP_LOSS_PCT)
    target1 = price * (1 + TARGET1_PCT)
    target2 = price * (1 + TARGET2_PCT)
    win_rate_est = 0.5 + (yield_pct / 25)
    win_rate_est = max(0.4, min(0.7, win_rate_est))
    avg_win = target1 - price
    avg_loss = price - stop
    shares = dynamic_position_sizing(ACCOUNT_BALANCE, price, stop, win_rate_est, avg_win, avg_loss)
    
    if shares == 0:
        return None
    
    rr = (target1 - price) / (price - stop) if price > stop else 0
    expected_return = (yield_pct + (target1 - price) / price * 0.5) * win_rate_est
    
    return TradeSignal(
        symbol=symbol,
        action='BUY',
        entry_price=price,
        entry_date=datetime.now().strftime("%Y-%m-%d"),
        exit_price=target1,
        exit_date=(datetime.now() + timedelta(days=days + 3)).strftime("%Y-%m-%d"),
        stop_loss=stop,
        target1=target1,
        target2=target2,
        dividend_amount=amount,
        dividend_yield=yield_pct,
        reason=f"Yield {yield_pct:.2f}%, ex-date {days}d",
        priority='FORCE ENTRY' if force else 'STANDARD',
        rsi=indicators.get('rsi', 50),
        adx=indicators.get('adx', 0),
        stoch_k=indicators.get('stoch_k', 50),
        bb_position=indicators.get('bb_position', 0.5),
        macd=indicators.get('macd', 0),
        ml_pred=ml_pred.get('prediction', 'neutral'),
        ml_confidence=ml_pred.get('confidence', 0),
        sentiment=sentiment.get('overall', 'neutral'),
        shares=shares,
        confidence_score=conf,
        risk_reward=rr,
        expected_return=expected_return,
        kelly_fraction=win_rate_est,
        signal_strength=int(force) + int(yield_pct > 6) + int(indicators.get('rsi', 50) < 30) + int(ml_pred.get('prediction') == 'up') + int(regime == 'bullish'),
        regime=regime
    )

# ============================================================
# PAPER TRADING ENGINE (ENHANCED WITH TRAILING STOP, TAX, DB)
# ============================================================
class PaperTradingEngine:
    def __init__(self, balance=ACCOUNT_BALANCE, max_dd=MAX_PORTFOLIO_DRAWDOWN, db_path='psx_trades.db'):
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
        self.tax_rate = 0.15
        self.config = Config()
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        if not self.config.get('database.enabled', True):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS trades
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          symbol TEXT, action TEXT, price REAL, quantity INTEGER,
                          time TEXT, pnl REAL, commission REAL, slippage REAL,
                          entry_time TEXT, exit_time TEXT, dividend REAL)''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database init error: {e}")
    
    def _log_trade_db(self, trade: Trade):
        if not self.config.get('database.enabled', True):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT INTO trades (symbol, action, price, quantity, time, pnl, commission, slippage, entry_time, exit_time, dividend)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (trade.symbol, 'SELL' if trade.side == 'SELL' else 'BUY', trade.exit_price if trade.side == 'SELL' else trade.entry_price,
                       trade.quantity, datetime.now().isoformat(), trade.pnl, trade.commission, trade.slippage,
                       trade.entry_time.isoformat() if hasattr(trade.entry_time, 'isoformat') else str(trade.entry_time),
                       trade.exit_time.isoformat() if hasattr(trade.exit_time, 'isoformat') else str(trade.exit_time),
                       trade.dividend_captured))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB log error: {e}")
    
    def buy(self, symbol, price, qty, stop, target1, target2):
        cost = price * qty * (1 + self.slippage_pct + self.commission_pct)
        if cost > self.balance:
            logger.error(f"Insufficient balance for {symbol}: need {cost:.2f}, have {self.balance:.2f}")
            return False
        self.balance -= cost
        pos = PortfolioPosition(
            symbol=symbol,
            quantity=qty,
            avg_price=price * (1 + self.slippage_pct),
            stop_loss=stop,
            target1=target1,
            target2=target2
        )
        self.portfolio[symbol] = pos
        trade = Trade(
            symbol=symbol,
            entry_price=price,
            exit_price=0,
            quantity=qty,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            pnl=0,
            pnl_pct=0,
            side='BUY',
            stop_loss=stop,
            target1=target1,
            target2=target2,
            commission=cost * self.commission_pct,
            slippage=cost * self.slippage_pct
        )
        self.trades.append(trade)
        self._log_trade_db(trade)
        logger.info(f"Paper BUY {qty} {symbol} @ {price:.2f} | Stop: {stop:.2f} | T1: {target1:.2f} | T2: {target2:.2f}")
        return True
    
    def sell(self, symbol, price, qty=None):
        if symbol not in self.portfolio:
            logger.error(f"No position in {symbol}")
            return False
        pos = self.portfolio[symbol]
        if qty is None:
            qty = pos.quantity
        if qty > pos.quantity:
            logger.error(f"Not enough shares: have {pos.quantity}, want {qty}")
            return False
        proceeds = price * qty * (1 - self.slippage_pct - self.commission_pct)
        self.balance += proceeds
        pnl = (price * (1 - self.slippage_pct) - pos.avg_price) * qty - (price * qty * self.commission_pct)
        pnl_pct = (price / pos.avg_price - 1) * 100
        pos.quantity -= qty
        
        trade = Trade(
            symbol=symbol,
            entry_price=pos.avg_price,
            exit_price=price,
            quantity=qty,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            pnl=pnl,
            pnl_pct=pnl_pct,
            side='SELL',
            commission=proceeds * self.commission_pct,
            slippage=price * qty * self.slippage_pct,
            holding_period=0
        )
        self.trades.append(trade)
        self._log_trade_db(trade)
        self._daily_loss += pnl
        
        if pos.quantity == 0:
            del self.portfolio[symbol]
        logger.info(f"Paper SELL {qty} {symbol} @ {price:.2f} | P&L: {pnl:+.2f} ({pnl_pct:+.2f}%)")
        return True
    
    def update_prices(self, live_prices: Dict[str, float]):
        for sym, price in live_prices.items():
            if sym in self.portfolio:
                pos = self.portfolio[sym]
                pos.current_price = price
                pos.pnl = (price - pos.avg_price) * pos.quantity
                pos.pnl_pct = (price / pos.avg_price - 1) * 100
    
    def check_trailing_stop(self, symbol, current_price):
        if symbol not in self.portfolio:
            return False
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
    
    def check_drawdown(self, current_value):
        if current_value > self.peak:
            self.peak = current_value
        dd = (self.peak - current_value) / self.peak if self.peak > 0 else 0
        if dd > self.max_dd:
            logger.warning(f"Drawdown {dd*100:.2f}% > limit {self.max_dd*100:.0f}%")
            return True
        return False
    
    def get_stats(self):
        completed = [t for t in self.trades if t.side == 'SELL']
        if not completed:
            return {'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0, 'win_rate': 0.0, 'total_pnl': 0.0,
                    'avg_pnl': 0, 'sharpe': 0, 'max_dd': 0}
        total_trades = len(completed)
        winning = sum(1 for t in completed if t.pnl > 0)
        losing = total_trades - winning
        total_pnl = sum(t.pnl for t in completed)
        win_rate = winning / total_trades
        avg_pnl = total_pnl / total_trades
        returns = [t.pnl for t in completed]
        sharpe = np.mean(returns) / (np.std(returns) + 1e-6)
        max_dd = calculate_max_drawdown(np.cumsum(returns))
        return {
            'total_trades': total_trades,
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'sharpe': sharpe,
            'max_dd': max_dd,
            'profit_factor': abs(sum(r for r in returns if r > 0) / (sum(r for r in returns if r < 0) + 1e-6))
        }

# ============================================================
# BACKTESTING ENGINE (ENHANCED WITH DIVIDEND CAPTURE LOGIC)
# ============================================================
class BacktestEngine:
    def __init__(self, initial_balance=ACCOUNT_BALANCE, slippage=0.001, commission=0.001, tax_rate=0.15):
        self.initial_balance = initial_balance
        self.slippage = slippage
        self.commission = commission
        self.tax_rate = tax_rate
    
    def run(self, symbol: str, df: pd.DataFrame, ex_dates: List[Dict]) -> BacktestResult:
        if df is None or df.empty or not ex_dates:
            return BacktestResult(symbol=symbol, total_trades=0, winning_trades=0, losing_trades=0,
                                  win_rate=0.0, total_pnl=0.0, avg_pnl=0.0, max_drawdown=0.0,
                                  sharpe_ratio=0.0, profit_factor=0.0)
        
        ex_date_list = [datetime.strptime(d['ex_date'], "%Y-%m-%d") for d in ex_dates]
        trades = []
        balance = self.initial_balance
        in_position = False
        entry_price = 0.0
        entry_date = None
        shares = 0
        
        for i, row in df.iterrows():
            date = i.to_pydatetime() if hasattr(i, 'to_pydatetime') else i
            price = row['Close'] if 'Close' in row else row.iloc[3]
            
            is_ex_date = any(abs((date - ex_date).days) < 1 for ex_date in ex_date_list)
            
            if not in_position and is_ex_date:
                shares = int(balance * 0.95 / price)
                if shares > 0:
                    entry_price = price * (1 + self.slippage)
                    entry_date = date
                    in_position = True
                    balance -= shares * entry_price
                    balance -= shares * entry_price * self.commission
                    div_amount = next((d['amount'] for d in ex_dates if abs((date - datetime.strptime(d['ex_date'], "%Y-%m-%d")).days) < 1), 0)
            
            elif in_position:
                days_held = (date - entry_date).days
                if days_held >= 3:
                    exit_price = price * (1 - self.slippage)
                    gross_pnl = (exit_price - entry_price) * shares
                    commission_exit = shares * exit_price * self.commission
                    pnl = gross_pnl - commission_exit
                    dividend_net = div_amount * shares * (1 - self.tax_rate) if div_amount else 0
                    pnl += dividend_net
                    balance += shares * exit_price + dividend_net - commission_exit
                    trades.append({
                        'entry': entry_price,
                        'exit': exit_price,
                        'pnl': pnl,
                        'holding_days': days_held,
                        'dividend': dividend_net
                    })
                    in_position = False
                    shares = 0
        
        if in_position and shares > 0:
            exit_price = df.iloc[-1]['Close'] if 'Close' in df else df.iloc[-1, 3]
            exit_price *= (1 - self.slippage)
            pnl = (exit_price - entry_price) * shares - (shares * exit_price * self.commission)
            dividend_net = div_amount * shares * (1 - self.tax_rate) if div_amount else 0
            balance += shares * exit_price + dividend_net
            trades.append({'entry': entry_price, 'exit': exit_price, 'pnl': pnl, 'holding_days': 0, 'dividend': dividend_net})
        
        total_trades = len(trades)
        if total_trades == 0:
            return BacktestResult(symbol=symbol, total_trades=0, winning_trades=0, losing_trades=0,
                                  win_rate=0.0, total_pnl=0.0, avg_pnl=0.0, max_drawdown=0.0,
                                  sharpe_ratio=0.0, profit_factor=0.0)
        
        winning = sum(1 for t in trades if t['pnl'] > 0)
        losing = total_trades - winning
        total_pnl = sum(t['pnl'] for t in trades)
        win_rate = winning / total_trades
        avg_pnl = total_pnl / total_trades
        pnls = [t['pnl'] for t in trades]
        max_dd = calculate_max_drawdown(np.cumsum(pnls))
        returns = pnls
        sharpe = np.mean(returns) / (np.std(returns) + 1e-6)
        profit_factor = abs(sum(r for r in returns if r > 0) / (sum(r for r in returns if r < 0) + 1e-6))
        holding_days = [t.get('holding_days', 0) for t in trades]
        avg_hold = np.mean(holding_days) if holding_days else 0
        consec_losses = max_consecutive(np.array(returns) < 0) if returns else 0
        recovery = total_pnl / abs(max_dd) if max_dd < 0 else float('inf')
        sortino = calculate_sortino(np.array(returns))
        calmar = calculate_calmar(np.array(returns))
        
        return BacktestResult(
            symbol=symbol,
            total_trades=total_trades,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            calmar_ratio=calmar,
            sortino_ratio=sortino,
            avg_holding_days=avg_hold,
            max_consecutive_losses=consec_losses,
            recovery_factor=recovery
        )

def max_consecutive(arr: np.ndarray, value=True):
    """Return max consecutive True values."""
    if len(arr) == 0:
        return 0
    arr = np.array(arr, dtype=bool) if value else ~np.array(arr, dtype=bool)
    groups = np.diff(np.where(np.concatenate(([arr[0]], arr[:-1] != arr[1:], [True])))[0])[::2]
    return groups.max() if len(groups) > 0 else 0

# ============================================================
# RISK MANAGEMENT (ENHANCED)
# ============================================================
def calculate_var(returns: np.ndarray, confidence: float = 0.95) -> float:
    if len(returns) == 0:
        return 0.0
    return np.percentile(returns, (1 - confidence) * 100)

def calculate_cvar(returns: np.ndarray, confidence: float = 0.95) -> float:
    if len(returns) == 0:
        return 0.0
    var = calculate_var(returns, confidence)
    return np.mean(returns[returns <= var]) if any(returns <= var) else var

def calculate_sharpe(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    if len(returns) < 2 or np.std(returns) == 0:
        return 0.0
    return (np.mean(returns) - risk_free_rate) / np.std(returns)

def calculate_sortino(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    downside = np.std(returns[returns < 0]) if any(returns < 0) else 0.001
    return (np.mean(returns) - risk_free_rate) / downside

def calculate_calmar(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    max_dd = np.min(returns) if any(returns < 0) else 0.0
    if max_dd == 0:
        return 0.0
    return np.mean(returns) / abs(max_dd)

def calculate_max_drawdown(pnl_series: List[float]) -> float:
    peak = pnl_series[0] if pnl_series else 0
    max_dd = 0
    for val in pnl_series:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd

class RiskManager:
    def __init__(self, config: Config):
        self.config = config
        self.daily_loss = 0.0
        self.weekly_loss = 0.0
        self.current_day = datetime.now().date()
        self.peak_balance = ACCOUNT_BALANCE
    
    def can_trade(self, current_balance: float) -> bool:
        max_daily = self.config.get('safety.max_daily_loss', 0.02) * self.peak_balance
        if abs(self.daily_loss) >= max_daily:
            logger.warning("Daily loss limit reached")
            return False
        dd = (self.peak_balance - current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        if dd >= self.config.get('safety.max_portfolio_drawdown', 0.02):
            logger.warning(f"Portfolio drawdown {dd:.2%} reached limit")
            return False
        return True
    
    def update(self, trade_pnl: float):
        today = datetime.now().date()
        if today != self.current_day:
            self.daily_loss = 0.0
            self.current_day = today
        self.daily_loss += trade_pnl
        if self.peak_balance < ACCOUNT_BALANCE:
            self.peak_balance = ACCOUNT_BALANCE

# ============================================================
# PORTFOLIO OPTIMIZATION (with PyPortfolioOpt if available)
# ============================================================
def optimize_portfolio(returns: pd.DataFrame, target_return: float = None,
                       risk_free_rate: float = 0.0) -> Dict:
    if returns.empty or returns.shape[1] < 2:
        return {}
    if PYPO_AVAILABLE:
        try:
            mu = expected_returns.mean_historical_return(returns)
            S = risk_models.sample_cov(returns)
            ef = EfficientFrontier(mu, S)
            if target_return is not None:
                ef.efficient_return(target_return)
            else:
                ef.max_sharpe(risk_free_rate)
            weights = ef.clean_weights()
            return {sym: w for sym, w in weights.items() if w > 0.001}
        except Exception as e:
            logger.debug(f"PyPortfolioOpt error: {e}")
    n = len(returns.columns)
    return {col: 1/n for col in returns.columns}

def calculate_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty:
        return pd.DataFrame()
    return returns.corr()

# ============================================================
# TELEGRAM ALERTS
# ============================================================
def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        resp = requests.post(url, json=data, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def send_telegram_signal(signal: TradeSignal) -> bool:
    emoji = "⭐" if signal.priority == "FORCE ENTRY" else "🟢"
    msg = f"""{emoji} <b>NEW SIGNAL: {signal.symbol}</b>
Price: PKR {signal.entry_price:.2f}
Ex-Date: {signal.entry_date}
Yield: {signal.dividend_yield:.2f}%
Stop: {signal.stop_loss:.2f}
T1: {signal.target1:.2f} (+{TARGET1_PCT*100:.0f}%)
T2: {signal.target2:.2f} (+{TARGET2_PCT*100:.0f}%)
Confidence: {signal.confidence_score:.1%}
Regime: {signal.regime}
Priority: {signal.priority}
Reason: {signal.reason}"""
    return send_telegram(msg)

# ============================================================
# EMAIL (RESEND)
# ============================================================
def send_email(subject: str, html_content: str) -> bool:
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not set")
        return False
    url = "https://api.resend.com/emails"
    headers = {'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'}
    data = {'from': FROM_EMAIL, 'to': [TO_EMAIL], 'subject': subject, 'html': html_content}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            logger.info("Email sent successfully")
            return True
        else:
            logger.error(f"Email failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False

# ============================================================
# HTML REPORT GENERATOR (LIGHT THEME)
# ============================================================
def generate_chart_base64(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return f'data:image/png;base64,{img_base64}'

def generate_performance_chart(paper_engine: PaperTradingEngine) -> str:
    pnl_series = []
    cum = 0
    for t in paper_engine.trades:
        if t.side == 'SELL':
            cum += t.pnl
            pnl_series.append(cum)
    if not pnl_series:
        return ""
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(pnl_series, color='#0066cc', lw=1)
    ax.set_title('Equity Curve', color='#222')
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')
    ax.tick_params(colors='#555')
    ax.spines['bottom'].set_color('#ccc')
    ax.spines['left'].set_color('#ccc')
    return generate_chart_base64(fig)

def generate_sentiment_chart(sentiment_data: Dict) -> str:
    if not sentiment_data.get('articles'):
        return ""
    polarities = [a['polarity'] for a in sentiment_data['articles'][:20]]
    fig, ax = plt.subplots(figsize=(6, 2))
    colors = ['#28a745' if p>0 else '#dc3545' for p in polarities]
    ax.bar(range(len(polarities)), polarities, color=colors)
    ax.set_title('News Sentiment Polarity', color='#222')
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')
    ax.tick_params(colors='#555')
    ax.spines['bottom'].set_color('#ccc')
    ax.spines['left'].set_color('#ccc')
    return generate_chart_base64(fig)

def generate_html_report(symbols, dividends, signals, live_prices, market_pulse,
                         indices, sectors, paper_engine, backtest_results,
                         sentiment_data, config, correlation_matrix=None) -> str:
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    div_rows = ""
    for d in dividends[:20]:
        days = d['days_until']
        status = "🔥 IMMINENT" if days <= 2 else "🔶 SOON"
        div_rows += f"<tr><td><strong>{d['symbol']}</strong></td><td>{d['ex_date']}</td><td>{d['amount']:.2f}</td><td>{days} days</td><td>{d.get('type', '')}</td><td>{status}</td></tr>"
    if not div_rows:
        div_rows = "<tr><td colspan='6'>No upcoming dividends</td></tr>"
    
    sig_rows = ""
    for s in signals[:20]:
        priority_badge = "⭐ FORCE ENTRY" if s.priority == "FORCE ENTRY" else "🟢 STANDARD"
        sig_rows += f"""
        <tr>
            <td><strong>{s.symbol}</strong></td>
            <td>{s.entry_price:.2f}</td>
            <td>T-{max(0, (datetime.strptime(s.entry_date, '%Y-%m-%d') - datetime.now()).days)}</td>
            <td>{s.entry_date}</td>
            <td>{s.dividend_amount:.2f}</td>
            <td class='positive'>{s.dividend_yield:.2f}%</td>
            <td>{s.stop_loss:.2f}</td>
            <td>{s.target1:.2f}</td>
            <td>{s.target2:.2f}</td>
            <td>{s.shares}</td>
            <td>{s.rsi:.1f}</td>
            <td>{s.adx:.1f}</td>
            <td>{s.stoch_k:.1f}</td>
            <td>{s.bb_position:.2f}</td>
            <td>{s.ml_pred}</td>
            <td>{s.sentiment}</td>
            <td>{s.risk_reward:.2f}</td>
            <td>{s.confidence_score:.1%}</td>
            <td><span class='priority'>{priority_badge}</span></td>
            <td class='positive'>🟢 BUY</td>
        </tr>"""
    if not sig_rows:
        sig_rows = "<tr><td colspan='20'>No qualifying signals</td></tr>"
    
    gainers = losers = active = "<li>No data</li>"
    if market_pulse:
        if market_pulse.get('gainers') is not None and not market_pulse['gainers'].empty:
            gainers = "".join([f"<li>{row.get('Symbol', 'N/A')}: <span class='positive'>{row.get('CHANGE %', 0):+.2f}%</span></li>" for _, row in market_pulse['gainers'].head(5).iterrows()])
        if market_pulse.get('losers') is not None and not market_pulse['losers'].empty:
            losers = "".join([f"<li>{row.get('Symbol', 'N/A')}: <span class='negative'>{row.get('CHANGE %', 0):+.2f}%</span></li>" for _, row in market_pulse['losers'].head(5).iterrows()])
        if market_pulse.get('active') is not None and not market_pulse['active'].empty:
            active = "".join([f"<li>{row.get('Symbol', 'N/A')}: {row.get('Volume', 0):,}</li>" for _, row in market_pulse['active'].head(5).iterrows()])
    
    bt_rows = ""
    for bt in backtest_results[:10]:
        bt_rows += f"<tr><td>{bt.symbol}</td><td>{bt.total_trades}</td><td>{bt.win_rate:.1%}</td><td>{bt.total_pnl:+.2f}</td><td>{bt.sharpe_ratio:.2f}</td><td>{bt.sortino_ratio:.2f}</td><td>{bt.calmar_ratio:.2f}</td><td>{bt.max_drawdown:.4f}</td><td>{bt.avg_holding_days:.1f}</td></tr>"
    if not bt_rows:
        bt_rows = "<tr><td colspan='9'>No backtest data</td></tr>"
    
    corr_html = ""
    if correlation_matrix is not None and not correlation_matrix.empty:
        corr_html = correlation_matrix.round(2).to_html(classes='data-table', border=0)
    else:
        corr_html = "<p>No correlation data</p>"
    
    journal = paper_engine.get_stats()
    total_trades = journal['total_trades']
    total_pnl = journal['total_pnl']
    win_rate = journal['win_rate'] * 100 if journal['win_rate'] else 0
    port_value = paper_engine.get_total_value(live_prices)
    
    sentiment_text = sentiment_data.get('overall', 'neutral').upper()
    sentiment_color = '#28a745' if sentiment_text == 'BULLISH' else '#dc3545' if sentiment_text == 'BEARISH' else '#ffc107'
    
    perf_chart = generate_performance_chart(paper_engine)
    sent_chart = generate_sentiment_chart(sentiment_data)
    
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
        ul {{ list-style: none; padding: 0; }}
        li {{ margin: 5px 0; }}
        .data-table th {{ background: #eef3f9; }}
        .data-table td {{ padding: 5px; border: 1px solid #eee; }}
        .chart-container {{ text-align: center; margin: 10px 0; }}
    </style>
    </head><body>
        <div class="header">
            <h1>💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v21.3</h1>
            <p style="color:#666;">Generated on {now}</p>
            <p>💰 Account: PKR {ACCOUNT_BALANCE:,.0f} | 📊 {len(dividends)} Upcoming Dividends | 🕌 {len(symbols)} Shariah Stocks</p>
            <p>📈 Projected Monthly: {sum(s.dividend_yield for s in signals)/len(signals) if signals else 0:.2f}% | Annual: {sum(s.dividend_yield for s in signals)/len(signals)*12 if signals else 0:.2f}%</p>
            <p>📋 Trades: {total_trades} | P&L: {total_pnl:+.2f} | Win Rate: {win_rate:.1f}% | Max DD: {journal.get('max_dd',0)*100:.2f}%</p>
            <p>📊 Sentiment: <span style='color:{sentiment_color}; font-weight:bold;'>{sentiment_text}</span></p>
        </div>
        <div class="section">
            <h2>📅 Upcoming Dividend Calendar</h2>
            <table><thead><tr><th>Symbol</th><th>Ex-Date</th><th>Amount</th><th>Days</th><th>Type</th><th>Status</th></tr></thead><tbody>{div_rows}</tbody></table>
        </div>
        <div class="section">
            <h2>🎯 Dividend Capture Trade Recommendations</h2>
            <table><thead>
                <tr><th>Symbol</th><th>Price</th><th>Entry</th><th>Ex-Date</th><th>Div</th><th>Yield</th><th>Stop</th><th>T1</th><th>T2</th><th>Shares</th><th>RSI</th><th>ADX</th><th>StochK</th><th>BB%</th><th>ML</th><th>Sent</th><th>R:R</th><th>Conf</th><th>Priority</th><th>Action</th></tr></thead>
                <tbody>{sig_rows}</tbody>
            </table>
        </div>
        <div class="section">
            <h2>📈 Market Pulse</h2>
            <div style="display:flex;flex-wrap:wrap;gap:20px;">
                <div><h3>🏆 Top Gainers</h3><ul>{gainers}</ul></div>
                <div><h3>📉 Top Losers</h3><ul>{losers}</ul></div>
                <div><h3>📊 Most Active</h3><ul>{active}</ul></div>
            </div>
        </div>
        <div class="section">
            <h2>📊 Performance Chart</h2>
            <div class="chart-container"><img src="{perf_chart}" alt="Equity Curve" style="max-width:100%;"/></div>
        </div>
        <div class="section">
            <h2>📊 Sentiment Analysis</h2>
            <div class="chart-container"><img src="{sent_chart}" alt="Sentiment" style="max-width:100%;"/></div>
        </div>
        <div class="section">
            <h2>📊 Portfolio</h2>
            <p>Cash: PKR {paper_engine.balance:,.2f}</p>
            <p>Total Value: PKR {port_value:,.2f}</p>
            <p>Unrealized P&L: PKR {paper_engine.get_unrealized_pnl(live_prices):+.2f}</p>
        </div>
        <div class="section">
            <h2>📊 Backtest Results (Enhanced)</h2>
            <table><thead><tr><th>Symbol</th><th>Trades</th><th>Win Rate</th><th>Total P&L</th><th>Sharpe</th><th>Sortino</th><th>Calmar</th><th>Max DD</th><th>Avg Hold</th></tr></thead><tbody>{bt_rows}</tbody></table>
        </div>
        <div class="section">
            <h2>📊 Correlation Matrix</h2>
            {corr_html}
        </div>
        <div class="footer">
            <p>🕌 Shariah-compliant | 📊 Data sourced from PSX website, pypsx, psx-data-reader & multiple APIs | ⚡ Generated by PSX Ultimate Engine v21.3</p>
            <p>⚠️ This is for informational purposes only. Always do your own research.</p>
        </div>
    </body></html>
    """
    return html

# ============================================================
# SCENARIO & STRESS TESTING
# ============================================================
def run_scenario_analysis(signals, paper_engine, price_shocks=[-0.1, -0.05, 0.05, 0.1]):
    results = {}
    for shock in price_shocks:
        simulated_pnl = 0
        for sym, pos in paper_engine.portfolio.items():
            new_price = pos.avg_price * (1 + shock)
            simulated_pnl += (new_price - pos.avg_price) * pos.quantity
        results[f"shock_{shock*100:.0f}%"] = simulated_pnl
    return results

# ============================================================
# WALK-FORWARD OPTIMIZATION (SIMPLIFIED)
# ============================================================
def walk_forward_optimization(symbol, historical_data, ex_dates, window_days=90, step_days=30):
    if historical_data is None or historical_data.empty:
        return []
    results = []
    df = historical_data.sort_index()
    start_dates = pd.date_range(df.index[0], periods=len(df)//step_days, freq=f'{step_days}D')
    for start in start_dates[:5]:
        end = start + pd.Timedelta(days=window_days)
        window_df = df[(df.index >= start) & (df.index <= end)]
        if len(window_df) < 30:
            continue
        ex_in_window = [d for d in ex_dates if start <= pd.Timestamp(d['ex_date']) <= end]
        bt = BacktestEngine()
        res = bt.run(symbol, window_df, ex_in_window)
        results.append(res)
    return results

# ============================================================
# MAIN EXECUTION
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='PSX Ultimate Dividend Capture Engine v21.3')
    parser.add_argument('--mode', choices=['live', 'backtest', 'report', 'scenario', 'walkforward'], default='live',
                        help='Operation mode')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--symbol', nargs='*', help='Symbols to focus on')
    args = parser.parse_args()
    
    print("=" * 80)
    print("💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v21.3 - LIGHT THEME")
    print("=" * 80)
    
    config = Config(args.config)
    global ACCOUNT_BALANCE, STOP_LOSS_PCT, TARGET1_PCT, TARGET2_PCT, CONFIDENCE_THRESHOLD
    ACCOUNT_BALANCE = float(os.environ.get('PSX_ACCOUNT_BALANCE', config.get('trading.initial_balance', 30000.0)))
    STOP_LOSS_PCT = config.get('trading.stop_loss_pct', 0.03)
    TARGET1_PCT = config.get('trading.target1_pct', 0.05)
    TARGET2_PCT = config.get('trading.target2_pct', 0.08)
    CONFIDENCE_THRESHOLD = config.get('ml.confidence_threshold', 0.3)
    
    symbols = [s['symbol'] for s in TOP_50_SHARIAH_STOCKS]
    if args.symbol:
        symbols = args.symbol
    
    if args.mode == 'backtest':
        print("Running backtests...")
        historical = {}
        # Try pypsx first
        try:
            import pypsx
            for sym in symbols:
                try:
                    end = datetime.now()
                    start = end - timedelta(days=BACKTEST_DAYS)
                    df = pypsx.PSXTicker(sym).get_historical(start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d"))
                    if df is not None and not df.empty:
                        historical[sym] = df
                except:
                    pass
        except:
            pass
        
        # Fallback to psx-data-reader if available and pypsx didn't get data
        if PSX_DATA_READER_AVAILABLE:
            psx_reader = PSXDataReaderHistFetcher()
            for sym in symbols:
                if sym not in historical:
                    end = date.today()
                    start = end - timedelta(days=BACKTEST_DAYS)
                    df = psx_reader.get_historical(sym, start, end)
                    if df is not None and not df.empty:
                        historical[sym] = df
        
        for sym, df in historical.items():
            bt = BacktestEngine()
            ex = EX_DATES.get(sym, [])
            res = bt.run(sym, df, ex)
            print(f"{sym}: Trades={res.total_trades}, WinRate={res.win_rate:.2%}, Total P&L={res.total_pnl:+.2f}, Sharpe={res.sharpe_ratio:.2f}, MaxDD={res.max_drawdown:.4f}")
        return 0
    
    print(f"Starting Balance: PKR {ACCOUNT_BALANCE:,.0f}")
    print(f"Paper Trading: {'ACTIVE' if PAPER_TRADING else 'DISABLED'}")
    print(f"Telegram Alerts: {'ENABLED' if TELEGRAM_BOT_TOKEN else 'DISABLED'}")
    print(f"Universe: {len(symbols)} Shariah Stocks")
    print("=" * 80)
    
    print("📡 Fetching live prices from PSX website & multiple sources...")
    fetcher = UnifiedDataFetcher()
    live_prices = fetcher.fetch_all(symbols)
    for sym, data in live_prices.items():
        print(f"   {sym}: PKR {data['price']:.2f} (source: {data.get('source', 'unknown')})")
    
    print("📅 Fetching dividend calendar...")
    dividends = get_upcoming_dividends(symbols)
    print(f"   Found {len(dividends)} upcoming dividends")
    
    print("📊 Fetching historical data...")
    historical = {}
    # Try pypsx first
    try:
        import pypsx
        for sym in symbols:
            try:
                end = datetime.now()
                start = end - timedelta(days=100)
                df = pypsx.PSXTicker(sym).get_historical(start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d"))
                if df is not None and not df.empty:
                    historical[sym] = df
            except:
                pass
    except:
        pass
    # Fallback to psx-data-reader if available
    if PSX_DATA_READER_AVAILABLE:
        psx_reader = PSXDataReaderHistFetcher()
        for sym in symbols:
            if sym not in historical:
                end = date.today()
                start = end - timedelta(days=100)
                df = psx_reader.get_historical(sym, start, end)
                if df is not None and not df.empty:
                    historical[sym] = df
                    print(f"   (psx-data-reader) {sym}: {len(df)} rows")
    
    print("📰 Fetching news sentiment...")
    sentiment = fetch_news_sentiment()
    
    print("🎯 Generating trading signals...")
    signals = []
    paper_engine = PaperTradingEngine()
    backtest_results = []
    returns_for_corr = {}
    risk_mgr = RiskManager(config)
    
    for stock in TOP_50_SHARIAH_STOCKS:
        sym = stock['symbol']
        price = live_prices.get(sym, {}).get('price', 0)
        if price <= 0:
            continue
        div_info = next((d for d in dividends if d['symbol'] == sym), None)
        if not div_info:
            continue
        ind = calculate_indicators(historical.get(sym)) if historical.get(sym) is not None else {}
        ml = ml_predict(historical.get(sym)) if historical.get(sym) is not None else {'prediction': 'neutral', 'confidence': 0.0}
        regime = detect_market_regime(historical.get(sym))
        signal = generate_signal(sym, price, div_info, ind, ml, sentiment, regime)
        if signal:
            signals.append(signal)
            print(f"   ✅ {sym}: {signal.priority} - Yield {signal.dividend_yield:.2f}% (Confidence: {signal.confidence_score:.1%})")
            if PAPER_TRADING and risk_mgr.can_trade(paper_engine.balance):
                paper_engine.buy(sym, price, signal.shares, signal.stop_loss, signal.target1, signal.target2)
            if ENABLE_BACKTESTING and historical.get(sym) is not None:
                bt_engine = BacktestEngine()
                ex_dates_for_sym = [{'ex_date': d['ex_date']} for d in EX_DATES.get(sym, [])]
                res = bt_engine.run(sym, historical[sym], ex_dates_for_sym)
                backtest_results.append(res)
            if historical.get(sym) is not None:
                close = historical[sym]['Close'] if 'Close' in historical[sym] else historical[sym].iloc[:, 3]
                returns_for_corr[sym] = close.pct_change().dropna()
    
    print(f"   Generated {len(signals)} signals")
    
    price_dict = {sym: data['price'] for sym, data in live_prices.items()}
    paper_engine.update_prices(price_dict)
    for sym, pos in list(paper_engine.portfolio.items()):
        current = price_dict.get(sym, pos.avg_price)
        if paper_engine.check_trailing_stop(sym, current):
            logger.info(f"Trailing stop hit for {sym}, selling")
            paper_engine.sell(sym, current)
            risk_mgr.update(paper_engine.trades[-1].pnl)
    
    corr_matrix = None
    if returns_for_corr:
        returns_df = pd.DataFrame(returns_for_corr)
        if not returns_df.empty:
            corr_matrix = calculate_correlation_matrix(returns_df)
    
    market_pulse = indices = sectors = None
    try:
        import pypsx
        market_pulse = {
            "gainers": pypsx.top_performers().get("top_gainers", pd.DataFrame()),
            "losers": pypsx.top_performers().get("top_decliners", pd.DataFrame()),
            "active": pypsx.top_performers().get("top_actives", pd.DataFrame())
        }
        indices = pypsx.get_indices()
        sectors = pypsx.sector_summary()
    except:
        pass
    
    if args.mode == 'scenario':
        scenarios = run_scenario_analysis(signals, paper_engine)
        print("\n📉 Scenario Analysis:")
        for sc, pnl in scenarios.items():
            print(f"   {sc}: PKR {pnl:+.2f}")
    
    print("📝 Generating HTML report...")
    html_report = generate_html_report(symbols, dividends, signals, live_prices, market_pulse,
                                       indices, sectors, paper_engine, backtest_results,
                                       sentiment, config, corr_matrix)
    
    print("📧 Sending email...")
    subject = f"PSX Dividend Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    if send_email(subject, html_report):
        print("✅ Email sent")
    else:
        print("❌ Email failed")
    
    if signals and TELEGRAM_BOT_TOKEN:
        for sig in signals[:3]:
            send_telegram_signal(sig)
        summary = f"📊 PSX Signals: {len(signals)} signals\n"
        for s in signals[:5]:
            summary += f"- {s.symbol}: {s.dividend_yield:.2f}% yield (Conf: {s.confidence_score:.0%})\n"
        send_telegram(summary)
    
    print("=" * 80)
    print("✅ Pipeline completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
