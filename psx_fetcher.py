#!/usr/bin/env python3
"""
PSX Live Data Fetcher - Dual Library (psxdata + pypsx)
Fetches live PSX data with fallback for reliability
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
    """Try to fetch data using psxdata library"""
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
    """Try to fetch data using pypsx library"""
    try:
        import pypsx
        psx = pypsx.PSX()
        data = psx.get_intraday(symbol)
        # Extract the latest data point
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
            return {"symbol": symbol, "error": "No data returned", "source": "pypsx"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "source": "pypsx"}

def fetch_psx_data():
    """Fetch data using psxdata first, fallback to pypsx if needed"""
    results = []
    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        
        # Try psxdata first
        result = fetch_quote_psxdata(symbol)
        
        # If psxdata failed, try pypsx
        if result.get("error"):
            print(f"psxdata failed for {symbol}, trying pypsx...")
            result = fetch_quote_pypsx(symbol)
        
        results.append(result)
    
    return results

def format_report(data):
    """Format data into a readable report"""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    output = f"""🚀 **PSX LIVE DATA REPORT** (Dual Library)
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
    print(f"📚 Using dual library: psxdata + pypsx")
    
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
    
    # Fetch data with fallback
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
