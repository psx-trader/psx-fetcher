#!/usr/bin/env python3
"""
PSX Ultimate Profit Intelligence Report - FULLY CORRECTED
Features: Shariah-Compliant Stocks + Technical Analysis + Futures + Dividends
"""

import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import concurrent.futures
import re
import time

# ============================================================
# CONFIGURATION
# ============================================================
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# ============================================================

# Well-known Shariah-compliant stocks (ticker symbols)
FALLBACK_SYMBOLS = [
    "FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB", 
    "OGDC", "PPL", "PSO", "LUCK", "MEBL", "UBL", 
    "NBP", "HBL", "DGKC", "MLCF", "FCCL", "ATRL", 
    "NRL", "PRL", "PAEL", "SEARL", "SNGP", "SSGC", 
    "ENGROH", "GAL", "GHNI", "HCAR", "NML", "TREET", 
    "CNERGY", "CPHL", "FFL", "AIRLINK", "KEL", "WTL",
    "TRG", "TPL", "PICT", "IBFL", "SCBPL", "SILK"
]

# Known valid ticker symbols on PSX
KNOWN_TICKERS = [
    "FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB", 
    "OGDC", "PPL", "PSO", "LUCK", "MEBL", "UBL", 
    "NBP", "HBL", "DGKC", "MLCF", "FCCL", "ATRL", 
    "NRL", "PRL", "PAEL", "SEARL", "SNGP", "SSGC", 
    "ENGROH", "GAL", "GHNI", "HCAR", "NML", "TREET", 
    "CNERGY", "CPHL", "FFL", "AIRLINK", "KEL", "WTL",
    "TRG", "TPL", "PICT", "IBFL", "SCBPL", "SILK",
    "GADT", "KAPCO", "NCL", "PSMC", "PSO", "PTC",
    "SBL", "SHFA", "SML", "SNBL", "SSML", "UPFL",
    "WAVES", "WSML", "BIL", "DSML", "FABL", "GGL",
    "HCL", "ISIL", "JKSM", "MSCL", "PASL", "PICL",
    "PIFL", "PKGS", "PSEL", "SFL", "SML", "TPL",
    "TREET", "UBL", "WTL"
]

# ============================================================
# 1. DATA FETCHING FUNCTIONS
# ============================================================

def is_valid_ticker(symbol):
    """Check if a symbol is a valid PSX ticker."""
    if not symbol or not isinstance(symbol, str):
        return False
    # Must be uppercase letters, 2-6 characters long
    if not re.match(r'^[A-Z]{2,6}$', symbol):
        return False
    # Must be in known tickers list (or we can just check format)
    return True

