# API Reference

Complete reference for every public method on `BinanceBook`.

---

## Schema Introspection

### `book.schema(data_type)`

Return the field definitions for a given data type.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `data_type` | str | Yes | Data type name. One of: `"trade"`, `"quote"`, `"bbo"`, `"level"`, `"bar"`, `"ticker"`, `"info"`. |

**Returns:** `dict[str, str]` — Mapping of field name to type string.

```python
book.schema("trade")
# {'TIMESTAMP': 'int', 'SYMBOL': 'str', 'PRICE': 'float', 
#  'SIZE': 'float', 'TRADE_ID': 'int', 'IS_BUYER_MAKER': 'bool'}

book.schema("level")
# {'TIMESTAMP': 'int', 'SYMBOL': 'str', 'SIDE': 'str',
#  'PRICE': 'float', 'SIZE': 'float', 'LEVEL': 'int', 'UPDATE_ID': 'int'}

book.schema("bar")
# {'TIMESTAMP': 'int', 'SYMBOL': 'str', 'OPEN': 'float', 'HIGH': 'float',
#  'LOW': 'float', 'CLOSE': 'float', 'VOLUME': 'float', ...}
```

### Data Types

| Data Type | Description | Binance Source |
|---|---|---|
| `"trade"` | Individual trade events | `/api/v3/trades`, `@trade` stream |
| `"quote"` | Best bid/offer quote | `@bookTicker` stream |
| `"bbo"` | Best bid/offer (alias for quote) | `@bookTicker` stream |
| `"level"` | Order book price level | `/api/v3/depth`, `@depth` stream |
| `"bar"` | OHLCV candlestick bar | `/api/v3/klines`, `@kline` stream |
| `"ticker"` | 24-hour rolling statistics | `/api/v3/ticker/24hr` |
| `"info"` | Symbol reference data | `/api/v3/exchangeInfo` |

---

## Symbol Discovery

### `book.symbols(market, quote, status, min_volume_24h)`

Get trading pair symbols with optional filtering.

**Parameters:**

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `market` | str | No | Client default | `"spot"`, `"futures_usdt"`, or `"futures_coin"` |
| `quote` | str | No | None | Filter by quote asset (e.g. `"USDT"`) |
| `status` | str | No | `"TRADING"` | Filter by trading status |
| `min_volume_24h` | float | No | None | Minimum 24h quote volume in USD |

**Returns:** `list[SymbolInfo]` — List of symbol metadata objects.

```python
# All spot symbols
symbols = book.symbols()

# Only USDT pairs
symbols = book.symbols(quote="USDT")

# High-volume USDT futures
symbols = book.symbols(market="futures_usdt", quote="USDT", min_volume_24h=1_000_000)

# Access fields
for s in symbols[:3]:
    print(f"{s.SYMBOL}: tick={s.TICK_SIZE}, lot={s.LOT_SIZE}, min_notional={s.MIN_NOTIONAL}")
```

**SymbolInfo fields:**

| Field | Type | Description |
|---|---|---|
| `SYMBOL` | str | Trading pair (e.g. `"BTCUSDT"`) |
| `BASE_ASSET` | str | Base asset (e.g. `"BTC"`) |
| `QUOTE_ASSET` | str | Quote asset (e.g. `"USDT"`) |
| `STATUS` | str | Trading status (e.g. `"TRADING"`) |
| `TICK_SIZE` | float | Minimum price movement |
| `LOT_SIZE` | float | Minimum quantity step |
| `MIN_NOTIONAL` | float | Minimum order value in quote asset |
| `MIN_QTY` | float | Minimum order quantity |
| `MAX_QTY` | float | Maximum order quantity |
| `BASE_PRECISION` | int | Decimal places for base asset |
| `QUOTE_PRECISION` | int | Decimal places for quote asset |

---

## Orderbook Snapshots

binance-book provides three orderbook representations. All three accept the same core parameters.

