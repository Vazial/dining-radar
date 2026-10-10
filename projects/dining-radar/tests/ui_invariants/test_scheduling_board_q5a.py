"""L5 geometry checks for ADR-0076 (KEN-50): the SCHEDULING dashboard returned
to board party2/b2 Q5-a.

Contract source (read-only for this file):
``gathering-scheduling-browser-interface.yaml`` ``organizerDashboard.
schedulingLayout`` (contractVersion 0.32.0) --

- ``candidateDateHeading`` CH-1..CH-5 (the 「候補日 N日」 band and the add button),
- ``responseTableWidth`` RT-1..RT-4 (the people x dates table, full width, outside a card),
- ``participantLinkHeading`` PH-1..PH-4 (the 「回答リンク N本」 band and the issue button),
- ``participantLinkRow`` LK-1..LK-3 (one line per link on the PC).

Same lane and style as ``test_top_bar_row.py`` (ADR-0020 decision 6: DOM and
geometry observations, no business scenario, no Gherkin). Every check reports
*all* broken clauses of a screen in one failure message. Tolerances are the
contract's own (1px).

Scope: organizerDashboard in SCHEDULING with 20 candidate dates, one answered
and one unanswered participant link, at 1440x900 (PC) and 390x844 (phone).
"""

from __future__ import annotations

import os
import re
import unittest

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import expect, sync_playwright

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.dsl.js_browser_mechanics import by_test_id

ORGANIZER_ACCOUNT_REF = "scheduling-q5a-organizer"
ORGANIZER_IDENTIFIER = "synthetic-scheduling-q5a-organizer"
ORGANIZER_PASSWORD = "synthetic-scheduling-q5a-secret"

PC_VIEWPORT = {"width": 1440, "height": 900}
PHONE_VIEWPORT = {"width": 390, "height": 844}
# KEN-50 audit M-1: the clipping sweep also runs at these sizes.
TABLET_VIEWPORT = {"width": 1024, "height": 768}
SMALL_PHONE_VIEWPORT = {"width": 360, "height": 740}
CLIP_VIEWPORTS = (PHONE_VIEWPORT, TABLET_VIEWPORT, PC_VIEWPORT, SMALL_PHONE_VIEWPORT)

CANDIDATE_DATE_COUNT = 20
TOLERANCE = 1  # contract: "tolerance 1px"
BAND_EDGE_GAP = 24  # contract: A.right >= H.right - 24

