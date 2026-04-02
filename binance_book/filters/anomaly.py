"""Statistical anomaly detection for orderbook levels.

Identifies size outliers (>Nσ from depth-band mean) that may indicate
spoof walls or unusual liquidity concentrations.
"""

from __future__ import annotations

import math
from typing import Any


def filter_anomalies(
    rows: list[dict[str, Any]],
    sigma: float = 3.0,
) -> list[dict[str, Any]]:
    """Remove orderbook levels whose size is a statistical outlier.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows with SIZE (or BID_SIZE/ASK_SIZE) fields.
    sigma : float
        Number of standard deviations above mean to classify as anomaly.
        Default 3.0.

    Returns
    -------
    list[dict]
        Rows with anomalous levels removed.
    """
    if len(rows) < 3:
        return list(rows)

    sizes = _extract_sizes(rows)
    if not sizes:
        return list(rows)

    mean, std = _mean_std(sizes)
    threshold = mean + sigma * std

    result: list[dict[str, Any]] = []
    for row, size in zip(rows, sizes):
        if size <= threshold:
            result.append(row)
    return result


def annotate_anomalies(
    rows: list[dict[str, Any]],
    sigma: float = 3.0,
) -> list[dict[str, Any]]:
    """Add IS_OUTLIER column flagging size anomalies.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows.
    sigma : float
        Outlier threshold in standard deviations.

    Returns
    -------
    list[dict]
        Rows with IS_OUTLIER (bool) column added.
    """
    if len(rows) < 3:
        return [{**r, "IS_OUTLIER": False} for r in rows]

    sizes = _extract_sizes(rows)
    if not sizes:
        return [{**r, "IS_OUTLIER": False} for r in rows]

    mean, std = _mean_std(sizes)
    threshold = mean + sigma * std

    result: list[dict[str, Any]] = []
    for row, size in zip(rows, sizes):
        enriched = {**row}
        enriched["IS_OUTLIER"] = size > threshold
        result.append(enriched)
    return result


def _extract_sizes(rows: list[dict[str, Any]]) -> list[float]:
    """Extract the primary size value from each row."""
    sizes: list[float] = []
    for row in rows:
        if "SIZE" in row:
            sizes.append(float(row["SIZE"]))
        elif "BID_SIZE" in row:
            sizes.append(max(float(row.get("BID_SIZE", 0)), float(row.get("ASK_SIZE", 0))))
        else:
            sizes.append(0.0)
    return sizes


def _mean_std(values: list[float]) -> tuple[float, float]:
    """Compute mean and standard deviation."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance)
