"""Async WebSocket client for Binance streams.

Talks directly to Binance WebSocket endpoints — no third-party Binance libraries.
Handles auto-reconnect, ping/pong, and 24-hour connection rotation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Callable, Optional

import orjson
import websockets
import websockets.client

from binance_book.exceptions import WebSocketDisconnected, WebSocketError

logger = logging.getLogger(__name__)

MAX_CONNECTION_LIFETIME_S = 23 * 3600  # Rotate before Binance's 24hr hard limit
PING_INTERVAL_S = 15
RECONNECT_DELAYS = [0.5, 1, 2, 4, 8, 16, 30]


class BinanceWebSocket:
    """Low-level async WebSocket client for a single Binance stream connection.

    Handles auto-reconnect with exponential backoff, ping/pong keepalive,
    and proactive 24-hour rotation (Binance disconnects after 24h).

    Parameters
    ----------
    url : str
        Full WebSocket URL including stream path.
    on_message : callable, optional
        Async callback for each received message (parsed JSON).
    max_reconnect_attempts : int
        Maximum consecutive reconnect attempts before giving up.
    """

    def __init__(
        self,
        url: str,
        on_message: Optional[Callable[[dict[str, Any]], Any]] = None,
        max_reconnect_attempts: int = 10,
    ) -> None:
        self._url = url
        self._on_message = on_message
        self._max_reconnect = max_reconnect_attempts
        self._ws: Optional[websockets.client.WebSocketClientProtocol] = None
        self._running = False
        self._connected_at: float = 0.0
        self._task: Optional[asyncio.Task[None]] = None
        self._message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=10000)
        self._reconnect_count = 0

    @property
    def is_connected(self) -> bool:
        """Whether the WebSocket is currently connected."""
        return self._ws is not None and self._ws.open

    @property
    def connection_age_s(self) -> float:
        """Seconds since the current connection was established."""
        if self._connected_at == 0:
            return 0.0
        return time.monotonic() - self._connected_at

    async def connect(self) -> None:
        """Start the WebSocket connection and begin receiving messages."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def disconnect(self) -> None:
        """Gracefully close the WebSocket connection."""
        self._running = False
        if self._ws and self._ws.open:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._ws = None

    async def recv(self) -> dict[str, Any]:
        """Receive the next parsed message from the stream.

        Returns
        -------
        dict
            Parsed JSON message from the Binance WebSocket stream.

        Raises
        ------
        WebSocketDisconnected
            If the connection is closed and not reconnecting.
        """
        msg = await self._message_queue.get()
        if msg.get("_error"):
            raise WebSocketDisconnected(msg["_error"])
        return msg

    async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        """Async iterate over messages from the stream."""
        while self._running:
            try:
                msg = await self.recv()
                yield msg
            except WebSocketDisconnected:
                if self._running:
                    continue
                break

    async def _run_loop(self) -> None:
        """Main loop: connect, receive messages, handle reconnection."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                self._reconnect_count += 1
                if self._reconnect_count > self._max_reconnect:
                    logger.error("Max reconnect attempts reached for %s", self._url)
                    await self._message_queue.put({"_error": f"Max reconnect attempts: {exc}"})
                    break
                delay = RECONNECT_DELAYS[min(self._reconnect_count - 1, len(RECONNECT_DELAYS) - 1)]
                logger.warning(
                    "WebSocket error (attempt %d/%d), reconnecting in %.1fs: %s",
                    self._reconnect_count,
                    self._max_reconnect,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

    async def _connect_and_listen(self) -> None:
        """Establish connection and process messages until disconnect or rotation."""
        logger.info("Connecting to %s", self._url)
        async with websockets.client.connect(
            self._url,
            ping_interval=PING_INTERVAL_S,
            ping_timeout=30,
            close_timeout=5,
            max_size=10 * 1024 * 1024,  # 10MB max message
        ) as ws:
            self._ws = ws
            self._connected_at = time.monotonic()
            self._reconnect_count = 0
            logger.info("Connected to %s", self._url)

            async for raw_message in ws:
                if not self._running:
                    break

                if self.connection_age_s > MAX_CONNECTION_LIFETIME_S:
                    logger.info("Connection lifetime exceeded, rotating: %s", self._url)
                    break

                try:
                    if isinstance(raw_message, bytes):
                        data = orjson.loads(raw_message)
                    else:
                        data = orjson.loads(raw_message.encode())
                except Exception:
                    logger.warning("Failed to parse message: %s", raw_message[:200])
                    continue

                if self._on_message:
                    try:
                        result = self._on_message(data)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception("Error in on_message callback")

                try:
                    self._message_queue.put_nowait(data)
                except asyncio.QueueFull:
                    try:
                        self._message_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    self._message_queue.put_nowait(data)

        self._ws = None

    async def subscribe(self, streams: list[str]) -> None:
        """Send a subscribe request over the existing connection.

        Parameters
        ----------
        streams : list[str]
            Stream names to subscribe to (e.g. ``["btcusdt@depth@100ms"]``).
        """
        if not self.is_connected or self._ws is None:
            raise WebSocketError("Not connected")
        payload = orjson.dumps({"method": "SUBSCRIBE", "params": streams, "id": 1})
        await self._ws.send(payload)

    async def unsubscribe(self, streams: list[str]) -> None:
        """Send an unsubscribe request over the existing connection."""
        if not self.is_connected or self._ws is None:
            raise WebSocketError("Not connected")
        payload = orjson.dumps({"method": "UNSUBSCRIBE", "params": streams, "id": 2})
        await self._ws.send(payload)
