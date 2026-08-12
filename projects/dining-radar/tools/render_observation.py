"""Render-observation tool (ADR-0020 decision 1).

Screenshots the real, authenticated candidate-proposal screen at a fixed set
of viewports so developer can look at their own rendering while implementing
a UI change. This tool performs no comparison and no pass/fail judgment --
unlike ``tests/ui_invariants`` (ADR-0020 decision 4's gate), it has no
concept of green or red. It is not part of any verification layer, is not
wired into CI (ADR-0020 decision 6), and never needs to run in a pipeline.

Output is written under ``.render-observations/`` at the project root
(overridable with ``RENDER_OBSERVATION_OUTPUT_DIR``), which is gitignored --
nothing this tool produces is committed.

Usage (from projects/toyama-dining-radar, with the project's dev extras
installed and Chromium available -- see pyproject.toml / CI's "Install the
JS-capable browser" step):

    python -m pytest tools/render_observation.py -s

    # A different synthetic candidate population
    # (contracts/test-support-api.yaml CandidateProposalAcceptanceState.mode):
    RENDER_OBSERVATION_MODE=IZAKAYA_BAR_ONLY python -m pytest tools/render_observation.py -s

This file is deliberately a pytest test function (not a test-runner script):
pytest-django's own ``live_server`` fixture already provides everything a
hand-rolled runner would otherwise have to reimplement (test database
lifecycle, same-origin static-file serving via ``django.contrib.staticfiles``
per pytest-django's documented behavior -- equivalent to
``StaticLiveServerTestCase``, which
``tests/acceptance/test_candidate_search_acceptance.py`` and
``tests/ui_invariants`` use directly). It is named ``render_observation.py``,
not ``test_render_observation.py``, so pyproject.toml's
``python_files = ["test_*.py"]`` never sweeps it into an implicit
``pytest``/``pytest tests/`` run; it only runs when invoked by this exact
path, matching its non-gate, run-it-yourself role.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

# Same known Playwright-sync / Django async_unsafe interaction documented in
# tests/acceptance/test_candidate_search_acceptance.py's setUpClass -- set
# before any Playwright sync call can run during this process.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

from django.test import SimpleTestCase  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / ".render-observations"

ORGANIZER_ACCOUNT_REF = "render-observer"
ORGANIZER_IDENTIFIER = "synthetic-render-observer"
ORGANIZER_PASSWORD = "synthetic-render-observer-secret"

# Mirrors contracts/test-support-api.yaml v1.0.2's
# CandidateProposalAcceptanceState.mode enum exactly (adr/0023 renames
# NORMAL_WITH_REPEAT to NORMAL_WITH_POOL, drops INVALID_REPROPOSAL_KIND with
# the retired ConceptKind re-proposal model, and adds ZERO_PENDING_MATCH /
# FALLBACK_PRESERVES_FILTERS).
VALID_MODES = [
    "NORMAL_WITH_POOL",
    "DEFAULT_EXCLUSION_VISIBLE",
    "CARD_PAYMENT_CAUTION_VISIBLE",
    "ZERO_PENDING_MATCH",
    "FALLBACK_PRESERVES_FILTERS",
    "IZAKAYA_BAR_ONLY",
    "NO_RESULTS",
    "PROVIDER_UNAVAILABLE",
    "RATE_LIMITED",
]

# Viewports the developer can look at. 390x844 and 1440x900 match the two
# widths orchestrator already measures by hand (activeContext.md); 730x900 is
# the width the original narrow-layout defect was reported at.
VIEWPORTS = [
    (390, 844, "mobile-390x844"),
    (730, 900, "narrow-730x900"),
    (1440, 900, "desktop-1440x900"),
]


def _null_assertions() -> SimpleTestCase:
    """A real ``SimpleTestCase`` instance, only for CandidateSearchBrowserDsl's
    Given-seam helpers to call ``self.assertions.assertX(...)`` on.

    This tool takes no screenshots-vs-anything comparison and asserts
    nothing of its own; it only needs an object with unittest's assert*
    methods because the DSL's setup helpers (reset/enable/sign-in) are
    written to call them. Constructing ``SimpleTestCase`` with an existing,
    harmless method name (never executed as a test) is the smallest way to
    get a real, working assertions object without a bespoke duplicate.
    """
    return SimpleTestCase("assertTrue")


def test_capture_render_observations(live_server) -> None:  # noqa: N802 - pytest test name
    """Sign in, load a synthetic proposal, and screenshot every viewport.

    Not a verification test: it makes no assertion about the screenshots'
    content. Its only job is to produce files a developer can open with the
    ``Read`` tool (or any image viewer) and look at.
    """
    mode = os.environ.get("RENDER_OBSERVATION_MODE", "NORMAL_WITH_POOL")
    if mode not in VALID_MODES:
        raise SystemExit(
            f"RENDER_OBSERVATION_MODE={mode!r} is not one of {VALID_MODES} "
            "(contracts/test-support-api.yaml CandidateProposalAcceptanceState.mode)"
        )
    output_dir = Path(os.environ.get("RENDER_OBSERVATION_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    output_dir.mkdir(parents=True, exist_ok=True)

    base_url = live_server.url
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    written: list[Path] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            # A fresh browser context (and therefore a fresh page load and a
            # fresh Leaflet map instance) per viewport, not one page resized
            # in place. Leaflet does not re-fit its view when its container
            # is resized without an explicit invalidateSize() call, which
            # candidate.js never makes -- reusing one already-loaded page
            # across set_viewport_size() calls therefore renders a stale map
            # (this was confirmed while building this tool: it made two
            # markers appear to vanish at narrow widths, an artifact of this
            # tool's own prior approach, not a real defect a user hitting
            # that width directly would see). A fresh load per viewport is
            # also simply more faithful to how a real visitor actually
            # arrives at a given width.
            for width, height, label in VIEWPORTS:
                context = browser.new_context(viewport={"width": width, "height": height})
                try:
                    page = context.new_page()
                    dsl = CandidateSearchBrowserDsl(_null_assertions(), page, base_url)
                    dsl.reset_authentication_state()
                    dsl.reset_candidate_state()
                    dsl.enable_organizer(
                        ORGANIZER_ACCOUNT_REF, ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD
                    )
                    dsl.sign_in(ORGANIZER_IDENTIFIER, ORGANIZER_PASSWORD)
                    dsl.set_candidate_state(mode)
                    dsl.open_candidate_screen()

                    path = output_dir / f"{timestamp}-{mode}-{label}.png"
                    page.screenshot(path=str(path), full_page=True)
                    written.append(path)
                finally:
                    context.close()
        finally:
            browser.close()

    print(f"\nrender-observation: wrote {len(written)} screenshot(s) to {output_dir}")
    for path in written:
        print(f"  {path}")
