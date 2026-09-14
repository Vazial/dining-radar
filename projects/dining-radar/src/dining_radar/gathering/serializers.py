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
    Origin,
    capacity_tier,
    dinner_budget_tier,
    walking_time_minutes,
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
    # Gated on votingStartedAt (not on the shortlisted-shops tally list
    # itself, adr/0048) -- the tally list's own tie-break now needs
    # shop_lookup/origin to sort by distance, so resolving them can no
    # longer wait until after the tallies are computed. votingStartedAt
    # non-null and shortlistedShops non-empty are the same condition (see
    # that field's own schema description), so this mirrors
    # serialize_participant_view's identical gate.
    voting_started = gathering.voting_started_at is not None
    # Resolved once per request and reused for every shortlisted shop's
    # display fields (adr/0044's location/walkingTimeMinutes/providerPageUrl)
    # rather than triggering one real provider fetch per shop.
    population_source = services.resolve_population_source() if voting_started else None
    origin = population_source[1] if population_source is not None else None
    shop_lookup = (
        services.shop_lookup_for_gathering(gathering, population_source) if voting_started else {}
    )
    shortlisted_tallies = services.shortlisted_shops_with_tallies(gathering, shop_lookup, origin)
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
            serialize_shortlisted_shop(tally, shop_lookup, origin) for tally in shortlisted_tallies
        ],
        "finalizedShopId": gathering.finalized_shop_id,
    }


def participant_link_url(request: HttpRequest, link: ParticipantLink) -> str:
    """The full same-origin participant URL (``IssuedParticipantLink.url``)."""
    path = reverse("gathering:participant-answer", kwargs={"token": link.token})
    return request.build_absolute_uri(path)


def serialize_issued_participant_link(request: HttpRequest, link: ParticipantLink) -> dict:
    return {"token": link.token, "url": participant_link_url(request, link)}


def serialize_participant_link_summary(
    link: ParticipantLink, schedule_responses: Sequence[tuple[object, str]] = ()
) -> dict:
    """``ParticipantLinkSummary`` (ADR-0036 decision 7, ``scheduleResponses`` added
    ADR-0056 decision 1, 2026-09-12 human decision).

    ``schedule_responses`` is a sequence of ``(candidate_date_id, status)``
    pairs -- callers pass the entry for this specific link out of
    ``services.participant_link_schedule_responses``'s whole-gathering
    mapping (one query for every link, not one per link). Organizer-only:
    this function's output is never reused for ``ParticipantView`` (the
    participant-facing schema), which has no field this value could occupy.
    """
    return {
        "id": str(link.id),
        "issuedAt": link.issued_at.isoformat(),
        "hasResponded": link.has_responded,
        "revoked": link.revoked,
        "displayName": link.display_name,
        "scheduleResponses": [
            {"candidateDateId": str(candidate_date_id), "status": status}
            for candidate_date_id, status in schedule_responses
        ],
    }


def _candidate_display_fields(candidate: NormalizedCandidate, origin: Origin) -> dict:
    """The 9 display fields shared by ``OpenShopPreviewItem``/``LiveProjectedShop``/etc.

    A single source for this mapping (ADR-0034 decision 6's live-projection
    fields) so ``OpenShopPreviewItem``, ``LiveProjectedShop``,
    ``ShortlistedShop``, and ``ParticipantShopVoteOption`` never repeat it.
    ``shopId`` is ``candidate.provider_page_url`` -- the same natural,
    already-unique shop identity this codebase already uses elsewhere (e.g.
    ``dining_radar.recommendation.pipeline._dedupe``); adr/0042 added this
    field to ``OpenShopPreviewItem`` so a browser can correlate a previewed
    row with the id it later submits to ``setShortlistedShops``.
    ``location``/``walkingTimeMinutes``/``providerPageUrl`` were added
    2026-09-04 (adr/0044, human decision: show the same map/detail
    information the lunch-candidate screen shows) -- computed live from
    ``origin`` and this candidate's own coordinates on every read, the same
    calculation ``dining_radar.web.serializers.serialize_candidate`` uses
    for ``candidate-search-api.yaml``'s own ``Candidate`` schema, never
    persisted.
    """
    return {
        "shopId": candidate.provider_page_url,
        "name": candidate.name,
        "genre": candidate.genre,
        "capacityTier": capacity_tier(candidate.total_seats),
        "nonSmokingStatus": candidate.non_smoking_status,
        "dinnerBudgetTier": dinner_budget_tier(candidate.budget_average),
        "location": {"latitude": candidate.latitude, "longitude": candidate.longitude},
        "walkingTimeMinutes": walking_time_minutes(origin, candidate),
        "providerPageUrl": candidate.provider_page_url,
    }


