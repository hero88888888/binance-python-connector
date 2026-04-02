"""Ticker stream helpers — @bookTicker, @ticker, @miniTicker."""

from __future__ import annotations

from typing import AsyncIterator

from binance_book.api import endpoints as ep
from binance_book.api.websocket import BinanceWebSocket
from binance_book.schemas.quote import Quote
from binance_book.schemas.ticker import Ticker24hr


async def iter_book_tickers(
    ws_base_url: str,
    symbol: str,
) -> AsyncIterator[Quote]:
    """Iterate over live best bid/offer updates from Binance.

    Parameters
    ----------
    ws_base_url : str
        WebSocket base URL.
    symbol : str
        Trading pair symbol.

    Yields
    ------
    Quote
        Parsed quote on each BBO update.
    """
    stream = ep.ws_book_ticker_stream(symbol)
    url = ep.ws_single_url(ws_base_url, stream)
    ws = BinanceWebSocket(url)
    await ws.connect()
    try:
        async for msg in ws:
            if "b" in msg and "a" in msg:
                yield Quote.from_binance(msg, symbol=symbol)
    finally:
        await ws.disconnect()


async def iter_tickers(
    ws_base_url: str,
    symbol: str,
) -> AsyncIterator[Ticker24hr]:
    """Iterate over live 24hr ticker updates from Binance.

    Parameters
    ----------
    ws_base_url : str
        WebSocket base URL.
    symbol : str
        Trading pair symbol.

    Yields
    ------
    Ticker24hr
        Parsed 24hr ticker on each update.
    """
    stream = ep.ws_ticker_stream(symbol)
    url = ep.ws_single_url(ws_base_url, stream)
    ws = BinanceWebSocket(url)
    await ws.connect()
    try:
        async for msg in ws:
            if msg.get("e") == "24hrTicker":
                yield Ticker24hr.from_binance(msg)
    finally:
        await ws.disconnect()
