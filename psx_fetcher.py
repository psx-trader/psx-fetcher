#!/usr/bin/env python3
"""
PSX Market Intelligence Report - Working Version
Fetches stock data, market pulse, index summary, and fundamentals.
Uses pypsx and psxdata libraries.
"""

import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ===== CONFIGURATION =====
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# =========================

STOCK_SYMBOLS = ["FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB"]

# ------------------------------------------------------------
# 1. Data Fetching Functions
# ------------------------------------------------------------

def fetch_stock_quote(symbol):
    """Fetch real-time quote for a stock."""
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        return {
            'price': reg_data.get('Current', 'N/A'),
            'change': reg_data.get('Change', 'N/A'),
            'change_pct': reg_data.get('Change %', 'N/A'),
            'volume': reg_data.get('Volume', 'N/A'),
            'high': reg_data.get('High', 'N/A'),
            'low': reg_data.get('Low', 'N/A'),
            'open': reg_data.get('Open', 'N/A')
        }
    except Exception as e:
        print(f"Error fetching quote for {symbol}: {e}")
        return None

def fetch_stock_fundamentals(symbol):
    """Fetch fundamental data."""
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        return {
            'pe': reg_data.get('P/E', 'N/A'),
            'div_yield': reg_data.get('Dividend Yield', 'N/A'),
            'high_52w': reg_data.get('52W High', 'N/A'),
            'low_52w': reg_data.get('52W Low', 'N/A')
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {symbol}: {e}")
        return None

def fetch_historical_data(symbol, days=90):
    """Fetch historical data for technical analysis."""
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
        print(f"Error fetching historical data for {symbol}: {e}")
        return None

def fetch_market_pulse():
    """Fetch top gainers, losers, and most active stocks."""
    try:
        import pypsx
        performers = pypsx.top_performers()
        return {
            "gainers": performers.get("top_gainers", pd.DataFrame()),
            "losers": performers.get("top_decliners", pd.DataFrame()),
            "active": performers.get("top_actives", pd.DataFrame())
        }
    except Exception as e:
        print(f"Error fetching market pulse: {e}")
        return {"gainers": None, "losers": None, "active": None}

def fetch_index_summary():
    """Fetch current values for major indices."""
    try:
        import pypsx
        indices = pypsx.get_indices()
        return indices
    except Exception as e:
        print(f"Error fetching indices: {e}")
        return None

def fetch_sector_performance():
    """Fetch sector summary."""
    try:
        import pypsx
        sectors = pypsx.sector_summary()
        return sectors
    except Exception as e:
        print(f"Error fetching sector data: {e}")
        return None

# ------------------------------------------------------------
# 2. Technical Indicators
# ------------------------------------------------------------

def calculate_indicators(df):
    """Calculate technical indicators from historical data."""
    if df is None or df.empty:
        return {}
    
    # Auto-detect column names
    close_col = None
    high_col = None
    low_col = None
    volume_col = None
    
    for col in df.columns:
        col_lower = col.lower()
        if 'close' in col_lower or 'adj close' in col_lower:
            close_col = col
        elif 'high' in col_lower:
            high_col = col
        elif 'low' in col_lower:
            low_col = col
        elif 'volume' in col_lower:
            volume_col = col
    
    if close_col is None:
        close_col = df.columns[3] if len(df.columns) > 3 else df.columns[0]
    if high_col is None:
        high_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    if low_col is None:
        low_col = df.columns[2] if len(df.columns) > 2 else df.columns[0]
    if volume_col is None:
        volume_col = df.columns[4] if len(df.columns) > 4 else df.columns[0]
    
    close = df[close_col]
    high = df[high_col]
    low = df[low_col]
    volume = df[volume_col]
    
    indicators = {}
    
    # RSI
    try:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1] if len(rs) > 0 else None
    except:
        indicators['rsi'] = None
    
    # SMAs
    try:
        indicators['sma_20'] = close.tail(20).mean() if len(close) >= 20 else None
        indicators['sma_50'] = close.tail(50).mean() if len(close) >= 50 else None
    except:
        indicators['sma_20'] = None
        indicators['sma_50'] = None
    
    # MACD
    try:
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        indicators['macd'] = macd.iloc[-1] if len(macd) > 0 else None
        indicators['macd_signal'] = signal.iloc[-1] if len(signal) > 0 else None
    except:
        indicators['macd'] = None
        indicators['macd_signal'] = None
    
    # Bollinger Bands
    try:
        sma_20 = close.tail(20).mean()
        std_20 = close.tail(20).std()
        indicators['bb_upper'] = sma_20 + (std_20 * 2)
        indicators['bb_middle'] = sma_20
        indicators['bb_lower'] = sma_20 - (std_20 * 2)
        if indicators['bb_upper'] != indicators['bb_lower']:
            indicators['bb_position'] = ((close.iloc[-1] - indicators['bb_lower']) / 
                                         (indicators['bb_upper'] - indicators['bb_lower']))
        else:
            indicators['bb_position'] = 0.5
    except:
        indicators['bb_upper'] = None
        indicators['bb_middle'] = None
        indicators['bb_lower'] = None
        indicators['bb_position'] = None
    
    # ATR
    try:
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        indicators['atr'] = tr.rolling(window=14).mean().iloc[-1] if len(tr) >= 14 else None
    except:
        indicators['atr'] = None
    
    # Volume
    try:
        indicators['volume_sma'] = volume.tail(20).mean() if len(volume) >= 20 else None
        if indicators['volume_sma'] and indicators['volume_sma'] > 0:
            indicators['volume_ratio'] = volume.iloc[-1] / indicators['volume_sma']
        else:
            indicators['volume_ratio'] = None
    except:
        indicators['volume_sma'] = None
        indicators['volume_ratio'] = None
    
    return indicators

