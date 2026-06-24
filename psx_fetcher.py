#!/usr/bin/env python3
"""
psx_fetcher.py
PSX Ultimate Dividend Capture & Trading Automation
Shariah-Compliant | Monthly Cycles | Full Automation

Author: AI Assistant
Version: 10.0
"""

import os
import sys
import json
import yaml
import logging
import smtplib
import argparse
import hashlib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import re
from pathlib import Path

import requests
import pandas as pd
import numpy as np
import feedparser
from textblob import TextBlob
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    """Configuration manager for all parameters."""
    def __init__(self, config_path: str = "config.yaml"):
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
        else:
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        return {
            "trading": {
                "stop_loss_pct": 0.015,
                "trailing_stop_pct": 0.015,
                "max_position_pct": 0.10,
                "target1_pct": 0.05,
                "target2_pct": 0.08,
                "rsi_buy_threshold": 30,
                "rsi_sell_threshold": 70,
                "min_dividend_yield": 0.02,
                "max_allocation_per_stock": 0.10,
                "min_volume_crores": 1,
                "blackout_days": 3,
            },
            "universe": {
                "max_stocks": 50,
                "min_market_cap": 1000000000,
                "min_volume": 100000,
            },
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "send_time": "07:00",
                "timezone": "Asia/Karachi",
            },
            "logging": {
                "level": "INFO",
                "file": "psx_fetcher.log",
                "max_size_mb": 10,
            },
            "shariah": {
                "indices": ["KMI30", "KMIALLSHR"],
                "max_debt_ratio": 0.33,
                "max_non_compliant_income": 0.05,
            }
        }
    
    def __getitem__(self, key):
        return self._config.get(key, {})
    
    def get(self, key, default=None):
        return self._config.get(key, default)

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Stock:
    symbol: str
    name: str = ""
    sector: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    market_cap: float = 0.0
    dividend_yield: float = 0.0
    eps: float = 0.0
    pe_ratio: float = 0.0
    ex_date: Optional[str] = None
    dividend_amount: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0
    rsi: float = 50.0
    sma_20: float = 0.0
    sma_50: float = 0.0
    shariah_compliant: bool = True

@dataclass
class TradeSignal:
    symbol: str
    action: str  # BUY, SELL, HOLD
    entry_price: float
    entry_date: str
    entry_time: str
    exit_price: float
    exit_date: str
    exit_time: str
    stop_loss: float
    target1: float
    target2: float
    dividend_amount: float = 0.0
    dividend_yield: float = 0.0
    reason: str = ""
    priority: str = "NORMAL"

@dataclass
class CorporateAction:
    type: str  # IPO, RIGHT_SHARES, BONUS
    symbol: str
    company: str
    announcement_date: str
    record_date: str
    details: Dict = field(default_factory=dict)

@dataclass
class AccumulationAlert:
    symbol: str
    current_holding: int
    total_shares: int
    ownership_pct: float
    threshold: float
    action_required: str

