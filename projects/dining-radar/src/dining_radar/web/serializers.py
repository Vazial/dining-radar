"""Builds the ``CandidateProposalResponse`` JSON shape.

Field names and nesting mirror ``contracts/candidate-search-api.yaml``
exactly (``additionalProperties: false``): no extra key is ever added.

Per adr/0020, the response is no longer a single ``proposal`` concept plus
``reProposalOptions``: it is a flat ``candidates`` array (already filtered,
ordered, and randomly sampled by ``dining_radar.recommendation.pipeline``),
``izakayaBarFallbackApplied``, and ``availableGenres``.

Per ADR-0019 decision 4, this module derives ``capacityTier`` from
``totalSeats`` -- the one card-only coarse reference value that still lives
here rather than in ``recommendation`` (it never participates in filtering or
ordering, so `dining_radar.recommendation.pipeline` has no reason to compute
it). ``dinnerBudgetTier`` (adr/0019 decision 8, adr/0020 decision 10) is
computed by ``dining_radar.recommendation.pipeline.dinner_budget_tier``
instead of being duplicated here, because ``recommendation`` also needs that
same coarse tier for ``budgetTiers`` filtering and ordering (adr/0020 decision
3): keeping the threshold mapping in one place is what keeps the two from
silently disagreeing.
"""

from __future__ import annotations

from dining_radar.recommendation.pipeline import (
    NormalizedCandidate,
    PopulationAttribute,
    dinner_budget_tier,
)
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


def _capacity_tier(total_seats: int | None) -> str | None:
    if total_seats is None:
        return None
    if total_seats <= _CAPACITY_TIER_SMALL_MAX_SEATS:
        return "SMALL"
    if total_seats <= _CAPACITY_TIER_MEDIUM_MAX_SEATS:
        return "MEDIUM"
    return "LARGE"


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
        "dinnerBudgetTier": dinner_budget_tier(candidate.budget_average),
        "location": {"latitude": candidate.latitude, "longitude": candidate.longitude},
        "providerPageUrl": candidate.provider_page_url,
    }


def serialize_population_attribute(attribute: PopulationAttribute) -> dict:
    """One identity-free population row (see ``PopulationAttribute``).

    Deliberately carries no name, provider page URL, or coordinates: the
    browser uses these only to count how many candidates a pending filter
    selection would match, never to render a shop.
    """
    return {
        "genre": attribute.genre,
        "nonSmokingStatus": attribute.non_smoking_status,
        "cardPaymentAvailable": attribute.card_payment_available,
        "dinnerBudgetTier": attribute.dinner_budget_tier,
        "defaultExcluded": attribute.default_excluded,
    }


def serialize_result(result: ProposalResult) -> dict:
    return {
        "candidates": [
            serialize_candidate(candidate, index)
            for index, candidate in enumerate(result.candidates)
        ],
        "izakayaBarFallbackApplied": result.izakaya_bar_fallback_applied,
        "availableGenres": list(result.available_genres),
        "populationAttributes": [
            serialize_population_attribute(attribute) for attribute in result.population_attributes
        ],
        "providerCredit": PROVIDER_CREDIT,
    }
