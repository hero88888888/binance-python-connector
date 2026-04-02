"""Order book level data model.

Maps to Binance ``/api/v3/depth`` and ``@depth`` WebSocket stream.
Represents a single price level on one side of the book.
"""

from __future__ import annotations

from pydantic import ConfigDict

from binance_book.schemas.base import BaseTick, Side


class OrderBookLevel(BaseTick):
    """A single order book price level.

    Fields
    ------
    TIMESTAMP : int
        Snapshot or update time in milliseconds since epoch (UTC).
    SYMBOL : str, optional
        Trading pair symbol.
    SIDE : Side
        ``"BID"`` or ``"ASK"``.
    PRICE : float
        Price at this level.
    SIZE : float
        Total quantity resting at this price level.
    LEVEL : int
        Depth level number (1 = best, 2 = second best, ...).
    UPDATE_ID : int
        Binance ``lastUpdateId`` at the time of this snapshot/update.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    SIDE: Side
    PRICE: float
    SIZE: float
    LEVEL: int
    UPDATE_ID: int = 0

    @property
    def NOTIONAL(self) -> float:
        """Notional value (PRICE * SIZE) in quote asset units."""
        return self.PRICE * self.SIZE

    @staticmethod
    def from_depth_snapshot(
        bids: list[list[str]],
        asks: list[list[str]],
        last_update_id: int,
        symbol: str | None = None,
        timestamp: int | None = None,
    ) -> list["OrderBookLevel"]:
        """Parse a Binance depth snapshot into a list of OrderBookLevel models.

        Parameters
        ----------
        bids : list[list[str]]
            List of ``[price, quantity]`` pairs for the bid side.
        asks : list[list[str]]
            List of ``[price, quantity]`` pairs for the ask side.
        last_update_id : int
            The ``lastUpdateId`` from the Binance depth response.
        symbol : str, optional
            Trading pair symbol.
        timestamp : int, optional
            Snapshot time. Defaults to now.

        Returns
        -------
        list[OrderBookLevel]
            Combined bid and ask levels ordered by side then level number.
        """
        from binance_book.schemas.base import Timestamp

        ts = timestamp or Timestamp.now_ms()
        levels: list[OrderBookLevel] = []
        for i, (price, qty) in enumerate(bids):
            levels.append(
                OrderBookLevel(
                    TIMESTAMP=ts,
                    SYMBOL=symbol,
                    SIDE=Side.BID,
                    PRICE=float(price),
                    SIZE=float(qty),
                    LEVEL=i + 1,
                    UPDATE_ID=last_update_id,
                )
            )
        for i, (price, qty) in enumerate(asks):
            levels.append(
                OrderBookLevel(
                    TIMESTAMP=ts,
                    SYMBOL=symbol,
                    SIDE=Side.ASK,
                    PRICE=float(price),
                    SIZE=float(qty),
                    LEVEL=i + 1,
                    UPDATE_ID=last_update_id,
                )
            )
        return levels
