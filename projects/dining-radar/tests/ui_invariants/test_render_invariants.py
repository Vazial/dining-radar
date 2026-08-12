"""Machine-checked UI invariants against the real rendered candidate screen.

ADR-0020 decision 4 defines four Must, gate invariants -- (a) narrow-width map
reachability, (c) keyboard reachability/activation, (d) internal-enum
non-exposure, (e) 44px minimum activatable-control size -- as independent DOM/
geometry checks, deliberately not full-screen pixel comparison (decision 2,
decision 5; ``meta/adr/0021``/``meta/adr/0024`` are not superseded). This file
implements them.

This is not a Gherkin/step/DSL translation of a business scenario (ADR-0020
decision 6, decision 9): it directly asserts the four mechanical rules
against ``contracts/candidate-search-browser-interface.yaml``'s own control
surface. It lives outside ``tests/acceptance/steps``/``dsl`` on purpose --
those are the tester's domain (``developer.md``); this file, like ordinary
implementation code and unit tests, is maintained by developer.

It reuses the same JS-capable browser harness
(``StaticLiveServerTestCase`` + ``sync_playwright``) as
``tests/acceptance/test_candidate_search_acceptance.py`` (ADR-0020 decision 6
explicitly allows this), and reuses ``CandidateSearchBrowserDsl`` only for its
already-reviewed Given-seam setup and screen navigation (``reset_*``,
``enable_organizer``, ``sign_in``, ``set_candidate_state``,
``open_candidate_screen``) -- never for assertions, which are this file's own
and specific to ADR-0020 decision 4, not to any TDR-CS business scenario.

Floor changes: decision 4's four invariants (and the (d)/(e) allowlists this
file maintains) are this ADR's own initial baseline (decision 2's "initial
approval doubles as baseline approval"). Loosening any of them, or adding a
fifth gate invariant, needs a new ADR (decision 2); the allowlists themselves
may be updated here, by developer, only to track a contract change the
allowlists' own comments cite (decision 4(d), decision 4(e)).
"""

from __future__ import annotations

import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import Locator, expect, sync_playwright

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.dsl.js_browser_mechanics import (
    by_test_id,
    is_candidate_proposal_response,
    wait_for_at_least_one,
)

ORGANIZER_ACCOUNT_REF = "ui-invariants-organizer"
ORGANIZER_IDENTIFIER = "synthetic-ui-invariants-organizer"
ORGANIZER_PASSWORD = "synthetic-ui-invariants-secret"

# ADR-0020 decision 4(a): the viewport set a narrow-width check runs against.
# 730px is mandatory -- it is the exact width the original human-reported
# defect occurred at (ADR-0020 context section 1/2) -- plus two other widths
# developer already treats as distinct layout cases: 390px (a common phone
# width, also the one orchestrator measured in activeContext.md) and 1023px
# (the pixel just below home.html's own 64rem/1024px breakpoint, i.e. the
# narrowest case still using the "map above cards" grid-template-areas
# layout rather than the side-by-side one).
NARROW_VIEWPORTS = [
    (390, 844, "phone-390x844"),
    (730, 900, "original-defect-730x900"),
    (1023, 900, "pre-breakpoint-1023x900"),
]

# ADR-0020 decision 4(e): the viewport set the 44px activatable-control check
# runs against -- the two widths orchestrator already measured by hand in
# activeContext.md (390x844, 1440x900), plus the 730px defect width shared
# with the (a) check above, so both known layout branches (narrow
# grid-template-areas, wide side-by-side) are exercised at more than one
# concrete width each.
CONTROL_SIZE_VIEWPORTS = [
    (390, 844, "phone-390x844"),
    (730, 900, "original-defect-730x900"),
    (1440, 900, "desktop-1440x900"),
]

MINIMUM_TARGET_PX = 44

