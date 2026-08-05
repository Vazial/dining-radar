from django.test import SimpleTestCase

from dining_radar.recommendation.pipeline import (
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
    business_hours="11:00-14:00",
    regular_holiday="日曜",
    access="アクセス情報",
):
    return NormalizedCandidate(
        name=name,
        genre=genre,
        description=description,
        business_hours=business_hours,
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

    def test_genre_variety_is_absent_with_a_single_genre(self):
        concepts = build_concepts(
            [
                candidate(provider_page_url="https://example.invalid/a", genre="和食"),
                candidate(provider_page_url="https://example.invalid/b", genre="和食"),
            ],
            ORIGIN,
        )

        self.assertNotIn(ConceptKind.GENRE_VARIETY, [c.kind for c in concepts])

    def test_genre_variety_interleaves_distinct_genres_to_the_front(self):
        japanese_1 = candidate(
            name="和食1", provider_page_url="https://example.invalid/j1", genre="和食"
        )
        japanese_2 = candidate(
            name="和食2", provider_page_url="https://example.invalid/j2", genre="和食"
        )
        western = candidate(
            name="洋食1", provider_page_url="https://example.invalid/w1", genre="洋食"
        )

        concepts = build_concepts([japanese_1, japanese_2, western], ORIGIN)

        genre_variety = next(c for c in concepts if c.kind is ConceptKind.GENRE_VARIETY)
        self.assertEqual([c.name for c in genre_variety.candidates], ["和食1", "洋食1", "和食2"])

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
                ConceptKind.GENRE_VARIETY,
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
