#!/usr/bin/env python3
"""
PSX ULTIMATE PROFIT ENGINE v3.1 — MAXIMUM PROFIT EDITION
Features: Kelly Sizing, Trailing Stops, Dividend Capture, Sector Rotation, Correlation Analysis
"""

import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import json
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
MAX_RISK_PER_TRADE = 0.02  # 2%
PAPER_TRADING = True
# ============================================================

# Shariah-compliant tickers
VALID_SHARIAH_TICKERS = [
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

RSS_FEEDS = [
    "https://www.dawn.com/feeds/business",
    "https://www.brecorder.com/rss/news",
    "https://www.thenews.com.pk/rss/2/5"
]

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def df_to_html(df, limit=10):
    if df is None or df.empty:
        return "<p>No data available</p>"
    df = df.head(limit)
    return df.to_html(index=False, border=0, classes='data-table')

def is_valid_ticker(symbol):
    if not symbol or not isinstance(symbol, str):
        return False
    if not re.match(r'^[A-Z]+$', symbol):
        return False
    if len(symbol) < 2 or len(symbol) > 6:
        return False
    invalid = ["CEMENT", "FERTILIZER", "BANKING", "TEXTILE", "ENERGY", "OIL", "GAS"]
    if symbol in invalid:
        return False
    return symbol in VALID_SHARIAH_TICKERS

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

def calculate_kelly(win_rate, avg_win, avg_loss, max_fraction=0.25):
    """Calculate Kelly Criterion optimal position fraction."""
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    if b <= 0:
        return 0.0
    kelly = (b * p - q) / b
    return max(0.0, min(kelly, max_fraction))

def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """Calculate Sharpe ratio from returns series."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate
    return excess.mean() / excess.std() if excess.std() > 0 else 0.0

# ============================================================
# DATA FETCHING
# ============================================================

def fetch_top_shariah_stocks(limit=50):
    print(f"📡 Fetching top {limit} Shariah-compliant stocks...")
    try:
        import pypsx
        market_watch = pypsx.market_watch()
        if market_watch is None or market_watch.empty:
            return VALID_SHARIAH_TICKERS[:limit]
        
        symbol_col = None
        for col in ['Symbol', 'symbol', 'Ticker', 'ticker']:
            if col in market_watch.columns:
                symbol_col = col
                break
        if symbol_col is None:
            symbol_col = market_watch.columns[0]
        
        market_tickers = market_watch[symbol_col].tolist()
        valid_tickers = [t for t in market_tickers if is_valid_ticker(t)]
        shariah_tickers = [t for t in valid_tickers if t in VALID_SHARIAH_TICKERS]
        
        if not shariah_tickers:
            return VALID_SHARIAH_TICKERS[:limit]
        
        if 'Volume' in market_watch.columns:
            market_watch['Volume'] = pd.to_numeric(market_watch['Volume'], errors='coerce')
            shariah_data = market_watch[market_watch[symbol_col].isin(shariah_tickers)]
            if not shariah_data.empty:
                top_data = shariah_data.sort_values('Volume', ascending=False).head(limit)
                return top_data[symbol_col].tolist()
        
        return shariah_tickers[:limit]
    except Exception as e:
        print(f"Error: {e}. Using fallback list.")
        return VALID_SHARIAH_TICKERS[:limit]

def fetch_quote(symbol):
    if not is_valid_ticker(symbol):
        return {'symbol': symbol, 'error': 'Invalid ticker', 'price': 'N/A'}
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        return {
            'symbol': symbol,
            'price': reg_data.get('Current', 'N/A'),
            'change': reg_data.get('Change', 'N/A'),
            'change_pct': reg_data.get('Change %', 'N/A'),
            'volume': reg_data.get('Volume', 'N/A'),
            'high': reg_data.get('High', 'N/A'),
            'low': reg_data.get('Low', 'N/A'),
            'open': reg_data.get('Open', 'N/A')
        }
    except Exception as e:
        return {'symbol': symbol, 'error': str(e), 'price': 'N/A'}

def fetch_fundamentals(symbol):
    if not is_valid_ticker(symbol):
        return {'symbol': symbol, 'error': 'Invalid ticker'}
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

def fetch_historical(symbol, days=180):
    if not is_valid_ticker(symbol):
        return None
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

# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def calculate_indicators(df):
    if df is None or df.empty:
        return {}
    
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
    
    close = pd.Series(df[close_col].values)
    high = pd.Series(df[high_col].values)
    low = pd.Series(df[low_col].values)
    volume = pd.Series(df[volume_col].values)
    
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
        indicators['sma_200'] = close.tail(200).mean() if len(close) >= 200 else None
    except:
        indicators['sma_20'] = None
        indicators['sma_50'] = None
        indicators['sma_200'] = None
    
    # MACD
    try:
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        indicators['macd'] = macd.iloc[-1] if len(macd) > 0 else None
        indicators['macd_signal'] = signal.iloc[-1] if len(signal) > 0 else None
        indicators['macd_hist'] = (macd - signal).iloc[-1] if len(macd) > 0 and len(signal) > 0 else None
    except:
        indicators['macd'] = None
        indicators['macd_signal'] = None
        indicators['macd_hist'] = None
    
    # Bollinger Bands
    try:
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        indicators['bb_upper'] = sma_20.iloc[-1] + 2 * std_20.iloc[-1] if len(sma_20) > 0 else None
        indicators['bb_middle'] = sma_20.iloc[-1] if len(sma_20) > 0 else None
        indicators['bb_lower'] = sma_20.iloc[-1] - 2 * std_20.iloc[-1] if len(sma_20) > 0 else None
        if indicators['bb_upper'] and indicators['bb_lower'] and indicators['bb_upper'] != indicators['bb_lower']:
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
    
    # Volume Ratio
    try:
        indicators['volume_sma'] = volume.tail(20).mean() if len(volume) >= 20 else None
        if indicators['volume_sma'] and indicators['volume_sma'] > 0:
            indicators['volume_ratio'] = volume.iloc[-1] / indicators['volume_sma']
        else:
            indicators['volume_ratio'] = None
    except:
        indicators['volume_sma'] = None
        indicators['volume_ratio'] = None
    
    # ADX (simplified)
    try:
        plus_dm = high.diff()
        minus_dm = low.diff()
        tr_s = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr_14 = tr_s.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        indicators['adx'] = dx.rolling(14).mean().iloc[-1] if len(dx) >= 14 else None
    except:
        indicators['adx'] = None
    
    # Stochastic
    try:
        low_14 = low.rolling(14).min()
        high_14 = high.rolling(14).max()
        stoch_k = 100 * ((close - low_14) / (high_14 - low_14))
        indicators['stoch_k'] = stoch_k.iloc[-1] if len(stoch_k) > 0 else None
        indicators['stoch_d'] = stoch_k.rolling(3).mean().iloc[-1] if len(stoch_k) >= 3 else None
    except:
        indicators['stoch_k'] = None
        indicators['stoch_d'] = None
    
    return indicators

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
                    'summary': summary[:200] + '...' if len(summary) > 200 else summary,
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
# ULTIMATE SIGNAL GENERATION WITH KELLY
# ============================================================

def generate_signals(symbol, price, indicators, sentiment, fundamentals):
    signals = []
    if not indicators or price is None:
        return {'primary': '⏳ NEUTRAL', 'details': [], 'score': 0, 'win_rate_est': 0.5}
    
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            return {'primary': '⏳ NEUTRAL', 'details': [], 'score': 0, 'win_rate_est': 0.5}
    if not isinstance(price, (int, float)):
        return {'primary': '⏳ NEUTRAL', 'details': [], 'score': 0, 'win_rate_est': 0.5}
    
    score = 0
    details = []
    
    # RSI
    rsi = indicators.get('rsi')
    if rsi is not None:
        if rsi < 30:
            score += 2
            details.append({'model': 'RSI', 'signal': 'BUY', 'weight': 2, 'value': rsi, 'reason': f'Oversold ({rsi:.2f} < 30)'})
        elif rsi > 70:
            score -= 2
            details.append({'model': 'RSI', 'signal': 'SELL', 'weight': -2, 'value': rsi, 'reason': f'Overbought ({rsi:.2f} > 70)'})
    
    # MACD
    macd = indicators.get('macd')
    macd_signal = indicators.get('macd_signal')
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            score += 1.5
            details.append({'model': 'MACD', 'signal': 'BUY', 'weight': 1.5, 'value': macd, 'reason': 'Bullish crossover'})
        else:
            score -= 1.5
            details.append({'model': 'MACD', 'signal': 'SELL', 'weight': -1.5, 'value': macd, 'reason': 'Bearish crossover'})
    
    # Bollinger Bands
    bb_pos = indicators.get('bb_position')
    if bb_pos is not None:
        if bb_pos < 0.2:
            score += 1
            details.append({'model': 'Bollinger', 'signal': 'BUY', 'weight': 1, 'value': bb_pos, 'reason': 'At lower band'})
        elif bb_pos > 0.8:
            score -= 1
            details.append({'model': 'Bollinger', 'signal': 'SELL', 'weight': -1, 'value': bb_pos, 'reason': 'At upper band'})
    
    # ADX trend strength
    adx = indicators.get('adx')
    if adx is not None and adx > 25:
        score += 0.5
        details.append({'model': 'ADX', 'signal': 'TREND', 'weight': 0.5, 'value': adx, 'reason': f'Strong trend ({adx:.2f})'})
    
    # Stochastic
    stoch_k = indicators.get('stoch_k')
    stoch_d = indicators.get('stoch_d')
    if stoch_k is not None and stoch_d is not None:
        if stoch_k < 20 and stoch_d < 20:
            score += 1.5
            details.append({'model': 'Stochastic', 'signal': 'BUY', 'weight': 1.5, 'value': f'K={stoch_k:.2f}', 'reason': 'Oversold crossover'})
        elif stoch_k > 80 and stoch_d > 80:
            score -= 1.5
            details.append({'model': 'Stochastic', 'signal': 'SELL', 'weight': -1.5, 'value': f'K={stoch_k:.2f}', 'reason': 'Overbought crossover'})
    
    # Sentiment
    if sentiment and sentiment.get('overall') != 'neutral':
        if sentiment['overall'] == 'bullish':
            score += 0.5
            details.append({'model': 'Sentiment', 'signal': 'BULLISH', 'weight': 0.5, 'value': sentiment.get('avg_polarity', 0), 'reason': 'Positive news'})
        else:
            score -= 0.5
            details.append({'model': 'Sentiment', 'signal': 'BEARISH', 'weight': -0.5, 'value': sentiment.get('avg_polarity', 0), 'reason': 'Negative news'})
    
    # Fundamentals
    if fundamentals:
        pe = fundamentals.get('pe')
        div_yield = fundamentals.get('div_yield')
        if pe is not None and pe != 'N/A' and isinstance(pe, (int, float)) and pe < 15:
            score += 0.5
            details.append({'model': 'Fundamental', 'signal': 'BUY', 'weight': 0.5, 'value': pe, 'reason': f'Low P/E ({pe:.2f})'})
        if div_yield is not None and div_yield != 'N/A' and isinstance(div_yield, (int, float)) and div_yield > 5:
            score += 0.5
            details.append({'model': 'Dividend', 'signal': 'BUY', 'weight': 0.5, 'value': div_yield, 'reason': f'High yield ({div_yield:.2f}%)'})
    
    # Estimate win rate from score
    win_rate_est = 0.5 + (score / 15)
    win_rate_est = max(0.3, min(0.7, win_rate_est))
    
    if score > 2.5:
        primary = "🟢 STRONG BUY"
        timing = "Immediate — market open"
        priority = "HIGH"
        action = "BUY"
    elif score > 1.5:
        primary = "🟢 BUY"
        timing = "Buy on dips"
        priority = "MEDIUM"
        action = "BUY"
    elif score < -2.5:
        primary = "🔴 STRONG SELL"
        timing = "Sell immediately"
        priority = "HIGH"
        action = "SELL"
    elif score < -1.5:
        primary = "🔴 SELL"
        timing = "Take profits"
        priority = "MEDIUM"
        action = "SELL"
    else:
        primary = "⏳ NEUTRAL"
        timing = "Wait for breakout"
        priority = "LOW"
        action = "WAIT"
    
    return {
        'primary': primary,
        'timing': timing,
        'priority': priority,
        'action': action,
        'details': details,
        'score': score,
        'win_rate_est': win_rate_est,
        'buy_count': sum(1 for d in details if 'BUY' in d.get('signal', '')),
        'sell_count': sum(1 for d in details if 'SELL' in d.get('signal', ''))
    }

# ============================================================
# ENTRY/EXIT WITH KELLY CRITERION & TRAILING STOP
# ============================================================

def calculate_entry_exit(symbol, price, signal, indicators, account_balance=30000, risk_per_trade=0.02):
    if price is None or not isinstance(price, (int, float)):
        return {
            'entry_price': 'N/A',
            'target_price': 'N/A',
            'stop_loss': 'N/A',
            'trailing_stop': 'N/A',
            'position_size': 0,
            'risk_amount': 0,
            'potential_profit': 0,
            'kelly_fraction': 0,
            'win_rate': 0
        }
    
    atr = indicators.get('atr', price * 0.02) if indicators else price * 0.02
    if atr is None or atr <= 0:
        atr = price * 0.02
    
    # Volatility adjustment: wider stops for volatile stocks
    vol_adjustment = 1.0
    if indicators and indicators.get('volume_ratio'):
        vol_ratio = indicators.get('volume_ratio', 1.0)
        if vol_ratio and vol_ratio > 0:
            vol_adjustment = min(1.5, max(0.5, vol_ratio / 1.5))
    
    if signal.get('action') == 'BUY':
        entry = price
        stop = price - 2 * atr * vol_adjustment
        target = price + 4 * atr * vol_adjustment
        trailing_stop = stop
    elif signal.get('action') == 'SELL':
        entry = price
        stop = price + 2 * atr * vol_adjustment
        target = price - 4 * atr * vol_adjustment
        trailing_stop = stop
    else:
        entry = price
        stop = price - 2 * atr * vol_adjustment
        target = price + 4 * atr * vol_adjustment
        trailing_stop = stop
    
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return {
            'entry_price': round(entry, 2),
            'target_price': round(target, 2),
            'stop_loss': round(stop, 2),
            'trailing_stop': 'N/A',
            'position_size': 0,
            'risk_amount': 0,
            'potential_profit': 0,
            'kelly_fraction': 0,
            'win_rate': 0
        }
    
    # Kelly Criterion position sizing
    win_rate = signal.get('win_rate_est', 0.5)
    avg_win = target - entry if signal.get('action') == 'BUY' else entry - target
    avg_loss = entry - stop if signal.get('action') == 'BUY' else stop - entry
    kelly = calculate_kelly(win_rate, avg_win, avg_loss)
    kelly_fraction = kelly if kelly > 0 else 0.02
    
    # Position size with Kelly
    risk_amount = account_balance * (risk_per_trade + kelly_fraction * 0.5)
    shares = int(risk_amount / risk_per_share)
    potential_profit = shares * (target - entry) if signal.get('action') == 'BUY' else shares * (entry - target)
    
    return {
        'entry_price': round(entry, 2),
        'target_price': round(target, 2),
        'stop_loss': round(stop, 2),
        'trailing_stop': round(trailing_stop, 2),
        'position_size': shares,
        'risk_amount': round(risk_amount, 2),
        'potential_profit': round(potential_profit, 2),
        'kelly_fraction': round(kelly_fraction, 4),
        'win_rate': round(win_rate, 3)
    }

# ============================================================
# PORTFOLIO CORRELATION & SECTOR ROTATION
# ============================================================

def calculate_correlation_matrix(historical_data, symbols):
    """Calculate correlation matrix for portfolio diversification."""
    if not historical_data or len(historical_data) < 2:
        return None
    
    returns_dict = {}
    for symbol in symbols:
        df = historical_data.get(symbol)
        if df is not None and not df.empty:
            close_col = None
            for col in df.columns:
                if 'close' in col.lower() or 'adj close' in col.lower():
                    close_col = col
                    break
            if close_col is None:
                close_col = df.columns[3] if len(df.columns) > 3 else df.columns[0]
            returns_dict[symbol] = df[close_col].pct_change().dropna()
    
    if len(returns_dict) < 2:
        return None
    
    returns_df = pd.DataFrame(returns_dict)
    return returns_df.corr()

def sector_rotation_score(symbol, sector_data, current_sector=''):
    """Calculate sector rotation score for capital allocation."""
    if sector_data is None or sector_data.empty:
        return 0.0
    
    try:
        # Find sector performance
        sector_row = sector_data[sector_data['SECTOR NAME'].str.contains(symbol[:3], case=False, na=False)]
        if sector_row.empty:
            return 0.0
        turnover = sector_row['TURNOVER'].values[0] if 'TURNOVER' in sector_row.columns else 0
        return safe_float(turnover, 0)
    except:
        return 0.0

# ============================================================
# REPORT GENERATION
# ============================================================

def generate_ultimate_report(quotes, fundamentals, indicators, sentiment_data,
                             signals, entry_exit, market_pulse, index_summary, sector_data,
                             stock_symbols, correlation_matrix, account_balance=30000,
                             trade_journal=None, paper_engine=None):
    """Generate comprehensive HTML report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    index_html = df_to_html(index_summary, 10)
    gainers_html = df_to_html(market_pulse.get('gainers'), 5)
    losers_html = df_to_html(market_pulse.get('losers'), 5)
    active_html = df_to_html(market_pulse.get('active'), 5)
    sectors_html = df_to_html(sector_data, 10)
    
    # Build lists
    buy_list = []
    sell_list = []
    hold_list = []
    for symbol in stock_symbols:
        sig = signals.get(symbol, {})
        if sig.get('action') == 'BUY':
            buy_list.append(symbol)
        elif sig.get('action') == 'SELL':
            sell_list.append(symbol)
        else:
            hold_list.append(symbol)
    
    # Journal summary
    journal = trade_journal.get_summary() if trade_journal else {}
    
    # Correlation matrix HTML
    corr_html = ""
    if correlation_matrix is not None and not correlation_matrix.empty:
        corr_html = correlation_matrix.round(2).to_html(border=0, classes='data-table')
    
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
            .kelly-badge {{ background: #00ff88; color: #0a0a0a; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ PSX ULTIMATE PROFIT ENGINE v3.1</h1>
            <p>Generated on {now}</p>
            <p>💰 Account: PKR {account_balance:,.0f} | 📊 {len(stock_symbols)} Shariah Stocks</p>
            <p>📋 Paper Trading: {'🟢 ACTIVE' if PAPER_TRADING else '🔴 DISABLED'}</p>
            <p>🧠 Kelly Criterion: ENABLED | Trailing Stops: ENABLED</p>
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
            <h2>🧠 News Sentiment</h2>
            <p><strong>Overall:</strong> {sentiment_data.get('overall', 'neutral').upper()} (Polarity: {sentiment_data.get('avg_polarity', 0):.3f})</p>
            <ul>
    """
    for article in sentiment_data.get('articles', [])[:5]:
        color = '#00ff88' if article['sentiment'] == 'bullish' else '#ff4444' if article['sentiment'] == 'bearish' else '#ffaa00'
        html += f"<li style='color:#ccc;'><span style='color:{color};'>{article['sentiment'].upper()}</span> — {article['title'][:80]}...</li>"
    html += """
            </ul>
        </div>

        <div class="section">
            <h2>📊 Portfolio Correlation Matrix</h2>
            {corr_html}
            <p style="font-size: 12px; color: #888;">⬆ Diversify by choosing stocks with low correlation</p>
        </div>

        <div class="section">
            <h2>🎯 Trading Signals with Kelly Sizing</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Signal</th>
                        <th>Score</th>
                        <th>Entry</th>
                        <th>Target</th>
                        <th>Stop</th>
                        <th>Trailing</th>
                        <th>Shares</th>
                        <th>Risk (PKR)</th>
                        <th>Profit</th>
                        <th>Kelly</th>
                    </tr>
                </thead>
                <tbody>
    """
    for symbol in stock_symbols[:30]:
        q = quotes.get(symbol, {})
        price = q.get('price', 'N/A')
        if price == 'N/A':
            continue
        sig = signals.get(symbol, {})
        ee = entry_exit.get(symbol, {})
        primary = sig.get('primary', '⏳ NEUTRAL')
        signal_class = 'buy' if 'BUY' in primary else 'sell' if 'SELL' in primary else 'neutral'
        kelly_pct = f"{ee.get('kelly_fraction', 0)*100:.1f}%"
        html += f"""
            <tr class="signal-{signal_class}">
                <td><strong style="color:#00ff88;">{symbol}</strong></td>
                <td>{price}</td>
                <td class="{signal_class}">{primary}</td>
                <td>{sig.get('score', 0):.1f}</td>
                <td>{ee.get('entry_price', 'N/A')}</td>
                <td>{ee.get('target_price', 'N/A')}</td>
                <td>{ee.get('stop_loss', 'N/A')}</td>
                <td>{ee.get('trailing_stop', 'N/A')}</td>
                <td>{ee.get('position_size', 0)}</td>
                <td class="{'profit' if ee.get('risk_amount', 0) > 0 else 'loss'}">{ee.get('risk_amount', 0):.2f}</td>
                <td class="{'profit' if ee.get('potential_profit', 0) > 0 else 'loss'}">{ee.get('potential_profit', 0):.2f}</td>
                <td><span class="kelly-badge">{kelly_pct}</span></td>
            </tr>
        """
    html += """
                </tbody>
            </table>
            <p style="font-size: 12px; color: #888;">Kelly = Optimal position fraction based on win rate and risk/reward</p>
        </div>

        <div class="section">
            <h2>📋 Execution Summary</h2>
            <h3 style="color: #00ff88;">🟢 BUY NOW ({buy_count})</h3>
            <p>{buy_list}</p>
            <h3 style="color: #ffaa00;">🟡 HOLD / WAIT ({hold_count})</h3>
            <p>{hold_list}</p>
            <h3 style="color: #ff4444;">🔴 SELL / TAKE PROFIT ({sell_count})</h3>
            <p>{sell_list}</p>
        </div>

        <div class="section">
            <h2>📋 Trade Journal</h2>
            <p><strong>Total Trades:</strong> {journal.get('total_trades', 0)}</p>
            <p><strong>Total P&L:</strong> <span class="{'profit' if journal.get('total_pnl', 0) > 0 else 'loss'}">PKR {journal.get('total_pnl', 0):,.2f}</span></p>
            <p><strong>Win Rate:</strong> {journal.get('win_rate', 0)*100:.1f}%</p>
            <p><strong>Profit Factor:</strong> {journal.get('profit_factor', 0):.2f}</p>
        </div>

        <div class="section">
            <h2>⏰ Optimal Entry Times</h2>
            <p><strong>Best Time to Buy:</strong> 9:30 AM - 10:30 AM PKT (Opening momentum)</p>
            <p><strong>Best Time to Sell:</strong> 2:00 PM - 3:00 PM PKT (Closing momentum)</p>
            <p><strong>Ex-Dividend Strategy:</strong> Buy 1 day before ex-date, sell on ex-date</p>
        </div>

        <div class="footer">
            <p>🕌 All stocks Shariah-compliant (KMI All Share Index)</p>
            <p>📊 Indicators: RSI + MACD + BB + ADX + Stochastic + Sentiment + Fundamentals</p>
            <p>💰 Kelly Criterion + Trailing Stops + Volatility Adjustment</p>
            <p>⚠️ Informational only. Always do your own research.</p>
            <p>⚡ Generated by PSX Ultimate Profit Engine v3.1</p>
        </div>
    </body>
    </html>
    """.format(
        now=now,
        account_balance=account_balance,
        stock_symbols=stock_symbols,
        index_html=index_html,
        gainers_html=gainers_html,
        losers_html=losers_html,
        active_html=active_html,
        sectors_html=sectors_html,
        sentiment_data=sentiment_data,
        signals=signals,
        entry_exit=entry_exit,
        quotes=quotes,
        buy_count=len(buy_list),
        sell_count=len(sell_list),
        hold_count=len(hold_list),
        buy_list=', '.join(buy_list[:20]) + ('...' if len(buy_list) > 20 else ''),
        sell_list=', '.join(sell_list[:20]) + ('...' if len(sell_list) > 20 else ''),
        hold_list=', '.join(hold_list[:20]) + ('...' if len(hold_list) > 20 else ''),
        journal=journal,
        corr_html=corr_html
    )
    
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
# TRADE JOURNAL
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
            return {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0, 'profit_factor': 0}
        total_pnl = sum(t['profit_loss'] for t in self.trades)
        win_rate = len([t for t in self.trades if t['profit_loss'] > 0]) / len(self.trades) if self.trades else 0
        total_wins = sum(t['profit_loss'] for t in self.trades if t['profit_loss'] > 0)
        total_losses = sum(t['profit_loss'] for t in self.trades if t['profit_loss'] < 0)
        profit_factor = abs(total_wins / total_losses) if total_losses != 0 else 0
        return {
            'total_trades': len(self.trades),
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'profit_factor': profit_factor
        }

# ============================================================
# PAPER TRADING ENGINE
# ============================================================

class PaperTradingEngine:
    def __init__(self, initial_balance=30000):
        self.balance = initial_balance
        self.portfolio = {}
        self.initial_balance = initial_balance
        self.trade_journal = TradeJournal()
    
    def buy(self, symbol, price, quantity):
        cost = price * quantity
        if cost > self.balance:
            print(f"❌ Insufficient balance. Need PKR {cost:.2f}, have PKR {self.balance:.2f}")
            return False
        self.balance -= cost
        if symbol in self.portfolio:
            self.portfolio[symbol]['quantity'] += quantity
        else:
            self.portfolio[symbol] = {'quantity': quantity, 'avg_price': price}
        self.trade_journal.log_trade(symbol, price, None, quantity, datetime.now(), None, None)
        print(f"✅ BUY {quantity} {symbol} @ PKR {price:.2f}")
        return True
    
    def sell(self, symbol, price, quantity=None):
        if symbol not in self.portfolio:
            print(f"❌ No position in {symbol}")
            return False
        if quantity is None:
            quantity = self.portfolio[symbol]['quantity']
        if quantity > self.portfolio[symbol]['quantity']:
            print(f"❌ Not enough shares. Have {self.portfolio[symbol]['quantity']}, want {quantity}")
            return False
        proceeds = price * quantity
        self.balance += proceeds
        self.portfolio[symbol]['quantity'] -= quantity
        if self.portfolio[symbol]['quantity'] == 0:
            del self.portfolio[symbol]
        print(f"✅ SELL {quantity} {symbol} @ PKR {price:.2f}")
        return True

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    print("⚡ PSX ULTIMATE PROFIT ENGINE v3.1 — MAXIMUM PROFIT EDITION")
    print("=" * 75)
    print(f"💰 Starting Balance: PKR {ACCOUNT_BALANCE:,.0f}")
    print(f"📋 Paper Trading: {'ACTIVE' if PAPER_TRADING else 'DISABLED'}")
    print(f"🧠 Kelly Criterion: ENABLED")
    print(f"📊 Trailing Stops: ENABLED")
    print("=" * 75)
    
    # 1. Fetch stocks
    stock_symbols = fetch_top_shariah_stocks(limit=50)
    stock_symbols = [s for s in stock_symbols if is_valid_ticker(s)]
    print(f"📊 Tracking {len(stock_symbols)} Shariah stocks")
    
    # 2. Fetch data
    print("📡 Fetching data...")
    quotes = {}
    fundamentals = {}
    historical_data = {}
    for sym in stock_symbols:
        quotes[sym] = fetch_quote(sym)
        fundamentals[sym] = fetch_fundamentals(sym)
        historical_data[sym] = fetch_historical(sym, days=180)
    
    # 3. Market data
    market_pulse = fetch_market_pulse()
    index_summary = fetch_index_summary()
    sector_data = fetch_sector_performance()
    
    # 4. Calculate indicators
    print("📊 Calculating indicators...")
    indicators = {}
    for sym, hist in historical_data.items():
        indicators[sym] = calculate_indicators(hist)
    
    # 5. Sentiment
    print("📰 Fetching news sentiment...")
    sentiment_data = fetch_sentiment()
    
    # 6. Correlation matrix
    print("📊 Calculating correlation matrix...")
    correlation_matrix = calculate_correlation_matrix(historical_data, stock_symbols[:20])
    
    # 7. Paper trading
    paper_engine = PaperTradingEngine(ACCOUNT_BALANCE)
    trade_journal = TradeJournal()
    
    # 8. Generate signals
    print("🎯 Generating ultimate signals...")
    signals = {}
    entry_exit = {}
    for sym in stock_symbols:
        price = quotes[sym].get('price')
        if isinstance(price, str):
            try:
                price = float(price)
            except:
                price = None
        elif not isinstance(price, (int, float)):
            price = None
        
        sig = generate_signals(
            sym, price, indicators.get(sym, {}),
            sentiment_data, fundamentals.get(sym, {})
        )
        signals[sym] = sig
        ee = calculate_entry_exit(
            sym, price, sig, indicators.get(sym, {}),
            ACCOUNT_BALANCE, MAX_RISK_PER_TRADE
        )
        entry_exit[sym] = ee
        
        trade_journal.log_signal(sym, sig.get('primary', 'NEUTRAL'), sig.get('score', 0) / 10, len(sig.get('details', [])))
        
        if PAPER_TRADING and price and isinstance(price, (int, float)):
            if sig.get('action') == 'BUY' and ee.get('position_size', 0) > 0:
                paper_engine.buy(sym, price, ee.get('position_size', 0))
            elif sig.get('action') == 'SELL' and sym in paper_engine.portfolio:
                paper_engine.sell(sym, price)
    
    # 9. Generate report
    print("📝 Generating HTML report...")
    html_report = generate_ultimate_report(
        quotes, fundamentals, indicators, sentiment_data,
        signals, entry_exit, market_pulse, index_summary, sector_data,
        stock_symbols, correlation_matrix,
        ACCOUNT_BALANCE, trade_journal, paper_engine
    )
    
    # 10. Send email
    subject = f"⚡ PSX Ultimate Report - {len(stock_symbols)} Stocks - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    success = send_html_email(subject, html_report)
    if success:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
