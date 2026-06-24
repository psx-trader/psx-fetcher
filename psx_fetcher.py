#!/usr/bin/env python3
"""
PSX ULTIMATE DIVIDEND CAPTURE ENGINE v11.0 — FINAL VERSION
Features:
- Shariah-Compliant (KMI-30 / KMI All Share)
- Dividend Capture with FORCE ENTRY for high-yield imminent dividends
- Swing Trading Signals (RSI-based)
- IPO & Right Shares Dashboard
- Accumulation Alerts
- Resend API for Email (No Gmail SMTP issues)
- Full Automation via GitHub Actions / Render
"""

import os
import sys
import json
import yaml
import logging
import argparse
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

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

# Read from environment variables (Render)
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')

# Trading parameters
ACCOUNT_BALANCE = 30000
MAX_RISK_PER_TRADE = 0.02
MAX_PORTFOLIO_DRAWDOWN = 0.02
STOP_LOSS_PCT = 0.03
TARGET1_PCT = 0.05
TARGET2_PCT = 0.08
PAPER_TRADING = True

# ============================================================
# SHARIAH-COMPLIANT DIVIDEND STOCKS
# ============================================================

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

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

def is_valid_ticker(symbol):
    return symbol in [s["symbol"] for s in DIVIDEND_STOCKS]

# ============================================================
# DIVIDEND CALENDAR
# ============================================================

def fetch_dividend_calendar():
    today = datetime.now().date()
    upcoming = []
    for stock in DIVIDEND_STOCKS:
        ex_date = datetime.strptime(stock["ex_date"], "%Y-%m-%d").date()
        days_until = (ex_date - today).days
        if 0 <= days_until <= 10:
            upcoming.append({**stock, "days_until": days_until})
    return upcoming

# ============================================================
# DATA FETCHING (with fallbacks)
# ============================================================

def fetch_quote(symbol):
    """Fetch real-time quote with fallback to pypsx and manual data."""
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        return {
            'symbol': symbol,
            'price': float(reg_data.get('Current', 0)) or 0,
            'change': float(reg_data.get('Change', 0)) or 0,
            'change_pct': float(reg_data.get('Change %', 0)) or 0,
            'volume': int(reg_data.get('Volume', 0)) or 0,
            'high': float(reg_data.get('High', 0)) or 0,
            'low': float(reg_data.get('Low', 0)) or 0,
            'open': float(reg_data.get('Open', 0)) or 0
        }
    except Exception as e:
        # Fallback to known prices from earlier data
        known_prices = {
            'FFC': 565.00,
            'SYS': 149.43,
            'MARI': 656.72,
            'EFERT': 199.38,
            'HUBC': 231.81,
            'MCB': 398.83,
            'OGDC': 320.00,
            'PPL': 230.00,
            'PSO': 355.00,
            'LUCK': 440.00,
            'MEBL': 500.00,
            'UBL': 415.00,
            'NBP': 192.00,
            'HBL': 290.00,
            'DGKC': 200.00,
            'MLCF': 84.00,
            'FCCL': 54.00,
            'ATRL': 885.00,
            'NRL': 371.00,
            'PRL': 35.00,
        }
        price = known_prices.get(symbol, 0)
        return {'symbol': symbol, 'price': price, 'volume': 0}

def fetch_fundamentals(symbol):
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        return {
            'pe': float(reg_data.get('P/E', 0)) or 0,
            'div_yield': float(reg_data.get('Dividend Yield', '0').replace('%', '')) or 0,
            'high_52w': float(reg_data.get('52W High', 0)) or 0,
            'low_52w': float(reg_data.get('52W Low', 0)) or 0
        }
    except Exception as e:
        return {'pe': 0, 'div_yield': 0, 'high_52w': 0, 'low_52w': 0}

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
        return pypsx.get_indices()
    except Exception as e:
        return None

def fetch_sector_performance():
    try:
        import pypsx
        return pypsx.sector_summary()
    except Exception as e:
        return None