# One probe returns every rectangle the clauses need; the checks below are
# pure functions of it, so the calibration tests can feed them broken data.
_PROBE_JS = """
() => {
  const q = (id, root) => Array.from((root || document).querySelectorAll(`[data-testid="${id}"]`));
  const rect = (el) => {
    const r = el.getBoundingClientRect();
    return {left: r.left, right: r.right, top: r.top, bottom: r.bottom,
            width: r.width, height: r.height};
  };
  const textRuns = (root, excludes) => {
    const runs = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.textContent.trim() === '') continue;
      if (excludes.some((x) => x && x.contains(node))) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      runs.push({left: r.left, right: r.right, top: r.top, bottom: r.bottom,
                 text: node.textContent.trim()});
    }
    return runs;
  };
  const cardLike = (el) => {
    const cs = getComputedStyle(el);
    const border = ['Top', 'Right', 'Bottom', 'Left'].some(
      (s) => parseFloat(cs[`border${s}Width`]) > 0 && cs[`border${s}Style`] !== 'none'
        && cs[`border${s}Color`] !== 'rgba(0, 0, 0, 0)');
    const radius = ['TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'].some(
      (c) => parseFloat(cs[`border${c}Radius`]) > 0);
    return {border, radius, shadow: cs.boxShadow !== 'none'};
  };
  const info = (el) => {
    const cs = getComputedStyle(el);
    return {rect: rect(el), bg: cs.backgroundColor,
            borderStyle: cs.borderTopStyle, borderWidth: parseFloat(cs.borderTopWidth)};
  };
  const V = document.documentElement.clientWidth;
  const out = {V, pageOverflowsX: document.documentElement.scrollWidth > V + 1};

  const one = (id) => { const l = q(id); return l.length === 1 ? l[0] : null; };

  // --- headings ---
  const heading = (headId, listId, buttonId, extraInsideList) => {
    const H = one(headId), L = one(listId), A = one(buttonId);
    if (!H || !L || !A) {
      return {missing: [!H && headId, !L && listId, !A && buttonId].filter(Boolean)};
    }
    const insideChip = !!A.closest('[data-testid="gathering-candidate-date"]');
    return {
      H: info(H), L: info(L), A: info(A),
      hContainsL: H.contains(L), lContainsH: L.contains(H),
      aInsideH: H.contains(A), aInsideL: L.contains(A), aInsideChip: insideChip,
      labelRuns: textRuns(H, [A]),
      hasFormControlPurpose: H.hasAttribute('data-gathering-control-purpose'),
    };
  };
  out.candidate = heading('gathering-candidate-date-heading', 'gathering-candidate-date-list',
                          'gathering-add-candidate-date-open');
  out.link = heading('gathering-participant-link-heading', 'gathering-participant-link-list',
                     'gathering-participant-link-copy');

  // --- response table ---
  const table = one('gathering-response-table');
  if (!table) {
    out.table = {missing: true};
  } else {
    let T = table;
    for (let e = table.parentElement; e; e = e.parentElement) {
      const ox = getComputedStyle(e).overflowX;
      if (ox === 'auto' || ox === 'scroll') { T = e; break; }
    }
    const cs = getComputedStyle(T);
    const visibleSideBorder = ['Left', 'Right'].some(
      (s) => parseFloat(cs[`border${s}Width`]) > 0 && cs[`border${s}Style`] !== 'none');
    const radius = ['TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'].some(
      (c) => parseFloat(cs[`border${c}Radius`]) > 0);
    const cards = [];
    for (let e = T.parentElement; e && e !== document.body; e = e.parentElement) {
      const c = cardLike(e);
      if (c.border || c.radius || c.shadow) {
        cards.push(e.tagName.toLowerCase() + '.' + (e.className || '') + JSON.stringify(c));
      }
    }
    const headerCells = q('gathering-response-table-header-cell').map((c) => ({
      rect: rect(c), runs: textRuns(c, [])}));
    const names = q('gathering-response-table-row').map((row) => {
      const kids = Array.from(row.children);
      return kids.length ? textRuns(kids[0], []) : [];
    });
    out.table = {
      V, T: rect(T), tableIsT: T === table, visibleSideBorder, radius, cards,
      headerCells, names, scrollLeft: T.scrollLeft,
    };
  }

  // --- link rows ---
  out.rows = q('gathering-participant-link-item').map((I) => {
    const R = q('gathering-participant-link-recopy', I)[0] || null;
    const Vv = q('gathering-participant-link-revoke', I)[0] || null;
    return {
      I: rect(I), R: R && rect(R), V: Vv && rect(Vv),
      runs: textRuns(I, [R, Vv]),
      runsR: R ? textRuns(R, []) : [], runsV: Vv ? textRuns(Vv, []) : [],
    };
  });
  return out;
}
"""


