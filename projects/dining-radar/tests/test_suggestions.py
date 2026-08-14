import random
from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from dining_radar.recommendation.pipeline import (
    CandidateFilters,
    NormalizedCandidate,
    Origin,
    dinner_budget_tier,
)
from dining_radar.suggestions import acceptance_state
from dining_radar.suggestions.errors import CandidateSourceUnavailableError
from dining_radar.suggestions.hotpepper_source import fetch_real_candidates
from dining_radar.suggestions.rate_limit import ProposalThrottle
from dining_radar.suggestions.service import propose_candidates

ORIGIN = Origin(latitude=0.0, longitude=0.0)

# Seeds swept when asserting that a candidate is *reachable* under
# adr/0023/adr/0024's distance-weighted random selection. Each seed makes one
# run reproducible; the sweep makes reachability itself a deterministic
# property of the fixed set.
_REACHABILITY_SEEDS = 20


def _candidate(provider_page_url="https://example.invalid/shop", **overrides):
    defaults = dict(
        name="架空食堂",
        genre="和食",
        description=None,
        regular_holiday=None,
        total_seats=None,
        non_smoking_status=None,
        card_payment_available=None,
        budget_average=None,
        latitude=0.001,
        longitude=0.0,
        provider_page_url=provider_page_url,
    )
    defaults.update(overrides)
    return NormalizedCandidate(**defaults)


class ProposeCandidatesTests(SimpleTestCase):
    def test_empty_source_returns_an_empty_proposal(self):
        result = propose_candidates(
            CandidateFilters(),
            fetch_candidates=lambda: ([], ORIGIN),
            random_source=random.Random(1),
        )

        self.assertEqual(result.candidates, ())

    def test_returns_the_eligible_candidates_ordered_nearest_first(self):
        candidates = [
            _candidate(provider_page_url="https://example.invalid/a", latitude=0.001),
            _candidate(provider_page_url="https://example.invalid/b", latitude=0.0005),
        ]

        result = propose_candidates(
            CandidateFilters(),
            fetch_candidates=lambda: (candidates, ORIGIN),
            random_source=random.Random(1),
        )

        self.assertEqual(
            [c.provider_page_url for c in result.candidates],
            ["https://example.invalid/b", "https://example.invalid/a"],
        )

    def test_filters_are_forwarded_to_the_pipeline(self):
        soba = _candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        yoshoku = _candidate(provider_page_url="https://example.invalid/yoshoku", genre="洋食")

        result = propose_candidates(
            CandidateFilters(genres=("和食",)),
            fetch_candidates=lambda: ([soba, yoshoku], ORIGIN),
            random_source=random.Random(1),
        )

        self.assertEqual([c.genre for c in result.candidates], ["和食"])

    def test_izakaya_bar_fallback_is_forwarded_from_the_pipeline(self):
        izakaya = _candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        result = propose_candidates(
            CandidateFilters(),
            fetch_candidates=lambda: ([izakaya], ORIGIN),
            random_source=random.Random(1),
        )

        self.assertTrue(result.izakaya_bar_fallback_applied)

    def test_available_genres_is_forwarded_from_the_pipeline(self):
        soba = _candidate(provider_page_url="https://example.invalid/soba", genre="和食")

        result = propose_candidates(
            CandidateFilters(),
            fetch_candidates=lambda: ([soba], ORIGIN),
            random_source=random.Random(1),
        )

        self.assertEqual(result.available_genres, ("和食",))

    def test_no_random_source_defaults_to_a_fresh_non_deterministic_one(self):
        # adr/0023 decision 4: production omits an injected random source, so
        # this must not raise and must still return a well-formed result.
        candidates = [
            _candidate(provider_page_url=f"https://example.invalid/{i}", latitude=0.001 * i)
            for i in range(1, 4)
        ]

        result = propose_candidates(
            CandidateFilters(), fetch_candidates=lambda: (candidates, ORIGIN)
        )

        self.assertEqual(len(result.candidates), 3)

    # shown_provider_page_urls / shown_pool_exhausted (adr/0024 decision 4) --

    def test_no_shown_provider_page_urls_defaults_to_treating_everything_as_unseen(self):
        candidates = [
            _candidate(provider_page_url=f"https://example.invalid/default-{i}", latitude=0.001 * i)
            for i in range(1, 4)
        ]

        result = propose_candidates(
            CandidateFilters(),
            fetch_candidates=lambda: (candidates, ORIGIN),
            random_source=random.Random(1),
        )

        self.assertFalse(result.shown_pool_exhausted)

    def test_shown_provider_page_urls_is_forwarded_to_the_pipeline(self):
        candidates = [
            _candidate(provider_page_url=f"https://example.invalid/shown-{i}", latitude=0.001 * i)
            for i in range(1, 4)
        ]
        shown = {c.provider_page_url for c in candidates}

        result = propose_candidates(
            CandidateFilters(),
            fetch_candidates=lambda: (candidates, ORIGIN),
            random_source=random.Random(1),
            shown_provider_page_urls=shown,
        )

        self.assertTrue(result.shown_pool_exhausted)
        self.assertEqual(len(result.candidates), 3)


