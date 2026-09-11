"""JS-capable browser L4 runner for the current TDR-CS scenarios."""

from __future__ import annotations

import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from tests.acceptance.dsl.candidate_search_browser import (
    CandidateSearchBrowserDsl,
    next_weekday_iso,
)
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
        self.steps.lunch_candidates_can_be_proposed_at_a_known_search_origin()
        self.steps.organizer_opens_candidate_proposal_screen()
        self.steps.default_filters_and_nearest_candidates_are_shown()
        self.steps.initial_display_requests_no_filter_input()
        self.steps.initial_candidates_have_no_duplicate_shop()
        self.steps.search_origin_marker_is_shown()
        self.steps.search_range_value_is_not_shown()
        self.steps.source_display_and_detail_link_are_shown()

    def test_tdr_cs_02_compare_candidates_on_cards_and_map(self) -> None:
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed_at_a_known_search_origin()
        self.steps.organizer_has_filtered_candidates()
        self.steps.current_candidates_are_in_cards_and_map()
        self.steps.render_mode_test_ids_are_mutually_exclusive()
        self.steps.selecting_a_card_highlights_its_marker()
        self.steps.selecting_a_marker_highlights_its_card()
        self.steps.map_shows_displayed_candidates_and_attribution()
        self.steps.map_shows_search_origin_marker_and_walking_radius_rings()
        self.steps.walking_radius_rings_show_each_bands_minutes()
        self.steps.cards_show_required_shop_fields()
        self.steps.walking_time_is_shown_as_an_estimate()
        self.steps.organizer_opens_filter_panel()
        self.steps.dinner_budget_reference_is_disclosed_once_on_screen()
        self.steps.walking_route_and_current_location_are_not_shown()
        self.steps.search_range_value_is_not_shown()

    def test_tdr_cs_02_desktop_two_column_layout_shows_every_candidate_without_paging(
        self,
    ) -> None:
        """TDR-CS-02のUI実装詳細 (adr/0049 決定4、2026-09-08 人間裁定「微妙。右に地図で一覧左
        とかじゃなかったっけ」): デスクトップ幅ではtwoColumnLayoutが成立し、最大5件のカードが
        送りボタンなしで一覧として同時にすべて見える。renderModes.twoColumnLayoutは専有の
        test idを持たない（空配列、adr/0049決定4）ため、mapPrimaryTouchLayout側の swipe-
        surface/position が両方とも不在であることの消去法で成立を確認する
        (renderModes.invariantのvacuous/non-vacuousな扱い、
        assert_render_mode_test_ids_are_mutually_exclusiveの docstring 参照)。デッキの送り
        ボタン（candidate-deck-previous/-next）とそのpurposeはcontractVersion 1.8.0
        (adr/0049決定4) で退役しており、この画面には一切存在しない
        (unavailableControls.allowedPurposesの1:1突き合わせが別途保証する)。地図上のピンを
        選ぶとカードが選択状態になること (selectMarker.deckVisibility) はtwoColumnLayoutでは
        「窓が無いので自明に満たされる」("trivially satisfied") と契約が明記しており、この
        固定ビューポートでも成立することを確認する。renderModes.verificationAllocation.L4
        のとおり、幅ごとの正しさそのものはADR-0032/L5の管轄で、ここでは扱わない。
        """
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed_at_a_known_search_origin()
        self.steps.organizer_compares_candidates_at_two_column_viewport()
        self.steps.two_column_layout_holds()
        self.steps.render_mode_test_ids_are_mutually_exclusive()
        self.steps.all_cards_visible_without_paging()
        self.steps.selecting_a_marker_highlights_its_card()
        self.steps.no_location_range_or_manual_order_control_exists()

    def test_tdr_cs_02_mobile_deck_navigation_swipes_candidates_without_changing_them(
        self,
    ) -> None:
        """TDR-CS-02のUI実装詳細 (adr/0033): モバイル幅の地図主役レイアウトでは、指のスワイプが
        デッキの表示窓を動かすだけで、カード集合・選択・適用済み/pending絞り込み条件のいずれも
        変えない。デスクトップ版 (test_tdr_cs_02_desktop_deck_navigation_...) と対をなす、
        mapPrimaryTouchLayout側の検査。renderModes.verificationAllocation.L4 のとおり、この
        テストは単一の固定ビューポート（MOBILE_MAP_PRIMARY_TOUCH_VIEWPORT）で
        mapPrimaryTouchLayoutが成立する前提のもとで動く。pageDeckSwipeForward/Backwardの
        boundaryOvershootは、先に反対方向の到達点まで実際に送って正のコントロールを取ってから
        でなければ検査できない設計にしてある（meta/adr/0065; 送りが一度も届かない場合との
        取り違えを防ぐ） -- 各境界検査の直前に、その方向の「until」ヘルパーを必ず経由する。

        限界: dispatch_deck_swipeが送るのは合成のポインタイベント列であり、実機で人間の指が
        この範囲を実際につまんでスワイプできることまでは証明しない
        (adr/0033 決定4; activeContext.md G1と同種、ドラッグ操作へ初めて広げた限界)。
        """
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed_at_a_known_search_origin()
        self.steps.organizer_compares_candidates_at_map_primary_touch_viewport()
        self.steps.map_primary_touch_layout_holds()
        self.steps.render_mode_test_ids_are_mutually_exclusive()
        self.steps.deck_position_counter_is_well_formed()
        self.steps.organizer_swipes_the_deck_forward_until_it_reaches_the_end()
        self.steps.deck_swipe_forward_is_a_no_op_at_the_boundary()
        self.steps.organizer_swipes_the_deck_backward_until_it_reaches_the_start()
        self.steps.deck_swipe_backward_is_a_no_op_at_the_boundary()
        self.steps.selecting_a_marker_outside_the_deck_window_brings_its_card_into_view()

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
        self.steps.selecting_no_results_guidance_opens_the_filter_panel()

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
        self.steps.organizer_opens_filter_panel()
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

    # TDR-CS-17/18/19 (new, 2026-09-08, ADR-0049 decision 1. 店選びはランチ
    # 候補画面に一本化する -- gathering-scheduling.featureのTDR-GTH-44/45と
    # 対を成す、この画面から見た同じ業務規則) -----------------------------

    def test_tdr_cs_17_organizer_toggles_a_shop_into_and_out_of_the_gathering(self) -> None:
        """**Fixed**: toggling off the *only* shortlisted shop made the WHEN
        step attempt to empty the shortlist entirely -- gathering-scheduling-
        api.yaml's SetShortlistedShopsRequest.shopIds carries `minItems: 1`,
        so the server correctly rejected it with 400 INVALID_SHOP_SELECTION,
        leaving the toggle's own attribute and the band both unchanged
        (reproduced empirically: the click fired but data-gathering-
        shortlisted stayed "true" and the band count stayed 1 even after
        waiting). This scenario's own assertions are about the one specific
        shop's own toggle-in/toggle-out outcome, not about the shortlist
        becoming empty overall, so selecting 2 before toggling one back off
        (leaving 1, never 0) tests the identical business behavior without
        colliding with this orthogonal Must -- mirrors gathering_scheduling_
        browser.py's own identical fix for this same gatheringMode screen's
        TDR-GTH-44.
        """
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed()
        gathering_id = self.steps.organizer_has_a_selecting_shop_gathering("会CS17")
        self.steps.organizer_opens_this_screen_in_gathering_mode(gathering_id)
        self.steps.gathering_mode_band_shows(shortlisted=0)
        self.steps.organizer_adds_a_candidate_to_the_gathering()
        self.steps.gathering_mode_band_shows(shortlisted=1)
        self.steps.organizer_adds_a_candidate_to_the_gathering()
        self.steps.gathering_mode_band_shows(shortlisted=2)
        self.steps.organizer_removes_the_shop_from_the_gathering()
        self.steps.gathering_mode_band_shows(shortlisted=1)
        # FR-030's repeated lesson: gatheringMode is a new screen state this
        # cross-cutting check must be exercised against.
        self.steps.no_location_range_or_manual_order_control_exists()

    def test_tdr_cs_18_gathering_mode_narrows_candidates_to_the_confirmed_dates_open_shops(
        self,
    ) -> None:
        self._sign_in()
        self.steps.lunch_candidates_can_be_proposed()
        gathering_id = self.steps.organizer_has_a_selecting_shop_gathering("会CS18")
        self.steps.organizer_opens_this_screen_in_gathering_mode(gathering_id)
        self.steps.gathering_mode_candidates_are_within_the_open_shop_population(gathering_id)

    def test_tdr_cs_19_at_most_five_shops_can_be_in_the_gathering(self) -> None:
        """**Fixed**: this Given previously used lunch_candidates_can_be_
        proposed (NORMAL_WITH_WEIGHTED_SAMPLING, >=40 synthetic candidates).
        candidate-search-api.yaml's own 5-item display cap means any single
        proposeCandidates response can render at most 5 cards; toggling all
        5 of them in (the only ones ever shown) leaves no not-yet-
        shortlisted card on screen at all to assert disabled, and reopening
        this large a population never re-shows an already-shortlisted card
        either (shownPoolPriority guarantees a fresh, wholly disjoint 5 while
        the not-yet-shown remainder stays far above the cap) -- reproduced
        empirically: "no [data-gathering-shortlisted=false] element found".
        test-support-api.yaml's own 2026-09-09 header addendum names
        GATHERING_OPEN_SHOP_WEEKDAY_MATCH as this scenario's intended Given
        for exactly this reason -- its Thursday population is exactly 6 open
        shops (OPEN_SHOP_COUNT_BY_WEEKDAY), so after 5 are shortlisted
        through this screen's own cardToggle, a search-again replay's
        shownPoolPriority is guaranteed to surface the 1 not-yet-shown spare
        (disabled, count>=5) alongside 4 repeats of the already-shortlisted
        ones (still enabled) -- mirroring gathering-scheduling.feature's own
        TDR-GTH-45 technique for this identical requirement on this same
        gatheringMode screen.
        """
        self._sign_in()
        self.steps.gathering_open_shop_population_is_available()
        thursday = next_weekday_iso(3)
        gathering_id = self.steps.organizer_has_a_selecting_shop_gathering("会CS19", thursday)
        self.steps.organizer_opens_this_screen_in_gathering_mode(gathering_id)
        for _ in range(5):
            self.steps.organizer_adds_a_candidate_to_the_gathering()
        self.steps.gathering_mode_band_shows(shortlisted=5)
        self.steps.organizer_searches_again_on_shop_selection_entry()
        self.steps.unselected_candidate_toggle_is_disabled()
        # adr/0049 決定8 後段: 既に選択済みのカードは5件到達後も外す操作として活性のまま
        self.steps.selected_candidate_toggle_is_enabled()
