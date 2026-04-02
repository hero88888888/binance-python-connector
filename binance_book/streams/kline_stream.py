"""Kline/candlestick stream helper — @kline_<interval>."""

from __future__ import annotations

from typing import AsyncIterator

from binance_book.api import endpoints as ep
from binance_book.api.websocket import BinanceWebSocket
from binance_book.schemas.ohlcv import OHLCVBar


async def iter_klines(
    ws_base_url: str,
    symbol: str,
    interval: str = "1m",
) -> AsyncIterator[OHLCVBar]:
    """Iterate over live kline/candlestick updates from Binance.

    Parameters
    ----------
    ws_base_url : str
        WebSocket base URL.
    symbol : str
        Trading pair symbol.
    interval : str
        Kline interval (e.g. ``"1m"``, ``"5m"``, ``"1h"``, ``"1d"``).

    Yields
    ------
    OHLCVBar
        Parsed OHLCV bar on each update.
    """
    stream = ep.ws_kline_stream(symbol, interval=interval)
    url = ep.ws_single_url(ws_base_url, stream)
    ws = BinanceWebSocket(url)
    await ws.connect()
    try:
        async for msg in ws:
            if msg.get("e") == "kline":
                yield OHLCVBar.from_binance_ws(msg, symbol=symbol)
    finally:
        await ws.disconnect()
