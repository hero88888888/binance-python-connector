# Getting Started

## Installation

```bash
pip install binance-book
```

### Optional Extras

| Extra | What it adds | Install command |
|---|---|---|
| `dataframe` | pandas — enables `format="dataframe"` output | `pip install binance-book[dataframe]` |
| `analytics` | numpy — enables advanced analytics computations | `pip install binance-book[analytics]` |
| `parquet` | pyarrow — enables Parquet file persistence | `pip install binance-book[parquet]` |
| `all` | All of the above | `pip install binance-book[all]` |

## Creating a Client

```python
from binance_book import BinanceBook

# No API key needed for public market data
book = BinanceBook()

# With API key (for authenticated endpoints)
book = BinanceBook(api_key="your_key", api_secret="your_secret")

# For USDT-M Futures instead of Spot
book = BinanceBook(market="futures_usdt")

# For testnet
book = BinanceBook(testnet=True)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | str | None | Binance API key. Only needed for authenticated endpoints. |
| `api_secret` | str | None | Binance API secret. |
| `testnet` | bool | False | Use Binance testnet endpoints. |
| `market` | str | `"spot"` | Default market: `"spot"`, `"futures_usdt"`, or `"futures_coin"`. |
| `model` | str | None | LLM model name for auto-sizing output (e.g. `"gpt-4o"`). |
| `context_budget` | int | None | Total context tokens available. Auto-detected from `model`. |
| `reserved_tokens` | int | 64000 | Tokens reserved for system prompt / conversation. |
| `timeout` | float | 10.0 | HTTP request timeout in seconds. |

## Configuration for AI Agents

If you're building an AI agent, configure the context budget so data output is automatically sized to fit:

```python
book = BinanceBook(
    model="gpt-4o",           # auto-sets budget to 128k tokens
    reserved_tokens=64000,    # leaves 64k for data
)

# Now detail="auto" will pick the right detail level
book.ob_snapshot(["BTCUSDT", "ETHUSDT", ...], detail="auto")
```

## Async Usage

All methods work synchronously by default. For async code:

```python
import asyncio
from binance_book import BinanceBook

async def main():
    book = BinanceBook()
    
    # Use the _async variants directly
    ob = await book._ob_snapshot_wide_async("BTCUSDT", max_levels=5)
    
    # Streaming is always async
    async for update in book.ob_stream("BTCUSDT", max_levels=5):
        print(update)
    
    await book.close()

asyncio.run(main())
```

## Supported Markets

| Market | Value | REST Base | WS Base |
|---|---|---|---|
| Spot | `"spot"` | `api.binance.com` | `stream.binance.com:9443` |
| USDT-M Futures | `"futures_usdt"` | `fapi.binance.com` | `fstream.binance.com` |
| COIN-M Futures | `"futures_coin"` | `dapi.binance.com` | `dstream.binance.com` |

All methods accept an optional `market` parameter to override the default:

```python
book = BinanceBook()  # default: spot
book.ob_snapshot("BTCUSDT", market="futures_usdt")  # override for this call
```
