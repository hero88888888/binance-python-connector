"""Configuration for BinanceBook client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class FilterConfig:
    """Configuration for orderbook data cleaning filters.

    Controls which filters are applied when ``clean=True`` is passed to data methods.
    Thresholds are calibrated from live BTCUSDT analysis where 27-49% of top-100
    levels are dust and 75-79% have price gaps > 1 tick.
    """

    remove_dust: bool = True
    dust_notional_usd: float = 5.0
    remove_stale: bool = False
    staleness_ms: int = 5000
    remove_sparse: bool = False
    sparse_max_gap_ticks: int = 50
    flag_anomalies: bool = True
    anomaly_sigma: float = 3.0


@dataclass
class BinanceBookConfig:
    """Top-level configuration for BinanceBook.

    Parameters
    ----------
    api_key : str, optional
        Binance API key. Required only for authenticated endpoints.
    api_secret : str, optional
        Binance API secret.
    testnet : bool
        If True, use Binance testnet endpoints.
    market : str
        Default market type: ``"spot"``, ``"futures_usdt"``, ``"futures_coin"``.
    base_url : str, optional
        Override the REST base URL.
    ws_url : str, optional
        Override the WebSocket base URL.
    timeout : float
        HTTP request timeout in seconds.
    max_book_levels : int
        Maximum number of price levels to store per side in the depth cache.
        Prevents unbounded growth (a common bug where books grow from 1000 to
        4000+ rows over hours).
    model : str, optional
        LLM model name for auto-sizing context-window-aware output.
        Supported: ``"gpt-4o"``, ``"gpt-4o-mini"``, ``"claude-3.5-sonnet"``,
        ``"claude-3-opus"``, ``"gemini-1.5-pro"``, etc.
    context_budget : int, optional
        Total context window tokens available for data output. If ``model`` is
        set, this is auto-detected. Otherwise defaults to 64000.
    reserved_tokens : int
        Tokens reserved for system prompt, conversation, and reasoning.
        Data output budget = context_budget - reserved_tokens.
    filters : FilterConfig
        Default filter configuration for ``clean=True``.
    """

    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    testnet: bool = False
    market: Literal["spot", "futures_usdt", "futures_coin"] = "spot"
    base_url: Optional[str] = None
    ws_url: Optional[str] = None
    timeout: float = 10.0
    max_book_levels: int = 1000
    model: Optional[str] = None
    context_budget: Optional[int] = None
    reserved_tokens: int = 64000
    filters: FilterConfig = field(default_factory=FilterConfig)

    def get_rest_base_url(self) -> str:
        """Return the REST base URL for the configured market."""
        if self.base_url:
            return self.base_url.rstrip("/")
        if self.testnet:
            return _TESTNET_REST[self.market]
        return _PROD_REST[self.market]

    def get_ws_base_url(self) -> str:
        """Return the WebSocket base URL for the configured market."""
        if self.ws_url:
            return self.ws_url.rstrip("/")
        if self.testnet:
            return _TESTNET_WS[self.market]
        return _PROD_WS[self.market]

    def get_data_token_budget(self) -> int:
        """Return the number of tokens available for data output."""
        budget = self.context_budget
        if budget is None:
            budget = MODEL_CONTEXT_WINDOWS.get(self.model or "", 128000)
        return max(0, budget - self.reserved_tokens)


MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-3.5-turbo": 16385,
    "claude-3.5-sonnet": 200000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-4-sonnet": 200000,
    "gemini-1.5-pro": 1000000,
    "gemini-1.5-flash": 1000000,
    "gemini-2.0-flash": 1000000,
    "llama-3.1-70b": 128000,
    "llama-3.1-8b": 128000,
}


_PROD_REST: dict[str, str] = {
    "spot": "https://api.binance.com",
    "futures_usdt": "https://fapi.binance.com",
    "futures_coin": "https://dapi.binance.com",
}

_PROD_WS: dict[str, str] = {
    "spot": "wss://stream.binance.com:9443",
    "futures_usdt": "wss://fstream.binance.com",
    "futures_coin": "wss://dstream.binance.com",
}

_TESTNET_REST: dict[str, str] = {
    "spot": "https://testnet.binance.vision",
    "futures_usdt": "https://testnet.binancefuture.com",
    "futures_coin": "https://testnet.binancefuture.com",
}

_TESTNET_WS: dict[str, str] = {
    "spot": "wss://testnet.binance.vision/ws",
    "futures_usdt": "wss://fstream.binancefuture.com",
    "futures_coin": "wss://dstream.binancefuture.com",
}
