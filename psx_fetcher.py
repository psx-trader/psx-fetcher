def fetch_quote_pypsx(symbol):
    """Try to fetch data using pypsx library - corrected API"""
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
                    # If all fail, fallback to HTTP
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
    """Fallback: Fetch data directly from API"""
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
