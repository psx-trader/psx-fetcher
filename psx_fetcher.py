#!/usr/bin/env python3
"""
PSX Live Data Fetcher - Triple Fallback (psxdata + pypsx + HTTP)
Fetches live PSX data with multiple fallback options
"""

import requests
from datetime import datetime
import os

# ===== CONFIGURATION (Read from Render Environment Variables) =====
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# ================================================================

# Stock symbols to track (Shariah-compliant PSX stocks)
SYMBOLS = ["FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB"]

def fetch_quote_psxdata(symbol):
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
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "error": None,
            "source": "psxdata"
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "psxdata"}

def fetch_quote_pypsx(symbol):
    """Try pypsx library with corrected API"""
    try:
        import pypsx
        # Try multiple possible API patterns
        try:
            from pypsx import get_intraday
            data = get_intraday(symbol)
        except:
            try:
                data = pypsx.get_intraday(symbol)
            except:
                try:
                    psx = pypsx.PakistanStockExchange()
                    data = psx.get_intraday(symbol)
                except:
                    return fetch_quote_http(symbol)
        
        if data and len(data) > 0:
            latest = data[-1]
            return {
                "symbol": symbol,
                "price": latest.get('close', 'N/A'),
                "change": latest.get('change', 'N/A'),
                "volume": latest.get('volume', 'N/A'),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "error": None,
                "source": "pypsx"
            }
        else:
            return {"symbol": symbol, "error": "No data", "source": "pypsx"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "pypsx"}

def fetch_quote_http(symbol):
    """Fallback: Direct HTTP request"""
    try:
        import requests
        url = f"https://psxterminal.com/api/ticks/REG/{symbol}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "symbol": symbol,
                "price": data.get('lastPrice', 'N/A'),
                "change": data.get('changePercent', 'N/A'),
                "volume": data.get('volume', 'N/A'),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "error": None,
                "source": "http"
            }
        else:
            return {"symbol": symbol, "error": f"HTTP {response.status_code}", "source": "http"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "http"}

def fetch_psx_data():
    """Triple fallback: psxdata → pypsx → HTTP"""
    results = []
    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        
        # Try psxdata first
        result = fetch_quote_psxdata(symbol)
        
        # If psxdata failed, try pypsx
        if result.get("error"):
            print(f"psxdata failed for {symbol}, trying pypsx...")
            result = fetch_quote_pypsx(symbol)
        
        # If pypsx failed, try HTTP
        if result.get("error"):
            print(f"pypsx failed for {symbol}, trying HTTP...")
            result = fetch_quote_http(symbol)
        
        results.append(result)
    
    return results

def format_report(data):
    """Format data into a readable report"""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    output = f"""🚀 **PSX LIVE DATA REPORT** (Triple Fallback)
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
    print(f"📚 Using triple fallback: psxdata + pypsx + HTTP")
    
    # Check if environment variables are set
    if not RESEND_API_KEY:
        print("❌ ERROR: RESEND_API_KEY not set in environment variables")
        return
    if not FROM_EMAIL:
        print("❌ ERROR: FROM_EMAIL not set in environment variables")
        return
    if not TO_EMAIL:
        print("❌ ERROR: TO_EMAIL not set in environment variables")
        return
    
    # Fetch data with triple fallback
    data = fetch_psx_data()
    
    # Print summary
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
