"""Book imbalance computation — (bid_vol - ask_vol) / (bid_vol + ask_vol).

Imbalance near +1 means the book is heavily bid-weighted (buying pressure),
near -1 means ask-weighted (selling pressure), 0 means balanced.
"""

from __future__ import annotations

from typing import Any


def compute_imbalance(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    levels: int | None = None,
    weighted: bool = False,
) -> float:
    """Compute order book imbalance from bid/ask levels.

    Parameters
    ----------
    bids : list[tuple[float, float]]
        Bid levels as (price, quantity) pairs, best first.
    asks : list[tuple[float, float]]
        Ask levels as (price, quantity) pairs, best first.
    levels : int, optional
        Number of top levels to include. None uses all.
    weighted : bool
        If True, weight by notional (price * qty) instead of raw quantity.

    Returns
    -------
    float
        Imbalance in [-1, +1]. Positive = bid-heavy, negative = ask-heavy.
    """
    b = bids[:levels] if levels else bids
    a = asks[:levels] if levels else asks

    if weighted:
        bid_vol = sum(p * q for p, q in b)
        ask_vol = sum(p * q for p, q in a)
    else:
        bid_vol = sum(q for _, q in b)
        ask_vol = sum(q for _, q in a)

    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return (bid_vol - ask_vol) / total


def imbalance_from_rows(
    rows: list[dict[str, Any]],
    levels: int | None = None,
    weighted: bool = False,
) -> float:
    """Compute imbalance from wide-format orderbook rows.

    Parameters
    ----------
    rows : list[dict]
        Wide-format rows with BID_PRICE, BID_SIZE, ASK_PRICE, ASK_SIZE.
    levels : int, optional
        Top N levels. None uses all.
    weighted : bool
        Notional weighting.

    Returns
    -------
    float
        Imbalance in [-1, +1].
    """
    r = rows[:levels] if levels else rows
    if weighted:
        bid_vol = sum(float(x.get("BID_PRICE", 0)) * float(x.get("BID_SIZE", 0)) for x in r)
        ask_vol = sum(float(x.get("ASK_PRICE", 0)) * float(x.get("ASK_SIZE", 0)) for x in r)
    else:
        bid_vol = sum(float(x.get("BID_SIZE", 0)) for x in r)
        ask_vol = sum(float(x.get("ASK_SIZE", 0)) for x in r)

    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return (bid_vol - ask_vol) / total
