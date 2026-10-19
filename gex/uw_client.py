"""Thin client for the Unusual Whales public API.

Docs: https://api.unusualwhales.com/docs
Auth: Authorization: Bearer <UNUSUAL_WHALES_API_KEY>
"""
import os
import time
from typing import Any

import requests

BASE_URL = "https://api.unusualwhales.com"


class UWError(RuntimeError):
    pass


class UWClient:
    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        self.api_key = api_key or os.environ.get("UNUSUAL_WHALES_API_KEY")
        if not self.api_key:
            raise UWError(
                "No API key. Set UNUSUAL_WHALES_API_KEY in your environment or pass api_key=."
            )
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        )

    def _get(self, path: str, params: dict[str, Any] | None = None, retries: int = 2) -> dict:
        url = f"{BASE_URL}{path}"
        last_exc = None
        for attempt in range(retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(0.5 * (attempt + 1))
        raise UWError(f"GET {path} failed after retries: {last_exc}")

    # -- Greek / gamma exposure -------------------------------------------------

    def greek_exposure_by_strike(self, ticker: str, date: str | None = None) -> dict:
        """Per-strike greek exposure (gamma/delta/vanna/charm aggregates)."""
        return self._get(f"/api/stock/{ticker}/greek-exposure/strike", _params(date=date))

    def greek_exposure(self, ticker: str, date: str | None = None, timeframe: str | None = None) -> dict:
        return self._get(f"/api/stock/{ticker}/greek-exposure", _params(date=date, timeframe=timeframe))

    def spot_exposures_by_strike(
        self,
        ticker: str,
        date: str | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        limit: int | None = None,
    ) -> dict:
        """Spot GEX per strike -- the curve you derive call wall / put wall / gamma flip from."""
        return self._get(
            f"/api/stock/{ticker}/spot-exposures/strike",
            _params(date=date, min_strike=min_strike, max_strike=max_strike, limit=limit),
        )

    def spot_exposures_1m(self, ticker: str, date: str | None = None) -> dict:
        """Spot GEX per 1-minute interval (dollar gamma per 1% move)."""
        return self._get(f"/api/stock/{ticker}/spot-exposures", _params(date=date))

    def max_pain(self, ticker: str, date: str | None = None) -> dict:
        return self._get(f"/api/stock/{ticker}/max-pain", _params(date=date))

    # -- Options flow -------------------------------------------------------

    def flow_alerts(
        self,
        ticker_symbol: str | None = None,
        min_premium: float | None = None,
        is_sweep: bool | None = None,
        is_ask_side: bool | None = None,
        is_bid_side: bool | None = None,
        is_call: bool | None = None,
        is_put: bool | None = None,
        issue_types: list[str] | None = None,
        min_dte: int | None = None,
        max_dte: int | None = None,
        newer_than: str | None = None,
        limit: int = 100,
    ) -> dict:
        params = _params(
            ticker_symbol=ticker_symbol,
            min_premium=min_premium,
            is_sweep=is_sweep,
            is_ask_side=is_ask_side,
            is_bid_side=is_bid_side,
            is_call=is_call,
            is_put=is_put,
            min_dte=min_dte,
            max_dte=max_dte,
            newer_than=newer_than,
            limit=limit,
        )
        if issue_types:
            params["issue_types[]"] = issue_types
        return self._get("/api/option-trades/flow-alerts", params)


def _params(**kwargs) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}
