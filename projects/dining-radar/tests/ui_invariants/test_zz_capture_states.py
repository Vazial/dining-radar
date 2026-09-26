"""Board-conformance capture harness (not an L5 gate).

Only runs when ``DINING_RADAR_CAPTURE_DIR`` is set (orchestrator's own
tool, comparing real screenshots against the board). Under plain
``pytest tests/ui_invariants`` (no env var) the whole class is skipped, so
this file adds no new assertions to L5. Sorted after
``test_render_invariants.py`` by the ``zz`` filename prefix on purpose --
harmless either way (independent test classes), but keeps the gate file
listed first when a human scans this directory.

Each ``test_capture_*`` method owns one board screen and writes every
(state, size) combination for it: a real, viewport-sized screenshot
(``full_page=False`` -- a fixed element's position is only meaningful
against the actual viewport) plus a same-named ``.json`` with every
``[data-testid]`` element's bounding box/visibility/leading text, the
page's horizontal-scroll amount, and the viewport size itself. Given-state
construction (synthetic data, sign-in, gathering create/confirm/vote,
random-seed pinning) mirrors ``test_render_invariants.py``'s own
established patterns; helpers below are independent copies, not imports --
that file's own module docstring already establishes this project's
"developer-maintained, not imported" convention for exactly this kind of
duplication across ``tests/ui_invariants/*.py`` sibling files.
"""

from __future__ import annotations

import json
import os
import re
import unittest
from collections.abc import Callable

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import Locator, Page, Route, expect, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.dsl.js_browser_mechanics import by_test_id, csrf_token, wait_for_at_least_one
from tests.support.business_days import next_business_weekday_iso

CAPTURE_DIR_ENV = "DINING_RADAR_CAPTURE_DIR"
CAPTURE_DIR = os.environ.get(CAPTURE_DIR_ENV)

# 5 phone/tablet portrait sizes plus 1 PC size, per the task's own list.
CAPTURE_SIZES: list[tuple[int, int]] = [
    (360, 740),
    (390, 844),
    (430, 932),
    (768, 1024),
    (1024, 768),
    (1440, 900),
]

ORGANIZER_ACCOUNT_REF = "capture-organizer"
ORGANIZER_IDENTIFIER = "synthetic-capture-organizer"
ORGANIZER_PASSWORD = "synthetic-capture-secret"

# Collects every [data-testid] element in one round trip (not one Python
# call per element -- this file's own combo count makes that slow).
# "Visible" here is a plain, self-contained geometry/style check (rendered
# box has real area and is not display:none/visibility:hidden/opacity:0),
# not Playwright's own stricter is_visible() (ancestor-chain aware) -- good
# enough for a capture/diff tool, not an assertion gate.
_ELEMENT_SNAPSHOT_JS = """
() => {
  const out = [];
  document.querySelectorAll('[data-testid]').forEach((el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    const hidden = style.display === 'none' || style.visibility === 'hidden'
      || parseFloat(style.opacity || '1') === 0;
    const visible = !hidden && rect.width > 0 && rect.height > 0;
    out.push({
      testId: el.getAttribute('data-testid'),
      visible: visible,
      rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
      text: (el.innerText || '').trim().slice(0, 40),
    });
  });
  return out;
}
"""


def _click(locator: Locator) -> None:
    """Prefers a real click (matches genuine user interaction, so a day
    cell/tab/button that only responds to a trusted click still works);
    falls back to a direct DOM ``dispatch_event`` only once a real click
    times out. Real measurement (2026-09-22 rerun) found a blanket
    ``force=True`` unsafe here instead: Playwright's own force click still
    delivers the click to whatever element the browser's real hit-test
    resolves at that screen coordinate, so at a narrow width where a fixed
    bottom nav bar visually overlaps the intended control it silently
    activated the *nav link* underneath instead of erroring loudly.
    ``dispatch_event`` (used only as this fallback) fires the event
    directly on the located element instead, bypassing that hit-test
    entirely.
    """
    try:
        locator.click(timeout=5000)
    except PlaywrightTimeoutError:
        locator.dispatch_event("click")


