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
from .models import CandidateDate, Gathering, GatheringPhase, ParticipantLink


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
    shortlisted_tallies = services.shortlisted_shops_with_tallies(gathering)
    shop_lookup = services.shop_lookup_for_gathering(gathering) if shortlisted_tallies else {}
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
        "votingStartedAt": (
            gathering.voting_started_at.isoformat() if gathering.voting_started_at else None
        ),
        "shortlistedShops": [
            serialize_shortlisted_shop(tally, shop_lookup) for tally in shortlisted_tallies
        ],
        "finalizedShopId": gathering.finalized_shop_id,
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


def _candidate_display_fields(candidate: NormalizedCandidate) -> dict:
    """The 6 display fields shared by ``OpenShopPreviewItem``/``LiveProjectedShop``/etc.

    A single source for this mapping (ADR-0034 decision 6's live-projection
    fields) so ``OpenShopPreviewItem``, ``LiveProjectedShop``,
    ``ShortlistedShop``, and ``ParticipantShopVoteOption`` never repeat it.
    ``shopId`` is ``candidate.provider_page_url`` -- the same natural,
    already-unique shop identity this codebase already uses elsewhere (e.g.
    ``dining_radar.recommendation.pipeline._dedupe``); adr/0042 added this
    field to ``OpenShopPreviewItem`` so a browser can correlate a previewed
    row with the id it later submits to ``setShortlistedShops``.
    """
    return {
        "shopId": candidate.provider_page_url,
        "name": candidate.name,
        "genre": candidate.genre,
        "capacityTier": capacity_tier(candidate.total_seats),
        "nonSmokingStatus": candidate.non_smoking_status,
        "dinnerBudgetTier": dinner_budget_tier(candidate.budget_average),
    }


def _live_projected_display_fields(candidate: NormalizedCandidate | None, shop_id: str) -> dict:
    """Same 6 fields as ``_candidate_display_fields``, tolerant of a missing lookup.

    ``candidate`` is ``None`` when ``shop_id`` is no longer present in a
    fresh refetch of the confirmed candidate date's open-shop population
    (ADR-0034 decision 6 never persists these fields, so a shop's live
    attributes -- or its continued presence at all -- can change between
    when it was shortlisted/voted on and a later read). No TDR-GTH scenario
    exercises this path and this contract does not define its shape;
    developer discretion (FR-028, reported not resolved): fall back to the
    opaque shop id itself for the required, non-nullable `name`/`genre`
    fields (an honest "this shop's live attributes could not be confirmed
    just now", not a fabricated guess) and to `null` for every already-
    nullable tier/status field, mirroring this codebase's existing
    "確認できないことを断定しない" convention for an unconfirmed attribute.
    """
    if candidate is not None:
        return _candidate_display_fields(candidate)
    return {
        "shopId": shop_id,
        "name": shop_id,
        "genre": "",
        "capacityTier": None,
        "nonSmokingStatus": None,
        "dinnerBudgetTier": None,
    }


def serialize_open_shop_preview_item(candidate: NormalizedCandidate) -> dict:
    return _candidate_display_fields(candidate)


def serialize_live_projected_shop(shop_id: str, shop_lookup: dict) -> dict:
    """``components.schemas.LiveProjectedShop`` (adr/0041)."""
    return _live_projected_display_fields(shop_lookup.get(shop_id), shop_id)


def serialize_shortlisted_shop(tally: services.ShortlistedShopTally, shop_lookup: dict) -> dict:
    """``components.schemas.ShortlistedShop`` (adr/0040)."""
    shop = tally.shortlisted_shop
    return {
        **_live_projected_display_fields(shop_lookup.get(shop.shop_id), shop.shop_id),
        "addedAt": shop.added_at.isoformat(),
        "approvalCount": tally.approval_count,
        "respondedParticipantCount": tally.responded_participant_count,
    }


def serialize_participant_shop_vote_option(
    option: services.ParticipantShopVoteOption, shop_lookup: dict
) -> dict:
    """``components.schemas.ParticipantShopVoteOption`` (adr/0040)."""
    shop = option.shortlisted_shop
    entry = {
        **_live_projected_display_fields(shop_lookup.get(shop.shop_id), shop.shop_id),
        "yourApproval": option.your_approval,
    }
    entry["tally"] = (
        None
        if option.your_approval is None
        else {
            "approvalCount": option.approval_count,
            "respondedParticipantCount": option.responded_participant_count,
        }
    )
    return entry


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


def serialize_decision(link: ParticipantLink, gathering: Gathering, shop_lookup: dict) -> dict:
    """``ParticipantView.decision`` (adr/0040, extended by P5/adr/0041).

    Never another participant's answers or votes -- both new fields are
    derived solely from this participant's own recorded data
    (``scheduleQuestions``/``shopVoteQuestions``), never a tally or another
    participant's identifier (adr/0041 decision 3).
    """
    your_schedule_response = (
        services.participant_schedule_status(link, gathering.confirmed_candidate_date)
        if gathering.confirmed_candidate_date_id
        else None
    )
    your_approved_shops = [
        serialize_live_projected_shop(option.shortlisted_shop.shop_id, shop_lookup)
        for option in services.participant_shop_vote_options(link)
        if option.your_approval is True
    ]
    return {
        "confirmedCandidateDate": gathering.confirmed_candidate_date.start_at.isoformat(),
        "shop": serialize_live_projected_shop(gathering.finalized_shop_id, shop_lookup),
        "yourScheduleResponse": your_schedule_response,
        "yourApprovedShops": your_approved_shops,
    }


def serialize_participant_view(link: ParticipantLink) -> dict:
    gathering = link.gathering
    tallies = services.candidate_dates_with_tallies(gathering)
    # Resolved once per request and reused for every candidate date and every
    # shop lookup, rather than triggering one real provider fetch per
    # gathering-schedule-question/shop-vote-question (see
    # resolve_population_source's own docstring).
    population_source = services.resolve_population_source()
    voting_started = gathering.voting_started_at is not None
    shop_lookup = (
        services.shop_lookup_for_gathering(gathering, population_source) if voting_started else {}
    )
    shop_vote_questions = (
        [
            serialize_participant_shop_vote_option(option, shop_lookup)
            for option in services.participant_shop_vote_options(link)
        ]
        if voting_started
        else None
    )
    decision = (
        serialize_decision(link, gathering, shop_lookup)
        if gathering.phase == GatheringPhase.FINALIZED
        else None
    )
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
        "shopVoteQuestions": shop_vote_questions,
        "decision": decision,
    }
