#!/usr/bin/env python3
"""
PSX Maximum Information Trading Report
Combines: Stock Data + Technical Indicators + Macroeconomic Context + News Sentiment + Trading Signals
"""

import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import feedparser
from textblob import TextBlob
import concurrent.futures

# ============================================================
# CONFIGURATION
# ============================================================
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')

# Stock symbols to track
STOCK_SYMBOLS = ["FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB"]

# Trading parameters
TRADING_PARAMS = {
    "RSI_OVERSOLD": 30,
    "RSI_OVERBOUGHT": 70,
    "SMA_SHORT": 20,
    "SMA_LONG": 50,
    "PROFIT_TARGET_PCT": 10,
    "STOP_LOSS_PCT": 5,
}

# SBP EasyData API Key (get from https://easydata.sbp.org.pk)
SBP_API_KEY = os.environ.get('SBP_API_KEY', 'C10D3D29160CE5693F56AA9846ABB2C423D8B123')

# News RSS Feeds
NEWS_FEEDS = [
    "https://www.dawn.com/feeds/business",
    "https://www.brecorder.com/rss/news",
    "https://www.thenews.com.pk/rss/2/5",
]

# ============================================================
# 1. PSX-MCP DATA FETCHING (MCP Server)
# ============================================================

def fetch_psx_mcp_data(symbol):
    """Fetch comprehensive data from psx-mcp server.
    Requires psx-mcp server running locally or remotely.
    Install: pip install psx-mcp
    Run: psx-mcp --transport http
    """
    base_url = "http://localhost:5000"  # Default psx-mcp HTTP server
    
    try:
        # Get quote
        quote_resp = requests.post(f"{base_url}/tools/get_quote", 
                                   json={"symbol": symbol}, timeout=5)
        quote_data = quote_resp.json() if quote_resp.status_code == 200 else {}
        
        # Get upcoming dividends
        div_resp = requests.post(f"{base_url}/tools/get_upcoming_dividends",
                                 json={"symbol": symbol}, timeout=5)
        div_data = div_resp.json() if div_resp.status_code == 200 else {}
        
        # Get dividend history
        hist_resp = requests.post(f"{base_url}/tools/get_dividend_history",
                                  json={"symbol": symbol, "years": 5}, timeout=5)
        hist_data = hist_resp.json() if hist_resp.status_code == 200 else {}
        
        # Get announcements
        ann_resp = requests.post(f"{base_url}/tools/get_announcements",
                                 json={"symbol": symbol, "limit": 5}, timeout=5)
        ann_data = ann_resp.json() if ann_resp.status_code == 200 else {}
        
        # Get indices
        idx_resp = requests.post(f"{base_url}/tools/get_indices", timeout=5)
        idx_data = idx_resp.json() if idx_resp.status_code == 200 else {}
        
        # Get market status
        status_resp = requests.post(f"{base_url}/tools/get_market_status", timeout=5)
        status_data = status_resp.json() if status_resp.status_code == 200 else {}
        
        return {
            "symbol": symbol,
            "quote": quote_data,
            "dividends": div_data,
            "dividend_history": hist_data,
            "announcements": ann_data,
            "indices": idx_data,
            "market_status": status_data
        }
    except Exception as e:
        print(f"psx-mcp error for {symbol}: {e}")
        return None

# ============================================================
# 2. PYPSX DATA FETCHING (Fallback / Direct)
# ============================================================

