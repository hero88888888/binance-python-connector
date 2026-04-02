# Data Quality

Understanding and handling the real-world quality issues in Binance orderbook data.

---

## The Problem

Raw Binance orderbook data has significant quality issues that most libraries ignore. Our empirical analysis of live BTCUSDT data found:

| Issue | Finding | Impact |
|---|---|---|
| **Dust orders** | 27-49% of top 100 levels have < $66 notional | Inflates apparent depth, distorts imbalance signals |
| **Book sparsity** | 75-79% of levels have price gaps > 1 tick | Misleading level count; gaps of 28-113 ticks are common |
| **Depth asymmetry** | 3:1 bid/ask imbalance ($1.53M vs $481K) | Normal, but important to understand |
| **Unbounded growth** | Without pruning, book grows from 1000 to 4000+ rows in 13 hours | Memory leaks in long-running processes |
| **Latency spikes** | Feed delays spike to seconds during volatile events | Stale quotes misrepresent the book |

## Built-in Filters

### Dust Filter

Removes levels with notional value below a threshold.

```python
# Default: removes levels < $5 notional
ob = book.ob_snapshot("BTCUSDT", max_levels=50, clean=["dust"])

# Custom threshold
from binance_book.filters.dust import filter_dust
raw = book.ob_snapshot("BTCUSDT", max_levels=50)
clean = filter_dust(raw, min_notional_usd=100)  # Only keep levels > $100
```

### Stale Filter

Removes levels with timestamps older than a threshold.

```python
from binance_book.filters.stale import filter_stale
clean = filter_stale(raw, staleness_ms=5000)  # Remove anything > 5 seconds old
```

### Gap Filter

Removes levels with large price gaps from their neighbor.

```python
from binance_book.filters.gap import filter_gap
clean = filter_gap(raw, max_gap_ticks=50, tick_size=0.01)
```

### Anomaly Filter

Removes statistical size outliers (potential spoof walls).

```python
from binance_book.filters.anomaly import filter_anomalies
clean = filter_anomalies(raw, sigma=3.0)  # Remove sizes > 3σ from mean
```

## Annotation Mode

Instead of removing rows, add quality columns for analysis:

```python
ob = book.ob_snapshot("BTCUSDT", max_levels=20, annotate=True)
# Each row gets: IS_DUST, NOTIONAL_USD, GAP_TICKS, IS_OUTLIER, IS_STALE, STALENESS_MS
```

## Token Budget Reality

A full 5000-level BTCUSDT orderbook is 332 KB / ~85,000 tokens. This table shows how many symbols you can fit in different LLM context windows:

| Detail Level | Tokens/Symbol | GPT-4o (64k avail) | Claude 3.5 (100k avail) |
|---|---|---|---|
| `"minimal"` | ~34 | 1,280 symbols | 2,000 symbols |
| `"summary"` | ~136 | 426 symbols | 666 symbols |
| `"standard"` | ~500 | 128 symbols | 200 symbols |
| `"detailed"` | ~2,500 | 25 symbols | 40 symbols |
| `"full"` | ~100,000 | 0 symbols | 1 symbol |

**Rule of thumb:** Use `detail="auto"` and let binance-book pick the right level based on your context budget.

## Streaming Bandwidth

| Stream | Per Symbol | 10 Symbols | 100 Symbols |
|---|---|---|---|
| `@depth@100ms` | ~12.7 KB/s, 44.6 MB/hr | 446 MB/hr | 4.4 GB/hr |
| `@depth` (1s) | ~1.3 KB/s, 4.5 MB/hr | 45 MB/hr | 450 MB/hr |
| `@bookTicker` | ~5 KB/s | 50 KB/s | 500 KB/s |
| `@trade` | ~1.5 KB/s | 15 KB/s | 150 KB/s |
