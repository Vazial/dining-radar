import random
from collections import Counter

from django.test import SimpleTestCase

from dining_radar.recommendation.pipeline import (
    DEFAULT_EXCLUDED_GENRES,
    DISPLAY_CAP,
    METERS_PER_DEGREE_LATITUDE,
    WALKING_DETOUR_FACTOR,
    WALKING_METERS_PER_MINUTE,
    WALKING_TIME_MAX_PRESET_MINUTES,
    CandidateFilters,
    NormalizedCandidate,
    Origin,
    apply_izakaya_bar_fallback,
    available_genres,
    build_proposal,
    capacity_tier,
    dinner_budget_tier,
    filter_candidates,
    is_confirmed_closed_on_weekday,
    open_shop_population,
    order_confirmed_then_unconfirmed,
    partition_by_shown,
    population_attributes,
    select_pool_and_sample,
    select_with_shown_priority,
    walking_time_band,
    walking_time_minutes,
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
            ],
            ORIGIN,
        )[0]

        self.assertEqual(
            set(vars(row)),
            {
                "genre",
                "non_smoking_status",
                "card_payment_available",
                "dinner_budget_tier",
                "default_excluded",
                "walking_time_band",
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

        in_source_order = population_attributes([first_source_row, second_source_row], ORIGIN)
        in_reverse_source_order = population_attributes(
            [second_source_row, first_source_row], ORIGIN
        )

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
            return population_attributes([second, first], ORIGIN)

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

    def test_walking_time_band_is_the_final_tie_break(self):
        # adr/0025 decision 3: two rows identical on every other public
        # filter value must still be ordered by walking_time_band (nearer,
        # bucketed first; farther-than-every-preset/None last) -- otherwise
        # this dataclass's sole location-derived field would leak no
        # information the browser could use, and a stable sort would instead
        # silently preserve input order.
        near = candidate(
            provider_page_url="https://example.invalid/band-near",
            latitude=0.001,
            genre="same-genre",
            non_smoking_status="FULL",
            card_payment_available=True,
            budget_average=1500.0,
        )
        far = candidate(
            provider_page_url="https://example.invalid/band-far",
            latitude=9.0,  # ~1,000km away -- exceeds every walking-time preset
            genre="same-genre",
            non_smoking_status="FULL",
            card_payment_available=True,
            budget_average=1500.0,
        )

        rows = population_attributes([far, near], ORIGIN)

        self.assertIsNotNone(rows[0].walking_time_band)
        self.assertIsNone(rows[1].walking_time_band)

    def test_walking_time_band_orders_two_non_null_bands_ascending(self):
        # Both rows below land in a real (non-None) preset bucket, so
        # ordering between them can only come from directly comparing the
        # two band values -- unlike the near-vs-None case above, which the
        # earlier "is None" tie-break key alone already decides.
        band_ten = candidate(
            provider_page_url="https://example.invalid/band-ten",
            # 460m -> ceil(460*1.3/80) = 8 min -> bucket 10 (the smallest
            # preset >= 8 once the 5 preset from human decision 2026-08-26
            # is included; 100m/~2min used before that change fell into the
            # new 5-min bucket instead, no longer distinguishing this case
            # from band_thirty's own bucket the way this test needs).
            latitude=460 / METERS_PER_DEGREE_LATITUDE,
            genre="same-genre",
            non_smoking_status="FULL",
            card_payment_available=True,
            budget_average=1500.0,
        )
        band_thirty = candidate(
            provider_page_url="https://example.invalid/band-thirty",
            latitude=1500 / METERS_PER_DEGREE_LATITUDE,  # 25 min (with detour) -> bucket 30
            genre="same-genre",
            non_smoking_status="FULL",
            card_payment_available=True,
            budget_average=1500.0,
        )

        rows = population_attributes([band_thirty, band_ten], ORIGIN)

        self.assertEqual([row.walking_time_band for row in rows], [10, 30])


class FilterCandidatesTests(SimpleTestCase):
    def test_no_filters_excludes_only_the_default_excluded_genres(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        result = filter_candidates([soba, izakaya], CandidateFilters(), ORIGIN)

        self.assertEqual([c.name for c in result], [soba.name])

    def test_include_izakaya_bar_keeps_the_default_excluded_genre(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        result = filter_candidates(
            [soba, izakaya], CandidateFilters(include_izakaya_bar=True), ORIGIN
        )

        self.assertEqual(
            {c.provider_page_url for c in result},
            {soba.provider_page_url, izakaya.provider_page_url},
        )

    def test_genres_filter_keeps_only_the_requested_genres(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")
        yoshoku = candidate(provider_page_url="https://example.invalid/yoshoku", genre="洋食")

        result = filter_candidates([soba, yoshoku], CandidateFilters(genres=("和食",)), ORIGIN)

        self.assertEqual([c.name for c in result], [soba.name])

    def test_genres_filter_does_not_reach_into_the_default_excluded_population(self):
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        result = filter_candidates([izakaya], CandidateFilters(genres=("居酒屋",)), ORIGIN)

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
            [full, none_status, unconfirmed], CandidateFilters(non_smoking_only=True), ORIGIN
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
            [available, unavailable, unconfirmed], CandidateFilters(card_payment_only=True), ORIGIN
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
            [low, high, unconfirmed], CandidateFilters(budget_tiers=("LOW",)), ORIGIN
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
            ORIGIN,
        )

        self.assertEqual([c.name for c in result], [matching.name])


class ApplyIzakayaBarFallbackTests(SimpleTestCase):
    def test_non_empty_result_is_returned_without_a_fallback(self):
        soba = candidate(provider_page_url="https://example.invalid/soba", genre="和食")

        population, fallback_applied = apply_izakaya_bar_fallback(
            [soba], CandidateFilters(), ORIGIN
        )

        self.assertEqual([c.name for c in population], [soba.name])
        self.assertFalse(fallback_applied)

    def test_empty_default_population_falls_back_to_include_izakaya_bar(self):
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        population, fallback_applied = apply_izakaya_bar_fallback(
            [izakaya], CandidateFilters(), ORIGIN
        )

        self.assertEqual([c.name for c in population], [izakaya.name])
        self.assertTrue(fallback_applied)

    def test_still_empty_after_fallback_is_not_flagged_as_applied(self):
        population, fallback_applied = apply_izakaya_bar_fallback([], CandidateFilters(), ORIGIN)

        self.assertEqual(population, [])
        self.assertFalse(fallback_applied)

    def test_already_true_include_izakaya_bar_never_triggers_a_fallback(self):
        population, fallback_applied = apply_izakaya_bar_fallback(
            [], CandidateFilters(include_izakaya_bar=True), ORIGIN
        )

        self.assertEqual(population, [])
        self.assertFalse(fallback_applied)

    def test_fallback_does_not_loosen_other_explicit_filters(self):
        # TDR-CS-10: only includeIzakayaBar is loosened; a genre filter that
        # still matches nothing after the fallback stays empty and unflagged.
        izakaya = candidate(provider_page_url="https://example.invalid/izakaya", genre="居酒屋")

        population, fallback_applied = apply_izakaya_bar_fallback(
            [izakaya], CandidateFilters(genres=("和食",)), ORIGIN
        )

        self.assertEqual(population, [])
        self.assertFalse(fallback_applied)

    def test_walking_time_max_minutes_is_not_loosened_by_the_fallback(self):
        # adr/0025 decision 3 amending TDR-CS-10: exactly like genres/
        # nonSmokingOnly/cardPaymentOnly/budgetTiers above, a walking-time
        # limit tight enough to exclude even the izakaya/bar-inclusive retry
        # must leave the fallback unflagged and the result empty.
        far_izakaya = candidate(
            provider_page_url="https://example.invalid/far-izakaya",
            genre="居酒屋",
            latitude=1.0,  # ~111,320m from ORIGIN -- far beyond any small limit
        )

        population, fallback_applied = apply_izakaya_bar_fallback(
            [far_izakaya], CandidateFilters(walking_time_max_minutes=1), ORIGIN
        )

        self.assertEqual(population, [])
        self.assertFalse(fallback_applied)

    def test_walking_time_max_minutes_still_permits_the_fallback_when_satisfied(self):
        near_izakaya = candidate(
            provider_page_url="https://example.invalid/near-izakaya",
            genre="居酒屋",
            latitude=0.0005,
        )

        population, fallback_applied = apply_izakaya_bar_fallback(
            [near_izakaya], CandidateFilters(walking_time_max_minutes=60), ORIGIN
        )

        self.assertEqual([c.name for c in population], [near_izakaya.name])
        self.assertTrue(fallback_applied)


class WalkingTimeMinutesTests(SimpleTestCase):
    """adr/0025 decision 2 + adr/0029 decision 1-2: derived from distance,
    corrected by ``WALKING_DETOUR_FACTOR``, rounded up, never ``None``."""

    def test_candidate_at_the_origin_is_zero_minutes(self):
        at_origin = candidate(provider_page_url="https://example.invalid/at-origin", latitude=0.0)

        self.assertEqual(walking_time_minutes(ORIGIN, at_origin), 0)

    def test_rounds_up_to_the_next_whole_minute(self):
        # The exact-10-minute boundary distance under the detour-corrected
        # formula (ceil(distance * WALKING_DETOUR_FACTOR /
        # WALKING_METERS_PER_MINUTE)) is distance = 10 * WALKING_METERS_PER_
        # MINUTE / WALKING_DETOUR_FACTOR; nudging the distance up by a
        # fraction of a meter past that boundary must round up to 11, never
        # truncate back down to 10, proving the ceiling (not floor/round)
        # rule survives the added multiplication.
        boundary_distance = 10 * WALKING_METERS_PER_MINUTE / WALKING_DETOUR_FACTOR
        just_over_ten_minutes = candidate(
            provider_page_url="https://example.invalid/just-over-ten",
            latitude=(boundary_distance + 0.5) / METERS_PER_DEGREE_LATITUDE,
        )

        self.assertEqual(walking_time_minutes(ORIGIN, just_over_ten_minutes), 11)

    def test_exactly_on_a_whole_minute_boundary_does_not_round_up_further(self):
        exactly_ten_minutes = candidate(
            provider_page_url="https://example.invalid/exactly-ten",
            latitude=(
                (10 * WALKING_METERS_PER_MINUTE / WALKING_DETOUR_FACTOR)
                / METERS_PER_DEGREE_LATITUDE
            ),
        )

        self.assertEqual(walking_time_minutes(ORIGIN, exactly_ten_minutes), 10)

    def test_farther_candidates_have_a_greater_or_equal_walking_time(self):
        near = candidate(provider_page_url="https://example.invalid/near-walk", latitude=0.001)
        far = candidate(provider_page_url="https://example.invalid/far-walk", latitude=0.02)

        self.assertGreaterEqual(
            walking_time_minutes(ORIGIN, far), walking_time_minutes(ORIGIN, near)
        )

    def test_nonzero_origin_subtracts_rather_than_adds_each_coordinate(self):
        # ORIGIN is (0, 0) everywhere else in this file, which cannot
        # distinguish "candidate - origin" from "candidate + origin" (both
        # reduce to the same value when origin is zero). This test uses a
        # nonzero origin on both axes and an independently hand-computed
        # expected result, so it fails if either coordinate's subtraction is
        # ever replaced with addition, or if latitude_scale's multiplication
        # is replaced with division.
        origin = Origin(latitude=35.0, longitude=139.0)
        nearby = candidate(
            provider_page_url="https://example.invalid/nonzero-origin",
            latitude=35.001,
            longitude=139.002,
        )

        # Independently computed: latitude_scale = cos(radians(35.0));
        # delta_latitude = 0.001; delta_longitude = 0.002 * latitude_scale;
        # degrees = hypot(delta_latitude, delta_longitude); meters = degrees
        # * METERS_PER_DEGREE_LATITUDE (~213.666m); minutes =
        # ceil(meters * 1.3 / 80) = 4. Swapping either subtraction for
        # addition, or the scale's multiplication for division, changes this
        # to a different integer.
        self.assertEqual(walking_time_minutes(origin, nearby), 4)


class WalkingTimeBandTests(SimpleTestCase):
    """adr/0025 decision 3: the coarse bucket ``PopulationAttribute.walkingTimeBand`` uses."""

    def test_below_the_smallest_preset_buckets_to_the_smallest_preset(self):
        self.assertEqual(walking_time_band(1), min(WALKING_TIME_MAX_PRESET_MINUTES))

    def test_exactly_on_a_preset_buckets_to_that_preset(self):
        for preset in WALKING_TIME_MAX_PRESET_MINUTES:
            with self.subTest(preset=preset):
                self.assertEqual(walking_time_band(preset), preset)

    def test_between_two_presets_buckets_to_the_larger_one(self):
        ordered = sorted(WALKING_TIME_MAX_PRESET_MINUTES)
        self.assertGreaterEqual(len(ordered), 2, "need at least two presets to test a gap")
        between = ordered[0] + 1
        self.assertLess(between, ordered[1])

        self.assertEqual(walking_time_band(between), ordered[1])

    def test_beyond_the_largest_preset_is_none(self):
        beyond = max(WALKING_TIME_MAX_PRESET_MINUTES) + 1

        self.assertIsNone(walking_time_band(beyond))

    def test_custom_preset_set_is_honored_over_the_module_default(self):
        self.assertEqual(walking_time_band(7, presets=(5, 10)), 10)
        self.assertIsNone(walking_time_band(11, presets=(5, 10)))


class FilterCandidatesWalkingTimeMaxMinutesTests(SimpleTestCase):
    """adr/0025 decision 3: a hard filter, unlike the three soft filters above."""

    def test_none_means_no_restriction(self):
        far = candidate(provider_page_url="https://example.invalid/unrestricted-far", latitude=1.0)

        result = filter_candidates([far], CandidateFilters(), ORIGIN)

        self.assertEqual([c.name for c in result], [far.name])

    def test_excludes_candidates_strictly_over_the_limit(self):
        near = candidate(provider_page_url="https://example.invalid/limit-near", latitude=0.0005)
        far = candidate(provider_page_url="https://example.invalid/limit-far", latitude=1.0)

        result = filter_candidates(
            [near, far], CandidateFilters(walking_time_max_minutes=5), ORIGIN
        )

        self.assertEqual([c.name for c in result], [near.name])

    def test_keeps_a_candidate_exactly_at_the_limit(self):
        exactly_at_limit = candidate(
            provider_page_url="https://example.invalid/limit-boundary",
            latitude=(
                (5 * WALKING_METERS_PER_MINUTE / WALKING_DETOUR_FACTOR) / METERS_PER_DEGREE_LATITUDE
            ),
        )

        result = filter_candidates(
            [exactly_at_limit], CandidateFilters(walking_time_max_minutes=5), ORIGIN
        )

        self.assertEqual([c.name for c in result], [exactly_at_limit.name])

    def test_no_walking_time_is_ever_unconfirmed_so_nothing_is_preserved_past_the_limit(self):
        # Unlike non_smoking_only/card_payment_only/budget_tiers, there is no
        # "unconfirmed" candidate this filter must keep -- every candidate's
        # walking time is always computable, so a limit excludes every
        # over-limit candidate with certainty.
        far = candidate(provider_page_url="https://example.invalid/certainly-far", latitude=1.0)

        result = filter_candidates([far], CandidateFilters(walking_time_max_minutes=1), ORIGIN)

        self.assertEqual(result, [])

    def test_composes_with_other_active_filters(self):
        matching = candidate(
            provider_page_url="https://example.invalid/walk-and-genre-match",
            genre="和食",
            latitude=0.0005,
        )
        wrong_genre_but_near = candidate(
            provider_page_url="https://example.invalid/walk-ok-wrong-genre",
            genre="洋食",
            latitude=0.0005,
        )
        right_genre_but_far = candidate(
            provider_page_url="https://example.invalid/walk-too-far-right-genre",
            genre="和食",
            latitude=1.0,
        )

        result = filter_candidates(
            [matching, wrong_genre_but_near, right_genre_but_far],
            CandidateFilters(genres=("和食",), walking_time_max_minutes=5),
            ORIGIN,
        )

        self.assertEqual([c.name for c in result], [matching.name])


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

    # search_origin / walking-time-max filter (adr/0025) -------------------

    def test_search_origin_is_carried_through_onto_the_proposal(self):
        origin = Origin(latitude=12.5, longitude=-3.25)

        proposal = build_proposal([], origin, CandidateFilters(), random_source=random.Random(1))

        self.assertEqual(proposal.search_origin, origin)

    def test_walking_time_max_minutes_filters_out_the_far_candidate_end_to_end(self):
        near = candidate(
            name="近い店", provider_page_url="https://example.invalid/e2e-near", latitude=0.0005
        )
        far = candidate(
            name="遠い店", provider_page_url="https://example.invalid/e2e-far", latitude=1.0
        )

        proposal = build_proposal(
            [near, far],
            ORIGIN,
            CandidateFilters(walking_time_max_minutes=5),
            random_source=random.Random(1),
        )

        self.assertEqual([c.name for c in proposal.candidates], ["近い店"])

    def test_population_attributes_walking_time_band_reflects_the_origin(self):
        near = candidate(provider_page_url="https://example.invalid/e2e-band-near", latitude=0.0005)
        far = candidate(provider_page_url="https://example.invalid/e2e-band-far", latitude=1.0)

        proposal = build_proposal(
            [near, far], ORIGIN, CandidateFilters(), random_source=random.Random(1)
        )

        bands = {attribute.walking_time_band for attribute in proposal.population_attributes}
        # The near candidate must land in some real preset bucket; the far
        # one (roughly 111km away) must exceed every preset (adr/0025
        # decision 3's "None" case).
        self.assertTrue(any(band is not None for band in bands))
        self.assertIn(None, bands)


class CapacityTierTests(SimpleTestCase):
    """adr/0019 decision 4, moved here from web.serializers (see capacity_tier's own docstring)."""

    def test_null_total_seats_is_a_null_tier(self):
        self.assertIsNone(capacity_tier(None))

    def test_twenty_seats_or_fewer_is_small(self):
        self.assertEqual(capacity_tier(20), "SMALL")

    def test_twenty_one_to_sixty_seats_is_medium(self):
        self.assertEqual(capacity_tier(21), "MEDIUM")
        self.assertEqual(capacity_tier(60), "MEDIUM")

    def test_sixty_one_seats_or_more_is_large(self):
        self.assertEqual(capacity_tier(61), "LARGE")


class IsConfirmedClosedOnWeekdayTests(SimpleTestCase):
    """adr/0035 decision 6 / adr/0037 decision 3: TDR-GTH's weekday soft matcher."""

    MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)

    def test_unconfirmed_holiday_is_never_closed_on_any_weekday(self):
        for weekday in range(7):
            with self.subTest(weekday=weekday):
                # assertIs (not assertFalse) so a `return False` -> `return
                # None` mutant is actually caught: `assertFalse(None)` would
                # otherwise still pass.
                self.assertIs(is_confirmed_closed_on_weekday(None, weekday), False)

    def test_irregular_holiday_text_is_never_closed_on_any_weekday(self):
        for weekday in range(7):
            with self.subTest(weekday=weekday):
                self.assertIs(is_confirmed_closed_on_weekday("不定休", weekday), False)

    def test_single_weekday_text_confirms_closure_only_on_that_weekday(self):
        for weekday in range(7):
            with self.subTest(weekday=weekday):
                self.assertEqual(
                    is_confirmed_closed_on_weekday("月曜", weekday), weekday == self.MONDAY
                )

    def test_two_weekday_text_confirms_closure_on_both_contained_weekdays(self):
        for weekday in range(7):
            with self.subTest(weekday=weekday):
                self.assertEqual(
                    is_confirmed_closed_on_weekday("火・水曜", weekday),
                    weekday in (self.TUESDAY, self.WEDNESDAY),
                )

    def test_existing_default_synthetic_holiday_text_confirms_closure_only_on_sunday(self):
        for weekday in range(7):
            with self.subTest(weekday=weekday):
                self.assertEqual(
                    is_confirmed_closed_on_weekday("日曜・祝日", weekday), weekday == self.SUNDAY
                )

    def test_known_limitation_negated_phrasing_is_misread_as_a_confirmed_closure(self):
        # Documented, accepted limitation (this function's own docstring,
        # test-support-api.yaml's GATHERING_OPEN_SHOP_WEEKDAY_MATCH): a
        # substring-only scan cannot tell "水曜以外" ("except Wednesday")
        # apart from a genuine Wednesday closure. Pinned here as a
        # regression test for the *documented* behavior, not a bug report.
        self.assertTrue(is_confirmed_closed_on_weekday("水曜以外", self.WEDNESDAY))


class OpenShopPopulationTests(SimpleTestCase):
    """adr/0035 decision 6 / adr/0037 decision 3: gathering-scheduling's open-shop preview."""

    MONDAY, TUESDAY, WEDNESDAY = 0, 1, 2

    def test_empty_population_is_empty(self):
        self.assertEqual(open_shop_population([], ORIGIN, self.MONDAY), [])

    def test_default_excluded_genre_is_excluded_like_candidate_search(self):
        izakaya = candidate(
            genre="居酒屋", provider_page_url="https://example.invalid/open-shop-izakaya"
        )
        washoku = candidate(
            genre="和食", provider_page_url="https://example.invalid/open-shop-washoku"
        )

        result = open_shop_population([izakaya, washoku], ORIGIN, self.MONDAY)

        self.assertEqual([c.provider_page_url for c in result], [washoku.provider_page_url])

    def test_a_shop_confirmed_closed_on_the_given_weekday_is_excluded(self):
        closed_monday = candidate(
            provider_page_url="https://example.invalid/open-shop-closed-monday",
            regular_holiday="月曜",
        )
        always_open = candidate(
            provider_page_url="https://example.invalid/open-shop-always-open",
            regular_holiday="不定休",
        )

        monday_result = open_shop_population([closed_monday, always_open], ORIGIN, self.MONDAY)
        tuesday_result = open_shop_population([closed_monday, always_open], ORIGIN, self.TUESDAY)

        self.assertEqual(
            [c.provider_page_url for c in monday_result], [always_open.provider_page_url]
        )
        self.assertEqual(
            {c.provider_page_url for c in tuesday_result},
            {closed_monday.provider_page_url, always_open.provider_page_url},
        )

    def test_result_is_ordered_nearest_first(self):
        far = candidate(
            name="遠い店",
            provider_page_url="https://example.invalid/open-shop-far",
            latitude=0.01,
        )
        near = candidate(
            name="近い店",
            provider_page_url="https://example.invalid/open-shop-near",
            latitude=0.001,
        )

        result = open_shop_population([far, near], ORIGIN, self.WEDNESDAY)

        self.assertEqual([c.name for c in result], ["近い店", "遠い店"])

    def test_deduplicates_by_provider_page_url(self):
        one = candidate(provider_page_url="https://example.invalid/open-shop-dup")
        duplicate = candidate(provider_page_url="https://example.invalid/open-shop-dup")

        result = open_shop_population([one, duplicate], ORIGIN, self.MONDAY)

        self.assertEqual(len(result), 1)
