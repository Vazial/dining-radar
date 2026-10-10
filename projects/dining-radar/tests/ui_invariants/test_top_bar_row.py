"""L5 geometry checks for ADR-0075 (KEN-53): the PC top bar row and the
dashboard's return link position.

Contract sources (read-only for this file):
- ``candidate-search-browser-interface.yaml`` ``gatheringEntry.
  primaryNavigationGeometry.topBar`` -- TB-1 (same line), TB-2 (name at the
  left), TB-3 (nothing above the bar row), TB-4 (exactly one h1).
- ``gathering-scheduling-browser-interface.yaml`` ``organizerDashboard.
  headingBar.backLink`` -- BL-1 (above the name), BL-2 (left edges aligned
  within 4px), BL-3 (below the bar row while twoColumnLayout holds).

Same lane and style as ``test_layout_sanity.py`` (ADR-0020 decision 6: DOM and
geometry observations, no business scenario, no Gherkin). The Given-state
builders are an independent copy of that file's, not an import of its test
class (importing a ``TestCase`` would make pytest collect it twice).

Scope (task for KEN-53):
- 1440x900: candidate screen (ordinary and gatheringMode), organizerGatheringList,
  organizerGatheringCreate, organizerDashboard in SCHEDULING / SELECTING_SHOP /
  FINALIZED -> TB-1..TB-4; on the dashboard also BL-1..BL-3.
- 390x844: organizerDashboard in the three phases -> BL-1 and BL-2 only.

Every check reports *all* the broken conditions of a screen in one failure
message (a findings list), so a red run names which clause is broken. No
tolerance is wider than the contract's own (1px; 4px for BL-2).

``TopBarCheckerCalibrationTests`` shows the checkers themselves go red when a
single property of an otherwise clean synthetic bar is broken (ADR-0065).
"""

from __future__ import annotations

import os
import re

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import Locator, Page, expect, sync_playwright

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.dsl.js_browser_mechanics import by_test_id, csrf_token, wait_for_at_least_one

ORGANIZER_ACCOUNT_REF = "top-bar-row-organizer"
ORGANIZER_IDENTIFIER = "synthetic-top-bar-row-organizer"
ORGANIZER_PASSWORD = "synthetic-top-bar-row-secret"

PC_VIEWPORT = {"width": 1440, "height": 900}
PHONE_VIEWPORT = {"width": 390, "height": 844}

MENU_TOGGLE = "candidate-primary-nav-menu-toggle"
TOP_LABEL = "gathering-dashboard-top-label"
DASHBOARD_TITLE = "gathering-dashboard-title"
DASHBOARD_BACK = "gathering-dashboard-back"

TOLERANCE = 1  # contract: "Tolerances are 1px unless stated"
BL2_TOLERANCE = 4  # contract: BL-2 "<= 4px"

# TB-3: visible element that carries its own text or is operable, listed when
# its bottom edge is at or above ``top``. S, T, their descendants and their
# enclosing ancestors are not "above" the bar. Elements wholly outside the
# viewport and 1px clip-style screen-reader text are not visible.
_ABOVE_THE_BAR_JS = """
(s, t) => {
  const top = Math.min(s.getBoundingClientRect().top, t.getBoundingClientRect().top);
  const operable = (el) => el.matches(
    'a[href],button,input:not([type=hidden]),select,textarea,summary,' +
    '[role=button],[role=link],[tabindex]:not([tabindex="-1"])'
  );
  const found = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (s.contains(el) || t.contains(el) || el.contains(s) || el.contains(t)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility !== 'visible' || Number(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    if (r.bottom <= 0 || r.right <= 0 || r.left >= window.innerWidth) continue;
    const ownText = Array.from(el.childNodes).some(
      (n) => n.nodeType === 3 && n.textContent.trim() !== ''
    );
    if (!ownText && !operable(el)) continue;
    if (r.bottom <= top) {
      found.push(
        el.tagName.toLowerCase() +
        (el.getAttribute('data-testid') ? '[' + el.getAttribute('data-testid') + ']' : '') +
        ' bottom=' + r.bottom.toFixed(1) + ' barTop=' + top.toFixed(1)
      );
    }
  }
  return found;
}
"""


# ---------------------------------------------------------------------------
# Checkers (pure observations of the rendered page; used by the screen tests
# and by the calibration tests below).
# ---------------------------------------------------------------------------


