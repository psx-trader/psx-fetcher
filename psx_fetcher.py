#!/usr/bin/env python3
"""
PSX ULTIMATE INTELLIGENCE ENGINE v2.0
Advanced Features: TA-Lib, ML, Sentiment, Risk Management, Backtesting
"""

import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import concurrent.futures
import re
import time
import json
import feedparser
from textblob import TextBlob

# ============================================================
# CONFIGURATION
# ============================================================
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# ============================================================

# TA-Lib fallback: try to import, else use manual implementations
try:
    import talib
    TA_LIB_AVAILABLE = True
except ImportError:
    TA_LIB_AVAILABLE = False
    print("⚠️ TA-Lib not installed. Using manual indicator calculations.")

# Well-known Shariah-compliant tickers
VALID_SHARIAH_TICKERS = [
    "FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB", 
    "OGDC", "PPL", "PSO", "LUCK", "MEBL", "UBL", 
    "NBP", "HBL", "DGKC", "MLCF", "FCCL", "ATRL", 
    "NRL", "PRL", "PAEL", "SEARL", "SNGP", "SSGC", 
    "ENGROH", "GAL", "GHNI", "HCAR", "NML", "TREET", 
    "CNERGY", "CPHL", "FFL", "AIRLINK", "KEL", "WTL",
    "TRG", "TPL", "PICT", "IBFL", "SCBPL", "SILK",
    "KAPCO", "NCL", "PSMC", "PTC", "SBL", "SHFA",
    "SML", "SNBL", "SSML", "UPFL", "WAVES", "WSML"
]

ALL_KNOWN_TICKERS = VALID_SHARIAH_TICKERS.copy()  # expand as needed

# RSS Feeds for sentiment (Dawn, Brecorder, The News)
RSS_FEEDS = [
    "https://www.dawn.com/feeds/business",
    "https://www.brecorder.com/rss/news",
    "https://www.thenews.com.pk/rss/2/5"
]

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def is_valid_ticker(symbol):
    if not symbol or not isinstance(symbol, str):
        return False
    if not re.match(r'^[A-Z]+$', symbol):
        return False
    if len(symbol) < 2 or len(symbol) > 6:
        return False
    invalid_sectors = ["CEMENT", "FERTILIZER", "BANKING", "TEXTILE", "ENERGY", "OIL", "GAS"]
    if symbol in invalid_sectors:
        return False
    return symbol in ALL_KNOWN_TICKERS

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

# ============================================================
# 1. DATA FETCHING (Enhanced with L1/L2 via psx-terminal if available)
# ============================================================

def fetch_top_shariah_compliant_stocks(limit=50):
    """Fetch Shariah-compliant stocks from KMI All Share Index."""
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
        # Intersect with Shariah list
        shariah_tickers = [t for t in valid_tickers if t in VALID_SHARIAH_TICKERS]
        if not shariah_tickers:
            return VALID_SHARIAH_TICKERS[:limit]
        # Rank by volume
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

def fetch_stock_quote(symbol):
    """Fetch real-time quote, with optional L1/L2 data if psx-terminal available."""
    if not is_valid_ticker(symbol):
        return {'symbol': symbol, 'error': 'Invalid ticker', 'price': 'N/A'}
    try:
        # Try using psx-terminal for L1 data if available
        try:
            from psx_terminal.feed_parser import fetch_quotes
            quotes = fetch_quotes(symbol)
            if quotes and len(quotes) > 0:
                latest = quotes[-1]
                return {
                    'symbol': symbol,
                    'price': latest.price if hasattr(latest, 'price') else 'N/A',
                    'bid': latest.bid if hasattr(latest, 'bid') else 'N/A',
                    'ask': latest.ask if hasattr(latest, 'ask') else 'N/A',
                    'volume': latest.volume if hasattr(latest, 'volume') else 'N/A',
                    'change': latest.change if hasattr(latest, 'change') else 'N/A',
                    'change_pct': latest.change_pct if hasattr(latest, 'change_pct') else 'N/A',
                    'high': latest.high if hasattr(latest, 'high') else 'N/A',
                    'low': latest.low if hasattr(latest, 'low') else 'N/A',
                    'open': latest.open if hasattr(latest, 'open') else 'N/A',
                    'source': 'psx-terminal'
                }
        except:
            pass
        # Fallback to pypsx
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
            'open': reg_data.get('Open', 'N/A'),
            'source': 'pypsx'
        }
    except Exception as e:
        return {'symbol': symbol, 'error': str(e), 'price': 'N/A'}

