# binance-book

The best agentic AI wrapper for Binance orderbook data.

[![PyPI](https://img.shields.io/pypi/v/binance-book)](https://pypi.org/project/binance-book/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**[Documentation](https://hero88888888.github.io/binance-python-connector)** · **[PyPI](https://pypi.org/project/binance-book/)** · **[Examples](https://hero88888888.github.io/binance-python-connector/examples/)**

---

- **Typed schemas** — Pydantic models for all data types (trade, quote, level, bar, info)
- **Three orderbook representations** — levels (per-side), wide (paired), flat (single-row)
- **Context-window-aware output** — Auto-sizes data to fit your LLM's token budget
- **Built-in data cleaning** — Dust removal, stale quote detection, gap handling, anomaly detection
- **Agentic AI native** — Auto-exports tools for OpenAI, Anthropic, and MCP
- **Built-in analytics** — Book imbalance, sweep (VWAP), spread computation
- **Standalone** — Talks directly to Binance REST/WS APIs, no third-party Binance libs

## Install

```bash
pip install binance-book
```

With optional extras:

```bash
pip install binance-book[all]        # pandas + numpy + pyarrow
pip install binance-book[dataframe]  # pandas only
```

## Quick Start

```python
from binance_book import BinanceBook

book = BinanceBook()

# Three orderbook representations
book.ob_snapshot("BTCUSDT", max_levels=5)       # per level per side
book.ob_snapshot_wide("BTCUSDT", max_levels=5)  # per level, both sides paired
book.ob_snapshot_flat("BTCUSDT", max_levels=5)  # single row, all levels flattened

# Analytics
book.imbalance("BTCUSDT", levels=5)                         # → -0.55 (ask-heavy)
book.sweep_by_qty("BTCUSDT", side="ASK", qty=10.0)          # → {vwap, total_cost, ...}
book.spread("BTCUSDT")                                       # → {quoted, quoted_bps, mid, ...}

# Data cleaning
book.ob_snapshot("BTCUSDT", max_levels=50, clean=True)       # removes dust orders
book.ob_snapshot("BTCUSDT", max_levels=20, annotate=True)    # adds IS_DUST, IS_OUTLIER cols

# Output formats
book.ob_snapshot_wide("BTCUSDT", format="narrative")         # natural language for LLMs
book.ob_snapshot_wide("BTCUSDT", format="markdown")          # markdown table
book.ob_snapshot_wide("BTCUSDT", format="dataframe")         # pandas DataFrame

# Streaming (async)
async for update in book.ob_stream("BTCUSDT", max_levels=5, format="flat"):
    print(update)
```

## For AI Agents

Every method auto-exports as a callable tool:

```python
# OpenAI function-calling
tools = book.tools(format="openai")
# → Pass to ChatCompletion(tools=tools)

# Anthropic tool_use
tools = book.tools(format="anthropic")
# → Pass to messages.create(tools=tools)

# Dispatch tool calls from LLM responses
result = book.execute("ob_snapshot_wide", {"symbol": "BTCUSDT", "max_levels": 5})

# MCP server mode
book.serve_mcp(port=8080)
```

No API key is required for public market data. Supports Spot, USDT-M Futures, and COIN-M Futures.

## Schema Introspection

```python
book.schema("trade")   # → {'PRICE': 'float', 'SIZE': 'float', 'TRADE_ID': 'int', ...}
book.schema("level")   # → {'SIDE': 'str', 'PRICE': 'float', 'SIZE': 'float', 'LEVEL': 'int', ...}
book.schema("bar")     # → {'OPEN': 'float', 'HIGH': 'float', 'LOW': 'float', 'CLOSE': 'float', ...}
book.schema("quote")   # → {'BID_PRICE': 'float', 'ASK_PRICE': 'float', ...}
book.schema("ticker")  # → {'VOLUME': 'float', 'PRICE_CHANGE_PERCENT': 'float', ...}
book.schema("info")    # → {'SYMBOL': 'str', 'TICK_SIZE': 'float', 'LOT_SIZE': 'float', ...}
```

## Documentation

Full documentation at **[hero88888888.github.io/binance-python-connector](https://hero88888888.github.io/binance-python-connector)**

- [Getting Started](https://hero88888888.github.io/binance-python-connector/getting-started/)
- [API Reference](https://hero88888888.github.io/binance-python-connector/api-reference/)
- [Examples](https://hero88888888.github.io/binance-python-connector/examples/)
- [Data Quality](https://hero88888888.github.io/binance-python-connector/data-quality/)

## License

MIT
