#!/usr/bin/env python3
"""
PSX Live Data Fetcher - Parallel Fetching
Fetches live PSX data from multiple sources simultaneously
"""

import requests
from datetime import datetime
import os
import concurrent.futures

# ===== CONFIGURATION (Read from Render Environment Variables) =====
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# ================================================================

# Stock symbols to track
SYMBOLS = ["FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB"]

def fetch_from_psxdata(symbol):
    """Try psxdata library"""
    try:
        import psxdata
        psx = psxdata.PSXData()
        quote = psx.get_quote(symbol)
        return {
            "symbol": symbol,
            "price": quote.price,
            "change": quote.change,
            "volume": quote.volume,
            "source": "psxdata",
            "error": None
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "psxdata"}

def fetch_from_pypsx(symbol):
    """Try pypsx library"""
    try:
        import pypsx
        try:
            from pypsx import get_intraday
            data = get_intraday(symbol)
        except:
            data = pypsx.get_intraday(symbol)
        
        if data and len(data) > 0:
            latest = data[-1]
            return {
                "symbol": symbol,
                "price": latest.get('close', 'N/A'),
                "change": latest.get('change', 'N/A'),
                "volume": latest.get('volume', 'N/A'),
                "source": "pypsx",
                "error": None
            }
        else:
            return {"symbol": symbol, "error": "No data", "source": "pypsx"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "pypsx"}

def fetch_from_psx_mcp(symbol):
    """Try psx-mcp server"""
    try:
        url = "http://localhost:5000/tools/get_quote"
        response = requests.post(url, json={"symbol": symbol}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "symbol": symbol,
                "price": data.get('price', 'N/A'),
                "change": data.get('change', 'N/A'),
                "volume": data.get('volume', 'N/A'),
                "source": "psx-mcp",
                "error": None
            }
        else:
            return {"symbol": symbol, "error": f"HTTP {response.status_code}", "source": "psx-mcp"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "psx-mcp"}

def fetch_psx_data_parallel(symbol):
    """
    Fetch data from all sources simultaneously.
    The first successful response wins.
    """
    sources = [fetch_from_psxdata, fetch_from_pypsx, fetch_from_psx_mcp]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks at once (parallel)
        future_to_source = {
            executor.submit(source, symbol): source.__name__ 
            for source in sources
        }
        
        # Check results as they complete
        for future in concurrent.futures.as_completed(future_to_source):
            result = future.result()
            # If we get valid data (no error), return it immediately
            if result and not result.get("error"):
                print(f"✅ Got data from {result.get('source')}")
                return result
        
        # If all failed, return the first error
        for future in concurrent.futures.as_completed(future_to_source):
            result = future.result()
            if result:
                return result

def fetch_all_symbols():
    """Fetch data for all symbols using parallel fetching"""
    results = []
    for symbol in SYMBOLS:
        print(f"📡 Fetching {symbol} in parallel...")
        result = fetch_psx_data_parallel(symbol)
        # Ensure timestamp is added
        if result and not result.get("error"):
            result["timestamp"] = datetime.now().strftime("%H:%M:%S")
        results.append(result)
    return results

def format_report(data):
    """Format data into a readable report"""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    output = f"""🚀 **PSX LIVE DATA REPORT** (Parallel Fetching)
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
            print(f"❌ Resend API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

def main():
    print(f"🚀 Starting PSX data fetch at {datetime.now()}")
    print(f"📚 Using parallel fetching: psxdata + pypsx + psx-mcp")
    
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
    
    # Fetch data in parallel
    data = fetch_all_symbols()
    
    # Count successful fetches
    successful = sum(1 for d in data if not d.get("error"))
    print(f"✅ Fetched data for {successful} out of {len(data)} symbols")
    
    # Generate report
    report = format_report(data)
    
    # Send email
    subject = f"PSX Live Data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    email_sent = send_via_resend(subject, report)
    
    print(f"✅ Data fetched. Email sent: {email_sent}")

if __name__ == "__main__":
    main()
