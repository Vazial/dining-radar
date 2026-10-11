"""PC geometry invariants for the candidate filter genre row (KEN-57).

The row has one fixed entry point (``ほか N件…``) and a separately
scrollable chip subgroup.  These checks deliberately observe rendered DOM
geometry rather than implementation classes or CSS source so that they fail
when the row regresses to a wrapping flex layout.
"""

from __future__ import annotations

import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import Locator, expect, sync_playwright

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.dsl.js_browser_mechanics import by_test_id

ORGANIZER_ACCOUNT_REF = "genre-row-pc-organizer"
ORGANIZER_IDENTIFIER = "synthetic-genre-row-pc-organizer"
ORGANIZER_PASSWORD = "synthetic-genre-row-pc-secret"

PC_VIEWPORT = {"width": 1450, "height": 900}
OVERFLOW_TOGGLE = "candidate-filter-genre-overflow"
GENRE_OPTION = "candidate-filter-genre-option"
FILTER_PANEL = "candidate-filter-panel"
PANEL_CORNER_EXTRA_INSET = 4


def _box(locator: Locator, label: str) -> dict:
    expect(locator).to_have_count(1)
    box = locator.bounding_box()
    assert box is not None, f"{label} has no rendered box"
    return box


def _assert_boxes_do_not_overlap(box_a: dict, box_b: dict, label: str) -> None:
    a_right = box_a["x"] + box_a["width"]
    a_bottom = box_a["y"] + box_a["height"]
    b_right = box_b["x"] + box_b["width"]
    b_bottom = box_b["y"] + box_b["height"]
    overlap_x = box_a["x"] < b_right and box_b["x"] < a_right
    overlap_y = box_a["y"] < b_bottom and box_b["y"] < a_bottom
    assert not (overlap_x and overlap_y), f"{label}: bounding boxes overlap (a={box_a}, b={box_b})"


class _BrowserHarness(StaticLiveServerTestCase):
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
        self.context = self._browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.base_url = os.environ["TDR_ACCEPTANCE_BASE_URL"]
        self.dsl = CandidateSearchBrowserDsl(self, self.page, self.base_url)

    def _open_genre_panel(self) -> None:
        self.page.set_viewport_size(PC_VIEWPORT)
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("GENRE_ORDER_BY_COUNT", random_seed=20261011)
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.open_candidate_screen_at_two_column_viewport()
        # The shared acceptance helper also asserts the historical
        # character-length genre order.  KEN-57 observes geometry only; use
        # the public control directly so that this invariant remains
        # independent of that unrelated ordering assertion.
        by_test_id(self.page, "candidate-filter-open").click()
        expect(by_test_id(self.page, FILTER_PANEL)).to_be_visible()


