"""Three orderbook snapshot representations from a DepthCache.

Converts the live depth cache state into structured formats:
- Levels: one row per level per side
- Wide: one row per level, both sides paired
- Flat: single row with all levels flattened
"""

from __future__ import annotations

from typing import Any, Optional

from binance_book.book.depth_cache import DepthCache
from binance_book.schemas.base import Timestamp


def ob_snapshot_from_cache(
    cache: DepthCache,
    max_levels: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Generate level-per-side rows from a live DepthCache.

    One row per level per side. Fields: TIMESTAMP, SYMBOL, SIDE, PRICE,
    SIZE, LEVEL, UPDATE_ID.

    Parameters
    ----------
    cache : DepthCache
        A synchronized depth cache instance.
    max_levels : int, optional
        Max levels per side. None returns all.

    Returns
    -------
    list[dict]
        Rows ordered by side (BID first) then level.
    """
    ts = Timestamp.now_ms()
    uid = cache.last_update_id
    rows: list[dict[str, Any]] = []

    for i, (price, qty) in enumerate(cache.get_bids(max_levels)):
        rows.append({
            "TIMESTAMP": ts,
            "SYMBOL": cache.symbol,
            "SIDE": "BID",
            "PRICE": price,
            "SIZE": qty,
            "LEVEL": i + 1,
            "UPDATE_ID": uid,
        })

    for i, (price, qty) in enumerate(cache.get_asks(max_levels)):
        rows.append({
            "TIMESTAMP": ts,
            "SYMBOL": cache.symbol,
            "SIDE": "ASK",
            "PRICE": price,
            "SIZE": qty,
            "LEVEL": i + 1,
            "UPDATE_ID": uid,
        })

    return rows


def ob_snapshot_wide_from_cache(
    cache: DepthCache,
    max_levels: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Generate wide-format rows from a live DepthCache.

    One row per level with both bid and ask paired. Fields: TIMESTAMP,
    SYMBOL, LEVEL, BID_PRICE, BID_SIZE, ASK_PRICE, ASK_SIZE.

    Parameters
    ----------
    cache : DepthCache
        A synchronized depth cache instance.
    max_levels : int, optional
        Max levels. None returns all.

    Returns
    -------
    list[dict]
        Wide-format rows ordered by level.
    """
    ts = Timestamp.now_ms()
    bids = cache.get_bids(max_levels)
    asks = cache.get_asks(max_levels)
    n = min(len(bids), len(asks))
    if max_levels:
        n = min(n, max_levels)

    rows: list[dict[str, Any]] = []
    for i in range(n):
        rows.append({
            "TIMESTAMP": ts,
            "SYMBOL": cache.symbol,
            "LEVEL": i + 1,
            "BID_PRICE": bids[i][0],
            "BID_SIZE": bids[i][1],
            "ASK_PRICE": asks[i][0],
            "ASK_SIZE": asks[i][1],
        })

    return rows


def ob_snapshot_flat_from_cache(
    cache: DepthCache,
    max_levels: Optional[int] = None,
) -> dict[str, Any]:
    """Generate a flat single-row dict from a live DepthCache.

    All levels flattened into one row: BID_PRICE1, BID_SIZE1, ASK_PRICE1,
    ASK_SIZE1, BID_PRICE2, ...

    Parameters
    ----------
    cache : DepthCache
        A synchronized depth cache instance.
    max_levels : int, optional
        Max levels. None returns all.

    Returns
    -------
    dict
        Single flat row with all levels.
    """
    ts = Timestamp.now_ms()
    bids = cache.get_bids(max_levels)
    asks = cache.get_asks(max_levels)
    n = min(len(bids), len(asks))
    if max_levels:
        n = min(n, max_levels)

    row: dict[str, Any] = {"TIMESTAMP": ts, "SYMBOL": cache.symbol}
    for i in range(n):
        lvl = i + 1
        row[f"BID_PRICE{lvl}"] = bids[i][0]
        row[f"BID_SIZE{lvl}"] = bids[i][1]
        row[f"ASK_PRICE{lvl}"] = asks[i][0]
        row[f"ASK_SIZE{lvl}"] = asks[i][1]

    return row
