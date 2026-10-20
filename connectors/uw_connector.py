"""Unusual Whales connector status + data wrapper for the dashboard."""
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gex.gex_calc import summarize  # noqa: E402
from gex.uw_client import UWClient, UWError  # noqa: E402


@dataclass
class UWStatus:
    connected: bool
    configured: bool
    error: str | None
    gex: dict


def status(tickers: tuple[str, ...] = ("SPX",)) -> UWStatus:
    try:
        client = UWClient()
    except UWError as exc:
        return UWStatus(connected=False, configured=False, error=str(exc), gex={})

    gex_out = {}
    any_ok = False
    for ticker in tickers:
        try:
            payload = client.spot_exposures_by_strike(ticker)
            summary = summarize(ticker, payload)
            gex_out[ticker] = {
                "call_wall": summary.call_wall,
                "put_wall": summary.put_wall,
                "gamma_flip": summary.gamma_flip,
            }
            any_ok = True
        except (UWError, ValueError) as exc:
            gex_out[ticker] = {"error": str(exc)}

    return UWStatus(
        connected=any_ok,
        configured=True,
        error=None if any_ok else "All ticker requests failed",
        gex=gex_out,
    )
