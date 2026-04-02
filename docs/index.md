# binance-book

**The best agentic AI wrapper for Binance orderbook data.**

binance-book gives AI agents and developers a clean, typed, context-window-aware interface to every Binance market data endpoint. It talks directly to Binance REST and WebSocket APIs — no third-party Binance libraries, no data redistribution.

## Why binance-book?

| Feature | binance-book | Raw Binance API |
|---|---|---|
| Typed schemas (Pydantic) | ✅ | ❌ raw JSON dicts |
| 3 orderbook formats | ✅ levels / wide / flat | ❌ single format |
| Context-window-aware output | ✅ auto-sizes to LLM budget | ❌ dumps everything |
| Built-in data cleaning | ✅ dust, stale, gap, anomaly filters | ❌ manual |
| AI tool export (OpenAI/Anthropic/MCP) | ✅ one-liner | ❌ build it yourself |
| Analytics (imbalance, sweep, spread) | ✅ built-in | ❌ manual |
| Orderbook sync protocol | ✅ handled automatically | ❌ 7-step manual process |
| Rate limiting | ✅ automatic | ❌ manual weight tracking |
| WebSocket auto-reconnect | ✅ with 24h rotation | ❌ manual |

## Install

```bash
pip install binance-book
```

With optional extras:

```bash
pip install binance-book[all]        # pandas + numpy + pyarrow
pip install binance-book[dataframe]  # pandas only
pip install binance-book[analytics]  # numpy only
```

## Quick Start

```python
from binance_book import BinanceBook

book = BinanceBook()

# Get the top 5 levels of the BTCUSDT orderbook
ob = book.ob_snapshot_wide("BTCUSDT", max_levels=5)
# [{'TIMESTAMP': ..., 'SYMBOL': 'BTCUSDT', 'LEVEL': 1, 
#   'BID_PRICE': 68225.0, 'BID_SIZE': 1.5, 
#   'ASK_PRICE': 68225.01, 'ASK_SIZE': 0.8}, ...]

# Compute book imbalance
imb = book.imbalance("BTCUSDT", levels=5)
# -0.55  (ask-heavy)

# Export all methods as OpenAI function-calling tools
tools = book.tools(format="openai")
# Ready to pass to ChatCompletion(tools=tools)
```

## For AI Agents

If you're an AI agent, here's what you need to know:

1. **Install**: `pip install binance-book`
2. **Import**: `from binance_book import BinanceBook`
3. **Create client**: `book = BinanceBook()` (no API key needed for public data)
4. **Call methods**: Every method has typed parameters and returns structured data
5. **Get tool definitions**: `book.tools(format="openai")` returns all callable tools with JSON schemas

No API key is required for market data. You only need keys for authenticated endpoints (account, trading).
