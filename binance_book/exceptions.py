"""Typed exception hierarchy for binance-book."""

from __future__ import annotations


class BinanceBookError(Exception):
    """Base exception for all binance-book errors."""


class BinanceAPIError(BinanceBookError):
    """Raised when the Binance API returns an error response.

    Attributes
    ----------
    status_code : int
        HTTP status code.
    error_code : int
        Binance-specific error code (the ``code`` field in the JSON body).
    message : str
        Human-readable error message from Binance.
    """

    def __init__(self, status_code: int, error_code: int, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"Binance API error {error_code}: {message} (HTTP {status_code})")


class BinanceRateLimitError(BinanceAPIError):
    """Raised when a request is rejected due to rate limiting (HTTP 429 or 418)."""

    def __init__(self, status_code: int, error_code: int, message: str, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(status_code, error_code, message)


class BinanceRequestError(BinanceBookError):
    """Raised when an HTTP request fails at the network level (timeout, DNS, etc.)."""


class WebSocketError(BinanceBookError):
    """Raised when a WebSocket connection encounters an error."""


class WebSocketDisconnected(WebSocketError):
    """Raised when the WebSocket connection is unexpectedly closed."""


class DepthCacheSyncError(BinanceBookError):
    """Raised when the local depth cache detects an update-ID gap and must resnapshot.

    This is an internal signal — the depth cache handles it automatically.
    Users only see this if auto-resnapshot also fails.
    """


class DepthCacheDesyncError(BinanceBookError):
    """Raised when the depth cache cannot recover sync after multiple retries."""


class InvalidSymbolError(BinanceBookError):
    """Raised when a requested symbol does not exist or is not trading."""


class SchemaError(BinanceBookError):
    """Raised when data does not conform to the expected schema."""


class ContextBudgetExceeded(BinanceBookError):
    """Raised when the requested data would exceed the configured context token budget.

    This protects AI agents from receiving data payloads that overflow their
    context window.  Use ``detail="auto"`` to auto-size output.
    """


class DependencyError(BinanceBookError):
    """Raised when an optional dependency is required but not installed.

    For example, ``format="dataframe"`` requires ``pandas``.
    """
