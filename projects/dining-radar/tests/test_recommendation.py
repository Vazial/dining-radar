from django.test import SimpleTestCase

from dining_radar.recommendation.pipeline import (
    DEFAULT_EXCLUDED_GENRES,
    ConceptKind,
    NormalizedCandidate,
    Origin,
    ReproposalKindUnavailableError,
    build_concepts,
    reproposal_options,
    select_initial,
    select_reproposal,
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
    amenity_score=0,
    description="紹介文",
    regular_holiday="日曜",
    access="アクセス情報",
):
    return NormalizedCandidate(
        name=name,
        genre=genre,
        description=description,
        regular_holiday=regular_holiday,
        total_seats=total_seats,
        access=access,
        latitude=latitude,
        longitude=longitude,
        provider_page_url=provider_page_url,
        amenity_score=amenity_score,
    )


class BuildConceptsTests(SimpleTestCase):
    def test_no_candidates_produces_no_concepts(self):
        self.assertEqual(build_concepts([], ORIGIN), [])

    def test_duplicate_provider_page_urls_are_deduplicated(self):
        first = candidate(name="一号店", provider_page_url="https://example.invalid/shop-a")
        duplicate = candidate(
            name="一号店（重複）", provider_page_url="https://example.invalid/shop-a"
        )

        concepts = build_concepts([first, duplicate], ORIGIN)

        proximity = next(concept for concept in concepts if concept.kind is ConceptKind.PROXIMITY)
        self.assertEqual(len(proximity.candidates), 1)
        self.assertEqual(proximity.candidates[0].name, "一号店")

    def test_proximity_is_always_offered_when_any_candidate_exists(self):
        concepts = build_concepts([candidate()], ORIGIN)

        self.assertEqual(concepts[0].kind, ConceptKind.PROXIMITY)

    def test_proximity_orders_by_distance_from_origin(self):
        near = candidate(
            name="近い店", provider_page_url="https://example.invalid/near", latitude=0.001
        )
        far = candidate(
            name="遠い店", provider_page_url="https://example.invalid/far", latitude=0.05
        )

        concepts = build_concepts([far, near], ORIGIN)

        proximity = next(concept for concept in concepts if concept.kind is ConceptKind.PROXIMITY)
        self.assertEqual([c.name for c in proximity.candidates], ["近い店", "遠い店"])

    def test_capacity_reference_is_absent_without_any_seat_data(self):
        concepts = build_concepts(
            [candidate(provider_page_url="https://example.invalid/a", total_seats=None)], ORIGIN
        )

        self.assertNotIn(ConceptKind.CAPACITY_REFERENCE, [c.kind for c in concepts])

    def test_capacity_reference_orders_seats_descending_with_missing_data_last(self):
        many_seats = candidate(
            name="広い店", provider_page_url="https://example.invalid/big", total_seats=50
        )
        few_seats = candidate(
            name="狭い店", provider_page_url="https://example.invalid/small", total_seats=10
        )
        unknown_seats = candidate(
            name="不明な店", provider_page_url="https://example.invalid/unknown", total_seats=None
        )

        concepts = build_concepts([few_seats, unknown_seats, many_seats], ORIGIN)

        capacity = next(c for c in concepts if c.kind is ConceptKind.CAPACITY_REFERENCE)
        self.assertEqual([c.name for c in capacity.candidates], ["広い店", "狭い店", "不明な店"])

    def test_genre_variety_is_not_a_buildable_concept_kind(self):
        # adr/0016: GENRE_VARIETY was removed from ConceptKind because real
        # production data showed it always converged to the same candidate
        # set and order as PROXIMITY. Its enum member no longer exists, so
        # this asserts the closed set of buildable kinds directly rather
        # than the pre-adr/0016 "absent for a single genre" behaviour, which
        # no longer applies to anything.
        self.assertEqual(
            {kind.value for kind in ConceptKind},
            {"PROXIMITY", "CAPACITY_REFERENCE", "AMENITY_REFERENCE", "IZAKAYA_BAR_INCLUDED"},
        )

    def test_amenity_reference_is_absent_without_any_amenity_signal(self):
        concepts = build_concepts(
            [candidate(provider_page_url="https://example.invalid/a", amenity_score=0)], ORIGIN
        )

        self.assertNotIn(ConceptKind.AMENITY_REFERENCE, [c.kind for c in concepts])

    def test_amenity_reference_orders_by_score_descending(self):
        equipped = candidate(
            name="設備充実", provider_page_url="https://example.invalid/equipped", amenity_score=3
        )
        plain = candidate(
            name="設備なし", provider_page_url="https://example.invalid/plain", amenity_score=0
        )

        concepts = build_concepts([plain, equipped], ORIGIN)

        amenity = next(c for c in concepts if c.kind is ConceptKind.AMENITY_REFERENCE)
        self.assertEqual([c.name for c in amenity.candidates], ["設備充実", "設備なし"])

    def test_concepts_are_returned_in_a_fixed_priority_order(self):
        equipped = candidate(
            provider_page_url="https://example.invalid/a",
            total_seats=10,
            amenity_score=1,
            genre="和食",
        )
        other = candidate(
            provider_page_url="https://example.invalid/b",
            total_seats=5,
            amenity_score=1,
            genre="洋食",
        )

        concepts = build_concepts([equipped, other], ORIGIN)

        self.assertEqual(
            [c.kind for c in concepts],
            [
                ConceptKind.PROXIMITY,
                ConceptKind.CAPACITY_REFERENCE,
                ConceptKind.AMENITY_REFERENCE,
            ],
        )


