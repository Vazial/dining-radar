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
from datetime import UTC, datetime, timedelta

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

            # Account menu: toggle, sign-out, password-change-open.
            by_test_id(self.page, "auth-account-menu-toggle").click()
            expect(by_test_id(self.page, "auth-sign-out")).to_be_visible()
            self._assert_all_declared_controls_meet_44px(f"account menu open at {label}")
            by_test_id(self.page, "auth-account-menu-toggle").click()

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

    def _create_selecting_shop_gathering_via_api(self, title: str) -> str:
        """Raw-HTTP Given-state builder (mirrors GatheringScreenInvariantTests.
        _seed_one_shortlisted_shop's own precedent of calling public
        gathering-scheduling-api.yaml operations directly via
        self.context.request rather than tests/acceptance/dsl/
        gathering_scheduling_browser.py, which is reserved to tester per
        ADR-0020 decision 6, the same boundary this file's own module
        docstring states). Creates one candidate date tomorrow and
        immediately confirms it, reaching SELECTING_SHOP -- the phase
        gatheringMode.band requires (candidate-search-browser-interface.yaml
        gatheringMode.band's own gatingcondition is
        response.gatheringContext non-null, which candidate-proposals only
        returns once a gatheringId names a gathering past SCHEDULING).
        ``self.page`` must already be on an organizer-authenticated page
        carrying the hidden CSRF field (the candidate screen itself, reached
        via sign_in, satisfies this -- home.html's own
        auth-account-menu-toggle sits behind the same hidden token
        organizer_dashboard.html's `<div hidden>{% csrf_token %}</div>`
        exposes).
        """
        token = csrf_token(self.page)
        tomorrow = (datetime.now(UTC) + timedelta(days=3)).strftime("%Y-%m-%dT12:00:00Z")
        create_response = self.context.request.post(
            f"{self.dsl.base_url}/gatherings",
            data={"title": title, "candidateDates": [{"startAt": tomorrow}]},
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

    def test_gathering_mode_band_and_persistent_nav_meet_44px_and_are_keyboard_operable(
        self,
    ) -> None:
        """New controls this integration round adds to this screen that
        friction-log.md FR-035's gate never covered: candidate-gathering-
        mode-band (会モードの帯, this screen's sole return path back to the
        gathering, ADR-0054 decision 4 -- see candidate-search-browser-
        interface.yaml's gatheringMode.band.navigation) and this screen's
        own copy of the persistent two-location nav (ADR-0054 decision 1:
        "ランチ候補をさがす"/"ランチ会", added to web/templates/web/home.html
        this same integration round). Neither carries
        data-candidate-control-purpose (both are plain `<a href>` navigation
        elements per this contract's own precedent, outside
        allCandidateScreenFormControlsMustDeclarePurpose's scan -- see
        gatheringEntry.entry.requirement/gatheringMode.band.navigation), so
        neither is caught by test_e_activatable_controls_meet_44px_minimum_
        target's purpose-based scan above; this test measures all three
        directly instead, mirroring GatheringScreenInvariantTests.
        test_gathering_screens_persistent_primary_nav_meets_44px_and_is_
        keyboard_operable's identical reasoning for candidate-gathering-
        entry on the organizer-facing screens.
        """
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        self.dsl.open_candidate_screen()
        gathering_id = self._create_selecting_shop_gathering_via_api("会UI不変量の確認会")

        for width, height, label in CONTROL_SIZE_VIEWPORTS:
            with self.subTest(viewport=label):
                self.page.set_viewport_size({"width": width, "height": height})
                self.page.goto(f"{self.dsl.base_url}/?gatheringId={gathering_id}")
                band = by_test_id(self.page, "candidate-gathering-mode-band")
                expect(band).to_be_visible()
                self._assert_tabbable(band, f"candidate-gathering-mode-band at {label}")
                band_box = band.bounding_box()
                self.assertIsNotNone(band_box, f"band has no bounding box ({label})")
                self.assertGreaterEqual(band_box["width"], MINIMUM_TARGET_PX, label)
                self.assertGreaterEqual(band_box["height"], MINIMUM_TARGET_PX, label)

                for test_id, label_class in (
                    ("candidate-gathering-entry", "candidate-gathering-entry-label"),
                    (None, "gathering-primary-nav-label"),
                ):
                    entry = (
                        by_test_id(self.page, test_id)
                        if test_id
                        else self.page.locator(".gathering-primary-nav-link--current")
                    )
                    expect(entry).to_be_visible()
                    entry_label = test_id or "gathering-primary-nav-link"
                    self._assert_tabbable(entry, f"{entry_label} at {label}")
                    entry_box = entry.bounding_box()
                    self.assertIsNotNone(entry_box, f"{test_id} has no bounding box ({label})")
                    self.assertGreaterEqual(entry_box["width"], MINIMUM_TARGET_PX, label)
                    self.assertGreaterEqual(entry_box["height"], MINIMUM_TARGET_PX, label)
                    label_node = entry.locator(f".{label_class}")
                    self.assertNotEqual(
                        (label_node.text_content() or "").strip(),
                        "",
                        f"{test_id or 'gathering-primary-nav-link'} label text empty ({label})",
                    )


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
        """
        copy_control = by_test_id(self.page, "gathering-participant-link-copy")
        copy_control.click()
        expect(copy_control).to_have_attribute("data-issued-link-url", re.compile(r"^http"))
        url = copy_control.get_attribute("data-issued-link-url")
        assert url is not None
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

        submit = by_test_id(self.page, "gathering-create-submit")
        self._assert_tabbable(submit, "gathering-create-submit")
        submit.press("Enter")
        expect(self.page).to_have_url(re.compile(r"/gatherings/[0-9a-fA-F-]+/$"))

        # cancel, exercised on a second, fresh instance of this screen.
        self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
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

        day_cell = self._first_enabled_day_cell(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
        )
        selected_iso = day_cell.get_attribute("data-date")
        day_cell.click()
        self.assertEqual(day_cell.get_attribute("data-selected"), "true")

        remove_selected = self.page.locator(
            '[data-testid="gathering-create-candidate-date-remove-selected"]'
        ).first
        self._assert_tabbable(remove_selected, "gathering-create-candidate-date-remove-selected")
        remove_selected.press("Enter")
        expect(
            self.page.locator(
                f'[data-testid="gathering-create-candidate-date-day"][data-date="{selected_iso}"]'
            )
        ).to_have_attribute("data-selected", "false")
        self.assertEqual(
            self.page.locator(
                '[data-testid="gathering-create-candidate-date-remove-selected"]'
            ).count(),
            0,
        )

    def test_e_gathering_create_calendar_navigation_and_remove_selected_meet_44px_minimum_target(
        self,
    ) -> None:
        self._sign_in_as_organizer()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.dsl.base_url}/gatherings/new/")
            day_cell = self._first_enabled_day_cell(
                self.page,
                "gathering-create-candidate-date-day",
                "gathering-create-candidate-date-month-next",
            )
            day_cell.click()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"with a remove-selected control shown at {label}"
            )

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
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "SELECTING_SHOP"
        )

        copy_control = by_test_id(self.page, "gathering-participant-link-copy")
        self._assert_tabbable(copy_control, "gathering-participant-link-copy")
        copy_control.press("Enter")
        expect(copy_control).to_have_attribute("data-issued-link-url", re.compile(r"^http"))

        # shopSelectionEntry.open: only tabbability/activation is asserted
        # here. Its requiredOutcome navigates to
        # candidate-search-browser-interface.yaml's own gatheringMode screen
        # -- a screen outside this file's four-screen scope (class
        # docstring) -- so this file does not follow it there or assert its
        # contents.
        shortlist_open = by_test_id(self.page, "gathering-shortlist-open")
        self._assert_tabbable(shortlist_open, "gathering-shortlist-open")
        url_before = self.page.url
        shortlist_open.press("Enter")
        self.page.wait_for_timeout(500)
        self.assertNotEqual(self.page.url, url_before, "gathering-shortlist-open did not navigate")

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
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "SELECTING_SHOP"
        )
        expect(
            self.page.locator(
                '[data-testid="gathering-candidate-date"][data-confirmed="true"] '
                '[data-testid="gathering-candidate-date-remove"]'
            )
        ).to_have_count(0)

    def test_b_gathering_dashboard_finalize_confirmation_is_keyboard_operable(self) -> None:
        """ADR-0054 decision 5 / ADR-0056 decision 11 (2026-09-12): finalize
        is now a 4-part open/confirm-dialog(with a 3-row changes table)/
        confirm/cancel flow, the same shape deleteGathering already uses --
        FR-035's gate must cover these newly-declared operational controls
        (gathering-finalize-open/-confirm/-cancel) the same way it already
        covers gathering-delete-open/-confirm/-cancel.
        """
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("確定フローの確認会")
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "SELECTING_SHOP"
        )
        self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()

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
        expect(by_test_id(self.page, "gathering-finalize-confirm-changes")).to_be_visible()

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

    def test_gathering_screens_persistent_primary_nav_meets_44px_and_is_keyboard_operable(
        self,
    ) -> None:
        """ADR-0054 decision 1 (2026-09-12, human decision): "ランチ候補を
        さがす"/"ランチ会" stay reachable, at a real tap-target size, from
        every organizer-facing gathering screen -- fixing the production
        report "会に入ると出られない". candidate-gathering-entry carries no
        ``data-gathering-control-purpose`` (a plain navigation-only ``<a>``,
        contracts/candidate-search-browser-interface.yaml's own
        gatheringEntry.entry.requirement), so it is not caught by
        ``_assert_all_declared_gathering_controls_meet_44px``'s purpose-based
        scan above -- this test measures it directly instead, on all three
        organizer screens this round adds it to.
        """
        self._sign_in_as_organizer()
        gathering_id = self._create_gathering_via_ui("常設ナビの確認会")
        urls = [
            f"{self.dsl.base_url}/gatherings/",
            f"{self.dsl.base_url}/gatherings/new/",
            f"{self.dsl.base_url}/gatherings/{gathering_id}/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.page.goto(url)
                entry = by_test_id(self.page, "candidate-gathering-entry")
                expect(entry).to_be_visible()
                self._assert_tabbable(entry, "candidate-gathering-entry")
                box = entry.bounding_box()
                self.assertIsNotNone(box, f"candidate-gathering-entry has no bounding box ({url})")
                self.assertGreaterEqual(box["width"], MINIMUM_TARGET_PX)
                self.assertGreaterEqual(box["height"], MINIMUM_TARGET_PX)
                label = entry.locator(".candidate-gathering-entry-label")
                self.assertNotEqual(
                    (label.text_content() or "").strip(), "", f"label text empty ({url})"
                )

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
        expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
            "data-gathering-phase", "SELECTING_SHOP"
        )
        self._assert_no_forbidden_enum_token_is_visible_standalone_text(self.page)
        # SELECTING_SHOP's own shop-vote tallies (WANT_TO_GO/OK_TO_GO) and
        # FINALIZED are not reached here -- both need a shopId sourced from
        # candidate-search-browser-interface.yaml's own gatheringMode/
        # recommendation population, a screen outside this file's
        # four-screen scope (class docstring).

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
            expect(by_test_id(self.page, "gathering-phase-indicator")).to_have_attribute(
                "data-gathering-phase", "SELECTING_SHOP"
            )
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"SELECTING_SHOP at {label}"
            )

            by_test_id(self.page, "gathering-delete-open").click()
            expect(by_test_id(self.page, "gathering-delete-confirm-dialog")).to_be_attached()
            self._assert_all_declared_gathering_controls_meet_44px(
                self.page, f"delete-confirm dialog open at {label}"
            )

    # --- participantAnswer --------------------------------------------------

    def test_b_participant_answer_controls_are_keyboard_operable(self) -> None:
        link_url = self._build_participant_link()
        page = self._open_participant_view(link_url)

        option = by_test_id(page, "gathering-schedule-response-option").first
        self._assert_tabbable(option, "gathering-schedule-response-option")
        response_value = option.get_attribute("data-response-value")
        option.press("Enter")
        expect(by_test_id(page, "gathering-schedule-question").first).to_have_attribute(
            "data-your-response", response_value
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

        answer_later = by_test_id(page, "gathering-participant-answer-later")
        self._assert_tabbable(answer_later, "gathering-participant-answer-later")
        answer_later.press("Enter")
        expect(by_test_id(page, "gathering-participant-answer-later-confirmation")).to_be_attached()

        peek = by_test_id(page, "gathering-participant-peek-results")
        self._assert_tabbable(peek, "gathering-participant-peek-results")
        peek.press("Enter")
        expect(by_test_id(page, "gathering-schedule-tally").first).to_be_visible()

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

    def test_e_participant_answer_footer_controls_meet_44px_minimum_target(self) -> None:
        """Primary target of this round (friction-log.md FR-035):
        ``participant.js``'s ``renderFooter()`` used to push the "あとで
        答える" confirmation ``<p>`` into the same flex row (``.gth-foot``)
        as the two footer buttons, as a third flex sibling with no
        ``flex-basis``/``flex-grow`` of its own -- squeezing both
        ``flex: 1`` buttons' own width well under 44px once the
        confirmation text is showing. Exercised both before and after that
        confirmation appears, at two widths (``GATHERING_CONTROL_SIZE_VIEWPORTS``).
        """
        link_url = self._build_participant_link()
        for width, height, label in GATHERING_CONTROL_SIZE_VIEWPORTS:
            page = self._open_participant_view(link_url, viewport=(width, height))
            wait_for_at_least_one(page, "gathering-participant-answer-later")
            self._assert_all_declared_gathering_controls_meet_44px(
                page, f"before answer-later at {label}"
            )

            by_test_id(page, "gathering-participant-answer-later").click()
            expect(
                by_test_id(page, "gathering-participant-answer-later-confirmation")
            ).to_be_attached()
            self._assert_all_declared_gathering_controls_meet_44px(
                page, f"after answer-later confirmation shown at {label}"
            )

    def test_e_answer_later_confirmations_overlapping_surface_and_peek_are_keyboard_operable(
        self,
    ) -> None:
        """2026-09-13 integration-round fixes, both newly covered here
        (friction-log.md FR-035's own recurrence -- this file previously had
        no test exercising either): (1) the answerLater confirmation's own
        overlapping surface (``.gth-overlay``, ADR-0055 decision 3's "重なる
        別の面") was mouse-only -- a keyboard-only participant had no way to
        dismiss it at all before this round's fix added a
        tabindex/role="button"/Enter-Space handler to the scrim; (2) that
        same scrim used to sit above *every* other control at a higher
        z-index, including 結果をのぞく (gathering-participant-peek-results,
        a read-only, non-destructive control this round's fix deliberately
        keeps reachable regardless of any open overlay) -- a real
        integration defect this round found via
        ``test_gth_answer_later_and_peek_results_are_functional`` (a
        30-second Playwright actionability timeout, ".gth-overlay
        intercepts pointer events"), fixed by giving peekResults a higher
        stacking order than the scrim.
        """
        link_url = self._build_participant_link()
        page = self._open_participant_view(link_url)
        wait_for_at_least_one(page, "gathering-participant-answer-later")

        by_test_id(page, "gathering-participant-answer-later").click()
        overlay = page.locator(".gth-overlay")
        confirmation = by_test_id(page, "gathering-participant-answer-later-confirmation")
        expect(confirmation).to_be_visible()
        box = confirmation.bounding_box()
        self.assertIsNotNone(box, "answerLater confirmation has no bounding box")
        self.assertGreater(box["width"], 0)
        self.assertGreater(box["height"], 0)

        # (2) peekResults stays reachable through the still-open overlay --
        # a real click, not merely a tabindex check, since this is exactly
        # the actionability failure the integration round reproduced.
        peek = by_test_id(page, "gathering-participant-peek-results")
        peek.click()
        expect(by_test_id(page, "gathering-schedule-tally").first).to_be_visible()
        # The overlay itself is unaffected by activating peek (peekResults
        # calls no public operation and does not touch answerLater's own
        # state) -- still open, confirming this was a real click-through fix,
        # not an accidental dismissal.
        expect(confirmation).to_be_visible()

        # (1) the scrim itself is keyboard-tabbable and Enter closes it.
        self._assert_tabbable(overlay, "gathering answerLater overlay scrim")
        overlay.focus()
        page.keyboard.press("Enter")
        expect(confirmation).to_have_count(0)
