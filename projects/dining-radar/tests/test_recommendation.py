import random

from django.test import SimpleTestCase

from dining_radar.recommendation.pipeline import (
    DEFAULT_EXCLUDED_GENRES,
    CandidateFilters,
    NormalizedCandidate,
    Origin,
    apply_izakaya_bar_fallback,
    available_genres,
    build_proposal,
    dinner_budget_tier,
    filter_candidates,
    order_confirmed_then_unconfirmed,
    select_pool_and_sample,
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
        # adr/0020 decision 9: availableGenres reflects only includeIzakayaBar,
        # never the genres/nonSmokingOnly/cardPaymentOnly/budgetTiers filters
        # themselves -- this function does not even accept those, by design.
        candidates = [
            candidate(provider_page_url="https://example.invalid/a", genre="和食"),
            candidate(provider_page_url="https://example.invalid/b", genre="洋食"),
        ]

        self.assertEqual(available_genres(candidates, False), ["和食", "洋食"])


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

        sample = select_pool_and_sample(population, random_source=random.Random(1))

        self.assertEqual({c.name for c in sample}, {"店1", "店2", "店3"})

    def test_sample_is_bounded_by_the_display_cap(self):
        population = self._ordered(10)

        sample = select_pool_and_sample(population, random_source=random.Random(1))

        self.assertEqual(len(sample), 5)

    def test_pool_is_limited_to_the_nearest_pool_size_candidates(self):
        population = self._ordered(10)

        # pool_size=3 with display_cap=3: only the three nearest can ever be
        # sampled, regardless of seed.
        for seed in range(5):
            sample = select_pool_and_sample(
                population, random_source=random.Random(seed), pool_size=3, display_cap=3
            )
            self.assertEqual({c.name for c in sample}, {"店1", "店2", "店3"})

    def test_same_seed_reproduces_the_identical_sample(self):
        population = self._ordered(10)

        first = select_pool_and_sample(population, random_source=random.Random(42))
        second = select_pool_and_sample(population, random_source=random.Random(42))

        self.assertEqual([c.name for c in first], [c.name for c in second])

    def test_different_seeds_can_produce_different_samples(self):
        population = self._ordered(30)

        samples = {
            tuple(
                c.name
                for c in select_pool_and_sample(population, random_source=random.Random(seed))
            )
            for seed in range(10)
        }

        self.assertGreater(len(samples), 1, "every seed produced the identical sample")

    def test_empty_population_returns_an_empty_sample(self):
        sample = select_pool_and_sample([], random_source=random.Random(1))

        self.assertEqual(sample, [])


class BuildProposalTests(SimpleTestCase):
    def test_no_candidates_yields_an_empty_proposal(self):
        proposal = build_proposal([], ORIGIN, CandidateFilters(), random_source=random.Random(1))

        self.assertEqual(proposal.candidates, ())
        self.assertFalse(proposal.izakaya_bar_fallback_applied)
        self.assertEqual(proposal.available_genres, ())

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
        # A population smaller than the pool means every candidate is
        # sampled; the final display order must still be nearest-first
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
        # adr/0020 decision 3: filtering must run on the full population, not
        # a display-truncated subset -- so a genre filter can eliminate
        # candidates the pool would otherwise have included.
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        yoshoku = candidate(provider_page_url="https://example.invalid/yoshoku", genre="洋食")

        proposal = build_proposal(
            [soba, yoshoku],
            ORIGIN,
            CandidateFilters(genres=("和食",)),
            random_source=random.Random(1),
        )

        self.assertEqual([c.genre for c in proposal.candidates], ["和食"])
