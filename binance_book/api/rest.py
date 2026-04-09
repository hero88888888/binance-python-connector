"""Async HTTP client for Binance REST API.

Talks directly to Binance endpoints — no third-party Binance libraries.
Handles rate-limit headers, retries on 429/418, and request signing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Optional

import aiohttp
import orjson

from binance_book.api.auth import sign_params
from binance_book.api.endpoints import Endpoint, depth_weight
from binance_book.exceptions import (
    BinanceAPIError,
    BinanceRateLimitError,
    BinanceRequestError,
)

logger = logging.getLogger(__name__)


class BinanceRestClient:
    """Low-level async HTTP client for Binance REST API.

    Manages a single ``aiohttp.ClientSession``, tracks rate-limit weight
    consumption from response headers, and auto-retries on HTTP 429/418.

    Parameters
    ----------
    base_url : str
        REST API base URL (e.g. ``https://api.binance.com``).
    api_key : str, optional
        Binance API key for authenticated requests.
    api_secret : str, optional
        Binance API secret for request signing.
    timeout : float
        Request timeout in seconds.
    on_request_complete : callable, optional
        Callback invoked after every request completes (success or error).
        Signature: ``(endpoint_path: str, latency_ms: float, success: bool) -> None``.
        Used for telemetry. Never raises.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: float = 10.0,
        on_request_complete: Optional[Callable[[str, float, bool], None]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._on_request_complete = on_request_complete

        self._used_weight: int = 0
        self._weight_limit: int = 1200
        self._weight_reset_ts: float = 0.0
        self._retry_after: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers: dict[str, str] = {}
            if self._api_key:
                headers["X-MBX-APIKEY"] = self._api_key
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers=headers,
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def used_weight(self) -> int:
        """Current consumed API weight in the rate-limit window."""
        now = time.monotonic()
        if now >= self._weight_reset_ts:
            self._used_weight = 0
        return self._used_weight

    async def request(
        self,
        method: str,
        endpoint: Endpoint,
        params: Optional[dict[str, Any]] = None,
        signed: bool = False,
        weight_override: Optional[int] = None,
    ) -> Any:
        """Send an HTTP request to the Binance API.

        Parameters
        ----------
        method : str
            HTTP method (``"GET"``, ``"POST"``, etc.).
        endpoint : Endpoint
            The endpoint object containing path and base weight.
        params : dict, optional
            Query parameters.
        signed : bool
            If True, add timestamp and HMAC signature to the request.
        weight_override : int, optional
            Override the endpoint's default weight (e.g. depth weight varies by limit).

        Returns
        -------
        Any
            Parsed JSON response body.

        Raises
        ------
        BinanceRateLimitError
            On HTTP 429 or 418 (IP ban).
        BinanceAPIError
            On any Binance error response.
        BinanceRequestError
            On network-level failures.
        """
        if params is None:
            params = {}

        if signed and self._api_secret:
            params = sign_params(params, self._api_secret)

        url = f"{self._base_url}{endpoint.path}"
        weight = weight_override or endpoint.weight

        now = time.monotonic()
        if now < self._retry_after:
            wait = self._retry_after - now
            logger.warning("Rate-limited, waiting %.1fs", wait)
            await asyncio.sleep(wait)

        for attempt in range(3):
            t0 = time.monotonic()
            try:
                session = await self._get_session()
                async with session.request(method, url, params=params) as resp:
                    self._update_weight_from_headers(resp.headers, weight)

                    body = await resp.read()

                    if resp.status == 429 or resp.status == 418:
                        retry_after = int(resp.headers.get("Retry-After", "60"))
                        self._retry_after = time.monotonic() + retry_after
                        data = orjson.loads(body) if body else {}
                        self._notify_complete(endpoint.path, t0, success=False)
                        raise BinanceRateLimitError(
                            status_code=resp.status,
                            error_code=data.get("code", -1),
                            message=data.get("msg", "Rate limited"),
                            retry_after=retry_after,
                        )

                    if resp.status >= 400:
                        data = orjson.loads(body) if body else {}
                        self._notify_complete(endpoint.path, t0, success=False)
                        raise BinanceAPIError(
                            status_code=resp.status,
                            error_code=data.get("code", -1),
                            message=data.get("msg", f"HTTP {resp.status}"),
                        )

                    self._notify_complete(endpoint.path, t0, success=True)
                    return orjson.loads(body)

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                self._notify_complete(endpoint.path, t0, success=False)
                if attempt == 2:
                    raise BinanceRequestError(f"Request failed after 3 attempts: {exc}") from exc
                wait = 0.5 * (2**attempt)
                logger.warning("Request error (attempt %d/3), retrying in %.1fs: %s", attempt + 1, wait, exc)
                await asyncio.sleep(wait)

        raise BinanceRequestError("Request failed after 3 attempts")

    async def get(
        self,
        endpoint: Endpoint,
        params: Optional[dict[str, Any]] = None,
        signed: bool = False,
        weight_override: Optional[int] = None,
    ) -> Any:
        """Shorthand for a GET request."""
        return await self.request("GET", endpoint, params, signed, weight_override)

    def _notify_complete(self, endpoint_path: str, t0: float, success: bool) -> None:
        """Invoke the ``on_request_complete`` callback if one is registered."""
        if self._on_request_complete is None:
            return
        latency_ms = (time.monotonic() - t0) * 1000
        try:
            self._on_request_complete(endpoint_path, latency_ms, success)
        except Exception:
            pass

    def _update_weight_from_headers(self, headers: Any, request_weight: int) -> None:
        """Parse rate-limit info from Binance response headers."""
        for key in ("X-MBX-USED-WEIGHT-1M", "X-MBX-USED-WEIGHT-1m"):
            val = headers.get(key)
            if val is not None:
                try:
                    self._used_weight = int(val)
                except ValueError:
                    pass
                self._weight_reset_ts = time.monotonic() + 60
                return

        self._used_weight += request_weight
        if self._weight_reset_ts == 0.0:
            self._weight_reset_ts = time.monotonic() + 60
