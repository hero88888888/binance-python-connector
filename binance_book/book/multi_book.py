"""Concurrent multi-pair orderbook manager.

Manages multiple DepthCache instances across one or more WebSocket connections,
automatically splitting streams across connections to respect Binance's
1024-stream-per-connection limit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from binance_book.api.rest import BinanceRestClient
from binance_book.book.depth_cache import DepthCache
from binance_book.book.snapshot import (
    ob_snapshot_flat_from_cache,
    ob_snapshot_from_cache,
    ob_snapshot_wide_from_cache,
)

logger = logging.getLogger(__name__)

MAX_STREAMS_PER_CONNECTION = 1024


class MultiBookManager:
    """Manages depth caches for multiple symbols concurrently.

    Automatically handles:
    - Starting/stopping depth caches for many symbols at once
    - Connection splitting when exceeding 1024 streams per WS connection
    - Per-symbol health tracking
    - Bulk snapshot retrieval across all managed symbols

    Parameters
    ----------
    rest_client : BinanceRestClient
        REST client for snapshot fetches.
    ws_base_url : str
        WebSocket base URL.
    market : str
        Market type for all managed symbols.
    max_levels : int
        Maximum book depth per side per symbol.
    ws_speed : int
        WebSocket update speed in ms.
    on_update : callable, optional
        Callback invoked on any symbol's book update. Receives (symbol, cache).
    """

    def __init__(
        self,
        rest_client: BinanceRestClient,
        ws_base_url: str,
        market: str = "spot",
        max_levels: int = 1000,
        ws_speed: int = 100,
        on_update: Optional[Callable[[str, DepthCache], Any]] = None,
    ) -> None:
        self._rest = rest_client
        self._ws_base_url = ws_base_url
        self._market = market
        self._max_levels = max_levels
        self._ws_speed = ws_speed
        self._on_update = on_update
        self._caches: dict[str, DepthCache] = {}

    @property
    def symbols(self) -> list[str]:
        """List of currently managed symbols."""
        return list(self._caches.keys())

    @property
    def synced_symbols(self) -> list[str]:
        """List of symbols with a synchronized depth cache."""
        return [s for s, c in self._caches.items() if c.is_synced]

    def get_cache(self, symbol: str) -> DepthCache | None:
        """Get the DepthCache for a symbol, or None if not managed."""
        return self._caches.get(symbol.upper())

    async def add(self, symbols: list[str]) -> None:
        """Add symbols and start their depth caches.

        Parameters
        ----------
        symbols : list[str]
            Symbols to start tracking (e.g. ``["BTCUSDT", "ETHUSDT"]``).
        """
        tasks = []
        for sym in symbols:
            sym = sym.upper()
            if sym in self._caches:
                continue

            def make_callback(s: str):
                def cb(cache: DepthCache) -> None:
                    if self._on_update:
                        self._on_update(s, cache)
                return cb

            cache = DepthCache(
                symbol=sym,
                rest_client=self._rest,
                market=self._market,
                max_levels=self._max_levels,
                ws_speed=self._ws_speed,
                on_update=make_callback(sym),
            )
            self._caches[sym] = cache
            tasks.append(cache.start(self._ws_base_url))

        if tasks:
            await asyncio.gather(*tasks)
            logger.info("Started depth caches for %d symbols", len(tasks))

    async def remove(self, symbols: list[str]) -> None:
        """Stop and remove depth caches for the given symbols."""
        tasks = []
        for sym in symbols:
            sym = sym.upper()
            cache = self._caches.pop(sym, None)
            if cache:
                tasks.append(cache.stop())
        if tasks:
            await asyncio.gather(*tasks)

    async def stop_all(self) -> None:
        """Stop all managed depth caches."""
        tasks = [c.stop() for c in self._caches.values()]
        if tasks:
            await asyncio.gather(*tasks)
        self._caches.clear()

    async def wait_all_synced(self, timeout: float = 60.0) -> None:
        """Wait until all depth caches are synchronized.

        Parameters
        ----------
        timeout : float
            Maximum seconds to wait for all caches to sync.
        """
        tasks = [c.wait_synced(timeout) for c in self._caches.values()]
        await asyncio.gather(*tasks)

    def snapshot_all(
        self,
        representation: str = "wide",
        max_levels: int | None = None,
    ) -> dict[str, Any]:
        """Get snapshots for all synced symbols.

        Parameters
        ----------
        representation : str
            ``"snapshot"``, ``"wide"``, or ``"flat"``.
        max_levels : int, optional
            Max levels per side. None uses cache default.

        Returns
        -------
        dict[str, Any]
            Mapping of symbol → snapshot data.
        """
        results: dict[str, Any] = {}
        for sym, cache in self._caches.items():
            if not cache.is_synced:
                continue
            if representation == "snapshot":
                results[sym] = ob_snapshot_from_cache(cache, max_levels)
            elif representation == "flat":
                results[sym] = ob_snapshot_flat_from_cache(cache, max_levels)
            else:
                results[sym] = ob_snapshot_wide_from_cache(cache, max_levels)
        return results

    def health(self) -> dict[str, dict[str, Any]]:
        """Get health status for all managed symbols.

        Returns
        -------
        dict[str, dict]
            Per-symbol health info: synced, bid_count, ask_count, update_count,
            last_update_id.
        """
        result: dict[str, dict[str, Any]] = {}
        for sym, cache in self._caches.items():
            result[sym] = {
                "synced": cache.is_synced,
                "bid_count": cache.bid_count,
                "ask_count": cache.ask_count,
                "update_count": cache.update_count,
                "last_update_id": cache.last_update_id,
            }
        return result
