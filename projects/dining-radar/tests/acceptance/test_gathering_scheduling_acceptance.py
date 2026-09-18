"""JS-capable browser/API L4 runner for TDR-GTH-01 through TDR-GTH-63.

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
TDR-GTH-49 through TDR-GTH-55 (ADR-0054/0055/0056, 2026-09-12〜13, contracts/
REVISION-PLAN.md 5節) add: the per-participant/per-candidate-date response
table (49), removing a candidate date and the confirmed-date rejection
boundary (50/51), the post-finalize decision map (52), the finalize
confirmation dialog (53), and the corrected zero-vote/tie current-leader
rules (54/55). TDR-GTH-20/34/38's own bodies were rewritten this round too
(see each test's own docstring for what changed and why).

**Corrected (2026-09-13, gathering-scheduling-browser-interface.yaml 0.18.0
追補15, second integration round)**: the note this docstring previously
carried here -- "TDR-GTH-09 is unchanged... participantAnswer.
scheduleQuestion still requires data-open-shop-count unconditionally" -- was
itself wrong against this contract revision. gathering-scheduling-api.yaml
removed ParticipantScheduleQuestion.openShopCount at v0.11.0;
gathering-scheduling.feature's own TDR-GTH-09 body was rewritten the same
round (ADR-0055 decision 1) to a negative assertion ("その候補日に開いている
店の件数は示されない"), and 0.18.0 closed the contradiction by requiring
this element carry no data-open-shop-count attribute at all. See
test_tdr_gth_09_participant_sees_no_open_shop_count_or_shop_details below.

TDR-GTH-56 (ADR-0056 decision 9, gathering-scheduling-browser-interface.yaml
0.15.0 追補12) adds the shop-vote bar's total-active-participant-count
denominator, sized against the whole group rather than respondents so far.

**Updated 2026-09-17 (ADR-0061, 束C「参加者を呼ぶ・答える」, browser-interface
0.23.0 / api 0.17.0)**: TDR-GTH-03 now issues at least one link through
issueDialog's own two-step copy flow (issue_participant_link_and_copy_via_
dialog), asserting the clipboard write there instead of on the bare
participantLinkCopy activation (decision 1). TDR-GTH-34 is rewritten again --
decision 5 reverses ADR-0055 decision 8 a second time, so the finalized
participant view once more shows no other shop's tally/map, matching
TDR-GTH-34's own text (which this round leaves unchanged, same as every prior
round). test_gth_answer_later_and_peek_results_are_functional is retired along
with the two controls it exercised (decision 3) and replaced by
test_gth_participant_day_navigation_is_functional, the same "contract Must
with no dedicated scenario" precedent, now covering daySkip/dayPrevious/
dayList/auto-advance instead. New: TDR-GTH-64 (decision 2, respondentList).

TDR-GTH-07/43/57..63 (ADR-0060, 2026-09-16, gathering-scheduling-browser-
interface.yaml 0.22.0 / gathering-scheduling-api.yaml v0.16.0): candidate
dates are ordered by startAt ascending (開催日の早い順), replacing adr/0048's
goingCount-descending rule (TDR-GTH-07 rewritten, TDR-GTH-43's own assertion
is unchanged but now checks the primary rule, not a tie-break); a Saturday,
Sunday, or Japan public holiday can no longer be a candidate date, enforced
by createGathering/addCandidateDates with the new CANDIDATE_DATE_NOT_A_
BUSINESS_DAY code (TDR-GTH-57/58); and gathering-candidate-date/
scheduleQuestion.tally gain a data-current-leader attribute computed by a
two-level goingCount-then-maybeCount cascade, mirrored unchanged to the
participant side (TDR-GTH-59..63). organizerGatheringCreate's own "つくる"
is now open-then-confirm (gathering-create-review-open/-dialog/-cancel,
ADR-0060 decision 5) -- create_prepared_gathering_via_browser and
test_tdr_gth_23 below are rewritten to match; gathering-create-submit and
gathering-create-candidate-date-remove-selected keep their existing test
ids/purposes, only their DOM home and requirement (remove-selected is now
scoped to the dialog's own currently-displayed month) changed.
"""

from __future__ import annotations