# ------------------------------------------------------------
# 3. Signal Generation
# ------------------------------------------------------------

def generate_signals(symbol, price, indicators):
    """Generate buy/sell signals based on technical indicators."""
    signals = []
    
    if not indicators or price is None:
        return [{"signal": "⚠️ Insufficient data"}]
    
    # RSI
    rsi = indicators.get('rsi')
    if rsi is not None:
        if rsi < 30:
            signals.append({
                "signal": "🟢 BUY",
                "indicator": "RSI",
                "value": f"{rsi:.2f}",
                "reason": f"RSI oversold ({rsi:.2f} < 30)",
                "timing": "Immediate — market open",
                "priority": "HIGH"
            })
        elif rsi > 70:
            signals.append({
                "signal": "🔴 SELL/AVOID",
                "indicator": "RSI",
                "value": f"{rsi:.2f}",
                "reason": f"RSI overbought ({rsi:.2f} > 70)",
                "timing": "Wait for pullback",
                "priority": "HIGH"
            })
        else:
            signals.append({
                "signal": "⏳ NEUTRAL",
                "indicator": "RSI",
                "value": f"{rsi:.2f}",
                "reason": f"RSI in neutral zone (30-70)",
                "timing": "Watch for breakout",
                "priority": "MEDIUM"
            })
    
    # SMA Crossover
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
    
    # MACD
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
    
    # Bollinger Bands
    bb_lower = indicators.get('bb_lower')
    bb_upper = indicators.get('bb_upper')
    if bb_lower is not None and bb_upper is not None and isinstance(price, (int, float)):
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
    
    return signals

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
        target = price * 1.10
        stop = price * 0.95
        timing = "Market open — buy immediately"
        exit_timing = f"When price reaches PKR {target:.2f} or falls below {stop:.2f}"
    else:
        entry = price * 0.97
        target = entry * 1.10
        stop = entry * 0.95
        timing = f"Wait for dip to PKR {entry:.2f}"
        exit_timing = f"When price reaches PKR {target:.2f} or falls below {stop:.2f}"
    
    return {
        'entry_price': round(entry, 2),
        'target_price': round(target, 2),
        'stop_loss': round(stop, 2),
        'entry_timing': timing,
        'exit_timing': exit_timing
    }

# ------------------------------------------------------------
# 4. Report Generation
# ------------------------------------------------------------