class GenreRowPcTests(_BrowserHarness):
    """KEN-57: the overflow toggle is fixed while only the chip side scrolls."""

    def test_genre_row_is_one_aligned_non_overlapping_pc_lane(self) -> None:
        self._open_genre_panel()

        toggle = by_test_id(self.page, OVERFLOW_TOGGLE)
        options = by_test_id(self.page, GENRE_OPTION)
        scrollable = self.page.locator(".candidate-genre-scrollable")
        panel = by_test_id(self.page, FILTER_PANEL)

        expect(toggle).to_be_visible()
        expect(options.first).to_be_visible()
        expect(scrollable).to_have_count(1)
        # Expand the deterministic five-genre response so the right-hand
        # subgroup has content beyond the PC lane and must scroll.
        toggle.click()
        expect(options).to_have_count(5)
        toggle_box = _box(toggle, OVERFLOW_TOGGLE)
        first_option_box = _box(options.first, "first genre option")

        # (b) Every chip stays on the first row and the chip subgroup really
        # owns horizontal overflow.  A wrap regression creates a second row.
        option_boxes = [
            _box(options.nth(index), f"genre option {index}") for index in range(options.count())
        ]
        first_top = option_boxes[0]["y"]
        first_bottom = first_top + option_boxes[0]["height"]
        for index, option_box in enumerate(option_boxes):
            _assert_boxes_do_not_overlap(
                toggle_box,
                option_box,
                f"overflow toggle and genre option {index}",
            )
            for other_index in range(index):
                _assert_boxes_do_not_overlap(
                    option_boxes[other_index],
                    option_box,
                    f"genre options {other_index} and {index}",
                )
        assert all(
            abs(box["y"] - first_top) <= 1 and abs((box["y"] + box["height"]) - first_bottom) <= 1
            for box in option_boxes
        ), f"genre chips wrapped: {option_boxes!r}"
        # (a) The fixed toggle and the first chip row share a vertical center.
        toggle_center = toggle_box["y"] + toggle_box["height"] / 2
        first_option_center = first_option_box["y"] + first_option_box["height"] / 2
        assert abs(toggle_center - first_option_center) <= 1, (
            "overflow toggle and first genre chip are not on the same row: "
            f"toggle center={toggle_center:.1f}, chip center={first_option_center:.1f}"
        )
        scroll_metrics = scrollable.evaluate(
            "el => ({scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, "
            "scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, "
            "flexWrap: getComputedStyle(el).flexWrap})"
        )
        assert scroll_metrics["scrollWidth"] > scroll_metrics["clientWidth"] + 1, (
            f"genre chip subgroup has no horizontal overflow to scroll: {scroll_metrics!r}"
        )
        assert scroll_metrics["scrollHeight"] <= scroll_metrics["clientHeight"] + 1, (
            f"genre chip subgroup has more than one row: {scroll_metrics!r}"
        )
        assert scroll_metrics["flexWrap"] == "nowrap", scroll_metrics

        # Scrolling the chip side must not move the fixed entry point.
        before_scroll = _box(toggle, OVERFLOW_TOGGLE)
        scrollable.evaluate("el => { el.scrollLeft = el.scrollWidth; }")
        after_scroll = _box(toggle, OVERFLOW_TOGGLE)
        assert abs(after_scroll["x"] - before_scroll["x"]) <= 1
        assert abs(after_scroll["y"] - before_scroll["y"]) <= 1
        assert scrollable.evaluate("el => el.scrollLeft") > 0

        # (c) The open panel may geometrically cover the result surface, but
        # nothing from that surface may paint above it.  Hit-testing points
        # inside the panel catches a transparent/under-z-index panel without
        # mistaking intentional overlay geometry for a defect.
        background_at_panel_points = self.page.evaluate(
            """
            (panel) => {
              const r = panel.getBoundingClientRect();
              const style = getComputedStyle(panel);
              const radius = Math.max(
                parseFloat(style.borderTopLeftRadius),
                parseFloat(style.borderTopRightRadius),
                parseFloat(style.borderBottomLeftRadius),
                parseFloat(style.borderBottomRightRadius),
              );
              const inset = radius + %d;
              const points = [
                [r.left + inset, r.top + inset],
                [r.right - inset, r.top + inset],
                [r.left + inset, r.bottom - inset],
                [r.right - inset, r.bottom - inset],
                [(r.left + r.right) / 2, (r.top + r.bottom) / 2],
              ];
              const result = [];
              for (const [x, y] of points) {
                const top = document.elementFromPoint(x, y);
                if (top && top !== panel && !panel.contains(top)) {
                  const testId = top.getAttribute('data-testid') || '';
                  result.push(`${top.tagName.toLowerCase()}[${testId}] @ ` +
                    `${x.toFixed(1)},${y.toFixed(1)}`);
                }
              }
              return result;
            }
            """
            % PANEL_CORNER_EXTRA_INSET,
            panel.element_handle(),
        )
        assert background_at_panel_points == [], (
            "filter panel does not cover the background at its own hit-test points: "
            f"{background_at_panel_points}"
        )
