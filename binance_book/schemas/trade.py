"""Trade event data model.

Maps to Binance ``/api/v3/trades`` and ``@trade`` WebSocket stream.
"""

from __future__ import annotations

from pydantic import ConfigDict

from binance_book.schemas.base import BaseTick


class Trade(BaseTick):
    """A single trade event.

    Fields
    ------
    TIMESTAMP : int
        Trade execution time in milliseconds since epoch (UTC).
    SYMBOL : str, optional
        Trading pair symbol (e.g. ``"BTCUSDT"``).
    PRICE : float
        Trade execution price.
    SIZE : float
        Trade quantity in base asset units.
    TRADE_ID : int
        Unique trade identifier assigned by Binance.
    IS_BUYER_MAKER : bool
        True if the buyer was the maker (i.e. the trade was a sell).
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    PRICE: float
    SIZE: float
    TRADE_ID: int
    IS_BUYER_MAKER: bool

    @staticmethod
    def from_binance(data: dict, symbol: str | None = None) -> "Trade":
        """Parse a Binance REST or WebSocket trade into a Trade model.

        Parameters
        ----------
        data : dict
            Raw Binance trade payload. Accepts both REST format (``id``,
            ``price``, ``qty``, ``time``) and WebSocket format (``t``, ``p``,
            ``q``, ``T``).
        symbol : str, optional
            Override symbol (useful when stream payload lacks it).
        """
        if "e" in data:
            return Trade(
                TIMESTAMP=data["T"],
                SYMBOL=symbol or data.get("s"),
                PRICE=float(data["p"]),
                SIZE=float(data["q"]),
                TRADE_ID=data["t"],
                IS_BUYER_MAKER=data["m"],
            )
        return Trade(
            TIMESTAMP=data["time"],
            SYMBOL=symbol,
            PRICE=float(data["price"]),
            SIZE=float(data["qty"]),
            TRADE_ID=data["id"],
            IS_BUYER_MAKER=data["isBuyerMaker"],
        )
