"""Interval VWAP computation from trade data."""

from __future__ import annotations

from typing import Any


def compute_vwap(trades: list[dict[str, Any]]) -> dict[str, float]:
    """Compute volume-weighted average price from a list of trades.

    Parameters
    ----------
    trades : list[dict]
        Trade records with PRICE and SIZE fields.

    Returns
    -------
    dict
        ``vwap``: volume-weighted average price.
        ``total_volume``: total traded volume.
        ``total_notional``: total notional traded.
        ``trade_count``: number of trades.
    """
    total_notional = 0.0
    total_volume = 0.0

    for t in trades:
        price = float(t.get("PRICE", 0))
        size = float(t.get("SIZE", 0))
        total_notional += price * size
        total_volume += size

    vwap = total_notional / total_volume if total_volume > 0 else 0.0

    return {
        "vwap": round(vwap, 8),
        "total_volume": round(total_volume, 8),
        "total_notional": round(total_notional, 2),
        "trade_count": len(trades),
    }
