"""Spread analytics — quoted, effective, and notional spread computation."""

from __future__ import annotations

from typing import Any


def compute_spread(
    best_bid: float,
    best_ask: float,
    best_bid_size: float = 0.0,
    best_ask_size: float = 0.0,
) -> dict[str, float]:
    """Compute spread metrics from best bid/ask.

    Parameters
    ----------
    best_bid : float
        Best bid price.
    best_ask : float
        Best ask price.
    best_bid_size : float
        Size at best bid (for notional spread).
    best_ask_size : float
        Size at best ask (for notional spread).

    Returns
    -------
    dict
        ``quoted``: absolute spread (ask - bid).
        ``quoted_bps``: spread in basis points relative to mid.
        ``mid``: mid price.
        ``notional_bid``: notional at best bid (price * size).
        ``notional_ask``: notional at best ask (price * size).
    """
    spread = best_ask - best_bid
    mid = (best_ask + best_bid) / 2.0 if (best_ask + best_bid) > 0 else 0.0
    spread_bps = (spread / mid * 10000) if mid > 0 else 0.0

    return {
        "quoted": round(spread, 8),
        "quoted_bps": round(spread_bps, 4),
        "mid": round(mid, 8),
        "notional_bid": round(best_bid * best_bid_size, 2),
        "notional_ask": round(best_ask * best_ask_size, 2),
    }


def spread_from_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Compute spread from wide-format orderbook rows (uses first row = top of book).

    Parameters
    ----------
    rows : list[dict]
        Wide-format rows with BID_PRICE, BID_SIZE, ASK_PRICE, ASK_SIZE.

    Returns
    -------
    dict
        Spread metrics.
    """
    if not rows:
        return {"quoted": 0, "quoted_bps": 0, "mid": 0, "notional_bid": 0, "notional_ask": 0}

    top = rows[0]
    return compute_spread(
        best_bid=float(top.get("BID_PRICE", 0)),
        best_ask=float(top.get("ASK_PRICE", 0)),
        best_bid_size=float(top.get("BID_SIZE", 0)),
        best_ask_size=float(top.get("ASK_SIZE", 0)),
    )