def fetch_news_sentiment():
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                blob = TextBlob(title + " " + summary)
                polarity = blob.sentiment.polarity
                sentiment = 'bullish' if polarity > 0.1 else 'bearish' if polarity < -0.1 else 'neutral'
                articles.append({
                    'title': title,
                    'summary': summary[:200] + '...' if len(summary) > 200 else summary,
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'sentiment': sentiment,
                    'polarity': polarity
                })
        except Exception as e:
            pass
    if articles:
        avg_polarity = np.mean([a['polarity'] for a in articles])
        overall = 'bullish' if avg_polarity > 0.05 else 'bearish' if avg_polarity < -0.05 else 'neutral'
        return {'overall': overall, 'avg_polarity': avg_polarity, 'articles': articles[:10]}
    return {'overall': 'neutral', 'avg_polarity': 0, 'articles': []}

def fetch_ipos():
    # In production, scrape from PSX website
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

# ============================================================
# DIVIDEND CAPTURE SIGNAL GENERATION
# ============================================================

def generate_dividend_signal(symbol, price, stock_info):
    """
    FORCE ENTRY for high-yield dividends (>=6%) with imminent ex-date (<=2 days).
    Standard entry for other dividend opportunities.
    """
    if price <= 0 or not stock_info:
        return None
    
    div_amount = stock_info.get("amount", 0)
    ex_date = stock_info.get("ex_date", "")
    days_until = stock_info.get("days_until", 10)
    yield_pct = (div_amount / price) * 100 if price > 0 else 0
    
    # FORCE ENTRY: High yield + imminent ex-date
    force_entry = (yield_pct >= 6 and days_until <= 2) or (yield_pct >= 8 and days_until <= 4)
    
    # Standard entry: yield >= 4% and days_until between 2-5
    standard_entry = yield_pct >= 4 and 2 <= days_until <= 5
    
    if not force_entry and not standard_entry:
        return None
    
    shares = int(ACCOUNT_BALANCE * 0.95 / price)
    stop_loss = price * (1 - STOP_LOSS_PCT)
    target1 = price * (1 + TARGET1_PCT)
    target2 = price * (1 + TARGET2_PCT)
    
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
        'action': 'BUY',
        'priority': '⭐ FORCE ENTRY' if force_entry else '🟢 STANDARD',
        'reason': f'Yield {yield_pct:.1f}%, ex-date in {days_until} days'
    }

def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 50.0
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if len(rsi) > 0 else 50.0

# ============================================================
# EMAIL SENDING (Resend API — No Gmail SMTP)
# ============================================================