class SelectInitialTests(SimpleTestCase):
    def test_no_concepts_selects_nothing(self):
        self.assertIsNone(select_initial([]))

    def test_first_concept_in_priority_order_is_selected(self):
        concepts = build_concepts([candidate()], ORIGIN)

        self.assertEqual(select_initial(concepts).kind, ConceptKind.PROXIMITY)


class ReproposalOptionsTests(SimpleTestCase):
    def test_displayed_kind_is_excluded(self):
        concepts = build_concepts(
            [candidate(provider_page_url="https://example.invalid/a", total_seats=1)], ORIGIN
        )

        options = reproposal_options(concepts, ConceptKind.PROXIMITY)

        self.assertNotIn(ConceptKind.PROXIMITY, [option.kind for option in options])

    def test_offers_at_most_three_options(self):
        candidates = [
            candidate(
                provider_page_url=f"https://example.invalid/{i}",
                genre=str(i),
                total_seats=i,
                amenity_score=1,
            )
            for i in range(1, 4)
        ]
        concepts = build_concepts(candidates, ORIGIN)

        options = reproposal_options(concepts, None)

        self.assertLessEqual(len(options), 3)

    def test_all_four_buildable_kinds_never_exceed_the_three_option_cap(self):
        # adr/0016 decision 4: with GENRE_VARIETY removed, ConceptKind has
        # four members, so "every kind except the displayed one" is always
        # at most three -- unlike the pre-adr/0016 five-kind shape, where
        # IZAKAYA_BAR_INCLUDED could be silently dropped by maxItems: 3
        # (FR-010). Build candidates that make all four kinds explainable
        # (a total-seat value, an amenity signal, and an excluded-genre
        # candidate alongside a default-population one) and assert none of
        # the three non-displayed kinds is missing.
        candidates = [
            candidate(
                name="和食",
                provider_page_url="https://example.invalid/soba",
                genre="和食",
                total_seats=10,
                amenity_score=1,
            ),
            candidate(
                name="居酒屋",
                provider_page_url="https://example.invalid/izakaya",
                genre="居酒屋",
                total_seats=20,
            ),
        ]

        concepts = build_concepts(candidates, ORIGIN)
        self.assertEqual(
            {c.kind for c in concepts},
            {
                ConceptKind.PROXIMITY,
                ConceptKind.CAPACITY_REFERENCE,
                ConceptKind.AMENITY_REFERENCE,
                ConceptKind.IZAKAYA_BAR_INCLUDED,
            },
        )

        options = reproposal_options(concepts, ConceptKind.PROXIMITY)

        self.assertEqual(len(options), 3)
        self.assertEqual(
            {option.kind for option in options},
            {
                ConceptKind.CAPACITY_REFERENCE,
                ConceptKind.AMENITY_REFERENCE,
                ConceptKind.IZAKAYA_BAR_INCLUDED,
            },
        )