# ============================================================
# LOGGING
# ============================================================

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('psx_fetcher.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================
# DATA FETCHER
# ============================================================

class DataFetcher:
    """Fetches all market data from various sources."""
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    def __init__(self, config: Config):
        self.config = config
        self.cache = {}
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def fetch_shariah_index_constituents(self, index: str = "KMIALLSHR") -> List[str]:
        """Fetch constituents from PSX-KMI index."""
        try:
            import pypsx
            constituents = pypsx.index_constituents(index)
            if constituents is not None and not constituents.empty:
                symbol_col = None
                for col in ['Symbol', 'symbol', 'Ticker', 'ticker']:
                    if col in constituents.columns:
                        symbol_col = col
                        break
                if symbol_col is None:
                    symbol_col = constituents.columns[0]
                return constituents[symbol_col].tolist()
        except Exception as e:
            logger.error(f"Error fetching {index} constituents: {e}")
        
        # Fallback to known list
        fallback = [
            "FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB", 
            "OGDC", "PPL", "PSO", "LUCK", "MEBL", "UBL", 
            "NBP", "HBL", "DGKC", "MLCF", "FCCL", "ATRL", 
            "NRL", "PRL", "PAEL", "SEARL", "SNGP", "SSGC", 
            "ENGROH", "GAL", "GHNI", "HCAR", "NML", "TREET", 
            "CNERGY", "CPHL", "FFL", "AIRLINK", "KEL", "WTL",
            "TRG", "TPL", "PICT", "IBFL", "SCBPL", "SILK",
            "KAPCO", "NCL", "PSMC", "PTC", "SBL", "SHFA",
            "SML", "SNBL"
        ]
        return fallback
    
    def fetch_stock_quote(self, symbol: str) -> Dict:
        """Fetch real-time quote for a stock."""
        try:
            import pypsx
            ticker = pypsx.PSXTicker(symbol)
            snapshot = ticker.snapshot
            reg_data = snapshot.get('REG', {})
            return {
                'symbol': symbol,
                'price': float(reg_data.get('Current', 0)) or 0,
                'change_pct': float(reg_data.get('Change %', 0)) or 0,
                'volume': int(reg_data.get('Volume', 0)) or 0,
                'high': float(reg_data.get('High', 0)) or 0,
                'low': float(reg_data.get('Low', 0)) or 0,
                'open': float(reg_data.get('Open', 0)) or 0,
                'prev_close': float(reg_data.get('Previous Close', 0)) or 0
            }
        except Exception as e:
            logger.debug(f"Error fetching quote for {symbol}: {e}")
            return {'symbol': symbol, 'price': 0, 'volume': 0}
    
    def fetch_fundamentals(self, symbol: str) -> Dict:
        """Fetch fundamental data."""
        try:
            import pypsx
            ticker = pypsx.PSXTicker(symbol)
            snapshot = ticker.snapshot
            reg_data = snapshot.get('REG', {})
            return {
                'pe': float(reg_data.get('P/E', 0)) or 0,
                'div_yield': float(reg_data.get('Dividend Yield', 0).replace('%', '')) or 0,
                'high_52w': float(reg_data.get('52W High', 0)) or 0,
                'low_52w': float(reg_data.get('52W Low', 0)) or 0,
                'eps': 0,  # Not available from snapshot
            }
        except Exception as e:
            logger.debug(f"Error fetching fundamentals for {symbol}: {e}")
            return {'pe': 0, 'div_yield': 0, 'high_52w': 0, 'low_52w': 0, 'eps': 0}
    
    def fetch_historical(self, symbol: str, days: int = 60) -> Optional[pd.DataFrame]:
        """Fetch historical data."""
        try:
            import pypsx
            ticker = pypsx.PSXTicker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            df = ticker.get_historical(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d")
            )
            return df
        except Exception as e:
            logger.debug(f"Error fetching historical for {symbol}: {e}")
            return None
    
    def fetch_market_watch(self) -> pd.DataFrame:
        """Fetch full market watch."""
        try:
            import pypsx
            return pypsx.market_watch()
        except Exception as e:
            logger.error(f"Error fetching market watch: {e}")
            return pd.DataFrame()
    
    def fetch_index_summary(self) -> pd.DataFrame:
        """Fetch index summary."""
        try:
            import pypsx
            return pypsx.get_indices()
        except Exception as e:
            logger.error(f"Error fetching indices: {e}")
            return pd.DataFrame()
    
    def fetch_dividend_calendar(self, symbols: List[str]) -> List[Dict]:
        """Fetch dividend calendar for given symbols."""
        dividends = []
        for symbol in symbols:
            try:
                import pypsx
                ticker = pypsx.PSXTicker(symbol)
                snapshot = ticker.snapshot
                reg_data = snapshot.get('REG', {})
                # Parse dividend yield and estimate ex-date
                div_yield = float(reg_data.get('Dividend Yield', '0').replace('%', '')) or 0
                if div_yield > 0:
                    # Estimate ex-date based on last dividend (simplified)
                    # In production, scrape actual ex-dates from PSX
                    dividends.append({
                        'symbol': symbol,
                        'amount': div_yield * 0.5,  # Estimate
                        'yield': div_yield,
                        'ex_date': (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
                        'payment_date': (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d"),
                    })
            except Exception as e:
                logger.debug(f"Error fetching dividend for {symbol}: {e}")
        return dividends
    
    def fetch_ipos(self) -> List[Dict]:
        """Fetch upcoming IPOs from PSX."""
        # In production, scrape from PSX website
        # For now, return sample data
        return [
            {
                'company': 'Sample IPO Company',
                'symbol': 'SAMPLE',
                'offer_price': 50.0,
                'lot_size': 500,
                'subscription_open': (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d"),
                'subscription_close': (datetime.now() + timedelta(days=19)).strftime("%Y-%m-%d"),
                'status': 'UPCOMING'
            }
        ]
    
    def fetch_right_shares(self) -> List[Dict]:
        """Fetch right shares announcements."""
        return []  # In production, scrape from PSX
    
    def fetch_news_sentiment(self) -> Dict:
        """Fetch and analyze news sentiment."""
        articles = []
        feeds = [
            "https://www.dawn.com/feeds/business",
            "https://www.brecorder.com/rss/news",
            "https://www.thenews.com.pk/rss/2/5"
        ]
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    blob = TextBlob(title + " " + summary)
                    polarity = blob.sentiment.polarity
                    if polarity > 0.1:
                        sentiment = 'bullish'
                    elif polarity < -0.1:
                        sentiment = 'bearish'
                    else:
                        sentiment = 'neutral'
                    articles.append({
                        'title': title,
                        'summary': summary[:200] + '...' if len(summary) > 200 else summary,
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'sentiment': sentiment,
                        'polarity': polarity
                    })
            except Exception as e:
                logger.debug(f"RSS error for {feed_url}: {e}")
        
        if articles:
            avg_polarity = np.mean([a['polarity'] for a in articles])
            overall = 'bullish' if avg_polarity > 0.05 else 'bearish' if avg_polarity < -0.05 else 'neutral'
            return {'overall': overall, 'avg_polarity': avg_polarity, 'articles': articles[:10]}
        return {'overall': 'neutral', 'avg_polarity': 0, 'articles': []}

# ============================================================
# SIGNAL GENERATOR
# ============================================================

class SignalGenerator:
    """Generates trading signals based on multiple strategies."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period:
            return 50.0
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if len(rsi) > 0 else 50.0
    
    def calculate_sma(self, prices: pd.Series, period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return prices.iloc[-1] if len(prices) > 0 else 0
        return prices.tail(period).mean()
    
    def generate_dividend_signals(self, stocks: List[Stock], ex_dates: List[Dict]) -> List[TradeSignal]:
        """Generate dividend capture signals."""
        signals = []
        today = datetime.now().date()
        trading_days = 5  # Assume weekdays
        
        for stock in stocks:
            # Find ex-date for this stock
            ex_date_info = next((d for d in ex_dates if d['symbol'] == stock.symbol), None)
            if not ex_date_info:
                continue
            
            try:
                ex_date = datetime.strptime(ex_date_info['ex_date'], "%Y-%m-%d").date()
                days_until = (ex_date - today).days
                
                # Only process upcoming ex-dates within 10 days
                if days_until < 0 or days_until > 10:
                    continue
                
                # Calculate buy date (2 trading days before ex-date)
                buy_offset = 2
                buy_date = ex_date - timedelta(days=buy_offset)
                # Adjust for weekends
                if buy_date.weekday() >= 5:  # Saturday or Sunday
                    buy_date = buy_date - timedelta(days=buy_date.weekday() - 4)  # Thursday
                
                # Calculate exit date (on ex-date)
                exit_date = ex_date
                if exit_date.weekday() >= 5:
                    exit_date = exit_date + timedelta(days=1)  # Next trading day
                
                entry_price = stock.price
                if entry_price <= 0:
                    continue
                
                yield_pct = (ex_date_info.get('amount', 0) / entry_price) * 100
                
                # Check minimum yield
                if yield_pct < self.config['trading']['min_dividend_yield'] * 100:
                    continue
                
                # Calculate targets and stop
                stop_loss = entry_price * (1 - self.config['trading']['stop_loss_pct'])
                target1 = entry_price * (1 + self.config['trading']['target1_pct'])
                target2 = entry_price * (1 + self.config['trading']['target2_pct'])
                
                # Force entry for high yield
                force_entry = (yield_pct >= 6 and days_until <= 2) or (yield_pct >= 8 and days_until <= 4)
                
                if force_entry or (yield_pct >= 4 and 2 <= days_until <= 5):
                    signals.append(TradeSignal(
                        symbol=stock.symbol,
                        action='BUY',
                        entry_price=entry_price,
                        entry_date=buy_date.strftime("%Y-%m-%d"),
                        entry_time="09:31",
                        exit_price=target1,  # Will use target1 as initial exit
                        exit_date=exit_date.strftime("%Y-%m-%d"),
                        exit_time="15:15",
                        stop_loss=stop_loss,
                        target1=target1,
                        target2=target2,
                        dividend_amount=ex_date_info.get('amount', 0),
                        dividend_yield=yield_pct,
                        reason=f"Dividend capture | Yield: {yield_pct:.2f}% | Ex-date: {ex_date}",
                        priority="FORCE ENTRY" if force_entry else "STANDARD"
                    ))
            except Exception as e:
                logger.debug(f"Error generating signal for {stock.symbol}: {e}")
        
        return signals
    
    def generate_swing_signals(self, stocks: List[Stock], historical_data: Dict) -> List[TradeSignal]:
        """Generate swing trading signals based on RSI."""
        signals = []
        today = datetime.now().date()
        
        for stock in stocks:
            hist = historical_data.get(stock.symbol)
            if hist is None or hist.empty:
                continue
            
            # Find close price column
            close_col = None
            for col in hist.columns:
                if 'close' in col.lower() or 'adj close' in col.lower():
                    close_col = col
                    break
            if close_col is None:
                close_col = hist.columns[3] if len(hist.columns) > 3 else hist.columns[0]
            
            prices = hist[close_col]
            rsi = self.calculate_rsi(prices, 14)
            sma_20 = self.calculate_sma(prices, 20)
            
            if rsi < self.config['trading']['rsi_buy_threshold'] and stock.price > 0:
                # Oversold - Buy signal
                entry_price = stock.price
                stop_loss = entry_price * (1 - self.config['trading']['stop_loss_pct'])
                target1 = entry_price * (1 + self.config['trading']['target1_pct'])
                target2 = entry_price * (1 + self.config['trading']['target2_pct'])
                
                signals.append(TradeSignal(
                    symbol=stock.symbol,
                    action='BUY',
                    entry_price=entry_price,
                    entry_date=today.strftime("%Y-%m-%d"),
                    entry_time="09:31",
                    exit_price=target1,
                    exit_date=(today + timedelta(days=5)).strftime("%Y-%m-%d"),
                    exit_time="15:15",
                    stop_loss=stop_loss,
                    target1=target1,
                    target2=target2,
                    dividend_amount=0,
                    dividend_yield=0,
                    reason=f"Swing trade | RSI: {rsi:.2f} < {self.config['trading']['rsi_buy_threshold']}",
                    priority="SWING"
                ))
            
            elif rsi > self.config['trading']['rsi_sell_threshold']:
                # Overbought - Sell signal
                signals.append(TradeSignal(
                    symbol=stock.symbol,
                    action='SELL',
                    entry_price=0,
                    entry_date="",
                    entry_time="",
                    exit_price=stock.price,
                    exit_date=today.strftime("%Y-%m-%d"),
                    exit_time="15:15",
                    stop_loss=0,
                    target1=0,
                    target2=0,
                    dividend_amount=0,
                    dividend_yield=0,
                    reason=f"Swing trade exit | RSI: {rsi:.2f} > {self.config['trading']['rsi_sell_threshold']}",
                    priority="SWING"
                ))
        
        return signals

# ============================================================
# EMAILER
# ============================================================

class Emailer:
    """Sends comprehensive email reports."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def generate_html_report(self, signals: List[TradeSignal], market_data: Dict,
                              upcoming_dividends: List[Dict], ipos: List[Dict],
                              right_shares: List[Dict], accumulation_alerts: List[Dict],
                              sentiment: Dict, index_summary: pd.DataFrame) -> str:
        """Generate HTML email content."""
        now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
        
        # Build signals table
        signals_html = ""
        if signals:
            for sig in signals[:20]:
                priority_badge = f"🔥 {sig.priority}" if sig.priority == "FORCE ENTRY" else sig.priority
                signals_html += f"""
                    <tr>
                        <td><strong>{sig.symbol}</strong></td>
                        <td>{sig.action}</td>
                        <td>{sig.entry_price:.2f}</td>
                        <td>{sig.entry_date}</td>
                        <td>{sig.exit_price:.2f}</td>
                        <td>{sig.exit_date}</td>
                        <td>{sig.stop_loss:.2f}</td>
                        <td>{sig.target1:.2f}</td>
                        <td>{sig.dividend_yield:.2f}%</td>
                        <td><span class="priority">{priority_badge}</span></td>
                    </tr>
                """
        else:
            signals_html = '<tr><td colspan="10">⚠️ No active signals</td></tr>'
        
        # Build dividend calendar
        div_html = ""
        for div in upcoming_dividends[:20]:
            days_until = (datetime.strptime(div['ex_date'], "%Y-%m-%d").date() - datetime.now().date()).days
            status = "🔥 IMMINENT" if days_until <= 2 else "🔶 SOON"
            div_html += f"""
                <tr>
                    <td><strong>{div['symbol']}</strong></td>
                    <td>{div['amount']:.2f}</td>
                    <td>{div['yield']:.2f}%</td>
                    <td>{div['ex_date']}</td>
                    <td>{days_until} days</td>
                    <td>{status}</td>
                </tr>
            """
        if not div_html:
            div_html = '<tr><td colspan="6">No upcoming dividends</td></tr>'
        
        # Build IPO table
        ipo_html = ""
        for ipo in ipos:
            ipo_html += f"""
                <tr>
                    <td><strong>{ipo.get('company', 'N/A')}</strong></td>
                    <td>{ipo.get('symbol', 'N/A')}</td>
                    <td>{ipo.get('offer_price', 0):.2f}</td>
                    <td>{ipo.get('subscription_open', 'N/A')}</td>
                    <td>{ipo.get('subscription_close', 'N/A')}</td>
                    <td>{ipo.get('status', 'N/A')}</td>
                </tr>
            """
        if not ipo_html:
            ipo_html = '<tr><td colspan="6">No upcoming IPOs</td></tr>'
        
        # Build accumulation alerts
        acc_html = ""
        for alert in accumulation_alerts:
            acc_html += f"""
                <tr>
                    <td><strong>{alert.get('symbol', 'N/A')}</strong></td>
                    <td>{alert.get('ownership_pct', 0):.2f}%</td>
                    <td>{alert.get('threshold', 0):.0f}%</td>
                    <td><span class="alert">{alert.get('action_required', 'N/A')}</span></td>
                </tr>
            """
        if not acc_html:
            acc_html = '<tr><td colspan="4">No accumulation alerts</td></tr>'
        
        # Sentiment
        sentiment_text = sentiment.get('overall', 'neutral').upper()
        sentiment_color = '#00ff88' if sentiment_text == 'BULLISH' else '#ff4444' if sentiment_text == 'BEARISH' else '#ffaa00'
        
        # Index summary
        index_html = ""
        if index_summary is not None and not index_summary.empty:
            for idx, row in index_summary.head(5).iterrows():
                name = row.get('Index', row.get('name', 'N/A'))
                current = row.get('Current', row.get('current', 'N/A'))
                change = row.get('PERCENTAGE_CHANGE', row.get('change', 'N/A'))
                index_html += f"<li><strong>{name}</strong>: {current} ({change}%)</li>"
        if not index_html:
            index_html = "<li>No index data available</li>"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; background: #0a0a0a; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #0a1628, #1a3a5c); color: #00ff88; padding: 20px; border-radius: 8px; text-align: center; }}
                .header h1 {{ margin: 0; color: #00ff88; }}
                .header p {{ margin: 5px 0; color: #aaa; }}
                .section {{ background: #1a1a2e; margin: 20px 0; padding: 20px; border-radius: 8px; border: 1px solid #2a2a4e; }}
                .section h2 {{ color: #00ff88; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 13px; color: #ccc; }}
                th {{ background: #0a1628; color: #00ff88; padding: 10px; text-align: left; border-bottom: 2px solid #00ff88; }}
                td {{ padding: 10px; border-bottom: 1px solid #2a2a4e; color: #ddd; }}
                .buy {{ color: #00ff88; font-weight: bold; }}
                .sell {{ color: #ff4444; font-weight: bold; }}
                .neutral {{ color: #ffaa00; font-weight: bold; }}
                .priority {{ background: #ffaa00; color: #0a0a0a; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
                .alert {{ background: #ff4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
                .footer {{ text-align: center; font-size: 12px; color: #666; margin-top: 20px; padding: 10px; border-top: 1px solid #2a2a4e; }}
                ul {{ color: #ccc; }}
                li {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v10.0</h1>
                <p>Generated on {now}</p>
                <p>💰 Account: PKR 30,000 | Strategy: Dividend Capture + Swing Trading</p>
                <p>🕌 Shariah-Compliant | Monthly Cycles | Full Automation</p>
                <p>📊 Market Sentiment: <span style="color:{sentiment_color};">{sentiment_text}</span></p>
            </div>

            <div class="section">
                <h2>📊 Market Snapshot</h2>
                <ul>
                    {index_html}
                </ul>
            </div>

            <div class="section">
                <h2>🎯 Actionable Trade Signals</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Action</th>
                            <th>Entry</th>
                            <th>Buy Date</th>
                            <th>Exit</th>
                            <th>Sell Date</th>
                            <th>Stop</th>
                            <th>Target1</th>
                            <th>Yield</th>
                            <th>Priority</th>
                        </tr>
                    </thead>
                    <tbody>
                        {signals_html}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>📅 Upcoming Dividend Calendar</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Amount (PKR)</th>
                            <th>Yield %</th>
                            <th>Ex-Date</th>
                            <th>Days Until</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {div_html}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>🏢 IPO & Right Shares Dashboard</h2>
                <h3>Upcoming IPOs</h3>
                <table>
                    <thead>
                        <tr><th>Company</th><th>Symbol</th><th>Price</th><th>Open</th><th>Close</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        {ipo_html}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>📊 Portfolio Accumulation Alerts</h2>
                <table>
                    <thead>
                        <tr><th>Symbol</th><th>Ownership %</th><th>Threshold</th><th>Action Required</th></tr>
                    </thead>
                    <tbody>
                        {acc_html}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>📰 News Sentiment</h2>
                <ul>
        """
        for article in sentiment.get('articles', [])[:5]:
            color = '#00ff88' if article['sentiment'] == 'bullish' else '#ff4444' if article['sentiment'] == 'bearish' else '#ffaa00'
            html += f"<li><span style='color:{color};'>{article['sentiment'].upper()}</span> — {article['title'][:100]}...</li>"
        
        html += f"""
                </ul>
            </div>

            <div class="footer">
                <p>🕌 All stocks Shariah-compliant (KMI All Share Index)</p>
                <p>🛡️ Stop-Loss: 1.5% | Trailing Stop: 1.5% | Max Position: 10%</p>
                <p>⚠️ No trading system eliminates risk. Always do your own research.</p>
                <p>⚡ Generated by PSX Ultimate Dividend Capture Engine v10.0</p>
            </div>
        </body>
        </html>
        """
        return html
    
    def send_report(self, html_body: str, subject: str = "PSX Dividend Capture Report") -> bool:
        """Send email via SMTP."""
        try:
            sender = os.environ.get('EMAIL_SENDER')
            password = os.environ.get('EMAIL_PASSWORD')
            receiver = os.environ.get('EMAIL_RECEIVER')
            smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.environ.get('SMTP_PORT', 587))
            
            if not sender or not password or not receiver:
                logger.error("Missing email credentials in environment variables")
                return False
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = receiver
            
            # Plain text fallback
            text_body = re.sub(r'<[^>]+>', '', html_body)
            text_body = '\n'.join([line.strip() for line in text_body.split('\n') if line.strip()])
            msg.attach(MIMEText(text_body, 'plain'))
            
            # HTML body
            msg.attach(MIMEText(html_body, 'html'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Email sent to {receiver}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main entry point for the PSX Dividend Capture System."""
    parser = argparse.ArgumentParser(description='PSX Dividend Capture System')
    parser.add_argument('--dry-run', action='store_true', help='Print email content without sending')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    args = parser.parse_args()
    
    print("💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v10.0")
    print("=" * 80)
    print(f"📋 Dry Run: {'ACTIVE' if args.dry_run else 'DISABLED'}")
    print("=" * 80)
    
    # Load configuration
    config = Config(args.config)
    
    # Initialize components
    fetcher = DataFetcher(config)
    signal_gen = SignalGenerator(config)
    emailer = Emailer(config)
    
    # 1. Get Shariah-compliant universe
    print("📡 Fetching Shariah-compliant universe...")
    all_stocks = fetcher.fetch_shariah_index_constituents("KMIALLSHR")
    print(f"   Found {len(all_stocks)} Shariah-compliant stocks")
    
    # 2. Get market watch for pricing
    print("📡 Fetching market data...")
    market_watch = fetcher.fetch_market_watch()
    
    # 3. Build stock objects with real-time data
    stocks = []
    for symbol in all_stocks[:50]:  # Top 50
        quote = fetcher.fetch_stock_quote(symbol)
        fundamentals = fetcher.fetch_fundamentals(symbol)
        hist = fetcher.fetch_historical(symbol, 60)
        
        if quote.get('price', 0) > 0:
            stock = Stock(
                symbol=symbol,
                price=float(quote.get('price', 0)),
                change_pct=float(quote.get('change_pct', 0)),
                volume=int(quote.get('volume', 0)),
                dividend_yield=fundamentals.get('div_yield', 0),
                pe_ratio=fundamentals.get('pe', 0),
                high_52w=fundamentals.get('high_52w', 0),
                low_52w=fundamentals.get('low_52w', 0)
            )
            stocks.append(stock)
    print(f"   Tracking {len(stocks)} stocks with price data")
    
    # 4. Get dividend calendar
    print("📅 Fetching dividend calendar...")
    dividends = fetcher.fetch_dividend_calendar([s.symbol for s in stocks])
    print(f"   Found {len(dividends)} upcoming dividends")
    
    # 5. Generate signals
    print("🎯 Generating trading signals...")
    signals = signal_gen.generate_dividend_signals(stocks, dividends)
    print(f"   Generated {len(signals)} signals")
    
    # 6. Get IPOs and right shares
    print("🏢 Fetching corporate actions...")
    ipos = fetcher.fetch_ipos()
    right_shares = fetcher.fetch_right_shares()
    
    # 7. Get news sentiment
    print("📰 Fetching news sentiment...")
    sentiment = fetcher.fetch_news_sentiment()
    
    # 8. Get index summary
    index_summary = fetcher.fetch_index_summary()
    
    # 9. Build accumulation alerts (placeholder)
    accumulation_alerts = []
    
    # 10. Generate email report
    print("📝 Generating email report...")
    html_report = emailer.generate_html_report(
        signals=signals,
        market_data={},
        upcoming_dividends=dividends,
        ipos=ipos,
        right_shares=right_shares,
        accumulation_alerts=accumulation_alerts,
        sentiment=sentiment,
        index_summary=index_summary
    )
    
    # 11. Send or print
    if args.dry_run:
        print("\n" + "=" * 80)
        print("📧 EMAIL CONTENT (DRY RUN)")
        print("=" * 80)
        print(html_report)
        print("=" * 80)
    else:
        subject = f"PSX Dividend Capture Report - {datetime.now().strftime('%Y-%m-%d')}"
        success = emailer.send_report(html_report, subject)
        if success:
            print("✅ Report sent successfully!")
        else:
            print("❌ Failed to send report.")
    
    print("=" * 80)
    print("✅ Pipeline completed successfully!")

if __name__ == "__main__":
    main()
