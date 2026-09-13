"""Thin Gherkin-to-DSL mappings for TDR-GTH-01 through TDR-GTH-55."""

from __future__ import annotations

from tests.acceptance.dsl.gathering_scheduling_browser import GatheringSchedulingBrowserDsl


class GatheringSchedulingSteps:
    def __init__(self, dsl: GatheringSchedulingBrowserDsl) -> None:
        self.dsl = dsl

    # Setup / Given -----------------------------------------------------

    def reset_state(self) -> None:
        self.dsl.reset_authentication_state()
        self.dsl.reset_gathering_scheduling_state()
        self.dsl.reset_candidate_state()

    def organizer_is_signed_in(self, account_ref: str, identifier: str, password: str) -> None:
        self.dsl.enable_organizer(account_ref, identifier, password)
        self.dsl.sign_in(identifier, password)

    def organizer_prepares_a_gathering(self, title: str, candidate_date_isos: list[str]) -> None:
        self.dsl.prepare_new_gathering(title, candidate_date_isos)

    def organizer_creates_the_gathering(self) -> None:
        self.dsl.create_prepared_gathering_via_browser()

    def organizer_has_a_scheduling_gathering(
        self, title: str, candidate_date_isos: list[str]
    ) -> None:
        self.dsl.given_scheduling_gathering(title, candidate_date_isos)

    def gathering_open_shop_population_is_available(self) -> None:
        self.dsl.set_gathering_open_shop_population()

    def organizer_opens_the_dashboard(self) -> None:
        self.dsl.open_organizer_dashboard()

    def organizer_opens_the_add_candidate_date_form(self) -> None:
        self.dsl.open_add_candidate_date_form()

    def organizer_submits_the_add_candidate_date_form(
        self, candidate_date_isos: list[str]
    ) -> object:
        return self.dsl.submit_add_candidate_date_form(candidate_date_isos)

    def organizer_fills_the_gathering_create_candidate_dates(self, isos: list[str]) -> None:
        self.dsl.select_gathering_create_candidate_date_days(isos)

    def candidate_dates_snapshot(self) -> list[dict[str, object]]:
        return self.dsl.candidate_dates_snapshot()

    def organizer_has_multiple_scheduling_gatherings(
        self, specs: list[tuple[str, list[str]]]
    ) -> list[dict]:
        return self.dsl.given_multiple_scheduling_gatherings(specs)

    def gathering_candidate_date_is_confirmed_via_api(
        self, gathering_id: str, candidate_date_id: str
    ) -> dict:
        return self.dsl.confirm_candidate_date_via_api(gathering_id, candidate_date_id)

    def organizer_opens_the_gathering_list(self) -> None:
        self.dsl.open_organizer_gathering_list()

    def organizer_opens_gathering_from_list(self, gathering_id: str) -> None:
        self.dsl.open_gathering_from_list(gathering_id)

    def organizer_opens_the_gathering_create_screen(self) -> None:
        self.dsl.open_gathering_create_from_header()

    def organizer_activates_create_open_from_the_empty_state(self) -> None:
        self.dsl.activate_create_open_from_empty_state()

    def organizer_fills_the_gathering_name(self, title: str) -> None:
        self.dsl.fill_gathering_create_name(title)

    def organizer_attempts_to_create_gathering_via_api_with_no_candidate_dates(
        self, title: str
    ) -> object:
        return self.dsl.attempt_create_gathering_via_api_with_no_candidate_dates(title)

    def lunch_candidate_screen_is_available(self) -> None:
        self.dsl.set_lunch_candidate_screen_available()

    def organizer_opens_the_lunch_candidate_screen(self) -> None:
        self.dsl.open_lunch_candidate_screen()

    def organizer_opens_the_gathering_entry(self) -> None:
        self.dsl.open_gathering_entry_from_candidate_screen()

    def organizer_issues_a_participant_link(self) -> dict[str, str]:
        return self.dsl.issue_participant_link_from_dashboard()

    def organizer_issues_participant_links(self, count: int) -> list[dict[str, str]]:
        return self.dsl.issue_n_participant_links_from_dashboard(count)

    def a_participant_link_is_issued(self) -> dict[str, str]:
        return self.dsl.issue_participant_link_via_api()

    def a_participant_has_already_answered_one_candidate_date(
        self, status: str = "GOING"
    ) -> tuple[dict[str, str], str]:
        return self.dsl.given_participant_link_with_one_answer(status)

    def organizer_tentatively_selects_the_candidate_date(self, candidate_date_id: str) -> None:
        self.dsl.tentatively_select_candidate_date(candidate_date_id)

    def organizer_confirms_the_tentatively_selected_date(self) -> None:
        self.dsl.confirm_tentatively_selected_date()

    def organizer_attempts_to_confirm_another_candidate_date_via_the_api(
        self, candidate_date_id: str
    ) -> object:
        return self.dsl.attempt_confirm_candidate_date_via_api(candidate_date_id)

    def organizer_recopies_the_link_at(self, index: int) -> str:
        return self.dsl.recopy_participant_link_at(index)

    def organizer_revokes_the_link_at(self, index: int) -> None:
        self.dsl.revoke_participant_link_at(index)

    def organizer_attempts_to_revoke_the_link_at_via_the_api(self, index: int) -> object:
        return self.dsl.attempt_revoke_participant_link_via_api(index)

    def participant_opens_the_link(self, link: dict[str, str]) -> None:
        self.dsl.open_participant_link(link)

    def participant_answers_the_candidate_date(self, candidate_date_id: str, status: str) -> None:
        self.dsl.answer_schedule_question(candidate_date_id, status)

    def participant_answers_the_first_candidate_date(self, status: str) -> str:
        return self.dsl.answer_first_schedule_question(status)

    def participant_attaches_a_display_name(self, name: str) -> None:
        self.dsl.attach_display_name(name)

    def link_is_seeded_as_expired(self, link: dict[str, str]) -> None:
        self.dsl.seed_expired_participant_link(link)

    def link_is_seeded_as_rate_limited(self, link: dict[str, str]) -> None:
        self.dsl.seed_rate_limited_participant_link(link)

    def link_is_seeded_to_fail_unexpectedly(self, link: dict[str, str]) -> None:
        self.dsl.seed_participant_link_server_error(link)

    def participant_attempts_to_answer_expecting_rate_limit(
        self, candidate_date_id: str, status: str
    ) -> None:
        self.dsl.attempt_answer_schedule_question_expecting_rate_limit(candidate_date_id, status)

    def someone_guesses_a_token_and_requests_the_participant_view(self) -> object:
        return self.dsl.attempt_get_participant_view_with_guessed_token()

    def prior_answers_snapshot(self, candidate_date_ids: list[str]) -> dict[str, dict[str, object]]:
        return self.dsl.capture_current_answer_state(candidate_date_ids)

    def unanswered_summary_snapshot(self) -> dict[str, int]:
        return self.dsl.capture_unanswered_summary()

    # Then ----------------------------------------------------------------

    def gathering_is_created_in_scheduling_phase(self) -> None:
        self.dsl.assert_gathering_created_in_scheduling_phase()

    def prepared_candidate_dates_are_all_registered(self) -> None:
        self.dsl.assert_prepared_candidate_dates_all_registered()

    def gathering_has_no_confirmed_date(self) -> None:
        self.dsl.assert_no_candidate_date_is_confirmed_on_gathering()

    def new_candidate_dates_are_added_via_inline_form(
        self,
        response: object,
        before_dates: list[dict[str, object]],
        expected_phase: str,
        expected_new_count: int = 1,
    ) -> None:
        self.dsl.assert_candidate_dates_added_via_inline_form(
            response,  # type: ignore[arg-type]
            before_dates,
            expected_phase,
            expected_new_count,
        )

    def duplicate_candidate_date_is_rejected(
        self,
        response: object,
        candidate_date_isos: list[str],
        before_dates: list[dict[str, object]],
    ) -> None:
        self.dsl.assert_duplicate_candidate_date_rejected_by_inline_form(
            response,  # type: ignore[arg-type]
            candidate_date_isos,
            before_dates,
        )

    def organizer_attempts_to_create_gathering_via_api_with_a_past_candidate_date(
        self, title: str, past_or_today_iso: str
    ) -> object:
        return self.dsl.attempt_create_gathering_via_api_with_a_past_candidate_date(
            title, past_or_today_iso
        )

    def create_is_rejected_because_date_not_in_future(self, response: object) -> None:
        self.dsl.assert_create_rejected_because_date_not_in_future(response)  # type: ignore[arg-type]

    def gathering_list_matches(self, expected: list[dict[str, object]]) -> None:
        self.dsl.assert_gathering_list_matches(expected)

    def dashboard_is_shown_for(self, gathering_id: str, expected_phase: str) -> None:
        self.dsl.assert_dashboard_is_shown_for(gathering_id, expected_phase)

    def gathering_list_is_empty(self) -> None:
        self.dsl.assert_gathering_list_is_empty()

    def gathering_create_screen_is_shown(self) -> None:
        self.dsl.assert_gathering_create_screen_is_shown()

    def gathering_create_submit_is_disabled(self) -> None:
        self.dsl.assert_gathering_create_submit_is_disabled()

    def create_is_rejected_for_missing_candidate_dates(self, response: object) -> None:
        self.dsl.assert_create_rejected_because_no_candidate_dates(response)  # type: ignore[arg-type]

    def no_gathering_exists_with_title(self, title: str) -> None:
        self.dsl.assert_no_gathering_exists_with_title(title)

    def in_progress_gathering_count_badge_shows(self, expected_count: int) -> None:
        self.dsl.assert_in_progress_gathering_count_badge(expected_count)

    def gathering_list_screen_is_shown(self) -> None:
        self.dsl.assert_gathering_list_screen_is_shown()

    def issued_links_are_distinct(self, links: list[dict[str, str]]) -> None:
        self.dsl.assert_issued_links_are_distinct(links)

    def participant_view_for_other_link_is_still_unanswered(self, candidate_date_id: str) -> None:
        self.dsl.assert_schedule_question_your_response(candidate_date_id, "UNANSWERED")

    def participant_is_recorded_as_nameless(self) -> None:
        self.dsl.assert_participant_is_nameless()

    def participant_is_recorded_as_named(self) -> None:
        self.dsl.assert_participant_is_named()

    def dashboard_shows_responded_summary(self, responded: int, anonymous: int) -> None:
        self.dsl.assert_responded_summary(responded=responded, anonymous=anonymous)

    def participant_link_list_matches(self, expected: list[dict[str, object]]) -> None:
        self.dsl.assert_participant_link_list_matches(expected)

    def schedule_question_shows_response(
        self, candidate_date_id: str, expected_status: str
    ) -> None:
        self.dsl.assert_schedule_question_your_response(candidate_date_id, expected_status)

    def gathering_phase_is(self, phase: str) -> None:
        self.dsl.assert_gathering_phase(phase)

    def participant_header_shows_gathering_phase(self, phase: str) -> None:
        self.dsl.assert_participant_header_phase(phase)

    def candidate_dates_are_ordered_by_going_count_descending(self) -> None:
        self.dsl.assert_candidate_date_list_is_ordered_by_going_count_descending()

    def candidate_date_order_snapshot(self) -> list[str]:
        return self.dsl.capture_candidate_date_order()

    def candidate_date_order_matches_start_at_order(self, candidate_date_isos: list[str]) -> None:
        self.dsl.assert_candidate_date_order_matches_start_at_order(candidate_date_isos)

    def candidate_date_order_is_unchanged(self, before: list[str]) -> None:
        self.dsl.assert_candidate_date_order_unchanged(before)

    def first_reachable_schedule_question_matches_start_at_order(
        self, candidate_date_isos: list[str]
    ) -> None:
        self.dsl.assert_first_reachable_schedule_question_matches_start_at_order(
            candidate_date_isos
        )

    def first_reachable_schedule_question_candidate_date(self) -> str:
        return self.dsl.first_reachable_schedule_question_candidate_date_id()

    def first_reachable_schedule_question_is_unchanged(self, before: str) -> None:
        self.dsl.assert_first_reachable_schedule_question_unchanged(before)

    def unanswered_summary_is(
        self, *, total_issued: int, revoked: int, active_issued: int, unanswered: int
    ) -> None:
        self.dsl.assert_unanswered_summary(
            total_issued=total_issued,
            revoked=revoked,
            active_issued=active_issued,
            unanswered=unanswered,
        )

    def unanswered_summary_unchanged(self, before: dict[str, int]) -> None:
        self.dsl.assert_unanswered_summary_equals(before)

    def unanswered_summary_reflects_one_revocation(self, before: dict[str, int]) -> None:
        self.dsl.assert_unanswered_summary_reflects_one_revocation(before)

    def open_shop_preview_shows_count(self, count: int) -> None:
        self.dsl.assert_open_shop_preview_shows_expected_count(count)

    def open_shop_preview_shows_no_shop_details(self) -> None:
        self.dsl.assert_open_shop_preview_shows_no_shop_details()

    def no_candidate_date_is_confirmed(self) -> None:
        self.dsl.assert_no_candidate_date_confirmed()

    def schedule_question_has_no_open_shop_count(self, candidate_date_id: str) -> None:
        self.dsl.assert_schedule_question_has_no_open_shop_count(candidate_date_id)

    def schedule_question_shows_no_shop_details(self, candidate_date_id: str) -> None:
        self.dsl.assert_schedule_question_no_shop_details(candidate_date_id)

    def other_candidate_date_confirm_is_rejected(self, response: object) -> None:
        self.dsl.assert_confirm_rejected_because_not_in_scheduling_phase(response)  # type: ignore[arg-type]

    def candidate_date_tally_is(
        self, candidate_date_id: str, *, going: int, maybe: int, not_going: int
    ) -> None:
        self.dsl.assert_candidate_date_tally(
            candidate_date_id, going=going, maybe=maybe, not_going=not_going
        )

    def schedule_question_tally_is(
        self, candidate_date_id: str, *, going: int, maybe: int, not_going: int
    ) -> None:
        self.dsl.assert_schedule_question_tally(
            candidate_date_id, going=going, maybe=maybe, not_going=not_going
        )

    def access_is_denied_without_disclosure(self, response: object) -> None:
        self.dsl.assert_access_denied_without_disclosure(response)  # type: ignore[arg-type]

    def participant_sees_link_error(self, code: str) -> None:
        self.dsl.assert_participant_link_error(code)

    def participant_view_is_valid(self) -> None:
        self.dsl.assert_valid_participant_view_is_shown()

    # answerLater / peekResults (adr/0050 decision 1) ------------------------

    def answer_later_and_peek_results_are_present(self) -> None:
        self.dsl.assert_answer_later_and_peek_results_present()

    def answer_later_and_peek_results_are_absent(self) -> None:
        self.dsl.assert_answer_later_and_peek_results_absent()

    def participant_activates_answer_later_and_state_is_unchanged(
        self, candidate_date_id: str, expected_response: str
    ) -> None:
        self.dsl.activate_answer_later_and_verify_it_changes_no_state(
            candidate_date_id, expected_response
        )

    def participant_activates_peek_results_and_tallies_are_visible(
        self, candidate_date_id: str
    ) -> None:
        self.dsl.activate_peek_results_and_verify_tallies_are_visible(candidate_date_id)

    def answer_later_confirmation_reproduces_schedule_answer(
        self, candidate_date_id: str, expected_response: str
    ) -> None:
        self.dsl.assert_answer_later_confirmation_reproduces_schedule_answer(
            candidate_date_id, expected_response
        )

    def prior_responses_are_retained(self, before: dict[str, dict[str, object]]) -> None:
        self.dsl.assert_answer_state_unchanged(before)

    def screen_has_no_forbidden_controls_or_disclosures(self) -> None:
        self.dsl.assert_gathering_screen_has_no_forbidden_surfaces()

    def participant_sees_a_load_failure_notice(self) -> None:
        self.dsl.assert_participant_load_failure_notice_is_shown()

    def load_failure_hides_the_schedule_and_shop_questions(self) -> None:
        self.dsl.assert_participant_load_failure_hides_questions()

    def load_failure_has_no_retry_control(self) -> None:
        self.dsl.assert_participant_load_failure_has_no_retry_control()

    def load_failure_is_exclusive_of_other_outcomes(self) -> None:
        self.dsl.assert_participant_load_failure_is_exclusive_of_other_outcomes()

    def load_failure_discloses_no_technical_detail(self) -> None:
        self.dsl.assert_participant_load_failure_discloses_no_technical_detail()

    def participant_token_is_not_persisted(self, link: dict[str, str]) -> None:
        self.dsl.assert_participant_token_not_persisted(link)

    def revoke_control_is_absent_at(self, index: int) -> None:
        self.dsl.assert_revoke_control_absent_at(index)

    def revoke_is_rejected_because_already_answered(self, response: object) -> None:
        self.dsl.assert_revoke_rejected_because_already_answered(response)  # type: ignore[arg-type]

    def recopied_link_matches_original(
        self, recopied_url: str, original_link: dict[str, str]
    ) -> None:
        self.dsl.assert_recopied_url_matches_original(recopied_url, original_link["url"])

    # Given / When -- shortlist selection, D7 replace, finalize (TDR-GTH-26/27/
    # 31/32/33/35/36) -----------------------------------------------------

    def organizer_has_a_selecting_shop_gathering(
        self, title: str, candidate_date_isos: list[str], confirm_index: int = 0
    ) -> str:
        return self.dsl.create_selecting_shop_gathering(title, candidate_date_isos, confirm_index)

    def gathering_state_is_refreshed(self) -> dict:
        return self.dsl.refresh_gathering_from_api()

    def open_shop_ids_for_the_confirmed_date(self) -> list[str]:
        return self.dsl.fetch_confirmed_date_open_shop_ids()

    def organizer_shortlists_shops_via_api(self, shop_ids: list[str]) -> dict:
        return self.dsl.set_shortlisted_shops_via_api(shop_ids)

    def shop_id_closed_only_on(self, closed_weekday: int, open_weekday: int) -> str:
        return self.dsl.fetch_shop_id_closed_only_on(closed_weekday, open_weekday)

    def confirmed_date_open_shop_ids_with_a_spare(self) -> tuple[list[str], str]:
        return self.dsl.fetch_confirmed_date_open_shop_ids_with_a_spare()

    def organizer_opens_shop_selection_entry(self) -> None:
        self.dsl.open_shop_selection_entry()

    def organizer_selects_first_n_candidates_into_gathering(self, n: int) -> list[str]:
        return self.dsl.select_first_n_candidates_into_gathering(n)

    def organizer_attempts_to_shortlist_shops_via_api(self, shop_ids: list[str]) -> object:
        return self.dsl.attempt_set_shortlisted_shops_via_api(shop_ids)

    def organizer_replaces_a_shortlisted_shop(self, old_shop_id: str, new_shop_id: str) -> dict:
        return self.dsl.replace_shortlisted_shop(old_shop_id, new_shop_id)

    def organizer_selects_a_shop_for_finalize(self, shop_id: str) -> None:
        self.dsl.select_shop_for_finalize(shop_id)

    def organizer_finalizes_via_dashboard(self) -> None:
        self.dsl.finalize_via_dashboard()

    def organizer_opens_finalize_confirmation(self) -> None:
        self.dsl.open_finalize_confirmation()

    def finalize_confirm_dialog_shows_changes_summary(self) -> None:
        self.dsl.assert_finalize_confirm_dialog_shows_changes_summary()

    def organizer_confirms_finalize(self) -> None:
        self.dsl.confirm_finalize()

    def organizer_cancels_finalize_confirmation(self) -> None:
        self.dsl.cancel_finalize()

    def organizer_attempts_to_issue_a_participant_link_via_api(self) -> object:
        return self.dsl.attempt_issue_participant_link_via_api()

    def organizer_attempts_to_finalize_via_api(self, shop_id: str) -> object:
        return self.dsl.attempt_finalize_via_api(shop_id)

    # Then -- shortlist / vote / finalize / decision -----------------------

    def shortlisted_shops_match(self, expected_ids: list[str]) -> None:
        self.dsl.assert_shortlisted_shop_ids(expected_ids)

    def shortlisted_shop_tally_is(
        self, shop_id: str, *, want_to_go: int, ok_to_go: int, not_going: int, responded: int
    ) -> None:
        self.dsl.assert_shortlisted_shop_tally(
            shop_id,
            want_to_go=want_to_go,
            ok_to_go=ok_to_go,
            not_going=not_going,
            responded=responded,
        )

    def shortlisted_shop_list_is_ordered_by_combined_tier_descending(self) -> None:
        self.dsl.assert_shortlisted_shop_list_is_ordered_by_combined_tier_descending()

    def no_shortlisted_shop_is_the_current_leader(self) -> None:
        self.dsl.assert_no_shortlisted_shop_is_current_leader()

    def shortlisted_shop_current_leaders_are(self, expected_leader_ids: set[str]) -> None:
        self.dsl.assert_shortlisted_shop_current_leaders_are(expected_leader_ids)

    def shortlisted_shop_list_shows_map_and_shop_details(self) -> None:
        self.dsl.assert_shortlisted_shop_list_shows_map_and_shop_details()

    def rejected_as_invalid_shop_selection(self, response: object) -> None:
        self.dsl.assert_rejected_as_invalid_shop_selection(response)  # type: ignore[arg-type]

    def rejected_because_not_selecting_shop_phase(self, response: object) -> None:
        self.dsl.assert_rejected_because_not_selecting_shop_phase(response)  # type: ignore[arg-type]

    def rejected_because_shop_voting_not_started(self, response: object) -> None:
        self.dsl.assert_rejected_because_shop_voting_not_started(response)  # type: ignore[arg-type]

    def finalized_controls_are_absent(self) -> None:
        self.dsl.assert_finalized_controls_are_absent()

    def rejected_because_gathering_finalized(self, response: object) -> None:
        self.dsl.assert_rejected_because_gathering_finalized(response)  # type: ignore[arg-type]

    # Participant shop-vote / finalized decision (TDR-GTH-28/29/30/34/37/39/41,
    # three-tier vote model, near-first stable order, map/detail fields,
    # search-origin marker -- adr/0044/0045/0046) ---------------------------

    def participant_answers_shop_vote(self, shop_id: str, status: str) -> None:
        self.dsl.answer_shop_vote_question(shop_id, status)

    def participant_answers_shop_votes(self, votes: dict[str, str]) -> None:
        self.dsl.answer_shop_vote_questions(votes)

    def shop_vote_your_vote_is(self, shop_id: str, expected: str) -> None:
        self.dsl.assert_shop_vote_your_vote(shop_id, expected)

    def shop_vote_tally_is(
        self, shop_id: str, *, want_to_go: int, ok_to_go: int, not_going: int, responded: int
    ) -> None:
        self.dsl.assert_shop_vote_tally(
            shop_id,
            want_to_go=want_to_go,
            ok_to_go=ok_to_go,
            not_going=not_going,
            responded=responded,
        )

    def shop_vote_question_list_shows_map_and_shop_details(self, link: dict[str, str]) -> None:
        self.dsl.assert_shop_vote_question_list_shows_map_and_shop_details(link)

    def shop_vote_tally_total_active_participant_count_is(
        self, shop_id: str, expected: int
    ) -> None:
        self.dsl.assert_shop_vote_tally_total_active_participant_count(shop_id, expected)

    def shop_vote_map_shows_search_origin_marker(self) -> None:
        self.dsl.assert_shop_vote_map_shows_search_origin_marker()

    def shop_vote_question_order_snapshot(self) -> list[str]:
        return self.dsl.capture_shop_vote_question_order()

    def shop_vote_question_order_matches_participant_view(self, link: dict[str, str]) -> None:
        self.dsl.assert_shop_vote_question_order_matches_participant_view(link)

    def shop_vote_question_order_is_unchanged(self, before: list[str]) -> None:
        self.dsl.assert_shop_vote_question_order_unchanged(before)

    def participant_attempts_to_answer_via_api(
        self, link: dict[str, str], candidate_date_id: str, status: str
    ) -> object:
        return self.dsl.attempt_set_schedule_response_via_api(link, candidate_date_id, status)

    def participant_attempts_to_vote_via_api(
        self, link: dict[str, str], votes: dict[str, str]
    ) -> object:
        return self.dsl.attempt_set_shop_votes_via_api(link, votes)

    def participant_decision_is(
        self,
        *,
        confirmed_candidate_date: str,
        shop_id: str,
    ) -> None:
        self.dsl.assert_participant_decision(
            confirmed_candidate_date=confirmed_candidate_date,
            shop_id=shop_id,
        )

    def participant_decision_has_no_shop_breakdown(self) -> None:
        self.dsl.assert_participant_decision_has_no_shop_breakdown()

    def participant_decision_has_no_own_response_attribute(self) -> None:
        self.dsl.assert_participant_decision_has_no_own_response_attribute()

    def participant_decision_shows_shop_location_details(
        self, *, shop_id: str, walking_time_minutes: int, provider_page_url: str
    ) -> None:
        self.dsl.assert_participant_decision_shows_shop_location_details(
            shop_id=shop_id,
            walking_time_minutes=walking_time_minutes,
            provider_page_url=provider_page_url,
        )

    def participant_decision_map_shows_shop_and_origin_only(self) -> None:
        self.dsl.assert_participant_decision_map_shows_shop_and_origin_only()

    def participant_view_via_api(self, link: dict[str, str]) -> dict:
        return self.dsl.fetch_participant_view_via_api(link)

    def participant_question_surfaces_are_replaced(self) -> None:
        self.dsl.assert_participant_question_surfaces_are_replaced()

    def finalized_view_still_shows_shop_vote_tally(
        self, shop_id: str, *, want_to_go: int, ok_to_go: int, not_going: int, responded: int
    ) -> None:
        self.dsl.assert_finalized_view_still_shows_shop_vote_tally(
            shop_id,
            want_to_go=want_to_go,
            ok_to_go=ok_to_go,
            not_going=not_going,
            responded=responded,
        )

    def participant_name_controls_are_absent(self) -> None:
        self.dsl.assert_participant_name_controls_are_absent()

    # Delete gathering (TDR-GTH-48, adr/0050 decision 4) --------------------

    def organizer_deletes_the_gathering(self) -> None:
        self.dsl.delete_gathering_via_dashboard()

    def gathering_is_absent_from_the_list(self, gathering_id: str) -> None:
        self.dsl.assert_gathering_absent_from_list(gathering_id)

    # Toggle a shop into/out of a gathering from candidate-search's own
    # gatheringMode (TDR-GTH-44/45, adr/0049 decision 1) --------------------

    def gathering_mode_band_shows(self, *, shortlisted: int, max_shortlisted: int = 5) -> None:
        self.dsl.assert_gathering_mode_band_shows(
            shortlisted=shortlisted, max_shortlisted=max_shortlisted
        )

    def organizer_toggles_off_the_first_shortlisted_candidate(self) -> None:
        self.dsl.toggle_off_the_first_shortlisted_candidate_card()

    def organizer_searches_again_on_shop_selection_entry(self) -> None:
        self.dsl.search_again_on_shop_selection_entry()

    def unselected_candidate_toggle_is_disabled(self) -> None:
        self.dsl.assert_unselected_candidate_card_toggle_is_disabled()

    # organizerDashboard.responseTable (ADR-0056 decision 1, TDR-GTH-49) -----

    def participant_link_ids_in_order(self) -> list[str]:
        return self.dsl.read_participant_link_ids_in_order()

    def response_table_matches(self, expected: dict[str, dict[str, str]]) -> None:
        self.dsl.assert_response_table_matches(expected)

    # organizerDashboard.candidateDateList.removeCandidateDate (ADR-0056
    # decision 2, TDR-GTH-50/51) --------------------------------------------

    def organizer_removes_the_candidate_date(self, candidate_date_id: str) -> None:
        self.dsl.remove_candidate_date(candidate_date_id)

    def candidate_date_is_absent(self, candidate_date_id: str) -> None:
        self.dsl.assert_candidate_date_absent(candidate_date_id)

    def organizer_attempts_to_remove_candidate_date_via_api(self, candidate_date_id: str) -> object:
        return self.dsl.attempt_remove_candidate_date_via_api(candidate_date_id)

    def remove_candidate_date_control_is_absent(self, candidate_date_id: str) -> None:
        self.dsl.assert_remove_candidate_date_control_absent(candidate_date_id)

    def remove_candidate_date_is_rejected_because_not_in_scheduling_phase(
        self, response: object
    ) -> None:
        self.dsl.assert_remove_candidate_date_rejected_because_not_in_scheduling_phase(
            response  # type: ignore[arg-type]
        )

    # participantLinkList.issuanceClosed (ADR-0056 decision 11) -------------

    def participant_link_issuance_closed_badge_is_shown(self) -> None:
        self.dsl.assert_participant_link_issuance_closed_badge_is_shown()