def _live_projected_display_fields(
    candidate: NormalizedCandidate | None, shop_id: str, origin: Origin | None
) -> dict:
    """Same 9 fields as ``_candidate_display_fields``, tolerant of a missing lookup.

    ``candidate`` is ``None`` when ``shop_id`` is no longer present in a
    fresh refetch of the confirmed candidate date's open-shop population, or
    when the private population source itself could not be resolved at all
    (a provider outage) -- ``origin`` is then also ``None`` (ADR-0034
    decision 6 never persists these fields, so a shop's live attributes --
    or its continued presence at all -- can change between when it was
    shortlisted/voted on and a later read). No TDR-GTH scenario exercises
    this path and this contract does not define its shape; developer
    discretion (FR-028, reported not resolved): fall back to the opaque
    shop id itself for the required, non-nullable ``name``/``genre``/
    ``providerPageUrl`` fields (``shop_id`` *is* the shop's own
    ``provider_page_url`` by construction -- see
    ``_candidate_display_fields`` above -- so reusing it for
    ``providerPageUrl`` is not a fabrication, unlike a guessed location
    would be) and to ``null`` for every already-nullable tier/status field,
    mirroring this codebase's existing "確認できないことを断定しない"
    convention for an unconfirmed attribute. ``location``/
    ``walkingTimeMinutes`` are, unlike those fields, required and
    non-nullable in the contract's schema -- there is no honest non-null
    value for an unresolvable shop's real position, so this fallback uses
    an explicit, clearly-not-a-real-address sentinel (0, 0 -- 'null
    island', off the coast of west Africa, nowhere near any real search
    origin this product configures) rather than a value a reader could
    mistake for a genuine estimate.
    """
    if candidate is not None and origin is not None:
        return _candidate_display_fields(candidate, origin)
    return {
        "shopId": shop_id,
        "name": shop_id,
        "genre": "",
        "capacityTier": None,
        "nonSmokingStatus": None,
        "dinnerBudgetTier": None,
        "location": {"latitude": 0.0, "longitude": 0.0},
        "walkingTimeMinutes": 0,
        "providerPageUrl": shop_id,
    }


def serialize_live_projected_shop(shop_id: str, shop_lookup: dict, origin: Origin | None) -> dict:
    """``components.schemas.LiveProjectedShop`` (adr/0041, extended by adr/0044)."""
    return _live_projected_display_fields(shop_lookup.get(shop_id), shop_id, origin)


def serialize_shortlisted_shop(
    tally: services.ShortlistedShopTally, shop_lookup: dict, origin: Origin | None
) -> dict:
    """``components.schemas.ShortlistedShop`` (adr/0040, three-tier tallies adr/0044)."""
    shop = tally.shortlisted_shop
    return {
        **_live_projected_display_fields(shop_lookup.get(shop.shop_id), shop.shop_id, origin),
        "addedAt": shop.added_at.isoformat(),
        "wantToGoCount": tally.want_to_go_count,
        "okToGoCount": tally.ok_to_go_count,
        "notGoingCount": tally.not_going_count,
        "respondedParticipantCount": tally.responded_participant_count,
    }


