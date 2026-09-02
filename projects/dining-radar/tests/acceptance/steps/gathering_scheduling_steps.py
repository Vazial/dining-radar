"""Thin Gherkin-to-DSL mappings for TDR-GTH-01 through TDR-GTH-25."""

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
        self.dsl.create_prepared_gathering()

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

    def organizer_submits_the_add_candidate_date_form(self, candidate_date_iso: str) -> object:
        return self.dsl.submit_add_candidate_date_form(candidate_date_iso)

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

    def new_candidate_date_is_added_via_inline_form(
        self,
        response: object,
        before_dates: list[dict[str, object]],
        expected_phase: str,
    ) -> None:
        self.dsl.assert_candidate_date_added_via_inline_form(
            response,
            before_dates,
            expected_phase,  # type: ignore[arg-type]
        )

    def duplicate_candidate_date_is_rejected(
        self,
        response: object,
        candidate_date_iso: str,
        before_dates: list[dict[str, object]],
    ) -> None:
        self.dsl.assert_duplicate_candidate_date_rejected_by_inline_form(
            response,
            candidate_date_iso,
            before_dates,  # type: ignore[arg-type]
        )

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
        self.dsl.assert_open_shop_preview_shows_expected_count_and_order(count)

    def no_candidate_date_is_confirmed(self) -> None:
        self.dsl.assert_no_candidate_date_confirmed()

    def schedule_question_shows_open_shop_count(self, candidate_date_id: str, count: int) -> None:
        self.dsl.assert_schedule_question_open_shop_count(candidate_date_id, count)

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

    def schedule_question_tally_is_absent(self, candidate_date_id: str) -> None:
        self.dsl.assert_schedule_question_tally_absent(candidate_date_id)

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

    def prior_responses_are_retained(self, before: dict[str, dict[str, object]]) -> None:
        self.dsl.assert_answer_state_unchanged(before)

    def screen_has_no_forbidden_controls_or_disclosures(self) -> None:
        self.dsl.assert_gathering_screen_has_no_forbidden_surfaces()

    def participant_token_is_not_persisted(self, link: dict[str, str]) -> None:
        self.dsl.assert_participant_token_not_persisted(link)

    def revoke_control_is_disabled_at(self, index: int) -> None:
        self.dsl.assert_revoke_control_disabled_at(index)

    def revoke_is_rejected_because_already_answered(self, response: object) -> None:
        self.dsl.assert_revoke_rejected_because_already_answered(response)  # type: ignore[arg-type]

    def recopied_link_matches_original(
        self, recopied_url: str, original_link: dict[str, str]
    ) -> None:
        self.dsl.assert_recopied_url_matches_original(recopied_url, original_link["url"])
