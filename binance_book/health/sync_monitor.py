"""Depth cache sync monitoring — detects update ID gaps and triggers re-snapshots.

The #1 community-reported issue with Binance orderbook management is silent
sync failures. This monitor tracks update ID continuity and provides health
status for each managed depth cache.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SyncStatus:
    """Health status for a single depth cache."""

    symbol: str
    synced: bool = False
    last_update_id: int = 0
    gap_count: int = 0
    resnapshot_count: int = 0
    last_gap_time: float = 0.0
    last_sync_time: float = 0.0
    updates_since_sync: int = 0

    @property
    def seconds_since_sync(self) -> float:
        """Seconds since last successful sync."""
        if self.last_sync_time == 0:
            return float("inf")
        return time.monotonic() - self.last_sync_time

    @property
    def seconds_since_gap(self) -> float:
        """Seconds since last detected gap."""
        if self.last_gap_time == 0:
            return float("inf")
        return time.monotonic() - self.last_gap_time


class SyncMonitor:
    """Monitors depth cache synchronization health across multiple symbols.

    Tracks update ID continuity, gap frequency, and re-snapshot counts.
    Provides aggregated health views for operational monitoring.

    Parameters
    ----------
    max_gap_history : int
        Maximum number of gap events to remember per symbol.
    """

    def __init__(self, max_gap_history: int = 100) -> None:
        self._statuses: dict[str, SyncStatus] = {}
        self._max_gap_history = max_gap_history

    def register(self, symbol: str) -> None:
        """Register a symbol for sync monitoring."""
        self._statuses[symbol] = SyncStatus(symbol=symbol)

    def unregister(self, symbol: str) -> None:
        """Remove a symbol from monitoring."""
        self._statuses.pop(symbol, None)

    def on_sync(self, symbol: str, last_update_id: int) -> None:
        """Record a successful sync/resnapshot."""
        status = self._statuses.get(symbol)
        if status is None:
            return
        status.synced = True
        status.last_update_id = last_update_id
        status.last_sync_time = time.monotonic()
        status.updates_since_sync = 0

    def on_update(self, symbol: str, update_id: int) -> None:
        """Record a successful update application."""
        status = self._statuses.get(symbol)
        if status is None:
            return
        status.last_update_id = update_id
        status.updates_since_sync += 1

    def on_gap(self, symbol: str, expected_id: int, received_id: int) -> None:
        """Record a detected update ID gap."""
        status = self._statuses.get(symbol)
        if status is None:
            return
        status.gap_count += 1
        status.last_gap_time = time.monotonic()
        status.synced = False
        logger.warning(
            "%s: Gap detected (expected %d, got %d). Total gaps: %d",
            symbol, expected_id, received_id, status.gap_count,
        )

    def on_resnapshot(self, symbol: str) -> None:
        """Record a re-snapshot attempt."""
        status = self._statuses.get(symbol)
        if status is None:
            return
        status.resnapshot_count += 1

    def get_status(self, symbol: str) -> Optional[SyncStatus]:
        """Get sync status for a symbol."""
        return self._statuses.get(symbol)

    def get_all_statuses(self) -> dict[str, SyncStatus]:
        """Get sync status for all monitored symbols."""
        return dict(self._statuses)

    def get_health_summary(self) -> dict:
        """Get an aggregate health summary.

        Returns
        -------
        dict
            Summary with total_symbols, synced_count, total_gaps, etc.
        """
        statuses = list(self._statuses.values())
        return {
            "total_symbols": len(statuses),
            "synced": sum(1 for s in statuses if s.synced),
            "desynced": sum(1 for s in statuses if not s.synced),
            "total_gaps": sum(s.gap_count for s in statuses),
            "total_resnapshots": sum(s.resnapshot_count for s in statuses),
            "symbols_with_gaps": [s.symbol for s in statuses if s.gap_count > 0],
        }