def serialize_participant_shop_vote_option(
    option: services.ParticipantShopVoteOption, shop_lookup: dict, origin: Origin | None
) -> dict:
    """``components.schemas.ParticipantShopVoteOption`` (adr/0040, three-tier adr/0044)."""
    shop = option.shortlisted_shop
    entry = {
        **_live_projected_display_fields(shop_lookup.get(shop.shop_id), shop.shop_id, origin),
        "yourVote": option.your_vote,
        # Added 2026-09-13 (ADR-0056 decision 6, addendum 9): server-computed
        # boolean mirroring the organizer-facing
        # data-added-after-voting-started signal -- addedAt/votingStartedAt
        # themselves are never exposed to this unauthenticated, signed-link
        # participant (see services.ParticipantShopVoteOption's own
        # docstring).
        "addedAfterVotingStarted": option.added_after_voting_started,
    }
    # Always present (adr/0050 decision 2, 2026-09-08/09 human decision:
    # reverses this schema's original "answer first, then see others" gating
    # on ``option.your_vote`` -- other participants' tallies are visible
    # whether or not this participant has voted on this shop yet).
    entry["tally"] = {
        "wantToGoCount": option.want_to_go_count,
        "okToGoCount": option.ok_to_go_count,
        "notGoingCount": option.not_going_count,
        "respondedParticipantCount": option.responded_participant_count,
    }
    return entry


def serialize_search_origin(origin: Origin) -> dict:
    """``components.schemas.SearchOriginLocation`` (adr/0044/adr/0045).

    Mirrors ``dining_radar.web.serializers.serialize_search_origin`` exactly
    (same shape, same "coordinates only, never the configured search range"
    discipline) -- kept as a separate copy here rather than imported, the
    same "no shared-module system" precedent this codebase already
    establishes for its other small, single-purpose helpers.
    """
    return {"latitude": origin.latitude, "longitude": origin.longitude}


def serialize_open_shop_preview(
    candidate_date: CandidateDate, population: Sequence[NormalizedCandidate], origin: Origin | None
) -> dict:
    """``CandidateDateOpenShopPreview`` (adr/0049 decision 2: count-only).

    ``previewShops``/``OpenShopPreviewItem`` were both retired 2026-09-09 --
    shop selection moved to ``candidate-search-api.yaml``'s gathering mode
    (adr/0049 decision 1), so no screen browses a shop list from this
    operation any longer. ``origin`` is accepted (unused) so this function's
    signature stays stable against ``services.preview_open_shops_for_
    candidate_date``'s own return shape, which callers still use for other
    purposes.
    """
    del origin
    return {
        "candidateDateId": str(candidate_date.id),
        "openShopCount": len(population),
    }


def serialize_schedule_question(link: ParticipantLink, tally: services.CandidateDateTally) -> dict:
    """``ParticipantScheduleQuestion``.

    No longer carries ``openShopCount`` -- removed 2026-09-12 (ADR-0055
    decision 1, human decision: a shop count did not help a participant
    decide on a candidate date and only added to the screen's information
    volume). The organizer-facing equivalent,
    ``CandidateDateOpenShopPreview.openShopCount``
    (``serialize_open_shop_preview`` above), is unchanged by this removal.
    """
    candidate_date = tally.candidate_date
    your_response = services.participant_schedule_status(link, candidate_date)
    return {
        "candidateDateId": str(candidate_date.id),
        "startAt": candidate_date.start_at.isoformat(),
        "yourResponse": your_response,
        # Always present (adr/0050 decision 2, 2026-09-08/09 human decision:
        # reverses this schema's original "answer first, then see others"
        # gating on ``your_response`` -- other participants' counts are
        # visible whether or not this participant has answered yet).
        "tally": {
            "goingCount": tally.going_count,
            "maybeCount": tally.maybe_count,
            "notGoingCount": tally.not_going_count,
        },
    }


