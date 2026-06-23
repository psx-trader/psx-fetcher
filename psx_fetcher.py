#!/usr/bin/env python3
"""
PSX Live Data Fetcher - Parallel Fetching (Corrected)
Uses psxdata and pypsx correctly from official documentation
"""

import requests
from datetime import datetime
import os
import concurrent.futures

# ===== CONFIGURATION =====
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# =========================

SYMBOLS = ["FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB"]

def fetch_from_psxdata(symbol):
    """Fetch live quote using psxdata library (correct way from docs)"""
    try:
        import psxdata
        # ✅ Correct: psxdata.quote() is a function
        quote = psxdata.quote(symbol)
        
        # quote returns a pandas Series
        if quote is not None and not quote.empty:
            return {
                "symbol": symbol,
                "price": quote.get('price', 'N/A'),
                "change": quote.get('change', 'N/A'),
                "volume": quote.get('volume', 'N/A'),
                "source": "psxdata",
                "error": None
            }
        else:
            return {"symbol": symbol, "error": "No data returned", "source": "psxdata"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "psxdata"}

def fetch_from_pypsx(symbol):
    """Fetch data using pypsx library (correct way from docs)"""
    try:
        import pypsx
        # ✅ Correct: Use PSXTicker class
        ticker = pypsx.PSXTicker(symbol)
        
        # Get snapshot data (OHLCV, bid/ask, etc.)
        snapshot = ticker.snapshot
        
        # Get REG tab data (OHLCV, ranges, ratios)
        reg_data = snapshot.get('REG', {})
        
        if reg_data:
            return {
                "symbol": symbol,
                "price": reg_data.get('Current', reg_data.get('Close', 'N/A')),
                "change": reg_data.get('Change %', reg_data.get('Change', 'N/A')),
                "volume": reg_data.get('Volume', 'N/A'),
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
        API_KEY = "YOUR_ALPHA_VANTAGE_API_KEY"  # Get from alphavantage.co
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
                return {"symbol": symbol, "error": "No data from Alpha Vantage", "source": "alphavantage"}
        else:
            return {"symbol": symbol, "error": f"HTTP {response.status_code}", "source": "alphavantage"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "alphavantage"}

def fetch_psx_data_parallel(symbol):
    """Fetch from all sources in parallel"""
    sources = [fetch_from_psxdata, fetch_from_pypsx, fetch_from_alpha_vantage]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_source = {
            executor.submit(source, symbol): source.__name__ 
            for source in sources
        }
        
        for future in concurrent.futures.as_completed(future_to_source):
            result = future.result()
            if result and not result.get("error"):
                print(f"✅ Got data from {result.get('source')}")
                return result
        
        for future in concurrent.futures.as_completed(future_to_source):
            result = future.result()
            if result:
                return result

def fetch_all_symbols():
    """Fetch all symbols in parallel"""
    results = []
    for symbol in SYMBOLS:
        print(f"📡 Fetching {symbol} in parallel...")
        result = fetch_psx_data_parallel(symbol)
        if result and not result.get("error"):
            result["timestamp"] = datetime.now().strftime("%H:%M:%S")
        results.append(result)
    return results

def format_report(data):
    """Format data into readable report"""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    output = f"""🚀 **PSX LIVE DATA REPORT** (Fixed Libraries)
📅 Date: {current_date}
⏰ Time: {current_time} PKT
💰 Portfolio: PKR 30,000

{'='*60}

**📊 LIVE MARKET DATA:**

"""
    for stock in data:
        if stock.get("error"):
            output += f"❌ **{stock['symbol']}**: ERROR - {stock['error']} (source: {stock.get('source', 'unknown')})\n\n"
        else:
            output += f"**{stock['symbol']}** (source: {stock.get('source', 'unknown')})\n"
            output += f"   • Price: {stock.get('price', 'N/A')}\n"
            output += f"   • Change: {stock.get('change', 'N/A')}\n"
            output += f"   • Volume: {stock.get('volume', 'N/A')}\n\n"
    
    output += f"{'='*60}\n"
    output += f"⏱️ Report generated at: {current_time} PKT\n"
    output += f"🕌 Verify Shariah compliance on PSX-KMI index\n"
    return output

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

def main():
    print(f"🚀 Starting PSX data fetch at {datetime.now()}")
    print(f"📚 Using fixed libraries: psxdata + pypsx (from official docs)")
    
    if not RESEND_API_KEY:
        print("❌ ERROR: RESEND_API_KEY not set")
        return
    if not FROM_EMAIL:
        print("❌ ERROR: FROM_EMAIL not set")
        return
    if not TO_EMAIL:
        print("❌ ERROR: TO_EMAIL not set")
        return
    
    data = fetch_all_symbols()
    successful = sum(1 for d in data if not d.get("error"))
    print(f"✅ Fetched data for {successful} out of {len(data)} symbols")
    
    report = format_report(data)
    subject = f"PSX Live Data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    email_sent = send_via_resend(subject, report)
    print(f"✅ Email sent: {email_sent}")

if __name__ == "__main__":
    main()
