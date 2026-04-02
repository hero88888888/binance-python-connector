"""Tests for data cleaning filters — dust, stale, gap, anomaly."""

from __future__ import annotations

import time

from binance_book.filters.dust import filter_dust, annotate_dust
from binance_book.filters.stale import filter_stale, annotate_stale
from binance_book.filters.gap import filter_gap, annotate_gaps
from binance_book.filters.anomaly import filter_anomalies, annotate_anomalies


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

OB_SNAPSHOT_ROWS = [
    {"SIDE": "BID", "PRICE": 68225.0, "SIZE": 1.5, "LEVEL": 1, "TIMESTAMP": int(time.time() * 1000)},
    {"SIDE": "BID", "PRICE": 68224.0, "SIZE": 0.00005, "LEVEL": 2, "TIMESTAMP": int(time.time() * 1000)},  # dust
    {"SIDE": "BID", "PRICE": 68220.0, "SIZE": 0.3, "LEVEL": 3, "TIMESTAMP": int(time.time() * 1000)},
    {"SIDE": "ASK", "PRICE": 68226.0, "SIZE": 0.4, "LEVEL": 1, "TIMESTAMP": int(time.time() * 1000)},
    {"SIDE": "ASK", "PRICE": 68227.0, "SIZE": 0.00003, "LEVEL": 2, "TIMESTAMP": int(time.time() * 1000)},  # dust
    {"SIDE": "ASK", "PRICE": 68230.0, "SIZE": 0.5, "LEVEL": 3, "TIMESTAMP": int(time.time() * 1000)},
]

WIDE_ROWS = [
    {"LEVEL": 1, "BID_PRICE": 100.0, "BID_SIZE": 1.0, "ASK_PRICE": 101.0, "ASK_SIZE": 0.5, "TIMESTAMP": int(time.time() * 1000)},
    {"LEVEL": 2, "BID_PRICE": 99.0, "BID_SIZE": 0.00001, "ASK_PRICE": 102.0, "ASK_SIZE": 0.00001, "TIMESTAMP": int(time.time() * 1000)},  # dust
    {"LEVEL": 3, "BID_PRICE": 98.0, "BID_SIZE": 2.0, "ASK_PRICE": 103.0, "ASK_SIZE": 1.0, "TIMESTAMP": int(time.time() * 1000)},
]


class TestDustFilter:
    def test_removes_dust(self):
        result = filter_dust(OB_SNAPSHOT_ROWS, min_notional_usd=5.0)
        assert len(result) < len(OB_SNAPSHOT_ROWS)
        for row in result:
            notional = row["PRICE"] * row["SIZE"]
            assert notional >= 5.0

    def test_keeps_large_orders(self):
        result = filter_dust(OB_SNAPSHOT_ROWS, min_notional_usd=5.0)
        prices = [r["PRICE"] for r in result]
        assert 68225.0 in prices  # 68225 * 1.5 = $102K

    def test_custom_threshold(self):
        result_low = filter_dust(OB_SNAPSHOT_ROWS, min_notional_usd=1.0)
        result_high = filter_dust(OB_SNAPSHOT_ROWS, min_notional_usd=10000.0)
        assert len(result_low) >= len(result_high)

    def test_annotate_dust(self):
        result = annotate_dust(OB_SNAPSHOT_ROWS, min_notional_usd=5.0)
        assert len(result) == len(OB_SNAPSHOT_ROWS)
        for row in result:
            assert "IS_DUST" in row
            assert "NOTIONAL_USD" in row
            assert isinstance(row["IS_DUST"], bool)
            assert isinstance(row["NOTIONAL_USD"], float)

    def test_annotate_flags_correctly(self):
        result = annotate_dust(OB_SNAPSHOT_ROWS, min_notional_usd=5.0)
        dust_rows = [r for r in result if r["IS_DUST"]]
        non_dust = [r for r in result if not r["IS_DUST"]]
        assert len(dust_rows) >= 2  # at least our 2 known dust rows
        for r in non_dust:
            assert r["NOTIONAL_USD"] >= 5.0

    def test_wide_format_dust(self):
        result = filter_dust(WIDE_ROWS, min_notional_usd=5.0)
        assert len(result) < len(WIDE_ROWS)

    def test_empty_input(self):
        assert filter_dust([], min_notional_usd=5.0) == []


class TestStaleFilter:
    def test_removes_stale(self):
        now_ms = int(time.time() * 1000)
        rows = [
            {"TIMESTAMP": now_ms, "PRICE": 100.0, "SIZE": 1.0},
            {"TIMESTAMP": now_ms - 10000, "PRICE": 99.0, "SIZE": 1.0},  # 10s old
            {"TIMESTAMP": now_ms - 100, "PRICE": 101.0, "SIZE": 1.0},
        ]
        result = filter_stale(rows, staleness_ms=5000)
        assert len(result) == 2

    def test_keeps_fresh(self):
        now_ms = int(time.time() * 1000)
        rows = [{"TIMESTAMP": now_ms, "PRICE": 100.0, "SIZE": 1.0}]
        result = filter_stale(rows, staleness_ms=5000)
        assert len(result) == 1

    def test_annotate_stale(self):
        now_ms = int(time.time() * 1000)
        rows = [
            {"TIMESTAMP": now_ms, "PRICE": 100.0},
            {"TIMESTAMP": now_ms - 10000, "PRICE": 99.0},
        ]
        result = annotate_stale(rows, staleness_ms=5000)
        assert len(result) == 2
        assert result[0]["IS_STALE"] is False
        assert result[1]["IS_STALE"] is True
        assert "STALENESS_MS" in result[0]

    def test_empty_input(self):
        assert filter_stale([], staleness_ms=5000) == []


