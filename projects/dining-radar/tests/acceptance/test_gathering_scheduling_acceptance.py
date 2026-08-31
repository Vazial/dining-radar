"""JS-capable browser/API L4 runner for TDR-GTH-01 through TDR-GTH-20.

gathering-scheduling-browser-interface.yaml's own profiles.localAcceptance
marks TDR-GTH-01 (no approved creation screen yet) and TDR-GTH-13 (token
guessing is API-level fuzzing, not a browser click-through) as
notVerifiedHere for the browser control surface; both are still exercised
here at the API/boundary level through the same authenticated Playwright
session (see gathering_scheduling_browser.py's module docstring).
"""

from __future__ import annotations

import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from tests.acceptance.dsl.gathering_scheduling_browser import (
    OPEN_SHOP_COUNT_BY_WEEKDAY,
    GatheringSchedulingBrowserDsl,
    days_from_now_iso,
    next_weekday_iso,
)
from tests.acceptance.steps.gathering_scheduling_steps import GatheringSchedulingSteps


class GatheringSchedulingAcceptanceTests(StaticLiveServerTestCase):
    """Each test mirrors one TDR-GTH scenario through Chromium (or, where the
    browser contract itself scopes a scenario to the API boundary, through
    the same authenticated session's direct API calls).
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
        self.context = self._browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dsl = GatheringSchedulingBrowserDsl(
            self, self.page, os.environ["TDR_ACCEPTANCE_BASE_URL"]
        )
        self.steps = GatheringSchedulingSteps(self.dsl)
        self.steps.reset_state()

    def _sign_in(self) -> None:
        self.steps.organizer_is_signed_in(
            "organizer-gth", "synthetic-organizer-gth", "synthetic-secret-gth"
        )

    # TDR-GTH-01 -- API/boundary-level acceptance (no creation screen yet) --

    def test_tdr_gth_01_organizer_creates_a_gathering_with_candidate_dates(self) -> None:
        self._sign_in()
        self.steps.organizer_prepares_a_gathering(
            "第7回 社内ランチ会", [days_from_now_iso(3), days_from_now_iso(10)]
        )
        self.steps.organizer_creates_the_gathering()
        self.steps.gathering_is_created_in_scheduling_phase()
        self.steps.prepared_candidate_dates_are_all_registered()
        self.steps.gathering_has_no_confirmed_date()

    def test_tdr_gth_02_organizer_adds_a_candidate_date_after_creation(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会2", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_activates_the_add_candidate_date_entry_point()
        self.steps.organizer_adds_a_candidate_date(days_from_now_iso(20))
        self.steps.new_candidate_date_is_added_without_phase_change(
            self.dsl.candidate_date_id_at(1)
        )

    def test_tdr_gth_03_organizer_issues_participant_links(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会3", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        links = self.steps.organizer_issues_participant_links(2)
        self.steps.issued_links_are_distinct(links)
        first_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.participant_opens_the_link(links[0])
        self.steps.participant_answers_the_candidate_date(first_date_id, "GOING")
        self.steps.participant_opens_the_link(links[1])
        self.steps.participant_view_for_other_link_is_still_unanswered(first_date_id)

    def test_tdr_gth_04_participant_answers_without_a_name(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会4", [days_from_now_iso(3)])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_first_candidate_date("GOING")
        self.steps.participant_is_recorded_as_nameless()
        self.steps.organizer_opens_the_dashboard()
        self.steps.dashboard_shows_responded_summary(1, 1)

    def test_tdr_gth_05_participant_attaches_a_name_later(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会5", [days_from_now_iso(3)])
        link, candidate_date_id = self.steps.a_participant_has_already_answered_one_candidate_date(
            "GOING"
        )
        self.steps.participant_attaches_a_display_name("ゆかり")
        self.steps.participant_is_recorded_as_named()
        self.steps.schedule_question_shows_response(candidate_date_id, "GOING")
        self.steps.organizer_opens_the_dashboard()
        self.steps.participant_link_list_matches([{"hasResponded": True, "named": True}])

    def test_tdr_gth_06_participant_can_always_change_the_answer(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会6", [days_from_now_iso(3), days_from_now_iso(10)]
        )
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "MAYBE")
        self.steps.schedule_question_shows_response(candidate_date_id, "MAYBE")
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_tentatively_selects_the_candidate_date(candidate_date_id)
        self.steps.organizer_confirms_the_tentatively_selected_date()
        self.steps.gathering_phase_is("SELECTING_SHOP")
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "NOT_GOING")
        self.steps.schedule_question_shows_response(candidate_date_id, "NOT_GOING")
        self.steps.participant_header_shows_gathering_phase("SELECTING_SHOP")

    def test_tdr_gth_07_organizer_sees_two_distinct_denominators(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会7", [days_from_now_iso(3), days_from_now_iso(10)]
        )
        candidate_date_a = self.dsl.candidate_date_id_at(0)
        candidate_date_b = self.dsl.candidate_date_id_at(1)
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_the_candidate_date(candidate_date_a, "GOING")
        self.steps.participant_answers_the_candidate_date(candidate_date_b, "MAYBE")
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.participant_answers_the_candidate_date(candidate_date_a, "MAYBE")
        self.steps.a_participant_link_is_issued()  # link three never answers
        self.steps.organizer_opens_the_dashboard()
        self.steps.unanswered_summary_is(total_issued=3, revoked=0, active_issued=3, unanswered=1)
        self.steps.candidate_date_tally_is(candidate_date_a, going=1, maybe=1, not_going=0)
        self.steps.candidate_date_tally_is(candidate_date_b, going=0, maybe=1, not_going=0)
        self.steps.candidate_dates_are_ordered_by_going_count_descending()

    def test_tdr_gth_08_organizer_previews_open_shops_for_a_tentative_date(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        monday = next_weekday_iso(0)
        other_day = days_from_now_iso(45)
        self.steps.organizer_has_a_scheduling_gathering("会8", [monday, other_day])
        self.steps.organizer_opens_the_dashboard()
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.organizer_tentatively_selects_the_candidate_date(candidate_date_id)
        self.steps.open_shop_preview_shows_count(OPEN_SHOP_COUNT_BY_WEEKDAY[0])
        self.steps.gathering_phase_is("SCHEDULING")
        self.steps.no_candidate_date_is_confirmed()

    def test_tdr_gth_09_participant_sees_only_the_open_shop_count(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        wednesday = next_weekday_iso(2)
        self.steps.organizer_has_a_scheduling_gathering("会9", [wednesday])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.schedule_question_shows_open_shop_count(
            candidate_date_id, OPEN_SHOP_COUNT_BY_WEEKDAY[2]
        )
        self.steps.schedule_question_shows_no_shop_details(candidate_date_id)

    def test_tdr_gth_10_organizer_confirms_a_candidate_date(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会10", [days_from_now_iso(3), days_from_now_iso(10)]
        )
        candidate_date_a = self.dsl.candidate_date_id_at(0)
        candidate_date_b = self.dsl.candidate_date_id_at(1)
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_a, "GOING")
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_tentatively_selects_the_candidate_date(candidate_date_a)
        self.steps.organizer_confirms_the_tentatively_selected_date()
        self.steps.gathering_phase_is("SELECTING_SHOP")
        response = self.steps.organizer_attempts_to_confirm_another_candidate_date_via_the_api(
            candidate_date_b
        )
        self.steps.other_candidate_date_confirm_is_rejected(response)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_a, "MAYBE")
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_tally_is(candidate_date_a, going=0, maybe=1, not_going=0)

    def test_tdr_gth_11_responses_continue_after_a_date_is_selected(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会11", [days_from_now_iso(3), days_from_now_iso(10)]
        )
        candidate_date_a = self.dsl.candidate_date_id_at(0)
        candidate_date_b = self.dsl.candidate_date_id_at(1)
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_tentatively_selects_the_candidate_date(candidate_date_a)
        self.steps.organizer_confirms_the_tentatively_selected_date()
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_a, "GOING")
        self.steps.participant_answers_the_candidate_date(candidate_date_b, "MAYBE")
        self.steps.participant_header_shows_gathering_phase("SELECTING_SHOP")
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_tally_is(candidate_date_a, going=1, maybe=0, not_going=0)
        self.steps.candidate_date_tally_is(candidate_date_b, going=0, maybe=1, not_going=0)
        self.steps.gathering_phase_is("SELECTING_SHOP")

    def test_tdr_gth_12_other_answers_are_revealed_only_after_answering(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会12", [days_from_now_iso(3)])
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        link_a = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_a)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        link_b = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_b)
        self.steps.schedule_question_tally_is_absent(candidate_date_id)
        self.steps.schedule_question_shows_response(candidate_date_id, "UNANSWERED")
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "MAYBE")
        self.steps.schedule_question_tally_is(candidate_date_id, going=1, maybe=1, not_going=0)

    def test_tdr_gth_13_guessing_a_token_is_denied_without_disclosure(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("秘密の会13", [days_from_now_iso(3)])
        self.steps.a_participant_link_is_issued()
        response = self.steps.someone_guesses_a_token_and_requests_the_participant_view()
        self.steps.access_is_denied_without_disclosure(response)

    def test_tdr_gth_14_expired_link_cannot_be_used(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会14", [days_from_now_iso(3)])
        link = self.steps.a_participant_link_is_issued()
        self.steps.link_is_seeded_as_expired(link)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_sees_link_error("LINK_EXPIRED")

    def test_tdr_gth_15_rate_limited_response_does_not_lose_prior_answers(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会15", [days_from_now_iso(3)])
        link, candidate_date_id = self.steps.a_participant_has_already_answered_one_candidate_date(
            "GOING"
        )
        before = self.steps.prior_answers_snapshot([candidate_date_id])
        self.steps.link_is_seeded_as_rate_limited(link)
        self.steps.participant_attempts_to_answer_expecting_rate_limit(candidate_date_id, "MAYBE")
        self.steps.prior_responses_are_retained(before)

    def test_tdr_gth_16_organizer_reviews_the_issued_link_list(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会16", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        links = self.steps.organizer_issues_participant_links(3)
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.participant_opens_the_link(links[0])
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        self.steps.participant_attaches_a_display_name("たけし")
        self.steps.organizer_opens_the_dashboard()
        self.steps.participant_link_list_matches(
            [
                {"hasResponded": True, "named": True},
                {"hasResponded": False, "named": False},
                {"hasResponded": False, "named": False},
            ]
        )

    def test_tdr_gth_17_organizer_recopies_a_link(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会17", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        before = self.steps.unanswered_summary_snapshot()
        recopied_url = self.steps.organizer_recopies_the_link_at(0)
        self.steps.recopied_link_matches_original(recopied_url, link)
        self.steps.unanswered_summary_unchanged(before)
        self.steps.participant_link_list_matches([{"hasResponded": False, "named": False}])

    def test_tdr_gth_18_revoking_an_unanswered_link_reduces_the_denominator(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会18", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_issues_a_participant_link()
        before = self.steps.unanswered_summary_snapshot()
        self.steps.organizer_revokes_the_link_at(0)
        self.steps.unanswered_summary_reflects_one_revocation(before)
        self.steps.participant_link_list_matches(
            [{"hasResponded": False, "named": False, "revoked": True}]
        )

    def test_tdr_gth_19_revoked_link_cannot_be_used(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会19", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        self.steps.organizer_revokes_the_link_at(0)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_sees_link_error("LINK_REVOKED")

    def test_tdr_gth_20_answered_link_cannot_be_revoked(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会20", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        self.steps.organizer_opens_the_dashboard()
        self.steps.revoke_control_is_disabled_at(0)
        before = self.steps.unanswered_summary_snapshot()
        response = self.steps.organizer_attempts_to_revoke_the_link_at_via_the_api(0)
        self.steps.revoke_is_rejected_because_already_answered(response)
        self.steps.unanswered_summary_unchanged(before)
        self.steps.participant_link_list_matches(
            [{"hasResponded": True, "named": False, "revoked": False}]
        )
        self.steps.participant_opens_the_link(link)
        self.steps.participant_view_is_valid()
