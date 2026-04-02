"""Sparse book gap filter — handles price-level gaps in the orderbook.

From live BTCUSDT analysis: 75-79% of top 100 levels have gaps >1 tick.
Gaps of 28-113 ticks are common even in the top 20 levels. This filter
identifies and optionally removes levels with large gaps from their neighbor.
"""

from __future__ import annotations

from typing import Any


def filter_gap(
    rows: list[dict[str, Any]],
    max_gap_ticks: int = 50,
    tick_size: float = 0.01,
) -> list[dict[str, Any]]:
    """Remove orderbook levels that have a large price gap from the previous level.

    Only works on level-per-side or wide-format rows (with LEVEL and
    PRICE or BID_PRICE/ASK_PRICE fields).

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows sorted by level.
    max_gap_ticks : int
        Maximum allowed gap in tick-size units. Levels with larger gaps are
        removed. Default 50 ticks.
    tick_size : float
        Price tick size for the symbol. Default 0.01 (BTCUSDT).

    Returns
    -------
    list[dict]
        Filtered rows.
    """
    max_gap = max_gap_ticks * tick_size
    result: list[dict[str, Any]] = []

    if not rows:
        return result

    if "SIDE" in rows[0]:
        bids = [r for r in rows if str(r.get("SIDE", "")).replace("Side.", "") == "BID"]
        asks = [r for r in rows if str(r.get("SIDE", "")).replace("Side.", "") == "ASK"]
        result.extend(_filter_side(bids, "PRICE", max_gap, descending=True))
        result.extend(_filter_side(asks, "PRICE", max_gap, descending=False))
    elif "BID_PRICE" in rows[0]:
        result = _filter_wide(rows, max_gap)
    else:
        result = list(rows)

    return result


def annotate_gaps(
    rows: list[dict[str, Any]],
    tick_size: float = 0.01,
) -> list[dict[str, Any]]:
    """Add GAP_TICKS column showing the price gap from the previous level.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows.
    tick_size : float
        Price tick size.

    Returns
    -------
    list[dict]
        Rows with GAP_TICKS (int) column added.
    """
    result: list[dict[str, Any]] = []

    if not rows:
        return result

    if "SIDE" in rows[0]:
        bids = [r for r in rows if str(r.get("SIDE", "")).replace("Side.", "") == "BID"]
        asks = [r for r in rows if str(r.get("SIDE", "")).replace("Side.", "") == "ASK"]
        result.extend(_annotate_side(bids, "PRICE", tick_size, descending=True))
        result.extend(_annotate_side(asks, "PRICE", tick_size, descending=False))
    elif "BID_PRICE" in rows[0]:
        prev_bid = None
        prev_ask = None
        for row in rows:
            enriched = {**row}
            bp = float(row.get("BID_PRICE", 0))
            ap = float(row.get("ASK_PRICE", 0))
            bid_gap = abs(prev_bid - bp) / tick_size if prev_bid is not None else 0
            ask_gap = abs(ap - prev_ask) / tick_size if prev_ask is not None else 0
            enriched["BID_GAP_TICKS"] = round(bid_gap)
            enriched["ASK_GAP_TICKS"] = round(ask_gap)
            prev_bid = bp
            prev_ask = ap
            result.append(enriched)
    else:
        result = [{**r, "GAP_TICKS": 0} for r in rows]

    return result


def _filter_side(
    levels: list[dict[str, Any]],
    price_key: str,
    max_gap: float,
    descending: bool,
) -> list[dict[str, Any]]:
    """Filter levels on one side by max price gap."""
    result: list[dict[str, Any]] = []
    prev_price = None
    for row in levels:
        price = float(row.get(price_key, 0))
        if prev_price is not None:
            gap = abs(prev_price - price)
            if gap > max_gap:
                continue
        result.append(row)
        prev_price = price
    return result


def _filter_wide(rows: list[dict[str, Any]], max_gap: float) -> list[dict[str, Any]]:
    """Filter wide-format rows by max gap on either side."""
    result: list[dict[str, Any]] = []
    prev_bid = None
    prev_ask = None
    for row in rows:
        bp = float(row.get("BID_PRICE", 0))
        ap = float(row.get("ASK_PRICE", 0))
        if prev_bid is not None:
            if abs(prev_bid - bp) > max_gap or abs(ap - prev_ask) > max_gap:
                continue
        result.append(row)
        prev_bid = bp
        prev_ask = ap
    return result


def _annotate_side(
    levels: list[dict[str, Any]],
    price_key: str,
    tick_size: float,
    descending: bool,
) -> list[dict[str, Any]]:
    """Add GAP_TICKS to levels on one side."""
    result: list[dict[str, Any]] = []
    prev_price = None
    for row in levels:
        enriched = {**row}
        price = float(row.get(price_key, 0))
        if prev_price is not None:
            enriched["GAP_TICKS"] = round(abs(prev_price - price) / tick_size)
        else:
            enriched["GAP_TICKS"] = 0
        prev_price = price
        result.append(enriched)
    return result
