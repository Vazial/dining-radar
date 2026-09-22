"""Screen-agnostic, machine-checked layout-sanity invariants.

Human request (orchestrator, 2026-09-22): "細かいレイアウト崩れがたくさんある。
Claude が検知して人間レビューの前に直せないか" -- three concrete examples were
given (a heading crammed against the control row right above/below it, a menu
that opens off-screen, an "ⓘ" button that does nothing when pressed). This
file adds 7 *general* checks that apply to any screen/state/size, rather than
one bespoke assertion per reported symptom -- extending the render-invariant
harness ADR-0020 decision 1 established (``test_render_invariants.py``, this
package's sibling file, which this file does not edit or import test methods
from -- ADR-0020 decision 6 places both files in developer's own maintenance
lane, so a second, independent file here follows the same precedent that
file's own two classes already set for each other).

**Process note, recorded here rather than left silent (P-08's "flag, do not
silently proceed" applied to a process question, not a business one)**:
ADR-0020 decision 2 requires a *new ADR* before decision 4's frozen invariant
list gains a genuinely new category (the procedure ADR-0032 and ADR-0065
each followed for their own additions). The 7 checks below are exactly that
-- a new category, not an implementation detail of an existing one -- and
developer does not author ADRs (``developer.md``'s own "契約ファイルを変更
しない" line; ADR authorship is architect's role, meta/agents.md). This file
was written on direct orchestrator instruction as the investigative step the
task itself describes ("まず検査を書いて...どこが落ちるかを洗い出す...直すか
どうかは orchestrator が人間の合意と照らして決める") -- the same order ADR-0020
itself was born in (developer/orchestrator measurement first, architect's ADR
second). Until an architect writes that follow-up ADR (mirroring ADR-0032/
ADR-0065's own addenda to ADR-0020 decision 4) and a human approves it, the
7 checks below should be read as a *proposed* extension backed by real
measurement, not yet a ratified permanent gate -- even though, mechanically,
every non-``xfail`` assertion in this file already blocks CI today. This
note exists so that fact is visible to whoever reviews the PR, not only to
whoever reads this file's own git history.

Sizes (human decision, this task): 360x740, 390x844, 768x1024, 1440x900 --
one narrow phone, one common phone, one tablet/narrow-desktop boundary, one
desktop, matching this product's own two render-mode breakpoint (64rem =
1024px; ADR-0032/ADR-0049).

Each of the 7 checks operates on "visible elements with their own text, or
that are operable controls" (``_LAYOUT_SCAN_JS``'s own population, computed
once per screen/state/size and shared across checks 1-5 and 6's own
resolution) rather than bespoke per-screen selectors, so the same check code
runs unchanged against every screen this file visits.
"""

from __future__ import annotations

import os
import re

import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import Locator, Page, expect, sync_playwright

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.dsl.js_browser_mechanics import by_test_id, csrf_token, wait_for_at_least_one

ORGANIZER_ACCOUNT_REF = "layout-sanity-organizer"
ORGANIZER_IDENTIFIER = "synthetic-layout-sanity-organizer"
ORGANIZER_PASSWORD = "synthetic-layout-sanity-secret"

# The task's own 4 sizes.
VIEWPORTS = [
    (360, 740, "phone-360x740"),
    (390, 844, "phone-390x844"),
    (768, 1024, "tablet-768x1024"),
    (1440, 900, "desktop-1440x900"),
]

# Real-measurement finding: pytest's own native unittest-subTest reporting
# surfaces a SUBFAILED result for *every* subTest a test method entered
# whenever that method fails at all -- including via a single ``assert``
# placed entirely *outside* every subTest block, after the per-viewport loop
# has already finished -- and each such SUBFAILED counts toward pytest's own
# exit code independently of whether the enclosing test method itself is
# marked ``@pytest.mark.xfail``. That defeated xfail(strict=True)'s own
# purpose here (keeping the suite's exit code green apart from the declared
# xfails), so the per-viewport loops below use a plain ``if True:`` instead
# of ``with self.subTest(...):`` -- each finding string already carries its
# own viewport label, so this loses no diagnostic information.
MIN_GAP_PX = 4.0
TOLERANCE_PX = 1.0

# ---------------------------------------------------------------------------
# Exclusion allowlists. Each entry is one intentional design choice, with its
# own one-line reason -- "除外は「浮かせる層」を明示した一覧で持ち、理由を1行
# ずつ書く" (task instruction). Loosening/adding an entry here is developer's
# ordinary allowlist maintenance (ADR-0020 decision 2's own precedent for
# CONTROL_SIZE_ALLOWLIST_TEST_IDS/FORBIDDEN_INTERNAL_ENUM_TOKENS in this
# package's sibling file), not a change to the 7 checks themselves.

# Check 1 (overlap): elements inside one of these are a deliberately floated
# layer -- allowed to cover whatever sits underneath, but still checked
# against *each other* if two floating elements share the same root.
FLOATING_LAYER_SELECTORS = [
    # desktop >=1024px "≡" dropdown menu -- opens over the page below it.
    ".primary-nav-menu-panel",
    # mobile bottom-sheet account menu -- opens over the bottom nav/page.
    ".primary-nav-account-sheet",
    # "この会に入れました" toast -- floats over the map/card deck.
    ".candidate-gathering-shortlist-toast",
    # mobile filter dropdown -- floats over cards/map below it (desktop:
    # ordinary static flow, so this selector is inert there).
    '[data-testid="candidate-filter-panel"]',
    # card deck floats over the map at narrow widths (map-primary skeleton,
    # ADR-0033/ADR-0049); ordinary static flow at >=64rem.
    ".candidate-deck",
    # gathering small windows/dialogs/sheets -- each intentionally floats
    # over its own dashboard/list/create screen.
    '[data-testid="gathering-participant-link-issue-dialog"]',
    '[data-testid="gathering-finalize-confirm-dialog"]',
    '[data-testid="gathering-delete-confirm-dialog"]',
    '[data-testid="gathering-create-review-dialog"]',
    '[data-testid="gathering-add-candidate-date-calendar"]',
    '[data-testid="gathering-participant-day-list"]',
    # mobile shop-selection sheet floats over the shortlist map (ADR-0062
    # "地図いっぱい" skeleton).
    ".gth-shop-panel",
    # finalized-stage sheet floats over the decided-shop map.
    ".gth-decision-panel",
    # the swipe-position counter ("1/5") is deliberately positioned with a
    # negative top offset over the deck card's own corner (home.html: "its
    # own negative top offset is not clipped by that element's own
    # overflow: hidden").
    ".candidate-deck-position",
    # Real-measurement finding: a fixed bottom nav bar (position: fixed;
    # bottom: 0) is persistent chrome, painted at the same viewport-
    # relative position regardless of scroll -- ordinary page content
    # legitimately, transiently sits in that same screen region as the
    # page scrolls past it (that is what "scrolls under a fixed bar" means)
    # and reads as an "overlap" in any single, unscrolled snapshot, which
    # is all this check takes. Whether the page's own *final* content still
    # ends up hidden behind the bar after scrolling all the way down (the
    # real defect this bar's own body { padding-bottom } CSS rule exists to
    # prevent) is not something a single snapshot can tell apart from that
    # ordinary case -- this is a known, documented gap (would need a
    # scroll-to-bottom re-measurement pass), not a silent exclusion.
    ".primary-nav-bar",
]

# Check 1: map pins/ring-labels are allowed to overlap *each other* (real
# geographic proximity in the data, not a layout bug) -- never excused
# against a non-marker control (e.g. the Leaflet zoom button), which is
# exactly the real defect class ADR-0065's own map-label-vs-zoom-control
# check (test_render_invariants.py) was written against.
MAP_MARKER_SELECTORS = [
    '[data-testid^="candidate-map-marker"]',
    '[data-testid^="candidate-origin-marker"]',
    '[data-testid^="gathering-shortlisted-shop-map-marker"]',
    '[data-testid^="gathering-decision-shop-map-marker"]',
    '[data-testid^="gathering-search-origin-marker"]',
    ".candidate-walking-radius-ring-label-visual",
    # Real-measurement finding: each marker's own inner "visual" circle
    # (Leaflet divIcon html) and the gathering markers' permanent name-tag
    # tooltip carry no data-testid of their own (only the outer icon
    # wrapper does, via setAttribute) -- without these, two *different*
    # markers' own inner spans (never each other's ancestor/descendant)
    # were misread as an unrelated overlap instead of ordinary close-
    # together pins. gth-map-label is still checked against a *non-marker*
    # control (e.g. the Leaflet zoom button) -- only marker-vs-marker pairs
    # are skipped, which is what ADR-0065's own map-label-vs-zoom-control
    # check (test_render_invariants.py) already depends on.
    ".candidate-map-marker-icon",
    ".candidate-map-marker-visual",
    ".candidate-origin-marker-icon",
    ".candidate-origin-marker-visual",
    ".gathering-shortlisted-shop-map-marker-visual",
    ".gathering-decision-shop-map-marker-icon",
    ".gathering-decision-shop-map-marker-visual",
    ".gathering-search-origin-marker-icon",
    ".gathering-search-origin-marker-visual",
    ".gth-map-label",
]

