"""Browser DSL for the filter-model TDR-CS acceptance scenarios.

Candidate setup uses only the acceptance-only seam declared in
``contracts/test-support-api.yaml``. Every observed action uses Chromium
against the same-origin screen or its public candidate-proposal endpoint.
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

from django.test import SimpleTestCase
from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

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
    is_candidate_proposal_request,
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
CARDS = "candidate-proposal-cards"
CARD = "candidate-card"
MAP = "candidate-map"
MAP_MARKER = "candidate-map-marker"
MAP_ATTRIBUTION = "candidate-map-attribution"
PROVIDER_CREDIT = "candidate-provider-credit"
FILTER_OPEN = "candidate-filter-open"
FILTER_PANEL = "candidate-filter-panel"
FILTER_GENRE_OPTION = "candidate-filter-genre-option"
FILTER_GENRE_OVERFLOW = "candidate-filter-genre-overflow"
FILTER_INCLUDE_IZAKAYA_BAR = "candidate-filter-include-izakaya-bar"
FILTER_NON_SMOKING_ONLY = "candidate-filter-non-smoking-only"
FILTER_CARD_PAYMENT_ONLY = "candidate-filter-card-payment-only"
FILTER_BUDGET_TIER_OPTION = "candidate-filter-budget-tier-option"
FILTER_APPLY = "candidate-filter-apply"
FILTER_REVERT = "candidate-filter-revert"
FILTER_PENDING_NOTE = "candidate-filter-pending-note"
SEARCH_AGAIN = "candidate-search-again"
IZAKAYA_BAR_FALLBACK_NOTICE = "candidate-izakaya-bar-fallback-notice"
BUDGET_TIER_NOTE = "candidate-budget-tier-note"
NO_RESULTS = "candidate-no-results"
PROBLEM = "candidate-proposal-problem"
PROBLEM_GUIDANCE = "candidate-proposal-problem-guidance"
MANUAL_ORDERING = "candidate-manual-ordering"

DISCLOSURE_FORBIDDEN_TEST_IDS = [
    "private-search-origin",
    "candidate-provider-internals",
    "candidate-origin-marker",
    "candidate-route",
    "candidate-current-location",
]
MAP_FORBIDDEN_TEST_IDS = [*DISCLOSURE_FORBIDDEN_TEST_IDS, "candidate-walking-time"]
UNAUTHENTICATED_FORBIDDEN_TEST_IDS = [
    CONTENT,
    CARDS,
    CARD,
    MAP,
    MAP_MARKER,
    MAP_ATTRIBUTION,
    PROVIDER_CREDIT,
    FILTER_OPEN,
    FILTER_PANEL,
    SEARCH_AGAIN,
    BUDGET_TIER_NOTE,
    MANUAL_ORDERING,
    "private-search-origin",
]
REQUIRED_CARD_FIELDS: dict[str, tuple[str, str | None]] = {
    "name": ("candidate-card-name", None),
    "genre": ("candidate-card-genre", None),
    "description": ("candidate-card-description", None),
    "regularHoliday": ("candidate-card-regular-holiday", None),
    "totalSeats": ("candidate-card-total-seats", "data-raw-value"),
    "nonSmokingStatus": ("candidate-card-non-smoking", "data-raw-value"),
    "dinnerBudgetTier": ("candidate-card-dinner-budget", "data-raw-value"),
}
CARD_PAYMENT_CAUTION_TEST_ID = "candidate-card-payment-caution"
CARD_PAYMENT_CAUTION_ATTRIBUTE = "data-card-payment-available"
CARD_PAYMENT_VALUE_STATE_ATTRIBUTE = "data-card-payment-value-state"
PROVIDER_PAGE_LINK_TEST_ID = "candidate-card-provider-page-link"
ALLOWED_CONTROL_PURPOSES = {
    "candidate-card-selection",
    "candidate-map-marker-selection",
    "candidate-filter-open",
    "candidate-filter-genre-selection",
    "candidate-filter-genre-overflow-toggle",
    "candidate-filter-izakaya-bar-toggle",
    "candidate-filter-non-smoking-toggle",
    "candidate-filter-card-payment-toggle",
    "candidate-filter-budget-tier-selection",
    "candidate-filter-apply",
    "candidate-filter-revert",
    "candidate-search-again",
    "auth-sign-out",
    "auth-password-change-open",
    "auth-account-menu-toggle",
}
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
LOCATION_RANGE_FORBIDDEN_TEST_IDS = [
    "candidate-search-origin",
    "candidate-search-location",
    "candidate-current-location-control",
    "candidate-search-range",
    "candidate-search-radius",
    "candidate-search-distance",
]
LOCATION_RANGE_FORBIDDEN_TOKENS = [
    "検索地点",
    "検索場所",
    "検索基点",
    "起点",
    "現在地",
    "探索範囲",
    "検索範囲",
    "半径",
    "距離",
    "search-location",
    "search-origin",
    "current-location",
    "search-range",
    "radius",
    "distance",
]
STATUS_BY_PROBLEM_CODE = {"PROVIDER_UNAVAILABLE": 503, "PROPOSAL_RATE_LIMITED": 429}


class CandidateSearchBrowserDsl:
    def __init__(self, assertions: SimpleTestCase, page: Page, base_url: str) -> None:
        self.assertions = assertions
        self.page = page
        self.base_url = base_url.rstrip("/")
        self._auth_seam = AuthenticationBrowserDsl(assertions, base_url)
        self.support = HttpBrowser(base_url)
        self.initial: CapturedApiResponse | None = None
        self.current: CapturedApiResponse | None = None
        self.search_again_response: CapturedApiResponse | None = None
        self.original_seed_response: CapturedApiResponse | None = None
        self._expected_changed_filter: tuple[str, object] | None = None
        self._applied_filters: dict[str, object] = self._normalized_filters({})
        self._pending_filters: dict[str, object] | None = None

    # Given seams ---------------------------------------------------------

    def reset_authentication_state(self) -> None:
        self._auth_seam.reset_authentication_state()

    def enable_organizer(self, account_ref: str, identifier: str, password: str) -> None:
        self._auth_seam.set_active_organizer(account_ref, identifier, password)

    def reset_candidate_state(self) -> None:
        response = self.support.request("DELETE", "/test-support/candidate-proposals/state")
        assert_no_content(self.assertions, response, "candidate-proposal state reset")

    def set_candidate_state(self, mode: str, random_seed: int | None = None) -> None:
        payload: dict[str, object] = {"mode": mode}
        if random_seed is not None:
            payload["randomSeed"] = random_seed
        response = self.support.request(
            "PUT",
            "/test-support/candidate-proposals/state",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, f"candidate-proposal state set to {mode}")

    def assert_no_active_session(self) -> None:
        self.assertions.assertFalse(
            any(cookie["name"] == "sessionid" for cookie in self.page.context.cookies())
        )

    # Browser actions -----------------------------------------------------

    def sign_in(self, identifier: str, password: str) -> None:
        self.page.goto(f"{self.base_url}/")
        by_test_id(self.page, AUTH_LOGIN_IDENTIFIER).fill(identifier)
        by_test_id(self.page, AUTH_PASSWORD).fill(password)
        by_test_id(self.page, AUTH_SIGN_IN_SUBMIT).click()
        assert_present(self.assertions, self.page, AUTHENTICATED_SHELL)
        self.page.wait_for_load_state("networkidle")

    def open_candidate_screen_unauthenticated(self) -> None:
        self.page.goto(f"{self.base_url}/")

    def open_candidate_screen(self) -> None:
        self.initial = capture_candidate_proposal_response(
            self.page, lambda: self.page.goto(f"{self.base_url}/")
        )
        self.current = self.initial
        if self.initial.status == 200:
            self._current_proposal()
            self._applied_filters = self._normalized_filters(self._current_filters())
            self._pending_filters = dict(self._applied_filters)

    def open_filter_panel(self) -> None:
        url_before = self.page.url
        by_test_id(self.page, FILTER_OPEN).click()
        assert_all_present(
            self.assertions,
            self.page,
            [
                FILTER_PANEL,
                FILTER_INCLUDE_IZAKAYA_BAR,
                FILTER_NON_SMOKING_ONLY,
                FILTER_CARD_PAYMENT_ONLY,
                FILTER_BUDGET_TIER_OPTION,
                BUDGET_TIER_NOTE,
            ],
        )
        self.assertions.assertEqual(self.page.url, url_before)
        if self._pending_filters is None:
            self._pending_filters = dict(self._applied_filters)
        self._assert_genre_presentation()
        budgets = wait_for_at_least_one(self.page, FILTER_BUDGET_TIER_OPTION)
        self.assertions.assertEqual(
            [
                budgets.nth(index).get_attribute("data-budget-tier-value")
                for index in range(budgets.count())
            ],
            ["LOW", "MID", "HIGH"],
        )

    def enable_card_payment_only(self) -> None:
        self._change_pending_filters(
            lambda: by_test_id(self.page, FILTER_CARD_PAYMENT_ONLY).click(),
            {"cardPaymentOnly": True},
        )
        self._expected_changed_filter = ("cardPaymentOnly", True)

    def enable_include_izakaya_bar(self) -> None:
        self._change_pending_filters(
            lambda: by_test_id(self.page, FILTER_INCLUDE_IZAKAYA_BAR).click(),
            {"includeIzakayaBar": True},
        )
        self._expected_changed_filter = ("includeIzakayaBar", True)

    def enable_low_budget_tier(self) -> None:
        self._change_pending_filters(
            lambda: self._click_budget_tier("LOW"), {"budgetTiers": ["LOW"]}
        )

    def enable_filter_with_unknown_candidate_information(self) -> None:
        filters = self._unknown_safe_filter_configuration()

        def trigger() -> None:
            self._click_genre_option(filters["genres"][0])
            if filters["nonSmokingOnly"]:
                by_test_id(self.page, FILTER_NON_SMOKING_ONLY).click()
            if filters["cardPaymentOnly"]:
                by_test_id(self.page, FILTER_CARD_PAYMENT_ONLY).click()
            for tier in filters["budgetTiers"]:
                self._click_budget_tier(tier)

        self._change_pending_filters(trigger, filters)
        self._expected_changed_filter = ("unknownSoftFilter", True)

    def enable_filters_that_require_izakaya_fallback(self) -> None:
        filters: dict[str, object] = {
            "genres": [],
            "includeIzakayaBar": False,
            "nonSmokingOnly": True,
            "cardPaymentOnly": True,
            "budgetTiers": ["LOW"],
        }

        def trigger() -> None:
            by_test_id(self.page, FILTER_NON_SMOKING_ONLY).click()
            by_test_id(self.page, FILTER_CARD_PAYMENT_ONLY).click()
            self._click_budget_tier("LOW")

        self._change_pending_filters(trigger, filters)

    def enable_explicit_genre_with_no_matches(self) -> None:
        available = self._current_proposal()["availableGenres"]
        self.assertions.assertEqual(len(available), 1)
        filters: dict[str, object] = {
            "genres": [available[0]],
            "includeIzakayaBar": False,
            "nonSmokingOnly": True,
            "cardPaymentOnly": False,
            "budgetTiers": [],
        }

        def trigger() -> None:
            self._click_genre_option(available[0])
            by_test_id(self.page, FILTER_CARD_PAYMENT_ONLY).click()
            self._click_budget_tier("LOW")

        self._change_pending_filters(trigger, filters)

    def revert_pending_filters(self) -> None:
        snapshot = self._display_snapshot()
        self._perform_without_candidate_request(
            lambda: by_test_id(self.page, FILTER_REVERT).click()
        )
        self._pending_filters = dict(self._applied_filters)
        assert_present(self.assertions, self.page, FILTER_PANEL)
        assert_all_absent(
            self.assertions, self.page, [FILTER_PENDING_NOTE, FILTER_REVERT, FILTER_APPLY]
        )
        expect(by_test_id(self.page, SEARCH_AGAIN)).to_be_enabled()
        self._assert_display_snapshot(snapshot)

    def close_filter_panel_preserving_pending(self) -> None:
        snapshot = self._display_snapshot()
        pending_before = dict(require(self._pending_filters, "filter panel was not opened"))
        self._perform_without_candidate_request(lambda: by_test_id(self.page, FILTER_OPEN).click())
        assert_all_absent(self.assertions, self.page, [FILTER_PANEL, BUDGET_TIER_NOTE])
        self.assertions.assertEqual(self._pending_filters, pending_before)
        self._assert_display_snapshot(snapshot)

    def reopen_filter_panel_with_pending_filters(self) -> None:
        pending_before = dict(require(self._pending_filters, "filter panel was not opened"))
        self._perform_without_candidate_request(lambda: by_test_id(self.page, FILTER_OPEN).click())
        assert_present(self.assertions, self.page, FILTER_PANEL)
        self.assertions.assertEqual(self._pending_filters, pending_before)
        if self._pending_filters != self._applied_filters:
            self._assert_dirty_filter_actions()

    def apply_filters(self) -> None:
        def trigger() -> None:
            by_test_id(self.page, FILTER_APPLY).click()

        self.current = capture_candidate_proposal_response(self.page, trigger)
        self._current_proposal()
        self._applied_filters = self._normalized_filters(self._current_filters())
        self._pending_filters = dict(self._applied_filters)

    def search_again(self) -> None:
        def trigger() -> None:
            by_test_id(self.page, SEARCH_AGAIN).click()

        response = capture_candidate_proposal_response(self.page, trigger)
        self.current = response
        self._current_proposal()
        self._applied_filters = self._normalized_filters(self._current_filters())
        self._pending_filters = dict(self._applied_filters)
        if self.search_again_response is None:
            self.search_again_response = response
        else:
            self.original_seed_response = response

    # Then: initial/authenticated screen ---------------------------------

    def assert_visitor_guided_to_sign_in_without_candidate_surface(self) -> None:
        assert_present(self.assertions, self.page, AUTH_SIGN_IN_FORM)
        assert_all_absent(self.assertions, self.page, UNAUTHENTICATED_FORBIDDEN_TEST_IDS)
        self._assert_no_disclosures()

    def assert_initial_proposal_screen(self) -> None:
        assert_all_present(
            self.assertions,
            self.page,
            [CONTENT, CARDS, MAP, PROVIDER_CREDIT, FILTER_OPEN, SEARCH_AGAIN],
        )
        assert_all_absent(self.assertions, self.page, [FILTER_PANEL, MANUAL_ORDERING])
        self.assert_current_display_ordering()
        self._assert_no_disclosures()

    def assert_filter_panel_is_closed_until_requested(self) -> None:
        assert_present(self.assertions, self.page, FILTER_OPEN)
        assert_all_absent(self.assertions, self.page, [FILTER_PANEL, BUDGET_TIER_NOTE])

    def assert_no_duplicate_shops(self) -> None:
        urls = [
            candidate["providerPageUrl"] for candidate in self._current_proposal()["candidates"]
        ]
        self.assertions.assertTrue(urls)
        self.assertions.assertEqual(len(urls), len(set(urls)))

    def assert_provider_credit(self) -> None:
        credit = assert_present(self.assertions, self.page, PROVIDER_CREDIT)
        expected = self._current_proposal()["providerCredit"]
        expect(credit).to_have_attribute("href", expected["url"])
        self.assertions.assertEqual(credit.inner_text().strip(), expected["text"])

    def assert_screen_has_no_private_disclosures(self) -> None:
        self._assert_no_disclosures()

    def assert_no_location_range_or_manual_order_control(self) -> None:
        assert_all_absent(
            self.assertions,
            self.page,
            [
                MANUAL_ORDERING,
                *DISCLOSURE_FORBIDDEN_TEST_IDS,
                *LOCATION_RANGE_FORBIDDEN_TEST_IDS,
            ],
        )
        controls = self.page.locator(FORM_CONTROL_SELECTOR)
        for index in range(controls.count()):
            control = controls.nth(index)
            if control.locator(f'xpath=ancestor::*[@data-testid="{MAP}"]').count():
                continue
            purpose = control.get_attribute("data-candidate-control-purpose")
            self.assertions.assertIn(purpose, ALLOWED_CONTROL_PURPOSES)
            observed_semantics = " ".join(
                filter(
                    None,
                    [
                        purpose,
                        control.get_attribute("id"),
                        control.get_attribute("name"),
                        control.get_attribute("data-testid"),
                        control.get_attribute("aria-label"),
                        control.get_attribute("title"),
                        control.inner_text().strip(),
                    ],
                )
            ).casefold()
            for forbidden in LOCATION_RANGE_FORBIDDEN_TOKENS:
                self.assertions.assertNotIn(forbidden.casefold(), observed_semantics)
            self.assertions.assertNotIn(
                purpose,
                {
                    "sort",
                    "manual-ordering",
                    "free-text-search",
                    "search-origin",
                    "search-location",
                    "current-location",
                    "search-range",
                    "radius",
                    "distance",
                },
            )

    # Then: cards, map, and disclosures ----------------------------------

    def assert_cards_and_map_show_current_proposal(self) -> None:
        candidates = self._current_proposal()["candidates"]
        expected_refs = [candidate["candidateRef"] for candidate in candidates]
        cards = self._card_candidate_refs()
        markers = [ref for ref in self._marker_candidate_refs() if ref]
        self.assertions.assertEqual(cards, expected_refs)
        self.assertions.assertEqual(sorted(markers), sorted(expected_refs))
        self.assertions.assertEqual(len(markers), len(set(markers)))

    def assert_required_card_fields_match_current_proposal(self) -> None:
        cards, candidates_by_ref = self._current_cards_by_candidate_ref()
        for index in range(cards.count()):
            card = cards.nth(index)
            candidate = candidates_by_ref[card.get_attribute("data-candidate-ref")]
            for field, (test_id, raw_attribute) in REQUIRED_CARD_FIELDS.items():
                node = by_test_id(card, test_id)
                self.assertions.assertTrue(node.get_attribute("data-field-label"))
                expected = candidate[field]
                if expected is None:
                    self.assertions.assertEqual(
                        node.get_attribute("data-value-state"), "unavailable"
                    )
                    if raw_attribute:
                        self.assertions.assertIsNone(node.get_attribute(raw_attribute))
                else:
                    self.assertions.assertEqual(node.get_attribute("data-value-state"), "provided")
                    actual = (
                        node.get_attribute(raw_attribute)
                        if raw_attribute
                        else node.inner_text().strip()
                    )
                    self.assertions.assertEqual(actual, str(expected))
            link = by_test_id(card, PROVIDER_PAGE_LINK_TEST_ID)
            self.assertions.assertEqual(link.get_attribute("data-value-state"), "provided")
            self.assertions.assertEqual(link.get_attribute("href"), candidate["providerPageUrl"])

    def assert_dinner_budget_reference_is_shown(self) -> None:
        notes = by_test_id(self.page, BUDGET_TIER_NOTE)
        self.assertions.assertEqual(notes.count(), 1)
        panel = assert_present(self.assertions, self.page, FILTER_PANEL)
        self.assertions.assertEqual(by_test_id(panel, BUDGET_TIER_NOTE).count(), 1)
        note = notes.first.inner_text().strip()
        self.assertions.assertTrue(note)
        self.assertions.assertIn("ディナー", note)
        self.assertions.assertNotIn("\n", note)
        self.assertions.assertNotRegex(note, r"[¥￥円0-9０-９]")
        if "ランチ" in note:
            self.assertions.assertRegex(
                note, r"ランチ価格.*(?:示すものではありません|ではありません|ではない)"
            )
        card_budgets = by_test_id(self.page, "candidate-card-dinner-budget")
        for index in range(card_budgets.count()):
            self.assertions.assertNotIn("ディナー", card_budgets.nth(index).inner_text())

    def assert_map_attribution_and_fit(self) -> None:
        map_node = assert_present(self.assertions, self.page, MAP)
        expect(map_node).to_have_attribute("data-map-fit-state", "displayed-candidates")
        expect(map_node).to_have_attribute("data-map-tile-provider", "openstreetmap-standard")
        attribution = assert_present(self.assertions, self.page, MAP_ATTRIBUTION)
        expect(attribution).to_have_attribute("href", "https://www.openstreetmap.org/copyright")
        self.assertions.assertEqual(
            attribution.inner_text().strip(), "© OpenStreetMap contributors"
        )

    def assert_map_has_no_forbidden_surfaces(self) -> None:
        assert_all_absent(self.assertions, self.page, MAP_FORBIDDEN_TEST_IDS)

    def select_first_card_and_verify_marker_highlighted(self) -> None:
        card = wait_for_at_least_one(self.page, CARD).first
        candidate_ref = card.get_attribute("data-candidate-ref")
        self.assertions.assertTrue(candidate_ref)
        card.click()
        expect(card).to_have_attribute("data-selection-state", "selected")
        marker = self.page.locator(
            f'[data-testid="{MAP_MARKER}"][data-candidate-ref="{candidate_ref}"]'
        )
        expect(marker).to_have_attribute("data-selection-state", "selected")
        self._assert_all_other_cards_and_markers_unselected(candidate_ref)

    def select_first_marker_and_verify_card_highlighted(self) -> None:
        markers = wait_for_at_least_one(self.page, MAP_MARKER)
        marker = None
        for index in range(markers.count()):
            candidate = markers.nth(index)
            try:
                candidate.click(trial=True, timeout=1_000)
            except PlaywrightTimeoutError:
                continue
            marker = candidate
            break
        if marker is None:
            raise AssertionError("no displayed map marker is interactable")
        candidate_ref = marker.get_attribute("data-candidate-ref")
        self.assertions.assertTrue(candidate_ref)
        marker.click()
        expect(marker).to_have_attribute("data-selection-state", "selected")
        card = self.page.locator(f'[data-testid="{CARD}"][data-candidate-ref="{candidate_ref}"]')
        expect(card).to_have_attribute("data-selection-state", "selected")
        self._assert_all_other_cards_and_markers_unselected(candidate_ref)

    # Then: filters and ordering -----------------------------------------

    def assert_changed_filters_were_sent(self) -> None:
        key, expected = self._expected_changed_filter or (None, None)
        self.assertions.assertIsNotNone(key)
        filters = self._current_filters()
        if key == "budgetTiers":
            self.assertions.assertTrue(filters.get(key))
        else:
            self.assertions.assertEqual(filters.get(key), expected)

    def assert_display_matches_current_proposal(self) -> None:
        assert_absent(self.assertions, self.page, FILTER_PANEL)
        self.assert_cards_and_map_show_current_proposal()

    def assert_current_candidates_match_active_filters(self) -> None:
        filters = self._current_filters()
        for candidate in self._current_proposal()["candidates"]:
            if filters.get("genres"):
                self.assertions.assertIn(candidate["genre"], filters["genres"])
            if filters.get("nonSmokingOnly"):
                self.assertions.assertNotEqual(candidate["nonSmokingStatus"], "NONE")
            if filters.get("cardPaymentOnly"):
                self.assertions.assertIsNot(candidate["cardPaymentAvailable"], False)
            if filters.get("budgetTiers") and candidate["dinnerBudgetTier"] is not None:
                self.assertions.assertIn(candidate["dinnerBudgetTier"], filters["budgetTiers"])

    def _is_unconfirmed_for_active_filters(self, candidate: dict) -> bool:
        filters = self._current_filters()
        return bool(
            (filters.get("nonSmokingOnly") and candidate["nonSmokingStatus"] is None)
            or (filters.get("cardPaymentOnly") and candidate["cardPaymentAvailable"] is None)
            or (filters.get("budgetTiers") and candidate["dinnerBudgetTier"] is None)
        )

    def assert_current_display_ordering(self) -> None:
        candidates = self._current_proposal()["candidates"]
        self.assertions.assertEqual(
            self._card_candidate_refs(), [candidate["candidateRef"] for candidate in candidates]
        )
        unconfirmed = [
            self._is_unconfirmed_for_active_filters(candidate) for candidate in candidates
        ]
        self.assertions.assertEqual(unconfirmed, sorted(unconfirmed))

    def assert_unknown_candidates_are_shown(self) -> None:
        unknowns = [
            candidate
            for candidate in self._current_proposal()["candidates"]
            if self._is_unconfirmed_for_active_filters(candidate)
        ]
        self.assertions.assertTrue(unknowns)
        filters = self._current_filters()
        for candidate in unknowns:
            card = self.page.locator(
                f'[data-testid="{CARD}"][data-candidate-ref="{candidate["candidateRef"]}"]'
            )
            if filters.get("nonSmokingOnly") and candidate["nonSmokingStatus"] is None:
                expect(by_test_id(card, "candidate-card-non-smoking")).to_have_attribute(
                    "data-value-state", "unavailable"
                )
            if filters.get("cardPaymentOnly") and candidate["cardPaymentAvailable"] is None:
                expect(card).to_have_attribute(CARD_PAYMENT_VALUE_STATE_ATTRIBUTE, "unavailable")
            if filters.get("budgetTiers") and candidate["dinnerBudgetTier"] is None:
                expect(by_test_id(card, "candidate-card-dinner-budget")).to_have_attribute(
                    "data-value-state", "unavailable"
                )

    def assert_filter_open_is_available(self) -> None:
        assert_present(self.assertions, self.page, FILTER_OPEN)

    def assert_default_izakaya_bar_exclusion_was_requested(self) -> None:
        self.assertions.assertFalse(self._current_filters().get("includeIzakayaBar", False))

    def assert_izakaya_bar_filter_is_available(self) -> None:
        assert_present(self.assertions, self.page, FILTER_INCLUDE_IZAKAYA_BAR)

    def assert_izakaya_bar_inclusion_adds_candidates(self) -> None:
        self.assertions.assertEqual(self._current_filters().get("includeIzakayaBar"), True)
        initial_response = require(self.initial, "initial proposal was not requested").payload
        excluded_genres = {
            row["genre"]
            for row in initial_response["populationAttributes"]
            if row["defaultExcluded"]
        }
        self.assertions.assertTrue(excluded_genres)
        initial = initial_response["candidates"]
        current = self._current_proposal()["candidates"]
        self.assertions.assertFalse(
            any(candidate["genre"] in excluded_genres for candidate in initial)
        )
        self.assertions.assertTrue(
            any(candidate["genre"] in excluded_genres for candidate in current)
        )

    def assert_izakaya_bar_fallback_is_shown(self) -> None:
        proposal = self._current_proposal()
        self.assertions.assertTrue(proposal["izakayaBarFallbackApplied"])
        self.assertions.assertTrue(proposal["candidates"])
        assert_all_present(
            self.assertions, self.page, [CONTENT, CARDS, MAP, IZAKAYA_BAR_FALLBACK_NOTICE]
        )
        notices = by_test_id(self.page, IZAKAYA_BAR_FALLBACK_NOTICE)
        self.assertions.assertEqual(notices.count(), 1)
        notice = notices.first.inner_text().strip()
        self.assertions.assertRegex(notice, r"居酒屋.*バー|バー.*居酒屋")
        self.assertions.assertIn("ランチ", notice)
        self.assertions.assertRegex(
            notice, r"未確認|確認できていません|確認できない|確認しづらい|とは限らない"
        )

    def assert_explicit_genre_filter_was_not_relaxed(self) -> None:
        proposal = self._current_proposal()
        filters = require(self._pending_filters, "pending filters were not initialized")
        self.assertions.assertTrue(filters.get("genres"))
        self.assertions.assertTrue(filters.get("nonSmokingOnly"))
        self.assertions.assertEqual(self._population_match_count(filters), 0)
        expect(by_test_id(self.page, FILTER_APPLY)).to_have_attribute("data-match-count", "0")
        expect(by_test_id(self.page, FILTER_APPLY)).to_be_disabled()
        self.assertions.assertTrue(
            any(
                row["defaultExcluded"] and row["nonSmokingStatus"] == "FULL"
                for row in proposal["populationAttributes"]
            )
        )

    # Then: repeated search and card-payment caution ---------------------

    def assert_no_results_indicator_absent(self) -> None:
        assert_absent(self.assertions, self.page, NO_RESULTS)

    def assert_search_again_reused_filters_and_replaced_display(self) -> None:
        initial = require(self.initial, "initial proposal was not requested")
        repeated = require(self.search_again_response, "search-again request was not sent")
        self.assertions.assertIn("filters", repeated.request_body)
        self.assertions.assertEqual(
            self._normalized_filters(self._effective_filters(repeated.request_body)),
            self._normalized_filters(self._effective_filters(initial.request_body)),
        )
        self.assert_cards_and_map_show_current_proposal()

    def assert_new_seed_changed_sample(self) -> None:
        initial = require(self.initial, "initial proposal was not requested")
        repeated = require(self.search_again_response, "search-again request was not sent")
        self.assertions.assertNotEqual(
            initial.payload["candidates"], repeated.payload["candidates"]
        )

    def assert_original_seed_reproduced_sample(self) -> None:
        initial = require(self.initial, "initial proposal was not requested")
        repeated = require(self.original_seed_response, "original-seed search was not sent")
        self.assertions.assertEqual(initial.payload["candidates"], repeated.payload["candidates"])
        self.assert_cards_and_map_show_current_proposal()

    def assert_payment_caution_shown_for_unavailable_card_payment(self) -> None:
        cards, candidates_by_ref = self._current_cards_by_candidate_ref()
        unavailable_seen = False
        for index in range(cards.count()):
            card = cards.nth(index)
            if (
                candidates_by_ref[card.get_attribute("data-candidate-ref")]["cardPaymentAvailable"]
                is False
            ):
                unavailable_seen = True
                caution = assert_present(self.assertions, card, CARD_PAYMENT_CAUTION_TEST_ID)
                expect(caution).to_have_attribute(CARD_PAYMENT_CAUTION_ATTRIBUTE, "false")
                text = caution.inner_text().strip()
                self.assertions.assertIn("クレジットカード", text)
                self.assertions.assertRegex(text, r"利用できません|利用不可|非対応|使えません")
                for other_payment_claim in (
                    "現金",
                    "電子マネー",
                    "QR",
                    "コード決済",
                    "デビット",
                    "cash",
                ):
                    self.assertions.assertNotIn(other_payment_claim.casefold(), text.casefold())
        self.assertions.assertTrue(unavailable_seen)

    def assert_payment_caution_absent_when_card_payment_is_available_or_unknown(self) -> None:
        cards, candidates_by_ref = self._current_cards_by_candidate_ref()
        other_seen = False
        for index in range(cards.count()):
            card = cards.nth(index)
            if (
                candidates_by_ref[card.get_attribute("data-candidate-ref")]["cardPaymentAvailable"]
                is not False
            ):
                other_seen = True
                assert_absent(self.assertions, card, CARD_PAYMENT_CAUTION_TEST_ID)
        self.assertions.assertTrue(other_seen)

    # Then: no-results and problem responses -----------------------------

    def assert_no_results_shown(self) -> None:
        assert_present(self.assertions, self.page, NO_RESULTS)
        assert_all_absent(self.assertions, self.page, [CARDS, MAP, PROBLEM])
        self._assert_no_disclosures()

    def assert_no_results_from_captured_api(self) -> None:
        self.assertions.assertEqual(self._current_proposal()["candidates"], [])

    def assert_safe_unavailable_guidance(self, expected_code: str) -> None:
        problem = assert_present(self.assertions, self.page, PROBLEM)
        guidance = assert_present(self.assertions, self.page, PROBLEM_GUIDANCE)
        expect(problem).to_have_attribute("data-problem-code", expected_code)
        self.assertions.assertTrue(guidance.inner_text().strip())
        assert_all_absent(self.assertions, self.page, [CARDS, MAP])
        self._assert_no_disclosures()

    def assert_captured_problem_matches_schema(self, expected_code: str) -> None:
        response = require(self.current, "candidate screen was not opened")
        self.assertions.assertEqual(response.status, STATUS_BY_PROBLEM_CODE[expected_code])
        assert_matches_openapi_schema(
            response.payload, CANDIDATE_API_CONTRACT, "#/components/schemas/ProblemResponse"
        )
        self.assertions.assertEqual(response.payload["code"], expected_code)
        self.assertions.assertTrue(response.payload["message"])

    # Private helpers -----------------------------------------------------

    def _current_proposal(self) -> dict:
        response = require(self.current, "candidate proposal was not requested")
        self.assertions.assertEqual(response.status, 200)
        assert_matches_openapi_schema(
            response.payload,
            CANDIDATE_API_CONTRACT,
            "#/components/schemas/CandidateProposalResponse",
        )
        return response.payload

    def _assert_dirty_filter_actions(self) -> None:
        assert_all_present(
            self.assertions, self.page, [FILTER_PENDING_NOTE, FILTER_REVERT, FILTER_APPLY]
        )
        expect(by_test_id(self.page, SEARCH_AGAIN)).to_be_disabled()
        pending = require(self._pending_filters, "pending filters were not initialized")
        match_count = self._population_match_count(pending)
        apply = by_test_id(self.page, FILTER_APPLY)
        expect(apply).to_have_attribute("data-match-count", str(match_count))
        if match_count == 0:
            expect(apply).to_be_disabled()
        else:
            expect(apply).to_be_enabled()

    def _change_pending_filters(self, trigger: object, updates: dict[str, object]) -> None:
        snapshot = self._display_snapshot()
        self._perform_without_candidate_request(trigger)
        pending = dict(require(self._pending_filters, "filter panel was not opened"))
        pending.update(updates)
        self._pending_filters = pending
        self._assert_display_snapshot(snapshot)
        self._assert_dirty_filter_actions()

    def _perform_without_candidate_request(self, trigger: object) -> None:
        requests: list[object] = []

        def record(request: object) -> None:
            if is_candidate_proposal_request(request):
                requests.append(request)

        self.page.on("request", record)
        try:
            trigger()
        finally:
            self.page.remove_listener("request", record)
        self.assertions.assertEqual(requests, [])

    def _display_snapshot(self) -> tuple[list[str], list[str | None], str, dict[str, object]]:
        return (
            self._card_candidate_refs(),
            self._marker_candidate_refs(),
            self._condition_summary_text(),
            dict(self._applied_filters),
        )

    def _assert_display_snapshot(
        self, snapshot: tuple[list[str], list[str | None], str, dict[str, object]]
    ) -> None:
        cards, markers, summary, applied = snapshot
        self.assertions.assertEqual(self._card_candidate_refs(), cards)
        self.assertions.assertEqual(self._marker_candidate_refs(), markers)
        self.assertions.assertEqual(self._condition_summary_text(), summary)
        self.assertions.assertEqual(self._applied_filters, applied)

    def _condition_summary_text(self) -> str:
        filter_control = by_test_id(self.page, FILTER_OPEN)
        semantic_summary = filter_control.locator("summary")
        if semantic_summary.count() == 1:
            text = semantic_summary.inner_text().strip()
            return "\n".join(line for line in text.splitlines() if line.strip() not in {"⌃", "⌄"})
        text = filter_control.inner_text().strip()
        for test_id in (FILTER_PENDING_NOTE, FILTER_REVERT, FILTER_APPLY):
            nodes = by_test_id(filter_control, test_id)
            for index in range(nodes.count()):
                text = text.replace(nodes.nth(index).inner_text().strip(), "")
        return "\n".join(
            line for line in text.splitlines() if line.strip() and line.strip() not in {"⌃", "⌄"}
        )

    def _population_match_count(self, filters: dict[str, object]) -> int:
        rows = self._current_proposal()["populationAttributes"]
        matching = [
            row
            for row in rows
            if (not filters["genres"] or row["genre"] in filters["genres"])
            and (
                not filters["nonSmokingOnly"]
                or row["nonSmokingStatus"] is None
                or row["nonSmokingStatus"] != "NONE"
            )
            and (
                not filters["cardPaymentOnly"]
                or row["cardPaymentAvailable"] is None
                or row["cardPaymentAvailable"] is not False
            )
            and (
                not filters["budgetTiers"]
                or row["dinnerBudgetTier"] is None
                or row["dinnerBudgetTier"] in filters["budgetTiers"]
            )
        ]
        if filters["includeIzakayaBar"]:
            return len(matching)
        without_default_excluded = [row for row in matching if not row["defaultExcluded"]]
        return len(without_default_excluded or matching)

    def _assert_genre_presentation(self) -> None:
        """Verify the compact preview and its no-search overflow toggle."""
        available = self._current_proposal()["availableGenres"]
        ordered = self.page.evaluate(
            """(genres) => [...genres].sort(
                (left, right) => left.length - right.length || left.localeCompare(right, "ja")
            )""",
            available,
        )
        preview = ordered[:4]
        if not ordered:
            self.assertions.assertEqual(by_test_id(self.page, FILTER_GENRE_OPTION).count(), 0)
            self.assertions.assertEqual(by_test_id(self.page, FILTER_GENRE_OVERFLOW).count(), 0)
            return
        self.assertions.assertEqual(self._genre_values(), preview)

        overflow = by_test_id(self.page, FILTER_GENRE_OVERFLOW)
        if len(ordered) <= 4:
            self.assertions.assertEqual(overflow.count(), 0)
            return

        self.assertions.assertEqual(overflow.count(), 1)
        self.assertions.assertEqual(overflow.inner_text().strip(), f"ほか {len(ordered) - 4}件…")
        self._assert_genre_overflow_toggle_preserves_proposal(ordered, "閉じる")
        self._assert_genre_overflow_toggle_preserves_proposal(
            preview, f"ほか {len(ordered) - 4}件…"
        )

    def _unknown_safe_filter_configuration(self) -> dict[str, object]:
        """Choose visible closed controls that make CS-13's Given observable.

        ``populationAttributes`` deliberately has no candidate identity, but
        the API contract makes it the public, identity-free source for exact
        pending-filter population membership.  Restricting to an eligible
        population of at most five makes the scenario's required unavailable
        value observable after the response's five-card display cap.
        """
        proposal = self._current_proposal()
        rows = proposal["populationAttributes"]
        configurations: list[tuple[int, int, dict[str, object]]] = []
        budget_options = [[], ["LOW"], ["MID"], ["HIGH"]]

        for genre, non_smoking_only, card_payment_only, budget_tiers in product(
            proposal["availableGenres"], [False, True], [False, True], budget_options
        ):
            if not (non_smoking_only or card_payment_only or budget_tiers):
                continue
            eligible = [
                row
                for row in rows
                if not row["defaultExcluded"]
                and row["genre"] == genre
                and (
                    not non_smoking_only
                    or row["nonSmokingStatus"] is None
                    or row["nonSmokingStatus"] != "NONE"
                )
                and (
                    not card_payment_only
                    or row["cardPaymentAvailable"] is None
                    or row["cardPaymentAvailable"] is not False
                )
                and (
                    not budget_tiers
                    or row["dinnerBudgetTier"] is None
                    or row["dinnerBudgetTier"] in budget_tiers
                )
            ]
            has_unavailable_active_filter = (
                (non_smoking_only and any(row["nonSmokingStatus"] is None for row in eligible))
                or (
                    card_payment_only
                    and any(row["cardPaymentAvailable"] is None for row in eligible)
                )
                or (budget_tiers and any(row["dinnerBudgetTier"] is None for row in eligible))
            )
            if eligible and len(eligible) <= 5 and has_unavailable_active_filter:
                configurations.append(
                    (
                        len(eligible),
                        int(non_smoking_only) + int(card_payment_only) + int(bool(budget_tiers)),
                        {
                            "genres": [genre],
                            "nonSmokingOnly": non_smoking_only,
                            "cardPaymentOnly": card_payment_only,
                            "budgetTiers": budget_tiers,
                        },
                    )
                )

        if not configurations:
            raise AssertionError(
                "NORMAL_WITH_POOL does not expose a <=5-member anonymous population "
                "with an unavailable active soft-filter value for TDR-CS-13"
            )
        return min(configurations, key=lambda item: (item[0], item[1]))[2]

    def _click_genre_option(self, genre: str) -> None:
        options = by_test_id(self.page, FILTER_GENRE_OPTION)
        for index in range(options.count()):
            if options.nth(index).get_attribute("data-genre-value") == genre:
                options.nth(index).click()
                return
        by_test_id(self.page, FILTER_GENRE_OVERFLOW).click()
        self._click_genre_option(genre)

    def _click_budget_tier(self, tier: str) -> None:
        options = wait_for_at_least_one(self.page, FILTER_BUDGET_TIER_OPTION)
        for index in range(options.count()):
            if options.nth(index).get_attribute("data-budget-tier-value") == tier:
                options.nth(index).click()
                return
        raise AssertionError(f"budget tier {tier!r} is not present in the filter panel")

    def _assert_genre_overflow_toggle_preserves_proposal(
        self, expected_genres: list[str], expected_overflow_label: str
    ) -> None:
        cards_before = self._card_candidate_refs()
        markers_before = self._marker_candidate_refs()
        request_urls: list[str] = []

        def record_candidate_post(request: object) -> None:
            if getattr(request, "method", None) == "POST" and str(
                getattr(request, "url", "")
            ).endswith("/candidate-proposals"):
                request_urls.append(getattr(request, "url"))

        self.page.on("request", record_candidate_post)
        try:
            by_test_id(self.page, FILTER_GENRE_OVERFLOW).click()
        finally:
            self.page.remove_listener("request", record_candidate_post)

        self.assertions.assertEqual(request_urls, [])
        self.assertions.assertEqual(self._genre_values(), expected_genres)
        self.assertions.assertEqual(
            by_test_id(self.page, FILTER_GENRE_OVERFLOW).inner_text().strip(),
            expected_overflow_label,
        )
        self.assertions.assertEqual(self._card_candidate_refs(), cards_before)
        self.assertions.assertEqual(self._marker_candidate_refs(), markers_before)

    def _genre_values(self) -> list[str | None]:
        genres = wait_for_at_least_one(self.page, FILTER_GENRE_OPTION)
        return [
            genres.nth(index).get_attribute("data-genre-value") for index in range(genres.count())
        ]

    def _current_filters(self) -> dict:
        response = require(self.current, "candidate proposal was not requested")
        return (response.request_body or {}).get("filters") or {}

    @staticmethod
    def _normalized_filters(filters: dict) -> dict[str, object]:
        return {
            "genres": list(filters.get("genres") or []),
            "includeIzakayaBar": bool(filters.get("includeIzakayaBar", False)),
            "nonSmokingOnly": bool(filters.get("nonSmokingOnly", False)),
            "cardPaymentOnly": bool(filters.get("cardPaymentOnly", False)),
            "budgetTiers": list(filters.get("budgetTiers") or []),
        }

    @staticmethod
    def _effective_filters(request_body: dict | None) -> dict:
        return (request_body or {}).get("filters") or {}

    def _current_cards_by_candidate_ref(self) -> tuple[Locator, dict[str, dict]]:
        candidates = self._current_proposal()["candidates"]
        cards = wait_for_at_least_one(self.page, CARD)
        expect(cards.first).to_have_attribute("data-candidate-ref", candidates[0]["candidateRef"])
        return cards, {candidate["candidateRef"]: candidate for candidate in candidates}

    def _card_candidate_refs(self) -> list[str]:
        cards = wait_for_at_least_one(self.page, CARD)
        return [
            cards.nth(index).get_attribute("data-candidate-ref") for index in range(cards.count())
        ]

    def _marker_candidate_refs(self) -> list[str | None]:
        markers = wait_for_at_least_one(self.page, MAP_MARKER)
        return [
            markers.nth(index).get_attribute("data-candidate-ref")
            for index in range(markers.count())
        ]

    def _assert_all_other_cards_and_markers_unselected(self, selected_ref: str) -> None:
        for test_id in (CARD, MAP_MARKER):
            nodes = by_test_id(self.page, test_id)
            for index in range(nodes.count()):
                node = nodes.nth(index)
                if node.get_attribute("data-candidate-ref") != selected_ref:
                    expect(node).to_have_attribute("data-selection-state", "unselected")

    def _assert_no_disclosures(self) -> None:
        html = self.page.content()
        self.assertions.assertNotIn(PRIVATE_ORIGIN_CANARY, html)
        self.assertions.assertNotIn(PROVIDER_INTERNALS_CANARY, html)
        assert_all_absent(self.assertions, self.page, DISCLOSURE_FORBIDDEN_TEST_IDS)
