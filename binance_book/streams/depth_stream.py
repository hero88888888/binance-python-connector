"""Depth stream helpers — @depth, @depth@100ms, @depth5/10/20."""

from __future__ import annotations

from typing import AsyncIterator, Any, Optional

from binance_book.api import endpoints as ep
from binance_book.api.websocket import BinanceWebSocket
from binance_book.schemas.base import Timestamp


async def iter_depth_updates(
    ws_base_url: str,
    symbol: str,
    speed: int = 100,
) -> AsyncIterator[dict[str, Any]]:
    """Iterate over diff-depth updates from the Binance WebSocket stream.

    Yields raw depth update events with fields: ``e``, ``E``, ``s``, ``U``,
    ``u``, ``b`` (bids), ``a`` (asks).

    Parameters
    ----------
    ws_base_url : str
        WebSocket base URL.
    symbol : str
        Trading pair symbol.
    speed : int
        Update speed: 100 (ms) or 1000 (ms).

    Yields
    ------
    dict
        Raw depth update events.
    """
    stream = ep.ws_depth_stream(symbol, speed=speed)
    url = ep.ws_single_url(ws_base_url, stream)
    ws = BinanceWebSocket(url)
    await ws.connect()
    try:
        async for msg in ws:
            if msg.get("e") == "depthUpdate":
                yield msg
    finally:
        await ws.disconnect()


async def iter_partial_depth(
    ws_base_url: str,
    symbol: str,
    levels: int = 5,
    speed: int = 100,
) -> AsyncIterator[dict[str, Any]]:
    """Iterate over partial book depth snapshots from Binance.

    Unlike diff-depth, partial depth streams push the top N levels as a
    full snapshot on every update — no sync protocol needed.

    Parameters
    ----------
    ws_base_url : str
        WebSocket base URL.
    symbol : str
        Trading pair symbol.
    levels : int
        Number of levels: 5, 10, or 20.
    speed : int
        Update speed: 100 (ms) or 1000 (ms).

    Yields
    ------
    dict
        Partial depth snapshots with ``lastUpdateId``, ``bids``, ``asks``.
    """
    stream = ep.ws_partial_depth_stream(symbol, levels=levels, speed=speed)
    url = ep.ws_single_url(ws_base_url, stream)
    ws = BinanceWebSocket(url)
    await ws.connect()
    try:
        async for msg in ws:
            if "lastUpdateId" in msg:
                yield msg
    finally:
        await ws.disconnect()
