#!/usr/bin/env python3
"""
PSX Live Data Fetcher - Uses Resend API for email
Fetches live PSX data using psx-terminal and emails via Resend
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

def fetch_psx_data():
    """Fetch live PSX data using psx-terminal library"""
    try:
        from psx_terminal.feed_parser import fetch_quotes
    except ImportError:
        return [{"error": "psx-terminal library not installed."}]
    
    results = []
    for symbol in SYMBOLS:
        try:
            quotes = fetch_quotes(symbol)
            if quotes and len(quotes) > 0:
                latest = quotes[-1]
                results.append({
                    "symbol": symbol,
                    "price": latest.price if hasattr(latest, 'price') else "N/A",
                    "change": latest.change if hasattr(latest, 'change') else "N/A",
                    "volume": latest.volume if hasattr(latest, 'volume') else "N/A",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "error": None
                })
            else:
                results.append({"symbol": symbol, "error": "No data returned"})
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})
    return results

def format_report(data):
    """Format data into a readable report"""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    output = f"""🚀 **PSX LIVE DATA REPORT**
📅 Date: {current_date}
⏰ Time: {current_time} PKT
💰 Portfolio: PKR 30,000

{'='*60}

**📊 LIVE MARKET DATA:**

"""
    for stock in data:
        if stock.get("error"):
            output += f"❌ **{stock['symbol']}**: ERROR - {stock['error']}\n\n"
        else:
            output += f"**{stock['symbol']}**\n"
            output += f"   • Price: {stock.get('price', 'N/A')}\n"
            output += f"   • Change: {stock.get('change', 'N/A')}\n"
            output += f"   • Volume: {stock.get('volume', 'N/A')}\n\n"
    
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
    
    data = fetch_psx_data()
    report = format_report(data)
    subject = f"PSX Live Data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    email_sent = send_via_resend(subject, report)
    print(f"✅ Data fetched. Email sent: {email_sent}")

if __name__ == "__main__":
    main()
