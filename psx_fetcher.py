#!/usr/bin/env python3
"""
Titan PSX Fetcher – Always returns data, never fails cron.
If the real PSX API is unreachable, it generates mock data and logs a warning.
"""

import json, os, random, sys, time, urllib.request
from datetime import datetime

URL = os.environ.get("PSX_URL", "https://dps.psx.com.pk/api/v2/market-summary")
OUT = os.environ.get("OUTPUT_DIR", "/opt/render/project/src")
OUT_FILE = os.path.join(OUT, "market_data.json")

SYMBOLS = [
    "FFC", "EFERT", "MARI", "OGDC", "PPL", "HUBC",
    "MCB", "UBL", "NBP", "HBL", "LUCK", "DGKC",
    "MLCF", "FCCL", "ATRL", "NRL", "PRL", "PAEL", "SEARL",
]

def fetch_real():
    req = urllib.request.Request(URL, headers={"User-Agent": "Titan/106"})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
            data = json.loads(raw)
            return data
        except Exception as e:
            print(f"Attempt {attempt}/3 failed: {e}", file=sys.stderr)
            if attempt < 3:
                time.sleep(5)
    raise RuntimeError("PSX unreachable after 3 attempts")

def make_mock():
    """Generate plausible mock market data so the pipeline never stops."""
    stocks = []
    for sym in SYMBOLS:
        stocks.append({
            "symbol": sym,
            "current_price": round(random.uniform(50, 800), 2),
            "volume": random.randint(1000, 500000),
        })
    return {"stocks": stocks, "mock": True}

def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        data = fetch_real()
        data["mock"] = False
    except Exception:
        print("WARNING: Using MOCK data because PSX API is unavailable", file=sys.stderr)
        data = make_mock()

    data["fetched_at"] = datetime.utcnow().isoformat()
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    count = len(data.get("stocks", []))
    tag = "MOCK" if data.get("mock") else "LIVE"
    print(f"[{datetime.utcnow().isoformat()}] {tag} data – {count} stocks → {OUT_FILE}")

if __name__ == "__main__":
    main()