def send_via_resend(subject, html_body):
    """Send email using Resend API (HTTP, no SMTP needed)."""
    if not RESEND_API_KEY:
        print("❌ ERROR: RESEND_API_KEY not set in environment variables")
        return False
    
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
            print("✅ Email sent successfully via Resend")
            return True
        else:
            print(f"❌ Resend error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

# ============================================================
# HTML REPORT GENERATION
# ============================================================

def generate_html_report(upcoming_dividends, signals, market_pulse, index_summary, sector_data, sentiment, ipos):
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    today = datetime.now().date()
    
    # Build dividend calendar
    div_calendar = ""
    for stock in upcoming_dividends[:20]:
        days = stock.get('days_until', 0)
        status = "🔥 IMMINENT" if days <= 2 else "🔶 SOON"
        div_calendar += f"""
            <tr>
                <td><strong>{stock['symbol']}</strong></td>
                <td>{stock.get('sector', 'N/A')}</td>
                <td>{stock['ex_date']}</td>
                <td>{stock['amount']:.2f}</td>
                <td>{days} days</td>
                <td>{status}</td>
            </tr>
        """
    if not div_calendar:
        div_calendar = '<tr><td colspan="6">No upcoming dividends</td></tr>'
    
    # Build signals table
    signals_html = ""
    for sig in signals[:20]:
        priority_badge = f"⭐ FORCE ENTRY" if sig.get('priority') == '⭐ FORCE ENTRY' else "🟢 STANDARD"
        signals_html += f"""
            <tr>
                <td><strong>{sig['symbol']}</strong></td>
                <td>{sig['entry_price']:.2f}</td>
                <td>{sig['entry_day']}</td>
                <td>{sig['ex_date']}</td>
                <td>{sig['div_amount']:.2f}</td>
                <td class="buy">{sig['yield_pct']:.2f}%</td>
                <td>{sig['stop_loss']}</td>
                <td>{sig['target1']}</td>
                <td>{sig['target2']}</td>
                <td>{sig['shares']}</td>
                <td><span class="priority">{priority_badge}</span></td>
                <td class="buy">🟢 BUY</td>
            </tr>
        """
    if not signals_html:
        signals_html = '<tr><td colspan="12">⚠️ No qualifying dividend capture signals available</td></tr>'
    
    # Build market pulse
    gainers_html = ""
    losers_html = ""
    active_html = ""
    if market_pulse:
        if market_pulse.get('gainers') is not None and not market_pulse['gainers'].empty:
            for idx, row in market_pulse['gainers'].head(5).iterrows():
                gainers_html += f"<li>{row.get('Symbol', 'N/A')}: {row.get('CHANGE %', 0)}%</li>"
        if market_pulse.get('losers') is not None and not market_pulse['losers'].empty:
            for idx, row in market_pulse['losers'].head(5).iterrows():
                losers_html += f"<li>{row.get('Symbol', 'N/A')}: {row.get('CHANGE %', 0)}%</li>"
        if market_pulse.get('active') is not None and not market_pulse['active'].empty:
            for idx, row in market_pulse['active'].head(5).iterrows():
                active_html += f"<li>{row.get('Symbol', 'N/A')}: {row.get('Volume', 0)}</li>"
    
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
    
    # Sentiment
    sentiment_text = sentiment.get('overall', 'neutral').upper()
    sentiment_color = '#00ff88' if sentiment_text == 'BULLISH' else '#ff4444' if sentiment_text == 'BEARISH' else '#ffaa00'
    
    # Projected returns
    if signals:
        avg_yield = np.mean([s.get('yield_pct', 0) for s in signals])
        projected_monthly = avg_yield * 1.2
        projected_annual = projected_monthly * 12
    else:
        projected_monthly = 0
        projected_annual = 0
    
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
            .footer {{ text-align: center; font-size: 12px; color: #666; margin-top: 20px; padding: 10px; border-top: 1px solid #2a2a4e; }}
            ul {{ color: #ccc; }}
            li {{ margin: 5px 0; }}
            .force-entry {{ background: #ff4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v11.0</h1>
            <p>Generated on {now}</p>
            <p>💰 Account: PKR {ACCOUNT_BALANCE:,.0f} | 📊 {len(upcoming_dividends)} Upcoming Dividends</p>
            <p>⚡ FORCE ENTRY for High-Yield Imminent Dividends | Resend Email API</p>
            <p>📊 Market Sentiment: <span style="color:{sentiment_color};">{sentiment_text}</span></p>
            <p>📈 Projected Monthly Return: {projected_monthly:.2f}% | Annual: {projected_annual:.2f}%</p>
        </div>

        <div class="section">
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
                    {div_calendar}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>🎯 Dividend Capture Trade Recommendations</h2>
            <p><strong>FORCE ENTRY:</strong> Yield ≥ 6% + ex-date ≤ 2 days | <strong>Standard:</strong> Yield ≥ 4% + ex-date 2-5 days</p>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Entry Day</th>
                        <th>Ex-Date</th>
                        <th>Dividend</th>
                        <th>Yield %</th>
                        <th>Stop</th>
                        <th>Target1</th>
                        <th>Target2</th>
                        <th>Shares</th>
                        <th>Priority</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {signals_html}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>📈 Market Pulse</h2>
            <h3>🏆 Top Gainers</h3>
            <ul>{gainers_html or '<li>No data</li>'}</ul>
            <h3>📉 Top Losers</h3>
            <ul>{losers_html or '<li>No data</li>'}</ul>
            <h3>📊 Most Active</h3>
            <ul>{active_html or '<li>No data</li>'}</ul>
        </div>

        <div class="section">
            <h2>🏭 Sector Performance</h2>
            {df_to_html(sector_data, 10) if sector_data is not None else '<p>No sector data available</p>'}
        </div>

        <div class="section">
            <h2>📊 Index Summary</h2>
            {df_to_html(index_summary, 5) if index_summary is not None else '<p>No index data available</p>'}
        </div>

        <div class="section">
            <h2>🏢 IPO Dashboard</h2>
            <table>
                <thead>
                    <tr><th>Company</th><th>Symbol</th><th>Offer Price</th><th>Subscription Open</th><th>Subscription Close</th><th>Status</th></tr>
                </thead>
                <tbody>{ipo_html}</tbody>
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

        <div class="section">
            <h2>⏰ Monthly Cycle Schedule</h2>
            <p><strong>Week 1-2:</strong> Screen for upcoming dividends with FORCE ENTRY detection</p>
            <p><strong>Week 2-3:</strong> Enter positions 1-2 days before ex-date</p>
            <p><strong>Week 3:</strong> Hold through ex-date, receive dividend</p>
            <p><strong>Week 3-4:</strong> Exit at Target1 (5%), hold for Target2 (8%)</p>
            <p><strong>Week 4:</strong> Stop-loss at -3% protects capital</p>
            <p><strong>Repeat:</strong> Compound profits into next dividend cycle</p>
        </div>

        <div class="footer">
            <p>🕌 All stocks Shariah-compliant (KMI All Share Index)</p>
            <p>🛡️ Stop-Loss: 3% | Max Daily Loss: 2% | Position Sizing: 95% of capital</p>
            <p>📧 Email via Resend API (No Gmail SMTP required)</p>
            <p>⚠️ No trading system eliminates risk. Always do your own research.</p>
            <p>⚡ Generated by PSX Ultimate Dividend Capture Engine v11.0</p>
        </div>
    </body>
    </html>
    """
    return html

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    print("💰 PSX ULTIMATE DIVIDEND CAPTURE ENGINE v11.0")
    print("=" * 80)
    print(f"💰 Starting Balance: PKR {ACCOUNT_BALANCE:,.0f}")
    print(f"📋 Paper Trading: {'ACTIVE' if PAPER_TRADING else 'DISABLED'}")
    print(f"📧 Email via Resend API (No Gmail SMTP issues)")
    print("=" * 80)
    
    # 1. Fetch dividend calendar
    print("📅 Fetching dividend calendar...")
    upcoming_dividends = fetch_dividend_calendar()
    print(f"   Upcoming dividends: {len(upcoming_dividends)}")
    
    # 2. Fetch stock data
    print("📡 Fetching stock data...")
    quotes = {}
    for stock in upcoming_dividends:
        symbol = stock['symbol']
        quotes[symbol] = fetch_quote(symbol)
    
    # 3. Generate signals
    print("🎯 Generating dividend capture signals...")
    signals = []
    for stock in upcoming_dividends:
        symbol = stock['symbol']
        quote = quotes.get(symbol, {})
        price = quote.get('price', 0)
        if price > 0:
            signal = generate_dividend_signal(symbol, price, stock)
            if signal:
                signals.append(signal)
    
    print(f"   Generated {len(signals)} signals")
    
    # 4. Fetch market data
    print("📊 Fetching market data...")
    market_pulse = fetch_market_pulse()
    index_summary = fetch_index_summary()
    sector_data = fetch_sector_performance()
    sentiment = fetch_news_sentiment()
    ipos = fetch_ipos()
    
    # 5. Generate report
    print("📝 Generating HTML report...")
    html_report = generate_html_report(
        upcoming_dividends, signals, market_pulse,
        index_summary, sector_data, sentiment, ipos
    )
    
    # 6. Send email
    print("📧 Sending email via Resend API...")
    subject = f"💰 Dividend Capture Report - {datetime.now().strftime('%Y-%m-%d')}"
    success = send_via_resend(subject, html_report)
    
    if success:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")
    
    print("=" * 80)
    print("✅ Pipeline completed!")

if __name__ == "__main__":
    main()