# ADR-0020 decision 4(e)'s explicit, human-confirmed exception: the two
# credit/attribution links (activeContext.md; WCAG 2.5.8's in-sentence-link
# case; candidate-search-browser-interface.yaml fixes their wording by
# contract, so they cannot be grown into a button-shaped 44px target without
# contradicting that fixed text). Neither test id below ever declares
# data-candidate-control-purpose in the current implementation, so today this
# allowlist only documents the exception rather than actually excluding
# anything from the query below; it is kept explicit (not a silent omission)
# so a future change that *does* give either link a control purpose is still
# covered, per decision 4(e)'s "no silent exclusion" requirement.
CONTROL_SIZE_ALLOWLIST_TEST_IDS = {
    "candidate-provider-credit",
    "candidate-map-attribution",
}

# ADR-0020 decision 4(d): the closed, developer-maintained list of internal
# enum tokens that must never appear as their own standalone visible text
# node. Sourced from contracts/candidate-search-api.yaml's own enum
# definitions (ConceptKind, Candidate.capacityTier, Candidate.nonSmokingStatus,
# Candidate.dinnerBudgetTier); update this list in the same change that adds,
# renames, or removes an enum value in that contract.
FORBIDDEN_INTERNAL_ENUM_TOKENS = [
    # ConceptKind
    "PROXIMITY",
    "GENRE_FOCUS",
    "NON_SMOKING_REFERENCE",
    "IZAKAYA_BAR_INCLUDED",
    # Candidate.capacityTier
    "SMALL",
    "MEDIUM",
    "LARGE",
    # Candidate.nonSmokingStatus
    "FULL",
    "PARTIAL",
    "NONE",
    # Candidate.dinnerBudgetTier
    "LOW",
    "MID",
    "HIGH",
]

# Scans only real DOM text nodes (never attribute values, so a
# data-raw-value/data-reproposal-kind attribute's own raw enum string is
# never itself examined here -- "outside data-raw-value" per decision 4(d) is
# automatically true for a text-node walk) for a trimmed, standalone,
# case-sensitive match against the developer-maintained token list above.
_SCAN_VISIBLE_TEXT_FOR_TOKENS_JS = """
(tokens) => {
  const tokenSet = new Set(tokens);
  const matches = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const text = node.textContent.trim();
    if (text && tokenSet.has(text)) {
      const parent = node.parentElement;
      matches.push({
        text: text,
        parentTag: parent ? parent.tagName : null,
        parentTestId: parent ? parent.getAttribute("data-testid") : null,
      });
    }
    node = walker.nextNode();
  }
  return matches;
}
"""


