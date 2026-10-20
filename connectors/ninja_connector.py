"""NinjaTrader connector.

NinjaTrader has no first-class Python API. The practical bridge is:
a NinjaScript indicator (see ninjatrader/LevelExporter.cs) runs inside NT8
on your chart and writes a small JSON file to disk every few seconds.
This module just reads that file and reports whether it's fresh.

"Connected" here means: the export file exists and was updated recently
(default: within the last 90 seconds). If NinjaTrader isn't running, or
the indicator isn't attached to a chart, the file goes stale and this
reports disconnected -- that's the signal, not a live socket.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXPORT_PATH = Path.home() / "Documents" / "NinjaTrader 8" / "bin" / "Custom" / "exports" / "levels.json"
STALE_AFTER_SECONDS = 90


@dataclass
class NinjaStatus:
    connected: bool
    last_update: float | None
    age_seconds: float | None
    error: str | None
    levels: dict | None


def read_levels(export_path: Path | str = DEFAULT_EXPORT_PATH) -> NinjaStatus:
    path = Path(export_path)
    if not path.exists():
        return NinjaStatus(
            connected=False,
            last_update=None,
            age_seconds=None,
            error=f"Export file not found at {path}. Is the LevelExporter indicator attached in NT8?",
            levels=None,
        )

    try:
        mtime = path.stat().st_mtime
        age = time.time() - mtime
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return NinjaStatus(connected=False, last_update=None, age_seconds=None, error=str(exc), levels=None)

    connected = age <= STALE_AFTER_SECONDS
    return NinjaStatus(
        connected=connected,
        last_update=mtime,
        age_seconds=age,
        error=None if connected else f"Export file is stale ({age:.0f}s old) -- is NinjaTrader running?",
        levels=payload,
    )