class TestGapFilter:
    def test_removes_large_gaps(self):
        rows = [
            {"SIDE": "BID", "PRICE": 100.0, "SIZE": 1.0, "LEVEL": 1},
            {"SIDE": "BID", "PRICE": 99.99, "SIZE": 1.0, "LEVEL": 2},  # 1 tick gap
            {"SIDE": "BID", "PRICE": 99.0, "SIZE": 1.0, "LEVEL": 3},   # 99 tick gap
        ]
        result = filter_gap(rows, max_gap_ticks=50, tick_size=0.01)
        assert len(result) < len(rows)

    def test_keeps_tight_book(self):
        rows = [
            {"SIDE": "BID", "PRICE": 100.0, "SIZE": 1.0, "LEVEL": 1},
            {"SIDE": "BID", "PRICE": 99.99, "SIZE": 1.0, "LEVEL": 2},
            {"SIDE": "BID", "PRICE": 99.98, "SIZE": 1.0, "LEVEL": 3},
        ]
        result = filter_gap(rows, max_gap_ticks=50, tick_size=0.01)
        assert len(result) == 3

    def test_wide_format(self):
        rows = [
            {"LEVEL": 1, "BID_PRICE": 100.0, "BID_SIZE": 1.0, "ASK_PRICE": 101.0, "ASK_SIZE": 1.0},
            {"LEVEL": 2, "BID_PRICE": 99.99, "BID_SIZE": 1.0, "ASK_PRICE": 101.01, "ASK_SIZE": 1.0},
            {"LEVEL": 3, "BID_PRICE": 98.0, "BID_SIZE": 1.0, "ASK_PRICE": 103.0, "ASK_SIZE": 1.0},  # big gap
        ]
        result = filter_gap(rows, max_gap_ticks=50, tick_size=0.01)
        assert len(result) < 3

    def test_annotate_gaps(self):
        rows = [
            {"SIDE": "BID", "PRICE": 100.0, "SIZE": 1.0, "LEVEL": 1},
            {"SIDE": "BID", "PRICE": 99.5, "SIZE": 1.0, "LEVEL": 2},
        ]
        result = annotate_gaps(rows, tick_size=0.01)
        assert result[0]["GAP_TICKS"] == 0  # first level
        assert result[1]["GAP_TICKS"] == 50  # 0.50 / 0.01

    def test_empty_input(self):
        assert filter_gap([], max_gap_ticks=50) == []


class TestAnomalyFilter:
    def test_removes_outliers(self):
        rows = [
            {"SIZE": 1.0}, {"SIZE": 1.1}, {"SIZE": 0.9}, {"SIZE": 1.0},
            {"SIZE": 1.2}, {"SIZE": 0.8}, {"SIZE": 1.0}, {"SIZE": 1.1},
            {"SIZE": 100.0},  # outlier
        ]
        result = filter_anomalies(rows, sigma=2.0)
        assert len(result) < len(rows)
        sizes = [r["SIZE"] for r in result]
        assert 100.0 not in sizes

    def test_keeps_normal(self):
        rows = [{"SIZE": 1.0}, {"SIZE": 1.1}, {"SIZE": 0.9}]
        result = filter_anomalies(rows, sigma=3.0)
        assert len(result) == 3

    def test_annotate_anomalies(self):
        rows = [
            {"SIZE": 1.0}, {"SIZE": 1.1}, {"SIZE": 0.9}, {"SIZE": 1.0},
            {"SIZE": 1.0}, {"SIZE": 1.1}, {"SIZE": 0.9}, {"SIZE": 1.0},
            {"SIZE": 100.0},  # outlier
        ]
        result = annotate_anomalies(rows, sigma=2.0)
        assert len(result) == 9
        outlier = result[8]
        assert outlier["IS_OUTLIER"] is True
        assert result[0]["IS_OUTLIER"] is False

    def test_small_dataset(self):
        rows = [{"SIZE": 1.0}]
        result = filter_anomalies(rows, sigma=3.0)
        assert len(result) == 1

    def test_empty_input(self):
        assert filter_anomalies([], sigma=3.0) == []

    def test_wide_format(self):
        rows = [
            {"BID_SIZE": 1.0, "ASK_SIZE": 1.0},
            {"BID_SIZE": 1.1, "ASK_SIZE": 1.1},
            {"BID_SIZE": 0.9, "ASK_SIZE": 0.9},
            {"BID_SIZE": 1.0, "ASK_SIZE": 1.0},
            {"BID_SIZE": 1.0, "ASK_SIZE": 1.0},
            {"BID_SIZE": 1.1, "ASK_SIZE": 1.1},
            {"BID_SIZE": 0.9, "ASK_SIZE": 0.9},
            {"BID_SIZE": 1.0, "ASK_SIZE": 1.0},
            {"BID_SIZE": 100.0, "ASK_SIZE": 100.0},  # outlier
        ]
        result = filter_anomalies(rows, sigma=2.0)
        assert len(result) < len(rows)