# Check 1: a decorative, pointer-events:none overlay required by contract
# (provider/OSM attribution text) -- excluded from the overlap population
# entirely rather than paired-excluded, since it is *meant* to sit on top of
# the map at all times.
DECORATIVE_SELECTORS = ['[data-testid="candidate-map-attribution"]']

# Check 2 (text clipping): elements excluded from the "content fits without
# scrolling" check, each for its own reason -- not a blanket allowlist.
TEXT_CLIPPING_ALLOW_SELECTORS = [
    ".candidate-genre-scrollable",  # horizontally scrollable genre chip row
    ".candidate-filter-row-chips",  # same row, its own flex/overflow rule
    ".gth-shop-panel-body",  # mobile shop-list sheet's own internal scroll
    # the standard sr-only pattern (visually hidden, kept for assistive
    # tech): its own overflow: hidden + clip: rect(0 0 0 0) is the whole
    # point, not a clipping defect.
    ".visually-hidden",
]

# Check 3 (unintended wrap): controls whose multi-line wrap is an accepted,
# real-measured design (long shop/provider names), not a defect.
WRAP_ALLOW_SELECTORS = [
    ".gth-shop-name",  # long synthetic shop names measured to wrap ~2 lines
]

_LAYOUT_SCAN_JS = r"""
(config) => {
  const floatingSelectors = config.floatingSelectors;
  const mapMarkerSelectors = config.mapMarkerSelectors;
  const decorativeSelectors = config.decorativeSelectors;
  const textClippingAllowSelectors = config.textClippingAllowSelectors;
  const wrapAllowSelectors = config.wrapAllowSelectors;

  function isVisible(el) {
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (parseFloat(style.opacity) === 0) return false;
    // Real-measurement finding: the standard sr-only pattern
    // (.visually-hidden -- position:absolute, 1x1px, clip:rect(0 0 0 0))
    // itself passes the plain width/height check below (1px > 0.5px), and
    // a *descendant* of it reports its own full, unclipped
    // getBoundingClientRect() regardless (an ancestor's own overflow never
    // shrinks what a descendant reports -- the same fact this file's own
    // clip-ancestor logic elsewhere in this codebase already relies on) --
    // together this let an accessibility-only duplicate's own children
    // register as large, out-of-place visible elements (a phantom overlap
    // with the heading above it, a phantom "overflow" past their own
    // 1x1px container), even though nothing sighted users see is affected.
    if (el.closest(".visually-hidden")) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0.5 && rect.height > 0.5;
  }
  function ownText(el) {
    let text = "";
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) text += node.textContent;
    }
    return text.trim();
  }
  function matchesAny(el, selectors) {
    for (const sel of selectors) {
      try {
        if (el.matches(sel)) return true;
      } catch (e) {}
    }
    return false;
  }
  function closestAny(el, selectors) {
    // Walks up one ancestor at a time, checking every selector at each
    // level together (rather than checking one whole selector's own
    // .closest() at a time) -- real-measurement finding: with the latter,
    // an element that itself matches a *later* selector in the list (e.g.
    // its own small floating badge) but also sits inside an *earlier*
    // selector's ancestor (e.g. a large floating container) would resolve
    // to that distant ancestor instead of itself, since the earlier
    // selector's own .closest() walk reaches it first regardless of which
    // match is nearer.
    let node = el;
    while (node) {
      if (matchesAny(node, selectors)) return node;
      node = node.parentElement;
    }
    return null;
  }
  function describe(el) {
    const testid = el.getAttribute("data-testid");
    if (testid) return "testid=" + testid;
    const cls =
      el.className && el.className.toString ? el.className.toString().trim().split(/\s+/)[0] : "";
    return el.tagName.toLowerCase() + (cls ? "." + cls : "");
  }
  function nearestClippingAncestor(el) {
    let node = el.parentElement;
    while (node && node !== document.documentElement) {
      const s = getComputedStyle(node);
      if (s.overflowX !== "visible" || s.overflowY !== "visible") {
        return node;
      }
      node = node.parentElement;
    }
    return null;
  }
  function countTextLines(el) {
    // Range.getClientRects() gives one rect per visually-rendered line of
    // the element's own rendered content -- robust against padding/
    // min-height inflating the box (an <input>/a padded button both read
    // as 1 line here even though their own bounding-box height is taller
    // than one line-height), unlike a height-vs-line-height comparison.
    try {
      const range = document.createRange();
      range.selectNodeContents(el);
      const rects = Array.from(range.getClientRects()).filter(
        (r) => r.width > 0.5 && r.height > 0.5
      );
      if (rects.length === 0) return 1;
      const tops = new Set(rects.map((r) => Math.round(r.top)));
      return tops.size;
    } catch (e) {
      return 1;
    }
  }

  const all = Array.from(document.querySelectorAll("body *"));
  const items = [];
  for (const el of all) {
    if (!isVisible(el)) continue;
    if (matchesAny(el, decorativeSelectors)) continue;
    const own = ownText(el);
    const purposeAttr = Array.from(el.attributes).find(
      (a) => /-control-purpose$/.test(a.name)
    );
    const isControl =
      el.matches("button, a[href], input, select, textarea, summary") || !!purposeAttr;
    if (!own && !isControl) continue;

    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    const floatingRoot = closestAny(el, floatingSelectors);
    const clipAncestor = nearestClippingAncestor(el);
    const clipRect = clipAncestor ? clipAncestor.getBoundingClientRect() : null;

    items.push({
      el: el,
      testid: el.getAttribute("data-testid"),
      tag: el.tagName.toLowerCase(),
      text: own,
      isControl: isControl,
      controlPurpose: purposeAttr ? purposeAttr.value : null,
      href: el.tagName === "A" ? el.getAttribute("href") : null,
      ariaExpanded: el.getAttribute("aria-expanded"),
      ariaControls: el.getAttribute("aria-controls"),
      isHeading: /^H[1-6]$/.test(el.tagName),
      isMapMarkerLike: matchesAny(el, mapMarkerSelectors),
      isTextClippingAllowed: matchesAny(el, textClippingAllowSelectors),
      isWrapAllowed: matchesAny(el, wrapAllowSelectors),
      isFormField: el.matches("input, select, textarea"),
      isSimpleLabelControl: isControl && el.children.length === 0,
      lineCount: isControl && el.children.length === 0 ? countTextLines(el) : 1,
      floatingRoot: floatingRoot,
      rect: {
        x: rect.x,
        y: rect.y,
        right: rect.right,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
      },
      clipAncestorRect: clipRect
        ? { x: clipRect.x, y: clipRect.y, right: clipRect.right, bottom: clipRect.bottom }
        : null,
      clipAncestorDescribe: clipAncestor ? describe(clipAncestor) : null,
      clipAncestorOverflowX: clipAncestor ? getComputedStyle(clipAncestor).overflowX : null,
      clipAncestorOverflowY: clipAncestor ? getComputedStyle(clipAncestor).overflowY : null,
      clientWidth: el.clientWidth,
      scrollWidth: el.scrollWidth,
      clientHeight: el.clientHeight,
      scrollHeight: el.scrollHeight,
      textOverflow: style.textOverflow,
      overflowX: style.overflowX,
      overflowY: style.overflowY,
      whiteSpace: style.whiteSpace,
      lineClamp: style.getPropertyValue("-webkit-line-clamp") || style.webkitLineClamp || "none",
      lineHeightPx: parseFloat(style.lineHeight) || null,
      fontSizePx: parseFloat(style.fontSize) || null,
      describe: describe(el),
    });
  }

  // Check 1: pairwise overlap among the population above.
  const overlaps = [];
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const a = items[i];
      const b = items[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      if (a.isMapMarkerLike && b.isMapMarkerLike) continue;
      if (a.floatingRoot && a.floatingRoot !== b.floatingRoot && !a.floatingRoot.contains(b.el)) {
        continue;
      }
      if (b.floatingRoot && b.floatingRoot !== a.floatingRoot && !b.floatingRoot.contains(a.el)) {
        continue;
      }
      const ra = a.rect;
      const rb = b.rect;
      const ix = Math.min(ra.right, rb.right) - Math.max(ra.x, rb.x);
      const iy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.y, rb.y);
      if (ix > 1 && iy > 1) {
        overlaps.push({ a: a.describe, b: b.describe, ix: ix, iy: iy });
      }
    }
  }

  // Check 5: for each heading, the minimum positive vertical gap to the
  // nearest horizontally-overlapping, non-overlapping item immediately
  // above/below it (same floating layer only -- comparing a base-page
  // heading against a dialog's own unrelated content would be meaningless).
  const headingGaps = [];
  for (const h of items) {
    if (!h.isHeading) continue;
    let minAbove = Infinity;
    let minAboveDesc = null;
    let minBelow = Infinity;
    let minBelowDesc = null;
    for (const other of items) {
      if (other === h) continue;
      if (h.el.contains(other.el) || other.el.contains(h.el)) continue;
      if (h.floatingRoot !== other.floatingRoot) continue;
      const xOverlap =
        Math.min(h.rect.right, other.rect.right) - Math.max(h.rect.x, other.rect.x);
      if (xOverlap <= 1) continue;
      const yOverlap =
        Math.min(h.rect.bottom, other.rect.bottom) - Math.max(h.rect.y, other.rect.y);
      if (yOverlap > 1) continue; // an overlap is check 1's concern, not this one
      if (other.rect.bottom <= h.rect.y) {
        const gap = h.rect.y - other.rect.bottom;
        if (gap < minAbove) {
          minAbove = gap;
          minAboveDesc = other.describe;
        }
      } else if (other.rect.y >= h.rect.bottom) {
        const gap = other.rect.y - h.rect.bottom;
        if (gap < minBelow) {
          minBelow = gap;
          minBelowDesc = other.describe;
        }
      }
    }
    headingGaps.push({
      heading: h.describe,
      gapAbovePx: minAbove === Infinity ? null : minAbove,
      aboveDescribe: minAboveDesc,
      gapBelowPx: minBelow === Infinity ? null : minBelow,
      belowDescribe: minBelowDesc,
    });
  }

  // Currently-open floating layer roots, for check 4's own "does the open
  // menu/dialog/sheet itself stay inside the viewport" half.
  const floatingRoots = [];
  for (const sel of floatingSelectors) {
    let matches;
    try {
      matches = document.querySelectorAll(sel);
    } catch (e) {
      continue;
    }
    for (const node of matches) {
      if (!isVisible(node)) continue;
      const r = node.getBoundingClientRect();
      floatingRoots.push({
        selector: sel,
        describe: describe(node),
        rect: {
          x: r.x,
          y: r.y,
          right: r.right,
          bottom: r.bottom,
          width: r.width,
          height: r.height,
        },
      });
    }
  }

  const cleanItems = items.map((it) => {
    const clean = Object.assign({}, it);
    delete clean.el;
    clean.isFloating = !!it.floatingRoot;
    delete clean.floatingRoot;
    return clean;
  });

  return {
    elements: cleanItems,
    overlaps: overlaps,
    headingGaps: headingGaps,
    floatingRoots: floatingRoots,
    viewport: { width: window.innerWidth, height: window.innerHeight },
  };
}
"""


