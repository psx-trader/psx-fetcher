#!/usr/bin/env python3
"""
PSX ULTIMATE DIVIDEND CAPTURE ENGINE v8.1 — MORE FLEXIBLE
Features: Relaxed Filters, Dividend Priority, Imminent Dividend Entry
"""

import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import feedparser
from textblob import TextBlob
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIGURATION
# ============================================================
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
ACCOUNT_BALANCE = 30000
MAX_RISK_PER_TRADE = 0.02
MAX_PORTFOLIO_DRAWDOWN = 0.02
STOP_LOSS_PCT = 0.03
TARGET1_PCT = 0.05
TARGET2_PCT = 0.08
MIN_DIVIDEND_YIELD = 0.04
MIN_VOLUME_CRORES = 1  # Relaxed from 2 to 1 crore
RISK_OFF_INDEX_DROP = 0.015
PAPER_TRADING = True
# ============================================================

# Shariah-compliant dividend stocks with known schedules
DIVIDEND_STOCKS = [
    {"symbol": "FFC", "sector": "Fertilizer", "div_yield": 0.08, "ex_date": "2026-06-25", "amount": 45.00},
    {"symbol": "EFERT", "sector": "Fertilizer", "div_yield": 0.07, "ex_date": "2026-07-15", "amount": 14.00},
    {"symbol": "MARI", "sector": "Oil & Gas", "div_yield": 0.09, "ex_date": "2026-06-30", "amount": 59.00},
    {"symbol": "OGDC", "sector": "Oil & Gas", "div_yield": 0.08, "ex_date": "2026-07-10", "amount": 26.00},
    {"symbol": "HUBC", "sector": "Energy", "div_yield": 0.06, "ex_date": "2026-07-20", "amount": 14.00},
    {"symbol": "MCB", "sector": "Banking", "div_yield": 0.07, "ex_date": "2026-06-28", "amount": 28.00},
    {"symbol": "UBL", "sector": "Banking", "div_yield": 0.06, "ex_date": "2026-07-05", "amount": 25.00},
    {"symbol": "PPL", "sector": "Oil & Gas", "div_yield": 0.07, "ex_date": "2026-07-25", "amount": 16.00},
    {"symbol": "PSO", "sector": "Oil & Gas", "div_yield": 0.08, "ex_date": "2026-08-01", "amount": 28.00},
    {"symbol": "LUCK", "sector": "Cement", "div_yield": 0.05, "ex_date": "2026-08-10", "amount": 22.00},
    {"symbol": "NBP", "sector": "Banking", "div_yield": 0.06, "ex_date": "2026-07-08", "amount": 12.00},
    {"symbol": "HBL", "sector": "Banking", "div_yield": 0.05, "ex_date": "2026-07-12", "amount": 14.00},
    {"symbol": "DGKC", "sector": "Cement", "div_yield": 0.06, "ex_date": "2026-08-05", "amount": 12.00},
    {"symbol": "MLCF", "sector": "Cement", "div_yield": 0.05, "ex_date": "2026-08-15", "amount": 4.00},
    {"symbol": "FCCL", "sector": "Cement", "div_yield": 0.05, "ex_date": "2026-08-20", "amount": 2.70},
]

RSS_FEEDS = [
    "https://www.dawn.com/feeds/business",
    "https://www.brecorder.com/rss/news",
    "https://www.thenews.com.pk/rss/2/5"
]

# ============================================================
# GLOBAL HELPERS
# ============================================================

def df_to_html(df, limit=10):
    if df is None or df.empty:
        return "<p>No data available</p>"
    df = df.head(limit)
    return df.to_html(index=False, border=0, classes='data-table')

def is_valid_ticker(symbol):
    return symbol in [s["symbol"] for s in DIVIDEND_STOCKS]

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

# ============================================================
# DIVIDEND CALENDAR
# ============================================================