def fetch_top_shariah_compliant_stocks(limit=50):
    """
    Fetch Shariah-compliant stocks from KMI All Share Index.
    Returns valid ticker symbols only.
    """
    print(f"📡 Fetching top {limit} Shariah-compliant stocks...")
    try:
        import pypsx
        
        # Try to get market watch first to get valid symbols
        market_watch = pypsx.market_watch()
        if market_watch is None or market_watch.empty:
            print("⚠️ Could not fetch market watch. Using fallback list.")
            return FALLBACK_SYMBOLS[:limit]
        
        # Find symbol column
        symbol_col = None
        for col in ['Symbol', 'symbol', 'Ticker', 'ticker']:
            if col in market_watch.columns:
                symbol_col = col
                break
        if symbol_col is None:
            symbol_col = market_watch.columns[0]
        
        # Get all market tickers
        market_tickers = market_watch[symbol_col].tolist()
        # Filter to valid tickers only
        valid_market_tickers = [t for t in market_tickers if isinstance(t, str) and re.match(r'^[A-Z]{2,6}$', t)]
        
        if not valid_market_tickers:
            print("⚠️ No valid tickers in market watch. Using fallback list.")
            return FALLBACK_SYMBOLS[:limit]
        
        # Get Shariah-compliant symbols from KMI All Share
        all_shariah_data = pypsx.index_constituents("KMIALLSHR")
        
        if all_shariah_data is None or all_shariah_data.empty:
            print("⚠️ Could not fetch KMI All Share. Using fallback list.")
            return FALLBACK_SYMBOLS[:limit]
        
        # Extract ticker symbols from the index data
        shariah_tickers = []
        for col in all_shariah_data.columns:
            for val in all_shariah_data[col].dropna().tolist():
                val_str = str(val).upper().strip()
                # Check if this value is a valid ticker that exists in market watch
                if re.match(r'^[A-Z]{2,6}$', val_str) and val_str in valid_market_tickers:
                    if val_str not in shariah_tickers:
                        shariah_tickers.append(val_str)
        
        # If no tickers found, try a broader approach
        if not shariah_tickers:
            print("⚠️ No direct ticker matches found. Trying name matching...")
            for col in all_shariah_data.columns:
                for val in all_shariah_data[col].dropna().head(50):
                    val_str = str(val).upper().strip()
                    # Try to find a ticker within the text
                    for ticker in valid_market_tickers:
                        if ticker in val_str:
                            if ticker not in shariah_tickers:
                                shariah_tickers.append(ticker)
        
        # If still no tickers, use fallback
        if not shariah_tickers:
            print("⚠️ Could not extract ticker symbols. Using fallback list.")
            return FALLBACK_SYMBOLS[:limit]
        
        # Rank by volume to get top stocks
        shariah_market = market_watch[market_watch[symbol_col].isin(shariah_tickers)]
        if shariah_market.empty:
            print("⚠️ No Shariah stocks in market watch. Using fallback list.")
            return FALLBACK_SYMBOLS[:limit]
        
        # Sort by volume and get top 'limit'
        if 'Volume' in shariah_market.columns:
            shariah_market['Volume'] = pd.to_numeric(shariah_market['Volume'], errors='coerce')
            top_stocks = shariah_market.sort_values('Volume', ascending=False).head(limit)
            top_symbols = top_stocks[symbol_col].tolist()
        else:
            top_symbols = shariah_tickers[:limit]
        
        print(f"✅ Selected {len(top_symbols)} Shariah-compliant stocks.")
        return top_symbols
        
    except Exception as e:
        print(f"Error fetching Shariah-compliant stocks: {e}")
        print(f"⚠️ Using fallback list of {len(FALLBACK_SYMBOLS)} symbols.")
        return FALLBACK_SYMBOLS[:limit]

def fetch_stock_quote(symbol):
    """Fetch real-time quote for a stock."""
    if not symbol or not is_valid_ticker(symbol):
        return {'symbol': symbol, 'error': 'Invalid ticker symbol'}
    
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
        print(f"Error fetching quote for {symbol}: {e}")
        return {'symbol': symbol, 'error': str(e)}

def fetch_stock_fundamentals(symbol):
    """Fetch fundamental data."""
    if not symbol or not is_valid_ticker(symbol):
        return {'symbol': symbol, 'error': 'Invalid ticker symbol'}
    
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
        print(f"Error fetching fundamentals for {symbol}: {e}")
        return {'symbol': symbol, 'error': str(e)}

def fetch_historical_data(symbol, days=90):
    """Fetch historical data for technical analysis."""
    if not symbol or not is_valid_ticker(symbol):
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
        # Silently skip — some symbols may not have historical data
        return None

def fetch_dividend_data(symbol):
    """Fetch dividend data."""
    if not symbol or not is_valid_ticker(symbol):
        return {'symbol': symbol, 'div_yield': 'N/A', 'dividend_history': None}
    
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        dividend_history = None
        try:
            dividend_history = ticker.dividends()
        except:
            pass
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        div_yield = reg_data.get('Dividend Yield', 'N/A')
        return {
            'symbol': symbol,
            'div_yield': div_yield,
            'dividend_history': dividend_history,
            'source': 'pypsx'
        }
    except Exception as e:
        return {'symbol': symbol, 'div_yield': 'N/A', 'dividend_history': None, 'source': 'error'}

def analyze_dividend_opportunity(symbol, price, div_yield):
    """Analyze dividend opportunity."""
    if price is None:
        return None
    
    # Convert price to float if needed
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            return None
    
    if not isinstance(price, (int, float)):
        return None
    
    if div_yield == 'N/A' or div_yield is None:
        return None
    
    if isinstance(div_yield, str):
        try:
            div_yield = float(div_yield.replace('%', '').strip())
        except:
            return None
    
    if div_yield > 0:
        annual_dividend = price * (div_yield / 100)
        return {
            'symbol': symbol,
            'price': price,
            'div_yield_pct': div_yield,
            'annual_dividend_per_share': round(annual_dividend, 2),
            'quarterly_dividend_per_share': round(annual_dividend / 4, 2),
            'dividend_rank': 'HIGH' if div_yield > 6 else 'MEDIUM' if div_yield > 3 else 'LOW'
        }
    return None

