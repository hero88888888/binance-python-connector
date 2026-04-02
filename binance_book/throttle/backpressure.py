"""Backpressure and overflow protection for high-frequency streams.

At 100 symbols streaming @depth@100ms, inbound data reaches 4.4 GB/hour.
This module provides configurable strategies for when processing can't
keep up with the incoming message rate.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Literal

logger = logging.getLogger(__name__)

OverflowStrategy = Literal["drop_oldest", "drop_newest", "block"]


class BackpressureQueue:
    """A bounded queue with configurable overflow strategy.

    Parameters
    ----------
    maxsize : int
        Maximum items in the queue.
    strategy : str
        What to do when the queue is full:
        - ``"drop_oldest"``: remove the oldest item and add the new one
        - ``"drop_newest"``: discard the new item
        - ``"block"``: wait until space is available
    """

    def __init__(
        self,
        maxsize: int = 10000,
        strategy: OverflowStrategy = "drop_oldest",
    ) -> None:
        self._maxsize = maxsize
        self._strategy = strategy
        self._queue: deque[Any] = deque(maxlen=maxsize if strategy == "drop_oldest" else None)
        self._async_queue: asyncio.Queue[Any] | None = None
        self._dropped: int = 0

    @property
    def dropped_count(self) -> int:
        """Number of messages dropped due to backpressure."""
        return self._dropped

    @property
    def size(self) -> int:
        """Current queue size."""
        return len(self._queue)

    @property
    def is_full(self) -> bool:
        """Whether the queue is at capacity."""
        return len(self._queue) >= self._maxsize

    def put_nowait(self, item: Any) -> bool:
        """Add an item to the queue without blocking.

        Returns
        -------
        bool
            True if the item was accepted, False if dropped.
        """
        if self._strategy == "drop_oldest":
            if len(self._queue) >= self._maxsize:
                self._queue.popleft()
                self._dropped += 1
            self._queue.append(item)
            return True

        elif self._strategy == "drop_newest":
            if len(self._queue) >= self._maxsize:
                self._dropped += 1
                return False
            self._queue.append(item)
            return True

        else:
            if len(self._queue) >= self._maxsize:
                return False
            self._queue.append(item)
            return True

    def get_nowait(self) -> Any | None:
        """Get an item from the queue without blocking. Returns None if empty."""
        if self._queue:
            return self._queue.popleft()
        return None

    def get_batch(self, max_items: int = 100) -> list[Any]:
        """Get up to max_items from the queue at once."""
        items: list[Any] = []
        for _ in range(min(max_items, len(self._queue))):
            items.append(self._queue.popleft())
        return items

    def clear(self) -> None:
        """Clear all items from the queue."""
        self._queue.clear()

    def to_dict(self) -> dict:
        """Export queue status."""
        return {
            "size": self.size,
            "maxsize": self._maxsize,
            "strategy": self._strategy,
            "dropped": self._dropped,
            "is_full": self.is_full,
            "utilization_pct": round(self.size / self._maxsize * 100, 1) if self._maxsize else 0,
        }
