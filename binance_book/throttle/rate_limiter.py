"""REST API weight tracking and auto-throttling.

Binance rate limits: 1200 weight/min for spot, varying for futures.
Each endpoint has a weight cost that varies by parameters (e.g. depth
limit=5000 costs 50 weight vs limit=100 costs 5 weight).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Tracks API weight consumption and auto-throttles when approaching limits.

    Reads ``X-MBX-USED-WEIGHT-1M`` from response headers to stay accurate.
    When usage exceeds the safety threshold, requests are delayed until the
    window resets.

    Parameters
    ----------
    weight_limit : int
        Maximum weight allowed per minute. Default 1200 (Binance spot).
    safety_pct : float
        Start throttling when usage exceeds this percentage of the limit.
        Default 0.8 (80%).
    """

    def __init__(
        self,
        weight_limit: int = 1200,
        safety_pct: float = 0.8,
    ) -> None:
        self._limit = weight_limit
        self._safety = int(weight_limit * safety_pct)
        self._used: int = 0
        self._window_start: float = time.monotonic()

    @property
    def used_weight(self) -> int:
        """Current consumed weight in this window."""
        self._maybe_reset()
        return self._used

    @property
    def remaining_weight(self) -> int:
        """Remaining weight in this window."""
        self._maybe_reset()
        return max(0, self._limit - self._used)

    @property
    def is_throttled(self) -> bool:
        """Whether requests should be delayed."""
        self._maybe_reset()
        return self._used >= self._safety

    def update_from_header(self, used_weight: int) -> None:
        """Update weight from Binance response header value."""
        self._used = used_weight
        if self._window_start == 0:
            self._window_start = time.monotonic()

    def add_weight(self, weight: int) -> None:
        """Manually add weight (when headers aren't available)."""
        self._maybe_reset()
        self._used += weight

    async def wait_if_needed(self, request_weight: int = 1) -> None:
        """Wait if adding this request would exceed the safety threshold.

        Parameters
        ----------
        request_weight : int
            Weight of the upcoming request.
        """
        self._maybe_reset()
        if self._used + request_weight > self._safety:
            wait_time = self._seconds_until_reset()
            if wait_time > 0:
                logger.info(
                    "Rate limiter: %d/%d weight used, waiting %.1fs for reset",
                    self._used, self._limit, wait_time,
                )
                await asyncio.sleep(wait_time)
                self._reset()

    def _maybe_reset(self) -> None:
        """Reset the window if 60 seconds have passed."""
        if time.monotonic() - self._window_start >= 60.0:
            self._reset()

    def _reset(self) -> None:
        """Reset the weight window."""
        self._used = 0
        self._window_start = time.monotonic()

    def _seconds_until_reset(self) -> float:
        """Seconds until the current rate-limit window resets."""
        elapsed = time.monotonic() - self._window_start
        return max(0.0, 60.0 - elapsed)

    def to_dict(self) -> dict:
        """Export current state as a dict."""
        self._maybe_reset()
        return {
            "used_weight": self._used,
            "limit": self._limit,
            "remaining": self.remaining_weight,
            "is_throttled": self.is_throttled,
            "seconds_until_reset": round(self._seconds_until_reset(), 1),
        }
