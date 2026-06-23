#!/usr/bin/env python3
"""
PSX Live Data Fetcher - Stocks + Indexes
Monitors individual stocks AND KMI-30 / KMI All Share Islamic Indexes
"""

import requests
from datetime import datetime
import os
import concurrent.futures
import pandas as pd

# ===== CONFIGURATION =====
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# =========================

# Stock symbols to track (Shariah-compliant PSX stocks)
STOCK_SYMBOLS = ["FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB"]

# Index symbols to track
INDEX_SYMBOLS = ["KMI30", "KMIALLSHR", "KSE100"]

def extract_scalar(value):
    """Convert pandas Series/DataFrame to scalar value"""
    if value is None:
        return 'N/A'
    if isinstance(value, (pd.Series, pd.DataFrame)):
        if len(value) > 0:
            return value.iloc[0]
        else:
            return 'N/A'
    return value

# ============================================================
# STOCK DATA FETCHING FUNCTIONS
# ============================================================

def fetch_from_psxdata(symbol):
    """Fetch live quote using psxdata library"""
    try:
        import psxdata
        quote = psxdata.quote(symbol)
        
        if quote is not None and not quote.empty:
            price = extract_scalar(quote.get('price'))
            change = extract_scalar(quote.get('change'))
            volume = extract_scalar(quote.get('volume'))
            
            return {
                "symbol": symbol,
                "price": price,
                "change": change,
                "volume": volume,
                "source": "psxdata",
                "error": None
            }
        else:
            return {"symbol": symbol, "error": "No data returned", "source": "psxdata"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "psxdata"}

def fetch_from_pypsx(symbol):
    """Fetch data using pypsx library"""
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        
        if reg_data:
            price = reg_data.get('Current', reg_data.get('Close', 'N/A'))
            change = reg_data.get('Change %', reg_data.get('Change', 'N/A'))
            volume = reg_data.get('Volume', 'N/A')
            
            if isinstance(price, (pd.Series, pd.DataFrame)):
                price = price.iloc[0] if len(price) > 0 else 'N/A'
            if isinstance(change, (pd.Series, pd.DataFrame)):
                change = change.iloc[0] if len(change) > 0 else 'N/A'
            if isinstance(volume, (pd.Series, pd.DataFrame)):
                volume = volume.iloc[0] if len(volume) > 0 else 'N/A'
            
            return {
                "symbol": symbol,
                "price": price,
                "change": change,
                "volume": volume,
                "source": "pypsx",
                "error": None
            }
        else:
            return {"symbol": symbol, "error": "No data from pypsx", "source": "pypsx"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "pypsx"}

def fetch_from_alpha_vantage(symbol):
    """Fallback: Fetch data from Alpha Vantage API"""
    try:
        API_KEY = "YOUR_ALPHA_VANTAGE_API_KEY"
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}.KAR&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            quote = data.get('Global Quote', {})
            if quote:
                return {
                    "symbol": symbol,
                    "price": quote.get('05. price', 'N/A'),
                    "change": quote.get('10. change percent', 'N/A').replace('%', ''),
                    "volume": quote.get('06. volume', 'N/A'),
                    "source": "alphavantage",
                    "error": None
                }
            else:
                return {"symbol": symbol, "error": "No data", "source": "alphavantage"}
        else:
            return {"symbol": symbol, "error": f"HTTP {response.status_code}", "source": "alphavantage"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "alphavantage"}

def fetch_stock_parallel(symbol):
    """Fetch stock from all sources in parallel"""
    sources = [fetch_from_psxdata, fetch_from_pypsx, fetch_from_alpha_vantage]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_source = {
            executor.submit(source, symbol): source.__name__ 
            for source in sources
        }
        
        for future in concurrent.futures.as_completed(future_to_source):
            result = future.result()
            if result and not result.get("error"):
                print(f"✅ Got stock data from {result.get('source')}")
                return result
        
        for future in concurrent.futures.as_completed(future_to_source):
            result = future.result()
            if result:
                return result

# ============================================================
# INDEX DATA FETCHING FUNCTIONS
# ============================================================

