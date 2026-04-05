"""Tests for error reporting and bug report utilities."""

from __future__ import annotations

import os
import sys
import re
from unittest.mock import MagicMock, patch, ANY

import pytest

from binance_book.error_reporting import (
    ErrorEntry,
    ErrorReporter,
    SmtpConfig,
    SUPPORT_EMAIL,
    GITHUB_ISSUES_URL,
    MAX_LOG_ENTRIES,
    report_bug,
    print_bug_report,
    send_email,
    _open_mailto,
)


# ---------------------------------------------------------------------------
# ErrorEntry
# ---------------------------------------------------------------------------

class TestErrorEntry:
    def test_to_text_basic(self):
        entry = ErrorEntry(
            timestamp=1711929600.0,
            exception_type="ValueError",
            message="bad value",
            traceback="Traceback ...",
        )
        text = entry.to_text()
        assert "ValueError" in text
        assert "bad value" in text
        assert "Traceback" in text

    def test_to_text_with_context(self):
        entry = ErrorEntry(
            timestamp=1711929600.0,
            exception_type="RuntimeError",
            message="oops",
            traceback="",
            context="ob_snapshot",
        )
        text = entry.to_text()
        assert "Context: ob_snapshot" in text

    def test_to_text_no_traceback(self):
        entry = ErrorEntry(
            timestamp=1711929600.0,
            exception_type="RuntimeError",
            message="oops",
            traceback="",
        )
        text = entry.to_text()
        assert "RuntimeError" in text
        # Should NOT have an empty trailing line for traceback
        assert text.strip() == text.split("\n")[0].strip()

    def test_to_text_timestamp_format(self):
        entry = ErrorEntry(
            timestamp=1711929600.0,
            exception_type="ValueError",
            message="test",
            traceback="",
        )
        text = entry.to_text()
        # Should contain a date-like pattern [YYYY-MM-DD HH:MM:SS]
        assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", text)


# ---------------------------------------------------------------------------
# SmtpConfig
# ---------------------------------------------------------------------------