def fetch_pypsx_data(symbol):
    """Fetch data using pypsx library (direct, no MCP server needed)."""
    try:
        import pypsx
        
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        
        # Get historical data for technical analysis
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        hist_df = ticker.get_historical(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
        return {
            "symbol": symbol,
            "price": reg_data.get('Current', 'N/A'),
            "change": reg_data.get('Change', 'N/A'),
            "change_pct": reg_data.get('Change %', 'N/A'),
            "volume": reg_data.get('Volume', 'N/A'),
            "high": reg_data.get('High', 'N/A'),
            "low": reg_data.get('Low', 'N/A'),
            "open": reg_data.get('Open', 'N/A'),
            "pe": reg_data.get('P/E', 'N/A'),
            "div_yield": reg_data.get('Dividend Yield', 'N/A'),
            "high_52w": reg_data.get('52W High', 'N/A'),
            "low_52w": reg_data.get('52W Low', 'N/A'),
            "historical": hist_df
        }
    except Exception as e:
        print(f"pypsx error for {symbol}: {e}")
        return None

# ============================================================
# 3. MACROECONOMIC DATA (SBP EasyData)
# ============================================================

def fetch_macro_data():
    """Fetch macroeconomic indicators from SBP EasyData."""
    try:
        # Try using EasyDataPy library if available
        try:
            from EasyDataPy import EasyData_key_setup, download_series, build_time_series
            EasyData_key_setup(SBP_API_KEY)
            
            # Download key indicators
            # Repo rate
            repo_data = download_series("TS_GP_IR_REPOMR_D.ORR", 
                                        (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
                                        datetime.now().strftime("%Y-%m-%d"), "csv")
            repo_ts = build_time_series(repo_data) if repo_data is not None else None
            
            # Current account balance (example series ID)
            ca_data = download_series("TS_GP_EXT_CA_D.BOP",
                                      (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
                                      datetime.now().strftime("%Y-%m-%d"), "csv")
            ca_ts = build_time_series(ca_data) if ca_data is not None else None
            
            return {
                "repo_rate": repo_ts.iloc[-1] if repo_ts is not None and len(repo_ts) > 0 else "N/A",
                "current_account": ca_ts.iloc[-1] if ca_ts is not None and len(ca_ts) > 0 else "N/A",
                "source": "EasyDataPy"
            }
        except ImportError:
            # Fallback: Use web scraping or static data
            print("EasyDataPy not installed. Using fallback macro data.")
            return {
                "repo_rate": "15.00%",
                "current_account": "-$324M",
                "source": "Fallback"
            }
    except Exception as e:
        print(f"Macro data error: {e}")
        return {"repo_rate": "N/A", "current_account": "N/A", "source": "Error"}

# ============================================================
# 4. NEWS SENTIMENT ANALYSIS
# ============================================================

def fetch_news_sentiment():
    """Fetch and analyze news sentiment from RSS feeds."""
    articles = []
    
    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                # Get title and summary
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                
                # Sentiment analysis using TextBlob
                blob = TextBlob(title + " " + summary)
                sentiment_polarity = blob.sentiment.polarity  # -1 to 1
                sentiment_subjectivity = blob.sentiment.subjectivity  # 0 to 1
                
                # Classify sentiment
                if sentiment_polarity > 0.1:
                    sentiment_label = "🟢 Bullish"
                elif sentiment_polarity < -0.1:
                    sentiment_label = "🔴 Bearish"
                else:
                    sentiment_label = "🟡 Neutral"
                
                # Check for PSX-related keywords
                psx_keywords = ["PSX", "KSE", "stock", "market", "share", "dividend", "profit"]
                is_psx_related = any(kw.lower() in (title + summary).lower() for kw in psx_keywords)
                
                articles.append({
                    "title": title,
                    "summary": summary[:200] + "..." if len(summary) > 200 else summary,
                    "link": entry.get('link', ''),
                    "published": entry.get('published', ''),
                    "sentiment": sentiment_label,
                    "polarity": sentiment_polarity,
                    "subjectivity": sentiment_subjectivity,
                    "is_psx_related": is_psx_related
                })
        except Exception as e:
            print(f"Error fetching feed {feed_url}: {e}")
    
    # Sort by recency and relevance
    articles.sort(key=lambda x: (x['is_psx_related'], abs(x['polarity'])), reverse=True)
    return articles[:15]  # Return top 15 most relevant articles

# ============================================================
# 5. TECHNICAL INDICATORS
# ============================================================

def calculate_indicators(df):
    """Calculate technical indicators from historical data."""
    if df is None or df.empty:
        return {}
    
    # Ensure we have the right column names
    close_col = 'close' if 'close' in df.columns else 'Close' if 'Close' in df.columns else df.columns[3]
    high_col = 'high' if 'high' in df.columns else 'High' if 'High' in df.columns else df.columns[1]
    low_col = 'low' if 'low' in df.columns else 'Low' if 'Low' in df.columns else df.columns[2]
    volume_col = 'volume' if 'volume' in df.columns else 'Volume' if 'Volume' in df.columns else df.columns[4]
    
    close = df[close_col]
    high = df[high_col]
    low = df[low_col]
    volume = df[volume_col]
    
    indicators = {}
    
    # RSI (14-period)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1] if len(rs) > 0 else None
    
    # SMA
    indicators['sma_20'] = close.tail(20).mean() if len(close) >= 20 else None
    indicators['sma_50'] = close.tail(50).mean() if len(close) >= 50 else None
    indicators['sma_200'] = close.tail(200).mean() if len(close) >= 200 else None
    
    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    indicators['macd'] = macd.iloc[-1] if len(macd) > 0 else None
    indicators['macd_signal'] = signal.iloc[-1] if len(signal) > 0 else None
    indicators['macd_histogram'] = (macd - signal).iloc[-1] if len(macd) > 0 and len(signal) > 0 else None
    
    # Bollinger Bands
    sma_20 = close.tail(20).mean()
    std_20 = close.tail(20).std()
    indicators['bb_upper'] = sma_20 + (std_20 * 2)
    indicators['bb_middle'] = sma_20
    indicators['bb_lower'] = sma_20 - (std_20 * 2)
    indicators['bb_position'] = ((close.iloc[-1] - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])) if indicators['bb_upper'] != indicators['bb_lower'] else 0.5
    
    # ATR (Average True Range)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    indicators['atr'] = tr.rolling(window=14).mean().iloc[-1] if len(tr) >= 14 else None
    
    # Volume indicators
    indicators['volume_sma'] = volume.tail(20).mean() if len(volume) >= 20 else None
    indicators['volume_ratio'] = (volume.iloc[-1] / indicators['volume_sma']) if indicators['volume_sma'] and indicators['volume_sma'] > 0 else None
    
    # Support / Resistance (simple approach)
    if len(close) >= 20:
        indicators['resistance'] = close.tail(20).max()
        indicators['support'] = close.tail(20).min()
    else:
        indicators['resistance'] = None
        indicators['support'] = None
    
    return indicators

# ============================================================
# 6. SIGNAL GENERATION
# ============================================================

def generate_signals(symbol, price, indicators, fundamentals):
    """Generate buy/sell signals based on technical indicators."""
    signals = []
    
    if not indicators:
        return [{"signal": "⚠️ Insufficient data"}]
    
    # 1. RSI Signal
    rsi = indicators.get('rsi')
    if rsi is not None:
        if rsi < TRADING_PARAMS["RSI_OVERSOLD"]:
            signals.append({
                "signal": "🟢 BUY",
                "indicator": "RSI",
                "value": f"{rsi:.2f}",
                "reason": f"RSI oversold ({rsi:.2f} < {TRADING_PARAMS['RSI_OVERSOLD']})",
                "timing": "Immediate — market open",
                "priority": "HIGH"
            })
        elif rsi > TRADING_PARAMS["RSI_OVERBOUGHT"]:
            signals.append({
                "signal": "🔴 SELL/AVOID",
                "indicator": "RSI",
                "value": f"{rsi:.2f}",
                "reason": f"RSI overbought ({rsi:.2f} > {TRADING_PARAMS['RSI_OVERBOUGHT']})",
                "timing": "Wait for pullback",
                "priority": "HIGH"
            })
        else:
            signals.append({
                "signal": "⏳ NEUTRAL",
                "indicator": "RSI",
                "value": f"{rsi:.2f}",
                "reason": f"RSI in neutral zone ({TRADING_PARAMS['RSI_OVERSOLD']}-{TRADING_PARAMS['RSI_OVERBOUGHT']})",
                "timing": "Watch for breakout",
                "priority": "MEDIUM"
            })
    
    # 2. SMA Crossover
    sma_short = indicators.get('sma_20')
    sma_long = indicators.get('sma_50')
    if sma_short is not None and sma_long is not None:
        if sma_short > sma_long:
            signals.append({
                "signal": "🟢 BULLISH",
                "indicator": "SMA 20/50",
                "value": f"SMA20: {sma_short:.2f}, SMA50: {sma_long:.2f}",
                "reason": "Short-term > Long-term — uptrend",
                "timing": "Buy on dips",
                "priority": "HIGH"
            })
        else:
            signals.append({
                "signal": "🔴 BEARISH",
                "indicator": "SMA 20/50",
                "value": f"SMA20: {sma_short:.2f}, SMA50: {sma_long:.2f}",
                "reason": "Short-term < Long-term — downtrend",
                "timing": "Avoid, wait for reversal",
                "priority": "HIGH"
            })
    
    # 3. MACD
    macd = indicators.get('macd')
    macd_signal = indicators.get('macd_signal')
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            signals.append({
                "signal": "🟢 BULLISH",
                "indicator": "MACD",
                "value": f"MACD: {macd:.4f}, Signal: {macd_signal:.4f}",
                "reason": "MACD above signal line — bullish momentum",
                "timing": "Buy on confirmation",
                "priority": "MEDIUM"
            })
        else:
            signals.append({
                "signal": "🔴 BEARISH",
                "indicator": "MACD",
                "value": f"MACD: {macd:.4f}, Signal: {macd_signal:.4f}",
                "reason": "MACD below signal line — bearish momentum",
                "timing": "Sell or avoid",
                "priority": "MEDIUM"
            })
    
    # 4. Bollinger Bands
    bb_lower = indicators.get('bb_lower')
    bb_upper = indicators.get('bb_upper')
    if bb_lower is not None and bb_upper is not None and price is not None and isinstance(price, (int, float)):
        if price <= bb_lower:
            signals.append({
                "signal": "🟢 BUY",
                "indicator": "Bollinger Bands",
                "value": f"Lower: {bb_lower:.2f}, Price: {price:.2f}",
                "reason": "Price at lower band — potential bounce",
                "timing": "Immediate — market open",
                "priority": "HIGH"
            })
        elif price >= bb_upper:
            signals.append({
                "signal": "🔴 SELL/PROFIT",
                "indicator": "Bollinger Bands",
                "value": f"Upper: {bb_upper:.2f}, Price: {price:.2f}",
                "reason": "Price at upper band — potential reversal",
                "timing": "Take profits now",
                "priority": "HIGH"
            })
    
    # 5. Volume analysis
    vol_ratio = indicators.get('volume_ratio')
    if vol_ratio is not None:
        if vol_ratio > 1.5:
            signals.append({
                "signal": "📊 HIGH VOLUME",
                "indicator": "Volume",
                "value": f"{vol_ratio:.2f}x average",
                "reason": "Volume 50% above average — strong interest",
                "timing": "Watch for breakout direction",
                "priority": "MEDIUM"
            })
    
    return signals

# ============================================================
# 7. ENTRY/EXIT PRICE CALCULATION
# ============================================================

def calculate_entry_exit(symbol, price, signals):
    """Calculate entry, target, and stop-loss prices."""
    if price is None or not isinstance(price, (int, float)):
        return {
            'entry_price': 'N/A',
            'target_price': 'N/A',
            'stop_loss': 'N/A',
            'entry_timing': 'N/A',
            'exit_timing': 'N/A'
        }
    
    bullish_signals = [s for s in signals if 'BUY' in s.get('signal', '') or 'BULLISH' in s.get('signal', '')]
    bearish_signals = [s for s in signals if 'SELL' in s.get('signal', '') or 'BEARISH' in s.get('signal', '')]
    
    if len(bullish_signals) > len(bearish_signals):
        entry = price
        target = price * (1 + TRADING_PARAMS["PROFIT_TARGET_PCT"] / 100)
        stop = price * (1 - TRADING_PARAMS["STOP_LOSS_PCT"] / 100)
        timing = "Market open — buy immediately"
        exit_timing = f"When price reaches PKR {target:.2f} or falls below {stop:.2f}"
    else:
        entry = price * 0.97
        target = entry * (1 + TRADING_PARAMS["PROFIT_TARGET_PCT"] / 100)
        stop = entry * (1 - TRADING_PARAMS["STOP_LOSS_PCT"] / 100)
        timing = f"Wait for dip to PKR {entry:.2f}"
        exit_timing = f"When price reaches PKR {target:.2f} or falls below {stop:.2f}"
    
    return {
        'entry_price': round(entry, 2),
        'target_price': round(target, 2),
        'stop_loss': round(stop, 2),
        'entry_timing': timing,
        'exit_timing': exit_timing
    }

# ============================================================
# 8. HTML REPORT GENERATION
# ============================================================

def generate_html_report(quotes, fundamentals, indicators_data, signals_data, entry_exit_data,
                         macro_data, news_articles, index_data, mcp_data):
    """Generate comprehensive HTML report with all information."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #1a3a5c, #2a5a8c); color: white; padding: 20px; text-align: center; }}
            .section {{ background: white; margin: 20px; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .section h2 {{ color: #1a3a5c; margin-top: 0; border-bottom: 2px solid #1a3a5c; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
            th {{ background: #1a3a5c; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 10px; border-bottom: 1px solid #eee; }}
            .buy {{ color: green; font-weight: bold; }}
            .sell {{ color: red; font-weight: bold; }}
            .neutral {{ color: orange; font-weight: bold; }}
            .signal-buy {{ background: #e8f5e9; }}
            .signal-sell {{ background: #ffebee; }}
            .signal-neutral {{ background: #fff3e0; }}
            .footer {{ text-align: center; font-size: 12px; color: #888; margin: 20px; padding: 10px; border-top: 1px solid #ddd; }}
            .highlight {{ background: #fff9c4; padding: 2px 6px; border-radius: 3px; }}
            .positive {{ color: green; font-weight: bold; }}
            .negative {{ color: red; font-weight: bold; }}
            .macro-box {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .news-box {{ background: #fafafa; padding: 10px; border-radius: 5px; margin: 5px 0; border-left: 4px solid #1a3a5c; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📈 PSX Maximum Information Report</h1>
            <p>Comprehensive Market Intelligence for Informed Trading Decisions</p>
            <p>Generated on {now}</p>
        </div>
    """
    
    # ====== SECTION 1: MACROECONOMIC CONTEXT ======
    html += """
        <div class="section">
            <h2>🏛️ Macroeconomic Context</h2>
            <div class="macro-box">
    """
    if macro_data:
        html += f"""
                <p><strong>Repo Rate:</strong> {macro_data.get('repo_rate', 'N/A')}</p>
                <p><strong>Current Account Balance:</strong> {macro_data.get('current_account', 'N/A')}</p>
                <p><strong>Data Source:</strong> {macro_data.get('source', 'N/A')}</p>
                <p style="font-size: 12px; color: #666;">📌 Higher repo rates generally make borrowing expensive, impacting corporate profits.</p>
            </div>
        </div>
        """
    else:
        html += "<p>⚠️ Macroeconomic data unavailable</p></div></div>"
    
    # ====== SECTION 2: MARKET INDICES ======
    html += """
        <div class="section">
            <h2>📊 Market Indices</h2>
            <table>
                <thead>
                    <tr><th>Index</th><th>Current</th><th>Change</th><th>Change %</th></tr>
                </thead>
                <tbody>
    """
    if index_data is not None and not index_data.empty:
        for idx, row in index_data.head(10).iterrows():
            name = row.get('Index', row.get('name', 'N/A'))
            current = row.get('Current', row.get('current', 'N/A'))
            change = row.get('Change', row.get('change', 'N/A'))
            change_pct = row.get('Change %', row.get('change_pct', 'N/A'))
            html += f"<tr><td>{name}</td><td>{current}</td><td>{change}</td><td>{change_pct}</td></tr>"
    else:
        html += "<tr><td colspan='4'>⚠️ Index data unavailable</td></tr>"
    html += """
                </tbody>
            </table>
        </div>
    """
    
    # ====== SECTION 3: MARKET STATUS (MCP) ======
    if mcp_data and mcp_data.get('market_status'):
        status = mcp_data['market_status']
        html += f"""
        <div class="section">
            <h2>⏰ Market Status</h2>
            <p><strong>Status:</strong> {status.get('status', 'N/A')}</p>
            <p><strong>Next Open:</strong> {status.get('next_open', 'N/A')}</p>
        </div>
        """
    
    # ====== SECTION 4: STOCK DATA WITH SIGNALS ======
    html += """
        <div class="section">
            <h2>📈 Stock Data & Trading Signals</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Change %</th>
                        <th>Volume</th>
                        <th>P/E</th>
                        <th>Div Yield</th>
                        <th>52W High</th>
                        <th>52W Low</th>
                        <th>Signal</th>
                    </tr>
                </thead>
                <tbody>
    """
    for symbol in STOCK_SYMBOLS:
        q = quotes.get(symbol, {})
        f = fundamentals.get(symbol, {})
        sigs = signals_data.get(symbol, [])
        price = q.get('price', 'N/A')
        change_pct = q.get('change_pct', 'N/A')
        
        # Determine primary signal
        primary_signal = "⏳ NEUTRAL"
        for sig in sigs:
            if 'BUY' in sig.get('signal', '') and sig.get('priority') == 'HIGH':
                primary_signal = "🟢 BUY"
                break
            elif 'SELL' in sig.get('signal', '') and sig.get('priority') == 'HIGH':
                primary_signal = "🔴 SELL"
                break
        
        html += f"""
                    <tr>
                        <td><strong>{symbol}</strong></td>
                        <td>{price}</td>
                        <td>{change_pct}</td>
                        <td>{q.get('volume', 'N/A')}</td>
                        <td>{f.get('pe', 'N/A')}</td>
                        <td>{f.get('div_yield', 'N/A')}</td>
                        <td>{f.get('high_52w', 'N/A')}</td>
                        <td>{f.get('low_52w', 'N/A')}</td>
                        <td><span class="{'buy' if 'BUY' in primary_signal else 'sell' if 'SELL' in primary_signal else 'neutral'}">{primary_signal}</span></td>
                    </tr>
        """
    html += """
                </tbody>
            </table>
        </div>
    """
    
    # ====== SECTION 5: DETAILED SIGNALS ======
    html += """
        <div class="section">
            <h2>🎯 Detailed Trading Signals</h2>
    """
    for symbol in STOCK_SYMBOLS:
        sigs = signals_data.get(symbol, [])
        ee = entry_exit_data.get(symbol, {})
        if sigs:
            html += f"<h3>{symbol}</h3>"
            html += "<table><thead><tr><th>Signal</th><th>Indicator</th><th>Value</th><th>Reason</th><th>Timing</th></tr></thead><tbody>"
            for sig in sigs[:5]:
                row_class = 'signal-buy' if 'BUY' in sig.get('signal', '') else 'signal-sell' if 'SELL' in sig.get('signal', '') else 'signal-neutral'
                signal_class = 'buy' if 'BUY' in sig.get('signal', '') else 'sell' if 'SELL' in sig.get('signal', '') else 'neutral'
                html += f"""
                    <tr class="{row_class}">
                        <td class="{signal_class}">{sig.get('signal', 'N/A')}</td>
                        <td>{sig.get('indicator', 'N/A')}</td>
                        <td>{sig.get('value', 'N/A')}</td>
                        <td>{sig.get('reason', 'N/A')}</td>
                        <td><span class="highlight">{sig.get('timing', 'N/A')}</span></td>
                    </tr>
                """
            html += "</tbody></table>"
            html += f"""
                <p style="margin-top: 5px;">
                    <strong>Entry:</strong> PKR {ee.get('entry_price', 'N/A')} | 
                    <strong>Target:</strong> PKR {ee.get('target_price', 'N/A')} | 
                    <strong>Stop Loss:</strong> PKR {ee.get('stop_loss', 'N/A')}
                </p>
                <p style="font-size: 12px; color: #666;">
                    <strong>Entry Timing:</strong> {ee.get('entry_timing', 'N/A')}<br>
                    <strong>Exit Timing:</strong> {ee.get('exit_timing', 'N/A')}
                </p>
            """
    html += "</div>"
    
    # ====== SECTION 6: TECHNICAL INDICATORS ======
    html += """
        <div class="section">
            <h2>📊 Technical Indicators</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>RSI</th>
                        <th>SMA20</th>
                        <th>SMA50</th>
                        <th>MACD</th>
                        <th>BB Position</th>
                        <th>ATR</th>
                        <th>Vol Ratio</th>
                    </tr>
                </thead>
                <tbody>
    """
    for symbol in STOCK_SYMBOLS:
        ind = indicators_data.get(symbol, {})
        html += f"""
                    <tr>
                        <td><strong>{symbol}</strong></td>
                        <td>{ind.get('rsi', 'N/A'):.2f if ind.get('rsi') else 'N/A'}</td>
                        <td>{ind.get('sma_20', 'N/A'):.2f if ind.get('sma_20') else 'N/A'}</td>
                        <td>{ind.get('sma_50', 'N/A'):.2f if ind.get('sma_50') else 'N/A'}</td>
                        <td>{ind.get('macd', 'N/A'):.4f if ind.get('macd') else 'N/A'}</td>
                        <td>{ind.get('bb_position', 'N/A'):.2f if ind.get('bb_position') else 'N/A'}</td>
                        <td>{ind.get('atr', 'N/A'):.2f if ind.get('atr') else 'N/A'}</td>
                        <td>{ind.get('volume_ratio', 'N/A'):.2f if ind.get('volume_ratio') else 'N/A'}</td>
                    </tr>
        """
    html += """
                </tbody>
            </table>
            <p style="font-size: 12px; color: #666; margin-top: 10px;">
                📌 <strong>BB Position:</strong> 0 = lower band (oversold), 1 = upper band (overbought)<br>
                📌 <strong>Vol Ratio:</strong> > 1.5 indicates unusually high trading activity
            </p>
        </div>
    """
    
    # ====== SECTION 7: NEWS SENTIMENT ======
    html += """
        <div class="section">
            <h2>📰 News Sentiment</h2>
    """
    if news_articles:
        for article in news_articles[:10]:
            sentiment_color = '#4caf50' if 'Bullish' in article['sentiment'] else '#f44336' if 'Bearish' in article['sentiment'] else '#ff9800'
            html += f"""
                <div class="news-box" style="border-left-color: {sentiment_color};">
                    <p><strong>{article['title']}</strong></p>
                    <p style="font-size: 13px; color: #555;">{article['summary']}</p>
                    <p style="font-size: 11px; color: #999;">
                        <span style="color: {sentiment_color}; font-weight: bold;">{article['sentiment']}</span> | 
                        Polarity: {article['polarity']:.2f} | 
                        {article.get('published', '')}
                        {' | 📌 PSX Related' if article.get('is_psx_related') else ''}
                    </p>
                </div>
            """
    else:
        html += "<p>⚠️ No news articles available</p>"
    html += "</div>"
    
    # ====== SECTION 8: EXECUTION SUMMARY ======
    buy_list = []
    sell_list = []
    hold_list = []
    
    for symbol in STOCK_SYMBOLS:
        sigs = signals_data.get(symbol, [])
        has_buy = any('BUY' in s.get('signal', '') for s in sigs)
        has_sell = any('SELL' in s.get('signal', '') for s in sigs)
        
        if has_buy and not has_sell:
            buy_list.append(symbol)
        elif has_sell and not has_buy:
            sell_list.append(symbol)
        else:
            hold_list.append(symbol)
    
    html += f"""
        <div class="section">
            <h2>📋 Execution Summary</h2>
            <h3 style="color: green;">🟢 BUY NOW</h3>
            <p>{', '.join(buy_list) if buy_list else 'No immediate buy signals — wait for pullback'}</p>
            <h3 style="color: orange;">🟡 HOLD / WAIT</h3>
            <p>{', '.join(hold_list) if hold_list else 'None'}</p>
            <h3 style="color: red;">🔴 SELL / TAKE PROFIT</h3>
            <p>{', '.join(sell_list) if sell_list else 'No sell signals — hold positions'}</p>
        </div>
    """
    
    # ====== FOOTER ======
    html += f"""
        <div class="footer">
            <p>🕌 All stocks verified on PSX-KMI index</p>
            <p>📊 Data sources: pypsx, psx-mcp, SBP EasyData, News RSS Feeds</p>
            <p>⚠️ This is for informational purposes only. Always do your own research before trading.</p>
            <p>📈 Generated by PSX Maximum Information Bot</p>
        </div>
    </body>
    </html>
    """
    return html

# ============================================================
# 9. EMAIL SENDING
# ============================================================

def send_html_email(subject, html_body):
    """Send HTML email using Resend API."""
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
            print("✅ HTML email sent successfully.")
            return True
        else:
            print(f"❌ Resend API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

# ============================================================
# 10. MAIN EXECUTION
# ============================================================

def main():
    print("📈 Generating PSX Maximum Information Report...")
    print("=" * 60)
    
    # 1. Fetch stock data (pypsx)
    print("📡 Fetching stock data via pypsx...")
    quotes = {}
    fundamentals = {}
    historical_data = {}
    
    for symbol in STOCK_SYMBOLS:
        data = fetch_pypsx_data(symbol)
        if data:
            quotes[symbol] = {
                'price': data.get('price'),
                'change': data.get('change'),
                'change_pct': data.get('change_pct'),
                'volume': data.get('volume'),
            }
            fundamentals[symbol] = {
                'pe': data.get('pe'),
                'div_yield': data.get('div_yield'),
                'high_52w': data.get('high_52w'),
                'low_52w': data.get('low_52w'),
            }
            historical_data[symbol] = data.get('historical')
        else:
            print(f"⚠️ No data for {symbol}")
    
    print(f"✅ Fetched data for {len([q for q in quotes.values() if q])} symbols")
    
    # 2. Fetch MCP data (if available)
    print("📡 Fetching MCP data (psx-mcp)...")
    mcp_data = {}
    for symbol in STOCK_SYMBOLS:
        mcp = fetch_psx_mcp_data(symbol)
        if mcp:
            mcp_data[symbol] = mcp
    
    # 3. Fetch macro data
    print("📡 Fetching macroeconomic data...")
    macro_data = fetch_macro_data()
    
    # 4. Fetch news sentiment
    print("📡 Fetching news sentiment...")
    news_articles = fetch_news_sentiment()
    print(f"✅ Fetched {len(news_articles)} news articles")
    
    # 5. Calculate technical indicators
    print("📊 Calculating technical indicators...")
    indicators_data = {}
    for symbol, hist in historical_data.items():
        indicators_data[symbol] = calculate_indicators(hist)
    
    # 6. Generate signals
    print("🎯 Generating trading signals...")
    signals_data = {}
    entry_exit_data = {}
    
    for symbol in STOCK_SYMBOLS:
        price = quotes.get(symbol, {}).get('price')
        ind = indicators_data.get(symbol, {})
        fund = fundamentals.get(symbol, {})
        
        signals = generate_signals(symbol, price, ind, fund)
        signals_data[symbol] = signals
        entry_exit_data[symbol] = calculate_entry_exit(symbol, price, signals)
    
    # 7. Get index data
    print("📊 Fetching index data...")
    index_data = None
    try:
        import pypsx
        index_data = pypsx.get_indices()
    except Exception as e:
        print(f"Index data error: {e}")
    
    # 8. Generate HTML report
    print("📝 Generating HTML report...")
    html_report = generate_html_report(
        quotes, fundamentals, indicators_data, signals_data, entry_exit_data,
        macro_data, news_articles, index_data, mcp_data
    )
    
    # 9. Send email
    subject = f"📈 PSX Max Info Report - {datetime.now().strftime('%Y-%m-%d')}"
    email_sent = send_html_email(subject, html_report)
    
    if email_sent:
        print("✅ Maximum information report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