class SelectReproposalTests(SimpleTestCase):
    def test_selects_the_matching_buildable_concept(self):
        concepts = build_concepts(
            [candidate(provider_page_url="https://example.invalid/a", total_seats=1)], ORIGIN
        )

        selected = select_reproposal(concepts, ConceptKind.CAPACITY_REFERENCE)

        self.assertEqual(selected.kind, ConceptKind.CAPACITY_REFERENCE)

    def test_raises_for_an_unbuildable_kind(self):
        concepts = build_concepts(
            [candidate(provider_page_url="https://example.invalid/a", amenity_score=0)], ORIGIN
        )

        with self.assertRaises(ReproposalKindUnavailableError):
            select_reproposal(concepts, ConceptKind.AMENITY_REFERENCE)

    def test_requesting_the_currently_displayed_kind_returns_it_again(self):
        # adr/0016 decision 2-3: a same-lens "try again" request resends
        # proposal.kind as reproposalKind. This is not a new code path --
        # select_reproposal already looks up any requested kind from the
        # freshly built concepts, whether or not it matches what was
        # previously displayed, since the server holds no memory of it.
        concepts = build_concepts(
            [candidate(provider_page_url="https://example.invalid/a")], ORIGIN
        )
        displayed = select_initial(concepts)

        selected = select_reproposal(concepts, displayed.kind)

        self.assertEqual(selected.kind, displayed.kind)
        self.assertEqual(selected, displayed)


# adr/0015 decision 2-3: default genre exclusion and IZAKAYA_BAR_INCLUDED.
class DefaultGenreExclusionTests(SimpleTestCase):
    def test_confirmed_excluded_genres_are_exactly_two(self):
        # Locks the confirmed-member set itself (adr/0015 decision 3) so an
        # accidental addition/removal is caught here rather than only through
        # its behavioural effects below.
        self.assertEqual(DEFAULT_EXCLUDED_GENRES, {"居酒屋", "ダイニングバー・バル"})

    def test_default_excluded_genre_candidate_is_absent_from_every_default_population_concept(
        self,
    ):
        izakaya = candidate(
            name="除外対象",
            genre="居酒屋",
            provider_page_url="https://example.invalid/izakaya",
            total_seats=99,
            amenity_score=1,
        )
        soba = candidate(
            name="非除外",
            provider_page_url="https://example.invalid/soba",
            genre="和食",
            total_seats=10,
        )
        udon = candidate(
            name="非除外2",
            provider_page_url="https://example.invalid/udon",
            genre="洋食",
            total_seats=20,
        )

        concepts = build_concepts([izakaya, soba, udon], ORIGIN)

        for concept in concepts:
            if concept.kind is ConceptKind.IZAKAYA_BAR_INCLUDED:
                continue
            self.assertNotIn(
                "除外対象",
                [c.name for c in concept.candidates],
                f"{concept.kind} must exclude the default-excluded-genre candidate",
            )

    def test_the_other_confirmed_excluded_genre_is_also_excluded(self):
        bar = candidate(
            name="バー",
            genre="ダイニングバー・バル",
            provider_page_url="https://example.invalid/bar",
        )
        soba = candidate(
            name="そば", genre="和食", provider_page_url="https://example.invalid/soba"
        )

        concepts = build_concepts([bar, soba], ORIGIN)

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)
        self.assertEqual([c.name for c in proximity.candidates], ["そば"])

    def test_izakaya_bar_included_is_absent_without_any_excluded_genre_candidate(self):
        concepts = build_concepts([candidate()], ORIGIN)

        self.assertNotIn(ConceptKind.IZAKAYA_BAR_INCLUDED, [c.kind for c in concepts])

    def test_izakaya_bar_included_ranks_the_full_population_by_proximity(self):
        near_izakaya = candidate(
            name="近い居酒屋",
            genre="居酒屋",
            provider_page_url="https://example.invalid/near-izakaya",
            latitude=0.001,
        )
        far_soba = candidate(
            name="遠いそば",
            genre="和食",
            provider_page_url="https://example.invalid/far-soba",
            latitude=0.05,
        )

        concepts = build_concepts([far_soba, near_izakaya], ORIGIN)

        izakaya_bar_included = next(
            c for c in concepts if c.kind is ConceptKind.IZAKAYA_BAR_INCLUDED
        )
        self.assertEqual(
            [c.name for c in izakaya_bar_included.candidates], ["近い居酒屋", "遠いそば"]
        )

    def test_izakaya_bar_included_title_matches_the_scenario_wording(self):
        izakaya = candidate(genre="居酒屋", provider_page_url="https://example.invalid/izakaya")

        concepts = build_concepts([izakaya], ORIGIN)

        izakaya_bar_included = next(
            c for c in concepts if c.kind is ConceptKind.IZAKAYA_BAR_INCLUDED
        )
        self.assertEqual(izakaya_bar_included.title, "居酒屋・バーを含めて探す")

    def test_izakaya_bar_included_rationale_does_not_assert_confirmed_lunch_service(self):
        izakaya = candidate(genre="居酒屋", provider_page_url="https://example.invalid/izakaya")

        concepts = build_concepts([izakaya], ORIGIN)

        izakaya_bar_included = next(
            c for c in concepts if c.kind is ConceptKind.IZAKAYA_BAR_INCLUDED
        )
        # TDR-CS-09's "含めた店舗が実際にランチ営業していると断定しない": the
        # rationale must state the inclusion decision without claiming lunch
        # service is confirmed to happen.
        self.assertIn("とは限らない", izakaya_bar_included.rationale)
        self.assertNotIn("ランチ営業しています", izakaya_bar_included.rationale)

    def test_excluding_the_default_population_falls_through_to_izakaya_bar_included_alone(self):
        """TDR-CS-10: when every default-population concept is unbuildable."""
        izakaya = candidate(genre="居酒屋", provider_page_url="https://example.invalid/izakaya")
        bar = candidate(
            genre="ダイニングバー・バル", provider_page_url="https://example.invalid/bar"
        )

        concepts = build_concepts([izakaya, bar], ORIGIN)

        self.assertEqual([c.kind for c in concepts], [ConceptKind.IZAKAYA_BAR_INCLUDED])
        self.assertEqual(select_initial(concepts).kind, ConceptKind.IZAKAYA_BAR_INCLUDED)
        self.assertEqual(reproposal_options(concepts, ConceptKind.IZAKAYA_BAR_INCLUDED), [])

    def test_izakaya_bar_included_is_offered_as_a_reproposal_option(self):
        izakaya = candidate(genre="居酒屋", provider_page_url="https://example.invalid/izakaya")
        soba = candidate(genre="和食", provider_page_url="https://example.invalid/soba")

        concepts = build_concepts([izakaya, soba], ORIGIN)

        options = reproposal_options(concepts, ConceptKind.PROXIMITY)

        self.assertIn(ConceptKind.IZAKAYA_BAR_INCLUDED, [option.kind for option in options])

    def test_select_reproposal_for_izakaya_bar_included_raises_when_unavailable(self):
        concepts = build_concepts([candidate()], ORIGIN)

        with self.assertRaises(ReproposalKindUnavailableError):
            select_reproposal(concepts, ConceptKind.IZAKAYA_BAR_INCLUDED)

    def test_select_reproposal_for_izakaya_bar_included_includes_the_excluded_candidate(self):
        izakaya = candidate(
            name="含まれる店", genre="居酒屋", provider_page_url="https://example.invalid/izakaya"
        )
        soba = candidate(genre="和食", provider_page_url="https://example.invalid/soba")

        concepts = build_concepts([izakaya, soba], ORIGIN)
        selected = select_reproposal(concepts, ConceptKind.IZAKAYA_BAR_INCLUDED)

        self.assertIn("含まれる店", [c.name for c in selected.candidates])