# KEN-50 audit C-1/M-1: nothing may be cut off by an ancestor's overflow, and
# the page must scroll to its end. Rectangles alone cannot see a clip, so this
# probe also reads scrollHeight/clientHeight of each section.
_CLIP_PROBE_JS = """
(formOpen) => {
  const q = (id) => Array.from(document.querySelectorAll(`[data-testid="${id}"]`));
  const rect = (el) => {
    const r = el.getBoundingClientRect();
    return {left: r.left, right: r.right, top: r.top, bottom: r.bottom,
            width: r.width, height: r.height};
  };
  const section = (name, box, last) => {
    if (!box) return {name, missing: true};
    return {name, rect: rect(box), scrollHeight: box.scrollHeight,
            clientHeight: box.clientHeight, last: last ? rect(last) : null};
  };
  const lastOf = (id) => { const l = q(id); return l.length ? l[l.length - 1] : null; };
  const bandOf = (id) => { const h = q(id)[0]; return h ? h.closest('.gth-banded') : null; };
  const table = q('gathering-response-table')[0] || null;
  let scroller = table;
  for (let e = table && table.parentElement; e; e = e.parentElement) {
    const ox = getComputedStyle(e).overflowX;
    if (ox === 'auto' || ox === 'scroll') { scroller = e; break; }
  }
  const tableSection = table ? table.closest('.gth-response-section') : null;
  const sections = [
    section('table scroller', scroller, lastOf('gathering-response-table-row')),
    section('table section', tableSection, lastOf('gathering-response-table-row')),
    section('candidate band', bandOf('gathering-candidate-date-heading'),
            formOpen ? q('gathering-add-candidate-date-form')[0]
                     : lastOf('gathering-candidate-date')),
    section('link band', bandOf('gathering-participant-link-heading'),
            lastOf('gathering-participant-link-item')),
  ];
  const docEl = document.documentElement;
  const before = window.scrollY;
  window.scrollTo(0, docEl.scrollHeight);
  const scrolledTo = window.scrollY;
  // After sliding to the end, the lowest section must be inside the window.
  const lowest = Math.max(...sections.filter((s) => !s.missing).map(
    (s) => s.rect.bottom - (scrolledTo - before)));
  const out = {innerHeight: window.innerHeight, docHeight: docEl.scrollHeight, sections,
               contentBottomAtTop: Math.max(...sections.filter((s) => !s.missing).map(
                 (s) => s.rect.bottom + before)),
               scrolledTo, lowestBottomAtEnd: lowest};
  window.scrollTo(0, before);
  return out;
}
"""


def _within(inner: dict, outer: dict) -> bool:
    return (
        inner["left"] >= outer["left"] - TOLERANCE
        and inner["right"] <= outer["right"] + TOLERANCE
        and inner["top"] >= outer["top"] - TOLERANCE
        and inner["bottom"] <= outer["bottom"] + TOLERANCE
    )


def _center_y(r: dict) -> float:
    return (r["top"] + r["bottom"]) / 2


def _check_heading(
    probe: dict, prefix: str, label: str, list_name: str, findings: list[str]
) -> None:
    """CH-1..5 (prefix ``CH``) and PH-1..4 (prefix ``PH``)."""
    if "missing" in probe:
        findings.append(f"{label}: {prefix} missing element(s): {probe['missing']}")
        return
    h, lst, a = probe["H"]["rect"], probe["L"]["rect"], probe["A"]["rect"]
    if not (h["bottom"] <= lst["top"] + TOLERANCE and h["top"] < lst["top"]):
        findings.append(
            f"{label}: {prefix}-1 heading is not a band above {list_name} "
            f"(H y={h['top']:.1f}..{h['bottom']:.1f}, list top={lst['top']:.1f})"
        )
    if probe["hContainsL"] or probe["lContainsH"]:
        findings.append(f"{label}: {prefix}-1 heading and {list_name} contain one another")
    if not (probe["aInsideH"] and _within(a, h)):
        findings.append(f"{label}: {prefix}-2 button is not inside the band's rectangle")
    if a["right"] < h["right"] - BAND_EDGE_GAP:
        findings.append(
            f"{label}: {prefix}-2 button is not at the band's right "
            f"(A.right={a['right']:.1f}, H.right={h['right']:.1f})"
        )
    if not (h["top"] - TOLERANCE <= _center_y(a) <= h["bottom"] + TOLERANCE):
        findings.append(f"{label}: {prefix}-2 button's vertical centre is outside the band")
    if probe["aInsideL"] or probe["aInsideChip"]:
        findings.append(f"{label}: {prefix}-2 button sits inside {list_name} or a chip")
    runs = probe["labelRuns"]
    if not runs:
        findings.append(f"{label}: {prefix}-3 band has no label text")
    for run in runs:
        if run["right"] > a["left"] + TOLERANCE:
            findings.append(f"{label}: {prefix}-3 label {run['text']!r} is not left of the button")
        if not (a["top"] - TOLERANCE <= _center_y(run) <= a["bottom"] + TOLERANCE):
            findings.append(
                f"{label}: {prefix}-3 label {run['text']!r} is not on the button's line"
            )
    if probe["A"]["borderStyle"] in ("dashed", "dotted") or probe["A"]["borderWidth"] < 1:
        findings.append(
            f"{label}: {prefix}-4 button is not an ordinary bordered button "
            f"(border {probe['A']['borderStyle']} {probe['A']['borderWidth']}px)"
        )
    if prefix == "CH" and a["height"] < 44 - TOLERANCE:
        findings.append(f"{label}: CH-4 button is {a['height']:.1f}px tall (< 44)")
    if probe["H"]["bg"] == probe["L"]["bg"]:
        findings.append(
            f"{label}: {prefix}-5 band background equals {list_name}'s ({probe['H']['bg']})"
        )
    if probe["hasFormControlPurpose"]:
        findings.append(f"{label}: heading carries a control purpose (must be display-only)")


