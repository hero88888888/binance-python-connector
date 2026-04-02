"""Tests for all Pydantic schema models."""

from __future__ import annotations

from binance_book.schemas.base import BaseTick, Side, Timestamp
from binance_book.schemas.trade import Trade
from binance_book.schemas.quote import Quote
from binance_book.schemas.orderbook import OrderBookLevel
from binance_book.schemas.ohlcv import OHLCVBar
from binance_book.schemas.ticker import Ticker24hr
from binance_book.schemas.static import SymbolInfo
from tests.conftest import (
    MOCK_TRADES,
    MOCK_KLINES,
    MOCK_BOOK_TICKER,
    MOCK_TICKER_24HR,
    MOCK_EXCHANGE_INFO,
    MOCK_DEPTH,
)


class TestTimestamp:
    def test_from_ms(self):
        dt = Timestamp.from_ms(1711929600000)
        assert dt.year == 2024
        assert dt.month == 4

    def test_now_ms(self):
        ms = Timestamp.now_ms()
        assert isinstance(ms, int)
        assert ms > 1700000000000


class TestSide:
    def test_values(self):
        assert Side.BID == "BID"
        assert Side.ASK == "ASK"


class TestBaseTick:
    def test_creation(self):
        tick = BaseTick(TIMESTAMP=1711929600000, SYMBOL="BTCUSDT")
        assert tick.TIMESTAMP == 1711929600000
        assert tick.SYMBOL == "BTCUSDT"

    def test_datetime_utc(self):
        tick = BaseTick(TIMESTAMP=1711929600000)
        dt = tick.datetime_utc
        assert dt.year == 2024

    def test_optional_symbol(self):
        tick = BaseTick(TIMESTAMP=1711929600000)
        assert tick.SYMBOL is None


class TestTrade:
    def test_from_binance_rest(self):
        t = Trade.from_binance(MOCK_TRADES[0], symbol="BTCUSDT")
        assert t.PRICE == 68225.0
        assert t.SIZE == 0.5
        assert t.TRADE_ID == 6167847072
        assert t.IS_BUYER_MAKER is False
        assert t.SYMBOL == "BTCUSDT"
        assert t.TIMESTAMP == 1711929600000

    def test_from_binance_ws(self):
        ws_data = {
            "e": "trade", "E": 1711929600000, "s": "BTCUSDT",
            "t": 123, "p": "68225.00", "q": "1.5", "T": 1711929600000, "m": True,
        }
        t = Trade.from_binance(ws_data)
        assert t.PRICE == 68225.0
        assert t.SIZE == 1.5
        assert t.IS_BUYER_MAKER is True

    def test_model_dump(self):
        t = Trade.from_binance(MOCK_TRADES[0], symbol="BTCUSDT")
        d = t.model_dump()
        assert "PRICE" in d
        assert "SIZE" in d
        assert isinstance(d, dict)


class TestQuote:
    def test_from_binance_rest(self):
        q = Quote.from_binance(MOCK_BOOK_TICKER)
        assert q.BID_PRICE == 68225.0
        assert q.BID_SIZE == 1.5
        assert q.ASK_PRICE == 68225.01
        assert q.ASK_SIZE == 0.4
        assert q.SYMBOL == "BTCUSDT"

    def test_spread_properties(self):
        q = Quote.from_binance(MOCK_BOOK_TICKER)
        assert abs(q.SPREAD - 0.01) < 0.001
        assert abs(q.MID_PRICE - 68225.005) < 0.01
        assert q.SPREAD_BPS > 0

    def test_from_binance_ws(self):
        ws_data = {
            "u": 400900217, "s": "BTCUSDT", "E": 1711929600000,
            "b": "68225.00", "B": "1.50", "a": "68225.01", "A": "0.40",
        }
        q = Quote.from_binance(ws_data)
        assert q.BID_PRICE == 68225.0
        assert q.ASK_PRICE == 68225.01


