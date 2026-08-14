import random
from collections import Counter

from django.test import SimpleTestCase

from dining_radar.recommendation.pipeline import (
    DEFAULT_EXCLUDED_GENRES,
    DISPLAY_CAP,
    CandidateFilters,
    NormalizedCandidate,
    Origin,
    apply_izakaya_bar_fallback,
    available_genres,
    build_proposal,
    dinner_budget_tier,
    filter_candidates,
    order_confirmed_then_unconfirmed,
    partition_by_shown,
    population_attributes,
    select_pool_and_sample,
    select_with_shown_priority,
)

ORIGIN = Origin(latitude=0.0, longitude=0.0)


def candidate(
    *,
    name="架空食堂",
    genre="和食",
    provider_page_url="https://example.invalid/shop",
    latitude=0.001,
    longitude=0.0,
    total_seats=None,
    non_smoking_status=None,
    card_payment_available=None,
    budget_average=None,
    description="紹介文",
    regular_holiday="日曜",
):
    return NormalizedCandidate(
        name=name,
        genre=genre,
        description=description,
        regular_holiday=regular_holiday,
        total_seats=total_seats,
        non_smoking_status=non_smoking_status,
        card_payment_available=card_payment_available,
        budget_average=budget_average,
        latitude=latitude,
        longitude=longitude,
        provider_page_url=provider_page_url,
    )


class DinnerBudgetTierTests(SimpleTestCase):
    def test_null_budget_average_is_a_null_tier(self):
        self.assertIsNone(dinner_budget_tier(None))

    def test_two_thousand_yen_or_less_is_low(self):
        self.assertEqual(dinner_budget_tier(2000.0), "LOW")

    def test_two_thousand_one_to_four_thousand_yen_is_mid(self):
        self.assertEqual(dinner_budget_tier(2001.0), "MID")
        self.assertEqual(dinner_budget_tier(4000.0), "MID")

    def test_over_four_thousand_yen_is_high(self):
        self.assertEqual(dinner_budget_tier(4001.0), "HIGH")


class DefaultExcludedGenresTests(SimpleTestCase):
    def test_confirmed_excluded_genres_are_exactly_two(self):
        self.assertEqual(DEFAULT_EXCLUDED_GENRES, {"居酒屋", "ダイニングバー・バル"})


class AvailableGenresTests(SimpleTestCase):
    def test_returns_distinct_genres_sorted(self):
        candidates = [
            candidate(provider_page_url="https://example.invalid/a", genre="洋食"),
            candidate(provider_page_url="https://example.invalid/b", genre="和食"),
            candidate(provider_page_url="https://example.invalid/c", genre="和食"),
        ]

        self.assertEqual(available_genres(candidates, include_izakaya_bar=False), ["和食", "洋食"])

    def test_excludes_default_excluded_genres_when_izakaya_bar_not_included(self):
        candidates = [
            candidate(provider_page_url="https://example.invalid/a", genre="和食"),
            candidate(provider_page_url="https://example.invalid/b", genre="居酒屋"),
        ]

        self.assertEqual(available_genres(candidates, include_izakaya_bar=False), ["和食"])

    def test_includes_default_excluded_genres_when_izakaya_bar_included(self):
        candidates = [
            candidate(provider_page_url="https://example.invalid/a", genre="和食"),
            candidate(provider_page_url="https://example.invalid/b", genre="居酒屋"),
        ]

        self.assertEqual(available_genres(candidates, include_izakaya_bar=True), ["和食", "居酒屋"])

    def test_not_narrowed_by_any_other_filter(self):
        # adr/0023 decision 9: availableGenres reflects only includeIzakayaBar,
        # never the genres/nonSmokingOnly/cardPaymentOnly/budgetTiers filters
        # themselves -- this function does not even accept those, by design.
        candidates = [
            candidate(provider_page_url="https://example.invalid/a", genre="和食"),
            candidate(provider_page_url="https://example.invalid/b", genre="洋食"),
        ]

        self.assertEqual(available_genres(candidates, False), ["和食", "洋食"])