def _check_table(probe: dict, label: str, *, pc: bool, findings: list[str]) -> None:
    if probe.get("missing"):
        findings.append(f"{label}: gathering-response-table is missing")
        return
    t, v = probe["T"], probe["V"]
    # RT-1 and RT-2 apply at both sizes.
    if t["left"] > TOLERANCE or t["right"] < v - TOLERANCE:
        findings.append(
            f"{label}: RT-1 table container is not full width "
            f"(T.left={t['left']:.1f}, T.right={t['right']:.1f}, V={v})"
        )
    if probe["radius"] or probe["visibleSideBorder"]:
        findings.append(f"{label}: RT-2 table container has a radius or side border")
    if probe["cards"]:
        findings.append(f"{label}: RT-2 table sits inside a card-like ancestor: {probe['cards']}")
    if pc:
        for i, cell in enumerate(probe["headerCells"]):
            r = cell["rect"]
            if r["width"] < 44 - TOLERANCE:
                findings.append(f"{label}: RT-3 header cell {i} is {r['width']:.1f}px wide (< 44)")
            for run in cell["runs"]:
                if run["left"] < r["left"] - TOLERANCE or run["right"] > r["right"] + TOLERANCE:
                    findings.append(
                        f"{label}: RT-3 header cell {i} text {run['text']!r} leaves its cell "
                        f"({run['left']:.1f}..{run['right']:.1f} vs "
                        f"{r['left']:.1f}..{r['right']:.1f})"
                    )
    else:
        if t["right"] > v + TOLERANCE:
            findings.append(f"{label}: RT-4 table container exceeds the viewport")
        for i, runs in enumerate(probe["names"]):
            for run in runs:
                if run["left"] < t["left"] - TOLERANCE or run["right"] > t["right"] + TOLERANCE:
                    findings.append(f"{label}: RT-4 name {run['text']!r} (row {i}) is outside T")
        cells = probe["headerCells"]
        if not cells:
            findings.append(f"{label}: RT-4 no header cells")
        else:
            r = cells[0]["rect"]
            if r["left"] < t["left"] - TOLERANCE or r["right"] > t["right"] + TOLERANCE:
                findings.append(f"{label}: RT-4 the first header cell is not wholly inside T")


def _check_rows(rows: list[dict], label: str, *, pc: bool, findings: list[str]) -> None:
    if not rows:
        findings.append(f"{label}: LK no participant-link rows")
        return
    for i, row in enumerate(rows):
        i_, r, v = row["I"], row["R"], row["V"]
        if r is None:
            findings.append(f"{label}: LK row {i} has no recopy button")
            continue
        runs = row["runs"] + row["runsR"] + row["runsV"]
        if pc:
            if i_["bottom"] - i_["top"] > r["bottom"] - r["top"] + 24:
                findings.append(
                    f"{label}: LK-1 row {i} is {i_['bottom'] - i_['top']:.1f}px tall, "
                    f"recopy is {r['bottom'] - r['top']:.1f}px (not one line)"
                )
            for run in runs:
                if not (r["top"] - TOLERANCE <= _center_y(run) <= r["bottom"] + TOLERANCE):
                    findings.append(
                        f"{label}: LK-1 row {i} text {run['text']!r} is off the recopy's line"
                    )
            if v is not None and not (
                _center_y(v) >= r["top"] - TOLERANCE and _center_y(v) <= r["bottom"] + TOLERANCE
            ):
                findings.append(f"{label}: LK-1 row {i} revoke is off the recopy's line")
            own = row["runs"]
            for a, b in zip(own, own[1:], strict=False):
                if b["left"] < a["right"] - TOLERANCE:
                    findings.append(f"{label}: LK-2 row {i} text runs overlap or run backwards")
            if own and own[-1]["right"] > r["left"] + TOLERANCE:
                findings.append(f"{label}: LK-2 row {i} status text is not left of recopy")
            if v is not None and v["left"] < r["right"] - TOLERANCE:
                findings.append(f"{label}: LK-2 row {i} revoke is not right of recopy")
        else:
            for name, box in (("recopy", r), ("revoke", v)):
                if box is not None and not _within(box, i_):
                    findings.append(f"{label}: LK-3 row {i} {name} is not wholly inside the row")
            if i_["right"] > PHONE_VIEWPORT["width"] + TOLERANCE:
                findings.append(f"{label}: LK-3 row {i} overflows the page horizontally")