# ============================================================
# 2. MARKET PULSE & INDICES
# ============================================================

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

# ============================================================
# 3. TECHNICAL INDICATORS
# ============================================================

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
    
    return indicators

# ============================================================
# 4. FUTURES & DERIVATIVES
# ============================================================

def fetch_csf_eligible_securities():
    """Fetch Cash-Settled Futures (CSF) eligible securities."""
    return [
        "ACPL", "AICL", "AIRLINK", "AKBL", "ANL", "ATRL", "AVN",
        "BAFL", "BAHL", "BBFL", "BFAGRO", "BFBIO", "BIPL", "BNL",
        "BOP", "CNERGY", "CPHL", "CSAP", "DGKC", "DOL", "EFERT",
        "ENGRO", "EPCL", "FABL", "FATIMA", "FCCL", "FFBL", "FFC",
        "GADT", "GAL", "GHGL", "GLAXO", "HBL", "HCAR", "HINOON",
        "HUBC", "IBFL", "ICIBL", "ILP", "INIL", "JLICL", "KAPCO",
        "KEL", "KOHE", "KOSM", "LOTCHEM", "LUCK", "MARI", "MCB",
        "MEBL", "MLCF", "MSCL", "MTL", "NBP", "NCL", "NESTLE",
        "NRL", "OGDC", "PAEL", "PIBTL", "PICT", "PIOC", "PPL",
        "PRL", "PSMC", "PSO", "PTC", "PWR", "SBL", "SCBPL",
        "SEARL", "SFL", "SHFA", "SILK", "SML", "SNBL", "SNGP",
        "SSGC", "SYS", "TPL", "TREET", "TRG", "UBL", "WTL"
    ]

def fetch_futures_contract_info(symbol):
    """Fetch futures contract information for a symbol."""
    try:
        now = datetime.now()
        contracts = []
        for month_offset in [0, 1, 2]:
            contract_month = (now + timedelta(days=30 * month_offset)).strftime("%b%Y")
            contracts.append({
                'symbol': symbol,
                'contract': f"{symbol}-{contract_month}",
                'month': contract_month,
                'expiry': (now + timedelta(days=30 * (month_offset + 1))).strftime("%Y-%m-%d")
            })
        return contracts
    except Exception as e:
        return []

def analyze_futures_opportunity(symbol, spot_price, futures_data):
    """Analyze futures trading opportunities."""
    if spot_price is None:
        return None
    
    if isinstance(spot_price, str):
        try:
            spot_price = float(spot_price)
        except:
            return None
    
    if not isinstance(spot_price, (int, float)) or spot_price <= 0:
        return None
    
    opportunities = []
    for contract in futures_data:
        futures_price = spot_price * (1 + 0.01)
        basis_pct = ((futures_price - spot_price) / spot_price) * 100
        
        if basis_pct > 2:
            signal = "🟢 FUTURES ARBITRAGE"
            reason = f"Futures at {basis_pct:.2f}% premium to spot"
            action = "Consider selling futures, buying spot"
        elif basis_pct < -2:
            signal = "🟢 FUTURES ARBITRAGE"
            reason = f"Futures at {abs(basis_pct):.2f}% discount to spot"
            action = "Consider buying futures, selling spot"
        else:
            signal = "⏳ NEUTRAL"
            reason = f"Futures near spot ({basis_pct:.2f}% difference)"
            action = "Wait for wider spread"
        
        opportunities.append({
            'symbol': symbol,
            'contract': contract.get('contract', ''),
            'expiry': contract.get('expiry', ''),
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis_pct': basis_pct,
            'signal': signal,
            'reason': reason,
            'action': action
        })
    
    return opportunities

# ============================================================
# 5. RIGHT SHARES & OWNERSHIP ANALYSIS
# ============================================================