def _run_layout_scan(page: Page) -> dict:
    return page.evaluate(
        _LAYOUT_SCAN_JS,
        {
            "floatingSelectors": FLOATING_LAYER_SELECTORS,
            "mapMarkerSelectors": MAP_MARKER_SELECTORS,
            "decorativeSelectors": DECORATIVE_SELECTORS,
            "textClippingAllowSelectors": TEXT_CLIPPING_ALLOW_SELECTORS,
            "wrapAllowSelectors": WRAP_ALLOW_SELECTORS,
        },
    )


# --- Per-check assertion helpers: each appends human-readable finding
# strings to a shared list rather than asserting immediately, so one test
# method can run all 5 geometric checks across all 4 sizes and report every
# violation at once (matches the task's own "報告は...一覧で" instruction). ---


def _check_1_overlap(scan: dict, label: str, findings: list[str]) -> None:
    for o in scan["overlaps"]:
        findings.append(
            f"{label} [1.重なり] {o['a']} と {o['b']} が {o['ix']:.1f}x{o['iy']:.1f}px 重なっている"
        )


def _check_2_text_clipping(scan: dict, label: str, findings: list[str]) -> None:
    """Only flags an axis whose own computed ``overflow`` is not
    ``visible`` (real-measurement finding: several icon/label spans have no
    ``overflow`` rule of their own at all, so their content -- e.g. a
    Japanese label a touch taller than its own ``line-height: 1`` box --
    simply spills out visibly rather than being cut off; ``scrollHeight``
    still exceeds ``clientHeight`` there, but nothing is actually clipped,
    so it is not this check's concern).
    """
    for el in scan["elements"]:
        if el["isTextClippingAllowed"]:
            continue
        clamp = el["lineClamp"]
        has_clamp = clamp not in (None, "none", "")
        if el["textOverflow"] == "ellipsis" or has_clamp:
            continue
        overflow_x = el["scrollWidth"] - el["clientWidth"] > 1 and el["overflowX"] != "visible"
        overflow_y = el["scrollHeight"] - el["clientHeight"] > 1 and el["overflowY"] != "visible"
        if overflow_x or overflow_y:
            findings.append(
                f"{label} [2.文字の切れ] {el['describe']} text={el['text'][:30]!r} "
                f"scrollWidth={el['scrollWidth']} clientWidth={el['clientWidth']} "
                f"scrollHeight={el['scrollHeight']} clientHeight={el['clientHeight']}"
            )


def _check_3_unintended_wrap(scan: dict, label: str, findings: list[str]) -> None:
    """Scoped to button/tab/chip-like controls (task's own "ボタン・タブ・
    札・チップ") that are their own simple text leaf (``el.children.length
    === 0`` -- real-measurement finding: a composite control built from an
    icon span + a separately laid-out label span, e.g. the mobile bottom
    nav's own icon-above-label column, or a card that is itself clickable
    but holds many internal rows of real content, is a different and much
    larger shape than "one button/chip's own label wrapped unexpectedly";
    ``Range.getClientRects()`` over the *whole* composite subtree conflates
    "this control legitimately lays out several separate pieces" with "this
    one piece of text wrapped", which this scoping avoids rather than trying
    to reconcile). Also excludes plain form fields (``<input>``/``<select>``/
    ``<textarea>`` -- their own tap-target padding legitimately makes them
    taller than one line-height without their *text* ever wrapping).
    """
    for el in scan["elements"]:
        if not el["isSimpleLabelControl"] or el["isWrapAllowed"] or el["isFormField"]:
            continue
        if el["lineCount"] > 1:
            findings.append(
                f"{label} [3.意図しない折り返し] {el['describe']} text={el['text'][:30]!r} "
                f"lineCount={el['lineCount']} height={el['rect']['height']:.1f}px"
            )


#: Check 4: the mobile card deck's own swipe track (home.html's
#: ``.candidate-deck-viewport``/``candidate-deck-swipe-surface``) is a
#: horizontal carousel -- every card except the one currently showing sits
#: outside its own clipping ancestor's box *by design* (candidate.js slides
#: the whole flex row via ``transform``, revealing one card at a time), not
#: a layout defect. Matched by clip-ancestor description (only elements
#: *clipped by* this container are excused, not the container itself).
CAROUSEL_CLIP_ANCESTOR_DESCRIBE = "testid=candidate-deck-swipe-surface"