def _check_clipping(probe: dict, label: str, findings: list[str]) -> None:
    """C-1/M-1: every section shows all of its content, and the page can slide to the end."""
    for sec in probe["sections"]:
        name = sec["name"]
        if sec.get("missing"):
            findings.append(f"{label}: CLIP {name} is missing")
            continue
        if sec["scrollHeight"] > sec["clientHeight"] + TOLERANCE:
            findings.append(
                f"{label}: CLIP {name} is cut off "
                f"(scrollHeight {sec['scrollHeight']} > clientHeight {sec['clientHeight']})"
            )
        if sec["last"] is not None and not (
            sec["last"]["top"] >= sec["rect"]["top"] - TOLERANCE
            and sec["last"]["bottom"] <= sec["rect"]["bottom"] + TOLERANCE
        ):
            findings.append(
                f"{label}: CLIP the last item of {name} lies outside it "
                f"(item bottom {sec['last']['bottom']:.1f} > "
                f"section bottom {sec['rect']['bottom']:.1f})"
            )
    taller = probe["contentBottomAtTop"] > probe["innerHeight"] + TOLERANCE
    if taller and probe["scrolledTo"] <= 0:
        findings.append(
            f"{label}: CLIP content is taller than the window "
            f"({probe['contentBottomAtTop']:.0f} > {probe['innerHeight']}) "
            "but the page does not scroll"
        )
    if probe["lowestBottomAtEnd"] > probe["innerHeight"] + TOLERANCE:
        findings.append(
            f"{label}: CLIP the page cannot slide to the last section "
            f"(its bottom is {probe['lowestBottomAtEnd']:.0f} in a {probe['innerHeight']}px window)"
        )


def _all_findings(probe: dict, label: str, *, pc: bool) -> list[str]:
    findings: list[str] = []
    _check_heading(probe["candidate"], "CH", label, "the date list", findings)
    _check_table(probe["table"], label, pc=pc, findings=findings)
    _check_heading(probe["link"], "PH", label, "the link list", findings)
    _check_rows(probe["rows"], label, pc=pc, findings=findings)
    if probe["pageOverflowsX"]:
        findings.append(f"{label}: the page scrolls horizontally")
    return findings


