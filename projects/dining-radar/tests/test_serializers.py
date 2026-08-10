from django.test import SimpleTestCase

from dining_radar.recommendation.pipeline import NormalizedCandidate
from dining_radar.suggestions.service import ProposalResult
from dining_radar.web.serializers import serialize_result


def _candidate(**overrides):
    defaults = dict(
        name="架空食堂",
        genre="和食",
        description=None,
        regular_holiday="日曜",
        total_seats=None,
        non_smoking_status=None,
        card_payment_available=None,
        budget_average=None,
        latitude=35.0,
        longitude=139.0,
        provider_page_url="https://example.invalid/shop",
    )
    defaults.update(overrides)
    return NormalizedCandidate(**defaults)


class SerializeResultTests(SimpleTestCase):
    def test_empty_candidates_serializes_with_fixed_credit(self):
        result = ProposalResult((), False, ())

        payload = serialize_result(result)

        self.assertEqual(payload["candidates"], [])
        self.assertFalse(payload["izakayaBarFallbackApplied"])
        self.assertEqual(payload["availableGenres"], [])
        self.assertEqual(
            payload["providerCredit"],
            {
                "text": "Powered by ホットペッパーグルメ Webサービス",
                "url": "http://webservice.recruit.co.jp/",
            },
        )

    def test_candidate_fields_and_nullable_handling_are_preserved(self):
        candidate = _candidate(description=None, total_seats=None)
        result = ProposalResult((candidate,), False, ("和食",))

        payload = serialize_result(result)

        serialized_candidate = payload["candidates"][0]
        self.assertEqual(serialized_candidate["name"], "架空食堂")
        self.assertIsNone(serialized_candidate["description"])
        self.assertIsNone(serialized_candidate["totalSeats"])
        self.assertIsNone(serialized_candidate["capacityTier"])
        self.assertIsNone(serialized_candidate["nonSmokingStatus"])
        self.assertIsNone(serialized_candidate["cardPaymentAvailable"])
        self.assertIsNone(serialized_candidate["dinnerBudgetTier"])
        self.assertEqual(serialized_candidate["location"], {"latitude": 35.0, "longitude": 139.0})
        # adr/0020: the response no longer has a proposal/reProposalOptions
        # wrapper -- these keys must never appear.
        self.assertNotIn("businessHours", serialized_candidate)
        self.assertNotIn("access", serialized_candidate)
        self.assertEqual(payload["availableGenres"], ["和食"])

    def test_candidate_refs_are_unique_within_one_response(self):
        candidates = (
            _candidate(provider_page_url="https://example.invalid/a"),
            _candidate(provider_page_url="https://example.invalid/b"),
        )
        result = ProposalResult(candidates, False, ())

        payload = serialize_result(result)

        refs = [candidate["candidateRef"] for candidate in payload["candidates"]]
        self.assertEqual(len(refs), len(set(refs)))

    def test_izakaya_bar_fallback_applied_is_passed_through(self):
        result = ProposalResult((), True, ())

        payload = serialize_result(result)

        self.assertTrue(payload["izakayaBarFallbackApplied"])

    def test_response_has_exactly_the_contract_shape(self):
        result = ProposalResult((_candidate(),), False, ())

        payload = serialize_result(result)

        self.assertEqual(
            set(payload),
            {
                "candidates",
                "izakayaBarFallbackApplied",
                "availableGenres",
                "populationAttributes",
                "providerCredit",
            },
        )
        self.assertEqual(
            set(payload["candidates"][0]),
            {
                "candidateRef",
                "name",
                "genre",
                "description",
                "regularHoliday",
                "totalSeats",
                "capacityTier",
                "nonSmokingStatus",
                "cardPaymentAvailable",
                "dinnerBudgetTier",
                "location",
                "providerPageUrl",
            },
        )


class CapacityTierTests(SimpleTestCase):
    """adr/0019 decision 4: coarse seating-scale reference derived from totalSeats."""

    def _serialize_one(self, total_seats):
        candidate = _candidate(total_seats=total_seats)
        payload = serialize_result(ProposalResult((candidate,), False, ()))
        return payload["candidates"][0]

    def test_null_total_seats_is_a_null_capacity_tier(self):
        self.assertIsNone(self._serialize_one(None)["capacityTier"])

    def test_twenty_seats_or_fewer_is_small(self):
        self.assertEqual(self._serialize_one(20)["capacityTier"], "SMALL")

    def test_twenty_one_to_sixty_seats_is_medium(self):
        self.assertEqual(self._serialize_one(21)["capacityTier"], "MEDIUM")
        self.assertEqual(self._serialize_one(60)["capacityTier"], "MEDIUM")

    def test_sixty_one_seats_or_more_is_large(self):
        self.assertEqual(self._serialize_one(61)["capacityTier"], "LARGE")

    def test_visible_capacity_tier_wording_never_mentions_reservation_ease(self):
        for tier in ("SMALL", "MEDIUM", "LARGE"):
            self.assertNotIn("予約", tier)


class DinnerBudgetTierTests(SimpleTestCase):
    """adr/0019 decision 8 / adr/0020 decision 10: coarse dinner-price-range reference."""

    def _serialize_one(self, budget_average):
        candidate = _candidate(budget_average=budget_average)
        payload = serialize_result(ProposalResult((candidate,), False, ()))
        return payload["candidates"][0]

    def test_null_budget_average_is_a_null_dinner_budget_tier(self):
        self.assertIsNone(self._serialize_one(None)["dinnerBudgetTier"])

    def test_two_thousand_yen_or_less_is_low(self):
        self.assertEqual(self._serialize_one(2000.0)["dinnerBudgetTier"], "LOW")

    def test_two_thousand_one_to_four_thousand_yen_is_mid(self):
        self.assertEqual(self._serialize_one(2001.0)["dinnerBudgetTier"], "MID")
        self.assertEqual(self._serialize_one(4000.0)["dinnerBudgetTier"], "MID")

    def test_over_four_thousand_yen_is_high(self):
        self.assertEqual(self._serialize_one(4001.0)["dinnerBudgetTier"], "HIGH")


class PassThroughFieldTests(SimpleTestCase):
    def test_non_smoking_status_is_passed_through_unchanged(self):
        candidate = _candidate(non_smoking_status="PARTIAL")

        payload = serialize_result(ProposalResult((candidate,), False, ()))

        self.assertEqual(payload["candidates"][0]["nonSmokingStatus"], "PARTIAL")

    def test_card_payment_available_false_is_passed_through_unchanged(self):
        candidate = _candidate(card_payment_available=False)

        payload = serialize_result(ProposalResult((candidate,), False, ()))

        self.assertIs(payload["candidates"][0]["cardPaymentAvailable"], False)

    def test_card_payment_available_true_is_passed_through_unchanged(self):
        candidate = _candidate(card_payment_available=True)

        payload = serialize_result(ProposalResult((candidate,), False, ()))

        self.assertIs(payload["candidates"][0]["cardPaymentAvailable"], True)