# adr/0015 decision 1: 5-candidate display cap, applied after ranking.
class DisplayCapTests(SimpleTestCase):
    def _many_candidates(self, count, *, genre="和食"):
        return [
            candidate(
                name=f"店{i}",
                genre=genre,
                provider_page_url=f"https://example.invalid/many-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, count + 1)
        ]

    def test_a_concept_with_more_than_five_candidates_is_capped_to_the_five_nearest(self):
        concepts = build_concepts(self._many_candidates(7), ORIGIN)

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)

        self.assertEqual(len(proximity.candidates), 5)
        self.assertEqual(
            [c.name for c in proximity.candidates], ["店1", "店2", "店3", "店4", "店5"]
        )

    def test_a_concept_with_exactly_five_candidates_is_not_truncated(self):
        concepts = build_concepts(self._many_candidates(5), ORIGIN)

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)

        self.assertEqual(len(proximity.candidates), 5)

    def test_a_concept_with_fewer_than_five_candidates_is_unaffected(self):
        concepts = build_concepts(self._many_candidates(3), ORIGIN)

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)

        self.assertEqual(len(proximity.candidates), 3)

    def test_the_cap_ranks_over_the_full_population_before_truncating(self):
        # If the cap ran before ranking, a candidate placed 6th in insertion
        # order would be truncated away before ranking ever saw it, even
        # though it ranks 1st by total seats. Ranking the full six-candidate
        # population first, then capping to 5, must keep it.
        low_seats = [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/many-{i}",
                total_seats=10 - i,
            )
            for i in range(1, 6)
        ]
        highest_seats_last_in_order = candidate(
            name="満席店",
            provider_page_url="https://example.invalid/many-highest",
            total_seats=100,
        )

        concepts = build_concepts([*low_seats, highest_seats_last_in_order], ORIGIN)

        capacity = next(c for c in concepts if c.kind is ConceptKind.CAPACITY_REFERENCE)
        self.assertEqual(len(capacity.candidates), 5)
        self.assertEqual(capacity.candidates[0].name, "満席店")