def _box(loc: Locator, name: str, label: str, findings: list[str]) -> dict | None:
    """Rendered border box of the single element ``loc``, or None (with a
    finding) when it is absent or not rendered."""
    count = loc.count()
    if count != 1:
        findings.append(f"{label}: expected exactly 1 {name}, found {count}")
        return None
    box = loc.bounding_box()
    if box is None:
        findings.append(f"{label}: {name} is present but has no rendered box")
        return None
    return box


def _check_tb_1_to_3(
    page: Page, s_loc: Locator, t_loc: Locator, s_name: str, label: str, findings: list[str]
) -> None:
    s = _box(s_loc, s_name, label, findings)
    t = _box(t_loc, MENU_TOGGLE, label, findings)
    if s is None or t is None:
        return
    s_top, s_bottom, s_right = s["y"], s["y"] + s["height"], s["x"] + s["width"]
    t_top, t_bottom, t_left = t["y"], t["y"] + t["height"], t["x"]
    s_center = (s_top + s_bottom) / 2
    overlap = s_top < t_bottom and t_top < s_bottom
    center_in = t_top - TOLERANCE <= s_center <= t_bottom + TOLERANCE
    if not (overlap and center_in):
        findings.append(
            f"{label}: TB-1 {s_name} and menuToggle are not on the same line "
            f"(S y={s_top:.1f}..{s_bottom:.1f}, T y={t_top:.1f}..{t_bottom:.1f})"
        )
    if not s_right <= t_left + TOLERANCE:
        findings.append(
            f"{label}: TB-2 {s_name} is not wholly left of menuToggle "
            f"(S.right={s_right:.1f}, T.left={t_left:.1f})"
        )
    above = s_loc.evaluate(_ABOVE_THE_BAR_JS, t_loc.element_handle())
    if above:
        findings.append(f"{label}: TB-3 visible element(s) above the bar row: {above}")


def _check_tb_4(
    page: Page, label: str, findings: list[str], *, s_loc: Locator | None = None
) -> None:
    """Exactly one h1 on the screen. On the dashboard (``s_loc`` given) that
    h1 is gathering-dashboard-title and S itself is not a level-1 heading."""
    h1s = page.locator("h1")
    count = h1s.count()
    if count != 1:
        findings.append(f"{label}: TB-4 expected exactly 1 <h1>, found {count}")
    if s_loc is None:
        return
    if count == 1 and h1s.first.get_attribute("data-testid") != DASHBOARD_TITLE:
        findings.append(f"{label}: TB-4 the single <h1> is not {DASHBOARD_TITLE}")
    if s_loc.count() == 1:
        is_level_one = s_loc.evaluate(
            """el => el.tagName === 'H1' || el.closest('h1') !== null
                 || (el.getAttribute('role') === 'heading'
                     && el.getAttribute('aria-level') === '1')"""
        )
        if is_level_one:
            findings.append(f"{label}: TB-4 {TOP_LABEL} is a level-1 heading")


def _check_back_link(
    page: Page,
    label: str,
    findings: list[str],
    *,
    two_column: bool,
    s_loc: Locator | None = None,
    t_loc: Locator | None = None,
) -> None:
    link = _box(by_test_id(page, DASHBOARD_BACK), DASHBOARD_BACK, label, findings)
    name = _box(by_test_id(page, DASHBOARD_TITLE), DASHBOARD_TITLE, label, findings)
    if link is None or name is None:
        return
    l_top, l_bottom, l_left = link["y"], link["y"] + link["height"], link["x"]
    n_top, n_bottom, n_left = name["y"], name["y"] + name["height"], name["x"]
    if not (l_bottom <= n_top + TOLERANCE and (l_top + l_bottom) / 2 < (n_top + n_bottom) / 2):
        findings.append(
            f"{label}: BL-1 back link is not above the name "
            f"(L y={l_top:.1f}..{l_bottom:.1f}, N y={n_top:.1f}..{n_bottom:.1f})"
        )
    if abs(l_left - n_left) > BL2_TOLERANCE:
        findings.append(
            f"{label}: BL-2 back link left edge is not aligned with the name "
            f"(L.left={l_left:.1f}, N.left={n_left:.1f})"
        )
    if two_column:
        assert s_loc is not None and t_loc is not None
        s = _box(s_loc, TOP_LABEL, label, findings)
        t = _box(t_loc, MENU_TOGGLE, label, findings)
        if s is None or t is None:
            return
        bar_bottom = max(s["y"] + s["height"], t["y"] + t["height"])
        if l_top < bar_bottom - TOLERANCE:
            findings.append(
                f"{label}: BL-3 back link is not below the bar row "
                f"(L.top={l_top:.1f}, bar bottom={bar_bottom:.1f})"
            )


