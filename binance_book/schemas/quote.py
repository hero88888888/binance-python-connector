"""Quote and best bid/offer (BBO) data model.

Maps to Binance ``@bookTicker`` WebSocket stream and ``/api/v3/ticker/bookTicker``.
"""

from __future__ import annotations

from pydantic import ConfigDict

from binance_book.schemas.base import BaseTick


class Quote(BaseTick):
    """A best-bid/best-offer quote event.

    Fields
    ------
    TIMESTAMP : int
        Event time in milliseconds since epoch (UTC).
    SYMBOL : str, optional
        Trading pair symbol (e.g. ``"BTCUSDT"``).
    BID_PRICE : float
        Best bid price.
    BID_SIZE : float
        Quantity available at the best bid.
    ASK_PRICE : float
        Best ask price.
    ASK_SIZE : float
        Quantity available at the best ask.
    UPDATE_ID : int
        Order book update ID at the time of this quote.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    BID_PRICE: float
    BID_SIZE: float
    ASK_PRICE: float
    ASK_SIZE: float
    UPDATE_ID: int = 0

    @property
    def SPREAD(self) -> float:
        """Quoted spread (ask - bid)."""
        return self.ASK_PRICE - self.BID_PRICE

    @property
    def MID_PRICE(self) -> float:
        """Mid price ((ask + bid) / 2)."""
        return (self.ASK_PRICE + self.BID_PRICE) / 2.0

    @property
    def SPREAD_BPS(self) -> float:
        """Spread in basis points relative to mid price."""
        mid = self.MID_PRICE
        if mid == 0:
            return 0.0
        return (self.SPREAD / mid) * 10000.0

    @staticmethod
    def from_binance(data: dict, symbol: str | None = None, timestamp: int | None = None) -> "Quote":
        """Parse a Binance bookTicker payload into a Quote model.

        Parameters
        ----------
        data : dict
            Raw Binance bookTicker payload. Accepts both REST format
            (``symbol``, ``bidPrice``, etc.) and WebSocket format (``s``,
            ``b``, ``B``, ``a``, ``A``).
        symbol : str, optional
            Override symbol.
        timestamp : int, optional
            Override timestamp (Binance REST bookTicker has no timestamp).
        """
        if "b" in data and "a" in data and len(data.get("b", "")) > 0:
            from binance_book.schemas.base import Timestamp

            return Quote(
                TIMESTAMP=data.get("E", timestamp or Timestamp.now_ms()),
                SYMBOL=symbol or data.get("s"),
                BID_PRICE=float(data["b"]),
                BID_SIZE=float(data["B"]),
                ASK_PRICE=float(data["a"]),
                ASK_SIZE=float(data["A"]),
                UPDATE_ID=data.get("u", 0),
            )
        from binance_book.schemas.base import Timestamp

        return Quote(
            TIMESTAMP=timestamp or Timestamp.now_ms(),
            SYMBOL=symbol or data.get("symbol"),
            BID_PRICE=float(data["bidPrice"]),
            BID_SIZE=float(data["bidQty"]),
            ASK_PRICE=float(data["askPrice"]),
            ASK_SIZE=float(data["askQty"]),
            UPDATE_ID=0,
        )
