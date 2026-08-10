"""Builds the ``CandidateProposalResponse`` JSON shape.

Field names and nesting mirror ``contracts/candidate-search-api.yaml``
exactly (``additionalProperties: false``): no extra key is ever added.
Per ADR-0017 decision 7, ``Candidate`` no longer includes ``businessHours``.
Per ADR-0019 decision 6, ``Candidate`` no longer includes ``access``.

Per ADR-0019 decisions 4, 8, and 10, this module derives the two card-only
coarse reference values that never participate in ranking --
``capacityTier`` from ``totalSeats`` and ``dinnerBudgetTier`` from the
provider's raw dinner-budget figure -- since neither is a ranking input for
``recommendation`` (ADR-0019 decision 10's non-binding placement
recommendation). Both threshold sets are one-time field-survey-derived
provisional values (ADR-0019 §0) kept together here, each with a comment
referencing the deciding ADR, per the same discipline
``DEFAULT_EXCLUDED_GENRES`` already follows.
"""

from __future__ import annotations

from dining_radar.recommendation.pipeline import Concept, NormalizedCandidate, ReproposalOption
from dining_radar.suggestions.service import ProposalResult

PROVIDER_CREDIT = {
    "text": "Powered by ホットペッパーグルメ Webサービス",
    "url": "http://webservice.recruit.co.jp/",
}

# adr/0019 decision 4: coarse seating-scale reference derived from totalSeats.
# Provisional thresholds from one field-survey sample (11-200 seats observed,
# median 50); do not imply reservation ease or availability.
_CAPACITY_TIER_SMALL_MAX_SEATS = 20
_CAPACITY_TIER_MEDIUM_MAX_SEATS = 60

# adr/0019 decision 8: coarse dinner-price-range reference derived from the
# provider's dinner-oriented budget figure. Provisional thresholds from the
# same one-time field survey (64 candidates, roughly balanced 18/30/16
# split). Never used to infer or imply a lunch price.
_DINNER_BUDGET_LOW_MAX_YEN = 2000
_DINNER_BUDGET_MID_MAX_YEN = 4000


def _capacity_tier(total_seats: int | None) -> str | None:
    if total_seats is None:
        return None
    if total_seats <= _CAPACITY_TIER_SMALL_MAX_SEATS:
        return "SMALL"
    if total_seats <= _CAPACITY_TIER_MEDIUM_MAX_SEATS:
        return "MEDIUM"
    return "LARGE"


def _dinner_budget_tier(budget_average: float | None) -> str | None:
    if budget_average is None:
        return None
    if budget_average <= _DINNER_BUDGET_LOW_MAX_YEN:
        return "LOW"
    if budget_average <= _DINNER_BUDGET_MID_MAX_YEN:
        return "MID"
    return "HIGH"


def serialize_candidate(candidate: NormalizedCandidate, index: int) -> dict:
    return {
        "candidateRef": f"candidate-{index}",
        "name": candidate.name,
        "genre": candidate.genre,
        "description": candidate.description,
        "regularHoliday": candidate.regular_holiday,
        "totalSeats": candidate.total_seats,
        "capacityTier": _capacity_tier(candidate.total_seats),
        "nonSmokingStatus": candidate.non_smoking_status,
        "cardPaymentAvailable": candidate.card_payment_available,
        "dinnerBudgetTier": _dinner_budget_tier(candidate.budget_average),
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