# ---------------------------------------------------------------------------
# Browser harness (independent copy of test_layout_sanity.py's).
# ---------------------------------------------------------------------------


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
        self.base_url = os.environ["TDR_ACCEPTANCE_BASE_URL"]
        self.context = self._browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dsl = CandidateSearchBrowserDsl(self, self.page, self.base_url)


class TopBarRowTests(_BrowserHarness):
    """ADR-0075 decision 1 (TB-1..TB-4) and decision 2 (BL-1..BL-3)."""

    # --- Given-state helpers -------------------------------------------

    def _sign_in_as_organizer(self) -> None:
        self.dsl.reset_authentication_state()
        self.context.request.delete(f"{self.base_url}/test-support/gathering-scheduling-state")
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)

    def _select_first_calendar_day(self, day_test_id: str, month_next_test_id: str) -> None:
        for _ in range(6):
            cells = self.page.locator(
                f'[data-testid="{day_test_id}"][data-gathering-control-purpose]'
            )
            if cells.count() > 0:
                cells.first.click()
                return
            by_test_id(self.page, month_next_test_id).click()
        raise AssertionError(f"no enabled {day_test_id} cell found within 6 months")

    def _create_gathering_via_ui(self, title: str) -> str:
        self.page.goto(f"{self.base_url}/gatherings/new/")
        by_test_id(self.page, "gathering-create-name-input").fill(title)
        expect(
            self.page.locator(
                '[data-testid="gathering-create-candidate-date-day"][data-gathering-control-purpose]'
            ).first
        ).to_be_visible()
        self._select_first_calendar_day(
            "gathering-create-candidate-date-day", "gathering-create-candidate-date-month-next"
        )
        by_test_id(self.page, "gathering-create-review-open").click()
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
        by_test_id(self.page, "gathering-create-submit").click()
        expect(self.page).to_have_url(re.compile(r"/gatherings/[0-9a-fA-F-]+/$"))
        match = re.search(r"/gatherings/([0-9a-fA-F-]+)/", self.page.url)
        assert match is not None, self.page.url
        expect(by_test_id(self.page, "gathering-candidate-date").first).to_be_visible()
        return match.group(1)

    def _seed_one_shortlisted_shop(self, gathering_id: str) -> None:
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING", random_seed=20260922)
        token = csrf_token(self.page)
        propose = self.context.request.post(
            f"{self.base_url}/candidate-proposals",
            data={"gatheringId": gathering_id},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(propose.status, 200, propose.text())
        shop_id = propose.json()["candidates"][0]["shopId"]
        put = self.context.request.put(
            f"{self.base_url}/gatherings/{gathering_id}/shortlisted-shops",
            data={"shopIds": [shop_id]},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(put.status, 200, put.text())

    def _to_selecting_shop(self, title: str) -> str:
        gathering_id = self._create_gathering_via_ui(title)
        by_test_id(self.page, "gathering-candidate-date").click()
        by_test_id(self.page, "gathering-confirm-date-select").click()
        self._seed_one_shortlisted_shop(gathering_id)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
        return gathering_id

    def _to_finalized(self, title: str) -> str:
        gathering_id = self._to_selecting_shop(title)
        by_test_id(self.page, "gathering-finalize-shop-select").check(force=True)
        by_test_id(self.page, "gathering-finalize-open").click()
        by_test_id(self.page, "gathering-finalize-confirm").click()
        expect(by_test_id(self.page, "gathering-decision-banner")).to_be_visible()
        return gathering_id

    # --- assertions ---------------------------------------------------------

    def _assert_pc_top_bar_with_h1_label(self, label: str) -> None:
        """Candidate screen / 会の一覧 / 会をつくる: S is the screen's own h1."""
        findings: list[str] = []
        _check_tb_4(self.page, label, findings)
        h1s = self.page.locator("h1")
        if h1s.count() >= 1:
            _check_tb_1_to_3(
                self.page, h1s.first, by_test_id(self.page, MENU_TOGGLE), "h1", label, findings
            )
        assert not findings, "\n".join(findings)

    def _assert_dashboard(self, ready_test_id: str, label: str) -> None:
        """Dashboard in one phase: TB-1..4 and BL-1..3 at 1440x900, then BL-1/2
        at 390x844 (same gathering, reloaded)."""
        findings: list[str] = []
        top_label = by_test_id(self.page, TOP_LABEL)
        toggle = by_test_id(self.page, MENU_TOGGLE)
        _check_tb_4(self.page, f"{label} 1440x900", findings, s_loc=top_label)
        _check_tb_1_to_3(self.page, top_label, toggle, TOP_LABEL, f"{label} 1440x900", findings)
        _check_back_link(
            self.page,
            f"{label} 1440x900",
            findings,
            two_column=True,
            s_loc=top_label,
            t_loc=toggle,
        )

        self.page.set_viewport_size(PHONE_VIEWPORT)
        self.page.reload()
        expect(by_test_id(self.page, ready_test_id).first).to_be_visible()
        _check_back_link(self.page, f"{label} 390x844", findings, two_column=False)
        assert not findings, "\n".join(findings)

    # --- candidate screen -----------------------------------------------------

    def test_candidate_screen_ordinary(self) -> None:
        self._sign_in_as_organizer()
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING", random_seed=20260927)
        self.page.set_viewport_size(PC_VIEWPORT)
        self.page.goto(f"{self.base_url}/")
        wait_for_at_least_one(self.page, "candidate-card")
        self._assert_pc_top_bar_with_h1_label("candidate-screen 1440x900")

    def test_candidate_screen_gathering_mode(self) -> None:
        self._sign_in_as_organizer()
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        gathering_id = self.dsl.given_a_gathering_with_exactly_one_shortlisted_shop(
            "上部バー確認会モード"
        )
        self.page.set_viewport_size(PC_VIEWPORT)
        self.dsl.open_gathering_mode_from_dashboard(gathering_id)
        wait_for_at_least_one(self.page, "candidate-gathering-mode-band")
        self._assert_pc_top_bar_with_h1_label("candidate-gathering-mode 1440x900")

    # --- 会の一覧 / 会をつくる ---------------------------------------------------

    def test_gathering_list(self) -> None:
        self._sign_in_as_organizer()
        self.page.set_viewport_size(PC_VIEWPORT)
        self._create_gathering_via_ui("上部バー確認一覧")
        self.page.goto(f"{self.base_url}{reverse('gathering:organizer-gathering-list')}")
        wait_for_at_least_one(self.page, "gathering-list-item")
        self._assert_pc_top_bar_with_h1_label("gathering-list 1440x900")

    def test_gathering_create(self) -> None:
        self._sign_in_as_organizer()
        self.page.set_viewport_size(PC_VIEWPORT)
        self.page.goto(f"{self.base_url}/gatherings/new/")
        expect(by_test_id(self.page, "gathering-create-name-input")).to_be_visible()
        self._assert_pc_top_bar_with_h1_label("gathering-create 1440x900")

    # --- 幹事画面の3局面 ----------------------------------------------------------

    def test_dashboard_scheduling(self) -> None:
        self._sign_in_as_organizer()
        self.page.set_viewport_size(PC_VIEWPORT)
        self._create_gathering_via_ui("上部バー日程を聞き中")
        self._assert_dashboard("gathering-candidate-date", "dashboard-scheduling")

    def test_dashboard_selecting_shop(self) -> None:
        self._sign_in_as_organizer()
        self.page.set_viewport_size(PC_VIEWPORT)
        self._to_selecting_shop("上部バー店選び中")
        self._assert_dashboard("gathering-shortlisted-shop-list", "dashboard-selecting-shop")

    def test_dashboard_finalized(self) -> None:
        self._sign_in_as_organizer()
        self.page.set_viewport_size(PC_VIEWPORT)
        self._to_finalized("上部バー確定後")
        self._assert_dashboard("gathering-decision-banner", "dashboard-finalized")


# ---------------------------------------------------------------------------
# Calibration: each checker goes red when one property of a clean synthetic
# bar is broken (meta/adr/0065). Synthetic DOM, not the app, so it is
# independent of the implementation under change.
# ---------------------------------------------------------------------------

_CLEAN = {
    "bar": "display:flex;align-items:center;justify-content:space-between;height:60px;",
    "label": "",
    "toggle": "",
    "extra_above": "",
    "h1_count_extra": "",
    "back": "display:block;height:48px;",
    "name": "display:block;margin:0;",
    "back_left": "0px",
    "name_left": "0px",
}


def _bar_html(**over: str) -> str:
    v = {**_CLEAN, **over}
    return f"""
    <body style="margin:0;font:16px sans-serif">
      {v["extra_above"]}
      <div style="{v["bar"]}">
        <span data-testid="{TOP_LABEL}" style="{v["label"]}">ランチ会</span>
        <button data-testid="{MENU_TOGGLE}" style="width:44px;height:44px;{v["toggle"]}">≡</button>
      </div>
      <a data-testid="{DASHBOARD_BACK}" href="/x"
         style="{v["back"]};margin-left:{v["back_left"]}">‹ ランチ会</a>
      <h1 data-testid="{DASHBOARD_TITLE}" style="{v["name"]};margin-left:{v["name_left"]}">会</h1>
      {v["h1_count_extra"]}
    </body>"""


class TopBarCheckerCalibrationTests(_BrowserHarness):
    def _findings(self, html: str, *, two_column: bool = True) -> list[str]:
        self.page.set_viewport_size(PC_VIEWPORT)
        self.page.set_content(html)
        s = by_test_id(self.page, TOP_LABEL)
        t = by_test_id(self.page, MENU_TOGGLE)
        findings: list[str] = []
        _check_tb_4(self.page, "synthetic", findings, s_loc=s)
        _check_tb_1_to_3(self.page, s, t, TOP_LABEL, "synthetic", findings)
        _check_back_link(self.page, "synthetic", findings, two_column=two_column, s_loc=s, t_loc=t)
        return findings

    def test_clean_bar_has_no_findings(self) -> None:
        assert self._findings(_bar_html()) == []

    def test_tb_1_menu_toggle_on_its_own_row_is_caught(self) -> None:
        html = _bar_html(bar="display:block;", toggle="display:block;margin-left:auto;")
        assert any("TB-1" in f for f in self._findings(html))

    def test_tb_2_name_right_of_toggle_is_caught(self) -> None:
        html = _bar_html(bar=_CLEAN["bar"] + "flex-direction:row-reverse;")
        assert any("TB-2" in f for f in self._findings(html))

    def test_tb_3_element_above_the_bar_is_caught(self) -> None:
        html = _bar_html(extra_above='<p style="margin:0;height:30px">お知らせ</p>')
        assert any("TB-3" in f for f in self._findings(html))

    def test_tb_4_second_h1_is_caught(self) -> None:
        html = _bar_html(h1_count_extra="<h1>もう一つ</h1>")
        assert any("TB-4" in f for f in self._findings(html))

    def test_tb_4_top_label_as_h1_is_caught(self) -> None:
        self.page.set_viewport_size(PC_VIEWPORT)
        self.page.set_content(_bar_html())
        self.page.evaluate(
            f"""() => {{ const s = document.querySelector('[data-testid="{TOP_LABEL}"]');
                       s.setAttribute('role', 'heading'); s.setAttribute('aria-level', '1'); }}"""
        )
        findings: list[str] = []
        _check_tb_4(self.page, "synthetic", findings, s_loc=by_test_id(self.page, TOP_LABEL))
        assert any("TB-4" in f for f in findings)

    def test_bl_1_back_link_below_the_name_is_caught(self) -> None:
        html = _bar_html(back="display:block;height:48px;position:relative;top:120px")
        assert any("BL-1" in f for f in self._findings(html))

    def test_bl_2_misaligned_left_edge_is_caught(self) -> None:
        assert any("BL-2" in f for f in self._findings(_bar_html(back_left="40px")))

    def test_bl_3_back_link_inside_the_bar_row_is_caught(self) -> None:
        html = _bar_html(back="display:block;height:48px;position:relative;top:-70px")
        assert any("BL-3" in f for f in self._findings(html))

    def test_missing_back_link_is_caught(self) -> None:
        self.page.set_viewport_size(PC_VIEWPORT)
        self.page.set_content(_bar_html())
        self.page.evaluate(
            f"""() => document.querySelector('[data-testid="{DASHBOARD_BACK}"]').remove()"""
        )
        findings: list[str] = []
        _check_back_link(self.page, "synthetic", findings, two_column=False)
        assert any(DASHBOARD_BACK in f for f in findings)
