"""Thin Gherkin-to-DSL mappings for TDR-CS-00 through TDR-CS-11.

Signing in composes the DSL's own JS-capable ``sign_in`` (see
``dsl/candidate_search_browser.py`` module docstring for why this cannot
reuse the plain-HTTP ``AuthenticationSteps``): the candidate-search
Background line "幹事はサインインしている" is the same precondition as
TDR-AUTH-02, executed through the browser this scenario also observes.
"""

from __future__ import annotations

from tests.acceptance.dsl.candidate_search_browser import CandidateSearchBrowserDsl


class CandidateSearchSteps:
    def __init__(self, dsl: CandidateSearchBrowserDsl) -> None:
        self.dsl = dsl

    # Given -------------------------------------------------------------

    def reset_state(self) -> None:
        self.dsl.reset_authentication_state()
        self.dsl.reset_candidate_state()

    def visitor_has_no_active_organizer_session(self) -> None:
        self.dsl.assert_no_active_session()

    def organizer_is_signed_in(self, account_ref: str, identifier: str, password: str) -> None:
        self.dsl.enable_organizer(account_ref, identifier, password)
        self.dsl.sign_in(identifier, password)

    def lunch_candidates_can_be_proposed(self) -> None:
        self.dsl.set_candidate_state("NORMAL_WITH_REPEAT")

    def no_candidates_match_chosen_lens(self) -> None:
        self.dsl.set_candidate_state("NO_RESULTS")

    def candidate_information_is_unavailable_now(self) -> None:
        self.dsl.set_candidate_state("PROVIDER_UNAVAILABLE")

    def organizer_is_repeatedly_requesting_proposals(self) -> None:
        self.dsl.set_candidate_state("RATE_LIMITED")

    def organizer_has_one_lens_of_candidates(self) -> None:
        self.dsl.open_candidate_screen()

    def candidates_include_a_hard_to_confirm_lunch_genre(self) -> None:
        self.dsl.set_candidate_state("NORMAL_WITH_REPEAT")

    def excluding_the_genre_leaves_no_candidates_but_including_it_does(self) -> None:
        self.dsl.set_candidate_state("IZAKAYA_BAR_ONLY")

    # When ----------------------------------------------------------------

    def visitor_opens_candidate_proposal_screen(self) -> None:
        self.dsl.open_candidate_screen_unauthenticated()

    def organizer_opens_candidate_proposal_screen(self) -> None:
        self.dsl.open_candidate_screen()

    def organizer_opens_reproposal_popup(self) -> None:
        self.dsl.open_reproposal_popup()

    def organizer_selects_a_different_lens(self) -> str:
        return self.dsl.select_first_offered_lens()

    def organizer_requests_an_unsupported_lens_directly(self, kind: str) -> None:
        self.dsl.request_unsupported_lens_directly(kind)

    def organizer_selects_the_izakaya_bar_included_lens(self) -> None:
        self.dsl.select_izakaya_bar_included_lens()

    def organizer_selects_try_again(self) -> None:
        self.dsl.select_try_again()

    # Then ------------------------------------------------------------------

    def visitor_is_guided_to_sign_in_without_candidate_surface(self) -> None:
        self.dsl.assert_visitor_guided_to_sign_in_without_candidate_surface()

    def initial_lens_and_map_are_shown(self) -> None:
        self.dsl.assert_initial_proposal_screen()

    def initial_display_requests_no_secondary_input(self) -> None:
        self.dsl.assert_no_secondary_conditions_or_manual_sort()

    def initial_lens_has_a_rationale(self) -> None:
        self.dsl.assert_initial_concept_has_rationale()

    def initial_candidates_have_no_duplicate_shop(self) -> None:
        self.dsl.assert_no_duplicate_shops()

    def screen_has_no_private_disclosures(self) -> None:
        self.dsl.assert_screen_has_no_private_disclosures()

    def source_display_and_detail_link_are_shown(self) -> None:
        self.dsl.assert_provider_credit()

    def current_lens_shops_are_in_cards_and_map(self) -> None:
        self.dsl.assert_cards_and_map_show_current_concept()

    def cards_show_required_shop_fields(self) -> None:
        self.dsl.assert_required_card_fields_match_current_proposal()

    def map_has_no_forbidden_surfaces(self) -> None:
        self.dsl.assert_map_has_no_forbidden_surfaces()

    def map_shows_source_attribution(self) -> None:
        self.dsl.assert_map_attribution_and_fit()

    def selecting_a_card_highlights_its_marker(self) -> None:
        self.dsl.select_first_card_and_verify_marker_highlighted()

    def selecting_a_marker_highlights_its_card(self) -> None:
        self.dsl.select_first_marker_and_verify_card_highlighted()

    def reproposal_options_exclude_current_lens_and_are_bounded(self) -> None:
        self.dsl.assert_reproposal_options_bounded_and_exclude_current()

    def new_proposal_replaces_display_with_chosen_lens(self, chosen_kind: str) -> None:
        self.dsl.assert_display_replaced_by_reproposal(chosen_kind)

    def new_proposal_uses_same_lens_and_replaces_display(self) -> None:
        self.dsl.assert_new_proposal_uses_same_lens_and_replaces_display()

    def repeat_priority_orders_new_before_repeated(self) -> None:
        self.dsl.assert_repeat_priority_orders_new_before_repeated()

    def repeated_candidate_is_not_excluded(self) -> None:
        self.dsl.assert_repeated_candidate_not_excluded()

    def concept_choice_is_available_only_via_reproposal(self) -> None:
        self.dsl.assert_concept_choice_available_only_via_reproposal()

    def no_matching_candidates_are_shown(self) -> None:
        self.dsl.assert_no_results_shown()

    def no_matching_candidates_are_shown_by_api(self) -> None:
        self.dsl.assert_no_results_from_captured_api()

    def organizer_is_safely_guided_to_try_later(self) -> None:
        self.dsl.assert_safe_unavailable_guidance("PROVIDER_UNAVAILABLE")

    def organizer_is_safely_guided_to_try_later_by_api(self) -> None:
        self.dsl.assert_captured_problem_matches_schema("PROVIDER_UNAVAILABLE")

    def unsupported_lens_is_rejected(self) -> None:
        self.dsl.assert_direct_problem_matches_schema("PROPOSAL_REPROPOSAL_KIND_INVALID")

    def organizer_is_guided_to_wait_and_retry(self) -> None:
        self.dsl.assert_safe_unavailable_guidance("PROPOSAL_RATE_LIMITED")

    def organizer_is_guided_to_wait_and_retry_by_api(self) -> None:
        self.dsl.assert_captured_problem_matches_schema("PROPOSAL_RATE_LIMITED")

    def izakaya_bar_included_lens_is_offered_as_reproposal_option(self) -> None:
        self.dsl.assert_izakaya_bar_included_offered_as_reproposal_option()

    def initial_candidates_exclude_the_hard_to_confirm_lunch_genre(self) -> None:
        self.dsl.assert_initial_excludes_hard_to_confirm_lunch_genre()

    def chosen_lens_candidates_include_the_hard_to_confirm_lunch_genre(self) -> None:
        self.dsl.assert_chosen_lens_includes_hard_to_confirm_lunch_genre()

    def chosen_lens_rationale_does_not_assert_confirmed_lunch_service(self) -> None:
        self.dsl.assert_izakaya_bar_included_rationale_does_not_claim_confirmed_lunch()

    def candidates_are_shown_including_the_excluded_genre(self) -> None:
        self.dsl.assert_fallback_proposal_uses_izakaya_bar_included_lens()

    def no_results_guidance_is_not_shown(self) -> None:
        self.dsl.assert_no_results_indicator_absent()
