"""Tests for analytics — imbalance, sweep, spread, vwap, microstructure."""

from __future__ import annotations

from binance_book.analytics.imbalance import compute_imbalance, imbalance_from_rows
from binance_book.analytics.sweep import sweep_by_qty, sweep_by_price
from binance_book.analytics.spread import compute_spread, spread_from_rows
from binance_book.analytics.vwap import compute_vwap
from binance_book.analytics.microstructure import classify_ticks, estimate_market_impact


class TestImbalance:
    def test_balanced_book(self):
        bids = [(100.0, 1.0), (99.0, 1.0)]
        asks = [(101.0, 1.0), (102.0, 1.0)]
        assert compute_imbalance(bids, asks) == 0.0

    def test_bid_heavy(self):
        bids = [(100.0, 10.0)]
        asks = [(101.0, 1.0)]
        imb = compute_imbalance(bids, asks)
        assert imb > 0.5

    def test_ask_heavy(self):
        bids = [(100.0, 1.0)]
        asks = [(101.0, 10.0)]
        imb = compute_imbalance(bids, asks)
        assert imb < -0.5

    def test_with_levels_limit(self):
        bids = [(100.0, 10.0), (99.0, 1.0), (98.0, 1.0)]
        asks = [(101.0, 1.0), (102.0, 10.0), (103.0, 10.0)]
        imb_1 = compute_imbalance(bids, asks, levels=1)
        imb_all = compute_imbalance(bids, asks)
        assert imb_1 > imb_all  # top level is bid-heavy

    def test_weighted(self):
        bids = [(100.0, 1.0)]
        asks = [(200.0, 1.0)]  # same qty but double price
        imb_raw = compute_imbalance(bids, asks, weighted=False)
        imb_weighted = compute_imbalance(bids, asks, weighted=True)
        assert imb_raw == 0.0  # equal qty
        assert imb_weighted < 0  # ask side has more notional

    def test_empty_book(self):
        assert compute_imbalance([], []) == 0.0

    def test_from_rows(self):
        rows = [
            {"BID_PRICE": 100.0, "BID_SIZE": 5.0, "ASK_PRICE": 101.0, "ASK_SIZE": 3.0},
            {"BID_PRICE": 99.0, "BID_SIZE": 2.0, "ASK_PRICE": 102.0, "ASK_SIZE": 1.0},
        ]
        imb = imbalance_from_rows(rows)
        assert imb > 0  # 7 bid vs 4 ask


class TestSweepByQty:
    def test_single_level_fill(self):
        levels = [(100.0, 5.0), (101.0, 3.0)]
        result = sweep_by_qty(levels, qty=3.0)
        assert result["vwap"] == 100.0
        assert result["filled_qty"] == 3.0
        assert result["total_cost"] == 300.0
        assert result["levels_consumed"] == 1

    def test_multi_level_fill(self):
        levels = [(100.0, 2.0), (101.0, 3.0)]
        result = sweep_by_qty(levels, qty=4.0)
        assert result["filled_qty"] == 4.0
        assert result["levels_consumed"] == 2
        expected_cost = 100.0 * 2.0 + 101.0 * 2.0
        assert abs(result["total_cost"] - expected_cost) < 0.01
        expected_vwap = expected_cost / 4.0
        assert abs(result["vwap"] - expected_vwap) < 0.01

    def test_partial_fill(self):
        levels = [(100.0, 1.0)]
        result = sweep_by_qty(levels, qty=5.0)
        assert result["filled_qty"] == 1.0  # can only fill 1
        assert result["levels_consumed"] == 1

    def test_empty_book(self):
        result = sweep_by_qty([], qty=1.0)
        assert result["filled_qty"] == 0.0
        assert result["vwap"] == 0.0


class TestSweepByPrice:
    def test_bid_sweep(self):
        levels = [(100.0, 2.0), (99.0, 3.0), (98.0, 1.0)]
        result = sweep_by_price(levels, price=99.0, side="BID")
        assert result["total_qty"] == 5.0  # 100 + 99 levels
        assert result["levels_consumed"] == 2

    def test_ask_sweep(self):
        levels = [(101.0, 1.0), (102.0, 2.0), (103.0, 3.0)]
        result = sweep_by_price(levels, price=102.0, side="ASK")
        assert result["total_qty"] == 3.0  # 101 + 102 levels
        assert result["levels_consumed"] == 2

    def test_no_match(self):
        levels = [(100.0, 2.0), (99.0, 3.0)]
        result = sweep_by_price(levels, price=101.0, side="BID")
        assert result["total_qty"] == 0.0


class TestSpread:
    def test_basic_spread(self):
        result = compute_spread(100.0, 100.10, 5.0, 3.0)
        assert abs(result["quoted"] - 0.10) < 0.001
        assert result["mid"] == 100.05
        assert result["quoted_bps"] > 0
        assert result["notional_bid"] == 500.0
        assert result["notional_ask"] == 300.3

    def test_zero_spread(self):
        result = compute_spread(100.0, 100.0)
        assert result["quoted"] == 0.0
        assert result["quoted_bps"] == 0.0

    def test_from_rows(self):
        rows = [{"BID_PRICE": 100.0, "BID_SIZE": 5.0, "ASK_PRICE": 100.10, "ASK_SIZE": 3.0}]
        result = spread_from_rows(rows)
        assert abs(result["quoted"] - 0.10) < 0.001

    def test_from_empty_rows(self):
        result = spread_from_rows([])
        assert result["quoted"] == 0


class TestVWAP:
    def test_basic_vwap(self):
        trades = [
            {"PRICE": 100.0, "SIZE": 2.0},
            {"PRICE": 102.0, "SIZE": 3.0},
        ]
        result = compute_vwap(trades)
        expected = (100.0 * 2.0 + 102.0 * 3.0) / 5.0
        assert abs(result["vwap"] - expected) < 0.001
        assert result["total_volume"] == 5.0
        assert result["trade_count"] == 2

    def test_empty_trades(self):
        result = compute_vwap([])
        assert result["vwap"] == 0.0
        assert result["trade_count"] == 0


class TestMicrostructure:
    def test_classify_ticks(self):
        trades = [
            {"PRICE": 100.0},
            {"PRICE": 101.0},
            {"PRICE": 101.0},
            {"PRICE": 99.0},
        ]
        result = classify_ticks(trades)
        assert result[0]["TICK_DIRECTION"] == "ZERO"  # first
        assert result[1]["TICK_DIRECTION"] == "UP"
        assert result[2]["TICK_DIRECTION"] == "ZERO"
        assert result[3]["TICK_DIRECTION"] == "DOWN"

    def test_market_impact(self):
        levels = [(100.0, 1.0), (101.0, 1.0), (102.0, 1.0)]
        result = estimate_market_impact(levels, qty=2.0)
        assert result["best_price"] == 100.0
        assert result["filled_qty"] == 2.0
        expected_vwap = (100.0 + 101.0) / 2.0
        assert abs(result["vwap"] - expected_vwap) < 0.01
        assert result["slippage"] > 0
        assert result["slippage_bps"] > 0

    def test_market_impact_empty(self):
        result = estimate_market_impact([], qty=1.0)
        assert result["vwap"] == 0.0
        assert result["slippage"] == 0.0
