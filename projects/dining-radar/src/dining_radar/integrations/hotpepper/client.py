"""HTTPS communication with the Hot Pepper Gourmet Web Service.

Per ADR-0002 decision 3 and ADR-0008 decision 5, the API key is sent only in
a server-to-provider request and is never shown to a browser, log, error, or
trace. ``redact_query`` removes it from any URL before that URL is used in an
exception message. Per ADR-0002 decision 7, this module is exercised in
tests with an injected synthetic ``opener`` rather than a live credentialed
call.

Per adr/0020 decision 3-1 (Must), this module pages through the provider's
``start`` parameter whenever ``results_available`` exceeds
``results_returned``, so filtering (adr/0020 decisions 1-3) always sees the
full eligible population rather than a truncated first page. The current
measured production population fits in a single 100-count page (see
``activeContext.md`` "Live provider measurements"), so this is a safety net
that does not currently fire, not a behavior change to today's response
shape.
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

# Defensive cap on the number of pages a single fetch_shops call will follow.
# The current measured production population needs exactly one page (see
# module docstring); this exists only to keep a misbehaving or misreporting
# provider response from driving an unbounded request loop. Not required by
# any contract Must -- a plain defensive bound on adr/0020 decision 3-1's
# pagination loop.
_MAX_PAGES = 10

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


def _build_request(config: HotPepperConfig, *, start: int) -> urllib.request.Request:
    query = urllib.parse.urlencode(
        {
            "key": config.api_key,
            "lat": config.origin_latitude,
            "lng": config.origin_longitude,
            "range": config.search_range,
            "lunch": "1",
            "format": "json",
            "count": "100",
            "start": start,
        }
    )
    url = f"{config.base_url}?{query}"
    return urllib.request.Request(url, headers={"Accept": "application/json"})


def _fetch_one_page(request: urllib.request.Request, open_request: Opener) -> dict:
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


def _results_and_shop_list(payload: dict) -> tuple[dict, list] | None:
    """``(results, shop_list)`` when both are well-formed, else ``None``.

    A malformed or missing ``results``/``results.shop`` is deliberately not
    raised here: this function is used only to decide whether pagination can
    proceed, and ``normalize_shops`` already raises the contract's own
    validation error for a malformed response shape. Duplicating that
    validation here would only risk the two disagreeing.
    """
    results = payload.get("results")
    if not isinstance(results, dict):
        return None
    shop_list = results.get("shop")
    if not isinstance(shop_list, list):
        return None
    return results, shop_list


def fetch_shops(config: HotPepperConfig, *, opener: Opener | None = None) -> dict:
    """Perform one fresh Hot Pepper search and return the parsed JSON body.

    ``opener`` defaults to ``urllib.request.urlopen`` and may be replaced in
    tests with a synthetic callable; it must behave like a context manager
    whose ``read()`` returns bytes, matching ``http.client.HTTPResponse``.

    Per adr/0020 decision 3-1 (Must), this pages through ``start`` whenever
    the first page reports ``results_available`` greater than the shop count
    actually accumulated so far, merging every page's ``results.shop`` list
    into the returned payload's ``results.shop``. Pagination stops as soon as
    the accumulated count reaches ``results_available``, a page returns no
    shop, ``results_available``/``results_returned`` is missing or not an
    integer, or ``_MAX_PAGES`` is reached -- in every one of those cases the
    payload from the pages fetched so far is returned as-is, and any
    downstream validation of a malformed shape is left to
    ``normalize_shops``.
    """
    open_request = opener or urllib.request.urlopen
    start = 1
    combined_shops: list = []
    payload: dict = {}

    for _page in range(_MAX_PAGES):
        request = _build_request(config, start=start)
        payload = _fetch_one_page(request, open_request)

        parsed = _results_and_shop_list(payload)
        if parsed is None:
            return payload
        results, shop_list = parsed
        combined_shops.extend(shop_list)

        available = results.get("results_available")
        returned = results.get("results_returned")
        if (
            not isinstance(available, int)
            or not isinstance(returned, int)
            or not shop_list
            or len(combined_shops) >= available
        ):
            break
        start += len(shop_list)

    merged_results = dict(payload.get("results") or {})
    merged_results["shop"] = combined_shops
    return {**payload, "results": merged_results}