import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from tests.acceptance.dsl.gathering_scheduling_browser import (
    OPEN_SHOP_COUNT_BY_WEEKDAY,
    GatheringSchedulingBrowserDsl,
    next_fixed_public_holiday_on_weekday_iso,
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
            "第7回 社内ランチ会", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
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
        effect click plus a separate direct API POST. **Rewritten again
        2026-09-09 (adr/0049 decision 3)**: the form's single date-time input
        is retired -- selecting one calendar day and submitting the batch
        addCandidateDates now drives this same flow (a batch of one).
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会2", [self.dsl.days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        before_dates = self.steps.candidate_dates_snapshot()
        self.steps.organizer_opens_the_add_candidate_date_form()
        # Reviewer audit Major#3: the cross-cutting forbidden-surfaces check
        # (ADR-0039's registered-value-entry-control exemption) had never run
        # while gathering-add-candidate-date-form/-input -- the very controls
        # that motivated ADR-0039 -- actually existed in the DOM.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        new_date_iso = self.dsl.days_from_now_iso(20)
        response = self.steps.organizer_submits_the_add_candidate_date_form([new_date_iso])
        self.steps.new_candidate_dates_are_added_via_inline_form(
            response, before_dates, "SCHEDULING"
        )

    def test_tdr_gth_03_organizer_issues_participant_links(self) -> None:
        """**Rewritten 2026-09-17 (ADR-0061決定1, human decision "発行で小窓が
        開き、そこでコピー")**: issuing now opens gathering-participant-link-
        issue-dialog rather than writing to the clipboard directly; TDR-GTH-03's
        own "そのまま貼り付けて使える状態で得られる" is now asserted against
        the dialog's own 「リンクをコピー」 activation
        (issue_participant_link_and_copy_via_dialog), not the bare
        participantLinkCopy click every other scenario reuses as a Given
        (issue_participant_link_from_dashboard, which no longer embeds a
        clipboard assertion at all -- PR #196監査Minor, ADR-0061未決事項2).
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会3", [self.dsl.days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        first_link = self.steps.organizer_issues_and_copies_a_participant_link_via_dialog()
        second_link = self.steps.organizer_issues_a_participant_link()
        links = [first_link, second_link]
        self.steps.issued_links_are_distinct(links)
        first_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.participant_opens_the_link(links[0])
        self.steps.participant_answers_the_candidate_date(first_date_id, "GOING")
        self.steps.participant_opens_the_link(links[1])
        self.steps.participant_view_for_other_link_is_still_unanswered(first_date_id)

    def test_tdr_gth_04_participant_answers_without_a_name(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会4", [self.dsl.days_from_now_iso(3)])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_first_candidate_date("GOING")
        self.steps.participant_is_recorded_as_nameless()
        self.steps.organizer_opens_the_dashboard()
        self.steps.dashboard_shows_responded_summary(1, 1)

    def test_tdr_gth_05_participant_attaches_a_name_later(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会5", [self.dsl.days_from_now_iso(3)])
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
            "会6", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
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
        """**Rewritten 2026-09-16 (ADR-0060 decision 6, human decision: 候補日
        は日付順)**: candidate_date_a is given the *later* startAt and
        candidate_date_b the *earlier* one (reversed from this test's own
        pre-ADR-0060 shape, where candidate_date_a's larger goingCount used
        to place it first) -- deliberately proving the list's order now
        tracks startAt, not goingCount: candidate_date_a still accumulates
        strictly more responses than candidate_date_b below, so a list still
        ordered by goingCount descending would show candidate_date_a first,
        while the date-ordered list this scenario now asserts shows it
        second.
        """
        self._sign_in()
        earlier_iso = self.dsl.days_from_now_iso(3)
        later_iso = self.dsl.days_from_now_iso(10)
        self.steps.organizer_has_a_scheduling_gathering("会7", [earlier_iso, later_iso])
        candidate_date_b = self.dsl.candidate_date_id_at(0)  # earlier_iso
        candidate_date_a = self.dsl.candidate_date_id_at(1)  # later_iso, more responses below
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
        self.steps.candidate_date_order_matches_start_at_order([earlier_iso, later_iso])

    def test_tdr_gth_08_organizer_previews_open_shops_for_a_tentative_date(self) -> None:
        """**Rewritten 2026-09-09 (adr/0049 decision 2, 2026-09-08 human
        decision: 日程を聞いている段階の店は件数だけ)**: this preview no
        longer carries a shop-item list -- checks the count only, plus the
        rewritten scenario's stronger "店名やその他の店舗情報は示されない".
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        monday = self.dsl.next_weekday_iso(0)
        other_day = self.dsl.days_from_now_iso(45)
        self.steps.organizer_has_a_scheduling_gathering("会8", [monday, other_day])
        self.steps.organizer_opens_the_dashboard()
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.organizer_tentatively_selects_the_candidate_date(candidate_date_id)
        self.steps.open_shop_preview_shows_count(OPEN_SHOP_COUNT_BY_WEEKDAY[0])
        self.steps.open_shop_preview_shows_no_shop_details()
        self.steps.gathering_phase_is("SCHEDULING")
        self.steps.no_candidate_date_is_confirmed()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_09_participant_sees_no_open_shop_count_or_shop_details(self) -> None:
        """**書き換え（2026-09-13、ADR-0055決定1、人間裁定「参加者の画面から
        『この日に開いている店N件』を消す」、gathering-scheduling.feature
        TDR-GTH-09本文の書き換えに追随）**: 旧シナリオは件数が「示される」
        ことを検査していたが、gathering-scheduling-api.yamlがv0.11.0で
        ParticipantScheduleQuestion.openShopCountを削除し、契約0.18.0
        追補15がdata-open-shop-count属性そのものの不在を要求するよう
        是正した。件数も店の情報も「無い」ことを検査する。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        wednesday = self.dsl.next_weekday_iso(2)
        self.steps.organizer_has_a_scheduling_gathering("会9", [wednesday])
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.schedule_question_has_no_open_shop_count(candidate_date_id)
        self.steps.schedule_question_shows_no_shop_details(candidate_date_id)
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.participant_token_is_not_persisted(link)

    def test_tdr_gth_10_organizer_confirms_a_candidate_date(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会10", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
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
            "会11", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
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

    def test_tdr_gth_12_other_answers_are_visible_even_before_self_answers(self) -> None:
        """**Rewritten 2026-09-09 (adr/0050 decision 2, 2026-09-08〜09 human
        decision: 約束は覆してもよい)**: replaces the retired "answer first,
        then see others" scenario. link_b sees link_a's already-recorded
        answer *before* link_b answers anything, and the tally remains
        visible (unchanged) once link_b does answer.
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会12", [self.dsl.days_from_now_iso(3)])
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        link_a = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_a)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        link_b = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_b)
        self.steps.schedule_question_shows_response(candidate_date_id, "UNANSWERED")
        self.steps.schedule_question_tally_is(candidate_date_id, going=1, maybe=0, not_going=0)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "MAYBE")
        self.steps.schedule_question_tally_is(candidate_date_id, going=1, maybe=1, not_going=0)

    def test_gth_participant_day_navigation_is_functional(self) -> None:
        """UI実装詳細（ADR-0061決定3、2026-09-17人間裁定「1日ずつ、答えると
        自動で次の日へ」）: no dedicated TDR-GTH-6x scenario names daySkip/
        dayPrevious/dayList/responseOptions' own auto-advance individually
        (the contract's own note), so this is verified here directly as a
        contract Must with no scenario of its own -- replacing the retired
        test_gth_answer_later_and_peek_results_are_functional, which this
        same round's decision 3 overturned (「あとで答える」「結果をのぞく」
        は廃止). scheduleQuestion.cardinality's own reasoning applies: every
        answer already saves itself the moment it is submitted, so there is
        nothing this test needs to prove about leaving mid-way beyond what
        TDR-GTH-06 already covers -- what this Must-only test proves instead
        is the navigation surface itself (auto-advance, skip, previous, and
        jumping via the day list), including the progress counter's own two
        attributes staying correct throughout.
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering_with_business_days("会nav", 3)
        date_a, date_b, date_c = (self.dsl.candidate_date_id_at(index) for index in range(3))
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)

        self.steps.participant_schedule_progress_is(total=3, answered=0)
        self.steps.participant_day_previous_is_disabled()

        # responseOptions.requiredOutcome's own auto-advance: answering the
        # currently-displayed (first) day moves on to the next one.
        self.steps.participant_answers_the_currently_displayed_day("GOING")
        self.steps.participant_currently_displayed_day_is(date_b)
        self.steps.participant_schedule_progress_is(total=3, answered=1)
        self.steps.schedule_question_shows_response(date_a, "GOING")
        self.steps.schedule_question_shows_response(date_b, "UNANSWERED")

        # daySkip (「とばす」): moves past date_b without answering it.
        skipped = self.steps.participant_skips_the_currently_displayed_day()
        self.assertEqual(skipped, date_b)
        self.steps.participant_currently_displayed_day_is(date_c)
        self.steps.schedule_question_shows_response(date_b, "UNANSWERED")
        self.steps.participant_schedule_progress_is(total=3, answered=1)

        # dayPrevious (「前の日」): steps back from date_c to date_b.
        self.steps.participant_goes_to_the_previous_day()
        self.steps.participant_currently_displayed_day_is(date_b)

        # dayList (「日の一覧から日へ飛ぶ」): jumps directly to date_c.
        self.steps.participant_jumps_to_day_via_day_list(date_c)
        self.steps.participant_currently_displayed_day_is(date_c)
        self.steps.participant_answers_the_candidate_date(date_c, "NOT_GOING")
        self.steps.participant_schedule_progress_is(total=3, answered=2)

        # Finishing the last unanswered day (date_b, reached via the day
        # list) leaves every candidate date answered -- dayList doubles as
        # the "全部答えました" summary via this same progress counter
        # (gathering-participant-progress's own two attributes, contract's
        # own derivation note), no separate completion element exists.
        self.steps.participant_jumps_to_day_via_day_list(date_b)
        self.steps.participant_answers_the_candidate_date(date_b, "MAYBE")
        self.steps.participant_schedule_progress_is(total=3, answered=3)
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_gth_participant_day_list_sheet_is_functional_at_narrow_viewport(self) -> None:
        """UI実装詳細（ADR-0061 追補21、2026-09-18、contractVersion 0.23.1）。
        dayList.sheetOpen/sheetCloseに専用のTDR-GTH-*シナリオは無い（契約
        自身の注記）ので、test_gth_participant_day_navigation_is_functional
        と同じ「専用シナリオの無い契約Must」の扱いでここで直接検査する。

        **経緯（コーディネーター報告）**: この2つのボタンはdayListがスマホ幅で
        シートとして提示される画面にだけ現れる（sheetOpen/sheetClose.
        presenceRule）。developerの実装（44px・キーボード到達性の
        ADR-0020決定4監査、コミット54bf388）が先にtestId/data-gathering-
        control-purposeを付けたが、この契約が一度もそのpurposeを登録して
        いなかったため、assert_gathering_screen_has_no_forbidden_surfacesが
        この画面をスマホ幅で走査すると落ちる状態だった——この受け入れ
        テストは常にPC幅（CANDIDATE_SEARCH_DESKTOP_TWO_COLUMN_VIEWPORT等）
        でこの画面を開いていたため、気付けなかった（ADR-0061 追補21で
        契約側を是正、本テストがスマホ幅を初めて開く）。
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会daylistsheet", [self.dsl.days_from_now_iso(3)]
        )
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_uses_a_narrow_viewport()
        self.steps.participant_opens_the_link(link)
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.day_list_sheet_open_is_present()

        # sheetOpen.requiredOutcome: "Activating it discloses dayList as a
        # bottom sheet".
        self.steps.participant_opens_the_day_list_sheet()
        self.steps.day_list_is_visible()
        self.steps.day_list_sheet_close_is_offered()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

        # sheetClose.requiredOutcome: "Activating it hides the bottom sheet
        # sheetOpen discloses".
        self.steps.participant_closes_the_day_list_sheet()
        self.steps.day_list_is_not_visible()
        self.steps.day_list_sheet_close_is_not_offered()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_13_guessing_a_token_is_denied_without_disclosure(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "秘密の会13", [self.dsl.days_from_now_iso(3)]
        )
        self.steps.a_participant_link_is_issued()
        response = self.steps.someone_guesses_a_token_and_requests_the_participant_view()
        self.steps.access_is_denied_without_disclosure(response)

    def test_tdr_gth_14_expired_link_cannot_be_used(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会14", [self.dsl.days_from_now_iso(3)])
        link = self.steps.a_participant_link_is_issued()
        self.steps.link_is_seeded_as_expired(link)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_sees_link_error("LINK_EXPIRED")

    def test_tdr_gth_15_rate_limited_response_does_not_lose_prior_answers(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会15", [self.dsl.days_from_now_iso(3)])
        link, candidate_date_id = self.steps.a_participant_has_already_answered_one_candidate_date(
            "GOING"
        )
        before = self.steps.prior_answers_snapshot([candidate_date_id])
        self.steps.link_is_seeded_as_rate_limited(link)
        self.steps.participant_attempts_to_answer_expecting_rate_limit(candidate_date_id, "MAYBE")
        self.steps.prior_responses_are_retained(before)

    def test_tdr_gth_16_organizer_reviews_the_issued_link_list(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会16", [self.dsl.days_from_now_iso(3)])
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
        self.steps.organizer_has_a_scheduling_gathering("会17", [self.dsl.days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        before = self.steps.unanswered_summary_snapshot()
        recopied_url = self.steps.organizer_recopies_the_link_at(0)
        self.steps.recopied_link_matches_original(recopied_url, link)
        self.steps.unanswered_summary_unchanged(before)
        self.steps.participant_link_list_matches([{"hasResponded": False, "named": False}])

    def test_tdr_gth_18_revoking_an_unanswered_link_reduces_the_denominator(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会18", [self.dsl.days_from_now_iso(3)])
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
        self.steps.organizer_has_a_scheduling_gathering("会19", [self.dsl.days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        self.steps.organizer_revokes_the_link_at(0)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_sees_link_error("LINK_REVOKED")

    def test_tdr_gth_20_answered_link_has_no_revoke_control(self) -> None:
        """Rewritten 2026-09-13 (ADR-0055 decision 2, human decision "取り消
        すは未回答の行にだけ置く", contracts/gathering-scheduling.feature
        TDR-GTH-20). The prior scenario's own Then ("そのリンクを失効させる
        操作は無効化される") is replaced by "示されない" (not merely
        disabled): this test replaces the retired disabled-control check
        (revoke_control_is_disabled_at) with an absence check. The API's own
        PARTICIPANT_LINK_ALREADY_ANSWERED rejection is unchanged by this
        round (gathering-scheduling-api.yaml) and is kept here as a
        defense-in-depth boundary check, bypassing the (now absent, not
        merely disabled) UI control the same way TDR-GTH-23/47 already
        bypass a disabled/unreachable control to prove server-side
        enforcement.
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会20", [self.dsl.days_from_now_iso(3)])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        self.steps.organizer_opens_the_dashboard()
        self.steps.revoke_control_is_absent_at(0)
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
            [
                ("会21a", [self.dsl.days_from_now_iso(3)]),
                ("会21b", [self.dsl.days_from_now_iso(10)]),
            ]
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
        """**Rewritten 2026-09-16 (ADR-0060 decision 5)**: the name-empty/
        0-candidate-date disabled state moved from gathering-create-submit
        (now inside the review dialog) to gathering-create-review-open --
        this scenario's own Given/When never reaches the dialog at all, so
        it must check review-open's own disabledState now, not submit's.
        """
        self._sign_in()
        self.steps.organizer_opens_the_gathering_create_screen()
        self.steps.organizer_fills_the_gathering_name("会23")
        self.steps.gathering_create_review_open_is_disabled()
        attempt_create_without_dates = (
            self.steps.organizer_attempts_to_create_gathering_via_api_with_no_candidate_dates
        )
        response = attempt_create_without_dates("会23")
        self.steps.create_is_rejected_for_missing_candidate_dates(response)
        self.steps.no_gathering_exists_with_title("会23")
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_24_duplicate_candidate_date_is_rejected_by_the_inline_form(self) -> None:
        self._sign_in()
        existing_iso = self.dsl.days_from_now_iso(3)
        self.steps.organizer_has_a_scheduling_gathering("会24", [existing_iso])
        self.steps.organizer_opens_the_dashboard()
        before_dates = self.steps.candidate_dates_snapshot()
        self.steps.organizer_opens_the_add_candidate_date_form()
        response = self.steps.organizer_submits_the_add_candidate_date_form([existing_iso])
        self.steps.duplicate_candidate_date_is_rejected(response, [existing_iso], before_dates)

    def test_tdr_gth_46_batch_candidate_dates_reject_the_whole_batch_on_any_duplicate(
        self,
    ) -> None:
        """TDR-GTH-46（新規。adr/0049決定3）: a batch of two selected days,
        one of which duplicates an already-registered date, rejects the
        entire batch -- neither day is added (no partial success).
        """
        self._sign_in()
        existing_iso = self.dsl.days_from_now_iso(3)
        self.steps.organizer_has_a_scheduling_gathering("会46", [existing_iso])
        self.steps.organizer_opens_the_dashboard()
        before_dates = self.steps.candidate_dates_snapshot()
        self.steps.organizer_opens_the_add_candidate_date_form()
        new_iso = self.dsl.days_from_now_iso(20)
        response = self.steps.organizer_submits_the_add_candidate_date_form([existing_iso, new_iso])
        self.steps.duplicate_candidate_date_is_rejected(
            response, [existing_iso, new_iso], before_dates
        )

    def test_tdr_gth_47_todays_or_past_date_cannot_be_a_candidate_date(self) -> None:
        """TDR-GTH-47（新規。adr/0049決定3、adr/0051決定2）: verified from
        organizerGatheringCreate (the scenario's own Given, "幹事が会をつく
        ろうとしている") -- see attempt_create_gathering_via_api_with_a_past_
        candidate_date's own docstring for why this bypasses the calendar's
        (contract-optional) disabled-day UI affordance.
        """
        self._sign_in()
        self.steps.organizer_opens_the_gathering_create_screen()
        title = "会47"
        today_iso = self.dsl.days_from_now_iso(0)
        response = (
            self.steps.organizer_attempts_to_create_gathering_via_api_with_a_past_candidate_date(
                title, today_iso
            )
        )
        self.steps.create_is_rejected_because_date_not_in_future(response)
        self.steps.no_gathering_exists_with_title(title)

    def test_gth_create_review_dialog_pages_by_month_and_lets_the_organizer_remove_a_day(
        self,
    ) -> None:
        """review.dialog.item / monthNavigation (ADR-0060 decision 5). No
        dedicated TDR-GTH-5x/6x scenario names this control -- the same
        no-scenario-of-its-own precedent this file's own answerLater/
        peekResults test and TDR-GTH-43's ordering check already establish
        for contract Musts. Three selected days: one alone in the earliest
        month, two sharing a later month -- deliberately removing one of the
        *two* (not the last remaining day in its month), because this
        contract does not fix this dialog's behavior when a removal empties
        the currently-displayed month entirely (item.requiredOutcome's own
        note), so this test only exercises the one removal outcome the
        contract does fix.
        """
        self._sign_in()
        earlier_iso = self.dsl.days_from_now_iso(3)
        mid_a_iso, mid_b_iso = self.dsl.two_business_days_in_the_month_after_iso(earlier_iso)
        self.steps.organizer_opens_the_gathering_create_screen()
        self.steps.organizer_fills_the_gathering_name("会レビュー")
        self.steps.organizer_selects_gathering_create_candidate_dates(
            [earlier_iso, mid_a_iso, mid_b_iso]
        )
        self.steps.organizer_opens_the_gathering_create_review_dialog()
        self.assertEqual(self.steps.review_dialog_selected_days(), {earlier_iso[:10]})
        self.steps.organizer_pages_the_review_dialog_month(forward=True)
        self.assertEqual(self.steps.review_dialog_selected_days(), {mid_a_iso[:10], mid_b_iso[:10]})
        self.steps.organizer_removes_the_selected_day_from_the_review_dialog(mid_b_iso)
        self.assertEqual(self.steps.review_dialog_selected_days(), {mid_a_iso[:10]})
        self.steps.organizer_pages_the_review_dialog_month(forward=False)
        self.assertEqual(self.steps.review_dialog_selected_days(), {earlier_iso[:10]})
        payload = self.steps.organizer_confirms_the_review_dialog([earlier_iso, mid_a_iso])
        self.assertEqual(
            {date["startAt"][:10] for date in payload["candidateDates"]},
            {earlier_iso[:10], mid_a_iso[:10]},
        )

    def test_tdr_gth_25_candidate_screen_links_to_the_gathering_list_with_a_count(self) -> None:
        self._sign_in()
        self.steps.lunch_candidate_screen_is_available()
        self.steps.organizer_has_multiple_scheduling_gatherings(
            [
                ("会25a", [self.dsl.days_from_now_iso(3)]),
                ("会25b", [self.dsl.days_from_now_iso(10)]),
            ]
        )
        self.steps.organizer_opens_the_lunch_candidate_screen()
        self.steps.in_progress_gathering_count_badge_shows(2)
        self.steps.organizer_opens_the_gathering_entry()
        self.steps.gathering_list_screen_is_shown()

    # TDR-GTH-26 through TDR-GTH-36 (adr/0040/0041/0042: shop shortlisting, D7
    # replace, approval voting, finalize, finalized views) -----------------

    def test_tdr_gth_26_organizer_selects_five_shops_and_starts_voting(self) -> None:
        """**Rewired 2026-09-09 (adr/0049 decision 1)**: the WHEN step now
        drives candidate-search-browser-interface.yaml's gatheringMode
        (reached via shopSelectionEntry.open) instead of this file's own
        retired shortlistSelection -- each card toggle calls
        setShortlistedShops immediately (no separate submit).
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
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
        # out-of-population trigger was (TDR-GTH-27). open_shop_ids is
        # capped at 5 (candidate-search-api.yaml's own display cap, adr/0049
        # decision 1) -- appending a duplicate entry still exceeds
        # SetShortlistedShopsRequest's maxItems: 5 array-length bound,
        # regardless of the duplicate's own identity.
        empty_selection = self.steps.organizer_attempts_to_shortlist_shops_via_api([])
        self.steps.rejected_as_invalid_shop_selection(empty_selection)
        too_many = self.steps.organizer_attempts_to_shortlist_shops_via_api(
            [*open_shop_ids, open_shop_ids[0]]
        )
        self.steps.rejected_as_invalid_shop_selection(too_many)
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_opens_shop_selection_entry()
        # The cross-cutting purpose-declaration scan for *this* screen
        # (candidate-search-browser-interface.yaml's own
        # data-candidate-control-purpose namespace) is owned by
        # candidate_search_browser.py's ALLOWED_CONTROL_PURPOSES, exercised
        # by TDR-CS-17/18/19 in that sibling suite -- this file's own
        # screen_has_no_forbidden_controls_or_disclosures scans a different
        # attribute namespace and would be a false check here (module-
        # boundary note, top of file).
        selected = self.steps.organizer_selects_first_n_candidates_into_gathering(5)
        # **Fixed**: gathering-shortlisted-shop-item is organizerDashboard's
        # own exclusive test id (gathering-scheduling-browser-interface.yaml's
        # shortlistedShopVotes section, the same asymmetry the section's own
        # note names as deliberate, not an oversight) -- it does not exist on
        # candidate-search-browser-interface.yaml's gatheringMode screen this
        # scenario is still standing on immediately after the toggles above.
        # Calling shortlisted_shops_match here (before navigating away) was
        # asserting against a screen state that cannot be present yet. This
        # scenario already visits the dashboard next, so the fix is to check
        # identity there -- the only screen this contract lets read shopId
        # back (gatheringMode's own cardToggle carries no shopId-to-card DOM
        # correlation, so it cannot make this exact-set assertion at all).
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shops_match(selected)
        # Reviewer audit Major#1 precedent: shortlistedShopVotes (now reached
        # exclusively via gatheringMode) is a screen state this cross-cutting
        # check must still exercise on the *organizer dashboard* side.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.gathering_phase_is("SELECTING_SHOP")

    def test_tdr_gth_27_only_open_shops_are_offered_for_voting(self) -> None:
        """**Rewired 2026-09-09 (adr/0049 decision 2)**: previewOpenShopsFor
        CandidateDate no longer returns a shop list, so the closed-on-that-
        day shop is identified through two complete (<=5-open, cap-safe)
        probe gatherings instead of diffing the retired preview items --
        see fetch_shop_id_closed_only_on's own docstring. The UI-level
        absence check this scenario used to run against this file's own
        (now-retired) shortlistSelection list is dropped -- that population-
        narrowing property is now candidate-search-browser-interface.yaml's
        own, verified by TDR-CS-18 in the sibling suite -- leaving the
        API-boundary rejection as this scenario's own check.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        monday = self.dsl.next_weekday_iso(0)  # OPEN_SHOP_COUNT_BY_WEEKDAY[0]==5 (1 closed: Mon)
        wednesday = self.dsl.next_weekday_iso(2)  # OPEN_SHOP_COUNT_BY_WEEKDAY[2] == 4 (2 closed)
        closed_shop_id = self.steps.shop_id_closed_only_on(2, 0)  # closed on Wed, open on Mon
        self.steps.organizer_has_a_scheduling_gathering("会27", [monday, wednesday])
        self.steps.organizer_opens_the_dashboard()
        wednesday_id = self.dsl.candidate_date_id_at(1)
        # Reviewer audit Major#3: GATHERING_NOT_IN_SELECTING_SHOP_PHASE (409) was
        # never exercised -- the gathering is still SCHEDULING here (no date
        # confirmed yet), so setShortlistedShops must reject even a shopId
        # this contract's own weekday-matching would otherwise accept.
        phase_boundary_response = self.steps.organizer_attempts_to_shortlist_shops_via_api(
            [closed_shop_id]
        )
        self.steps.rejected_because_not_selecting_shop_phase(phase_boundary_response)
        self.steps.organizer_tentatively_selects_the_candidate_date(wednesday_id)
        self.steps.organizer_confirms_the_tentatively_selected_date()
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
        thursday = self.dsl.next_weekday_iso(3)
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

    def test_tdr_gth_29_other_participants_votes_are_visible_even_before_self_votes(self) -> None:
        """**Rewritten 2026-09-09 (adr/0050 decision 2, TDR-GTH-12's own shop-
        vote twin)**: replaces the retired "answer first, then see others"
        scenario. The tally is visible immediately on open, before this
        participant has voted on either shop, and remains visible (updated)
        once they do vote.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会29", [thursday])
        shop_a, shop_b = self.steps.open_shop_ids_for_the_confirmed_date()[:2]
        self.steps.organizer_shortlists_shops_via_api([shop_a, shop_b])
        other_link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(other_link)
        self.steps.participant_answers_shop_vote(shop_a, "WANT_TO_GO")
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_tally_is(shop_a, want_to_go=1, ok_to_go=0, not_going=0, responded=1)
        self.steps.shop_vote_tally_is(shop_b, want_to_go=0, ok_to_go=0, not_going=0, responded=0)
        self.steps.participant_answers_shop_vote(shop_a, "OK_TO_GO")
        self.steps.shop_vote_tally_is(shop_a, want_to_go=1, ok_to_go=1, not_going=0, responded=2)
        # Per-shop independence, not just global visibility: self still has
        # not answered shop_b, and its tally correctly remains 0/0/0.
        self.steps.shop_vote_tally_is(shop_b, want_to_go=0, ok_to_go=0, not_going=0, responded=0)

    def test_tdr_gth_30_participant_can_always_change_their_shop_vote(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
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
        """**Fixed** (found via ADR-0052, tester report): the "1 spare, not-
        yet-shortlisted" shop this D7 replace needs was previously found by
        probing which shop is "not open on Monday" and assuming it would
        therefore also be absent from this confirmed Thursday's own 5-shop
        display-cap sample -- true of the population (every shop is open on
        Thursday) but false of the *sample*, since which 5 of Thursday's 6
        shops the unseeded display-cap draw shows is a second, independent
        draw. Reproduced empirically failing (the probed shop appeared in
        the confirmed date's own sample, breaking the prior assertNotIn) --
        this is the same class of Given-state fragility as TDR-GTH-45's own
        fix, not a real "which day is it" dependency, though both surface
        identically as "fails depending on which random draw the run
        happens to get." adr/0052 decision 3's shown-pool-priority technique
        (fetch_confirmed_date_open_shop_ids_with_a_spare) fixes this
        deterministically instead: it performs both draws itself, from the
        same confirmed gathering, and *replays* the first draw's own shown
        set into the second -- guaranteeing (not merely likely) that the
        second draw's one new member is the true complement of the first.
        The replace itself is still driven at the setShortlistedShops API
        boundary rather than through candidate-search-browser-interface.
        yaml's own per-card toggle (see replace_shortlisted_shop's own
        docstring) -- the operation itself is unchanged by adr/0049.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会31", [thursday])
        shops, shop_5 = self.steps.confirmed_date_open_shop_ids_with_a_spare()
        shop_0, shop_1, shop_2, _shop_3, shop_4 = shops
        self.steps.organizer_shortlists_shops_via_api(shops)
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
        """**Fixed the same way TDR-GTH-31 is (see its own docstring)**. Also
        checks the tally is *present* (not absent) for the newly replaced
        shop before anyone has voted on it -- adr/0050 decision 2's
        visibility reversal makes tally unconditionally present, replacing
        the retired absent-until-self-votes assertion.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会32", [thursday])
        shops, shop_5 = self.steps.confirmed_date_open_shop_ids_with_a_spare()
        shop_0, _shop_1, _shop_2, _shop_3, shop_4 = shops
        self.steps.organizer_shortlists_shops_via_api(shops)
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_shop_vote(shop_0, "WANT_TO_GO")
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_replaces_a_shortlisted_shop(shop_4, shop_5)
        self.steps.participant_opens_the_link(link)
        self.steps.shop_vote_your_vote_is(shop_5, "UNANSWERED")
        self.steps.shop_vote_tally_is(shop_5, want_to_go=0, ok_to_go=0, not_going=0, responded=0)
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shop_tally_is(
            shop_5, want_to_go=0, ok_to_go=0, not_going=0, responded=0
        )

    def test_tdr_gth_33_organizer_finalizes_the_date_and_shop(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
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
        self.steps.organizer_finalizes_via_dashboard()
        self.steps.gathering_phase_is("FINALIZED")
        # Reviewer audit Major#1: organizerDashboard.finalizedSummary is one of
        # six new screen states this cross-cutting check had never run against.
        self.steps.screen_has_no_forbidden_controls_or_disclosures()
        self.steps.finalized_controls_are_absent()
        # participantLinkList.issuanceClosed (ADR-0056 decision 11): a new
        # positive badge this round adds alongside participantLinkCopy's own
        # (already-checked) absence.
        self.steps.participant_link_issuance_closed_badge_is_shown()
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

    def test_tdr_gth_34_finalized_view_shows_only_the_decision(self) -> None:
        """**Further simplified 2026-09-13 (ADR-0055 decision 7, human
        decision "あなたの回答は見れても別に意味ないかも" 再確認,
        contracts/gathering-scheduling.feature TDR-GTH-34)**: the single
        remaining self-record line this scenario previously required
        (yourScheduleResponse, kept after the 2026-09-09 simplification,
        adr/0050 decision 3) is retired too -- the finalized view now shows
        only the decision itself (confirmed date + shop), never any of this
        participant's own past answers.

        **Reversed back 2026-09-17 (ADR-0061決定5, human decision "他の候補の
        店と票は出さない")**: ADR-0055 decision 8 (2026-09-12) had kept the
        live shop-vote tally visible after finalization to resolve a
        self-contradiction between this contract's own presenceRule and
        TDR-GTH-34's literal text (which never stopped asserting "他の参加者の
        回答・投票、店ごとの回答の一覧は示されない"). The human has now seen
        the finalized screen in its real board form and chosen to hide every
        other shop there -- participant_question_surfaces_are_replaced below
        now asserts gathering-shop-vote-question/-tally/-map are all absent
        once finalized, matching TDR-GTH-34's own text (unchanged this round,
        same as every prior round). shop_b (voted on only by other_link,
        never by `link`) is kept in this Given purely to prove that fact does
        not surface anywhere once finalized -- not even as a live tally for a
        shop this participant never touched.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
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
        self.steps.organizer_finalizes_via_dashboard()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_decision_is(
            confirmed_candidate_date=confirmed_date_iso,
            shop_id=shop_a,
        )
        self.steps.participant_decision_has_no_own_response_attribute()
        self.steps.participant_decision_has_no_shop_breakdown()
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
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会35", [thursday])
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_finalizes_via_dashboard()
        response = self.steps.organizer_attempts_to_issue_a_participant_link_via_api()
        self.steps.rejected_because_gathering_finalized(response)
        self.steps.finalized_controls_are_absent()

    def test_tdr_gth_36_organizer_can_still_recopy_a_link_after_finalized(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会36", [thursday])
        self.steps.organizer_opens_the_dashboard()
        link = self.steps.organizer_issues_a_participant_link()
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_finalizes_via_dashboard()
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
        thursday = self.dsl.next_weekday_iso(3)
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

    def test_tdr_gth_38_organizer_sees_map_and_shop_details_on_the_vote_tally_view(self) -> None:
        """Rewritten 2026-09-13 (ADR-0055 decision 5 / ADR-0056 decision 5,
        human decision "投票タリー画面にも地図・店の情報を出す",
        contracts/gathering-scheduling.feature TDR-GTH-38). The scenario now
        names the organizer's own vote-tally view (organizerDashboard.
        shortlistedShopVotes), not candidate-search-browser-interface.
        yaml's gatheringMode (shopSelectionEntry.open) this test used to
        open before ADR-0049 retired the organizer's own shop-picking
        screen entirely -- shortlistedShopVotes now carries the map/detail
        fields directly instead (reversing the 2026-09-05 exclusion this
        same section's own contract description names as having been "a
        designer decision, not an oversight" -- ADR-0055 decision 5 finds
        that explanation itself was in error).

        **Extended 2026-09-17 (ADR-0062 decision 1, human decision, board D1
        lists ジャンル・席・禁煙・予算・徒歩約◯分 among this same row's
        visible fields)**: this view's own detailFields grow 5 more entries
        (genre/capacityTier/nonSmokingStatus/dinnerBudgetTier/walkingTime's
        own 「徒歩」-worded text) -- checked here, on the same screen this
        scenario already opens, rather than as a new scenario, since board
        D1 is the same human decision this test's own map/shop-details check
        already exists to verify. Also confirms data-added-after-voting-
        started (ADR-0056 decision 6) is retired from this same element the
        same round (board D1: 「あとから入りました」は出さない).
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会38", [thursday])
        shop_a, shop_b = self.steps.open_shop_ids_for_the_confirmed_date()[:2]
        self.steps.organizer_shortlists_shops_via_api([shop_a, shop_b])
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shop_list_shows_map_and_shop_details()
        self.steps.shortlisted_shop_items_show_detail_fields()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_39_participant_sees_map_and_shop_details_while_voting(self) -> None:
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
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
        thursday = self.dsl.next_weekday_iso(3)
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
        thursday = self.dsl.next_weekday_iso(3)
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
        self.steps.organizer_has_a_scheduling_gathering("会42", [self.dsl.days_from_now_iso(3)])
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
            self.dsl.days_from_now_iso(30),
            self.dsl.days_from_now_iso(3),
            self.dsl.days_from_now_iso(15),
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

    # TDR-GTH-44/45 (new, adr/0049 decision 1/8, 2026-09-08 human decision:
    # 店選びはランチ候補画面に一本化する). These scenarios' own screen
    # (candidate-search-browser-interface.yaml's gatheringMode) is owned by
    # the *sibling* candidate-search suite (mirrors TDR-GTH-25's existing
    # cross-file precedent) -- reused here, from the gathering-scheduling
    # side, since both scenarios' own Given ("幹事が開催日を決めた「店を選び
    # 中」の会を持っている") is this file's own gathering-scheduling Given.

    def test_tdr_gth_44_organizer_toggles_a_shop_into_and_out_of_the_gathering(self) -> None:
        """**Fixed (1)**: this scenario never leaves candidate-search-browser-
        interface.yaml's gatheringMode screen, but its two shortlisted_shops_
        match calls were asserting against gathering-shortlisted-shop-item --
        organizerDashboard's own exclusive test id (see gathering-scheduling-
        browser-interface.yaml's shortlistedShopVotes section), never present
        on this screen. Removed rather than reached via a dashboard round
        trip: gatheringMode's own cardToggle carries no shopId-to-card DOM
        correlation (its own contract note), so an exact-id-set assertion
        cannot be made here at all -- the "その店は会の候補として記録される"/
        "外れる" outcomes this scenario checks are already fully observed
        in-place, per-shop, by this test's own ref-tracked toggle-on/off
        assertions on the one card added and removed, combined with the
        shortlisted-count band below ruling out any other card having
        silently changed too.

        **Rewritten (2026-09-13, ADR-0057)**: the .feature Given now reads
        "すでに別の1件を会に入れている" -- removing the scenario's only
        shortlisted shop would collide with gathering-scheduling-api.yaml's
        SetShortlistedShopsRequest.shopIds `minItems: 1` (P2, adr/0041) and,
        since ADR-0057, would also disable that shop's own toggle outright
        (gatheringMode.cardToggle.disabledState case (2)). This Given is now
        built *before* opening the screen at all -- open_shop_ids_for_the_
        confirmed_date/organizer_shortlists_shops_via_api (both pre-existing
        Given-state builders, adr/0037 decision 1's public-API path, already
        used elsewhere for TDR-GTH-26/27/31/32) shortlist exactly 1 shop via
        setShortlistedShops directly, so the toggle click this scenario's own
        When drives is never the one used to build the Given. The When then
        adds a *second* shop (toggle_one_not_yet_shortlisted_candidate_card_
        and_return_ref, which must search for a not-yet-shortlisted card
        rather than assume index 0, since the Given's own shop may render
        first) and removes that same shop by its own data-candidate-ref
        (toggle_off_candidate_card_by_ref) -- never the Given's shop, and
        never emptying the shortlist. Each of the four gathering_mode_band_
        shows calls below observes the shortlisted count transition
        (1 -> 2 -> 1) via this screen's own band attribute, which the DSL's
        own to_have_attribute waits already ensure reflects the just-
        completed setShortlistedShops response before being read (FR-039).
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会44", [thursday])
        already_shortlisted_shop_id = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([already_shortlisted_shop_id])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_opens_shop_selection_entry()
        self.steps.gathering_mode_band_shows(shortlisted=1)
        candidate_ref = self.steps.organizer_toggles_a_shop_into_the_gathering_and_returns_its_ref()
        self.steps.gathering_mode_band_shows(shortlisted=2)
        self.steps.organizer_toggles_off_the_shop_by_ref(candidate_ref)
        self.steps.gathering_mode_band_shows(shortlisted=1)

    def test_tdr_gth_45_at_most_five_shops_can_be_in_the_gathering(self) -> None:
        """**Fixed (1)**: this scenario's own "既に入れている5件はそのまま
        変わらない" (the already-in 5 remain unchanged, an exact-identity
        claim) was checked via shortlisted_shops_match while still on
        candidate-search-browser-interface.yaml's gatheringMode screen --
        gathering-shortlisted-shop-item is organizerDashboard's own
        exclusive test id (gathering-scheduling-browser-interface.yaml's
        shortlistedShopVotes section), never present there. Unlike
        TDR-GTH-44, this scenario's Then genuinely needs identity (not just
        the count gathering_mode_band_shows and unselected_candidate_toggle_
        is_disabled already give below) -- gatheringMode's own cardToggle
        carries no shopId-to-card DOM correlation, so identity can only be
        read back from the dashboard, the one screen this contract exposes
        it on.

        **Fixed (2, found while fixing (1))**: the Given used to shortlist 5
        shops through a *separate* setShortlistedShops-via-API call, built
        from open_shop_ids_for_the_confirmed_date's own independent
        proposeCandidates draw, then separately opened shopSelectionEntry --
        a *second*, unrelated proposeCandidates draw from the same 6-shop
        population. Whether that second draw happened to render a
        not-yet-shortlisted (data-gathering-shortlisted="false") card at all
        was therefore incidental, not guaranteed -- reproduced empirically
        failing roughly 2 of 3 runs with no such element found. Shortlisting
        the 5 through this same screen's own cardToggle instead (matching
        TDR-GTH-26/44's technique) removes the second independent draw
        entirely; search_again_on_shop_selection_entry's own shown-pool-
        priority technique (adr/0052 decision 3) then deterministically
        surfaces the confirmed date's one not-yet-shortlisted 6th shop for
        unselected_candidate_toggle_is_disabled to check.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会45", [thursday])
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_opens_shop_selection_entry()
        self.steps.gathering_mode_band_shows(shortlisted=0)
        selected = self.steps.organizer_selects_first_n_candidates_into_gathering(5)
        self.steps.gathering_mode_band_shows(shortlisted=5)
        self.steps.organizer_searches_again_on_shop_selection_entry()
        self.steps.unselected_candidate_toggle_is_disabled()
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shops_match(selected)

    # TDR-GTH-48 (new, adr/0050 decision 4, 2026-09-08〜09 human decision:
    # 会を削除できるようにする) -------------------------------------------

    def test_tdr_gth_48_organizer_deletes_the_gathering(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会48", [self.dsl.days_from_now_iso(3)])
        gathering_id = self.dsl.gathering_id
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_deletes_the_gathering()
        self.steps.gathering_is_absent_from_the_list(gathering_id)
        self.steps.participant_opens_the_link(link)
        self.steps.participant_sees_link_error("LINK_NOT_FOUND")

    # TDR-GTH-49 through TDR-GTH-55 (new, 2026-09-13, ADR-0054/0055/0056,
    # contracts/REVISION-PLAN.md 5節) ---------------------------------------

    def test_tdr_gth_49_organizer_sees_each_participants_per_date_responses(self) -> None:
        """新規（2026-09-13、ADR-0056決定1、人間裁定「誰が・どの候補日に・
        何と答えたかを幹事に見せる」）。organizerDashboard.responseTable
        joins participantLinkList's own per-link identity with
        candidateDateList's own per-date aggregate for the first time (this
        contract's own header-comment note on the gap this closes) --
        constructs two participant links through the public boundary
        (adr/0037 decision 1).

        **是正済み（2026-09-13、欠陥注入で判明: ある参加者の行の中で候補日
        セルどうしの答えを入れ替える欠陥が緑のまま通った）**: 元の Given は
        リンク2本がそれぞれ別の候補日に1つずつ答えるだけだったため、どの行
        にもセルが1つしかなく、行内のセル入れ替えで何も変わらなかった
        （assert_response_table_matches 自体は link-id -> {date-id: status}
        の完全一致比較で正しい。薄かったのは Given のほう）。link_one を
        candidate_date_a・candidate_date_b の両方に別々の答えで応じさせ、
        1つの行に2セルを持たせることで、行内のセル入れ替えが完全一致比較で
        必ず落ちるようにする。link_two は candidate_date_b だけに答え、
        candidate_date_a は未回答のまま残すことで、per-cell correlation
        （本来の主眼）に加えて「未回答の候補日はセルごと不在」という契約の
        形も引き続き検査する。
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会49", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
        )
        candidate_date_a = self.dsl.candidate_date_id_at(0)
        candidate_date_b = self.dsl.candidate_date_id_at(1)
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_the_candidate_date(candidate_date_a, "GOING")
        self.steps.participant_answers_the_candidate_date(candidate_date_b, "NOT_GOING")
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.participant_answers_the_candidate_date(candidate_date_b, "MAYBE")
        self.steps.organizer_opens_the_dashboard()
        link_ids = self.steps.participant_link_ids_in_order()
        self.steps.response_table_matches(
            {
                link_ids[0]: {candidate_date_a: "GOING", candidate_date_b: "NOT_GOING"},
                link_ids[1]: {candidate_date_b: "MAYBE"},
            }
        )
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_50_organizer_removes_a_candidate_date(self) -> None:
        """新規（2026-09-13、ADR-0056決定2、人間裁定「候補日を足せるが取り
        除けないのは片手落ち」）。
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会50", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
        )
        self.steps.organizer_opens_the_dashboard()
        candidate_date_id = self.dsl.candidate_date_id_at(1)
        self.steps.organizer_removes_the_candidate_date(candidate_date_id)
        self.steps.candidate_date_is_absent(candidate_date_id)
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_51_confirmed_candidate_date_cannot_be_removed(self) -> None:
        """新規（2026-09-13、ADR-0056決定2）。**是正済み（2026-09-13、
        gathering-scheduling-api.yaml v0.13.0 追補10 / gathering-scheduling-
        browser-interface.yaml 0.17.0 追補14, commit 4c99644）**: この
        シナリオが元々期待していたCANDIDATE_DATE_CONFIRMEDは、確定した候補日を
        狙ったremoveCandidateDateが常に先にGATHERING_NOT_IN_SCHEDULING_PHASE
        で拒否される（確定は同じ操作でphaseをSCHEDULINGから進める）ため、公開
        APIから到達不能として廃止されたコードだった。GATHERING_NOT_IN_
        SCHEDULING_PHASEへ検査を差し替え、あわせて観測面0.18.0の
        removeCandidateDate.presenceRule（確定後の局面では削除の操作そのもの
        が不在）もダッシュボードUI側で検査する -- 元のAPI直叩き検査
        （TDR-GTH-20/47と同じ、不到達なUI制御を迂回してサーバ自身の強制を
        証明する技法）はGATHERING_NOT_IN_SCHEDULING_PHASEの検証としてそのまま
        残す。
        """
        self._sign_in()
        confirmed_id = self.steps.organizer_has_a_selecting_shop_gathering(
            "会51", [self.dsl.days_from_now_iso(3)]
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.remove_candidate_date_control_is_absent(confirmed_id)
        response = self.steps.organizer_attempts_to_remove_candidate_date_via_api(confirmed_id)
        self.steps.remove_candidate_date_is_rejected_because_not_in_scheduling_phase(response)

    def test_tdr_gth_52_participant_sees_the_decided_shops_location_after_finalize(self) -> None:
        """新規（2026-09-13、ADR-0056決定10）。API変更は不要（LiveProjectedShop
        は既にname/location/walkingTimeMinutes/providerPageUrlを持つ）——足り
        なかったのはブラウザ契約の観測面だけ、というarchitectの申し送りどおり、
        既存のgetParticipantViewの値と突き合わせるだけで検査できる。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会52", [thursday])
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        link = self.steps.a_participant_link_is_issued()
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_finalizes_via_dashboard()
        self.steps.participant_opens_the_link(link)
        decision_shop = self.steps.participant_view_via_api(link)["decision"]["shop"]
        self.steps.participant_decision_shows_shop_location_details(
            shop_id=shop_a,
            walking_time_minutes=decision_shop["walkingTimeMinutes"],
            provider_page_url=decision_shop["providerPageUrl"],
        )
        self.steps.participant_decision_map_shows_shop_and_origin_only()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_53_organizer_sees_a_confirmation_before_finalizing(self) -> None:
        """新規（2026-09-13、ADR-0054決定5・ADR-0056決定11、人間裁定「確定操作
        にも削除と対称な確認の一段を置く」）。開く→キャンセル→開き直す→確定、
        の順で通し、キャンセルが確定を呼ばず選択状態を保つこと
        （finalizeCancel.requiredOutcome）も合わせて確かめる。

        **書き換え済み（2026-09-17、ADR-0062決定3、人間裁定「日時とお店が
        あればいい。参加者は書かなくていい」、contracts/gathering-scheduling.
        feature TDR-GTH-53改）**: 3行の変化前後表（changesTable）を検査して
        いた finalize_confirm_dialog_shows_changes_summary を、日時・お店の
        2要素だけを検査する finalize_confirm_dialog_shows_date_and_shop へ
        置き換えた——確定の確認は日時とお店の2つだけであることを、期待値
        （確定済み候補日のISO・確定しようとしている店のshopId/name）と
        突き合わせて確かめる。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会53", [thursday])
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        confirmed_date_iso = self.dsl.gathering["candidateDates"][0]["startAt"]
        shop_a_name = next(
            shop["name"]
            for shop in self.dsl.gathering["shortlistedShops"]
            if shop["shopId"] == shop_a
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_opens_finalize_confirmation()
        self.steps.gathering_phase_is("SELECTING_SHOP")
        self.steps.finalize_confirm_dialog_shows_date_and_shop(
            confirmed_candidate_date=confirmed_date_iso, shop_id=shop_a, shop_name=shop_a_name
        )
        self.steps.organizer_cancels_finalize_confirmation()
        self.steps.gathering_phase_is("SELECTING_SHOP")
        self.steps.organizer_opens_finalize_confirmation()
        self.steps.organizer_confirms_finalize()
        self.steps.gathering_phase_is("FINALIZED")

    def test_tdr_gth_54_no_shop_leads_before_any_vote_is_cast(self) -> None:
        """新規（2026-09-13、ADR-0055決定6、人間裁定「票を入れた瞬間に嘘の
        最有力が出る」）。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会54", [thursday])
        shops = self.steps.open_shop_ids_for_the_confirmed_date()[:2]
        self.steps.organizer_shortlists_shops_via_api(shops)
        self.steps.organizer_opens_the_dashboard()
        self.steps.no_shortlisted_shop_is_the_current_leader()

    def test_tdr_gth_55_a_tie_for_the_top_vote_marks_every_tied_shop_as_leading(self) -> None:
        """新規（2026-09-13、ADR-0055決定6）。shop_tied_a/shop_tied_bを
        wantToGoCount+okToGoCount=2で同点に、shop_behindを0にそろえ、偶然の
        同点ではなく作為的な同点であることを保証する。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会55", [thursday])
        shop_tied_a, shop_tied_b, shop_behind = self.steps.open_shop_ids_for_the_confirmed_date()[
            :3
        ]
        self.steps.organizer_shortlists_shops_via_api([shop_tied_a, shop_tied_b, shop_behind])
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_shop_votes(
            {shop_tied_a: "WANT_TO_GO", shop_tied_b: "OK_TO_GO", shop_behind: "NOT_GOING"}
        )
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.participant_answers_shop_votes(
            {shop_tied_a: "WANT_TO_GO", shop_tied_b: "OK_TO_GO", shop_behind: "NOT_GOING"}
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.shortlisted_shop_current_leaders_are({shop_tied_a, shop_tied_b})

    def test_tdr_gth_56_shop_vote_bar_is_sized_against_total_active_participants(
        self,
    ) -> None:
        """新規（2026-09-13、gathering-scheduling-browser-interface.yaml
        0.15.0 追補12、ADR-0056決定9、人間裁定「票の帯は全員の人数で固定
        する」）。「発行され取り消されていない参加者リンクの本数」(n) を
        「発行した本数」と食い違わせるため、3本発行したうち1本を未回答の
        まま取り消す -- data-total-active-participant-countがn=2（3では
        ない）に一致し、その店にまだ票が集まっていなくても値が変わらない
        ことを確かめる。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会56", [thursday])
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        link_a = self.steps.a_participant_link_is_issued()
        self.steps.a_participant_link_is_issued()
        self.steps.a_participant_link_is_issued()
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_revokes_the_link_at(2)
        self.steps.participant_opens_the_link(link_a)
        self.steps.shop_vote_tally_total_active_participant_count_is(shop_a, 2)

    def test_tdr_gth_65_organizer_sees_the_decided_shops_location_after_finalize(self) -> None:
        """新規（2026-09-17、ADR-0062決定4、人間裁定「地図は画面いっぱい、店を
        選び中と同じ骨組み」、TDR-GTH-52の幹事版）。API変更は不要
        （Gathering.shortlistedShopsは既にname/location/walkingTimeMinutes/
        providerPageUrlを持つ）——足りなかったのはブラウザ契約の観測面
        （finalizedSummary.decisionBanner自身のmap/providerPageLink）だけ。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会65", [thursday])
        shop_a = self.steps.open_shop_ids_for_the_confirmed_date()[0]
        self.steps.organizer_shortlists_shops_via_api([shop_a])
        confirmed_date_iso = self.dsl.gathering["candidateDates"][0]["startAt"]
        shop_a_data = next(
            shop for shop in self.dsl.gathering["shortlistedShops"] if shop["shopId"] == shop_a
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_finalizes_via_dashboard()
        self.steps.organizer_decision_shows_decided_shop(
            confirmed_candidate_date=confirmed_date_iso,
            shop_id=shop_a,
            shop_name=shop_a_data["name"],
            provider_page_url=shop_a_data["providerPageUrl"],
        )
        self.steps.organizer_decision_map_shows_shop_and_origin_only()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    def test_tdr_gth_66_organizer_sees_only_the_decided_shop_after_finalize(self) -> None:
        """新規（2026-09-17、ADR-0062決定4、人間裁定「決まった店と集まる場所
        だけ」、TDR-GTH-34の幹事版）。確定前に投票にかけていた他の店
        （shop_b、確定でも投票でも一度も選ばれない）を残したまま確定し、
        確定後は決まった店（shop_a）の名前・場所だけが示され、
        gathering-shortlisted-shop-list/-item（旧「票の記録」パネル）が
        丸ごと不在になることを確かめる——finalized_controls_are_absent
        （ADR-0062決定4でこのリストの absence を追加済み）を再利用する。
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = self.dsl.next_weekday_iso(3)
        self.steps.organizer_has_a_selecting_shop_gathering("会66", [thursday])
        shop_a, shop_b = self.steps.open_shop_ids_for_the_confirmed_date()[:2]
        self.steps.organizer_shortlists_shops_via_api([shop_a, shop_b])
        confirmed_date_iso = self.dsl.gathering["candidateDates"][0]["startAt"]
        shop_a_data = next(
            shop for shop in self.dsl.gathering["shortlistedShops"] if shop["shopId"] == shop_a
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.organizer_selects_a_shop_for_finalize(shop_a)
        self.steps.organizer_finalizes_via_dashboard()
        self.steps.organizer_decision_shows_decided_shop(
            confirmed_candidate_date=confirmed_date_iso,
            shop_id=shop_a,
            shop_name=shop_a_data["name"],
            provider_page_url=shop_a_data["providerPageUrl"],
        )
        self.steps.finalized_controls_are_absent()
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    # TDR-GTH-64 (new, ADR-0061決定2, 2026-09-17人間裁定「束Cレイアウト案F2
    # 『空いた所にだれが何と答えたかを名前つきで並べる』」) ------------------

    def test_tdr_gth_64_participant_sees_other_respondents_names_and_answers(self) -> None:
        """respondentList (ADR-0061決定2): これまでは候補日ごとの人数の内訳
        だけだった参加者どうしの可視性を、幹事にはすでに開いている個人単位の
        可視性（ADR-0056決定1）と同じ深さまで広げる。名前を付けた参加者は
        その名前と回答が、名乗らなかった参加者は名無しとその回答が示される
        -- 可視文字列そのものの一致は求めない契約なので（TDR-GTH-16と同じ
        「名無しを含む」区別可能性の扱い）、data-participant-named/
        data-response-value の対応だけを検査する。
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering("会64", [self.dsl.next_weekday_iso(3)])
        candidate_date_id = self.dsl.candidate_date_id_at(0)
        named_link_a = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(named_link_a)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "GOING")
        self.steps.participant_attaches_a_display_name("あおい")
        named_link_b = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(named_link_b)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "MAYBE")
        self.steps.participant_attaches_a_display_name("そら")
        anonymous_link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(anonymous_link)
        self.steps.participant_answers_the_candidate_date(candidate_date_id, "NOT_GOING")
        viewer_link = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(viewer_link)
        self.steps.schedule_question_respondents_are(
            candidate_date_id,
            [
                {"response": "GOING", "named": True},
                {"response": "MAYBE", "named": True},
                {"response": "NOT_GOING", "named": False},
            ],
        )
        self.steps.screen_has_no_forbidden_controls_or_disclosures()

    # TDR-GTH-57/58 (new, ADR-0060 decision 1/2/4, 2026-09-16 human decision:
    # 平日ランチの会には土日・祝日は不要). Both bypass organizerGatheringCreate's
    # calendar the same way TDR-GTH-47 does -- a weekend/holiday day cell
    # carries the native disabled state and can never itself be clicked, so
    # the server-side rejection is exercised directly (the contract's own
    # "authoritative enforcement" framing for CANDIDATE_DATE_NOT_A_BUSINESS_DAY,
    # ADR-0060 decision 4). self.dsl.next_weekday_iso(5)/next_fixed_public_
    # holiday_on_weekday_iso compute a real Saturday/holiday date from actual calendar
    # time -- no server-clock faking, the same technique TDR-GTH-47 already
    # uses for "today".

    def test_tdr_gth_57_a_weekend_date_cannot_be_a_candidate_date(self) -> None:
        self._sign_in()
        self.steps.organizer_opens_the_gathering_create_screen()
        title = "会57"
        saturday_iso = self.dsl.next_weekday_iso(5)
        response = (
            self.steps.organizer_attempts_to_create_gathering_via_api_with_a_weekend_candidate_date(
                title, saturday_iso
            )
        )
        self.steps.create_is_rejected_because_date_is_not_a_business_day(response)
        self.steps.no_gathering_exists_with_title(title)

    def test_tdr_gth_58_a_public_holiday_date_cannot_be_a_candidate_date(self) -> None:
        self._sign_in()
        self.steps.organizer_opens_the_gathering_create_screen()
        title = "会58"
        holiday_iso = next_fixed_public_holiday_on_weekday_iso()
        response = (
            self.steps.organizer_attempts_to_create_gathering_via_api_with_a_holiday_candidate_date(
                title, holiday_iso
            )
        )
        self.steps.create_is_rejected_because_date_is_not_a_business_day(response)
        self.steps.no_gathering_exists_with_title(title)

    # TDR-GTH-59..62 (new, ADR-0060 decision 7, 2026-09-16 human decision:
    # "○が多い日を優先。同票なら△が多いほう。それでも同票ならすべてつける").
    # candidateDateList.candidateDate's data-current-leader -- TDR-GTH-54/55's
    # own shop-side precedent, applied to candidate dates with the two-level
    # goingCount-then-maybeCount cascade ADR-0060 decision 7 defines (distinct
    # from the shop side's single summed value).

    def test_tdr_gth_59_no_candidate_date_leads_before_any_answer_is_given(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会59", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
        )
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_current_leaders_are(set())

    def test_tdr_gth_60_the_candidate_date_with_the_most_going_answers_leads(self) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会60", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
        )
        leading_date = self.dsl.candidate_date_id_at(0)
        behind_date = self.dsl.candidate_date_id_at(1)
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_the_candidate_date(leading_date, "GOING")
        self.steps.participant_answers_the_candidate_date(behind_date, "GOING")
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.participant_answers_the_candidate_date(leading_date, "GOING")
        self.steps.participant_answers_the_candidate_date(behind_date, "MAYBE")
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_current_leaders_are({leading_date})

    def test_tdr_gth_61_a_going_tie_is_broken_by_the_maybe_count(self) -> None:
        """TDR-GTH-61: leading_date and behind_date both collect goingCount=1
        (an intentional tie, not incidental), so only maybeCount -- an
        additional MAYBE answer on leading_date alone -- can distinguish them.
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会61", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
        )
        leading_date = self.dsl.candidate_date_id_at(0)
        behind_date = self.dsl.candidate_date_id_at(1)
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_the_candidate_date(leading_date, "GOING")
        self.steps.participant_answers_the_candidate_date(behind_date, "GOING")
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.participant_answers_the_candidate_date(leading_date, "MAYBE")
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_current_leaders_are({leading_date})

    def test_tdr_gth_62_a_tie_on_both_going_and_maybe_marks_every_tied_date_as_leading(
        self,
    ) -> None:
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会62", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
        )
        tied_a = self.dsl.candidate_date_id_at(0)
        tied_b = self.dsl.candidate_date_id_at(1)
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_the_candidate_date(tied_a, "GOING")
        self.steps.participant_answers_the_candidate_date(tied_b, "GOING")
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.participant_answers_the_candidate_date(tied_a, "MAYBE")
        self.steps.participant_answers_the_candidate_date(tied_b, "MAYBE")
        self.steps.organizer_opens_the_dashboard()
        self.steps.candidate_date_current_leaders_are({tied_a, tied_b})

    def test_tdr_gth_63_participant_also_sees_the_leading_candidate_date(self) -> None:
        """TDR-GTH-63 (new, ADR-0060 decision 8): scheduleQuestion.tally's
        data-current-leader mirrors the organizer-facing value exactly, for a
        participant who has not answered either candidate date yet (TDR-GTH-12
        precedent: the participant sees others' answers before their own).
        """
        self._sign_in()
        self.steps.organizer_has_a_scheduling_gathering(
            "会63", [self.dsl.days_from_now_iso(3), self.dsl.days_from_now_iso(10)]
        )
        leading_date = self.dsl.candidate_date_id_at(0)
        behind_date = self.dsl.candidate_date_id_at(1)
        link_one = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_one)
        self.steps.participant_answers_the_candidate_date(leading_date, "GOING")
        self.steps.participant_answers_the_candidate_date(behind_date, "MAYBE")
        link_two = self.steps.a_participant_link_is_issued()
        self.steps.participant_opens_the_link(link_two)
        self.steps.schedule_question_current_leader_is(leading_date, True)
        self.steps.schedule_question_current_leader_is(behind_date, False)
