from django.test import SimpleTestCase

from dining_radar.recommendation.pipeline import (
    Concept,
    ConceptKind,
    NormalizedCandidate,
    ReproposalOption,
)
from dining_radar.suggestions.service import ProposalResult
from dining_radar.web.serializers import serialize_result


def _candidate(**overrides):
    defaults = dict(
        name="架空食堂",
        genre="和食",
        description=None,
        business_hours="11:00-14:00",
        regular_holiday="日曜",
        total_seats=None,
        access="架空アクセス",
        latitude=35.0,
        longitude=139.0,
        provider_page_url="https://example.invalid/shop",
    )
    defaults.update(overrides)
    return NormalizedCandidate(**defaults)


class SerializeResultTests(SimpleTestCase):
    def test_null_proposal_serializes_to_null_with_fixed_credit(self):
        result = ProposalResult(None, [])

        payload = serialize_result(result)

        self.assertIsNone(payload["proposal"])
        self.assertEqual(payload["reProposalOptions"], [])
        self.assertEqual(
            payload["providerCredit"],
            {
                "text": "Powered by ホットペッパーグルメ Webサービス",
                "url": "http://webservice.recruit.co.jp/",
            },
        )

    def test_candidate_fields_and_nullable_handling_are_preserved(self):
        candidate = _candidate(description=None, total_seats=None)
        concept = Concept(ConceptKind.PROXIMITY, "近さを優先する", "理由", (candidate,))
        result = ProposalResult(
            concept, [ReproposalOption(ConceptKind.GENRE_VARIETY, "変化", "理由2")]
        )

        payload = serialize_result(result)

        serialized_candidate = payload["proposal"]["candidates"][0]
        self.assertEqual(serialized_candidate["name"], "架空食堂")
        self.assertIsNone(serialized_candidate["description"])
        self.assertIsNone(serialized_candidate["totalSeats"])
        self.assertEqual(serialized_candidate["location"], {"latitude": 35.0, "longitude": 139.0})
        self.assertEqual(payload["proposal"]["kind"], "PROXIMITY")
        self.assertEqual(
            payload["reProposalOptions"],
            [{"kind": "GENRE_VARIETY", "title": "変化", "rationale": "理由2"}],
        )

    def test_candidate_refs_are_unique_within_one_response(self):
        candidates = (
            _candidate(provider_page_url="https://example.invalid/a"),
            _candidate(provider_page_url="https://example.invalid/b"),
        )
        concept = Concept(ConceptKind.PROXIMITY, "近さを優先する", "理由", candidates)
        result = ProposalResult(concept, [])

        payload = serialize_result(result)

        refs = [candidate["candidateRef"] for candidate in payload["proposal"]["candidates"]]
        self.assertEqual(len(refs), len(set(refs)))
