"""binance-book: The best agentic AI wrapper for Binance orderbook data."""

from binance_book.client import BinanceBook
from binance_book.error_reporting import ErrorReporter, SmtpConfig, report_bug

__all__ = ["BinanceBook", "ErrorReporter", "SmtpConfig", "report_bug"]
__version__ = "0.1.1"
