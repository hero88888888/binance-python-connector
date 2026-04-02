"""Symbol discovery across all Binance market types.

Provides unified access to symbol metadata for Spot, USDT-M Futures,
COIN-M Futures, with filtering by quote asset, status, and volume.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from binance_book.api import endpoints as ep
from binance_book.api.rest import BinanceRestClient
from binance_book.schemas.static import SymbolInfo

logger = logging.getLogger(__name__)

MarketType = Literal["spot", "futures_usdt", "futures_coin"]

_EXCHANGE_INFO_ENDPOINTS: dict[str, ep.Endpoint] = {
    "spot": ep.SPOT_EXCHANGE_INFO,
    "futures_usdt": ep.FUTURES_USDT_EXCHANGE_INFO,
    "futures_coin": ep.FUTURES_COIN_EXCHANGE_INFO,
}


async def fetch_symbols(
    client: BinanceRestClient,
    market: MarketType = "spot",
    quote: Optional[str] = None,
    status: str = "TRADING",
    min_volume_24h: Optional[float] = None,
    ticker_client: Optional[BinanceRestClient] = None,
) -> list[SymbolInfo]:
    """Fetch and filter trading pair symbols from Binance.

    Retrieves exchange info for the specified market and returns a list of
    ``SymbolInfo`` models, optionally filtered by quote asset, trading status,
    and 24-hour volume.

    Parameters
    ----------
    client : BinanceRestClient
        REST client configured for the target market's base URL.
    market : str
        Market type: ``"spot"``, ``"futures_usdt"``, or ``"futures_coin"``.
    quote : str, optional
        Filter by quote asset (e.g. ``"USDT"``, ``"BTC"``).
    status : str
        Only include symbols with this status. Default ``"TRADING"``.
    min_volume_24h : float, optional
        Minimum 24-hour quote volume to include. Requires an additional API
        call to the 24hr ticker endpoint.
    ticker_client : BinanceRestClient, optional
        Separate client for ticker requests (in case market differs).

    Returns
    -------
    list[SymbolInfo]
        Filtered list of symbol metadata, sorted alphabetically by symbol.
    """
    endpoint = _EXCHANGE_INFO_ENDPOINTS[market]
    data = await client.get(endpoint)

    symbols: list[SymbolInfo] = []
    for sym_data in data.get("symbols", []):
        info = SymbolInfo.from_binance(sym_data)
        if status and info.STATUS != status:
            continue
        if quote and info.QUOTE_ASSET != quote.upper():
            continue
        symbols.append(info)

    if min_volume_24h is not None and min_volume_24h > 0:
        symbols = await _filter_by_volume(
            symbols,
            min_volume_24h,
            market,
            ticker_client or client,
        )

    symbols.sort(key=lambda s: s.SYMBOL)
    return symbols


async def _filter_by_volume(
    symbols: list[SymbolInfo],
    min_volume: float,
    market: MarketType,
    client: BinanceRestClient,
) -> list[SymbolInfo]:
    """Filter symbols by 24h quote volume using the ticker endpoint."""
    ticker_endpoints: dict[str, ep.Endpoint] = {
        "spot": ep.SPOT_TICKER_24HR,
        "futures_usdt": ep.FUTURES_USDT_TICKER_24HR,
        "futures_coin": ep.FUTURES_COIN_TICKER_24HR,
    }
    endpoint = ticker_endpoints[market]

    try:
        tickers = await client.get(endpoint)
    except Exception:
        logger.warning("Failed to fetch 24hr tickers for volume filtering, skipping filter")
        return symbols

    volume_map: dict[str, float] = {}
    for t in tickers:
        sym = t.get("symbol", "")
        vol = float(t.get("quoteVolume", 0))
        volume_map[sym] = vol

    return [s for s in symbols if volume_map.get(s.SYMBOL, 0) >= min_volume]


def get_symbol_names(symbols: list[SymbolInfo]) -> list[str]:
    """Extract just the symbol name strings from a list of SymbolInfo."""
    return [s.SYMBOL for s in symbols]
