"""Stale quote filter — detects and removes levels that haven't been updated recently.

During volatile events, feed latency can spike to seconds. Stale levels
misrepresent the current state of the book and degrade analytics quality.
"""

from __future__ import annotations

import time
from typing import Any


def filter_stale(
    rows: list[dict[str, Any]],
    staleness_ms: int = 5000,
    reference_time_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Remove orderbook rows whose TIMESTAMP is older than the staleness threshold.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows with a TIMESTAMP field (ms epoch).
    staleness_ms : int
        Maximum age in milliseconds. Rows older than this are removed.
        Default 5000 (5 seconds).
    reference_time_ms : int, optional
        Reference time for comparison. Defaults to current time.

    Returns
    -------
    list[dict]
        Rows with stale entries removed.
    """
    ref = reference_time_ms or int(time.time() * 1000)
    return [r for r in rows if ref - r.get("TIMESTAMP", ref) <= staleness_ms]


def annotate_stale(
    rows: list[dict[str, Any]],
    staleness_ms: int = 5000,
    reference_time_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Add IS_STALE and STALENESS_MS columns to orderbook rows.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows with a TIMESTAMP field.
    staleness_ms : int
        Threshold for stale classification.
    reference_time_ms : int, optional
        Reference time. Defaults to now.

    Returns
    -------
    list[dict]
        Rows with IS_STALE (bool) and STALENESS_MS (int) added.
    """
    ref = reference_time_ms or int(time.time() * 1000)
    result: list[dict[str, Any]] = []
    for row in rows:
        enriched = {**row}
        age = ref - row.get("TIMESTAMP", ref)
        enriched["STALENESS_MS"] = age
        enriched["IS_STALE"] = age > staleness_ms
        result.append(enriched)
    return result
