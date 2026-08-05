"""JS-capable browser L4 runner for TDR-CS-00 through TDR-CS-08.

Per ADR-0009, the authenticated candidate-proposal screen renders candidate
cards, the map, the re-proposal modal, and error surfaces with client-side
JavaScript after the server returns only an empty mount point. Every scenario
in this file therefore runs against a real Chromium instance (Playwright)
that executes that script, rather than against server-rendered HTML.

Every scenario below executes for real -- none is skipped. As of this
writing, ``test_tdr_cs_02_compare_candidates_on_cards_and_map`` and
``test_tdr_cs_03_reproposal_via_popup_replaces_the_display`` fail against the
current implementation: enumerating every ``[data-testid]`` element on the
fully-rendered authenticated screen (with the ``NORMAL_WITH_REPEAT``
synthetic Given state) finds ``candidate-card``, ``candidate-map``, and every
other test id ``candidate-search-browser-interface.yaml`` requires, but no
``candidate-map-marker`` anywhere -- Leaflet's own marker DOM element carries
only a plain CSS class (``candidate-map-marker-icon``), not the contract's
``data-testid``/``data-candidate-ref``/``data-selection-state`` attributes.
This is a red, not a skip: per this project's step-definition rules, testers
do not read or adapt to implementation source, so this file asserts exactly
what the contract requires and reports the resulting failure rather than
working around it.
"""

from __future__ import annotations

import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.steps.candidate_search_steps import CandidateSearchSteps


class CandidateSearchAcceptanceTests(StaticLiveServerTestCase):
    """Each method mirrors one approved TDR-CS browser scenario.

    Unlike TDR-AUTH's plain-HTTP tests (which only ever fetch the raw HTML
    document and never a linked asset), a real browser also requests every
    CSS/JS/image the client-rendered screen references -- including the
    server-served ``static/`` assets this screen depends on (``candidate.js``,
    and Leaflet's vendored dist per ADR-0010). ``StaticLiveServerTestCase``
    serves those through the staticfiles finders (source tree, no build/
    collectstatic step), unlike plain ``LiveServerTestCase`` which requires a
    populated ``STATIC_ROOT``. This is a test-harness choice local to this
    file; it does not change the application's own static-file configuration.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._previous_base_url = os.environ.get("TDR_ACCEPTANCE_BASE_URL")
        os.environ["TDR_ACCEPTANCE_BASE_URL"] = cls.live_server_url
        # Playwright's sync API marks an asyncio loop as "running" in this
        # thread as a side effect of waiting on browser events (its sync
        # wrapper drives an underlying async client through a greenlet
        # dispatcher). Django's per-test `flush` (required because
        # LiveServerTestCase/StaticLiveServerTestCase reset data by flushing,
        # not transaction rollback, since the live server runs on its own
        # thread/connection) then misreads that leftover marker as "we are
        # inside async code" and refuses the synchronous DB call. This is a
        # known interaction between Playwright's sync API and Django's
        # `async_unsafe` guard, not a change to what is being verified here.
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
        # A fresh browser context per test is an isolated cookie jar (no
        # organizer session survives across tests) and an isolated page.
        self.context = self._browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dsl = CandidateSearchBrowserDsl(self, self.page, base_url)
        self.steps = CandidateSearchSteps(self.dsl)
        self.steps.reset_state()

    def test_tdr_cs_00_unauthenticated_visitor_is_guided_to_sign_in(self) -> None:
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.visitor_opens_candidate_proposal_screen()
        self.steps.visitor_is_guided_to_sign_in_without_candidate_surface()

    def test_tdr_cs_01_initial_candidates_and_map_are_compared_immediately(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.initial_lens_and_map_are_shown()
        self.steps.initial_display_requests_no_secondary_input()
        self.steps.initial_lens_has_a_rationale()
        self.steps.initial_candidates_have_no_duplicate_shop()
        self.steps.screen_has_no_private_disclosures()
        self.steps.source_display_and_detail_link_are_shown()

    def test_tdr_cs_02_compare_candidates_on_cards_and_map(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_has_one_lens_of_candidates()
        self.steps.current_lens_shops_are_in_cards_and_map()
        self.steps.selecting_a_card_highlights_its_marker()
        self.steps.selecting_a_marker_highlights_its_card()
        self.steps.map_shows_source_attribution()
        self.steps.cards_show_required_shop_fields()
        self.steps.map_has_no_forbidden_surfaces()

    def test_tdr_cs_03_reproposal_via_popup_replaces_the_display(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_has_one_lens_of_candidates()
        self.steps.organizer_opens_reproposal_popup()
        self.steps.reproposal_options_exclude_current_lens_and_are_bounded()
        chosen_kind = self.steps.organizer_selects_a_different_lens()
        self.steps.new_proposal_replaces_display_with_chosen_lens(chosen_kind)
        self.steps.repeat_priority_orders_new_before_repeated()
        self.steps.repeated_candidate_is_not_excluded()

    def test_tdr_cs_04_no_secondary_conditions_or_manual_sort(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.initial_display_requests_no_secondary_input()
        self.steps.concept_choice_is_available_only_via_reproposal()

    def test_tdr_cs_05_no_matching_lunch_candidates(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.no_candidates_match_chosen_lens()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.no_matching_candidates_are_shown()
        self.steps.no_matching_candidates_are_shown_by_api()

    def test_tdr_cs_06_candidate_information_is_unavailable(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.candidate_information_is_unavailable_now()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.organizer_is_safely_guided_to_try_later()
        self.steps.organizer_is_safely_guided_to_try_later_by_api()

    def test_tdr_cs_07_unsupported_reproposal_lens_is_rejected(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_has_one_lens_of_candidates()
        self.steps.organizer_requests_an_unsupported_lens_directly("AMENITY_REFERENCE")
        self.steps.unsupported_lens_is_rejected()

    def test_tdr_cs_08_repeated_requests_are_rate_limited(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.organizer_is_repeatedly_requesting_proposals()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.organizer_is_guided_to_wait_and_retry()
        self.steps.organizer_is_guided_to_wait_and_retry_by_api()