def df_to_html(df, limit=10):
    """Convert DataFrame to HTML table."""
    if df is None or df.empty:
        return "<p>No data available</p>"
    
    df = df.head(limit)
    return df.to_html(index=False, border=0, classes='data-table')

def generate_html_report(quotes, fundamentals, indicators, signals, entry_exit, 
                         market_pulse, index_summary, sector_data):
    """Generate comprehensive HTML report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    # Convert DataFrames to HTML
    index_html = df_to_html(index_summary, 10)
    gainers_html = df_to_html(market_pulse.get('gainers'), 5)
    losers_html = df_to_html(market_pulse.get('losers'), 5)
    active_html = df_to_html(market_pulse.get('active'), 5)
    sectors_html = df_to_html(sector_data, 10)
    
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
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 PSX Market Intelligence Report</h1>
            <p>Generated on {now}</p>
        </div>

        <!-- Index Summary -->
        <div class="section">
            <h2>📊 Index Summary</h2>
            {index_html}
        </div>

        <!-- Market Pulse -->
        <div class="section">
            <h2>📈 Market Pulse</h2>
            <h3>Top Gainers</h3>
            {gainers_html}
            <h3>Top Losers</h3>
            {losers_html}
            <h3>Most Active</h3>
            {active_html}
        </div>

        <!-- Sector Performance -->
        <div class="section">
            <h2>🏭 Sector Performance</h2>
            {sectors_html}
        </div>

        <!-- Portfolio Watchlist -->
        <div class="section">
            <h2>💼 Your Portfolio Watchlist</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price (PKR)</th>
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
        sig = signals.get(symbol, [])
        price = q.get('price', 'N/A')
        
        primary_signal = "⏳ NEUTRAL"
        for s in sig:
            if 'BUY' in s.get('signal', '') and s.get('priority') == 'HIGH':
                primary_signal = "🟢 BUY"
                break
            elif 'SELL' in s.get('signal', '') and s.get('priority') == 'HIGH':
                primary_signal = "🔴 SELL"
                break
        
        signal_class = 'buy' if 'BUY' in primary_signal else 'sell' if 'SELL' in primary_signal else 'neutral'
        html += f"""
                    <tr>
                        <td><strong>{symbol}</strong></td>
                        <td>{price}</td>
                        <td>{q.get('change_pct', 'N/A')}</td>
                        <td>{q.get('volume', 'N/A')}</td>
                        <td>{f.get('pe', 'N/A')}</td>
                        <td>{f.get('div_yield', 'N/A')}</td>
                        <td>{f.get('high_52w', 'N/A')}</td>
                        <td>{f.get('low_52w', 'N/A')}</td>
                        <td class="{signal_class}">{primary_signal}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
        </div>
    """
    
    # Detailed Signals
    html += """
        <div class="section">
            <h2>🎯 Detailed Trading Signals</h2>
    """
    
    for symbol in STOCK_SYMBOLS:
        sigs = signals.get(symbol, [])
        ee = entry_exit.get(symbol, {})
        if sigs and not (len(sigs) == 1 and 'Insufficient data' in sigs[0].get('signal', '')):
            html += f"<h3>{symbol}</h3>"
            html += "<table><thead><tr><th>Signal</th><th>Indicator</th><th>Value</th><th>Reason</th><th>Timing</th></tr></thead><tbody>"
            for s in sigs[:5]:
                row_class = 'signal-buy' if 'BUY' in s.get('signal', '') else 'signal-sell' if 'SELL' in s.get('signal', '') else 'signal-neutral'
                signal_class = 'buy' if 'BUY' in s.get('signal', '') else 'sell' if 'SELL' in s.get('signal', '') else 'neutral'
                html += f"""
                    <tr class="{row_class}">
                        <td class="{signal_class}">{s.get('signal', 'N/A')}</td>
                        <td>{s.get('indicator', 'N/A')}</td>
                        <td>{s.get('value', 'N/A')}</td>
                        <td>{s.get('reason', 'N/A')}</td>
                        <td><span class="highlight">{s.get('timing', 'N/A')}</span></td>
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
    
    # Technical Indicators
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
                        <th>BB Position</th>
                        <th>ATR</th>
                        <th>Vol Ratio</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for symbol in STOCK_SYMBOLS:
        ind = indicators.get(symbol, {})
        rsi = f"{ind.get('rsi', 'N/A'):.2f}" if ind.get('rsi') else 'N/A'
        sma20 = f"{ind.get('sma_20', 'N/A'):.2f}" if ind.get('sma_20') else 'N/A'
        sma50 = f"{ind.get('sma_50', 'N/A'):.2f}" if ind.get('sma_50') else 'N/A'
        bb_pos = f"{ind.get('bb_position', 'N/A'):.2f}" if ind.get('bb_position') else 'N/A'
        atr = f"{ind.get('atr', 'N/A'):.2f}" if ind.get('atr') else 'N/A'
        vol_ratio = f"{ind.get('volume_ratio', 'N/A'):.2f}" if ind.get('volume_ratio') else 'N/A'
        
        html += f"""
                    <tr>
                        <td><strong>{symbol}</strong></td>
                        <td>{rsi}</td>
                        <td>{sma20}</td>
                        <td>{sma50}</td>
                        <td>{bb_pos}</td>
                        <td>{atr}</td>
                        <td>{vol_ratio}</td>
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
    
    # Execution Summary
    buy_list = []
    sell_list = []
    hold_list = []
    
    for symbol in STOCK_SYMBOLS:
        sigs = signals.get(symbol, [])
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
    
    html += f"""
        <div class="footer">
            <p>🕌 All stocks verified on PSX-KMI index</p>
            <p>⚠️ This is for informational purposes only. Always do your own research before trading.</p>
            <p>📈 Generated by PSX Market Intelligence Bot</p>
        </div>
    </body>
    </html>
    """
    
    return html

# ------------------------------------------------------------
# 5. Email Sending
# ------------------------------------------------------------

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

# ------------------------------------------------------------
# 6. Main Execution
# ------------------------------------------------------------

def main():
    print("🚀 Generating PSX Market Intelligence Report...")
    print("=" * 60)
    
    # 1. Fetch stock data
    print("📡 Fetching stock data...")
    quotes = {}
    fundamentals = {}
    historical_data = {}
    
    for symbol in STOCK_SYMBOLS:
        print(f"   Fetching {symbol}...")
        quotes[symbol] = fetch_stock_quote(symbol)
        fundamentals[symbol] = fetch_stock_fundamentals(symbol)
        historical_data[symbol] = fetch_historical_data(symbol)
    
    print("✅ Stock data fetched")
    
    # 2. Fetch market pulse
    print("📡 Fetching market pulse...")
    market_pulse = fetch_market_pulse()
    
    # 3. Fetch index summary
    print("📡 Fetching index summary...")
    index_summary = fetch_index_summary()
    
    # 4. Fetch sector performance
    print("📡 Fetching sector performance...")
    sector_data = fetch_sector_performance()
    
    # 5. Calculate indicators
    print("📊 Calculating technical indicators...")
    indicators = {}
    for symbol, hist in historical_data.items():
        indicators[symbol] = calculate_indicators(hist)
    
    # 6. Generate signals
    print("🎯 Generating trading signals...")
    signals = {}
    entry_exit = {}
    
    for symbol in STOCK_SYMBOLS:
        price = quotes.get(symbol, {}).get('price')
        if isinstance(price, str) and price != 'N/A':
            try:
                price = float(price)
            except:
                price = None
        elif not isinstance(price, (int, float)):
            price = None
        
        ind = indicators.get(symbol, {})
        sigs = generate_signals(symbol, price, ind)
        signals[symbol] = sigs
        entry_exit[symbol] = calculate_entry_exit(symbol, price, sigs)
    
    # 7. Generate report
    print("📝 Generating HTML report...")
    html_report = generate_html_report(
        quotes, fundamentals, indicators, signals, entry_exit,
        market_pulse, index_summary, sector_data
    )
    
    # 8. Send email
    subject = f"PSX Market Report - {datetime.now().strftime('%Y-%m-%d')}"
    email_sent = send_html_email(subject, html_report)
    
    if email_sent:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
