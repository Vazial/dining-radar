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
    is_candidate_proposal_request,
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
# definitions (Candidate.capacityTier, Candidate.nonSmokingStatus,
# Candidate.dinnerBudgetTier); update this list in the same change that adds,
# renames, or removes an enum value in that contract. adr/0023 retires
# ConceptKind entirely (its values PROXIMITY/GENRE_FOCUS/
# NON_SMOKING_REFERENCE/IZAKAYA_BAR_INCLUDED no longer exist anywhere in the
# contract), so they are removed from this list rather than left as dead
# tokens that could never be exercised.
FORBIDDEN_INTERNAL_ENUM_TOKENS = [
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
# data-raw-value/data-genre-value/data-budget-tier-value attribute's own raw
# enum string is never itself examined here -- "outside data-raw-value" per
# decision 4(d) is automatically true for a text-node walk) for a trimmed,
# standalone, case-sensitive match against the developer-maintained token
# list above.
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

    def _sign_in_with_candidates(self, mode: str = "NORMAL_WITH_WEIGHTED_SAMPLING") -> None:
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state(mode)
        self.dsl.open_candidate_screen()

    def test_long_regular_holiday_wraps_inside_a_narrow_card_without_truncation(self) -> None:
        """Regression coverage for the provider's free-text holiday reference.

        This is intentionally a presentation regression, not an additional
        ADR-0020 gate invariant: it intercepts only the already-synthetic
        proposal response to give its first card a long free-text value.
        The public API shape, acceptance steps, and state seam remain
        unchanged.
        """

        long_regular_holiday = (
            "毎週月曜日・第2火曜日・祝日の翌日・年末年始・臨時休業は店舗にご確認ください" * 3
        )

        def with_long_regular_holiday(route):
            response = route.fetch()
            body = response.json()
            body["candidates"][0]["regularHoliday"] = long_regular_holiday
            route.fulfill(response=response, json=body)

        self._sign_in_with_candidates()
        self.page.route("**/candidate-proposals", with_long_regular_holiday)
        by_test_id(self.page, "candidate-search-again").click()
        self.page.set_viewport_size({"width": 390, "height": 844})

        regular_holiday = by_test_id(self.page, "candidate-card-regular-holiday").first
        expect(regular_holiday).to_have_text(long_regular_holiday)

        measurement = regular_holiday.evaluate(
            """node => {
              const card = node.closest('[data-testid="candidate-card"]');
              const nodeBox = node.getBoundingClientRect();
              const cardBox = card.getBoundingClientRect();
              const nodeStyle = getComputedStyle(node);
              const cardStyle = getComputedStyle(card);
              return {
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                height: nodeBox.height,
                width: nodeBox.width,
                cardHeight: cardBox.height,
                cardWidth: cardBox.width,
                left: nodeBox.left,
                right: nodeBox.right,
                cardLeft: cardBox.left,
                cardRight: cardBox.right,
                whiteSpace: nodeStyle.whiteSpace,
                textOverflow: nodeStyle.textOverflow,
                overflowX: nodeStyle.overflowX,
                cardOverflowY: cardStyle.overflowY,
              };
            }"""
        )

        self.assertEqual(measurement["whiteSpace"], "normal")
        self.assertEqual(measurement["textOverflow"], "clip")
        self.assertEqual(measurement["overflowX"], "visible")
        self.assertLessEqual(measurement["scrollWidth"], measurement["clientWidth"])
        self.assertGreaterEqual(
            measurement["width"],
            measurement["cardWidth"] * 0.7,
            "regular-holiday value should keep most of the card width after "
            "the link moves below it",
        )
        self.assertGreater(
            measurement["height"], 32, "long text should wrap beyond two short lines"
        )
        self.assertGreater(
            measurement["cardHeight"], 216, "card must grow beyond the retired max height"
        )
        self.assertGreaterEqual(measurement["left"], measurement["cardLeft"])
        self.assertLessEqual(measurement["right"], measurement["cardRight"])
        self.assertNotEqual(measurement["cardOverflowY"], "hidden")

    def test_map_tiles_still_cover_the_container_after_it_resizes_without_a_window_resize(
        self,
    ) -> None:
        """Regression coverage for activeContext.md's Next work 5.

        This is intentionally a presentation regression, not an additional
        ADR-0020 gate invariant (decision 4's four invariants are frozen;
        see this file's module docstring): it exercises one specific,
        previously-unhandled path to a stale Leaflet view, not a new gate.

        Leaflet's own default ``trackResize: true`` (candidate.js never
        overrides it) already re-fits the map on a plain browser ``window``
        "resize" event -- confirmed by reading the vendored leaflet.js's own
        ``_initEvents`` and, independently, by testing: even before
        candidate.js grew its own resize handling, a real
        ``page.set_viewport_size()`` call (which fires a ``window`` resize)
        already left the map's tiles covering the container correctly. What
        that built-in handler cannot see is a container-size change with no
        accompanying ``window`` resize event -- which this screen's own CSS
        can produce on a phone, since ``candidate-map``'s height is sized in
        ``dvh``/``vh`` units (home.html): a mobile browser's toolbar
        collapsing or reappearing while the organizer scrolls (the persona
        this screen is built for, per human decision 2026-08-22) resizes the
        container purely through CSS, without reliably firing ``window``
        "resize" on every mobile browser. This test reproduces that
        narrower path directly -- changing the container's own box via an
        inline style, with no viewport change at all -- which a plain
        ``page.set_viewport_size()``-based test cannot distinguish (Leaflet's
        own built-in handling already covers that case regardless of
        candidate.js). Reverting candidate.js's ``ResizeObserver`` and
        re-running this test reproduces a real, measured failure: the tiles
        stay at their stale pre-resize extent, leaving a real uncovered gap
        rather than covering the grown container.
        """
        self._sign_in_with_candidates()
        self.page.set_viewport_size({"width": 390, "height": 844})
        wait_for_at_least_one(self.page, "candidate-map-marker")

        map_container = by_test_id(self.page, "candidate-map")
        before = map_container.bounding_box()
        self.assertIsNotNone(before, "candidate-map has no bounding box before the resize")

        # Force the container's own box to grow well beyond its CSS-driven
        # size, without any window/viewport resize -- the same kind of
        # container-only size change a dvh-sized element undergoes when a
        # mobile browser's toolbar collapses.
        grown_width = int(before["width"]) + 400
        grown_height = int(before["height"]) + 200
        map_container.evaluate(
            "(node, size) => {"
            "  node.style.setProperty('width', size.width + 'px', 'important');"
            "  node.style.setProperty('height', size.height + 'px', 'important');"
            # candidate-map-wrapper is a column flexbox, so the map's own
            # main-axis (height) size would otherwise still be shrunk to fit
            # the wrapper's own fixed height despite the explicit height
            # above -- pin flex-basis/grow/shrink too so the forced size
            # actually takes effect.
            "  node.style.setProperty('flex', '0 0 ' + size.height + 'px', 'important');"
            "}",
            {"width": grown_width, "height": grown_height},
        )
        self.page.wait_for_timeout(400)

        after = map_container.bounding_box()
        self.assertIsNotNone(after, "candidate-map has no bounding box after the resize")
        self.assertAlmostEqual(after["width"], grown_width, delta=1)
        self.assertAlmostEqual(after["height"], grown_height, delta=1)

        coverage = self.page.evaluate(
            """() => {
              const container = document.querySelector('[data-testid="candidate-map"]');
              const containerBox = container.getBoundingClientRect();
              const tiles = Array.from(container.querySelectorAll('.leaflet-tile'));
              let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
              for (const tile of tiles) {
                const box = tile.getBoundingClientRect();
                minX = Math.min(minX, box.left);
                minY = Math.min(minY, box.top);
                maxX = Math.max(maxX, box.right);
                maxY = Math.max(maxY, box.bottom);
              }
              return {
                containerLeft: containerBox.left,
                containerTop: containerBox.top,
                containerRight: containerBox.right,
                containerBottom: containerBox.bottom,
                tileCount: tiles.length,
                tileMinX: minX,
                tileMinY: minY,
                tileMaxX: maxX,
                tileMaxY: maxY,
              };
            }"""
        )

        self.assertGreater(
            coverage["tileCount"], 0, "no map tiles rendered at all after the resize"
        )
        self.assertLessEqual(
            coverage["tileMinX"],
            coverage["containerLeft"],
            "rendered tiles do not reach the container's left edge -- stale Leaflet "
            "view after a container-only resize",
        )
        self.assertLessEqual(
            coverage["tileMinY"],
            coverage["containerTop"],
            "rendered tiles do not reach the container's top edge -- stale Leaflet "
            "view after a container-only resize",
        )
        self.assertGreaterEqual(
            coverage["tileMaxX"],
            coverage["containerRight"],
            "rendered tiles do not reach the container's right edge -- stale Leaflet "
            "view after a container-only resize",
        )
        self.assertGreaterEqual(
            coverage["tileMaxY"],
            coverage["containerBottom"],
            "rendered tiles do not reach the container's bottom edge -- stale Leaflet "
            "view after a container-only resize",
        )

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

    def test_c_filter_panel_open_and_apply_are_keyboard_operable(self) -> None:
        # ADR-0020 decision 4(c)'s original Given used the retired re-proposal
        # modal (candidate-reproposal-open/-dialog/-option); this project's
        # current control surface for "open a secondary condition surface,
        # change something, and commit it" is the always-visible filter panel
        # (adr/0023), so this test exercises the same invariant against
        # candidate-filter-open/-panel/-apply instead. Every control here is
        # a plain server-rendered <button>, which is natively keyboard-
        # operable without a custom keydown handler (unlike the Leaflet
        # marker case covered separately below) -- this test still presses
        # Enter explicitly, rather than only asserting tabbability, so a
        # future regression that intercepts/prevents the native activation
        # would still be caught.
        self._sign_in_with_candidates()
        url_before = self.page.url

        open_control = by_test_id(self.page, "candidate-filter-open")
        self._assert_tabbable(open_control, "candidate-filter-open")
        open_control.press("Enter")
        expect(by_test_id(self.page, "candidate-filter-panel")).to_be_attached()
        self.assertEqual(self.page.url, url_before, "opening the filter panel must not navigate")

        toggle = by_test_id(self.page, "candidate-filter-non-smoking-only")
        self._assert_tabbable(toggle, "candidate-filter-non-smoking-only")
        toggle.press("Enter")
        expect(by_test_id(self.page, "candidate-filter-pending-note")).to_be_attached()

        apply = by_test_id(self.page, "candidate-filter-apply")
        self._assert_tabbable(apply, "candidate-filter-apply")
        with self.page.expect_response(is_candidate_proposal_response):
            apply.press("Enter")
        expect(by_test_id(self.page, "candidate-filter-panel")).to_have_count(0)

    def test_c_filter_panel_revert_is_keyboard_operable_without_a_public_operation(self) -> None:
        # The filter model's analogue of the retired re-proposal dialog's
        # "cancel" control: candidate-filter-revert discards a pending change
        # via the keyboard alone, keeps the panel open, and -- unlike
        # apply -- never starts a public /candidate-proposals request
        # (contracts/candidate-search-browser-interface.yaml's
        # revertPendingFilters.requiredOutcome.publicOperation: none).
        self._sign_in_with_candidates()
        by_test_id(self.page, "candidate-filter-open").click()
        expect(by_test_id(self.page, "candidate-filter-panel")).to_be_attached()

        toggle = by_test_id(self.page, "candidate-filter-non-smoking-only")
        toggle.press("Enter")
        expect(by_test_id(self.page, "candidate-filter-pending-note")).to_be_attached()

        revert = by_test_id(self.page, "candidate-filter-revert")
        self._assert_tabbable(revert, "candidate-filter-revert")

        requests: list[object] = []

        def record(request: object) -> None:
            if is_candidate_proposal_request(request):
                requests.append(request)

        self.page.on("request", record)
        try:
            revert.press("Enter")
        finally:
            self.page.remove_listener("request", record)

        self.assertEqual(requests, [], "revert must not send a public candidate-proposal request")
        expect(by_test_id(self.page, "candidate-filter-panel")).to_be_attached()
        expect(by_test_id(self.page, "candidate-filter-pending-note")).to_have_count(0)

    def test_c_search_again_is_keyboard_operable(self) -> None:
        # Renamed from the retired candidate-reproposal-try-again control
        # (adr/0023): "search again with the same applied filters" is now
        # candidate-search-again.
        self._sign_in_with_candidates()
        search_again = by_test_id(self.page, "candidate-search-again")
        self._assert_tabbable(search_again, "candidate-search-again")
        with self.page.expect_response(is_candidate_proposal_response) as info:
            search_again.press("Enter")
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

        # Re-check with the filter panel open: its genre chips, soft-filter
        # toggles, and budget-tier options (candidate-filter-budget-tier-
        # option) render fixed labels/provider-supplied strings -- never the
        # raw LOW/MID/HIGH dinnerBudgetTier enum (adr/0023 decision 10) --
        # even though data-budget-tier-value carries that same raw string as
        # an attribute, not as this element's own visible text.
        by_test_id(self.page, "candidate-filter-open").click()
        wait_for_at_least_one(self.page, "candidate-filter-budget-tier-option")
        self._assert_no_forbidden_enum_token_is_visible_standalone_text()

        # Re-check once more after a real filter-apply response has rendered
        # new cards (a different nonSmokingStatus/dinnerBudgetTier mix).
        by_test_id(self.page, "candidate-filter-non-smoking-only").click()
        with self.page.expect_response(is_candidate_proposal_response):
            by_test_id(self.page, "candidate-filter-apply").click()
        self._assert_no_raw_value_element_shows_its_own_raw_value_as_text()
        self._assert_no_forbidden_enum_token_is_visible_standalone_text()

    # (e) 44px minimum activatable-control target --------------------------

    def _assert_all_declared_controls_meet_44px(self, context_label: str) -> None:
        """decision 4(e) gates the size of *activatable* control surface.

        A control declared inside a currently-closed native disclosure
        (``<details>``/``<summary>``, e.g. ``auth-sign-out`` and
        ``auth-password-change-open`` before ``auth-account-menu-toggle`` is
        opened) exists in server-rendered HTML per
        ``authentication-browser-interface.yaml``'s ``renderModel`` --
        satisfying "present" -- but is not activatable yet: it cannot be
        clicked, and (per ``authentication-browser-interface.yaml``'s own
        accountMenuToggleNotes) it becomes reachable only once the toggle
        discloses it. ``Locator.bounding_box()`` (``getBoundingClientRect()``)
        on such a not-yet-disclosed element was found to be flaky --
        returning a real, non-zero size on one Windows run and a zero-sized
        box on the very next Windows run of the same query, and a
        consistent zero-sized box on Ubuntu CI -- because it reads whatever
        stale/UA-internal layout box a browser happens to keep for hidden
        ``<details>`` content, which is not specified to be stable. Using
        ``Locator.is_visible()`` first (confirmed to return exactly
        ``False`` for this element in this closed state, deterministically,
        on both platforms) to decide whether to measure a control at all
        avoids depending on that unspecified, environment-dependent value
        for pass/fail, while a genuinely visible, undersized control is
        still measured and still fails here exactly as before -- this
        method is called again, later in the same test, once each
        disclosure (the re-proposal dialog, the account menu) is open and
        its own controls have become visible, so nothing here is
        permanently excluded from the gate, only deferred to the phase
        where it is actually activatable.
        """
        controls = self.page.locator("[data-candidate-control-purpose]")
        count = controls.count()
        self.assertGreater(
            count,
            0,
            f"no activatable controls with a declared purpose were found ({context_label})",
        )
        checked = 0
        for index in range(count):
            control = controls.nth(index)
            test_id = control.get_attribute("data-testid") or "(no testid)"
            if test_id in CONTROL_SIZE_ALLOWLIST_TEST_IDS:
                continue
            if not control.is_visible():
                continue
            checked += 1
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
        self.assertGreater(
            checked,
            0,
            f"no currently-visible activatable control was actually measured ({context_label})",
        )

    def test_e_activatable_controls_meet_44px_minimum_target(self) -> None:
        self._sign_in_with_candidates()
        for width, height, label in CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})

            # Default screen: cards, markers, filter-open, search-again.
            wait_for_at_least_one(self.page, "candidate-card")
            wait_for_at_least_one(self.page, "candidate-map-marker")
            self._assert_all_declared_controls_meet_44px(f"default screen at {label}")

            # Filter panel (clean): genre chips (plus overflow toggle, since
            # NORMAL_WITH_WEIGHTED_SAMPLING's synthetic population spans 5
            # non-excluded genres -- one more than genrePresentation's
            # 4-item preview -- and the izakaya/bar toggle, which now also
            # renders in this row, adr/0024 decision 2), the two remaining
            # soft-filter toggles, and the budget-tier options.
            by_test_id(self.page, "candidate-filter-open").click()
            wait_for_at_least_one(self.page, "candidate-filter-budget-tier-option")
            self._assert_all_declared_controls_meet_44px(f"filter panel (clean) at {label}")

            genre_overflow = by_test_id(self.page, "candidate-filter-genre-overflow")
            if genre_overflow.count() > 0:
                genre_overflow.first.click()
                self._assert_all_declared_controls_meet_44px(
                    f"filter panel (genre expanded) at {label}"
                )
                genre_overflow.first.click()

            # Filter panel (dirty): adds candidate-filter-revert/-apply.
            by_test_id(self.page, "candidate-filter-non-smoking-only").click()
            expect(by_test_id(self.page, "candidate-filter-apply")).to_be_attached()
            self._assert_all_declared_controls_meet_44px(f"filter panel (dirty) at {label}")
            by_test_id(self.page, "candidate-filter-revert").click()
            by_test_id(self.page, "candidate-filter-open").click()
            expect(by_test_id(self.page, "candidate-filter-panel")).to_have_count(0)

            # Account menu: toggle, sign-out, password-change-open.
            by_test_id(self.page, "auth-account-menu-toggle").click()
            expect(by_test_id(self.page, "auth-sign-out")).to_be_visible()
            self._assert_all_declared_controls_meet_44px(f"account menu open at {label}")
            by_test_id(self.page, "auth-account-menu-toggle").click()
