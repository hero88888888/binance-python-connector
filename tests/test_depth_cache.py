"""Tests for depth cache sync protocol logic."""

from __future__ import annotations

from sortedcontainers import SortedDict

from binance_book.book.depth_cache import DepthCache
from binance_book.book.snapshot import (
    ob_snapshot_from_cache,
    ob_snapshot_wide_from_cache,
    ob_snapshot_flat_from_cache,
)
from tests.conftest import MOCK_DEPTH, MOCK_DEPTH_UPDATE_1, MOCK_DEPTH_UPDATE_2


class TestDepthCacheApplyEvent:
    """Test the event application logic without needing WS/REST connections."""

    def _make_cache(self) -> DepthCache:
        """Create a DepthCache and manually initialize its state."""
        cache = DepthCache.__new__(DepthCache)
        cache.symbol = "BTCUSDT"
        cache._market = "spot"
        cache._max_levels = 1000
        cache._bids = SortedDict()
        cache._asks = SortedDict()
        cache._last_update_id = 0
        cache._prev_final_update_id = 0
        cache._synced = False
        cache._update_count = 0
        cache._last_event_time = 0.0
        cache._on_update = None
        return cache

    def _load_snapshot(self, cache: DepthCache) -> None:
        """Load the mock snapshot into the cache."""
        for price_str, qty_str in MOCK_DEPTH["bids"]:
            p, q = float(price_str), float(qty_str)
            if q > 0:
                cache._bids[p] = q
        for price_str, qty_str in MOCK_DEPTH["asks"]:
            p, q = float(price_str), float(qty_str)
            if q > 0:
                cache._asks[p] = q
        cache._last_update_id = MOCK_DEPTH["lastUpdateId"]
        cache._prev_final_update_id = MOCK_DEPTH["lastUpdateId"]
        cache._synced = True

    def test_snapshot_load(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        assert cache.bid_count == 10
        assert cache.ask_count == 10
        assert cache.last_update_id == 91286042658

    def test_get_best_bid(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        bb = cache.get_best_bid()
        assert bb is not None
        assert bb[0] == 68225.0
        assert bb[1] == 1.5

    def test_get_best_ask(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        ba = cache.get_best_ask()
        assert ba is not None
        assert ba[0] == 68225.01
        assert ba[1] == 0.4

    def test_mid_price(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        mid = cache.get_mid_price()
        assert mid is not None
        assert abs(mid - 68225.005) < 0.01

    def test_spread(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        spread = cache.get_spread()
        assert spread is not None
        assert abs(spread - 0.01) < 0.001

    def test_get_bids_with_limit(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        bids = cache.get_bids(limit=3)
        assert len(bids) == 3
        assert bids[0][0] > bids[1][0] > bids[2][0]  # descending

    def test_get_asks_with_limit(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        asks = cache.get_asks(limit=3)
        assert len(asks) == 3
        assert asks[0][0] < asks[1][0] < asks[2][0]  # ascending

    def test_apply_event_updates_qty(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        cache._apply_event(MOCK_DEPTH_UPDATE_1)
        bb = cache.get_best_bid()
        assert bb is not None
        assert bb[1] == 1.6  # updated from 1.5 to 1.6

    def test_apply_event_removes_zero_qty(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        initial_bid_count = cache.bid_count
        cache._apply_event(MOCK_DEPTH_UPDATE_1)
        # The event removes price 68224.0 (qty=0)
        assert cache.bid_count == initial_bid_count - 1
        assert 68224.0 not in cache._bids

    def test_apply_event_adds_new_level(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        cache._apply_event(MOCK_DEPTH_UPDATE_1)
        # The event adds ask at 68233.0
        assert 68233.0 in cache._asks
        assert cache._asks[68233.0] == 0.5

    def test_apply_event_updates_id(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        cache._apply_event(MOCK_DEPTH_UPDATE_1)
        assert cache.last_update_id == 91286042661
        assert cache._prev_final_update_id == 91286042661

    def test_apply_event_removes_ask(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        cache._apply_event(MOCK_DEPTH_UPDATE_1)
        cache._apply_event(MOCK_DEPTH_UPDATE_2)
        # Second event removes ask at 68225.01 (qty=0)
        assert 68225.01 not in cache._asks

    def test_apply_event_increments_count(self):
        cache = self._make_cache()
        self._load_snapshot(cache)
        assert cache.update_count == 0
        cache._apply_event(MOCK_DEPTH_UPDATE_1)
        assert cache.update_count == 1
        cache._apply_event(MOCK_DEPTH_UPDATE_2)
        assert cache.update_count == 2

    def test_trim_book(self):
        cache = self._make_cache()
        cache._max_levels = 5
        self._load_snapshot(cache)
        cache._trim_book()
        assert cache.bid_count <= 5
        assert cache.ask_count <= 5

    def test_empty_cache(self):
        cache = self._make_cache()
        assert cache.get_best_bid() is None
        assert cache.get_best_ask() is None
        assert cache.get_mid_price() is None
        assert cache.get_spread() is None
        assert cache.get_bids() == []
        assert cache.get_asks() == []


class TestSnapshotFromCache:
    def _make_loaded_cache(self) -> DepthCache:
        cache = DepthCache.__new__(DepthCache)
        cache.symbol = "BTCUSDT"
        cache._market = "spot"
        cache._max_levels = 1000
        cache._bids = SortedDict()
        cache._asks = SortedDict()
        cache._last_update_id = 12345
        cache._prev_final_update_id = 12345
        cache._synced = True
        cache._update_count = 0
        cache._last_event_time = 0.0
        cache._on_update = None
        for price_str, qty_str in MOCK_DEPTH["bids"][:5]:
            cache._bids[float(price_str)] = float(qty_str)
        for price_str, qty_str in MOCK_DEPTH["asks"][:5]:
            cache._asks[float(price_str)] = float(qty_str)
        return cache

    def test_ob_snapshot_shape(self):
        cache = self._make_loaded_cache()
        rows = ob_snapshot_from_cache(cache, max_levels=3)
        bids = [r for r in rows if r["SIDE"] == "BID"]
        asks = [r for r in rows if r["SIDE"] == "ASK"]
        assert len(bids) == 3
        assert len(asks) == 3
        assert bids[0]["LEVEL"] == 1
        assert asks[0]["LEVEL"] == 1

    def test_ob_snapshot_wide_shape(self):
        cache = self._make_loaded_cache()
        rows = ob_snapshot_wide_from_cache(cache, max_levels=3)
        assert len(rows) == 3
        assert "BID_PRICE" in rows[0]
        assert "ASK_PRICE" in rows[0]
        assert "LEVEL" in rows[0]
        assert rows[0]["LEVEL"] == 1

    def test_ob_snapshot_flat_shape(self):
        cache = self._make_loaded_cache()
        row = ob_snapshot_flat_from_cache(cache, max_levels=3)
        assert isinstance(row, dict)
        assert "BID_PRICE1" in row
        assert "BID_SIZE1" in row
        assert "ASK_PRICE1" in row
        assert "ASK_SIZE1" in row
        assert "BID_PRICE3" in row
        assert "BID_PRICE4" not in row  # only 3 levels

    def test_snapshot_prices_ordered(self):
        cache = self._make_loaded_cache()
        rows = ob_snapshot_wide_from_cache(cache, max_levels=5)
        for i in range(1, len(rows)):
            assert rows[i]["BID_PRICE"] <= rows[i - 1]["BID_PRICE"]  # bids descend
            assert rows[i]["ASK_PRICE"] >= rows[i - 1]["ASK_PRICE"]  # asks ascend

    def test_snapshot_has_symbol(self):
        cache = self._make_loaded_cache()
        rows = ob_snapshot_wide_from_cache(cache, max_levels=2)
        assert rows[0]["SYMBOL"] == "BTCUSDT"

    def test_snapshot_has_timestamp(self):
        cache = self._make_loaded_cache()
        rows = ob_snapshot_wide_from_cache(cache, max_levels=2)
        assert rows[0]["TIMESTAMP"] > 0