def _check_4_overflow(scan: dict, label: str, findings: list[str]) -> None:
    """Real-measurement finding: with no explicit clip ancestor, the
    fallback bound is the viewport -- but an ordinary, longer-than-one-
    screen page always has real content sitting below the *current* fold,
    reachable by an entirely normal vertical scroll (this is not what
    "はみ出し" means; ADR-0065 decision 5(g)'s own existing gate already
    encodes this same asymmetry, gating horizontal overflow only, never
    vertical). The same reasoning applies to a real clip ancestor whose own
    ``overflow`` is ``auto``/``scroll`` (as opposed to ``hidden``/``clip``)
    on a given axis -- a genuinely scrollable panel (e.g. the desktop two-
    column card list) legitimately holds more content than its own visible
    height, reachable the same way. Only an axis that is truly clipped
    (``hidden``/``clip``, or the viewport's own bottom edge) is checked; a
    floating layer (checked separately, ``scan["floatingRoots"]``) still
    gets the full 4-edge check regardless, since it declares no scroll
    affordance of its own.
    """
    viewport = scan["viewport"]
    for el in scan["elements"]:
        if el["clipAncestorDescribe"] == CAROUSEL_CLIP_ANCESTOR_DESCRIBE:
            continue
        rect = el["rect"]
        if el["clipAncestorRect"] is not None:
            bound = el["clipAncestorRect"]
            bound_desc = el["clipAncestorDescribe"]
            check_right = el["clipAncestorOverflowX"] not in ("auto", "scroll")
            check_bottom = el["clipAncestorOverflowY"] not in ("auto", "scroll")
        else:
            bound = {"x": 0, "y": 0, "right": viewport["width"], "bottom": viewport["height"]}
            bound_desc = "viewport"
            check_right = True
            check_bottom = False
        if (
            rect["x"] < bound["x"] - TOLERANCE_PX
            or rect["y"] < bound["y"] - TOLERANCE_PX
            or (check_right and rect["right"] > bound["right"] + TOLERANCE_PX)
            or (check_bottom and rect["bottom"] > bound["bottom"] + TOLERANCE_PX)
        ):
            findings.append(
                f"{label} [4.はみ出し] {el['describe']} rect=({rect['x']:.1f},{rect['y']:.1f})-"
                f"({rect['right']:.1f},{rect['bottom']:.1f}) は {bound_desc} "
                f"({bound['x']:.1f},{bound['y']:.1f})-({bound['right']:.1f},{bound['bottom']:.1f}) "
                "の外に出ている"
            )
    for root in scan["floatingRoots"]:
        r = root["rect"]
        if (
            r["x"] < -TOLERANCE_PX
            or r["y"] < -TOLERANCE_PX
            or r["right"] > viewport["width"] + TOLERANCE_PX
            or r["bottom"] > viewport["height"] + TOLERANCE_PX
        ):
            findings.append(
                f"{label} [4.はみ出し:小窓] {root['describe']} rect=({r['x']:.1f},{r['y']:.1f})-"
                f"({r['right']:.1f},{r['bottom']:.1f}) はビューポート "
                f"{viewport['width']}x{viewport['height']} の外に出ている"
            )


def _check_5_cramped_spacing(scan: dict, label: str, findings: list[str]) -> None:
    for hg in scan["headingGaps"]:
        if hg["gapAbovePx"] is not None and hg["gapAbovePx"] < MIN_GAP_PX:
            findings.append(
                f"{label} [5.窮屈な余白] {hg['heading']} の直前の {hg['aboveDescribe']} との間隔 "
                f"{hg['gapAbovePx']:.1f}px < {MIN_GAP_PX}px"
            )
        if hg["gapBelowPx"] is not None and hg["gapBelowPx"] < MIN_GAP_PX:
            findings.append(
                f"{label} [5.窮屈な余白] {hg['heading']} の直後の {hg['belowDescribe']} との間隔 "
                f"{hg['gapBelowPx']:.1f}px < {MIN_GAP_PX}px"
            )


def _run_checks_1_to_5(page: Page, label: str, findings: list[str]) -> None:
    scan = _run_layout_scan(page)
    _check_1_overlap(scan, label, findings)
    _check_2_text_clipping(scan, label, findings)
    _check_3_unintended_wrap(scan, label, findings)
    _check_4_overflow(scan, label, findings)
    _check_5_cramped_spacing(scan, label, findings)


# --- Check 6: toggle open direction -----------------------------------------
# Restricted, per the task's own wording, to controls that carry
# aria-expanded (this codebase's only two such toggles, confirmed by
# scanning every gathering-*.js/candidate.js file for the literal string):
# the mobile account-sheet toggle (every screen with a primary nav bar) and
# the desktop filter-panel toggle (candidate screen only). The desktop "≡"
# menu is a native <details>/<summary> disclosure -- browsers expose its
# open/closed state to assistive tech without an aria-expanded attribute, so
# it is out of this check's literal scope; noted here rather than silently
# skipped (task's "除外は理由を書く").
ACCOUNT_MENU_TOGGLE_TEST_ID = "candidate-primary-nav-account"
ACCOUNT_MENU_PANEL_ID = "primary-nav-account-sheet"
FILTER_TOGGLE_TEST_ID = "candidate-filter-open"
FILTER_PANEL_TEST_ID = "candidate-filter-panel"


#: Check 6's own anchor tolerance -- how close the panel's near edge must
#: sit to the toggle's own vertical span to count as "opening from the
#: toggle" (real-measurement finding: a viewport-bottom-anchored sheet
#: legitimately rises *from* a toggle that itself sits flush with the
#: viewport bottom, so its own near edge often lands exactly at, not past,
#: the toggle's own far edge -- a strict, zero-tolerance "never overlaps
#: the toggle at all" rule would reject that ordinary bottom-sheet pattern).
#: Real measurement against this codebase's own filter-panel dropdown
#: (home.html's "top: calc(100% + 0.4rem)") found real, deliberate gaps of
#: 8.4px/15.2px at two different widths -- both a deliberate small CSS
#: offset, not a "wrong direction" bug -- so this is set well above either,
#: while a genuine misdirection (this file's own fault-injection test
#: forces one) still lands far outside it (hundreds of px, not tens).
ANCHOR_ADJACENCY_TOLERANCE_PX = 24.0


def _assert_toggle_opens_in_place_and_in_viewport(
    page: Page, toggle: Locator, panel: Locator, label: str, findings: list[str]
) -> None:
    """Check 6: the panel must (1) share some horizontal range with the
    toggle, (2) open in a coherent direction from it, (3) stay inside the
    viewport.

    (2) is deliberately not "never overlaps the toggle at all" -- real
    measurement against this codebase's own mobile account sheet (both it
    and its own toggle are anchored to the viewport bottom, so the sheet's
    own bottom edge sits exactly at the toggle's own bottom edge and rises
    *upward*, overlapping the toggle's box) shows that is too strict for an
    ordinary, non-buggy bottom-sheet pattern. Instead: "opens upward" means
    the panel's own bottom edge sits at-or-within the toggle's own vertical
    span (``ANCHOR_ADJACENCY_TOLERANCE_PX``) while its top extends higher
    than the toggle's top; "opens downward" is the mirror image. A panel
    that lands somewhere unrelated to the toggle entirely (e.g. pinned to
    the opposite screen edge) satisfies neither.
    """
    expect(toggle).to_have_attribute("aria-expanded", "true")
    tbox = toggle.bounding_box()
    pbox = panel.bounding_box()
    if tbox is None or pbox is None:
        findings.append(f"{label} [6.開閉の向き] トグルまたはパネルの矩形が取得できない")
        return
    viewport = page.viewport_size
    x_overlap = min(tbox["x"] + tbox["width"], pbox["x"] + pbox["width"]) - max(
        tbox["x"], pbox["x"]
    )
    if x_overlap <= 0:
        findings.append(
            f"{label} [6.開閉の向き] パネルがトグルと水平方向に重ならない位置に開いている "
            f"(toggle x=[{tbox['x']:.1f},{tbox['x'] + tbox['width']:.1f}], "
            f"panel x=[{pbox['x']:.1f},{pbox['x'] + pbox['width']:.1f}])"
        )
    toggle_top = tbox["y"]
    toggle_bottom = tbox["y"] + tbox["height"]
    panel_top = pbox["y"]
    panel_bottom = pbox["y"] + pbox["height"]

    def _within_toggle_span(y: float) -> bool:
        return (
            (toggle_top - ANCHOR_ADJACENCY_TOLERANCE_PX)
            <= y
            <= (toggle_bottom + ANCHOR_ADJACENCY_TOLERANCE_PX)
        )

    opens_upward = _within_toggle_span(panel_bottom) and panel_top < toggle_top - TOLERANCE_PX
    opens_downward = _within_toggle_span(panel_top) and panel_bottom > toggle_bottom + TOLERANCE_PX
    if not (opens_upward or opens_downward):
        findings.append(
            f"{label} [6.開閉の向き] パネルがトグルの真下・真上のどちらにも落ちていない "
            f"(toggle y=[{toggle_top:.1f},{toggle_bottom:.1f}], "
            f"panel y=[{panel_top:.1f},{panel_bottom:.1f}])"
        )
    if (
        pbox["x"] < -TOLERANCE_PX
        or pbox["y"] < -TOLERANCE_PX
        or pbox["x"] + pbox["width"] > viewport["width"] + TOLERANCE_PX
        or pbox["y"] + pbox["height"] > viewport["height"] + TOLERANCE_PX
    ):
        findings.append(
            f"{label} [6.開閉の向き] パネルがビューポート {viewport['width']}x{viewport['height']} "
            f"の外に出ている (rect=({pbox['x']:.1f},{pbox['y']:.1f}) "
            f"{pbox['width']:.1f}x{pbox['height']:.1f})"
        )


