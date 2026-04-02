"""Market microstructure analytics — uptick/downtick, market impact estimation."""

from __future__ import annotations

from typing import Any


def classify_ticks(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify trades as uptick, downtick, or zero-tick.

    Parameters
    ----------
    trades : list[dict]
        Trade records with PRICE field, ordered chronologically.

    Returns
    -------
    list[dict]
        Trades with TICK_DIRECTION added: ``"UP"``, ``"DOWN"``, or ``"ZERO"``.
    """
    result: list[dict[str, Any]] = []
    prev_price = None
    for t in trades:
        enriched = {**t}
        price = float(t.get("PRICE", 0))
        if prev_price is None:
            enriched["TICK_DIRECTION"] = "ZERO"
        elif price > prev_price:
            enriched["TICK_DIRECTION"] = "UP"
        elif price < prev_price:
            enriched["TICK_DIRECTION"] = "DOWN"
        else:
            enriched["TICK_DIRECTION"] = "ZERO"
        prev_price = price
        result.append(enriched)
    return result


def estimate_market_impact(
    levels: list[tuple[float, float]],
    qty: float,
) -> dict[str, float]:
    """Estimate the market impact of executing a given quantity.

    Computes the price slippage from the best price to the VWAP of
    filling the target quantity.

    Parameters
    ----------
    levels : list[tuple[float, float]]
        Price levels as (price, quantity) pairs, best first.
    qty : float
        Target quantity to execute.

    Returns
    -------
    dict
        ``best_price``: price at the top of book.
        ``vwap``: volume-weighted average price for the fill.
        ``slippage``: absolute price slippage (vwap - best_price).
        ``slippage_bps``: slippage in basis points.
        ``filled_qty``: quantity actually filled.
    """
    if not levels or qty <= 0:
        return {
            "best_price": 0.0,
            "vwap": 0.0,
            "slippage": 0.0,
            "slippage_bps": 0.0,
            "filled_qty": 0.0,
        }

    best_price = levels[0][0]
    filled = 0.0
    cost = 0.0

    for price, available in levels:
        if filled >= qty:
            break
        take = min(available, qty - filled)
        cost += price * take
        filled += take

    vwap = cost / filled if filled > 0 else best_price
    slippage = abs(vwap - best_price)
    slippage_bps = (slippage / best_price * 10000) if best_price > 0 else 0.0

    return {
        "best_price": round(best_price, 8),
        "vwap": round(vwap, 8),
        "slippage": round(slippage, 8),
        "slippage_bps": round(slippage_bps, 4),
        "filled_qty": round(filled, 8),
    }
