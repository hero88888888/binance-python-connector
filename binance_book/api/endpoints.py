"""Binance REST and WebSocket endpoint URL constants.

All URLs are organized by market type (spot, futures_usdt, futures_coin).
Each endpoint includes its API weight for rate-limiting purposes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    """A Binance REST endpoint with its path and weight."""

    path: str
    weight: int


# ---------------------------------------------------------------------------
# Spot REST endpoints (api.binance.com)
# ---------------------------------------------------------------------------

SPOT_DEPTH = Endpoint("/api/v3/depth", 5)  # weight 5 for limit<=100, 25 for 500, 50 for 5000
SPOT_TRADES = Endpoint("/api/v3/trades", 25)
SPOT_AGG_TRADES = Endpoint("/api/v3/aggTrades", 2)
SPOT_KLINES = Endpoint("/api/v3/klines", 2)
SPOT_TICKER_24HR = Endpoint("/api/v3/ticker/24hr", 2)  # 2 per symbol, 80 for all
SPOT_TICKER_PRICE = Endpoint("/api/v3/ticker/price", 2)
SPOT_TICKER_BOOK = Endpoint("/api/v3/ticker/bookTicker", 2)
SPOT_EXCHANGE_INFO = Endpoint("/api/v3/exchangeInfo", 20)
SPOT_AVG_PRICE = Endpoint("/api/v3/avgPrice", 2)
SPOT_SERVER_TIME = Endpoint("/api/v3/time", 1)
SPOT_PING = Endpoint("/api/v3/ping", 1)

# ---------------------------------------------------------------------------
# USDT-M Futures REST endpoints (fapi.binance.com)
# ---------------------------------------------------------------------------

FUTURES_USDT_DEPTH = Endpoint("/fapi/v1/depth", 5)
FUTURES_USDT_TRADES = Endpoint("/fapi/v1/trades", 5)
FUTURES_USDT_AGG_TRADES = Endpoint("/fapi/v1/aggTrades", 20)
FUTURES_USDT_KLINES = Endpoint("/fapi/v1/klines", 5)
FUTURES_USDT_TICKER_24HR = Endpoint("/fapi/v1/ticker/24hr", 1)
FUTURES_USDT_TICKER_PRICE = Endpoint("/fapi/v2/ticker/price", 1)
FUTURES_USDT_TICKER_BOOK = Endpoint("/fapi/v1/ticker/bookTicker", 1)
FUTURES_USDT_EXCHANGE_INFO = Endpoint("/fapi/v1/exchangeInfo", 1)
FUTURES_USDT_SERVER_TIME = Endpoint("/fapi/v1/time", 1)
FUTURES_USDT_PING = Endpoint("/fapi/v1/ping", 1)

# ---------------------------------------------------------------------------
# COIN-M Futures REST endpoints (dapi.binance.com)
# ---------------------------------------------------------------------------

FUTURES_COIN_DEPTH = Endpoint("/dapi/v1/depth", 5)
FUTURES_COIN_TRADES = Endpoint("/dapi/v1/trades", 5)
FUTURES_COIN_AGG_TRADES = Endpoint("/dapi/v1/aggTrades", 20)
FUTURES_COIN_KLINES = Endpoint("/dapi/v1/klines", 5)
FUTURES_COIN_TICKER_24HR = Endpoint("/dapi/v1/ticker/24hr", 1)
FUTURES_COIN_TICKER_PRICE = Endpoint("/dapi/v1/ticker/price", 1)
FUTURES_COIN_TICKER_BOOK = Endpoint("/dapi/v1/ticker/bookTicker", 1)
FUTURES_COIN_EXCHANGE_INFO = Endpoint("/dapi/v1/exchangeInfo", 1)
FUTURES_COIN_SERVER_TIME = Endpoint("/dapi/v1/time", 1)
FUTURES_COIN_PING = Endpoint("/dapi/v1/ping", 1)


# ---------------------------------------------------------------------------
# Depth weight lookup (varies by limit parameter)
# ---------------------------------------------------------------------------

SPOT_DEPTH_WEIGHTS: dict[int, int] = {
    5: 5,
    10: 5,
    20: 5,
    50: 5,
    100: 5,
    500: 25,
    1000: 50,
    5000: 50,
}

FUTURES_DEPTH_WEIGHTS: dict[int, int] = {
    5: 2,
    10: 2,
    20: 2,
    50: 2,
    100: 5,
    500: 10,
    1000: 20,
}


def depth_weight(limit: int, market: str = "spot") -> int:
    """Return the API weight for a depth request with the given limit."""
    weights = SPOT_DEPTH_WEIGHTS if market == "spot" else FUTURES_DEPTH_WEIGHTS
    for threshold in sorted(weights.keys()):
        if limit <= threshold:
            return weights[threshold]
    return max(weights.values())


# ---------------------------------------------------------------------------
# WebSocket stream name builders
# ---------------------------------------------------------------------------

def ws_depth_stream(symbol: str, speed: int = 100) -> str:
    """Build a diff-depth stream name. Speed is 100 (ms) or 1000 (ms)."""
    s = symbol.lower()
    if speed == 100:
        return f"{s}@depth@100ms"
    return f"{s}@depth"


def ws_partial_depth_stream(symbol: str, levels: int = 5, speed: int = 100) -> str:
    """Build a partial book depth stream name. Levels: 5, 10, or 20."""
    s = symbol.lower()
    suffix = "@100ms" if speed == 100 else ""
    return f"{s}@depth{levels}{suffix}"


def ws_book_ticker_stream(symbol: str) -> str:
    """Build an individual symbol book-ticker stream name."""
    return f"{symbol.lower()}@bookTicker"


def ws_trade_stream(symbol: str) -> str:
    """Build a trade stream name."""
    return f"{symbol.lower()}@trade"


def ws_agg_trade_stream(symbol: str) -> str:
    """Build an aggregate trade stream name."""
    return f"{symbol.lower()}@aggTrade"


def ws_kline_stream(symbol: str, interval: str = "1m") -> str:
    """Build a kline/candlestick stream name."""
    return f"{symbol.lower()}@kline_{interval}"


def ws_ticker_stream(symbol: str) -> str:
    """Build a 24hr ticker stream name."""
    return f"{symbol.lower()}@ticker"


def ws_mini_ticker_stream(symbol: str) -> str:
    """Build a mini-ticker stream name."""
    return f"{symbol.lower()}@miniTicker"


def ws_combined_url(base_url: str, streams: list[str]) -> str:
    """Build a combined stream WebSocket URL (up to 1024 streams per connection)."""
    joined = "/".join(streams)
    return f"{base_url}/stream?streams={joined}"


def ws_single_url(base_url: str, stream: str) -> str:
    """Build a single stream WebSocket URL."""
    return f"{base_url}/ws/{stream}"
