"""Tests for TelemetryCollector and BinanceBook telemetry integration."""

from __future__ import annotations

import re
import time
from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses

from binance_book.telemetry import RestEndpointStats, TelemetryCollector
from binance_book.client import BinanceBook
from tests.conftest import MOCK_DEPTH, MOCK_TRADES, MOCK_BOOK_TICKER


# ---------------------------------------------------------------------------
# RestEndpointStats
# ---------------------------------------------------------------------------

class TestRestEndpointStats:
    def test_initial_state(self):
        stats = RestEndpointStats(endpoint="/api/v3/depth")
        assert stats.call_count == 0
        assert stats.error_count == 0
        assert stats.avg_latency_ms == 0.0
        assert stats.error_rate == 0.0

    def test_record_success(self):
        stats = RestEndpointStats(endpoint="/api/v3/depth")
        stats.record(latency_ms=50.0, success=True)
        assert stats.call_count == 1
        assert stats.error_count == 0
        assert stats.avg_latency_ms == 50.0
        assert stats.min_latency_ms == 50.0
        assert stats.max_latency_ms == 50.0

    def test_record_error(self):
        stats = RestEndpointStats(endpoint="/api/v3/depth")
        stats.record(latency_ms=100.0, success=False)
        assert stats.call_count == 1
        assert stats.error_count == 1
        assert stats.error_rate == 1.0

    def test_record_multiple(self):
        stats = RestEndpointStats(endpoint="/api/v3/depth")
        stats.record(latency_ms=20.0, success=True)
        stats.record(latency_ms=80.0, success=True)
        stats.record(latency_ms=50.0, success=False)
        assert stats.call_count == 3
        assert stats.error_count == 1
        assert stats.avg_latency_ms == 50.0
        assert stats.min_latency_ms == 20.0
        assert stats.max_latency_ms == 80.0
        assert round(stats.error_rate, 4) == round(1 / 3, 4)

    def test_to_dict(self):
        stats = RestEndpointStats(endpoint="/api/v3/depth")
        stats.record(latency_ms=30.0, success=True)
        d = stats.to_dict()
        assert d["endpoint"] == "/api/v3/depth"
        assert d["call_count"] == 1
        assert d["error_count"] == 0
        assert d["avg_latency_ms"] == 30.0
        assert d["min_latency_ms"] == 30.0
        assert d["max_latency_ms"] == 30.0
        assert d["error_rate"] == 0.0

    def test_to_dict_no_calls(self):
        stats = RestEndpointStats(endpoint="/api/v3/trades")
        d = stats.to_dict()
        assert d["call_count"] == 0
        assert d["min_latency_ms"] == 0.0  # inf mapped to 0


# ---------------------------------------------------------------------------
# TelemetryCollector — disabled
# ---------------------------------------------------------------------------

class TestTelemetryCollectorDisabled:
    def test_disabled_record_rest_is_noop(self):
        tc = TelemetryCollector(enabled=False)
        tc.record_rest_call("/api/v3/depth", 50.0, True)
        report = tc.get_report()
        assert report["enabled"] is False
        assert report["rest"] == {}
        assert report["websocket"] == {}

    def test_disabled_record_ws_returns_zero(self):
        tc = TelemetryCollector(enabled=False)
        latency = tc.record_ws_message("BTCUSDT", int(time.time() * 1000) - 100, 512)
        assert latency == 0.0

    def test_disabled_get_report_has_uptime(self):
        tc = TelemetryCollector(enabled=False)
        report = tc.get_report()
        assert "uptime_seconds" in report
        assert report["uptime_seconds"] >= 0.0


# ---------------------------------------------------------------------------
# TelemetryCollector — enabled
# ---------------------------------------------------------------------------

