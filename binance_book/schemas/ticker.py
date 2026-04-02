"""DAY schema — 24-hour ticker statistics data model.

Maps to Binance ``/api/v3/ticker/24hr`` and ``@ticker`` WebSocket stream.
"""

from __future__ import annotations

from pydantic import ConfigDict

from binance_book.schemas.base import BaseTick


class Ticker24hr(BaseTick):
    """24-hour rolling window ticker statistics.

    Fields
    ------
    TIMESTAMP : int
        Event time in milliseconds since epoch (UTC).
    SYMBOL : str, optional
        Trading pair symbol.
    OPEN : float
        Opening price 24h ago.
    HIGH : float
        Highest price in the last 24h.
    LOW : float
        Lowest price in the last 24h.
    CLOSE : float
        Most recent trade price.
    VOLUME : float
        Total traded volume in base asset units over 24h.
    QUOTE_VOLUME : float
        Total traded volume in quote asset units over 24h.
    PRICE_CHANGE : float
        Absolute price change over 24h.
    PRICE_CHANGE_PERCENT : float
        Percentage price change over 24h.
    WEIGHTED_AVG_PRICE : float
        Volume-weighted average price over 24h.
    TRADE_COUNT : int
        Number of trades in 24h.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    OPEN: float
    HIGH: float
    LOW: float
    CLOSE: float
    VOLUME: float
    QUOTE_VOLUME: float = 0.0
    PRICE_CHANGE: float = 0.0
    PRICE_CHANGE_PERCENT: float = 0.0
    WEIGHTED_AVG_PRICE: float = 0.0
    TRADE_COUNT: int = 0

    @staticmethod
    def from_binance(data: dict) -> "Ticker24hr":
        """Parse a Binance 24hr ticker payload into a Ticker24hr model.

        Parameters
        ----------
        data : dict
            Raw Binance 24hr ticker payload (REST or WebSocket).
        """
        ts = data.get("E") or data.get("closeTime") or 0
        return Ticker24hr(
            TIMESTAMP=int(ts),
            SYMBOL=data.get("symbol") or data.get("s"),
            OPEN=float(data.get("openPrice", 0) or data.get("o", 0)),
            HIGH=float(data.get("highPrice", 0) or data.get("h", 0)),
            LOW=float(data.get("lowPrice", 0) or data.get("l", 0)),
            CLOSE=float(data.get("lastPrice", 0) or data.get("c", 0)),
            VOLUME=float(data.get("volume", 0) or data.get("v", 0)),
            QUOTE_VOLUME=float(data.get("quoteVolume", 0) or data.get("q", 0)),
            PRICE_CHANGE=float(data.get("priceChange", 0) or data.get("p", 0)),
            PRICE_CHANGE_PERCENT=float(data.get("priceChangePercent", 0) or data.get("P", 0)),
            WEIGHTED_AVG_PRICE=float(data.get("weightedAvgPrice", 0) or data.get("w", 0)),
            TRADE_COUNT=int(data.get("count", 0) or data.get("n", 0)),
        )