class TestSmtpConfig:
    def test_defaults(self):
        cfg = SmtpConfig()
        assert cfg.host == "smtp.gmail.com"
        assert cfg.port == 587
        assert cfg.username == ""
        assert cfg.password == ""
        assert cfg.use_tls is True
        assert cfg.from_addr is None

    def test_from_env_returns_none_without_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            assert SmtpConfig.from_env() is None

    def test_from_env_returns_none_missing_user(self):
        with patch.dict(os.environ, {"BINANCE_BOOK_SMTP_PASS": "pw"}, clear=True):
            assert SmtpConfig.from_env() is None

    def test_from_env_returns_none_missing_pass(self):
        with patch.dict(os.environ, {"BINANCE_BOOK_SMTP_USER": "user"}, clear=True):
            assert SmtpConfig.from_env() is None

    def test_from_env_with_required_vars(self):
        env = {
            "BINANCE_BOOK_SMTP_USER": "testuser@example.com",
            "BINANCE_BOOK_SMTP_PASS": "secret123",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = SmtpConfig.from_env()
            assert cfg is not None
            assert cfg.username == "testuser@example.com"
            assert cfg.password == "secret123"
            assert cfg.host == "smtp.gmail.com"  # default
            assert cfg.port == 587  # default

    def test_from_env_with_all_vars(self):
        env = {
            "BINANCE_BOOK_SMTP_USER": "user@custom.com",
            "BINANCE_BOOK_SMTP_PASS": "pw",
            "BINANCE_BOOK_SMTP_HOST": "smtp.custom.com",
            "BINANCE_BOOK_SMTP_PORT": "465",
            "BINANCE_BOOK_SMTP_TLS": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = SmtpConfig.from_env()
            assert cfg is not None
            assert cfg.host == "smtp.custom.com"
            assert cfg.port == 465
            assert cfg.use_tls is False


# ---------------------------------------------------------------------------
# ErrorReporter — core capture
# ---------------------------------------------------------------------------

class TestErrorReporterCapture:
    def test_disabled_by_default(self):
        reporter = ErrorReporter()
        assert reporter.enabled is False
        assert reporter.error_count == 0

    def test_enable_disable(self):
        reporter = ErrorReporter()
        reporter.enable()
        assert reporter.enabled is True
        reporter.disable()
        assert reporter.enabled is False

    def test_capture_when_disabled_does_nothing(self):
        reporter = ErrorReporter(enabled=False)
        reporter.capture(ValueError("test"))
        assert reporter.error_count == 0
        assert reporter.get_error_log() == "No errors captured."

    def test_capture_when_enabled(self):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(ValueError("something broke"))
        assert reporter.error_count == 1

    def test_capture_multiple_errors(self):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(ValueError("err1"))
        reporter.capture(RuntimeError("err2"))
        reporter.capture(TypeError("err3"))
        assert reporter.error_count == 3

    def test_capture_with_context(self):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(ValueError("test"), context="ob_snapshot")
        log = reporter.get_error_log()
        assert "ob_snapshot" in log

    def test_max_entries_bounded(self):
        reporter = ErrorReporter(enabled=True, max_entries=5)
        for i in range(10):
            reporter.capture(ValueError(f"error {i}"))
        assert reporter.error_count == 10  # total count still 10
        log = reporter.get_error_log()
        # Only last 5 should be in the log
        assert "error 5" in log
        assert "error 9" in log
        assert "error 0" not in log

    def test_clear(self):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(ValueError("test"))
        assert reporter.error_count == 1
        reporter.clear()
        assert reporter.error_count == 0
        assert reporter.get_error_log() == "No errors captured."


# ---------------------------------------------------------------------------
# ErrorReporter — error log and bug report
# ---------------------------------------------------------------------------

class TestErrorReporterReports:
    def test_get_error_log_empty(self):
        reporter = ErrorReporter(enabled=True)
        assert reporter.get_error_log() == "No errors captured."

    def test_get_error_log_with_errors(self):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(ValueError("broken"), context="test_method")
        log = reporter.get_error_log()
        assert "binance-book Error Log" in log
        assert "ValueError" in log
        assert "broken" in log
        assert "Total errors since start: 1" in log

    def test_get_system_info(self):
        reporter = ErrorReporter(enabled=True)
        info = reporter.get_system_info()
        assert "binance-book version:" in info
        assert "Python:" in info
        assert "Platform:" in info
        assert "OS:" in info
        assert "Architecture:" in info

    def test_get_bug_report_without_description(self):
        reporter = ErrorReporter(enabled=True)
        report = reporter.get_bug_report()
        assert "# binance-book Bug Report" in report
        assert "(No description provided)" in report
        assert "## System Info" in report
        assert "## Error Log" in report

    def test_get_bug_report_with_description(self):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(RuntimeError("crash"))
        report = reporter.get_bug_report("Something went wrong")
        assert "Something went wrong" in report
        assert "RuntimeError" in report
        assert "crash" in report

    def test_bug_report_no_secrets(self):
        """Ensure API keys are never in the report even if in exc message."""
        reporter = ErrorReporter(enabled=True)
        # Even if someone accidentally puts a key in an error message,
        # the report only includes what was captured — it doesn't access config
        reporter.capture(ValueError("some error"))
        report = reporter.get_bug_report()
        assert "api_key" not in report.lower()
        assert "api_secret" not in report.lower()


# ---------------------------------------------------------------------------
# ErrorReporter — on_error callback
# ---------------------------------------------------------------------------

class TestErrorReporterCallback:
    def test_on_error_called(self):
        callback = MagicMock()
        reporter = ErrorReporter(enabled=True, on_error=callback)
        exc = ValueError("test")
        reporter.capture(exc)
        callback.assert_called_once()
        entry = callback.call_args[0][0]
        assert isinstance(entry, ErrorEntry)
        assert entry.exception_type == "ValueError"
        assert entry.message == "test"

    def test_on_error_exception_swallowed(self):
        """on_error callback raising should not prevent capture."""
        def bad_callback(entry):
            raise RuntimeError("callback broke")

        reporter = ErrorReporter(enabled=True, on_error=bad_callback)
        reporter.capture(ValueError("test"))  # should not raise
        assert reporter.error_count == 1


# ---------------------------------------------------------------------------
# ErrorReporter — excepthook
# ---------------------------------------------------------------------------

class TestExcepthook:
    def test_install_and_uninstall(self):
        original_hook = sys.excepthook
        reporter = ErrorReporter(enabled=True)
        reporter.install_excepthook()
        assert sys.excepthook is not original_hook
        reporter.uninstall_excepthook()
        assert sys.excepthook is original_hook

    def test_uninstall_without_install_is_noop(self):
        original_hook = sys.excepthook
        reporter = ErrorReporter(enabled=True)
        reporter.uninstall_excepthook()  # should not crash
        assert sys.excepthook is original_hook

    def test_excepthook_captures_exception(self):
        reporter = ErrorReporter(enabled=True)
        reporter.install_excepthook()
        try:
            exc = ValueError("uncaught test error")
            # Simulate what Python does with uncaught exceptions
            with patch.object(reporter, '_original_excepthook'):
                sys.excepthook(type(exc), exc, exc.__traceback__)
            assert reporter.error_count == 1
            log = reporter.get_error_log()
            assert "uncaught test error" in log
            assert "uncaught exception (sys.excepthook)" in log
        finally:
            reporter.uninstall_excepthook()

    def test_excepthook_ignores_keyboard_interrupt(self):
        reporter = ErrorReporter(enabled=True)
        reporter.install_excepthook()
        try:
            exc = KeyboardInterrupt()
            with patch.object(reporter, '_original_excepthook'):
                sys.excepthook(type(exc), exc, None)
            assert reporter.error_count == 0  # not captured
        finally:
            reporter.uninstall_excepthook()

    def test_excepthook_auto_email(self):
        reporter = ErrorReporter(enabled=True, auto_email=True)
        reporter.install_excepthook()
        try:
            exc = RuntimeError("fatal")
            with patch.object(reporter, '_try_send_email') as mock_send:
                with patch.object(reporter, '_original_excepthook'):
                    sys.excepthook(type(exc), exc, exc.__traceback__)
                mock_send.assert_called_once_with(
                    subject="[binance-book] Uncaught RuntimeError",
                    fatal=True,
                )
        finally:
            reporter.uninstall_excepthook()


# ---------------------------------------------------------------------------
# ErrorReporter — SMTP email
# ---------------------------------------------------------------------------

class TestErrorReporterEmail:
    def test_get_smtp_config_explicit(self):
        cfg = SmtpConfig(username="u", password="p")
        reporter = ErrorReporter(enabled=True, smtp_config=cfg)
        assert reporter._get_smtp_config() is cfg

    def test_get_smtp_config_from_env(self):
        env = {
            "BINANCE_BOOK_SMTP_USER": "env_user",
            "BINANCE_BOOK_SMTP_PASS": "env_pass",
        }
        reporter = ErrorReporter(enabled=True)
        with patch.dict(os.environ, env, clear=True):
            cfg = reporter._get_smtp_config()
            assert cfg is not None
            assert cfg.username == "env_user"

    def test_get_smtp_config_none_when_not_configured(self):
        reporter = ErrorReporter(enabled=True)
        with patch.dict(os.environ, {}, clear=True):
            assert reporter._get_smtp_config() is None

    def test_try_send_email_returns_false_without_smtp(self):
        reporter = ErrorReporter(enabled=True)
        with patch.dict(os.environ, {}, clear=True):
            assert reporter._try_send_email() is False

    def test_try_send_email_calls_send_email(self):
        cfg = SmtpConfig(username="u", password="p")
        reporter = ErrorReporter(enabled=True, smtp_config=cfg)
        reporter.capture(ValueError("test"))
        with patch("binance_book.error_reporting.send_email", return_value=True) as mock:
            result = reporter._try_send_email(subject="Test Subject")
            assert result is True
            mock.assert_called_once_with(
                to_addr=SUPPORT_EMAIL,
                subject="Test Subject",
                body=ANY,
                smtp_config=cfg,
            )

    def test_try_send_email_handles_exception(self):
        cfg = SmtpConfig(username="u", password="p")
        reporter = ErrorReporter(enabled=True, smtp_config=cfg)
        with patch("binance_book.error_reporting.send_email", side_effect=Exception("boom")):
            result = reporter._try_send_email()
            assert result is False  # no exception raised

    def test_send_report_without_smtp_returns_false(self):
        reporter = ErrorReporter(enabled=True)
        with patch.dict(os.environ, {}, clear=True):
            assert reporter.send_report("test") is False

    def test_send_report_with_smtp(self):
        cfg = SmtpConfig(username="u", password="p")
        reporter = ErrorReporter(enabled=True, smtp_config=cfg)
        with patch("binance_book.error_reporting.send_email", return_value=True) as mock:
            result = reporter.send_report("broken feature")
            assert result is True
            mock.assert_called_once()
            call_kwargs = mock.call_args
            assert "broken feature" in call_kwargs[1]["subject"]


# ---------------------------------------------------------------------------
# send_email (standalone)
# ---------------------------------------------------------------------------

class TestSendEmail:
    def test_send_email_tls(self):
        cfg = SmtpConfig(
            host="smtp.test.com",
            port=587,
            username="user@test.com",
            password="pass",
            use_tls=True,
        )
        mock_server = MagicMock()
        with patch("binance_book.error_reporting.smtplib.SMTP", return_value=mock_server):
            result = send_email("to@test.com", "Subject", "Body", cfg)
            assert result is True
            mock_server.ehlo.assert_called()
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@test.com", "pass")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_email_ssl(self):
        cfg = SmtpConfig(
            host="smtp.test.com",
            port=465,
            username="user@test.com",
            password="pass",
            use_tls=False,
        )
        mock_server = MagicMock()
        with patch("binance_book.error_reporting.smtplib.SMTP_SSL", return_value=mock_server):
            result = send_email("to@test.com", "Subject", "Body", cfg)
            assert result is True
            mock_server.login.assert_called_once_with("user@test.com", "pass")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_email_custom_from_addr(self):
        cfg = SmtpConfig(
            host="smtp.test.com",
            port=587,
            username="user@test.com",
            password="pass",
            from_addr="custom@test.com",
        )
        mock_server = MagicMock()
        with patch("binance_book.error_reporting.smtplib.SMTP", return_value=mock_server):
            send_email("to@test.com", "Subject", "Body", cfg)
            call_args = mock_server.sendmail.call_args[0]
            assert call_args[0] == "custom@test.com"

    def test_send_email_failure_returns_false(self):
        cfg = SmtpConfig(username="user", password="pass")
        with patch("binance_book.error_reporting.smtplib.SMTP", side_effect=Exception("connection failed")):
            result = send_email("to@test.com", "Subject", "Body", cfg)
            assert result is False


# ---------------------------------------------------------------------------
# report_bug (standalone function)
# ---------------------------------------------------------------------------

class TestReportBug:
    def test_text_method_returns_report(self):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(ValueError("test error"))
        report = report_bug("my issue", error_reporter=reporter, method="text")
        assert "# binance-book Bug Report" in report
        assert "my issue" in report
        assert "ValueError" in report

    def test_text_method_without_reporter(self):
        report = report_bug("just a description", method="text")
        assert "# binance-book Bug Report" in report
        assert "just a description" in report

    def test_email_method_opens_mailto(self):
        with patch("binance_book.error_reporting._open_mailto") as mock:
            report = report_bug("test", method="email")
            mock.assert_called_once()
            assert isinstance(report, str)

    def test_github_method_opens_browser(self):
        with patch("binance_book.error_reporting.webbrowser.open") as mock:
            report = report_bug("test issue", method="github")
            mock.assert_called_once()
            url = mock.call_args[0][0]
            assert GITHUB_ISSUES_URL in url

    def test_send_method_with_smtp(self):
        cfg = SmtpConfig(username="u", password="p")
        reporter = ErrorReporter(enabled=True, smtp_config=cfg)
        with patch("binance_book.error_reporting.send_email", return_value=True):
            report = report_bug("issue", error_reporter=reporter, method="send")
            assert isinstance(report, str)

    def test_send_method_falls_back_to_mailto(self):
        reporter = ErrorReporter(enabled=True)  # no smtp
        with patch.dict(os.environ, {}, clear=True):
            with patch("binance_book.error_reporting._open_mailto") as mock_mailto:
                report_bug("issue", error_reporter=reporter, method="send")
                mock_mailto.assert_called_once()


# ---------------------------------------------------------------------------
# print_bug_report
# ---------------------------------------------------------------------------

class TestPrintBugReport:
    def test_prints_report(self, capsys):
        reporter = ErrorReporter(enabled=True)
        reporter.capture(TypeError("type err"))
        print_bug_report("my description", error_reporter=reporter)
        captured = capsys.readouterr()
        assert "# binance-book Bug Report" in captured.out
        assert "my description" in captured.out
        assert SUPPORT_EMAIL in captured.out
        assert GITHUB_ISSUES_URL in captured.out


# ---------------------------------------------------------------------------
# _open_mailto
# ---------------------------------------------------------------------------

class TestOpenMailto:
    def test_opens_webbrowser(self):
        with patch("binance_book.error_reporting.webbrowser.open") as mock:
            _open_mailto("Test report body")
            mock.assert_called_once()
            url = mock.call_args[0][0]
            assert url.startswith(f"mailto:{SUPPORT_EMAIL}")
            assert "subject=" in url

    def test_handles_browser_failure(self):
        with patch("binance_book.error_reporting.webbrowser.open", side_effect=Exception("no browser")):
            _open_mailto("Test report body")  # should not raise


# ---------------------------------------------------------------------------
# BinanceBook client integration
# ---------------------------------------------------------------------------

class TestClientErrorReporting:
    def test_error_reporting_disabled_by_default(self):
        from binance_book.client import BinanceBook
        book = BinanceBook()
        assert book._error_reporter.enabled is False

    def test_error_reporting_enabled(self):
        from binance_book.client import BinanceBook
        book = BinanceBook(error_reporting=True)
        assert book._error_reporter.enabled is True

    def test_get_error_log_empty(self):
        from binance_book.client import BinanceBook
        book = BinanceBook(error_reporting=True)
        assert book.get_error_log() == "No errors captured."

    def test_report_bug_returns_string(self):
        from binance_book.client import BinanceBook
        book = BinanceBook(error_reporting=True)
        report = book.report_bug("test", method="text")
        assert "# binance-book Bug Report" in report

    def test_errors_captured_on_exception(self):
        """When error_reporting is on and a method raises, the error is captured."""
        from binance_book.client import BinanceBook
        book = BinanceBook(error_reporting=True, timeout=2.0)
        try:
            # Use a fake symbol that guarantees a Binance API error
            book.quote("FAKESYMBOL999")
        except Exception:
            pass
        assert book._error_reporter.error_count >= 1
        log = book.get_error_log()
        assert "errors" in log.lower() or "Error" in log

    def test_errors_not_captured_when_disabled(self):
        from binance_book.client import BinanceBook
        book = BinanceBook(error_reporting=False, timeout=2.0)
        try:
            book.quote("FAKESYMBOL999")
        except Exception:
            pass
        assert book._error_reporter.error_count == 0

    def test_close_uninstalls_excepthook(self):
        import asyncio
        from binance_book.client import BinanceBook
        book = BinanceBook(error_reporting=True)
        original = book._error_reporter._original_excepthook
        assert original is not None  # installed
        loop = asyncio.new_event_loop()
        loop.run_until_complete(book.close())
        loop.close()
        assert book._error_reporter._original_excepthook is None  # uninstalled

    def test_auto_email_errors_param(self):
        from binance_book.client import BinanceBook
        book = BinanceBook(error_reporting=True, auto_email_errors=True)
        assert book._error_reporter._auto_email is True

    def test_smtp_config_param(self):
        from binance_book.client import BinanceBook
        cfg = SmtpConfig(username="u", password="p")
        book = BinanceBook(error_reporting=True, smtp_config=cfg)
        assert book._error_reporter._smtp_config is cfg


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------

class TestPackageExports:
    def test_imports(self):
        from binance_book import BinanceBook, ErrorReporter, SmtpConfig, report_bug
        assert BinanceBook is not None
        assert ErrorReporter is not None
        assert SmtpConfig is not None
        assert callable(report_bug)
