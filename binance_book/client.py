"""Main BinanceBook client — the primary interface for all operations.

Phase 1 implements REST-only functionality: symbol discovery, orderbook
snapshots (3 representations), trades, klines, quotes, and schema introspection.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, Optional, Union

from binance_book.api import endpoints as ep
from binance_book.api.rest import BinanceRestClient
from binance_book.config import BinanceBookConfig, FilterConfig
from binance_book.exceptions import DependencyError, InvalidSymbolError
from binance_book.markets import MarketType, fetch_symbols, get_symbol_names
from binance_book.schemas.base import Side, Timestamp
from binance_book.schemas.ohlcv import OHLCVBar
from binance_book.schemas.orderbook import OrderBookLevel
from binance_book.schemas.quote import Quote
from binance_book.schemas.static import SymbolInfo
from binance_book.schemas.ticker import Ticker24hr
from binance_book.schemas.trade import Trade

logger = logging.getLogger(__name__)

DetailLevel = Literal["minimal", "summary", "standard", "detailed", "full", "auto"]
OutputFormat = Literal["json", "csv", "markdown", "narrative", "dataframe"]


# ---------------------------------------------------------------------------
# Schema registry for introspection
# ---------------------------------------------------------------------------

_SCHEMA_MAP: dict[str, dict[str, str]] = {
    "trade": {
        "TIMESTAMP": "int",
        "SYMBOL": "str",
        "PRICE": "float",
        "SIZE": "float",
        "TRADE_ID": "int",
        "IS_BUYER_MAKER": "bool",
    },
    "quote": {
        "TIMESTAMP": "int",
        "SYMBOL": "str",
        "BID_PRICE": "float",
        "BID_SIZE": "float",
        "ASK_PRICE": "float",
        "ASK_SIZE": "float",
        "UPDATE_ID": "int",
    },
    "bbo": {
        "TIMESTAMP": "int",
        "SYMBOL": "str",
        "BID_PRICE": "float",
        "BID_SIZE": "float",
        "ASK_PRICE": "float",
        "ASK_SIZE": "float",
        "UPDATE_ID": "int",
    },
    "level": {
        "TIMESTAMP": "int",
        "SYMBOL": "str",
        "SIDE": "str",
        "PRICE": "float",
        "SIZE": "float",
        "LEVEL": "int",
        "UPDATE_ID": "int",
    },
    "bar": {
        "TIMESTAMP": "int",
        "SYMBOL": "str",
        "OPEN": "float",
        "HIGH": "float",
        "LOW": "float",
        "CLOSE": "float",
        "VOLUME": "float",
        "CLOSE_TIME": "int",
        "QUOTE_VOLUME": "float",
        "TRADE_COUNT": "int",
    },
    "ticker": {
        "TIMESTAMP": "int",
        "SYMBOL": "str",
        "OPEN": "float",
        "HIGH": "float",
        "LOW": "float",
        "CLOSE": "float",
        "VOLUME": "float",
        "QUOTE_VOLUME": "float",
        "PRICE_CHANGE": "float",
        "PRICE_CHANGE_PERCENT": "float",
        "TRADE_COUNT": "int",
    },
    "info": {
        "SYMBOL": "str",
        "BASE_ASSET": "str",
        "QUOTE_ASSET": "str",
        "STATUS": "str",
        "TICK_SIZE": "float",
        "LOT_SIZE": "float",
        "MIN_NOTIONAL": "float",
    },
}


class BinanceBook:
    """The best agentic AI wrapper for Binance orderbook data.

    Provides a unified interface for retrieving market data from Binance
    across all market types (Spot, USDT-M Futures, COIN-M Futures).  Every
    method is designed for both human and AI-agent consumption with
    context-window-aware output sizing.

    Parameters
    ----------
    api_key : str, optional
        Binance API key. Required only for authenticated endpoints.
    api_secret : str, optional
        Binance API secret.
    testnet : bool
        Use Binance testnet endpoints.
    market : str
        Default market: ``"spot"``, ``"futures_usdt"``, or ``"futures_coin"``.
    model : str, optional
        LLM model name for auto-sizing output (e.g. ``"gpt-4o"``).
    context_budget : int, optional
        Total context tokens available. Auto-detected from ``model`` if set.
    reserved_tokens : int
        Tokens reserved for system prompt / conversation. Default 64000.
    timeout : float
        HTTP request timeout in seconds.

    Examples
    --------
    >>> book = BinanceBook()
    >>> symbols = book.symbols(quote="USDT")
    >>> ob = book.ob_snapshot_wide("BTCUSDT", max_levels=5)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        market: MarketType = "spot",
        model: Optional[str] = None,
        context_budget: Optional[int] = None,
        reserved_tokens: int = 64000,
        timeout: float = 10.0,
    ) -> None:
        self._config = BinanceBookConfig(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            market=market,
            model=model,
            context_budget=context_budget,
            reserved_tokens=reserved_tokens,
            timeout=timeout,
        )
        self._rest = BinanceRestClient(
            base_url=self._config.get_rest_base_url(),
            api_key=api_key,
            api_secret=api_secret,
            timeout=timeout,
        )
        self._symbol_cache: dict[str, SymbolInfo] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close all connections and release resources."""
        await self._rest.close()

    async def __aenter__(self) -> "BinanceBook":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    def schema(self, data_type: str) -> dict[str, str]:
        """Return the field definitions for a given data type.

        Supported data types: ``"trade"``, ``"quote"``, ``"bbo"``,
        ``"level"``, ``"bar"``, ``"ticker"``, ``"info"``.

        Parameters
        ----------
        data_type : str
            Data type name (case-insensitive).

        Returns
        -------
        dict[str, str]
            Mapping of field name to type string.

        Examples
        --------
        >>> book.schema("trade")
        {'TIMESTAMP': 'int', 'PRICE': 'float', 'SIZE': 'float', ...}
        """
        key = data_type.lower()
        if key not in _SCHEMA_MAP:
            raise ValueError(f"Unknown data type: {data_type!r}. Supported: {list(_SCHEMA_MAP)}")
        return dict(_SCHEMA_MAP[key])

    # ------------------------------------------------------------------
    # Agentic AI — tools, execute, MCP
    # ------------------------------------------------------------------

    def tools(self, format: str = "openai") -> list[dict[str, Any]]:
        """Export all public methods as AI-agent tool definitions.

        Returns a list of tool definitions with JSON schemas generated from
        type hints and docstrings.  Compatible with OpenAI function-calling,
        Anthropic tool_use, or raw registry format.

        Parameters
        ----------
        format : str
            Export format: ``"openai"``, ``"anthropic"``, or ``"raw"``.

        Returns
        -------
        list[dict]
            Tool definitions in the requested format.

        Examples
        --------
        >>> tools = book.tools(format="openai")
        >>> # Pass directly to OpenAI Chat Completions API
        """
        from binance_book.tools.registry import ToolRegistry

        registry = ToolRegistry(self)

        if format == "anthropic":
            from binance_book.tools.anthropic import to_anthropic_tools
            return to_anthropic_tools(registry)
        elif format == "openai":
            from binance_book.tools.openai import to_openai_tools
            return to_openai_tools(registry)
        else:
            return [t.to_dict() for t in registry.get_all()]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch an AI-agent tool call by name.

        Looks up the method on this BinanceBook instance and calls it with
        the provided arguments.  This is the entry point for AI agents that
        receive tool-call responses from LLMs.

        Parameters
        ----------
        tool_name : str
            Name of the tool/method (e.g. ``"ob_snapshot"``).
        arguments : dict
            Keyword arguments for the method.

        Returns
        -------
        Any
            The method's return value.

        Examples
        --------
        >>> book.execute("ob_snapshot", {"symbol": "BTCUSDT", "max_levels": 10})
        """
        from binance_book.tools.registry import ToolRegistry

        registry = ToolRegistry(self)
        return registry.execute(tool_name, arguments)

    def serve_mcp(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Start an MCP (Model Context Protocol) server exposing all tools.

        The server listens for JSON-RPC requests on ``/mcp`` and supports
        ``tools/list`` and ``tools/call`` methods.  Any MCP-compatible AI
        agent can discover and invoke BinanceBook tools over HTTP.

        Parameters
        ----------
        host : str
            Bind address. Default ``"0.0.0.0"``.
        port : int
            Port number. Default 8080.
        """
        from binance_book.tools.mcp import MCPServer
        from binance_book.tools.registry import ToolRegistry

        registry = ToolRegistry(self)
        server = MCPServer(registry)
        _run_sync(server.serve(host=host, port=port))

    # ------------------------------------------------------------------
    # Symbol discovery
    # ------------------------------------------------------------------

    def symbols(
        self,
        market: Optional[MarketType] = None,
        quote: Optional[str] = None,
        status: str = "TRADING",
        min_volume_24h: Optional[float] = None,
    ) -> list[SymbolInfo]:
        """Get trading pair symbols with optional filtering.

        Retrieves all symbols for the specified market and filters by quote
        asset, trading status, and minimum 24-hour volume.

        Parameters
        ----------
        market : str, optional
            Market type. Defaults to the client's configured market.
        quote : str, optional
            Filter by quote asset (e.g. ``"USDT"``).
        status : str
            Only include symbols with this status. Default ``"TRADING"``.
        min_volume_24h : float, optional
            Minimum 24-hour quote volume in USD to include.

        Returns
        -------
        list[SymbolInfo]
            List of SymbolInfo models sorted alphabetically.

        Examples
        --------
        >>> symbols = book.symbols(quote="USDT", min_volume_24h=1_000_000)
        """
        return _run_sync(self._symbols_async(market, quote, status, min_volume_24h))

    async def _symbols_async(
        self,
        market: Optional[MarketType] = None,
        quote: Optional[str] = None,
        status: str = "TRADING",
        min_volume_24h: Optional[float] = None,
    ) -> list[SymbolInfo]:
        mkt = market or self._config.market
        client = self._get_rest_client(mkt)
        result = await fetch_symbols(client, mkt, quote, status, min_volume_24h)
        for s in result:
            self._symbol_cache[s.SYMBOL] = s
        return result

    # ------------------------------------------------------------------
    # Orderbook snapshots — three representations
    # ------------------------------------------------------------------

    def ob_snapshot(
        self,
        symbol: Union[str, list[str]],
        max_levels: int = 10,
        market: Optional[MarketType] = None,
        detail: DetailLevel = "standard",
        format: OutputFormat = "json",
        clean: Union[bool, list[str]] = False,
        annotate: bool = False,
    ) -> Any:
        """Get orderbook snapshot with one row per level per side.

        Returns bid and ask levels as separate rows, each tagged with SIDE,
        PRICE, SIZE, and LEVEL number.

        Parameters
        ----------
        symbol : str or list[str]
            Trading pair symbol(s). Pass a list for multi-symbol queries.
        max_levels : int
            Maximum depth levels per side. Default 10.
        market : str, optional
            Override market type for this request.
        detail : str
            Output detail level: ``"minimal"``, ``"summary"``, ``"standard"``,
            ``"detailed"``, ``"full"``, or ``"auto"``.
        format : str
            Output format: ``"json"``, ``"csv"``, ``"markdown"``,
            ``"narrative"``, or ``"dataframe"``.
        clean : bool or list[str]
            Apply data cleaning filters. ``True`` for all defaults, or a list
            of filter names (e.g. ``["dust", "stale"]``).
        annotate : bool
            If True, add quality columns (IS_DUST, NOTIONAL_USD, GAP_TICKS).

        Returns
        -------
        list[dict] or DataFrame or str
            Orderbook levels depending on ``format``.
        """
        return _run_sync(
            self._ob_snapshot_async(symbol, max_levels, market, detail, format, clean, annotate)
        )

    async def _ob_snapshot_async(
        self,
        symbol: Union[str, list[str]],
        max_levels: int = 10,
        market: Optional[MarketType] = None,
        detail: DetailLevel = "standard",
        format: OutputFormat = "json",
        clean: Union[bool, list[str]] = False,
        annotate: bool = False,
    ) -> Any:
        if isinstance(symbol, list):
            results = {}
            for sym in symbol:
                results[sym] = await self._ob_snapshot_single(
                    sym, max_levels, market, detail, format, clean, annotate
                )
            return results
        return await self._ob_snapshot_single(
            symbol, max_levels, market, detail, format, clean, annotate
        )

    async def _ob_snapshot_single(
        self,
        symbol: str,
        max_levels: int,
        market: Optional[MarketType],
        detail: DetailLevel,
        format: OutputFormat,
        clean: Union[bool, list[str]],
        annotate: bool,
    ) -> Any:
        mkt = market or self._config.market
        raw = await self._fetch_depth(symbol, max_levels, mkt)
        levels = OrderBookLevel.from_depth_snapshot(
            bids=raw["bids"][:max_levels],
            asks=raw["asks"][:max_levels],
            last_update_id=raw["lastUpdateId"],
            symbol=symbol,
        )
        rows = [lvl.model_dump() for lvl in levels]
        rows = _apply_filters(rows, clean, annotate, self._config.filters)
        return self._format_output(rows, format, f"{symbol} orderbook levels")

    def ob_snapshot_wide(
        self,
        symbol: Union[str, list[str]],
        max_levels: int = 10,
        market: Optional[MarketType] = None,
        detail: DetailLevel = "standard",
        format: OutputFormat = "json",
        clean: Union[bool, list[str]] = False,
        annotate: bool = False,
    ) -> Any:
        """Get orderbook snapshot with one row per level, both sides.

        Each row contains bid and ask price/size for the same depth level,
        making it easy to see the spread at each level.

        Parameters
        ----------
        symbol : str or list[str]
            Trading pair symbol(s).
        max_levels : int
            Maximum depth levels. Default 10.
        market : str, optional
            Override market type.
        detail : str
            Output detail level.
        format : str
            Output format.
        clean : bool or list[str]
            Apply data cleaning filters.
        annotate : bool
            If True, add quality columns (IS_DUST, NOTIONAL_USD, etc.).

        Returns
        -------
        list[dict] or DataFrame or str
            Wide-format orderbook levels.
        """
        return _run_sync(
            self._ob_snapshot_wide_async(symbol, max_levels, market, detail, format, clean, annotate)
        )

    async def _ob_snapshot_wide_async(
        self,
        symbol: Union[str, list[str]],
        max_levels: int = 10,
        market: Optional[MarketType] = None,
        detail: DetailLevel = "standard",
        format: OutputFormat = "json",
        clean: Union[bool, list[str]] = False,
        annotate: bool = False,
    ) -> Any:
        if isinstance(symbol, list):
            results = {}
            for sym in symbol:
                results[sym] = await self._ob_snapshot_wide_single(
                    sym, max_levels, market, detail, format, clean, annotate
                )
            return results
        return await self._ob_snapshot_wide_single(
            symbol, max_levels, market, detail, format, clean, annotate
        )

    async def _ob_snapshot_wide_single(
        self,
        symbol: str,
        max_levels: int,
        market: Optional[MarketType],
        detail: DetailLevel,
        format: OutputFormat,
        clean: Union[bool, list[str]],
        annotate: bool = False,
    ) -> Any:
        mkt = market or self._config.market
        raw = await self._fetch_depth(symbol, max_levels, mkt)
        ts = Timestamp.now_ms()
        bids = raw["bids"][:max_levels]
        asks = raw["asks"][:max_levels]
        n = min(len(bids), len(asks), max_levels)

        rows: list[dict[str, Any]] = []
        for i in range(n):
            rows.append({
                "TIMESTAMP": ts,
                "SYMBOL": symbol,
                "LEVEL": i + 1,
                "BID_PRICE": float(bids[i][0]),
                "BID_SIZE": float(bids[i][1]),
                "ASK_PRICE": float(asks[i][0]),
                "ASK_SIZE": float(asks[i][1]),
            })

        rows = _apply_filters(rows, clean, annotate, self._config.filters)
        return self._format_output(rows, format, f"{symbol} orderbook wide")

    def ob_snapshot_flat(
        self,
        symbol: Union[str, list[str]],
        max_levels: int = 10,
        market: Optional[MarketType] = None,
        detail: DetailLevel = "standard",
        format: OutputFormat = "json",
        clean: Union[bool, list[str]] = False,
    ) -> Any:
        """Get orderbook snapshot as a single flattened row.

        All levels are flattened into one row with columns like BID_PRICE1,
        BID_SIZE1, ASK_PRICE1, ASK_SIZE1, BID_PRICE2, ... This is the most
        compact representation and ideal for feeding into ML models.

        Parameters
        ----------
        symbol : str or list[str]
            Trading pair symbol(s).
        max_levels : int
            Maximum depth levels. Default 10.
        market : str, optional
            Override market type.
        detail : str
            Output detail level.
        format : str
            Output format.
        clean : bool or list[str]
            Apply data cleaning filters.

        Returns
        -------
        dict or DataFrame or str
            Single-row flattened orderbook.
        """
        return _run_sync(
            self._ob_snapshot_flat_async(symbol, max_levels, market, detail, format, clean)
        )

    async def _ob_snapshot_flat_async(
        self,
        symbol: Union[str, list[str]],
        max_levels: int = 10,
        market: Optional[MarketType] = None,
        detail: DetailLevel = "standard",
        format: OutputFormat = "json",
        clean: Union[bool, list[str]] = False,
    ) -> Any:
        if isinstance(symbol, list):
            results = {}
            for sym in symbol:
                results[sym] = await self._ob_snapshot_flat_single(
                    sym, max_levels, market, detail, format, clean
                )
            return results
        return await self._ob_snapshot_flat_single(
            symbol, max_levels, market, detail, format, clean
        )

    async def _ob_snapshot_flat_single(
        self,
        symbol: str,
        max_levels: int,
        market: Optional[MarketType],
        detail: DetailLevel,
        format: OutputFormat,
        clean: Union[bool, list[str]],
    ) -> Any:
        mkt = market or self._config.market
        raw = await self._fetch_depth(symbol, max_levels, mkt)
        ts = Timestamp.now_ms()
        bids = raw["bids"][:max_levels]
        asks = raw["asks"][:max_levels]
        n = min(len(bids), len(asks), max_levels)

        row: dict[str, Any] = {"TIMESTAMP": ts, "SYMBOL": symbol}
        for i in range(n):
            lvl = i + 1
            row[f"BID_PRICE{lvl}"] = float(bids[i][0])
            row[f"BID_SIZE{lvl}"] = float(bids[i][1])
            row[f"ASK_PRICE{lvl}"] = float(asks[i][0])
            row[f"ASK_SIZE{lvl}"] = float(asks[i][1])

        return self._format_output([row], format, f"{symbol} orderbook flat")

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def trades(
        self,
        symbol: str,
        limit: int = 100,
        market: Optional[MarketType] = None,
        format: OutputFormat = "json",
    ) -> Any:
        """Get recent trades for a symbol.

        Parameters
        ----------
        symbol : str
            Trading pair symbol (e.g. ``"BTCUSDT"``).
        limit : int
            Number of trades to retrieve (max 1000). Default 100.
        market : str, optional
            Override market type.
        format : str
            Output format.

        Returns
        -------
        list[dict] or DataFrame or str
            Recent trades.
        """
        return _run_sync(self._trades_async(symbol, limit, market, format))

    async def _trades_async(
        self,
        symbol: str,
        limit: int = 100,
        market: Optional[MarketType] = None,
        format: OutputFormat = "json",
    ) -> Any:
        mkt = market or self._config.market
        client = self._get_rest_client(mkt)
        endpoint = ep.SPOT_TRADES if mkt == "spot" else ep.FUTURES_USDT_TRADES
        data = await client.get(endpoint, params={"symbol": symbol, "limit": min(limit, 1000)})
        trades = [Trade.from_binance(t, symbol=symbol).model_dump() for t in data]
        return self._format_output(trades, format, f"{symbol} trades")

    # ------------------------------------------------------------------
    # Klines / OHLCV
    # ------------------------------------------------------------------

    def klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
        market: Optional[MarketType] = None,
        format: OutputFormat = "json",
    ) -> Any:
        """Get OHLCV candlestick bars for a symbol.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        interval : str
            Kline interval: ``"1m"``, ``"5m"``, ``"15m"``, ``"1h"``, ``"4h"``,
            ``"1d"``, etc. Default ``"1m"``.
        limit : int
            Number of bars (max 1000). Default 100.
        market : str, optional
            Override market type.
        format : str
            Output format.

        Returns
        -------
        list[dict] or DataFrame or str
            OHLCV bars.
        """
        return _run_sync(self._klines_async(symbol, interval, limit, market, format))

    async def _klines_async(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
        market: Optional[MarketType] = None,
        format: OutputFormat = "json",
    ) -> Any:
        mkt = market or self._config.market
        client = self._get_rest_client(mkt)
        endpoint = ep.SPOT_KLINES if mkt == "spot" else ep.FUTURES_USDT_KLINES
        data = await client.get(
            endpoint,
            params={"symbol": symbol, "interval": interval, "limit": min(limit, 1000)},
        )
        bars = [OHLCVBar.from_binance_kline(k, symbol=symbol).model_dump() for k in data]
        return self._format_output(bars, format, f"{symbol} {interval} klines")

    # ------------------------------------------------------------------
    # Quotes / BBO
    # ------------------------------------------------------------------

    def quote(
        self,
        symbol: str,
        market: Optional[MarketType] = None,
    ) -> dict[str, Any]:
        """Get the current best bid/offer (BBO) for a symbol.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        market : str, optional
            Override market type.

        Returns
        -------
        dict
            Quote with BID_PRICE, BID_SIZE, ASK_PRICE, ASK_SIZE, SPREAD, MID_PRICE.
        """
        return _run_sync(self._quote_async(symbol, market))

    async def _quote_async(
        self,
        symbol: str,
        market: Optional[MarketType] = None,
    ) -> dict[str, Any]:
        mkt = market or self._config.market
        client = self._get_rest_client(mkt)
        endpoint = ep.SPOT_TICKER_BOOK if mkt == "spot" else ep.FUTURES_USDT_TICKER_BOOK
        data = await client.get(endpoint, params={"symbol": symbol})
        q = Quote.from_binance(data, symbol=symbol)
        result = q.model_dump()
        result["SPREAD"] = q.SPREAD
        result["MID_PRICE"] = q.MID_PRICE
        result["SPREAD_BPS"] = q.SPREAD_BPS
        return result

    # ------------------------------------------------------------------
    # 24hr ticker
    # ------------------------------------------------------------------

    def ticker_24hr(
        self,
        symbol: Optional[str] = None,
        market: Optional[MarketType] = None,
        format: OutputFormat = "json",
    ) -> Any:
        """Get 24-hour ticker statistics.

        Parameters
        ----------
        symbol : str, optional
            Trading pair symbol. If None, returns all tickers.
        market : str, optional
            Override market type.
        format : str
            Output format.

        Returns
        -------
        dict or list[dict] or DataFrame or str
            24hr ticker statistics.
        """
        return _run_sync(self._ticker_24hr_async(symbol, market, format))

    async def _ticker_24hr_async(
        self,
        symbol: Optional[str] = None,
        market: Optional[MarketType] = None,
        format: OutputFormat = "json",
    ) -> Any:
        mkt = market or self._config.market
        client = self._get_rest_client(mkt)
        endpoint = ep.SPOT_TICKER_24HR if mkt == "spot" else ep.FUTURES_USDT_TICKER_24HR
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        data = await client.get(endpoint, params=params)
        if isinstance(data, list):
            tickers = [Ticker24hr.from_binance(t).model_dump() for t in data]
            return self._format_output(tickers, format, "24hr tickers")
        return Ticker24hr.from_binance(data).model_dump()

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def imbalance(
        self,
        symbol: str,
        levels: int = 5,
        weighted: bool = False,
        market: Optional[MarketType] = None,
    ) -> float:
        """Compute order book imbalance for a symbol.

        Returns a value in [-1, +1]: positive means bid-heavy (buying
        pressure), negative means ask-heavy (selling pressure), 0 means
        balanced.

        Parameters
        ----------
        symbol : str
            Trading pair symbol (e.g. ``"BTCUSDT"``).
        levels : int
            Number of top levels to include. Default 5.
        weighted : bool
            If True, weight by notional (price * qty) instead of raw quantity.
        market : str, optional
            Override market type.

        Returns
        -------
        float
            Imbalance in [-1, +1].
        """
        return _run_sync(self._imbalance_async(symbol, levels, weighted, market))

    async def _imbalance_async(
        self, symbol: str, levels: int, weighted: bool, market: Optional[MarketType]
    ) -> float:
        from binance_book.analytics.imbalance import compute_imbalance

        mkt = market or self._config.market
        raw = await self._fetch_depth(symbol, levels, mkt)
        bids = [(float(p), float(q)) for p, q in raw["bids"][:levels]]
        asks = [(float(p), float(q)) for p, q in raw["asks"][:levels]]
        return round(compute_imbalance(bids, asks, weighted=weighted), 6)

    def sweep_by_qty(
        self,
        symbol: str,
        side: str = "ASK",
        qty: float = 1.0,
        market: Optional[MarketType] = None,
    ) -> dict[str, float]:
        """Sweep the book by quantity — compute VWAP for immediate execution.

        Walk through the book levels consuming liquidity until the target
        quantity is filled. Returns the volume-weighted average price, total
        cost, and number of levels consumed.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        side : str
            ``"ASK"`` to simulate a buy, ``"BID"`` to simulate a sell.
        qty : float
            Target quantity in base asset units.
        market : str, optional
            Override market type.

        Returns
        -------
        dict
            ``vwap``, ``total_cost``, ``filled_qty``, ``levels_consumed``.
        """
        return _run_sync(self._sweep_by_qty_async(symbol, side, qty, market))

    async def _sweep_by_qty_async(
        self, symbol: str, side: str, qty: float, market: Optional[MarketType]
    ) -> dict[str, float]:
        from binance_book.analytics.sweep import sweep_by_qty

        mkt = market or self._config.market
        raw = await self._fetch_depth(symbol, 1000, mkt)
        key = "asks" if side.upper() == "ASK" else "bids"
        levels = [(float(p), float(q)) for p, q in raw[key]]
        return sweep_by_qty(levels, qty)

    def sweep_by_price(
        self,
        symbol: str,
        side: str = "BID",
        price: float = 0.0,
        market: Optional[MarketType] = None,
    ) -> dict[str, float]:
        """Sweep the book by price — total quantity at a price or better.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        side : str
            ``"BID"`` (levels >= price) or ``"ASK"`` (levels <= price).
        price : float
            Target price threshold.
        market : str, optional
            Override market type.

        Returns
        -------
        dict
            ``total_qty``, ``total_notional``, ``levels_consumed``.
        """
        return _run_sync(self._sweep_by_price_async(symbol, side, price, market))

    async def _sweep_by_price_async(
        self, symbol: str, side: str, price: float, market: Optional[MarketType]
    ) -> dict[str, float]:
        from binance_book.analytics.sweep import sweep_by_price

        mkt = market or self._config.market
        raw = await self._fetch_depth(symbol, 1000, mkt)
        key = "bids" if side.upper() == "BID" else "asks"
        levels = [(float(p), float(q)) for p, q in raw[key]]
        return sweep_by_price(levels, price, side=side)

    def spread(
        self,
        symbol: str,
        market: Optional[MarketType] = None,
    ) -> dict[str, float]:
        """Compute spread metrics for a symbol.

        Returns quoted spread (absolute and in basis points), mid price,
        and notional at best bid/ask.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        market : str, optional
            Override market type.

        Returns
        -------
        dict
            ``quoted``, ``quoted_bps``, ``mid``, ``notional_bid``, ``notional_ask``.
        """
        return _run_sync(self._spread_async(symbol, market))

    async def _spread_async(
        self, symbol: str, market: Optional[MarketType]
    ) -> dict[str, float]:
        from binance_book.analytics.spread import compute_spread

        mkt = market or self._config.market
        raw = await self._fetch_depth(symbol, 5, mkt)
        bids = raw["bids"]
        asks = raw["asks"]
        if not bids or not asks:
            return {"quoted": 0, "quoted_bps": 0, "mid": 0, "notional_bid": 0, "notional_ask": 0}
        return compute_spread(
            best_bid=float(bids[0][0]),
            best_ask=float(asks[0][0]),
            best_bid_size=float(bids[0][1]),
            best_ask_size=float(asks[0][1]),
        )

    # ------------------------------------------------------------------
    # Streaming (async only)
    # ------------------------------------------------------------------

    async def ob_stream(
        self,
        symbol: str,
        max_levels: int = 10,
        market: Optional[MarketType] = None,
        format: Literal["snapshot", "wide", "flat"] = "wide",
        speed: int = 100,
    ) -> Any:
        """Async iterator that yields live orderbook snapshots on every update.

        Uses Binance partial-depth streams (``@depth<N>@100ms``) to push the
        top N levels as a full snapshot on each update — no sync protocol
        needed. For full-depth streaming with sync, use the ``DepthCache``
        directly via ``book.depth_cache()``.

        Parameters
        ----------
        symbol : str
            Trading pair symbol (e.g. ``"BTCUSDT"``).
        max_levels : int
            Number of depth levels: 5, 10, or 20.  Default 10.
        market : str, optional
            Override market type.
        format : str
            Snapshot format: ``"snapshot"`` (per level per side),
            ``"wide"`` (per level both sides), ``"flat"`` (single row).
        speed : int
            Update speed in ms: 100 or 1000.

        Yields
        ------
        list[dict] or dict
            Orderbook snapshot on each update.

        Examples
        --------
        >>> async for update in book.ob_stream("BTCUSDT", max_levels=5, format="flat"):
        ...     print(update)
        """
        from binance_book.streams.depth_stream import iter_partial_depth

        valid_levels = [5, 10, 20]
        actual_levels = min(valid_levels, key=lambda x: abs(x - max_levels))

        mkt = market or self._config.market
        ws_url = BinanceBookConfig(
            testnet=self._config.testnet, market=mkt
        ).get_ws_base_url()

        async for msg in iter_partial_depth(ws_url, symbol, levels=actual_levels, speed=speed):
            ts = Timestamp.now_ms()
            bids = msg.get("bids", [])[:max_levels]
            asks = msg.get("asks", [])[:max_levels]
            n = min(len(bids), len(asks), max_levels)

            if format == "snapshot":
                rows: list[dict[str, Any]] = []
                for i in range(n):
                    rows.append({
                        "TIMESTAMP": ts, "SYMBOL": symbol, "SIDE": "BID",
                        "PRICE": float(bids[i][0]), "SIZE": float(bids[i][1]), "LEVEL": i + 1,
                    })
                for i in range(n):
                    rows.append({
                        "TIMESTAMP": ts, "SYMBOL": symbol, "SIDE": "ASK",
                        "PRICE": float(asks[i][0]), "SIZE": float(asks[i][1]), "LEVEL": i + 1,
                    })
                yield rows

            elif format == "flat":
                row: dict[str, Any] = {"TIMESTAMP": ts, "SYMBOL": symbol}
                for i in range(n):
                    lvl = i + 1
                    row[f"BID_PRICE{lvl}"] = float(bids[i][0])
                    row[f"BID_SIZE{lvl}"] = float(bids[i][1])
                    row[f"ASK_PRICE{lvl}"] = float(asks[i][0])
                    row[f"ASK_SIZE{lvl}"] = float(asks[i][1])
                yield row

            else:  # wide
                wide_rows: list[dict[str, Any]] = []
                for i in range(n):
                    wide_rows.append({
                        "TIMESTAMP": ts, "SYMBOL": symbol, "LEVEL": i + 1,
                        "BID_PRICE": float(bids[i][0]), "BID_SIZE": float(bids[i][1]),
                        "ASK_PRICE": float(asks[i][0]), "ASK_SIZE": float(asks[i][1]),
                    })
                yield wide_rows

    async def depth_cache(
        self,
        symbol: str,
        market: Optional[MarketType] = None,
        max_levels: int = 1000,
        ws_speed: int = 100,
        on_update: Optional[Any] = None,
    ) -> Any:
        """Create and start a full-depth DepthCache with the Binance sync protocol.

        Unlike ``ob_stream()`` which uses partial-depth streams (top 5/10/20),
        this creates a fully synchronized local orderbook using the diff-depth
        stream + REST snapshot protocol.  Handles update-ID sequencing, gap
        detection with auto-resnapshot, zero-quantity pruning, and bounded
        book size.

        This is the right choice when you need:
        - Full book depth (not just top 5/10/20)
        - Sequencing guarantees (every update applied in order)
        - Deep liquidity analysis

        Parameters
        ----------
        symbol : str
            Trading pair symbol (e.g. ``"BTCUSDT"``).
        market : str, optional
            Override market type.
        max_levels : int
            Maximum price levels to maintain per side. Default 1000.
        ws_speed : int
            WebSocket update speed in ms: 100 or 1000.
        on_update : callable, optional
            Push-model callback invoked on every book update.  Receives the
            ``DepthCache`` instance.  Can be sync or async.

        Returns
        -------
        DepthCache
            A started, synchronizing depth cache.  Call ``await cache.wait_synced()``
            before reading, and ``await cache.stop()`` when done.

        Examples
        --------
        >>> cache = await book.depth_cache("BTCUSDT")
        >>> await cache.wait_synced()
        >>> print(cache.get_best_bid(), cache.get_best_ask())
        >>> print(cache.get_bids(limit=50))  # full depth, not just top 5/10/20
        >>> await cache.stop()
        """
        from binance_book.book.depth_cache import DepthCache

        mkt = market or self._config.market
        client = self._get_rest_client(mkt)
        ws_url = BinanceBookConfig(
            testnet=self._config.testnet, market=mkt
        ).get_ws_base_url()

        cache = DepthCache(
            symbol=symbol,
            rest_client=client,
            market=mkt,
            max_levels=max_levels,
            ws_speed=ws_speed,
            on_update=on_update,
        )
        await cache.start(ws_url)
        return cache

    async def ob_stream_full(
        self,
        symbol: str,
        max_levels: int = 100,
        market: Optional[MarketType] = None,
        format: Literal["snapshot", "wide", "flat"] = "wide",
        on_update: Optional[Any] = None,
    ) -> Any:
        """Async iterator yielding full-depth orderbook snapshots via the sync protocol.

        Unlike ``ob_stream()`` (which uses partial-depth streams limited to
        5/10/20 levels), this uses a full ``DepthCache`` with the Binance
        diff-depth sync protocol — giving you sequenced, gap-detected,
        full-depth book snapshots.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        max_levels : int
            Max levels to include in each yielded snapshot.  The cache
            maintains up to 1000 levels internally; this controls output size.
        market : str, optional
            Override market type.
        format : str
            ``"snapshot"`` (per level per side), ``"wide"`` (paired),
            ``"flat"`` (single row).
        on_update : callable, optional
            Push-model callback on every update (in addition to yielding).

        Yields
        ------
        list[dict] or dict
            Orderbook snapshot after each update.
        """
        from binance_book.book.snapshot import (
            ob_snapshot_from_cache,
            ob_snapshot_wide_from_cache,
            ob_snapshot_flat_from_cache,
        )

        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        def _push(cache: Any) -> None:
            if on_update:
                try:
                    result = on_update(cache)
                    if asyncio.iscoroutine(result):
                        asyncio.get_event_loop().create_task(result)
                except Exception:
                    pass
            try:
                queue.put_nowait(cache)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(cache)

        cache = await self.depth_cache(
            symbol, market=market, on_update=_push,
        )

        try:
            await cache.wait_synced(timeout=30)

            while True:
                updated_cache = await queue.get()
                if format == "snapshot":
                    yield ob_snapshot_from_cache(updated_cache, max_levels)
                elif format == "flat":
                    yield ob_snapshot_flat_from_cache(updated_cache, max_levels)
                else:
                    yield ob_snapshot_wide_from_cache(updated_cache, max_levels)
        finally:
            await cache.stop()

    async def trade_stream(
        self,
        symbol: str,
        market: Optional[MarketType] = None,
    ) -> Any:
        """Async iterator that yields live trade events.

        Parameters
        ----------
        symbol : str
            Trading pair symbol.
        market : str, optional
            Override market type.

        Yields
        ------
        dict
            Trade event with TIMESTAMP, PRICE, SIZE, TRADE_ID, IS_BUYER_MAKER.
        """
        from binance_book.streams.trade_stream import iter_trades

        mkt = market or self._config.market
        ws_url = BinanceBookConfig(
            testnet=self._config.testnet, market=mkt
        ).get_ws_base_url()

        async for trade in iter_trades(ws_url, symbol):
            yield trade.model_dump()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_depth(self, symbol: str, limit: int, market: MarketType) -> dict:
        """Fetch raw depth data from REST API."""
        client = self._get_rest_client(market)
        if market == "spot":
            endpoint = ep.SPOT_DEPTH
            weight = ep.depth_weight(limit, "spot")
        elif market == "futures_usdt":
            endpoint = ep.FUTURES_USDT_DEPTH
            weight = ep.depth_weight(limit, "futures_usdt")
        else:
            endpoint = ep.FUTURES_COIN_DEPTH
            weight = ep.depth_weight(limit, "futures_coin")

        api_limit = self._snap_limit(limit)
        return await client.get(
            endpoint,
            params={"symbol": symbol, "limit": api_limit},
            weight_override=weight,
        )

    @staticmethod
    def _snap_limit(requested: int) -> int:
        """Snap a requested depth limit to a valid Binance API limit."""
        valid = [5, 10, 20, 50, 100, 500, 1000, 5000]
        for v in valid:
            if requested <= v:
                return v
        return 5000

    def _get_rest_client(self, market: MarketType) -> BinanceRestClient:
        """Get or create a REST client for the given market type."""
        cfg = BinanceBookConfig(
            api_key=self._config.api_key,
            api_secret=self._config.api_secret,
            testnet=self._config.testnet,
            market=market,
            timeout=self._config.timeout,
        )
        if market == self._config.market:
            return self._rest
        return BinanceRestClient(
            base_url=cfg.get_rest_base_url(),
            api_key=self._config.api_key,
            api_secret=self._config.api_secret,
            timeout=self._config.timeout,
        )

    def _format_output(self, data: list[dict], format: OutputFormat, label: str = "") -> Any:
        """Format output data according to the requested format."""
        if format == "json":
            return data if len(data) != 1 else data[0]
        elif format == "csv":
            return _to_csv(data)
        elif format == "markdown":
            return _to_markdown(data, label)
        elif format == "narrative":
            return _to_narrative(data, label)
        elif format == "dataframe":
            return _to_dataframe(data)
        return data


# ---------------------------------------------------------------------------
# Filter application helper
# ---------------------------------------------------------------------------

def _apply_filters(
    rows: list[dict[str, Any]],
    clean: Union[bool, list[str]],
    annotate: bool,
    filter_config: FilterConfig,
) -> list[dict[str, Any]]:
    """Apply data cleaning filters and/or annotations to orderbook rows.

    Parameters
    ----------
    rows : list[dict]
        Orderbook rows in any representation.
    clean : bool or list[str]
        True for all default filters, or a list of filter names.
    annotate : bool
        If True, add quality columns instead of removing rows.
    filter_config : FilterConfig
        Default filter configuration.

    Returns
    -------
    list[dict]
        Filtered/annotated rows.
    """
    if not clean and not annotate:
        return rows

    from binance_book.filters.dust import annotate_dust, filter_dust
    from binance_book.filters.stale import annotate_stale, filter_stale
    from binance_book.filters.gap import annotate_gaps, filter_gap
    from binance_book.filters.anomaly import annotate_anomalies, filter_anomalies

    if isinstance(clean, bool):
        active = ["dust", "stale", "gap", "anomaly"] if clean else []
    else:
        active = list(clean)

    if annotate:
        rows = annotate_dust(rows, min_notional_usd=filter_config.dust_notional_usd)
        rows = annotate_gaps(rows)
        rows = annotate_anomalies(rows, sigma=filter_config.anomaly_sigma)
        rows = annotate_stale(rows, staleness_ms=filter_config.staleness_ms)
        return rows

    if "dust" in active:
        rows = filter_dust(rows, min_notional_usd=filter_config.dust_notional_usd)
    if "stale" in active and filter_config.remove_stale:
        rows = filter_stale(rows, staleness_ms=filter_config.staleness_ms)
    if "gap" in active and filter_config.remove_sparse:
        rows = filter_gap(rows, max_gap_ticks=filter_config.sparse_max_gap_ticks)
    if "anomaly" in active:
        rows = filter_anomalies(rows, sigma=filter_config.anomaly_sigma)

    return rows


# ---------------------------------------------------------------------------
# Sync helper
# ---------------------------------------------------------------------------

_shared_loop: asyncio.AbstractEventLoop | None = None


def _get_shared_loop() -> asyncio.AbstractEventLoop:
    """Get or create a shared event loop for sync calls.

    Unlike ``asyncio.run()``, this keeps the loop alive between calls so that
    ``aiohttp.ClientSession`` objects are not invalidated.
    """
    global _shared_loop
    if _shared_loop is None or _shared_loop.is_closed():
        _shared_loop = asyncio.new_event_loop()
    return _shared_loop


def _run_sync(coro: Any) -> Any:
    """Run an async coroutine synchronously.

    Uses a persistent shared event loop so that aiohttp sessions survive
    across multiple sync method calls.  If an event loop is already running
    (e.g. in Jupyter), falls back to nest_asyncio.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        try:
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        except ImportError:
            raise RuntimeError(
                "An event loop is already running. Either use `await` with async methods, "
                "or install nest_asyncio: pip install nest_asyncio"
            )

    shared = _get_shared_loop()
    return shared.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Output formatters (basic — Phase 4 adds output/ module for full support)
# ---------------------------------------------------------------------------

def _to_csv(data: list[dict]) -> str:
    """Convert list of dicts to CSV string."""
    if not data:
        return ""
    headers = list(data[0].keys())
    lines = [",".join(str(h) for h in headers)]
    for row in data:
        lines.append(",".join(str(row.get(h, "")) for h in headers))
    return "\n".join(lines)


def _to_markdown(data: list[dict], label: str = "") -> str:
    """Convert list of dicts to a markdown table."""
    if not data:
        return f"*{label}: No data*" if label else "*No data*"
    headers = list(data[0].keys())
    lines: list[str] = []
    if label:
        lines.append(f"**{label}**\n")
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in data:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def _to_narrative(data: list[dict], label: str = "") -> str:
    """Convert orderbook data to a natural language summary for LLMs."""
    if not data:
        return f"{label}: No data available."

    first = data[0]
    symbol = first.get("SYMBOL", label.split()[0] if label else "")

    if "BID_PRICE" in first and "ASK_PRICE" in first and "LEVEL" in first:
        bp = first["BID_PRICE"]
        bs = first["BID_SIZE"]
        ap = first["ASK_PRICE"]
        as_ = first["ASK_SIZE"]
        spread = ap - bp
        mid = (ap + bp) / 2
        spread_bps = (spread / mid * 10000) if mid else 0
        bid_depth = sum(r.get("BID_SIZE", 0) for r in data)
        ask_depth = sum(r.get("ASK_SIZE", 0) for r in data)
        bid_notional = sum(r.get("BID_PRICE", 0) * r.get("BID_SIZE", 0) for r in data)
        ask_notional = sum(r.get("ASK_PRICE", 0) * r.get("ASK_SIZE", 0) for r in data)
        imb = (bid_depth - ask_depth) / (bid_depth + ask_depth) if (bid_depth + ask_depth) else 0
        return (
            f"{symbol} orderbook ({len(data)} levels): "
            f"bid ${bp:,.2f} ({bs:.4f}) / ask ${ap:,.2f} ({as_:.4f}), "
            f"spread ${spread:.2f} ({spread_bps:.2f} bps), mid ${mid:,.2f}, "
            f"bid depth {bid_depth:.4f} (${bid_notional:,.0f}) / "
            f"ask depth {ask_depth:.4f} (${ask_notional:,.0f}), "
            f"imbalance {imb:+.3f}"
        )

    if "BID_PRICE1" in first:
        bp1 = first.get("BID_PRICE1", 0)
        ap1 = first.get("ASK_PRICE1", 0)
        spread = ap1 - bp1
        mid = (ap1 + bp1) / 2
        spread_bps = (spread / mid * 10000) if mid else 0
        n_levels = sum(1 for k in first if k.startswith("BID_PRICE"))
        return (
            f"{symbol} orderbook ({n_levels} levels flat): "
            f"best bid ${bp1:,.2f} / best ask ${ap1:,.2f}, "
            f"spread ${spread:.2f} ({spread_bps:.2f} bps)"
        )

    if "SIDE" in first:
        bids = [r for r in data if str(r.get("SIDE", "")).replace("Side.", "") == "BID"]
        asks = [r for r in data if str(r.get("SIDE", "")).replace("Side.", "") == "ASK"]
        bid_depth = sum(r.get("SIZE", 0) for r in bids)
        ask_depth = sum(r.get("SIZE", 0) for r in asks)
        best_bid = bids[0]["PRICE"] if bids else 0
        best_ask = asks[0]["PRICE"] if asks else 0
        spread = best_ask - best_bid
        mid = (best_ask + best_bid) / 2
        spread_bps = (spread / mid * 10000) if mid else 0
        return (
            f"{symbol} orderbook ({len(bids)} bid + {len(asks)} ask levels): "
            f"best bid ${best_bid:,.2f} / best ask ${best_ask:,.2f}, "
            f"spread ${spread:.2f} ({spread_bps:.2f} bps), "
            f"bid depth {bid_depth:.4f} / ask depth {ask_depth:.4f}"
        )

    return f"{label}: {len(data)} records"


def _to_dataframe(data: list[dict]) -> Any:
    """Convert list of dicts to pandas DataFrame (requires optional dep)."""
    try:
        import pandas as pd
    except ImportError:
        raise DependencyError(
            "pandas is required for format='dataframe'. "
            "Install it with: pip install binance-book[dataframe]"
        )
    return pd.DataFrame(data)
