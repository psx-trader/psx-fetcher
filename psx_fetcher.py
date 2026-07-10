#!/usr/bin/env python3
"""Simple PSX market‑data fetcher for cron."""

import os
import json
import sys
import urllib.request
from datetime import datetime

PSX_URL = os.environ.get("PSX_URL", "https://dps.psx.com.pk/api/v2/market-summary")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/opt/render/project/src")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "market_data.json")

def main():
    try:
        with urllib.request.urlopen(PSX_URL, timeout=15) as resp:
            raw = resp.read()
            data = json.loads(raw)

        # Add a timestamp so you know how fresh the data is
        data["fetched_at"] = datetime.utcnow().isoformat()

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        stocks = data.get("stocks", [])
        print(f"[{datetime.utcnow().isoformat()}] Fetched {len(stocks)} stocks → {OUTPUT_FILE}")

    except Exception as exc:
        print(f"ERROR fetching PSX data: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
