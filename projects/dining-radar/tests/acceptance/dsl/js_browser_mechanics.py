"""JS-capable browser mechanics shared only by the TDR-CS acceptance DSL.

Per ADR-0009, the authenticated candidate-proposal screen renders its content
(cards, map, re-proposal modal, error surfaces) with client-side JavaScript
after the server returns only an empty mount point. Plain HTTP + HTML parsing
(``browser_mechanics.py``, still used unmodified by TDR-AUTH per ADR-0009
decision 4) cannot execute that script or observe its resulting DOM, so this
module wraps Playwright instead: a real Chromium instance that runs the
screen's own JavaScript and lets tests read/drive the DOM it produces.

This module holds only generic Playwright plumbing (test-id lookup by the
project's existing ``data-testid`` convention -- Playwright's default test-id
attribute is already ``data-testid``, so no project-specific configuration is
needed -- and capturing the exact ``POST /candidate-proposals`` request and
response a browser action triggered). It knows nothing about candidate-search
business vocabulary; ``candidate_search_browser.py`` composes these
primitives.

``is_candidate_proposal_request`` (as opposed to ``_response``) exists for
callers that only need to count outgoing requests -- e.g. asserting that
cancelling the filter panel sends none at all -- without waiting on a
response.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from django.test import SimpleTestCase
from playwright.sync_api import APIResponse, Locator, Page, Request, Response, expect

CANDIDATE_PROPOSAL_PATH = "/candidate-proposals"


def is_candidate_proposal_response(response: Response) -> bool:
    return response.request.method == "POST" and response.url.rstrip("/").endswith(
        CANDIDATE_PROPOSAL_PATH
    )


def is_candidate_proposal_request(request: Request) -> bool:
    return request.method == "POST" and request.url.rstrip("/").endswith(CANDIDATE_PROPOSAL_PATH)


@dataclass(frozen=True)
class CapturedApiResponse:
    """The exact response body the browser received for one public operation.

    Capturing the real network exchange (rather than issuing a second,
    separate call afterward) keeps the assertion faithful to what the
    client-side JavaScript actually rendered from. ``request_body`` is the
    exact JSON body the browser itself sent for this same exchange (``None``
    when the underlying network object exposes no associated request, or when
    that request carried no JSON body) -- captured the same way, from the real
    exchange rather than a second call -- so a Then-clause can verify a
    request-shape invariant (adr/0017's ``previouslyShownProviderPageUrls``
    echo requirement) without re-deriving what was actually sent.
    """

    status: int
    body: str
    payload: Any | None
    retry_after: str | None
    request_body: Any | None = None


def _header(headers: dict[str, str], name: str) -> str | None:
    name_lower = name.lower()
    for key, value in headers.items():
        if key.lower() == name_lower:
            return value
    return None


def build_captured_response(response: Response | APIResponse) -> CapturedApiResponse:
    body = response.text()
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001 - a non-JSON body is itself the observation
        payload = None
    request = getattr(response, "request", None)
    request_body = request.post_data_json if request is not None else None
    return CapturedApiResponse(
        response.status,
        body,
        payload,
        _header(response.headers, "retry-after"),
        request_body,
    )


def capture_candidate_proposal_response(
    page: Page, trigger: Callable[[], None]
) -> CapturedApiResponse:
    with page.expect_response(is_candidate_proposal_response) as info:
        trigger()
    return build_captured_response(info.value)


def by_test_id(scope: Page | Locator, test_id: str) -> Locator:
    return scope.get_by_test_id(test_id)


def wait_for_at_least_one(scope: Page | Locator, test_id: str) -> Locator:
    """Return the (possibly multi-element) locator for ``test_id``, waiting until
    client-side JavaScript has rendered at least one matching element.

    Plain ``.count()``/``.nth()`` calls read the DOM's current snapshot without
    waiting; callers that are about to enumerate a collection use this first so
    a render still in flight cannot be misread as "no candidates".
    """
    locator = by_test_id(scope, test_id)
    expect(locator.first).to_be_attached()
    return locator


def assert_present(assertions: SimpleTestCase, scope: Page | Locator, test_id: str) -> Locator:
    locator = by_test_id(scope, test_id).first
    expect(locator).to_be_attached()
    return locator


def assert_absent(assertions: SimpleTestCase, scope: Page | Locator, test_id: str) -> None:
    expect(by_test_id(scope, test_id)).to_have_count(0)


def assert_all_present(
    assertions: SimpleTestCase, scope: Page | Locator, test_ids: Iterable[str]
) -> None:
    for test_id in test_ids:
        assert_present(assertions, scope, test_id)


def assert_all_absent(
    assertions: SimpleTestCase, scope: Page | Locator, test_ids: Iterable[str]
) -> None:
    for test_id in test_ids:
        assert_absent(assertions, scope, test_id)


def csrf_token(page: Page) -> str:
    """Read the same-origin CSRF token a compliant same-origin request must send.

    This application carries no readable ``csrftoken`` cookie (confirmed by
    enumerating ``page.context.cookies()``: only the HttpOnly session cookie
    is present) -- Django's session-based CSRF storage, the same mechanism
    that already lets ``candidate_search_browser.py``'s ``sign_in`` submit a
    server-rendered form successfully. The token is instead carried in a
    hidden ``csrfmiddlewaretoken`` form field (present on the authenticated
    screen; observed alongside ``auth-sign-out-form``), which is the value
    this application's own client-side JavaScript must also read to attach
    ``X-CSRFToken`` to its own same-origin fetch calls.
    """
    field = page.locator('input[name="csrfmiddlewaretoken"]').first
    value = field.get_attribute("value")
    if not value:
        raise AssertionError(
            "no csrfmiddlewaretoken field is available; a same-origin page "
            "load must happen before a CSRF-protected request"
        )
    return value


def require(value: object, message: str) -> object:
    if value is None:
        raise AssertionError(message)
    return value
