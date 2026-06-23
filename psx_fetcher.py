#!/usr/bin/env python3
"""
PSX Market Intelligence Report - Enhanced Edition (Fixed)
Fetches stock data, market pulse (gainers/losers), index summary, and fundamentals.
"""

import requests
import os
import pandas as pd
from datetime import datetime

# ===== CONFIGURATION =====
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL')
# =========================

STOCK_SYMBOLS = ["FFC", "SYS", "MARI", "EFERT", "HUBC", "MCB"]

# ------------------------------------------------------------
# 1. Data Fetching Functions
# ------------------------------------------------------------

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
    """Fetch sector summary (top sectors by performance)."""
    try:
        import pypsx
        sectors = pypsx.sector_summary()
        return sectors
    except Exception as e:
        print(f"Error fetching sector data: {e}")
        return None

def fetch_stock_fundamentals(symbol):
    """Fetch fundamental data for a stock (P/E, Dividend Yield, 52W High/Low)."""
    try:
        import pypsx
        ticker = pypsx.PSXTicker(symbol)
        snapshot = ticker.snapshot
        reg_data = snapshot.get('REG', {})
        
        pe = reg_data.get('P/E', 'N/A')
        div_yield = reg_data.get('Dividend Yield', 'N/A')
        high_52w = reg_data.get('52W High', 'N/A')
        low_52w = reg_data.get('52W Low', 'N/A')
        
        return {
            'P/E': pe,
            'Div Yield': div_yield,
            '52W High': high_52w,
            '52W Low': low_52w
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {symbol}: {e}")
        return {
            'P/E': 'N/A',
            'Div Yield': 'N/A',
            '52W High': 'N/A',
            '52W Low': 'N/A'
        }

def fetch_stock_quotes(symbols):
    """Fetch real-time quotes for a list of symbols."""
    quotes = {}
    for symbol in symbols:
        try:
            import pypsx
            ticker = pypsx.PSXTicker(symbol)
            snapshot = ticker.snapshot
            reg_data = snapshot.get('REG', {})
            
            quotes[symbol] = {
                'price': reg_data.get('Current', 'N/A'),
                'change': reg_data.get('Change', 'N/A'),
                'change_pct': reg_data.get('Change %', 'N/A'),
                'volume': reg_data.get('Volume', 'N/A')
            }
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            quotes[symbol] = {
                'price': 'N/A',
                'change': 'N/A',
                'change_pct': 'N/A',
                'volume': 'N/A'
            }
    return quotes

# ------------------------------------------------------------
# 2. HTML Report Generation
# ------------------------------------------------------------

def df_to_html(df, display_columns=None, limit=5):
    """Convert DataFrame to HTML table with intelligent column detection."""
    if df is None or df.empty:
        return "<p>No data available</p>"
    
    # If display_columns is provided, try to use them
    if display_columns:
        # Find which columns actually exist in the DataFrame
        existing_cols = [col for col in display_columns if col in df.columns]
        if existing_cols:
            df = df[existing_cols]
        else:
            # If none of the requested columns exist, use all columns
            pass
    
    # Limit rows
    df = df.head(limit)
    
    # Convert to HTML with styling
    return df.to_html(index=False, border=0, classes='data-table')

def generate_html_report(quotes, fundamentals, market_pulse, index_summary, sector_data):
    """Generate a professional HTML email report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M:%S PKT")

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            .header {{ background-color: #1a3a5c; color: white; padding: 15px; text-align: center; }}
            .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            .section h2 {{ color: #1a3a5c; margin-top: 0; }}
            table.data-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
            table.data-table th {{ background-color: #f2f2f2; text-align: left; padding: 8px; border-bottom: 2px solid #ddd; }}
            table.data-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            .footer {{ text-align: center; font-size: 12px; color: #888; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
            .positive {{ color: green; font-weight: bold; }}
            .negative {{ color: red; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 PSX Comprehensive Market Report</h1>
            <p>Generated on {now}</p>
        </div>

        <!-- Index Summary -->
        <div class="section">
            <h2>📊 Index Summary</h2>
            {df_to_html(index_summary, limit=10)}
        </div>

        <!-- Market Pulse -->
        <div class="section">
            <h2>📈 Market Pulse</h2>
            <h3>Top Gainers (PKR)</h3>
            {df_to_html(market_pulse['gainers'], limit=5)}
            
            <h3>Top Losers (PKR)</h3>
            {df_to_html(market_pulse['losers'], limit=5)}
            
            <h3>Most Active (by Volume)</h3>
            {df_to_html(market_pulse['active'], limit=5)}
        </div>

        <!-- Sector Performance -->
        <div class="section">
            <h2>🏭 Sector Performance</h2>
            {df_to_html(sector_data, limit=10)}
        </div>

        <!-- Portfolio Watchlist -->
        <div class="section">
            <h2>💼 Your Portfolio Watchlist</h2>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price (PKR)</th>
                        <th>Change %</th>
                        <th>Volume</th>
                        <th>P/E</th>
                        <th>Div Yield</th>
                        <th>52W High</th>
                        <th>52W Low</th>
                    </tr>
                </thead>
                <tbody>
    """
    for symbol in STOCK_SYMBOLS:
        q = quotes.get(symbol, {})
        f = fundamentals.get(symbol, {})
        change_pct = q.get('change_pct', 'N/A')
        change_class = ''
        if isinstance(change_pct, (int, float)):
            change_class = 'positive' if change_pct > 0 else 'negative' if change_pct < 0 else ''
        html += f"""
                    <tr>
                        <td><strong>{symbol}</strong></td>
                        <td>{q.get('price', 'N/A')}</td>
                        <td class="{change_class}">{change_pct}</td>
                        <td>{q.get('volume', 'N/A')}</td>
                        <td>{f.get('P/E', 'N/A')}</td>
                        <td>{f.get('Div Yield', 'N/A')}</td>
                        <td>{f.get('52W High', 'N/A')}</td>
                        <td>{f.get('52W Low', 'N/A')}</td>
                    </tr>
        """

    html += f"""
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>🕌 All stocks verified on PSX-KMI index</p>
            <p>Data sourced from PSX via pypsx | This is for informational purposes only.</p>
        </div>
    </body>
    </html>
    """
    return html

# ------------------------------------------------------------
# 3. Email Sending Function
# ------------------------------------------------------------

def send_html_email(subject, html_body):
    """Send an HTML email using Resend API."""
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

# ------------------------------------------------------------
# 4. Main Execution
# ------------------------------------------------------------

def main():
    print("🚀 Generating PSX Market Intelligence Report...")
    
    # 1. Fetch all data
    print("📡 Fetching market data...")
    quotes = fetch_stock_quotes(STOCK_SYMBOLS)
    fundamentals = {s: fetch_stock_fundamentals(s) for s in STOCK_SYMBOLS}
    market_pulse = fetch_market_pulse()
    index_summary = fetch_index_summary()
    sector_data = fetch_sector_performance()
    
    # 2. Generate HTML report
    print("📝 Generating HTML report...")
    html_report = generate_html_report(quotes, fundamentals, market_pulse, index_summary, sector_data)
    
    # 3. Send email
    subject = f"PSX Market Report - {datetime.now().strftime('%Y-%m-%d')}"
    email_sent = send_html_email(subject, html_report)
    
    if email_sent:
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.")

if __name__ == "__main__":
    main()
