"""Thin scenario-to-DSL mappings for current TDR-CS acceptance scenarios."""

from __future__ import annotations

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl


class CandidateSearchSteps:
    def __init__(self, dsl: CandidateSearchBrowserDsl) -> None:
        self.dsl = dsl

    def reset_state(self) -> None:
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()

    def visitor_has_no_active_organizer_session(self) -> None:
        self.dsl.assert_no_active_session()

    def organizer_is_signed_in(self, account_ref: str, identifier: str, password: str) -> None:
        self.dsl.enable_organizer(account_ref, identifier, password)
        self.dsl.sign_in(identifier, password)

    def lunch_candidates_can_be_proposed(self) -> None:
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING")

    def zero_pending_match_can_be_observed(self) -> None:
        self.dsl.set_candidate_state("ZERO_PENDING_MATCH")

    def seeded_lunch_candidates_can_be_proposed(self, seed: int) -> None:
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING", random_seed=seed)

    def candidate_state_uses_a_different_random_seed(self, seed: int) -> None:
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING", random_seed=seed)

    def candidate_state_reuses_the_original_random_seed(self, seed: int) -> None:
        self.dsl.set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING", random_seed=seed)

    def no_candidates_match_applied_filters(self) -> None:
        self.dsl.set_candidate_state("NO_RESULTS")

    def candidate_information_is_unavailable_now(self) -> None:
        self.dsl.set_candidate_state("PROVIDER_UNAVAILABLE")

    def organizer_is_repeatedly_requesting_proposals(self) -> None:
        self.dsl.set_candidate_state("RATE_LIMITED")

    def candidates_include_a_hard_to_confirm_lunch_genre(self) -> None:
        self.dsl.set_candidate_state("DEFAULT_EXCLUSION_VISIBLE")

    def only_izakaya_bar_candidates_can_be_proposed(self) -> None:
        self.dsl.set_candidate_state("FALLBACK_PRESERVES_FILTERS")

    def candidates_include_a_shop_without_card_payment(self) -> None:
        self.dsl.set_candidate_state("CARD_PAYMENT_CAUTION_VISIBLE")

    def a_large_pool_of_candidates_can_be_proposed(self) -> None:
        self.dsl.set_candidate_state("SHOWN_POOL_PRIORITY")

    def visitor_opens_candidate_proposal_screen(self) -> None:
        self.dsl.open_candidate_screen_unauthenticated()

    def organizer_opens_candidate_proposal_screen(self) -> None:
        self.dsl.open_candidate_screen()

    def organizer_has_filtered_candidates(self) -> None:
        self.dsl.open_candidate_screen()

    def organizer_compares_candidates(self) -> None:
        self.dsl.open_candidate_screen()

    def organizer_opens_filter_panel(self) -> None:
        self.dsl.open_filter_panel()

    def organizer_enables_card_payment_filter(self) -> None:
        self.dsl.enable_card_payment_only()

    def organizer_adds_low_budget_filter(self) -> None:
        self.dsl.enable_low_budget_tier()

    def organizer_reverts_pending_filters(self) -> None:
        self.dsl.revert_pending_filters()

    def organizer_closes_filter_panel(self) -> None:
        self.dsl.close_filter_panel_preserving_pending()

    def organizer_reopens_filter_panel(self) -> None:
        self.dsl.reopen_filter_panel_with_pending_filters()

    def organizer_includes_izakaya_bar(self) -> None:
        self.dsl.enable_include_izakaya_bar()

    def organizer_enables_a_filter_with_unknown_candidate_information(self) -> None:
        self.dsl.enable_filter_with_unknown_candidate_information()

    def organizer_selects_a_filter_preserved_by_fallback(self) -> None:
        self.dsl.enable_filters_that_require_izakaya_fallback()

    def organizer_selects_an_explicit_genre_with_no_matches(self) -> None:
        self.dsl.enable_explicit_genre_with_no_matches()

    def organizer_applies_changed_filters(self) -> None:
        self.dsl.apply_filters()

    def organizer_searches_again(self) -> None:
        self.dsl.search_again()

    def organizer_searches_again_to_reproduce_the_original_sample(self) -> None:
        self.dsl.search_again_reproducing_original_seed()

    def organizer_repeats_search_again_with_the_same_filters(self) -> None:
        self.dsl.repeat_search_again_through_shown_pool_cycle()

    def visitor_is_guided_to_sign_in_without_candidate_surface(self) -> None:
        self.dsl.assert_visitor_guided_to_sign_in_without_candidate_surface()

    def default_filters_and_nearest_candidates_are_shown(self) -> None:
        self.dsl.assert_initial_proposal_screen()

    def initial_display_requests_no_filter_input(self) -> None:
        self.dsl.assert_filter_panel_is_closed_until_requested()

    def initial_candidates_have_no_duplicate_shop(self) -> None:
        self.dsl.assert_no_duplicate_shops()

    def screen_has_no_private_disclosures(self) -> None:
        self.dsl.assert_screen_has_no_private_disclosures()

    def source_display_and_detail_link_are_shown(self) -> None:
        self.dsl.assert_provider_credit()

    def current_candidates_are_in_cards_and_map(self) -> None:
        self.dsl.assert_cards_and_map_show_current_proposal()

    def selecting_a_card_highlights_its_marker(self) -> None:
        self.dsl.select_first_card_and_verify_marker_highlighted()

    def selecting_a_marker_highlights_its_card(self) -> None:
        self.dsl.select_first_marker_and_verify_card_highlighted()

    def map_shows_displayed_candidates_and_attribution(self) -> None:
        self.dsl.assert_map_attribution_and_fit()

    def cards_show_required_shop_fields(self) -> None:
        self.dsl.assert_required_card_fields_match_current_proposal()

    def dinner_budget_reference_is_disclosed_once_on_screen(self) -> None:
        self.dsl.assert_dinner_budget_reference_is_shown()

    def map_has_no_forbidden_surfaces(self) -> None:
        self.dsl.assert_map_has_no_forbidden_surfaces()

    def changed_filters_are_sent_in_a_new_proposal_request(self) -> None:
        self.dsl.assert_changed_filters_were_sent()

    def new_filtered_proposal_replaces_the_display(self) -> None:
        self.dsl.assert_display_matches_current_proposal()

    def new_filtered_proposal_only_has_matching_or_unknown_candidates(self) -> None:
        self.dsl.assert_current_candidates_match_active_filters()

    def new_filtered_proposal_uses_the_display_ordering(self) -> None:
        self.dsl.assert_current_display_ordering()

    def no_location_range_or_manual_order_control_exists(self) -> None:
        self.dsl.assert_no_location_range_or_manual_order_control()

    def no_matching_candidates_are_shown_distinct_from_a_problem(self) -> None:
        self.dsl.assert_no_results_shown()
        self.dsl.assert_no_results_from_captured_api()

    def organizer_can_change_filters(self) -> None:
        self.dsl.assert_filter_open_is_available()

    def organizer_is_safely_guided_to_try_later(self) -> None:
        self.dsl.assert_safe_unavailable_guidance("PROVIDER_UNAVAILABLE")

    def organizer_is_safely_guided_to_try_later_by_api(self) -> None:
        self.dsl.assert_captured_problem_matches_schema("PROVIDER_UNAVAILABLE")

    def organizer_is_guided_to_wait_and_retry(self) -> None:
        self.dsl.assert_safe_unavailable_guidance("PROPOSAL_RATE_LIMITED")

    def organizer_is_guided_to_wait_and_retry_by_api(self) -> None:
        self.dsl.assert_captured_problem_matches_schema("PROPOSAL_RATE_LIMITED")

    def initial_request_uses_default_izakaya_bar_exclusion(self) -> None:
        self.dsl.assert_default_izakaya_bar_exclusion_was_requested()

    def izakaya_bar_filter_is_available(self) -> None:
        self.dsl.assert_izakaya_bar_filter_is_available()

    def including_izakaya_bar_adds_previously_excluded_candidates(self) -> None:
        self.dsl.assert_izakaya_bar_inclusion_adds_candidates()

    def fallback_candidates_and_uncertainty_notice_are_shown(self) -> None:
        self.dsl.assert_izakaya_bar_fallback_is_shown()

    def no_results_guidance_is_not_shown(self) -> None:
        self.dsl.assert_no_results_indicator_absent()

    def fallback_preserves_the_explicit_filter(self) -> None:
        self.dsl.assert_current_candidates_match_active_filters()

    def explicit_genre_filter_is_not_relaxed_by_fallback(self) -> None:
        self.dsl.assert_explicit_genre_filter_was_not_relaxed()

    def search_again_reuses_the_same_filters_and_replaces_the_display(self) -> None:
        self.dsl.assert_search_again_reused_filters_and_replaced_display()

    def new_seed_changes_the_candidate_sample(self) -> None:
        self.dsl.assert_new_seed_changed_sample()

    def original_seed_reproduces_the_original_candidate_sample(self) -> None:
        self.dsl.assert_original_seed_reproduced_sample()

    def payment_caution_is_shown_for_shops_without_card_payment(self) -> None:
        self.dsl.assert_payment_caution_shown_for_unavailable_card_payment()

    def payment_caution_is_not_shown_for_other_shops(self) -> None:
        self.dsl.assert_payment_caution_absent_when_card_payment_is_available_or_unknown()

    def confirmed_non_matching_candidates_are_excluded(self) -> None:
        self.dsl.assert_current_candidates_match_active_filters()

    def unknown_candidates_remain_with_an_unknown_state(self) -> None:
        self.dsl.assert_unknown_candidates_are_shown()

    def unknown_candidates_follow_confirmed_matches(self) -> None:
        self.dsl.assert_current_display_ordering()

    def candidates_greatly_outnumber_the_display_count(self) -> None:
        self.dsl.assert_eligible_population_greatly_exceeds_display_cap()

    def not_yet_shown_candidates_are_shown_first(self) -> None:
        self.dsl.assert_not_yet_shown_candidates_are_prioritized()

    def previously_shown_candidates_are_postponed_not_excluded(self) -> None:
        self.dsl.assert_previously_shown_candidates_are_postponed_not_excluded()

    def previously_shown_candidates_can_reappear_after_a_full_cycle(self) -> None:
        self.dsl.assert_previously_shown_candidates_can_reappear_after_a_full_cycle()

    def shown_memory_survives_a_reload_within_the_tab(self) -> None:
        self.dsl.assert_shown_memory_survives_a_reload()

    def shown_memory_fades_after_its_retention_period(self) -> None:
        self.dsl.assert_shown_memory_fades_after_its_retention_period()

    def shown_memory_is_not_shared_across_accounts_or_devices(self) -> None:
        self.dsl.assert_shown_memory_is_not_shared_with_another_device()
