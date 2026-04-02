"""Error reporting and bug report utilities.

Provides opt-in error capture, automatic email reporting of uncaught
exceptions, and easy manual bug reporting.

Privacy: Reports never include API keys, secrets, or account data. Only
exception traces, library version, Python version, and OS info are collected.

Automatic email sending requires an SMTP configuration. If SMTP is not
configured, the fallback is ``mailto:`` links or printed reports.
"""

from __future__ import annotations

import logging
import os
import platform
import smtplib
import ssl
import sys
import textwrap
import time
import traceback
import urllib.parse
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = "pr8wn.bot@gmail.com"
GITHUB_ISSUES_URL = "https://github.com/hero88888888/binance-python-connector/issues/new"
MAX_LOG_ENTRIES = 200


@dataclass
class SmtpConfig:
    """SMTP configuration for sending error reports via email.

    Parameters
    ----------
    host : str
        SMTP server hostname (e.g. ``"smtp.gmail.com"``).
    port : int
        SMTP server port (587 for TLS, 465 for SSL).
    username : str
        SMTP login username (usually the email address).
    password : str
        SMTP login password or app password.
    use_tls : bool
        If True, use STARTTLS (port 587). If False, use SSL (port 465).
    from_addr : str, optional
        Sender address. Defaults to ``username``.
    """

    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_addr: Optional[str] = None

    @classmethod
    def from_env(cls) -> Optional["SmtpConfig"]:
        """Create SmtpConfig from environment variables.

        Looks for ``BINANCE_BOOK_SMTP_HOST``, ``BINANCE_BOOK_SMTP_PORT``,
        ``BINANCE_BOOK_SMTP_USER``, ``BINANCE_BOOK_SMTP_PASS``.
        Returns None if the required variables are not set.
        """
        user = os.environ.get("BINANCE_BOOK_SMTP_USER", "")
        password = os.environ.get("BINANCE_BOOK_SMTP_PASS", "")
        if not user or not password:
            return None
        return cls(
            host=os.environ.get("BINANCE_BOOK_SMTP_HOST", "smtp.gmail.com"),
            port=int(os.environ.get("BINANCE_BOOK_SMTP_PORT", "587")),
            username=user,
            password=password,
            use_tls=os.environ.get("BINANCE_BOOK_SMTP_TLS", "true").lower() in ("true", "1", "yes"),
        )


@dataclass
class ErrorEntry:
    """A captured error with context."""

    timestamp: float
    exception_type: str
    message: str
    traceback: str
    context: str = ""

    def to_text(self) -> str:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        lines = [
            f"[{ts}] {self.exception_type}: {self.message}",
        ]
        if self.context:
            lines.append(f"  Context: {self.context}")
        if self.traceback:
            lines.append(self.traceback)
        return "\n".join(lines)