class SchedulingBoardQ5aTests(StaticLiveServerTestCase):
    """ADR-0076 decisions 1-3 in the SCHEDULING phase."""

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
        self.context = self._browser.new_context(viewport=PC_VIEWPORT)
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dsl = CandidateSearchBrowserDsl(self, self.page, self.base_url)

    # --- Given -----------------------------------------------------------

    def _select_calendar_days(self, count: int) -> None:
        day = "gathering-create-candidate-date-day"
        month_next = "gathering-create-candidate-date-month-next"
        selected = 0
        for _ in range(12):
            cells = self.page.locator(f'[data-testid="{day}"][data-gathering-control-purpose]')
            available = cells.count()
            while selected < count and selected < available:
                cells.nth(selected).click()
                selected += 1
            if selected >= count:
                return
            by_test_id(self.page, month_next).click()
        raise AssertionError(f"could not select {count} candidate days")

    def _given_scheduling_gathering(
        self, dates: int = CANDIDATE_DATE_COUNT, links: int = 2
    ) -> None:
        self.dsl.reset_authentication_state()
        self.context.request.delete(f"{self.base_url}/test-support/gathering-scheduling-state")
        self.dsl.enable_organizer(ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
        self.page.goto(f"{self.base_url}/gatherings/new/")
        by_test_id(self.page, "gathering-create-name-input").fill("板Q5a確認会")
        expect(by_test_id(self.page, "gathering-create-candidate-date-day").first).to_be_visible()
        self._select_calendar_days(dates)
        by_test_id(self.page, "gathering-create-review-open").click()
        expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
        by_test_id(self.page, "gathering-create-submit").click()
        expect(self.page).to_have_url(re.compile(r"/gatherings/[0-9a-fA-F-]+/$"))
        expect(by_test_id(self.page, "gathering-candidate-date").first).to_be_visible()
        # The first link is answered (no revoke), the others stay open (revoke).
        urls = []
        for _ in range(links):
            by_test_id(self.page, "gathering-participant-link-copy").click()
            dialog = by_test_id(self.page, "gathering-participant-link-issue-dialog")
            expect(dialog).to_have_attribute("data-issued-link-url", re.compile(r"^http"))
            urls.append(dialog.get_attribute("data-issued-link-url"))
            by_test_id(self.page, "gathering-participant-link-issue-dialog-close").click()
            expect(dialog).to_have_count(0)
        answerer = self.context.browser.new_context(viewport=PHONE_VIEWPORT)
        try:
            page = answerer.new_page()
            assert urls[0] is not None
            page.goto(urls[0])
            by_test_id(page, "gathering-schedule-response-option").first.click()
            expect(by_test_id(page, "gathering-schedule-question").first).to_have_attribute(
                "data-your-response", re.compile(r".+")
            )
        finally:
            answerer.close()
        self.page.reload()
        expect(by_test_id(self.page, "gathering-participant-link-item")).to_have_count(links)

    def _probe(self, viewport: dict) -> dict:
        self.page.set_viewport_size(viewport)
        self.page.reload()
        expect(by_test_id(self.page, "gathering-participant-link-item").first).to_be_visible()
        return self.page.evaluate(_PROBE_JS)

    def _clip_findings(self, label: str) -> list[str]:
        """Probe every size, with the add-date form closed and then open."""
        findings: list[str] = []
        for viewport in CLIP_VIEWPORTS:
            size = f"{label} {viewport['width']}x{viewport['height']}"
            self._probe(viewport)
            _check_clipping(self.page.evaluate(_CLIP_PROBE_JS, False), size, findings)
            by_test_id(self.page, "gathering-add-candidate-date-open").click()
            expect(by_test_id(self.page, "gathering-add-candidate-date-form")).to_be_visible()
            _check_clipping(
                self.page.evaluate(_CLIP_PROBE_JS, True), f"{size} (add form open)", findings
            )
        return findings

    # --- Then ------------------------------------------------------------

    def test_pc_1440x900(self) -> None:
        self._given_scheduling_gathering()
        findings = _all_findings(self._probe(PC_VIEWPORT), "scheduling 1440x900", pc=True)
        assert not findings, "\n".join(findings)

    def test_phone_390x844(self) -> None:
        self._given_scheduling_gathering()
        findings = _all_findings(self._probe(PHONE_VIEWPORT), "scheduling 390x844", pc=False)
        assert not findings, "\n".join(findings)

    def test_nothing_is_cut_off_with_20_dates_and_9_participants(self) -> None:
        self._given_scheduling_gathering(dates=20, links=9)
        findings = self._clip_findings("20 dates / 9 people")
        assert not findings, "\n".join(findings)

    def test_nothing_is_cut_off_with_14_dates(self) -> None:
        self._given_scheduling_gathering(dates=14)
        findings = self._clip_findings("14 dates")
        assert not findings, "\n".join(findings)

    def test_nothing_is_cut_off_with_3_dates(self) -> None:
        self._given_scheduling_gathering(dates=3)
        findings = self._clip_findings("3 dates")
        assert not findings, "\n".join(findings)


# ---------------------------------------------------------------------------
# Calibration: each checker goes red on one broken property of otherwise clean
# probe data (meta/adr/0065). Pure data, independent of the app.
# ---------------------------------------------------------------------------


def _rect(left: float, top: float, right: float, bottom: float) -> dict:
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }


