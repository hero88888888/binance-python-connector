"""Live statistics tracker — msg/sec, bytes/sec, book size, staleness."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class SymbolStats:
    """Live statistics for a single symbol's data stream."""

    symbol: str
    messages_received: int = 0
    bytes_received: int = 0
    _msg_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    _byte_samples: deque = field(default_factory=lambda: deque(maxlen=1000))

    def record_message(self, byte_size: int = 0) -> None:
        """Record a received message."""
        now = time.monotonic()
        self.messages_received += 1
        self.bytes_received += byte_size
        self._msg_times.append(now)
        self._byte_samples.append((now, byte_size))

    @property
    def messages_per_second(self) -> float:
        """Current message rate (computed over last 10 seconds)."""
        if len(self._msg_times) < 2:
            return 0.0
        now = time.monotonic()
        cutoff = now - 10.0
        recent = [t for t in self._msg_times if t > cutoff]
        if len(recent) < 2:
            return 0.0
        span = recent[-1] - recent[0]
        return len(recent) / span if span > 0 else 0.0

    @property
    def bytes_per_second(self) -> float:
        """Current byte rate (computed over last 10 seconds)."""
        if len(self._byte_samples) < 2:
            return 0.0
        now = time.monotonic()
        cutoff = now - 10.0
        recent = [(t, b) for t, b in self._byte_samples if t > cutoff]
        if len(recent) < 2:
            return 0.0
        total_bytes = sum(b for _, b in recent)
        span = recent[-1][0] - recent[0][0]
        return total_bytes / span if span > 0 else 0.0

    def to_dict(self) -> dict:
        """Export stats as a dict."""
        return {
            "symbol": self.symbol,
            "total_messages": self.messages_received,
            "total_bytes": self.bytes_received,
            "msg_per_sec": round(self.messages_per_second, 1),
            "bytes_per_sec": round(self.bytes_per_second, 0),
            "kb_per_sec": round(self.bytes_per_second / 1024, 1),
        }


class StatsCollector:
    """Collects live statistics across all managed symbols.

    Parameters
    ----------
    enable : bool
        Whether to collect stats. Can be disabled for performance.
    """

    def __init__(self, enable: bool = True) -> None:
        self._enabled = enable
        self._stats: dict[str, SymbolStats] = {}
        self._start_time = time.monotonic()

    def record(self, symbol: str, byte_size: int = 0) -> None:
        """Record a message for a symbol."""
        if not self._enabled:
            return
        if symbol not in self._stats:
            self._stats[symbol] = SymbolStats(symbol=symbol)
        self._stats[symbol].record_message(byte_size)

    def get_stats(self, symbol: str) -> dict | None:
        """Get stats for a single symbol."""
        s = self._stats.get(symbol)
        return s.to_dict() if s else None

    def get_all_stats(self) -> dict[str, dict]:
        """Get stats for all symbols."""
        return {sym: s.to_dict() for sym, s in self._stats.items()}

    def get_summary(self) -> dict:
        """Get aggregate summary across all symbols."""
        all_stats = list(self._stats.values())
        uptime = time.monotonic() - self._start_time
        return {
            "symbols_tracked": len(all_stats),
            "uptime_seconds": round(uptime, 1),
            "total_messages": sum(s.messages_received for s in all_stats),
            "total_bytes": sum(s.bytes_received for s in all_stats),
            "aggregate_msg_per_sec": round(sum(s.messages_per_second for s in all_stats), 1),
            "aggregate_kb_per_sec": round(sum(s.bytes_per_second for s in all_stats) / 1024, 1),
        }
