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
("新しい提案が以前とすべて異なる店舗になるとは限らない", worded identically in
both TDR-CS-03 and TDR-CS-11) states a non-constraint -- that full turnover
is *allowed*, not required -- so it has no corresponding assertion here;
permitting overlap is exactly what ``repeated_candidate_is_not_excluded``
below verifies.

TDR-CS-09 and TDR-CS-10 (adr/0015, candidate-search-api.yaml v0.5.0,
test-support-api.yaml v0.3.0) add the default genre exclusion and its
IZAKAYA_BAR_INCLUDED re-proposal lens; see the dedicated section below for
why TDR-CS-09's "excludes the genre" claim is verified by comparison against
that lens's response rather than a genre-string literal.

TDR-CS-11 (adr/0016, candidate-search-api.yaml v0.6.0,
candidate-search-browser-interface.yaml v0.4, test-support-api.yaml v0.4.0)
adds a same-lens "try again" action (``candidate-reproposal-try-again``) that
is always available outside the re-proposal dialog and resends the currently
displayed proposal's own kind. That same amendment also retires
``candidate-reproposal-submit``/purpose ``reproposal-submit``: selecting a
re-proposal option (``candidate-reproposal-option``) itself now performs the
re-proposal request, with no separate confirmation click. Every browser
action below that used to click a submit control after selecting an option
now captures the response from the selection click itself.

adr/0017 (candidate-search-api.yaml v0.7.0, candidate-search-browser-interface.yaml
v0.5, test-support-api.yaml v0.5.0) moves repeat demotion server-side: a
re-proposal request now carries ``previouslyShownProviderPageUrls``, the exact
providerPageUrl values already rendered on this screen, and the server -- not
the browser -- demotes matching candidates before applying the 5-item display
cap. ``businessHours`` is removed from the Candidate schema and from
``requiredFields``, so it is no longer asserted on cards (TDR-CS-02).
``requiredFields`` field list and card-level formatting are otherwise
unchanged. The revised ``repeatPriority.invariant`` in
candidate-search-browser-interface.yaml is a machine-checkable, black-box
observation (the exact request body the browser sent, and the absence of the
comparison state from storage/cookie/URL) rather than a judgment about prose,
so it is asserted directly -- see ``assert_repeat_priority_orders_new_before_repeated``
and its private helpers below -- unlike TDR-CS-09's rationale-tone claim
(module section below), which meta/verification.md 3.4 rules out of L4.
test-support-api.yaml's NORMAL_WITH_REPEAT now supplies, for at least one
concept, more than 5 lunch-eligible synthetic candidates so this demotion is
genuinely exercised by TDR-CS-03, TDR-CS-09, and TDR-CS-11's requests rather
than satisfied by a fixed response shape independent of what was sent.

adr/0019 (candidate-search-api.yaml v0.9.0, candidate-search-browser-interface.yaml
v0.7, test-support-api.yaml v0.7.0) regroups ConceptKind onto PROXIMITY,
GENRE_FOCUS, NON_SMOKING_REFERENCE, and IZAKAYA_BAR_INCLUDED (CAPACITY_REFERENCE
and AMENITY_REFERENCE are retired), removes ``access`` from the Candidate
schema and from ``requiredFields``, and adds three new Candidate fields:
``capacityTier`` (a coarse label that becomes totalSeats's own visible value,
still checked for exact raw equality only through totalSeats's existing
``data-raw-value`` attribute -- no separate DOM assertion exists for
capacityTier itself, since the browser interface does not give it one),
``nonSmokingStatus`` and ``dinnerBudgetTier`` (each a new ``requiredFields``
entry reusing the same rawValueAttribute mechanism ADR-0011 established for
totalSeats, extended to a second and third field for the first time). A new
conditional element, ``cardPaymentCaution``, is asserted only via the two new
TDR-CS-12 methods near the bottom of this module -- it is not a
``requiredFields`` entry (it has no ``data-value-state``/unavailable state;
its presence itself is the signal) and is asserted separately from
``assert_required_card_fields_match_current_proposal``. See that method's new
sibling ``assert_dinner_budget_reference_is_shown`` for why TDR-CS-02's new
"discloses it is a dinner reference" Then-clause is limited to a presence
check.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase
from playwright.sync_api import Locator, Page, expect

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
TRY_AGAIN = "candidate-reproposal-try-again"
NO_RESULTS = "candidate-no-results"
PROBLEM = "candidate-proposal-problem"
PROBLEM_GUIDANCE = "candidate-proposal-problem-guidance"
SECONDARY_CONDITIONS = "candidate-secondary-conditions"
MANUAL_ORDERING = "candidate-manual-ordering"

