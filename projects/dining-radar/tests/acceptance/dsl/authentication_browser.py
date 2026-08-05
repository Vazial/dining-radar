"""Public-browser DSL for TDR-AUTH acceptance scenarios.

The only setup operations in this module are the acceptance-only seams declared
in ``contracts/test-support-api.yaml``. Every user operation and assertion uses
the browser control surface from ``authentication-browser-interface.yaml`` or
the public candidate-proposal API contract.

Generic HTTP/HTML mechanics (cookie-jar browser, data-testid lookup, form
submission) live in ``browser_mechanics.py`` and are shared with
``candidate_search_browser.py`` rather than duplicated.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase

from tests.acceptance.dsl.browser_mechanics import (
    BrowserResponse,
    HtmlNode,
    HttpBrowser,
    activate_control,
    assert_no_content,
    assert_status,
    assert_test_ids,
    require,
    submit_form,
    test_id_node,
)
from tests.acceptance.dsl.openapi_schema import assert_matches_openapi_schema

SIGN_IN_FORM = "auth-sign-in-form"
APPLICATION_SHELL = "authenticated-application-shell"
SIGN_IN_FAILURE = "auth-sign-in-failure"
THROTTLED_FAILURE = "auth-sign-in-throttled"
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
        assert_no_content(self.assertions, response, "authentication-state reset")

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
        assert_no_content(self.assertions, response, "login-throttle seed")

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
        initial = require(self.entry_response, "browser entry was not opened")
        sign_up = self.browser.request("GET", "/sign-up", follow_redirects=False)
        password_reset = self.browser.request("GET", "/password-reset", follow_redirects=False)
        self.sign_in("synthetic-public-operation-unknown", "synthetic-public-operation-secret")
        generic_failure = require(self.last_response, "generic failure was not returned")
        self.seed_throttled_sign_in("synthetic-public-operation-throttled")
        self.open_entry()
        self.sign_in("synthetic-public-operation-throttled", "synthetic-throttled-secret")
        throttled_failure = require(self.last_response, "throttled failure was not returned")
        self.public_operation_responses = [
            initial,
            sign_up,
            password_reset,
            generic_failure,
            throttled_failure,
        ]

    def sign_in(self, login_identifier: str, password: str) -> None:
        entry = require(self.entry_response, "sign-in requires the browser entry document")
        self.last_response = submit_form(
            self.browser,
            entry,
            SIGN_IN_FORM,
            {
                "auth-login-identifier": login_identifier,
                "auth-password": password,
            },
            "auth-sign-in-submit",
        )

    def sign_out(self) -> None:
        response = require(self.last_response, "sign-out requires an authenticated document")
        self.last_response = activate_control(self.browser, response, "auth-sign-out")

    def open_password_change(self) -> None:
        response = require(self.last_response, "password change requires an authenticated document")
        self.last_response = activate_control(self.browser, response, "auth-password-change-open")

    def change_password(self, current_password: str, new_password: str) -> None:
        response = require(self.last_response, "password change form must be open")
        self.last_response = submit_form(
            self.browser,
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
        response = require(self.entry_response, "browser entry was not opened")
        assert_status(self.assertions, response, 200, "unauthenticated entry")
        self._assert_unauthenticated_controls(response)
        self._assert_no_disclosures(response)

    def assert_candidate_api_requires_authentication(self) -> None:
        response = require(self.candidate_response, "candidate API was not requested")
        assert_status(self.assertions, response, 401, "unauthenticated candidate proposal API")
        payload = json.loads(response.body)
        assert_matches_openapi_schema(
            payload,
            CANDIDATE_API_CONTRACT,
            "#/components/schemas/ProblemResponse",
        )
        self.assertions.assertEqual(payload["code"], "AUTHENTICATION_REQUIRED")
        self._assert_no_disclosures(response)

    def assert_authenticated_shell(self) -> None:
        response = require(self.last_response, "no browser response to inspect")
        assert_status(self.assertions, response, 200, "authenticated browser outcome")
        assert_test_ids(
            self.assertions,
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
            assert_test_ids(
                self.assertions,
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
        assert_status(self.assertions, sign_up, 404, "public sign-up route probe")
        assert_status(self.assertions, password_reset, 404, "email password-reset route probe")
        self._assert_json_keys_absent(password_reset, {"token", "resetToken", "email"})
        self._assert_no_disclosures(sign_up)
        self._assert_no_disclosures(password_reset)

    def assert_signed_out(self) -> None:
        response = require(self.last_response, "no sign-out response to inspect")
        assert_test_ids(
            self.assertions,
            response,
            present=[SIGN_IN_FORM],
            absent=[APPLICATION_SHELL, "auth-sign-out"],
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
        response = require(self.last_response, "no sign-in response to inspect")
        assert_test_ids(
            self.assertions,
            response,
            present=[SIGN_IN_FORM, SIGN_IN_FAILURE],
            absent=[*UNAUTHENTICATED_FORBIDDEN_TEST_IDS, THROTTLED_FAILURE],
        )
        self._assert_no_disclosures(response, submitted_password=password)
        return self._normalized_public_content(response)

    def assert_throttled_sign_in_failure(self, password: str) -> str:
        response = require(self.last_response, "no sign-in response to inspect")
        assert_test_ids(
            self.assertions,
            response,
            present=[SIGN_IN_FORM, THROTTLED_FAILURE],
            absent=UNAUTHENTICATED_FORBIDDEN_TEST_IDS,
        )
        self._assert_no_disclosures(response, submitted_password=password)
        return self._normalized_public_content(response)

    # Private helpers ------------------------------------------------------

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
        assert_no_content(self.assertions, response, "acceptance account setup")

    def _assert_unauthenticated_controls(self, response: BrowserResponse) -> None:
        assert_test_ids(
            self.assertions,
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
        assert_test_ids(self.assertions, response, present=[], absent=DISCLOSURE_TEST_IDS)

    def _assert_test_id_attributes(
        self, response: BrowserResponse, test_id: str, expected: dict[str, str]
    ) -> None:
        node = test_id_node(response.document(), test_id)
        for name, value in expected.items():
            self.assertions.assertEqual(node.attributes.get(name), value)

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

    @staticmethod
    def _require(value: BrowserResponse | None, message: str) -> BrowserResponse:
        return require(value, message)  # type: ignore[return-value]