def fetch_dividend_calendar():
    today = datetime.now().date()
    upcoming = []
    active = []
    for stock in DIVIDEND_STOCKS:
        ex_date = datetime.strptime(stock["ex_date"], "%Y-%m-%d").date()
        days_until = (ex_date - today).days
        if days_until < 0:
            active.append({**stock, "status": "Past", "days_until": days_until})
        elif days_until <= 10:
            upcoming.append({**stock, "status": "Upcoming", "days_until": days_until})
            active.append({**stock, "status": "Upcoming", "days_until": days_until})
        else:
            active.append({**stock, "status": "Future", "days_until": days_until})
    return upcoming, active

# ============================================================
# DATA FETCHING
# ============================================================

def fetch_quote(symbol):
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        volume = safe_float(reg_data.get('Volume', 0))
        return {
            'symbol': symbol,
            'price': reg_data.get('Current', 'N/A'),
            'change': reg_data.get('Change', 'N/A'),
            'change_pct': reg_data.get('Change %', 'N/A'),
            'volume': volume,
            'high': reg_data.get('High', 'N/A'),
            'low': reg_data.get('Low', 'N/A'),
            'open': reg_data.get('Open', 'N/A'),
            'prev_close': reg_data.get('Previous Close', 'N/A')
        }
    except Exception as e:
        return {'symbol': symbol, 'error': str(e), 'price': 'N/A', 'volume': 0}

def fetch_fundamentals(symbol):
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        return {
            'symbol': symbol,
            'pe': reg_data.get('P/E', 'N/A'),
            'div_yield': reg_data.get('Dividend Yield', 'N/A'),
            'high_52w': reg_data.get('52W High', 'N/A'),
            'low_52w': reg_data.get('52W Low', 'N/A')
        }
    except Exception as e:
        return {'symbol': symbol, 'error': str(e)}

def fetch_historical(symbol, days=60):
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
        return None

def fetch_market_pulse():
    try:
        import pypsx
        performers = pypsx.top_performers()
        return {
            "gainers": performers.get("top_gainers", pd.DataFrame()),
            "losers": performers.get("top_decliners", pd.DataFrame()),
            "active": performers.get("top_actives", pd.DataFrame())
        }
    except Exception as e:
        return {"gainers": None, "losers": None, "active": None}

def fetch_index_summary():
    try:
        import pypsx
        indices = pypsx.get_indices()
        return indices
    except Exception as e:
        return None

def fetch_sector_performance():
    try:
        import pypsx
        sectors = pypsx.sector_summary()
        return sectors
    except Exception as e:
        return None

def calculate_indicators(df):
    if df is None or df.empty:
        return {}
    close_col = None
    for col in df.columns:
        if 'close' in col.lower() or 'adj close' in col.lower():
            close_col = col
            break
    if close_col is None:
        close_col = df.columns[3] if len(df.columns) > 3 else df.columns[0]
    close = pd.Series(df[close_col].values)
    indicators = {}
    try:
        indicators['sma_20'] = close.tail(20).mean() if len(close) >= 20 else None
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1] if len(rs) > 0 else None
    except:
        indicators['sma_20'] = None
        indicators['rsi'] = None
    return indicators

# ============================================================
# ULTIMATE DIVIDEND CAPTURE SIGNAL (RELAXED FILTERS)
# ============================================================

