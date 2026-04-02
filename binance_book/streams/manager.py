"""WebSocket stream lifecycle manager.

Handles auto-reconnect, 24-hour rotation, ping/pong, connection pooling,
and combined stream multiplexing across multiple symbols.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, Optional

from binance_book.api import endpoints as ep
from binance_book.api.websocket import BinanceWebSocket

logger = logging.getLogger(__name__)

MAX_STREAMS_PER_CONNECTION = 1024


class StreamManager:
    """Manages one or more WebSocket connections to Binance streams.

    Handles combined-stream multiplexing (up to 1024 streams per connection),
    automatic connection splitting for larger subscription sets, and
    dispatching messages to per-stream callbacks.

    Parameters
    ----------
    ws_base_url : str
        WebSocket base URL (e.g. ``wss://stream.binance.com:9443``).
    on_message : callable, optional
        Global callback for all received messages.
    """

    def __init__(
        self,
        ws_base_url: str,
        on_message: Optional[Callable[[dict[str, Any]], Any]] = None,
    ) -> None:
        self._ws_base_url = ws_base_url
        self._on_message = on_message
        self._connections: list[BinanceWebSocket] = []
        self._stream_callbacks: dict[str, list[Callable]] = {}
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the manager is actively running."""
        return self._running

    @property
    def connection_count(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._connections)

    async def subscribe(
        self,
        streams: list[str],
        callback: Optional[Callable[[dict[str, Any]], Any]] = None,
    ) -> None:
        """Subscribe to one or more streams.

        Automatically creates combined-stream connections, splitting into
        multiple connections if the stream count exceeds 1024.

        Parameters
        ----------
        streams : list[str]
            Stream names (e.g. ``["btcusdt@depth@100ms", "ethusdt@trade"]``).
        callback : callable, optional
            Per-stream callback for received messages.
        """
        self._running = True

        if callback:
            for s in streams:
                self._stream_callbacks.setdefault(s, []).append(callback)

        chunks = [
            streams[i : i + MAX_STREAMS_PER_CONNECTION]
            for i in range(0, len(streams), MAX_STREAMS_PER_CONNECTION)
        ]

        for chunk in chunks:
            url = ep.ws_combined_url(self._ws_base_url, chunk)
            ws = BinanceWebSocket(url, on_message=self._dispatch)
            self._connections.append(ws)
            await ws.connect()
            logger.info("Connected combined stream with %d streams", len(chunk))

    async def subscribe_single(
        self,
        stream: str,
        callback: Optional[Callable[[dict[str, Any]], Any]] = None,
    ) -> BinanceWebSocket:
        """Subscribe to a single stream on a dedicated connection.

        Parameters
        ----------
        stream : str
            Stream name.
        callback : callable, optional
            Callback for received messages.

        Returns
        -------
        BinanceWebSocket
            The WebSocket connection (for direct iteration).
        """
        self._running = True
        if callback:
            self._stream_callbacks.setdefault(stream, []).append(callback)

        url = ep.ws_single_url(self._ws_base_url, stream)
        ws = BinanceWebSocket(url, on_message=self._dispatch)
        self._connections.append(ws)
        await ws.connect()
        return ws

    async def unsubscribe_all(self) -> None:
        """Disconnect all WebSocket connections."""
        self._running = False
        tasks = [ws.disconnect() for ws in self._connections]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._connections.clear()
        self._stream_callbacks.clear()

    def _dispatch(self, data: dict[str, Any]) -> None:
        """Dispatch a received message to registered callbacks."""
        if self._on_message:
            try:
                result = self._on_message(data)
                if asyncio.iscoroutine(result):
                    asyncio.get_event_loop().create_task(result)
            except Exception:
                logger.exception("Error in global on_message callback")

        stream_name = data.get("stream", "")
        payload = data.get("data", data)

        callbacks = self._stream_callbacks.get(stream_name, [])
        for cb in callbacks:
            try:
                result = cb(payload)
                if asyncio.iscoroutine(result):
                    asyncio.get_event_loop().create_task(result)
            except Exception:
                logger.exception("Error in stream callback for %s", stream_name)

    async def iter_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Async iterate over all messages from all connections.

        Merges messages from all active connections into a single stream.

        Yields
        ------
        dict
            Parsed JSON messages from Binance WebSocket streams.
        """
        if not self._connections:
            return

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def feed(ws: BinanceWebSocket) -> None:
            async for msg in ws:
                await queue.put(msg)

        tasks = [asyncio.create_task(feed(ws)) for ws in self._connections]

        try:
            while self._running:
                msg = await queue.get()
                yield msg
        finally:
            for t in tasks:
                t.cancel()