class TestOrderBookLevel:
    def test_from_depth_snapshot(self):
        levels = OrderBookLevel.from_depth_snapshot(
            bids=MOCK_DEPTH["bids"][:3],
            asks=MOCK_DEPTH["asks"][:3],
            last_update_id=MOCK_DEPTH["lastUpdateId"],
            symbol="BTCUSDT",
        )
        assert len(levels) == 6
        bids = [l for l in levels if l.SIDE == Side.BID]
        asks = [l for l in levels if l.SIDE == Side.ASK]
        assert len(bids) == 3
        assert len(asks) == 3
        assert bids[0].PRICE == 68225.0
        assert bids[0].LEVEL == 1
        assert asks[0].PRICE == 68225.01
        assert asks[0].LEVEL == 1

    def test_notional_property(self):
        levels = OrderBookLevel.from_depth_snapshot(
            bids=MOCK_DEPTH["bids"][:1],
            asks=MOCK_DEPTH["asks"][:1],
            last_update_id=1,
            symbol="BTCUSDT",
        )
        bid = levels[0]
        assert abs(bid.NOTIONAL - 68225.0 * 1.5) < 1.0

    def test_update_id_preserved(self):
        levels = OrderBookLevel.from_depth_snapshot(
            bids=MOCK_DEPTH["bids"][:1],
            asks=[],
            last_update_id=12345,
        )
        assert levels[0].UPDATE_ID == 12345


class TestOHLCVBar:
    def test_from_binance_kline(self):
        bar = OHLCVBar.from_binance_kline(MOCK_KLINES[0], symbol="BTCUSDT")
        assert bar.OPEN == 68100.0
        assert bar.HIGH == 68300.0
        assert bar.LOW == 68050.0
        assert bar.CLOSE == 68225.0
        assert bar.VOLUME == 1234.5
        assert bar.TRADE_COUNT == 45000
        assert bar.SYMBOL == "BTCUSDT"

    def test_from_binance_ws(self):
        ws_data = {
            "e": "kline", "k": {
                "t": 1711929600000, "T": 1711929659999, "s": "BTCUSDT",
                "o": "68100", "h": "68300", "l": "68050", "c": "68225",
                "v": "1234.5", "q": "84200000", "n": 45000,
                "V": "600", "Q": "40900000",
            },
        }
        bar = OHLCVBar.from_binance_ws(ws_data)
        assert bar.OPEN == 68100.0
        assert bar.CLOSE == 68225.0


class TestTicker24hr:
    def test_from_binance(self):
        t = Ticker24hr.from_binance(MOCK_TICKER_24HR)
        assert t.SYMBOL == "BTCUSDT"
        assert t.OPEN == 67500.0
        assert t.HIGH == 69000.0
        assert t.LOW == 67200.0
        assert t.CLOSE == 68225.0
        assert t.VOLUME == 25000.0
        assert t.TRADE_COUNT == 1200000
        assert t.PRICE_CHANGE == 725.0
        assert abs(t.PRICE_CHANGE_PERCENT - 1.07) < 0.01


class TestSymbolInfo:
    def test_from_binance(self):
        info = SymbolInfo.from_binance(MOCK_EXCHANGE_INFO["symbols"][0])
        assert info.SYMBOL == "BTCUSDT"
        assert info.BASE_ASSET == "BTC"
        assert info.QUOTE_ASSET == "USDT"
        assert info.STATUS == "TRADING"
        assert info.TICK_SIZE == 0.01
        assert info.LOT_SIZE == 0.00001
        assert info.MIN_NOTIONAL == 5.0
        assert info.MIN_QTY == 0.00001
        assert info.MAX_QTY == 9000.0

    def test_empty_filters(self):
        info = SymbolInfo.from_binance(MOCK_EXCHANGE_INFO["symbols"][2])
        assert info.SYMBOL == "BNBBTC"
        assert info.TICK_SIZE == 0.0
        assert info.LOT_SIZE == 0.0
