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
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

CANDIDATE_PROPOSAL_PATH = "/candidate-proposals"

# ADR-0058: a Must this contract states as a side effect (a browser API call),
# not a DOM attribute, so it is not observable through by_test_id/expect
# alone. Headless Chromium's clipboard permission grant + OS-clipboard
# readback (context.grant_permissions + navigator.clipboard.readText) is the
# alternative ADR-0058 decision 3 names, but is unreliable under CI's
# ubuntu-latest headless launch (no real desktop clipboard backing it), so
# this instead wraps navigator.clipboard.writeText itself via an init script
# and records what was passed to it -- deterministic regardless of headless
# clipboard-permission support.
_CLIPBOARD_MONITOR_INIT_SCRIPT = """
(() => {
  window.__clipboardWrites = [];
  if (!window.navigator.clipboard) {
    Object.defineProperty(window.navigator, "clipboard", {
      value: {},
      configurable: true,
    });
  }
  window.navigator.clipboard.writeText = (text) => {
    window.__clipboardWrites.push(text);
    return Promise.resolve();
  };
})();
"""


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


def install_clipboard_write_monitor(page: Page) -> None:
    """Install the navigator.clipboard.writeText monitor (see
    _CLIPBOARD_MONITOR_INIT_SCRIPT above) on ``page``.

    Must be called before ``page``'s first navigation -- Playwright's
    add_init_script re-runs the script on every subsequent navigation of this
    same page, but does not apply retroactively to a document already
    loaded.
    """
    page.add_init_script(_CLIPBOARD_MONITOR_INIT_SCRIPT)


def clipboard_write_count(page: Page) -> int:
    """The number of navigator.clipboard.writeText calls recorded so far
    (see install_clipboard_write_monitor above). A caller takes this
    *before* triggering the activation under test, then passes it to
    assert_clipboard_write_received as ``since_count`` -- recopy's returned
    URL is byte-identical to the URL an earlier issue already wrote
    (TDR-GTH-17: "同じ参加者に向けたリンクがあらためて得られる"), so checking
    "this exact text appears anywhere in the whole history" would pass even
    if *this* activation never called writeText at all, as long as some
    earlier activation happened to write the same text.
    """
    return page.evaluate("(window.__clipboardWrites || []).length")


def assert_clipboard_write_received(
    assertions: SimpleTestCase, page: Page, expected_text: str, since_count: int
) -> None:
    """Wait for a navigator.clipboard.writeText call carrying exactly
    ``expected_text`` among the writes recorded *after* ``since_count``
    (see clipboard_write_count above; ADR-0058 decision 1).
    """
    try:
        page.wait_for_function(
            "([text, since]) => (window.__clipboardWrites || []).slice(since).includes(text)",
            arg=[expected_text, since_count],
            timeout=2000,
        )
    except PlaywrightTimeoutError:
        writes = page.evaluate("window.__clipboardWrites || []")
        assertions.fail(
            f"navigator.clipboard.writeText was not called with "
            f"{expected_text!r} after this activation (since index "
            f"{since_count}); observed writes: {writes!r}"
        )
