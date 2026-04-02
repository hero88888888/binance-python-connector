"""STAT schema — symbol reference / static data model.

Maps to Binance ``/api/v3/exchangeInfo``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class SymbolInfo(BaseModel):
    """Static reference data for a trading pair.

    Fields
    ------
    SYMBOL : str
        Trading pair symbol (e.g. ``"BTCUSDT"``).
    BASE_ASSET : str
        Base asset (e.g. ``"BTC"``).
    QUOTE_ASSET : str
        Quote asset (e.g. ``"USDT"``).
    STATUS : str
        Trading status (e.g. ``"TRADING"``).
    TICK_SIZE : float
        Minimum price movement (from PRICE_FILTER).
    LOT_SIZE : float
        Minimum quantity step (from LOT_SIZE filter).
    MIN_NOTIONAL : float
        Minimum order notional value (from NOTIONAL or MIN_NOTIONAL filter).
    MIN_QTY : float
        Minimum order quantity.
    MAX_QTY : float
        Maximum order quantity.
    BASE_PRECISION : int
        Number of decimal places for base asset.
    QUOTE_PRECISION : int
        Number of decimal places for quote asset.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    SYMBOL: str
    BASE_ASSET: str
    QUOTE_ASSET: str
    STATUS: str
    TICK_SIZE: float = 0.0
    LOT_SIZE: float = 0.0
    MIN_NOTIONAL: float = 0.0
    MIN_QTY: float = 0.0
    MAX_QTY: float = 0.0
    BASE_PRECISION: int = 8
    QUOTE_PRECISION: int = 8

    @staticmethod
    def from_binance(data: dict) -> "SymbolInfo":
        """Parse a Binance exchangeInfo symbol entry into a SymbolInfo model.

        Parameters
        ----------
        data : dict
            A single symbol object from Binance ``exchangeInfo`` response.
        """
        tick_size = 0.0
        lot_size = 0.0
        min_notional = 0.0
        min_qty = 0.0
        max_qty = 0.0

        for f in data.get("filters", []):
            ft = f.get("filterType", "")
            if ft == "PRICE_FILTER":
                tick_size = float(f.get("tickSize", 0))
            elif ft == "LOT_SIZE":
                lot_size = float(f.get("stepSize", 0))
                min_qty = float(f.get("minQty", 0))
                max_qty = float(f.get("maxQty", 0))
            elif ft in ("NOTIONAL", "MIN_NOTIONAL"):
                min_notional = float(f.get("minNotional", 0))

        return SymbolInfo(
            SYMBOL=data["symbol"],
            BASE_ASSET=data.get("baseAsset", ""),
            QUOTE_ASSET=data.get("quoteAsset", ""),
            STATUS=data.get("status", "UNKNOWN"),
            TICK_SIZE=tick_size,
            LOT_SIZE=lot_size,
            MIN_NOTIONAL=min_notional,
            MIN_QTY=min_qty,
            MAX_QTY=max_qty,
            BASE_PRECISION=data.get("baseAssetPrecision", 8),
            QUOTE_PRECISION=data.get("quoteAssetPrecision", 8),
        )