CANDIDATE_SCREEN_FORBIDDEN_WHEN_UNAUTHENTICATED = [
    CONTENT,
    MAP,
    REPROPOSAL_OPEN,
    TRY_AGAIN,
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
    # cardDataAttributes.requiredFields. rawValueAttribute is declared for
    # totalSeats (ADR-0011, the original field), and, since adr/0019, also
    # for nonSmokingStatus and dinnerBudgetTier: each of these three fields'
    # visible value may carry implementation-chosen display formatting (a
    # unit suffix, or -- for totalSeats specifically -- a wholly different
    # coarse label derived from capacityTier) around or instead of the
    # returned value, so equality is instead checked on that attribute.
    # ``access`` was removed entirely by adr/0019 (Candidate no longer
    # returns it; the map already shows shop location).
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
PROVIDER_PAGE_LINK_TEST_ID = "candidate-card-provider-page-link"
VALUE_STATES = {"provided", "unavailable"}
ALLOWED_CONTROL_PURPOSES = {
    "candidate-card-selection",
    "candidate-map-marker-selection",
    "reproposal-open",
    "reproposal-selection",
    "reproposal-try-again",
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

# adr/0017 + candidate-search-browser-interface.yaml repeatPriority.invariant:
# "The browser does not persist this state outside its own current-screen
# memory; it is never written to storage, a cookie, or the URL." This reads
# every key/value pair actually held in localStorage and sessionStorage (a
# plain property spread over a Storage object does not enumerate its entries,
# so the entries must be walked explicitly) as one JSON string a caller can
# search for a providerPageUrl value.
DUMP_BROWSER_STORAGE_JS = """
() => {
  const dump = (storage) => {
    const out = {};
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      out[key] = storage.getItem(key);
    }
    return out;
  };
  return JSON.stringify({ local: dump(localStorage), session: dump(sessionStorage) });
}
"""

# adr/0015: the only ConceptKind whose population additionally includes the
# genre category that is excluded by default from the other three kinds
# (PROXIMITY, GENRE_FOCUS, NON_SMOKING_REFERENCE, as regrouped by adr/0019;
# CAPACITY_REFERENCE and AMENITY_REFERENCE were removed, and GENRE_VARIETY
# was the prior fourth value until adr/0016 removed it).
IZAKAYA_BAR_INCLUDED = "IZAKAYA_BAR_INCLUDED"


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
            self.assertions,
            self.page,
            [CONTENT, CARDS, MAP, PROVIDER_CREDIT, REPROPOSAL_OPEN, TRY_AGAIN],
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
        cards, candidates_by_ref = self._current_cards_by_candidate_ref()
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

    def assert_dinner_budget_reference_is_shown(self) -> None:
        """TDR-CS-02's new Then-clause, "予算のめやすは、ディナーの価格である
        ことが分かるように示される", requires the visible dinnerBudgetTier
        label to disclose it is a dinner-price reference "or an equivalent
        qualifier" -- candidate-search-browser-interface.yaml's own
        nullBehavior description leaves the exact wording non-binding ("a
        'dinner' or equivalent qualifier"), and adr/0019 itself calls its
        example labels non-binding. Soundly verifying that free-form text
        discloses this specific meaning needs comprehension a mechanized L4
        check cannot provide without either rejecting a compliant but
        differently-worded label (a false negative if it required the
        literal substring "ディナー") or accepting a coincidental substring
        match that is not really a dinner disclosure (a false positive) --
        the same reasoning meta/verification.md 3.4 sets out, and the same
        reasoning that already limits
        assert_izakaya_bar_included_rationale_does_not_claim_confirmed_lunch
        to a presence check rather than reviving the keyword-denylist
        approach that check's own docstring records as rejected. This
        assertion is therefore limited to what
        assert_required_card_fields_match_current_proposal already
        establishes soundly for dinnerBudgetTier -- the field is rendered
        with its required label, and its data-raw-value attribute equals the
        returned enum value exactly -- and leaves the "states a dinner
        reference, not a lunch price" judgment to human review.
        """
        self.assert_required_card_fields_match_current_proposal()

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

    # Observable assertions and actions: re-proposal (TDR-CS-03, TDR-CS-11) -

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

    def select_first_offered_lens(self) -> str:
        # adr/0016: selecting a re-proposal option itself performs the
        # re-proposal request; there is no longer a separate submit control
        # to click afterward.
        options = wait_for_at_least_one(self.page, REPROPOSAL_OPTION)
        first_option = options.first
        chosen_kind = first_option.get_attribute("data-reproposal-kind")
        self.assertions.assertTrue(chosen_kind)

        def trigger() -> None:
            first_option.click()

        self.reproposal = capture_candidate_proposal_response(self.page, trigger)
        assert_matches_openapi_schema(
            self.reproposal.payload,
            CANDIDATE_API_CONTRACT,
            "#/components/schemas/CandidateProposalResponse",
        )
        return chosen_kind

    def select_try_again(self) -> None:
        # adr/0016: candidate-reproposal-try-again is always available (it
        # does not require opening the re-proposal dialog first) and resends
        # the currently displayed proposal's own kind.
        def trigger() -> None:
            by_test_id(self.page, TRY_AGAIN).click()

        self.reproposal = capture_candidate_proposal_response(self.page, trigger)
        assert_matches_openapi_schema(
            self.reproposal.payload,
            CANDIDATE_API_CONTRACT,
            "#/components/schemas/CandidateProposalResponse",
        )

    def assert_display_replaced_by_reproposal(self, chosen_kind: str) -> None:
        self._assert_display_matches_reproposal_of_kind(chosen_kind)

    def assert_new_proposal_uses_same_lens_and_replaces_display(self) -> None:
        previous_kind = require(self.initial, "candidate screen was not opened").payload[
            "proposal"
        ]["kind"]
        self._assert_display_matches_reproposal_of_kind(previous_kind)

    def _assert_display_matches_reproposal_of_kind(self, expected_kind: str) -> None:
        assert_absent(self.assertions, self.page, REPROPOSAL_DIALOG)
        response = require(self.reproposal, "re-proposal was not requested")
        proposal = response.payload["proposal"]
        self.assertions.assertIsNotNone(proposal)
        self.assertions.assertEqual(proposal["kind"], expected_kind)
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
        self._assert_previously_shown_urls_were_echoed_exactly(previous_hrefs)
        self._assert_shown_state_not_persisted_outside_screen_memory(previous_hrefs)
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

    def _assert_previously_shown_urls_were_echoed_exactly(self, previously_shown: set[str]) -> None:
        """adr/0017 + repeatPriority.invariant: the request body's
        ``previouslyShownProviderPageUrls`` must contain exactly the
        providerPageUrl values already rendered on this screen, and nothing
        else -- not invented by the browser. This is a structural comparison
        of the exact JSON request the browser sent (captured from the real
        network exchange, not re-derived) against the exact set of URLs the
        prior response actually returned, so it needs no meaning judgment.
        """
        response = require(self.reproposal, "re-proposal was not requested")
        sent = response.request_body or {}
        echoed = set(sent.get("previouslyShownProviderPageUrls") or [])
        self.assertions.assertEqual(
            echoed,
            previously_shown,
            "previouslyShownProviderPageUrls must echo exactly the "
            "providerPageUrl values already rendered on this screen, and "
            "nothing else (adr/0017)",
        )

    def _assert_shown_state_not_persisted_outside_screen_memory(
        self, previously_shown: set[str]
    ) -> None:
        """adr/0017 + repeatPriority.invariant: the browser does not persist
        the shown-candidate comparison state outside its own current-screen
        memory -- never written to storage, a cookie, or the URL. Checked by
        searching the real values a leak would have to contain (the shown
        candidates' providerPageUrl values) in the browser's actual storage
        contents, cookie jar, and current URL -- the same canary-search
        pattern already used for private-origin disclosure (``_assert_no_disclosures``),
        not a judgment about implementation structure.
        """
        storage_dump = self.page.evaluate(DUMP_BROWSER_STORAGE_JS)
        cookie_values = " ".join(cookie.get("value", "") for cookie in self.page.context.cookies())
        for url in previously_shown:
            self.assertions.assertNotIn(
                url,
                storage_dump,
                "shown-candidate comparison state must not be written to "
                "localStorage or sessionStorage (adr/0008 decision 3, adr/0017)",
            )
            self.assertions.assertNotIn(
                url,
                cookie_values,
                "shown-candidate comparison state must not be written to a "
                "cookie (adr/0008 decision 3, adr/0017)",
            )
            self.assertions.assertNotIn(
                url,
                self.page.url,
                "shown-candidate comparison state must not be written to the "
                "URL (adr/0008 decision 3, adr/0017)",
            )

    # Observable assertions and actions: default genre exclusion ----------
    # (TDR-CS-09, TDR-CS-10). TDR-CS-09's "初期の候補には...含めない" has no
    # contract-given genre-string oracle (candidate-search-api.yaml
    # deliberately leaves genre membership to implementation, per adr/0015
    # decision 3), so the only sound black-box verification compares the
    # default proposal's candidates against the IZAKAYA_BAR_INCLUDED lens's
    # candidates -- exactly the comparison test-support-api.yaml's
    # NORMAL_WITH_REPEAT guarantee describes for TDR-CS-09. This requires the
    # lens-selection action to have already happened, so the test method
    # performs that action before asserting the "excludes" claim even though
    # the claim appears earlier in the scenario's Then block.

    def assert_izakaya_bar_included_offered_as_reproposal_option(self) -> None:
        options = wait_for_at_least_one(self.page, REPROPOSAL_OPTION)
        kinds = [
            options.nth(index).get_attribute("data-reproposal-kind")
            for index in range(options.count())
        ]
        self.assertions.assertIn(
            IZAKAYA_BAR_INCLUDED,
            kinds,
            "IZAKAYA_BAR_INCLUDED was not offered among the re-proposal options",
        )

    def select_izakaya_bar_included_lens(self) -> None:
        options = wait_for_at_least_one(self.page, REPROPOSAL_OPTION)
        matching = [
            options.nth(index)
            for index in range(options.count())
            if options.nth(index).get_attribute("data-reproposal-kind") == IZAKAYA_BAR_INCLUDED
        ]
        self.assertions.assertTrue(matching, "IZAKAYA_BAR_INCLUDED was not offered to select")
        target = matching[0]

        def trigger() -> None:
            target.click()

        self.reproposal = capture_candidate_proposal_response(self.page, trigger)
        assert_matches_openapi_schema(
            self.reproposal.payload,
            CANDIDATE_API_CONTRACT,
            "#/components/schemas/CandidateProposalResponse",
        )

    def assert_initial_excludes_hard_to_confirm_lunch_genre(self) -> None:
        additions = self._izakaya_bar_included_additions()
        self.assertions.assertTrue(
            additions,
            "selecting IZAKAYA_BAR_INCLUDED added no candidate absent from the "
            "initial default proposal, so this scenario's Given precondition "
            "(a hard-to-confirm-genre candidate exists) was not observable",
        )
        added_genres = {candidate["genre"] for candidate in additions}
        default = require(self.initial, "candidate screen was not opened").payload["proposal"]
        default_genres = {candidate["genre"] for candidate in default["candidates"]}
        self.assertions.assertFalse(
            default_genres & added_genres,
            "the initial default proposal included a shop whose genre matches a "
            "shop only reachable via the IZAKAYA_BAR_INCLUDED lens (adr/0015)",
        )

    def assert_chosen_lens_includes_hard_to_confirm_lunch_genre(self) -> None:
        additions = self._izakaya_bar_included_additions()
        self.assertions.assertTrue(
            additions,
            "the IZAKAYA_BAR_INCLUDED lens did not include any candidate absent "
            "from the initial default proposal",
        )

    def assert_izakaya_bar_included_rationale_does_not_claim_confirmed_lunch(self) -> None:
        """TDR-CS-09's "その切り口の説明は...断定しない" is a claim about the
        *meaning* of free-form prose; candidate-search-api.yaml's rationale
        constraint is prose ("must not promise... other unavailable facts"),
        not an enum or exact string this file can compare against.

        A keyword-denylist substring check
        (``LUNCH_SERVICE_CONFIRMED_CLAIM_MARKERS``, since removed) was tried
        first and rejected by a real run: a compliant, correctly-hedged
        rationale ("...含めた店舗が実際にランチ営業しているとは限らない
        ため...") contains the substring "実際にランチ営業している" only as
        part of its own negation ("とは限らない"), so naive substring
        matching produced a false failure against exactly the behavior this
        scenario requires. Soundly verifying a negative natural-language
        claim needs meaning comprehension a mechanized L4 check cannot
        provide without risking the same false positive again under
        different but equally compliant phrasing (meta/verification.md
        3.4's "検証手段を選ぶ前に、まずその検証に意味理解が要るかを問う").
        This assertion is therefore limited to what a presence check can
        soundly establish -- the concept shows a rationale at all -- and
        leaves the tone judgment to human review.
        """
        rationale = by_test_id(self.page, CONCEPT_RATIONALE).inner_text().strip()
        self.assertions.assertTrue(
            rationale, "the IZAKAYA_BAR_INCLUDED concept must show a rationale"
        )

    def assert_fallback_proposal_uses_izakaya_bar_included_lens(self) -> None:
        response = require(self.initial, "candidate screen was not opened")
        self.assertions.assertEqual(response.status, 200)
        proposal = response.payload["proposal"]
        self.assertions.assertIsNotNone(
            proposal,
            "excluding the hard-to-confirm lunch genre must not surface as 'no "
            "matching candidates' when including that genre still has "
            "candidates (adr/0015 decision 4)",
        )
        self.assertions.assertEqual(proposal["kind"], IZAKAYA_BAR_INCLUDED)
        self.assertions.assertTrue(
            proposal["candidates"], "the fallback proposal has no candidates"
        )
        assert_all_present(self.assertions, self.page, [CONTENT, CARDS, MAP])

    def assert_no_results_indicator_absent(self) -> None:
        assert_absent(self.assertions, self.page, NO_RESULTS)

    # Observable assertions: card-payment caution (TDR-CS-12, adr/0019) ---
    # cardPaymentCaution is a conditional element, not a requiredFields
    # entry: candidate-search-browser-interface.yaml gives it its own
    # presenceRule (present with data-card-payment-available="false" only
    # when cardPaymentAvailable is false; otherwise absent from the DOM
    # entirely, unlike an unavailable requiredFields entry which still
    # renders with data-value-state=unavailable). It is therefore asserted
    # separately from assert_required_card_fields_match_current_proposal
    # rather than folded into REQUIRED_CARD_FIELDS.

    def assert_payment_caution_shown_for_unavailable_card_payment(self) -> None:
        cards, candidates_by_ref = self._current_cards_by_candidate_ref()
        unavailable_seen = False
        for index in range(cards.count()):
            card = cards.nth(index)
            candidate = candidates_by_ref[card.get_attribute("data-candidate-ref")]
            if candidate["cardPaymentAvailable"] is False:
                unavailable_seen = True
                caution = assert_present(self.assertions, card, CARD_PAYMENT_CAUTION_TEST_ID)
                expect(caution).to_have_attribute(CARD_PAYMENT_CAUTION_ATTRIBUTE, "false")
        self.assertions.assertTrue(
            unavailable_seen,
            "no displayed candidate had cardPaymentAvailable false; the "
            "Given precondition (a shop without card payment) was not "
            "observable in this response",
        )

    def assert_payment_caution_absent_when_card_payment_is_available_or_unknown(self) -> None:
        cards, candidates_by_ref = self._current_cards_by_candidate_ref()
        other_seen = False
        for index in range(cards.count()):
            card = cards.nth(index)
            candidate = candidates_by_ref[card.get_attribute("data-candidate-ref")]
            if candidate["cardPaymentAvailable"] is not False:
                other_seen = True
                assert_absent(self.assertions, card, CARD_PAYMENT_CAUTION_TEST_ID)
        self.assertions.assertTrue(
            other_seen,
            "every displayed candidate had cardPaymentAvailable false; no "
            "contrasting candidate (true or null) was observable in this "
            "response",
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
        # requestUnavailableEnumLens exists because the requested kind
        # (NON_SMOKING_REFERENCE, since adr/0019 -- test-support-api.yaml's
        # NORMAL_WITH_REPEAT deliberately gives every default-population
        # candidate the same non-smoking reference so this valid enum value
        # is unbuildable, replacing the removed AMENITY_REFERENCE reference)
        # is, by this scenario's own precondition, not
        # among the reproposal dialog's currently offered options -- there is
        # no clickable UI option for it. Opening the dialog and selecting a
        # different, actually-offered option keeps the request on the real
        # UI-driven request/response code path the contract's requiredOutcome
        # observes (adr/0016: selecting an option itself performs the
        # re-proposal, so that click is the trigger); only the outgoing body
        # is substituted for the contract's exact publicOperation.requestBody
        # before it reaches the server, so the app's own client-side handling
        # renders the rejection outcome from a genuine server response rather
        # than from a side-channel call its JavaScript never sees.
        self.open_reproposal_popup()
        offered_option = wait_for_at_least_one(self.page, REPROPOSAL_OPTION).first

        def trigger() -> None:
            offered_option.click()

        self.direct = capture_candidate_proposal_response_with_overridden_body(
            self.page, trigger, {"reproposalKind": kind}
        )

    # Private helpers -------------------------------------------------------

    def _current_cards_by_candidate_ref(self) -> tuple[Locator, dict[str, dict]]:
        """The rendered card locator plus the initial response's own
        candidates keyed by candidateRef, shared by every assertion that
        must compare a specific rendered card against the specific response
        candidate it was rendered from (required-field equality, card-payment
        caution presence)."""
        response = require(self.initial, "candidate screen was not opened")
        proposal = response.payload["proposal"]
        self.assertions.assertIsNotNone(proposal)
        candidates_by_ref = {c["candidateRef"]: c for c in proposal["candidates"]}
        cards = wait_for_at_least_one(self.page, CARD)
        return cards, candidates_by_ref

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

    def _izakaya_bar_included_additions(self) -> list[dict]:
        default = require(self.initial, "candidate screen was not opened").payload["proposal"]
        included = require(self.reproposal, "IZAKAYA_BAR_INCLUDED lens was not selected").payload[
            "proposal"
        ]
        default_urls = {candidate["providerPageUrl"] for candidate in default["candidates"]}
        return [
            candidate
            for candidate in included["candidates"]
            if candidate["providerPageUrl"] not in default_urls
        ]

    def _assert_no_disclosures(self) -> None:
        html = self.page.content()
        self.assertions.assertNotIn(PRIVATE_ORIGIN_CANARY, html)
        self.assertions.assertNotIn(PROVIDER_INTERNALS_CANARY, html)
        assert_all_absent(self.assertions, self.page, DISCLOSURE_FORBIDDEN_TEST_IDS)
