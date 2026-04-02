"""Shared test fixtures — mock Binance API responses."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Mock Binance REST response data
# ---------------------------------------------------------------------------

MOCK_DEPTH = {
    "lastUpdateId": 91286042658,
    "bids": [
        ["68225.00000000", "1.50000000"],
        ["68224.99000000", "0.30000000"],
        ["68224.50000000", "0.80000000"],
        ["68224.00000000", "2.10000000"],
        ["68223.50000000", "0.05000000"],
        ["68223.00000000", "0.00008000"],  # dust
        ["68222.00000000", "0.00003000"],  # dust
        ["68221.00000000", "5.00000000"],  # outlier
        ["68220.00000000", "0.10000000"],
        ["68219.00000000", "0.20000000"],
    ],
    "asks": [
        ["68225.01000000", "0.40000000"],
        ["68225.50000000", "0.20000000"],
        ["68226.00000000", "0.10000000"],
        ["68226.50000000", "1.80000000"],
        ["68227.00000000", "0.00006000"],  # dust
        ["68228.00000000", "0.00002000"],  # dust
        ["68229.00000000", "0.50000000"],
        ["68230.00000000", "3.50000000"],  # outlier
        ["68231.00000000", "0.15000000"],
        ["68232.00000000", "0.25000000"],
    ],
}

MOCK_TRADES = [
    {
        "id": 6167847072,
        "price": "68225.00000000",
        "qty": "0.50000000",
        "quoteQty": "34112.50000000",
        "time": 1711929600000,
        "isBuyerMaker": False,
        "isBestMatch": True,
    },
    {
        "id": 6167847073,
        "price": "68225.01000000",
        "qty": "0.10000000",
        "quoteQty": "6822.50100000",
        "time": 1711929600100,
        "isBuyerMaker": True,
        "isBestMatch": True,
    },
    {
        "id": 6167847074,
        "price": "68226.00000000",
        "qty": "0.30000000",
        "quoteQty": "20467.80000000",
        "time": 1711929600200,
        "isBuyerMaker": False,
        "isBestMatch": True,
    },
]

MOCK_KLINES = [
    [
        1711929600000, "68100.00", "68300.00", "68050.00", "68225.00",
        "1234.50", 1711929659999, "84200000.00", 45000,
        "600.00", "40900000.00", "0",
    ],
    [
        1711929660000, "68225.00", "68350.00", "68200.00", "68300.00",
        "900.00", 1711929719999, "61470000.00", 32000,
        "450.00", "30735000.00", "0",
    ],
]

MOCK_BOOK_TICKER = {
    "symbol": "BTCUSDT",
    "bidPrice": "68225.00000000",
    "bidQty": "1.50000000",
    "askPrice": "68225.01000000",
    "askQty": "0.40000000",
}

MOCK_TICKER_24HR = {
    "symbol": "BTCUSDT",
    "priceChange": "725.00000000",
    "priceChangePercent": "1.07",
    "weightedAvgPrice": "67850.00000000",
    "lastPrice": "68225.00000000",
    "volume": "25000.00000000",
    "quoteVolume": "1700000000.00000000",
    "openPrice": "67500.00000000",
    "highPrice": "69000.00000000",
    "lowPrice": "67200.00000000",
    "count": 1200000,
    "closeTime": 1711929600000,
}

MOCK_EXCHANGE_INFO = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "status": "TRADING",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 8,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00001000", "minQty": "0.00001000", "maxQty": "9000.00000000"},
                {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
            ],
        },
        {
            "symbol": "ETHUSDT",
            "baseAsset": "ETH",
            "quoteAsset": "USDT",
            "status": "TRADING",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 8,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00010000", "minQty": "0.00010000", "maxQty": "100000.00000000"},
                {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
            ],
        },
        {
            "symbol": "BNBBTC",
            "baseAsset": "BNB",
            "quoteAsset": "BTC",
            "status": "TRADING",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 8,
            "filters": [],
        },
    ],
}


# ---------------------------------------------------------------------------
# Depth update WS events (for depth cache tests)
# ---------------------------------------------------------------------------

MOCK_DEPTH_UPDATE_1 = {
    "e": "depthUpdate",
    "E": 1711929600100,
    "s": "BTCUSDT",
    "U": 91286042659,
    "u": 91286042661,
    "b": [["68225.00000000", "1.60000000"], ["68224.00000000", "0.00000000"]],
    "a": [["68225.01000000", "0.35000000"], ["68233.00000000", "0.50000000"]],
}

MOCK_DEPTH_UPDATE_2 = {
    "e": "depthUpdate",
    "E": 1711929600200,
    "s": "BTCUSDT",
    "U": 91286042662,
    "u": 91286042664,
    "b": [["68225.50000000", "0.70000000"]],
    "a": [["68225.01000000", "0.00000000"]],
}
