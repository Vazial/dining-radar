"""JS-capable browser L4 runner for the current TDR-CS scenarios."""

from __future__ import annotations

import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl
from tests.acceptance.steps.candidate_search_steps import CandidateSearchSteps


class CandidateSearchAcceptanceTests(StaticLiveServerTestCase):
    """Each test mirrors one current TDR-CS scenario through Chromium."""

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
        self.dsl = CandidateSearchBrowserDsl(self, self.page, os.environ["TDR_ACCEPTANCE_BASE_URL"])
        self.steps = CandidateSearchSteps(self.dsl)
        self.steps.reset_state()

    def _sign_in(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )

    def test_tdr_cs_00_unauthenticated_visitor_is_guided_to_sign_in(self) -> None:
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.visitor_opens_candidate_proposal_screen()
        self.steps.visitor_is_guided_to_sign_in_without_candidate_surface()

    def test_tdr_cs_01_initial_candidates_and_map_are_compared_immediately(self) -> None:
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.default_filters_and_nearest_candidates_are_shown()
        self.steps.initial_display_requests_no_filter_input()
        self.steps.initial_candidates_have_no_duplicate_shop()
        self.steps.search_origin_marker_is_shown()
        self.steps.search_range_value_is_not_shown()
        self.steps.source_display_and_detail_link_are_shown()

    def test_tdr_cs_02_compare_candidates_on_cards_and_map(self) -> None:
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_has_filtered_candidates()
        self.steps.current_candidates_are_in_cards_and_map()
        self.steps.selecting_a_card_highlights_its_marker()
        self.steps.selecting_a_marker_highlights_its_card()
        self.steps.map_shows_displayed_candidates_and_attribution()
        self.steps.map_shows_search_origin_marker_and_walking_radius_rings()
        self.steps.cards_show_required_shop_fields()
        self.steps.walking_time_is_shown_as_an_estimate()
        self.steps.organizer_opens_filter_panel()
        self.steps.dinner_budget_reference_is_disclosed_once_on_screen()
        self.steps.walking_route_and_current_location_are_not_shown()
        self.steps.search_range_value_is_not_shown()

    def test_tdr_cs_03_changed_filters_replace_the_proposal(self) -> None:
        self._sign_in()
        self.steps.zero_pending_match_can_be_observed()
        self.steps.organizer_has_filtered_candidates()
        self.steps.organizer_opens_filter_panel()
        self.steps.organizer_enables_card_payment_filter()
        self.steps.organizer_adds_low_budget_filter()
        self.steps.organizer_reverts_pending_filters()
        self.steps.organizer_enables_card_payment_filter()
        self.steps.organizer_closes_filter_panel()
        self.steps.organizer_reopens_filter_panel()
        self.steps.organizer_applies_changed_filters()
        self.steps.changed_filters_are_sent_in_a_new_proposal_request()
        self.steps.new_filtered_proposal_replaces_the_display()
        self.steps.new_filtered_proposal_only_has_matching_or_unknown_candidates()
        self.steps.new_filtered_proposal_uses_the_display_ordering()

    def test_tdr_cs_04_private_search_location_and_range_cannot_be_selected(self) -> None:
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.no_location_range_or_manual_order_control_exists()
        self.steps.search_origin_marker_is_display_only()

    def test_tdr_cs_05_no_matching_lunch_candidates(self) -> None:
        self._sign_in()
        self.steps.no_candidates_match_applied_filters()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.no_matching_candidates_are_shown_distinct_from_a_problem()
        self.steps.organizer_can_change_filters()

    def test_tdr_cs_06_candidate_information_is_unavailable(self) -> None:
        self._sign_in()
        self.steps.candidate_information_is_unavailable_now()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.organizer_is_safely_guided_to_try_later()
        self.steps.organizer_is_safely_guided_to_try_later_by_api()

    def test_tdr_cs_08_repeated_requests_are_rate_limited(self) -> None:
        self._sign_in()
        self.steps.organizer_is_repeatedly_requesting_proposals()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.organizer_is_guided_to_wait_and_retry()
        self.steps.organizer_is_guided_to_wait_and_retry_by_api()

    def test_tdr_cs_09_izakaya_bar_is_excluded_by_default_and_can_be_included(self) -> None:
        self._sign_in()
        self.steps.candidates_include_a_hard_to_confirm_lunch_genre()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.initial_request_uses_default_izakaya_bar_exclusion()
        self.steps.organizer_opens_filter_panel()
        self.steps.izakaya_bar_filter_is_available()
        self.steps.organizer_includes_izakaya_bar()
        self.steps.organizer_applies_changed_filters()
        self.steps.including_izakaya_bar_adds_previously_excluded_candidates()

    def test_tdr_cs_10_default_izakaya_bar_exclusion_falls_back_only_when_needed(self) -> None:
        self._sign_in()
        self.steps.only_izakaya_bar_candidates_can_be_proposed()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.organizer_opens_filter_panel()
        self.steps.organizer_selects_a_filter_preserved_by_fallback()
        self.steps.organizer_applies_changed_filters()
        self.steps.fallback_candidates_and_uncertainty_notice_are_shown()
        self.steps.fallback_preserves_the_explicit_filter()
        self.steps.no_results_guidance_is_not_shown()
        self.steps.organizer_opens_filter_panel()
        self.steps.organizer_selects_an_explicit_genre_with_no_matches()
        self.steps.explicit_genre_filter_is_not_relaxed_by_fallback()

    def test_tdr_cs_11_search_again_reuses_filters_and_can_change_sample(self) -> None:
        self._sign_in()
        self.steps.seeded_lunch_candidates_can_be_proposed(7)
        self.steps.organizer_has_filtered_candidates()
        self.steps.candidate_state_uses_a_different_random_seed(19)
        self.steps.organizer_searches_again()
        self.steps.search_again_reuses_the_same_filters_and_replaces_the_display()
        self.steps.new_seed_changes_the_candidate_sample()
        self.steps.candidate_state_reuses_the_original_random_seed(7)
        self.steps.organizer_searches_again_to_reproduce_the_original_sample()
        self.steps.original_seed_reproduces_the_original_candidate_sample()

    def test_tdr_cs_12_payment_caution_shown_only_when_card_payment_is_unavailable(self) -> None:
        self._sign_in()
        self.steps.candidates_include_a_shop_without_card_payment()
        self.steps.organizer_compares_candidates()
        self.steps.payment_caution_is_shown_for_shops_without_card_payment()
        self.steps.payment_caution_is_not_shown_for_other_shops()

    def test_tdr_cs_13_unknown_soft_filter_information_is_kept_and_sorts_last(self) -> None:
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed()
        self.steps.organizer_has_filtered_candidates()
        self.steps.organizer_opens_filter_panel()
        self.steps.organizer_enables_a_filter_with_unknown_candidate_information()
        self.steps.organizer_applies_changed_filters()
        self.steps.confirmed_non_matching_candidates_are_excluded()
        self.steps.unknown_candidates_remain_with_an_unknown_state()
        self.steps.unknown_candidates_follow_confirmed_matches()

    def test_tdr_cs_14_previously_shown_candidates_are_postponed_not_excluded(self) -> None:
        self._sign_in()
        self.steps.a_large_pool_of_candidates_can_be_proposed()
        self.steps.organizer_has_filtered_candidates()
        self.steps.candidates_greatly_outnumber_the_display_count()
        self.steps.organizer_repeats_search_again_with_the_same_filters()
        self.steps.not_yet_shown_candidates_are_shown_first()
        self.steps.previously_shown_candidates_are_postponed_not_excluded()
        self.steps.previously_shown_candidates_can_reappear_after_a_full_cycle()
        self.steps.shown_memory_survives_a_reload_within_the_tab()
        self.steps.shown_memory_fades_after_its_retention_period()
        self.steps.shown_memory_is_not_shared_across_accounts_or_devices()

    def test_tdr_cs_15_walking_time_max_excludes_candidates(self) -> None:
        self._sign_in()
        self.steps.walking_time_limit_candidates_can_be_proposed()
        self.steps.organizer_has_filtered_candidates()
        self.steps.population_includes_a_candidate_beyond_the_upcoming_walking_time_max()
        self.steps.organizer_selects_a_walking_time_max_filter()
        self.steps.organizer_applies_changed_filters()
        self.steps.candidates_over_the_walking_time_max_are_excluded()
        self.steps.candidates_at_or_under_the_walking_time_max_remain()
        self.steps.no_candidate_remains_due_to_unknown_walking_time()

    def test_tdr_cs_16_a_fetch_failure_after_success_retains_prior_candidates(self) -> None:
        self._sign_in()

        self.steps.subsequent_requests_are_rate_limited_after_an_initial_success()
        self.steps.organizer_has_filtered_candidates()
        self.steps.organizer_attempts_to_search_again()
        self.steps.prior_candidates_and_map_remain()
        self.steps.fetch_failure_is_announced()

        self.steps.subsequent_requests_are_rate_limited_after_an_initial_success()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.organizer_opens_filter_panel()
        self.steps.organizer_enables_card_payment_filter()
        self.steps.organizer_attempts_to_apply_changed_filters()
        self.steps.prior_candidates_and_map_remain()
        self.steps.fetch_failure_is_announced()