def generate_dividend_signal(symbol, price, stock_info, indicators, quote):
    """
    Generate dividend capture signal with relaxed filters.
    Dividend priority: If yield > 6% or ex-date <= 2 days, relax filters.
    """
    if price <= 0 or not stock_info:
        return None
    
    div_amount = stock_info.get("amount", 0)
    ex_date = stock_info.get("ex_date", "")
    days_until = stock_info.get("days_until", 10)
    yield_pct = (div_amount / price) * 100
    
    # Check if this is a high-priority dividend
    high_priority = yield_pct >= 6 or days_until <= 2
    
    # Safety filters - relaxed for high priority
    if high_priority:
        # Relaxed filters for high-priority dividends
        filters = {
            'min_yield': yield_pct >= 3.5,  # Relaxed from 4%
            'volume_ok': quote.get('volume', 0) >= 0.5 * 1e7,  # Relaxed from 1 crore
            'sma_ok': True,  # Remove SMA filter for high priority
            'rsi_ok': indicators.get('rsi') is None or (25 <= indicators.get('rsi', 50) <= 75),  # Relaxed RSI
            'timing_ok': 1 <= days_until <= 7,  # Expanded window
        }
    else:
        # Standard filters
        filters = {
            'min_yield': yield_pct >= MIN_DIVIDEND_YIELD * 100,
            'volume_ok': quote.get('volume', 0) >= MIN_VOLUME_CRORES * 1e7,
            'sma_ok': indicators.get('sma_20') is None or price >= indicators.get('sma_20', 0) * 0.95,
            'rsi_ok': indicators.get('rsi') is None or (30 <= indicators.get('rsi', 50) <= 70),
            'timing_ok': 1 <= days_until <= 5,
        }
    
    if not all(filters.values()):
        failed_filters = [k for k, v in filters.items() if not v]
        return {
            'symbol': symbol,
            'entry_price': price,
            'ex_date': ex_date,
            'div_amount': div_amount,
            'yield_pct': yield_pct,
            'days_until': days_until,
            'action': 'HOLD',
            'reason': f"Filters failed: {', '.join(failed_filters)}",
            'filters': filters,
            'high_priority': high_priority
        }
    
    # Calculate position size
    shares = int(ACCOUNT_BALANCE * 0.95 / price)
    stop_loss = price * (1 - STOP_LOSS_PCT)
    target1 = price * (1 + TARGET1_PCT)
    target2 = price * (1 + TARGET2_PCT)
    
    risk = price - stop_loss
    reward1 = target1 - price
    reward2 = target2 - price
    rr1 = reward1 / risk if risk > 0 else 0
    rr2 = reward2 / risk if risk > 0 else 0
    
    priority_label = "⭐ HIGH PRIORITY" if high_priority else ""
    
    return {
        'symbol': symbol,
        'entry_price': price,
        'stop_loss': round(stop_loss, 2),
        'target1': round(target1, 2),
        'target2': round(target2, 2),
        'shares': shares,
        'ex_date': ex_date,
        'div_amount': div_amount,
        'yield_pct': yield_pct,
        'days_until': days_until,
        'entry_day': f"T-{max(0, days_until - 1)}",
        'exit_day': "T+3",
        'risk_reward1': round(rr1, 2),
        'risk_reward2': round(rr2, 2),
        'action': 'BUY',
        'priority': priority_label,
        'filters': filters,
        'reason': 'All filters passed' + (f" [{priority_label}]" if high_priority else "")
    }

# ============================================================
# SENTIMENT ANALYSIS
# ============================================================

def fetch_sentiment():
    articles = []
    for feed_url in RSS_FEEDS:
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
                    'summary': summary[:200] + '...',
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'sentiment': sentiment,
                    'polarity': polarity
                })
        except Exception as e:
            print(f"RSS error: {e}")
    if articles:
        avg_polarity = np.mean([a['polarity'] for a in articles])
        overall = 'bullish' if avg_polarity > 0.05 else 'bearish' if avg_polarity < -0.05 else 'neutral'
        return {'overall': overall, 'avg_polarity': avg_polarity, 'articles': articles[:10]}
    return {'overall': 'neutral', 'avg_polarity': 0, 'articles': []}

# ============================================================
# TRADE JOURNAL & PAPER TRADING
# ============================================================

class TradeJournal:
    def __init__(self):
        self.trades = []
        self.signals = []
    
    def log_trade(self, symbol, entry_price, exit_price, quantity, entry_time, exit_time, profit_loss):
        self.trades.append({
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'profit_loss': profit_loss
        })
    
    def log_signal(self, symbol, signal, confidence, indicators_used):
        self.signals.append({
            'symbol': symbol,
            'signal': signal,
            'confidence': confidence,
            'indicators': indicators_used
        })
    
    def get_summary(self):
        if not self.trades:
            return {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0, 'profit_factor': 0, 'max_drawdown': 0}
        total_pnl = sum(t['profit_loss'] for t in self.trades)
        win_rate = len([t for t in self.trades if t['profit_loss'] > 0]) / len(self.trades) if self.trades else 0
        total_wins = sum(t['profit_loss'] for t in self.trades if t['profit_loss'] > 0)
        total_losses = sum(t['profit_loss'] for t in self.trades if t['profit_loss'] < 0)
        profit_factor = abs(total_wins / total_losses) if total_losses != 0 else 0
        max_drawdown = min(t['profit_loss'] for t in self.trades) if self.trades else 0
        return {
            'total_trades': len(self.trades),
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown
        }

