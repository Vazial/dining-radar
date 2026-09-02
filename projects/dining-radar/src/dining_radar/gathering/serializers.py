"""Builds JSON shapes matching ``contracts/gathering-scheduling-api.yaml`` exactly.

Field names and nesting mirror the contract's schemas (each carries
``additionalProperties: false``): no extra key is ever added, mirroring
``dining_radar.web.serializers``'s own discipline.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.http import HttpRequest
from django.urls import reverse

from dining_radar.recommendation.pipeline import (
    NormalizedCandidate,
    capacity_tier,
    dinner_budget_tier,
)

from . import services
from .models import CandidateDate, Gathering, ParticipantLink


def serialize_candidate_date(tally: services.CandidateDateTally, gathering: Gathering) -> dict:
    candidate_date = tally.candidate_date
    return {
        "id": str(candidate_date.id),
        "startAt": candidate_date.start_at.isoformat(),
        "goingCount": tally.going_count,
        "maybeCount": tally.maybe_count,
        "notGoingCount": tally.not_going_count,
        "isConfirmed": gathering.confirmed_candidate_date_id == candidate_date.id,
    }


def serialize_gathering(gathering: Gathering) -> dict:
    tallies = services.candidate_dates_with_tallies(gathering)
    responded_count, anonymous_count = services.response_summary(gathering)
    return {
        "id": str(gathering.id),
        "title": gathering.title,
        "phase": gathering.phase,
        "createdAt": gathering.created_at.isoformat(),
        "candidateDates": [serialize_candidate_date(tally, gathering) for tally in tallies],
        "totalIssuedParticipantLinks": gathering.total_issued_participant_links,
        "totalRevokedParticipantLinks": gathering.total_revoked_participant_links,
        "activeParticipantLinkCount": gathering.active_participant_link_count,
        "respondedParticipantCount": responded_count,
        "anonymousRespondedParticipantCount": anonymous_count,
        "confirmedCandidateDateId": (
            str(gathering.confirmed_candidate_date_id)
            if gathering.confirmed_candidate_date_id
            else None
        ),
    }


def participant_link_url(request: HttpRequest, link: ParticipantLink) -> str:
    """The full same-origin participant URL (``IssuedParticipantLink.url``)."""
    path = reverse("gathering:participant-answer", kwargs={"token": link.token})
    return request.build_absolute_uri(path)


def serialize_issued_participant_link(request: HttpRequest, link: ParticipantLink) -> dict:
    return {"token": link.token, "url": participant_link_url(request, link)}


def serialize_participant_link_summary(link: ParticipantLink) -> dict:
    return {
        "id": str(link.id),
        "issuedAt": link.issued_at.isoformat(),
        "hasResponded": link.has_responded,
        "revoked": link.revoked,
        "displayName": link.display_name,
    }


def serialize_open_shop_preview_item(candidate: NormalizedCandidate) -> dict:
    return {
        "name": candidate.name,
        "genre": candidate.genre,
        "capacityTier": capacity_tier(candidate.total_seats),
        "nonSmokingStatus": candidate.non_smoking_status,
        "dinnerBudgetTier": dinner_budget_tier(candidate.budget_average),
    }


def serialize_open_shop_preview(
    candidate_date: CandidateDate, population: Sequence[NormalizedCandidate]
) -> dict:
    return {
        "candidateDateId": str(candidate_date.id),
        "openShopCount": len(population),
        "previewShops": [
            serialize_open_shop_preview_item(candidate)
            for candidate in population[: services.OPEN_SHOP_PREVIEW_MAX_ITEMS]
        ],
    }


def serialize_schedule_question(
    link: ParticipantLink, tally: services.CandidateDateTally, population_source: object
) -> dict:
    candidate_date = tally.candidate_date
    your_response = services.participant_schedule_status(link, candidate_date)
    open_population = services.open_shop_population_for_candidate_date(
        candidate_date, population_source
    )
    question = {
        "candidateDateId": str(candidate_date.id),
        "startAt": candidate_date.start_at.isoformat(),
        "openShopCount": len(open_population),
        "yourResponse": your_response,
    }
    if your_response is not None:
        question["tally"] = {
            "goingCount": tally.going_count,
            "maybeCount": tally.maybe_count,
            "notGoingCount": tally.not_going_count,
        }
    return question


def serialize_participant_view(link: ParticipantLink) -> dict:
    gathering = link.gathering
    tallies = services.candidate_dates_with_tallies(gathering)
    # Resolved once per request and reused for every candidate date, rather
    # than triggering one real provider fetch per
    # gathering-schedule-question (see resolve_population_source's own
    # docstring).
    population_source = services.resolve_population_source()
    return {
        "gatheringTitle": gathering.title,
        "phase": gathering.phase,
        "displayName": link.display_name,
        "scheduleQuestions": [
            serialize_schedule_question(link, tally, population_source) for tally in tallies
        ],
        "confirmedCandidateDate": (
            gathering.confirmed_candidate_date.start_at.isoformat()
            if gathering.confirmed_candidate_date_id
            else None
        ),
    }
