# Project Handoff: SPX/SPY/ES Trading Dashboard

This document summarizes a long conversation with a cloud Claude Code
session that scaffolded this repo. It exists so a **local** Claude Code
session (the one with real access to NinjaTrader, TWS, and this folder)
can pick up full context without re-deriving it. Read this before making
changes.

## The goal

The user trades SPX/SPY options and ES/NQ futures. They follow two
traders' public methodologies and want to build their own system that
merges both into one dashboard/signal engine:

1. **"Adam Set" (@Adaamset on X, SetStack/Substack newsletter)** — trades
   ES futures using Market/Auction Profile (TPO) theory: composite
   multi-day profiles, tiered pivot levels (Overnight High/Low →
   multi-day "SetStack" composite support/resistance → Minor Pivot →
   intraday recovery), pre-session scripted scenarios ("I see this
   Auction in three states..."), and footprint/order-flow confirmation
   at those levels. Sizes 0DTE SPX options with risk defined in the
   underlying's price (not the option's P&L).

2. **"Eagle" (Discord, "elite-trading-floor" channel)** — reads **SPX
   options block-print/sweep tape** live: large size trades at a given
   strike, compared to the live bid/ask to infer aggressor side (trade at
   ask ≈ buyer-initiated, trade at bid ≈ seller-initiated), to infer
   dealer hedging pressure. Caveat established in conversation: **you
   cannot know opening vs. closing from the tape alone** — only
   next-day open interest changes confirm that. "On the fence" calls
   happen when bid/ask context is too thin (e.g. bid=0) to read cleanly.

## Architecture decided on

Three data sources, each on its own natural refresh cadence — do **not**
force them onto one uniform poll loop:

