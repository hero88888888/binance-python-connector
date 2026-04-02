"""Tests for BinanceBook client methods with mocked Binance API responses."""

from __future__ import annotations

import re

import pytest
from aioresponses import aioresponses

from binance_book.client import BinanceBook
from tests.conftest import (
    MOCK_DEPTH,
    MOCK_TRADES,
    MOCK_KLINES,
    MOCK_BOOK_TICKER,
    MOCK_TICKER_24HR,
    MOCK_EXCHANGE_INFO,
)

BASE = "https://api.binance.com"


@pytest.fixture
def book():
    return BinanceBook()


@pytest.fixture
def mock_api():
    with aioresponses() as m:
        yield m


def _mock_depth(m):
    m.get(re.compile(r"https://api\.binance\.com/api/v3/depth\b"), payload=MOCK_DEPTH, repeat=True)


def _mock_trades(m):
    m.get(re.compile(r"https://api\.binance\.com/api/v3/trades\b"), payload=MOCK_TRADES, repeat=True)


def _mock_klines(m):
    m.get(re.compile(r"https://api\.binance\.com/api/v3/klines\b"), payload=MOCK_KLINES, repeat=True)


def _mock_book_ticker(m):
    m.get(re.compile(r"https://api\.binance\.com/api/v3/ticker/bookTicker\b"), payload=MOCK_BOOK_TICKER, repeat=True)


def _mock_ticker_24hr(m):
    m.get(re.compile(r"https://api\.binance\.com/api/v3/ticker/24hr\b"), payload=MOCK_TICKER_24HR, repeat=True)


def _mock_exchange_info(m):
    m.get(re.compile(r"https://api\.binance\.com/api/v3/exchangeInfo\b"), payload=MOCK_EXCHANGE_INFO, repeat=True)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_trade_schema(self, book):
        s = book.schema("trade")
        assert "PRICE" in s
        assert "SIZE" in s
        assert s["PRICE"] == "float"

    def test_level_schema(self, book):
        s = book.schema("level")
        assert "SIDE" in s
        assert "LEVEL" in s

    def test_bar_schema(self, book):
        s = book.schema("bar")
        assert "OPEN" in s
        assert "CLOSE" in s

    def test_all_types(self, book):
        for dt in ["trade", "quote", "bbo", "level", "bar", "ticker", "info"]:
            s = book.schema(dt)
            assert isinstance(s, dict)
            assert len(s) > 0

    def test_invalid_type(self, book):
        with pytest.raises(ValueError, match="Unknown data type"):
            book.schema("INVALID")

    def test_case_insensitive(self, book):
        s1 = book.schema("trade")
        s2 = book.schema("Trade")
        s3 = book.schema("TRADE")
        assert s1 == s2 == s3


# ---------------------------------------------------------------------------
# Orderbook snapshots (mocked)
# ---------------------------------------------------------------------------

class TestObSnapshot:
    def test_returns_list(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=5)
        assert isinstance(result, list)
        assert len(result) == 10  # 5 bids + 5 asks

    def test_has_correct_fields(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=3)
        row = result[0]
        assert "TIMESTAMP" in row
        assert "SYMBOL" in row
        assert "SIDE" in row
        assert "PRICE" in row
        assert "SIZE" in row
        assert "LEVEL" in row

    def test_bids_and_asks(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=3)
        sides = set(str(r["SIDE"]).replace("Side.", "") for r in result)
        assert "BID" in sides
        assert "ASK" in sides

    def test_csv_format(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=3, format="csv")
        assert isinstance(result, str)
        assert "PRICE" in result
        lines = result.strip().split("\n")
        assert len(lines) == 7  # header + 6 rows

    def test_markdown_format(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=2, format="markdown")
        assert isinstance(result, str)
        assert "|" in result
        assert "PRICE" in result

    def test_narrative_format(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=3, format="narrative")
        assert isinstance(result, str)
        assert "BTCUSDT" in result

    def test_dataframe_format(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=3, format="dataframe")
        import pandas as pd
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 6