class PopulationAttributesTests(SimpleTestCase):
    def test_has_only_the_filter_membership_values_required_for_pending_counts(self):
        row = population_attributes(
            [
                candidate(
                    name="private name must not escape",
                    provider_page_url="https://example.invalid/private-id",
                    latitude=35.123,
                    longitude=139.456,
                    genre="western",
                    non_smoking_status="FULL",
                    card_payment_available=True,
                    budget_average=1500.0,
                )
            ]
        )[0]

        self.assertEqual(
            set(vars(row)),
            {
                "genre",
                "non_smoking_status",
                "card_payment_available",
                "dinner_budget_tier",
                "default_excluded",
            },
        )
        self.assertEqual(row.genre, "western")
        self.assertEqual(row.non_smoking_status, "FULL")
        self.assertIs(row.card_payment_available, True)
        self.assertEqual(row.dinner_budget_tier, "LOW")
        self.assertFalse(row.default_excluded)

    def test_order_is_independent_of_provider_source_order_and_candidate_distance(self):
        first_source_row = candidate(
            name="first provider result",
            provider_page_url="https://example.invalid/first",
            latitude=0.001,
            genre="western",
            non_smoking_status="FULL",
            card_payment_available=True,
            budget_average=5000.0,
        )
        second_source_row = candidate(
            name="second provider result",
            provider_page_url="https://example.invalid/second",
            latitude=9.0,
            genre="japanese",
            non_smoking_status=None,
            card_payment_available=False,
            budget_average=None,
        )

        in_source_order = population_attributes([first_source_row, second_source_row])
        in_reverse_source_order = population_attributes([second_source_row, first_source_row])

        self.assertEqual(in_source_order, in_reverse_source_order)
        self.assertEqual(
            [row.genre for row in in_source_order],
            ["japanese", "western"],
        )

    def test_canonical_order_uses_every_non_derived_public_filter_value(self):
        def rows_with(**first_overrides):
            defaults = {
                "genre": "same-genre",
                "non_smoking_status": "FULL",
                "card_payment_available": True,
                "budget_average": 1500.0,
            }
            defaults.update(first_overrides)
            first = candidate(
                provider_page_url="https://example.invalid/first",
                latitude=9.0,
                **defaults,
            )
            second = candidate(
                provider_page_url="https://example.invalid/second",
                latitude=0.001,
                genre="same-genre",
                non_smoking_status="FULL",
                card_payment_available=True,
                budget_average=1500.0,
            )
            return population_attributes([second, first])

        self.assertEqual(
            [row.non_smoking_status for row in rows_with(non_smoking_status="PARTIAL")],
            ["FULL", "PARTIAL"],
        )
        self.assertEqual(
            [row.non_smoking_status for row in rows_with(non_smoking_status=None)],
            ["FULL", None],
        )
        self.assertEqual(
            [row.card_payment_available for row in rows_with(card_payment_available=False)],
            [False, True],
        )
        self.assertEqual(
            [row.card_payment_available for row in rows_with(card_payment_available=None)],
            [True, None],
        )
        self.assertEqual(
            [row.dinner_budget_tier for row in rows_with(budget_average=5000.0)],
            ["HIGH", "LOW"],
        )
        self.assertEqual(
            [row.dinner_budget_tier for row in rows_with(budget_average=None)],
            ["LOW", None],
        )


