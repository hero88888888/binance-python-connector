"""OHLCV schema — candlestick / kline bar data model.

Maps to Binance ``/api/v3/klines`` and ``@kline`` WebSocket stream.
"""

from __future__ import annotations

from pydantic import ConfigDict

from binance_book.schemas.base import BaseTick


class OHLCVBar(BaseTick):
    """A single OHLCV candlestick bar.

    Fields
    ------
    TIMESTAMP : int
        Bar open time in milliseconds since epoch (UTC).
    SYMBOL : str, optional
        Trading pair symbol.
    OPEN : float
        Opening price.
    HIGH : float
        Highest price during the bar.
    LOW : float
        Lowest price during the bar.
    CLOSE : float
        Closing price.
    VOLUME : float
        Total traded volume in base asset units.
    CLOSE_TIME : int
        Bar close time in milliseconds since epoch (UTC).
    QUOTE_VOLUME : float
        Total traded volume in quote asset units.
    TRADE_COUNT : int
        Number of trades during the bar.
    TAKER_BUY_VOLUME : float
        Taker buy volume in base asset units.
    TAKER_BUY_QUOTE_VOLUME : float
        Taker buy volume in quote asset units.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    OPEN: float
    HIGH: float
    LOW: float
    CLOSE: float
    VOLUME: float
    CLOSE_TIME: int
    QUOTE_VOLUME: float = 0.0
    TRADE_COUNT: int = 0
    TAKER_BUY_VOLUME: float = 0.0
    TAKER_BUY_QUOTE_VOLUME: float = 0.0

    @staticmethod
    def from_binance_kline(data: list, symbol: str | None = None) -> "OHLCVBar":
        """Parse a Binance kline array into an OHLCVBar model.

        Parameters
        ----------
        data : list
            Raw Binance kline array: ``[open_time, open, high, low, close,
            volume, close_time, quote_volume, trade_count,
            taker_buy_base_vol, taker_buy_quote_vol, ignore]``.
        symbol : str, optional
            Trading pair symbol.
        """
        return OHLCVBar(
            TIMESTAMP=data[0],
            SYMBOL=symbol,
            OPEN=float(data[1]),
            HIGH=float(data[2]),
            LOW=float(data[3]),
            CLOSE=float(data[4]),
            VOLUME=float(data[5]),
            CLOSE_TIME=data[6],
            QUOTE_VOLUME=float(data[7]),
            TRADE_COUNT=int(data[8]),
            TAKER_BUY_VOLUME=float(data[9]),
            TAKER_BUY_QUOTE_VOLUME=float(data[10]),
        )

    @staticmethod
    def from_binance_ws(data: dict, symbol: str | None = None) -> "OHLCVBar":
        """Parse a Binance WebSocket kline event into an OHLCVBar model.

        Parameters
        ----------
        data : dict
            Raw Binance WebSocket kline payload (the ``k`` sub-object).
        symbol : str, optional
            Override symbol.
        """
        k = data.get("k", data)
        return OHLCVBar(
            TIMESTAMP=k["t"],
            SYMBOL=symbol or k.get("s"),
            OPEN=float(k["o"]),
            HIGH=float(k["h"]),
            LOW=float(k["l"]),
            CLOSE=float(k["c"]),
            VOLUME=float(k["v"]),
            CLOSE_TIME=k["T"],
            QUOTE_VOLUME=float(k["q"]),
            TRADE_COUNT=int(k["n"]),
            TAKER_BUY_VOLUME=float(k["V"]),
            TAKER_BUY_QUOTE_VOLUME=float(k["Q"]),
        )