def serialize_decision(
    link: ParticipantLink, gathering: Gathering, shop_lookup: dict, origin: Origin | None
) -> dict:
    """``ParticipantView.decision`` (adr/0040, extended by P5/adr/0041, simplified adr/0050).

    Carries only this participant's own retrospective schedule answer
    (``yourScheduleResponse``) -- never another participant's answers or
    votes (adr/0041 decision 3). ``yourShopVotes`` (the per-shop
    retrospective P5 added, generalized to the three-tier vote by adr/0044,
    extended to never-answered shops by adr/0046) was retired 2026-09-09
    (adr/0050 decision 3, human decision: "あなたの回答は見れても別に意味
    ないかも") -- a participant can still see every shop's live tally via
    ``shopVoteQuestions`` (unaffected by finalization, adr/0050 decision 2).
    """
    your_schedule_response = (
        services.participant_schedule_status(link, gathering.confirmed_candidate_date)
        if gathering.confirmed_candidate_date_id
        else None
    )
    return {
        "confirmedCandidateDate": gathering.confirmed_candidate_date.start_at.isoformat(),
        "shop": serialize_live_projected_shop(gathering.finalized_shop_id, shop_lookup, origin),
        "yourScheduleResponse": your_schedule_response,
    }


def serialize_participant_view(link: ParticipantLink) -> dict:
    gathering = link.gathering
    tallies = services.candidate_dates_with_tallies(gathering)
    voting_started = gathering.voting_started_at is not None
    # Resolved once per request and reused for every candidate date and every
    # shop lookup, rather than triggering one real provider fetch per
    # gathering-schedule-question/shop-vote-question (see
    # resolve_population_source's own docstring). Only needed once voting has
    # started -- shopVoteQuestions/searchOrigin (gated below by
    # voting_started) and decision (gated by FINALIZED, which
    # set_shortlisted_shops/finalize_gathering guarantee only reaches after
    # voting_started_at is set -- finalize_gathering requires a non-empty
    # shortlist, and the only place that populates one also sets
    # voting_started_at) are the only readers. Before voting starts this
    # would otherwise trigger a real provider fetch on every schedule-answer
    # PUT (and the initial GET), gated exactly like serialize_gathering's own
    # identical population_source resolution above.
    population_source = services.resolve_population_source() if voting_started else None
    origin = population_source[1] if population_source is not None else None
    shop_lookup = (
        services.shop_lookup_for_gathering(gathering, population_source) if voting_started else {}
    )
    shop_vote_questions = (
        [
            serialize_participant_shop_vote_option(option, shop_lookup, origin)
            for option in services.participant_shop_vote_options(link, shop_lookup, origin)
        ]
        if voting_started
        else None
    )
    # ParticipantView.searchOrigin (adr/0044/adr/0045): non-null under the
    # same gating as shopVoteQuestions -- present once voting has started,
    # extending ADR-0025 decision 1's authenticated-organizer-screen
    # disclosure to this unauthenticated, signed-link screen. Falls back to
    # null (schema-legal, nullable: true) on the same rare provider-outage
    # edge case openShopCount/shop_lookup already fall back for.
    search_origin = (
        serialize_search_origin(origin) if voting_started and origin is not None else None
    )
    decision = (
        serialize_decision(link, gathering, shop_lookup, origin)
        if gathering.phase == GatheringPhase.FINALIZED
        else None
    )
    return {
        "gatheringTitle": gathering.title,
        "phase": gathering.phase,
        "displayName": link.display_name,
        # Added 2026-09-12 (ADR-0056 decision 9, human decision): sizes a
        # participant's own vote-tally bar against the whole invited group,
        # not the count of respondents seen so far. Present unconditionally,
        # in every phase (ADR-0056 未決事項4 -- whether to gate this by phase
        # is left open, so this contract does not gate it).
        "totalActiveParticipantCount": gathering.active_participant_link_count,
        "scheduleQuestions": [serialize_schedule_question(link, tally) for tally in tallies],
        "confirmedCandidateDate": (
            gathering.confirmed_candidate_date.start_at.isoformat()
            if gathering.confirmed_candidate_date_id
            else None
        ),
        "shopVoteQuestions": shop_vote_questions,
        "searchOrigin": search_origin,
        "decision": decision,
    }
