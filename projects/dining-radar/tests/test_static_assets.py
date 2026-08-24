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

    def test_map_led_deck_keeps_cards_and_map_in_the_same_surface(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('grid-template-areas: "map" "cards"', source)
        self.assertIn("scroll-snap-type: inline mandatory", source)
        self.assertIn("height: calc(100dvh - 6.875rem)", source)
        self.assertIn("position: absolute; inset: 0", source)
        self.assertIn("height: clamp(22rem, 50dvh, 34rem)", source)
        self.assertIn("flex: 0 0 calc(100vw - 2rem)", source)
        self.assertIn("min-height: 12.9rem", source)
        self.assertIn("scrollbar-width: none", source)
        self.assertIn("isolation: isolate", source)
        self.assertIn("top: 0.5rem;\n      right: 0.5rem", source)
        self.assertIn("background: rgb(255 255 255 / 92%)", source)

    def test_mobile_layout_keeps_decision_controls_compact(self):
        template = HOME_TEMPLATE.read_text(encoding="utf-8")
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("min-height: 3.25rem", template)
        self.assertIn("height: 3.5rem", template)
        self.assertIn("height: 3.25rem", template)
        self.assertIn("flex-wrap: nowrap; overflow-x: auto", template)
        self.assertIn("candidate-card-description", template)
        self.assertIn("display: none", template)
        self.assertIn('"data-testid": "candidate-deck-counter"', script)
        self.assertIn('["1/" + String(body.candidates.length)]', script)

    def test_card_payment_caution_and_regular_holiday_do_not_overstate_or_truncate(self):
        template = HOME_TEMPLATE.read_text(encoding="utf-8")
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("クレジットカード非対応（支払い方法は要確認）", script)
        self.assertIn("candidate-fact-row--candidate-card-regular-holiday", template)
        self.assertIn("flex-direction: column; align-items: stretch", template)
        self.assertIn("width: 100%", template)
        self.assertIn("white-space: normal", template)
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

    def test_desktop_visual_polish_keeps_filter_workflow_and_deck_cues(self):
        template = HOME_TEMPLATE.read_text(encoding="utf-8")
        script = CANDIDATE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", template)
        self.assertIn("position: absolute; top: calc(100% + 0.5rem)", template)
        self.assertIn('[data-testid="candidate-proposal-cards"]::after', template)
        self.assertIn("scrollbar-width: thin", template)
        self.assertIn("scrollbar-color: #8da093 transparent", template)
        self.assertIn(
            '[data-testid="candidate-proposal-cards"]::-webkit-scrollbar { height: 0.5rem; }',
            template,
        )
        self.assertIn("candidate-search-again-label", template)
        self.assertIn('"class": "candidate-search-again-label"', script)
        self.assertIn('"aria-hidden": "true"', script)

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
