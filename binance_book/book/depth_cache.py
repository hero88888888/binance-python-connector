"""Local depth cache with full Binance sync protocol.

Implements the official Binance local orderbook management protocol for both
Spot and USDT-M Futures, handling:
- Buffered WS events + REST snapshot synchronization
- Update ID gap detection with automatic re-snapshot
- Zero-quantity level pruning
- Bounded level count (prevents unbounded growth bug)
- O(log n) operations via sortedcontainers.SortedDict
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable, Optional

from sortedcontainers import SortedDict

from binance_book.api import endpoints as ep
from binance_book.api.rest import BinanceRestClient
from binance_book.api.websocket import BinanceWebSocket
from binance_book.exceptions import DepthCacheDesyncError, DepthCacheSyncError

logger = logging.getLogger(__name__)


class DepthCache:
    """Maintains a synchronized local copy of a Binance orderbook.

    Follows the official Binance protocol:

    **Spot** (api.binance.com):
    1. Open ``@depth`` WS stream, buffer events
    2. GET ``/api/v3/depth?limit=1000`` for snapshot
    3. Discard events where ``u <= lastUpdateId``
    4. First valid event must have ``lastUpdateId`` in ``[U, u]``
    5. Each subsequent event: ``U == prev_u + 1``
    6. Gap detected → auto re-snapshot

    **USDT-M Futures** (fapi.binance.com):
    1. Open ``@depth`` WS stream, buffer events
    2. GET ``/fapi/v1/depth?limit=1000``
    3. Discard events where ``u < lastUpdateId``
    4. First event: ``U <= lastUpdateId AND u >= lastUpdateId``
    5. Each subsequent event: ``pu == previous u``
    6. Gap detected → auto re-snapshot

    Parameters
    ----------
    symbol : str
        Trading pair symbol (e.g. ``"BTCUSDT"``).
    rest_client : BinanceRestClient
        REST client for fetching depth snapshots.
    market : str
        ``"spot"``, ``"futures_usdt"``, or ``"futures_coin"``.
    max_levels : int
        Maximum number of price levels to maintain per side.
    ws_speed : int
        WebSocket update speed in ms (100 or 1000).
    on_update : callable, optional
        Async callback invoked after each successful book update.
    max_resnapshot_attempts : int
        Maximum consecutive re-snapshot attempts before raising.
    """

    def __init__(
        self,
        symbol: str,
        rest_client: BinanceRestClient,
        market: str = "spot",
        max_levels: int = 1000,
        ws_speed: int = 100,
        on_update: Optional[Callable[["DepthCache"], Any]] = None,
        max_resnapshot_attempts: int = 5,
    ) -> None:
        self.symbol = symbol.upper()
        self._rest = rest_client
        self._market = market
        self._max_levels = max_levels
        self._ws_speed = ws_speed
        self._on_update = on_update
        self._max_resnapshot = max_resnapshot_attempts

        self._bids: SortedDict = SortedDict()
        self._asks: SortedDict = SortedDict()
        self._last_update_id: int = 0
        self._prev_final_update_id: int = 0
        self._synced: bool = False
        self._sync_event = asyncio.Event()

        self._buffer: deque[dict] = deque(maxlen=5000)
        self._ws: Optional[BinanceWebSocket] = None
        self._task: Optional[asyncio.Task] = None
        self._resnapshot_count: int = 0

        self._update_count: int = 0
        self._last_event_time: float = 0.0
        self._snapshot_time: float = 0.0

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    @property
    def is_synced(self) -> bool:
        """Whether the depth cache is synchronized with the exchange."""
        return self._synced

    @property
    def last_update_id(self) -> int:
        """The last processed update ID."""
        return self._last_update_id

    @property
    def update_count(self) -> int:
        """Total number of updates processed since last snapshot."""
        return self._update_count

    def get_bids(self, limit: Optional[int] = None) -> list[tuple[float, float]]:
        """Return bid levels as (price, quantity) pairs, best first.

        Parameters
        ----------
        limit : int, optional
            Max number of levels. None returns all.
        """
        items = list(reversed(self._bids.items()))
        if limit:
            items = items[:limit]
        return [(float(p), float(q)) for p, q in items]

    def get_asks(self, limit: Optional[int] = None) -> list[tuple[float, float]]:
        """Return ask levels as (price, quantity) pairs, best first.

        Parameters
        ----------
        limit : int, optional
            Max number of levels. None returns all.
        """
        items = list(self._asks.items())
        if limit:
            items = items[:limit]
        return [(float(p), float(q)) for p, q in items]

    def get_best_bid(self) -> tuple[float, float] | None:
        """Return the best bid (price, quantity) or None if empty."""
        if not self._bids:
            return None
        key = self._bids.keys()[-1]
        return (float(key), float(self._bids[key]))

    def get_best_ask(self) -> tuple[float, float] | None:
        """Return the best ask (price, quantity) or None if empty."""
        if not self._asks:
            return None
        key = self._asks.keys()[0]
        return (float(key), float(self._asks[key]))

    def get_mid_price(self) -> float | None:
        """Return the mid price or None if book is empty."""
        bb = self.get_best_bid()
        ba = self.get_best_ask()
        if bb is None or ba is None:
            return None
        return (bb[0] + ba[0]) / 2.0

    def get_spread(self) -> float | None:
        """Return the spread (ask - bid) or None."""
        bb = self.get_best_bid()
        ba = self.get_best_ask()
        if bb is None or ba is None:
            return None
        return ba[0] - bb[0]

    @property
    def bid_count(self) -> int:
        """Number of bid price levels in the cache."""
        return len(self._bids)

    @property
    def ask_count(self) -> int:
        """Number of ask price levels in the cache."""
        return len(self._asks)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, ws_base_url: str) -> None:
        """Start the depth cache: connect WS, fetch snapshot, begin syncing.

        Parameters
        ----------
        ws_base_url : str
            WebSocket base URL (e.g. ``wss://stream.binance.com:9443``).
        """
        stream = ep.ws_depth_stream(self.symbol, speed=self._ws_speed)
        url = ep.ws_single_url(ws_base_url, stream)
        self._ws = BinanceWebSocket(url, on_message=self._on_ws_message)
        await self._ws.connect()
        self._task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        """Stop the depth cache and close the WebSocket."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.disconnect()
        self._synced = False

    async def wait_synced(self, timeout: float = 30.0) -> None:
        """Wait until the depth cache is synchronized.

        Parameters
        ----------
        timeout : float
            Maximum seconds to wait.

        Raises
        ------
        asyncio.TimeoutError
            If sync is not achieved within the timeout.
        """
        await asyncio.wait_for(self._sync_event.wait(), timeout=timeout)

    # ------------------------------------------------------------------
    # Internal sync machinery
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        """Main sync loop: snapshot → apply buffered → apply live."""
        while True:
            try:
                await self._initialize()
                break
            except DepthCacheSyncError:
                self._resnapshot_count += 1
                if self._resnapshot_count > self._max_resnapshot:
                    raise DepthCacheDesyncError(
                        f"{self.symbol}: Failed to sync after {self._max_resnapshot} attempts"
                    )
                wait = min(2 ** self._resnapshot_count, 30)
                logger.warning(
                    "%s: Re-snapshot attempt %d/%d in %.0fs",
                    self.symbol, self._resnapshot_count, self._max_resnapshot, wait,
                )
                await asyncio.sleep(wait)
            except asyncio.CancelledError:
                return

    async def _initialize(self) -> None:
        """Fetch snapshot and sync with buffered WS events."""
        await asyncio.sleep(0.5)

        snapshot = await self._fetch_snapshot()
        snap_update_id = snapshot["lastUpdateId"]
        logger.info(
            "%s: Got snapshot with lastUpdateId=%d, %d bids, %d asks",
            self.symbol, snap_update_id, len(snapshot["bids"]), len(snapshot["asks"]),
        )

        self._bids.clear()
        self._asks.clear()
        for price_str, qty_str in snapshot["bids"]:
            p = float(price_str)
            q = float(qty_str)
            if q > 0:
                self._bids[p] = q
        for price_str, qty_str in snapshot["asks"]:
            p = float(price_str)
            q = float(qty_str)
            if q > 0:
                self._asks[p] = q

        self._last_update_id = snap_update_id
        self._prev_final_update_id = snap_update_id
        self._snapshot_time = time.monotonic()
        self._update_count = 0

        buffered = list(self._buffer)
        self._buffer.clear()

        first_applied = False
        for event in buffered:
            if self._should_discard(event, snap_update_id, first_event=not first_applied):
                continue
            if not first_applied:
                if not self._is_valid_first_event(event, snap_update_id):
                    raise DepthCacheSyncError(
                        f"{self.symbol}: First buffered event doesn't bridge snapshot. "
                        f"U={event.get('U')}, u={event.get('u')}, lastUpdateId={snap_update_id}"
                    )
                first_applied = True
            self._apply_event(event)

        self._synced = True
        self._sync_event.set()
        self._resnapshot_count = 0
        logger.info("%s: Depth cache synced (applied %d buffered events)", self.symbol, self._update_count)

    def _on_ws_message(self, data: dict) -> None:
        """Handle incoming WS message: buffer if not synced, apply if synced."""
        if data.get("e") != "depthUpdate":
            return

        if not self._synced:
            self._buffer.append(data)
            return

        try:
            self._process_live_event(data)
        except DepthCacheSyncError:
            logger.warning("%s: Sync lost, will re-snapshot", self.symbol)
            self._synced = False
            self._sync_event.clear()
            self._buffer.clear()
            self._buffer.append(data)
            asyncio.get_event_loop().create_task(self._sync_loop())

    def _process_live_event(self, event: dict) -> None:
        """Process a live depth update event."""
        u = event.get("u", 0)
        U = event.get("U", 0)

        if u <= self._last_update_id:
            return

        if self._market == "spot":
            if U > self._prev_final_update_id + 1:
                raise DepthCacheSyncError(
                    f"{self.symbol}: Gap detected. U={U}, expected <= {self._prev_final_update_id + 1}"
                )
        else:
            pu = event.get("pu", 0)
            if pu != self._prev_final_update_id:
                raise DepthCacheSyncError(
                    f"{self.symbol}: Gap detected. pu={pu}, expected {self._prev_final_update_id}"
                )

        self._apply_event(event)

    def _should_discard(self, event: dict, snap_update_id: int, first_event: bool) -> bool:
        """Check if a buffered event should be discarded."""
        u = event.get("u", 0)
        if self._market == "spot":
            return u <= snap_update_id
        else:
            return u < snap_update_id

    def _is_valid_first_event(self, event: dict, snap_update_id: int) -> bool:
        """Check if this is a valid first event after snapshot."""
        U = event.get("U", 0)
        u = event.get("u", 0)
        if self._market == "spot":
            return U <= snap_update_id + 1 <= u
        else:
            return U <= snap_update_id and u >= snap_update_id

    def _apply_event(self, event: dict) -> None:
        """Apply a depth update event to the local book."""
        for price_str, qty_str in event.get("b", []):
            p = float(price_str)
            q = float(qty_str)
            if q == 0:
                self._bids.pop(p, None)
            else:
                self._bids[p] = q

        for price_str, qty_str in event.get("a", []):
            p = float(price_str)
            q = float(qty_str)
            if q == 0:
                self._asks.pop(p, None)
            else:
                self._asks[p] = q

        self._prev_final_update_id = event.get("u", 0)
        self._last_update_id = event.get("u", 0)
        self._last_event_time = time.monotonic()
        self._update_count += 1

        self._trim_book()

        if self._on_update:
            try:
                result = self._on_update(self)
                if asyncio.iscoroutine(result):
                    asyncio.get_event_loop().create_task(result)
            except Exception:
                logger.exception("Error in on_update callback")

    def _trim_book(self) -> None:
        """Enforce max_levels cap on both sides to prevent unbounded growth."""
        while len(self._bids) > self._max_levels:
            self._bids.popitem(0)
        while len(self._asks) > self._max_levels:
            self._asks.popitem(-1)

    async def _fetch_snapshot(self) -> dict:
        """Fetch a depth snapshot from the REST API."""
        if self._market == "spot":
            endpoint = ep.SPOT_DEPTH
        elif self._market == "futures_usdt":
            endpoint = ep.FUTURES_USDT_DEPTH
        else:
            endpoint = ep.FUTURES_COIN_DEPTH

        return await self._rest.get(
            endpoint,
            params={"symbol": self.symbol, "limit": min(self._max_levels, 1000)},
        )
