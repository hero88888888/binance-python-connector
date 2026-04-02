"""Book sweep — sweep by price and sweep by quantity (VWAP).

Sweep by price: given a price, how much quantity is available at that price
or better? Sweep by quantity: given a quantity, what VWAP would you get if
you executed immediately against the book?
"""

from __future__ import annotations

from typing import Any


def sweep_by_qty(
    levels: list[tuple[float, float]],
    qty: float,
) -> dict[str, float]:
    """Sweep the book by quantity and compute VWAP.

    Walk through the book levels consuming liquidity until the target
    quantity is filled. Returns the volume-weighted average price.

    Parameters
    ----------
    levels : list[tuple[float, float]]
        Price levels as (price, quantity) pairs, best first.
    qty : float
        Target quantity to fill.

    Returns
    -------
    dict
        ``vwap``: volume-weighted average price.
        ``total_cost``: total cost in quote asset.
        ``filled_qty``: quantity actually filled (may be < qty if book is thin).
        ``levels_consumed``: number of price levels consumed.
    """
    filled = 0.0
    cost = 0.0
    levels_consumed = 0

    for price, available in levels:
        if filled >= qty:
            break
        take = min(available, qty - filled)
        cost += price * take
        filled += take
        levels_consumed += 1

    vwap = cost / filled if filled > 0 else 0.0

    return {
        "vwap": round(vwap, 8),
        "total_cost": round(cost, 8),
        "filled_qty": round(filled, 8),
        "levels_consumed": levels_consumed,
    }


def sweep_by_price(
    levels: list[tuple[float, float]],
    price: float,
    side: str = "BID",
) -> dict[str, float]:
    """Sweep the book by price — total quantity available at a price or better.

    Parameters
    ----------
    levels : list[tuple[float, float]]
        Price levels as (price, quantity) pairs, best first.
    price : float
        Target price threshold.
    side : str
        ``"BID"`` (sum where level price >= target) or
        ``"ASK"`` (sum where level price <= target).

    Returns
    -------
    dict
        ``total_qty``: total quantity available at or better than the price.
        ``total_notional``: total notional value.
        ``levels_consumed``: number of levels within the price range.
    """
    total_qty = 0.0
    total_notional = 0.0
    levels_consumed = 0

    for level_price, level_qty in levels:
        if side.upper() == "BID":
            if level_price < price:
                break
        else:
            if level_price > price:
                break
        total_qty += level_qty
        total_notional += level_price * level_qty
        levels_consumed += 1

    return {
        "total_qty": round(total_qty, 8),
        "total_notional": round(total_notional, 8),
        "levels_consumed": levels_consumed,
    }
