"""Investment universe per spec §2.

11 instruments traded via liquid ETF/futures proxies. VIX is regime-only,
not tradeable. BTC splices spot pre-2024 with IBIT post-2024.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Instrument:
    symbol: str
    exposure: str
    tradeable: bool
    notes: str = ""


INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument("SPY", "S&P 500", True, "History back to 1993"),
    Instrument("QQQ", "Nasdaq 100", True),
    Instrument("IWM", "Russell 2000", True),
    Instrument("IEF", "US 10Y Treasury", True, "7-10y Treasury ETF"),
    Instrument("SHY", "US 2Y Treasury", True),
    Instrument("GLD", "Gold", True, "Spot proxy"),
    Instrument("USO", "WTI Oil", True, "Acknowledge contango drag in paper"),
    Instrument("UUP", "DXY", True, "Bullish-USD ETF"),
    Instrument("VIX", "Volatility", False, "Regime indicator only — NOT tradeable"),
    Instrument("EEM", "MSCI EM", True),
    Instrument("BTC", "Bitcoin", True, "BTC spot pre-2024-01-11; IBIT post-2024-01-11"),
)

TRADEABLE_SYMBOLS: tuple[str, ...] = tuple(i.symbol for i in INSTRUMENTS if i.tradeable)
ALL_SYMBOLS: tuple[str, ...] = tuple(i.symbol for i in INSTRUMENTS)

BTC_SPLICE_DATE = date(2024, 1, 11)


def resolve_btc_ticker(d: date) -> str:
    """BTC splice rule per §2."""
    return "IBIT" if d >= BTC_SPLICE_DATE else "BTC-USD"


def is_tradeable(symbol: str) -> bool:
    return symbol in TRADEABLE_SYMBOLS
