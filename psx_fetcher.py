#!/usr/bin/env python3
"""Minimal PSX market data fetcher – runs in cron without errors."""

import os, json, sys, time, urllib.request
from datetime import datetime

PSX_URL = os.environ.get("PSX_URL", "https://dps.psx.com.pk/api/v2/market-summary")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/opt/render/project/src")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "market_data.json")

def main():
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                PSX_URL,
                headers={"User-Agent": "Mozilla/5.0 Titan/106"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                data = json.loads(raw)

            data["fetched_at"] = datetime.utcnow().isoformat()
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            stocks = data.get("stocks", [])
            print(f"[{datetime.utcnow().isoformat()}] Fetched {len(stocks)} stocks → {OUTPUT_FILE}")
            return   # success – exit

        except Exception as exc:
            print(f"Attempt {attempt}/{max_retries} failed: {exc}", file=sys.stderr)
            if attempt < max_retries:
                time.sleep(5)
            else:
                sys.exit(1)

if __name__ == "__main__":
    main()