def _clean_heading() -> dict:
    return {
        "H": {
            "rect": _rect(0, 0, 1000, 60),
            "bg": "rgb(234, 244, 238)",
            "borderStyle": "none",
            "borderWidth": 0,
        },
        "L": {
            "rect": _rect(0, 60, 1000, 200),
            "bg": "rgb(255, 255, 255)",
            "borderStyle": "none",
            "borderWidth": 0,
        },
        "A": {
            "rect": _rect(850, 8, 990, 52),
            "bg": "rgb(255, 255, 255)",
            "borderStyle": "solid",
            "borderWidth": 1,
        },
        "hContainsL": False,
        "lContainsH": False,
        "aInsideH": True,
        "aInsideL": False,
        "aInsideChip": False,
        "labelRuns": [{"left": 10, "right": 80, "top": 20, "bottom": 40, "text": "候補日"}],
        "hasFormControlPurpose": False,
    }


def _clean_table(pc: bool) -> dict:
    cells = [
        {
            "rect": _rect(100 + 44 * i, 0, 144 + 44 * i, 40),
            "runs": [
                {"left": 105 + 44 * i, "right": 139 + 44 * i, "top": 5, "bottom": 20, "text": "9"}
            ],
        }
        for i in range(5)
    ]
    return {
        "T": _rect(0, 0, 1440 if pc else 390, 300),
        "V": 1440 if pc else 390,
        "visibleSideBorder": False,
        "radius": False,
        "cards": [],
        "headerCells": cells,
        "names": [[{"left": 10, "right": 50, "top": 0, "bottom": 10, "text": "あ"}]],
    }


def _clean_row(width: float = 1000) -> dict:
    shift = width - 1000  # a phone-width row keeps its buttons at its right end
    return {
        "I": _rect(0, 0, width, 56),
        "R": _rect(700 + shift, 4, 820 + shift, 52),
        "V": _rect(830 + shift, 4, 920 + shift, 52),
        "runs": [
            {"left": 10, "right": 60, "top": 20, "bottom": 36, "text": "あおい"},
            {"left": 400, "right": 440, "top": 20, "bottom": 36, "text": "まだ"},
        ],
        "runsR": [{"left": 720, "right": 800, "top": 20, "bottom": 36, "text": "コピー"}],
        "runsV": [{"left": 840, "right": 900, "top": 20, "bottom": 36, "text": "取り消す"}],
    }


def _clean_probe(pc: bool = True) -> dict:
    return {
        "candidate": _clean_heading(),
        "link": _clean_heading(),
        "table": _clean_table(pc),
        "rows": [_clean_row(1000 if pc else 390)],
        "pageOverflowsX": False,
    }


def _clean_clip_probe() -> dict:
    def sec(name: str, top: float, bottom: float) -> dict:
        return {
            "name": name,
            "rect": _rect(0, top, 390, bottom),
            "scrollHeight": bottom - top,
            "clientHeight": bottom - top,
            "last": _rect(0, bottom - 40, 390, bottom - 4),
        }

    return {
        "innerHeight": 844,
        "docHeight": 1400,
        "scrolledTo": 556,
        "contentBottomAtTop": 1300,
        "lowestBottomAtEnd": 744,
        "sections": [
            sec("table scroller", 0, 300),
            sec("table section", 0, 300),
            sec("candidate band", 320, 800),
            sec("link band", 820, 1300),
        ],
    }


