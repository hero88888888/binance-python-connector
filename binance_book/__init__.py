"""binance-book: The best agentic AI wrapper for Binance orderbook data."""

from binance_book.client import BinanceBook
from binance_book.error_reporting import ErrorReporter, SmtpConfig, report_bug
from binance_book.telemetry import TelemetryCollector

__all__ = ["BinanceBook", "ErrorReporter", "SmtpConfig", "report_bug", "TelemetryCollector"]
__version__ = "0.1.1"
