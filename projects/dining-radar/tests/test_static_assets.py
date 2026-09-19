"""ADR-0010: Leaflet is vendored under ``static/`` and served same-origin.

The authenticated candidate-proposal screen must not load Leaflet's JS/CSS
from a third-party CDN (``https://unpkg.com`` or any other external origin).
Only the OSM tile server (already boundaried by ADR-0008) remains an external
contact point for the map UI.
"""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOME_TEMPLATE = PROJECT_ROOT / "src" / "dining_radar" / "web" / "templates" / "web" / "home.html"
CANDIDATE_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "web"
    / "static"
    / "dining_radar"
    / "web"
    / "candidate.js"
)

_VENDORED_LEAFLET_ASSETS = (
    "dining_radar/web/vendor/leaflet/leaflet.js",
    "dining_radar/web/vendor/leaflet/leaflet.css",
    "dining_radar/web/vendor/leaflet/LICENSE",
    "dining_radar/web/vendor/leaflet/images/marker-icon.png",
    "dining_radar/web/vendor/leaflet/images/marker-icon-2x.png",
    "dining_radar/web/vendor/leaflet/images/marker-shadow.png",
    "dining_radar/web/vendor/leaflet/images/layers.png",
    "dining_radar/web/vendor/leaflet/images/layers-2x.png",
)

DASHBOARD_TEMPLATE = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "templates"
    / "gathering"
    / "organizer_dashboard.html"
)
GATHERING_CREATE_TEMPLATE = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "templates"
    / "gathering"
    / "organizer_gathering_create.html"
)
GATHERING_LIST_TEMPLATE = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "templates"
    / "gathering"
    / "organizer_gathering_list.html"
)
PRIMARY_NAV_PARTIAL = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "templates"
    / "gathering"
    / "organizer_primary_nav.html"
)
ORGANIZER_CSS = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "organizer.css"
)
GATHERING_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "gathering.js"
)
GATHERING_CREATE_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "gathering_create.js"
)
GATHERING_LIST_SCRIPT = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "gathering_list.js"
)


class GatheringCalendarNoLongerVendorsFlatpickrTests(SimpleTestCase):
    """**2026-09-13 (ADR-0054 decision 3 / ADR-0056 decision 3, human
    decision)**: flatpickr (previously vendored under
    ``dining_radar/gathering/vendor/flatpickr/`` -- see the removed
    ``FlatpickrVendoringSourceTests`` this class replaces, and
    ``git log`` for its own prior content) is retired outright, not merely
    hidden -- the human picked a hand-built "案B｜表" calendar after seeing
    it actually run (``scratchpad/cal/looks.html``/``script.js``), which
    also removes two defects the vendored library itself caused: the input
    element it always built internally (worked around to satisfy
    ``unavailableControls.allGatheringScreenFormControlsMustDeclarePurpose``)
    and, as a side effect of that same workaround, a static year label that
    never updated on month navigation (friction-log.md FR-033). Both
    gathering screens now build their own calendar entirely in JS
    (``gathering.js``/``gathering_create.js``'s own
    ``buildCandidateDateCalendar``) with no vendored script or stylesheet of
    its own."""

    def test_gathering_templates_do_not_reference_a_third_party_cdn(self):
        for template in (DASHBOARD_TEMPLATE, GATHERING_CREATE_TEMPLATE):
            with self.subTest(template=template.name):
                source = template.read_text(encoding="utf-8")
                self.assertNotIn("unpkg.com", source)
                self.assertNotIn("cdn.jsdelivr.net", source)
                self.assertNotIn("cdnjs.cloudflare.com", source)

    def test_gathering_templates_no_longer_reference_flatpickr(self):
        for template in (DASHBOARD_TEMPLATE, GATHERING_CREATE_TEMPLATE):
            with self.subTest(template=template.name):
                source = template.read_text(encoding="utf-8")
                self.assertNotIn("flatpickr", source.lower())

    def test_flatpickr_assets_are_no_longer_vendored_or_discoverable(self):
        for asset in (
            "dining_radar/gathering/vendor/flatpickr/flatpickr.min.js",
            "dining_radar/gathering/vendor/flatpickr/flatpickr.min.css",
            "dining_radar/gathering/vendor/flatpickr/LICENSE",
        ):
            with self.subTest(asset=asset):
                self.assertIsNone(
                    finders.find(asset),
                    f"{asset} is still discoverable -- flatpickr should be fully removed",
                )
        vendor_dir = (
            PROJECT_ROOT
            / "src"
            / "dining_radar"
            / "gathering"
            / "static"
            / "dining_radar"
            / "gathering"
            / "vendor"
            / "flatpickr"
        )
        self.assertFalse(vendor_dir.exists(), f"{vendor_dir} should have been removed")


