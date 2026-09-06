"""JS-capable browser/API L4 runner for TDR-GTH-01 through TDR-GTH-43.

gathering-scheduling-browser-interface.yaml's own profiles.localAcceptance
marks only TDR-GTH-13 (token guessing is API-level fuzzing, not a browser
click-through) as notVerifiedHere for the browser control surface; it is
exercised here at the API/boundary level through the same authenticated
Playwright session (see gathering_scheduling_browser.py's module docstring).
TDR-GTH-01 drives organizerGatheringCreate end-to-end through the browser
(reviewer audit Major#2, resolving the prior direct-API gap this docstring
used to describe). TDR-GTH-26 through TDR-GTH-36 (adr/0040-0042) add the
5-shop shortlist, D7 replace, three-tier voting, finalize, and finalized-view
scenarios; every Given-state builder that is not itself the scenario under
test still goes through gathering-scheduling-api.yaml's public boundary
(adr/0037 decision 1), not a new test-support seam. TDR-GTH-37 through
TDR-GTH-41 (adr/0044/0045/0046, 2026-09-04/05) revise the shop-vote model to
three tiers (WANT_TO_GO/OK_TO_GO/NOT_GOING replacing the retired boolean
approvedShopIds), stabilize the participant's shop order against votes, and
add map/shop-detail observations to both the organizer's shortlist-selection
screen and the participant's vote screen (the latter also gaining a
search-origin marker). TDR-GTH-28/29/30/31/32/33/34 below are rewritten to
match -- their .feature scenario bodies are unchanged (per the contract's own
header comment), but every browser/API interaction they drive changed shape.
TDR-GTH-42 (adr/0047, 2026-09-06) adds a third, mutually exclusive
participant-load outcome (browser-interface.yaml v0.8.0's
unexpectedLoadFailureOutcome) alongside validLinkOutcome and
invalidLinkOutcome, built with test-support-api.yaml 1.5.4's new
seedParticipantLinkServerError seam. TDR-GTH-43 (adr/0048, 2026-09-06) adds a
deterministic-ordering regression check for candidate dates tied on
goingCount, covering both organizerDashboard.candidateDateList and
participantAnswer.scheduleQuestion (the latter's orderingInvariant is new to
browser-interface.yaml v0.9.0 and has no separate .feature scenario of its
own -- adr/0048 decision 3 declines a parallel scenario, so it is checked
here as the same underlying defect this scenario already guards).
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
        """Rewritten (browser-interface.yaml v0.4: "Supports TDR-GTH-01 (now
        browser-verifiable)"; reviewer audit Major#2): drives the create
        screen end-to-end -- list -> create screen -> name -> first row ->
        addRow -> second row -> submit -> dashboard -- instead of calling
        createGathering directly. This exercises organizerGatheringCreate.
        submit's success path and addRow for the first time in this suite.
        """
        self._sign_in()
        self.steps.organizer_prepares_a_gathering(
            "第7回 社内ランチ会", [days_from_now_iso(3), days_from_now_iso(10)]
        )
        self.steps.organizer_creates_the_gathering()
        self.steps.gathering_is_created_in_scheduling_phase()
        self.steps.prepared_candidate_dates_are_all_registered()
        self.steps.gathering_has_no_confirmed_date()
        self.steps.dashboard_is_shown_for(self.dsl.gathering_id, "SCHEDULING")

    def test_tdr_gth_02_organizer_adds_a_candidate_date_after_creation(self) -> None:
        """Rewritten (adr/0038, reviewer audit Major#1 resolved): drives the
        inline add-candidate-date form end-to-end -- opening it, submitting a
        new date, and observing it appear -- rather than the prior no-side-
        effect click plus a separate direct API POST.
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会2", [days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        before_dates = self.steps.candidate_dates_snapshot()
        self.steps.organizer_opens_the_add_candidate_date_form()
        # Reviewer audit Major#3: the cross-cutting forbidden-surfaces check
        # (ADR-0039's registered-value-entry-control exemption) had never run
        # while gathering-add-candidate-date-form/-input -- the very controls
        # that motivated ADR-0039 -- actually existed in the DOM.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        new_date_iso = days_from_now_iso(20)
        response = self.steps.organizer_submits_the_add_candidate_date_form(new_date_iso)
        self.steps.new_candidate_date_is_added_via_inline_form(response, before_dates, "SCHEDULING")

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
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.participant_token_is_not_persisted(link)
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
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

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
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.participant_token_is_not_persisted(link)

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
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

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

    # TDR-GTH-21 through TDR-GTH-25 (adr/0038, entry screens) ---------------

    def test_tdr_gth_21_organizer_opens_a_gathering_from_the_list(self) -> None:
        self._sign_in()
        gathering_a, gathering_b = self.steps.organizer_has_multiple_scheduling_gatherings(
            [("会21a", [days_from_now_iso(3)]), ("会21b", [days_from_now_iso(10)])]
        )
        confirmed_date_iso = gathering_b["candidateDates"][0]["startAt"]
        confirmed_date_id = gathering_b["candidateDates"][0]["id"]
        gathering_b = self.steps.gathering_candidate_date_is_confirmed_via_api(
            gathering_b["id"], confirmed_date_id
        )
        # Issues one link for gathering_b so data-active-issued-links has a
        # non-zero value to check (reviewer audit Major#1): an all-zero
        # expected value would still catch a missing attribute, but not one
        # that is present yet wrong.
        self.steps.a_participant_link_is_issued()
        self.steps.organizer_opens_the_gathering_list()
        # createdAt descending (新しい順): the more-recently-created gathering_b
        # first. This does not assert either gathering's title/name -- see
        # assert_gathering_list_matches's own docstring for the contract gap.
        self.steps.gathering_list_matches(
            [
                {
                    "id": gathering_b["id"],
                    "phase": "SELECTING_SHOP",
                    "confirmedCandidateDate": confirmed_date_iso,
                    "respondedCount": 0,
                    "activeIssuedLinks": 1,
                },
                {
                    "id": gathering_a["id"],
                    "phase": "SCHEDULING",
                    "confirmedCandidateDate": None,
                    "respondedCount": 0,
                    "activeIssuedLinks": 0,
                },
            ]
        )
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.organizer_opens_gathering_from_list(gathering_a["id"])
        self.steps.dashboard_is_shown_for(gathering_a["id"], "SCHEDULING")

    def test_tdr_gth_22_organizer_creates_a_gathering_from_the_empty_state(self) -> None:
        self._sign_in()
        self.steps.organizer_opens_the_gathering_list()
        self.steps.gathering_list_is_empty()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.organizer_activates_create_open_from_the_empty_state()
        self.steps.gathering_create_screen_is_shown()

    def test_tdr_gth_23_cannot_create_a_gathering_without_a_candidate_date(self) -> None:
        self._sign_in()
        self.steps.organizer_opens_the_gathering_create_screen()
        self.steps.organizer_fills_the_gathering_name("会23")
        self.steps.gathering_create_submit_is_disabled()
        attempt_create_without_dates = (
            self.steps.organizer_attempts_to_create_gathering_via_api_with_no_candidate_dates
        )
        response = attempt_create_without_dates("会23")
        self.steps.create_is_rejected_for_missing_candidate_dates(response)
        self.steps.no_gathering_exists_with_title("会23")
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_24_duplicate_candidate_date_is_rejected_by_the_inline_form(self) -> None:
        self._sign_in()
        existing_iso = days_from_now_iso(3)
        self.steps.organizer_has_a_scheduling_gathering("会24", [existing_iso])
        self.steps.organizer_opens_the_dashboard()
        before_dates = self.steps.candidate_dates_snapshot()
        self.steps.organizer_opens_the_add_candidate_date_form()
        response = self.steps.organizer_submits_the_add_candidate_date_form(existing_iso)
        self.steps.duplicate_candidate_date_is_rejected(response, existing_iso, before_dates)

    def test_tdr_gth_25_candidate_screen_links_to_the_gathering_list_with_a_count(self) -> None:
        self._sign_in()
        self.steps.lunch_candidate_screen_is_available()
        self.steps.organizer_has_multiple_scheduling_gatherings(
            [("会25a", [days_from_now_iso(3)]), ("会25b", [days_from_now_iso(10)])]
        )
        self.steps.organizer_opens_the_lunch_candidate_screen()
        self.steps.in_progress_gathering_count_badge_shows(2)
        self.steps.organizer_opens_the_gathering_entry()
        self.steps.gathering_list_screen_is_shown()

    # TDR-GTH-26 through TDR-GTH-36 (adr/0040/0041/0042: shop shortlisting, D7
    # replace, approval voting, finalize, finalized views) -----------------

    def test_tdr_gth_26_organizer_selects_five_shops_and_starts_voting(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会26", [thursday])
        open_shop_ids = self.steps.open_shop_ids_for_the_confirmed_date()
        # Reviewer audit Major#3: SHOP_VOTING_NOT_STARTED (409) was never
        # exercised for either operation it gates -- Gathering.shortlistedShops
        # is still empty at this point (setShortlistedShops has not been
        # called yet).
        finalize_too_early = self.steps.organizer_attempts_to_finalize_via_api(open_shop_ids[0])
        self.steps.rejected_because_shop_voting_not_started(finalize_too_early)
        early_link = self.steps.a_participant_link_is_issued()
        vote_too_early = self.steps.participant_attempts_to_vote_via_api(
            early_link, {open_shop_ids[0]: "WANT_TO_GO"}
        )
        self.steps.rejected_because_shop_voting_not_started(vote_too_early)
        # Reviewer audit Major#3: INVALID_SHOP_SELECTION's two count-boundary
        # triggers (0 entries, more than 5) were never exercised -- only the
        # out-of-population trigger was (TDR-GTH-27).
        empty_selection = self.steps.organizer_attempts_to_shortlist_shops_via_api([])
        self.steps.rejected_as_invalid_shop_selection(empty_selection)
        too_many = self.steps.organizer_attempts_to_shortlist_shops_via_api(open_shop_ids)
        self.steps.rejected_as_invalid_shop_selection(too_many)
        self.steps.organizer_opens_the_dashboard()
        # Reviewer audit Major#1: shortlistSelection is one of six new screen
        # states this cross-cutting check had never run against.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        selected = self.steps.organizer_selects_first_n_open_shops(5)
        # gathering-open-shop-select's own pending-only model (contrast with
        # participant shop-vote's immediate model, adr/0042's asymmetric design):
        # nothing is sent to the server until submit is activated.
        self.steps.no_shortlist_is_recorded_yet()
        self.steps.organizer_submits_the_shortlist()
        self.steps.shortlisted_shops_match(selected)
        self.steps.gathering_phase_is("SELECTING_SHOP")

    def test_tdr_gth_27_only_open_shops_are_offered_for_voting(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        monday = next_weekday_iso(0)  # OPEN_SHOP_COUNT_BY_WEEKDAY[0] == 5 (1 closed)
        thursday = next_weekday_iso(3)  # OPEN_SHOP_COUNT_BY_WEEKDAY[3] == 6 (all open)
        self.steps.organizer_has_a_scheduling_gathering("会27", [monday, thursday])
        self.steps.organizer_opens_the_dashboard()
        monday_id = self.dsl.candidate_date_id_at(0)
        thursday_id = self.dsl.candidate_date_id_at(1)
        closed_shop_id = self.steps.organizer_identifies_a_closed_shop(thursday_id, monday_id)
        # Reviewer audit Major#3: GATHERING_NOT_IN_SELECTING_SHOP_PHASE (409) was
        # never exercised -- the gathering is still SCHEDULING here (no date
        # confirmed yet), so setShortlistedShops must reject even a shopId that
        # is otherwise valid (one of Monday's own open shops).
        monday_open_shop_id = next(iter(self.dsl.current_preview_shop_ids()))
        phase_boundary_response = self.steps.organizer_attempts_to_shortlist_shops_via_api(
            [monday_open_shop_id]
        )
        self.steps.rejected_because_not_selecting_shop_phase(phase_boundary_response)
        self.steps.organizer_confirms_the_tentatively_selected_date()
        self.steps.shop_is_not_offered_in_the_shortlist(closed_shop_id)
        response = self.steps.organizer_attempts_to_shortlist_shops_via_api([closed_shop_id])
        self.steps.rejected_as_invalid_shop_selection(response)

    def test_tdr_gth_28_participant_answers_a_shop_with_one_of_three_tiers(self) -> None:
        """Rewritten (adr/0044, 2026-09-04 human decision): the approve-any-
        number model is retired -- a participant now answers each shortlisted
        shop with exactly one of WANT_TO_GO/OK_TO_GO/NOT_GOING (行きたい／
        行ってもいい／むり), not a boolean approve/exclude toggle.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会28", [thursday])
        shop_a, shop_b = self.steps.open_shop_ids_for_the_confirmed_date()[:2]
        self.steps.organizer_shortlists_shops_via_api([shop_a, shop_b])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_your_vote_is(shop_a, "UNANSWERED")
        self.steps.participant_answers_shop_vote(shop_a, "WANT_TO_GO")
        self.steps.shop_vote_your_vote_is(shop_a, "WANT_TO_GO")
        self.steps.shop_vote_your_vote_is(shop_b, "UNANSWERED")
        # Reviewer audit Major#1: participantAnswer.shopVoteQuestion is one of
        # six new screen states this cross-cutting check had never run against.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        # A third-tier answer ("むり") is itself a recorded vote, distinct from
        # never having answered at all (UNANSWERED) -- both are exercised here.
        self.steps.participant_answers_shop_vote(shop_b, "NOT_GOING")
        self.steps.shop_vote_your_vote_is(shop_b, "NOT_GOING")
        self.steps.participant_view_is_valid()

    def test_tdr_gth_29_other_participants_votes_are_hidden_until_self_votes(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会29", [thursday])
        shop_a, shop_b = self.steps.open_shop_ids_for_the_confirmed_date()[:2]
        self.steps.organizer_shortlists_shops_via_api([shop_a, shop_b])
        other_link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(other_link)
        self.steps.participant_answers_shop_vote(shop_a, "WANT_TO_GO")
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_tally_is_absent(shop_a)
        self.steps.shop_vote_tally_is_absent(shop_b)
        self.steps.participant_answers_shop_vote(shop_a, "OK_TO_GO")
        self.steps.shop_vote_tally_is(shop_a, want_to_go=1, ok_to_go=1, not_going=0, responded=2)
        # Per-shop gating, not global: self has not answered shop_b (only
        # shop_a), so shop_b's tally stays hidden even though shop_a's is now
        # visible -- gating is genuinely per-shop.
        self.steps.shop_vote_tally_is_absent(shop_b)

    def test_tdr_gth_30_participant_can_always_change_their_shop_vote(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会30", [thursday])
        open_shop_ids = self.steps.open_shop_ids_for_the_confirmed_date()
        shop_a, _shop_b, not_shortlisted_shop = open_shop_ids[:3]
        self.steps.organizer_shortlists_shops_via_api(open_shop_ids[:2])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_shop_vote(shop_a, "WANT_TO_GO")
        self.steps.shop_vote_your_vote_is(shop_a, "WANT_TO_GO")
        self.steps.participant_answers_shop_vote(shop_a, "NOT_GOING")
        self.steps.shop_vote_your_vote_is(shop_a, "NOT_GOING")
        # Reviewer audit Major#3: INVALID_SHOP_SELECTION's setShopVotes trigger
        # (naming a shopId absent from the current shortlist) was never
        # exercised -- only setShortlistedShops' own trigger was (TDR-GTH-27).
        foreign_vote = self.steps.participant_attempts_to_vote_via_api(
            link, {not_shortlisted_shop: "WANT_TO_GO"}
        )
        self.steps.rejected_as_invalid_shop_selection(foreign_vote)

    def test_tdr_gth_31_kept_shops_retain_votes_after_a_replace(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会31", [thursday])
        shops = self.steps.open_shop_ids_for_the_confirmed_date()[:6]
        shop_0, shop_1, shop_2, _shop_3, shop_4, shop_5 = shops
        self.steps.organizer_shortlists_shops_via_api(shops[:5])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_shop_votes(
            {shop_0: "WANT_TO_GO", shop_1: "OK_TO_GO", shop_2: "NOT_GOING"}
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shop_tally_is(
            shop_0, want_to_go=1, ok_to_go=0, not_going=0, responded=1
        )
        self.steps.shortlisted_shop_tally_is(
            shop_1, want_to_go=0, ok_to_go=1, not_going=0, responded=1
        )
        self.steps.shortlisted_shop_tally_is(
            shop_2, want_to_go=0, ok_to_go=0, not_going=1, responded=1
        )
        self.steps.organizer_replaces_a_shortlisted_shop(shop_4, shop_5)
        self.steps.shortlisted_shop_tally_is(
            shop_0, want_to_go=1, ok_to_go=0, not_going=0, responded=1
        )
        self.steps.shortlisted_shop_tally_is(
            shop_1, want_to_go=0, ok_to_go=1, not_going=0, responded=1
        )
        self.steps.shortlisted_shop_tally_is(
            shop_2, want_to_go=0, ok_to_go=0, not_going=1, responded=1
        )

    def test_tdr_gth_32_a_newly_replaced_shop_stays_unanswered_for_participants_who_already_voted(
        self,
    ) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会32", [thursday])
        shops = self.steps.open_shop_ids_for_the_confirmed_date()[:6]
        shop_0, _shop_1, _shop_2, _shop_3, shop_4, shop_5 = shops
        self.steps.organizer_shortlists_shops_via_api(shops[:5])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_shop_vote(shop_0, "WANT_TO_GO")
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_replaces_a_shortlisted_shop(shop_4, shop_5)
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_your_vote_is(shop_5, "UNANSWERED")
        self.steps.shop_vote_tally_is_absent(shop_5)
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shop_tally_is(
            shop_5, want_to_go=0, ok_to_go=0, not_going=0, responded=0
        )

    def test_tdr_gth_33_organizer_finalizes_the_date_and_shop(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会33", [thursday])
        shop_a, shop_b, foreign_shop = self.steps.open_shop_ids_for_the_confirmed_date()[:3]
        self.steps.organizer_shortlists_shops_via_api([shop_a, shop_b])
        link = self.steps.a_participant_link_is_issued()
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.organizer_opens_the_dashboard()
        # Reviewer audit Major#1: shortlistedShopVotes (with the finalize
        # radios/submit present) is one of six new screen states this
        # cross-cutting check had never run against.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        # Reviewer audit Major#3: INVALID_SHOP_SELECTION's finalizeGathering
        # trigger (naming a shopId absent from the current shortlist) was
        # never exercised -- only setShortlistedShops' own trigger was
        # (TDR-GTH-27).
        foreign_finalize = self.steps.organizer_attempts_to_finalize_via_api(foreign_shop)
        self.steps.rejected_as_invalid_shop_selection(foreign_finalize)
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_submits_finalize()
        self.steps.gathering_phase_is("FINALIZED")
        # Reviewer audit Major#1: organizerDashboard.finalizedSummary is one of
        # six new screen states this cross-cutting check had never run against.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.finalized_controls_are_absent()
        schedule_response = self.steps.participant_attempts_to_answer_via_api(
            link, candidate_date_id, "MAYBE"
        )
        self.steps.rejected_because_gathering_finalized(schedule_response)
        vote_response = self.steps.participant_attempts_to_vote_via_api(
            link, {shop_a: "WANT_TO_GO"}
        )
        self.steps.rejected_because_gathering_finalized(vote_response)
        # Reviewer audit Major#3: finalizeGathering's own third 409 branch
        # (already FINALIZED) was never exercised -- only its effect on other
        # operations was.
        refinalize_response = self.steps.organizer_attempts_to_finalize_via_api(shop_a)
        self.steps.rejected_because_gathering_finalized(refinalize_response)

    def test_tdr_gth_34_finalized_view_shows_the_decision_and_own_record_only(self) -> None:
        """Rewritten (adr/0044 three-tier model; adr/0046 open item 3,
        2026-09-05 human decision): the finalized retrospective now carries
        one entry per shortlisted shop -- including one this participant
        never voted on, shown as "UNANSWERED" rather than omitted. shop_b
        below is exactly that shop: only other_link votes it, `link` never
        does, satisfying TDR-GTH-34's own added Given ("投票にかけられた店の
        中に、その参加者が一度も答えなかった店が1件ある").
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_scheduling_gathering("会34", [thursday])
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        self.steps.gathering_candidate_date_is_confirmed_via_api(
            self.dsl.gathering_id, candidate_date_id
        )
        self.steps.gathering_state_is_refreshed()
        shop_a, shop_b = self.steps.open_shop_ids_for_the_confirmed_date()[:2]
        self.steps.organizer_shortlists_shops_via_api([shop_a, shop_b])
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_shop_vote(shop_a, "WANT_TO_GO")
        other_link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(other_link)
        self.steps.participant_answers_shop_vote(shop_b, "OK_TO_GO")
        confirmed_date_iso = self.dsl.gathering["candidateDates"][0]["startAt"]
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_submits_finalize()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_decision_is(
            confirmed_candidate_date=confirmed_date_iso,
            shop_id=shop_a,
            your_schedule_response="GOING",
            shop_votes={shop_a: "WANT_TO_GO", shop_b: "UNANSWERED"},
        )
        self.steps.participant_question_surfaces_are_replaced()
        # Reviewer audit Major#1: participantAnswer.finalizedView is one of six
        # new screen states this cross-cutting check had never run against.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        # Reviewer audit Major#2 (adr/0042 決定4): "名前を変える操作も置かない" --
        # gathering-participant-name-open/-submit must also be absent once
        # ParticipantView.decision is non-null, not only the schedule/vote/
        # progress surfaces participant_question_surfaces_are_replaced checks.
        self.steps.participant_name_controls_are_absent()
        schedule_response = self.steps.participant_attempts_to_answer_via_api(
            link, candidate_date_id, "MAYBE"
        )
        self.steps.rejected_because_gathering_finalized(schedule_response)
        vote_response = self.steps.participant_attempts_to_vote_via_api(
            link, {shop_a: "WANT_TO_GO"}
        )
        self.steps.rejected_because_gathering_finalized(vote_response)

    def test_tdr_gth_35_no_new_participant_links_after_finalized(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会35", [thursday])
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_submits_finalize()
        response = self.steps.organizer_attempts_to_issue_a_participant_link_via_api()
        self.steps.rejected_because_gathering_finalized(response)
        self.steps.finalized_controls_are_absent()

    def test_tdr_gth_36_organizer_can_still_recopy_a_link_after_finalized(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会36", [thursday])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_submits_finalize()
        recopied_url = self.steps.organizer_recopies_the_link_at(0)
        self.steps.recopied_link_matches_original(recopied_url, link)

    # TDR-GTH-37 through TDR-GTH-41 (adr/0044/0045/0046, 2026-09-04/05: a
    # production defect report drove three-tier voting, a nearest-first
    # stable participant shop order, and map/shop-detail observations on both
    # the organizer's shortlist-selection screen and the participant's vote
    # screen -- the latter also gaining a search-origin marker) ------------

    def test_tdr_gth_37_participant_shop_order_is_nearest_first_and_stable(self) -> None:
        """participantAnswer.shopVoteQuestion.orderingInvariant (adr/0044
        decision 2): the near-order clause is checked the same way TDR-GTH-08's
        own near-order clause already is -- self-consistency against the API's
        own claimed order, not an independent geographic recomputation (this
        suite cannot read src/** or the synthetic population's coordinates).
        The stability clause ("投票しても変わらない") is fully verifiable:
        the DOM order recorded before a vote must equal the order after it.
        The invariant text also names votes cast by other participants
        (reviewer audit Minor#2), so a second participant's vote is checked
        too, not only this participant's own.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会37", [thursday])
        shops = self.steps.open_shop_ids_for_the_confirmed_date()[:5]
        self.steps.organizer_shortlists_shops_via_api(shops)
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_question_order_matches_participant_view(link)
        before_order = self.steps.shop_vote_question_order_snapshot()
        self.steps.participant_answers_shop_vote(shops[0], "WANT_TO_GO")
        self.steps.shop_vote_question_order_is_unchanged(before_order)
        # Reviewer audit Minor#2: another participant voting must not move
        # this participant's order either -- reopen this link (fresh page
        # load) after a different participant votes on a different shop.
        other_link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(other_link)
        self.steps.participant_answers_shop_vote(shops[1], "OK_TO_GO")
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_question_order_is_unchanged(before_order)

    def test_tdr_gth_38_organizer_sees_map_and_shop_details_while_selecting(self) -> None:
        """TDR-GTH-38: shortlistSelection.list (PickFive.dc.html, the "その日に
        開いている店の一覧") shows a map and per-shop detail fields -- not the
        shortlistedShopVotes tally view (adr/0044's own documented asymmetry).
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会38", [thursday])
        self.steps.organizer_opens_the_dashboard()
        self.steps.open_shop_list_shows_map_and_shop_details()
        # Reviewer audit Major#1's own lesson (前ラウンドで2回指摘): a
        # cross-cutting check must be exercised against every new screen
        # state a round introduces, not only re-run against ones a prior
        # round already covered -- this is the map-bearing selection screen.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_39_participant_sees_map_and_shop_details_while_voting(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会39", [thursday])
        shops = self.steps.open_shop_ids_for_the_confirmed_date()[:3]
        self.steps.organizer_shortlists_shops_via_api(shops)
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_question_list_shows_map_and_shop_details(link)
        # Same lesson as TDR-GTH-38 above, applied to the map-bearing vote
        # screen (a distinct new screen state from the pre-map TDR-GTH-28/29).
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_40_organizer_sees_the_three_tier_breakdown_ordered_by_combined_count(
        self,
    ) -> None:
        """TDR-GTH-40: 店ごとの三段階の内訳（行きたい／行ってもいい／むり）が、
        その店に回答した人数を分母にして示され、店は「行きたい」+「行ってもいい」
        の合計が多い順に並ぶ (adr/0044 decision 3). shop_high/shop_mid/shop_low
        are engineered to distinct combined counts (2/1/0) so the ordering
        assertion does not depend on an implementation-chosen tie-break.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会40", [thursday])
        shop_high, shop_mid, shop_low = self.steps.open_shop_ids_for_the_confirmed_date()[:3]
        self.steps.organizer_shortlists_shops_via_api([shop_high, shop_mid, shop_low])
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_shop_votes(
            {shop_high: "WANT_TO_GO", shop_mid: "OK_TO_GO", shop_low: "NOT_GOING"}
        )
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.participant_answers_shop_votes(
            {shop_high: "WANT_TO_GO", shop_mid: "NOT_GOING", shop_low: "NOT_GOING"}
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shop_tally_is(
            shop_high, want_to_go=2, ok_to_go=0, not_going=0, responded=2
        )
        self.steps.shortlisted_shop_tally_is(
            shop_mid, want_to_go=0, ok_to_go=1, not_going=1, responded=2
        )
        self.steps.shortlisted_shop_tally_is(
            shop_low, want_to_go=0, ok_to_go=0, not_going=2, responded=2
        )
        self.steps.shortlisted_shop_list_is_ordered_by_combined_tier_descending()

    def test_tdr_gth_41_participant_map_shows_the_search_origin_marker(self) -> None:
        """TDR-GTH-41 (adr/0045): 参加者の投票画面の地図には検索基点の位置も
        示される -- extends ADR-0025 decision 1's organizer-only disclosure to
        this unauthenticated, signed-link screen.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会41", [thursday])
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_map_shows_search_origin_marker()
        # Reviewer audit Minor#3: this test introduces the search-origin
        # marker itself, so it must call the cross-cutting check directly
        # rather than rely on TDR-GTH-39's incidental coverage of the same
        # screen-state gating (shopVoteMap's votingStartedAt presenceRule).
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    # TDR-GTH-42 (adr/0047, 2026-09-06): a participant screen that fails to
    # load unrecognizably shows a short notice instead of rendering blank --

    def test_tdr_gth_42_participant_load_failure_shows_a_short_notice(self) -> None:
        """TDR-GTH-42: 参加者画面の読み込みに失敗すると短いお知らせが示される.
        Given a valid signed link (a_participant_link_is_issued mirrors
        TDR-GTH-14/15/19's own Given shape); the seam under test
        (seedParticipantLinkServerError) makes only the *next*
        getParticipantView call fail unrecognizably, so opening the link
        once is the trigger for "画面の読み込みに失敗する". This is a
        distinct outcome from invalidLinkOutcome (TDR-GTH-14/19's
        LINK_EXPIRED/LINK_REVOKED) -- asserting mutual exclusivity against
        every surface those two outcomes require, not only the two the
        scenario body names (設問), is what actually exercises
        unexpectedLoadFailureOutcome's own "mutually exclusive and
        exhaustive" declaration.
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会42", [days_from_now_iso(3)])
        link = self.steps.a_participant_link_is_issued()
        self.steps.link_is_seeded_to_fail_unexpectedly(link)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_sees_a_load_failure_notice()
        self.steps.load_failure_hides_the_schedule_and_shop_questions()
        self.steps.load_failure_has_no_retry_control()
        self.steps.load_failure_is_exclusive_of_other_outcomes()
        self.steps.load_failure_discloses_no_technical_detail()
        # This is a new participant screen state (blank-until-now, adr/0047's
        # own developer-found gap) -- FR-030's repeated lesson is that the
        # cross-cutting check must be exercised against every new screen
        # state a round introduces.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    # TDR-GTH-43 (adr/0048, 2026-09-06): candidate dates tied on goingCount
    # must render in a deterministic, reopen-stable order --------------------

    def test_tdr_gth_43_candidate_date_order_is_stable_and_deterministic(self) -> None:
        """TDR-GTH-43: 得票が同じ候補日でも、並び順は開くたびに変わらない.
        Candidate dates are supplied out of chronological order at creation
        time (30/3/15 days out) so a defect that reintroduced an insertion-
        or creation-order tie-break would fail this assertion instead of
        passing by coincidence -- adr/0048 replaced an undocumented
        "implementation-chosen stable" tie-break with startAt ascending.
        Also checks participantAnswer.scheduleQuestion (adr/0048 decision 2):
        gathering-scheduling-api.yaml's own scheduleQuestions description
        names this same fix as needed to reliably reach a specific candidate
        date's question across repeated loads -- the participant-side shape
        of the identical production defect (gathering-schedule-question
        intermittently not found). Checking both surfaces from this one
        scenario, rather than only its literal "幹事が…開き直す" wording,
        follows the same beyond-the-literal-clause precedent
        TDR-GTH-37 already set.
        """
        self._sign_in()
        candidate_date_isos = [
            days_from_now_iso(30),
            days_from_now_iso(3),
            days_from_now_iso(15),
        ]
        self.steps.organizer_has_a_scheduling_gathering("会43", candidate_date_isos)

        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_order_matches_start_at_order(candidate_date_isos)
        before_order = self.steps.candidate_date_order_snapshot()
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_order_is_unchanged(before_order)
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_order_is_unchanged(before_order)
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.first_reachable_schedule_question_matches_start_at_order(candidate_date_isos)
        first_seen = self.steps.first_reachable_schedule_question_candidate_date()
        self.steps.participant_opens_the_link(link)
        self.steps.first_reachable_schedule_question_is_unchanged(first_seen)
        self.steps.participant_opens_the_link(link)
        self.steps.first_reachable_schedule_question_is_unchanged(first_seen)
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
