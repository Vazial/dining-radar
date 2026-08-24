"""Browser DSL for the filter-model TDR-CS acceptance scenarios.

Candidate setup uses only the acceptance-only seam declared in
``contracts/test-support-api.yaml``. Every observed action uses Chromium
against the same-origin screen or its public candidate-proposal endpoint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
# adr/0025 decision 1: the search origin is now a display-only map marker,
# with zero-or-more concentric walking-time rings around it.
SEARCH_ORIGIN_MARKER = "candidate-origin-marker"
# contractVersion 1.3.2 (FR-022, 3rd recurrence; adr/0027): mapObservations.
# searchOriginMarker.positionAttributes -- read-only proxies for the
# marker's rendered geographic position, checked for *numeric* equality
# (parse both sides, compare within an absolute tolerance) against the
# current response's searchOrigin. Deliberately not REQUIRED_CARD_FIELDS'
# rawValueAttribute string-equality style: that style only ever compares
# integers/closed enum strings with exactly one canonical spelling,
# whereas latitude/longitude are floating-point measurements with more
# than one valid decimal-string spelling per language runtime (adr/0027).
SEARCH_ORIGIN_LATITUDE_ATTRIBUTE = "data-origin-latitude"
SEARCH_ORIGIN_LONGITUDE_ATTRIBUTE = "data-origin-longitude"
# searchOriginMarker.presenceRule's stated absolute tolerance (adr/0027 decision 1).
SEARCH_ORIGIN_POSITION_TOLERANCE_DEGREES = 1e-9
# Synthetic, non-default search origin (audit F1,
# reviews/audit-tdr-cs-origin-marker-position.md; test-support-api.yaml
# 1.4.0's optional CandidateProposalAcceptanceState.searchOrigin). Every
# mode's omitted-searchOrigin default is an implementation-chosen constant
# shared across every mode -- a self-consistency check against that shared
# constant cannot distinguish a correctly wired implementation from one that
# hardcodes the same constant, so TDR-CS-01/TDR-CS-02 (the scenarios that
# assert searchOriginMarker's position) must instead pin a value this DSL
# itself chooses. Latitude and longitude deliberately have differently
# shaped digit sequences and opposite signs so a swapped-axis bug also fails
# assert_search_origin_marker_is_shown's tolerance comparison. Not a real
# search origin, name, or address.
KNOWN_SEARCH_ORIGIN = (12.345678, -98.765432)
WALKING_RADIUS_RING = "candidate-walking-radius-ring"
PROVIDER_CREDIT = "candidate-provider-credit"
FILTER_OPEN = "candidate-filter-open"
FILTER_PANEL = "candidate-filter-panel"
FILTER_GENRE_OPTION = "candidate-filter-genre-option"
FILTER_GENRE_OVERFLOW = "candidate-filter-genre-overflow"
FILTER_INCLUDE_IZAKAYA_BAR = "candidate-filter-include-izakaya-bar"
FILTER_NON_SMOKING_ONLY = "candidate-filter-non-smoking-only"
FILTER_CARD_PAYMENT_ONLY = "candidate-filter-card-payment-only"
FILTER_BUDGET_TIER_OPTION = "candidate-filter-budget-tier-option"
# adr/0025 decision 3: walking-time-max is a hard filter, not a soft one --
# see _population_match_count's walkingTimeBand handling below.
FILTER_WALKING_TIME_MAX_OPTION = "candidate-filter-walking-time-max-option"
WALKING_TIME_MAX_VALUE_ATTRIBUTE = "data-walking-time-max-value"
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

# contracts/candidate-search-browser-interface.yaml shownCandidateMemory (adr/0024 decision 4).
SHOWN_CANDIDATE_MEMORY_KEY = "dining-radar:shown-provider-page-urls"
# test-support-api.yaml's SHOWN_POOL_PRIORITY Given (adr/0024 decision 4): exactly 10 candidates
# against the 5-candidate display cap, so the not-yet-shown partition size is deterministic.
SHOWN_POOL_SIZE = 10
DISPLAY_CAP = 5
# contracts/candidate-search-browser-interface.yaml shownCandidateMemory.expiry.maxAge (20 hours);
# a stale entry must be strictly older than this to be pruned on the next read.
SHOWN_MEMORY_MAX_AGE_HOURS = 20

# adr/0025 decision 1 moved candidate-origin-marker from forbidden to
# required (browser-interface.yaml's disclosureObservations.
# bodyMustNotExposeTestIds and mapObservations.forbiddenTestIds both dropped
# it); the old bare candidate-walking-time id no longer exists at all,
# replaced by the card-scoped candidate-card-walking-time, which is a
# required field, not a forbidden one.
DISCLOSURE_FORBIDDEN_TEST_IDS = [
    "private-search-origin",
    "candidate-provider-internals",
    "candidate-route",
    "candidate-current-location",
]
# mapObservations.forbiddenTestIds is the same list minus
# candidate-provider-internals, but assert_map_has_no_forbidden_surfaces
# already checks page-wide rather than scoped to the map element, so the
# broader DISCLOSURE_FORBIDDEN_TEST_IDS list is reused directly (a strict
# superset is a safe, pre-existing over-approximation, not a new one).
SEARCH_RANGE_FORBIDDEN_TOKENS = ["探索範囲", "検索範囲", "半径"]
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
# walkingTimeMinutes is deliberately not in REQUIRED_CARD_FIELDS: its visible
# text is wrapped in estimate wording (walkingTimeEstimateWording), not an
# exact match to str(candidate["walkingTimeMinutes"]) the way the fields
# above are, so it needs its own checks rather than REQUIRED_CARD_FIELDS'
# generic exact-match branch. See assert_required_card_fields_match_current_
# proposal (presence/value-state only) and assert_walking_time_is_shown_as_
# an_estimate (wording content, TDR-CS-02).
CARD_WALKING_TIME_TEST_ID = "candidate-card-walking-time"
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


@dataclass(frozen=True)
class DisplaySnapshot:
    """Everything browser-interface.yaml's several *-unchanged Musts (and
    TDR-CS-16's priorDisplayRetained) require to stay identical across an
    action that must not alter the display: card/marker candidateRef order,
    each card's and marker's own data-selection-state (in that same ref
    order, so a card<->marker correspondence break -- e.g. only the marker
    side losing its selected state -- is caught, not just ref-list
    equality), the condition summary text, and the applied filters.
    """

    card_refs: list[str]
    marker_refs: list[str | None]
    card_selection_states: list[str | None]
    marker_selection_states: list[str | None]
    condition_summary: str
    applied_filters: dict[str, object]


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
        self.failed_response: CapturedApiResponse | None = None
        self._prior_snapshot: DisplaySnapshot | None = None
        self._expected_changed_filter: tuple[str, object] | None = None
        self._applied_filters: dict[str, object] = self._normalized_filters({})
        self._pending_filters: dict[str, object] | None = None
        self._organizer_credentials: tuple[str, str] | None = None
        self._shown_pool_rounds: dict[str, object] | None = None

    # Given seams ---------------------------------------------------------

    def reset_authentication_state(self) -> None:
        self._auth_seam.reset_authentication_state()

    def enable_organizer(self, account_ref: str, identifier: str, password: str) -> None:
        self._auth_seam.set_active_organizer(account_ref, identifier, password)

    def reset_candidate_state(self) -> None:
        response = self.support.request("DELETE", "/test-support/candidate-proposals/state")
        assert_no_content(self.assertions, response, "candidate-proposal state reset")

    def set_candidate_state(
        self,
        mode: str,
        random_seed: int | None = None,
        search_origin: tuple[float, float] | None = None,
    ) -> None:
        payload: dict[str, object] = {"mode": mode}
        if random_seed is not None:
            payload["randomSeed"] = random_seed
        if search_origin is not None:
            latitude, longitude = search_origin
            payload["searchOrigin"] = {"latitude": latitude, "longitude": longitude}
        response = self.support.request(
            "PUT",
            "/test-support/candidate-proposals/state",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, f"candidate-proposal state set to {mode}")

    def set_lunch_candidates_with_a_known_search_origin(self) -> None:
        """test-support-api.yaml 1.4.0's CandidateProposalAcceptanceState.searchOrigin
        (audit F1). Pins a synthetic, non-default searchOrigin so
        assert_search_origin_marker_is_shown's numeric-equality check can
        actually distinguish a correctly wired implementation from one that
        hardcodes the previously-shared default constant every mode
        returned when this property was omitted.
        """
        self.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING", search_origin=KNOWN_SEARCH_ORIGIN)

    def seed_shown_candidate_memory_from_observed_urls(self, urls: set[str]) -> None:
        """Given-seam: construct shownCandidateMemory directly from providerPageUrl
        values already observed through the public API.

        test-support-api.yaml's SHOWN_POOL_PRIORITY description explicitly
        sanctions this construction ("the acceptance test constructs [a
        shownProviderPageUrls value] from previously observed providerPageUrl
        values"), unlike a DB-direct Given, which meta/verification.md
        reserves for explicitly declared seams. Only the *values* to seed are
        this method's concern; how the caller obtained them (necessarily a
        prior public "search again" call, since no dedicated fixture exists
        for the partial not-yet-shown case) is a separate, When-level browser
        action.
        """
        self._write_shown_candidate_memory(
            [{"url": url, "storedAt": self._browser_now_ms()} for url in urls]
        )

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
        self._organizer_credentials = (identifier, password)

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
                FILTER_WALKING_TIME_MAX_OPTION,
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

    def enable_walking_time_max_filter_that_excludes_some_candidates(self) -> None:
        """幹事が徒歩の上限を指定する (TDR-CS-15, adr/0025 決定3).

        The offered preset values are UI-implementation-owned and not fixed
        by the API schema (CandidateFilters.walkingTimeMaxMinutes
        description; test-support-api.yaml's WALKING_TIME_LIMIT_EXCLUDES
        only fixes the *synthetic candidates'* minutes, not the panel's
        offered presets). This reads the panel's actual
        data-walking-time-max-value options and picks the smallest one that
        still splits the already-open unfiltered proposal's candidates
        (keeps the nearest, excludes the farthest), mirroring how
        _unknown_safe_filter_configuration searches for a usable
        configuration for TDR-CS-13 instead of assuming a fixed value.
        """
        initial = require(self.initial, "initial proposal was not requested")
        minutes = sorted({c["walkingTimeMinutes"] for c in initial.payload["candidates"]})
        options = wait_for_at_least_one(self.page, FILTER_WALKING_TIME_MAX_OPTION)
        offered = sorted(
            int(options.nth(index).get_attribute(WALKING_TIME_MAX_VALUE_ATTRIBUTE))
            for index in range(options.count())
        )
        chosen = next((value for value in offered if minutes[0] <= value < minutes[-1]), None)
        if chosen is None:
            raise AssertionError(
                "no offered candidate-filter-walking-time-max-option value both "
                "keeps and excludes a WALKING_TIME_LIMIT_EXCLUDES candidate"
            )
        self._change_pending_filters(
            lambda: self._click_walking_time_max_option(chosen),
            {"walkingTimeMaxMinutes": chosen},
        )
        self._expected_changed_filter = ("walkingTimeMaxMinutes", chosen)

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

    def search_again_reproducing_original_seed(self) -> None:
        """Search again after clearing shownCandidateMemory (adr/0024 decision 4).

        Reproducing a pinned randomSeed now additionally requires an identical
        shownProviderPageUrls (test-support-api.yaml's randomSeed description).
        The very first captured response saw an empty shown-memory; without
        clearing it here, the intervening different-seed search already
        accumulated entries the first response never saw, breaking
        byte-identical reproduction for a reason unrelated to this scenario's
        own concern (pure seed-based sampling, TDR-CS-11).
        """
        self.clear_shown_candidate_memory()
        self.search_again()

    def apply_filters_expecting_failure(self) -> None:
        """絞り込み条件を変更する...で候補情報を取得できない, applyFilters branch (TDR-CS-16).

        Unlike apply_filters(), this expects a problem response rather than
        200 and does not update _applied_filters/_pending_filters -- the
        prior applied state is exactly what browser-interface.yaml's
        priorDisplayRetained requires to survive unchanged. The snapshot is
        captured immediately before the request, matching that Must's own
        "immediately before this request" wording.
        """
        self._prior_snapshot = self._display_snapshot()

        def trigger() -> None:
            by_test_id(self.page, FILTER_APPLY).click()

        self.failed_response = capture_candidate_proposal_response(self.page, trigger)
        self.assertions.assertEqual(self.failed_response.status, 429)
        self.assertions.assertEqual(
            self.failed_response.payload.get("code"), "PROPOSAL_RATE_LIMITED"
        )

    def search_again_expecting_failure(self) -> None:
        """絞り込み条件を変更する...で候補情報を取得できない, searchAgain branch (TDR-CS-16)."""
        self._prior_snapshot = self._display_snapshot()

        def trigger() -> None:
            by_test_id(self.page, SEARCH_AGAIN).click()

        self.failed_response = capture_candidate_proposal_response(self.page, trigger)
        self.assertions.assertEqual(self.failed_response.status, 429)
        self.assertions.assertEqual(
            self.failed_response.payload.get("code"), "PROPOSAL_RATE_LIMITED"
        )

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

    def assert_search_origin_marker_is_shown(self) -> None:
        """地図には検索基点のマーカーが示される (TDR-CS-01, adr/0025 決定1).

        mapObservations.searchOriginMarker.presenceRule (contractVersion
        1.3.2, adr/0027) requires the marker's positionAttributes to be
        numerically equal -- within an absolute tolerance of
        SEARCH_ORIGIN_POSITION_TOLERANCE_DEGREES -- to the current
        response's searchOrigin.latitude/longitude, rather than an
        independently-known constant -- this is what proves the marker's
        position derives from the response, not a fixture-baked value
        (FR-022, 3rd recurrence). Equality is numeric, not lexical: the
        response is serialized server-side in Python and positionAttributes
        are set client-side by candidate.js, and the two runtimes do not
        share one canonical decimal spelling for the same IEEE 754 value
        (adr/0027). It does not read the marker's rendered pixel position;
        positionAttributes is the DOM-readable proxy the contract defines
        for that instead.
        """
        proposal = self._current_proposal()
        marker = assert_present(self.assertions, self.page, SEARCH_ORIGIN_MARKER)
        origin = proposal["searchOrigin"]
        self.assertions.assertAlmostEqual(
            float(marker.get_attribute(SEARCH_ORIGIN_LATITUDE_ATTRIBUTE)),
            origin["latitude"],
            delta=SEARCH_ORIGIN_POSITION_TOLERANCE_DEGREES,
        )
        self.assertions.assertAlmostEqual(
            float(marker.get_attribute(SEARCH_ORIGIN_LONGITUDE_ATTRIBUTE)),
            origin["longitude"],
            delta=SEARCH_ORIGIN_POSITION_TOLERANCE_DEGREES,
        )

    def assert_search_range_value_is_not_shown(self) -> None:
        """探索範囲そのものの値は示されない (TDR-CS-01/02, adr/0025 決定4・決定8).

        The response schema already forbids a range/radius field
        (CandidateProposalResponse/SearchOriginLocation additionalProperties:
        false, checked by every _current_proposal() call this DSL already
        performs); this defends the same property from the rendered side,
        scanning the page's own text for the range vocabulary alone.
        Deliberately narrower than LOCATION_RANGE_FORBIDDEN_TOKENS, which
        also includes 検索基点/起点/現在地 -- the origin marker now
        legitimately carries 検索基点 as its own label
        (displayOnlyOriginException), so a whole-page scan using that wider
        list would false-positive on this scenario's own required marker.
        """
        self._current_proposal()
        html = self.page.content()
        for forbidden in SEARCH_RANGE_FORBIDDEN_TOKENS:
            self.assertions.assertNotIn(forbidden, html)

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

    def assert_origin_marker_and_rings_are_display_only(self) -> None:
        """検索基点は地図上のマーカーとして示されるが、幹事はその位置を変更できない (TDR-CS-04,
        adr/0025 決定7).

        unavailableControls.locationRangeControlProhibition's
        displayOnlyOriginException.verificationAllocation.L4 requires
        driving every available activation of candidate-origin-marker and
        any candidate-walking-radius-ring and proving none of them starts a
        public operation or changes the display -- the exception is defined
        by behavior, not element identity, so this reuses the same
        pointer/keyboard-activation-then-snapshot technique
        _perform_without_candidate_request and _display_snapshot already
        apply to filter-panel controls (e.g. revert_pending_filters).

        The candidate-card deck legitimately overlaps the map by design
        (the human-approved mobile-first placement,
        projects/dining-radar/activeContext.md) -- a real Locator.click()
        fails Playwright's own "receives pointer events" actionability
        check here (the topmost element at that point is a card, not the
        marker), which is a fact about this layout, not a defect this
        contract's Must is about. dispatch_event("click") fires the click
        event on the marker/ring node itself, bypassing hit-testing, which
        is what actually proves *this element's own* activation is a no-op
        -- a coordinate-based forced click would instead risk clicking
        through to whatever card sits on top, testing the wrong element.
        """
        for test_id in (SEARCH_ORIGIN_MARKER, WALKING_RADIUS_RING):
            nodes = by_test_id(self.page, test_id)
            for index in range(nodes.count()):
                node = nodes.nth(index)
                self._assert_activation_changes_nothing(lambda n=node: n.dispatch_event("click"))
                if node.get_attribute("tabindex") is not None:
                    self._assert_activation_changes_nothing(
                        lambda n=node: (n.focus(), n.press("Enter"))
                    )
                    self._assert_activation_changes_nothing(
                        lambda n=node: (n.focus(), n.press("Space"))
                    )

    def _assert_activation_changes_nothing(self, activate: object) -> None:
        snapshot = self._display_snapshot()
        self._perform_without_candidate_request(activate)
        self._assert_display_snapshot(snapshot)

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
            # walkingTimeMinutes is never null (candidate-search-api.yaml's
            # Candidate.walkingTimeMinutes description) and its visible
            # wording is checked separately by
            # assert_walking_time_is_shown_as_an_estimate; this only proves
            # the field itself is present and never unavailable.
            walking_time = by_test_id(card, CARD_WALKING_TIME_TEST_ID)
            self.assertions.assertEqual(walking_time.get_attribute("data-value-state"), "provided")
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
        assert_all_absent(self.assertions, self.page, DISCLOSURE_FORBIDDEN_TEST_IDS)

    def assert_map_shows_search_origin_marker_and_walking_radius_rings(self) -> None:
        """地図には検索基点のマーカーと、それを中心とする徒歩圏の同心リングが示される (TDR-CS-02).

        Ring count/radii are an implementation choice the contract does not
        fix (walkingRadiusRings.presenceRule), but this scenario's own
        Gherkin states rings *are* shown (plural "同心リング"), so at least
        one is required here specifically, unlike the schema-level
        zero-or-more cardinality.
        """
        self._current_proposal()
        assert_present(self.assertions, self.page, SEARCH_ORIGIN_MARKER)
        rings = by_test_id(self.page, WALKING_RADIUS_RING)
        self.assertions.assertGreaterEqual(rings.count(), 1)

    def assert_walking_time_is_shown_as_an_estimate(self) -> None:
        """徒歩のめやす時間は推定であり、実際に歩いた経路を測った時間ではないことが分かる形で
        示される (TDR-CS-02, adr/0025 決定2).

        walkingTimeEstimateWording requires an approximation marker on the
        same element cardDataAttributes.requiredFields' walkingTimeMinutes
        entry names -- unlike REQUIRED_CARD_FIELDS' exact-text fields, the
        visible text intentionally differs from the bare number, so this
        checks value-state and wording content directly rather than
        REQUIRED_CARD_FIELDS' generic exact-match branch. The exact wording
        is an implementation choice the contract does not fix; the regex
        below covers the contract's own examples (約, 推定) plus common
        synonyms, mirroring how assert_izakaya_bar_fallback_is_shown already
        accepts several equivalent uncertainty phrasings for a similarly
        unfixed wording Must.
        """
        cards, candidates_by_ref = self._current_cards_by_candidate_ref()
        for index in range(cards.count()):
            card = cards.nth(index)
            candidate = candidates_by_ref[card.get_attribute("data-candidate-ref")]
            node = by_test_id(card, CARD_WALKING_TIME_TEST_ID)
            self.assertions.assertEqual(node.get_attribute("data-value-state"), "provided")
            text = node.inner_text().strip()
            self.assertions.assertIn(str(candidate["walkingTimeMinutes"]), text)
            self.assertions.assertNotEqual(text, str(candidate["walkingTimeMinutes"]))
            self.assertions.assertRegex(text, r"約|およそ|推定|めやす|見込み|くらい|程度")

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

    # Given/Then: walking-time-max hard filter (TDR-CS-15) ----------------

    def assert_population_includes_a_candidate_beyond_the_upcoming_walking_time_max(
        self,
    ) -> None:
        """提案できる候補に、これから指定する徒歩の上限を超える店舗が含まれている (TDR-CS-15 Given).

        WALKING_TIME_LIMIT_EXCLUDES already guarantees a below/at/above-limit
        spread (test-support-api.yaml); this reads the already-captured
        unfiltered proposal to confirm walkingTimeMinutes actually varies,
        rather than trusting the Given's prose alone.
        """
        initial = require(self.initial, "initial proposal was not requested")
        minutes = {candidate["walkingTimeMinutes"] for candidate in initial.payload["candidates"]}
        self.assertions.assertGreater(len(minutes), 1)

    def assert_candidates_over_the_walking_time_max_are_excluded(self) -> None:
        """指定した上限を超える徒歩のめやす時間の店舗は候補から除かれる (TDR-CS-15)."""
        limit = self._applied_filters["walkingTimeMaxMinutes"]
        self.assertions.assertIsNotNone(limit)
        initial = require(self.initial, "initial proposal was not requested")
        over_limit_refs = {
            candidate["candidateRef"]
            for candidate in initial.payload["candidates"]
            if candidate["walkingTimeMinutes"] > limit
        }
        self.assertions.assertTrue(over_limit_refs)
        current_refs = {
            candidate["candidateRef"] for candidate in self._current_proposal()["candidates"]
        }
        self.assertions.assertEqual(over_limit_refs & current_refs, set())

    def assert_candidates_at_or_under_the_walking_time_max_remain(self) -> None:
        """上限以内の徒歩のめやす時間の店舗は候補に残る (TDR-CS-15)."""
        limit = self._applied_filters["walkingTimeMaxMinutes"]
        self.assertions.assertIsNotNone(limit)
        initial = require(self.initial, "initial proposal was not requested")
        at_or_under_refs = {
            candidate["candidateRef"]
            for candidate in initial.payload["candidates"]
            if candidate["walkingTimeMinutes"] <= limit
        }
        self.assertions.assertTrue(at_or_under_refs)
        current_refs = {
            candidate["candidateRef"] for candidate in self._current_proposal()["candidates"]
        }
        self.assertions.assertEqual(at_or_under_refs, current_refs)

    def assert_no_candidate_remains_due_to_unknown_walking_time(self) -> None:
        """徒歩のめやす時間が確認できないという理由で候補が残ることはない (TDR-CS-15).

        Candidate.walkingTimeMinutes is never null (adr/0025 決定2), so there
        is no "unknown, kept anyway" path for this hard filter to begin
        with; this proves that structurally, by asserting every displayed
        candidate's own field is present, matching-and-excluding refs proof
        above (never data-value-state=unavailable, never a null value).
        """
        cards = wait_for_at_least_one(self.page, CARD)
        for index in range(cards.count()):
            node = by_test_id(cards.nth(index), CARD_WALKING_TIME_TEST_ID)
            self.assertions.assertEqual(node.get_attribute("data-value-state"), "provided")
        for candidate in self._current_proposal()["candidates"]:
            self.assertions.assertIsNotNone(candidate["walkingTimeMinutes"])

    # Then: fetch failure retains the prior display (TDR-CS-16) -----------

    def assert_prior_candidates_and_map_remain(self) -> None:
        """直前まで表示していた候補と地図はそのまま残る (TDR-CS-16).

        Verifies browser-interface.yaml's priorDisplayRetained Must: every
        card/marker ref, their selection correspondence, and the condition
        summary from immediately before the failed request are unchanged,
        and candidate-proposal-cards/candidate-map are not removed the way
        the `empty` render state removes them.
        """
        snapshot = require(self._prior_snapshot, "no prior display snapshot was captured")
        self._assert_display_snapshot(snapshot)
        assert_all_present(self.assertions, self.page, [CARDS, MAP])

    def assert_fetch_failure_is_announced(self) -> None:
        """取得できなかったことが案内される (TDR-CS-16).

        candidate-proposal-problem and its guidance render in addition to,
        not instead of, the retained cards/map -- assert_prior_candidates_
        and_map_remain proves the "in addition to" half; this proves the
        problem surface itself appears.
        """
        require(self.failed_response, "no failing request was captured")
        assert_present(self.assertions, self.page, PROBLEM)
        guidance = assert_present(self.assertions, self.page, PROBLEM_GUIDANCE)
        self.assertions.assertTrue(guidance.inner_text().strip())

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

    # Given/Then: not-yet-shown priority and shownCandidateMemory (TDR-CS-14) --

    def assert_eligible_population_greatly_exceeds_display_cap(self) -> None:
        population = self._eligible_population_count(self._current_proposal())
        self.assertions.assertGreaterEqual(population, DISPLAY_CAP * 2)

    def repeat_search_again_through_shown_pool_cycle(self) -> None:
        """Repeat "search again" through one whole not-yet-shown priority cycle.

        Round A is the already-captured initial proposal; round B is the first
        repeat, whose shownProviderPageUrls is exactly round A's 5 shown URLs,
        so its not-yet-shown partition has exactly 5 members (SHOWN_POOL_SIZE
        candidates minus round A's 5) -- the contract's second deterministic
        case. The partial (1-4 not-yet-shown) case is then exercised directly
        via the seed_shown_candidate_memory_from_observed_urls Given-seam,
        fed with URLs already observed in rounds A and B, exactly as
        test-support-api.yaml's SHOWN_POOL_PRIORITY description directs ("the
        acceptance test constructs [it] from previously observed
        providerPageUrl values"). The cycle finishes with one more repeat,
        whose accumulated shownProviderPageUrls by then covers the full
        population, exhausting it (adr/0024 decision 4).
        """
        round_a = require(self.initial, "initial proposal was not requested")
        self.search_again()
        round_b = require(self.current, "search-again response missing")

        all_urls = sorted(set(self._urls(round_a)) | set(self._urls(round_b)))
        self.assertions.assertEqual(len(all_urls), SHOWN_POOL_SIZE)
        partial_seen = set(all_urls[: SHOWN_POOL_SIZE - 3])
        self.seed_shown_candidate_memory_from_observed_urls(partial_seen)
        self.search_again()
        round_partial = require(self.current, "search-again response missing")

        self.search_again()
        round_exhausted = require(self.current, "search-again response missing")

        self._shown_pool_rounds = {
            "a": round_a,
            "b": round_b,
            "partial": round_partial,
            "partial_seen": partial_seen,
            "exhausted": round_exhausted,
        }

    def assert_not_yet_shown_candidates_are_prioritized(self) -> None:
        rounds = require(self._shown_pool_rounds, "shown-pool cycle was not performed")
        urls_a = set(self._urls(rounds["a"]))
        urls_b = set(self._urls(rounds["b"]))
        self.assertions.assertEqual(len(urls_a), DISPLAY_CAP)
        self.assertions.assertEqual(len(urls_b), DISPLAY_CAP)
        self.assertions.assertEqual(urls_a & urls_b, set())
        self.assertions.assertFalse(rounds["b"].payload["shownPoolExhausted"])

    def assert_previously_shown_candidates_are_postponed_not_excluded(self) -> None:
        rounds = require(self._shown_pool_rounds, "shown-pool cycle was not performed")
        partial_seen: set[str] = rounds["partial_seen"]
        returned = set(self._urls(rounds["partial"]))
        unseen_expected = (set(self._urls(rounds["a"])) | set(self._urls(rounds["b"]))) - (
            partial_seen
        )
        self.assertions.assertEqual(len(unseen_expected), SHOWN_POOL_SIZE - len(partial_seen))
        self.assertions.assertTrue(unseen_expected.issubset(returned))
        self.assertions.assertEqual(
            len(returned & partial_seen), DISPLAY_CAP - len(unseen_expected)
        )
        self.assertions.assertFalse(rounds["partial"].payload["shownPoolExhausted"])

    def assert_previously_shown_candidates_can_reappear_after_a_full_cycle(self) -> None:
        rounds = require(self._shown_pool_rounds, "shown-pool cycle was not performed")
        self.assertions.assertTrue(rounds["exhausted"].payload["shownPoolExhausted"])
        all_urls = set(self._urls(rounds["a"])) | set(self._urls(rounds["b"]))
        self.assertions.assertEqual(len(all_urls), SHOWN_POOL_SIZE)
        returned = set(self._urls(rounds["exhausted"]))
        # By this point every eligible candidate (all SHOWN_POOL_SIZE of them)
        # was already shown, so a response satisfying the schema could only
        # ever be a subset of all_urls -- checking that alone is true even for
        # an empty or short response and would not catch an implementation
        # that (wrongly) treats "exhausted" as "nothing left to show".
        # Requiring a full 5-candidate response, entirely drawn from the
        # already-shown set, is what actually distinguishes "previously shown
        # candidates reappear" from "previously shown candidates stayed
        # excluded".
        self.assertions.assertEqual(len(returned), DISPLAY_CAP)
        self.assertions.assertEqual(returned, returned & all_urls)

    def assert_shown_memory_survives_a_reload(self) -> None:
        before = self._read_shown_candidate_memory()
        self.assertions.assertTrue(before)
        reloaded = capture_candidate_proposal_response(self.page, lambda: self.page.reload())
        sent = set((reloaded.request_body or {}).get("shownProviderPageUrls") or [])
        self.assertions.assertEqual(sent, {entry["url"] for entry in before})
        self.current = reloaded
        self._current_proposal()

    def assert_shown_memory_fades_after_its_retention_period(self) -> None:
        entries = self._read_shown_candidate_memory()
        self.assertions.assertEqual(len(entries), SHOWN_POOL_SIZE)
        stale_url = entries[0]["url"]
        past_max_age_ms = (SHOWN_MEMORY_MAX_AGE_HOURS + 1) * 60 * 60 * 1000
        aged = [
            {"url": entry["url"], "storedAt": self._browser_now_ms() - past_max_age_ms}
            if entry["url"] == stale_url
            else entry
            for entry in entries
        ]
        self._write_shown_candidate_memory(aged)
        response = capture_candidate_proposal_response(
            self.page, lambda: by_test_id(self.page, SEARCH_AGAIN).click()
        )
        self.current = response
        self._current_proposal()
        sent = set((response.request_body or {}).get("shownProviderPageUrls") or [])
        self.assertions.assertNotIn(stale_url, sent)
        # Pruning exactly one entry out of the otherwise-full SHOWN_POOL_SIZE
        # population leaves a not-yet-shown partition of exactly 1 member
        # (stale_url itself). proposal.shownPoolPriority's set-membership
        # invariant guarantees that member is included in the response for
        # every randomSeed, so this is a deterministic (not merely probable)
        # observation that the pruned candidate is once again treated as
        # not-yet-shown, closing the second half of
        # shownCandidateMemory.expiry.verificationNote's required pair of
        # observations (dropped from the request AND treated as unseen).
        self.assertions.assertEqual(len(sent), SHOWN_POOL_SIZE - 1)
        self.assertions.assertIn(stale_url, set(self._urls(response)))

    def assert_shown_memory_is_not_shared_with_another_device(self) -> None:
        identifier, password = require(
            self._organizer_credentials, "no organizer credentials were captured yet"
        )
        other_context = self.page.context.browser.new_context()
        try:
            other_page = other_context.new_page()
            other_page.goto(f"{self.base_url}/")

            def sign_in_from_another_device() -> None:
                by_test_id(other_page, AUTH_LOGIN_IDENTIFIER).fill(identifier)
                by_test_id(other_page, AUTH_PASSWORD).fill(password)
                by_test_id(other_page, AUTH_SIGN_IN_SUBMIT).click()

            response = capture_candidate_proposal_response(other_page, sign_in_from_another_device)
            sent = (response.request_body or {}).get("shownProviderPageUrls")
            self.assertions.assertFalse(sent)
        finally:
            other_context.close()

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

    @staticmethod
    def _urls(response: CapturedApiResponse) -> list[str]:
        return [candidate["providerPageUrl"] for candidate in response.payload["candidates"]]

    @staticmethod
    def _eligible_population_count(proposal: dict) -> int:
        rows = proposal["populationAttributes"]
        return len([row for row in rows if not row["defaultExcluded"]])

    # shownCandidateMemory (sessionStorage) access -------------------------
    #
    # contracts/candidate-search-browser-interface.yaml's shownCandidateMemory
    # is client-only state (adr/0024 decision 4): the server never receives,
    # stores, or reasons about it beyond the one request field it is copied
    # into. Reading/writing it directly here is the contract's own sanctioned
    # technique for constructing an arbitrary shownProviderPageUrls value from
    # previously observed URLs and for seeding a stale entry
    # (shownCandidateMemory.expiry.verificationNote); it is not a shortcut
    # around the public boundary, since this storage itself is the observable
    # surface TDR-CS-14 verifies.

    def _read_shown_candidate_memory(self) -> list[dict]:
        raw = self.page.evaluate(
            "(key) => window.sessionStorage.getItem(key)", SHOWN_CANDIDATE_MEMORY_KEY
        )
        return json.loads(raw) if raw else []

    def _write_shown_candidate_memory(self, entries: list[dict]) -> None:
        self.page.evaluate(
            "([key, value]) => window.sessionStorage.setItem(key, value)",
            [SHOWN_CANDIDATE_MEMORY_KEY, json.dumps(entries)],
        )

    def clear_shown_candidate_memory(self) -> None:
        self.page.evaluate(
            "(key) => window.sessionStorage.removeItem(key)", SHOWN_CANDIDATE_MEMORY_KEY
        )

    def _browser_now_ms(self) -> int:
        return self.page.evaluate("() => Date.now()")

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

    def _display_snapshot(self) -> DisplaySnapshot:
        return DisplaySnapshot(
            card_refs=self._card_candidate_refs(),
            marker_refs=self._marker_candidate_refs(),
            card_selection_states=self._card_selection_states(),
            marker_selection_states=self._marker_selection_states(),
            condition_summary=self._condition_summary_text(),
            applied_filters=dict(self._applied_filters),
        )

    def _assert_display_snapshot(self, snapshot: DisplaySnapshot) -> None:
        self.assertions.assertEqual(self._card_candidate_refs(), snapshot.card_refs)
        self.assertions.assertEqual(self._marker_candidate_refs(), snapshot.marker_refs)
        self.assertions.assertEqual(self._card_selection_states(), snapshot.card_selection_states)
        self.assertions.assertEqual(
            self._marker_selection_states(), snapshot.marker_selection_states
        )
        self.assertions.assertEqual(self._condition_summary_text(), snapshot.condition_summary)
        self.assertions.assertEqual(self._applied_filters, snapshot.applied_filters)

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
            and (
                filters["walkingTimeMaxMinutes"] is None
                # A hard filter (adr/0025 決定3): unlike the soft filters
                # above, a null walkingTimeBand ("farther than every
                # currently offered preset") never passes -- there is no
                # unknown-candidate case to preserve for this filter.
                or (
                    row["walkingTimeBand"] is not None
                    and row["walkingTimeBand"] <= filters["walkingTimeMaxMinutes"]
                )
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
                "NORMAL_WITH_WEIGHTED_SAMPLING does not expose a <=5-member anonymous population "
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

    def _click_walking_time_max_option(self, minutes: int) -> None:
        options = wait_for_at_least_one(self.page, FILTER_WALKING_TIME_MAX_OPTION)
        for index in range(options.count()):
            if options.nth(index).get_attribute(WALKING_TIME_MAX_VALUE_ATTRIBUTE) == str(minutes):
                options.nth(index).click()
                return
        raise AssertionError(
            f"walking-time-max option {minutes!r} is not present in the filter panel"
        )

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
            "walkingTimeMaxMinutes": filters.get("walkingTimeMaxMinutes"),
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

    def _card_selection_states(self) -> list[str | None]:
        cards = wait_for_at_least_one(self.page, CARD)
        return [
            cards.nth(index).get_attribute("data-selection-state") for index in range(cards.count())
        ]

    def _marker_selection_states(self) -> list[str | None]:
        markers = wait_for_at_least_one(self.page, MAP_MARKER)
        return [
            markers.nth(index).get_attribute("data-selection-state")
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