# --- Check 7: dead controls --------------------------------------------------
# Controls this file deliberately does not click, with a one-line reason
# each (task's own "除外は理由を書く" applied to check 7):
DEAD_CONTROL_SKIP_TEST_IDS = {
    # Irreversible within a shared page/session -- clicking would end the
    # test's own authenticated session, breaking every later control in the
    # same sweep.
    "auth-sign-out": "サインアウトはセッションを終了させ以降の検査を続けられなくするため押さない",
    # Destructive-confirm half of a two-step control (task's own "確認の
    # 小窓が開くところまでで止める"). The *open* half
    # (gathering-delete-open/gathering-finalize-open) is still clicked and
    # checked below.
    "gathering-delete-confirm": (
        "取り返しのつかない削除の確定操作のため押さない（小窓を開くところまでで止める）"
    ),
    "gathering-finalize-confirm": (
        "会の確定は同一会に対して繰り返せないため押さない（小窓を開くところまでで止める）"
    ),
    # Revoking a participant link is one-way for that link -- opening the
    # dialog it lives in is exercised elsewhere (the main matrix tests);
    # this sweep does not additionally revoke a real link.
    "gathering-participant-link-revoke": "参加者リンクの失効は元に戻せないため押さない",
    # candidate.js's own documented behaviour ("Activating it while already
    # true does not reload the same screen (no-op)"): on the candidate
    # screen itself these two carry data-primary-nav-current="true" and the
    # click handler calls preventDefault, so no DOM/URL/focus change is the
    # *correct*, contractual outcome there -- not a dead control. (The same
    # test ids are reused, current="false", on the 3 gathering screens,
    # where they do navigate normally and are not skipped.)
    "candidate-primary-nav-search": (
        "候補画面自身では現在地ナビとしてno-op（candidate.jsの仕様どおり）"
    ),
    "candidate-primary-nav-menu-search": (
        "候補画面自身では現在地ナビとしてno-op（candidate.jsの仕様どおり）"
    ),
    # candidate.js's own renderCard/selectCandidate: the *first* rendered
    # card starts already selected (index === 0), and selectCandidate only
    # (re-)writes each card's own data-selection-state to whichever value
    # it already has when the already-selected card is clicked again -- no
    # attribute actually changes. This sweep always resolves a repeated
    # testid to its first DOM match, so it always lands on exactly this
    # card; a *different* (non-first) card's own selection is already
    # covered by test_render_invariants.py's own
    # test_c_candidate_card_selection_is_keyboard_operable.
    "candidate-card": (
        "先頭カードは初期状態で既に選択済みのため、クリックしても無変化になるのは仕様どおり"
    ),
}

EXTERNAL_LINK_TEST_ID_PREFIXES = (
    "candidate-card-provider-page-link",
    "gathering-shortlisted-shop-page-link",
    "gathering-decision-shop-page-link",
    "candidate-provider-credit",
    "candidate-map-attribution",
)


_FOCUS_DESCRIPTOR_JS = """
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const testid = el.getAttribute("data-testid");
  if (testid) return "testid=" + testid;
  return el.tagName + "#" + (el.id || "") + "." + (el.className || "");
}
"""


def _focus_descriptor(page: Page) -> str | None:
    return page.evaluate(_FOCUS_DESCRIPTOR_JS)


def _sweep_controls_for_dead_clicks(page: Page, label: str, findings: list[str]) -> None:
    """Check 7: click each visible, declared control once; assert something
    observable changed (DOM, URL, aria-expanded/aria-pressed, focus, or a
    clipboard write). Deduplicates by ``data-testid`` (list rows repeat the
    same testid many times; one representative click is enough to prove the
    handler exists). External links are confirmed to carry a real ``href``
    without being clicked (this file has no network access to the real
    provider). Destructive/irreversible controls stop at the confirmation
    dialog they open (``DEAD_CONTROL_SKIP_TEST_IDS``).

    Uses a work queue re-filled after every click (rather than one fixed,
    upfront list): a control hidden behind a still-closed toggle (e.g. the
    "≡" menu's own sign-out link, or the mobile account sheet's contents)
    is invisible -- and so absent from ``_run_layout_scan``'s own
    population -- until *after* its own toggle has already been clicked
    once earlier in this same sweep. A fixed upfront snapshot would never
    reach it at all.
    """
    page.bring_to_front()
    element_info: dict[str, dict] = {}
    queue: list[str] = []

    def _refresh_queue() -> None:
        scan = _run_layout_scan(page)
        for el in scan["elements"]:
            testid = el["testid"]
            if testid and el["isControl"] and testid not in element_info:
                element_info[testid] = el
                queue.append(testid)

    _refresh_queue()
    while queue:
        # LIFO: a control a toggle just revealed is tested *immediately*,
        # while its own toggle is still open -- restoring (closing the
        # toggle again) happens only once nothing newly revealed remains to
        # test, so a revealed control is never silently skipped for having
        # gone invisible again by the time its turn would otherwise come.
        testid = queue.pop()
        el = element_info[testid]

        if testid.startswith(EXTERNAL_LINK_TEST_ID_PREFIXES):
            href = el["href"]
            if not href:
                findings.append(
                    f"{label} [7.押しても何も起きない] {testid}: 外部リンクにhrefが無い"
                )
            continue
        if testid in DEAD_CONTROL_SKIP_TEST_IDS:
            continue

        locator = by_test_id(page, testid).first
        try:
            if locator.count() == 0 or not locator.is_visible():
                continue
            # A disabled control (e.g. a submit button before its own
            # required field is filled) legitimately does nothing when
            # clicked -- that is what "disabled" means, not a dead-control
            # defect -- and Playwright's own actionability check otherwise
            # waits (here, times out) for it to become enabled instead of
            # ever attempting the click.
            if locator.is_disabled():
                continue
        except Exception:  # noqa: BLE001 - a stale locator from a prior click is skipped, not fatal
            continue

        before_url = page.url
        before_html = page.evaluate("() => document.body.outerHTML")
        before_clip = page.evaluate("() => (window.__clipboardWrites || []).length")
        before_focus = _focus_descriptor(page)

        try:
            locator.click(timeout=2000)
            page.wait_for_timeout(250)
        except Exception as exc:  # noqa: BLE001 - record and move on, do not abort the whole sweep
            findings.append(f"{label} [7.押しても何も起きない] {testid}: クリックに失敗 ({exc})")
            continue

        after_url = page.url
        try:
            after_html = page.evaluate("() => document.body.outerHTML")
            after_focus = _focus_descriptor(page)
        except Exception:  # noqa: BLE001 - navigation mid-evaluate
            after_html = None
            after_focus = None
        after_clip = page.evaluate("() => (window.__clipboardWrites || []).length")

        # A plain <button>/control-purpose element natively receives focus
        # on click in Chromium regardless of whether any handler ran --
        # that alone is not evidence of a working control, so a *change* in
        # focus is required for those. A form field (<input>/<select>/
        # <textarea>) simply *being* focused after the click is itself the
        # real, expected response (real-measurement finding: Chromium can
        # autofocus a form's first field on load -- e.g. a password field,
        # for password-manager assistance -- so "focus changed" would be
        # false for that one field even though it responded correctly; the
        # postcondition "is focused" holds regardless of the prior state).
        after_is_self = after_focus == f"testid={testid}"
        if el["isFormField"]:
            meaningful_focus_change = after_is_self
        else:
            focus_changed = before_focus != after_focus
            meaningful_focus_change = focus_changed and not after_is_self

        changed = (
            before_url != after_url
            or before_html != after_html
            or after_clip > before_clip
            or meaningful_focus_change
        )
        if not changed:
            findings.append(
                f"{label} [7.押しても何も起きない] {testid}: "
                "クリック後もDOM・URL・クリップボードに変化が無い"
            )

        # Queue anything this click newly revealed (e.g. a toggle's own
        # menu items) *before* the restore step below closes it again --
        # after restoring, those same controls are invisible once more and
        # would never be scanned at all.
        if after_url == before_url:
            try:
                _refresh_queue()
            except Exception:  # noqa: BLE001 - a mid-navigation scan is skipped, not fatal
                pass

        # Best-effort restore so later controls in this sweep see the
        # original screen, not a side effect of this one.
        if after_url != before_url:
            try:
                page.go_back(timeout=3000)
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:  # noqa: BLE001
                pass
        else:
            try:
                page.keyboard.press("Escape")
            except Exception:  # noqa: BLE001
                pass

        try:
            _refresh_queue()
        except Exception:  # noqa: BLE001 - a mid-navigation scan is skipped, not fatal
            pass


