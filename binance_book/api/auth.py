"""HMAC-SHA256 request signing for authenticated Binance endpoints."""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode


def generate_signature(secret: str, query_string: str) -> str:
    """Create an HMAC-SHA256 signature of the query string."""
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_params(params: dict, secret: str) -> dict:
    """Add ``timestamp`` and ``signature`` to request parameters.

    Parameters
    ----------
    params : dict
        Existing query parameters (will not be mutated).
    secret : str
        Binance API secret key.

    Returns
    -------
    dict
        A new dict containing the original params plus ``timestamp`` and
        ``signature``.
    """
    signed = {**params, "timestamp": int(time.time() * 1000)}
    qs = urlencode(signed)
    signed["signature"] = generate_signature(secret, qs)
    return signed