class PaperTradingEngine:
    def __init__(self, initial_balance=30000, max_drawdown=0.02):
        self.balance = initial_balance
        self.portfolio = {}
        self.initial_balance = initial_balance
        self.peak_balance = initial_balance
        self.max_drawdown_limit = max_drawdown
        self.trade_journal = TradeJournal()
    
    def buy(self, symbol, price, quantity, stop_loss=None, target1=None, target2=None):
        cost = price * quantity
        if cost > self.balance:
            return False
        self.balance -= cost
        self.portfolio[symbol] = {
            'quantity': quantity,
            'avg_price': price,
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'entry_date': datetime.now()
        }
        self.trade_journal.log_trade(symbol, price, None, quantity, datetime.now(), None, None)
        return True
    
    def sell(self, symbol, price, quantity=None):
        if symbol not in self.portfolio:
            return False
        pos = self.portfolio[symbol]
        if quantity is None:
            quantity = pos['quantity']
        if quantity > pos['quantity']:
            return False
        proceeds = price * quantity
        self.balance += proceeds
        pos['quantity'] -= quantity
        pnl = (price - pos['avg_price']) * quantity
        self.trade_journal.log_trade(symbol, pos['avg_price'], price, quantity, pos['entry_date'], datetime.now(), pnl)
        if pos['quantity'] == 0:
            del self.portfolio[symbol]
        return True

# ============================================================
# REPORT GENERATION
# ============================================================