class LayoutSanityTests(StaticLiveServerTestCase):
    """Setup mirrors ``test_render_invariants.py``'s own two classes (same
    known Playwright-sync/Django async_unsafe interaction, ADR-0020 decision
    6's shared harness) -- an independent copy, not an import, since this
    file's own Given-state builders below are new and specific to the 9
    screen/state combinations the task names, not a reuse of that file's
    private per-class helpers.
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

    def _seed_one_shortlisted_shop(self, gathering_id: str) -> str:
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
        return shop_id

    def _issue_participant_link_url(self) -> str:
        by_test_id(self.page, "gathering-participant-link-copy").click()
        dialog = by_test_id(self.page, "gathering-participant-link-issue-dialog")
        expect(dialog).to_have_attribute("data-issued-link-url", re.compile(r"^http"))
        url = dialog.get_attribute("data-issued-link-url")
        assert url is not None
        by_test_id(self.page, "gathering-participant-link-issue-dialog-close").click()
        return url

    # --- 1/2/3: candidate screen (normal / gathering mode / menu open) ----

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目1・2: デスクトップ1440x900で候補画面の≡メニューの列が折り返し"
            "画面左端付近（x=-107〜85）に来ている（h1直前0px間隔・パネルもビューポート左端"
            "の外にはみ出す、check4・check5）。加えてcandidate-provider-credit（クレジット"
            "表記）がカード本文と重なる（最大424x30px、check1）。"
        ),
    )
    def test_candidate_normal_and_menu_open(self) -> None:
        """候補画面 通常状態、および同じ Given から ≡ メニュー/アカウントシート
        を開いた状態 -- 見出し(h1)・条件バー・地図・カード・上部/下部ナビの
        すべてを1つの Given で確認する。
        """
        findings: list[str] = []
        self._sign_in_as_organizer()
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                self.dsl.reset_candidate_state()
                self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
                self.page.goto(f"{self.base_url}/")
                wait_for_at_least_one(self.page, "candidate-card")

                _run_checks_1_to_5(self.page, f"candidate-normal ({label})", findings)

                is_two_column = width >= 1024
                if is_two_column:
                    by_test_id(self.page, "candidate-primary-nav-menu-toggle").click()
                    self.page.wait_for_timeout(150)
                    _run_checks_1_to_5(self.page, f"candidate-menu-open ({label})", findings)
                    self.page.keyboard.press("Escape")
                else:
                    by_test_id(self.page, "candidate-primary-nav-account").click()
                    self.page.wait_for_timeout(150)
                    _run_checks_1_to_5(
                        self.page, f"candidate-account-sheet-open ({label})", findings
                    )
                    self.page.keyboard.press("Escape")

                if label in ("phone-390x844", "desktop-1440x900"):
                    _sweep_controls_for_dead_clicks(
                        self.page, f"candidate-normal ({label})", findings
                    )

        assert not findings, "\n".join(findings)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目1・2: 会モードでも候補画面と同じ根本原因（項目1・2参照、"
            "デスクトップ1440x900の≡メニュー折り返しとクレジット表記の重なり）が"
            "そのまま再現する。"
        ),
    )
    def test_candidate_gathering_mode(self) -> None:
        """候補画面（会モード）: `given_a_gathering_with_exactly_one_shortlisted_
        shop`(既存DSLの公開Given-seam、ADR-0020決定6が明示的に許すreuse)で
        会に1件入れた状態から開く。
        """
        findings: list[str] = []
        self._sign_in_as_organizer()
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        gathering_id = self.dsl.given_a_gathering_with_exactly_one_shortlisted_shop(
            "会モード確認会"
        )
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                self.dsl.open_gathering_mode_from_dashboard(gathering_id)
                wait_for_at_least_one(self.page, "candidate-gathering-mode-band")
                _run_checks_1_to_5(self.page, f"candidate-gathering-mode ({label})", findings)

        assert not findings, "\n".join(findings)

    # --- 4: 会の一覧 -------------------------------------------------------

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目7: デスクトップ1440x900でh1直前の≡メニューが0px間隔で詰まる"
            "（項目1と同じ根本原因）。他はすべて緑。"
        ),
    )
    def test_gathering_list(self) -> None:
        findings: list[str] = []
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("一覧確認会")
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                self.page.goto(f"{self.base_url}{reverse('gathering:organizer-gathering-list')}")
                wait_for_at_least_one(self.page, "gathering-list-item")
                _run_checks_1_to_5(self.page, f"gathering-list ({label})", findings)
                if label == "desktop-1440x900":
                    _sweep_controls_for_dead_clicks(
                        self.page, f"gathering-list ({label})", findings
                    )

        assert not findings, "\n".join(findings)

    # --- 5: 会をつくる と確認の小窓 ------------------------------------------

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目3・11: デスクトップ1440x900で、作成画面本体・確認小窓のいずれも"
            "h1直前の≡メニューが0px間隔で詰まる（項目1と同じ根本原因）。加えて"
            "gathering-create-candidate-date-day（カレンダーの日付セル）を押しても check7 "
            "からは変化が見えない（未確認）。"
        ),
    )
    def test_gathering_create_and_confirm_dialog(self) -> None:
        findings: list[str] = []
        self._sign_in_as_organizer()
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                self.page.goto(f"{self.base_url}{reverse('gathering:organizer-gathering-create')}")
                by_test_id(self.page, "gathering-create-name-input").fill(f"作成画面確認会 {label}")
                expect(
                    self.page.locator(
                        '[data-testid="gathering-create-candidate-date-day"]'
                        "[data-gathering-control-purpose]"
                    ).first
                ).to_be_visible()
                self._select_first_calendar_day(
                    "gathering-create-candidate-date-day",
                    "gathering-create-candidate-date-month-next",
                )
                _run_checks_1_to_5(self.page, f"gathering-create ({label})", findings)

                by_test_id(self.page, "gathering-create-review-open").click()
                expect(by_test_id(self.page, "gathering-create-review-dialog")).to_be_attached()
                _run_checks_1_to_5(
                    self.page, f"gathering-create-confirm-dialog ({label})", findings
                )
                by_test_id(self.page, "gathering-create-review-cancel").click()
                expect(by_test_id(self.page, "gathering-create-review-dialog")).to_have_count(0)

                if label == "desktop-1440x900":
                    _sweep_controls_for_dead_clicks(
                        self.page, f"gathering-create ({label})", findings
                    )

        assert not findings, "\n".join(findings)

    # --- 6/7/8: 幹事の会の画面（3局面）とタブ・小窓 -------------------------

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目4・5・6: デスクトップ1440x900でh1直前の≡メニューが0px間隔で"
            "詰まる（項目1と同じ根本原因）。加えてphone-360x740で候補日追加の小窓が"
            "ビューポート下端の外（約85px）にはみ出し（check4:小窓）、削除確認の小窓を"
            "開くとh1が画面上端の外（y=-18）に押し出される（check4）。"
        ),
    )
    def test_gathering_dashboard_scheduling_phase(self) -> None:
        """SCHEDULING局面（候補日一覧・仮決定・候補日追加の小窓・削除確認の
        小窓）。"""
        findings: list[str] = []
        self._sign_in_as_organizer()
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                self._create_gathering_via_ui(f"日程調整局面確認会 {label}")
                _run_checks_1_to_5(self.page, f"dashboard-scheduling ({label})", findings)

                by_test_id(self.page, "gathering-add-candidate-date-open").click()
                expect(
                    by_test_id(self.page, "gathering-add-candidate-date-calendar")
                ).to_be_attached()
                _run_checks_1_to_5(
                    self.page, f"dashboard-scheduling-add-date-dialog ({label})", findings
                )
                by_test_id(self.page, "gathering-add-candidate-date-cancel").click()

                by_test_id(self.page, "gathering-delete-open").click()
                expect(by_test_id(self.page, "gathering-delete-confirm-dialog")).to_be_attached()
                _run_checks_1_to_5(
                    self.page, f"dashboard-scheduling-delete-dialog ({label})", findings
                )
                by_test_id(self.page, "gathering-delete-cancel").click()

                if label == "desktop-1440x900":
                    _sweep_controls_for_dead_clicks(
                        self.page, f"dashboard-scheduling ({label})", findings
                    )

        assert not findings, "\n".join(findings)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目4: デスクトップ1440x900で、4タブ・リンク発行小窓・確定確認小窓の"
            "いずれでもh1直前の≡メニューが0px間隔で詰まっている（項目1と同じ根本原因、"
            "gathering-scheduling-browser-interface.yamlの3画面に共通）。"
        ),
    )
    def test_gathering_dashboard_selecting_shop_phase_and_tabs(self) -> None:
        """SELECTING_SHOP局面の4タブ（schedule/shop/links/answers）と、
        リンク発行・確定確認の小窓。"""
        findings: list[str] = []
        self._sign_in_as_organizer()
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                gathering_id = self._create_gathering_via_ui(f"店選び局面確認会 {label}")
                by_test_id(self.page, "gathering-candidate-date").click()
                by_test_id(self.page, "gathering-confirm-date-select").click()
                self._seed_one_shortlisted_shop(gathering_id)
                self.page.reload()
                expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()

                for tab in (
                    "gathering-shop-select-tab-schedule",
                    "gathering-shop-select-tab-shop",
                    "gathering-shop-select-tab-links",
                    "gathering-shop-select-tab-answers",
                ):
                    by_test_id(self.page, tab).click()
                    _run_checks_1_to_5(
                        self.page, f"dashboard-selecting-shop-{tab} ({label})", findings
                    )

                by_test_id(self.page, "gathering-shop-select-tab-links").click()
                by_test_id(self.page, "gathering-participant-link-copy").click()
                expect(
                    by_test_id(self.page, "gathering-participant-link-issue-dialog")
                ).to_be_attached()
                _run_checks_1_to_5(
                    self.page, f"dashboard-selecting-shop-link-dialog ({label})", findings
                )
                by_test_id(self.page, "gathering-participant-link-issue-dialog-close").click()

                by_test_id(self.page, "gathering-shop-select-tab-shop").click()
                by_test_id(self.page, "gathering-finalize-shop-select").check(force=True)
                by_test_id(self.page, "gathering-finalize-open").click()
                expect(by_test_id(self.page, "gathering-finalize-confirm-dialog")).to_be_attached()
                _run_checks_1_to_5(
                    self.page, f"dashboard-selecting-shop-finalize-dialog ({label})", findings
                )
                by_test_id(self.page, "gathering-finalize-cancel").click()

                if label == "desktop-1440x900":
                    by_test_id(self.page, "gathering-shop-select-tab-shop").click()
                    _sweep_controls_for_dead_clicks(
                        self.page, f"dashboard-selecting-shop ({label})", findings
                    )

        assert not findings, "\n".join(findings)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目4・8: デスクトップ1440x900でh1直前の≡メニューが0px間隔で詰まる"
            "（項目1と同じ根本原因）。加えてphone-360x740/390x844で回答・リンクの開閉行を"
            "開くと、中身が gathering-decision-links-open 等と重なり "
            "div.gth-decision-disclosure-panel の外にもはみ出す（check1・check4）。"
        ),
    )
    def test_gathering_dashboard_finalized_phase(self) -> None:
        findings: list[str] = []
        self._sign_in_as_organizer()
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                gathering_id = self._create_gathering_via_ui(f"確定局面確認会 {label}")
                by_test_id(self.page, "gathering-candidate-date").click()
                by_test_id(self.page, "gathering-confirm-date-select").click()
                self._seed_one_shortlisted_shop(gathering_id)
                self.page.reload()
                expect(by_test_id(self.page, "gathering-shortlisted-shop-list")).to_be_visible()
                by_test_id(self.page, "gathering-finalize-shop-select").check(force=True)
                by_test_id(self.page, "gathering-finalize-open").click()
                by_test_id(self.page, "gathering-finalize-confirm").click()
                expect(by_test_id(self.page, "gathering-decision-banner")).to_be_visible()

                _run_checks_1_to_5(self.page, f"dashboard-finalized ({label})", findings)

                by_test_id(self.page, "gathering-decision-answers-open").click()
                by_test_id(self.page, "gathering-decision-links-open").click()
                _run_checks_1_to_5(
                    self.page, f"dashboard-finalized-entrance-rows-open ({label})", findings
                )

                if label == "desktop-1440x900":
                    _sweep_controls_for_dead_clicks(
                        self.page, f"dashboard-finalized ({label})", findings
                    )

        assert not findings, "\n".join(findings)

    # --- 9: 参加者の回答画面 -------------------------------------------------

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目10: デスクトップ1440x900でgathering-participant-answer-skip・"
            "gathering-participant-name-submit・gathering-participant-day-item を押しても"
            "check7 からは変化が見えない（未確認。項目9と同じ検査の限界の可能性、または"
            "実際に反応していない可能性の両方が残る）。確認して直すか、限界と分かれば外す。"
        ),
    )
    def test_participant_answer(self) -> None:
        findings: list[str] = []
        self._sign_in_as_organizer()
        self._create_gathering_via_ui("参加者画面確認会")
        by_test_id(self.page, "gathering-add-candidate-date-open").click()
        self._select_first_calendar_day(
            "gathering-add-candidate-date-day", "gathering-add-candidate-date-month-next"
        )
        by_test_id(self.page, "gathering-add-candidate-date-submit").click()
        link_url = self._issue_participant_link_url()

        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                context = self._browser.new_context(viewport={"width": width, "height": height})
                self.addCleanup(context.close)
                page = context.new_page()
                page.goto(link_url)
                wait_for_at_least_one(page, "gathering-schedule-question")
                _run_checks_1_to_5(page, f"participant-answer ({label})", findings)

                if width < 1024:
                    by_test_id(page, "gathering-participant-day-list-open").click()
                    expect(by_test_id(page, "gathering-participant-day-list")).to_be_visible()
                    _run_checks_1_to_5(
                        page, f"participant-answer-day-list-open ({label})", findings
                    )
                    by_test_id(page, "gathering-participant-day-list-close").click()

                if label == "desktop-1440x900":
                    _sweep_controls_for_dead_clicks(page, f"participant-answer ({label})", findings)

        assert not findings, "\n".join(findings)

    # --- 10: パスワード変更 --------------------------------------------------

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "報告リスト項目9: デスクトップ1440x900でauth-password-change-submitを"
            "空欄のまま押しても check7 からは変化が見えない -- ネイティブHTML5バリデーション"
            "のバブルはouterHTMLに現れないため、本チェックの既知の限界（壊れているとは断定"
            "できない）。修正または限界の追認で外す。"
        ),
    )
    def test_password_change(self) -> None:
        findings: list[str] = []
        self._sign_in_as_organizer()
        for width, height, label in VIEWPORTS:
            if True:  # per-viewport -- not subTest, see VIEWPORTS's own comment above
                self.page.set_viewport_size({"width": width, "height": height})
                self.page.goto(f"{self.base_url}{reverse('authentication:password_change')}")
                expect(by_test_id(self.page, "auth-password-change-submit")).to_be_visible()
                _run_checks_1_to_5(self.page, f"password-change ({label})", findings)
                if label == "desktop-1440x900":
                    _sweep_controls_for_dead_clicks(
                        self.page, f"password-change ({label})", findings
                    )

        assert not findings, "\n".join(findings)

    # --- Check 6: toggle open direction, dedicated (not part of the 1-5
    # matrix above -- needs its own open/verify/close sequencing). ----------

    def test_toggle_direction_mobile_account_sheet(self) -> None:
        findings: list[str] = []
        self._sign_in_as_organizer()
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        self.page.goto(f"{self.base_url}/")
        wait_for_at_least_one(self.page, "candidate-card")
        toggle = by_test_id(self.page, ACCOUNT_MENU_TOGGLE_TEST_ID)
        toggle.click()
        panel = self.page.locator(f"#{ACCOUNT_MENU_PANEL_ID}")
        _assert_toggle_opens_in_place_and_in_viewport(
            self.page, toggle, panel, "mobile-account-sheet", findings
        )
        assert not findings, "\n".join(findings)

    def test_toggle_direction_filter_panel(self) -> None:
        findings: list[str] = []
        self._sign_in_as_organizer()
        for width, height, label in ((390, 844, "phone-390x844"), (1440, 900, "desktop-1440x900")):
            self.page.set_viewport_size({"width": width, "height": height})
            self.dsl.reset_candidate_state()
            self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
            self.page.goto(f"{self.base_url}/")
            wait_for_at_least_one(self.page, "candidate-card")
            toggle = by_test_id(self.page, FILTER_TOGGLE_TEST_ID)
            toggle.click()
            panel = by_test_id(self.page, FILTER_PANEL_TEST_ID)
            _assert_toggle_opens_in_place_and_in_viewport(
                self.page, toggle, panel, f"filter-panel ({label})", findings
            )
            toggle.click()
        assert not findings, "\n".join(findings)


class LayoutSanityFaultInjectionTests(StaticLiveServerTestCase):
    """One deliberate defect per check, confirming the check catches it
    (task's own "欠陥注入: 7種類の検査それぞれで...1回ずつ行い落ちることを
    確かめる"). Each test injects via ``page.add_style_tag``/JS eval against
    an otherwise-clean screen, then calls the same check function the main
    matrix above uses -- this only exercises the check functions
    themselves, never asserts business behaviour, so it does not duplicate
    ``test_render_invariants.py``'s own coverage.
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
        self.dsl.reset_authentication_state()
        self.context.request.delete(f"{self.base_url}/test-support/gathering-scheduling-state")
        self.dsl.enable_organizer(
            "fault-injection-organizer", "fault-injection-id", "fault-injection-pw"
        )
        self.dsl.sign_in("fault-injection-id", "fault-injection-pw")

    def _open_candidate_screen(self, width: int = 390, height: int = 844) -> None:
        self.page.set_viewport_size({"width": width, "height": height})
        self.dsl.reset_candidate_state()
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")
        self.page.goto(f"{self.base_url}/")
        wait_for_at_least_one(self.page, "candidate-card")

    def test_injected_overlap_is_caught(self) -> None:
        self._open_candidate_screen()
        findings: list[str] = []
        _check_1_overlap(_run_layout_scan(self.page), "baseline", findings)
        assert not findings, "baseline unexpectedly has an overlap: " + "\n".join(findings)

        self.page.add_style_tag(
            content=(
                '[data-testid="candidate-search-again"] '
                "{ position: fixed !important; top: 0 !important; left: 0 !important; "
                "z-index: 999 !important; }"
            )
        )
        injected: list[str] = []
        _check_1_overlap(_run_layout_scan(self.page), "injected", injected)
        assert injected, "check 1 (overlap) did not catch the injected overlap"

    def test_injected_text_clipping_is_caught(self) -> None:
        self._open_candidate_screen()
        findings: list[str] = []
        _check_2_text_clipping(_run_layout_scan(self.page), "baseline", findings)
        assert not findings, "baseline unexpectedly clips text: " + "\n".join(findings)

        self.page.add_style_tag(
            content=(
                '[data-testid="candidate-card-name"] '
                "{ text-overflow: clip !important; flex: 0 0 12px !important; "
                "width: 12px !important; white-space: nowrap !important; }"
            )
        )
        injected: list[str] = []
        _check_2_text_clipping(_run_layout_scan(self.page), "injected", injected)
        assert injected, "check 2 (text clipping) did not catch the injected clip"

    def test_injected_unintended_wrap_is_caught(self) -> None:
        # A genre chip (candidate.js's chip()) is a plain <button>text</button>
        # with no element children -- check 3's own simple-label-control
        # scope (its docstring) -- unlike an icon+label composite button.
        self._open_candidate_screen()
        by_test_id(self.page, "candidate-filter-open").click()
        expect(self.page.locator(".candidate-chip").first).to_be_visible()
        findings: list[str] = []
        _check_3_unintended_wrap(_run_layout_scan(self.page), "baseline", findings)
        assert not findings, "baseline unexpectedly wraps a control: " + "\n".join(findings)

        self.page.add_style_tag(
            content=(
                ".candidate-chip "
                "{ width: 24px !important; white-space: normal !important; "
                "word-break: break-all !important; }"
            )
        )
        injected: list[str] = []
        _check_3_unintended_wrap(_run_layout_scan(self.page), "injected", injected)
        assert injected, "check 3 (unintended wrap) did not catch the injected wrap"

    def test_injected_overflow_is_caught(self) -> None:
        self._open_candidate_screen()
        findings: list[str] = []
        _check_4_overflow(_run_layout_scan(self.page), "baseline", findings)
        assert not findings, "baseline unexpectedly overflows: " + "\n".join(findings)

        self.page.add_style_tag(
            content=(
                '[data-testid="candidate-filter-open"] '
                "{ position: relative !important; left: -9999px !important; }"
            )
        )
        injected: list[str] = []
        _check_4_overflow(_run_layout_scan(self.page), "injected", injected)
        assert injected, "check 4 (overflow) did not catch the injected off-container control"

    def test_injected_cramped_spacing_is_caught(self) -> None:
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.goto(f"{self.base_url}{reverse('authentication:password_change')}")
        expect(by_test_id(self.page, "auth-password-change-submit")).to_be_visible()
        findings: list[str] = []
        _check_5_cramped_spacing(_run_layout_scan(self.page), "baseline", findings)
        assert not findings, "baseline unexpectedly crams the heading: " + "\n".join(findings)

        # base.html's own "form > p { margin: 1rem 0; }" gives the form's
        # own first paragraph a 1rem top margin that collapses through the
        # plain <header>/<form> sibling boundary -- zeroing only the
        # header's own margin leaves that paragraph margin still providing
        # a real gap, so this must be zeroed too to actually crowd them.
        self.page.add_style_tag(
            content=(
                ".app-header, .app-header h1 { margin-bottom: 0 !important; } "
                "form > p:first-of-type { margin-top: 0 !important; }"
            )
        )
        injected: list[str] = []
        _check_5_cramped_spacing(_run_layout_scan(self.page), "injected", injected)
        assert injected, "check 5 (cramped spacing) did not catch the injected crowding"

    def test_injected_toggle_wrong_direction_is_caught(self) -> None:
        self._open_candidate_screen()
        toggle = by_test_id(self.page, ACCOUNT_MENU_TOGGLE_TEST_ID)
        toggle.click()
        panel = self.page.locator(f"#{ACCOUNT_MENU_PANEL_ID}")
        findings: list[str] = []
        _assert_toggle_opens_in_place_and_in_viewport(
            self.page, toggle, panel, "baseline", findings
        )
        assert not findings, "baseline toggle unexpectedly misdirected: " + "\n".join(findings)
        # Escape, not a second .click() -- the open sheet visually covers
        # its own toggle (both anchored to the viewport bottom, the sheet's
        # own higher z-index; the same real geometry check 6's own docstring
        # explains), so Playwright's actionability check correctly refuses a
        # second coordinate-click on the now-covered toggle.
        self.page.keyboard.press("Escape")
        expect(panel).to_be_hidden()

        toggle.click()
        self.page.add_style_tag(
            content=(
                f"#{ACCOUNT_MENU_PANEL_ID} {{ position: fixed !important; top: 0 !important; "
                "left: auto !important; right: -600px !important; bottom: auto !important; "
                "width: 200px !important; }}"
            )
        )
        injected: list[str] = []
        _assert_toggle_opens_in_place_and_in_viewport(
            self.page, toggle, panel, "injected", injected
        )
        assert injected, "check 6 (toggle direction) did not catch the injected misdirection"

    def test_injected_dead_control_is_caught(self) -> None:
        self._open_candidate_screen()
        findings: list[str] = []
        _sweep_controls_for_dead_clicks(self.page, "baseline-partial", findings)
        assert not findings, "baseline unexpectedly has a dead control: " + "\n".join(findings)

        # Clone-and-replace strips every listener Playwright's own .click()
        # would otherwise still trigger, leaving the button visually
        # identical but functionally inert -- the exact "ⓘ button that does
        # nothing" shape the human reported.
        self.page.evaluate(
            """() => {
              const el = document.querySelector('[data-testid="candidate-search-again"]');
              const clone = el.cloneNode(true);
              el.replaceWith(clone);
            }"""
        )
        injected: list[str] = []
        _sweep_controls_for_dead_clicks(self.page, "injected", injected)
        assert any("candidate-search-again" in f for f in injected), (
            "check 7 (dead control) did not catch the injected inert control: "
            + "\n".join(injected)
        )


# ---------------------------------------------------------------------------
# xfail registrations for known-broken (screen, size, check) combinations
# found on main (f153a1b) by this file's own first discovery run. Each is
# ``strict=True`` -- fixing the underlying layout bug turns the method green
# again, which xfail(strict=True) reports as an unexpected pass (XPASS),
# failing CI until the xfail marker below is removed. See this task's own
# chat report for the full, numbered findings list these reasons reference.