# adr/0017 decision 2: server-side repeat demotion, applied after ranking and
# before the adr/0015 display cap. This replaces the browser-side algorithm
# ADR-0008 decision 2 previously specified.
class RepeatDemotionTests(SimpleTestCase):
    def _ordered_candidates(self, count):
        return [
            candidate(
                name=f"店{i}",
                provider_page_url=f"https://example.invalid/order-{i}",
                latitude=0.001 * i,
            )
            for i in range(1, count + 1)
        ]

    def test_no_previously_shown_urls_leaves_ranking_unaffected(self):
        candidates = self._ordered_candidates(3)

        without_argument = build_concepts(candidates, ORIGIN)
        with_empty_list = build_concepts(candidates, ORIGIN, [])

        proximity_without = next(c for c in without_argument if c.kind is ConceptKind.PROXIMITY)
        proximity_with_empty = next(c for c in with_empty_list if c.kind is ConceptKind.PROXIMITY)
        expected_order = ["店1", "店2", "店3"]
        self.assertEqual([c.name for c in proximity_without.candidates], expected_order)
        self.assertEqual([c.name for c in proximity_with_empty.candidates], expected_order)

    def test_previously_shown_urls_not_matching_any_candidate_has_no_effect(self):
        candidates = self._ordered_candidates(3)

        concepts = build_concepts(candidates, ORIGIN, ["https://example.invalid/no-such-candidate"])

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)
        self.assertEqual([c.name for c in proximity.candidates], ["店1", "店2", "店3"])

    def test_previously_shown_candidate_is_demoted_to_the_end_but_not_excluded(self):
        candidates = self._ordered_candidates(3)

        concepts = build_concepts(candidates, ORIGIN, ["https://example.invalid/order-1"])

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)
        # 店1 ranked nearest (1st); once named as previously shown it moves
        # behind every unseen candidate but is still present, not excluded.
        self.assertEqual([c.name for c in proximity.candidates], ["店2", "店3", "店1"])

    def test_relative_order_is_preserved_within_each_of_the_two_demoted_groups(self):
        candidates = self._ordered_candidates(5)

        concepts = build_concepts(
            candidates,
            ORIGIN,
            [
                "https://example.invalid/order-1",
                "https://example.invalid/order-3",
            ],
        )

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)
        # Unseen (店2, 店4, 店5) keep their ranked relative order and precede
        # the demoted pair (店1, 店3), which also keeps its ranked relative
        # order among itself -- a stable partition, not a re-ranking.
        self.assertEqual(
            [c.name for c in proximity.candidates], ["店2", "店4", "店5", "店1", "店3"]
        )

    def test_demotion_runs_before_the_display_cap_so_an_unseen_candidate_is_promoted(self):
        # Six candidates exceed the adr/0015 5-item display cap. Naming the
        # five nearest as previously shown must let the sixth (otherwise
        # truncated away before ranking-order alone would ever show it)
        # appear in the capped, displayed set ahead of every repeat --
        # exactly the defect adr/0017 fixes (the browser-only version of
        # this mechanism never received the sixth candidate at all).
        candidates = self._ordered_candidates(6)
        previously_shown = [f"https://example.invalid/order-{i}" for i in range(1, 6)]

        concepts = build_concepts(candidates, ORIGIN, previously_shown)

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)
        self.assertEqual(len(proximity.candidates), 5)
        self.assertEqual(proximity.candidates[0].name, "店6")
        self.assertEqual(
            {c.name for c in proximity.candidates[1:]},
            {"店1", "店2", "店3", "店4"},
            "the cap should keep the one unseen candidate plus four of the five repeats",
        )

    def test_demotion_applies_independently_per_concept_kind(self):
        # AMENITY_REFERENCE ranks by amenity_score descending, the opposite
        # order from PROXIMITY's ranking by distance here, so the same
        # previously-shown URL demotes a different candidate's position in
        # each concept -- demotion must run against each concept's own
        # ranked order, not a single shared order.
        near_low_amenity = candidate(
            name="近いが設備少",
            provider_page_url="https://example.invalid/near-low",
            latitude=0.001,
            amenity_score=1,
        )
        far_high_amenity = candidate(
            name="遠いが設備充実",
            provider_page_url="https://example.invalid/far-high",
            latitude=0.002,
            amenity_score=3,
        )

        concepts = build_concepts(
            [near_low_amenity, far_high_amenity],
            ORIGIN,
            ["https://example.invalid/near-low"],
        )

        proximity = next(c for c in concepts if c.kind is ConceptKind.PROXIMITY)
        amenity = next(c for c in concepts if c.kind is ConceptKind.AMENITY_REFERENCE)
        # PROXIMITY ranks near_low_amenity first; demoting it moves it behind
        # far_high_amenity.
        self.assertEqual([c.name for c in proximity.candidates], ["遠いが設備充実", "近いが設備少"])
        # AMENITY_REFERENCE already ranks far_high_amenity first on its own
        # criterion, so demoting near_low_amenity (already last) is a no-op
        # on this concept's visible order.
        self.assertEqual([c.name for c in amenity.candidates], ["遠いが設備充実", "近いが設備少"])