class ErrorReporter:
    """Captures, stores, and reports errors for debugging.

    When ``auto_email=True`` and SMTP is configured, uncaught exceptions
    that propagate through the library are automatically emailed to the
    support address. Otherwise errors are stored in memory for manual
    retrieval via ``get_error_log()`` or ``report_bug()``.

    Parameters
    ----------
    enabled : bool
        Whether to capture errors. Default False.
    max_entries : int
        Maximum error entries to keep in memory.
    auto_email : bool
        If True, attempt to send an email automatically when a fatal/uncaught
        error is captured. Requires SMTP configuration.
    smtp_config : SmtpConfig, optional
        SMTP configuration for auto-email. If not provided, tries to load
        from environment variables.
    on_error : callable, optional
        Custom callback invoked on every captured error. Receives the
        ``ErrorEntry`` as argument. Runs after email (if any).
    """

    def __init__(
        self,
        enabled: bool = False,
        max_entries: int = MAX_LOG_ENTRIES,
        auto_email: bool = False,
        smtp_config: Optional[SmtpConfig] = None,
        on_error: Optional[Callable[[ErrorEntry], Any]] = None,
    ) -> None:
        self._enabled = enabled
        self._errors: deque[ErrorEntry] = deque(maxlen=max_entries)
        self._error_count: int = 0
        self._auto_email = auto_email
        self._smtp_config = smtp_config
        self._on_error = on_error
        self._original_excepthook: Optional[Any] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def error_count(self) -> int:
        return self._error_count

    def enable(self) -> None:
        """Enable error capture."""
        self._enabled = True

    def disable(self) -> None:
        """Disable error capture."""
        self._enabled = False

    def install_excepthook(self) -> None:
        """Install a global ``sys.excepthook`` that captures uncaught exceptions.

        The original excepthook is preserved and still called, so tracebacks
        still print to stderr as usual. This ensures that any uncaught
        exception anywhere in the process is recorded (and optionally emailed).
        """
        self._original_excepthook = sys.excepthook

        def _hook(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
            # Only capture Exception subclasses (not KeyboardInterrupt, SystemExit)
            if isinstance(exc_value, Exception):
                self.capture(exc_value, context="uncaught exception (sys.excepthook)")

                # Auto-email on uncaught exceptions
                if self._auto_email:
                    self._try_send_email(
                        subject=f"[binance-book] Uncaught {exc_type.__name__}",
                        fatal=True,
                    )

            # Call the original hook so the traceback still prints
            if self._original_excepthook:
                self._original_excepthook(exc_type, exc_value, exc_tb)

        sys.excepthook = _hook

    def uninstall_excepthook(self) -> None:
        """Restore the original ``sys.excepthook``."""
        if self._original_excepthook is not None:
            sys.excepthook = self._original_excepthook
            self._original_excepthook = None

    def capture(self, exc: Exception, context: str = "") -> None:
        """Capture an exception.

        Parameters
        ----------
        exc : Exception
            The exception to capture.
        context : str
            Additional context (e.g. which method was called).
        """
        if not self._enabled:
            return

        self._error_count += 1
        entry = ErrorEntry(
            timestamp=time.time(),
            exception_type=type(exc).__name__,
            message=str(exc),
            traceback=traceback.format_exc(),
            context=context,
        )
        self._errors.append(entry)
        logger.debug("Captured error #%d: %s: %s", self._error_count, type(exc).__name__, exc)

        if self._on_error:
            try:
                self._on_error(entry)
            except Exception:
                logger.debug("on_error callback raised", exc_info=True)

    def get_error_log(self) -> str:
        """Get all captured errors as a formatted text log.

        Returns
        -------
        str
            Formatted error log. API keys and secrets are never included.
        """
        if not self._errors:
            return "No errors captured."

        lines = [
            f"binance-book Error Log ({len(self._errors)} errors)",
            f"Total errors since start: {self._error_count}",
            "=" * 60,
        ]
        for entry in self._errors:
            lines.append(entry.to_text())
            lines.append("-" * 40)

        return "\n".join(lines)

    def get_system_info(self) -> str:
        """Get sanitized system info for bug reports."""
        try:
            import binance_book
            version = binance_book.__version__
        except Exception:
            version = "unknown"

        return "\n".join([
            f"binance-book version: {version}",
            f"Python: {sys.version}",
            f"Platform: {platform.platform()}",
            f"OS: {platform.system()} {platform.release()}",
            f"Architecture: {platform.machine()}",
        ])

    def get_bug_report(self, description: str = "") -> str:
        """Generate a full bug report with system info and error log.

        Parameters
        ----------
        description : str
            User description of what went wrong.

        Returns
        -------
        str
            Complete bug report text, safe to share (no secrets).
        """
        sections = [
            "# binance-book Bug Report",
            "",
            "## Description",
            description or "(No description provided)",
            "",
            "## System Info",
            self.get_system_info(),
            "",
            "## Error Log",
            self.get_error_log(),
        ]
        return "\n".join(sections)

    def clear(self) -> None:
        """Clear all captured errors."""
        self._errors.clear()
        self._error_count = 0

    # ------------------------------------------------------------------
    # Email sending
    # ------------------------------------------------------------------

    def _get_smtp_config(self) -> Optional[SmtpConfig]:
        """Resolve SMTP config from explicit config or env vars."""
        if self._smtp_config:
            return self._smtp_config
        return SmtpConfig.from_env()

    def _try_send_email(self, subject: str = "", fatal: bool = False) -> bool:
        """Attempt to send an error report email via SMTP.

        Returns True if the email was sent successfully, False otherwise.
        Never raises — failures are logged silently.
        """
        config = self._get_smtp_config()
        if not config:
            logger.debug(
                "SMTP not configured, skipping auto-email. "
                "Set BINANCE_BOOK_SMTP_USER and BINANCE_BOOK_SMTP_PASS env vars, "
                "or pass smtp_config to ErrorReporter."
            )
            return False

        try:
            report = self.get_bug_report(
                description="Automatic error report" + (" (FATAL — uncaught exception)" if fatal else "")
            )
            return send_email(
                to_addr=SUPPORT_EMAIL,
                subject=subject or "[binance-book] Error Report",
                body=report,
                smtp_config=config,
            )
        except Exception:
            logger.debug("Failed to send error email", exc_info=True)
            return False

    def send_report(self, description: str = "") -> bool:
        """Manually send the current error log via email.

        Requires SMTP configuration (env vars or explicit SmtpConfig).

        Parameters
        ----------
        description : str
            Description of what went wrong.

        Returns
        -------
        bool
            True if the email was sent successfully.
        """
        config = self._get_smtp_config()
        if not config:
            logger.warning(
                "Cannot send email: SMTP not configured. "
                "Set BINANCE_BOOK_SMTP_USER and BINANCE_BOOK_SMTP_PASS, "
                "or use report_bug(method='email') to open a mailto link instead."
            )
            return False

        report = self.get_bug_report(description)
        return send_email(
            to_addr=SUPPORT_EMAIL,
            subject=f"[binance-book] Bug Report: {description[:60]}" if description else "[binance-book] Bug Report",
            body=report,
            smtp_config=config,
        )


def send_email(
    to_addr: str,
    subject: str,
    body: str,
    smtp_config: SmtpConfig,
) -> bool:
    """Send a plain-text email via SMTP.

    Uses only Python stdlib (``smtplib``, ``email``). No external
    dependencies required.

    Parameters
    ----------
    to_addr : str
        Recipient email address.
    subject : str
        Email subject line.
    body : str
        Plain-text email body.
    smtp_config : SmtpConfig
        SMTP server configuration.

    Returns
    -------
    bool
        True if the email was sent successfully.
    """
    from_addr = smtp_config.from_addr or smtp_config.username

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        if smtp_config.use_tls:
            # STARTTLS on port 587
            server = smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=15)
            server.ehlo()
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
        else:
            # Direct SSL on port 465
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_config.host, smtp_config.port, context=context, timeout=15)

        server.login(smtp_config.username, smtp_config.password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        logger.info("Error report email sent to %s", to_addr)
        return True

    except Exception as e:
        logger.warning("Failed to send email via SMTP: %s", e)
        return False


def report_bug(
    description: str = "",
    error_reporter: Optional[ErrorReporter] = None,
    method: str = "email",
) -> str:
    """Generate a bug report and open it for sending.

    Parameters
    ----------
    description : str
        Description of the issue.
    error_reporter : ErrorReporter, optional
        Error reporter instance with captured errors.
    method : str
        How to send: ``"email"`` (opens mailto link), ``"github"``
        (opens GitHub issue), ``"send"`` (sends via SMTP immediately),
        or ``"text"`` (returns report as string).

    Returns
    -------
    str
        The bug report text.
    """
    reporter = error_reporter or ErrorReporter(enabled=False)
    report = reporter.get_bug_report(description)

    if method == "send":
        success = reporter.send_report(description)
        if not success:
            logger.warning("SMTP send failed, falling back to mailto link")
            _open_mailto(report)

    elif method == "email":
        _open_mailto(report)

    elif method == "github":
        title = urllib.parse.quote(f"Bug: {description[:80]}" if description else "Bug report")
        body = urllib.parse.quote(report[:5000])
        url = f"{GITHUB_ISSUES_URL}?title={title}&body={body}"
        try:
            webbrowser.open(url)
            logger.info("Opened GitHub issue form with bug report")
        except Exception:
            logger.warning("Could not open browser. Report:\n%s", report)

    return report


def print_bug_report(
    description: str = "",
    error_reporter: Optional[ErrorReporter] = None,
) -> None:
    """Print a bug report to stdout for copy-pasting.

    Parameters
    ----------
    description : str
        Description of the issue.
    error_reporter : ErrorReporter, optional
        Error reporter with captured errors.
    """
    reporter = error_reporter or ErrorReporter(enabled=False)
    report = reporter.get_bug_report(description)
    print(report)
    print(f"\nTo report, email this to: {SUPPORT_EMAIL}")
    print(f"Or open a GitHub issue: {GITHUB_ISSUES_URL}")


def _open_mailto(report: str) -> None:
    """Open a mailto link with the bug report."""
    subject = urllib.parse.quote("binance-book bug report")
    body = urllib.parse.quote(report[:2000])  # mailto has length limits
    mailto = f"mailto:{SUPPORT_EMAIL}?subject={subject}&body={body}"
    try:
        webbrowser.open(mailto)
        logger.info("Opened email client with bug report")
    except Exception:
        logger.warning("Could not open email client. Report:\n%s", report)
