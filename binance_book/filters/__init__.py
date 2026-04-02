"""Data cleaning and quality filters for orderbook data.

Calibrated from live Binance analysis:
- 27-49% of top 100 levels are dust (<$66 notional)
- 75-79% of levels have price gaps >1 tick
- Book grows unbounded without pruning (1000→4000 rows in 13h)
"""

from binance_book.filters.dust import filter_dust
from binance_book.filters.stale import filter_stale
from binance_book.filters.gap import filter_gap, annotate_gaps
from binance_book.filters.anomaly import filter_anomalies, annotate_anomalies

__all__ = [
    "filter_dust",
    "filter_stale",
    "filter_gap",
    "annotate_gaps",
    "filter_anomalies",
    "annotate_anomalies",
]