### Common Parameters

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str or list[str] | Yes | — | Trading pair(s). Pass a list for multi-symbol. |
| `max_levels` | int | No | 10 | Maximum depth levels per side. |
| `market` | str | No | Client default | Override market type. |
| `detail` | str | No | `"standard"` | Output detail level (see [Output Control](#output-control)). |
| `format` | str | No | `"json"` | Output format (see [Output Formats](#output-formats)). |
| `clean` | bool or list | No | False | Apply data cleaning filters (see [Data Cleaning](#data-cleaning)). |
| `annotate` | bool | No | False | Add quality columns (IS_DUST, NOTIONAL_USD, etc.). |

### `book.ob_snapshot(symbol, ...)`

One row per level per side. Best for: programmatic processing, filtering by side.

```python
ob = book.ob_snapshot("BTCUSDT", max_levels=3)
# [
#   {'TIMESTAMP': 1711929600000, 'SYMBOL': 'BTCUSDT', 'SIDE': 'BID', 
#    'PRICE': 68225.0, 'SIZE': 1.5, 'LEVEL': 1, 'UPDATE_ID': 91286042658},
#   {'TIMESTAMP': 1711929600000, 'SYMBOL': 'BTCUSDT', 'SIDE': 'BID',
#    'PRICE': 68224.99, 'SIZE': 0.3, 'LEVEL': 2, 'UPDATE_ID': 91286042658},
#   {'TIMESTAMP': 1711929600000, 'SYMBOL': 'BTCUSDT', 'SIDE': 'BID',
#    'PRICE': 68224.5, 'SIZE': 0.8, 'LEVEL': 3, 'UPDATE_ID': 91286042658},
#   {'TIMESTAMP': 1711929600000, 'SYMBOL': 'BTCUSDT', 'SIDE': 'ASK',
#    'PRICE': 68225.01, 'SIZE': 0.4, 'LEVEL': 1, 'UPDATE_ID': 91286042658},
#   ...
# ]
```

**Returns:** `list[dict]` — 2 × max_levels rows (bids + asks).

### `book.ob_snapshot_wide(symbol, ...)`

One row per level, both sides paired. Best for: seeing the spread at each level, analytics.

```python
ob = book.ob_snapshot_wide("BTCUSDT", max_levels=3)
# [
#   {'TIMESTAMP': ..., 'SYMBOL': 'BTCUSDT', 'LEVEL': 1,
#    'BID_PRICE': 68225.0, 'BID_SIZE': 1.5, 'ASK_PRICE': 68225.01, 'ASK_SIZE': 0.4},
#   {'TIMESTAMP': ..., 'SYMBOL': 'BTCUSDT', 'LEVEL': 2,
#    'BID_PRICE': 68224.99, 'BID_SIZE': 0.3, 'ASK_PRICE': 68225.5, 'ASK_SIZE': 0.2},
#   ...
# ]
```

**Returns:** `list[dict]` — max_levels rows.

### `book.ob_snapshot_flat(symbol, ...)`

Single row, all levels flattened. Best for: ML features, compact storage, minimal tokens.

```python
ob = book.ob_snapshot_flat("BTCUSDT", max_levels=3)
# {'TIMESTAMP': ..., 'SYMBOL': 'BTCUSDT',
#  'BID_PRICE1': 68225.0, 'BID_SIZE1': 1.5, 'ASK_PRICE1': 68225.01, 'ASK_SIZE1': 0.4,
#  'BID_PRICE2': 68224.99, 'BID_SIZE2': 0.3, 'ASK_PRICE2': 68225.5, 'ASK_SIZE2': 0.2,
#  'BID_PRICE3': 68224.5, 'BID_SIZE3': 0.8, 'ASK_PRICE3': 68226.0, 'ASK_SIZE3': 0.1}
```

**Returns:** `dict` — Single row with `BID_PRICE1..N`, `BID_SIZE1..N`, `ASK_PRICE1..N`, `ASK_SIZE1..N`.

### Multi-Symbol Queries

Pass a list of symbols to get data for multiple pairs in one call:

```python
result = book.ob_snapshot_wide(["BTCUSDT", "ETHUSDT", "SOLUSDT"], max_levels=5)
# {'BTCUSDT': [...], 'ETHUSDT': [...], 'SOLUSDT': [...]}

for symbol, levels in result.items():
    print(f"{symbol}: bid={levels[0]['BID_PRICE']}, ask={levels[0]['ASK_PRICE']}")
```

---

## Trades

### `book.trades(symbol, limit, market, format)`

Get recent trades for a symbol.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair symbol |
| `limit` | int | No | 100 | Number of trades (max 1000) |
| `market` | str | No | Client default | Override market type |
| `format` | str | No | `"json"` | Output format |

```python
trades = book.trades("BTCUSDT", limit=5)
# [{'TIMESTAMP': 1711929600000, 'SYMBOL': 'BTCUSDT', 'PRICE': 68225.0,
#   'SIZE': 0.5, 'TRADE_ID': 6167847072, 'IS_BUYER_MAKER': False}, ...]
```

---

## Klines (OHLCV Bars)

### `book.klines(symbol, interval, limit, market, format)`

Get OHLCV candlestick bars.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair symbol |
| `interval` | str | No | `"1m"` | Bar interval: `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"4h"`, `"1d"`, etc. |
| `limit` | int | No | 100 | Number of bars (max 1000) |
| `market` | str | No | Client default | Override market type |
| `format` | str | No | `"json"` | Output format |

```python
bars = book.klines("BTCUSDT", interval="1h", limit=3)
# [{'TIMESTAMP': ..., 'SYMBOL': 'BTCUSDT', 'OPEN': 68100.0, 'HIGH': 68300.0,
#   'LOW': 68050.0, 'CLOSE': 68225.0, 'VOLUME': 1234.5, 'CLOSE_TIME': ...,
#   'QUOTE_VOLUME': 84200000.0, 'TRADE_COUNT': 45000, ...}, ...]
```

---

## Quotes (Best Bid/Offer)

### `book.quote(symbol, market)`

Get the current best bid/offer for a symbol.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair symbol |
| `market` | str | No | Client default | Override market type |

```python
q = book.quote("BTCUSDT")
# {'TIMESTAMP': ..., 'SYMBOL': 'BTCUSDT',
#  'BID_PRICE': 68225.0, 'BID_SIZE': 1.5,
#  'ASK_PRICE': 68225.01, 'ASK_SIZE': 0.4,
#  'UPDATE_ID': 91286042658,
#  'SPREAD': 0.01, 'MID_PRICE': 68225.005, 'SPREAD_BPS': 0.0015}
```

---

## 24-Hour Ticker

### `book.ticker_24hr(symbol, market, format)`

Get 24-hour rolling window statistics.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | No | None | Symbol. If None, returns all tickers. |
| `market` | str | No | Client default | Override market type |
| `format` | str | No | `"json"` | Output format |

```python
# Single symbol
t = book.ticker_24hr("BTCUSDT")
# {'TIMESTAMP': ..., 'SYMBOL': 'BTCUSDT', 'OPEN': 67500.0, 'HIGH': 69000.0,
#  'LOW': 67200.0, 'CLOSE': 68225.0, 'VOLUME': 25000.0, 
#  'QUOTE_VOLUME': 1700000000.0, 'PRICE_CHANGE': 725.0,
#  'PRICE_CHANGE_PERCENT': 1.07, 'TRADE_COUNT': 1200000}

# All tickers
all_tickers = book.ticker_24hr(format="json")
```

---

## Analytics

### `book.imbalance(symbol, levels, weighted, market)`

Compute order book imbalance. Returns a value in [-1, +1]: positive = bid-heavy (buying pressure), negative = ask-heavy (selling pressure).

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair |
| `levels` | int | No | 5 | Number of top levels to include |
| `weighted` | bool | No | False | If True, weight by notional (price × qty) |
| `market` | str | No | Client default | Override market type |

```python
imb = book.imbalance("BTCUSDT", levels=5)
# -0.55  (ask-heavy, selling pressure)

imb = book.imbalance("BTCUSDT", levels=10, weighted=True)
# -0.72  (notional-weighted)
```

### `book.sweep_by_qty(symbol, side, qty, market)`

Sweep the book by quantity — compute the VWAP if you executed a given quantity immediately against the book.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair |
| `side` | str | No | `"ASK"` | `"ASK"` to simulate a buy, `"BID"` to simulate a sell |
| `qty` | float | No | 1.0 | Target quantity in base asset units |
| `market` | str | No | Client default | Override market type |

```python
sweep = book.sweep_by_qty("BTCUSDT", side="ASK", qty=10.0)
# {'vwap': 68226.5, 'total_cost': 682265.0, 'filled_qty': 10.0, 'levels_consumed': 8}
```

### `book.sweep_by_price(symbol, side, price, market)`

Sweep the book by price — total quantity available at a price or better.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair |
| `side` | str | No | `"BID"` | `"BID"` (levels ≥ price) or `"ASK"` (levels ≤ price) |
| `price` | float | No | 0.0 | Target price threshold |
| `market` | str | No | Client default | Override market type |

```python
sp = book.sweep_by_price("BTCUSDT", side="BID", price=68000.0)
# {'total_qty': 128.7, 'total_notional': 8775615.99, 'levels_consumed': 1000}
```

### `book.spread(symbol, market)`

Compute spread metrics.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair |
| `market` | str | No | Client default | Override market type |

```python
sp = book.spread("BTCUSDT")
# {'quoted': 0.01, 'quoted_bps': 0.0015, 'mid': 68225.005,
#  'notional_bid': 102337.5, 'notional_ask': 27290.0}
```

---

## Streaming (Async)

### `book.ob_stream(symbol, max_levels, market, format, speed)`

Async iterator that yields live orderbook snapshots on every update. Uses Binance partial-depth streams.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | str | Yes | — | Trading pair |
| `max_levels` | int | No | 10 | Levels: 5, 10, or 20 |
| `market` | str | No | Client default | Override market type |
| `format` | str | No | `"wide"` | `"snapshot"`, `"wide"`, or `"flat"` |
| `speed` | int | No | 100 | Update speed in ms: 100 or 1000 |

```python
import asyncio
from binance_book import BinanceBook

async def main():
    book = BinanceBook()
    async for update in book.ob_stream("BTCUSDT", max_levels=5, format="flat"):
        print(f"bid1={update['BID_PRICE1']} ask1={update['ASK_PRICE1']}")
    await book.close()

asyncio.run(main())
```

### `book.trade_stream(symbol, market)`

Async iterator that yields live trade events.

```python
async for trade in book.trade_stream("BTCUSDT"):
    print(f"price={trade['PRICE']} size={trade['SIZE']}")
```

---

## Output Control

### Output Formats

Every data method accepts a `format` parameter:

| Format | Type Returned | Description | Best For |
|---|---|---|---|
| `"json"` | dict or list[dict] | Structured Python dicts | Default, programmatic use |
| `"csv"` | str | Comma-separated values | Compact text output |
| `"markdown"` | str | Markdown table | Chat display, documentation |
| `"narrative"` | str | Natural language summary | LLM consumption |
| `"dataframe"` | pandas DataFrame | Tabular data | Data analysis (requires pandas) |

```python
# Markdown table
print(book.ob_snapshot_wide("BTCUSDT", max_levels=3, format="markdown"))
# | TIMESTAMP | SYMBOL | LEVEL | BID_PRICE | BID_SIZE | ASK_PRICE | ASK_SIZE |
# | --- | --- | --- | --- | --- | --- | --- |
# | 1711929600000 | BTCUSDT | 1 | 68225.0 | 1.5 | 68225.01 | 0.4 |
# ...

# Natural language (great for LLMs)
print(book.ob_snapshot_wide("BTCUSDT", max_levels=5, format="narrative"))
# "BTCUSDT orderbook (5 levels): bid $68,225.00 (1.5000) / ask $68,225.01 (0.4000),
#  spread $0.01 (0.00 bps), mid $68,225.01, bid depth 3.1000 ($211,498) /
#  ask depth 1.2000 ($81,870), imbalance +0.441"

# pandas DataFrame
df = book.ob_snapshot_wide("BTCUSDT", max_levels=10, format="dataframe")
# Standard pandas operations work:
# df.describe(), df.plot(), df.to_csv(), etc.
```

### Detail Levels

The `detail` parameter controls how much data is returned. This is critical for AI agents to avoid overflowing their context window.

| Detail | Content | ~Tokens/Symbol | Use Case |
|---|---|---|---|
| `"minimal"` | BBO + spread + imbalance | ~34 | Screening 500+ symbols |
| `"summary"` | + top 5 levels + depth stats | ~136 | Multi-symbol analysis |
| `"standard"` | 10 levels wide format | ~500 | Default single-symbol |
| `"detailed"` | 50 levels wide format | ~2,500 | Deep analysis |
| `"full"` | All available levels | ~5,000-100,000 | Programmatic only |
| `"auto"` | Auto-picks based on context budget | varies | **Recommended for agents** |

---

## Data Cleaning

### Using `clean` Parameter

```python
# Apply all default filters
ob = book.ob_snapshot("BTCUSDT", max_levels=20, clean=True)

# Apply specific filters only
ob = book.ob_snapshot("BTCUSDT", max_levels=20, clean=["dust"])
ob = book.ob_snapshot("BTCUSDT", max_levels=20, clean=["dust", "stale"])
```

### Using `annotate` Parameter

Instead of removing rows, add quality columns:

```python
ob = book.ob_snapshot("BTCUSDT", max_levels=10, annotate=True)
# Each row now has:
#   IS_DUST: bool       — True if notional < $5
#   NOTIONAL_USD: float  — price × size
#   GAP_TICKS: int       — price gap from previous level in ticks
#   IS_OUTLIER: bool     — True if size is >3σ outlier
#   IS_STALE: bool       — True if timestamp is old
#   STALENESS_MS: int    — milliseconds since update
```

### Available Filters

| Filter | What It Does | Why |
|---|---|---|
| `"dust"` | Removes levels with notional < $5 | 27-49% of book levels are economically meaningless |
| `"stale"` | Removes levels older than staleness threshold | Feed latency can spike during volatile events |
| `"gap"` | Removes levels with large price gaps | 75-79% of levels have gaps > 1 tick |
| `"anomaly"` | Removes size outliers (> 3σ) | Detects potential spoof walls |

---

## Agentic AI Tools

### `book.tools(format)`

Export all public methods as AI-agent tool definitions.

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `format` | str | No | `"openai"` | `"openai"`, `"anthropic"`, or `"raw"` |

```python
# OpenAI function-calling format
tools = book.tools(format="openai")
# [
#   {
#     "type": "function",
#     "function": {
#       "name": "ob_snapshot_wide",
#       "description": "Get orderbook snapshot with one row per level, both sides.",
#       "parameters": {
#         "type": "object",
#         "properties": {
#           "symbol": {"type": "string", "description": "Trading pair symbol(s)."},
#           "max_levels": {"type": "integer", "description": "Maximum depth levels.", "default": 10}
#         },
#         "required": ["symbol"]
#       }
#     }
#   },
#   ...
# ]

# Anthropic tool_use format
tools = book.tools(format="anthropic")
# [{"name": "ob_snapshot_wide", "description": "...", "input_schema": {...}}, ...]

# Pass directly to OpenAI
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's the BTCUSDT orderbook like?"}],
    tools=book.tools(format="openai"),
)
```

### `book.execute(tool_name, arguments)`

Dispatch an AI-agent tool call by name.

```python
# After receiving a tool_call from the LLM:
result = book.execute("ob_snapshot_wide", {"symbol": "BTCUSDT", "max_levels": 5})
result = book.execute("imbalance", {"symbol": "BTCUSDT", "levels": 10})
result = book.execute("spread", {"symbol": "ETHUSDT"})
```

### `book.serve_mcp(host, port)`

Start an MCP (Model Context Protocol) server. Any MCP-compatible agent can discover and call tools over HTTP.

```python
book.serve_mcp(port=8080)
# Server runs at http://localhost:8080/mcp
# POST /mcp with JSON-RPC: {"method": "tools/list"} or {"method": "tools/call", ...}
# GET /health for status check
```

---

## Error Handling

All errors inherit from `BinanceBookError`:

```python
from binance_book.exceptions import (
    BinanceBookError,      # Base exception
    BinanceAPIError,       # Binance returned an error (status, code, message)
    BinanceRateLimitError, # HTTP 429/418 rate limit (includes retry_after)
    BinanceRequestError,   # Network-level failure (timeout, DNS, etc.)
    InvalidSymbolError,    # Symbol doesn't exist
    DependencyError,       # Optional dep not installed (e.g. pandas)
)

try:
    ob = book.ob_snapshot("INVALIDPAIR")
except BinanceAPIError as e:
    print(f"Error {e.error_code}: {e.message}")
except BinanceRateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
```
