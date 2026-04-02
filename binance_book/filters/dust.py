"""Dust order filter — removes economically meaningless price levels.

From live BTCUSDT analysis: 27% of top 100 levels have size <0.0001 BTC
(~$6.6 notional), and 49% have <0.001 BTC (~$66). These dust orders add
noise without representing genuine liquidity.
"""

from __future__ import annotations

from typing import Any


def filter_dust(
    rows: list[dict[str, Any]],
    min_notional_usd: float = 5.0,
    mid_price: float | None = None,
) -> list[dict[str, Any]]:
    """Remove orderbook levels below a minimum notional value.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows with PRICE and SIZE fields (any representation).
    min_notional_usd : float
        Minimum notional value in USD to keep. Default $5 (Binance's own
        minimum order notional).
    mid_price : float, optional
        Current mid price for estimating notional on levels that only have
        SIZE (e.g. level-per-side format). If None, uses the level's PRICE.

    Returns
    -------
    list[dict]
        Filtered rows with dust levels removed.
    """
    result: list[dict[str, Any]] = []
    for row in rows:
        if _is_dust(row, min_notional_usd, mid_price):
            continue
        result.append(row)
    return result


def annotate_dust(
    rows: list[dict[str, Any]],
    min_notional_usd: float = 5.0,
    mid_price: float | None = None,
) -> list[dict[str, Any]]:
    """Add IS_DUST and NOTIONAL_USD columns to orderbook rows.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows.
    min_notional_usd : float
        Threshold for dust classification.
    mid_price : float, optional
        Current mid price.

    Returns
    -------
    list[dict]
        Rows with IS_DUST (bool) and NOTIONAL_USD (float) added.
    """
    result: list[dict[str, Any]] = []
    for row in rows:
        enriched = {**row}
        notional = _compute_notional(row, mid_price)
        enriched["NOTIONAL_USD"] = round(notional, 2)
        enriched["IS_DUST"] = notional < min_notional_usd
        result.append(enriched)
    return result


def _is_dust(row: dict[str, Any], threshold: float, mid_price: float | None) -> bool:
    """Check if a row is dust based on notional value."""
    return _compute_notional(row, mid_price) < threshold


def _compute_notional(row: dict[str, Any], mid_price: float | None) -> float:
    """Compute the notional value of a row."""
    if "PRICE" in row and "SIZE" in row:
        return float(row["PRICE"]) * float(row["SIZE"])

    if "BID_PRICE" in row and "BID_SIZE" in row:
        bid_notional = float(row["BID_PRICE"]) * float(row["BID_SIZE"])
        ask_notional = float(row.get("ASK_PRICE", 0)) * float(row.get("ASK_SIZE", 0))
        return min(bid_notional, ask_notional) if ask_notional > 0 else bid_notional

    for i in range(1, 100):
        bp = row.get(f"BID_PRICE{i}")
        bs = row.get(f"BID_SIZE{i}")
        if bp is not None and bs is not None:
            return float(bp) * float(bs)

    return 0.0
