# Examples

Real-world usage patterns for common tasks.

---

## Screen All USDT Pairs by Imbalance

Find the most bid-heavy and ask-heavy pairs across all USDT markets:

```python
from binance_book import BinanceBook

book = BinanceBook()
symbols = book.symbols(quote="USDT", min_volume_24h=10_000_000)

results = []
for sym in symbols:
    try:
        imb = book.imbalance(sym.SYMBOL, levels=5)
        sp = book.spread(sym.SYMBOL)
        results.append({
            "symbol": sym.SYMBOL,
            "imbalance": imb,
            "spread_bps": sp["quoted_bps"],
            "mid": sp["mid"],
        })
    except Exception:
        continue

# Sort by imbalance
results.sort(key=lambda x: x["imbalance"])
print("Most ask-heavy (selling pressure):")
for r in results[:5]:
    print(f"  {r['symbol']}: imb={r['imbalance']:+.3f}, spread={r['spread_bps']:.2f}bps")

print("\nMost bid-heavy (buying pressure):")
for r in results[-5:]:
    print(f"  {r['symbol']}: imb={r['imbalance']:+.3f}, spread={r['spread_bps']:.2f}bps")
```

---

## Estimate Execution Cost

How much would it cost to buy 10 BTC right now?

```python
book = BinanceBook()
sweep = book.sweep_by_qty("BTCUSDT", side="ASK", qty=10.0)

print(f"VWAP: ${sweep['vwap']:,.2f}")
print(f"Total cost: ${sweep['total_cost']:,.2f}")
print(f"Levels consumed: {sweep['levels_consumed']}")
print(f"Slippage from best ask: ${sweep['vwap'] - book.quote('BTCUSDT')['ASK_PRICE']:.2f}")
```

---

## Clean Orderbook for Analysis

Remove noise and see what the "real" book looks like:

```python
book = BinanceBook()

# Raw book
raw = book.ob_snapshot("BTCUSDT", max_levels=50)
print(f"Raw: {len(raw)} levels")

# Cleaned (removes dust orders < $5 notional)
clean = book.ob_snapshot("BTCUSDT", max_levels=50, clean=True)
print(f"Cleaned: {len(clean)} levels ({len(raw) - len(clean)} dust removed)")

# Annotated — see which levels are dust, outliers, etc.
ann = book.ob_snapshot("BTCUSDT", max_levels=20, annotate=True)
for row in ann[:5]:
    print(f"  L{row['LEVEL']} {row['SIDE']}: ${row['PRICE']:,.2f} × {row['SIZE']:.4f}"
          f"  notional=${row['NOTIONAL_USD']:,.2f}"
          f"  dust={'YES' if row['IS_DUST'] else 'no'}"
          f"  outlier={'YES' if row['IS_OUTLIER'] else 'no'}")
```

---

## Stream Live Orderbook Updates

```python
import asyncio
from binance_book import BinanceBook

async def monitor_book():
    book = BinanceBook()
    count = 0
    async for update in book.ob_stream("BTCUSDT", max_levels=5, format="flat"):
        bid = update["BID_PRICE1"]
        ask = update["ASK_PRICE1"]
        spread = ask - bid
        print(f"[{count}] bid={bid} ask={ask} spread={spread:.2f}")
        count += 1
        if count >= 100:
            break
    await book.close()

asyncio.run(monitor_book())
```

---

## OpenAI Agent Integration

Build an AI agent that can answer questions about crypto markets:

```python
from openai import OpenAI
from binance_book import BinanceBook
import json

book = BinanceBook()
client = OpenAI()

# Get tool definitions
tools = book.tools(format="openai")

# Send user question
messages = [{"role": "user", "content": "What's the current BTCUSDT spread and book imbalance?"}]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
)

# Handle tool calls
for tool_call in response.choices[0].message.tool_calls:
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    result = book.execute(name, args)
    
    messages.append(response.choices[0].message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(result, default=str),
    })

# Get final response
final = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
)
print(final.choices[0].message.content)
```

---

## Anthropic Agent Integration

```python
import anthropic
from binance_book import BinanceBook
import json

book = BinanceBook()
client = anthropic.Anthropic()

tools = book.tools(format="anthropic")

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Show me the ETHUSDT orderbook top 5 levels"}],
)

for block in response.content:
    if block.type == "tool_use":
        result = book.execute(block.name, block.input)
        # Send result back to Claude...
```

---

## Multi-Format Output Comparison

See the same data in every supported format:

```python
book = BinanceBook()

for fmt in ["json", "csv", "markdown", "narrative"]:
    print(f"\n{'='*40}")
    print(f"Format: {fmt}")
    print(f"{'='*40}")
    result = book.ob_snapshot_wide("BTCUSDT", max_levels=3, format=fmt)
    print(result if isinstance(result, str) else result)
```

---

## Compare Spot vs Futures Orderbook

```python
book = BinanceBook()

spot_spread = book.spread("BTCUSDT", market="spot")
futures_spread = book.spread("BTCUSDT", market="futures_usdt")

print(f"Spot spread:    {spot_spread['quoted_bps']:.4f} bps (mid=${spot_spread['mid']:,.2f})")
print(f"Futures spread: {futures_spread['quoted_bps']:.4f} bps (mid=${futures_spread['mid']:,.2f})")
print(f"Basis: ${futures_spread['mid'] - spot_spread['mid']:,.2f}")
```
