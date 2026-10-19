"""Derive call wall / put wall / gamma flip from Unusual Whales spot-exposure data.

The UW docs don't publish exact field names for the GEX endpoints, so this
module is defensive: it looks for a strike field and a gamma-exposure field
under a few likely names rather than hard-coding one schema. Run
`scripts/inspect_uw_response.py` once against your API key to see the real
field names, then tighten STRIKE_KEYS / GEX_KEYS below if needed.
"""
from dataclasses import dataclass

STRIKE_KEYS = ("strike", "strike_price")
GEX_KEYS = ("gamma_exposure", "gex", "spot_gex", "total_gamma", "gamma", "net_gamma")


@dataclass
class GexSummary:
    ticker: str
    spot: float | None
    call_wall: float | None
    put_wall: float | None
    gamma_flip: float | None
    raw_points: list[dict]


def _find(record: dict, keys: tuple[str, ...]) -> float | None:
    for k in keys:
        if k in record and record[k] is not None:
            try:
                return float(record[k])
            except (TypeError, ValueError):
                continue
    return None


def _extract_rows(payload: dict) -> list[dict]:
    if isinstance(payload, list):
        return payload
    for key in ("data", "results", "items"):
        if key in payload and isinstance(payload[key], list):
            return payload[key]
    raise ValueError(
        f"Could not find a list of per-strike rows in response; top-level keys: {list(payload.keys())}"
    )


def summarize(ticker: str, spot_exposure_payload: dict, spot: float | None = None) -> GexSummary:
    rows = _extract_rows(spot_exposure_payload)
    points = []
    for row in rows:
        strike = _find(row, STRIKE_KEYS)
        gex = _find(row, GEX_KEYS)
        if strike is None or gex is None:
            continue
        points.append({"strike": strike, "gex": gex})

    if not points:
        raise ValueError(
            "No rows had a recognizable strike/gamma field. "
            "Run scripts/inspect_uw_response.py and update STRIKE_KEYS/GEX_KEYS."
        )

    points.sort(key=lambda p: p["strike"])

    call_wall = max(points, key=lambda p: p["gex"])
    put_wall = min(points, key=lambda p: p["gex"])

    gamma_flip = None
    for a, b in zip(points, points[1:]):
        if a["gex"] == 0:
            gamma_flip = a["strike"]
            break
        if (a["gex"] < 0) != (b["gex"] < 0):
            span = b["gex"] - a["gex"]
            if span != 0:
                frac = (0 - a["gex"]) / span
                gamma_flip = a["strike"] + frac * (b["strike"] - a["strike"])
            break

    return GexSummary(
        ticker=ticker,
        spot=spot,
        call_wall=call_wall["strike"],
        put_wall=put_wall["strike"],
        gamma_flip=gamma_flip,
        raw_points=points,
    )