GivenFn = Callable[[int, int], Page]


@unittest.skipUnless(CAPTURE_DIR, f"set {CAPTURE_DIR_ENV} to enable board-conformance capture")
class BoardConformanceCaptureTests(StaticLiveServerTestCase):
    """One test method per board screen; see module docstring."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        assert CAPTURE_DIR is not None  # guaranteed by skipUnless above
        os.makedirs(CAPTURE_DIR, exist_ok=True)
        cls._previous_base_url = os.environ.get("TDR_ACCEPTANCE_BASE_URL")
        os.environ["TDR_ACCEPTANCE_BASE_URL"] = cls.live_server_url
        cls._previous_async_unsafe = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"
        cls._playwright = sync_playwright().start()
        cls._browser = cls._playwright.chromium.launch()
        cls._index_entries: list[dict[str, str]] = []

    @classmethod
    def tearDownClass(cls) -> None:
        cls._write_index()
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

    @classmethod
    def _write_index(cls) -> None:
        assert CAPTURE_DIR is not None
        index_path = os.path.join(CAPTURE_DIR, "index.json")
        with open(index_path, "w", encoding="utf-8") as fh:
            json.dump(cls._index_entries, fh, ensure_ascii=False, indent=2)

    def setUp(self) -> None:
        self.base_url = os.environ["TDR_ACCEPTANCE_BASE_URL"]
        self.context = self._browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dsl = CandidateSearchBrowserDsl(self, self.page, self.base_url)

    # --- capture plumbing --------------------------------------------------

    def _capture(self, page: Page, screen: str, state: str, width: int, height: int) -> None:
        assert CAPTURE_DIR is not None
        base_name = f"{screen}__{state}__{width}x{height}"
        png_path = os.path.join(CAPTURE_DIR, f"{base_name}.png")
        json_path = os.path.join(CAPTURE_DIR, f"{base_name}.json")
        page.screenshot(path=png_path, full_page=False)
        elements = page.evaluate(_ELEMENT_SNAPSHOT_JS)
        horizontal_scroll = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        payload = {
            "screen": screen,
            "state": state,
            "viewportWidth": width,
            "viewportHeight": height,
            "horizontalScroll": horizontal_scroll,
            "elements": elements,
        }
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        type(self)._index_entries.append(
            {
                "screen": screen,
                "state": state,
                "size": f"{width}x{height}",
                "png": os.path.basename(png_path),
                "json": os.path.basename(json_path),
            }
        )
        # Rewritten after every single capture (not only at tearDownClass)
        # so a mid-run failure still leaves a valid, if partial, index.json.
        type(self)._write_index()

    def _capture_state_across_sizes(self, screen: str, state: str, given: GivenFn) -> None:
        """``given(width, height)`` must set the viewport itself (before
        navigating) and return the ``Page`` to screenshot -- ``self.page``
        for every organizer/signed-in screen, or a fresh per-context page
        for ``participantAnswer`` (no ``organizerSession`` cookie, its own
        contract requirement). Render mode is read once at load/reload,
        never on a live resize, across every screen this file covers
        (``test_render_invariants.py``'s own established reason) -- viewport
        must therefore already be set before ``given`` navigates.
        """
        for width, height in CAPTURE_SIZES:
            page = given(width, height)
            self._capture(page, screen, state, width, height)
            if page is not self.page:
                # A fresh per-size participantAnswer context (see
                # _open_participant_view) -- closed immediately rather than
                # left for addCleanup at test-method end. Real measurement
                # (2026-09-22 rerun) found dozens of these piling up across
                # one test method's own many (state, size) combinations
                # destabilizes the single, class-shared Chromium instance
                # (self._browser) for every later test method in the same
                # run, not only the one that opened them.
                page.context.close()

    # --- shared Given helpers ------------------------------------------------

    def _sign_in_as_organizer(self) -> None:
        self.dsl.reset_authentication_state()
        self._reset_gathering_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)

    def _reset_gathering_state(self) -> None:
        response = self.context.request.delete(
            f"{self.base_url}/test-support/gathering-scheduling-state"
        )
        assert response.status == 204, response.text()

    def _open_account_disclosure(self) -> None:
        mobile_account = by_test_id(self.page, "candidate-primary-nav-account")
        if mobile_account.count() > 0:
            _click(mobile_account)
        else:
            _click(by_test_id(self.page, "candidate-primary-nav-menu-toggle"))

    def _find_longest_candidate_name(self, tries: int = 15) -> str:
        """The longest ``Candidate.name`` seen across ``tries`` fresh,
        non-gathering-mode draws -- a real synthetic shop, not a fabricated
        string (mirrors ``test_render_invariants.py``'s own
        ``_shortlist_the_longest_named_shop`` precedent, applied to the
        plain candidate-search population instead of a gathering's).
        """
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        self.dsl.open_candidate_screen()
        token = csrf_token(self.page)
        longest = ""
        for _ in range(tries):
            response = self.context.request.post(
                f"{self.base_url}/candidate-proposals",
                data={},
                headers={"X-CSRFToken": token},
            )
            assert response.status == 200, response.text()
            for candidate in response.json().get("candidates", []):
                if len(candidate["name"]) > len(longest):
                    longest = candidate["name"]
        assert longest, "no synthetic candidates available to measure"
        return longest

    def _create_selecting_shop_gathering(self, title: str) -> str:
        """Raw-HTTP Given (mirrors ``test_render_invariants.py``'s own
        ``_create_selecting_shop_gathering_via_api``): creates one candidate
        date and confirms it immediately, reaching SELECTING_SHOP -- the
        phase ``candidate-search-browser-interface.yaml``'s gathering mode
        requires. ``self.page`` must already carry the hidden CSRF field
        (any authenticated page render satisfies this).
        """
        token = csrf_token(self.page)
        start_at = next_business_weekday_iso(0)
        create = self.context.request.post(
            f"{self.base_url}/gatherings",
            data={"title": title, "candidateDates": [{"startAt": start_at}]},
            headers={"X-CSRFToken": token},
        )
        assert create.status == 201, create.text()
        gathering = create.json()
        confirm = self.context.request.post(
            f"{self.base_url}/gatherings/{gathering['id']}/confirm-date",
            data={"candidateDateId": gathering["candidateDates"][0]["id"]},
            headers={"X-CSRFToken": token},
        )
        assert confirm.status == 200, confirm.text()
        return gathering["id"]

    def _select_n_calendar_days(
        self, page: Page, day_test_id: str, month_next_test_id: str, count: int
    ) -> None:
        """Selects ``count`` enabled day cells, paging month-next as needed
        (a single-month calendar, ADR-0054 decision 3) -- bounded so a real
        regression (too few enabled days ever appearing) fails fast."""
        selected = 0
        for _ in range(12):
            cells = page.locator(f'[data-testid="{day_test_id}"][data-gathering-control-purpose]')
            available = cells.count()
            while selected < count and selected < available:
                _click(cells.nth(selected))
                selected += 1
            if selected >= count:
                return
            _click(by_test_id(page, month_next_test_id))
        raise AssertionError(f"could not select {count} candidate day(s) for capture")

    def _create_gathering_via_ui(self, title: str, count: int = 1) -> str:
        self.page.goto(f"{self.base_url}/gatherings/new/")
        by_test_id(self.page, "gathering-create-name-input").fill(title)
        expect(by_test_id(self.page, "gathering-create-candidate-date-day").first).to_be_visible()
        self._select_n_calendar_days(
            self.page,
            "gathering-create-candidate-date-day",
            "gathering-create-candidate-date-month-next",
            count,
        )
        _click(by_test_id(self.page, "gathering-create-review-open"))
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
        _click(by_test_id(self.page, "gathering-create-submit"))
        expect(self.page).to_have_url(re.compile(r"/gatherings/[0-9a-fA-F-]+/$"))
        match = re.search(r"/gatherings/([0-9a-fA-F-]+)/", self.page.url)
        assert match is not None, self.page.url
        expect(by_test_id(self.page, "gathering-candidate-date").first).to_be_visible()
        return match.group(1)

    def _confirm_first_candidate_date(self) -> None:
        first_date = by_test_id(self.page, "gathering-candidate-date").first
        _click(first_date)
        # gathering-confirm-date-select only becomes visible/enabled once
        # this candidate date is tentatively selected client-side --
        # waiting for it directly (rather than clicking immediately after
        # the line above) closes a real, observed race under load.
        expect(first_date).to_have_attribute("data-tentative-selected", "true")
        _click(by_test_id(self.page, "gathering-confirm-date-select"))
        expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()

    def _shortlist_n_shops(
        self, gathering_id: str, count: int, prefer_longest: bool = False, tries: int = 25
    ) -> list[dict]:
        """Shortlists ``count`` distinct real synthetic shops. When
        ``prefer_longest``, forces the longest-named shop seen across the
        draws into the shortlist (this screen group's own "含む店名が一番
        長い店" state, per the task's own requirement)."""
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        token = csrf_token(self.page)
        seen: dict[str, dict] = {}
        for _ in range(tries):
            response = self.context.request.post(
                f"{self.base_url}/candidate-proposals",
                data={"gatheringId": gathering_id},
                headers={"X-CSRFToken": token},
            )
            assert response.status == 200, response.text()
            for candidate in response.json()["candidates"]:
                seen[candidate["shopId"]] = candidate
            if len(seen) >= count:
                break
        candidates = list(seen.values())
        assert len(candidates) >= count, f"only found {len(candidates)} distinct synthetic shops"
        if prefer_longest:
            longest = max(candidates, key=lambda c: len(c["name"]))
            rest = [c for c in candidates if c["shopId"] != longest["shopId"]]
            chosen = [longest, *rest[: count - 1]]
        else:
            chosen = candidates[:count]
        put = self.context.request.put(
            f"{self.base_url}/gatherings/{gathering_id}/shortlisted-shops",
            data={"shopIds": [c["shopId"] for c in chosen]},
            headers={"X-CSRFToken": token},
        )
        assert put.status == 200, put.text()
        return chosen

    def _issue_participant_link_url(self) -> str:
        """Opens ``linksTab`` first when present (SELECTING_SHOP phase,
        ADR-0063 decision 3) -- absent during SCHEDULING, where
        participantLinkCopy sits directly on the dashboard.
        """
        links_tab = by_test_id(self.page, "gathering-shop-select-tab-links")
        if links_tab.count() > 0:
            _click(links_tab)
        _click(by_test_id(self.page, "gathering-participant-link-copy"))
        dialog = by_test_id(self.page, "gathering-participant-link-issue-dialog")
        expect(dialog).to_have_attribute("data-issued-link-url", re.compile(r"^http"))
        url = dialog.get_attribute("data-issued-link-url")
        assert url is not None
        _click(by_test_id(self.page, "gathering-participant-link-issue-dialog-close"))
        expect(dialog).to_have_count(0)
        return url

    def _open_participant_view(self, url: str, viewport: tuple[int, int]) -> Page:
        """No ``organizerSession`` cookie -- its own fresh context, closed by
        ``_capture_state_across_sizes`` right after its capture (not
        ``addCleanup``, which would only run at this whole test method's end
        -- see that method's own comment)."""
        context = self._browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        page = context.new_page()
        page.goto(url)
        return page

    def _finalize_first_shop(self) -> None:
        # A caller may have just switched shopSelectionPanel to a different
        # tab (e.g. _issue_participant_link_url's own linksTab) -- shopTab's
        # own finalize radio is not reachable there (ADR-0063 decision 3).
        shop_tab = by_test_id(self.page, "gathering-shop-select-tab-shop")
        if shop_tab.count() > 0:
            _click(shop_tab)
        _click(by_test_id(self.page, "gathering-finalize-shop-select").first)
        _click(by_test_id(self.page, "gathering-finalize-open"))
        _click(by_test_id(self.page, "gathering-finalize-confirm"))
        expect(by_test_id(self.page, "gathering-decision-banner")).to_be_visible()

    # --- signin --------------------------------------------------------------

    def test_capture_signin(self) -> None:
        screen = "signin"

        def given_initial(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self.dsl.reset_authentication_state()
            self.page.goto(f"{self.base_url}/")
            expect(by_test_id(self.page, "auth-sign-in-form")).to_be_visible()
            return self.page

        self._capture_state_across_sizes(screen, "initial", given_initial)

    # --- password_change -------------------------------------------------------

    def test_capture_password_change(self) -> None:
        screen = "password_change"
        self._sign_in_as_organizer()

        def given_initial(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.base_url}{reverse('authentication:password_change')}")
            expect(by_test_id(self.page, "auth-password-change-form")).to_be_visible()
            return self.page

        self._capture_state_across_sizes(screen, "initial", given_initial)

    # --- candidates ------------------------------------------------------------

    def test_capture_candidates(self) -> None:
        screen = "candidates"
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)

        longest_name = self._find_longest_candidate_name()

        def given_normal(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self.dsl.reset_candidate_state()
            self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")

            def _inject_longest_name(route: Route) -> None:
                response = route.fetch()
                body = response.json()
                if body.get("candidates"):
                    body["candidates"][0]["name"] = longest_name
                route.fulfill(response=response, json=body)

            self.page.route("**/candidate-proposals", _inject_longest_name)
            self.dsl.open_candidate_screen()
            self.page.unroute("**/candidate-proposals", _inject_longest_name)
            return self.page

        self._capture_state_across_sizes(screen, "normal", given_normal)

        def given_disclosure(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self.dsl.reset_candidate_state()
            self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
            self.dsl.open_candidate_screen()
            self._open_account_disclosure()
            return self.page

        # Same Given for both named states: whichever disclosure this
        # viewport actually renders (≡ menu on PC, account sheet on
        # mobile) -- the other state name at that same size is therefore
        # a duplicate image, not a silent gap (no control exists there to
        # tell them apart at that width).
        self._capture_state_across_sizes(screen, "menu_open", given_disclosure)
        self._capture_state_across_sizes(screen, "account_sheet_open", given_disclosure)

        def given_gathering_mode(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self.dsl.reset_candidate_state()
            self.dsl.set_candidate_state("GATHERING_OPEN_SHOP_WEEKDAY_MATCH")
            self.dsl.open_candidate_screen()
            self._reset_gathering_state()
            gathering_id = self._create_selecting_shop_gathering("会モード撮影会")
            self.page.goto(f"{self.base_url}/?gatheringId={gathering_id}")
            wait_for_at_least_one(self.page, "candidate-card")
            # Real measurement (2026-09-22): this screen's own gatheringId
            # fetch can still be settling behind an in-flight, about-to-be-
            # replaced first render -- waiting for network idle here (the
            # same pattern this file's own sign_in already relies on)
            # closes that race before a caller clicks a card.
            self.page.wait_for_load_state("networkidle")
            return self.page

        self._capture_state_across_sizes(screen, "gathering_mode", given_gathering_mode)

        def given_gathering_added(width: int, height: int) -> Page:
            given_gathering_mode(width, height)
            toggle = by_test_id(self.page, "candidate-card").first.locator(
                '[data-testid="candidate-card-gathering-toggle"]'
            )
            # dispatch_event directly, not this file's own _click helper's
            # "real click first" default: real measurement (2026-09-22,
            # network-response diagnostics) found a real Playwright click
            # here -- reported successful, actionability checks and all --
            # deep into this file's own long, many-navigation full-suite
            # run repeatedly never actually sent the resulting PUT
            # /shortlisted-shops request at all (not a slow response, an
            # unsent one), narrowest to this one screen's own touch-deck
            # swipe-gesture surface (mapPrimaryTouchLayout,
            # candidate-deck-swipe-surface) at CAPTURE_SIZES' own narrowest
            # width -- consistent with that surface's own gesture handling
            # intercepting a real synthetic pointer sequence before the
            # button's own click listener runs, even though it never does
            # so for a genuine user tap. dispatch_event fires the "click"
            # event directly on the button node instead, bypassing that
            # surface's own pointer/touch handling entirely.
            toggle.dispatch_event("click")
            expect(toggle).to_have_attribute("data-gathering-shortlisted", "true")
            expect(
                by_test_id(self.page, "candidate-gathering-shortlist-toast-return")
            ).to_be_visible()
            return self.page

        self._capture_state_across_sizes(
            screen, "gathering_mode_added_toast", given_gathering_added
        )

        def given_zero(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self.dsl.reset_candidate_state()
            self.dsl.set_candidate_state("NO_RESULTS")
            self.dsl.open_candidate_screen()
            return self.page

        self._capture_state_across_sizes(screen, "zero_results", given_zero)

    # --- gathering_list ----------------------------------------------------------

    def test_capture_gathering_list(self) -> None:
        screen = "gathering_list"
        self._sign_in_as_organizer()

        def given_empty(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            self.page.goto(f"{self.base_url}/gatherings/")
            wait_for_at_least_one(self.page, "gathering-list-empty")
            return self.page

        self._capture_state_across_sizes(screen, "empty", given_empty)

        def given_in_progress(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            self._create_gathering_via_ui("進行中撮影会")
            self.page.goto(f"{self.base_url}/gatherings/")
            wait_for_at_least_one(self.page, "gathering-list-item")
            return self.page

        self._capture_state_across_sizes(screen, "in_progress", given_in_progress)

    # --- gathering_create --------------------------------------------------------

    def test_capture_gathering_create(self) -> None:
        screen = "gathering_create"
        self._sign_in_as_organizer()

        def given_calendar(count: int) -> GivenFn:
            def _given(width: int, height: int) -> Page:
                self.page.set_viewport_size({"width": width, "height": height})
                self.page.goto(f"{self.base_url}/gatherings/new/")
                by_test_id(self.page, "gathering-create-name-input").fill(
                    f"カレンダー撮影会{count}"
                )
                if count > 0:
                    expect(
                        by_test_id(self.page, "gathering-create-candidate-date-day").first
                    ).to_be_visible()
                    self._select_n_calendar_days(
                        self.page,
                        "gathering-create-candidate-date-day",
                        "gathering-create-candidate-date-month-next",
                        count,
                    )
                return self.page

            return _given

        self._capture_state_across_sizes(screen, "calendar_0", given_calendar(0))
        self._capture_state_across_sizes(screen, "calendar_3", given_calendar(3))
        self._capture_state_across_sizes(screen, "calendar_20", given_calendar(20))

        def given_review_dialog(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(f"{self.base_url}/gatherings/new/")
            by_test_id(self.page, "gathering-create-name-input").fill("確認小窓撮影会")
            expect(
                by_test_id(self.page, "gathering-create-candidate-date-day").first
            ).to_be_visible()
            self._select_n_calendar_days(
                self.page,
                "gathering-create-candidate-date-day",
                "gathering-create-candidate-date-month-next",
                3,
            )
            _click(by_test_id(self.page, "gathering-create-review-open"))
            expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
            return self.page

        self._capture_state_across_sizes(screen, "review_dialog", given_review_dialog)

    # --- dashboard_scheduling ----------------------------------------------------

    def test_capture_dashboard_scheduling(self) -> None:
        screen = "dashboard_scheduling"
        self._sign_in_as_organizer()

        def given_3_no_answers(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            gathering_id = self._create_gathering_via_ui("日程調整撮影会3件", count=3)
            self.page.goto(f"{self.base_url}/gatherings/{gathering_id}/")
            expect(by_test_id(self.page, "gathering-phase-indicator")).to_be_visible()
            return self.page

        self._capture_state_across_sizes(screen, "candidate_dates_3_no_answers", given_3_no_answers)

        def given_14_with_answers(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            gathering_id = self._create_gathering_via_ui("日程調整撮影会14件", count=14)
            link_url = self._issue_participant_link_url()
            participant_page = self._open_participant_view(link_url, viewport=(390, 844))
            _click(by_test_id(participant_page, "gathering-schedule-response-option").first)
            expect(
                by_test_id(participant_page, "gathering-schedule-question").first
            ).to_have_attribute("data-your-response", re.compile(r".+"))
            # Not the page being captured this call -- close its own context
            # now (_capture_state_across_sizes only closes the page it
            # actually captures).
            participant_page.context.close()
            self.page.goto(f"{self.base_url}/gatherings/{gathering_id}/")
            expect(by_test_id(self.page, "gathering-phase-indicator")).to_be_visible()
            return self.page

        self._capture_state_across_sizes(
            screen, "candidate_dates_14_with_answers", given_14_with_answers
        )

        def given_link_dialog(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            self._create_gathering_via_ui("リンク発行小窓撮影会")
            self._issue_participant_link_url_leave_open(self.page)
            return self.page

        self._capture_state_across_sizes(screen, "link_issue_dialog", given_link_dialog)

    def _issue_participant_link_url_leave_open(self, page: Page) -> None:
        """Like ``_issue_participant_link_url`` but leaves the dialog open
        (a capture target of its own), instead of closing it."""
        links_tab = by_test_id(page, "gathering-shop-select-tab-links")
        if links_tab.count() > 0:
            _click(links_tab)
        _click(by_test_id(page, "gathering-participant-link-copy"))
        expect(by_test_id(page, "gathering-participant-link-issue-dialog")).to_be_attached()

    # --- dashboard_selecting -------------------------------------------------------

    def test_capture_dashboard_selecting(self) -> None:
        screen = "dashboard_selecting"
        self._sign_in_as_organizer()

        def _new_confirmed_gathering(title: str) -> str:
            gathering_id = self._create_gathering_via_ui(title)
            self._confirm_first_candidate_date()
            return gathering_id

        def given_shops_0(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            _new_confirmed_gathering("店0件撮影会")
            self.page.reload()
            expect(by_test_id(self.page, "gathering-dashboard-confirmed-date")).to_be_visible()
            return self.page

        self._capture_state_across_sizes(screen, "shops_0", given_shops_0)

        def given_shops_1(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            gathering_id = _new_confirmed_gathering("店1件撮影会")
            self._shortlist_n_shops(gathering_id, 1)
            self.page.reload()
            expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
            return self.page

        self._capture_state_across_sizes(screen, "shops_1", given_shops_1)

        def given_shops_5(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            gathering_id = _new_confirmed_gathering("店5件撮影会")
            self._shortlist_n_shops(gathering_id, 5, prefer_longest=True)
            self.page.reload()
            expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
            return self.page

        self._capture_state_across_sizes(screen, "shops_5", given_shops_5)

        for state, tab_test_id in (
            ("tab_shop", "gathering-shop-select-tab-shop"),
            ("tab_schedule", "gathering-shop-select-tab-schedule"),
            ("tab_answers", "gathering-shop-select-tab-answers"),
            ("tab_links", "gathering-shop-select-tab-links"),
        ):

            def given_tab(width: int, height: int, tab_test_id: str = tab_test_id) -> Page:
                given_shops_5(width, height)
                _click(by_test_id(self.page, tab_test_id))
                return self.page

            self._capture_state_across_sizes(screen, state, given_tab)

        def given_shop_selected(width: int, height: int) -> Page:
            given_shops_5(width, height)
            _click(by_test_id(self.page, "gathering-finalize-shop-select").first)
            return self.page

        self._capture_state_across_sizes(screen, "shop_selected", given_shop_selected)

        def given_finalize_dialog(width: int, height: int) -> Page:
            given_shop_selected(width, height)
            _click(by_test_id(self.page, "gathering-finalize-open"))
            expect(by_test_id(self.page, "gathering-finalize-confirm-dialog")).to_be_attached()
            return self.page

        self._capture_state_across_sizes(screen, "finalize_confirm_dialog", given_finalize_dialog)

    # --- dashboard_finalized ---------------------------------------------------

    def test_capture_dashboard_finalized(self) -> None:
        screen = "dashboard_finalized"
        self._sign_in_as_organizer()

        def given_initial(width: int, height: int) -> Page:
            self.page.set_viewport_size({"width": width, "height": height})
            self._reset_gathering_state()
            gathering_id = self._create_gathering_via_ui("確定後撮影会")
            self._confirm_first_candidate_date()
            self._shortlist_n_shops(gathering_id, 1, prefer_longest=True)
            self.page.reload()
            expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
            self._finalize_first_shop()
            return self.page

        self._capture_state_across_sizes(screen, "initial", given_initial)

        def given_answers_open(width: int, height: int) -> Page:
            given_initial(width, height)
            _click(by_test_id(self.page, "gathering-decision-answers-open"))
            return self.page

        self._capture_state_across_sizes(screen, "answers_open", given_answers_open)

        def given_links_open(width: int, height: int) -> Page:
            given_initial(width, height)
            _click(by_test_id(self.page, "gathering-decision-links-open"))
            return self.page

        self._capture_state_across_sizes(screen, "links_open", given_links_open)

    # --- participant -----------------------------------------------------------

    def test_capture_participant(self) -> None:
        screen = "participant"
        self._sign_in_as_organizer()

        def given_schedule(count: int) -> GivenFn:
            def _given(width: int, height: int) -> Page:
                self._reset_gathering_state()
                self._create_gathering_via_ui(f"日程回答撮影会{count}", count=count)
                link_url = self._issue_participant_link_url()
                page = self._open_participant_view(link_url, viewport=(width, height))
                wait_for_at_least_one(page, "gathering-schedule-question")
                return page

            return _given

        self._capture_state_across_sizes(screen, "schedule_3", given_schedule(3))
        self._capture_state_across_sizes(screen, "schedule_14", given_schedule(14))

        def given_day_list_open(width: int, height: int) -> Page:
            self._reset_gathering_state()
            self._create_gathering_via_ui("日一覧撮影会", count=3)
            link_url = self._issue_participant_link_url()
            page = self._open_participant_view(link_url, viewport=(width, height))
            wait_for_at_least_one(page, "gathering-schedule-question")
            if width < 1024:
                _click(by_test_id(page, "gathering-participant-day-list-open"))
                expect(by_test_id(page, "gathering-participant-day-list")).to_be_visible()
            return page

        self._capture_state_across_sizes(screen, "day_list_open", given_day_list_open)

        def given_shop_vote(width: int, height: int) -> Page:
            self._reset_gathering_state()
            gathering_id = self._create_gathering_via_ui("店投票撮影会")
            self._confirm_first_candidate_date()
            self._shortlist_n_shops(gathering_id, 1, prefer_longest=True)
            link_url = self._issue_participant_link_url()
            page = self._open_participant_view(link_url, viewport=(width, height))
            wait_for_at_least_one(page, "gathering-shop-vote-question")
            return page

        self._capture_state_across_sizes(screen, "shop_vote", given_shop_vote)

        def given_decided(width: int, height: int) -> Page:
            self._reset_gathering_state()
            gathering_id = self._create_gathering_via_ui("参加者確定後撮影会")
            self._confirm_first_candidate_date()
            self._shortlist_n_shops(gathering_id, 1)
            # _shortlist_n_shops writes via a raw API call -- self.page still
            # shows the pre-shortlist DOM until reloaded (mirrors
            # test_render_invariants.py's own reload-after-seed discipline).
            self.page.reload()
            expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
            link_url = self._issue_participant_link_url()
            self._finalize_first_shop()
            page = self._open_participant_view(link_url, viewport=(width, height))
            wait_for_at_least_one(page, "gathering-participant-decision")
            return page

        self._capture_state_across_sizes(screen, "decided", given_decided)