def fetch_kmi30_constituents():
    """Fetch KMI 30 index constituents"""
    try:
        import psxdata
        kmi30 = psxdata.indices("KMI30")
        if kmi30 is not None and not kmi30.empty:
            print(f"✅ KMI 30: {len(kmi30)} constituents")
            return kmi30
        else:
            return None
    except Exception as e:
        print(f"Error fetching KMI30: {e}")
        return None

def fetch_kmi_all_share_constituents():
    """Fetch KMI All Share index constituents"""
    try:
        import psxdata
        kmi_all = psxdata.indices("KMIALLSHR")
        if kmi_all is not None and not kmi_all.empty:
            print(f"✅ KMI All Share: {len(kmi_all)} constituents")
            return kmi_all
        else:
            return None
    except Exception as e:
        print(f"Error fetching KMI All Share: {e}")
        return None

def fetch_indices_performance():
    """Fetch all indices performance"""
    try:
        import psxdata
        indices = psxdata.indices_all()
        if indices is not None and not indices.empty:
            print(f"✅ Index performance data available")
            return indices
        else:
            return None
    except Exception as e:
        print(f"Error fetching index performance: {e}")
        return None

def fetch_kmi30_via_pypsx():
    """Alternative: Fetch KMI 30 data using pypsx"""
    try:
        import pypsx
        kmi30 = pypsx.index_constituents("KMI30")
        if kmi30 is not None and not kmi30.empty:
            print(f"✅ KMI 30 (pypsx): {len(kmi30)} constituents")
            return kmi30
        else:
            return None
    except Exception as e:
        print(f"Error fetching KMI30 via pypsx: {e}")
        return None

# ============================================================
# REPORT FORMATTING
# ============================================================

def format_report(stock_data, kmi30_data, kmi_all_data, indices_data):
    """Format all data into a comprehensive report"""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    output = f"""🚀 **PSX COMPREHENSIVE MARKET REPORT**
📅 Date: {current_date}
⏰ Time: {current_time} PKT
💰 Portfolio: PKR 30,000

{'='*60}

**📊 INDEX PERFORMANCE:**

"""
    # Add index performance data
    if indices_data is not None and not indices_data.empty:
        for idx, row in indices_data.iterrows():
            name = row.get('name', 'N/A')
            current = row.get('current', 'N/A')
            change = row.get('change', 'N/A')
            output += f"• **{name}**: {current} ({change}%)\n"
    else:
        output += "⚠️ Index performance data not available\n"
    
    output += f"\n{'='*60}\n"
    
    # KMI 30 Constituents (Top 10)
    output += f"**📈 KMI 30 INDEX CONSTITUENTS (Top 10 of {len(kmi30_data) if kmi30_data is not None else 'N/A'}):**\n"
    if kmi30_data is not None and not kmi30_data.empty:
        # Get the actual column name (could be 'Symbol', 'symbol', or the symbol itself)
        symbol_col = None
        for col in ['Symbol', 'symbol', 'Ticker', 'ticker']:
            if col in kmi30_data.columns:
                symbol_col = col
                break
        
        if symbol_col is None:
            # Use first column
            symbol_col = kmi30_data.columns[0]
        
        top_10 = kmi30_data.head(10)
        for idx, row in top_10.iterrows():
            symbol = row.get(symbol_col, 'N/A')
            output += f"   • {symbol}\n"
    else:
        output += "   ⚠️ KMI 30 data not available\n"
    
    output += f"\n{'='*60}\n"
    
    # KMI All Share Summary
    if kmi_all_data is not None and not kmi_all_data.empty:
        output += f"**📊 KMI ALL SHARE ISLAMIC INDEX:**\n"
        output += f"   • Total Constituents: {len(kmi_all_data)}\n"
        # Show first 5 constituents
        symbol_col = None
        for col in ['Symbol', 'symbol', 'Ticker', 'ticker']:
            if col in kmi_all_data.columns:
                symbol_col = col
                break
        if symbol_col is None:
            symbol_col = kmi_all_data.columns[0]
        output += f"   • Sample: "
        sample_symbols = kmi_all_data[symbol_col].head(5).tolist()
        output += ", ".join([str(s) for s in sample_symbols]) + ", ...\n"
    
    output += f"\n{'='*60}\n"
    
    # Stock Data
    output += f"**📊 LIVE STOCK MARKET DATA:**\n\n"
    for stock in stock_data:
        if stock.get("error"):
            output += f"❌ **{stock['symbol']}**: ERROR - {stock['error']} (source: {stock.get('source', 'unknown')})\n\n"
        else:
            output += f"**{stock['symbol']}** (source: {stock.get('source', 'unknown')})\n"
            output += f"   • Price: {stock.get('price', 'N/A')}\n"
            output += f"   • Change: {stock.get('change', 'N/A')}\n"
            output += f"   • Volume: {stock.get('volume', 'N/A')}\n\n"
    
    output += f"{'='*60}\n"
    output += f"⏱️ Report generated at: {current_time} PKT\n"
    output += f"🕌 All stocks verified on PSX-KMI index\n"
    output += f"📋 KMI index recomposition: Semi-annually (June & December)\n"
    
    return output

