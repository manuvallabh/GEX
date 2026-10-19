#!/usr/bin/env python3
"""Pull GEX (call wall / put wall / gamma flip) for one or more tickers and
write them to gex.json -- the file the merge engine (added later) reads.

Usage:
    export UNUSUAL_WHALES_API_KEY=xxx
    python scripts/fetch_gex.py SPX ES  # ES has no options GEX; skip futures here
    python scripts/fetch_gex.py SPX NDX
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gex.gex_calc import summarize  # noqa: E402
from gex.uw_client import UWClient, UWError  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "gex.json"


def main():
    tickers = sys.argv[1:] or ["SPX"]
    client = UWClient()

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "tickers": {}}

    for ticker in tickers:
        try:
            payload = client.spot_exposures_by_strike(ticker)
            summary = summarize(ticker, payload)
            out["tickers"][ticker] = {
                "call_wall": summary.call_wall,
                "put_wall": summary.put_wall,
                "gamma_flip": summary.gamma_flip,
                "n_strikes": len(summary.raw_points),
            }
            print(
                f"{ticker}: call_wall={summary.call_wall} put_wall={summary.put_wall} "
                f"gamma_flip={summary.gamma_flip}"
            )
        except (UWError, ValueError) as exc:
            print(f"{ticker}: FAILED - {exc}", file=sys.stderr)
            out["tickers"][ticker] = {"error": str(exc)}

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