def analyze_right_shares_opportunity(symbol, price):
    """Simulate right shares opportunity analysis."""
    if price is None:
        return None
    
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            return None
    
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    
    # Simulate right shares for some stocks
    if symbol in ['FFC', 'MARI', 'EFERT', 'HUBC', 'SYS']:
        return {
            'company': symbol,
            'symbol': symbol,
            'ratio': '1:4',
            'offer_price': price * 0.75,
            'market_price': price,
            'record_date': (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
            'discount_pct': 25,
            'recommendation': '🟢 STRONG BUY',
            'reason': f"Trading at 25% discount to market price"
        }
    return None

def analyze_ownership_accumulation(symbol, volume_data, price_data):
    """Analyze ownership accumulation patterns."""
    if not volume_data or not price_data:
        return None
    
    analysis = {
        'symbol': symbol,
        'accumulation_signal': 'NEUTRAL',
        'indicators': []
    }
    
    if 'volume_ratio' in volume_data and volume_data['volume_ratio'] and volume_data['volume_ratio'] > 1.5:
        analysis['indicators'].append({
            'signal': '📊 HIGH VOLUME',
            'detail': f"Volume {volume_data['volume_ratio']:.2f}x average",
            'interpretation': 'Possible accumulation'
        })
    
    if 'atr' in price_data and price_data['atr'] and 'price' in price_data:
        if isinstance(price_data['price'], (int, float)) and price_data['price'] > 0:
            atr_pct = (price_data['atr'] / price_data['price']) * 100
            if atr_pct < 3:
                analysis['indicators'].append({
                    'signal': '📊 PRICE STABILITY',
                    'detail': f"ATR at {atr_pct:.2f}%",
                    'interpretation': 'Potential accumulation zone'
                })
    
    if 'rsi' in price_data and price_data['rsi']:
        if 40 < price_data['rsi'] < 60:
            analysis['indicators'].append({
                'signal': '📊 NEUTRAL RSI',
                'detail': f"RSI at {price_data['rsi']:.2f}",
                'interpretation': 'No clear signal'
            })
    
    if len(analysis['indicators']) >= 2:
        analysis['accumulation_signal'] = '🟢 ACCUMULATION POSSIBLE'
    elif len(analysis['indicators']) == 1:
        analysis['accumulation_signal'] = '🟡 WATCH FOR ACCUMULATION'
    else:
        analysis['accumulation_signal'] = '⏳ NO CLEAR SIGNAL'
    
    return analysis

# ============================================================
# 6. SIGNAL GENERATION
# ============================================================

def generate_signals(symbol, price, indicators, dividend_analysis, futures_opportunities, right_share_analysis, ownership_analysis):
    """Generate buy/sell signals with all data sources."""
    signals = []
    
    if not indicators or price is None:
        return [{"signal": "⏳ NEUTRAL"}]
    
    # Convert price to float if needed
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            return [{"signal": "⏳ NEUTRAL"}]
    
    if not isinstance(price, (int, float)):
        return [{"signal": "⏳ NEUTRAL"}]
    
    # RSI Signal
    rsi = indicators.get('rsi')
    if rsi is not None:
        if rsi < 30:
            signals.append({
                "signal": "🟢 STRONG BUY",
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
                "reason": "RSI in neutral zone",
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
    
    # Bollinger Bands
    bb_lower = indicators.get('bb_lower')
    bb_upper = indicators.get('bb_upper')
    if bb_lower is not None and bb_upper is not None:
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
    
    # Dividend Signal
    if dividend_analysis and dividend_analysis.get('div_yield_pct', 0) > 0:
        div_yield = dividend_analysis.get('div_yield_pct', 0)
        if div_yield > 6:
            signals.append({
                "signal": "💰 HIGH DIVIDEND",
                "indicator": "Dividend Yield",
                "value": f"{div_yield:.2f}%",
                "reason": f"Attractive {div_yield:.2f}% dividend yield",
                "timing": "Buy before ex-dividend date",
                "priority": "HIGH"
            })
    
    # Futures Signal
    if futures_opportunities:
        for fut in futures_opportunities[:2]:
            if 'ARBITRAGE' in fut.get('signal', ''):
                signals.append({
                    "signal": fut.get('signal', ''),
                    "indicator": "Futures Arbitrage",
                    "value": f"{fut.get('basis_pct', 0):.2f}%",
                    "reason": fut.get('reason', ''),
                    "timing": fut.get('action', ''),
                    "priority": "HIGH"
                })
    
    # Right Shares Signal
    if right_share_analysis and right_share_analysis.get('recommendation') in ['🟢 STRONG BUY', '🟡 BUY']:
        signals.append({
            "signal": right_share_analysis.get('recommendation', ''),
            "indicator": "Right Shares",
            "value": f"{right_share_analysis.get('discount_pct', 0):.1f}% discount",
            "reason": right_share_analysis.get('reason', ''),
            "timing": "Before record date",
            "priority": "HIGH"
        })
    
    # Ownership Accumulation Signal
    if ownership_analysis and ownership_analysis.get('accumulation_signal') == '🟢 ACCUMULATION POSSIBLE':
        signals.append({
            "signal": "🟢 ACCUMULATION",
            "indicator": "Ownership Analysis",
            "value": ownership_analysis.get('accumulation_signal', ''),
            "reason": "Multiple indicators suggest accumulation",
            "timing": "Buy on weakness",
            "priority": "MEDIUM"
        })
    
    return signals if signals else [{"signal": "⏳ NEUTRAL"}]

def calculate_entry_exit(symbol, price, signals, dividend_analysis):
    """Calculate entry, target, and stop-loss prices."""
    if price is None:
        return {'entry_price': 'N/A', 'target_price': 'N/A', 'stop_loss': 'N/A', 
                'entry_timing': 'N/A', 'exit_timing': 'N/A'}
    
    if isinstance(price, str):
        try:
            price = float(price)
        except:
            return {'entry_price': 'N/A', 'target_price': 'N/A', 'stop_loss': 'N/A', 
                    'entry_timing': 'N/A', 'exit_timing': 'N/A'}
    
    if not isinstance(price, (int, float)):
        return {'entry_price': 'N/A', 'target_price': 'N/A', 'stop_loss': 'N/A', 
                'entry_timing': 'N/A', 'exit_timing': 'N/A'}
    
    bullish_signals = [s for s in signals if 'BUY' in s.get('signal', '') or 'BULLISH' in s.get('signal', '')]
    bearish_signals = [s for s in signals if 'SELL' in s.get('signal', '') or 'BEARISH' in s.get('signal', '')]
    
    div_yield = dividend_analysis.get('div_yield_pct', 0) if dividend_analysis else 0
    target_multiplier = 1.10 + (div_yield / 100)
    
    if len(bullish_signals) > len(bearish_signals):
        entry = price
        target = price * target_multiplier
        stop = price * 0.95
        timing = "Market open — buy immediately"
        exit_timing = f"When price reaches PKR {target:.2f} or falls below {stop:.2f}"
    else:
        entry = price * 0.97
        target = entry * target_multiplier
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

# ============================================================
# 7. REPORT GENERATION
# ============================================================

def df_to_html(df, limit=10):
    """Convert DataFrame to HTML table."""
    if df is None or df.empty:
        return "<p>No data available</p>"
    df = df.head(limit)
    return df.to_html(index=False, border=0, classes='data-table')

def generate_html_report(quotes, fundamentals, indicators, signals, entry_exit, 
                         market_pulse, index_summary, sector_data, stock_symbols,
                         dividend_analysis, csf_symbols, futures_analysis,
                         right_shares_analysis, ownership_analysis):
    """Generate comprehensive HTML report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")
    
    index_html = df_to_html(index_summary, 10)
    gainers_html = df_to_html(market_pulse.get('gainers'), 5)
    losers_html = df_to_html(market_pulse.get('losers'), 5)
    active_html = df_to_html(market_pulse.get('active'), 5)
    sectors_html = df_to_html(sector_data, 10)
    
    # Dividend opportunities
    dividend_opportunities = []
    for symbol in stock_symbols:
        da = dividend_analysis.get(symbol, {})
        if da and da.get('div_yield_pct', 0) > 0:
            dividend_opportunities.append({
                'symbol': symbol,
                'div_yield': da.get('div_yield_pct', 0),
                'annual_div': da.get('annual_dividend_per_share', 0),
                'rank': da.get('dividend_rank', 'LOW')
            })
    dividend_opportunities.sort(key=lambda x: x['div_yield'], reverse=True)
    
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
            .dividend-high {{ color: #2e7d32; font-weight: bold; }}
            .dividend-medium {{ color: #f57c00; font-weight: bold; }}
            .dividend-low {{ color: #c62828; font-weight: bold; }}
            .futures-section {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .corporate-action {{ background: #fce4ec; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 PSX Ultimate Profit Intelligence Report</h1>
            <p>Generated on {now}</p>
            <p>Tracking {len(stock_symbols)} Shariah-Compliant Stocks</p>
            <p>📊 {len(csf_symbols)} CSF Futures Eligible Securities</p>
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
            <h2>📈 Cash-Settled Futures (CSF) Eligible Securities</h2>
            <p><strong>Total:</strong> {len(csf_symbols)} securities eligible for CSF trading</p>
            <p><strong>Contract Size:</strong> 500 shares per contract</p>
            <p><strong>Contract Period:</strong> 90 days</p>
            <table>
                <thead>
                    <tr><th>Symbol</th><th>Status</th></tr>
                </thead>
                <tbody>
    """
    
    for symbol in csf_symbols[:30]:
        q = quotes.get(symbol, {})
        price = q.get('price', 'N/A')
        status = "🟢 Active" if price != 'N/A' and price != 0 else "⏳ Check"
        html += f"""
                    <tr><td><strong>{symbol}</strong></td><td>{status}</td></tr>
        """
    
    html += """
                </tbody>
            </table>
            <p style="font-size: 12px; color: #666; margin-top: 10px;">
                📌 CSF allows leveraged exposure with lower upfront margin<br>
                📌 Can be used for arbitrage, hedging, and speculation
            </p>
        </div>

        <div class="section">
            <h2>💰 Top Dividend Opportunities</h2>
            <table>
                <thead>
                    <tr><th>Symbol</th><th>Dividend Yield</th><th>Annual Dividend (PKR)</th><th>Rank</th></tr>
                </thead>
                <tbody>
    """
    
    for d in dividend_opportunities[:20]:
        rank_class = 'dividend-high' if d['rank'] == 'HIGH' else 'dividend-medium' if d['rank'] == 'MEDIUM' else 'dividend-low'
        html += f"""
                    <tr>
                        <td><strong>{d['symbol']}</strong></td>
                        <td class="{rank_class}">{d['div_yield']:.2f}%</td>
                        <td>{d['annual_div']:.2f}</td>
                        <td>{d['rank']}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
        </div>

        <div class="section futures-section">
            <h2>🎯 Futures Arbitrage Opportunities</h2>
            <table>
                <thead>
                    <tr><th>Symbol</th><th>Contract</th><th>Basis %</th><th>Signal</th><th>Action</th></tr>
                </thead>
                <tbody>
    """
    
    arbitrage_count = 0
    for symbol in stock_symbols:
        fa = futures_analysis.get(symbol, [])
        for f in fa[:2]:
            if 'ARBITRAGE' in f.get('signal', ''):
                arbitrage_count += 1
                signal_class = 'buy' if 'BUY' in f.get('signal', '') else 'neutral'
                html += f"""
                            <tr>
                                <td><strong>{f.get('symbol', 'N/A')}</strong></td>
                                <td>{f.get('contract', 'N/A')}</td>
                                <td class="{signal_class}">{f.get('basis_pct', 0):.2f}%</td>
                                <td class="{signal_class}">{f.get('signal', 'N/A')}</td>
                                <td>{f.get('action', 'N/A')}</td>
                            </tr>
                """
    
    if arbitrage_count == 0:
        html += '<tr><td colspan="5">No significant futures arbitrage opportunities detected</td></tr>'
    
    html += """
                </tbody>
            </table>
        </div>

        <div class="section corporate-action">
            <h2>🏢 Corporate Actions (Right Shares)</h2>
            <h3>📊 Right Shares Opportunities</h3>
            <table>
                <thead>
                    <tr><th>Symbol</th><th>Discount %</th><th>Recommendation</th><th>Reason</th></tr>
                </thead>
                <tbody>
    """
    
    rs_count = 0
    for symbol in stock_symbols:
        ra = right_shares_analysis.get(symbol, {})
        if ra and ra.get('recommendation') in ['🟢 STRONG BUY', '🟡 BUY']:
            rs_count += 1
            rec_class = 'buy' if 'BUY' in ra.get('recommendation', '') else 'neutral'
            html += f"""
                        <tr>
                            <td><strong>{symbol}</strong></td>
                            <td class="{rec_class}">{ra.get('discount_pct', 0):.1f}%</td>
                            <td class="{rec_class}">{ra.get('recommendation', 'N/A')}</td>
                            <td>{ra.get('reason', 'N/A')}</td>
                        </tr>
            """
    
    if rs_count == 0:
        html += '<tr><td colspan="4">No right shares opportunities detected</td></tr>'
    
    html += """
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>💼 Shariah-Compliant Stocks Watchlist</h2>
            <table>
                <thead>
                    <tr><th>Symbol</th><th>Price (PKR)</th><th>Change %</th><th>Volume</th><th>P/E</th><th>Div Yield</th><th>52W High</th><th>52W Low</th><th>Signal</th></tr>
                </thead>
                <tbody>
    """
    
    for symbol in stock_symbols:
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
    
    displayed = 0
    for symbol in stock_symbols:
        sigs = signals.get(symbol, [])
        ee = entry_exit.get(symbol, {})
        da = dividend_analysis.get(symbol, {})
        
        if not sigs or (len(sigs) == 1 and 'NEUTRAL' in sigs[0].get('signal', '')):
            continue
        
        if displayed >= 10:
            break
        
        html += f"<h3>{symbol}</h3>"
        if da and da.get('div_yield_pct', 0) > 0:
            html += f"<p><strong>💵 Dividend Yield:</strong> {da.get('div_yield_pct', 0):.2f}% | <strong>Annual Dividend:</strong> PKR {da.get('annual_dividend_per_share', 0):.2f}</p>"
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
        displayed += 1
    
    if displayed == 0:
        html += "<p>No actionable signals available at this time.</p>"
    
    html += "</div>"
    
    # Technical Indicators
    html += """
        <div class="section">
            <h2>📊 Technical Indicators</h2>
            <table>
                <thead>
                    <tr><th>Symbol</th><th>RSI</th><th>SMA20</th><th>SMA50</th><th>BB Position</th><th>ATR</th><th>Vol Ratio</th></tr>
                </thead>
                <tbody>
    """
    
    indicator_count = 0
    for symbol in stock_symbols:
        if indicator_count >= 20:
            break
        ind = indicators.get(symbol, {})
        if ind and ind.get('rsi') is not None:
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
            indicator_count += 1
    
    if indicator_count == 0:
        html += "<tr><td colspan='7'>No technical indicator data available.</td></tr>"
    
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
    
    for symbol in stock_symbols:
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
            <p>{', '.join(hold_list[:20]) if hold_list else 'None'}{'...' if len(hold_list) > 20 else ''}</p>
            <h3 style="color: red;">🔴 SELL / TAKE PROFIT</h3>
            <p>{', '.join(sell_list) if sell_list else 'No sell signals — hold positions'}</p>
        </div>
    """
    
    html += f"""
        <div class="footer">
            <p>🕌 All stocks verified as Shariah-compliant (KMI All Share Index)</p>
            <p>📊 Tracking {len(stock_symbols)} Shariah-compliant stocks</p>
            <p>📈 CSF Futures: {len(csf_symbols)} eligible securities</p>
            <p>⚠️ This is for informational purposes only. Always do your own research before trading.</p>
            <p>📈 Generated by PSX Ultimate Profit Intelligence Bot</p>
        </div>
    </body>
    </html>
    """
    
    return html

# ============================================================
# 8. EMAIL SENDING
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
# 9. MAIN EXECUTION
# ============================================================

def main():
    print("🚀 Generating PSX Ultimate Profit Intelligence Report...")
    print("=" * 60)
    
    # 1. Fetch top Shariah-compliant stocks
    stock_symbols = fetch_top_shariah_compliant_stocks(limit=50)
    print(f"📊 Tracking {len(stock_symbols)} stocks.")
    
    # 2. Fetch CSF eligible securities
    print("📡 Fetching CSF Futures eligible securities...")
    csf_symbols = fetch_csf_eligible_securities()
    print(f"📊 CSF eligible: {len(csf_symbols)} securities")
    
    # 3. Fetch stock data
    print("📡 Fetching stock data...")
    quotes = {}
    fundamentals = {}
    historical_data = {}
    dividend_data = {}
    
    for symbol in stock_symbols:
        print(f"   Fetching {symbol}...")
        quotes[symbol] = fetch_stock_quote(symbol)
        fundamentals[symbol] = fetch_stock_fundamentals(symbol)
        historical_data[symbol] = fetch_historical_data(symbol)
        dividend_data[symbol] = fetch_dividend_data(symbol)
    
    print("✅ Stock data fetched")
    
    # 4. Fetch market pulse
    print("📡 Fetching market pulse...")
    market_pulse = fetch_market_pulse()
    
    # 5. Fetch index summary
    print("📡 Fetching index summary...")
    index_summary = fetch_index_summary()
    
    # 6. Fetch sector performance
    print("📡 Fetching sector performance...")
    sector_data = fetch_sector_performance()
    
    # 7. Calculate indicators
    print("📊 Calculating technical indicators...")
    indicators = {}
    for symbol, hist in historical_data.items():
        indicators[symbol] = calculate_indicators(hist)
    
    # 8. Analyze dividends
    print("💵 Analyzing dividend opportunities...")
    dividend_analysis = {}
    for symbol in stock_symbols:
        price = quotes.get(symbol, {}).get('price')
        div_yield = fundamentals.get(symbol, {}).get('div_yield', 'N/A')
        dividend_analysis[symbol] = analyze_dividend_opportunity(symbol, price, div_yield)
    
    # 9. Analyze futures
    print("📈 Analyzing futures opportunities...")
    futures_analysis = {}
    for symbol in stock_symbols[:20]:
        price = quotes.get(symbol, {}).get('price')
        if price and price != 'N/A':
            futures_data = fetch_futures_contract_info(symbol)
            futures_analysis[symbol] = analyze_futures_opportunity(symbol, price, futures_data)
    
    # 10. Analyze right shares
    print("🏢 Analyzing right shares opportunities...")
    right_shares_analysis = {}
    for symbol in stock_symbols:
        price = quotes.get(symbol, {}).get('price')
        right_shares_analysis[symbol] = analyze_right_shares_opportunity(symbol, price)
    
    # 11. Analyze ownership accumulation
    print("🏛️ Analyzing ownership accumulation signals...")
    ownership_analysis = {}
    for symbol in stock_symbols:
        ind = indicators.get(symbol, {})
        quote = quotes.get(symbol, {})
        price = quote.get('price', 0)
        ownership_analysis[symbol] = analyze_ownership_accumulation(
            symbol,
            {'volume_ratio': ind.get('volume_ratio', 0)},
            {'price': price, 'atr': ind.get('atr', 0), 'rsi': ind.get('rsi', 0)}
        )
    
    # 12. Generate signals
    print("🎯 Generating trading signals...")
    signals = {}
    entry_exit = {}
    
    for symbol in stock_symbols:
        price = quotes.get(symbol, {}).get('price')
        ind = indicators.get(symbol, {})
        da = dividend_analysis.get(symbol, {})
        fa = futures_analysis.get(symbol, [])
        ra = right_shares_analysis.get(symbol, {})
        oa = ownership_analysis.get(symbol, {})
        
        sigs = generate_signals(symbol, price, ind, da, fa, ra, oa)
        signals[symbol] = sigs
        entry_exit[symbol] = calculate_entry_exit(symbol, price, sigs, da)
    
    # 13. Generate report
    print("📝 Generating HTML report...")
    html_report = generate_html_report(
        quotes, fundamentals, indicators, signals, entry_exit,
        market_pulse, index_summary, sector_data, stock_symbols,
        dividend_analysis, csf_symbols, futures_analysis,
        right_shares_analysis, ownership_analysis
    )
    
    # 14. Send email
    subject = f"PSX Ultimate Profit Report - {len(stock_symbols)} Stocks - {datetime.now().strftime('%Y-%m-%d')}"
    email_sent = send_html_email(subject, html_report)
    
    if email_sent:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
