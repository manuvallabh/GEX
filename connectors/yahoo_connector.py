"""Free fallback data source: Yahoo Finance via yfinance.

Use this when UW/IBKR are down or you want a free sanity-check. Two things
it provides:
  1. Live(ish) price for SPY/QQQ/^GSPC etc -- delayed ~15min typically.
  2. A *rough* GEX approximation computed locally from the public option
     chain (open interest + implied vol), using Black-Scholes gamma.

Caveat on #2: this is NOT what UW/SpotGamma give you. We don't know real
dealer positioning (who's actually long/short), so this uses the common
retail approximation -- call OI = positive dealer gamma, put OI = negative
dealer gamma -- which is a simplification, not verified fact. Treat this
as a cheap directional sanity check against the UW numbers, not a
replacement for them.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import yfinance as yf
    HAVE_YFINANCE = True
except ImportError:
    HAVE_YFINANCE = False


@dataclass
class YahooStatus:
    connected: bool
    error: str | None
    prices: dict
    gex_approx: dict


def _bs_gamma(spot: float, strike: float, iv: float, dte_years: float) -> float:
    if iv <= 0 or dte_years <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + 0.5 * iv * iv * dte_years) / (iv * math.sqrt(dte_years))
    return math.exp(-0.5 * d1 * d1) / (spot * iv * math.sqrt(2 * math.pi * dte_years))


def get_prices(tickers: tuple[str, ...] = ("SPY", "^GSPC", "QQQ", "^NDX")) -> YahooStatus:
    if not HAVE_YFINANCE:
        return YahooStatus(connected=False, error="yfinance not installed (pip install yfinance)", prices={}, gex_approx={})

    prices = {}
    try:
        for t in tickers:
            info = yf.Ticker(t).fast_info
            prices[t] = {"last": info.get("lastPrice"), "prev_close": info.get("previousClose")}
        return YahooStatus(connected=True, error=None, prices=prices, gex_approx={})
    except Exception as exc:
        return YahooStatus(connected=False, error=str(exc), prices=prices, gex_approx={})


def approx_gex(ticker: str = "SPY", max_expiries: int = 1) -> dict:
    """Rough GEX curve from the nearest expiry's public option chain."""
    if not HAVE_YFINANCE:
        return {"error": "yfinance not installed"}

    tk = yf.Ticker(ticker)
    expiries = tk.options[:max_expiries]
    if not expiries:
        return {"error": "no option expiries returned"}

    spot = tk.fast_info.get("lastPrice")
    if not spot:
        return {"error": "no spot price available"}

    by_strike: dict[float, float] = {}
    for expiry in expiries:
        chain = tk.option_chain(expiry)
        dte_years = max((datetime.strptime(expiry, "%Y-%m-%d").replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days, 1) / 365.0

        for row in chain.calls.itertuples():
            g = _bs_gamma(spot, row.strike, row.impliedVolatility, dte_years)
            by_strike[row.strike] = by_strike.get(row.strike, 0.0) + g * row.openInterest * 100 * spot * spot * 0.01

        for row in chain.puts.itertuples():
            g = _bs_gamma(spot, row.strike, row.impliedVolatility, dte_years)
            by_strike[row.strike] = by_strike.get(row.strike, 0.0) - g * row.openInterest * 100 * spot * spot * 0.01

    if not by_strike:
        return {"error": "no option rows with usable OI/IV"}

    call_wall = max(by_strike.items(), key=lambda kv: kv[1])
    put_wall = min(by_strike.items(), key=lambda kv: kv[1])
    return {
        "spot": spot,
        "call_wall": call_wall[0],
        "put_wall": put_wall[0],
        "note": "Rough local approximation -- cross-check against UW, do not trade on this alone.",
    }
