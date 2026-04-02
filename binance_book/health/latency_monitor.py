"""Per-message latency monitoring.

Tracks the difference between Binance event timestamps and local receive
time. During volatile events, latency can spike from ~10ms to seconds.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class LatencyStats:
    """Latency statistics for a symbol."""

    symbol: str
    sample_count: int = 0
    last_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    _sum: float = 0.0

    def record(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        self.sample_count += 1
        self.last_latency_ms = latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self._sum += latency_ms
        self.avg_latency_ms = self._sum / self.sample_count

    def to_dict(self) -> dict:
        """Export as a dict."""
        return {
            "symbol": self.symbol,
            "sample_count": self.sample_count,
            "last_ms": round(self.last_latency_ms, 2),
            "min_ms": round(self.min_latency_ms, 2) if self.min_latency_ms != float("inf") else 0,
            "max_ms": round(self.max_latency_ms, 2),
            "avg_ms": round(self.avg_latency_ms, 2),
        }


class LatencyMonitor:
    """Monitors event-to-receive latency across multiple symbols.

    Computes latency as ``receive_time - event_time`` from Binance's ``E``
    (event time) field in WebSocket messages.

    Parameters
    ----------
    spike_threshold_ms : float
        Latency above this triggers a spike alert. Default 1000 (1 second).
    window_size : int
        Number of recent samples to keep per symbol for windowed stats.
    """

    def __init__(
        self,
        spike_threshold_ms: float = 1000.0,
        window_size: int = 1000,
    ) -> None:
        self._threshold = spike_threshold_ms
        self._window_size = window_size
        self._stats: dict[str, LatencyStats] = {}
        self._recent: dict[str, deque[float]] = {}
        self._spike_count: int = 0

    def record(self, symbol: str, event_time_ms: int) -> float:
        """Record a latency measurement from a WebSocket event.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        event_time_ms : int
            Binance event timestamp (``E`` field) in milliseconds.

        Returns
        -------
        float
            Measured latency in milliseconds.
        """
        receive_ms = time.time() * 1000
        latency = receive_ms - event_time_ms

        if symbol not in self._stats:
            self._stats[symbol] = LatencyStats(symbol=symbol)
            self._recent[symbol] = deque(maxlen=self._window_size)

        self._stats[symbol].record(latency)
        self._recent[symbol].append(latency)

        if latency > self._threshold:
            self._spike_count += 1

        return latency

    def get_stats(self, symbol: str) -> LatencyStats | None:
        """Get latency stats for a symbol."""
        return self._stats.get(symbol)

    def get_all_stats(self) -> dict[str, dict]:
        """Get latency stats for all symbols."""
        return {sym: stats.to_dict() for sym, stats in self._stats.items()}

    @property
    def total_spikes(self) -> int:
        """Total number of latency spikes detected."""
        return self._spike_count

    def get_summary(self) -> dict:
        """Get aggregate latency summary."""
        all_stats = list(self._stats.values())
        if not all_stats:
            return {"symbols": 0, "total_spikes": 0}

        return {
            "symbols": len(all_stats),
            "total_spikes": self._spike_count,
            "worst_symbol": max(all_stats, key=lambda s: s.max_latency_ms).symbol,
            "worst_max_ms": max(s.max_latency_ms for s in all_stats),
            "overall_avg_ms": round(
                sum(s.avg_latency_ms for s in all_stats) / len(all_stats), 2
            ),
        }