| Source | What it gives | Refresh | Why |
|---|---|---|---|
| **NinjaTrader** (file export) | ES footprint/auction structure: POC/VAH/VAL, cumulative delta, session H/L | ~60s | Auction structure evolves through the session |
| **Unusual Whales API** | Dealer GEX (call wall / put wall / gamma flip), options flow/sweep alerts (this *is* Eagle's tape, pre-classified by UW: `is_ask_side`/`is_bid_side`/`has_sweep`/`total_premium`) | GEX: 15-30 min (OI barely moves intraday) · flow: event-driven, never poll this slowly | |
| **IBKR API** | Execution (placing/managing SPX option trades), SPX/SPY/ES live quotes, secondary data cross-check | real-time, on demand | Primarily for execution, not signal generation |
| **Yahoo Finance (yfinance)** | Free fallback: delayed prices + a *rough* local GEX approximation computed from public option OI/IV via Black-Scholes gamma | whenever | Sanity-check only, not a real GEX replacement — flagged clearly in code comments |

**Symbol scope, deliberately narrow for now**: build and validate
**SPX + ES only** first. NDX + NQ is phase 2, once the pipeline is
proven. QQQ/SPY and MES/MNQ were explicitly deprioritized (ETF
settlement quirks / just fractional duplicates of ES/NQ).

Merge design:

```
NinjaTrader (NT8, footprint)      Unusual Whales API         IBKR API
  NinjaScript writes JSON           GEX + flow-alerts           execution + quotes
  every ~60s                        (different cadences)
        |                                |                        |
        v                                v                        v
   levels.json                      gex.json / flow.json      (on-demand)
        \_______________  merge_engine.py (cheap, 1-5 min) ______/
                               |
                               v
                          state.json
                               |
                               v
                         dashboard.html  (polls state.json)
```

## What's actually built so far (this repo)

- `gex/uw_client.py` — UW API client. Confirmed real endpoints (not
  guessed): base `https://api.unusualwhales.com`, auth
  `Authorization: Bearer <key>`, `GET /api/stock/{ticker}/spot-exposures/strike`,
  `GET /api/stock/{ticker}/greek-exposure/strike`, `GET /api/stock/{ticker}/max-pain`,
  `GET /api/option-trades/flow-alerts` (params include `ticker_symbol`,
  `is_sweep`, `is_ask_side`/`is_bid_side`, `min_premium`, `issue_types[]`
  with `"index"` for SPX/NDX).
- `gex/gex_calc.py` — derives call wall / put wall / gamma flip from UW's
  spot-exposure response. **UW doesn't publish exact JSON field names
  publicly**, so this is written defensively (tries several likely key
  names). Run `scripts/inspect_uw_response.py` against a real API key
  first to confirm/correct `STRIKE_KEYS`/`GEX_KEYS` in that file.
- `scripts/inspect_uw_response.py` — one-time helper, dumps raw UW JSON
  so field names can be confirmed.
- `scripts/fetch_gex.py` — CLI, writes `data/gex.json`.
- `connectors/ninja_connector.py` — reads the JSON file NinjaTrader
  exports; "connected" = file updated within last 90s.
- `connectors/ibkr_connector.py` — `ib_insync` client, connects to local
  TWS/Gateway (127.0.0.1:7497 default), pulls SPX/SPY/ES quotes.
  Degrades gracefully (reports `configured: false`) if `ib_insync` isn't
  installed or TWS isn't reachable.
- `connectors/uw_connector.py` — wraps the UW client as connected/
  disconnected status for the dashboard.
- `connectors/yahoo_connector.py` — free fallback, `yfinance` prices +
  local Black-Scholes GEX approximation (explicitly caveatted in code
  comments as not dealer-verified, sanity-check only).
- `server.py` — Flask app, polls all four sources every 15s, serves
  `/api/state` (JSON) and the dashboard at `/`.
- `dashboard/index.html` — one box per source (NinjaTrader, IBKR,
  Unusual Whales, Yahoo Finance), green/amber/red dot:
  - **green** = connected
  - **amber "Not Configured"** = dependency/key simply missing (not an
    outage) — e.g. UW key unset, `ib_insync`/`yfinance` not installed,
    NinjaTrader export never seen yet
  - **red "Disconnected"** = was configured but the live check failed
- `ninjatrader/LevelExporter.cs` — NT8 NinjaScript indicator. Writes
  session POC/VAH/VAL (price/volume histogram approximation) and an
  **approximate** cumulative delta (close-vs-open direction, not real
  bid/ask delta — flagged as TODO in the file) to
  `Documents\NinjaTrader 8\bin\Custom\exports\levels.json` every bar
  close. **For true order-flow delta, the chart needs NT8's Volumetric
  Bars type** — the file has comments on how to upgrade this.
- `README.md` — setup steps (pip install, env var, NinjaScript compile +
  attach, TWS API enable, run `python server.py`, open
  `http://127.0.0.1:8787`).

All of the above was smoke-tested in the cloud sandbox: Python syntax
verified, server boots, `/api/state` returns correctly-shaped JSON with
graceful degradation when a source isn't configured, dashboard HTML
serves and renders. **None of it has been tested against real
NinjaTrader, real TWS, or a real UW key** — that can only happen locally,
which is the whole reason for this handoff.

## Known gaps / what's NOT built yet

1. **The merge engine** (`merge_engine.py` referenced in the architecture
   diagram above) doesn't exist yet. This is the piece that would turn
   the four sources' current state into Adam/Eagle-style scenario output
   (e.g. "Play 1: 65% prob, dip-buy trigger X, target Y, stop Z").
   Everything built so far is **connection health + raw data plumbing
   only**.
2. UW's exact GEX response field names are unconfirmed — run
   `scripts/inspect_uw_response.py` with a real key and fix
   `gex/gex_calc.py`'s `STRIKE_KEYS`/`GEX_KEYS` if the guesses are wrong.
3. `LevelExporter.cs`'s cumulative delta is an approximation, not true
   footprint delta. Needs NT8 Volumetric Bars to do this properly.
4. The user has **other, possibly overlapping local Claude Code
   projects** already on this machine under `Downloads\Claude`:
   `ibkr-monitor`, `NinjaDayTrader`, `IBKR_Automation`, `FeedBot`,
   `DayTrade`, `Trading Algos Testing`,
   `glamping-capital-engine-uw-integrati...` (name suggests it already
   has UW integration). **These were never inspected in this
   conversation.** Worth checking before building more in this repo —
   there may be reusable code or outright duplication to avoid.

## Practical setup reminders

- This must run **on the same Windows machine as NinjaTrader and
  TWS/IB Gateway** — both only expose local files/sockets, no cloud
  session can reach them.
- `pip install -r requirements.txt` (uses `python3 -m pip` if there's a
  python version mismatch between `python3` and `pip` on this machine,
  as there was in the cloud sandbox).
- Symbols in scope right now: **SPX, SPY (display-only, no new
  building), ES**. NDX/NQ later. QQQ/SPY-options and MES/MNQ explicitly
  out of scope per earlier decision.

## Suggested next step for whoever picks this up

1. Check the other local project folders listed above for overlap first.
2. Run `scripts/inspect_uw_response.py` against a real UW key, fix field
   names in `gex_calc.py` if needed.
3. Compile + attach `LevelExporter.cs` in NT8, confirm the dashboard's
   NinjaTrader box goes green.
4. Enable TWS API access, confirm the IBKR box goes green.
5. Only once all three real boxes are green: build `merge_engine.py` and
   the scenario/signal layer on top.
