"""Public-browser DSL for TDR-AUTH acceptance scenarios.

The only setup operations in this module are the acceptance-only seams declared
in ``contracts/test-support-api.yaml``. Every user operation and assertion uses
the browser control surface from ``authentication-browser-interface.yaml`` or
the public candidate-proposal API contract.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from django.test import SimpleTestCase

from tests.acceptance.dsl.openapi_schema import assert_matches_openapi_schema

SIGN_IN_FORM = "auth-sign-in-form"
APPLICATION_SHELL = "authenticated-application-shell"
SIGN_IN_FAILURE = "auth-sign-in-failure"
THROTTLED_FAILURE = "auth-sign-in-throttled"
LOCAL_REQUEST_TIMEOUT_SECONDS = 10
PRIVATE_ORIGIN_CANARY = "synthetic-private-origin-never-disclose.invalid"
PROVIDER_INTERNALS_CANARY = "synthetic-provider-internals-never-disclose"
UNAUTHENTICATED_FORBIDDEN_TEST_IDS = [
    APPLICATION_SHELL,
    "auth-sign-out",
    "auth-password-change-open",
    "candidate-proposal-content",
    "candidate-map",
    "candidate-reproposal-lenses",
    "private-search-origin",
]
DISCLOSURE_TEST_IDS = [
    "auth-account-exists",
    "auth-account-disabled",
    "private-search-origin",
]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_API_CONTRACT = PROJECT_ROOT / "contracts" / "candidate-search-api.yaml"
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


class AuthenticationBrowserDsl:
    """Business operations for the local browser L4 scenarios only."""

    def __init__(self, assertions: SimpleTestCase, base_url: str) -> None:
        self.assertions = assertions
        self.browser = HttpBrowser(base_url)
        self.support = HttpBrowser(base_url)
        self.entry_response: BrowserResponse | None = None
        self.candidate_response: BrowserResponse | None = None
        self.last_response: BrowserResponse | None = None
        self.public_operation_responses: list[BrowserResponse] = []

    # Given seams ---------------------------------------------------------

    def reset_authentication_state(self) -> None:
        response = self.support.request("DELETE", "/test-support/authentication-state")
        self._assert_no_content(response, "authentication-state reset")

    def set_active_organizer(self, account_ref: str, login_identifier: str, password: str) -> None:
        self._set_organizer(account_ref, login_identifier, password, is_active=True)

    def deactivate_organizer(self, account_ref: str, login_identifier: str, password: str) -> None:
        self._set_organizer(account_ref, login_identifier, password, is_active=False)

    def seed_throttled_sign_in(self, login_identifier: str) -> None:
        response = self.support.request(
            "POST",
            "/test-support/authentication/login-throttle",
            data=json.dumps({"loginIdentifier": login_identifier}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        self._assert_no_content(response, "login-throttle seed")

    # Browser actions -----------------------------------------------------

    def open_entry(self) -> None:
        self.entry_response = self.browser.get("/")
        self.last_response = self.entry_response

    def open_candidate_proposal_api_without_session(self) -> None:
        self.candidate_response = self.browser.request(
            "POST",
            "/candidate-proposals",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            follow_redirects=False,
        )

    def exercise_unavailable_public_operations(self) -> None:
        self.open_entry()
        initial = self._require(self.entry_response, "browser entry was not opened")
        sign_up = self.browser.request("GET", "/sign-up", follow_redirects=False)
        password_reset = self.browser.request("GET", "/password-reset", follow_redirects=False)
        self.sign_in("synthetic-public-operation-unknown", "synthetic-public-operation-secret")
        generic_failure = self._require(self.last_response, "generic failure was not returned")
        self.seed_throttled_sign_in("synthetic-public-operation-throttled")
        self.open_entry()
        self.sign_in("synthetic-public-operation-throttled", "synthetic-throttled-secret")
        throttled_failure = self._require(self.last_response, "throttled failure was not returned")
        self.public_operation_responses = [
            initial,
            sign_up,
            password_reset,
            generic_failure,
            throttled_failure,
        ]

    def sign_in(self, login_identifier: str, password: str) -> None:
        entry = self._require(self.entry_response, "sign-in requires the browser entry document")
        self.last_response = self._submit_form(
            entry,
            SIGN_IN_FORM,
            {
                "auth-login-identifier": login_identifier,
                "auth-password": password,
            },
            "auth-sign-in-submit",
        )

    def sign_out(self) -> None:
        response = self._require(self.last_response, "sign-out requires an authenticated document")
        self.last_response = self._activate_control(response, "auth-sign-out")

    def open_password_change(self) -> None:
        response = self._require(
            self.last_response, "password change requires an authenticated document"
        )
        self.last_response = self._activate_control(response, "auth-password-change-open")

    def change_password(self, current_password: str, new_password: str) -> None:
        response = self._require(self.last_response, "password change form must be open")
        self.last_response = self._submit_form(
            response,
            "auth-password-change-form",
            {
                "auth-current-password": current_password,
                "auth-new-password": new_password,
                "auth-new-password-confirmation": new_password,
            },
            "auth-password-change-submit",
        )

    # Observable assertions ---------------------------------------------

    def assert_unauthenticated_entry(self) -> None:
        response = self._require(self.entry_response, "browser entry was not opened")
        self._assert_status(response, 200, "unauthenticated entry")
        self._assert_unauthenticated_controls(response)
        self._assert_no_disclosures(response)

    def assert_candidate_api_requires_authentication(self) -> None:
        response = self._require(self.candidate_response, "candidate API was not requested")
        self._assert_status(response, 401, "unauthenticated candidate proposal API")
        payload = json.loads(response.body)
        assert_matches_openapi_schema(
            payload,
            CANDIDATE_API_CONTRACT,
            "#/components/schemas/ProblemResponse",
        )
        self.assertions.assertEqual(payload["code"], "AUTHENTICATION_REQUIRED")
        self._assert_no_disclosures(response)

    def assert_authenticated_shell(self) -> None:
        response = self._require(self.last_response, "no browser response to inspect")
        self._assert_status(response, 200, "authenticated browser outcome")
        self._assert_test_ids(
            response,
            present=[
                APPLICATION_SHELL,
                "auth-sign-out",
                "auth-password-change-open",
                "auth-individual-account-guidance",
            ],
            absent=[SIGN_IN_FORM],
        )
        self._assert_test_id_attributes(
            response,
            "auth-individual-account-guidance",
            {
                "data-auth-account-use": "individual-only",
                "data-auth-credential-sharing": "not-requested",
            },
        )

    def assert_persistent_authenticated_session(self) -> None:
        self.open_entry()
        self.assert_authenticated_shell()

    def assert_authenticated_candidate_screen_with_persistent_session(self) -> None:
        self.assert_authenticated_shell()
        self.assert_persistent_authenticated_session()

    def assert_public_account_operations_are_absent(self) -> None:
        if len(self.public_operation_responses) != 5:
            raise AssertionError("public account-operation states were not exercised")
        initial, sign_up, password_reset, generic_failure, throttled_failure = (
            self.public_operation_responses
        )
        for response in [initial, generic_failure, throttled_failure]:
            self._assert_unauthenticated_controls(response)
            self._assert_test_ids(
                response,
                present=["auth-administrator-assistance"],
                absent=["auth-public-sign-up", "auth-email-password-reset"],
            )
            self._assert_no_disclosures(response)
        self._assert_no_disclosures(
            generic_failure,
            submitted_password="synthetic-public-operation-secret",
        )
        self._assert_no_disclosures(
            throttled_failure,
            submitted_password="synthetic-throttled-secret",
        )
        self._assert_status(sign_up, 404, "public sign-up route probe")
        self._assert_status(password_reset, 404, "email password-reset route probe")
        self._assert_json_keys_absent(password_reset, {"token", "resetToken", "email"})
        self._assert_no_disclosures(sign_up)
        self._assert_no_disclosures(password_reset)

    def assert_signed_out(self) -> None:
        response = self._require(self.last_response, "no sign-out response to inspect")
        self._assert_test_ids(
            response, present=[SIGN_IN_FORM], absent=[APPLICATION_SHELL, "auth-sign-out"]
        )

    def assert_protected_access_is_revoked(self) -> None:
        self.open_candidate_proposal_api_without_session()
        self.assert_candidate_api_requires_authentication()
        self.open_entry()
        self.assert_unauthenticated_entry()

    def assert_signed_out_and_protected_access_is_revoked(self) -> None:
        self.assert_signed_out()
        self.assert_protected_access_is_revoked()

    def assert_generic_sign_in_failure(self, password: str) -> str:
        response = self._require(self.last_response, "no sign-in response to inspect")
        self._assert_test_ids(
            response,
            present=[SIGN_IN_FORM, SIGN_IN_FAILURE],
            absent=[*UNAUTHENTICATED_FORBIDDEN_TEST_IDS, THROTTLED_FAILURE],
        )
        self._assert_no_disclosures(response, submitted_password=password)
        return self._normalized_public_content(response)

    def assert_throttled_sign_in_failure(self, password: str) -> str:
        response = self._require(self.last_response, "no sign-in response to inspect")
        self._assert_test_ids(
            response,
            present=[SIGN_IN_FORM, THROTTLED_FAILURE],
            absent=UNAUTHENTICATED_FORBIDDEN_TEST_IDS,
        )
        self._assert_no_disclosures(response, submitted_password=password)
        return self._normalized_public_content(response)

    # Public browser mechanics ------------------------------------------

    def _submit_form(
        self,
        response: BrowserResponse,
        form_test_id: str,
        values_by_test_id: dict[str, str],
        submit_test_id: str,
    ) -> BrowserResponse:
        document = response.document()
        form = self._test_id_node(document, form_test_id)
        submit = self._test_id_node(form, submit_test_id)
        fields = self._form_fields(form)
        for test_id, value in values_by_test_id.items():
            input_node = self._test_id_node(form, test_id)
            name = input_node.attributes.get("name")
            if not name:
                raise AssertionError(f"{test_id} must be a named form field")
            fields[name] = value
        action = (
            submit.attributes.get("formaction") or form.attributes.get("action") or response.url
        )
        method = submit.attributes.get("formmethod") or form.attributes.get("method", "GET")
        encoded = urlencode(fields).encode("utf-8")
        if method.upper() == "GET":
            separator = "&" if "?" in action else "?"
            return self.browser.get(f"{action}{separator}{encoded.decode('utf-8')}")
        return self.browser.request(
            method.upper(),
            action,
            data=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def _activate_control(self, response: BrowserResponse, test_id: str) -> BrowserResponse:
        document = response.document()
        control = self._test_id_node(document, test_id)
        if control.tag == "a" and control.attributes.get("href"):
            return self.browser.get(control.attributes["href"])
        form = self._containing_form(control)
        if form is None:
            raise AssertionError(f"{test_id} must be a link or belong to a form")
        form_test_id = form.test_id()
        if not form_test_id:
            raise AssertionError(f"form containing {test_id} must have data-testid")
        return self._submit_form(response, form_test_id, {}, test_id)

    def _set_organizer(
        self, account_ref: str, login_identifier: str, password: str, *, is_active: bool
    ) -> None:
        response = self.support.request(
            "PUT",
            f"/test-support/authentication/accounts/{account_ref}",
            data=json.dumps(
                {"loginIdentifier": login_identifier, "password": password, "isActive": is_active}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        self._assert_no_content(response, "acceptance account setup")

    def _form_fields(self, form: HtmlNode) -> dict[str, str]:
        fields: dict[str, str] = {}
        for node in form.descendants():
            if node.tag not in {"input", "textarea", "select"}:
                continue
            name = node.attributes.get("name")
            if name and node.attributes.get("type") not in {"submit", "button"}:
                fields[name] = node.attributes.get("value", "")
        return fields

    def _assert_test_ids(
        self, response: BrowserResponse, *, present: list[str], absent: list[str]
    ) -> None:
        document = response.document()
        available = {node.test_id() for node in document.descendants() if node.test_id()}
        for test_id in present:
            self.assertions.assertIn(test_id, available)
        for test_id in absent:
            self.assertions.assertNotIn(test_id, available)

    def _assert_test_id_attributes(
        self, response: BrowserResponse, test_id: str, expected: dict[str, str]
    ) -> None:
        node = self._test_id_node(response.document(), test_id)
        for name, value in expected.items():
            self.assertions.assertEqual(node.attributes.get(name), value)

    def _assert_unauthenticated_controls(self, response: BrowserResponse) -> None:
        self._assert_test_ids(
            response,
            present=[SIGN_IN_FORM],
            absent=UNAUTHENTICATED_FORBIDDEN_TEST_IDS,
        )

    def _assert_no_disclosures(
        self,
        response: BrowserResponse,
        *,
        submitted_password: str | None = None,
    ) -> None:
        self.assertions.assertNotIn(PRIVATE_ORIGIN_CANARY, response.body)
        self.assertions.assertNotIn(PROVIDER_INTERNALS_CANARY, response.body)
        if submitted_password is not None:
            self.assertions.assertNotIn(submitted_password, response.body)
        self._assert_test_ids(response, present=[], absent=DISCLOSURE_TEST_IDS)

    def _normalized_public_content(self, response: BrowserResponse) -> str:
        return repr(self._normalized_node(response.document()))

    def _normalized_node(self, node: HtmlNode) -> tuple[object, ...]:
        attributes = tuple(
            sorted((name, value) for name, value in node.attributes.items() if name != "value")
        )
        own_text = " ".join(part.strip() for part in node.text_parts if part.strip())
        children = tuple(self._normalized_node(child) for child in node.children)
        return node.tag, attributes, own_text, children

    def _assert_json_keys_absent(self, response: BrowserResponse, forbidden: set[str]) -> None:
        try:
            payload = json.loads(response.body)
        except json.JSONDecodeError:
            return
        observed = self._json_keys(payload)
        self.assertions.assertTrue(forbidden.isdisjoint(observed))

    def _json_keys(self, value: object) -> set[str]:
        if isinstance(value, dict):
            nested = set(value)
            for child in value.values():
                nested.update(self._json_keys(child))
            return nested
        if isinstance(value, list):
            nested: set[str] = set()
            for child in value:
                nested.update(self._json_keys(child))
            return nested
        return set()

    def _test_id_text(self, response: BrowserResponse, test_id: str) -> str:
        return " ".join(self._test_id_node(response.document(), test_id).text().split())

    @staticmethod
    def _test_id_node(document: HtmlNode, test_id: str) -> HtmlNode:
        for node in document.descendants():
            if node.test_id() == test_id:
                return node
        raise AssertionError(f"required browser control {test_id} was not found")

    @staticmethod
    def _containing_form(node: HtmlNode) -> HtmlNode | None:
        cursor: HtmlNode | None = node
        while cursor is not None:
            if cursor.tag == "form":
                return cursor
            cursor = cursor.parent
        return None

    def _assert_status(self, response: BrowserResponse, expected: int, context: str) -> None:
        self.assertions.assertEqual(response.status, expected, f"{context}: {response.body}")

    def _assert_no_content(self, response: BrowserResponse, context: str) -> None:
        self._assert_status(response, 204, context)
        self.assertions.assertEqual(response.body, "", context)

    @staticmethod
    def _require(value: BrowserResponse | None, message: str) -> BrowserResponse:
        if value is None:
            raise AssertionError(message)
        return value
