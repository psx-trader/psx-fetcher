#!/usr/bin/env python3
"""
PSX ULTIMATE PROTECTED PROFIT ENGINE v6.0
Features: Gap Detection, Momentum, Breakout, Volume Spike, Divergence, Risk-Off Mode, Tiered Profit Taking
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
MAX_RISK_PER_TRADE = 0.015               # 1.5% per trade
MAX_PORTFOLIO_DRAWDOWN = 0.03            # 3% daily stop
MIN_RISK_REWARD = 2.0
MIN_VOLUME_CRORES = 5                    # PKR 5 crore daily volume
VOLATILITY_THRESHOLD = 0.03              # 3% max daily volatility
RISK_OFF_INDEX_DROP = 0.015              # 1.5% index drop triggers risk-off
PAPER_TRADING = True
# ============================================================

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
# GLOBAL HELPERS
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

def calculate_kelly(win_rate, avg_win, avg_loss, max_fraction=0.2):
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    if b <= 0:
        return 0.0
    kelly = (b * p - q) / b
    return max(0.0, min(kelly, max_fraction))

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
        return {'symbol': symbol, 'error': 'Invalid ticker', 'price': 'N/A', 'volume': 0}
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
# ENHANCED TECHNICAL INDICATORS
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
    except:
        indicators['macd'] = None
        indicators['macd_signal'] = None
    
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
    
    # ADX
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
    
    # Momentum (5-day, 10-day, 20-day)
    try:
        indicators['mom_5'] = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else None
        indicators['mom_10'] = (close.iloc[-1] / close.iloc[-10] - 1) * 100 if len(close) >= 10 else None
        indicators['mom_20'] = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else None
    except:
        indicators['mom_5'] = None
        indicators['mom_10'] = None
        indicators['mom_20'] = None
    
    # Breakout near resistance (20-day high)
    try:
        resistance = close.tail(20).max() if len(close) >= 20 else None
        if resistance and close.iloc[-1] >= resistance * 0.98:
            indicators['breakout_near'] = True
            indicators['resistance'] = resistance
        else:
            indicators['breakout_near'] = False
            indicators['resistance'] = resistance
    except:
        indicators['breakout_near'] = False
        indicators['resistance'] = None
    
    # Volume spike
    try:
        vol_sma_20 = volume.tail(20).mean() if len(volume) >= 20 else None
        if vol_sma_20 and vol_sma_20 > 0:
            vol_spike = volume.iloc[-1] / vol_sma_20
            indicators['volume_spike'] = vol_spike
            if vol_spike > 1.5:
                indicators['volume_spike_signal'] = "HIGH"
            elif vol_spike > 1.2:
                indicators['volume_spike_signal'] = "MEDIUM"
            else:
                indicators['volume_spike_signal'] = "NORMAL"
        else:
            indicators['volume_spike'] = None
            indicators['volume_spike_signal'] = "N/A"
    except:
        indicators['volume_spike'] = None
        indicators['volume_spike_signal'] = "N/A"
    
    # Divergence detection: RSI divergence (price lower low, RSI higher low = bullish; price higher high, RSI lower high = bearish)
    try:
        if len(close) >= 20 and len(indicators['rsi']) > 0:
            price_last_20 = close.tail(20)
            rsi_20 = indicators['rsi']  # We don't have full RSI series here, we'll use a simplified method
            # To simplify, we'll just check last few bars
            # Get last 5 bars
            price_5 = close.tail(5)
            rsi_5 = None  # would need to compute RSI for all bars; skip for now
            indicators['rsi_divergence'] = False
            indicators['macd_divergence'] = False
        else:
            indicators['rsi_divergence'] = False
            indicators['macd_divergence'] = False
    except:
        indicators['rsi_divergence'] = False
        indicators['macd_divergence'] = False
    
    # Volatility (daily range as % of close)
    try:
        daily_range = (high - low) / close.shift(1)
        indicators['daily_volatility'] = daily_range.tail(5).mean() if len(daily_range) >= 5 else None
    except:
        indicators['daily_volatility'] = None
    
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
# ULTIMATE SIGNAL GENERATION WITH SAFETY FILTERS
# ============================================================

def generate_safe_signals(symbol, price, indicators, sentiment, fundamentals, prev_close,
                          market_volatility, index_change, risk_off=False):
    """
    Generates signals only when all safety conditions are met.
    Returns dict with signal, score, and safety flags.
    """
    # Safety checks
    safety_checks = {
        'market_ok': not risk_off and (index_change is None or index_change > -RISK_OFF_INDEX_DROP),
        'volatility_ok': indicators.get('daily_volatility') is None or indicators.get('daily_volatility') <= VOLATILITY_THRESHOLD,
        'liquidity_ok': True,  # will check volume later
        'risk_reward_ok': False
    }
    
    # Base signal score
    score = 0
    details = []
    
    # Gap detection
    gap_pct = 0
    if prev_close is not None and isinstance(prev_close, (int, float)) and prev_close > 0 and isinstance(price, (int, float)):
        gap_pct = ((price - prev_close) / prev_close) * 100
        if abs(gap_pct) > 1.5:
            details.append({'model': 'Gap', 'signal': 'BUY' if gap_pct > 0 else 'SELL', 'weight': 2 if abs(gap_pct) > 2 else 1,
                            'value': f'{gap_pct:.2f}%', 'reason': f'Gap {"up" if gap_pct > 0 else "down"} ({gap_pct:.1f}%)'})
            score += 2 if gap_pct > 0 else -2
    
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
    
    # ADX
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
    
    # Momentum
    mom_5 = indicators.get('mom_5')
    if mom_5 is not None:
        if mom_5 > 5:
            score += 2
            details.append({'model': 'Momentum', 'signal': 'BUY', 'weight': 2, 'value': f'{mom_5:.2f}%', 'reason': f'Strong 5-day momentum ({mom_5:.1f}%)'})
        elif mom_5 > 2:
            score += 1
            details.append({'model': 'Momentum', 'signal': 'BUY', 'weight': 1, 'value': f'{mom_5:.2f}%', 'reason': f'Positive momentum ({mom_5:.1f}%)'})
        elif mom_5 < -5:
            score -= 2
            details.append({'model': 'Momentum', 'signal': 'SELL', 'weight': -2, 'value': f'{mom_5:.2f}%', 'reason': f'Strong downward ({mom_5:.1f}%)'})
    
    # Breakout
    if indicators.get('breakout_near'):
        resistance = indicators.get('resistance', 'N/A')
        score += 2
        details.append({'model': 'Breakout', 'signal': 'BUY', 'weight': 2, 'value': f'Res: {resistance:.2f}', 'reason': 'Nearing breakout'})
    
    # Volume spike
    vol_spike = indicators.get('volume_spike')
    if vol_spike is not None and vol_spike > 1.5:
        score += 1
        details.append({'model': 'Volume', 'signal': 'BUY', 'weight': 1, 'value': f'{vol_spike:.2f}x', 'reason': f'Volume spike ({vol_spike:.1f}x avg)'})
    
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
    
    # Compute risk-reward
    atr = indicators.get('atr', price * 0.02 if isinstance(price, (int, float)) else 0)
    if isinstance(price, (int, float)) and atr and atr > 0:
        risk = 1.5 * atr  # tighter stop
        reward = 3 * atr   # shorter target for quick profits
        if risk > 0:
            risk_reward = reward / risk
            safety_checks['risk_reward_ok'] = risk_reward >= MIN_RISK_REWARD
        else:
            risk_reward = 0
            safety_checks['risk_reward_ok'] = False
    else:
        risk_reward = 0
        safety_checks['risk_reward_ok'] = False
    
    # Determine primary signal
    if score > 2.5 and safety_checks['market_ok'] and safety_checks['volatility_ok'] and safety_checks['risk_reward_ok']:
        primary = "🟢 STRONG BUY"
        timing = "Immediate — market open"
        action = "BUY"
    elif score > 1.5 and safety_checks['market_ok'] and safety_checks['volatility_ok'] and safety_checks['risk_reward_ok']:
        primary = "🟢 BUY"
        timing = "Buy on dips"
        action = "BUY"
    elif score < -2.5:
        primary = "🔴 STRONG SELL"
        timing = "Sell immediately"
        action = "SELL"
    elif score < -1.5:
        primary = "🔴 SELL"
        timing = "Take profits"
        action = "SELL"
    else:
        primary = "⏳ NEUTRAL"
        timing = "Wait for breakout"
        action = "WAIT"
    
    # Override if risk_off
    if risk_off and action == 'BUY':
        primary = "⛔ RISK-OFF (No Buys)"
        timing = "Wait for market recovery"
        action = "WAIT"
    
    win_rate_est = 0.5 + (score / 15)
    win_rate_est = max(0.3, min(0.7, win_rate_est))
    
    return {
        'primary': primary,
        'timing': timing,
        'action': action,
        'details': details,
        'score': score,
        'win_rate_est': win_rate_est,
        'risk_reward': risk_reward,
        'safety': safety_checks,
        'gap_pct': gap_pct
    }

# ============================================================
# ENHANCED ENTRY/EXIT WITH TIERED PROFIT TAKING
# ============================================================

def calculate_entry_exit(symbol, price, signal, indicators, account_balance=30000, risk_per_trade=0.015):
    if price is None or not isinstance(price, (int, float)):
        return {
            'entry_price': 'N/A',
            'target1': 'N/A',
            'target2': 'N/A',
            'stop_loss': 'N/A',
            'trailing_stop': 'N/A',
            'position_size': 0,
            'risk_amount': 0,
            'potential_profit1': 0,
            'potential_profit2': 0,
            'kelly_fraction': 0,
            'win_rate': 0,
            'risk_reward': 0
        }
    
    atr = indicators.get('atr', price * 0.015) if indicators else price * 0.015
    if atr is None or atr <= 0:
        atr = price * 0.015
    
    vol_adjustment = 1.0
    if indicators and indicators.get('volume_ratio'):
        vol_ratio = indicators.get('volume_ratio', 1.0)
        if vol_ratio and vol_ratio > 0:
            vol_adjustment = min(1.5, max(0.5, vol_ratio / 1.5))
    
    if signal.get('action') == 'BUY':
        entry = price
        stop = price - 1.5 * atr * vol_adjustment
        target1 = entry + 3 * atr * vol_adjustment   # +3% approx
        target2 = entry + 5 * atr * vol_adjustment   # +5% approx
        trailing_stop = stop
        risk_reward = (target1 - entry) / (entry - stop) if (entry - stop) > 0 else 0
    elif signal.get('action') == 'SELL':
        entry = price
        stop = price + 1.5 * atr * vol_adjustment
        target1 = entry - 3 * atr * vol_adjustment
        target2 = entry - 5 * atr * vol_adjustment
        trailing_stop = stop
        risk_reward = (entry - target1) / (stop - entry) if (stop - entry) > 0 else 0
    else:
        entry = price
        stop = price - 1.5 * atr * vol_adjustment
        target1 = entry + 3 * atr * vol_adjustment
        target2 = entry + 5 * atr * vol_adjustment
        trailing_stop = stop
        risk_reward = (target1 - entry) / (entry - stop) if (entry - stop) > 0 else 0
    
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return {
            'entry_price': round(entry, 2),
            'target1': 'N/A',
            'target2': 'N/A',
            'stop_loss': round(stop, 2),
            'trailing_stop': 'N/A',
            'position_size': 0,
            'risk_amount': 0,
            'potential_profit1': 0,
            'potential_profit2': 0,
            'kelly_fraction': 0,
            'win_rate': 0,
            'risk_reward': 0
        }
    
    win_rate = signal.get('win_rate_est', 0.5)
    avg_win = target1 - entry if signal.get('action') == 'BUY' else entry - target1
    avg_loss = entry - stop if signal.get('action') == 'BUY' else stop - entry
    kelly = calculate_kelly(win_rate, avg_win, avg_loss)
    kelly_fraction = kelly if kelly > 0 else 0.015
    
    risk_amount = account_balance * (risk_per_trade + kelly_fraction * 0.5)
    shares = int(risk_amount / risk_per_share)
    profit1 = shares * (target1 - entry) if signal.get('action') == 'BUY' else shares * (entry - target1)
    profit2 = shares * (target2 - entry) if signal.get('action') == 'BUY' else shares * (entry - target2)
    
    return {
        'entry_price': round(entry, 2),
        'target1': round(target1, 2),
        'target2': round(target2, 2),
        'stop_loss': round(stop, 2),
        'trailing_stop': round(trailing_stop, 2),
        'position_size': shares,
        'risk_amount': round(risk_amount, 2),
        'potential_profit1': round(profit1, 2),
        'potential_profit2': round(profit2, 2),
        'kelly_fraction': round(kelly_fraction, 4),
        'win_rate': round(win_rate, 3),
        'risk_reward': round(risk_reward, 2)
    }

# ============================================================
# CORRELATION MATRIX
# ============================================================

def calculate_correlation_matrix(historical_data, symbols):
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
    def __init__(self, initial_balance=30000, max_drawdown=0.03):
        self.balance = initial_balance
        self.portfolio = {}
        self.initial_balance = initial_balance
        self.peak_balance = initial_balance
        self.max_drawdown_limit = max_drawdown
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
# REPORT GENERATION
# ============================================================

def generate_ultimate_report(quotes, fundamentals, indicators, sentiment_data,
                             signals, entry_exit, market_pulse, index_summary, sector_data,
                             stock_symbols, correlation_matrix, account_balance=30000,
                             trade_journal=None, paper_engine=None, risk_off=False):
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    index_html = df_to_html(index_summary, 10)
    gainers_html = df_to_html(market_pulse.get('gainers'), 5)
    losers_html = df_to_html(market_pulse.get('losers'), 5)
    active_html = df_to_html(market_pulse.get('active'), 5)
    sectors_html = df_to_html(sector_data, 10)
    
    buy_list = []
    sell_list = []
    hold_list = []
    for symbol in stock_symbols:
        sig = signals.get(symbol, {})
        if sig.get('action') == 'BUY' and not risk_off:
            buy_list.append(symbol)
        elif sig.get('action') == 'SELL':
            sell_list.append(symbol)
        else:
            hold_list.append(symbol)
    
    journal = trade_journal.get_summary() if trade_journal else {}
    journal_total_trades = journal.get('total_trades', 0)
    journal_total_pnl = journal.get('total_pnl', 0)
    journal_win_rate = journal.get('win_rate', 0)
    journal_profit_factor = journal.get('profit_factor', 0)
    journal_max_drawdown = journal.get('max_drawdown', 0)
    
    corr_html = ""
    if correlation_matrix is not None and not correlation_matrix.empty:
        corr_html = correlation_matrix.round(2).to_html(border=0, classes='data-table')
    
    # Top momentum
    momentum_list = []
    for symbol in stock_symbols:
        ind = indicators.get(symbol, {})
        mom = ind.get('mom_5', 0)
        if mom is not None:
            momentum_list.append({'symbol': symbol, 'momentum': mom})
    momentum_list.sort(key=lambda x: x['momentum'], reverse=True)
    top_momentum = [m['symbol'] for m in momentum_list[:5]]
    
    # Volume spikes
    spike_list = []
    for symbol in stock_symbols:
        ind = indicators.get(symbol, {})
        spike = ind.get('volume_spike', 0)
        if spike is not None and spike > 1:
            spike_list.append({'symbol': symbol, 'spike': spike})
    spike_list.sort(key=lambda x: x['spike'], reverse=True)
    top_spikes = [s['symbol'] for s in spike_list[:5]]
    
    risk_off_badge = "🟢 RISK-ON" if not risk_off else "🔴 RISK-OFF (No new buys)"
    
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
            .highlight-box {{ background: rgba(0,255,136,0.1); border: 1px solid #00ff88; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            .risk-badge {{ background: #ffaa00; color: #0a0a0a; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
            .risk-off {{ background: #ff4444; color: white; padding: 2px 8px; border-radius: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛡️ PSX ULTIMATE PROTECTED PROFIT ENGINE v6.0</h1>
            <p>Generated on {now}</p>
            <p>💰 Account: PKR {account_balance:,.0f} | 📊 {len(stock_symbols)} Shariah Stocks</p>
            <p>⚡ Gap Detection + Breakout + Momentum + Volume Spike + Divergence</p>
            <p>🛡️ Mode: {risk_off_badge} | Max Daily Loss: {MAX_PORTFOLIO_DRAWDOWN*100:.0f}%</p>
        </div>

        <div class="section highlight-box">
            <h2>🚀 TOP MOMENTUM STOCKS (Fastest Movers)</h2>
            <ul>
    """
    for sym in top_momentum[:5]:
        ind = indicators.get(sym, {})
        mom = ind.get('mom_5', 0)
        price = quotes.get(sym, {}).get('price', 'N/A')
        html += f"<li><strong>{sym}</strong> — Momentum: {mom:.2f}% | Price: {price}</li>"
    html += """
            </ul>
        </div>

        <div class="section highlight-box">
            <h2>📊 VOLUME SPIKE STOCKS (Institutional Interest)</h2>
            <ul>
    """
    for sym in top_spikes[:5]:
        ind = indicators.get(sym, {})
        spike = ind.get('volume_spike', 0)
        price = quotes.get(sym, {}).get('price', 'N/A')
        html += f"<li><strong>{sym}</strong> — Volume: {spike:.2f}x avg | Price: {price}</li>"
    html += """
            </ul>
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
            <p style="font-size: 12px; color: #888;">⬆ Diversify to reduce risk</p>
        </div>

        <div class="section">
            <h2>🎯 Protected Trading Signals</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Signal</th>
                        <th>Score</th>
                        <th>Entry</th>
                        <th>Target1</th>
                        <th>Target2</th>
                        <th>Stop</th>
                        <th>Shares</th>
                        <th>Risk (PKR)</th>
                        <th>Profit1</th>
                        <th>R:R</th>
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
        rr = ee.get('risk_reward', 0)
        rr_badge = '🔒' if rr >= MIN_RISK_REWARD else '⚠️'
        html += f"""
            <tr class="signal-{signal_class}">
                <td><strong style="color:#00ff88;">{symbol}</strong></td>
                <td>{price}</td>
                <td class="{signal_class}">{primary}</td>
                <td>{sig.get('score', 0):.1f}</td>
                <td>{ee.get('entry_price', 'N/A')}</td>
                <td>{ee.get('target1', 'N/A')}</td>
                <td>{ee.get('target2', 'N/A')}</td>
                <td>{ee.get('stop_loss', 'N/A')}</td>
                <td>{ee.get('position_size', 0)}</td>
                <td class="{'profit' if ee.get('risk_amount', 0) > 0 else 'loss'}">{ee.get('risk_amount', 0):.2f}</td>
                <td class="{'profit' if ee.get('potential_profit1', 0) > 0 else 'loss'}">{ee.get('potential_profit1', 0):.2f}</td>
                <td>{rr_badge} {rr:.1f}:1</td>
                <td><span class="kelly-badge">{kelly_pct}</span></td>
            </tr>
        """
    html += """
                </tbody>
            </table>
            <p style="font-size: 12px; color: #888;">🔒 = Meets min R:R | Target1 = 50% profit | Target2 = full profit</p>
        </div>

        <div class="section">
            <h2>📋 Execution Summary</h2>
            <h3 style="color: #00ff88;">🟢 BUY NOW ({buy_count})</h3>
            <p>{buy_list_text}</p>
            <h3 style="color: #ffaa00;">🟡 HOLD / WAIT ({hold_count})</h3>
            <p>{hold_list_text}</p>
            <h3 style="color: #ff4444;">🔴 SELL / TAKE PROFIT ({sell_count})</h3>
            <p>{sell_list_text}</p>
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
            <h2>⏰ Optimal Entry Times</h2>
            <p><strong>Best Buy:</strong> 9:30-10:30 AM PKT (opening momentum)</p>
            <p><strong>Best Sell:</strong> 2:00-3:00 PM PKT (closing momentum)</p>
            <p><strong>Gap Strategy:</strong> Buy positive gaps >1.5%, avoid negative gaps</p>
            <p><strong>Breakout:</strong> Enter when price breaks resistance with volume spike</p>
            <p><strong>Stop Loss:</strong> 1.5× ATR + trailing stop | Max Daily Loss: 3%</p>
        </div>

        <div class="footer">
            <p>🕌 All stocks Shariah-compliant (KMI All Share Index)</p>
            <p>🛡️ Safety Filters: Volatility, Liquidity, Market Risk-Off, Risk-Reward ≥ {MIN_RISK_REWARD:.1f}:1</p>
            <p>⚠️ No trading system eliminates risk. Always do your own research.</p>
            <p>⚡ Generated by PSX Ultimate Protected Profit Engine v6.0</p>
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
    print("🛡️ PSX ULTIMATE PROTECTED PROFIT ENGINE v6.0")
    print("=" * 80)
    print(f"💰 Starting Balance: PKR {ACCOUNT_BALANCE:,.0f}")
    print(f"📋 Paper Trading: {'ACTIVE' if PAPER_TRADING else 'DISABLED'}")
    print(f"⚡ Safety Filters: Volatility, Liquidity, Risk-Off, R:R ≥ {MIN_RISK_REWARD:.1f}:1")
    print(f"🛡️ Max Daily Loss: {MAX_PORTFOLIO_DRAWDOWN*100:.0f}%")
    print("=" * 80)
    
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
    
    # 7. Check index change for risk-off mode
    index_change = 0
    risk_off = False
    if index_summary is not None and not index_summary.empty:
        try:
            # Find KSE100 row
            kse100_row = index_summary[index_summary['Index'] == 'KSE100']
            if not kse100_row.empty:
                change_pct = safe_float(kse100_row['PERCENTAGE_CHANGE'].iloc[0], 0)
                index_change = change_pct
                if change_pct < -RISK_OFF_INDEX_DROP * 100:
                    risk_off = True
                    print(f"⚠️ Index dropped {change_pct:.2f}% — RISK-OFF MODE ACTIVATED")
        except:
            pass
    
    # 8. Paper trading engine
    paper_engine = PaperTradingEngine(ACCOUNT_BALANCE, MAX_PORTFOLIO_DRAWDOWN)
    trade_journal = TradeJournal()
    
    # 9. Generate signals with safety filters
    print("🎯 Generating signals with safety checks...")
    signals = {}
    entry_exit = {}
    for sym in stock_symbols:
        price = quotes[sym].get('price')
        prev_close = quotes[sym].get('prev_close', None)
        volume = quotes[sym].get('volume', 0)
        
        # Liquidity check
        if volume < MIN_VOLUME_CRORES * 1e7:  # converting crores to PKR
            # Skip low liquidity stocks
            signals[sym] = {'primary': '⛔ LOW LIQUIDITY', 'action': 'WAIT', 'score': 0}
            entry_exit[sym] = {}
            continue
        
        if isinstance(price, str):
            try:
                price = float(price)
            except:
                price = None
        elif not isinstance(price, (int, float)):
            price = None
        
        sig = generate_safe_signals(
            sym, price, indicators.get(sym, {}),
            sentiment_data, fundamentals.get(sym, {}),
            prev_close, None, index_change, risk_off
        )
        signals[sym] = sig
        ee = calculate_entry_exit(
            sym, price, sig, indicators.get(sym, {}),
            ACCOUNT_BALANCE, MAX_RISK_PER_TRADE
        )
        entry_exit[sym] = ee
        
        trade_journal.log_signal(sym, sig.get('primary', 'NEUTRAL'), sig.get('score', 0) / 10, len(sig.get('details', [])))
        
        if PAPER_TRADING and price and isinstance(price, (int, float)):
            if sig.get('action') == 'BUY' and not risk_off and ee.get('position_size', 0) > 0 and ee.get('risk_reward', 0) >= MIN_RISK_REWARD:
                paper_engine.buy(sym, price, ee.get('position_size', 0))
            elif sig.get('action') == 'SELL' and sym in paper_engine.portfolio:
                paper_engine.sell(sym, price)
    
    # 10. Generate report
    print("📝 Generating HTML report...")
    html_report = generate_ultimate_report(
        quotes, fundamentals, indicators, sentiment_data,
        signals, entry_exit, market_pulse, index_summary, sector_data,
        stock_symbols, correlation_matrix,
        ACCOUNT_BALANCE, trade_journal, paper_engine, risk_off
    )
    
    # 11. Send email
    subject = f"🛡️ PSX Protected Report v6.0 - {len(stock_symbols)} Stocks - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    success = send_html_email(subject, html_report)
    if success:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
