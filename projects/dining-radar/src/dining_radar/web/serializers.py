"""Builds the ``CandidateProposalResponse`` JSON shape.

Field names and nesting mirror ``contracts/candidate-search-api.yaml``
exactly (``additionalProperties: false``): no extra key is ever added.

Per adr/0023, the response is no longer a single ``proposal`` concept plus
``reProposalOptions``: it is a flat ``candidates`` array (already filtered,
ordered, and randomly sampled by ``dining_radar.recommendation.pipeline``),
``izakayaBarFallbackApplied``, and ``availableGenres``.

Per ADR-0019 decision 4, this module originally derived ``capacityTier`` from
``totalSeats`` itself (it never participates in filtering or ordering, so
`dining_radar.recommendation.pipeline` had no reason to compute it). That
threshold mapping now lives in
``dining_radar.recommendation.pipeline.capacity_tier`` instead (developer
discretion, not a contract change) because ``dining_radar.gathering`` also
needs the identical coarse vocabulary for its own
``OpenShopPreviewItem.capacityTier``; see that function's own docstring.
``dinnerBudgetTier`` (adr/0019 decision 8, adr/0023 decision 10) is likewise
computed by ``dining_radar.recommendation.pipeline.dinner_budget_tier``
instead of being duplicated here, because ``recommendation`` also needs that
same coarse tier for ``budgetTiers`` filtering and ordering (adr/0023 decision
3): keeping every threshold mapping in one place is what keeps every caller
from silently disagreeing.
"""

from __future__ import annotations

from dining_radar.recommendation.pipeline import (
    NormalizedCandidate,
    Origin,
    PopulationAttribute,
    capacity_tier,
    dinner_budget_tier,
    walking_time_minutes,
)
from dining_radar.suggestions.service import ProposalResult

PROVIDER_CREDIT = {
    "text": "Powered by ホットペッパーグルメ Webサービス",
    "url": "http://webservice.recruit.co.jp/",
}


def serialize_candidate(candidate: NormalizedCandidate, index: int, origin: Origin) -> dict:
    return {
        "candidateRef": f"candidate-{index}",
        "name": candidate.name,
        "genre": candidate.genre,
        "description": candidate.description,
        "regularHoliday": candidate.regular_holiday,
        "totalSeats": candidate.total_seats,
        "capacityTier": capacity_tier(candidate.total_seats),
        "nonSmokingStatus": candidate.non_smoking_status,
        "cardPaymentAvailable": candidate.card_payment_available,
        "dinnerBudgetTier": dinner_budget_tier(candidate.budget_average),
        "location": {"latitude": candidate.latitude, "longitude": candidate.longitude},
        "providerPageUrl": candidate.provider_page_url,
        # adr/0025 decision 2: derived from `origin` and this candidate's own
        # location by dining_radar.recommendation.pipeline (the single source
        # of truth for the calculation), never computed here -- see that
        # module's walking_time_minutes for the estimate/rounding rationale.
        "walkingTimeMinutes": walking_time_minutes(origin, candidate),
    }


def serialize_population_attribute(attribute: PopulationAttribute) -> dict:
    """One identity-free population row (see ``PopulationAttribute``).

    Deliberately carries no name, provider page URL, or coordinates: the
    browser uses these only to count how many candidates a pending filter
    selection would match, never to render a shop. ``walkingTimeBand``
    (adr/0025 decision 3) is the one deliberate, coarse exception to that
    "no location attribute" rule -- see ``PopulationAttribute`` for why it is
    safe.
    """
    return {
        "genre": attribute.genre,
        "nonSmokingStatus": attribute.non_smoking_status,
        "cardPaymentAvailable": attribute.card_payment_available,
        "dinnerBudgetTier": attribute.dinner_budget_tier,
        "defaultExcluded": attribute.default_excluded,
        "walkingTimeBand": attribute.walking_time_band,
    }


def serialize_search_origin(origin: Origin) -> dict:
    """The ``SearchOriginLocation`` shape (adr/0025 decision 1).

    Carries only the origin's own coordinates -- never the configured search
    range/radius, a route, or the browser's current location.
    """
    return {"latitude": origin.latitude, "longitude": origin.longitude}


def serialize_result(result: ProposalResult) -> dict:
    return {
        "candidates": [
            serialize_candidate(candidate, index, result.search_origin)
            for index, candidate in enumerate(result.candidates)
        ],
        "izakayaBarFallbackApplied": result.izakaya_bar_fallback_applied,
        "availableGenres": list(result.available_genres),
        "populationAttributes": [
            serialize_population_attribute(attribute) for attribute in result.population_attributes
        ],
        "providerCredit": PROVIDER_CREDIT,
        "searchOrigin": serialize_search_origin(result.search_origin),
        # adr/0024 decision 4: true only when this response's selection drew
        # from the full eligible population because every eligible candidate
        # was already present in the request's shownProviderPageUrls.
        "shownPoolExhausted": result.shown_pool_exhausted,
    }
