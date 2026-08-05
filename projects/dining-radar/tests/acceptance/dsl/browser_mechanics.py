"""Generic plain-HTTP browser mechanics shared by every TDR acceptance DSL.

This module holds only transport- and markup-level plumbing (HTTP requests,
cookie jar, HTML parsing, generic "activate this control" / "submit this
form" mechanics keyed by ``data-testid``). It knows nothing about
authentication or candidate-search business vocabulary; scenario-specific DSL
modules (``authentication_browser.py``, ``candidate_search_browser.py``)
compose these primitives instead of duplicating them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from django.test import SimpleTestCase

LOCAL_REQUEST_TIMEOUT_SECONDS = 10

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


@dataclass
class HtmlNode:
    tag: str
    attributes: dict[str, str]
    parent: HtmlNode | None = None
    children: list[HtmlNode] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    def test_id(self) -> str | None:
        return self.attributes.get("data-testid")

    def descendants(self) -> Iterable[HtmlNode]:
        yield self
        for child in self.children:
            yield from child.descendants()

    def text(self) -> str:
        return (
            " ".join(part.strip() for part in self.text_parts if part.strip())
            + " "
            + " ".join(child.text() for child in self.children)
        )


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document", {})
        self.current = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HtmlNode(tag, {name: value or "" for name, value in attrs}, self.current)
        self.current.children.append(node)
        if tag not in VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        cursor = self.current
        while cursor is not self.root:
            if cursor.tag == tag:
                self.current = cursor.parent or self.root
                return
            cursor = cursor.parent or self.root

    def handle_data(self, data: str) -> None:
        self.current.text_parts.append(data)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


@dataclass(frozen=True)
class BrowserResponse:
    status: int
    url: str
    headers: object
    body: str

    def document(self) -> HtmlNode:
        parser = DocumentParser()
        parser.feed(self.body)
        parser.close()
        return parser.root


class HttpBrowser:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies), NoRedirect())

    def get(self, path_or_url: str) -> BrowserResponse:
        return self.request("GET", path_or_url)

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> BrowserResponse:
        url = urljoin(self.base_url, path_or_url)
        response = self._one_request(method, url, data=data, headers=headers)
        redirects = 0
        while follow_redirects and response.status in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location:
                raise AssertionError("redirect response must include Location")
            target_url = urljoin(response.url, location)
            if self._origin_of(target_url) != self._origin_of(self.base_url):
                raise AssertionError(
                    "local acceptance browser must remain on its configured "
                    "same-origin HTTP boundary: "
                    f"configured={self._origin_of(self.base_url)!r}, "
                    f"redirected={self._origin_of(target_url)!r}"
                )
            redirects += 1
            if redirects > 10:
                raise AssertionError("browser redirect loop exceeded 10 hops")
            redirect_method = method if response.status in {307, 308} else "GET"
            redirect_data = data if redirect_method == method else None
            response = self._one_request(
                redirect_method,
                target_url,
                data=redirect_data,
                headers=headers if redirect_data else None,
            )
        return response

    def csrf_cookie_value(self, name: str = "csrftoken") -> str:
        for cookie in self.cookies:
            if cookie.name == name and cookie.value:
                return cookie.value
        raise AssertionError(
            f"no {name!r} cookie is available; a same-origin GET must be "
            "issued before a CSRF-protected request"
        )

    @staticmethod
    def _origin_of(url: str) -> tuple[str, str]:
        parsed = urlsplit(url)
        return parsed.scheme, parsed.netloc

    def _one_request(
        self, method: str, url: str, *, data: bytes | None, headers: dict[str, str] | None
    ) -> BrowserResponse:
        request = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with self.opener.open(request, timeout=LOCAL_REQUEST_TIMEOUT_SECONDS) as opened:
                return BrowserResponse(
                    opened.status, opened.url, opened.headers, opened.read().decode("utf-8")
                )
        except HTTPError as error:
            return BrowserResponse(
                error.code, error.url, error.headers, error.read().decode("utf-8")
            )


# Generic data-testid / form mechanics -------------------------------------


def test_id_node(document: HtmlNode, test_id: str) -> HtmlNode:
    for node in document.descendants():
        if node.test_id() == test_id:
            return node
    raise AssertionError(f"required browser control {test_id} was not found")


def available_test_ids(document: HtmlNode) -> set[str]:
    return {node.test_id() for node in document.descendants() if node.test_id()}


def containing_form(node: HtmlNode) -> HtmlNode | None:
    cursor: HtmlNode | None = node
    while cursor is not None:
        if cursor.tag == "form":
            return cursor
        cursor = cursor.parent
    return None


def form_fields(form: HtmlNode) -> dict[str, str]:
    fields: dict[str, str] = {}
    for node in form.descendants():
        if node.tag not in {"input", "textarea", "select"}:
            continue
        name = node.attributes.get("name")
        if name and node.attributes.get("type") not in {"submit", "button"}:
            fields[name] = node.attributes.get("value", "")
    return fields


def submit_form(
    browser: HttpBrowser,
    response: BrowserResponse,
    form_test_id: str,
    values_by_test_id: dict[str, str],
    submit_test_id: str,
) -> BrowserResponse:
    document = response.document()
    form = test_id_node(document, form_test_id)
    submit = test_id_node(form, submit_test_id)
    fields = form_fields(form)
    for test_id, value in values_by_test_id.items():
        input_node = test_id_node(form, test_id)
        name = input_node.attributes.get("name")
        if not name:
            raise AssertionError(f"{test_id} must be a named form field")
        fields[name] = value
    action = submit.attributes.get("formaction") or form.attributes.get("action") or response.url
    method = submit.attributes.get("formmethod") or form.attributes.get("method", "GET")
    encoded = urlencode(fields).encode("utf-8")
    if method.upper() == "GET":
        separator = "&" if "?" in action else "?"
        return browser.get(f"{action}{separator}{encoded.decode('utf-8')}")
    return browser.request(
        method.upper(),
        action,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def activate_control(
    browser: HttpBrowser, response: BrowserResponse, test_id: str
) -> BrowserResponse:
    document = response.document()
    control = test_id_node(document, test_id)
    if control.tag == "a" and control.attributes.get("href"):
        return browser.get(control.attributes["href"])
    form = containing_form(control)
    if form is None:
        raise AssertionError(f"{test_id} must be a link or belong to a form")
    form_test_id = form.test_id()
    if not form_test_id:
        raise AssertionError(f"form containing {test_id} must have data-testid")
    return submit_form(browser, response, form_test_id, {}, test_id)


def assert_test_ids(
    assertions: SimpleTestCase, response: BrowserResponse, *, present: list[str], absent: list[str]
) -> None:
    available = available_test_ids(response.document())
    for test_id in present:
        assertions.assertIn(test_id, available)
    for test_id in absent:
        assertions.assertNotIn(test_id, available)


def assert_status(
    assertions: SimpleTestCase, response: BrowserResponse, expected: int, context: str
) -> None:
    assertions.assertEqual(response.status, expected, f"{context}: {response.body}")


def assert_no_content(assertions: SimpleTestCase, response: BrowserResponse, context: str) -> None:
    assert_status(assertions, response, 204, context)
    assertions.assertEqual(response.body, "", context)


def require(value: object, message: str) -> object:
    if value is None:
        raise AssertionError(message)
    return value