class TestTelemetryCollectorEnabled:
    def test_initial_get_report(self):
        tc = TelemetryCollector(enabled=True)
        report = tc.get_report()
        assert report["enabled"] is True
        assert "uptime_seconds" in report
        assert report["rest"]["aggregate"]["total_calls"] == 0
        assert report["rest"]["per_endpoint"] == {}

    def test_record_rest_call_success(self):
        tc = TelemetryCollector(enabled=True)
        tc.record_rest_call("/api/v3/depth", 45.0, True)
        report = tc.get_report()
        agg = report["rest"]["aggregate"]
        assert agg["total_calls"] == 1
        assert agg["total_errors"] == 0
        assert agg["error_rate"] == 0.0
        assert "/api/v3/depth" in report["rest"]["per_endpoint"]

    def test_record_rest_call_error(self):
        tc = TelemetryCollector(enabled=True)
        tc.record_rest_call("/api/v3/depth", 200.0, False)
        report = tc.get_report()
        agg = report["rest"]["aggregate"]
        assert agg["total_calls"] == 1
        assert agg["total_errors"] == 1
        assert agg["error_rate"] == 1.0

    def test_record_multiple_endpoints(self):
        tc = TelemetryCollector(enabled=True)
        tc.record_rest_call("/api/v3/depth", 30.0, True)
        tc.record_rest_call("/api/v3/trades", 50.0, True)
        tc.record_rest_call("/api/v3/depth", 40.0, False)
        report = tc.get_report()
        agg = report["rest"]["aggregate"]
        assert agg["total_calls"] == 3
        assert agg["total_errors"] == 1
        assert "/api/v3/depth" in report["rest"]["per_endpoint"]
        assert "/api/v3/trades" in report["rest"]["per_endpoint"]
        depth_stats = report["rest"]["per_endpoint"]["/api/v3/depth"]
        assert depth_stats["call_count"] == 2

    def test_record_ws_message(self):
        tc = TelemetryCollector(enabled=True)
        now_ms = int(time.time() * 1000)
        event_ms = now_ms - 50  # 50ms old event
        latency = tc.record_ws_message("BTCUSDT", event_ms, 1024)
        assert latency > 0
        report = tc.get_report()
        ws = report["websocket"]
        assert "latency" in ws
        assert "throughput" in ws
        assert ws["latency"]["symbols"] == 1
        assert "BTCUSDT" in ws["latency"]["per_symbol"]
        assert "BTCUSDT" in ws["throughput"]["per_symbol"]

    def test_reset_clears_data(self):
        tc = TelemetryCollector(enabled=True)
        tc.record_rest_call("/api/v3/depth", 30.0, True)
        now_ms = int(time.time() * 1000)
        tc.record_ws_message("BTCUSDT", now_ms - 10, 512)
        tc.reset()
        report = tc.get_report()
        assert report["rest"]["aggregate"]["total_calls"] == 0
        assert report["rest"]["per_endpoint"] == {}
        assert report["websocket"]["latency"]["symbols"] == 0

    def test_uptime_increases(self):
        tc = TelemetryCollector(enabled=True)
        t1 = tc.get_report()["uptime_seconds"]
        time.sleep(0.05)
        t2 = tc.get_report()["uptime_seconds"]
        assert t2 >= t1

    def test_avg_latency_in_aggregate(self):
        tc = TelemetryCollector(enabled=True)
        tc.record_rest_call("/api/v3/depth", 100.0, True)
        tc.record_rest_call("/api/v3/depth", 200.0, True)
        report = tc.get_report()
        assert report["rest"]["aggregate"]["avg_latency_ms"] == 150.0

    def test_properties(self):
        tc = TelemetryCollector(enabled=True)
        assert tc.enabled is True
        assert tc.latency_monitor is not None
        assert tc.stats_collector is not None


# ---------------------------------------------------------------------------
# BinanceBook telemetry integration (REST calls mocked)
# ---------------------------------------------------------------------------

