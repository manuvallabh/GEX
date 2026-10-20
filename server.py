#!/usr/bin/env python3
"""Local dashboard server: polls NinjaTrader export, IBKR, Unusual Whales,
and the free Yahoo fallback, merges them into one state, and serves a
dashboard showing connection health for each source.

Run on the same machine as NinjaTrader and TWS/IB Gateway:

    export UNUSUAL_WHALES_API_KEY=xxx
    pip install -r requirements.txt
    python server.py

Then open http://127.0.0.1:8787
"""
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from connectors import ibkr_connector, ninja_connector, uw_connector, yahoo_connector

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "data" / "state.json"
POLL_SECONDS = 15

app = Flask(__name__, static_folder=None)
_state_lock = threading.Lock()
_state: dict = {"generated_at": None, "sources": {}}


def poll_once() -> dict:
    sources = {}

    # NinjaTrader (file-based export, see ninjatrader/LevelExporter.cs)
    ninja = ninja_connector.read_levels()
    sources["ninjatrader"] = {
        "connected": ninja.connected,
        "configured": ninja.last_update is not None,
        "error": ninja.error,
        "age_seconds": ninja.age_seconds,
        "data": ninja.levels,
    }

    # IBKR (requires TWS/Gateway running locally)
    try:
        ib = ibkr_connector.IBKRConnector()
        ib_status = ib.status(symbols=("SPX", "SPY", "ES"))
        ib.disconnect()
        sources["ibkr"] = {
            "connected": ib_status.connected,
            "configured": ibkr_connector.HAVE_IB_INSYNC,
            "error": ib_status.error,
            "data": ib_status.quotes,
        }
    except Exception as exc:
        sources["ibkr"] = {"connected": False, "configured": ibkr_connector.HAVE_IB_INSYNC, "error": str(exc), "data": {}}

    # Unusual Whales
    uw = uw_connector.status(tickers=("SPX",))
    sources["unusual_whales"] = {
        "connected": uw.connected,
        "configured": uw.configured,
        "error": uw.error,
        "data": uw.gex,
    }

    # Free fallback: Yahoo Finance
    yprices = yahoo_connector.get_prices()
    sources["yahoo_finance"] = {
        "connected": yprices.connected,
        "configured": yahoo_connector.HAVE_YFINANCE,
        "error": yprices.error,
        "data": yprices.prices,
    }

    return {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": sources}


def poll_loop():
    global _state
    while True:
        try:
            new_state = poll_once()
            with _state_lock:
                _state = new_state
            STATE_PATH.parent.mkdir(exist_ok=True)
            STATE_PATH.write_text(json.dumps(new_state, indent=2, default=str))
        except Exception as exc:  # keep the loop alive no matter what
            print(f"[poll_loop] error: {exc}")
        time.sleep(POLL_SECONDS)


@app.route("/api/state")
def api_state():
    with _state_lock:
        return jsonify(_state)


@app.route("/")
def index():
    return send_from_directory(ROOT / "dashboard", "index.html")


if __name__ == "__main__":
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    app.run(host="127.0.0.1", port=8787, debug=False)