class TestObSnapshotWide:
    def test_returns_list(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_wide("BTCUSDT", max_levels=5)
        assert isinstance(result, list)
        assert len(result) == 5

    def test_has_both_sides(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_wide("BTCUSDT", max_levels=3)
        row = result[0]
        assert "BID_PRICE" in row
        assert "BID_SIZE" in row
        assert "ASK_PRICE" in row
        assert "ASK_SIZE" in row
        assert "LEVEL" in row

    def test_levels_sequential(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_wide("BTCUSDT", max_levels=5)
        for i, row in enumerate(result):
            assert row["LEVEL"] == i + 1

    def test_bid_ask_correct_side(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_wide("BTCUSDT", max_levels=3)
        assert result[0]["BID_PRICE"] < result[0]["ASK_PRICE"]


class TestObSnapshotFlat:
    def test_returns_dict(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_flat("BTCUSDT", max_levels=3)
        assert isinstance(result, dict)

    def test_has_numbered_fields(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_flat("BTCUSDT", max_levels=3)
        assert "BID_PRICE1" in result
        assert "BID_SIZE1" in result
        assert "ASK_PRICE1" in result
        assert "ASK_SIZE1" in result
        assert "BID_PRICE3" in result
        assert "BID_PRICE4" not in result

    def test_symbol_and_timestamp(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_flat("BTCUSDT", max_levels=2)
        assert result["SYMBOL"] == "BTCUSDT"
        assert result["TIMESTAMP"] > 0


# ---------------------------------------------------------------------------
# Multi-symbol
# ---------------------------------------------------------------------------

class TestMultiSymbol:
    def test_multi_returns_dict(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_wide(["BTCUSDT", "ETHUSDT"], max_levels=3)
        assert isinstance(result, dict)
        assert "BTCUSDT" in result
        assert "ETHUSDT" in result

    def test_multi_each_has_levels(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot_wide(["BTCUSDT", "ETHUSDT"], max_levels=3)
        for sym, rows in result.items():
            assert len(rows) == 3


# ---------------------------------------------------------------------------
# Trades, Klines, Quote, Ticker
# ---------------------------------------------------------------------------

class TestTrades:
    def test_returns_list(self, book, mock_api):
        _mock_trades(mock_api)
        result = book.trades("BTCUSDT", limit=3)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_trade_fields(self, book, mock_api):
        _mock_trades(mock_api)
        result = book.trades("BTCUSDT", limit=1)
        t = result[0]
        assert "PRICE" in t
        assert "SIZE" in t
        assert "TRADE_ID" in t


class TestKlines:
    def test_returns_list(self, book, mock_api):
        _mock_klines(mock_api)
        result = book.klines("BTCUSDT", interval="1m", limit=2)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_bar_fields(self, book, mock_api):
        _mock_klines(mock_api)
        result = book.klines("BTCUSDT", limit=1)
        bar = result[0]
        assert "OPEN" in bar
        assert "HIGH" in bar
        assert "LOW" in bar
        assert "CLOSE" in bar
        assert "VOLUME" in bar


class TestQuote:
    def test_returns_dict(self, book, mock_api):
        _mock_book_ticker(mock_api)
        result = book.quote("BTCUSDT")
        assert isinstance(result, dict)

    def test_quote_fields(self, book, mock_api):
        _mock_book_ticker(mock_api)
        result = book.quote("BTCUSDT")
        assert "BID_PRICE" in result
        assert "ASK_PRICE" in result
        assert "SPREAD" in result
        assert "MID_PRICE" in result
        assert "SPREAD_BPS" in result

    def test_spread_positive(self, book, mock_api):
        _mock_book_ticker(mock_api)
        result = book.quote("BTCUSDT")
        assert result["SPREAD"] >= 0


class TestTicker24hr:
    def test_returns_dict(self, book, mock_api):
        _mock_ticker_24hr(mock_api)
        result = book.ticker_24hr("BTCUSDT")
        assert isinstance(result, dict)
        assert "SYMBOL" in result
        assert "VOLUME" in result


# ---------------------------------------------------------------------------
# Data cleaning integration
# ---------------------------------------------------------------------------

class TestCleanIntegration:
    def test_clean_removes_rows(self, book, mock_api):
        _mock_depth(mock_api)
        raw = book.ob_snapshot("BTCUSDT", max_levels=10)
        clean = book.ob_snapshot("BTCUSDT", max_levels=10, clean=True)
        assert len(clean) <= len(raw)

    def test_annotate_adds_columns(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=5, annotate=True)
        row = result[0]
        assert "IS_DUST" in row
        assert "NOTIONAL_USD" in row
        assert "IS_OUTLIER" in row

    def test_selective_clean(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.ob_snapshot("BTCUSDT", max_levels=10, clean=["dust"])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Analytics integration (mocked)
# ---------------------------------------------------------------------------

class TestAnalyticsIntegration:
    def test_imbalance(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.imbalance("BTCUSDT", levels=5)
        assert isinstance(result, float)
        assert -1.0 <= result <= 1.0

    def test_sweep_by_qty(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.sweep_by_qty("BTCUSDT", side="ASK", qty=1.0)
        assert "vwap" in result
        assert "total_cost" in result
        assert "filled_qty" in result
        assert result["filled_qty"] > 0

    def test_sweep_by_price(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.sweep_by_price("BTCUSDT", side="BID", price=68220.0)
        assert "total_qty" in result
        assert "levels_consumed" in result

    def test_spread(self, book, mock_api):
        _mock_depth(mock_api)
        result = book.spread("BTCUSDT")
        assert "quoted" in result
        assert "quoted_bps" in result
        assert "mid" in result
        assert result["quoted"] >= 0
