#!/usr/bin/env python3
"""One-time helper: print raw UW API responses so we can confirm real field
names before trusting gex_calc.py's guesses. Run this first.

Usage:
    export UNUSUAL_WHALES_API_KEY=xxx
    python scripts/inspect_uw_response.py SPX
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gex.uw_client import UWClient  # noqa: E402


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPX"
    client = UWClient()

    for name, fn in [
        ("spot_exposures_by_strike", lambda: client.spot_exposures_by_strike(ticker, limit=5)),
        ("greek_exposure_by_strike", lambda: client.greek_exposure_by_strike(ticker)),
        ("max_pain", lambda: client.max_pain(ticker)),
        ("flow_alerts", lambda: client.flow_alerts(ticker_symbol=ticker, limit=3)),
    ]:
        print(f"\n=== {name} ===")
        try:
            payload = fn()
            print(json.dumps(payload, indent=2)[:3000])
        except Exception as exc:
            print(f"FAILED: {exc}")


if __name__ == "__main__":
    main()
