"""Machine-checked UI invariants against the real rendered candidate screen.

ADR-0020 decision 4 defines four Must, gate invariants -- (a) narrow-width map
reachability, (c) keyboard reachability/activation, (d) internal-enum
non-exposure, (e) 44px minimum activatable-control size -- as independent DOM/
geometry checks, deliberately not full-screen pixel comparison (decision 2,
decision 5; ``meta/adr/0021``/``meta/adr/0024`` are not superseded). ADR-0032
(2026-08-28) adds a fifth, (f) renderModes matches the tested viewport width,
to this same frozen set without editing ADR-0020 itself (ADR-0020 decision 2's
own "new ADR to add a gate" procedure). This file implements all five.

This is not a Gherkin/step/DSL translation of a business scenario (ADR-0020
decision 6, decision 9): it directly asserts the mechanical rules against
``contracts/candidate-search-browser-interface.yaml``'s own control surface.
It lives outside ``tests/acceptance/steps``/``dsl`` on purpose -- those are
the tester's domain (``developer.md``); this file, like ordinary
implementation code and unit tests, is maintained by developer.

It reuses the same JS-capable browser harness
(``StaticLiveServerTestCase`` + ``sync_playwright``) as
``tests/acceptance/test_candidate_search_acceptance.py`` (ADR-0020 decision 6
explicitly allows this), and reuses ``CandidateSearchBrowserDsl`` only for its
already-reviewed Given-seam setup and screen navigation (``reset_*``,
``enable_organizer``, ``sign_in``, ``set_candidate_state``,
``open_candidate_screen``) -- never for assertions, which are this file's own
and specific to ADR-0020 decision 4 / ADR-0032 decision 1, not to any TDR-CS
business scenario.

Floor changes: decision 4's four invariants plus ADR-0032's fifth (and the
(d)/(e)/(f) allowlists and viewport sets this file maintains) are each their
own ADR's initial baseline (ADR-0020 decision 2's "initial approval doubles
as baseline approval", which ADR-0032 decision 1 extends to (f)). Loosening
any of them, or adding a sixth gate invariant, needs a new ADR; the
allowlists/viewport sets themselves may be updated here, by developer, only
to track a contract change their own comments cite (decision 4(d),
decision 4(e), ADR-0032 decision 1/2 for (f)'s own TWO_COLUMN_VIEWPORTS).

``GatheringScreenInvariantTests`` below extends decision 4's (b)/(c)/(e) gate
set (this docstring's own (c)/(d)/(e) letters) to the 4 会の画面群 screens
(``contracts/gathering-scheduling-browser-interface.yaml``'s
``organizerGatheringList``/``organizerGatheringCreate``/``organizerDashboard``/
``participantAnswer``), closing the gap ``friction-log.md`` FR-035 recorded:
this file previously had no ``"gathering"`` string in it at all, so a real,
human-reported production defect (the participant footer's two buttons
collapsing well under 44px once the "あとで答える" confirmation text renders
as a third, un-sized flex sibling, ``participant.js``'s ``renderFooter``) had
no gate that could have caught it. (a) narrow-width map reachability is
deliberately not extended to any of the four screens -- see that class's own
docstring for the recorded rationale (decision 2's "no silent exclusion"
requirement). Given-state for these four screens is built only from
``test-support-api.yaml``'s own public seam
(``resetGatheringSchedulingAcceptanceState``) and
``gathering-scheduling-api.yaml``'s public operations, driven through each
screen's own real UI -- never through
``tests/acceptance/dsl/gathering_scheduling_browser.py`` or
``tests/acceptance/steps/gathering_scheduling_steps.py`` (outside developer's
role per ``developer.md``; reserved to tester by ADR-0020 decision 6, the
same boundary this file's own header paragraph above already states for the
candidate-search DSL).
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import Locator, expect, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.dsl.js_browser_mechanics import (
    by_test_id,
    csrf_token,
    is_candidate_proposal_request,
    is_candidate_proposal_response,
    wait_for_at_least_one,
)
from tests.support.business_days import next_business_weekday_iso, nth_business_day

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

# ADR-0032 decision1 (f): the two width sets renderModes' mode-correctness
# check runs against. adr/0033 decision6 (2026-08-29, human decision: mobile
# widths become map-primary too, paged by a swipe gesture instead of
# listPrimaryLayout's retired "地図で見る" ribbon/sheet) retired
# listPrimaryLayout and read the narrow-width member of this pair as
# mapPrimaryTouchLayout instead. adr/0049 decision4 (2026-09-08 human
# decision: "微妙。右に地図で一覧左とかじゃなかったっけ") in turn retires
# mapPrimaryLayout itself, replacing it with twoColumnLayout (a plain
# side-by-side list-and-map layout, no deck) -- adr/0032's own text is not
# edited by either revision (P-06), but this file's own allowlist below is
# the "developer-maintained" half of that decision (adr/0032 decision2), so
# it is what actually changes each time. mapPrimaryTouchLayout's own set
# reuses NARROW_VIEWPORTS outright (same reuse adr/0032 decision1 explicitly
# allowed for the narrow-width member originally: "決定4(a)が既に定める狭幅
# ビューポート集合をそのまま流用してよい" -- unaffected by either later
# revision, since neither changed the widths themselves, only which mode the
# narrow-width member expects). twoColumnLayout's own set is unchanged from
# mapPrimaryLayout's -- 1024px is home.html's own 64rem breakpoint's exact
# pixel boundary (the narrowest width twoColumnLayout must already hold at, a
# stronger check than only testing a comfortably-wide value like 1440px),
# plus 1440px (already CONTROL_SIZE_VIEWPORTS' own desktop width above, so
# this reuses a width already exercised elsewhere in this file rather than
# inventing a third).
TWO_COLUMN_VIEWPORTS = [
    (1024, 768, "two-column-boundary-1024x768"),
    (1440, 900, "two-column-1440x900"),
]

# mapPrimaryTouchLayout's (adr/0033 decision1) own exclusive testIds
# (contracts/candidate-search-browser-interface.yaml's renderModes section),
# duplicated here (not imported) since this file does not read the contract
# YAML directly -- same style as the other developer-maintained allowlists in
# this module (FORBIDDEN_INTERNAL_ENUM_TOKENS, CONTROL_SIZE_ALLOWLIST_TEST_IDS
# above). candidate-deck-position moved into this list by adr/0049 decision4
# (contractVersion 1.8.0): twoColumnLayout shows every card in one unpaged
# list, so it has no window for a position counter to describe any longer
# (unlike under adr/0033, where the counter was common to both named modes).
# twoColumnLayout's own testIds array is empty by contract design (it owns no
# exclusive test id of its own), so there is no TWO_COLUMN_TEST_IDS constant
# to check for presence -- only the absence of the touch-only ids below,
# mirroring tests/acceptance/dsl/candidate_search_browser.py's own
# assert_two_column_layout_holds (by-elimination reasoning).
RENDER_MODE_TOUCH_TEST_IDS = ["candidate-deck-swipe-surface", "candidate-deck-position"]

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

    def test_a_long_shop_name_does_not_push_the_card_past_its_own_column(self) -> None:
        """Regression coverage for a real-device report (2026-08-28).

        This is intentionally a presentation regression, not an additional
        ADR-0020 gate invariant (decision 4's four invariants are frozen;
        see this file's module docstring) -- same framing as
        ``test_long_regular_holiday_wraps_inside_a_narrow_card_without_
        truncation`` above, which this test mirrors closely.

        Root cause (activeContext.md): a CSS grid item's ``min-width``
        initial value is ``auto``, so [data-testid="candidate-proposal-
        cards"]'s own grid items (the cards) could never shrink below their
        content's min-content width -- a long, nowrap shop name (real
        provider data, e.g. "ドラゴンレッドリバー DRAGON RED RIVER") forced
        the card past its column, hiding the trailing walk-time chip under
        the map column. The local demo's own synthetic names
        (``合成母集団食堂 NN号店``) never exercised this because they were
        all short and near-identical in length -- this test injects one
        real-length name via route interception instead, so this file
        keeps proving the behaviour independently of whichever synthetic
        name acceptance_state.py happens to use today. Reproduced at both
        the exact widths orchestrator measured by hand: 1253px (desktop)
        and 442px (mobile, map-above-cards).

        adr/0031 (2026-08-28) had changed what "its own column" meant at
        1253px -- [data-testid="candidate-proposal-cards"] became the
        map-primary deck's own sliding row, holding every currently-loaded
        card side by side at a fixed width each, rather than a single,
        card-width column. adr/0049 decision4 (2026-09-08 human decision)
        retired that deck in favor of isTwoColumnLayout's plain
        .candidate-list-column, so 1253px (>=64rem) is a single-column list
        track again, the same shape 442px (<64rem, isMapPrimaryTouchLayout,
        unaffected by this revision) already was -- both widths below now
        share one assertion shape (card does not overflow its own track;
        chip stays visible within it; name still ellipsizes), unlike the
        deck-era version of this test, which branched on that geometry
        difference. Also re-navigates instead of resizing mid-test
        (isTwoColumnLayout is read once per render, not on a live resize --
        adr/0032 decision3; see
        test_e_activatable_controls_meet_44px_minimum_target's own comment
        for the same fix and the failure it reproduces without it).
        """
        long_name = "ドラゴンレッドリバー DRAGON RED RIVER 総本店（回帰テスト用）"

        def with_long_shop_name(route):
            response = route.fetch()
            body = response.json()
            body["candidates"][0]["name"] = long_name
            route.fulfill(response=response, json=body)

        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        self.page.route("**/candidate-proposals", with_long_shop_name)

        for width, height, label in ((1253, 900, "desktop-1253x900"), (442, 900, "mobile-442x900")):
            with self.subTest(viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                self.dsl.open_candidate_screen()

                name_node = by_test_id(self.page, "candidate-card-name").first
                expect(name_node).to_have_text(long_name)

                measurement = name_node.evaluate(
                    """node => {
                      const card = node.closest('[data-testid="candidate-card"]');
                      const track = card.closest('[data-testid="candidate-proposal-cards"]');
                      const chip = card.querySelector('.candidate-walk-chip');
                      const cardBox = card.getBoundingClientRect();
                      const trackBox = track.getBoundingClientRect();
                      const chipBox = chip.getBoundingClientRect();
                      return {
                        cardRight: cardBox.right,
                        cardWidth: cardBox.width,
                        trackRight: trackBox.right,
                        trackWidth: trackBox.width,
                        chipRight: chipBox.right,
                        chipWidth: chipBox.width,
                        nameTextOverflow: getComputedStyle(node).textOverflow,
                      };
                    }"""
                )

                self.assertEqual(measurement["nameTextOverflow"], "ellipsis")
                self.assertGreater(
                    measurement["chipWidth"],
                    0,
                    f"walk-time chip collapsed to zero width at {label}",
                )

                # Both widths are single-column list tracks now (mobile-
                # 442x900's mapPrimaryTouchLayout deck card fills its own
                # swipe-surface track at 100% width; desktop-1253x900's
                # isTwoColumnLayout card fills its own .candidate-list-column
                # track) -- see this test's own docstring for why this no
                # longer branches on width the way it did under the retired
                # PC deck.
                self.assertLessEqual(
                    measurement["cardRight"],
                    measurement["trackRight"] + 0.5,
                    f"card overflows its own column at {label} -- the long name pushed "
                    "the card past the track, the exact regression the human reported",
                )
                self.assertAlmostEqual(
                    measurement["cardWidth"],
                    measurement["trackWidth"],
                    delta=0.5,
                    msg=f"card width diverged from its column's own width at {label}",
                )
                self.assertLessEqual(
                    measurement["chipRight"],
                    measurement["trackRight"] + 0.5,
                    f"walk-time chip is hidden under the map column at {label}",
                )

    # (a) Narrow-width map reachability ------------------------------------

    def test_a_map_is_reachable_without_scrolling_at_narrow_widths(self) -> None:
        """adr/0049 decision4 (2026-09-08 human decision) made isTwoColumnLayout
        structurally different from isMapPrimaryTouchLayout at the outer
        .candidate-main-layout level for the first time (a separate
        .candidate-list-column sibling before the map, rather than a deck
        overlaid on top of it) -- unlike every render-mode difference before
        it, which only changed the deck's own paging affordance inside the
        same map-primary skeleton at every width. This file's own default
        page (opened once by _sign_in_with_candidates, at whatever viewport
        the browser context started with -- 1280x720, i.e. isTwoColumnLayout)
        used to remain a valid DOM shape for every subsequently *resized*
        narrow width too, since resizing alone never changed which JS-built
        structure was already on the page and CSS alone repositioned it
        correctly either way. That is no longer true: resizing down from a
        two-column render leaves .candidate-list-column's full card stack as
        a sibling that renders *above* the map at these narrow widths (which
        have no styling of their own for that class), pushing it far down
        the page -- reproduced directly: candidate-map's top measured
        1463.77px at 730x900 without this fix, failing this exact assertion.
        Each width now gets its own fresh navigation instead (self.dsl.
        open_candidate_screen, after setting the viewport, not before), the
        same fresh-render discipline test_e/test_f already established for
        the identical reason (isMapPrimaryLayout/isTwoColumnLayout read once
        per render, never on a live resize -- adr/0032 decision3's own
        explicit carve-out, which this test's original resize-only shape
        predates and did not yet need to account for).
        """
        self._sign_in_with_candidates()
        map_node = by_test_id(self.page, "candidate-map")
        for width, height, label in NARROW_VIEWPORTS:
            with self.subTest(viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                self.dsl.open_candidate_screen()
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

    def _account_disclosure_toggle(self) -> tuple[Locator, str]:
        """Render-mode-correct account entry point: mobile's
        candidate-primary-nav-account, else desktop's candidate-primary-nav-menu-toggle."""
        mobile_account = by_test_id(self.page, "candidate-primary-nav-account")
        if mobile_account.count() > 0:
            return mobile_account, "mapPrimaryTouchLayout"
        return by_test_id(self.page, "candidate-primary-nav-menu-toggle"), "twoColumnLayout"

    def test_c_account_menu_toggle_and_password_change_link_are_keyboard_operable(self) -> None:
        """Opens the render-mode-correct account entry point at each width before
        measuring what it discloses."""
        for width, height, label in (NARROW_VIEWPORTS[0], TWO_COLUMN_VIEWPORTS[1]):
            with self.subTest(viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                self._sign_in_with_candidates()
                toggle, mode = self._account_disclosure_toggle()
                self._assert_tabbable(toggle, f"account disclosure toggle ({mode}, {label})")
                # Present but hidden while closed, not absent.
                expect(by_test_id(self.page, "auth-password-change-open")).to_be_hidden()

                toggle.press("Enter")
                password_change = by_test_id(self.page, "auth-password-change-open")
                expect(password_change).to_be_visible()
                self._assert_tabbable(
                    password_change, f"auth-password-change-open ({mode}, {label})"
                )
                expected_path = reverse("authentication:password_change")
                password_change.press("Enter")
                expect(self.page).to_have_url(f"{self.dsl.base_url}{expected_path}")

    def test_c_sign_out_is_keyboard_operable(self) -> None:
        """Opens the render-mode-correct account entry point at each width
        before reaching sign-out."""
        for width, height, label in (NARROW_VIEWPORTS[0], TWO_COLUMN_VIEWPORTS[1]):
            with self.subTest(viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                self._sign_in_with_candidates()
                toggle, mode = self._account_disclosure_toggle()
                toggle.click()
                sign_out = by_test_id(self.page, "auth-sign-out")
                self._assert_tabbable(sign_out, f"auth-sign-out ({mode}, {label})")
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
        # adr/0031/0032/0049: isTwoColumnLayout (renamed from
        # isMapPrimaryLayout, renderModes.twoColumnLayout) is read once per
        # render, not on a live resize (adr/0032 decision3) -- unlike this
        # test's own pre-adr/0031 shape (a single sign-in/render, then
        # set_viewport_size alone across all three widths), each width
        # below now gets its own fresh navigation
        # (self.dsl.open_candidate_screen, after setting the viewport, not
        # before) so the DOM this test measures at each width actually
        # matches that width's own render mode -- the same fresh-render
        # discipline the (f) gate below applies for the identical reason.
        # A live-resize-without-reload run against this same code left a
        # map-primary-only candidate-deck-previous behind at 390px (CSS no
        # longer sizing it, since @media (min-width:64rem) had stopped
        # matching, while the JS-built DOM had not rebuilt to remove it) --
        # confirmed by reproducing that exact failure before this fix.
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        for width, height, label in CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self.dsl.open_candidate_screen()

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

            # Account menu: toggle, sign-out, password-change-open. Does not
            # re-click the toggle to close it -- the disclosed sheet covers
            # its own trigger, and the next iteration re-navigates anyway.
            account_toggle, _account_mode = self._account_disclosure_toggle()
            account_toggle.click()
            expect(by_test_id(self.page, "auth-sign-out")).to_be_visible()
            self._assert_all_declared_controls_meet_44px(f"account menu open at {label}")

    # (f) renderModes selects the correct mode at each tested width --------

    def test_f_render_mode_matches_viewport_width_on_independent_page_loads(self) -> None:
        """ADR-0032 decision1's fifth gate invariant.

        contracts/candidate-search-browser-interface.yaml's renderModes
        section (adr/0033 decision1, adr/0049 decision4) fixes only that
        exactly one of twoColumnLayout/mapPrimaryTouchLayout holds at a
        time and which testIds belong to each -- not the width threshold,
        which renderModes.verificationAllocation.L5 explicitly assigns to
        this ADR-0020 decision4 gate set instead (adr/0032 decision2: the
        width value lives in this test, not the contract). Each width below
        is checked via its own fresh navigation (self.dsl.
        open_candidate_screen calls page.goto internally) rather than a live
        self.page.set_viewport_size-then-assert -- ADR-0032 decision3
        deliberately does not require candidate.js to switch modes without a
        re-render, so a resize-only check would not be testing what this
        gate actually guarantees.

        adr/0033 decision6 (human decision 2026-08-29): the narrow-width
        member of this pair expects mapPrimaryTouchLayout, not the retired
        listPrimaryLayout. adr/0049 decision4 (2026-09-08 human decision:
        "微妙。右に地図で一覧左とかじゃなかったっけ") in turn retires the
        wide-width member's own mapPrimaryLayout (a button-paged deck) in
        favor of twoColumnLayout (a plain side-by-side list-and-map layout
        with no deck at all, and so no exclusive test id of its own --
        renderModes.twoColumnLayout.testIds is empty by contract design).
        Neither revision edits adr/0032's own text (P-06); only this test's
        own developer-maintained allowlists (module-level
        RENDER_MODE_TOUCH_TEST_IDS, TWO_COLUMN_VIEWPORTS) changed to track
        them. candidate-deck-position moved into RENDER_MODE_TOUCH_TEST_IDS
        by adr/0049 decision4 -- it is no longer common to both named modes
        the way it was under adr/0033, since a plain, unpaged list has no
        window for a position counter to describe.
        """
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")

        for width, height, label in NARROW_VIEWPORTS:
            with self.subTest(mode="mapPrimaryTouchLayout", viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                self.dsl.open_candidate_screen()
                for test_id in RENDER_MODE_TOUCH_TEST_IDS:
                    expect(by_test_id(self.page, test_id)).to_have_count(1, timeout=10_000)

        for width, height, label in TWO_COLUMN_VIEWPORTS:
            with self.subTest(mode="twoColumnLayout", viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                self.dsl.open_candidate_screen()
                for test_id in RENDER_MODE_TOUCH_TEST_IDS:
                    expect(by_test_id(self.page, test_id)).to_have_count(0)

    # --- gatheringMode band / persistent primary nav (2026-09-13 integration
    # round, friction-log.md FR-035's own recurrence: the organizer-facing
    # gathering screens' new controls got this file's coverage extended for
    # them (GatheringScreenInvariantTests.
    # test_gathering_screens_persistent_primary_nav_meets_44px_and_is_
    # keyboard_operable below); this screen's own new controls -- the
    # gatheringMode band (candidate-search-browser-interface.yaml 1.9.0,
    # ADR-0054 decision 4) and its own copy of the two-location persistent
    # nav (ADR-0054 decision 1) -- never got the same extension until now.
    # ------------------------------------------------------------------

    def _next_monday_iso(self) -> str:
        """Date-stable weekday pin for _create_selecting_shop_gathering_via_
        api below -- mirrors tests/acceptance/dsl/candidate_search_browser.
        py's own next_weekday_iso(0) intent (Monday, OPEN_SHOP_COUNT_BY_
        WEEKDAY[0] == 5 under GATHERING_OPEN_SHOP_WEEKDAY_MATCH, already
        relied on at L4 for the identical determinism reason).

        **Fixed (ADR-0060 decision 4, 2026-09-18)**: the former body picked
        the next Monday by calendar weekday alone, with no check against
        ``CANDIDATE_DATE_NOT_A_BUSINESS_DAY`` (holidays.is_business_day) --
        a "happy Monday" national holiday (成人の日/海の日/敬老の日/スポーツ
        の日) makes that Monday not a business day, and this suite's own
        gathering-create call would then be rejected with 400 depending on
        what day it happens to run (e.g. 2026-09-21, 敬老の日). Delegates to
        ``tests.support.business_days.next_business_weekday_iso`` (this
        project's one shared "N-th business day"/"next business weekday"
        fixture-date builder, also used by tests/test_candidate_search.py
        and tests/test_gathering.py) instead of re-deriving the same
        business-day check locally a third time.
        """
        return next_business_weekday_iso(0)

    def _create_selecting_shop_gathering_via_api(
        self, title: str, candidate_date_iso: str | None = None
    ) -> str:
        """Raw-HTTP Given-state builder (mirrors GatheringScreenInvariantTests.
        _seed_one_shortlisted_shop's own precedent of calling public
        gathering-scheduling-api.yaml operations directly via
        self.context.request rather than tests/acceptance/dsl/
        gathering_scheduling_browser.py, which is reserved to tester per
        ADR-0020 decision 6, the same boundary this file's own module
        docstring states). Creates one candidate date and immediately
        confirms it, reaching SELECTING_SHOP -- the phase gatheringMode.band
        requires (candidate-search-browser-interface.yaml gatheringMode.
        band's own gating condition is response.gatheringContext non-null,
        which candidate-proposals only returns once a gatheringId names a
        gathering past SCHEDULING). ``self.page`` must already be on an
        organizer-authenticated page carrying the hidden CSRF field (the
        candidate screen itself, reached via sign_in, satisfies this --
        home.html's own auth-account-menu-toggle sits behind the same
        hidden token organizer_dashboard.html's
        `<div hidden>{% csrf_token %}</div>` exposes).

        **Fixed (date-rollover flake, 2026-09-17)**: previously hardcoded
        "+3 days" with no caller-chosen weekday -- which weekday that lands
        on drifts with the calendar date this suite happens to run on, and
        the candidate population this screen shows for the confirmed date
        is not guaranteed non-empty for every weekday under every mode this
        file's own callers set (mirrors tests/acceptance/test_candidate_
        search_acceptance.py's own identical "Fixed (date-rollover flake)"
        note for TDR-CS-17/20, reproduced empirically here the same way:
        this method's callers passed while "today" was 2026-09-16 and
        failed once the date rolled to 2026-09-17). ``candidate_date_iso``
        lets a caller pin a date-stable weekday instead (mirrors
        tests/acceptance/dsl/candidate_search_browser.py's own
        next_weekday_iso-based callers); a business-day-only default is kept
        only for a caller that does not care.

        **Fixed (ADR-0060 decision 4, 2026-09-18)**: the former "+3 days"
        default (no weekday pinned) had the same
        ``CANDIDATE_DATE_NOT_A_BUSINESS_DAY`` exposure ``_next_monday_iso``
        above did -- unexercised by this file's own two current callers
        (both pass ``candidate_date_iso``), but still a candidate-date
        construction site that would fail depending on what day this suite
        runs, so it is routed through the same shared
        ``nth_business_day`` this module's other business-day fixture
        builders use rather than left as a live latent flake.
        """
        token = csrf_token(self.page)
        start_at = (
            datetime.fromisoformat(candidate_date_iso)
            if candidate_date_iso is not None
            else datetime.combine(nth_business_day(3), datetime.min.time())
        ).strftime("%Y-%m-%dT12:00:00Z")
        create_response = self.context.request.post(
            f"{self.dsl.base_url}/gatherings",
            data={"title": title, "candidateDates": [{"startAt": start_at}]},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(create_response.status, 201, create_response.text())
        gathering = create_response.json()
        candidate_date_id = gathering["candidateDates"][0]["id"]
        confirm_response = self.context.request.post(
            f"{self.dsl.base_url}/gatherings/{gathering['id']}/confirm-date",
            data={"candidateDateId": candidate_date_id},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(confirm_response.status, 200, confirm_response.text())
        return gathering["id"]

    def test_gathering_mode_band_is_no_longer_a_navigation_control(self) -> None:
        """ADR-0059 decision 5 (2026-09-16, 束A「会への戻り道」) retires
        candidate-gathering-mode-band's prior navigation role (ADR-0054
        decision 4: "帯自体が戻る動線を兼ねる") -- gatheringMode.band.
        navigationNote now states activating it "is no longer a recognized
        input and produces no navigation and no public operation; it is a
        pure status line". A regression that silently left the band's own
        prior click/Enter handler wired would pass an absence-only check
        (band itself still exists, just with a different role) -- this
        proves the no-op directly, mirroring tests/acceptance/dsl/
        candidate_search_browser.py's own assert_origin_marker_and_rings_
        are_display_only "activate, then assert nothing changed" style for
        a different always-present, non-interactive element.
        """
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state("GATHERING_OPEN_SHOP_WEEKDAY_MATCH")
        self.dsl.open_candidate_screen()
        gathering_id = self._create_selecting_shop_gathering_via_api(
            "会UI不変量の確認会", self._next_monday_iso()
        )

        self.page.goto(f"{self.dsl.base_url}/?gatheringId={gathering_id}")
        band = by_test_id(self.page, "candidate-gathering-mode-band")
        expect(band).to_be_visible()
        band_box = band.bounding_box()
        self.assertIsNotNone(band_box, "band has no bounding box")
        self.assertGreaterEqual(band_box["width"], MINIMUM_TARGET_PX)
        self.assertGreaterEqual(band_box["height"], MINIMUM_TARGET_PX)

        url_before = self.page.url
        band.dispatch_event("click")
        self.page.wait_for_timeout(300)
        self.assertEqual(self.page.url, url_before, "band navigated on click")
        if band.get_attribute("tabindex") is not None:
            band.focus()
            band.press("Enter")
            self.page.wait_for_timeout(300)
            self.assertEqual(self.page.url, url_before, "band navigated on Enter")
            band.press("Space")
            self.page.wait_for_timeout(300)
            self.assertEqual(self.page.url, url_before, "band navigated on Space")

    def test_gathering_mode_primary_nav_and_shortlist_toast_meet_44px_and_are_keyboard_operable(
        self,
    ) -> None:
        """ADR-0059 (2026-09-16, 束A「上部ナビと会への戻り道」) replaces this
        screen's prior render-mode-independent nav pair (ADR-0054 decision
        1: "ランチ候補をさがす"/"ランチ会") with a render-mode-specific
        design: candidate-primary-nav-bar (mobileBarSearch/-Gathering/
        -Account, unconditional under mapPrimaryTouchLayout) and candidate-
        primary-nav-menu-toggle -> -menu-panel (menuDestinationSearch/
        -Gathering + the existing account controls, unconditional under
        twoColumnLayout) -- both unconditional on this screen while in
        gathering mode too, since it is not one of gathering-scheduling-
        browser-interface.yaml's own three organizer-facing screens
        (gatheringEntry.mobileBar/menuToggle requirement paragraphs).
        candidate-gathering-entry (the chip) is unlike those two: it stays
        present here (unlike on the three organizer screens,
        GatheringScreenInvariantTests' own sibling test below), since
        entry.requirement's own exclusion only names those three screens,
        not gatheringMode. None of the new elements below carry
        data-candidate-control-purpose (plain navigation elements, per this
        contract's existing gatheringEntry.entry precedent), so none is
        caught by test_e_activatable_controls_meet_44px_minimum_target's
        purpose-based scan above -- this test measures each directly.
        gatheringMode.shortlistToast.returnControl is opened by actually
        adding a shop (FR-013: a closed disclosure's own descendants render
        an unreliable bounding box under this project's CI browser -- open
        it before measuring what it discloses, mirroring
        test_c_account_menu_toggle_and_password_change_link_are_keyboard_
        operable's identical precedent above).
        """
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state("GATHERING_OPEN_SHOP_WEEKDAY_MATCH")
        self.dsl.open_candidate_screen()
        gathering_id = self._create_selecting_shop_gathering_via_api(
            "会UI不変量ナビの確認会", self._next_monday_iso()
        )

        def _assert_44px_and_tabbable(locator, label: str) -> None:
            expect(locator).to_be_visible()
            self._assert_tabbable(locator, label)
            box = locator.bounding_box()
            self.assertIsNotNone(box, f"{label} has no bounding box")
            self.assertGreaterEqual(box["width"], MINIMUM_TARGET_PX, label)
            self.assertGreaterEqual(box["height"], MINIMUM_TARGET_PX, label)

        # --- mobile bottom nav (mapPrimaryTouchLayout, adr/0033 decision 1) ---
        mobile_width, mobile_height, mobile_label = NARROW_VIEWPORTS[0]
        self.page.set_viewport_size({"width": mobile_width, "height": mobile_height})
        self.page.goto(f"{self.dsl.base_url}/?gatheringId={gathering_id}")
        for test_id in (
            "candidate-primary-nav-search",
            "candidate-primary-nav-gathering",
            "candidate-primary-nav-account",
        ):
            with self.subTest(check="mobile-nav", test_id=test_id):
                _assert_44px_and_tabbable(
                    by_test_id(self.page, test_id), f"{test_id} ({mobile_label})"
                )
        gathering_item = by_test_id(self.page, "candidate-primary-nav-gathering")
        self.assertNotEqual(
            (gathering_item.inner_text() or "").strip(),
            "",
            f"candidate-primary-nav-gathering label text empty ({mobile_label})",
        )
        expect(by_test_id(self.page, "candidate-gathering-entry")).to_have_count(0)

        # --- desktop chip + menu (twoColumnLayout, adr/0049 decision 4) ---
        desktop_width, desktop_height, desktop_label = TWO_COLUMN_VIEWPORTS[1]
        self.page.set_viewport_size({"width": desktop_width, "height": desktop_height})
        self.page.goto(f"{self.dsl.base_url}/?gatheringId={gathering_id}")
        chip = by_test_id(self.page, "candidate-gathering-entry")
        _assert_44px_and_tabbable(chip, f"candidate-gathering-entry ({desktop_label})")
        self.assertNotEqual(
            (chip.inner_text() or "").strip(),
            "",
            f"candidate-gathering-entry label text empty ({desktop_label})",
        )

        toggle = by_test_id(self.page, "candidate-primary-nav-menu-toggle")
        _assert_44px_and_tabbable(toggle, f"candidate-primary-nav-menu-toggle ({desktop_label})")
        toggle.press("Enter")
        panel = by_test_id(self.page, "candidate-primary-nav-menu-panel")
        expect(panel).to_be_visible()
        menu_panel_test_ids = (
            "candidate-primary-nav-menu-search",
            "candidate-primary-nav-menu-gathering",
        )
        for test_id in menu_panel_test_ids:
            with self.subTest(check="menu-panel", test_id=test_id):
                _assert_44px_and_tabbable(
                    by_test_id(self.page, test_id), f"{test_id} ({desktop_label})"
                )

        # --- gatheringMode.shortlistToast.returnControl (ADR-0059 decision 5) ---
        self.page.goto(f"{self.dsl.base_url}/?gatheringId={gathering_id}")
        cards = wait_for_at_least_one(self.page, "candidate-card")
        cards.first.locator('[data-testid="candidate-card-gathering-toggle"]').click()
        toast_return = by_test_id(self.page, "candidate-gathering-shortlist-toast-return")
        _assert_44px_and_tabbable(toast_return, "candidate-gathering-shortlist-toast-return")


# ---------------------------------------------------------------------------
# 会の画面群 (organizerGatheringList / organizerGatheringCreate /
# organizerDashboard / participantAnswer) -- see this file's own module
# docstring for why this exists (friction-log.md FR-035) and the scope this
# extension covers.

GATHERING_ORGANIZER_ACCOUNT_REF = "gth-ui-invariants-org"
GATHERING_ORGANIZER_IDENTIFIER = "synthetic-ui-invariants-gathering-organizer"
GATHERING_ORGANIZER_PASSWORD = "synthetic-ui-invariants-gathering-secret"

# None of the four gathering screens define a renderModes-style
# width-dependent layout switch the way candidate-search does (no (f)
# equivalent is needed here for the same reason) -- two widths are enough: a
# common phone width (also used elsewhere in this file) and a comfortable
# desktop width. The participant footer bug this round's primary target
# (test_e_participant_answer_footer_controls_meet_44px_minimum_target below)
# in fact reproduces at both, since participant_answer.html's own
# ``.app-shell`` caps its width at ``min(100% - 2rem, 26rem)`` regardless of
# viewport width.
GATHERING_CONTROL_SIZE_VIEWPORTS = [
    (390, 844, "phone-390x844"),
    (1440, 900, "desktop-1440x900"),
]

# unavailableControls.allowedPurposes' own exception list
# (candidate-search-browser-interface.yaml's CONTROL_SIZE_ALLOWLIST_TEST_IDS
# equivalent) has no counterpart yet in
# gathering-scheduling-browser-interface.yaml -- no human-confirmed
# in-sentence-link exception exists for any gathering screen. Starts empty
# rather than omitted, the same "no silent exclusion" spirit decision 4(e)
# requires -- kept as its own named constant so a future exception is added
# here, not skipped ad hoc.
GATHERING_CONTROL_SIZE_ALLOWLIST_TEST_IDS: set[str] = set()

# ADR-0020 decision 4(d)'s enum-non-exposure check, extended to
# gathering-scheduling-api.yaml's own enums: Gathering.phase /
# ParticipantView.phase, ScheduleResponseStatus (plus the synthetic
# "UNANSWERED" sentinel every yourResponse/yourVote uses when null),
# ShopVoteStatus, and ProblemResponse's four recognized link-error codes.
# gathering.js/gathering_list.js/participant.js already translate every one
# of these to a Japanese label before rendering (PHASE_LABELS/
# RESPONSE_LABELS/VOTE_LABELS) -- this is a regression gate on that existing
# behaviour, not a new requirement (gathering.js's own PHASE_LABELS comment
# already invokes "ADR-0020 decision 4(d)'s spirit" by name).
GATHERING_FORBIDDEN_INTERNAL_ENUM_TOKENS = [
    # Gathering.phase / ParticipantView.phase
    "SCHEDULING",
    "SELECTING_SHOP",
    "FINALIZED",
    # ScheduleResponseStatus / yourResponse sentinel
    "GOING",
    "MAYBE",
    "NOT_GOING",
    "UNANSWERED",
    # ShopVoteStatus (NOT_GOING already listed above)
    "WANT_TO_GO",
    "OK_TO_GO",
    # ProblemResponse.code (gathering-participant-link-error)
    "LINK_NOT_FOUND",
    "LINK_EXPIRED",
    "LINK_REVOKED",
    "LINK_RATE_LIMITED",
]


class GatheringScreenInvariantTests(StaticLiveServerTestCase):
    """ADR-0020 decision 4's (b)/(c)/(e) gate, extended to the 4 gathering
    screens (``contracts/gathering-scheduling-browser-interface.yaml``).

    (a) narrow-width primary-content (map) reachability is intentionally
    **not** extended to any of these four screens, with the rationale
    recorded here rather than silently omitted (decision 2's "no silent
    exclusion" requirement):

    - ``organizerGatheringList``/``organizerGatheringCreate``/
      ``organizerDashboard`` define no map element at all
      (``gathering-scheduling-browser-interface.yaml``'s own
      ``forbiddenTestIdsNote``: ``organizerDashboard.shortlistSelection``'s
      own map was retired 2026-09-09, adr/0049 decision 1 -- shop-detail/map
      observation now lives entirely in
      ``candidate-search-browser-interface.yaml``'s ``gatheringMode``, a
      screen outside this file's four-screen scope).
    - ``participantAnswer`` does define its own map
      (``gathering-shop-vote-map``), but only once shop voting has started,
      and even then it renders as one secondary block partway down an
      ordinarily scrolling wizard page (``participant.js``'s ``render()``:
      header, schedule questions, the vote section, a next-steps panel, the
      footer, then fine print) -- unlike candidate-search's map, which
      decision 4(a) was written against and which *is* that screen's entire
      primary content. Gating "the map must be reachable without scrolling"
      here would fail against perfectly ordinary, correct scrolling on a
      long schedule, not against a real defect.

    Given-state is built only from ``test-support-api.yaml``'s own public
    seam (``resetGatheringSchedulingAcceptanceState``) and
    ``gathering-scheduling-api.yaml``'s public operations, driven through
    each screen's own real UI (fill/click) -- never through
    ``tests/acceptance/dsl/gathering_scheduling_browser.py`` or
    ``tests/acceptance/steps/gathering_scheduling_steps.py`` (outside
    developer's role, ADR-0020 decision 6 reserves step/DSL authorship to
    tester). ``CandidateSearchBrowserDsl`` is reused here only for its
    already-reviewed authentication seam (``reset_authentication_state``/
    ``enable_organizer``/``sign_in``) -- the same ``organizerSession`` every
    TDR-* screen shares (``gathering-scheduling-browser-interface.yaml``'s
    own ``browserEntry`` notes) -- exactly as
    ``RenderedScreenInvariantTests`` above already does for the same
    reason; it is never asked about candidate-search state and never used
    for a gathering assertion.
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
        self.base_url = os.environ["TDR_ACCEPTANCE_BASE_URL"]
        self.context = self._browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dsl = CandidateSearchBrowserDsl(self, self.page, self.base_url)

    # --- Given-state helpers (public seam + public API, driven through
    # each screen's own UI; see class docstring) ---------------------------

    def _reset_gathering_state(self) -> None:
        """``resetGatheringSchedulingAcceptanceState``
        (``test-support-api.yaml``, ``DELETE /test-support/gathering-scheduling-state``).
        """
        response = self.context.request.delete(
            f"{self.base_url}/test-support/gathering-scheduling-state"
        )
        self.assertEqual(response.status, 204, response.text())

    def _sign_in_as_organizer(self) -> None:
        self.dsl.reset_authentication_state()
        self._reset_gathering_state()
        self.dsl.enable_organizer(
            GATHERING_ORGANIZER_ACCOUNT_REF,
            GATHERING_ORGANIZER_IDENTIFIER,
            GATHERING_ORGANIZER_PASSWORD,
        )
        self.dsl.sign_in(GATHERING_ORGANIZER_IDENTIFIER, GATHERING_ORGANIZER_PASSWORD)

    def _select_calendar_days(
        self, page, day_test_id: str, month_next_test_id: str, count: int
    ) -> None:
        """Selects ``count`` enabled day cells, pressing the calendar's own
        month-next control if the currently-shown month does not have
        enough of them (ADR-0054 decision 3: this calendar shows a single
        month at a time, not the 3 simultaneous months the retired vendored
        library used to render -- FR-033's own conclusion is that a test
        needing more days than one month offers presses month-navigation
        itself, rather than the product defaulting to a wider view to make a
        test convenient). Bounded to a handful of month-next presses so a
        genuine regression fails fast instead of hanging.
        """
        selected = 0
        for _ in range(6):
            enabled_day_cells = page.locator(
                f'[data-testid="{day_test_id}"][data-gathering-control-purpose]'
            )
            available = enabled_day_cells.count()
            while selected < count and selected < available:
                enabled_day_cells.nth(selected).click()
                selected += 1
            if selected >= count:
                return
            by_test_id(page, month_next_test_id).click()
        raise AssertionError(f"could not select {count} candidate day(s) within 6 months")

    def _select_first_unselected_calendar_day(
        self, page, day_test_id: str, month_next_test_id: str, excluded_isos: set[str]
    ):
        """Returns (and clicks) the first enabled day cell whose ``data-date``
        is not in ``excluded_isos``, pressing month-next if the currently
        shown month has none (same single-month-calendar reasoning as
        ``_select_calendar_days`` above)."""
        for _ in range(6):
            enabled_day_cells = page.locator(
                f'[data-testid="{day_test_id}"][data-gathering-control-purpose]'
            )
            for index in range(enabled_day_cells.count()):
                candidate = enabled_day_cells.nth(index)
                if candidate.get_attribute("data-date") not in excluded_isos:
                    candidate.click()
                    return candidate
            by_test_id(page, month_next_test_id).click()
        raise AssertionError("could not find an unselected candidate day within 6 months")

    def _first_enabled_day_cell(self, page, day_test_id: str, month_next_test_id: str):
        """Returns the calendar's own first enabled day cell, pressing
        month-next first if the currently shown month happens to have none
        (the one-in-~30 edge case where "today" is a month's last day, so
        every enabled day already falls in the next month -- ADR-0054
        decision 3's single-month calendar makes this newly reachable; the
        retired, 3-simultaneous-month vendored calendar never hit it)."""
        for _ in range(2):
            enabled_day_cells = page.locator(
                f'[data-testid="{day_test_id}"][data-gathering-control-purpose]'
            )
            if enabled_day_cells.count() > 0:
                return enabled_day_cells.first
            by_test_id(page, month_next_test_id).click()
        return page.locator(f'[data-testid="{day_test_id}"][data-gathering-control-purpose]').first

    def _find_weekend_or_holiday_disabled_cell(
        self, page, day_test_id: str, month_next_test_id: str
    ):
        """A day cell disabled for a reason other than being today/past
        (ADR-0060 decision 1/2: a Saturday, Sunday, or Japan public holiday).
        Identified *relative to the calendar's own currently-enabled cells*,
        not by this file independently computing "today" or a holiday
        calendar (tester does not read implementation, and this file
        otherwise never computes dates itself either): 明日以降のみ
        (adr/0049 decision 3) only disables a contiguous run starting at the
        calendar's first visible day, so any disabled cell whose data-date
        sorts *after* the earliest enabled cell's data-date cannot be a
        past/today disablement -- it must be a weekend or public holiday.
        """
        for _ in range(6):
            all_cells = page.locator(f'[data-testid="{day_test_id}"]')
            count = all_cells.count()
            enabled_dates = sorted(
                date
                for index in range(count)
                if (date := all_cells.nth(index).get_attribute("data-date")) is not None
                and all_cells.nth(index).get_attribute("data-gathering-control-purpose") is not None
            )
            if enabled_dates:
                earliest_enabled = enabled_dates[0]
                for index in range(count):
                    cell = all_cells.nth(index)
                    if cell.get_attribute("data-gathering-control-purpose") is not None:
                        continue
                    cell_date = cell.get_attribute("data-date")
                    if cell_date is not None and cell_date > earliest_enabled:
                        return cell
            by_test_id(page, month_next_test_id).click()
        raise AssertionError(
            f"could not find a weekend/holiday-disabled {day_test_id} cell within 6 months"
        )

    def _create_gathering_via_ui(self, title: str, candidate_date_count: int = 1) -> str:
        """``createGathering`` (``gathering-scheduling-api.yaml``), driven
        through ``organizerGatheringCreate``'s own real UI. Leaves
        ``self.page`` on the newly created gathering's ``organizerDashboard``
        (``gathering_create.js``'s own post-submit navigation) and returns
        its ``gatheringId``.

        Waits past the URL change to the dashboard's own post-fetch render
        before returning: ``gathering_create.js``'s redirect changes the URL
        as soon as navigation is committed, but ``gathering.js`` still has to
        fetch this gathering and render it client-side afterwards
        (``loadGathering``'s own ``requestJson(...).then(render)``), so a
        caller that queries the dashboard's controls immediately after this
        method returns can otherwise race that render. ``gathering-candidate-date``
        is the element to wait for -- ``gathering-scheduling-browser-
        interface.yaml``'s ``organizerDashboard.candidateDateList.candidateDate``
        is "present unconditionally across all three phases", and a freshly
        created gathering is always still SCHEDULING, where this same
        element's ``tentativeSelectionAndPreview.trigger`` entry declares its
        ``data-gathering-control-purpose`` activatable -- exactly the
        attribute callers of this method scan for (e.g.
        ``_assert_all_declared_gathering_controls_meet_44px``).

        **Rewritten 2026-09-16 (ADR-0060 decision 5)**: "つくる" no longer
        creates the gathering directly -- gathering-create-review-open now
        opens gathering-create-review-dialog, whose own gathering-create-
        submit (same test id/purpose, moved DOM home) is what actually
        calls createGathering. Every other caller of this shared helper is
        unaffected by this change (they only observe its return value/the
        resulting dashboard).
        """
        self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
        by_test_id(self.page, "gathering-create-name-input").fill(title)
        day_cells = self.page.locator(
            '[data-testid="gathering-create-candidate-date-day"][data-gathering-control-purpose]'
        )
        expect(day_cells.first).to_be_visible()
        self._select_calendar_days(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
            candidate_date_count,
        )
        by_test_id(self.page, "gathering-create-review-open").click()
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
        by_test_id(self.page, "gathering-create-submit").click()
        expect(self.page).to_have_url(re.compile(r"/gatherings/[0-9a-fA-F-]+/$"))
        match = re.search(r"/gatherings/([0-9a-fA-F-]+)/", self.page.url)
        assert match is not None, self.page.url
        expect(by_test_id(self.page, "gathering-candidate-date").first).to_be_visible()
        return match.group(1)

    def _issue_participant_link_url(self) -> str:
        """``issueParticipantLinks``, driven through
        ``organizerDashboard.participantLinkCopy``. ``self.page`` must
        already be on that gathering's ``organizerDashboard``.

        ADR-0061 decision 1 (2026-09-17): activation no longer carries
        ``data-issued-link-url`` on the button itself -- it now opens
        ``issueDialog``, which carries that attribute instead. Closes the
        dialog afterwards so callers land on an ordinary dashboard, not one
        with a dialog left open.
        """
        by_test_id(self.page, "gathering-participant-link-copy").click()
        dialog = by_test_id(self.page, "gathering-participant-link-issue-dialog")
        expect(dialog).to_have_attribute("data-issued-link-url", re.compile(r"^http"))
        url = dialog.get_attribute("data-issued-link-url")
        assert url is not None
        by_test_id(self.page, "gathering-participant-link-issue-dialog-close").click()
        expect(dialog).to_have_count(0)
        return url

    def _open_participant_view(self, url: str, viewport: tuple[int, int] | None = None):
        """Opens a signed participant link in its own browser context -- no
        ``organizerSession`` cookie, mirroring
        ``browserEntry.participantAnswer``'s own note that the token alone
        is the credential; no session is required or accepted.
        """
        context_kwargs = {}
        if viewport is not None:
            context_kwargs["viewport"] = {"width": viewport[0], "height": viewport[1]}
        context = self._browser.new_context(**context_kwargs)
        self.addCleanup(context.close)
        page = context.new_page()
        page.goto(url)
        return page

    def _build_participant_link(self, candidate_date_count: int = 1) -> str:
        self._sign_in_as_organizer()
        self._create_gathering_via_ui(
            "参加者画面の確認会", candidate_date_count=candidate_date_count
        )
        return self._issue_participant_link_url()

    def _seed_one_shortlisted_shop(self, gathering_id: str) -> str:
        """Puts exactly one real, synthetic shop into this gathering's
        shortlist so shortlistedShopVotes/finalize can be exercised.

        Shop selection itself lives entirely on candidate-search-browser-
        interface.yaml's own gatheringMode screen (adr/0049 decision 1) --
        a screen outside this file's 4-screen scope (class docstring). Since
        driving that screen by hand is out of scope here, this calls the two
        underlying public API operations directly (``self.context.request``,
        the same raw-HTTP approach ``_reset_gathering_state`` above already
        uses for its own public seam) instead: ``candidate-search-api.yaml``'s
        ``proposeCandidates`` (in gathering mode, to read a real ``shopId``
        from the deterministic synthetic population
        ``CandidateSearchBrowserDsl.set_candidate_state`` seeds -- reused
        here only for that already-reviewed Given-seam, never for a
        candidate-search assertion) and ``gathering-scheduling-api.yaml``'s
        own ``setShortlistedShops``. ``self.page`` must already be on an
        organizer-authenticated page carrying the hidden CSRF field (any
        organizerDashboard/organizerGatheringList/organizerGatheringCreate
        render satisfies this).
        """
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        token = csrf_token(self.page)
        propose_response = self.context.request.post(
            f"{self.base_url}/candidate-proposals",
            data={"gatheringId": gathering_id},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(propose_response.status, 200, propose_response.text())
        candidates = propose_response.json()["candidates"]
        self.assertGreater(len(candidates), 0, "no synthetic candidates available to shortlist")
        shop_id = candidates[0]["shopId"]
        put_response = self.context.request.put(
            f"{self.dsl.base_url}/gatherings/{gathering_id}/shortlisted-shops",
            data={"shopIds": [shop_id]},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(put_response.status, 200, put_response.text())
        return shop_id

    def _seed_two_shortlisted_shops_with_a_clear_leader(self, gathering_id: str) -> tuple[str, str]:
        """Shortlists two real, synthetic shops and casts exactly one
        WANT_TO_GO vote for the first only, so it -- and only it -- carries
        data-current-leader="true" (ADR-0055 decision 6's 0-response-
        excluded rule leaves the second, unvoted shop "false"). Returns
        (leaderShopId, otherShopId) in shortlistedShopVotes.list.
        orderingInvariant's own order (votes descending) -- the leader
        sorts first.

        Same out-of-scope reasoning as ``_seed_one_shortlisted_shop`` above
        for shop selection (candidate-search-browser-interface.yaml's own
        gatheringMode); the vote itself (``setShopVotes``) is likewise
        driven directly through its own public API operation rather than
        participant.js's real UI, since actually opening and answering
        through participantAnswer for this purpose alone would pull a
        second, unrelated screen into a check this file's docstring scopes
        to the 4 organizer/participant dashboard screens' own render
        invariants, not participantAnswer's vote flow itself (already
        covered elsewhere in this file). ``self.page`` must already be on
        an organizer-authenticated page (same precondition as
        ``_seed_one_shortlisted_shop``).
        """
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        csrf = csrf_token(self.page)
        propose_response = self.context.request.post(
            f"{self.base_url}/candidate-proposals",
            data={"gatheringId": gathering_id},
            headers={"X-CSRFToken": csrf},
        )
        self.assertEqual(propose_response.status, 200, propose_response.text())
        candidates = propose_response.json()["candidates"]
        self.assertGreaterEqual(
            len(candidates), 2, "need at least 2 synthetic candidates to shortlist"
        )
        leader_shop_id = candidates[0]["shopId"]
        other_shop_id = candidates[1]["shopId"]
        put_response = self.context.request.put(
            f"{self.dsl.base_url}/gatherings/{gathering_id}/shortlisted-shops",
            data={"shopIds": [leader_shop_id, other_shop_id]},
            headers={"X-CSRFToken": csrf},
        )
        self.assertEqual(put_response.status, 200, put_response.text())

        issue_response = self.context.request.post(
            f"{self.dsl.base_url}/gatherings/{gathering_id}/participant-links",
            data={"count": 1},
            headers={"X-CSRFToken": csrf},
        )
        self.assertEqual(issue_response.status, 201, issue_response.text())
        participant_token = issue_response.json()["issuedLinks"][0]["token"]
        # setShopVotes is participant-token-authenticated, not session-based
        # (participant.js itself never sends a CSRF header for it) -- no
        # header needed here either.
        vote_response = self.context.request.put(
            f"{self.dsl.base_url}/participant-links/{participant_token}/shop-votes",
            data={"votes": [{"shopId": leader_shop_id, "status": "WANT_TO_GO"}]},
        )
        self.assertEqual(vote_response.status, 200, vote_response.text())
        return leader_shop_id, other_shop_id

    # --- shared assertion helpers (mirrors RenderedScreenInvariantTests'
    # own (c)/(e) helpers above, generalized to
    # data-gathering-control-purpose / GATHERING_* constants) ---------------

    def _assert_tabbable(self, locator: Locator, label: str) -> None:
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

    def _assert_no_forbidden_enum_token_is_visible_standalone_text(self, page) -> None:
        matches = page.evaluate(
            _SCAN_VISIBLE_TEXT_FOR_TOKENS_JS, GATHERING_FORBIDDEN_INTERNAL_ENUM_TOKENS
        )
        self.assertEqual(
            matches,
            [],
            "internal enum token(s) exposed as standalone visible text: "
            f"{matches} -- ADR-0020 decision 4(d)",
        )

    def _assert_all_declared_gathering_controls_meet_44px(self, page, context_label: str) -> None:
        controls = page.locator("[data-gathering-control-purpose]")
        # Locator.count() itself never waits (unlike expect(...)/wait_for()),
        # so it can observe 0 elements immediately after a navigation or a
        # click that triggers a client-side re-render, before that render has
        # actually happened -- a caller that has not already waited for one
        # of this screen's own controls to appear (as
        # _create_gathering_via_ui now does for organizerDashboard) would
        # otherwise see a false "no controls" failure here. This wait only
        # gives the render a chance to catch up; it does not change the
        # outcome for a genuine 0-controls screen -- if none ever appears,
        # this times out, count() below still observes 0, and the
        # assertGreater below still fails exactly as before.
        try:
            controls.first.wait_for(state="attached")
        except PlaywrightTimeoutError:
            pass
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
            if test_id in GATHERING_CONTROL_SIZE_ALLOWLIST_TEST_IDS:
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

    # --- organizerGatheringList ---------------------------------------------

    def test_b_gathering_list_entry_points_are_keyboard_operable(self) -> None:
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("キーボード到達性の確認会")
        self.page.goto(f"{self.dsl.base_url}/gatherings/")

        list_item_open = by_test_id(self.page, "gathering-list-item-open")
        self._assert_tabbable(list_item_open, "gathering-list-item-open")
        list_item_open.press("Enter")
        expect(self.page).to_have_url(f"{self.dsl.base_url}/gatherings/{gathering_id}/")

        self.page.goto(f"{self.dsl.base_url}/gatherings/")
        create_open = by_test_id(self.page, "gathering-create-open")
        self._assert_tabbable(create_open, "gathering-create-open")
        create_open.press("Enter")
        expect(self.page).to_have_url(f"{self.dsl.base_url}/gatherings/new/")

    def test_c_gathering_list_phase_is_never_shown_as_raw_enum_text(self) -> None:
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("表示enumの確認会（一覧）")
        self.page.goto(f"{self.dsl.base_url}/gatherings/")
        wait_for_at_least_one(self.page, "gathering-list-item")
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(self.page)

    def test_e_gathering_list_controls_meet_44px_minimum_target(self) -> None:
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("サイズ確認会（一覧）")
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.dsl.base_url}/gatherings/")
            wait_for_at_least_one(self.page, "gathering-list-item")
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"populated list at {label}"
            )

        # Entry.dc.html E-1b's empty state -- a second Given state for this
        # same screen, exercising empty.containsCreateOpen's own second
        # gathering-create-open instance.
        self._reset_gathering_state()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.dsl.base_url}/gatherings/")
            wait_for_at_least_one(self.page, "gathering-list-empty")
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"empty list at {label}"
            )

    # --- organizerGatheringCreate --------------------------------------------

    def test_b_gathering_create_calendar_and_actions_are_keyboard_operable(self) -> None:
        """**Rewritten 2026-09-16 (ADR-0060 decision 5)**: "つくる" no longer
        creates the gathering directly -- gathering-create-review-open (new)
        reveals gathering-create-review-dialog, whose own gathering-create-
        submit (same test id/purpose, moved DOM home) now does. Both the
        confirm and cancel paths through this dialog are exercised by
        keyboard alone, on two separate fresh instances of this screen.
        """
        self._sign_in_as_organizer()
        self.page.goto(f"{self.dsl.base_url}/gatherings/new/")

        day_cell = self._first_enabled_day_cell(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
        )
        expect(day_cell).to_be_visible()
        self._assert_tabbable(day_cell, "gathering-create-candidate-date-day")
        self.assertEqual(day_cell.get_attribute("data-selected"), "false")
        day_cell.press("Enter")
        self.assertEqual(day_cell.get_attribute("data-selected"), "true")

        by_test_id(self.page, "gathering-create-name-input").fill("キーボードだけで作る会")

        review_open = by_test_id(self.page, "gathering-create-review-open")
        self._assert_tabbable(review_open, "gathering-create-review-open")
        review_open.press("Enter")
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()

        submit = by_test_id(self.page, "gathering-create-submit")
        self._assert_tabbable(submit, "gathering-create-submit")
        submit.press("Enter")
        expect(self.page).to_have_url(re.compile(r"/gatherings/[0-9a-fA-F-]+/$"))

        # review.cancel / Escape, exercised on a second, fresh instance of
        # this screen -- both close the dialog without creating a gathering
        # and without discarding the pending day selection or name input
        # (review.cancel.requiredOutcome). Escape is not a Must this
        # contract fixes (its own review.dialog section names only the
        # click-driven cancel control), but the implementation's own commit
        # message states this dialog "moves focus in on open, closes on
        # Escape, restores focus to the opener on close" -- a real,
        # deliberately-built keyboard affordance this file's own
        # answerLater/peekResults precedent already establishes gets
        # checked even without a dedicated scenario ID.
        self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
        day_cell_2 = self._first_enabled_day_cell(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
        )
        day_cell_2.click()
        by_test_id(self.page, "gathering-create-name-input").fill("キャンセルの確認会")

        review_open_2 = by_test_id(self.page, "gathering-create-review-open")
        review_open_2.click()
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
        self.page.keyboard.press("Escape")
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_have_count(0)
        focused_test_id = self.page.evaluate(
            "() => document.activeElement && document.activeElement.getAttribute('data-testid')"
        )
        self.assertEqual(
            focused_test_id,
            "gathering-create-review-open",
            "Escape must return focus to the control that opened the dialog",
        )
        self.assertEqual(day_cell_2.get_attribute("data-selected"), "true")

        review_open_2.click()
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
        review_cancel = by_test_id(self.page, "gathering-create-review-cancel")
        self._assert_tabbable(review_cancel, "gathering-create-review-cancel")
        review_cancel.press("Enter")
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_have_count(0)
        expect(self.page).to_have_url(f"{self.dsl.base_url}/gatherings/new/")
        self.assertEqual(day_cell_2.get_attribute("data-selected"), "true")

        # gathering-create-cancel (whole-screen cancel, unaffected by
        # ADR-0060), exercised on the same still-open instance.
        cancel = by_test_id(self.page, "gathering-create-cancel")
        self._assert_tabbable(cancel, "gathering-create-cancel")
        cancel.press("Enter")
        expect(self.page).to_have_url(f"{self.dsl.base_url}/gatherings/")

    # No test_c here: organizerGatheringCreate shows only a free-text name
    # and a plain date calendar -- no Gathering.phase or other API enum is
    # ever displayed on this screen, so decision 4(d) has nothing to gate.

    def test_e_gathering_create_controls_meet_44px_minimum_target(self) -> None:
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
            expect(
                self._first_enabled_day_cell(
                    self.page,
                    "gathering-create-candidate-date-day",
                    "gathering-create-candidate-date-month-next",
                )
            ).to_be_visible()
            self._assert_all_declared_gathering_controls_meet_44px(self.page, label)

    def test_e_gathering_create_review_dialog_controls_meet_44px_minimum_target(self) -> None:
        """review.dialog's own controls (ADR-0060 decision 5) are a distinct
        DOM state from organizerGatheringCreate's own screen-level controls
        above, which never opens this dialog and so never measures anything
        inside it -- a closed disclosure's contents must be opened before
        being measured (FR-013), the same reasoning this file's own
        finalize-/delete-confirm-dialog 44px tests already apply.
        """
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
            by_test_id(self.page, "gathering-create-name-input").fill("モーダル寸法の確認会")
            self._first_enabled_day_cell(
                self.page,
                "gathering-create-candidate-date-day",
                "gathering-create-candidate-date-month-next",
            ).click()
            by_test_id(self.page, "gathering-create-review-open").click()
            expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"review dialog open at {label}"
            )

    def test_b_gathering_create_calendar_month_navigation_and_remove_selected_are_keyboard_operable(
        self,
    ) -> None:
        """ADR-0054 decision 3 / ADR-0056 decision 3 (2026-09-13): the
        self-made calendar's month-navigation arrows and each selected day's
        own remove (×) control are both newly-declared operational controls
        (``allowedPurposes``) this file's own FR-035 gate must cover --
        friction-log.md's own FR-035 names exactly this failure mode ("新し
        い操作を足したのに検査が増えていなければ、それは...再発である").
        """
        self._sign_in_as_organizer()
        self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
        by_test_id(self.page, "gathering-create-name-input").fill("月送りキーボード確認会")

        month_label = by_test_id(self.page, "gathering-create-candidate-date-calendar").locator(
            ".gth-cal-month"
        )
        month_before = month_label.inner_text()

        month_next = by_test_id(self.page, "gathering-create-candidate-date-month-next")
        self._assert_tabbable(month_next, "gathering-create-candidate-date-month-next")
        month_next.press("Enter")
        self.assertNotEqual(month_label.inner_text(), month_before, "month-next did not advance")

        month_previous = by_test_id(self.page, "gathering-create-candidate-date-month-previous")
        self._assert_tabbable(month_previous, "gathering-create-candidate-date-month-previous")
        month_previous.press("Enter")
        self.assertEqual(month_label.inner_text(), month_before, "month-previous did not return")

        # gathering-create-candidate-date-remove-selected moved into
        # gathering-create-review-dialog 2026-09-16 (ADR-0060 decision 5) --
        # its own month-paging is now the *dialog's* own monthNavigation
        # (gathering-create-review-month-previous/-next), a state
        # independent of the outer calendar's month-nav just exercised
        # above. Three selected days: one alone in the earliest month, two
        # sharing a later month -- deliberately keyboard-removing one of the
        # *two* (not the last remaining day in its month), because this
        # contract does not fix this dialog's behavior when a removal empties
        # the currently-displayed month entirely (item.requiredOutcome's own
        # note).
        first_day = self._first_enabled_day_cell(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
        )
        first_iso = first_day.get_attribute("data-date")
        first_day.click()

        by_test_id(self.page, "gathering-create-candidate-date-month-next").click()
        second_day = self._first_enabled_day_cell(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
        )
        second_iso = second_day.get_attribute("data-date")
        second_day.click()
        third_day = self._select_first_unselected_calendar_day(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
            {first_iso, second_iso},
        )
        third_iso = third_day.get_attribute("data-date")

        by_test_id(self.page, "gathering-create-review-open").click()
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()

        def _current_dialog_selected_dates() -> set[str]:
            items = self.page.locator(
                '[data-testid="gathering-create-candidate-date-remove-selected"]'
            )
            return {items.nth(i).get_attribute("data-date") for i in range(items.count())}

        # review.dialog.monthNavigation's own note: "Initial position is the
        # earliest month containing a currently-selected day" -- first_iso's
        # month, since it was selected before paging the outer calendar
        # forward to select second_iso/third_iso.
        self.assertEqual(_current_dialog_selected_dates(), {first_iso})

        review_month_next = by_test_id(self.page, "gathering-create-review-month-next")
        self._assert_tabbable(review_month_next, "gathering-create-review-month-next")
        review_month_next.press("Enter")
        self.assertEqual(_current_dialog_selected_dates(), {second_iso, third_iso})

        third_item = self.page.locator(
            f'[data-testid="gathering-create-candidate-date-remove-selected"][data-date="{third_iso}"]'
        )
        self._assert_tabbable(third_item, "gathering-create-candidate-date-remove-selected")
        third_item.press("Enter")
        # Only the dialog's own state is checked here, not the outer
        # calendar's day cell -- the outer calendar may or may not still be
        # showing third_iso's month at this point (this contract does not
        # fix whether selecting a day elsewhere changes which month the
        # outer calendar itself displays), and this test's own scope is the
        # dialog's keyboard operability, not the outer calendar's month
        # state (already covered separately, above).
        self.assertEqual(_current_dialog_selected_dates(), {second_iso})

        review_month_previous = by_test_id(self.page, "gathering-create-review-month-previous")
        self._assert_tabbable(review_month_previous, "gathering-create-review-month-previous")
        review_month_previous.press("Enter")
        self.assertEqual(_current_dialog_selected_dates(), {first_iso})

    def test_e_gathering_create_calendar_navigation_and_remove_selected_meet_44px_minimum_target(
        self,
    ) -> None:
        """**Rewritten 2026-09-16 (ADR-0060 decision 5)**: remove-selected
        only renders inside gathering-create-review-dialog now -- this test
        must open that dialog, or it silently stops measuring
        remove-selected at all (a closed disclosure's contents must be
        opened before being measured, FR-013).
        """
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
            by_test_id(self.page, "gathering-create-name-input").fill(f"サイズ確認{label}")
            day_cell = self._first_enabled_day_cell(
                self.page,
                "gathering-create-candidate-date-day",
                "gathering-create-candidate-date-month-next",
            )
            day_cell.click()
            by_test_id(self.page, "gathering-create-review-open").click()
            expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"with a remove-selected control shown in the dialog at {label}"
            )

    def test_gth_weekend_and_holiday_day_cells_cannot_be_selected(self) -> None:
        """ADR-0060 decision 1/2/4 (2026-09-16, TDR-GTH-57/58): a Saturday,
        Sunday, or Japan public holiday day cell carries no
        data-gathering-control-purpose (this product's own established
        enabled/disabled convention, not a native ``disabled`` attribute --
        every other day-cell/control check in this file already uses this
        same convention, e.g. ``_first_enabled_day_cell`` above) and cannot
        be forced into a selected state either. Checked on both calendars
        this contract fixes the same dayCell.disabledState rule for
        (organizerGatheringCreate.calendar and addCandidateDateForm.calendar).
        """
        self._sign_in_as_organizer()
        self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
        disabled_cell = self._find_weekend_or_holiday_disabled_cell(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
        )
        self.assertIsNone(
            disabled_cell.get_attribute("data-gathering-control-purpose"),
            "a weekend/holiday day cell must not declare an activation purpose",
        )
        self.assertEqual(disabled_cell.get_attribute("data-selected"), "false")
        disabled_cell.click(force=True)
        self.assertEqual(
            disabled_cell.get_attribute("data-selected"),
            "false",
            "clicking a disabled weekend/holiday day cell must not select it",
        )

        self._create_gathering_via_ui("休日マス確認会")
        by_test_id(self.page, "gathering-add-candidate-date-open").click()
        expect(by_test_id(self.page, "gathering-add-candidate-date-form")).to_be_attached()
        disabled_cell_add = self._find_weekend_or_holiday_disabled_cell(
            self.page,
            "gathering-add-candidate-date-day",
            "gathering-add-candidate-date-month-next",
        )
        self.assertIsNone(
            disabled_cell_add.get_attribute("data-gathering-control-purpose"),
            "a weekend/holiday day cell must not declare an activation purpose",
        )
        disabled_cell_add.click(force=True)
        self.assertEqual(disabled_cell_add.get_attribute("data-selected"), "false")

    # --- organizerDashboard ---------------------------------------------

    def test_b_gathering_dashboard_core_controls_are_keyboard_operable(self) -> None:
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui(
            "幹事ダッシュボードの確認会", candidate_date_count=2
        )
        # self.page is already on this gathering's organizerDashboard
        # (_create_gathering_via_ui's own post-submit navigation).

        add_open = by_test_id(self.page, "gathering-add-candidate-date-open")
        self._assert_tabbable(add_open, "gathering-add-candidate-date-open")
        add_open.press("Enter")
        expect(by_test_id(self.page, "gathering-add-candidate-date-form")).to_be_attached()

        # Not the calendar's own first enabled day: _create_gathering_via_ui
        # (candidate_date_count=2) above already used 2 of this month's own
        # enabled days as this gathering's candidate dates -- re-selecting
        # either from this second, independent calendar instance would trip
        # DUPLICATE_CANDIDATE_DATE and leave this form's own selection/count
        # unchanged, which is not what this keyboard-operability check is
        # testing. Reads the actual candidate dates back from the API
        # (rather than assuming which index the create screen picked) so
        # this stays correct regardless of which day of the month "today" is
        # (ADR-0054 decision 3: a single-month calendar, not the retired
        # 3-simultaneous-month one).
        existing_response = self.context.request.get(
            f"{self.dsl.base_url}/gatherings/{gathering_id}"
        )
        self.assertEqual(existing_response.status, 200, existing_response.text())
        excluded_isos = {
            candidate_date["startAt"][:10]
            for candidate_date in existing_response.json()["candidateDates"]
        }
        add_day = self._select_first_unselected_calendar_day(
            self.page,
            "gathering-add-candidate-date-day",
            "gathering-add-candidate-date-month-next",
            excluded_isos,
        )
        expect(add_day).to_be_visible()
        self._assert_tabbable(add_day, "gathering-add-candidate-date-day")
        self.assertEqual(add_day.get_attribute("data-selected"), "true")
        add_day.press("Enter")
        self.assertEqual(add_day.get_attribute("data-selected"), "false")
        add_day.press("Enter")
        self.assertEqual(add_day.get_attribute("data-selected"), "true")

        add_submit = by_test_id(self.page, "gathering-add-candidate-date-submit")
        self._assert_tabbable(add_submit, "gathering-add-candidate-date-submit")
        before_count = self.page.locator('[data-testid="gathering-candidate-date"]').count()
        add_submit.press("Enter")
        expect(self.page.locator('[data-testid="gathering-candidate-date"]')).to_have_count(
            before_count + 1
        )

        first_date = self.page.locator('[data-testid="gathering-candidate-date"]').first
        self._assert_tabbable(first_date, "gathering-candidate-date")
        first_date.press("Enter")
        expect(first_date).to_have_attribute("data-tentative-selected", "true")

        confirm = by_test_id(self.page, "gathering-confirm-date-select")
        self._assert_tabbable(confirm, "gathering-confirm-date-select")
        confirm.press("Enter")
        # ADR-0063 decision 1 (2026-09-19): gathering-phase-indicator itself
        # becomes absent while phase is SELECTING_SHOP -- headingBar's own
        # gathering-dashboard-confirmed-date (present exactly under the same
        # condition) is this file's own substitute "we reached SELECTING_
        # SHOP" signal from here on (the same substitution this ADR's own
        # 未決事項1 names).
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()

        # ADR-0063 decision 3: participantLinkCopy now lives behind
        # shopSelectionPanel's own linksTab -- opened here before
        # interacting with it (closed-tab content is not visible until its
        # own tab is activated, by design, mirroring this file's own
        # existing open-before-measuring discipline for FINALIZED's
        # linksOpen).
        by_test_id(self.page, "gathering-shop-select-tab-links").click()
        copy_control = by_test_id(self.page, "gathering-participant-link-copy")
        self._assert_tabbable(copy_control, "gathering-participant-link-copy")
        copy_control.press("Enter")
        # ADR-0061 decision 1: Enter opens issueDialog rather than writing
        # data-issued-link-url onto copy_control itself -- dialogCopy/
        # dialogClose get their own dedicated keyboard test below, this only
        # confirms the 2-step flow's first step still activates by keyboard.
        dialog = by_test_id(self.page, "gathering-participant-link-issue-dialog")
        expect(dialog).to_have_attribute("data-issued-link-url", re.compile(r"^http"))
        by_test_id(self.page, "gathering-participant-link-issue-dialog-close").press("Enter")
        expect(dialog).to_have_count(0)

        # shopSelectionEntry.open now lives behind shopTab -- switch back
        # before reaching for it. Only tabbability/activation is asserted
        # here. Its requiredOutcome navigates to
        # candidate-search-browser-interface.yaml's own gatheringMode screen
        # -- a screen outside this file's four-screen scope (class
        # docstring) -- so this file does not follow it there or assert its
        # contents.
        by_test_id(self.page, "gathering-shop-select-tab-shop").click()
        shortlist_open = by_test_id(self.page, "gathering-shortlist-open")
        self._assert_tabbable(shortlist_open, "gathering-shortlist-open")
        url_before = self.page.url
        shortlist_open.press("Enter")
        self.page.wait_for_timeout(500)
        self.assertNotEqual(self.page.url, url_before, "gathering-shortlist-open did not navigate")

    def test_b_gathering_dashboard_link_issue_dialog_is_keyboard_operable(self) -> None:
        """ADR-0061 decision 1 (2026-09-17, human decision: 「発行で小窓が
        開き、そこでコピー」): dedicated keyboard coverage of issueDialog's
        own dialogCopy/dialogClose (the core-controls test above only opens
        and closes it as a byproduct of walking every other control).
        Enter's effect on dialogCopy is checked by its own visible-text
        change (dialogCopy.requiredOutcome does not fix the wording, but
        this file's own render always flips it on activation) -- the
        clipboard write itself is TDR-GTH-03/17's L4 concern, not this
        gate's (decision4(c) only requires keyboard reachability/
        activation-parity, not the side effect's content).
        """
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("発行小窓のキーボード確認会")

        copy_control = by_test_id(self.page, "gathering-participant-link-copy")
        self._assert_tabbable(copy_control, "gathering-participant-link-copy")
        copy_control.press("Enter")
        dialog = by_test_id(self.page, "gathering-participant-link-issue-dialog")
        expect(dialog).to_have_attribute("data-issued-link-url", re.compile(r"^http"))

        dialog_copy = by_test_id(self.page, "gathering-participant-link-issue-dialog-copy")
        self._assert_tabbable(dialog_copy, "gathering-participant-link-issue-dialog-copy")
        dialog_copy.press("Enter")
        expect(dialog_copy).to_have_text("✓ コピーしました")

        dialog_close = by_test_id(self.page, "gathering-participant-link-issue-dialog-close")
        self._assert_tabbable(dialog_close, "gathering-participant-link-issue-dialog-close")
        dialog_close.press("Enter")
        expect(dialog).to_have_count(0)

    def test_e_gathering_dashboard_link_issue_dialog_controls_meet_44px_minimum_target(
        self,
    ) -> None:
        """dialogCopy/dialogClose already carry data-gathering-control-
        purpose, so the generic sweep covers them once the dialog is
        actually open (same open-before-measuring discipline
        test_e_gathering_dashboard_finalize_confirmation_meets_44px_minimum_target
        above already uses for its own dialog)."""
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self._create_gathering_via_ui(f"発行小窓サイズ確認会{label}")
            by_test_id(self.page, "gathering-participant-link-copy").click()
            dialog = by_test_id(self.page, "gathering-participant-link-issue-dialog")
            expect(dialog).to_be_attached()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"link issue dialog open at {label}"
            )

    def test_b_gathering_dashboard_remove_candidate_date_is_keyboard_operable(self) -> None:
        """ADR-0056 decision 2 (2026-09-12, human decision): a previously
        added, not-yet-confirmed candidate date can now be taken back --
        friction-log.md FR-035's own gate must cover this newly-declared
        operational control the same way it covers every other one.

        This backend endpoint (``DELETE
        /gatherings/{gatheringId}/candidate-dates/{candidateDateId}``) is
        being implemented in parallel by another developer (this round's
        Python is out of this developer's scope) -- this test asserts
        keyboard reachability and activation-does-not-error only; it does
        not assert the post-removal DOM outcome the contract's own
        ``requiredOutcome`` describes, since that outcome depends on the
        not-yet-landed server-side behavior. Once that lands, this test
        should be extended to also assert the row disappears (tester/
        integrator note).
        """
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("候補日削除の確認会", candidate_date_count=2)

        remove_button = self.page.locator('[data-testid="gathering-candidate-date-remove"]').first
        expect(remove_button).to_be_visible()
        self._assert_tabbable(remove_button, "gathering-candidate-date-remove")
        remove_button.press("Enter")
        # No exception/console error from activating it -- the dashboard
        # itself must still be intact regardless of the (currently
        # unimplemented) server response.
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_be_visible()

        # Once a candidate date is confirmed, it is no longer removable
        # (CANDIDATE_DATE_CONFIRMED) -- the control's own presenceRule
        # switches to absent, not merely disabled.
        confirmed_dates = self.page.locator('[data-testid="gathering-candidate-date"]')
        confirmed_dates.first.click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        # ADR-0063 decision 1: see this file's own
        # test_b_gathering_dashboard_core_controls_are_keyboard_operable
        # for why gathering-dashboard-confirmed-date replaces
        # gathering-phase-indicator as the "reached SELECTING_SHOP" signal
        # from here on.
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()
        expect(
            self.page.locator(
                '[data-testid="gathering-candidate-date"][data-confirmed="true"] '
                '[data-testid="gathering-candidate-date-remove"]'
            )
        ).to_have_count(0)

    def test_b_gathering_dashboard_finalize_confirmation_is_keyboard_operable(self) -> None:
        """ADR-0054 decision 5 / ADR-0056 decision 11 (2026-09-12): finalize
        is now a 4-part open/confirm-dialog/confirm/cancel flow, the same
        shape deleteGathering already uses -- FR-035's gate must cover these
        newly-declared operational controls (gathering-finalize-open/-confirm/
        -cancel) the same way it already covers gathering-delete-open/
        -confirm/-cancel.

        **Updated 2026-09-17 (ADR-0062 decision 3, human decision, board D3:
        「日時とお店があればいい。参加者は書かなくていい」)**: the dialog's
        own content check now reads gathering-finalize-confirm-date/-shop
        (confirmSummary, this decision's replacement structure) instead of
        the retired 3-row gathering-finalize-confirm-changes table, and cross
        -checks both against this gathering's own confirmed candidate date/
        shortlisted shop id -- also confirms the retired table itself no
        longer appears. Also checks gathering-shortlisted-shop-page-link
        (board D1's "店のページを見る" column) is keyboard-reachable with a
        real href, since detailFields' own providerPageLink is a plain
        anchor outside the declared-purpose 44px/keyboard sweep below.
        """
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("確定フローの確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()
        shop_id = self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        gathering_response = self.context.request.get(
            f"{self.dsl.base_url}/gatherings/{gathering_id}"
        )
        self.assertEqual(gathering_response.status, 200, gathering_response.text())
        confirmed_date_iso = gathering_response.json()["candidateDates"][0]["startAt"]

        page_link = by_test_id(self.page, "gathering-shortlisted-shop-page-link").first
        self._assert_tabbable(page_link, "gathering-shortlisted-shop-page-link")
        self.assertTrue(page_link.get_attribute("href"))

        radio = by_test_id(self.page, "gathering-finalize-shop-select")
        self._assert_tabbable(radio, "gathering-finalize-shop-select")
        # A native <input type="radio"> toggles on Space, not Enter (unlike
        # a <button>) -- this is the one control on this screen that is a
        # real native radio, so it is the one place this file presses
        # Space instead of Enter.
        radio.press(" ")
        self.assertEqual(radio.get_attribute("data-finalize-selected"), "true")

        finalize_open = by_test_id(self.page, "gathering-finalize-open")
        self._assert_tabbable(finalize_open, "gathering-finalize-open")
        finalize_open.press("Enter")
        expect(by_test_id(self.page, "gathering-finalize-confirm-dialog")).to_be_attached()
        confirm_date = by_test_id(self.page, "gathering-finalize-confirm-date")
        expect(confirm_date).to_be_visible()
        self.assertEqual(
            confirm_date.get_attribute("data-confirmed-candidate-date"), confirmed_date_iso
        )
        confirm_shop = by_test_id(self.page, "gathering-finalize-confirm-shop")
        expect(confirm_shop).to_be_visible()
        self.assertEqual(confirm_shop.get_attribute("data-shop-id"), shop_id)
        expect(by_test_id(self.page, "gathering-finalize-confirm-changes")).to_have_count(0)

        finalize_cancel = by_test_id(self.page, "gathering-finalize-cancel")
        self._assert_tabbable(finalize_cancel, "gathering-finalize-cancel")
        finalize_cancel.press("Enter")
        expect(by_test_id(self.page, "gathering-finalize-confirm-dialog")).to_have_count(0)
        # finalizeCancel.requiredOutcome: the pending radio selection
        # survives cancellation.
        expect(by_test_id(self.page, "gathering-finalize-shop-select")).to_have_attribute(
            "data-finalize-selected", "true"
        )

        finalize_open_again = by_test_id(self.page, "gathering-finalize-open")
        finalize_open_again.press("Enter")
        finalize_confirm = by_test_id(self.page, "gathering-finalize-confirm")
        self._assert_tabbable(finalize_confirm, "gathering-finalize-confirm")
        finalize_confirm.press("Enter")
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "FINALIZED"
        )
        expect(by_test_id(self.page, "gathering-finalize-open")).to_have_count(0)

    def test_e_gathering_dashboard_shortlisted_shop_panel_paints_above_the_map(self) -> None:
        """Real-machine finding: gth-shop-map (position: absolute) needs its
        own explicit z-index to establish a stacking context that contains
        Leaflet's internal panes (up to z-index 700) -- without one, a click/
        elementFromPoint check still passes (Leaflet's panes carry
        pointer-events: none and are shrink-to-fit zero-size boxes, so they
        are never the hit target either way) even though the map can paint
        over the floating list. Checks the actual stacking levels instead.
        """
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("地図と一覧の重なりの確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        styles = self.page.evaluate(
            """
            () => {
              const cs = (el) => el ? getComputedStyle(el) : null;
              const shopMap = document.querySelector('.gth-shop-map');
              const panel = document.querySelector('.gth-shop-panel');
              return {
                mapZIndex: cs(shopMap) ? cs(shopMap).zIndex : null,
                mapPosition: cs(shopMap) ? cs(shopMap).position : null,
                panelZIndex: cs(panel) ? cs(panel).zIndex : null,
              };
            }
            """
        )
        self.assertEqual(styles["mapPosition"], "absolute")
        self.assertNotEqual(
            styles["mapZIndex"],
            "auto",
            "gth-shop-map must set an explicit z-index (not auto) so its "
            "position: absolute establishes its own stacking context -- "
            "otherwise Leaflet's internal panes (tile/marker/tooltip/popup "
            "panes carry z-index up to 700) are free to compare directly "
            "against gth-shop-panel's own z-index instead of staying "
            "contained beneath the map as a whole",
        )
        self.assertLess(
            int(styles["mapZIndex"]),
            int(styles["panelZIndex"]),
            "gth-shop-map's own stacking level "
            f"({styles['mapZIndex']}) must sit below gth-shop-panel's "
            f"({styles['panelZIndex']}) so the floating list always paints "
            "above the map, matching every board frame (party2/d2/D1-a-*)",
        )

    def test_e_gathering_dashboard_finalize_confirmation_meets_44px_minimum_target(self) -> None:
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            gathering_id = self._create_gathering_via_ui(f"確定サイズ確認会{label}")
            by_test_id(self.page, "gathering-candidate-date").click()
            by_test_id(self.page, "gathering-confirm-date-select").click()
            self._seed_one_shortlisted_shop(gathering_id)
            self.page.reload()
            expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
            by_test_id(self.page, "gathering-finalize-shop-select").click()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"shop selected, before finalize dialog at {label}"
            )
            by_test_id(self.page, "gathering-finalize-open").click()
            expect(by_test_id(self.page, "gathering-finalize-confirm-dialog")).to_be_attached()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"finalize-confirm dialog open at {label}"
            )

    def test_b_gathering_dashboard_finalized_decision_screen_recopy_remains_keyboard_operable(
        self,
    ) -> None:
        """ADR-0062 decision 4 / addendum 22 (2026-09-19): once FINALIZED,
        shortlistedShopVotes itself becomes absent, but participantLinkList's
        own recopy control stays reachable post-finalize (P4, TDR-GTH-36) --
        now behind gathering-decision-links-open's own entrance (answersOpen/
        linksOpen), opened here before measuring (closed-entrance content is
        not visible until its own entrance is activated, by design).
        """
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("確定後キーボード確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        # ADR-0063 decision 3: participantLinkCopy now lives behind
        # shopSelectionPanel's own linksTab while SELECTING_SHOP (opened
        # here before interacting with it, same discipline as this file's
        # own FINALIZED-phase linksOpen below).
        by_test_id(self.page, "gathering-shop-select-tab-links").click()
        by_test_id(self.page, "gathering-participant-link-copy").click()
        self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        by_test_id(self.page, "gathering-finalize-shop-select").click()
        by_test_id(self.page, "gathering-finalize-open").click()
        by_test_id(self.page, "gathering-finalize-confirm").click()
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "FINALIZED"
        )
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_have_count(0)
        expect(by_test_id(self.page, "gathering-decision-banner")).to_be_visible()

        decision_link = by_test_id(self.page, "gathering-decision-shop-page-link")
        self._assert_tabbable(decision_link, "gathering-decision-shop-page-link")
        self.assertTrue(decision_link.get_attribute("href"))

        links_open = by_test_id(self.page, "gathering-decision-links-open")
        self._assert_tabbable(links_open, "gathering-decision-links-open")
        links_open.press("Enter")
        recopy = by_test_id(self.page, "gathering-participant-link-recopy").first
        expect(recopy).to_be_visible()
        self._assert_tabbable(recopy, "gathering-participant-link-recopy")
        recopy.press("Enter")
        # Activation-does-not-error only (mirrors this file's own
        # test_b_gathering_dashboard_remove_candidate_date_is_keyboard_
        # operable precedent) -- the dashboard itself must still be intact.
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_be_visible()

    def test_e_gathering_dashboard_finalized_decision_screen_meets_44px_minimum_target(
        self,
    ) -> None:
        """ADR-0062 decision 4 / addendum 22: the FINALIZED-phase
        organizerDashboard render is a screen state this file's own 44px
        sweep had never reached before. Measures both the default (answers-
        open) state and, after activating links-open, the entrance-revealed
        participantLinkList content too -- a closed entrance's own content
        is correctly invisible/unmeasured until opened, per design.
        """
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            gathering_id = self._create_gathering_via_ui(f"確定後サイズ確認会{label}")
            by_test_id(self.page, "gathering-candidate-date").click()
            by_test_id(self.page, "gathering-confirm-date-select").click()
            # ADR-0063 decision 3: see this file's own
            # test_b_gathering_dashboard_finalized_decision_screen_recopy_
            # remains_keyboard_operable for why linksTab is opened first.
            by_test_id(self.page, "gathering-shop-select-tab-links").click()
            by_test_id(self.page, "gathering-participant-link-copy").click()
            self._seed_one_shortlisted_shop(gathering_id)
            self.page.reload()
            expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
            by_test_id(self.page, "gathering-finalize-shop-select").click()
            by_test_id(self.page, "gathering-finalize-open").click()
            by_test_id(self.page, "gathering-finalize-confirm").click()
            expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
                "data-gathering-phase", "FINALIZED"
            )
            expect(by_test_id(self.page, "gathering-decision-banner")).to_be_visible()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"FINALIZED decision screen at {label}"
            )
            by_test_id(self.page, "gathering-decision-links-open").click()
            expect(by_test_id(self.page, "gathering-participant-link-list")).to_be_visible()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"FINALIZED decision screen, links-open at {label}"
            )

    def test_gathering_dashboard_finalized_answers_links_entrance_has_declared_purpose(
        self,
    ) -> None:
        """ADR-0062 addendum 22 (2026-09-19, contract 0.24.1): answersOpen/
        linksOpen (gathering-decision-answers-open/-links-open) are the
        entrance to responseTable/participantLinkList once FINALIZED --
        checked directly (not only via the generic 44px sweep, which would
        silently stop counting a control whose purpose attribute is
        removed, rather than failing) so removing either one's declared
        purpose is caught here specifically.
        """
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("確定後開閉目印確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        by_test_id(self.page, "gathering-finalize-shop-select").click()
        by_test_id(self.page, "gathering-finalize-open").click()
        by_test_id(self.page, "gathering-finalize-confirm").click()
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "FINALIZED"
        )
        for test_id in ("gathering-decision-answers-open", "gathering-decision-links-open"):
            control = by_test_id(self.page, test_id)
            expect(control).to_be_visible()
            self.assertEqual(control.get_attribute("data-gathering-control-purpose"), test_id)

    def test_gathering_dashboard_leader_summary_is_absent_once_a_date_is_decided(
        self,
    ) -> None:
        """ADR-0060 addendum 23 (2026-09-19, contract 0.24.2): leaderSummary
        (the "有力" row) helps pick a date -- once one is picked
        (SELECTING_SHOP onward), it is absent even though the same
        candidate date still carries data-current-leader="true" (that
        attribute itself is unchanged by this addendum).
        """
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("有力の消える確認会", candidate_date_count=2)
        link_url = self._issue_participant_link_url()
        participant_page = self._open_participant_view(link_url)
        by_test_id(participant_page, "gathering-schedule-response-option").first.click()
        self.page.reload()

        expect(
            self.page.locator(
                '[data-testid="gathering-candidate-date"][data-current-leader="true"]'
            )
        ).to_have_count(1)
        expect(by_test_id(self.page, "gathering-response-table-leader-summary")).to_be_visible()

        by_test_id(self.page, "gathering-candidate-date").first.click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()
        # ADR-0063 decision 3: candidateDateList/responseTable now live
        # behind shopSelectionPanel's own scheduleTab/answersTab while
        # SELECTING_SHOP -- each opened here in turn before its own content
        # is checked.
        by_test_id(self.page, "gathering-shop-select-tab-schedule").click()
        expect(
            self.page.locator(
                '[data-testid="gathering-candidate-date"][data-current-leader="true"]'
            )
        ).to_have_count(1)
        by_test_id(self.page, "gathering-shop-select-tab-answers").click()
        expect(by_test_id(self.page, "gathering-response-table-leader-summary")).to_have_count(0)

    def test_gathering_dashboard_response_table_reflects_one_row_per_participant_link(
        self,
    ) -> None:
        """ADR-0056 decision 1 (2026-09-12): gathering-response-table is a
        new, always-present element (one row per ParticipantLinkSummary).
        Reads ``ParticipantLinkSummary.scheduleResponses`` -- **not yet
        populated by this deployment's backend**
        (``gathering-scheduling-api.yaml`` v0.12.0 requires the field, but
        the Python side of this round is being implemented in parallel by
        another developer) -- so this asserts only that the table itself and
        one row per issued link exist (rendering correctly as all-empty
        rows until that field lands), not the per-cell schedule-response
        content the full contract describes.
        """
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("回答一覧の確認会")
        by_test_id(self.page, "gathering-participant-link-copy").click()
        by_test_id(self.page, "gathering-participant-link-copy").click()

        table = by_test_id(self.page, "gathering-response-table")
        expect(table).to_be_visible()
        expect(self.page.locator('[data-testid="gathering-response-table-row"]')).to_have_count(2)

    def test_gathering_dashboard_heading_bar_replaces_phase_indicator_only_while_selecting_shop(
        self,
    ) -> None:
        """ADR-0063 decisions 1-2 (2026-09-19, board S4): a full round trip
        (SCHEDULING -> SELECTING_SHOP -> FINALIZED) confirming headingBar
        (gathering-dashboard-title/-confirmed-date) and phaseIndicator
        (gathering-phase-indicator) are mutually exclusive across exactly
        the one phase decision 1 carves out -- both present together would
        be a regression of the "replaces the badge for this one phase"
        design, and headingBar surviving into FINALIZED would duplicate
        finalizedSummary.decisionBanner's own heading role.
        """
        self._sign_in_as_organizer()
        title = "見出し切り替えの確認会"
        gathering_id = self._create_gathering_via_ui(title)

        # SCHEDULING: phaseIndicator present, headingBar absent.
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "SCHEDULING"
        )
        expect(by_test_id(self.page, "gathering-dashboard-title")).to_have_count(0)
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_have_count(0)

        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()

        # SELECTING_SHOP: headingBar present with the real title/date,
        # phaseIndicator absent.
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_count(0)
        heading_title = by_test_id(self.page, "gathering-dashboard-title")
        expect(heading_title).to_be_visible()
        self.assertEqual(heading_title.get_attribute("data-gathering-title"), title)
        gathering_response = self.context.request.get(
            f"{self.dsl.base_url}/gatherings/{gathering_id}"
        )
        self.assertEqual(gathering_response.status, 200, gathering_response.text())
        confirmed_date_iso = gathering_response.json()["candidateDates"][0]["startAt"]
        heading_date = by_test_id(self.page, "gathering-dashboard-confirmed-date")
        expect(heading_date).to_be_visible()
        self.assertEqual(
            heading_date.get_attribute("data-confirmed-candidate-date"), confirmed_date_iso
        )

        self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        by_test_id(self.page, "gathering-finalize-shop-select").click()
        by_test_id(self.page, "gathering-finalize-open").click()
        by_test_id(self.page, "gathering-finalize-confirm").click()

        # FINALIZED: phaseIndicator returns, headingBar is gone again.
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "FINALIZED"
        )
        expect(by_test_id(self.page, "gathering-dashboard-title")).to_have_count(0)
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_have_count(0)

    def test_b_gathering_dashboard_shop_select_tabs_are_keyboard_operable_and_toggle_content(
        self,
    ) -> None:
        """ADR-0063 decision 3 (2026-09-19, board S4): the 4-tab strip
        (shopTab default-selected) -- each tab is keyboard-reachable, only
        one carries aria-selected="true" at a time, and activating one
        makes its own target's content visible while the others' own
        content is not (candidateDateList/responseTable/participantLinkList
        each keep their own presenceRule -- only whether this panel
        currently discloses them changes)."""
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("タブ切り替えの確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()

        shop_tab = by_test_id(self.page, "gathering-shop-select-tab-shop")
        schedule_tab = by_test_id(self.page, "gathering-shop-select-tab-schedule")
        answers_tab = by_test_id(self.page, "gathering-shop-select-tab-answers")
        links_tab = by_test_id(self.page, "gathering-shop-select-tab-links")

        # Default selection (board S4: 既定は「店」).
        expect(shop_tab).to_have_attribute("aria-selected", "true")
        expect(schedule_tab).to_have_attribute("aria-selected", "false")
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        expect(by_test_id(self.page, "gathering-candidate-date-list")).to_be_hidden()

        self._assert_tabbable(schedule_tab, "gathering-shop-select-tab-schedule")
        schedule_tab.press("Enter")
        expect(schedule_tab).to_have_attribute("aria-selected", "true")
        expect(shop_tab).to_have_attribute("aria-selected", "false")
        expect(by_test_id(self.page, "gathering-candidate-date-list")).to_be_visible()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_hidden()

        self._assert_tabbable(answers_tab, "gathering-shop-select-tab-answers")
        answers_tab.press("Enter")
        expect(answers_tab).to_have_attribute("aria-selected", "true")
        expect(schedule_tab).to_have_attribute("aria-selected", "false")
        expect(by_test_id(self.page, "gathering-response-table")).to_be_visible()
        expect(by_test_id(self.page, "gathering-candidate-date-list")).to_be_hidden()

        self._assert_tabbable(links_tab, "gathering-shop-select-tab-links")
        links_tab.press("Enter")
        expect(links_tab).to_have_attribute("aria-selected", "true")
        expect(answers_tab).to_have_attribute("aria-selected", "false")
        expect(by_test_id(self.page, "gathering-participant-link-list")).to_be_visible()
        expect(by_test_id(self.page, "gathering-response-table")).to_be_hidden()

        self._assert_tabbable(shop_tab, "gathering-shop-select-tab-shop")
        shop_tab.press("Enter")
        expect(shop_tab).to_have_attribute("aria-selected", "true")
        expect(links_tab).to_have_attribute("aria-selected", "false")
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        expect(by_test_id(self.page, "gathering-participant-link-list")).to_be_hidden()

    def test_gathering_dashboard_participant_link_copy_is_unconditional_on_shop_select_tab(
        self,
    ) -> None:
        """ADR-0063 decision 3's own scope note names exactly 4 tab-gated
        targets (shopSelectionEntry/shortlistedShopVotes.list,
        candidateDateList, responseTable, participantLinkList) --
        participantLinkCopy is deliberately not one of them, so its own
        presenceRule ("Present while phase is SCHEDULING or
        SELECTING_SHOP") must hold regardless of which tab is currently
        selected (tester finding, TDR-GTH-36: it must be reachable from
        the default shopTab, not only from linksTab)."""
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("回答リンク発行ボタンの確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()

        shop_tab = by_test_id(self.page, "gathering-shop-select-tab-shop")
        expect(shop_tab).to_have_attribute("aria-selected", "true")
        copy_control = by_test_id(self.page, "gathering-participant-link-copy")
        expect(copy_control).to_be_visible()
        self._assert_tabbable(copy_control, "gathering-participant-link-copy")

        for tab_test_id in (
            "gathering-shop-select-tab-schedule",
            "gathering-shop-select-tab-answers",
            "gathering-shop-select-tab-links",
        ):
            by_test_id(self.page, tab_test_id).click()
            expect(copy_control).to_be_visible()

    def test_gathering_dashboard_selected_shop_row_pins_without_reordering_the_list(
        self,
    ) -> None:
        """ADR-0063 decision 4 (2026-09-19, board S4, human decision:
        残りは票が多い順のまま並べ、番号の丸は票の順位を保つ): selecting a
        shop other than the current vote leader must not change
        gathering-shortlisted-shop-list's own DOM order (orderingInvariant,
        votes descending) -- only a CSS-visual pin, never a DOM reorder
        (this ADR's own 検討した代替案 explicitly rejects the reorder)."""
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("並び順の確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        leader_shop_id, other_shop_id = self._seed_two_shortlisted_shops_with_a_clear_leader(
            gathering_id
        )
        self.page.reload()
        items = self.page.locator('[data-testid="gathering-shortlisted-shop-item"]')
        expect(items).to_have_count(2)
        order_before = [items.nth(index).get_attribute("data-shop-id") for index in range(2)]
        self.assertEqual(order_before, [leader_shop_id, other_shop_id])
        expect(items.nth(0)).to_have_attribute("data-current-leader", "true")
        expect(items.nth(1)).to_have_attribute("data-current-leader", "false")
        # The rank badge itself carries no test id (display-only, board S4)
        # -- its text is read from the item's own DOM position, the same
        # position this test's own order_before/order_after compare.
        rank_before = items.nth(1).locator(".gth-shop-rank").inner_text()
        self.assertEqual(rank_before, "2", "the non-leader shop must start ranked 2nd")

        # Select the second (non-leader) row.
        self.page.locator(
            f'[data-testid="gathering-shortlisted-shop-item"][data-shop-id="{other_shop_id}"] '
            '[data-testid="gathering-finalize-shop-select"]'
        ).click()

        order_after = [items.nth(index).get_attribute("data-shop-id") for index in range(2)]
        self.assertEqual(
            order_after,
            order_before,
            "selecting a non-leader shop must not reorder gathering-shortlisted-shop-list",
        )
        rank_after = self.page.locator(
            f'[data-testid="gathering-shortlisted-shop-item"][data-shop-id="{other_shop_id}"]'
            " .gth-shop-rank"
        ).inner_text()
        self.assertEqual(
            rank_after, "2", "the selected shop's own rank number must stay 2, not jump to 1"
        )

    def test_gathering_dashboard_shop_map_marker_reflects_leader_and_selected_signals(
        self,
    ) -> None:
        """ADR-0063 decision 4 (2026-09-19, board S4, human decision: 緑=票が
        多いこと、スミ色=幹事が選んでいること): the map marker's own visual
        modifier classes are driven by the correlated
        gathering-shortlisted-shop-item's own data-current-leader/the
        radio's data-finalize-selected -- never conflated, and the two
        signals may point at two different shops at once (a shop can be
        the vote leader without being the organizer's current pick)."""
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("ピンの色の確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        leader_shop_id, other_shop_id = self._seed_two_shortlisted_shops_with_a_clear_leader(
            gathering_id
        )
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        self.page.locator(
            f'[data-testid="gathering-shortlisted-shop-item"][data-shop-id="{other_shop_id}"] '
            '[data-testid="gathering-finalize-shop-select"]'
        ).click()

        leader_marker = self.page.locator(
            f'[data-testid="gathering-shortlisted-shop-map-marker"][data-shop-id="{leader_shop_id}"]'
        )
        other_marker = self.page.locator(
            f'[data-testid="gathering-shortlisted-shop-map-marker"][data-shop-id="{other_shop_id}"]'
        )
        expect(leader_marker).to_be_visible()
        expect(other_marker).to_be_visible()

        leader_icon_class = leader_marker.evaluate("el => el.className")
        other_icon_class = other_marker.evaluate("el => el.className")
        self.assertIn("gathering-shortlisted-shop-map-marker-icon--leader", leader_icon_class)
        self.assertNotIn("gathering-shortlisted-shop-map-marker-icon--selected", leader_icon_class)
        self.assertIn("gathering-shortlisted-shop-map-marker-icon--selected", other_icon_class)
        self.assertNotIn("gathering-shortlisted-shop-map-marker-icon--leader", other_icon_class)

    def test_gathering_screens_persistent_primary_nav_meets_44px_and_is_keyboard_operable(
        self,
    ) -> None:
        """ADR-0059 (2026-09-16, 束A) replaces ADR-0054 decision 1's single,
        render-mode-independent candidate-gathering-entry chip on these
        three organizer screens with a render-mode-specific pair:
        candidate-primary-nav-bar (unconditional under
        mapPrimaryTouchLayout) and candidate-primary-nav-menu-toggle ->
        -menu-panel (unconditional under twoColumnLayout) -- both
        contracts/candidate-search-browser-interface.yaml's own
        gatheringEntry.mobileBar/menuToggle requirement paragraphs
        (2026-09-16) state this holds on these same three screens, not only
        on the candidate-search screen itself. candidate-gathering-entry
        itself is now the *opposite* of ADR-0054 decision 1's rule here --
        entry.requirement (2026-09-16) explicitly excludes these three
        screens ("redundant... on a screen that already is that gathering")
        -- this test also asserts its absence, a regression a silently-
        still-present chip would previously have passed unnoticed. None of
        the new elements carry ``data-gathering-control-purpose`` (plain
        navigation elements, mirroring the retired chip's own precedent),
        so none is caught by ``_assert_all_declared_gathering_controls_meet_
        44px``'s purpose-based scan above.
        """
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("常設ナビの確認会")
        urls = [
            f"{self.dsl.base_url}/gatherings/",
            f"{self.dsl.base_url}/gatherings/new/",
            f"{self.dsl.base_url}/gatherings/{gathering_id}/",
        ]

        def _assert_44px_and_tabbable(locator, label: str) -> None:
            expect(locator).to_be_visible()
            self._assert_tabbable(locator, label)
            box = locator.bounding_box()
            self.assertIsNotNone(box, f"{label} has no bounding box")
            self.assertGreaterEqual(box["width"], MINIMUM_TARGET_PX, label)
            self.assertGreaterEqual(box["height"], MINIMUM_TARGET_PX, label)

        mobile_width, mobile_height, mobile_label = GATHERING_CONTROL_SIZE_VIEWPORTS[0]
        self.page.set_viewport_size({"width": mobile_width, "height": mobile_height})
        for url in urls:
            with self.subTest(viewport=mobile_label, url=url):
                self.page.goto(url)
                bar = by_test_id(self.page, "candidate-primary-nav-bar")
                expect(bar).to_be_visible()
                for test_id in (
                    "candidate-primary-nav-search",
                    "candidate-primary-nav-gathering",
                    "candidate-primary-nav-account",
                ):
                    _assert_44px_and_tabbable(
                        by_test_id(self.page, test_id), f"{test_id} ({mobile_label}, {url})"
                    )
                expect(by_test_id(self.page, "candidate-gathering-entry")).to_have_count(0)

        desktop_width, desktop_height, desktop_label = GATHERING_CONTROL_SIZE_VIEWPORTS[1]
        self.page.set_viewport_size({"width": desktop_width, "height": desktop_height})
        for url in urls:
            with self.subTest(viewport=desktop_label, url=url):
                self.page.goto(url)
                toggle = by_test_id(self.page, "candidate-primary-nav-menu-toggle")
                _assert_44px_and_tabbable(
                    toggle, f"candidate-primary-nav-menu-toggle ({desktop_label}, {url})"
                )
                toggle.press("Enter")
                panel = by_test_id(self.page, "candidate-primary-nav-menu-panel")
                expect(panel).to_be_visible()
                for test_id in (
                    "candidate-primary-nav-menu-search",
                    "candidate-primary-nav-menu-gathering",
                ):
                    _assert_44px_and_tabbable(
                        by_test_id(self.page, test_id), f"{test_id} ({desktop_label}, {url})"
                    )
                expect(by_test_id(self.page, "candidate-gathering-entry")).to_have_count(0)

    def test_b_gathering_dashboard_delete_confirmation_is_keyboard_operable(self) -> None:
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("削除確認の確認会（キャンセル）")

        delete_open = by_test_id(self.page, "gathering-delete-open")
        self._assert_tabbable(delete_open, "gathering-delete-open")
        delete_open.press("Enter")
        expect(by_test_id(self.page, "gathering-delete-confirm-dialog")).to_be_attached()

        delete_cancel = by_test_id(self.page, "gathering-delete-cancel")
        self._assert_tabbable(delete_cancel, "gathering-delete-cancel")
        delete_cancel.press("Enter")
        expect(by_test_id(self.page, "gathering-delete-confirm-dialog")).to_have_count(0)

        # A second, throwaway gathering exercises the completing (confirm)
        # half of this same two-step control, leaving the cancel path above
        # non-destructive.
        self._create_gathering_via_ui("削除確認の確認会（実行）")
        delete_open_2 = by_test_id(self.page, "gathering-delete-open")
        self._assert_tabbable(delete_open_2, "gathering-delete-open")
        delete_open_2.press("Enter")
        delete_confirm = by_test_id(self.page, "gathering-delete-confirm")
        self._assert_tabbable(delete_confirm, "gathering-delete-confirm")
        delete_confirm.press("Enter")
        expect(self.page).to_have_url(f"{self.dsl.base_url}/gatherings/")

    def test_c_gathering_dashboard_phase_is_never_shown_as_raw_enum_text(self) -> None:
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("表示enum確認会（ダッシュボード）", candidate_date_count=1)
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(self.page)

        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()
        # ADR-0063 decision 1 (2026-09-19): the phase badge itself is gone
        # for this one phase, not merely re-labelled -- a direct regression
        # check on that presenceRule change, since this test's own purpose
        # (phase never shown as raw enum text) is closest in spirit to
        # catching a badge that silently came back showing the raw value.
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_count(0)
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(self.page)
        # ADR-0063 decision 3: sweeps every one of shopSelectionPanel's own
        # tabs too -- each reveals different visible text (schedule/answers/
        # links) this scan had never reached while phase is SELECTING_SHOP.
        for tab_test_id in (
            "gathering-shop-select-tab-schedule",
            "gathering-shop-select-tab-answers",
            "gathering-shop-select-tab-links",
        ):
            by_test_id(self.page, tab_test_id).click()
            self._assert_no_forbidden_enum_token_is_visible_standalone_text(self.page)
        # SELECTING_SHOP's own shop-vote tallies (WANT_TO_GO/OK_TO_GO) and
        # FINALIZED are not reached here -- both need a shopId sourced from
        # candidate-search-browser-interface.yaml's own gatheringMode/
        # recommendation population, a screen outside this file's
        # four-screen scope (class docstring).

    def test_gth_leading_candidate_date_does_not_expose_raw_response_enum_text(self) -> None:
        """ADR-0020 decision 4(d), applied to ADR-0060 decision 7's new
        最有力 mark (gathering-candidate-date's data-current-leader /
        responseTable.leaderSummary): renders only once at least one
        candidate date actually leads -- a closed disclosure opened before
        being measured (FR-013) -- and reuses the existing enum-token scan
        unchanged. This is a regression gate on gathering.js's already-
        established GOING/MAYBE/NOT_GOING translation, not a new
        forbidden-token addition (adding new tokens is a human-language
        judgment, ADR-0020 decision 4(d)'s own note, not a tester decision).
        """
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("最有力の確認会", candidate_date_count=2)
        link_url = self._issue_participant_link_url()
        participant_page = self._open_participant_view(link_url)
        by_test_id(participant_page, "gathering-schedule-response-option").first.click()

        self.page.reload()
        expect(
            self.page.locator(
                '[data-testid="gathering-candidate-date"][data-current-leader="true"]'
            )
        ).to_have_count(1)
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(self.page)

    def test_e_gathering_dashboard_controls_meet_44px_minimum_target(self) -> None:
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self._create_gathering_via_ui(
                f"サイズ確認会（ダッシュボード）{label}", candidate_date_count=1
            )
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"SCHEDULING at {label}"
            )

            by_test_id(self.page, "gathering-candidate-date").click()
            by_test_id(self.page, "gathering-confirm-date-select").click()
            expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"SELECTING_SHOP, shopTab at {label}"
            )
            # ADR-0063 decision 3: each of shopSelectionPanel's other 3
            # tabs reveals its own controls (candidateDateList's tentative-
            # select/removal, responseTable has none of its own, linksTab's
            # own participantLinkCopy) -- swept in turn the same way
            # FINALIZED's own links-open state is swept elsewhere in this
            # file.
            for tab_test_id in (
                "gathering-shop-select-tab-schedule",
                "gathering-shop-select-tab-answers",
                "gathering-shop-select-tab-links",
            ):
                by_test_id(self.page, tab_test_id).click()
                self._assert_all_declared_gathering_controls_meet_44px(
                    self.page, f"SELECTING_SHOP, {tab_test_id} at {label}"
                )
            by_test_id(self.page, "gathering-shop-select-tab-shop").click()

            by_test_id(self.page, "gathering-delete-open").click()
            expect(by_test_id(self.page, "gathering-delete-confirm-dialog")).to_be_attached()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"delete-confirm dialog open at {label}"
            )

    # --- participantAnswer --------------------------------------------------

    def test_b_participant_answer_controls_are_keyboard_operable(self) -> None:
        """ADR-0061 decision 3 replaces this test's old answerLater/
        peekResults tail (both retired) with daySkip/dayPrevious/dayList's
        own item -- the default context viewport (no explicit ``viewport``,
        >=1024px) puts dayList in its wide, always-visible sidebar shape
        (``DAY_LIST_WIDE_LAYOUT_QUERY``), so no sheet needs opening here.
        3 candidate dates (d0/d1/d2, startAt ascending): answering d0 auto-
        advances past it (responseOptions.requiredOutcome), so d0's own
        gathering-schedule-question is no longer in the DOM afterwards
        (scheduleQuestion.cardinality: exactly one reachable at a time) --
        its recorded response is instead read back from its own dayList
        row (dayList.item.attributes.yourResponse, always present
        regardless of which date is current).
        """
        link_url = self._build_participant_link(candidate_date_count=3)
        page = self._open_participant_view(link_url)
        day_items = by_test_id(page, "gathering-participant-day-item")
        d0, d1, d2 = (day_items.nth(i).get_attribute("data-candidate-date-id") for i in range(3))

        # d0 is current first (ensureCurrentCandidateDateId's own default:
        # the first not-yet-answered date) -- dayPrevious is disabled here.
        expect(by_test_id(page, "gathering-participant-answer-previous")).to_be_disabled()

        option = by_test_id(page, "gathering-schedule-response-option").first
        self._assert_tabbable(option, "gathering-schedule-response-option")
        response_value = option.get_attribute("data-response-value")
        option.press("Enter")
        expect(
            page.locator(
                f'[data-testid="gathering-participant-day-item"][data-candidate-date-id="{d0}"]'
            )
        ).to_have_attribute("data-your-response", response_value)
        # Auto-advance moved the currently reachable date to d1.
        expect(by_test_id(page, "gathering-schedule-question").first).to_have_attribute(
            "data-candidate-date-id", d1
        )

        name_open = by_test_id(page, "gathering-participant-name-open")
        self._assert_tabbable(name_open, "gathering-participant-name-open")
        name_open.press("Enter")
        expect(by_test_id(page, "gathering-participant-name-input")).to_be_visible()
        by_test_id(page, "gathering-participant-name-input").fill("キーボードさん")
        name_submit = by_test_id(page, "gathering-participant-name-submit")
        self._assert_tabbable(name_submit, "gathering-participant-name-submit")
        name_submit.press("Enter")
        expect(by_test_id(page, "gathering-participant-name-status")).to_have_attribute(
            "data-participant-named", "true"
        )

        # daySkip: d1 -> d2.
        skip = by_test_id(page, "gathering-participant-answer-skip")
        self._assert_tabbable(skip, "gathering-participant-answer-skip")
        skip.press("Enter")
        expect(by_test_id(page, "gathering-schedule-question").first).to_have_attribute(
            "data-candidate-date-id", d2
        )

        # dayPrevious: d2 -> d1 (enabled here, unlike at d0 above).
        previous = by_test_id(page, "gathering-participant-answer-previous")
        expect(previous).to_be_enabled()
        self._assert_tabbable(previous, "gathering-participant-answer-previous")
        previous.press("Enter")
        expect(by_test_id(page, "gathering-schedule-question").first).to_have_attribute(
            "data-candidate-date-id", d1
        )

        # dayList's own item: jumps straight to d0.
        target_item = day_items.nth(0)
        self._assert_tabbable(target_item, "gathering-participant-day-item")
        target_item.press("Enter")
        expect(by_test_id(page, "gathering-schedule-question").first).to_have_attribute(
            "data-candidate-date-id", d0
        )

    def test_b_participant_answer_day_list_sheet_toggle_is_keyboard_operable(self) -> None:
        """dayList's narrow-layout entry point (developer-chosen
        presentation, ADR-0061 decision 3 leaves the shape open) carries no
        contract-fixed test id, but ADR-0020 decision 4(c) still requires
        it to be keyboard reachable like any other activatable control --
        closes the same class of gap friction-log.md FR-035 named for the
        retired footer's own controls.
        """
        link_url = self._build_participant_link(candidate_date_count=2)
        page = self._open_participant_view(link_url, viewport=(390, 844))
        wait_for_at_least_one(page, "gathering-schedule-question")

        toggle = by_test_id(page, "gathering-participant-day-list-open")
        self._assert_tabbable(toggle, "gathering-participant-day-list-open")
        toggle.press("Enter")
        sheet_list = by_test_id(page, "gathering-participant-day-list")
        expect(sheet_list).to_be_visible()

        close = by_test_id(page, "gathering-participant-day-list-close")
        self._assert_tabbable(close, "gathering-participant-day-list-close")
        close.press("Enter")
        expect(sheet_list).to_be_hidden()

    def test_c_participant_answer_schedule_values_are_never_shown_as_raw_enum_text(self) -> None:
        link_url = self._build_participant_link(candidate_date_count=2)
        page = self._open_participant_view(link_url)
        wait_for_at_least_one(page, "gathering-schedule-question")
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(page)

        by_test_id(page, "gathering-schedule-response-option").first.click()
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(page)
        # WANT_TO_GO/OK_TO_GO's own shop-vote screen and FINALIZED's own
        # decision screen are not reached here -- same out-of-scope
        # reasoning as
        # test_c_gathering_dashboard_phase_is_never_shown_as_raw_enum_text
        # above (both need a shopId this file does not construct).

    def test_c_participant_answer_respondent_list_never_shows_raw_response_enum_text(
        self,
    ) -> None:
        """respondentList (ADR-0061 decision 2, board's F2: 「空いた所にだれが
        何と答えたかを名前つきで並べる」) translates ScheduleRespondent.response
        the same way yourResponse already does -- extends the existing
        enum-token gate to this newly-declared peer-facing surface. Two
        participant links answer the same candidate date so the list
        actually renders more than this viewer's own entry.
        """
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("respondentList表示enum確認会", candidate_date_count=1)
        first_link_url = self._issue_participant_link_url()
        second_link_url = self._issue_participant_link_url()

        first_page = self._open_participant_view(first_link_url)
        by_test_id(first_page, "gathering-schedule-response-option").first.click()
        expect(by_test_id(first_page, "gathering-schedule-question").first).to_have_attribute(
            "data-your-response", "GOING"
        )
        second_page = self._open_participant_view(second_link_url)
        by_test_id(second_page, "gathering-schedule-response-option").nth(1).click()
        expect(by_test_id(second_page, "gathering-schedule-question").first).to_have_attribute(
            "data-your-response", "MAYBE"
        )

        # Both PUTs have now been confirmed by their own page's DOM (above)
        # before reloading first_page to read back the peer's own entry --
        # not merely issued, avoiding a race against the second PUT's own
        # in-flight request.
        first_page.reload()
        wait_for_at_least_one(first_page, "gathering-schedule-respondent-item")
        expect(by_test_id(first_page, "gathering-schedule-respondent-item")).to_have_count(2)
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(first_page)

    def test_e_participant_answer_day_navigation_controls_meet_44px_minimum_target(
        self,
    ) -> None:
        """ADR-0061 decision 3 replaces this round's target (friction-
        log.md FR-035's own precedent) with daySkip/dayPrevious/dayList:
        the first two already carry data-gathering-control-purpose, so the
        existing generic sweep covers them once visible; dayList's own
        narrow-layout toggle/close (this file's own newly-added test ids,
        see participant.js) are opened first so the sheet's own item
        controls are actually visible before being measured (ADR-0020
        decision 6: a closed sheet is measured only after opening its real
        entry point).
        """
        link_url = self._build_participant_link(candidate_date_count=2)
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            page = self._open_participant_view(link_url, viewport=(width, height))
            wait_for_at_least_one(page, "gathering-schedule-question")
            if width < 1024:
                by_test_id(page, "gathering-participant-day-list-open").click()
                expect(by_test_id(page, "gathering-participant-day-list")).to_be_visible()
            self._assert_all_declared_gathering_controls_meet_44px(page, label)