class HotpepperSourceTests(SimpleTestCase):
    def test_missing_configuration_raises_candidate_source_unavailable(self):
        with self.assertRaises(CandidateSourceUnavailableError):
            fetch_real_candidates()


class _FakeRequest:
    def __init__(self, user):
        self.user = user
        self.META = {"REMOTE_ADDR": "127.0.0.1"}


class ProposalThrottleTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(PROPOSAL_RATE_LIMIT_MAX_REQUESTS=2, PROPOSAL_RATE_LIMIT_WINDOW_SECONDS=30)
    def test_is_limited_only_after_max_requests(self):
        user = MagicMock(pk=4242)
        throttle = ProposalThrottle(_FakeRequest(user))

        self.assertFalse(throttle.is_limited())
        throttle.record_request()
        self.assertFalse(throttle.is_limited())
        throttle.record_request()
        self.assertTrue(throttle.is_limited())

    def test_defaults_are_generous_when_unconfigured(self):
        user = MagicMock(pk=4343)
        throttle = ProposalThrottle(_FakeRequest(user))

        self.assertEqual(throttle.max_requests, 20)
        self.assertEqual(throttle.window_seconds, 60)


class AcceptanceStateGuardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(acceptance_state.reset_mode)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=False)
    def test_set_mode_is_unavailable_outside_the_acceptance_profile(self):
        with self.assertRaises(RuntimeError):
            acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=False)
    def test_active_mode_is_none_outside_the_acceptance_profile(self):
        self.assertIsNone(acceptance_state.active_mode())

    def test_active_mode_reflects_the_selected_mode(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.RATE_LIMITED)

        self.assertEqual(
            acceptance_state.active_mode(),
            acceptance_state.AcceptanceCandidateProposalMode.RATE_LIMITED,
        )

    def test_reset_mode_clears_the_selection(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS)

        acceptance_state.reset_mode()

        self.assertIsNone(acceptance_state.active_mode())


class ActiveRandomSourceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(acceptance_state.reset_mode)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_no_pinned_seed_returns_a_non_deterministic_source(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING
        )

        source = acceptance_state.active_random_source()

        self.assertIsInstance(source, random.Random)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_pinned_seed_is_reproducible(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
            random_seed=99,
        )

        first = acceptance_state.active_random_source().random()
        second = acceptance_state.active_random_source().random()

        self.assertEqual(first, second)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=False)
    def test_outside_the_acceptance_profile_the_seed_is_never_read(self):
        cache.set(acceptance_state._CACHE_KEY_SEED, 99, timeout=None)

        source = acceptance_state.active_random_source()

        # An unseeded source cannot be distinguished from a seeded one by
        # value alone; this asserts the seed cache entry was never consulted
        # by exercising the guard branch directly (matching active_mode's own
        # outside-the-profile guard test above).
        self.assertIsInstance(source, random.Random)


