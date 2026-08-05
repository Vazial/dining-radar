"""Builds the ``CandidateProposalResponse`` JSON shape.

Field names and nesting mirror ``contracts/candidate-search-api.yaml``
exactly (``additionalProperties: false``): no extra key is ever added.
"""

from __future__ import annotations

from dining_radar.recommendation.pipeline import Concept, NormalizedCandidate, ReproposalOption
from dining_radar.suggestions.service import ProposalResult

PROVIDER_CREDIT = {
    "text": "Powered by ホットペッパーグルメ Webサービス",
    "url": "http://webservice.recruit.co.jp/",
}


def serialize_candidate(candidate: NormalizedCandidate, index: int) -> dict:
    return {
        "candidateRef": f"candidate-{index}",
        "name": candidate.name,
        "genre": candidate.genre,
        "description": candidate.description,
        "businessHours": candidate.business_hours,
        "regularHoliday": candidate.regular_holiday,
        "totalSeats": candidate.total_seats,
        "access": candidate.access,
        "location": {"latitude": candidate.latitude, "longitude": candidate.longitude},
        "providerPageUrl": candidate.provider_page_url,
    }


def serialize_concept(concept: Concept) -> dict:
    return {
        "conceptRef": f"concept-{concept.kind.value.lower()}",
        "kind": concept.kind.value,
        "title": concept.title,
        "rationale": concept.rationale,
        "candidates": [
            serialize_candidate(candidate, index)
            for index, candidate in enumerate(concept.candidates)
        ],
    }


def serialize_reproposal_option(option: ReproposalOption) -> dict:
    return {"kind": option.kind.value, "title": option.title, "rationale": option.rationale}


def serialize_result(result: ProposalResult) -> dict:
    return {
        "proposal": serialize_concept(result.proposal) if result.proposal is not None else None,
        "reProposalOptions": [
            serialize_reproposal_option(option) for option in result.reproposal_options
        ],
        "providerCredit": PROVIDER_CREDIT,
    }