class Q5aCheckerCalibrationTests(unittest.TestCase):
    def _has(self, probe: dict, clause: str, *, pc: bool = True) -> bool:
        return any(clause in f for f in _all_findings(probe, "synthetic", pc=pc))

    def test_clean_probe_has_no_findings(self) -> None:
        assert _all_findings(_clean_probe(), "synthetic", pc=True) == []
        assert _all_findings(_clean_probe(False), "synthetic", pc=False) == []

    def test_ch_1_heading_below_the_list_is_caught(self) -> None:
        p = _clean_probe()
        p["candidate"]["H"]["rect"] = _rect(0, 150, 1000, 210)
        assert self._has(p, "CH-1")

    def test_ch_2_button_in_the_chip_row_is_caught(self) -> None:
        p = _clean_probe()
        p["candidate"]["aInsideH"] = False
        p["candidate"]["aInsideL"] = True
        assert self._has(p, "CH-2")

    def test_ch_3_label_right_of_the_button_is_caught(self) -> None:
        p = _clean_probe()
        p["candidate"]["labelRuns"][0]["right"] = 900
        assert self._has(p, "CH-3")

    def test_ch_4_dashed_button_is_caught(self) -> None:
        p = _clean_probe()
        p["candidate"]["A"]["borderStyle"] = "dashed"
        assert self._has(p, "CH-4")

    def test_ch_5_band_without_its_own_background_is_caught(self) -> None:
        p = _clean_probe()
        p["candidate"]["H"]["bg"] = p["candidate"]["L"]["bg"]
        assert self._has(p, "CH-5")

    def test_ph_2_button_at_the_left_is_caught(self) -> None:
        p = _clean_probe()
        p["link"]["A"]["rect"] = _rect(300, 8, 440, 52)
        assert self._has(p, "PH-2")

    def test_rt_1_table_inside_the_card_margin_is_caught(self) -> None:
        p = _clean_probe()
        p["table"]["T"] = _rect(120, 0, 1320, 300)
        assert self._has(p, "RT-1")

    def test_rt_2_card_ancestor_is_caught(self) -> None:
        p = _clean_probe()
        p["table"]["cards"] = ["div.gth-pane"]
        assert self._has(p, "RT-2")

    def test_rt_3_narrow_header_cell_is_caught(self) -> None:
        p = _clean_probe()
        p["table"]["headerCells"][0]["rect"] = _rect(100, 0, 130, 40)
        p["table"]["headerCells"][0]["runs"] = []
        assert self._has(p, "RT-3")

    def test_rt_3_header_text_leaving_its_cell_is_caught(self) -> None:
        p = _clean_probe()
        p["table"]["headerCells"][1]["runs"][0]["right"] = 400
        assert self._has(p, "RT-3")

    def test_rt_4_clipped_right_is_caught(self) -> None:
        p = _clean_probe(False)
        p["table"]["T"] = _rect(0, 0, 500, 300)
        assert self._has(p, "RT-4", pc=False)

    def test_lk_1_wrapped_row_is_caught(self) -> None:
        p = _clean_probe()
        p["rows"][0]["I"] = _rect(0, 0, 1000, 120)
        assert self._has(p, "LK-1")

    def test_lk_2_status_right_of_recopy_is_caught(self) -> None:
        p = _clean_probe()
        p["rows"][0]["runs"][1].update(left=740, right=780)
        assert self._has(p, "LK-2")

    def test_lk_3_button_outside_the_row_is_caught(self) -> None:
        p = _clean_probe(False)
        p["rows"][0]["R"] = _rect(300, 4, 500, 52)
        p["rows"][0]["I"] = _rect(0, 0, 390, 56)
        assert self._has(p, "LK-3", pc=False)

    def _clip_has(self, probe: dict) -> bool:
        findings: list[str] = []
        _check_clipping(probe, "synthetic", findings)
        return any("CLIP" in f for f in findings)

    def test_clip_clean_probe_has_no_findings(self) -> None:
        assert not self._clip_has(_clean_clip_probe())

    def test_clip_section_shorter_than_its_content_is_caught(self) -> None:
        p = _clean_clip_probe()
        p["sections"][2]["clientHeight"] = 130
        assert self._clip_has(p)

    def test_clip_last_item_below_its_section_is_caught(self) -> None:
        p = _clean_clip_probe()
        p["sections"][3]["last"] = _rect(0, 1280, 390, 1500)
        assert self._clip_has(p)

    def test_clip_page_that_does_not_scroll_is_caught(self) -> None:
        p = _clean_clip_probe()
        p["scrolledTo"] = 0
        assert self._clip_has(p)

    def test_clip_last_section_out_of_reach_is_caught(self) -> None:
        p = _clean_clip_probe()
        p["lowestBottomAtEnd"] = 1300
        assert self._clip_has(p)

    def test_clip_missing_section_is_caught(self) -> None:
        p = _clean_clip_probe()
        p["sections"][2] = {"name": "candidate band", "missing": True}
        assert self._clip_has(p)
