# GEX Dashboard

Local dashboard that shows live connection health for three data sources
(NinjaTrader footprint/levels, IBKR, Unusual Whales) plus a free Yahoo
Finance fallback, and merges their data toward an SPX/SPY/ES trading view.

This must run **on the same Windows machine as NinjaTrader and TWS/IB
Gateway** -- it reads a file NinjaTrader writes, and talks to TWS over a
local socket. It will not work from a cloud machine.

## Setup

1. Install Python 3.11+ if you haven't already.
2. `pip install -r requirements.txt`
3. Set your Unusual Whales key: `set UNUSUAL_WHALES_API_KEY=your_key` (Windows cmd)
   or `$env:UNUSUAL_WHALES_API_KEY="your_key"` (PowerShell).
4. In NinjaTrader 8: copy `ninjatrader/LevelExporter.cs` into
   `Documents\NinjaTrader 8\bin\Custom\Indicators\`, open the NinjaScript
   Editor, compile (F5), and add "LevelExporter" to your ES chart.
5. In TWS or IB Gateway: enable API access (Configure > API > Settings >
   Enable ActiveX and Socket Clients), note the port (7497 for TWS paper
   by default).
6. `python server.py`
7. Open http://127.0.0.1:8787

## What "connected" means per box

- **NinjaTrader**: the export file at
  `Documents\NinjaTrader 8\bin\Custom\exports\levels.json` exists and was
  updated within the last 90 seconds.
- **IBKR**: a live socket handshake to TWS/Gateway on `127.0.0.1:7497`
  succeeded just now.
- **Unusual Whales**: the GEX API call for SPX succeeded.
- **Yahoo Finance**: `yfinance` could fetch a live quote. This is a free
  fallback only -- delayed, and its GEX approximation
  (`connectors/yahoo_connector.approx_gex`) is a rough local calculation,
  not dealer-verified positioning. Cross-check, don't trade on it alone.

## Known gaps / next steps

- `LevelExporter.cs`'s cumulative delta is a close-vs-open approximation,
  not real bid/ask delta -- true footprint delta requires switching NT8's
  chart to Volumetric bars (see comment in the file).
- The merge engine that turns all four sources into one scenario/signal
  view (the "Play 1/2/3" style playbook) isn't built yet -- this phase
  is connection health + raw data only.
- `gex/gex_calc.py`'s field-name guesses for the UW spot-exposure response
  should be confirmed with `scripts/inspect_uw_response.py` against a real
  API key.
