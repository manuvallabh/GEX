"""IBKR connector via ib_insync.

Requires TWS or IB Gateway running locally with API access enabled
(Configure > API > Settings > Enable ActiveX and Socket Clients).
Default ports: 7497 (TWS paper), 7496 (TWS live), 4002/4001 (Gateway).

"Connected" means a live socket handshake to TWS/Gateway succeeded.
This module degrades gracefully (returns connected=False with an error
string) if ib_insync isn't installed or TWS isn't reachable, so the
dashboard can still run with the other sources up.
"""
from dataclasses import dataclass

try:
    from ib_insync import IB, Index, Stock, Future
    HAVE_IB_INSYNC = True
except ImportError:
    HAVE_IB_INSYNC = False


@dataclass
class IBKRStatus:
    connected: bool
    error: str | None
    quotes: dict


class IBKRConnector:
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 17):
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = IB() if HAVE_IB_INSYNC else None

    def status(self, symbols: tuple[str, ...] = ("SPX", "SPY")) -> IBKRStatus:
        if not HAVE_IB_INSYNC:
            return IBKRStatus(connected=False, error="ib_insync not installed (pip install ib_insync)", quotes={})

        try:
            if not self._ib.isConnected():
                self._ib.connect(self.host, self.port, clientId=self.client_id, timeout=4)
        except Exception as exc:
            return IBKRStatus(connected=False, error=f"Could not reach TWS/Gateway at {self.host}:{self.port}: {exc}", quotes={})

        quotes = {}
        for sym in symbols:
            try:
                contract = self._contract_for(sym)
                if sym == "ES":
                    # Futures need a resolved expiry; let IB pick the front month.
                    details = self._ib.reqContractDetails(contract)
                    if not details:
                        raise ValueError("No ES contract details returned (check TWS market data subscriptions)")
                    contract = sorted(details, key=lambda d: d.contract.lastTradeDateOrContractMonth)[0].contract
                ticker = self._ib.reqMktData(contract, "", False, False)
                self._ib.sleep(1.0)  # let a snapshot arrive
                quotes[sym] = {
                    "last": ticker.last,
                    "bid": ticker.bid,
                    "ask": ticker.ask,
                    "close": ticker.close,
                }
            except Exception as exc:
                quotes[sym] = {"error": str(exc)}

        return IBKRStatus(connected=True, error=None, quotes=quotes)

    @staticmethod
    def _contract_for(symbol: str):
        if symbol == "SPX":
            return Index("SPX", "CBOE")
        if symbol == "SPY":
            return Stock("SPY", "ARCA", "USD")
        if symbol == "ES":
            return Future("ES", exchange="CME")
        raise ValueError(f"Unknown symbol for IBKR contract: {symbol}")

    def disconnect(self):
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