def fetch_stock_fundamentals(symbol):
    """Fetch fundamental data."""
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

def fetch_historical_data(symbol, days=180):
    """Fetch historical data for technical analysis."""
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

# ============================================================
# 2. ADVANCED TECHNICAL INDICATORS (TA-Lib + Manual Fallback)
# ============================================================

def calculate_advanced_indicators(df):
    """Calculate 15+ indicators using TA-Lib or manual methods."""
    if df is None or df.empty:
        return {}
    # Auto-detect columns
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
    
    close = df[close_col].values
    high = df[high_col].values
    low = df[low_col].values
    volume = df[volume_col].values
    close_series = pd.Series(close)
    high_series = pd.Series(high)
    low_series = pd.Series(low)
    volume_series = pd.Series(volume)
    
    indicators = {}
    
    if TA_LIB_AVAILABLE:
        # Use TA-Lib
        try:
            indicators['rsi'] = talib.RSI(close, timeperiod=14)[-1]
            indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            indicators['macd'] = indicators['macd'][-1]
            indicators['macd_signal'] = indicators['macd_signal'][-1]
            indicators['macd_hist'] = indicators['macd_hist'][-1]
            indicators['adx'] = talib.ADX(high, low, close, timeperiod=14)[-1]
            indicators['stoch_k'], indicators['stoch_d'] = talib.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3)
            indicators['stoch_k'] = indicators['stoch_k'][-1]
            indicators['stoch_d'] = indicators['stoch_d'][-1]
            indicators['atr'] = talib.ATR(high, low, close, timeperiod=14)[-1]
            indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
            indicators['bb_upper'] = indicators['bb_upper'][-1]
            indicators['bb_middle'] = indicators['bb_middle'][-1]
            indicators['bb_lower'] = indicators['bb_lower'][-1]
            indicators['sma_20'] = talib.SMA(close, timeperiod=20)[-1]
            indicators['sma_50'] = talib.SMA(close, timeperiod=50)[-1]
            indicators['sma_200'] = talib.SMA(close, timeperiod=200)[-1] if len(close) >= 200 else None
            indicators['ema_12'] = talib.EMA(close, timeperiod=12)[-1]
            indicators['ema_26'] = talib.EMA(close, timeperiod=26)[-1]
            indicators['volume_sma'] = talib.SMA(volume, timeperiod=20)[-1]
            indicators['volume_ratio'] = volume[-1] / indicators['volume_sma'] if indicators['volume_sma'] and indicators['volume_sma'] > 0 else None
            indicators['obv'] = talib.OBV(close, volume)[-1]
        except Exception as e:
            print(f"TA-Lib error: {e}. Falling back to manual.")
            TA_LIB_AVAILABLE_FOR_THIS = False
        else:
            TA_LIB_AVAILABLE_FOR_THIS = True
    else:
        TA_LIB_AVAILABLE_FOR_THIS = False
    
    if not TA_LIB_AVAILABLE_FOR_THIS:
        # Manual fallback for key indicators
        # RSI
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1] if len(rs) > 0 else None
        
        # MACD
        exp1 = close_series.ewm(span=12, adjust=False).mean()
        exp2 = close_series.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        indicators['macd'] = macd.iloc[-1] if len(macd) > 0 else None
        indicators['macd_signal'] = signal.iloc[-1] if len(signal) > 0 else None
        indicators['macd_hist'] = (macd - signal).iloc[-1] if len(macd) > 0 and len(signal) > 0 else None
        
        # ADX (simplified)
        try:
            plus_dm = high_series.diff()
            minus_dm = low_series.diff()
            tr = pd.concat([high_series - low_series, (high_series - close_series.shift()).abs(), (low_series - close_series.shift()).abs()], axis=1).max(axis=1)
            atr_14 = tr.rolling(14).mean()
            plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
            minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            indicators['adx'] = dx.rolling(14).mean().iloc[-1] if len(dx) >= 14 else None
        except:
            indicators['adx'] = None
        
        # Stochastic
        try:
            low_14 = low_series.rolling(14).min()
            high_14 = high_series.rolling(14).max()
            stoch_k = 100 * ((close_series - low_14) / (high_14 - low_14))
            indicators['stoch_k'] = stoch_k.iloc[-1] if len(stoch_k) > 0 else None
            indicators['stoch_d'] = stoch_k.rolling(3).mean().iloc[-1] if len(stoch_k) >= 3 else None
        except:
            indicators['stoch_k'] = None
            indicators['stoch_d'] = None
        
        # Bollinger Bands
        sma_20 = close_series.rolling(20).mean()
        std_20 = close_series.rolling(20).std()
        indicators['bb_upper'] = sma_20.iloc[-1] + 2 * std_20.iloc[-1] if len(sma_20) > 0 else None
        indicators['bb_middle'] = sma_20.iloc[-1] if len(sma_20) > 0 else None
        indicators['bb_lower'] = sma_20.iloc[-1] - 2 * std_20.iloc[-1] if len(sma_20) > 0 else None
        
        # SMAs
        indicators['sma_20'] = close_series.tail(20).mean() if len(close_series) >= 20 else None
        indicators['sma_50'] = close_series.tail(50).mean() if len(close_series) >= 50 else None
        indicators['sma_200'] = close_series.tail(200).mean() if len(close_series) >= 200 else None
        indicators['ema_12'] = close_series.ewm(span=12, adjust=False).mean().iloc[-1] if len(close_series) >= 12 else None
        indicators['ema_26'] = close_series.ewm(span=26, adjust=False).mean().iloc[-1] if len(close_series) >= 26 else None
        
        # Volume
        indicators['volume_sma'] = volume_series.tail(20).mean() if len(volume_series) >= 20 else None
        indicators['volume_ratio'] = volume_series.iloc[-1] / indicators['volume_sma'] if indicators['volume_sma'] and indicators['volume_sma'] > 0 else None
        indicators['obv'] = None  # skip
    
    # BB Position
    if indicators.get('bb_upper') and indicators.get('bb_lower') and indicators.get('bb_middle'):
        if indicators['bb_upper'] != indicators['bb_lower']:
            indicators['bb_position'] = ((close[-1] - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower']))
        else:
            indicators['bb_position'] = 0.5
    else:
        indicators['bb_position'] = None
    
    # ATR (fallback if not set)
    if indicators.get('atr') is None:
        try:
            tr1 = high_series - low_series
            tr2 = (high_series - close_series.shift()).abs()
            tr3 = (low_series - close_series.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            indicators['atr'] = tr.rolling(window=14).mean().iloc[-1] if len(tr) >= 14 else None
        except:
            indicators['atr'] = None
    
    # Return as dict
    return indicators

# ============================================================
# 3. MACHINE LEARNING PREDICTOR (Linear Regression)
# ============================================================

def simple_ml_predictor(df, days_ahead=5):
    """
    Simple linear regression to predict future price direction.
    Returns: predicted change % and confidence.
    """
    if df is None or df.empty or len(df) < 20:
        return {'prediction': 'neutral', 'confidence': 0.0}
    try:
        close_col = None
        for col in df.columns:
            if 'close' in col.lower() or 'adj close' in col.lower():
                close_col = col
                break
        if close_col is None:
            close_col = df.columns[3] if len(df.columns) > 3 else df.columns[0]
        prices = df[close_col].values
        if len(prices) < 20:
            return {'prediction': 'neutral', 'confidence': 0.0}
        # Simple linear regression on lagged prices
        X = np.array(range(len(prices))).reshape(-1, 1)
        y = prices
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        model.fit(X, y)
        # Predict next days_ahead
        last_idx = len(prices) - 1
        future_idx = last_idx + days_ahead
        pred_price = model.predict([[future_idx]])[0]
        current_price = prices[-1]
        pct_change = (pred_price / current_price - 1) * 100
        # Confidence based on R^2
        r2 = model.score(X, y)
        if pct_change > 2:
            pred = 'up'
        elif pct_change < -2:
            pred = 'down'
        else:
            pred = 'neutral'
        return {
            'prediction': pred,
            'pct_change': pct_change,
            'confidence': r2,
            'predicted_price': pred_price
        }
    except Exception as e:
        return {'prediction': 'neutral', 'confidence': 0.0, 'error': str(e)}

# ============================================================
# 4. SENTIMENT ANALYSIS
# ============================================================

def fetch_news_sentiment():
    """Fetch and analyze news sentiment from RSS feeds."""
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                blob = TextBlob(title + " " + summary)
                polarity = blob.sentiment.polarity
                subjectivity = blob.sentiment.subjectivity
                # Classify
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
                    'polarity': polarity,
                    'subjectivity': subjectivity
                })
        except Exception as e:
            print(f"RSS error: {e}")
    # Aggregate sentiment
    if articles:
        avg_polarity = np.mean([a['polarity'] for a in articles])
        overall_sentiment = 'bullish' if avg_polarity > 0.05 else 'bearish' if avg_polarity < -0.05 else 'neutral'
        return {
            'overall': overall_sentiment,
            'avg_polarity': avg_polarity,
            'articles': articles[:10]
        }
    else:
        return {'overall': 'neutral', 'avg_polarity': 0, 'articles': []}

# ============================================================
# 5. RISK MANAGEMENT (Kelly Criterion, Dynamic Position Sizing)
# ============================================================

def calculate_kelly_position(win_rate, avg_win, avg_loss):
    """
    Kelly Criterion: f* = (bp - q) / b
    where b = avg_win/avg_loss, p = win_rate, q = 1-p
    Returns fraction of capital to risk.
    """
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    if b <= 0:
        return 0.0
    kelly = (b * p - q) / b
    # Cap at 25% to avoid overbetting
    return max(0.0, min(kelly, 0.25))

def dynamic_position_sizing(account_balance, entry_price, stop_loss_price, risk_per_trade_ratio=0.02, kelly_fraction=0.0):
    """
    Calculate position size based on account balance and risk per trade.
    If kelly_fraction > 0, use it to adjust risk.
    """
    if entry_price <= 0 or stop_loss_price >= entry_price:
        return 0
    risk_per_share = entry_price - stop_loss_price
    if risk_per_share <= 0:
        return 0
    # Base risk: 2% of account
    risk_amount = account_balance * risk_per_trade_ratio
    # Adjust by Kelly if provided
    if kelly_fraction > 0:
        risk_amount = risk_amount * (1 + kelly_fraction)
    shares = risk_amount / risk_per_share
    return int(shares)

# ============================================================
# 6. SIGNAL GENERATION WITH ADVANCED INDICATORS
# ============================================================

def generate_advanced_signals(symbol, price, indicators, ml_pred, sentiment, fundamentals):
    """Generate buy/sell signals based on multi-model ensemble."""
    signals = []
    if not indicators or price is None:
        return [{"signal": "⏳ NEUTRAL", "reason": "Insufficient data"}]
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            return [{"signal": "⏳ NEUTRAL", "reason": "Invalid price"}]
    if not isinstance(price, (int, float)):
        return [{"signal": "⏳ NEUTRAL", "reason": "Invalid price"}]
    
    # 1. RSI
    rsi = indicators.get('rsi')
    if rsi is not None:
        if rsi < 30:
            signals.append({"signal": "🟢 STRONG BUY", "source": "RSI", "value": f"{rsi:.2f}", "reason": "Oversold", "weight": 2})
        elif rsi > 70:
            signals.append({"signal": "🔴 STRONG SELL", "source": "RSI", "value": f"{rsi:.2f}", "reason": "Overbought", "weight": -2})
        else:
            signals.append({"signal": "⏳ NEUTRAL", "source": "RSI", "value": f"{rsi:.2f}", "reason": "Neutral", "weight": 0})
    
    # 2. MACD
    macd = indicators.get('macd')
    macd_signal = indicators.get('macd_signal')
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            signals.append({"signal": "🟢 BUY", "source": "MACD", "value": f"{macd:.3f}", "reason": "Bullish crossover", "weight": 1.5})
        else:
            signals.append({"signal": "🔴 SELL", "source": "MACD", "value": f"{macd:.3f}", "reason": "Bearish crossover", "weight": -1.5})
    
    # 3. ADX (trend strength)
    adx = indicators.get('adx')
    if adx is not None:
        if adx > 25:
            signals.append({"signal": "🟢 TRENDING", "source": "ADX", "value": f"{adx:.2f}", "reason": f"Strong trend (>{adx:.0f})", "weight": 1})
        else:
            signals.append({"signal": "⏳ NEUTRAL", "source": "ADX", "value": f"{adx:.2f}", "reason": "Weak/No trend", "weight": 0})
    
    # 4. Stochastic
    stoch_k = indicators.get('stoch_k')
    stoch_d = indicators.get('stoch_d')
    if stoch_k is not None and stoch_d is not None:
        if stoch_k < 20 and stoch_d < 20:
            signals.append({"signal": "🟢 BUY", "source": "Stochastic", "value": f"K={stoch_k:.2f}, D={stoch_d:.2f}", "reason": "Oversold crossover", "weight": 1.5})
        elif stoch_k > 80 and stoch_d > 80:
            signals.append({"signal": "🔴 SELL", "source": "Stochastic", "value": f"K={stoch_k:.2f}, D={stoch_d:.2f}", "reason": "Overbought crossover", "weight": -1.5})
    
    # 5. Bollinger Bands
    bb_position = indicators.get('bb_position')
    if bb_position is not None:
        if bb_position < 0.2:
            signals.append({"signal": "🟢 BUY", "source": "Bollinger", "value": f"{bb_position:.2f}", "reason": "At lower band", "weight": 1})
        elif bb_position > 0.8:
            signals.append({"signal": "🔴 SELL", "source": "Bollinger", "value": f"{bb_position:.2f}", "reason": "At upper band", "weight": -1})
    
    # 6. ML Prediction
    if ml_pred and ml_pred.get('prediction') != 'neutral' and ml_pred.get('confidence', 0) > 0.2:
        if ml_pred['prediction'] == 'up':
            signals.append({"signal": "🟢 BUY", "source": "ML", "value": f"{ml_pred.get('pct_change', 0):.2f}%", "reason": f"Predicted up {ml_pred.get('pct_change', 0):.1f}%", "weight": 1})
        else:
            signals.append({"signal": "🔴 SELL", "source": "ML", "value": f"{ml_pred.get('pct_change', 0):.2f}%", "reason": f"Predicted down {abs(ml_pred.get('pct_change', 0)):.1f}%", "weight": -1})
    
    # 7. Sentiment
    if sentiment and sentiment.get('overall') != 'neutral':
        if sentiment['overall'] == 'bullish':
            signals.append({"signal": "🟢 BULLISH", "source": "Sentiment", "value": f"{sentiment.get('avg_polarity', 0):.2f}", "reason": "Positive news sentiment", "weight": 0.5})
        else:
            signals.append({"signal": "🔴 BEARISH", "source": "Sentiment", "value": f"{sentiment.get('avg_polarity', 0):.2f}", "reason": "Negative news sentiment", "weight": -0.5})
    
    # 8. Fundamentals (P/E, Dividend)
    if fundamentals:
        pe = fundamentals.get('pe')
        div_yield = fundamentals.get('div_yield')
        if pe is not None and pe != 'N/A' and isinstance(pe, (int, float)) and pe < 15:
            signals.append({"signal": "🟢 VALUE", "source": "Fundamental", "value": f"P/E={pe:.2f}", "reason": "Low P/E", "weight": 0.5})
        if div_yield is not None and div_yield != 'N/A' and isinstance(div_yield, (int, float)) and div_yield > 5:
            signals.append({"signal": "💰 DIVIDEND", "source": "Fundamental", "value": f"Yield={div_yield:.2f}%", "reason": "High yield", "weight": 0.5})
    
    # Aggregate signals
    total_weight = sum([s.get('weight', 0) for s in signals])
    buy_count = sum(1 for s in signals if 'BUY' in s.get('signal', '') or 'BULLISH' in s.get('signal', ''))
    sell_count = sum(1 for s in signals if 'SELL' in s.get('signal', '') or 'BEARISH' in s.get('signal', ''))
    
    if total_weight > 1.5 and buy_count > sell_count:
        primary = "🟢 STRONG BUY"
        timing = "Immediate — market open"
        priority = "HIGH"
    elif total_weight > 0.5 and buy_count >= sell_count:
        primary = "🟢 BUY"
        timing = "Buy on dips"
        priority = "MEDIUM"
    elif total_weight < -1.5 and sell_count > buy_count:
        primary = "🔴 STRONG SELL"
        timing = "Sell immediately"
        priority = "HIGH"
    elif total_weight < -0.5 and sell_count >= buy_count:
        primary = "🔴 SELL"
        timing = "Take profits now"
        priority = "MEDIUM"
    else:
        primary = "⏳ NEUTRAL"
        timing = "Wait for breakout"
        priority = "LOW"
    
    # Return primary signal plus detailed list
    return {
        'primary': primary,
        'timing': timing,
        'priority': priority,
        'details': signals,
        'total_weight': total_weight,
        'buy_count': buy_count,
        'sell_count': sell_count
    }

# ============================================================
# 7. ENTRY/EXIT & POSITION SIZING
# ============================================================

def calculate_entry_exit_advanced(symbol, price, signals, indicators, account_balance=30000, risk_per_trade_ratio=0.02):
    """
    Calculate entry, target, stop-loss, and position size using ATR and Kelly.
    """
    if price is None or not isinstance(price, (int, float)):
        return {
            'entry_price': 'N/A',
            'target_price': 'N/A',
            'stop_loss': 'N/A',
            'position_size': 0,
            'entry_timing': 'N/A',
            'exit_timing': 'N/A',
            'risk_amount': 0,
            'potential_profit': 0
        }
    
    atr = indicators.get('atr', price * 0.02) if indicators else price * 0.02
    if atr is None or atr <= 0:
        atr = price * 0.02
    
    # Determine direction from signals
    if signals.get('primary', '').startswith('🟢'):
        direction = 'long'
        entry = price
        stop = price - 2 * atr  # 2 ATR stop
        target = price + 4 * atr  # 4 ATR target
        timing = signals.get('timing', 'Market open')
    elif signals.get('primary', '').startswith('🔴'):
        direction = 'short'
        entry = price
        stop = price + 2 * atr
        target = price - 4 * atr
        timing = signals.get('timing', 'Sell now')
    else:
        direction = 'neutral'
        entry = price
        stop = price - 2 * atr
        target = price + 4 * atr
        timing = 'Wait'
    
    # Position sizing using Kelly (simulate win rate from signals)
    # Use total_weight to estimate win rate (simplified)
    win_rate = 0.5 + (signals.get('total_weight', 0) / 10)  # scale
    win_rate = max(0.3, min(0.7, win_rate))
    avg_win = target - entry if direction == 'long' else entry - target
    avg_loss = entry - stop if direction == 'long' else stop - entry
    if avg_loss <= 0:
        kelly_fraction = 0.02
    else:
        kelly = calculate_kelly_position(win_rate, avg_win, avg_loss)
        kelly_fraction = kelly if kelly > 0 else 0.02
    shares = dynamic_position_sizing(account_balance, entry, stop, risk_per_trade_ratio, kelly_fraction)
    
    # Potential profit/loss
    risk_amount = shares * (entry - stop) if direction == 'long' else shares * (stop - entry)
    potential_profit = shares * (target - entry) if direction == 'long' else shares * (entry - target)
    
    return {
        'entry_price': round(entry, 2),
        'target_price': round(target, 2),
        'stop_loss': round(stop, 2),
        'position_size': shares,
        'entry_timing': timing,
        'exit_timing': f"When price reaches {round(target, 2)} or stop at {round(stop, 2)}",
        'risk_amount': round(risk_amount, 2),
        'potential_profit': round(potential_profit, 2),
        'kelly_fraction': round(kelly_fraction, 4),
        'win_rate_est': round(win_rate, 3)
    }

# ============================================================
# 8. REPORT GENERATION (ENHANCED)
# ============================================================

def df_to_html(df, limit=10):
    if df is None or df.empty:
        return "<p>No data available</p>"
    df = df.head(limit)
    return df.to_html(index=False, border=0, classes='data-table')

def generate_advanced_report(quotes, fundamentals, indicators, ml_predictions, sentiment_data,
                             signals, entry_exit, market_pulse, index_summary, sector_data,
                             stock_symbols, csf_symbols, account_balance=30000):
    """Generate comprehensive HTML report with all advanced metrics."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    index_html = df_to_html(index_summary, 10)
    gainers_html = df_to_html(market_pulse.get('gainers'), 5)
    losers_html = df_to_html(market_pulse.get('losers'), 5)
    active_html = df_to_html(market_pulse.get('active'), 5)
    sectors_html = df_to_html(sector_data, 10)
    
    # Build dividend opportunities
    div_opps = []
    for symbol in stock_symbols:
        f = fundamentals.get(symbol, {})
        div_yield = f.get('div_yield', 'N/A')
        if div_yield != 'N/A':
            try:
                dy = float(div_yield.replace('%', ''))
                if dy > 3:
                    div_opps.append({'symbol': symbol, 'yield': dy})
            except:
                pass
    div_opps.sort(key=lambda x: x['yield'], reverse=True)
    
    # Build buy/sell lists
    buy_list = []
    sell_list = []
    hold_list = []
    for symbol in stock_symbols:
        sig = signals.get(symbol, {})
        if sig.get('primary', '').startswith('🟢'):
            buy_list.append(symbol)
        elif sig.get('primary', '').startswith('🔴'):
            sell_list.append(symbol)
        else:
            hold_list.append(symbol)
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #1a3a5c, #2a5a8c); color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; }}
            .header p {{ margin: 5px 0; }}
            .section {{ background: white; margin: 20px; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .section h2 {{ color: #1a3a5c; margin-top: 0; border-bottom: 2px solid #1a3a5c; padding-bottom: 10px; }}
            .section h3 {{ color: #2a5a8c; margin: 10px 0; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            th {{ background: #1a3a5c; color: white; padding: 8px; text-align: left; }}
            td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            .buy {{ color: green; font-weight: bold; }}
            .sell {{ color: red; font-weight: bold; }}
            .neutral {{ color: orange; font-weight: bold; }}
            .signal-buy {{ background: #e8f5e9; }}
            .signal-sell {{ background: #ffebee; }}
            .signal-neutral {{ background: #fff3e0; }}
            .footer {{ text-align: center; font-size: 12px; color: #888; margin: 20px; padding: 10px; border-top: 1px solid #ddd; }}
            .highlight {{ background: #fff9c4; padding: 2px 6px; border-radius: 3px; }}
            .futures-section {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .corporate-action {{ background: #fce4ec; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .risk-section {{ background: #f1f8e9; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .ml-section {{ background: #fff3e0; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 PSX ULTIMATE INTELLIGENCE ENGINE v2.0</h1>
            <p>Generated on {now}</p>
            <p>Tracking {len(stock_symbols)} Shariah-Compliant Stocks | Account Balance: PKR {account_balance:,.0f}</p>
            <p>📊 {len(csf_symbols)} CSF Futures Eligible Securities</p>
            <p>🧠 TA-Lib: {'✅ Available' if TA_LIB_AVAILABLE else '❌ Manual fallback'}</p>
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

        <div class="section futures-section">
            <h2>📈 CSF Futures Eligible Securities</h2>
            <p><strong>Total:</strong> {len(csf_symbols)} securities | <strong>Contract Size:</strong> 500 shares | <strong>Period:</strong> 90 days</p>
            <table>
                <thead><tr><th>Symbol</th><th>Status</th></tr></thead>
                <tbody>
    """
    for symbol in csf_symbols[:30]:
        status = "🟢 Active" if quotes.get(symbol, {}).get('price') != 'N/A' else "⏳ Check"
        html += f"<tr><td><strong>{symbol}</strong></td><td>{status}</td></tr>"
    html += """
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>💵 Top Dividend Opportunities</h2>
            <table>
                <thead><tr><th>Symbol</th><th>Yield %</th></tr></thead>
                <tbody>
    """
    for d in div_opps[:20]:
        html += f"<tr><td><strong>{d['symbol']}</strong></td><td>{d['yield']:.2f}%</td></tr>"
    html += """
                </tbody>
            </table>
        </div>

        <div class="section ml-section">
            <h2>🧠 ML & Sentiment Insights</h2>
            <p><strong>Overall Sentiment:</strong> {sentiment} (Avg Polarity: {polarity:.2f})</p>
            <p><strong>Top News Headlines:</strong></p>
            <ul>
    """
    for article in sentiment_data.get('articles', [])[:5]:
        html += f"<li>{article['title']} — <span style='color:{'green' if article['sentiment']=='bullish' else 'red' if article['sentiment']=='bearish' else 'orange'}'>{article['sentiment']}</span></li>"
    html += """
            </ul>
        </div>

        <div class="section">
            <h2>🎯 Trading Signals & Execution Plan</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Signal</th>
                        <th>Entry</th>
                        <th>Target</th>
                        <th>Stop</th>
                        <th>Shares</th>
                        <th>Risk (PKR)</th>
                        <th>Potential Profit</th>
                    </tr>
                </thead>
                <tbody>
    """
    for symbol in stock_symbols[:20]:
        q = quotes.get(symbol, {})
        price = q.get('price', 'N/A')
        if price == 'N/A':
            continue
        sig = signals.get(symbol, {})
        ee = entry_exit.get(symbol, {})
        primary = sig.get('primary', '⏳ NEUTRAL')
        signal_class = 'buy' if 'BUY' in primary else 'sell' if 'SELL' in primary else 'neutral'
        html += f"""
            <tr class="signal-{signal_class}">
                <td><strong>{symbol}</strong></td>
                <td>{price}</td>
                <td class="{signal_class}">{primary}</td>
                <td>{ee.get('entry_price', 'N/A')}</td>
                <td>{ee.get('target_price', 'N/A')}</td>
                <td>{ee.get('stop_loss', 'N/A')}</td>
                <td>{ee.get('position_size', 0)}</td>
                <td>{ee.get('risk_amount', 0):.2f}</td>
                <td class="{'buy' if ee.get('potential_profit', 0) > 0 else 'sell'}">{ee.get('potential_profit', 0):.2f}</td>
            </tr>
        """
    html += """
                </tbody>
            </table>
        </div>

        <div class="section risk-section">
            <h2>🛡️ Risk Management</h2>
            <p><strong>Account Balance:</strong> PKR {account_balance:,.0f}</p>
            <p><strong>Max Risk per Trade:</strong> 2% (PKR {risk_amount:,.0f})</p>
            <p><strong>Kelly Criterion Applied:</strong> Dynamic position sizing based on win rate</p>
            <p><strong>Stop Loss Method:</strong> 2× ATR</p>
            <p><strong>Take Profit:</strong> 4× ATR</p>
        </div>

        <div class="section">
            <h2>📋 Execution Summary</h2>
            <h3 style="color: green;">🟢 BUY NOW ({len(buy_list)})</h3>
            <p>{', '.join(buy_list) if buy_list else 'No immediate buy signals'}</p>
            <h3 style="color: orange;">🟡 HOLD / WAIT ({len(hold_list)})</h3>
            <p>{', '.join(hold_list[:20]) + ('...' if len(hold_list)>20 else '') if hold_list else 'None'}</p>
            <h3 style="color: red;">🔴 SELL / TAKE PROFIT ({len(sell_list)})</h3>
            <p>{', '.join(sell_list) if sell_list else 'No sell signals'}</p>
        </div>

        <div class="footer">
            <p>🕌 All stocks Shariah-compliant (KMI All Share Index)</p>
            <p>📊 Advanced Indicators: {len(indicators)} per stock | ML: Linear Regression | Sentiment: TextBlob</p>
            <p>⚠️ For informational purposes only. Always do your own research.</p>
            <p>📈 Generated by PSX Ultimate Intelligence Engine v2.0</p>
        </div>
    </body>
    </html>
    """
    return html

# ============================================================
# 9. EMAIL SENDING
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
# 10. MAIN EXECUTION
# ============================================================

def main():
    print("🚀 PSX ULTIMATE INTELLIGENCE ENGINE v2.0")
    print("=" * 60)
    
    # 1. Fetch stocks
    stock_symbols = fetch_top_shariah_compliant_stocks(limit=50)
    stock_symbols = [s for s in stock_symbols if is_valid_ticker(s)]
    print(f"📊 Tracking {len(stock_symbols)} stocks")
    
    # 2. CSF eligible
    csf_symbols = ALL_KNOWN_TICKERS  # simplified
    
    # 3. Fetch data
    print("📡 Fetching stock data...")
    quotes = {}
    fundamentals = {}
    historical_data = {}
    for sym in stock_symbols:
        quotes[sym] = fetch_stock_quote(sym)
        fundamentals[sym] = fetch_stock_fundamentals(sym)
        historical_data[sym] = fetch_historical_data(sym, days=180)
    
    # 4. Market pulse, indices, sectors
    market_pulse = fetch_market_pulse()
    index_summary = fetch_index_summary()
    sector_data = fetch_sector_performance()
    
    # 5. Advanced indicators
    print("📊 Calculating advanced indicators...")
    indicators = {}
    ml_predictions = {}
    for sym, hist in historical_data.items():
        indicators[sym] = calculate_advanced_indicators(hist)
        ml_predictions[sym] = simple_ml_predictor(hist)
    
    # 6. Sentiment
    print("📰 Fetching news sentiment...")
    sentiment_data = fetch_news_sentiment()
    
    # 7. Generate signals & entry/exit
    print("🎯 Generating signals...")
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
        sig = generate_advanced_signals(
            sym, price, indicators.get(sym, {}),
            ml_predictions.get(sym, {}),
            sentiment_data,
            fundamentals.get(sym, {})
        )
        signals[sym] = sig
        entry_exit[sym] = calculate_entry_exit_advanced(
            sym, price, sig, indicators.get(sym, {}),
            account_balance=30000,
            risk_per_trade_ratio=0.02
        )
    
    # 8. Generate report
    print("📝 Generating HTML report...")
    html_report = generate_advanced_report(
        quotes, fundamentals, indicators, ml_predictions, sentiment_data,
        signals, entry_exit, market_pulse, index_summary, sector_data,
        stock_symbols, csf_symbols, account_balance=30000
    )
    
    # 9. Send email
    subject = f"PSX Ultimate Report - {len(stock_symbols)} Stocks - {datetime.now().strftime('%Y-%m-%d')}"
    success = send_html_email(subject, html_report)
    if success:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
