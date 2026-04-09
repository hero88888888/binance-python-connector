"""Telemetry collection for REST API calls and WebSocket streams.

Provides a unified ``TelemetryCollector`` that tracks:

- REST call counts, per-endpoint latency (min/max/avg), and error rates.
- WebSocket message rates and byte throughput (via ``StatsCollector``).
- WebSocket event-to-receive latency and spike detection (via ``LatencyMonitor``).

Privacy: No API keys, secrets, symbols, or market data values are stored.
Only call counts, timing measurements, and error flags are collected.

Example
-------
>>> book = BinanceBook(enable_telemetry=True)
>>> ob = book.ob_snapshot("BTCUSDT")
>>> report = book.telemetry.get_report()
>>> print(report["rest"]["aggregate"])
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from binance_book.health.latency_monitor import LatencyMonitor
from binance_book.health.stats import StatsCollector


@dataclass
class RestEndpointStats:
    """Telemetry statistics for a single REST endpoint path.

    Parameters
    ----------
    endpoint : str
        The endpoint path (e.g. ``"/api/v3/depth"``).
    """

    endpoint: str
    call_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0

    def record(self, latency_ms: float, success: bool) -> None:
        """Record a completed REST call.

        Parameters
        ----------
        latency_ms : float
            Round-trip latency in milliseconds.
        success : bool
            Whether the call succeeded (no exception / non-5xx).
        """
        self.call_count += 1
        if not success:
            self.error_count += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    @property
    def avg_latency_ms(self) -> float:
        """Average round-trip latency in milliseconds."""
        if self.call_count == 0:
            return 0.0
        return self.total_latency_ms / self.call_count

    @property
    def error_rate(self) -> float:
        """Fraction of calls that resulted in errors (0.0–1.0)."""
        if self.call_count == 0:
            return 0.0
        return self.error_count / self.call_count

    def to_dict(self) -> dict:
        """Export stats as a plain dictionary."""
        return {
            "endpoint": self.endpoint,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2) if self.min_latency_ms != float("inf") else 0.0,
            "max_latency_ms": round(self.max_latency_ms, 2),
        }


class TelemetryCollector:
    """Unified telemetry collector for REST API calls and WebSocket streams.

    Tracks REST call statistics, WebSocket message throughput, and WebSocket
    event-to-receive latency.  All collected data is safe to share — no API
    keys, secrets, symbol prices, or market data values are stored.

    Parameters
    ----------
    enabled : bool
        Whether to collect telemetry.  If False, all ``record_*`` calls are
        no-ops and ``get_report()`` returns an empty summary.  Default True.
    ws_spike_threshold_ms : float
        WebSocket latency above this value (in ms) triggers a spike counter.
        Default 1000 (1 second).
    ws_window_size : int
        Number of recent WebSocket samples to keep per symbol.  Default 1000.
    """

    def __init__(
        self,
        enabled: bool = True,
        ws_spike_threshold_ms: float = 1000.0,
        ws_window_size: int = 1000,
    ) -> None:
        self._enabled = enabled
        self._ws_spike_threshold_ms = ws_spike_threshold_ms
        self._ws_window_size = ws_window_size
        self._rest_stats: dict[str, RestEndpointStats] = {}
        self._latency_monitor = LatencyMonitor(
            spike_threshold_ms=ws_spike_threshold_ms,
            window_size=ws_window_size,
        )
        self._stats_collector = StatsCollector(enable=enabled)
        self._start_time = time.monotonic()

    @property
    def enabled(self) -> bool:
        """Whether telemetry collection is active."""
        return self._enabled

    @property
    def latency_monitor(self) -> LatencyMonitor:
        """WebSocket event-to-receive latency monitor."""
        return self._latency_monitor

    @property
    def stats_collector(self) -> StatsCollector:
        """WebSocket message rate and byte throughput collector."""
        return self._stats_collector

    def record_rest_call(
        self,
        endpoint: str,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Record a completed REST API call.

        Parameters
        ----------
        endpoint : str
            The endpoint path (e.g. ``"/api/v3/depth"``).
        latency_ms : float
            Round-trip latency in milliseconds.
        success : bool
            Whether the call completed without an exception or API error.
        """
        if not self._enabled:
            return
        if endpoint not in self._rest_stats:
            self._rest_stats[endpoint] = RestEndpointStats(endpoint=endpoint)
        self._rest_stats[endpoint].record(latency_ms, success)

    def record_ws_message(
        self,
        symbol: str,
        event_time_ms: int,
        byte_size: int = 0,
    ) -> float:
        """Record a received WebSocket message.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        event_time_ms : int
            Binance event timestamp (``E`` field) in milliseconds.
        byte_size : int
            Raw message size in bytes.  Default 0 (unknown).

        Returns
        -------
        float
            Measured event-to-receive latency in milliseconds.
        """
        if not self._enabled:
            return 0.0
        self._stats_collector.record(symbol, byte_size)
        return self._latency_monitor.record(symbol, event_time_ms)

    def get_report(self) -> dict:
        """Return a complete telemetry snapshot.

        Returns
        -------
        dict
            Keys: ``"enabled"``, ``"uptime_seconds"``, ``"rest"``, ``"websocket"``.
            ``"rest"`` contains per-endpoint stats and an aggregate.
            ``"websocket"`` contains per-symbol latency and throughput stats.
        """
        uptime = round(time.monotonic() - self._start_time, 1)

        if not self._enabled:
            return {
                "enabled": False,
                "uptime_seconds": uptime,
                "rest": {},
                "websocket": {},
            }

        # REST aggregate
        rest_per_endpoint = {ep: s.to_dict() for ep, s in self._rest_stats.items()}
        all_rest = list(self._rest_stats.values())
        rest_aggregate: dict = {
            "total_calls": sum(s.call_count for s in all_rest),
            "total_errors": sum(s.error_count for s in all_rest),
            "error_rate": round(
                sum(s.error_count for s in all_rest) / max(sum(s.call_count for s in all_rest), 1),
                4,
            ),
            "avg_latency_ms": round(
                sum(s.total_latency_ms for s in all_rest) / max(sum(s.call_count for s in all_rest), 1),
                2,
            ),
        }

        # WebSocket
        ws_latency = self._latency_monitor.get_summary()
        ws_latency["per_symbol"] = self._latency_monitor.get_all_stats()
        ws_throughput = self._stats_collector.get_summary()
        ws_throughput["per_symbol"] = self._stats_collector.get_all_stats()

        return {
            "enabled": True,
            "uptime_seconds": uptime,
            "rest": {
                "aggregate": rest_aggregate,
                "per_endpoint": rest_per_endpoint,
            },
            "websocket": {
                "latency": ws_latency,
                "throughput": ws_throughput,
            },
        }

    def reset(self) -> None:
        """Clear all collected telemetry data and restart the uptime clock."""
        self._rest_stats.clear()
        self._latency_monitor = LatencyMonitor(
            spike_threshold_ms=self._ws_spike_threshold_ms,
            window_size=self._ws_window_size,
        )
        self._stats_collector = StatsCollector(enable=self._enabled)
        self._start_time = time.monotonic()
