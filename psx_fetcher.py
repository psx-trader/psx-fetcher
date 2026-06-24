#!/usr/bin/env python3
"""
PSX ULTIMATE PROFIT ENGINE — BLACK BOX EDITION v3.0
Features:
- Multi-Model Ensemble (RSI, MACD, ADX, Stoch, BB, ML, Sentiment, Fundamentals)
- Kelly Criterion Position Sizing
- Backtesting Engine
- Trade Journal
- Paper Trading
- Risk-Adjusted Returns
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
import hashlib
import pickle

# ============================================================
# CONFIGURATION
# ============================================================
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
ACCOUNT_BALANCE = 30000  # PKR
MAX_RISK_PER_TRADE = 0.02  # 2%
PAPER_TRADING = True  # Set to False for live (requires API)
# ============================================================

# Try TA-Lib
try:
    import talib
    TA_LIB_AVAILABLE = True
except ImportError:
    TA_LIB_AVAILABLE = False
    print("⚠️ TA-Lib not installed. Using manual indicators.")

# Try sklearn for ML
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not installed. ML features limited.")

# Try TensorFlow for deep learning
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("⚠️ TensorFlow not installed. LSTM features disabled.")

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
    "SML", "SNBL", "SSML", "UPFL", "WAVES", "WSML"
]

RSS_FEEDS = [
    "https://www.dawn.com/feeds/business",
    "https://www.brecorder.com/rss/news",
    "https://www.thenews.com.pk/rss/2/5"
]

# ============================================================
# TRADE JOURNAL
# ============================================================

class TradeJournal:
    """Logs all trades, signals, and decisions for review."""
    def __init__(self):
        self.trades = []
        self.signals = []
        self.decisions = []
    
    def log_trade(self, symbol, entry_price, exit_price, quantity, entry_time, exit_time, profit_loss):
        self.trades.append({
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'profit_loss': profit_loss,
            'timestamp': datetime.now().isoformat()
        })
    
    def log_signal(self, symbol, signal, confidence, indicators_used):
        self.signals.append({
            'symbol': symbol,
            'signal': signal,
            'confidence': confidence,
            'indicators': indicators_used,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_summary(self):
        if not self.trades:
            return "No trades recorded."
        total_pnl = sum(t['profit_loss'] for t in self.trades)
        win_rate = len([t for t in self.trades if t['profit_loss'] > 0]) / len(self.trades) if self.trades else 0
        avg_win = sum(t['profit_loss'] for t in self.trades if t['profit_loss'] > 0) / len([t for t in self.trades if t['profit_loss'] > 0]) if [t for t in self.trades if t['profit_loss'] > 0] else 0
        avg_loss = sum(t['profit_loss'] for t in self.trades if t['profit_loss'] < 0) / len([t for t in self.trades if t['profit_loss'] < 0]) if [t for t in self.trades if t['profit_loss'] < 0] else 0
        profit_factor = abs(sum(t['profit_loss'] for t in self.trades if t['profit_loss'] > 0) / sum(t['profit_loss'] for t in self.trades if t['profit_loss'] < 0)) if sum(t['profit_loss'] for t in self.trades if t['profit_loss'] < 0) != 0 else 0
        return {
            'total_trades': len(self.trades),
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }

# ============================================================
# PAPER TRADING ENGINE
# ============================================================

class PaperTradingEngine:
    """Simulates trades without real money."""
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
            self.portfolio[symbol]['avg_price'] = (
                (self.portfolio[symbol]['avg_price'] * self.portfolio[symbol]['quantity_old'] + price * quantity) / 
                (self.portfolio[symbol]['quantity'] + quantity)
            )
        else:
            self.portfolio[symbol] = {'quantity': quantity, 'avg_price': price, 'quantity_old': 0}
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
        pnl = (price - self.portfolio[symbol]['avg_price']) * quantity
        self.trade_journal.log_trade(symbol, self.portfolio[symbol]['avg_price'], price, quantity, datetime.now(), datetime.now(), pnl)
        print(f"✅ SELL {quantity} {symbol} @ PKR {price:.2f} | PnL: PKR {pnl:.2f}")
        if self.portfolio[symbol]['quantity'] == 0:
            del self.portfolio[symbol]
        return True
    
    def get_summary(self):
        positions_value = 0
        for symbol, pos in self.portfolio.items():
            # We don't have current price here, will be updated in main
            pass
        return {
            'balance': self.balance,
            'total_value': self.balance + positions_value,
            'initial_balance': self.initial_balance,
            'return_pct': ((self.balance + positions_value) / self.initial_balance - 1) * 100,
            'positions': self.portfolio
        }

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
    invalid = ["CEMENT", "FERTILIZER", "BANKING", "TEXTILE", "ENERGY", "OIL", "GAS"]
    if symbol in invalid:
        return False
    return symbol in VALID_SHARIAH_TICKERS

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

# ============================================================
# 1. DATA FETCHING
# ============================================================

def fetch_top_shariah_compliant_stocks(limit=50):
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
        return VALID_SHARIAH_TICKERS[:limit]

def fetch_stock_quote(symbol):
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

def fetch_stock_fundamentals(symbol):
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

def fetch_historical_data(symbol, days=365):
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
# 2. ADVANCED TECHNICAL INDICATORS (TA-Lib + Manual)
# ============================================================

def calculate_advanced_indicators(df):
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
            indicators['willr'] = talib.WILLR(high, low, close, timeperiod=14)[-1]
            indicators['cci'] = talib.CCI(high, low, close, timeperiod=14)[-1]
            indicators['mfi'] = talib.MFI(high, low, close, volume, timeperiod=14)[-1]
            indicators['aroon_down'], indicators['aroon_up'] = talib.AROON(high, low, timeperiod=14)
            indicators['aroon_down'] = indicators['aroon_down'][-1]
            indicators['aroon_up'] = indicators['aroon_up'][-1]
        except Exception as e:
            TA_LIB_AVAILABLE_FOR_THIS = False
        else:
            TA_LIB_AVAILABLE_FOR_THIS = True
    else:
        TA_LIB_AVAILABLE_FOR_THIS = False
    
    if not TA_LIB_AVAILABLE_FOR_THIS:
        # Manual fallback for key indicators
        delta = close_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1] if len(rs) > 0 else None
        exp1 = close_series.ewm(span=12, adjust=False).mean()
        exp2 = close_series.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        indicators['macd'] = macd.iloc[-1] if len(macd) > 0 else None
        indicators['macd_signal'] = signal.iloc[-1] if len(signal) > 0 else None
        indicators['macd_hist'] = (macd - signal).iloc[-1] if len(macd) > 0 and len(signal) > 0 else None
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
        try:
            low_14 = low_series.rolling(14).min()
            high_14 = high_series.rolling(14).max()
            stoch_k = 100 * ((close_series - low_14) / (high_14 - low_14))
            indicators['stoch_k'] = stoch_k.iloc[-1] if len(stoch_k) > 0 else None
            indicators['stoch_d'] = stoch_k.rolling(3).mean().iloc[-1] if len(stoch_k) >= 3 else None
        except:
            indicators['stoch_k'] = None
            indicators['stoch_d'] = None
        sma_20 = close_series.rolling(20).mean()
        std_20 = close_series.rolling(20).std()
        indicators['bb_upper'] = sma_20.iloc[-1] + 2 * std_20.iloc[-1] if len(sma_20) > 0 else None
        indicators['bb_middle'] = sma_20.iloc[-1] if len(sma_20) > 0 else None
        indicators['bb_lower'] = sma_20.iloc[-1] - 2 * std_20.iloc[-1] if len(sma_20) > 0 else None
        indicators['sma_20'] = close_series.tail(20).mean() if len(close_series) >= 20 else None
        indicators['sma_50'] = close_series.tail(50).mean() if len(close_series) >= 50 else None
        indicators['sma_200'] = close_series.tail(200).mean() if len(close_series) >= 200 else None
        indicators['ema_12'] = close_series.ewm(span=12, adjust=False).mean().iloc[-1] if len(close_series) >= 12 else None
        indicators['ema_26'] = close_series.ewm(span=26, adjust=False).mean().iloc[-1] if len(close_series) >= 26 else None
        indicators['volume_sma'] = volume_series.tail(20).mean() if len(volume_series) >= 20 else None
        indicators['volume_ratio'] = volume_series.iloc[-1] / indicators['volume_sma'] if indicators['volume_sma'] and indicators['volume_sma'] > 0 else None
        indicators['obv'] = None
        indicators['willr'] = None
        indicators['cci'] = None
        indicators['mfi'] = None
        indicators['aroon_down'] = None
        indicators['aroon_up'] = None
    
    # BB Position
    if indicators.get('bb_upper') and indicators.get('bb_lower') and indicators.get('bb_middle'):
        if indicators['bb_upper'] != indicators['bb_lower']:
            indicators['bb_position'] = ((close[-1] - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower']))
        else:
            indicators['bb_position'] = 0.5
    else:
        indicators['bb_position'] = None
    
    return indicators

# ============================================================
# 3. MACHINE LEARNING PREDICTORS
# ============================================================

def train_lstm_model(df, lookback=60):
    """Train LSTM model for price prediction."""
    if not TF_AVAILABLE or df is None or len(df) < lookback + 10:
        return None
    try:
        close_col = None
        for col in df.columns:
            if 'close' in col.lower() or 'adj close' in col.lower():
                close_col = col
                break
        if close_col is None:
            close_col = df.columns[3] if len(df.columns) > 3 else df.columns[0]
        data = df[close_col].values
        # Normalize
        data_norm = (data - np.mean(data)) / np.std(data)
        X, y = [], []
        for i in range(lookback, len(data_norm) - 1):
            X.append(data_norm[i-lookback:i])
            y.append(data_norm[i])
        X = np.array(X).reshape(-1, lookback, 1)
        y = np.array(y)
        if len(X) < 10:
            return None
        # Build LSTM
        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(lookback, 1)),
            Dropout(0.2),
            LSTM(50, return_sequences=False),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse')
        model.fit(X, y, epochs=20, batch_size=32, verbose=0)
        return model
    except:
        return None

def lstm_predict(model, data, lookback=60):
    """Predict next price using LSTM model."""
    if model is None or len(data) < lookback:
        return None
    try:
        data_norm = (data - np.mean(data)) / np.std(data)
        X_input = data_norm[-lookback:].reshape(1, lookback, 1)
        pred_norm = model.predict(X_input, verbose=0)[0][0]
        mean = np.mean(data)
        std = np.std(data)
        return pred_norm * std + mean
    except:
        return None

def ensemble_ml_predictor(df):
    """Ensemble of Linear Regression, Random Forest, and LSTM."""
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
        
        predictions = []
        weights = []
        
        # 1. Linear Regression
        if SKLEARN_AVAILABLE:
            try:
                X = np.array(range(len(prices))).reshape(-1, 1)
                y = prices
                model = LinearRegression()
                model.fit(X, y)
                future_idx = len(prices) + 5
                pred_price = model.predict([[future_idx]])[0]
                pct_change = (pred_price / prices[-1] - 1) * 100
                r2 = model.score(X, y)
                predictions.append(pct_change)
                weights.append(r2 if r2 > 0 else 0.1)
            except:
                pass
        
        # 2. Random Forest
        if SKLEARN_AVAILABLE:
            try:
                X = np.array(range(len(prices))).reshape(-1, 1)
                y = prices
                model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
                model.fit(X, y)
                future_idx = len(prices) + 5
                pred_price = model.predict([[future_idx]])[0]
                pct_change = (pred_price / prices[-1] - 1) * 100
                predictions.append(pct_change)
                weights.append(0.8)
            except:
                pass
        
        # 3. LSTM (if available)
        if TF_AVAILABLE:
            try:
                model = train_lstm_model(df)
                if model:
                    pred_price = lstm_predict(model, prices)
                    if pred_price:
                        pct_change = (pred_price / prices[-1] - 1) * 100
                        predictions.append(pct_change)
                        weights.append(1.0)
            except:
                pass
        
        if predictions:
            # Weighted average
            weighted_avg = sum(p * w for p, w in zip(predictions, weights)) / sum(weights)
            confidence = min(1.0, sum(weights) / 3)
            if weighted_avg > 2:
                pred = 'up'
            elif weighted_avg < -2:
                pred = 'down'
            else:
                pred = 'neutral'
            return {
                'prediction': pred,
                'pct_change': weighted_avg,
                'confidence': confidence,
                'models_used': len(predictions),
                'ensemble_size': len(predictions)
            }
        else:
            return {'prediction': 'neutral', 'confidence': 0.0}
    except Exception as e:
        return {'prediction': 'neutral', 'confidence': 0.0, 'error': str(e)}

# ============================================================
# 4. SENTIMENT ANALYSIS
# ============================================================

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
                subjectivity = blob.sentiment.subjectivity
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
# 5. RISK MANAGEMENT & POSITION SIZING
# ============================================================

def calculate_kelly_position(win_rate, avg_win, avg_loss, max_fraction=0.25):
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    if b <= 0:
        return 0.0
    kelly = (b * p - q) / b
    return max(0.0, min(kelly, max_fraction))

def dynamic_position_sizing(account_balance, entry_price, stop_loss_price, win_rate_est, avg_win_est, avg_loss_est, risk_per_trade=0.02):
    if entry_price <= 0 or stop_loss_price >= entry_price:
        return 0
    risk_per_share = entry_price - stop_loss_price
    if risk_per_share <= 0:
        return 0
    # Kelly-adjusted risk
    kelly = calculate_kelly_position(win_rate_est, avg_win_est, avg_loss_est)
    risk_amount = account_balance * (risk_per_trade + kelly * 0.5)
    shares = risk_amount / risk_per_share
    return int(max(0, shares))

# ============================================================
# 6. ULTIMATE SIGNAL GENERATION (Multi-Model Ensemble)
# ============================================================

def generate_ultimate_signals(symbol, price, indicators, ml_pred, sentiment, fundamentals, historical_df):
    """Multi-model ensemble signal generation."""
    signals = []
    if not indicators or price is None:
        return {'primary': '⏳ NEUTRAL', 'details': [], 'score': 0}
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            return {'primary': '⏳ NEUTRAL', 'details': [], 'score': 0}
    if not isinstance(price, (int, float)):
        return {'primary': '⏳ NEUTRAL', 'details': [], 'score': 0}
    
    ensemble_score = 0
    signal_details = []
    
    # 1. RSI (weight: 2)
    rsi = indicators.get('rsi')
    if rsi is not None:
        if rsi < 30:
            ensemble_score += 2
            signal_details.append({'model': 'RSI', 'signal': 'BUY', 'weight': 2, 'value': rsi, 'reason': f'Oversold ({rsi:.2f} < 30)'})
        elif rsi > 70:
            ensemble_score -= 2
            signal_details.append({'model': 'RSI', 'signal': 'SELL', 'weight': -2, 'value': rsi, 'reason': f'Overbought ({rsi:.2f} > 70)'})
        else:
            signal_details.append({'model': 'RSI', 'signal': 'NEUTRAL', 'weight': 0, 'value': rsi, 'reason': f'Neutral ({rsi:.2f})'})
    
    # 2. MACD (weight: 1.5)
    macd = indicators.get('macd')
    macd_signal = indicators.get('macd_signal')
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            ensemble_score += 1.5
            signal_details.append({'model': 'MACD', 'signal': 'BUY', 'weight': 1.5, 'value': macd, 'reason': 'Bullish crossover'})
        else:
            ensemble_score -= 1.5
            signal_details.append({'model': 'MACD', 'signal': 'SELL', 'weight': -1.5, 'value': macd, 'reason': 'Bearish crossover'})
    
    # 3. ADX (weight: 1)
    adx = indicators.get('adx')
    if adx is not None and adx > 25:
        ensemble_score += 1
        signal_details.append({'model': 'ADX', 'signal': 'TRENDING', 'weight': 1, 'value': adx, 'reason': f'Strong trend ({adx:.2f} > 25)'})
    
    # 4. Stochastic (weight: 1.5)
    stoch_k = indicators.get('stoch_k')
    stoch_d = indicators.get('stoch_d')
    if stoch_k is not None and stoch_d is not None:
        if stoch_k < 20 and stoch_d < 20:
            ensemble_score += 1.5
            signal_details.append({'model': 'Stochastic', 'signal': 'BUY', 'weight': 1.5, 'value': f'K={stoch_k:.2f}, D={stoch_d:.2f}', 'reason': 'Oversold crossover'})
        elif stoch_k > 80 and stoch_d > 80:
            ensemble_score -= 1.5
            signal_details.append({'model': 'Stochastic', 'signal': 'SELL', 'weight': -1.5, 'value': f'K={stoch_k:.2f}, D={stoch_d:.2f}', 'reason': 'Overbought crossover'})
    
    # 5. Bollinger Bands (weight: 1)
    bb_position = indicators.get('bb_position')
    if bb_position is not None:
        if bb_position < 0.2:
            ensemble_score += 1
            signal_details.append({'model': 'Bollinger', 'signal': 'BUY', 'weight': 1, 'value': bb_position, 'reason': 'At lower band'})
        elif bb_position > 0.8:
            ensemble_score -= 1
            signal_details.append({'model': 'Bollinger', 'signal': 'SELL', 'weight': -1, 'value': bb_position, 'reason': 'At upper band'})
    
    # 6. Aroon (weight: 0.5)
    aroon_up = indicators.get('aroon_up')
    aroon_down = indicators.get('aroon_down')
    if aroon_up is not None and aroon_down is not None:
        if aroon_up > 70 and aroon_down < 30:
            ensemble_score += 0.5
            signal_details.append({'model': 'Aroon', 'signal': 'BUY', 'weight': 0.5, 'value': f'U={aroon_up:.2f}, D={aroon_down:.2f}', 'reason': 'Bullish crossover'})
        elif aroon_down > 70 and aroon_up < 30:
            ensemble_score -= 0.5
            signal_details.append({'model': 'Aroon', 'signal': 'SELL', 'weight': -0.5, 'value': f'U={aroon_up:.2f}, D={aroon_down:.2f}', 'reason': 'Bearish crossover'})
    
    # 7. ML Prediction (weight: 1)
    if ml_pred and ml_pred.get('prediction') != 'neutral' and ml_pred.get('confidence', 0) > 0.2:
        if ml_pred['prediction'] == 'up':
            ensemble_score += 1
            signal_details.append({'model': 'ML', 'signal': 'BUY', 'weight': 1, 'value': f"{ml_pred.get('pct_change', 0):.2f}%", 'reason': f"Predicted up {ml_pred.get('pct_change', 0):.1f}%"})
        else:
            ensemble_score -= 1
            signal_details.append({'model': 'ML', 'signal': 'SELL', 'weight': -1, 'value': f"{ml_pred.get('pct_change', 0):.2f}%", 'reason': f"Predicted down {abs(ml_pred.get('pct_change', 0)):.1f}%"})
    
    # 8. Sentiment (weight: 0.5)
    if sentiment and sentiment.get('overall') != 'neutral':
        if sentiment['overall'] == 'bullish':
            ensemble_score += 0.5
            signal_details.append({'model': 'Sentiment', 'signal': 'BULLISH', 'weight': 0.5, 'value': sentiment.get('avg_polarity', 0), 'reason': 'Positive news sentiment'})
        else:
            ensemble_score -= 0.5
            signal_details.append({'model': 'Sentiment', 'signal': 'BEARISH', 'weight': -0.5, 'value': sentiment.get('avg_polarity', 0), 'reason': 'Negative news sentiment'})
    
    # 9. Fundamentals (weight: 0.5)
    if fundamentals:
        pe = fundamentals.get('pe')
        div_yield = fundamentals.get('div_yield')
        if pe is not None and pe != 'N/A' and isinstance(pe, (int, float)) and pe < 15:
            ensemble_score += 0.5
            signal_details.append({'model': 'Fundamental (PE)', 'signal': 'BUY', 'weight': 0.5, 'value': pe, 'reason': f'Low P/E ({pe:.2f})'})
        if div_yield is not None and div_yield != 'N/A' and isinstance(div_yield, (int, float)) and div_yield > 5:
            ensemble_score += 0.5
            signal_details.append({'model': 'Fundamental (Div)', 'signal': 'BUY', 'weight': 0.5, 'value': div_yield, 'reason': f'High yield ({div_yield:.2f}%)'})
    
    # Determine signal strength
    confidence = min(1.0, abs(ensemble_score) / 10)
    
    if ensemble_score > 3:
        primary = "🟢 STRONG BUY"
        timing = "Immediate — market open"
        priority = "HIGH"
        recommended_action = "BUY"
    elif ensemble_score > 1.5:
        primary = "🟢 BUY"
        timing = "Buy on dips"
        priority = "MEDIUM"
        recommended_action = "BUY"
    elif ensemble_score < -3:
        primary = "🔴 STRONG SELL"
        timing = "Sell immediately"
        priority = "HIGH"
        recommended_action = "SELL"
    elif ensemble_score < -1.5:
        primary = "🔴 SELL"
        timing = "Take profits now"
        priority = "MEDIUM"
        recommended_action = "SELL"
    else:
        primary = "⏳ NEUTRAL"
        timing = "Wait for breakout"
        priority = "LOW"
        recommended_action = "WAIT"
    
    return {
        'primary': primary,
        'timing': timing,
        'priority': priority,
        'action': recommended_action,
        'details': signal_details,
        'ensemble_score': ensemble_score,
        'confidence': confidence,
        'buy_count': sum(1 for s in signal_details if 'BUY' in s.get('signal', '') or 'BULLISH' in s.get('signal', '')),
        'sell_count': sum(1 for s in signal_details if 'SELL' in s.get('signal', '') or 'BEARISH' in s.get('signal', ''))
    }

# ============================================================
# 7. ENTRY/EXIT WITH KELLY POSITION SIZING
# ============================================================

def calculate_ultimate_entry_exit(symbol, price, signal, indicators, account_balance=30000, risk_per_trade=0.02):
    if price is None or not isinstance(price, (int, float)):
        return {
            'entry_price': 'N/A',
            'target_price': 'N/A',
            'stop_loss': 'N/A',
            'position_size': 0,
            'entry_timing': 'N/A',
            'exit_timing': 'N/A',
            'risk_amount': 0,
            'potential_profit': 0,
            'kelly_fraction': 0,
            'win_rate_est': 0
        }
    
    atr = indicators.get('atr', price * 0.02) if indicators else price * 0.02
    if atr is None or atr <= 0:
        atr = price * 0.02
    
    if signal.get('action') == 'BUY':
        entry = price
        stop = price - 2 * atr
        target = price + 4 * atr
        timing = signal.get('timing', 'Market open')
        direction = 'long'
    elif signal.get('action') == 'SELL':
        entry = price
        stop = price + 2 * atr
        target = price - 4 * atr
        timing = signal.get('timing', 'Sell now')
        direction = 'short'
    else:
        entry = price
        stop = price - 2 * atr
        target = price + 4 * atr
        timing = 'Wait'
        direction = 'neutral'
    
    # Estimate win rate from ensemble score
    score = signal.get('ensemble_score', 0)
    win_rate = 0.5 + (score / 10)
    win_rate = max(0.3, min(0.7, win_rate))
    
    avg_win = target - entry if direction == 'long' else entry - target
    avg_loss = entry - stop if direction == 'long' else stop - entry
    if avg_loss <= 0:
        kelly_fraction = 0.02
    else:
        kelly = calculate_kelly_position(win_rate, avg_win, avg_loss)
        kelly_fraction = kelly if kelly > 0 else 0.02
    
    shares = dynamic_position_sizing(account_balance, entry, stop, win_rate, avg_win, avg_loss, risk_per_trade)
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
# 8. BACKTESTING ENGINE
# ============================================================

class BacktestingEngine:
    """Backtest strategies on historical data."""
    def __init__(self, initial_balance=30000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.portfolio = {}
        self.trades = []
    
    def run_backtest(self, historical_df, signal_generator, symbol, lookback=90):
        """Run backtest on historical data."""
        if historical_df is None or len(historical_df) < lookback:
            return {'error': 'Insufficient data'}
        
        # Simulate trading over the historical period
        close_col = None
        for col in historical_df.columns:
            if 'close' in col.lower() or 'adj close' in col.lower():
                close_col = col
                break
        if close_col is None:
            close_col = historical_df.columns[3] if len(historical_df.columns) > 3 else historical_df.columns[0]
        
        prices = historical_df[close_col].values
        if len(prices) < lookback:
            return {'error': 'Insufficient data'}
        
        # Simple strategy: buy when signal is BUY, sell when signal is SELL
        shares_held = 0
        entry_price = 0
        total_pnl = 0
        trades = []
        
        for i in range(lookback, len(prices) - 1):
            # Generate signal based on historical data
            df_slice = historical_df.iloc[i-lookback:i]
            indicators = calculate_advanced_indicators(df_slice)
            if not indicators:
                continue
            
            # Simplified signal: RSI-based
            rsi = indicators.get('rsi')
            if rsi is None:
                continue
            
            price = prices[i]
            next_price = prices[i+1]
            
            if rsi < 30 and shares_held == 0:
                # Buy
                shares_held = int(self.balance / price)
                entry_price = price
                self.balance -= shares_held * price
                trades.append({'type': 'BUY', 'price': price, 'date': df_slice.index[-1] if hasattr(df_slice, 'index') else i})
            elif rsi > 70 and shares_held > 0:
                # Sell
                pnl = shares_held * (price - entry_price)
                total_pnl += pnl
                self.balance += shares_held * price
                trades.append({'type': 'SELL', 'price': price, 'pnl': pnl, 'date': df_slice.index[-1] if hasattr(df_slice, 'index') else i})
                shares_held = 0
        
        # Close remaining position
        if shares_held > 0:
            final_price = prices[-1]
            pnl = shares_held * (final_price - entry_price)
            total_pnl += pnl
            self.balance += shares_held * final_price
            trades.append({'type': 'SELL (close)', 'price': final_price, 'pnl': pnl, 'date': 'end'})
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_pnl': total_pnl,
            'return_pct': ((self.balance / self.initial_balance) - 1) * 100,
            'trades': trades,
            'num_trades': len(trades),
            'win_rate': len([t for t in trades if t.get('pnl', 0) > 0]) / len(trades) if trades else 0
        }

# ============================================================
# 9. REPORT GENERATION (ULTIMATE)
# ============================================================

def generate_ultimate_report(quotes, fundamentals, indicators, ml_predictions, sentiment_data,
                             signals, entry_exit, market_pulse, index_summary, sector_data,
                             stock_symbols, csf_symbols, paper_engine, backtest_results,
                             account_balance=30000, trade_journal=None):
    """Generate the ultimate HTML report with all data."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    index_html = df_to_html(index_summary, 10)
    gainers_html = df_to_html(market_pulse.get('gainers'), 5)
    losers_html = df_to_html(market_pulse.get('losers'), 5)
    active_html = df_to_html(market_pulse.get('active'), 5)
    sectors_html = df_to_html(sector_data, 10)
    
    # Journal summary
    journal_summary = trade_journal.get_summary() if trade_journal else {}
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; background: #0a0a0a; }}
            .header {{ background: linear-gradient(135deg, #0a1628, #1a3a5c); color: #00ff88; padding: 20px; text-align: center; border-bottom: 2px solid #00ff88; }}
            .header h1 {{ margin: 0; color: #00ff88; }}
            .header p {{ margin: 5px 0; color: #aaa; }}
            .section {{ background: #1a1a2e; margin: 20px; padding: 20px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,255,136,0.1); border: 1px solid #2a2a4e; }}
            .section h2 {{ color: #00ff88; margin-top: 0; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
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
            .highlight {{ background: rgba(255,170,0,0.2); padding: 2px 6px; border-radius: 3px; color: #ffaa00; }}
            .futures-section {{ background: rgba(0,100,200,0.1); padding: 15px; border-radius: 5px; margin: 10px 0; border: 1px solid #0066cc; }}
            .risk-section {{ background: rgba(0,255,136,0.05); padding: 15px; border-radius: 5px; margin: 10px 0; border: 1px solid #00ff88; }}
            .ml-section {{ background: rgba(255,170,0,0.05); padding: 15px; border-radius: 5px; margin: 10px 0; border: 1px solid #ffaa00; }}
            .backtest-section {{ background: rgba(100,0,200,0.05); padding: 15px; border-radius: 5px; margin: 10px 0; border: 1px solid #6600cc; }}
            .journal-section {{ background: rgba(0,200,255,0.05); padding: 15px; border-radius: 5px; margin: 10px 0; border: 1px solid #00ccff; }}
            .profit {{ color: #00ff88; }}
            .loss {{ color: #ff4444; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ PSX ULTIMATE PROFIT ENGINE — BLACK BOX v3.0</h1>
            <p>Generated on {now}</p>
            <p>💰 Account: PKR {account_balance:,.0f} | 📊 {len(stock_symbols)} Shariah Stocks | 🧠 {len(csf_symbols)} CSF Securities</p>
            <p>📈 TA-Lib: {'✅' if TA_LIB_AVAILABLE else '❌'} | 🤖 ML: {'✅' if SKLEARN_AVAILABLE else '❌'} | 🧠 LSTM: {'✅' if TF_AVAILABLE else '❌'}</p>
            <p>📋 Paper Trading: {'🟢 ACTIVE' if PAPER_TRADING else '🔴 DISABLED'}</p>
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

        <div class="section ml-section">
            <h2>🧠 ML & Sentiment Insights</h2>
            <p><strong>Overall Sentiment:</strong> {sentiment_data.get('overall', 'neutral').upper()} (Polarity: {sentiment_data.get('avg_polarity', 0):.3f})</p>
            <p><strong>News Headlines:</strong></p>
            <ul>
    """
    for article in sentiment_data.get('articles', [])[:5]:
        color = '#00ff88' if article['sentiment'] == 'bullish' else '#ff4444' if article['sentiment'] == 'bearish' else '#ffaa00'
        html += f"<li style='color:#ccc;'><span style='color:{color};'>{article['sentiment'].upper()}</span> — {article['title'][:100]}...</li>"
    html += """
            </ul>
        </div>

        <div class="section risk-section">
            <h2>🛡️ Risk Management</h2>
            <p><strong>Account Balance:</strong> PKR {account_balance:,.0f}</p>
            <p><strong>Max Risk per Trade:</strong> {risk_pct:.1f}% (PKR {risk_amt:,.0f})</p>
            <p><strong>Kelly Criterion:</strong> Dynamic position sizing</p>
            <p><strong>Stop Loss:</strong> 2× ATR | <strong>Take Profit:</strong> 4× ATR</p>
        </div>

        <div class="section backtest-section">
            <h2>📊 Backtest Results</h2>
            <p><strong>Initial Balance:</strong> PKR {bt_initial}</p>
            <p><strong>Final Balance:</strong> PKR {bt_final}</p>
            <p><strong>Total P&L:</strong> <span class="{'profit' if bt_pnl > 0 else 'loss'}">PKR {bt_pnl:,.2f}</span></p>
            <p><strong>Return:</strong> <span class="{'profit' if bt_return > 0 else 'loss'}">{bt_return:.2f}%</span></p>
            <p><strong>Win Rate:</strong> {bt_winrate:.1f}%</p>
            <p><strong>Trades:</strong> {bt_trades}</p>
        </div>

        <div class="section journal-section">
            <h2>📋 Trade Journal</h2>
            <p><strong>Total Trades:</strong> {journal.get('total_trades', 0)}</p>
            <p><strong>Total P&L:</strong> <span class="{'profit' if journal.get('total_pnl', 0) > 0 else 'loss'}">PKR {journal.get('total_pnl', 0):,.2f}</span></p>
            <p><strong>Win Rate:</strong> {journal.get('win_rate', 0)*100:.1f}%</p>
            <p><strong>Profit Factor:</strong> {journal.get('profit_factor', 0):.2f}</p>
        </div>

        <div class="section">
            <h2>🎯 Ultimate Trading Signals</h2>
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
                        <th>Shares</th>
                        <th>Risk (PKR)</th>
                        <th>Profit (PKR)</th>
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
        html += f"""
            <tr class="signal-{signal_class}">
                <td><strong style="color:#00ff88;">{symbol}</strong></td>
                <td>{price}</td>
                <td class="{signal_class}">{primary}</td>
                <td>{sig.get('ensemble_score', 0):.1f}</td>
                <td>{ee.get('entry_price', 'N/A')}</td>
                <td>{ee.get('target_price', 'N/A')}</td>
                <td>{ee.get('stop_loss', 'N/A')}</td>
                <td>{ee.get('position_size', 0)}</td>
                <td class="{'profit' if ee.get('risk_amount', 0) > 0 else 'loss'}">{ee.get('risk_amount', 0):.2f}</td>
                <td class="{'profit' if ee.get('potential_profit', 0) > 0 else 'loss'}">{ee.get('potential_profit', 0):.2f}</td>
            </tr>
        """
    html += """
                </tbody>
            </table>
        </div>

        <div class="section futures-section">
            <h2>📈 CSF Futures Eligible Securities</h2>
            <p><strong>Total:</strong> {len(csf_symbols)} securities | <strong>Contract:</strong> 500 shares | <strong>Period:</strong> 90 days</p>
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
            <h2>📋 Execution Summary</h2>
            <h3 style="color: #00ff88;">🟢 BUY NOW</h3>
            <p>{buy_list}</p>
            <h3 style="color: #ffaa00;">🟡 HOLD / WAIT</h3>
            <p>{hold_list}</p>
            <h3 style="color: #ff4444;">🔴 SELL / TAKE PROFIT</h3>
            <p>{sell_list}</p>
        </div>

        <div class="footer">
            <p>🕌 All stocks Shariah-compliant (KMI All Share Index)</p>
            <p>🧠 Multi-Model Ensemble: RSI + MACD + ADX + Stoch + BB + Aroon + ML + Sentiment + Fundamentals</p>
            <p>📊 Backtesting: {bt_return:.2f}% return | Win Rate: {bt_winrate:.1f}%</p>
            <p>⚠️ Informational only. Always do your own research.</p>
            <p>⚡ Generated by PSX Ultimate Profit Engine v3.0 — Black Box Edition</p>
        </div>
    </body>
    </html>
    """
    return html

# ============================================================
# 10. EMAIL SENDING
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
# 11. MAIN EXECUTION
# ============================================================

def main():
    print("⚡ PSX ULTIMATE PROFIT ENGINE — BLACK BOX EDITION v3.0")
    print("=" * 70)
    print(f"💰 Starting Balance: PKR {ACCOUNT_BALANCE:,.0f}")
    print(f"📋 Paper Trading: {'ACTIVE' if PAPER_TRADING else 'DISABLED'}")
    print(f"🧠 TA-Lib: {'✅' if TA_LIB_AVAILABLE else '❌'}")
    print(f"🤖 ML: {'✅' if SKLEARN_AVAILABLE else '❌'}")
    print(f"🧠 LSTM: {'✅' if TF_AVAILABLE else '❌'}")
    print("=" * 70)
    
    # 1. Fetch stocks
    stock_symbols = fetch_top_shariah_compliant_stocks(limit=50)
    stock_symbols = [s for s in stock_symbols if is_valid_ticker(s)]
    print(f"📊 Tracking {len(stock_symbols)} Shariah stocks")
    
    # 2. CSF eligible
    csf_symbols = VALID_SHARIAH_TICKERS.copy()
    
    # 3. Fetch data
    print("📡 Fetching data...")
    quotes = {}
    fundamentals = {}
    historical_data = {}
    for sym in stock_symbols:
        quotes[sym] = fetch_stock_quote(sym)
        fundamentals[sym] = fetch_stock_fundamentals(sym)
        historical_data[sym] = fetch_historical_data(sym, days=365)
    
    # 4. Market data
    market_pulse = fetch_market_pulse()
    index_summary = fetch_index_summary()
    sector_data = fetch_sector_performance()
    
    # 5. Advanced indicators
    print("📊 Calculating indicators...")
    indicators = {}
    ml_predictions = {}
    for sym, hist in historical_data.items():
        indicators[sym] = calculate_advanced_indicators(hist)
        ml_predictions[sym] = ensemble_ml_predictor(hist)
    
    # 6. Sentiment
    print("📰 Fetching news sentiment...")
    sentiment_data = fetch_news_sentiment()
    
    # 7. Paper trading engine
    paper_engine = PaperTradingEngine(ACCOUNT_BALANCE)
    trade_journal = TradeJournal()
    
    # 8. Backtest
    print("📊 Running backtest...")
    backtest_results = {}
    for sym in stock_symbols[:10]:
        bt = BacktestingEngine(ACCOUNT_BALANCE)
        result = bt.run_backtest(historical_data.get(sym), None, sym)
        if result and 'error' not in result:
            backtest_results[sym] = result
    
    # 9. Generate signals
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
        
        sig = generate_ultimate_signals(
            sym, price, indicators.get(sym, {}),
            ml_predictions.get(sym, {}),
            sentiment_data,
            fundamentals.get(sym, {}),
            historical_data.get(sym)
        )
        signals[sym] = sig
        ee = calculate_ultimate_entry_exit(
            sym, price, sig, indicators.get(sym, {}),
            ACCOUNT_BALANCE, MAX_RISK_PER_TRADE
        )
        entry_exit[sym] = ee
        
        # Log signal
        trade_journal.log_signal(sym, sig.get('primary', 'NEUTRAL'), sig.get('confidence', 0), len(sig.get('details', [])))
        
        # Paper trade simulation (simple)
        if PAPER_TRADING and price and isinstance(price, (int, float)):
            if sig.get('action') == 'BUY' and ee.get('position_size', 0) > 0:
                paper_engine.buy(sym, price, ee.get('position_size', 0))
            elif sig.get('action') == 'SELL' and sym in paper_engine.portfolio:
                paper_engine.sell(sym, price)
    
    # 10. Generate report
    print("📝 Generating ultimate HTML report...")
    html_report = generate_ultimate_report(
        quotes, fundamentals, indicators, ml_predictions, sentiment_data,
        signals, entry_exit, market_pulse, index_summary, sector_data,
        stock_symbols, csf_symbols, paper_engine, backtest_results,
        ACCOUNT_BALANCE, trade_journal
    )
    
    # 11. Send email
    subject = f"⚡ PSX Ultimate Report - {len(stock_symbols)} Stocks - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    success = send_html_email(subject, html_report)
    if success:
        print("✅ Report sent!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