class RenderedScreenInvariantTests(StaticLiveServerTestCase):
    """Each test method is one independent ADR-0020 decision 4 invariant.

    Setup mirrors ``tests/acceptance/test_candidate_search_acceptance.py``
    (same known Playwright-sync/Django async_unsafe interaction; see that
    file's own comment for why ``DJANGO_ALLOW_ASYNC_UNSAFE`` is required).
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._previous_base_url = os.environ.get("TDR_ACCEPTANCE_BASE_URL")
        os.environ["TDR_ACCEPTANCE_BASE_URL"] = cls.live_server_url
        cls._previous_async_unsafe = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"
        cls._playwright = sync_playwright().start()
        cls._browser = cls._playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._playwright.stop()
        if cls._previous_async_unsafe is None:
            os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
        else:
            os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = cls._previous_async_unsafe
        if cls._previous_base_url is None:
            os.environ.pop("TDR_ACCEPTANCE_BASE_URL", None)
        else:
            os.environ["TDR_ACCEPTANCE_BASE_URL"] = cls._previous_base_url
        super().tearDownClass()

    def setUp(self) -> None:
        base_url = os.environ["TDR_ACCEPTANCE_BASE_URL"]
        self.context = self._browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dsl = CandidateSearchBrowserDsl(self, self.page, base_url)

    # Shared Given helper -------------------------------------------------

    def _sign_in_with_candidates(self, mode: str = "NORMAL_WITH_REPEAT") -> None:
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state(mode)
        self.dsl.open_candidate_screen()

    # (a) Narrow-width map reachability ------------------------------------

    def test_a_map_is_reachable_without_scrolling_at_narrow_widths(self) -> None:
        self._sign_in_with_candidates()
        map_node = by_test_id(self.page, "candidate-map")
        for width, height, label in NARROW_VIEWPORTS:
            with self.subTest(viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                expect(map_node).to_be_visible()
                box = map_node.bounding_box()
                self.assertIsNotNone(box, f"candidate-map has no bounding box at {label}")
                # Playwright's bounding_box() keys are x/y/width/height (page
                # coordinates); "y" is the element's getBoundingClientRect().top
                # equivalent used against the current scroll position (the page
                # is not scrolled here, so the two coincide).
                self.assertLess(
                    box["y"],
                    height,
                    f"candidate-map top ({box['y']}px) is not within the {label} "
                    f"viewport height ({height}px) without scrolling -- "
                    "ADR-0020 decision 4(a)",
                )

    # (c) Keyboard reachability and activation -----------------------------

    def _assert_tabbable(self, locator: Locator, label: str) -> None:
        """decision 4(c)(i): not excluded from the Tab order.

        The ADR's own definition of "excluded from Tab order" is
        ``tabindex="-1"`` or ``display:none``; this also checks
        ``visibility:hidden`` and the boolean ``hidden`` attribute as the
        same class of exclusion (neither receives focus via Tab either).
        """
        metrics = locator.evaluate(
            "el => ({tabIndex: el.tabIndex, display: getComputedStyle(el).display,"
            " visibility: getComputedStyle(el).visibility, hidden: el.hidden})"
        )
        self.assertNotEqual(
            metrics["tabIndex"], -1, f"{label}: tabindex=-1 excludes it from the Tab order"
        )
        self.assertNotEqual(
            metrics["display"], "none", f"{label}: display:none excludes it from the Tab order"
        )
        self.assertNotEqual(metrics["visibility"], "hidden", f"{label}: visibility:hidden")
        self.assertFalse(metrics["hidden"], f"{label}: carries the hidden attribute")

    def _locator_for_ref(self, test_id: str, candidate_ref: str | None) -> Locator:
        return self.page.locator(f'[data-testid="{test_id}"][data-candidate-ref="{candidate_ref}"]')

    def _card_for_ref(self, candidate_ref: str | None) -> Locator:
        return self._locator_for_ref("candidate-card", candidate_ref)

    def _marker_for_ref(self, candidate_ref: str | None) -> Locator:
        return self._locator_for_ref("candidate-map-marker", candidate_ref)

    def _assert_selected(self, locator: Locator) -> None:
        expect(locator).to_have_attribute("data-selection-state", "selected")

    def _assert_unselected(self, locator: Locator) -> None:
        expect(locator).to_have_attribute("data-selection-state", "unselected")

    def test_c_candidate_card_selection_is_keyboard_operable(self) -> None:
        self._sign_in_with_candidates()
        cards = wait_for_at_least_one(self.page, "candidate-card")
        self.assertGreaterEqual(cards.count(), 3, "need at least 3 cards to exercise this check")

        enter_target = cards.nth(1)
        self._assert_tabbable(enter_target, "candidate-card[1]")
        enter_ref = enter_target.get_attribute("data-candidate-ref")
        enter_target.press("Enter")
        self._assert_selected(enter_target)
        self._assert_selected(self._marker_for_ref(enter_ref))

        space_target = cards.nth(2)
        self._assert_tabbable(space_target, "candidate-card[2]")
        space_ref = space_target.get_attribute("data-candidate-ref")
        space_target.press(" ")
        self._assert_selected(space_target)
        self._assert_unselected(enter_target)
        self._assert_selected(self._marker_for_ref(space_ref))

    def test_c_candidate_map_marker_selection_is_keyboard_operable(self) -> None:
        # ADR-0020 decision 4(c) surfaced this as a real defect: Leaflet's
        # `keyboard: true` marker option only makes the marker icon element
        # focusable -- it does not translate Enter/Space into a "click" for a
        # marker with no bound popup (confirmed by inspecting the vendored
        # leaflet.js). candidate.js now adds an explicit keydown handler
        # mirroring the candidate card's own; this test is what would have
        # caught that gap before this ADR existed.
        self._sign_in_with_candidates()
        markers = wait_for_at_least_one(self.page, "candidate-map-marker")
        self.assertGreaterEqual(
            markers.count(), 3, "need at least 3 markers to exercise this check"
        )

        enter_target = markers.nth(1)
        self._assert_tabbable(enter_target, "candidate-map-marker[1]")
        enter_ref = enter_target.get_attribute("data-candidate-ref")
        enter_target.press("Enter")
        self._assert_selected(enter_target)
        self._assert_selected(self._card_for_ref(enter_ref))

        space_target = markers.nth(2)
        self._assert_tabbable(space_target, "candidate-map-marker[2]")
        space_ref = space_target.get_attribute("data-candidate-ref")
        space_target.press(" ")
        self._assert_selected(space_target)
        self._assert_unselected(enter_target)
        self._assert_selected(self._card_for_ref(space_ref))

    def test_c_reproposal_open_option_and_cancel_are_keyboard_operable(self) -> None:
        self._sign_in_with_candidates()
        url_before = self.page.url

        open_control = by_test_id(self.page, "candidate-reproposal-open")
        self._assert_tabbable(open_control, "candidate-reproposal-open")
        open_control.press("Enter")
        expect(by_test_id(self.page, "candidate-reproposal-dialog")).to_be_attached()
        self.assertEqual(self.page.url, url_before, "opening the dialog must not navigate")

        option = wait_for_at_least_one(self.page, "candidate-reproposal-option").first
        self._assert_tabbable(option, "candidate-reproposal-option")
        with self.page.expect_response(is_candidate_proposal_response):
            option.press("Enter")
        expect(by_test_id(self.page, "candidate-reproposal-dialog")).to_have_count(0)

        # Re-open (this time via the mouse, already covered above) so cancel
        # can be exercised independently of the option-selection outcome.
        open_control.click()
        cancel = by_test_id(self.page, "candidate-reproposal-cancel")
        self._assert_tabbable(cancel, "candidate-reproposal-cancel")
        cancel.press("Enter")
        expect(by_test_id(self.page, "candidate-reproposal-dialog")).to_have_count(0)

    def test_c_try_again_is_keyboard_operable(self) -> None:
        self._sign_in_with_candidates()
        try_again = by_test_id(self.page, "candidate-reproposal-try-again")
        self._assert_tabbable(try_again, "candidate-reproposal-try-again")
        with self.page.expect_response(is_candidate_proposal_response) as info:
            try_again.press("Enter")
        self.assertEqual(info.value.status, 200)
        expect(by_test_id(self.page, "candidate-proposal-content")).to_be_attached()

    def test_c_account_menu_toggle_and_password_change_link_are_keyboard_operable(self) -> None:
        self._sign_in_with_candidates()
        toggle = by_test_id(self.page, "auth-account-menu-toggle")
        self._assert_tabbable(toggle, "auth-account-menu-toggle")
        details = self.page.locator("details.candidate-account-menu")
        self.assertFalse(details.evaluate("el => el.open"), "menu must start closed")

        toggle.press("Enter")
        self.assertTrue(details.evaluate("el => el.open"), "Enter did not open the account menu")

        password_change = by_test_id(self.page, "auth-password-change-open")
        self._assert_tabbable(password_change, "auth-password-change-open")
        expected_path = reverse("authentication:password_change")
        password_change.press("Enter")
        expect(self.page).to_have_url(f"{self.dsl.base_url}{expected_path}")

    def test_c_sign_out_is_keyboard_operable(self) -> None:
        self._sign_in_with_candidates()
        toggle = by_test_id(self.page, "auth-account-menu-toggle")
        toggle.click()
        sign_out = by_test_id(self.page, "auth-sign-out")
        self._assert_tabbable(sign_out, "auth-sign-out")
        sign_out.press("Enter")
        expect(by_test_id(self.page, "auth-sign-in-form")).to_be_attached()

    # (d) Internal enum values are never exposed as visible text ----------

    def _assert_no_raw_value_element_shows_its_own_raw_value_as_text(self) -> None:
        raw_value_nodes = self.page.locator("[data-raw-value]")
        count = raw_value_nodes.count()
        for index in range(count):
            node = raw_value_nodes.nth(index)
            raw_value = node.get_attribute("data-raw-value")
            visible_text = node.inner_text().strip()
            test_id = node.get_attribute("data-testid")
            self.assertNotEqual(
                visible_text,
                raw_value,
                f"{test_id or '(no testid)'}: visible text equals its own "
                f"data-raw-value ({raw_value!r}) -- ADR-0020 decision 4(d)",
            )

    def _assert_no_forbidden_enum_token_is_visible_standalone_text(self) -> None:
        matches = self.page.evaluate(
            _SCAN_VISIBLE_TEXT_FOR_TOKENS_JS, FORBIDDEN_INTERNAL_ENUM_TOKENS
        )
        self.assertEqual(
            matches,
            [],
            "internal enum token(s) exposed as standalone visible text outside "
            f"data-raw-value: {matches} -- ADR-0020 decision 4(d)",
        )

    def test_d_internal_enum_values_are_not_exposed_as_visible_text(self) -> None:
        self._sign_in_with_candidates()
        self._assert_no_raw_value_element_shows_its_own_raw_value_as_text()
        self._assert_no_forbidden_enum_token_is_visible_standalone_text()

        # Re-check with the re-proposal dialog open: its options render a
        # ConceptKind-derived title/rationale (data-reproposal-kind carries
        # the raw enum as an attribute, never as this element's own text).
        by_test_id(self.page, "candidate-reproposal-open").click()
        wait_for_at_least_one(self.page, "candidate-reproposal-option")
        self._assert_no_forbidden_enum_token_is_visible_standalone_text()

        # Re-check once more after a real re-proposal response has rendered
        # new cards (repeat-status badges, a different concept's fields).
        option = by_test_id(self.page, "candidate-reproposal-option").first
        with self.page.expect_response(is_candidate_proposal_response):
            option.click()
        self._assert_no_raw_value_element_shows_its_own_raw_value_as_text()
        self._assert_no_forbidden_enum_token_is_visible_standalone_text()

    # (e) 44px minimum activatable-control target --------------------------

    def _assert_all_declared_controls_meet_44px(self, context_label: str) -> None:
        controls = self.page.locator("[data-candidate-control-purpose]")
        count = controls.count()
        self.assertGreater(
            count,
            0,
            f"no activatable controls with a declared purpose were found ({context_label})",
        )
        for index in range(count):
            control = controls.nth(index)
            test_id = control.get_attribute("data-testid") or "(no testid)"
            if test_id in CONTROL_SIZE_ALLOWLIST_TEST_IDS:
                continue
            box = control.bounding_box()
            self.assertIsNotNone(box, f"{test_id} has no bounding box ({context_label})")
            self.assertGreaterEqual(
                box["width"],
                MINIMUM_TARGET_PX,
                f"{test_id} width {box['width']}px < {MINIMUM_TARGET_PX}px ({context_label})",
            )
            self.assertGreaterEqual(
                box["height"],
                MINIMUM_TARGET_PX,
                f"{test_id} height {box['height']}px < {MINIMUM_TARGET_PX}px ({context_label})",
            )

    def test_e_activatable_controls_meet_44px_minimum_target(self) -> None:
        self._sign_in_with_candidates()
        for width, height, label in CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})

            # Default screen: cards, markers, reproposal-open, try-again.
            wait_for_at_least_one(self.page, "candidate-card")
            wait_for_at_least_one(self.page, "candidate-map-marker")
            self._assert_all_declared_controls_meet_44px(f"default screen at {label}")

            # Re-proposal dialog: option(s) and cancel.
            by_test_id(self.page, "candidate-reproposal-open").click()
            wait_for_at_least_one(self.page, "candidate-reproposal-option")
            self._assert_all_declared_controls_meet_44px(f"reproposal dialog at {label}")
            by_test_id(self.page, "candidate-reproposal-cancel").click()
            expect(by_test_id(self.page, "candidate-reproposal-dialog")).to_have_count(0)

            # Account menu: toggle, sign-out, password-change-open.
            by_test_id(self.page, "auth-account-menu-toggle").click()
            expect(by_test_id(self.page, "auth-sign-out")).to_be_visible()
            self._assert_all_declared_controls_meet_44px(f"account menu open at {label}")
            by_test_id(self.page, "auth-account-menu-toggle").click()
