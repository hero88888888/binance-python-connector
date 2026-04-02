"""Base tick model and shared types used across all schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Side(str, Enum):
    """Order book side."""

    BID = "BID"
    ASK = "ASK"


class Timestamp:
    """Utility for converting Binance millisecond timestamps."""

    @staticmethod
    def from_ms(ms: int) -> datetime:
        """Convert a millisecond Unix timestamp to a timezone-aware datetime."""
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)

    @staticmethod
    def now_ms() -> int:
        """Return the current time as a millisecond Unix timestamp."""
        return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


class BaseTick(BaseModel):
    """Base model for all tick-level data.

    Every tick carries a ``TIMESTAMP`` (millisecond precision, UTC) and an
    optional ``SYMBOL`` identifier.  All field names use UPPERCASE convention
    for consistency across data types.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    TIMESTAMP: int
    SYMBOL: Optional[str] = None

    @property
    def datetime_utc(self) -> datetime:
        """TIMESTAMP as a timezone-aware UTC datetime object."""
        return Timestamp.from_ms(self.TIMESTAMP)