class RealisticLargeMultiGenrePopulationShapeTests(SimpleTestCase):
    """Characterizes the real Hot Pepper production shape orchestrator measured
    and reported for adr/0015 §9 (candidate/genre.md): 64 candidates across 11
    genres, every candidate carrying a ``totalSeats`` value in [11, 200], with
    the deployed screen's displayed lens being ``PROXIMITY``. The real
    incident that prompted this reproduction was an empty ``reProposalOptions``
    for that state.

    This test is a synthetic reproduction of that shape only (ADR-0002
    decision 7 forbids a live credentialed call from this repository); it
    does not reproduce the real request/response sequence. Building concepts
    from this shape here yields non-empty re-proposal options (two, after
    adr/0016 removed GENRE_VARIETY -- this shape's own repeated review is
    part of what led to that removal), so this exact candidate shape alone
    does not explain an empty ``reProposalOptions``. It does not rule out
    the other named possibility
    (ADR-0008 decision 2: each request is an independent fresh provider
    search, so the request that produced the empty result may have returned a
    different, unmeasured shape) -- that possibility is outside what a
    synthetic unit test can observe or falsify.
    """

    _GENRE_COUNTS = {
        "居酒屋": 24,
        "和食": 9,
        "カフェ・スイーツ": 7,
        "中華": 7,
        "ラーメン": 4,
        "イタリアン・フレンチ": 4,
        "洋食": 3,
        "焼肉・ホルモン": 2,
        "ダイニングバー・バル": 2,
        "創作料理": 1,
        "お好み焼き・もんじゃ": 1,
    }
    _SEAT_VALUES = [11, 20, 35, 50, 65, 80, 95, 110, 130, 150, 170, 200]

    def _shaped_population(self):
        candidates = []
        index = 0
        for genre, count in self._GENRE_COUNTS.items():
            for _ in range(count):
                index += 1
                candidates.append(
                    candidate(
                        name=f"実測形状候補{index}",
                        genre=genre,
                        provider_page_url=f"https://example.invalid/realistic-{index}",
                        latitude=0.0001 * index,
                        total_seats=self._SEAT_VALUES[index % len(self._SEAT_VALUES)],
                    )
                )
        self.assertEqual(len(candidates), 64)
        self.assertEqual(len({c.provider_page_url for c in candidates}), 64)
        return candidates

    def test_reproposal_options_are_not_empty_for_this_shape(self):
        concepts = build_concepts(self._shaped_population(), ORIGIN)
        displayed = select_initial(concepts)

        self.assertIsNotNone(displayed)
        self.assertEqual(displayed.kind, ConceptKind.PROXIMITY)

        options = reproposal_options(concepts, displayed.kind)

        # adr/0016: GENRE_VARIETY no longer exists, so this real-data shape
        # (which previously built it as a redundant duplicate of PROXIMITY,
        # per adr/0016's own real-device finding) now yields two options
        # instead of three -- AMENITY_REFERENCE stays unbuildable here since
        # this synthetic shape carries no amenity signal.
        self.assertEqual(
            {option.kind for option in options},
            {
                ConceptKind.CAPACITY_REFERENCE,
                ConceptKind.IZAKAYA_BAR_INCLUDED,
            },
        )