class FilterCandidatesTests(SimpleTestCase):
    def test_no_filters_excludes_only_the_default_excluded_genres(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        result = filter_candidates([soba, izakaya], CandidateFilters())

        self.assertEqual([c.name for c in result], [soba.name])

    def test_include_izakaya_bar_keeps_the_default_excluded_genre(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        result = filter_candidates([soba, izakaya], CandidateFilters(include_izakaya_bar=True))

        self.assertEqual(
            {c.provider_page_url for c in result},
            {soba.provider_page_url, izakaya.provider_page_url},
        )

    def test_genres_filter_keeps_only_the_requested_genres(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        yoshoku = candidate(provider_page_url="https://example.invalid/yoshoku", genre="洋食")

        result = filter_candidates([soba, yoshoku], CandidateFilters(genres=("和食",)))

        self.assertEqual([c.name for c in result], [soba.name])

    def test_genres_filter_does_not_reach_into_the_default_excluded_population(self):
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        result = filter_candidates([izakaya], CandidateFilters(genres=("居酒屋",)))

        self.assertEqual(result, [])

    def test_non_smoking_only_excludes_confirmed_none_but_keeps_unconfirmed(self):
        full = candidate(
            provider_page_url="https://example.invalid/full", non_smoking_status="FULL"
        )
        none_status = candidate(
            provider_page_url="https://example.invalid/none", non_smoking_status="NONE"
        )
        unconfirmed = candidate(
            provider_page_url="https://example.invalid/unconfirmed", non_smoking_status=None
        )

        result = filter_candidates(
            [full, none_status, unconfirmed], CandidateFilters(non_smoking_only=True)
        )

        self.assertEqual(
            {c.provider_page_url for c in result},
            {full.provider_page_url, unconfirmed.provider_page_url},
        )

    def test_card_payment_only_excludes_confirmed_false_but_keeps_unconfirmed(self):
        available = candidate(
            provider_page_url="https://example.invalid/available", card_payment_available=True
        )
        unavailable = candidate(
            provider_page_url="https://example.invalid/unavailable", card_payment_available=False
        )
        unconfirmed = candidate(
            provider_page_url="https://example.invalid/unconfirmed", card_payment_available=None
        )

        result = filter_candidates(
            [available, unavailable, unconfirmed], CandidateFilters(card_payment_only=True)
        )

        self.assertEqual(
            {c.provider_page_url for c in result},
            {available.provider_page_url, unconfirmed.provider_page_url},
        )

    def test_budget_tiers_excludes_confirmed_non_matching_tiers_but_keeps_unconfirmed(self):
        low = candidate(provider_page_url="https://example.invalid/low", budget_average=1500.0)
        high = candidate(provider_page_url="https://example.invalid/high", budget_average=5000.0)
        unconfirmed = candidate(
            provider_page_url="https://example.invalid/unconfirmed", budget_average=None
        )

        result = filter_candidates(
            [low, high, unconfirmed], CandidateFilters(budget_tiers=("LOW",))
        )

        self.assertEqual(
            {c.provider_page_url for c in result},
            {low.provider_page_url, unconfirmed.provider_page_url},
        )

    def test_every_filter_composes(self):
        matching = candidate(
            provider_page_url="https://example.invalid/matching",
            genre="和食",
            non_smoking_status="FULL",
            card_payment_available=True,
            budget_average=1500.0,
        )
        wrong_genre = candidate(
            provider_page_url="https://example.invalid/wrong-genre",
            genre="洋食",
            non_smoking_status="FULL",
            card_payment_available=True,
            budget_average=1500.0,
        )

        result = filter_candidates(
            [matching, wrong_genre],
            CandidateFilters(
                genres=("和食",),
                non_smoking_only=True,
                card_payment_only=True,
                budget_tiers=("LOW",),
            ),
        )

        self.assertEqual([c.name for c in result], [matching.name])


class ApplyIzakayaBarFallbackTests(SimpleTestCase):
    def test_non_empty_result_is_returned_without_a_fallback(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")

        population, fallback_applied = apply_izakaya_bar_fallback([soba], CandidateFilters())

        self.assertEqual([c.name for c in population], [soba.name])
        self.assertFalse(fallback_applied)

    def test_empty_default_population_falls_back_to_include_izakaya_bar(self):
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        population, fallback_applied = apply_izakaya_bar_fallback([izakaya], CandidateFilters())

        self.assertEqual([c.name for c in population], [izakaya.name])
        self.assertTrue(fallback_applied)

    def test_still_empty_after_fallback_is_not_flagged_as_applied(self):
        population, fallback_applied = apply_izakaya_bar_fallback([], CandidateFilters())

        self.assertEqual(population, [])
        self.assertFalse(fallback_applied)

    def test_already_true_include_izakaya_bar_never_triggers_a_fallback(self):
        population, fallback_applied = apply_izakaya_bar_fallback(
            [], CandidateFilters(include_izakaya_bar=True)
        )

        self.assertEqual(population, [])
        self.assertFalse(fallback_applied)

    def test_fallback_does_not_loosen_other_explicit_filters(self):
        # TDR-CS-10: only includeIzakayaBar is loosened; a genre filter that
        # still matches nothing after the fallback stays empty and unflagged.
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        population, fallback_applied = apply_izakaya_bar_fallback(
            [izakaya], CandidateFilters(genres=("和食",))
        )

        self.assertEqual(population, [])
        self.assertFalse(fallback_applied)


class OrderConfirmedThenUnconfirmedTests(SimpleTestCase):
    def test_no_nullable_filter_active_is_plain_nearest_first(self):
        near = candidate(
            name="近い店", provider_page_url="https://example.invalid/near", latitude=0.001
        )
        far = candidate(
            name="遠い店", provider_page_url="https://example.invalid/far", latitude=0.05
        )

        ordered = order_confirmed_then_unconfirmed([far, near], ORIGIN, CandidateFilters())

        self.assertEqual([c.name for c in ordered], ["近い店", "遠い店"])

    def test_non_smoking_only_places_unconfirmed_after_confirmed(self):
        unconfirmed_near = candidate(
            name="近いが不明",
            provider_page_url="https://example.invalid/unconfirmed",
            non_smoking_status=None,
            latitude=0.001,
        )
        confirmed_far = candidate(
            name="遠いが確認済み",
            provider_page_url="https://example.invalid/confirmed",
            non_smoking_status="FULL",
            latitude=0.05,
        )

        ordered = order_confirmed_then_unconfirmed(
            [unconfirmed_near, confirmed_far], ORIGIN, CandidateFilters(non_smoking_only=True)
        )

        self.assertEqual([c.name for c in ordered], ["遠いが確認済み", "近いが不明"])

    def test_each_group_is_nearest_first_internally(self):
        confirmed_far = candidate(
            name="確認済み・遠い",
            provider_page_url="https://example.invalid/confirmed-far",
            card_payment_available=True,
            latitude=0.05,
        )
        confirmed_near = candidate(
            name="確認済み・近い",
            provider_page_url="https://example.invalid/confirmed-near",
            card_payment_available=True,
            latitude=0.001,
        )
        unconfirmed_far = candidate(
            name="不明・遠い",
            provider_page_url="https://example.invalid/unconfirmed-far",
            card_payment_available=None,
            latitude=0.06,
        )
        unconfirmed_near = candidate(
            name="不明・近い",
            provider_page_url="https://example.invalid/unconfirmed-near",
            card_payment_available=None,
            latitude=0.002,
        )

        ordered = order_confirmed_then_unconfirmed(
            [confirmed_far, unconfirmed_far, confirmed_near, unconfirmed_near],
            ORIGIN,
            CandidateFilters(card_payment_only=True),
        )

        self.assertEqual(
            [c.name for c in ordered],
            ["確認済み・近い", "確認済み・遠い", "不明・近い", "不明・遠い"],
        )

    def test_budget_tiers_also_drives_the_unconfirmed_grouping(self):
        confirmed = candidate(
            name="確認済み",
            provider_page_url="https://example.invalid/confirmed",
            budget_average=1500.0,
            latitude=0.05,
        )
        unconfirmed = candidate(
            name="不明",
            provider_page_url="https://example.invalid/unconfirmed",
            budget_average=None,
            latitude=0.001,
        )

        ordered = order_confirmed_then_unconfirmed(
            [unconfirmed, confirmed], ORIGIN, CandidateFilters(budget_tiers=("LOW",))
        )

        self.assertEqual([c.name for c in ordered], ["確認済み", "不明"])


class SelectPoolAndSampleTests(SimpleTestCase):
    """adr/0024 decision 3: distance-weighted sampling over the whole population.

    The fixed near-distance pool (adr/0023 decision 4 steps 4-5) is retired;
    ``select_pool_and_sample`` now takes ``origin`` directly and weighs every
    candidate in the input by distance rather than truncating to a pool
    first. The exact weighting formula is a non-binding implementation
    choice (adr/0024 decision 3) -- these tests verify only the two
    contractually-required statistical properties (P1, P2) plus the
    seed-reproducibility/display-cap/empty-population behavior that does not
    depend on the formula.
    """

    def _ordered(self, count):
        return [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/order-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, count + 1)
        ]

    def test_population_at_or_below_the_display_cap_returns_everything(self):
        population = self._ordered(3)

        sample = select_pool_and_sample(population, ORIGIN, random_source=random.Random(1))

        self.assertEqual({c.name for c in sample}, {"店1", "店2", "店3"})

    def test_sample_is_bounded_by_the_display_cap(self):
        population = self._ordered(10)

        sample = select_pool_and_sample(population, ORIGIN, random_source=random.Random(1))

        self.assertEqual(len(sample), 5)

    def test_same_seed_reproduces_the_identical_sample(self):
        population = self._ordered(10)

        first = select_pool_and_sample(population, ORIGIN, random_source=random.Random(42))
        second = select_pool_and_sample(population, ORIGIN, random_source=random.Random(42))

        self.assertEqual([c.name for c in first], [c.name for c in second])

    def test_different_seeds_can_produce_different_samples(self):
        population = self._ordered(30)

        samples = {
            tuple(
                c.name
                for c in select_pool_and_sample(
                    population, ORIGIN, random_source=random.Random(seed)
                )
            )
            for seed in range(10)
        }

        self.assertGreater(len(samples), 1, "every seed produced the identical sample")

    def test_empty_population_returns_an_empty_sample(self):
        sample = select_pool_and_sample([], ORIGIN, random_source=random.Random(1))

        self.assertEqual(sample, [])

    def test_no_pool_ceiling_the_farthest_candidate_is_reachable(self):
        # adr/0023 decision 4's fixed pool (min(population, 20)) meant a
        # candidate ranked beyond the pool size could never be drawn. That
        # ceiling is gone: a population far larger than the old recommended
        # pool size of 20 must still let its single farthest member surface
        # over enough trials (this is a coarse smoke test; the statistical
        # properties themselves are verified in
        # DistanceWeightedSelectionStatisticalTests below).
        population = self._ordered(30)
        farthest = population[-1].name

        seen_farthest = False
        for seed in range(500):
            sample = select_pool_and_sample(population, ORIGIN, random_source=random.Random(seed))
            if farthest in {c.name for c in sample}:
                seen_farthest = True
                break

        self.assertTrue(seen_farthest, "the farthest candidate was never selected in 500 trials")


class DistanceWeightedSelectionStatisticalTests(SimpleTestCase):
    """Statistical verification of P1/P2 (adr/0024 decision 3), many trials.

    Per candidate-search-browser-interface.yaml's
    ``proposal.distanceWeightedSelection`` invariant, this must not pin a
    single seed (a single run is a draw, not a property) and must not assume
    any particular weighting formula -- only that empirical selection
    frequency is non-increasing in distance (P1) and that the single
    farthest candidate is selected at least once across many trials (P2).
    Mirrors the methodology orchestrator used to measure this project's real
    duplication-rate improvement (adr/0024's cited 20000-trial measurement),
    scaled down for test runtime.
    """

    TRIALS = 4000

    def _population_by_distance(self, count):
        # Distinct, strictly increasing distances from ORIGIN so "closer"
        # and "farther" are unambiguous.
        return [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/weighted-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, count + 1)
        ]

    def test_selection_frequency_is_non_increasing_in_distance(self):
        population = self._population_by_distance(10)
        counts = Counter()
        random_source = random.Random(12345)

        for _ in range(self.TRIALS):
            sample = select_pool_and_sample(population, ORIGIN, random_source=random_source)
            counts.update(c.name for c in sample)

        frequencies = [counts[c.name] for c in population]  # nearest first
        # P1: closer candidates are never less likely than farther ones --
        # allow small statistical slack between adjacent ranks (a strict
        # non-increasing check across noisy empirical frequencies would be
        # flaky), but the nearest must be clearly more frequent than the
        # farthest overall.
        for earlier, later in zip(frequencies, frequencies[1:]):
            self.assertGreaterEqual(
                earlier + self.TRIALS // 20,
                later,
                f"frequencies {frequencies} are not statistically non-increasing",
            )
        self.assertGreater(frequencies[0], frequencies[-1])

    def test_farthest_candidate_is_selected_at_least_once(self):
        # P2: no eligible candidate has a structurally zero selection
        # probability, even the single farthest member of a population much
        # larger than the display cap.
        population = self._population_by_distance(25)
        farthest = population[-1].name
        random_source = random.Random(54321)

        selected_farthest = False
        for _ in range(self.TRIALS):
            sample = select_pool_and_sample(population, ORIGIN, random_source=random_source)
            if farthest in {c.name for c in sample}:
                selected_farthest = True
                break

        self.assertTrue(
            selected_farthest, f"the farthest candidate was never selected in {self.TRIALS} trials"
        )


class PartitionByShownTests(SimpleTestCase):
    def test_splits_into_unseen_and_seen_by_provider_page_url(self):
        seen_one = candidate(provider_page_url="https://example.invalid/seen-one")
        seen_two = candidate(provider_page_url="https://example.invalid/seen-two")
        unseen = candidate(provider_page_url="https://example.invalid/unseen")

        unseen_result, seen_result = partition_by_shown(
            [seen_one, unseen, seen_two],
            {"https://example.invalid/seen-one", "https://example.invalid/seen-two"},
        )

        self.assertEqual([c.name for c in unseen_result], [unseen.name])
        self.assertEqual(
            {c.provider_page_url for c in seen_result},
            {seen_one.provider_page_url, seen_two.provider_page_url},
        )

    def test_empty_shown_set_treats_every_candidate_as_unseen(self):
        one = candidate(provider_page_url="https://example.invalid/one")

        unseen_result, seen_result = partition_by_shown([one], set())

        self.assertEqual(unseen_result, [one])
        self.assertEqual(seen_result, [])


class SelectWithShownPriorityTests(SimpleTestCase):
    """adr/0024 decision 4's three set-membership properties.

    Deterministic (never depends on a particular randomSeed or the weighting
    formula) -- these test set membership only, matching
    candidate-search-browser-interface.yaml's proposal.shownPoolPriority
    invariant.
    """

    def _population(self, count):
        return [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/priority-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, count + 1)
        ]

    def test_unseen_at_or_above_display_cap_draws_only_from_unseen(self):
        population = self._population(10)
        shown = {c.provider_page_url for c in population[:2]}  # 8 remain unseen

        for seed in range(20):
            selected, exhausted = select_with_shown_priority(
                population, ORIGIN, shown, random_source=random.Random(seed)
            )
            self.assertFalse(exhausted)
            self.assertEqual(len(selected), DISPLAY_CAP)
            self.assertTrue(
                all(c.provider_page_url not in shown for c in selected),
                "a shown candidate was selected while unseen still had >= display cap members",
            )

    def test_unseen_below_display_cap_includes_every_unseen_member_and_fills_from_seen(self):
        population = self._population(10)
        # Exactly 8 already shown, leaving 2 unseen (< DISPLAY_CAP=5).
        shown = {c.provider_page_url for c in population[:8]}
        unseen_urls = {c.provider_page_url for c in population[8:]}

        for seed in range(20):
            selected, exhausted = select_with_shown_priority(
                population, ORIGIN, shown, random_source=random.Random(seed)
            )
            self.assertFalse(exhausted)
            self.assertEqual(len(selected), DISPLAY_CAP)
            selected_urls = {c.provider_page_url for c in selected}
            self.assertTrue(
                unseen_urls.issubset(selected_urls),
                "every not-yet-shown candidate must be included",
            )

    def test_unseen_empty_falls_back_to_the_full_population_and_reports_exhausted(self):
        population = self._population(7)
        shown = {c.provider_page_url for c in population}

        for seed in range(20):
            selected, exhausted = select_with_shown_priority(
                population, ORIGIN, shown, random_source=random.Random(seed)
            )
            self.assertTrue(exhausted)
            self.assertEqual(len(selected), DISPLAY_CAP)
            self.assertTrue(
                {c.provider_page_url for c in selected}.issubset(
                    {c.provider_page_url for c in population}
                )
            )

    def test_omitted_shown_set_behaves_as_entirely_unseen(self):
        population = self._population(3)

        selected, exhausted = select_with_shown_priority(
            population, ORIGIN, (), random_source=random.Random(1)
        )

        self.assertFalse(exhausted)
        self.assertEqual({c.name for c in selected}, {"店1", "店2", "店3"})


class BuildProposalTests(SimpleTestCase):
    def test_no_candidates_yields_an_empty_proposal(self):
        proposal = build_proposal([], ORIGIN, CandidateFilters(), random_source=random.Random(1))

        self.assertEqual(proposal.candidates, ())
        self.assertFalse(proposal.izakaya_bar_fallback_applied)
        self.assertEqual(proposal.available_genres, ())
        # adr/0024 decision 4: an empty eligible population trivially has no
        # unseen member, so this is the exhausted case by definition.
        self.assertTrue(proposal.shown_pool_exhausted)

    def test_duplicate_provider_page_urls_are_deduplicated(self):
        first = candidate(name="一号店", provider_page_url="https://example.invalid/shop-a")
        duplicate = candidate(
            name="一号店（重複）", provider_page_url="https://example.invalid/shop-a"
        )

        proposal = build_proposal(
            [first, duplicate], ORIGIN, CandidateFilters(), random_source=random.Random(1)
        )

        self.assertEqual(len(proposal.candidates), 1)

    def test_small_population_returns_every_eligible_candidate_ordered_nearest_first(self):
        near = candidate(
            name="近い店", provider_page_url="https://example.invalid/near", latitude=0.001
        )
        far = candidate(
            name="遠い店", provider_page_url="https://example.invalid/far", latitude=0.05
        )

        proposal = build_proposal(
            [far, near], ORIGIN, CandidateFilters(), random_source=random.Random(1)
        )

        self.assertEqual([c.name for c in proposal.candidates], ["近い店", "遠い店"])

    def test_available_genres_reflects_the_deduplicated_population(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        yoshoku = candidate(provider_page_url="https://example.invalid/yoshoku", genre="洋食")

        proposal = build_proposal(
            [soba, yoshoku], ORIGIN, CandidateFilters(), random_source=random.Random(1)
        )

        self.assertEqual(proposal.available_genres, ("和食", "洋食"))

    def test_izakaya_bar_fallback_is_reported_on_the_proposal(self):
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        proposal = build_proposal(
            [izakaya], ORIGIN, CandidateFilters(), random_source=random.Random(1)
        )

        self.assertTrue(proposal.izakaya_bar_fallback_applied)
        self.assertEqual([c.name for c in proposal.candidates], [izakaya.name])

    def test_display_order_is_reapplied_after_sampling(self):
        # A population at or below the display cap means every candidate is
        # selected; the final display order must still be nearest-first
        # (decision 4 step 6), regardless of the random draw order.
        candidates = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/order-{i}",
                latitude=0.001 * i,
            )
            for i in (3, 1, 2)
        ]

        proposal = build_proposal(
            candidates, ORIGIN, CandidateFilters(), random_source=random.Random(7)
        )

        self.assertEqual([c.name for c in proposal.candidates], ["店1", "店2", "店3"])

    def test_display_cap_applies_when_the_population_exceeds_it(self):
        candidates = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/many-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, 8)
        ]

        proposal = build_proposal(
            candidates, ORIGIN, CandidateFilters(), random_source=random.Random(1)
        )

        self.assertEqual(len(proposal.candidates), 5)

    def test_same_seed_reproduces_the_identical_proposal(self):
        candidates = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/many-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, 30)
        ]

        first = build_proposal(
            candidates, ORIGIN, CandidateFilters(), random_source=random.Random(99)
        )
        second = build_proposal(
            candidates, ORIGIN, CandidateFilters(), random_source=random.Random(99)
        )

        self.assertEqual(
            [c.provider_page_url for c in first.candidates],
            [c.provider_page_url for c in second.candidates],
        )

    def test_different_seeds_can_reproduce_different_proposals(self):
        candidates = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/many-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, 30)
        ]

        proposals = {
            tuple(
                c.provider_page_url
                for c in build_proposal(
                    candidates, ORIGIN, CandidateFilters(), random_source=random.Random(seed)
                ).candidates
            )
            for seed in range(10)
        }

        self.assertGreater(len(proposals), 1, "every seed produced the identical proposal")

    def test_filters_are_applied_before_pool_selection(self):
        # adr/0023 decision 3: filtering must run on the full population, not
        # a display-truncated subset -- so a genre filter can eliminate
        # candidates selection would otherwise have included.
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        yoshoku = candidate(provider_page_url="https://example.invalid/yoshoku", genre="洋食")

        proposal = build_proposal(
            [soba, yoshoku],
            ORIGIN,
            CandidateFilters(genres=("和食",)),
            random_source=random.Random(1),
        )

        self.assertEqual([c.genre for c in proposal.candidates], ["和食"])

    # adr/0024 decision 4: shown_provider_page_urls forwarding ------------

    def test_shown_provider_page_urls_defaults_to_treating_everything_as_unseen(self):
        candidates = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/default-unseen-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, 4)
        ]

        proposal = build_proposal(
            candidates, ORIGIN, CandidateFilters(), random_source=random.Random(1)
        )

        self.assertFalse(proposal.shown_pool_exhausted)
        self.assertEqual(len(proposal.candidates), 3)

    def test_shown_provider_page_urls_are_deprioritized_not_excluded(self):
        candidates = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/deprioritized-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, 8)
        ]
        shown = {c.provider_page_url for c in candidates[:6]}  # 1 unseen remains

        proposal = build_proposal(
            candidates,
            ORIGIN,
            CandidateFilters(),
            random_source=random.Random(1),
            shown_provider_page_urls=shown,
        )

        self.assertFalse(proposal.shown_pool_exhausted)
        self.assertEqual(len(proposal.candidates), 5)
        selected_urls = {c.provider_page_url for c in proposal.candidates}
        unseen_url = {c.provider_page_url for c in candidates} - shown
        # The sole unseen candidate must be included (adr/0024 decision 4's
        # "every unseen member is returned" property); the remaining slots
        # are filled from the already-shown candidates rather than the
        # response being short -- proving shown candidates are deprioritized,
        # not excluded from an otherwise-eligible population.
        self.assertTrue(unseen_url.issubset(selected_urls))
        self.assertTrue(selected_urls - unseen_url)

    def test_shown_pool_exhausted_when_every_eligible_candidate_was_already_shown(self):
        candidates = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/exhausted-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, 4)
        ]
        shown = {c.provider_page_url for c in candidates}

        proposal = build_proposal(
            candidates,
            ORIGIN,
            CandidateFilters(),
            random_source=random.Random(1),
            shown_provider_page_urls=shown,
        )

        self.assertTrue(proposal.shown_pool_exhausted)
        self.assertEqual(len(proposal.candidates), 3)

    def test_shown_provider_page_urls_do_not_affect_the_final_display_order(self):
        # decision 4 step 6 (unchanged): the shown/unseen partition is a
        # selection-stage concern only. Whatever gets selected must still be
        # re-ordered nearest-first for display.
        near = candidate(
            name="近い店",
            provider_page_url="https://example.invalid/order-near",
            latitude=0.001,
        )
        far = candidate(
            name="遠い店", provider_page_url="https://example.invalid/order-far", latitude=0.05
        )

        proposal = build_proposal(
            [far, near],
            ORIGIN,
            CandidateFilters(),
            random_source=random.Random(1),
            shown_provider_page_urls={far.provider_page_url},
        )

        self.assertEqual([c.name for c in proposal.candidates], ["近い店", "遠い店"])
