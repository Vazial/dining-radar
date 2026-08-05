"""JS-capable browser DSL for TDR-CS candidate-search acceptance scenarios.

Per ADR-0009, the authenticated candidate-proposal screen renders only an
empty mount point on the server response; candidate cards, the map, the
re-proposal modal, and error surfaces are all produced by client-side
JavaScript. Every observation below therefore reads the real DOM a Chromium
instance (Playwright, ``js_browser_mechanics.py``) produces after running
that script, rather than server-rendered HTML.

Given-seam setup uses only the acceptance-only seams declared in
``contracts/test-support-api.yaml``. Account/session setup composes
``AuthenticationBrowserDsl`` (already-reviewed TDR-AUTH DSL, unchanged by this
ADR) purely for its plain-JSON Given seams (``reset_authentication_state``,
``set_active_organizer``); it is not used to sign in, because signing in must
happen inside the same Playwright browser context that observes the
client-rendered screen afterward. Signing in and every other browser action
here use only the browser control surface declared in
``candidate-search-browser-interface.yaml`` and ``authentication-browser-interface.yaml``
(the sign-in fields are that contract's own vocabulary, reused -- not
reinvented -- for this scenario's Background precondition), or the public
candidate-proposal JSON API declared in ``candidate-search-api.yaml``.

One Then-clause the approved scenarios never require observing at all
(TDR-CS-03's "新しい提案が以前とすべて異なる店舗になるとは限らない") states a
non-constraint -- that full turnover is *allowed*, not required -- so it has
no corresponding assertion here; permitting overlap is exactly what
``repeated_candidate_is_not_excluded`` below verifies.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase
from playwright.sync_api import Page, expect

from tests.acceptance.dsl.authentication_browser import AuthenticationBrowserDsl
from tests.acceptance.dsl.browser_mechanics import HttpBrowser, assert_no_content
from tests.acceptance.dsl.js_browser_mechanics import (
    CapturedApiResponse,
    assert_absent,
    assert_all_absent,
    assert_all_present,
    assert_present,
    by_test_id,
    capture_candidate_proposal_response,
    capture_candidate_proposal_response_with_overridden_body,
    require,
    wait_for_at_least_one,
)
from tests.acceptance.dsl.openapi_schema import assert_matches_openapi_schema

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_API_CONTRACT = PROJECT_ROOT / "contracts" / "candidate-search-api.yaml"

PRIVATE_ORIGIN_CANARY = "synthetic-private-origin-never-disclose.invalid"
PROVIDER_INTERNALS_CANARY = "synthetic-provider-internals-never-disclose"

AUTH_SIGN_IN_FORM = "auth-sign-in-form"
AUTH_LOGIN_IDENTIFIER = "auth-login-identifier"
AUTH_PASSWORD = "auth-password"
AUTH_SIGN_IN_SUBMIT = "auth-sign-in-submit"
AUTHENTICATED_SHELL = "authenticated-application-shell"

CONTENT = "candidate-proposal-content"
CONCEPT_TITLE = "candidate-concept-title"
CONCEPT_RATIONALE = "candidate-concept-rationale"
CARDS = "candidate-proposal-cards"
CARD = "candidate-card"
MAP = "candidate-map"
MAP_MARKER = "candidate-map-marker"
MAP_ATTRIBUTION = "candidate-map-attribution"
PROVIDER_CREDIT = "candidate-provider-credit"
REPROPOSAL_OPEN = "candidate-reproposal-open"
REPROPOSAL_DIALOG = "candidate-reproposal-dialog"
REPROPOSAL_OPTION = "candidate-reproposal-option"
REPROPOSAL_SUBMIT = "candidate-reproposal-submit"
NO_RESULTS = "candidate-no-results"
PROBLEM = "candidate-proposal-problem"
PROBLEM_GUIDANCE = "candidate-proposal-problem-guidance"
SECONDARY_CONDITIONS = "candidate-secondary-conditions"
MANUAL_ORDERING = "candidate-manual-ordering"

CANDIDATE_SCREEN_FORBIDDEN_WHEN_UNAUTHENTICATED = [
    CONTENT,
    MAP,
    REPROPOSAL_OPEN,
    REPROPOSAL_DIALOG,
    SECONDARY_CONDITIONS,
    MANUAL_ORDERING,
    "private-search-origin",
]
DISCLOSURE_FORBIDDEN_TEST_IDS = [
    "private-search-origin",
    "candidate-provider-internals",
    "candidate-origin-marker",
    "candidate-route",
    "candidate-current-location",
]
MAP_FORBIDDEN_TEST_IDS = [
    "candidate-origin-marker",
    "candidate-route",
    "candidate-current-location",
    "candidate-walking-time",
    "private-search-origin",
]
REQUIRED_CARD_FIELDS: dict[str, tuple[str, str | None]] = {
    # (testId, rawValueAttribute) per candidate-search-browser-interface.yaml
    # cardDataAttributes.requiredFields. rawValueAttribute is currently
    # declared only for totalSeats (ADR-0011): its visible value may carry
    # implementation-chosen display formatting (e.g. a unit suffix) around
    # the returned value, so equality is instead checked on that attribute.
    "name": ("candidate-card-name", None),
    "genre": ("candidate-card-genre", None),
    "description": ("candidate-card-description", None),
    "businessHours": ("candidate-card-business-hours", None),
    "regularHoliday": ("candidate-card-regular-holiday", None),
    "totalSeats": ("candidate-card-total-seats", "data-raw-value"),
    "access": ("candidate-card-access", None),
}
PROVIDER_PAGE_LINK_TEST_ID = "candidate-card-provider-page-link"
VALUE_STATES = {"provided", "unavailable"}
ALLOWED_CONTROL_PURPOSES = {
    "candidate-card-selection",
    "candidate-map-marker-selection",
    "reproposal-open",
    "reproposal-selection",
    "reproposal-submit",
    "reproposal-cancel",
    "auth-sign-out",
    "auth-password-change-open",
}
# unavailableControls.forbiddenFormControlCategories: native tag names and,
# for categories with no dedicated HTML element, their WAI-ARIA role
# equivalent. allCandidateScreenFormControlsMustDeclarePurpose applies to
# every element in this union, "whether or not it has a test id" -- so the
# query below must not pre-filter on data-candidate-control-purpose already
# being present, or an undeclared control would be invisible to the check.
# input:not([type='hidden']) excludes the CSRF token field (see
# js_browser_mechanics.csrf_token's docstring): a hidden input carries no
# ARIA role and is not part of the accessibility tree, so it is not a "form
# control" the contract's interactive-control policy is about.
FORM_CONTROL_SELECTOR = ", ".join(
    [
        "select",
        "input:not([type='hidden'])",
        "textarea",
        "button",
        "[role='checkbox']",
        "[role='radio']",
        "[role='range']",
        "[role='combobox']",
        "[role='listbox']",
        "[role='slider']",
        "[role='spinbutton']",
    ]
)

STATUS_BY_PROBLEM_CODE = {
    "PROVIDER_UNAVAILABLE": 503,
    "PROPOSAL_RATE_LIMITED": 429,
    "PROPOSAL_REPROPOSAL_KIND_INVALID": 400,
}


class CandidateSearchBrowserDsl:
    """Business operations for the local browser L4 candidate-search scenarios."""

    def __init__(self, assertions: SimpleTestCase, page: Page, base_url: str) -> None:
        self.assertions = assertions
        self.page = page
        self.base_url = base_url.rstrip("/")
        # Given-seam-only reuse of the already-reviewed TDR-AUTH DSL (see module
        # docstring): account/session test-support setup, never sign-in itself.
        self._auth_seam = AuthenticationBrowserDsl(assertions, base_url)
        self.support = HttpBrowser(base_url)
        self.initial: CapturedApiResponse | None = None
        self.reproposal: CapturedApiResponse | None = None
        self.direct: CapturedApiResponse | None = None

    # Given seams -------------------------------------------------------

    def reset_authentication_state(self) -> None:
        self._auth_seam.reset_authentication_state()

    def enable_organizer(self, account_ref: str, identifier: str, password: str) -> None:
        self._auth_seam.set_active_organizer(account_ref, identifier, password)

    def reset_candidate_state(self) -> None:
        response = self.support.request("DELETE", "/test-support/candidate-proposals/state")
        assert_no_content(self.assertions, response, "candidate-proposal state reset")

    def set_candidate_state(self, mode: str) -> None:
        response = self.support.request(
            "PUT",
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": mode}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, f"candidate-proposal state set to {mode}")

    def assert_no_active_session(self) -> None:
        cookies = self.page.context.cookies()
        self.assertions.assertFalse(
            any(cookie["name"] == "sessionid" for cookie in cookies),
            "browser context already carries an organizer session cookie",
        )

    # Browser actions: sign-in and screen navigation ---------------------

    def sign_in(self, identifier: str, password: str) -> None:
        self.page.goto(f"{self.base_url}/")
        by_test_id(self.page, AUTH_LOGIN_IDENTIFIER).fill(identifier)
        by_test_id(self.page, AUTH_PASSWORD).fill(password)
        by_test_id(self.page, AUTH_SIGN_IN_SUBMIT).click()
        assert_present(self.assertions, self.page, AUTHENTICATED_SHELL)
        # The authenticated screen fetches its own initial proposal on load,
        # so signing in can itself start a POST /candidate-proposals (against
        # whatever candidate state existed before this scenario's Given seed).
        # Draining it here keeps that stray request from racing with the
        # scenario's own explicit "opens the screen" capture below.
        self.page.wait_for_load_state("networkidle")

    def open_candidate_screen_unauthenticated(self) -> None:
        self.page.goto(f"{self.base_url}/")

    def open_candidate_screen(self) -> None:
        self.initial = capture_candidate_proposal_response(
            self.page, lambda: self.page.goto(f"{self.base_url}/")
        )
        # A non-200 status means the body is a ProblemResponse, not a
        # CandidateProposalResponse; the dedicated problem-response
        # assertions (which use the correct schema ref) validate that shape.
        if self.initial.status == 200:
            assert_matches_openapi_schema(
                self.initial.payload,
                CANDIDATE_API_CONTRACT,
                "#/components/schemas/CandidateProposalResponse",
            )

    # Observable assertions: unauthenticated ------------------------------

    def assert_visitor_guided_to_sign_in_without_candidate_surface(self) -> None:
        assert_present(self.assertions, self.page, AUTH_SIGN_IN_FORM)
        assert_all_absent(
            self.assertions, self.page, CANDIDATE_SCREEN_FORBIDDEN_WHEN_UNAUTHENTICATED
        )
        self._assert_no_disclosures()

    # Observable assertions: initial proposal (TDR-CS-01) -----------------

    def assert_initial_proposal_screen(self) -> None:
        assert_all_present(
            self.assertions, self.page, [CONTENT, CARDS, MAP, PROVIDER_CREDIT, REPROPOSAL_OPEN]
        )
        assert_all_absent(
            self.assertions, self.page, [REPROPOSAL_DIALOG, SECONDARY_CONDITIONS, MANUAL_ORDERING]
        )
        self._assert_no_disclosures()

    def assert_initial_concept_has_rationale(self) -> None:
        title = by_test_id(self.page, CONCEPT_TITLE).inner_text().strip()
        rationale = by_test_id(self.page, CONCEPT_RATIONALE).inner_text().strip()
        self.assertions.assertTrue(title)
        self.assertions.assertTrue(rationale)

    def assert_no_duplicate_shops(self) -> None:
        # "同じ店舗は重複して示されない" is a shop-identity claim. candidateRef
        # is documented as an opaque per-response UI identity (not a provider
        # identifier), so its uniqueness alone would not detect the same shop
        # appearing twice under two different opaque refs. data-provider-page-href
        # (cardDataAttributes.repeatComparisonHref) is the contract's own
        # shop-identity comparison key -- the same attribute TDR-CS-03's repeat
        # detection compares across responses -- so duplicate-shop absence is
        # checked on that attribute instead.
        cards = wait_for_at_least_one(self.page, CARD)
        shop_refs = [
            cards.nth(index).get_attribute("data-provider-page-href")
            for index in range(cards.count())
        ]
        self.assertions.assertTrue(cards.count(), "no candidate cards were found to compare")
        self.assertions.assertTrue(
            all(shop_refs), "every candidate card must carry data-provider-page-href"
        )
        self.assertions.assertEqual(
            len(shop_refs),
            len(set(shop_refs)),
            "duplicate shop (data-provider-page-href) shown among initial candidates",
        )

    def assert_provider_credit(self) -> None:
        credit = by_test_id(self.page, PROVIDER_CREDIT)
        expect(credit).to_have_attribute("href", "http://webservice.recruit.co.jp/")
        expect(credit).to_contain_text("Powered by ホットペッパーグルメ Webサービス")

    def assert_no_secondary_conditions_or_manual_sort(self) -> None:
        assert_all_absent(self.assertions, self.page, [SECONDARY_CONDITIONS, MANUAL_ORDERING])
        # Queries every element in a form-control category the contract
        # polices (not only ones that already declare a purpose), so an
        # undeclared or disallowed control cannot silently evade this check.
        controls = self.page.locator(FORM_CONTROL_SELECTOR)
        for index in range(controls.count()):
            purpose = controls.nth(index).get_attribute("data-candidate-control-purpose")
            self.assertions.assertIn(
                purpose,
                ALLOWED_CONTROL_PURPOSES,
                "every candidate-screen form control must declare an allowed "
                "data-candidate-control-purpose",
            )

    def assert_concept_choice_available_only_via_reproposal(self) -> None:
        assert_present(self.assertions, self.page, REPROPOSAL_OPEN)
        assert_absent(self.assertions, self.page, REPROPOSAL_DIALOG)

    # Observable assertions: comparing candidates (TDR-CS-02) -------------

    def assert_cards_and_map_show_current_concept(self) -> None:
        card_refs = self._card_candidate_refs()
        marker_refs = [ref for ref in self._marker_candidate_refs() if ref]
        self.assertions.assertTrue(card_refs, "no candidate cards were found to compare")
        self.assertions.assertEqual(sorted(card_refs), sorted(marker_refs))
        self.assertions.assertEqual(len(marker_refs), len(set(marker_refs)))

    def assert_required_card_fields_match_current_proposal(self) -> None:
        response = require(self.initial, "candidate screen was not opened")
        proposal = response.payload["proposal"]
        self.assertions.assertIsNotNone(proposal)
        candidates_by_ref = {c["candidateRef"]: c for c in proposal["candidates"]}
        cards = wait_for_at_least_one(self.page, CARD)
        for index in range(cards.count()):
            card = cards.nth(index)
            candidate_ref = card.get_attribute("data-candidate-ref")
            self.assertions.assertIn(candidate_ref, candidates_by_ref)
            candidate = candidates_by_ref[candidate_ref]
            for field_name, (test_id, raw_value_attribute) in REQUIRED_CARD_FIELDS.items():
                node = by_test_id(card, test_id)
                value_state = node.get_attribute("data-value-state")
                self.assertions.assertIn(value_state, VALUE_STATES)
                self.assertions.assertTrue(node.get_attribute("data-field-label"))
                expected = candidate[field_name]
                if expected is None:
                    self.assertions.assertEqual(value_state, "unavailable")
                else:
                    self.assertions.assertEqual(value_state, "provided")
                    if raw_value_attribute is None:
                        self.assertions.assertEqual(node.inner_text().strip(), str(expected))
                    else:
                        self.assertions.assertEqual(
                            node.get_attribute(raw_value_attribute), str(expected)
                        )
            link = by_test_id(card, PROVIDER_PAGE_LINK_TEST_ID)
            self.assertions.assertEqual(link.get_attribute("data-value-state"), "provided")
            self.assertions.assertEqual(link.get_attribute("href"), candidate["providerPageUrl"])

    def assert_map_attribution_and_fit(self) -> None:
        map_node = by_test_id(self.page, MAP)
        expect(map_node).to_have_attribute("data-map-fit-state", "displayed-candidates")
        expect(map_node).to_have_attribute("data-map-tile-provider", "openstreetmap-standard")
        attribution = by_test_id(self.page, MAP_ATTRIBUTION)
        expect(attribution).to_have_attribute("href", "https://www.openstreetmap.org/copyright")
        expect(attribution).to_contain_text("OpenStreetMap contributors")

    def assert_map_has_no_forbidden_surfaces(self) -> None:
        assert_all_absent(self.assertions, self.page, MAP_FORBIDDEN_TEST_IDS)

    def select_first_card_and_verify_marker_highlighted(self) -> None:
        cards = wait_for_at_least_one(self.page, CARD)
        target = cards.first
        target_ref = target.get_attribute("data-candidate-ref")
        self.assertions.assertTrue(target_ref)
        target.click()
        expect(target).to_have_attribute("data-selection-state", "selected")
        marker = self.page.locator(
            f'[data-testid="{MAP_MARKER}"][data-candidate-ref="{target_ref}"]'
        )
        expect(marker).to_have_attribute("data-selection-state", "selected")
        self._assert_all_other_cards_and_markers_unselected(target_ref)

    def select_first_marker_and_verify_card_highlighted(self) -> None:
        markers = wait_for_at_least_one(self.page, MAP_MARKER)
        target = markers.first
        target_ref = target.get_attribute("data-candidate-ref")
        self.assertions.assertTrue(target_ref)
        target.click()
        expect(target).to_have_attribute("data-selection-state", "selected")
        card = self.page.locator(f'[data-testid="{CARD}"][data-candidate-ref="{target_ref}"]')
        expect(card).to_have_attribute("data-selection-state", "selected")
        self._assert_all_other_cards_and_markers_unselected(target_ref)

    # Observable assertions and actions: re-proposal (TDR-CS-03) ----------

    def open_reproposal_popup(self) -> None:
        url_before = self.page.url
        by_test_id(self.page, REPROPOSAL_OPEN).click()
        assert_present(self.assertions, self.page, REPROPOSAL_DIALOG)
        self.assertions.assertEqual(
            self.page.url, url_before, "opening the re-proposal dialog must not navigate"
        )

    def assert_reproposal_options_bounded_and_exclude_current(self) -> None:
        options = wait_for_at_least_one(self.page, REPROPOSAL_OPTION)
        count = options.count()
        self.assertions.assertLessEqual(count, 3)
        current_kind = require(self.initial, "candidate screen was not opened").payload["proposal"][
            "kind"
        ]
        for index in range(count):
            kind = options.nth(index).get_attribute("data-reproposal-kind")
            self.assertions.assertNotEqual(kind, current_kind)

    def select_and_submit_first_offered_lens(self) -> str:
        options = wait_for_at_least_one(self.page, REPROPOSAL_OPTION)
        first_option = options.first
        chosen_kind = first_option.get_attribute("data-reproposal-kind")
        self.assertions.assertTrue(chosen_kind)
        first_option.click()

        def trigger() -> None:
            by_test_id(self.page, REPROPOSAL_SUBMIT).click()

        self.reproposal = capture_candidate_proposal_response(self.page, trigger)
        assert_matches_openapi_schema(
            self.reproposal.payload,
            CANDIDATE_API_CONTRACT,
            "#/components/schemas/CandidateProposalResponse",
        )
        return chosen_kind

    def assert_display_replaced_by_reproposal(self, chosen_kind: str) -> None:
        assert_absent(self.assertions, self.page, REPROPOSAL_DIALOG)
        response = require(self.reproposal, "re-proposal was not requested")
        proposal = response.payload["proposal"]
        self.assertions.assertIsNotNone(proposal)
        self.assertions.assertEqual(proposal["kind"], chosen_kind)
        expected_refs = {c["candidateRef"] for c in proposal["candidates"]}
        displayed_card_refs = set(self._card_candidate_refs())
        displayed_marker_refs = {ref for ref in self._marker_candidate_refs() if ref}
        self.assertions.assertEqual(displayed_card_refs, expected_refs)
        self.assertions.assertEqual(displayed_marker_refs, expected_refs)

    def assert_repeat_priority_orders_new_before_repeated(self) -> None:
        cards = wait_for_at_least_one(self.page, CARD)
        count = cards.count()
        previous_hrefs = {
            c["providerPageUrl"]
            for c in require(self.initial, "candidate screen was not opened").payload["proposal"][
                "candidates"
            ]
        }
        statuses: list[str] = []
        for index in range(count):
            card = cards.nth(index)
            status = card.get_attribute("data-repeat-status")
            self.assertions.assertIn(status, {"new", "repeated"})
            href = card.get_attribute("data-provider-page-href")
            self.assertions.assertTrue(href)
            if status == "repeated":
                self.assertions.assertIn(href, previous_hrefs)
            else:
                self.assertions.assertNotIn(href, previous_hrefs)
            statuses.append(status)
        self.assertions.assertIn("new", statuses, "the synthetic re-proposal has no new candidate")
        self.assertions.assertIn(
            "repeated", statuses, "the synthetic re-proposal has no repeated candidate"
        )
        last_new_index = max(index for index, status in enumerate(statuses) if status == "new")
        first_repeated_index = min(
            index for index, status in enumerate(statuses) if status == "repeated"
        )
        self.assertions.assertLess(
            last_new_index,
            first_repeated_index,
            "every new candidate card must precede every repeated candidate card",
        )

    def assert_repeated_candidate_not_excluded(self) -> None:
        previous = require(self.initial, "candidate screen was not opened").payload["proposal"]
        new = require(self.reproposal, "re-proposal was not requested").payload["proposal"]
        previous_urls = {c["providerPageUrl"] for c in previous["candidates"]}
        new_urls = {c["providerPageUrl"] for c in new["candidates"]}
        self.assertions.assertTrue(
            previous_urls & new_urls,
            "the seeded repeat candidate (same providerPageUrl) was excluded from the new proposal",
        )

    # Observable assertions: empty / unavailable / rate-limited -----------

    def assert_no_results_shown(self) -> None:
        assert_present(self.assertions, self.page, NO_RESULTS)
        assert_all_absent(self.assertions, self.page, [CARDS, MAP, PROBLEM])
        self._assert_no_disclosures()

    def assert_no_results_from_captured_api(self) -> None:
        response = require(self.initial, "candidate screen was not opened")
        self.assertions.assertEqual(response.status, 200)
        self.assertions.assertIsNone(response.payload["proposal"])

    def assert_screen_has_no_private_disclosures(self) -> None:
        self._assert_no_disclosures()

    def assert_safe_unavailable_guidance(self, expected_code: str) -> None:
        problem = assert_present(self.assertions, self.page, PROBLEM)
        guidance = assert_present(self.assertions, self.page, PROBLEM_GUIDANCE)
        expect(problem).to_have_attribute("data-problem-code", expected_code)
        self.assertions.assertTrue(guidance.inner_text().strip())
        assert_all_absent(self.assertions, self.page, [CARDS, MAP])
        self._assert_no_disclosures()

    def assert_captured_problem_matches_schema(self, expected_code: str) -> None:
        self._assert_problem_response(
            require(self.initial, "candidate screen was not opened"), expected_code
        )

    def assert_direct_problem_matches_schema(self, expected_code: str) -> None:
        response = require(self.direct, "direct candidate-proposal request was not sent")
        self._assert_problem_response(response, expected_code)
        # browserActions.requestUnavailableEnumLens.requiredOutcome.present:
        # the rejection surfaces on the same real DOM/request cycle a UI
        # re-proposal submission produces (see request_unsupported_lens_directly),
        # not only in the captured API response.
        problem = assert_present(self.assertions, self.page, PROBLEM)
        guidance = assert_present(self.assertions, self.page, PROBLEM_GUIDANCE)
        expect(problem).to_have_attribute("data-problem-code", expected_code)
        self.assertions.assertTrue(guidance.inner_text().strip())
        self._assert_no_disclosures()

    def request_unsupported_lens_directly(self, kind: str) -> None:
        # requestUnavailableEnumLens exists because the offered chosen kind
        # (AMENITY_REFERENCE) is, by this scenario's own precondition, not
        # among the reproposal dialog's currently offered options -- there is
        # no clickable UI option for it. Opening the dialog and submitting a
        # different, actually-offered option keeps the request on the real
        # UI-driven request/response code path the contract's requiredOutcome
        # observes; only the outgoing body is substituted for the contract's
        # exact publicOperation.requestBody before it reaches the server, so
        # the app's own client-side handling renders the rejection outcome
        # from a genuine server response rather than from a side-channel call
        # its JavaScript never sees.
        self.open_reproposal_popup()
        offered_option = wait_for_at_least_one(self.page, REPROPOSAL_OPTION).first
        offered_option.click()

        def trigger() -> None:
            by_test_id(self.page, REPROPOSAL_SUBMIT).click()

        self.direct = capture_candidate_proposal_response_with_overridden_body(
            self.page, trigger, {"reproposalKind": kind}
        )

    # Private helpers -------------------------------------------------------

    def _card_candidate_refs(self) -> list[str]:
        cards = wait_for_at_least_one(self.page, CARD)
        refs = [cards.nth(i).get_attribute("data-candidate-ref") for i in range(cards.count())]
        return [ref for ref in refs if ref]

    def _marker_candidate_refs(self) -> list[str | None]:
        markers = wait_for_at_least_one(self.page, MAP_MARKER)
        return [markers.nth(i).get_attribute("data-candidate-ref") for i in range(markers.count())]

    def _assert_all_other_cards_and_markers_unselected(self, selected_ref: str) -> None:
        cards = by_test_id(self.page, CARD)
        for index in range(cards.count()):
            node = cards.nth(index)
            if node.get_attribute("data-candidate-ref") != selected_ref:
                expect(node).to_have_attribute("data-selection-state", "unselected")
        markers = by_test_id(self.page, MAP_MARKER)
        for index in range(markers.count()):
            node = markers.nth(index)
            if node.get_attribute("data-candidate-ref") != selected_ref:
                expect(node).to_have_attribute("data-selection-state", "unselected")

    def _assert_problem_response(self, response: CapturedApiResponse, expected_code: str) -> None:
        self.assertions.assertEqual(response.status, STATUS_BY_PROBLEM_CODE[expected_code])
        assert_matches_openapi_schema(
            response.payload, CANDIDATE_API_CONTRACT, "#/components/schemas/ProblemResponse"
        )
        self.assertions.assertEqual(response.payload["code"], expected_code)
        self.assertions.assertTrue(response.payload.get("message"))
        self.assertions.assertNotIn(PRIVATE_ORIGIN_CANARY, response.body)
        self.assertions.assertNotIn(PROVIDER_INTERNALS_CANARY, response.body)
        if expected_code == "PROPOSAL_RATE_LIMITED":
            self.assertions.assertIsNotNone(response.retry_after)
            self.assertions.assertGreaterEqual(int(response.retry_after), 1)

    def _assert_no_disclosures(self) -> None:
        html = self.page.content()
        self.assertions.assertNotIn(PRIVATE_ORIGIN_CANARY, html)
        self.assertions.assertNotIn(PROVIDER_INTERNALS_CANARY, html)
        assert_all_absent(self.assertions, self.page, DISCLOSURE_FORBIDDEN_TEST_IDS)
