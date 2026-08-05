"""HTTPS communication with the Hot Pepper Gourmet Web Service.

Per ADR-0002 decision 3 and ADR-0008 decision 5, the API key is sent only in
a server-to-provider request and is never shown to a browser, log, error, or
trace. ``redact_query`` removes it from any URL before that URL is used in an
exception message. Per ADR-0002 decision 7, this module is exercised in
tests with an injected synthetic ``opener`` rather than a live credentialed
call.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from .config import HotPepperConfig
from .errors import HotPepperCommunicationError, HotPepperResponseError

REQUEST_TIMEOUT_SECONDS = 8
_REDACTED_QUERY_PARAMETERS = frozenset({"key"})

Opener = Callable[[urllib.request.Request], object]


def redact_query(url: str) -> str:
    """Replace sensitive query values so the URL is safe to log or raise."""
    split = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(split.query, keep_blank_values=True)
    redacted_pairs = [
        (name, "REDACTED") if name in _REDACTED_QUERY_PARAMETERS else (name, value)
        for name, value in pairs
    ]
    redacted_query = urllib.parse.urlencode(redacted_pairs)
    return urllib.parse.urlunsplit(split._replace(query=redacted_query))


def _build_request(config: HotPepperConfig) -> urllib.request.Request:
    query = urllib.parse.urlencode(
        {
            "key": config.api_key,
            "lat": config.origin_latitude,
            "lng": config.origin_longitude,
            "range": config.search_range,
            "lunch": "1",
            "format": "json",
            "count": "100",
        }
    )
    url = f"{config.base_url}?{query}"
    return urllib.request.Request(url, headers={"Accept": "application/json"})


def fetch_shops(config: HotPepperConfig, *, opener: Opener | None = None) -> dict:
    """Perform one fresh Hot Pepper search and return the parsed JSON body.

    ``opener`` defaults to ``urllib.request.urlopen`` and may be replaced in
    tests with a synthetic callable; it must behave like a context manager
    whose ``read()`` returns bytes, matching ``http.client.HTTPResponse``.
    """
    request = _build_request(config)
    open_request = opener or urllib.request.urlopen
    try:
        with open_request(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read()
    except (urllib.error.URLError, OSError) as error:
        raise HotPepperCommunicationError(
            f"Provider communication failed for {redact_query(request.full_url)}"
        ) from error

    try:
        payload = json.loads(body)
    except (TypeError, ValueError) as error:
        raise HotPepperResponseError(
            f"Provider response was not valid JSON for {redact_query(request.full_url)}"
        ) from error

    if not isinstance(payload, dict):
        raise HotPepperResponseError(
            f"Provider response was not a JSON object for {redact_query(request.full_url)}"
        )

    return payload
