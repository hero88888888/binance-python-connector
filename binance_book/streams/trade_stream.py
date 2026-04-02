"""Trade stream helpers — @trade and @aggTrade."""

from __future__ import annotations

from typing import Any, AsyncIterator

from binance_book.api import endpoints as ep
from binance_book.api.websocket import BinanceWebSocket
from binance_book.schemas.trade import Trade


async def iter_trades(
    ws_base_url: str,
    symbol: str,
    aggregate: bool = False,
) -> AsyncIterator[Trade]:
    """Iterate over live trade events from the Binance WebSocket stream.

    Parameters
    ----------
    ws_base_url : str
        WebSocket base URL.
    symbol : str
        Trading pair symbol.
    aggregate : bool
        If True, use ``@aggTrade`` stream instead of ``@trade``.

    Yields
    ------
    Trade
        Parsed trade events.
    """
    if aggregate:
        stream = ep.ws_agg_trade_stream(symbol)
    else:
        stream = ep.ws_trade_stream(symbol)
    url = ep.ws_single_url(ws_base_url, stream)
    ws = BinanceWebSocket(url)
    await ws.connect()
    try:
        async for msg in ws:
            if msg.get("e") in ("trade", "aggTrade"):
                yield Trade.from_binance(msg, symbol=symbol)
    finally:
        await ws.disconnect()