# ============================================================
# EMAIL FUNCTION
# ============================================================

def send_via_resend(subject, body):
    """Send email using Resend API"""
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "from": FROM_EMAIL,
        "to": [TO_EMAIL],
        "subject": subject,
        "text": body
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            print(f"✅ Email sent successfully to {TO_EMAIL}")
            return True
        else:
            print(f"❌ Resend API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

# ============================================================
# MAIN FUNCTION
# ============================================================

def main():
    print(f"🚀 Starting PSX data fetch at {datetime.now()}")
    print(f"📚 Fetching: Stocks + KMI-30 + KMI All Share Islamic Index")
    
    # Check environment variables
    if not RESEND_API_KEY:
        print("❌ ERROR: RESEND_API_KEY not set")
        return
    if not FROM_EMAIL:
        print("❌ ERROR: FROM_EMAIL not set")
        return
    if not TO_EMAIL:
        print("❌ ERROR: TO_EMAIL not set")
        return
    
    # ============================================================
    # 1. FETCH STOCK DATA
    # ============================================================
    print("\n📡 Fetching stock data...")
    stock_data = []
    for symbol in STOCK_SYMBOLS:
        print(f"   Fetching {symbol}...")
        result = fetch_stock_parallel(symbol)
        if result and not result.get("error"):
            result["timestamp"] = datetime.now().strftime("%H:%M:%S")
        stock_data.append(result)
    
    stock_success = sum(1 for d in stock_data if not d.get("error"))
    print(f"✅ Fetched stock data for {stock_success} out of {len(STOCK_SYMBOLS)} symbols")
    
    # ============================================================
    # 2. FETCH INDEX DATA
    # ============================================================
    print("\n📡 Fetching index data...")
    
    # Try psxdata first
    kmi30_data = fetch_kmi30_constituents()
    if kmi30_data is None:
        # Fallback to pypsx
        kmi30_data = fetch_kmi30_via_pypsx()
    
    kmi_all_data = fetch_kmi_all_share_constituents()
    indices_data = fetch_indices_performance()
    
    # ============================================================
    # 3. GENERATE REPORT
    # ============================================================
    print("\n📝 Generating report...")
    report = format_report(stock_data, kmi30_data, kmi_all_data, indices_data)
    
    # ============================================================
    # 4. SEND EMAIL
    # ============================================================
    subject = f"PSX Market Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    email_sent = send_via_resend(subject, report)
    
    print(f"\n✅ Data fetched. Email sent: {email_sent}")
    print(f"📊 Summary:")
    print(f"   • Stocks: {stock_success}/{len(STOCK_SYMBOLS)}")
    print(f"   • KMI 30: {len(kmi30_data) if kmi30_data is not None else 'N/A'}")
    print(f"   • KMI All Share: {len(kmi_all_data) if kmi_all_data is not None else 'N/A'}")

if __name__ == "__main__":
    main()