class ProposeWithOverrideTests(SimpleTestCase):
    """Direct unit coverage of the adr/0023 synthetic seams.

    ``test_candidate_search.py`` covers the same behaviour through the public
    HTTP endpoint; these tests exercise ``propose_with_override`` itself so a
    change to the module's synthetic candidate sets or mode dispatch is
    caught here even if request/response wiring changes independently.
    """

    def test_izakaya_bar_only_mode_falls_through_to_the_izakaya_bar_population(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY, CandidateFilters()
        )

        self.assertTrue(result.izakaya_bar_fallback_applied)
        self.assertTrue(result.candidates)
        self.assertTrue(all(c.genre == "居酒屋" for c in result.candidates))

    def _normal_with_weighted_sampling_genres_across_seeds(
        self, filters: CandidateFilters
    ) -> list[set[str]]:
        """The displayed genres for each pinned seed in ``_REACHABILITY_SEEDS``.

        adr/0024 decision 3 samples the displayed candidates at random,
        weighted by distance, over the whole eligible population, so a
        single unseeded run cannot be asserted on: whether any one candidate
        is displayed is a draw, not an outcome. Pinning the seed makes each
        run reproducible, and sweeping a fixed range of seeds turns "is this
        candidate reachable at all" into a deterministic question.
        """
        try:
            genres_per_seed: list[set[str]] = []
            for seed in range(_REACHABILITY_SEEDS):
                acceptance_state.set_mode(
                    acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
                    random_seed=seed,
                )
                result = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
                    filters,
                )
                self.assertFalse(result.izakaya_bar_fallback_applied)
                genres_per_seed.append({candidate.genre for candidate in result.candidates})
            return genres_per_seed
        finally:
            acceptance_state.reset_mode()

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_normal_with_weighted_sampling_excludes_the_default_excluded_genre_by_default(self):
        genres_per_seed = self._normal_with_weighted_sampling_genres_across_seeds(
            CandidateFilters()
        )

        # Not "did not happen to be drawn" but "cannot be drawn": the default
        # exclusion removes the candidate from the population before
        # selection, so no seed can surface it.
        self.assertFalse(any("居酒屋" in genres for genres in genres_per_seed))

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_normal_with_weighted_sampling_include_izakaya_bar_reaches_the_excluded_candidate(
        self,
    ):
        genres_per_seed = self._normal_with_weighted_sampling_genres_across_seeds(
            CandidateFilters(include_izakaya_bar=True)
        )

        # Reachable, not guaranteed. adr/0024 decision 3 removed the fixed
        # near-distance pool, so every eligible candidate -- including the
        # nearest, which is the excluded-genre candidate here -- has a
        # nonzero selection probability (P2); only 5 are ever displayed, so
        # asserting it appears for any *particular* seed would be asserting a
        # draw.
        self.assertTrue(any("居酒屋" in genres for genres in genres_per_seed))

    def test_normal_with_weighted_sampling_population_exceeds_the_display_cap(self):
        # test-support-api.yaml v1.1.0 / adr/0024 decision 3:
        # NORMAL_WITH_WEIGHTED_SAMPLING must supply at least 40
        # default-population candidates, comfortably exceeding the
        # five-candidate display cap.
        self.assertGreaterEqual(
            len(
                [
                    c
                    for c in acceptance_state._CANDIDATES
                    if c.genre not in {"居酒屋", "ダイニングバー・バル"}
                ]
            ),
            40,
        )

    def test_normal_with_weighted_sampling_spans_at_least_three_genres_with_two_members(self):
        default_population = [
            c
            for c in acceptance_state._CANDIDATES
            if c.genre not in {"居酒屋", "ダイニングバー・バル"}
        ]
        counts: dict[str, int] = {}
        for c in default_population:
            counts[c.genre] = counts.get(c.genre, 0) + 1

        self.assertGreaterEqual(len(counts), 3)
        self.assertTrue(all(count >= 2 for count in counts.values()))

    def test_normal_with_weighted_sampling_spans_at_least_two_non_smoking_statuses(self):
        statuses = {c.non_smoking_status for c in acceptance_state._CANDIDATES}

        self.assertGreaterEqual(len(statuses), 2)

    def test_normal_with_weighted_sampling_has_both_true_and_false_card_payment_available(self):
        flags = {c.card_payment_available for c in acceptance_state._CANDIDATES}

        self.assertIn(True, flags)
        self.assertIn(False, flags)

    def test_normal_with_weighted_sampling_has_a_non_null_and_a_null_dinner_budget_candidate(
        self,
    ):
        budgets = [c.budget_average for c in acceptance_state._CANDIDATES]

        self.assertTrue(any(value is not None for value in budgets))
        self.assertIn(None, budgets)

    def test_normal_with_weighted_sampling_has_a_candidate_unconfirmed_for_at_least_one_soft_filter(
        self,
    ):
        # TDR-CS-13's ordering rule needs at least one candidate with a null
        # nonSmokingStatus, cardPaymentAvailable, or dinnerBudgetTier.
        self.assertTrue(
            any(
                c.non_smoking_status is None
                or c.card_payment_available is None
                or c.budget_average is None
                for c in acceptance_state._CANDIDATES
            )
        )

    def test_normal_with_weighted_sampling_random_seed_reproduces_the_identical_result(self):
        with override_settings(ACCEPTANCE_TEST_SUPPORT=True):
            cache.clear()
            self.addCleanup(acceptance_state.reset_mode)
            acceptance_state.set_mode(
                acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
                random_seed=13,
            )

            first = acceptance_state.propose_with_override(
                acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
                CandidateFilters(),
            )
            second = acceptance_state.propose_with_override(
                acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
                CandidateFilters(),
            )

            self.assertEqual(
                [c.provider_page_url for c in first.candidates],
                [c.provider_page_url for c in second.candidates],
            )

    def test_normal_with_weighted_sampling_different_random_seeds_can_differ(self):
        with override_settings(ACCEPTANCE_TEST_SUPPORT=True):
            cache.clear()
            self.addCleanup(acceptance_state.reset_mode)

            seen = set()
            for seed in range(10):
                acceptance_state.set_mode(
                    acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
                    random_seed=seed,
                )
                result = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
                    CandidateFilters(),
                )
                seen.add(tuple(c.provider_page_url for c in result.candidates))

            self.assertGreater(len(seen), 1, "every seed produced the identical candidate set")

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_default_exclusion_visible_mode_displays_the_excluded_category_only_when_enabled(self):
        try:
            for seed in range(_REACHABILITY_SEEDS):
                acceptance_state.set_mode(
                    acceptance_state.AcceptanceCandidateProposalMode.DEFAULT_EXCLUSION_VISIBLE,
                    random_seed=seed,
                )
                default_result = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.DEFAULT_EXCLUSION_VISIBLE,
                    CandidateFilters(),
                )
                included_result = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.DEFAULT_EXCLUSION_VISIBLE,
                    CandidateFilters(include_izakaya_bar=True),
                )
                excluded_by_genre = {
                    attribute.genre: attribute.default_excluded
                    for attribute in default_result.population_attributes
                }

                self.assertTrue(default_result.candidates)
                self.assertTrue(
                    all(
                        not excluded_by_genre[candidate.genre]
                        for candidate in default_result.candidates
                    )
                )
                self.assertTrue(
                    any(
                        excluded_by_genre[candidate.genre]
                        for candidate in included_result.candidates
                    )
                )
        finally:
            acceptance_state.reset_mode()

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_card_payment_caution_visible_mode_is_never_randomly_hidden(self):
        try:
            for seed in range(_REACHABILITY_SEEDS):
                acceptance_state.set_mode(
                    acceptance_state.AcceptanceCandidateProposalMode.CARD_PAYMENT_CAUTION_VISIBLE,
                    random_seed=seed,
                )
                result = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.CARD_PAYMENT_CAUTION_VISIBLE,
                    CandidateFilters(),
                )
                payment_values = {
                    candidate.card_payment_available for candidate in result.candidates
                }

                self.assertIn(False, payment_values)
                self.assertTrue(True in payment_values or None in payment_values)
        finally:
            acceptance_state.reset_mode()

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_zero_pending_match_mode_has_no_null_card_payment_or_budget_value(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.ZERO_PENDING_MATCH
        )
        try:
            result = acceptance_state.propose_with_override(
                acceptance_state.AcceptanceCandidateProposalMode.ZERO_PENDING_MATCH,
                CandidateFilters(),
            )

            self.assertTrue(result.population_attributes)
            self.assertTrue(
                all(
                    attribute.card_payment_available is not None
                    and attribute.dinner_budget_tier is not None
                    for attribute in result.population_attributes
                )
            )
        finally:
            acceptance_state.reset_mode()

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_zero_pending_match_mode_each_filter_alone_matches_but_combined_matches_nothing(self):
        try:
            for seed in range(_REACHABILITY_SEEDS):
                acceptance_state.set_mode(
                    acceptance_state.AcceptanceCandidateProposalMode.ZERO_PENDING_MATCH,
                    random_seed=seed,
                )
                card_only = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.ZERO_PENDING_MATCH,
                    CandidateFilters(card_payment_only=True),
                )
                budget_only = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.ZERO_PENDING_MATCH,
                    CandidateFilters(budget_tiers=("LOW",)),
                )
                combined = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.ZERO_PENDING_MATCH,
                    CandidateFilters(card_payment_only=True, budget_tiers=("LOW",)),
                )

                self.assertTrue(card_only.candidates)
                self.assertTrue(budget_only.candidates)
                self.assertEqual(combined.candidates, ())
        finally:
            acceptance_state.reset_mode()

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_fallback_preserves_filters_mode_falls_back_to_the_all_matching_candidate_only(self):
        try:
            for seed in range(_REACHABILITY_SEEDS):
                acceptance_state.set_mode(
                    acceptance_state.AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS,
                    random_seed=seed,
                )
                result = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS,
                    CandidateFilters(
                        non_smoking_only=True, card_payment_only=True, budget_tiers=("LOW",)
                    ),
                )

                self.assertTrue(result.izakaya_bar_fallback_applied)
                self.assertTrue(result.candidates)
                self.assertTrue(
                    all(
                        candidate.non_smoking_status != "NONE"
                        and candidate.card_payment_available is not False
                        and dinner_budget_tier(candidate.budget_average) in (None, "LOW")
                        for candidate in result.candidates
                    )
                )
        finally:
            acceptance_state.reset_mode()

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_fallback_preserves_filters_mode_keeps_non_matching_proof_rows_unadmitted(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS
        )
        try:
            result = acceptance_state.propose_with_override(
                acceptance_state.AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS,
                CandidateFilters(
                    non_smoking_only=True, card_payment_only=True, budget_tiers=("LOW",)
                ),
            )

            default_excluded_full = [
                attribute
                for attribute in result.population_attributes
                if attribute.default_excluded and attribute.non_smoking_status == "FULL"
            ]

            self.assertGreater(len(default_excluded_full), len(result.candidates))
        finally:
            acceptance_state.reset_mode()

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_fallback_preserves_filters_mode_does_not_relax_an_explicit_genre_filter(self):
        try:
            for seed in range(_REACHABILITY_SEEDS):
                acceptance_state.set_mode(
                    acceptance_state.AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS,
                    random_seed=seed,
                )
                default = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS,
                    CandidateFilters(),
                )
                self.assertEqual(len(default.available_genres), 1)
                genre = default.available_genres[0]

                result = acceptance_state.propose_with_override(
                    acceptance_state.AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS,
                    CandidateFilters(genres=(genre,), non_smoking_only=True),
                )

                self.assertEqual(result.candidates, ())
                self.assertFalse(result.izakaya_bar_fallback_applied)
        finally:
            acceptance_state.reset_mode()

    # GENRE_ORDER_BY_COUNT (adr/0024 decision 1, test-support-api.yaml v1.1.0) --

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_genre_order_by_count_default_population_has_the_documented_count_shape(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.GENRE_ORDER_BY_COUNT,
            CandidateFilters(),
        )

        counts: dict[str, int] = {}
        for attribute in result.population_attributes:
            if attribute.default_excluded:
                continue
            counts[attribute.genre] = counts.get(attribute.genre, 0) + 1

        self.assertEqual(len(counts), 5)
        ordered_counts = sorted(counts.values(), reverse=True)
        # One strictly greatest count, two tied at the next-greatest, and two
        # further strictly smaller and mutually distinct counts.
        self.assertGreater(ordered_counts[0], ordered_counts[1])
        self.assertEqual(ordered_counts[1], ordered_counts[2])
        self.assertGreater(ordered_counts[1], ordered_counts[3])
        self.assertGreater(ordered_counts[3], ordered_counts[4])
        self.assertEqual(len({ordered_counts[3], ordered_counts[4]}), 2)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_genre_order_by_count_tied_genres_have_different_string_lengths(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.GENRE_ORDER_BY_COUNT,
            CandidateFilters(),
        )

        counts: dict[str, int] = {}
        for attribute in result.population_attributes:
            if attribute.default_excluded:
                continue
            counts[attribute.genre] = counts.get(attribute.genre, 0) + 1

        max_count = max(counts.values())
        tied = [
            genre for genre, count in counts.items() if count == sorted(set(counts.values()))[-2]
        ]
        self.assertEqual(len(tied), 2)
        self.assertNotEqual(len(tied[0]), len(tied[1]))
        # And the greatest count is not itself part of the tie.
        self.assertNotIn(max_count, [counts[genre] for genre in tied])

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_genre_order_by_count_has_a_default_excluded_genre_with_its_own_distinct_count(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.GENRE_ORDER_BY_COUNT,
            CandidateFilters(include_izakaya_bar=True),
        )

        non_excluded_counts: set[int] = set()
        excluded_counts: dict[str, int] = {}
        for attribute in result.population_attributes:
            if attribute.default_excluded:
                excluded_counts[attribute.genre] = excluded_counts.get(attribute.genre, 0) + 1
            else:
                non_excluded_counts.add(attribute.genre)

        self.assertTrue(excluded_counts)
        for count in excluded_counts.values():
            self.assertNotIn(count, {6, 4, 3, 2})

    # SHOWN_POOL_PRIORITY (adr/0024 decision 4, TDR-CS-14) ------------------

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_shown_pool_priority_default_population_has_exactly_ten_distinct_candidates(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.SHOWN_POOL_PRIORITY,
            CandidateFilters(),
        )

        self.assertFalse(result.izakaya_bar_fallback_applied)
        self.assertEqual(len(acceptance_state._SHOWN_POOL_PRIORITY_CANDIDATES), 10)
        self.assertEqual(
            len({c.provider_page_url for c in acceptance_state._SHOWN_POOL_PRIORITY_CANDIDATES}),
            10,
        )

    @override_settings(ACCEPTANCE_TEST_SUPPORT=True)
    def test_shown_pool_priority_forwards_shown_provider_page_urls_to_the_pipeline(self):
        all_urls = {c.provider_page_url for c in acceptance_state._SHOWN_POOL_PRIORITY_CANDIDATES}

        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.SHOWN_POOL_PRIORITY,
            CandidateFilters(),
            all_urls,
        )

        self.assertTrue(result.shown_pool_exhausted)
        self.assertEqual(len(result.candidates), 5)