class LeafletVendoringSourceTests(SimpleTestCase):
    """Static checks against the template source (no request cycle needed)."""

    def test_home_template_does_not_reference_a_third_party_cdn(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn("unpkg.com", source)
        self.assertNotIn("cdn.jsdelivr.net", source)
        self.assertNotIn("cdnjs.cloudflare.com", source)

    def test_home_template_loads_leaflet_through_the_static_tag(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("{% static 'dining_radar/web/vendor/leaflet/leaflet.css' %}", source)
        self.assertIn("{% static 'dining_radar/web/vendor/leaflet/leaflet.js' %}", source)

    def test_vendored_leaflet_assets_are_discoverable_by_the_staticfiles_finders(self):
        for asset in _VENDORED_LEAFLET_ASSETS:
            with self.subTest(asset=asset):
                self.assertIsNotNone(
                    finders.find(asset), f"{asset} is not reachable by Django's staticfiles finders"
                )

    def test_vendored_leaflet_license_identifies_the_bsd_2_clause_terms(self):
        license_path = finders.find("dining_radar/web/vendor/leaflet/LICENSE")
        self.assertIsNotNone(license_path)

        license_text = Path(license_path).read_text(encoding="utf-8")
        self.assertIn("BSD 2-Clause License", license_text)

    def test_vendored_leaflet_does_not_reference_an_unvendored_source_map(self):
        script_path = finders.find("dining_radar/web/vendor/leaflet/leaflet.js")
        self.assertIsNotNone(script_path)

        script = Path(script_path).read_text(encoding="utf-8")
        self.assertNotIn("sourceMappingURL=leaflet.js.map", script)


class CandidateSurfaceSourceTests(SimpleTestCase):
    """Guard the presentation boundaries that do not need live provider data."""

    def test_map_primary_at_every_width_keeps_one_map_instance_and_retires_the_sheet(self):
        # adr/0033 (human decision 2026-08-29, Mobile.dc.html): the map is
        # primary at every width now, with the card deck floating over its
        # own bottom inset -- the earlier task 2/3 skeleton this test used
        # to guard (candidate-map-open/candidate-map-sheet-close/-panel, an
        # 88px closed band toggling to a full-screen sheet) is retired
        # outright, not merely hidden: contracts/candidate-search-browser-
        # interface.yaml v1.6.0 no longer defines renderModes.
        # listPrimaryLayout, and this screen must never emit those three
        # test ids into the DOM, or build the functions that used to create
        # them, at any width. One [data-testid="candidate-map"] element is
        # still declared once in candidate.js, never a second map instance
        # -- unchanged through every skeleton revision this file has
        # guarded (test_map_led_deck_keeps_cards_and_map_in_the_same_
        # surface, then task 3's list-primary/sheet, now this one).
        template = HOME_TEMPLATE.read_text(encoding="utf-8")
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('[data-testid="candidate-map"] {', template)
        self.assertIn(".candidate-map-wrapper {", template)
        self.assertEqual(
            script.count('{ "data-testid": "candidate-map", "data-map-tile-provider"'),
            1,
            "exactly one candidate-map element/Leaflet map instance must be declared",
        )
        self.assertIn("function refreshMapViewAndRings()", script)

        # The retired ribbon/sheet mechanism must not resurface anywhere --
        # neither its markup, its CSS, nor the JS functions that built it.
        # Matched by actual emission syntax (a CSS selector's own opening
        # brace, a JS attribute literal, a function declaration) rather
        # than a bare substring, since this file's own historical comments
        # (and this test's docstring above) legitimately name the retired
        # identifiers in prose without emitting them.
        self.assertNotIn(".candidate-map-open {", template)
        self.assertNotIn(".candidate-map-sheet-header {", template)
        self.assertNotIn(".candidate-map-sheet-panel {", template)
        self.assertNotIn(".candidate-map-sheet-back {", template)
        self.assertNotIn('"data-testid": "candidate-map-open"', script)
        self.assertNotIn('"data-testid": "candidate-map-sheet-close"', script)
        self.assertNotIn("function openMapSheet()", script)
        self.assertNotIn("function closeMapSheet()", script)
        self.assertNotIn("function syncMapSheetPanelToSelection()", script)
        self.assertNotIn("var mapSheetOpen", script)
        self.assertNotIn('"data-map-sheet-open", "true"', script)

        # adr/0049 decision 4 (2026-09-08 human decision: "微妙。右に地図で
        # 一覧左とかじゃなかったっけ") retires mapPrimaryLayout's own
        # button-paged deck outright, the same way task 2/3's ribbon/sheet
        # was retired above: >=64rem no longer builds candidate-deck-previous/
        # -next or their pager -- isTwoColumnLayout (renamed from
        # isMapPrimaryLayout) replaces the deck with a plain two-column
        # list-and-map layout instead. isMapPrimaryTouchLayout's own
        # swipe-paged deck (adr/0033) is unchanged by this revision.
        self.assertNotIn('"data-testid": "candidate-deck-previous"', script)
        self.assertNotIn('"data-testid": "candidate-deck-next"', script)
        self.assertNotIn(".candidate-deck-pager {", template)
        self.assertNotIn(".candidate-deck-nav {", template)
        self.assertNotIn("var isMapPrimaryLayout", script)
        self.assertIn("var isTwoColumnLayout", script)
        self.assertIn('"class": "candidate-list-column"', script)
        self.assertIn('"data-testid": "candidate-deck-swipe-surface"', script)
        self.assertIn('"data-testid": "candidate-deck-position"', script)
        self.assertIn("function attachSwipeGesture(", script)
        self.assertIn("function pageDeckNext()", script)
        self.assertIn("function pageDeckPrevious()", script)

    def test_mobile_layout_keeps_decision_controls_compact(self):
        template = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("min-height: 3.25rem", template)
        # Tokens.dc.html: header 52 / condition bar 48 (E:\AWS\dsg-out;
        # design realignment 2026-08-25).
        self.assertIn("height: 3rem", template)
        self.assertIn("height: 3.25rem", template)
        self.assertIn("flex-wrap: nowrap; overflow-x: auto", template)
        self.assertIn("candidate-card-description", template)
        self.assertIn("display: none", template)

    def test_card_payment_caution_does_not_overstate(self):
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("クレジットカード非対応（支払い方法は要確認）", script)

    def test_regular_holiday_moved_into_the_shared_detail_grid(self):
        """adr/0064 decision 2: cardDataAttributes.detailGroup.

        regularHoliday now shares dl.candidate-facts with totalSeats/
        nonSmokingStatus/dinnerBudgetTier -- the same DOM container, per the
        contract's new Must -- and no longer has a fieldRow call inside
        candidate-card-detail-footer (which now carries only the provider
        link).
        """
        template = HOME_TEMPLATE.read_text(encoding="utf-8")
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        # Structural placement: exactly one facts.appendChild call builds
        # regularHoliday's fieldRow, and it is the same `facts` dl instance
        # every other detailGroup member above it already appends into
        # (all four calls sit between `var facts = el("dl", ...)` and
        # `card.appendChild(facts)`, with no other appendChild target
        # anywhere in between).
        facts_start = script.index('var facts = el("dl", { "class": "candidate-facts" }, []);')
        facts_end = script.index("card.appendChild(facts);", facts_start)
        facts_block = script[facts_start:facts_end]
        self.assertEqual(facts_block.count("facts.appendChild("), 4)
        self.assertIn(
            'fieldRow("定休日", "candidate-card-regular-holiday", candidate.regularHoliday)',
            facts_block,
        )
        self.assertIn('"candidate-card-total-seats"', facts_block)
        self.assertIn('"candidate-card-non-smoking"', facts_block)
        self.assertIn('"candidate-card-dinner-budget"', facts_block)

        # The old detail-footer fieldRow call is gone -- that container now
        # wraps only the provider link.
        footer_call = (
            'card.appendChild(el("div", { "class": "candidate-card-detail-footer" }, [link]));'
        )
        self.assertIn(footer_call, script)
        self.assertNotIn(
            'fieldRow("定休日", "candidate-card-regular-holiday", candidate.regularHoliday),\n'
            "        link,",
            script,
        )

        # No truncation regression: the facts grid still wraps rather than
        # clipping long provider free text (overflow-wrap replaces the old
        # detail-footer-only white-space/overflow-wrap pair, which moved
        # with regularHoliday into this shared, generic rule).
        self.assertIn("overflow-wrap: anywhere", template)
        self.assertNotIn("max-height: 13.5rem", template)

    def test_unchanged_filter_panel_omits_batch_actions(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("var actions = [];", source)
        self.assertIn("actions.push(apply);", source)
        self.assertIn("if (actions.length > 0)", source)

    def test_filter_opener_uses_the_contract_test_id_and_allowed_control_purpose(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('"data-testid": "candidate-filter-open"', source)
        self.assertIn('"data-candidate-control-purpose": "candidate-filter-open"', source)
        self.assertNotIn('"data-testid": "candidate-filter-toggle"', source)
        self.assertNotIn('"data-candidate-control-purpose": "candidate-filter-toggle"', source)

    def test_pending_filter_text_cannot_replace_the_applied_summary(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("filterSummaryText(currentFilters)", source)
        self.assertIn("searchAgain.disabled = dirty", source)
        self.assertIn("if (matchCount === 0 || !dirty)", source)

    def test_filter_controls_keep_a_44px_minimum_target(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(".candidate-chip,", source)
        self.assertIn("min-height: 2.75rem", source)
        self.assertIn(".candidate-chip { min-width: 2.75rem; }", source)

    def test_desktop_visual_polish_keeps_filter_workflow(self):
        # The desktop-only horizontal-deck scrollbar theming this test used
        # to also guard is retired along with the deck itself (task 3; see
        # test_list_primary_map_ribbon_and_full_screen_sheet_keep_one_map_
        # instance above) -- [data-testid="candidate-proposal-cards"] is a
        # plain vertical list at every width now, so it has no desktop-only
        # scrollbar/fade styling left to assert.
        template = HOME_TEMPLATE.read_text(encoding="utf-8")
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", template)
        self.assertIn("position: absolute; top: calc(100% + 0.5rem)", template)
        self.assertIn("candidate-search-again-label", template)
        self.assertIn('"class": "candidate-search-again-label"', script)
        self.assertIn('"aria-hidden": "true"', script)

    def test_search_again_label_is_renamed_and_visible_under_every_render_mode(self):
        """adr/0064 decision 1: searchAgainControl's visible-label Must.

        The label reads "別の候補を出す" (not the retired "もう一度探す"),
        and no width-scoped override collapses this control back to a bare
        circular icon -- the shape the human ruling explicitly retired.
        """
        template = HOME_TEMPLATE.read_text(encoding="utf-8")
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        label_and_sr_text = (
            '["別の候補を出す"]),\n'
            '        el("span", { "class": "visually-hidden" }, ["別の候補を出す"])'
        )
        self.assertIn(label_and_sr_text, script)
        self.assertNotIn("もう一度探す", script)

        # No override anywhere in the template turns this control back into
        # an icon-only circle -- the label-hiding rule the narrow-width
        # media query used to pair with a circular .candidate-search-again
        # shape override is gone outright.
        self.assertNotIn(".candidate-search-again-label { display: none; }", template)

    def test_mobile_filter_panel_overlays_and_selected_chips_have_a_checkmark(self):
        template = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("overflow: visible;", template)
        self.assertIn("top: calc(100% + 0.4rem)", template)
        self.assertIn("background: rgb(255 255 255 / 98%)", template)
        self.assertIn('.candidate-chip[data-pressed="true"]::before', template)
        self.assertIn('content: "✓"', template)

    def test_soft_filter_labels_do_not_claim_unknown_values_are_confirmed(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("カード利用不可を除く", source)
        self.assertIn("ディナー予算感", source)
        self.assertIn("ディナー予算 ", source)
        self.assertIn(
            'fieldRow(\n        "ディナー予算感",\n        "candidate-card-dinner-budget"', source
        )
        self.assertIn('["クレジットカード非対応（支払い方法は要確認）"]', source)
        self.assertNotIn("お支払い方法は店舗にご確認ください", source)


class GenreOrderingAndFilterGroupingSourceTests(SimpleTestCase):
    """adr/0024 decisions 1-2: genre count-descending order, izakaya/bar regrouping."""

    def test_genre_order_no_longer_sorts_by_string_length_alone(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        # The retired sole ordering rule (adr/0023 decision 12) sorted
        # currentAvailableGenres directly; that direct call must be gone.
        self.assertNotIn(
            "currentAvailableGenres.slice().sort(function (left, right) {\n"
            "      return left.length - right.length",
            source,
        )

    def test_genre_population_counts_are_scoped_like_available_genres(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function genrePopulationCounts()", source)
        self.assertIn("currentFilters.includeIzakayaBar", source)
        self.assertIn("row.defaultExcluded", source)

    def test_ordered_available_genres_uses_count_then_the_original_tie_break(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function orderedAvailableGenres()", source)
        self.assertIn("countDifference", source)
        self.assertIn('left.length - right.length || left.localeCompare(right, "ja")', source)

    def test_genre_chips_uses_the_new_ordering_function(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("var orderedGenres = orderedAvailableGenres();", source)

    def test_izakaya_bar_toggle_renders_in_the_genre_row_not_the_preference_row(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        # It must render first within the genre row's own horizontally
        # scrollable sub-container -- ahead of the genre option chips --
        # so it stays within that sub-container's initially visible range
        # on narrow viewports (contracts/candidate-search-browser-
        # interface.yaml's controlGrouping.genreGroup requires membership
        # only, not order). adr/0025 + human decision 2026-08-23 moved the
        # overflow toggle itself out to a DOM sibling of this
        # sub-container (see genreGroupRow), which this test does not
        # re-assert (covered by the overflow-placement test below).
        self.assertIn("[izakayaBarToggleChip()].concat(genreOptionChips(visible))", source)
        self.assertIn("function izakayaBarToggleChip()", source)
        self.assertIn("function genreGroupRow()", source)

        # The old placement -- as a member of the "こだわり" chip array --
        # must be gone: candidate-filter-include-izakaya-bar's testId/purpose
        # must only be defined once, inside izakayaBarToggleChip.
        self.assertEqual(source.count('testId: "candidate-filter-include-izakaya-bar"'), 1)
        self.assertEqual(source.count('"candidate-filter-izakaya-bar-toggle"'), 1)

        preference_row_start = source.index('chipRow("こだわり", [')
        preference_row_end = source.index("]),", preference_row_start)
        preference_row_source = source[preference_row_start:preference_row_end]
        self.assertNotIn("izakaya", preference_row_source)

    def test_genre_overflow_toggle_is_the_leading_member_outside_the_scrollable_subgroup(self):
        # Human decision 2026-08-23 (design/wireframes/GenreRow.dc.html
        # option (c)): candidate-filter-genre-overflow must be a DOM
        # sibling that precedes the scrollable sub-container holding
        # izakayaBarToggleChip() and the genre option chips, not a
        # descendant of it -- otherwise its position would move with that
        # sub-container's own horizontal scroll offset (the entry point to
        # hidden genres must stay reachable regardless of scroll position).
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function genreOverflowToggle(hiddenCount, expanded)", source)
        group_start = source.index("function genreGroupRow()")
        group_end = source.index("function walkingTimeMaxChips()", group_start)
        group_source = source[group_start:group_end]

        # groupChildren's own push order is genreGroupRow's actual DOM
        # append order (el() appends each array member in sequence), unlike
        # the earlier `var scrollable = ...` declaration above these two
        # pushes, which is source-text order only and not DOM order.
        overflow_push_index = group_source.index(
            "groupChildren.push(genreOverflowToggle(hidden, genreOverflowExpanded));"
        )
        scrollable_push_index = group_source.index("groupChildren.push(scrollable);")
        self.assertLess(
            overflow_push_index,
            scrollable_push_index,
            "the overflow toggle must be appended to groupChildren before the scrollable container",
        )


class ShownCandidateMemorySourceTests(SimpleTestCase):
    """adr/0024 decision 4 (and item 8): browser-held shown-candidate priority."""

    def test_session_storage_key_and_twenty_hour_max_age_are_present(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            'var SHOWN_CANDIDATE_MEMORY_KEY = "dining-radar:shown-provider-page-urls";', source
        )
        # 20 hours, never the regulatory 24-hour ceiling itself (adr/0024
        # decision 4 item 8's stated safety margin).
        self.assertIn("var SHOWN_CANDIDATE_MEMORY_MAX_AGE_MS = 20 * 60 * 60 * 1000;", source)
        self.assertNotIn("24 * 60 * 60 * 1000", source)

    def test_expiry_is_pruned_on_both_read_paths(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function currentShownProviderPageUrls()", source)
        self.assertIn("function updateShownCandidateMemory(body)", source)
        self.assertIn("function readShownCandidateMemory()", source)
        # requestRule: prune, then write back the surviving set before
        # reading urls from it (not merely skip expired entries for one read).
        self.assertIn(
            "var surviving = readShownCandidateMemory();\n"
            "    writeShownCandidateMemory(surviving);",
            source,
        )

    def test_shown_pool_exhausted_clears_memory_before_re_adding(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("body.shownPoolExhausted ? [] : readShownCandidateMemory()", source)

    def test_stored_at_is_never_sent_to_the_server(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        # currentShownProviderPageUrls returns url values only (entry.url),
        # never the storedAt timestamp.
        self.assertIn(
            "return surviving.map(function (entry) {\n      return entry.url;\n    });", source
        )

    def test_request_proposal_attaches_shown_provider_page_urls_when_non_empty(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("var shownProviderPageUrls = currentShownProviderPageUrls();", source)
        self.assertIn(
            "if (shownProviderPageUrls.length > 0) {\n"
            "      body.shownProviderPageUrls = shownProviderPageUrls;\n"
            "    }",
            source,
        )

    def test_handle_proposal_response_updates_memory_on_every_successful_response(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        success_branch_start = source.index("if (status === 200) {")
        success_branch_end = source.index("return;", success_branch_start)
        success_branch_source = source[success_branch_start:success_branch_end]
        self.assertIn("updateShownCandidateMemory(body);", success_branch_source)


class LeafletVendoringRenderedPageTests(TestCase):
    """The authenticated screen's rendered HTML must carry the same-origin URLs."""

    def setUp(self):
        self.password = "Synthetic-passphrase-123!"
        self.user = get_user_model().objects.create_user(
            username="static-asset-organizer", password=self.password
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_rendered_home_page_references_the_same_origin_leaflet_assets(self):
        page = self.client.get(reverse("web:home"))
        body = page.content.decode("utf-8")

        self.assertIn("/static/dining_radar/web/vendor/leaflet/leaflet.css", body)
        self.assertIn("/static/dining_radar/web/vendor/leaflet/leaflet.js", body)

    def test_rendered_home_page_never_contacts_a_third_party_cdn_for_leaflet(self):
        page = self.client.get(reverse("web:home"))
        body = page.content.decode("utf-8")

        self.assertNotIn("unpkg.com", body)
        self.assertNotIn("cdn.jsdelivr.net", body)
        self.assertNotIn("cdnjs.cloudflare.com", body)


class PrimaryNavSourceTests(SimpleTestCase):
    """ADR-0059 (2026-09-16, 束A「上部ナビと会への戻り道」): the redrawn
    primary nav (desktop ≡ menu / mobile bottom bar, both mutually
    exclusive render-mode shapes) and the "入れた瞬間の小窓" return path.
    Mirrors this module's own CandidateSurfaceSourceTests source-text-
    assertion style -- these are markup/JS structural checks, not a
    substitute for tests/acceptance's own browser-executed L4/L5 coverage.
    """

    def test_home_template_server_renders_both_render_mode_shapes_unconditionally(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        # authentication-browser-interface.yaml's renderModel (2026-09-16
        # amendment): auth-sign-out/auth-password-change-open must exist in
        # server-rendered HTML, not be JS-inserted -- both the desktop menu
        # panel and the mobile account sheet carry their own copy here
        # (candidate.js's initializePrimaryNav removes whichever one does
        # not match the viewport at DOMContentLoaded, after the raw HTTP
        # response TDR-AUTH reads has already carried both).
        self.assertIn("data-primary-nav-desktop", source)
        self.assertIn('data-testid="candidate-primary-nav-menu-toggle"', source)
        self.assertIn('data-candidate-control-purpose="candidate-primary-nav-menu-toggle"', source)
        self.assertIn('data-testid="candidate-primary-nav-menu-panel"', source)
        self.assertIn('data-testid="candidate-primary-nav-menu-search"', source)
        self.assertIn('data-testid="candidate-primary-nav-menu-gathering"', source)
        self.assertIn("data-primary-nav-mobile", source)
        self.assertIn('data-testid="candidate-primary-nav-bar"', source)
        self.assertIn('data-testid="candidate-primary-nav-search"', source)
        self.assertIn('data-testid="candidate-primary-nav-gathering"', source)
        self.assertIn('data-testid="candidate-primary-nav-account"', source)
        self.assertIn('data-candidate-control-purpose="auth-account-menu-toggle"', source)
        self.assertIn('id="primary-nav-account-sheet"', source)
        # Each of the two account-control copies (menu panel, mobile sheet)
        # carries its own auth-sign-out/auth-password-change-open, per
        # menuPanel/mobileBarAccount's own requirement text -- both testids
        # appear (at least) twice in the raw template source.
        self.assertEqual(source.count('data-testid="auth-sign-out"'), 2)
        self.assertEqual(source.count('data-testid="auth-password-change-open"'), 2)

    def test_home_template_never_server_renders_the_chip(self):
        # gatheringEntry.entry.requirement (revised 2026-09-16): the chip
        # itself (not only its badge) must be entirely absent from the DOM
        # at count zero -- candidate.js builds it in full, once fetched
        # (loadGatheringEntryBadge), never server-rendered in home.html.
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn('data-testid="candidate-gathering-entry"', source)

    def test_home_template_retires_the_old_adr_0054_nav_and_account_menu(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn('class="gathering-primary-nav"', source)
        self.assertNotIn('data-testid="auth-account-menu-toggle"', source)
        self.assertNotIn('class="candidate-account-menu"', source)
        self.assertNotIn('class="account-nav"', source)

    def test_home_template_heading_reads_the_2026_09_16_wording(self):
        # ADR-0059 decision 7: this heading carries no contract test id, so
        # the wording change is implementation-only.
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("<h1>ランチ候補をさがす</h1>", source)
        self.assertNotIn("<h1>ランチ候補</h1>", source)

    def test_home_template_shortlist_toast_test_ids_are_present(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("candidate-gathering-shortlist-toast", source)
        self.assertIn("candidate-gathering-shortlist-toast-return", source)

    def test_organizer_primary_nav_partial_matches_the_render_mode_shapes(self):
        source = PRIMARY_NAV_PARTIAL.read_text(encoding="utf-8")

        self.assertIn('data-testid="candidate-primary-nav-menu-toggle"', source)
        self.assertIn('data-testid="candidate-primary-nav-menu-panel"', source)
        self.assertIn('data-testid="candidate-primary-nav-menu-search"', source)
        self.assertIn('data-testid="candidate-primary-nav-menu-gathering"', source)
        self.assertIn('data-testid="candidate-primary-nav-bar"', source)
        self.assertIn('data-testid="candidate-primary-nav-search"', source)
        self.assertIn('data-testid="candidate-primary-nav-gathering"', source)
        self.assertIn('data-testid="candidate-primary-nav-account"', source)
        self.assertIn('id="primary-nav-account-sheet"', source)
        self.assertEqual(source.count('data-testid="auth-sign-out"'), 2)
        self.assertEqual(source.count('data-testid="auth-password-change-open"'), 2)

    def test_organizer_primary_nav_partial_never_renders_the_chip(self):
        # ADR-0059 decision 2 reverses ADR-0054 decision 1's "unconditional
        # on every organizer-facing screen too" for candidate-gathering-
        # entry specifically -- gatheringEntry.entry.requirement now
        # excludes these three screens.
        source = PRIMARY_NAV_PARTIAL.read_text(encoding="utf-8")

        self.assertNotIn('data-testid="candidate-gathering-entry"', source)

    def test_organizer_primary_nav_partial_hardcodes_current_location(self):
        # These three screens are always "current" for the ランチ会
        # destination and never "current" for さがす -- no JS is needed for
        # this (unlike home.html's own JS-computed copy, which must react
        # to gathering mode on the *same* URL).
        source = PRIMARY_NAV_PARTIAL.read_text(encoding="utf-8")

        self.assertIn(
            'data-testid="candidate-primary-nav-menu-search"\n'
            '        data-primary-nav-current="false"',
            source,
        )
        self.assertIn(
            'data-testid="candidate-primary-nav-menu-gathering"\n'
            '        data-primary-nav-current="true"',
            source,
        )
        self.assertIn(
            'data-testid="candidate-primary-nav-search"\n    data-primary-nav-current="false"',
            source,
        )
        self.assertIn(
            'data-testid="candidate-primary-nav-gathering"\n    data-primary-nav-current="true"',
            source,
        )

    def test_three_gathering_templates_include_the_primary_nav_partial(self):
        for template in (DASHBOARD_TEMPLATE, GATHERING_CREATE_TEMPLATE, GATHERING_LIST_TEMPLATE):
            with self.subTest(template=template.name):
                source = template.read_text(encoding="utf-8")
                self.assertIn('{% include "gathering/organizer_primary_nav.html" %}', source)

    def test_organizer_css_defines_the_new_primary_nav_classes_not_the_old_ones(self):
        source = ORGANIZER_CSS.read_text(encoding="utf-8")

        self.assertIn(".primary-nav-menu-toggle {", source)
        self.assertIn(".primary-nav-menu-panel {", source)
        self.assertIn(".primary-nav-bar {", source)
        self.assertIn(".primary-nav-account-sheet {", source)
        self.assertNotIn(".gathering-primary-nav {", source)
        self.assertNotIn(".gathering-primary-nav-link", source)

    def test_candidate_js_band_is_a_status_only_div_with_no_navigation(self):
        # ADR-0059 decision 5: gatheringMode.band.navigationNote -- the band
        # is no longer returnToGatheringFromBand's input; renderGathering
        # ModeBand must build a plain, href-less <div>, and the retired
        # browserAction/empty|filled navigation-styled classes must not
        # resurface.
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        band_fn_start = source.index("function renderGatheringModeBand(context) {")
        band_fn_end = source.index("\n  }\n", band_fn_start)
        band_fn_source = source[band_fn_start:band_fn_end]
        self.assertIn('el(\n      "div",', band_fn_source)
        self.assertNotIn("href:", band_fn_source)

        self.assertNotIn("returnToGatheringFromBand", source)
        self.assertNotIn('"candidate-gathering-mode-band--empty"', source)
        self.assertNotIn('"candidate-gathering-mode-band--filled"', source)

    def test_candidate_js_builds_the_shortlist_toast_only_on_an_addition(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function renderGatheringShortlistToast(context) {", source)
        self.assertIn("function dismissGatheringShortlistToast() {", source)
        self.assertIn('"data-testid": "candidate-gathering-shortlist-toast"', source)
        self.assertIn('"data-testid": "candidate-gathering-shortlist-toast-return"', source)
        self.assertIn("var isAddition = false;", source)
        self.assertIn(
            "if (isAddition) {\n          renderGatheringShortlistToast(currentGatheringContext);\n"
            "        }",
            source,
        )
        # shortlistToast.presenceRule: does not self-dismiss once
        # shortlistedShopCount equals maxShortlistedShops -- the timer is
        # only started in the non-limit-reached branch.
        self.assertIn("if (!limitReached) {\n      shortlistToastDismissTimer", source)

    def test_candidate_js_defines_initialize_primary_nav_and_sync_helpers(self):
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function initializePrimaryNav() {", source)
        self.assertIn("function syncPrimaryNavGatheringLinks() {", source)
        self.assertIn("initializePrimaryNav();", source)
        # renderModes.invariant: exactly one render-mode nav survives --
        # the other's whole subtree is removed outright (never merely
        # hidden), mirroring this file's own isTwoColumnLayout precedent.
        self.assertIn('document.querySelectorAll("[data-primary-nav-mobile]")', source)
        self.assertIn('document.querySelector("[data-primary-nav-desktop]")', source)
        # gatheringEntry.menuDestinationSearch/mobileBarSearch's own no-op
        # rule (activating it while already current does not reload).
        self.assertIn("event.preventDefault();", source)
        # Esc closes both the ≡ <details> and the mobile account sheet.
        self.assertIn('event.key !== "Escape" && event.key !== "Esc"', source)

    def test_candidate_js_no_longer_builds_the_chip_from_a_static_element(self):
        # loadGatheringEntryBadge must build the whole chip in full (not
        # look one up that home.html no longer server-renders).
        source = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        badge_fn_start = source.index("function loadGatheringEntryBadge() {")
        badge_fn_end = source.index("\n  }\n", badge_fn_start)
        badge_fn_source = source[badge_fn_start:badge_fn_end]
        self.assertIn('el(\n              "a",', badge_fn_source)
        self.assertIn(
            "document.querySelector('[data-testid=\"candidate-primary-nav-gathering\"]')",
            badge_fn_source,
        )

    def test_gathering_scripts_define_initialize_primary_nav_and_drop_the_chip_lookup(self):
        for script in (GATHERING_SCRIPT, GATHERING_CREATE_SCRIPT, GATHERING_LIST_SCRIPT):
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                self.assertIn("function initializePrimaryNav() {", source)
                self.assertIn("initializePrimaryNav();", source)
                self.assertIn(
                    "document.querySelector('[data-testid=\"candidate-primary-nav-gathering\"]')",
                    source,
                )
                # ADR-0059 decision 2: these three screens never build
                # candidate-gathering-entry (the chip) at all any longer.
                self.assertNotIn('"data-testid": "candidate-gathering-entry"', source)
                self.assertNotIn("candidate-gathering-entry-badge", source)