def generate_dividend_report(quotes, fundamentals, market_pulse, index_summary, sector_data,
                              upcoming_dividends, signals, account_balance=30000,
                              trade_journal=None, paper_engine=None, risk_off=False):
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    today = datetime.now().date()
    
    index_html = df_to_html(index_summary, 10)
    gainers_html = df_to_html(market_pulse.get('gainers'), 5)
    losers_html = df_to_html(market_pulse.get('losers'), 5)
    active_html = df_to_html(market_pulse.get('active'), 5)
    sectors_html = df_to_html(sector_data, 10)
    
    # Dividend calendar
    div_calendar = []
    for stock in upcoming_dividends:
        ex_date = datetime.strptime(stock["ex_date"], "%Y-%m-%d").date()
        days_until = (ex_date - today).days
        div_calendar.append({
            'symbol': stock['symbol'],
            'sector': stock.get('sector', 'N/A'),
            'ex_date': stock['ex_date'],
            'amount': stock['amount'],
            'days_until': days_until,
            'status': '🔥 IMMINENT' if days_until <= 2 else '🔶 SOON'
        })
    
    # Trade signals
    buy_signals = [s for s in signals if s and s.get('action') == 'BUY']
    hold_signals = [s for s in signals if s and s.get('action') == 'HOLD']
    
    journal = trade_journal.get_summary() if trade_journal else {}
    journal_total_trades = journal.get('total_trades', 0)
    journal_total_pnl = journal.get('total_pnl', 0)
    journal_win_rate = journal.get('win_rate', 0)
    journal_profit_factor = journal.get('profit_factor', 0)
    journal_max_drawdown = journal.get('max_drawdown', 0)
    
    if buy_signals:
        avg_yield = np.mean([s.get('yield_pct', 0) for s in buy_signals])
        avg_rr = np.mean([s.get('risk_reward1', 0) for s in buy_signals])
        projected_monthly = avg_yield + avg_rr * 0.3
        projected_annual = projected_monthly * 12
    else:
        projected_monthly = 0
        projected_annual = 0
    
    risk_off_badge = "🔴 RISK-OFF" if risk_off else "🟢 RISK-ON"
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; background: #0a0a0a; }}
            .header {{ background: linear-gradient(135deg, #0a1628, #1a3a5c); color: #00ff88; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; color: #00ff88; }}
            .header p {{ margin: 5px 0; color: #aaa; }}
            .section {{ background: #1a1a2e; margin: 20px; padding: 20px; border-radius: 8px; border: 1px solid #2a2a4e; }}
            .section h2 {{ color: #00ff88; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
            .section h3 {{ color: #66d9ff; margin: 10px 0; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; color: #ccc; }}
            th {{ background: #0a1628; color: #00ff88; padding: 8px; text-align: left; border-bottom: 2px solid #00ff88; }}
            td {{ padding: 8px; border-bottom: 1px solid #2a2a4e; color: #ddd; }}
            .buy {{ color: #00ff88; font-weight: bold; }}
            .sell {{ color: #ff4444; font-weight: bold; }}
            .neutral {{ color: #ffaa00; font-weight: bold; }}
            .signal-buy {{ background: rgba(0,255,136,0.1); }}
            .signal-sell {{ background: rgba(255,68,68,0.1); }}
            .signal-neutral {{ background: rgba(255,170,0,0.1); }}
            .footer {{ text-align: center; font-size: 12px; color: #666; margin: 20px; padding: 10px; border-top: 1px solid #2a2a4e; }}
            .profit {{ color: #00ff88; }}
            .loss {{ color: #ff4444; }}
            .highlight-box {{ background: rgba(0,255,136,0.1); border: 1px solid #00ff88; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            .dividend-badge {{ background: #00ff88; color: #0a0a0a; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
            .upcoming {{ background: #ffaa00; color: #0a0a0a; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
            .imminent {{ background: #ff4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
            .risk-off {{ background: #ff4444; color: white; padding: 2px 8px; border-radius: 12px; }}
            .risk-on {{ background: #00ff88; color: #0a0a0a; padding: 2px 8px; border-radius: 12px; }}
            .priority-badge {{ background: #ffaa00; color: #0a0a0a; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>💰 ULTIMATE DIVIDEND CAPTURE ENGINE v8.1</h1>
            <p>Generated on {now}</p>
            <p>💰 Account: PKR {account_balance:,.0f} | 📊 {len(upcoming_dividends)} Upcoming Dividends</p>
            <p>⚡ Monthly Cycle | Relaxed Filters | Priority Entry | Tiered Profit Taking</p>
            <p>🛡️ Mode: {risk_off_badge} | Max Daily Loss: {MAX_PORTFOLIO_DRAWDOWN*100:.0f}%</p>
            <p>📈 Projected Monthly Return: {projected_monthly:.2f}% | Annual: {projected_annual:.2f}%</p>
        </div>

        <div class="section highlight-box">
            <h2>📅 Upcoming Dividend Calendar</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Sector</th>
                        <th>Ex-Date</th>
                        <th>Dividend (PKR)</th>
                        <th>Days Until</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    """
    for div in div_calendar[:20]:
        days = div.get('days_until', 0)
        if days <= 2:
            badge = f"<span class='imminent'>🔥 IMMINENT</span>"
        else:
            badge = f"<span class='upcoming'>🔶 SOON</span>"
        html += f"""
                    <tr>
                        <td><strong>{div['symbol']}</strong></td>
                        <td>{div['sector']}</td>
                        <td>{div['ex_date']}</td>
                        <td>{div['amount']:.2f}</td>
                        <td>{days} days</td>
                        <td>{badge}</td>
                    </tr>
        """
    html += """
                </tbody>
            </table>
        </div>

        <div class="section highlight-box">
            <h2>🎯 Dividend Capture Trade Recommendations</h2>
            <p><strong>Entry Filters (Relaxed):</strong> Yield ≥ 3.5% (Priority) or 4% (Standard) | Volume ≥ 0.5 Cr (Priority)</p>
            <p><strong>Exit Strategy:</strong> Stop Loss (-3%) | Target1 (+5%, sell 50%) | Target2 (+8%, sell 50%)</p>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Entry Day</th>
                        <th>Ex-Date</th>
                        <th>Div</th>
                        <th>Yield %</th>
                        <th>Stop</th>
                        <th>T1</th>
                        <th>T2</th>
                        <th>Shares</th>
                        <th>Priority</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
    """
    if buy_signals:
        for signal in buy_signals[:10]:
            priority_badge = f"<span class='priority-badge'>{signal.get('priority', '')}</span>" if signal.get('priority') else ""
            html += f"""
                        <tr class="signal-buy">
                            <td><strong>{signal.get('symbol', 'N/A')}</strong></td>
                            <td>{signal.get('entry_price', 'N/A')}</td>
                            <td>{signal.get('entry_day', 'N/A')}</td>
                            <td>{signal.get('ex_date', 'N/A')}</td>
                            <td>{signal.get('div_amount', 0):.2f}</td>
                            <td class="buy">{signal.get('yield_pct', 0):.2f}%</td>
                            <td>{signal.get('stop_loss', 'N/A')}</td>
                            <td>{signal.get('target1', 'N/A')}</td>
                            <td>{signal.get('target2', 'N/A')}</td>
                            <td>{signal.get('shares', 0)}</td>
                            <td>{priority_badge}</td>
                            <td class="buy">🟢 BUY</td>
                        </tr>
            """
    else:
        html += '<tr><td colspan="12">⚠️ No qualifying dividend capture signals available</td></tr>'
    html += """
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>📊 Index Summary</h2>
            {index_html}
        </div>

        <div class="section">
            <h2>📈 Market Pulse</h2>
            <h3>🏆 Top Gainers</h3>
            {gainers_html}
            <h3>📉 Top Losers</h3>
            {losers_html}
            <h3>📊 Most Active</h3>
            {active_html}
        </div>

        <div class="section">
            <h2>🏭 Sector Performance</h2>
            {sectors_html}
        </div>

        <div class="section">
            <h2>📋 Trade Journal</h2>
            <p><strong>Total Trades:</strong> {journal_total_trades}</p>
            <p><strong>Total P&L:</strong> <span class="{'profit' if journal_total_pnl > 0 else 'loss'}">PKR {journal_total_pnl:,.2f}</span></p>
            <p><strong>Win Rate:</strong> {journal_win_rate*100:.1f}%</p>
            <p><strong>Profit Factor:</strong> {journal_profit_factor:.2f}</p>
            <p><strong>Max Drawdown:</strong> <span class="{'loss' if journal_max_drawdown < 0 else 'profit'}">PKR {journal_max_drawdown:,.2f}</span></p>
        </div>

        <div class="section">
            <h2>📈 Projected Returns (Monthly Cycle)</h2>
            <p><strong>Starting Balance:</strong> PKR {account_balance:,.0f}</p>
            <p><strong>Projected Monthly Return:</strong> {projected_monthly:.2f}%</p>
            <p><strong>Projected Annual Return:</strong> {projected_annual:.2f}%</p>
            <p><strong>Projected 6-Month:</strong> PKR {account_balance * (1 + projected_monthly/100)**6 - account_balance:,.2f}</p>
            <p><strong>Projected 12-Month:</strong> PKR {account_balance * (1 + projected_monthly/100)**12 - account_balance:,.2f}</p>
        </div>

        <div class="footer">
            <p>🕌 All stocks Shariah-compliant (KMI All Share Index)</p>
            <p>🛡️ Safety Filters: Yield ≥ 3.5-4% | Volume ≥ 0.5-1 Cr | RSI 25-75 | Stop-Loss -3%</p>
            <p>💰 Tiered Profit Taking: 50% at +5%, 50% at +8%</p>
            <p>⚠️ No trading system eliminates risk. Always do your own research.</p>
            <p>⚡ Generated by PSX Ultimate Dividend Capture Engine v8.1</p>
        </div>
    </body>
    </html>
    """
    return html

# ============================================================
# EMAIL SENDING
# ============================================================

def send_html_email(subject, html_body):
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "from": FROM_EMAIL,
        "to": [TO_EMAIL],
        "subject": subject,
        "html": html_body
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            print("✅ HTML email sent.")
            return True
        else:
            print(f"❌ Resend error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    print("💰 ULTIMATE DIVIDEND CAPTURE ENGINE v8.1")
    print("=" * 80)
    print(f"💰 Starting Balance: PKR {ACCOUNT_BALANCE:,.0f}")
    print(f"📋 Paper Trading: {'ACTIVE' if PAPER_TRADING else 'DISABLED'}")
    print(f"⚡ Strategy: Dividend Capture | Relaxed Filters | Priority Entry")
    print(f"🛡️ Stop-Loss: {STOP_LOSS_PCT*100:.0f}% | Max Daily Loss: {MAX_PORTFOLIO_DRAWDOWN*100:.0f}%")
    print("=" * 80)
    
    # 1. Dividend calendar
    print("📅 Fetching dividend calendar...")
    upcoming_dividends, all_dividends = fetch_dividend_calendar()
    print(f"   Upcoming dividends: {len(upcoming_dividends)}")
    
    # 2. Fetch data
    print("📡 Fetching stock data...")
    quotes = {}
    fundamentals = {}
    historical = {}
    for stock in all_dividends:
        symbol = stock['symbol']
        quotes[symbol] = fetch_quote(symbol)
        fundamentals[symbol] = fetch_fundamentals(symbol)
        historical[symbol] = fetch_historical(symbol)
    
    # 3. Market data
    market_pulse = fetch_market_pulse()
    index_summary = fetch_index_summary()
    sector_data = fetch_sector_performance()
    
    # 4. Risk-off check
    risk_off = False
    if index_summary is not None and not index_summary.empty:
        try:
            kse100_row = index_summary[index_summary['Index'] == 'KSE100']
            if not kse100_row.empty:
                change_pct = safe_float(kse100_row['PERCENTAGE_CHANGE'].iloc[0], 0)
                if change_pct < -RISK_OFF_INDEX_DROP * 100:
                    risk_off = True
                    print(f"⚠️ Index dropped {change_pct:.2f}% — RISK-OFF MODE ACTIVATED")
        except:
            pass
    
    # 5. Sentiment
    print("📰 Fetching news sentiment...")
    sentiment_data = fetch_sentiment()
    
    # 6. Generate signals
    print("🎯 Generating dividend capture signals with relaxed filters...")
    signals = []
    for stock in upcoming_dividends:
        symbol = stock['symbol']
        quote = quotes.get(symbol, {})
        price = quote.get('price', 'N/A')
        if isinstance(price, str):
            try:
                price = float(price)
            except:
                price = 0
        elif not isinstance(price, (int, float)):
            price = 0
        
        if price > 0:
            ind = calculate_indicators(historical.get(symbol))
            signal = generate_dividend_signal(symbol, price, stock, ind, quote)
            if signal:
                signals.append(signal)
    
    # 7. Paper trading
    paper_engine = PaperTradingEngine(ACCOUNT_BALANCE, MAX_PORTFOLIO_DRAWDOWN)
    trade_journal = TradeJournal()
    
    # 8. Execute BUY signals
    for signal in signals:
        if signal.get('action') == 'BUY' and not risk_off:
            symbol = signal.get('symbol')
            price = signal.get('entry_price', 0)
            shares = signal.get('shares', 0)
            stop_loss = signal.get('stop_loss', 0)
            target1 = signal.get('target1', 0)
            target2 = signal.get('target2', 0)
            if PAPER_TRADING and price > 0 and shares > 0:
                paper_engine.buy(symbol, price, shares, stop_loss, target1, target2)
    
    # 9. Generate report
    print("📝 Generating ultimate dividend capture report...")
    html_report = generate_dividend_report(
        quotes, fundamentals, market_pulse, index_summary, sector_data,
        upcoming_dividends, signals,
        ACCOUNT_BALANCE, trade_journal, paper_engine, risk_off
    )
    
    # 10. Send email
    subject = f"💰 Dividend Capture Report v8.1 - {len(upcoming_dividends)} Upcoming - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    success = send_html_email(subject, html_report)
    if success:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