class TestBinanceBookTelemetry:
    @pytest.fixture
    def mock_api(self):
        with aioresponses() as m:
            yield m

    def test_telemetry_disabled_by_default(self):
        book = BinanceBook()
        assert book.telemetry.enabled is False

    def test_telemetry_enabled(self):
        book = BinanceBook(enable_telemetry=True)
        assert book.telemetry.enabled is True

    def test_telemetry_records_depth_call(self, mock_api):
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/depth\b"),
            payload=MOCK_DEPTH,
            repeat=True,
        )
        book = BinanceBook(enable_telemetry=True)
        book.ob_snapshot("BTCUSDT", max_levels=5)
        report = book.telemetry.get_report()
        agg = report["rest"]["aggregate"]
        assert agg["total_calls"] == 1
        assert agg["total_errors"] == 0

    def test_telemetry_records_multiple_calls(self, mock_api):
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/depth\b"),
            payload=MOCK_DEPTH,
            repeat=True,
        )
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/trades\b"),
            payload=MOCK_TRADES,
            repeat=True,
        )
        book = BinanceBook(enable_telemetry=True)
        book.ob_snapshot("BTCUSDT", max_levels=5)
        book.trades("BTCUSDT", limit=3)
        report = book.telemetry.get_report()
        agg = report["rest"]["aggregate"]
        assert agg["total_calls"] == 2

    def test_telemetry_not_collected_when_disabled(self, mock_api):
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/depth\b"),
            payload=MOCK_DEPTH,
            repeat=True,
        )
        book = BinanceBook(enable_telemetry=False)
        book.ob_snapshot("BTCUSDT", max_levels=5)
        report = book.telemetry.get_report()
        assert report["enabled"] is False
        assert report["rest"] == {}

    def test_telemetry_per_endpoint_stats(self, mock_api):
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/depth\b"),
            payload=MOCK_DEPTH,
            repeat=True,
        )
        book = BinanceBook(enable_telemetry=True)
        book.ob_snapshot("BTCUSDT", max_levels=5)
        book.ob_snapshot("ETHUSDT", max_levels=5)
        report = book.telemetry.get_report()
        # Two depth calls but same endpoint path
        depth_ep = report["rest"]["per_endpoint"].get("/api/v3/depth")
        assert depth_ep is not None
        assert depth_ep["call_count"] == 2

    def test_telemetry_latency_positive(self, mock_api):
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/depth\b"),
            payload=MOCK_DEPTH,
            repeat=True,
        )
        book = BinanceBook(enable_telemetry=True)
        book.ob_snapshot("BTCUSDT", max_levels=5)
        report = book.telemetry.get_report()
        assert report["rest"]["aggregate"]["avg_latency_ms"] >= 0.0

    def test_telemetry_reset(self, mock_api):
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/depth\b"),
            payload=MOCK_DEPTH,
            repeat=True,
        )
        book = BinanceBook(enable_telemetry=True)
        book.ob_snapshot("BTCUSDT", max_levels=5)
        book.telemetry.reset()
        report = book.telemetry.get_report()
        assert report["rest"]["aggregate"]["total_calls"] == 0

    def test_telemetry_book_ticker(self, mock_api):
        mock_api.get(
            re.compile(r"https://api\.binance\.com/api/v3/ticker/bookTicker\b"),
            payload=MOCK_BOOK_TICKER,
            repeat=True,
        )
        book = BinanceBook(enable_telemetry=True)
        book.quote("BTCUSDT")
        report = book.telemetry.get_report()
        assert report["rest"]["aggregate"]["total_calls"] == 1

    def test_telemetry_ws_manual_record(self):
        book = BinanceBook(enable_telemetry=True)
        now_ms = int(time.time() * 1000)
        book.telemetry.record_ws_message("BTCUSDT", now_ms - 20, 512)
        report = book.telemetry.get_report()
        assert report["websocket"]["latency"]["symbols"] == 1
        btc = report["websocket"]["latency"]["per_symbol"]["BTCUSDT"]
        assert btc["sample_count"] == 1
        assert btc["last_ms"] >= 0


# ---------------------------------------------------------------------------
# Package-level export
# ---------------------------------------------------------------------------

class TestTelemetryExport:
    def test_importable_from_package(self):
        from binance_book import TelemetryCollector as TC
        assert TC is TelemetryCollector

    def test_in_all(self):
        import binance_book
        assert "TelemetryCollector" in binance_book.__all__
