"""Business logic for gathering-scheduling-api.yaml.

Per ``ARCHITECTURE.md``'s module boundary table (extended here the same way
``dining_radar.web`` is bounded), this module -- not
``dining_radar.gathering.views`` -- owns every phase-transition rule,
denominator computation, and access check, so the view layer stays a thin
request/response translation (mirroring ``dining_radar.web.views``'s own
division of labor with ``dining_radar.suggestions``/``dining_radar
.recommendation``). Every exception below names exactly one
``ProblemResponse.code`` this contract defines; ``dining_radar.gathering
.views`` maps each to its documented HTTP status.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from dining_radar.recommendation.pipeline import NormalizedCandidate, Origin, open_shop_population
from dining_radar.suggestions import acceptance_state
from dining_radar.suggestions.errors import CandidateSourceUnavailableError
from dining_radar.suggestions.hotpepper_source import fetch_real_candidates

from . import tokens
from .models import (
    CandidateDate,
    Gathering,
    GatheringPhase,
    ParticipantLink,
    ScheduleResponse,
    ScheduleResponseStatus,
)

# adr/0035 decision 4: "有効期限90日" -- a deliberately weakly-justified value
# (ADR-0035's own words), recorded once here at issuance time (ParticipantLink
# .expires_at) so a later change to this constant never retroactively changes
# an already-issued link's own expiry.
PARTICIPANT_LINK_VALIDITY_DAYS = 90

# CandidateDateOpenShopPreview.previewShops: "maxItems: 10" (a nearest-first
# subset for organizer preview only; openShopCount is the authoritative
# total, not derived by counting this capped list).
OPEN_SHOP_PREVIEW_MAX_ITEMS = 10

# Distinguishes "no source argument supplied" (resolve one) from an
# explicitly passed ``None`` ("resolution already failed upstream; do not
# retry the provider fetch") in `open_shop_population_for_candidate_date`.
_SENTINEL = object()


class GatheringNotFoundError(Exception):
    """``GATHERING_NOT_FOUND``: no gathering exists, or it belongs to another organizer."""


class CandidateDateNotFoundError(Exception):
    """``CANDIDATE_DATE_NOT_FOUND``: no candidate date exists for this gathering."""


class GatheringNotInSchedulingPhaseError(Exception):
    """``GATHERING_NOT_IN_SCHEDULING_PHASE``: the operation requires SCHEDULING."""


class DuplicateCandidateDateError(Exception):
    """``DUPLICATE_CANDIDATE_DATE`` (adr/0038): this exact ``startAt`` already exists here.

    Raised by ``create_gathering`` when two or more entries in the same
    request share an exact ``startAt``, and by ``add_candidate_date`` when
    the new ``startAt`` exactly matches a candidate date already persisted
    on this gathering. This is architect's own design judgment (adr/0038
    header comment), not one of the 2026-09-01 human decisions.
    """


class ParticipantLinkNotFoundError(Exception):
    """``PARTICIPANT_LINK_NOT_FOUND``: no organizer-facing linkId exists here."""


class ParticipantLinkAlreadyAnsweredError(Exception):
    """``PARTICIPANT_LINK_ALREADY_ANSWERED``: revocation requires zero responses."""


class ParticipantLinkRevokedError(Exception):
    """``PARTICIPANT_LINK_REVOKED``: re-copying an already-revoked link is refused."""


class LinkNotFoundError(Exception):
    """``LINK_NOT_FOUND``: the token does not correspond to any issued link."""


class LinkExpiredError(Exception):
    """``LINK_EXPIRED``: the token's validity period has passed."""


class LinkRevokedError(Exception):
    """``LINK_REVOKED``: the organizer has revoked this token."""


class LinkRateLimitedError(Exception):
    """``LINK_RATE_LIMITED``: this token exceeded the allowed request frequency."""


class GatheringFinalizedError(Exception):
    """``GATHERING_FINALIZED``: no further schedule response is accepted."""


def _get_owned_gathering(organizer: AbstractBaseUser, gathering_id: object) -> Gathering:
    try:
        return Gathering.objects.get(id=gathering_id, organizer=organizer)
    except (Gathering.DoesNotExist, ValueError, TypeError) as error:
        raise GatheringNotFoundError from error


def _get_candidate_date(gathering: Gathering, candidate_date_id: object) -> CandidateDate:
    try:
        return gathering.candidate_dates.get(id=candidate_date_id)
    except (CandidateDate.DoesNotExist, ValueError, TypeError) as error:
        raise CandidateDateNotFoundError from error


def _get_participant_link(gathering: Gathering, link_id: object) -> ParticipantLink:
    try:
        return gathering.participant_links.get(id=link_id)
    except (ParticipantLink.DoesNotExist, ValueError, TypeError) as error:
        raise ParticipantLinkNotFoundError from error


def create_gathering(
    organizer: AbstractBaseUser, title: str, candidate_date_start_ats: Sequence[datetime]
) -> Gathering:
    """``createGathering``: a gathering always starts in SCHEDULING with >=1 date.

    Raises ``DuplicateCandidateDateError`` (adr/0038) if
    ``candidate_date_start_ats`` itself contains two entries sharing the
    exact same instant -- checked before any row is written, so a rejected
    request never creates a partial gathering. Aware-datetime equality
    already normalizes across timezone offsets representing the same
    instant, matching ``startAt``'s own "exact same date-time" wording.
    """
    if len(set(candidate_date_start_ats)) != len(candidate_date_start_ats):
        raise DuplicateCandidateDateError
    with transaction.atomic():
        gathering = Gathering.objects.create(organizer=organizer, title=title)
        CandidateDate.objects.bulk_create(
            CandidateDate(gathering=gathering, start_at=start_at)
            for start_at in candidate_date_start_ats
        )
    return gathering


def get_gathering(organizer: AbstractBaseUser, gathering_id: object) -> Gathering:
    """``getGathering``."""
    return _get_owned_gathering(organizer, gathering_id)


def list_gatherings(organizer: AbstractBaseUser) -> list[Gathering]:
    """``listGatherings`` (adr/0038): every gathering this organizer organizes, createdAt降順.

    Includes every phase, including FINALIZED -- there is no delete
    operation (ADR-0035 decision 1's D4).
    """
    return list(Gathering.objects.filter(organizer=organizer).order_by("-created_at"))


def count_in_progress_gatherings(organizer: AbstractBaseUser) -> int:
    """``getInProgressGatheringCount`` (adr/0038): SCHEDULING/SELECTING_SHOP only.

    FINALIZED is excluded -- its business is done (designer's judgment,
    carried into the contract).
    """
    return Gathering.objects.filter(
        organizer=organizer,
        phase__in=(GatheringPhase.SCHEDULING, GatheringPhase.SELECTING_SHOP),
    ).count()


def add_candidate_date(
    organizer: AbstractBaseUser, gathering_id: object, start_at: datetime
) -> tuple[Gathering, CandidateDate]:
    """``addCandidateDate``: only accepted while phase is SCHEDULING.

    Raises ``DuplicateCandidateDateError`` (adr/0038) if ``start_at``
    exactly matches a candidate date already persisted on this gathering.
    """
    gathering = _get_owned_gathering(organizer, gathering_id)
    if gathering.phase != GatheringPhase.SCHEDULING:
        raise GatheringNotInSchedulingPhaseError
    if gathering.candidate_dates.filter(start_at=start_at).exists():
        raise DuplicateCandidateDateError
    candidate_date = CandidateDate.objects.create(gathering=gathering, start_at=start_at)
    return gathering, candidate_date


def confirm_candidate_date(
    organizer: AbstractBaseUser, gathering_id: object, candidate_date_id: object
) -> Gathering:
    """``confirmCandidateDate`` ("この日にする"): SCHEDULING -> SELECTING_SHOP."""
    gathering = _get_owned_gathering(organizer, gathering_id)
    if gathering.phase != GatheringPhase.SCHEDULING:
        raise GatheringNotInSchedulingPhaseError
    candidate_date = _get_candidate_date(gathering, candidate_date_id)
    gathering.phase = GatheringPhase.SELECTING_SHOP
    gathering.confirmed_candidate_date = candidate_date
    gathering.save(update_fields=["phase", "confirmed_candidate_date"])
    return gathering


def issue_participant_links(
    organizer: AbstractBaseUser, gathering_id: object, count: int
) -> tuple[Gathering, list[ParticipantLink]]:
    """``issueParticipantLinks``: issue ``count`` new, distinct tokens."""
    gathering = _get_owned_gathering(organizer, gathering_id)
    issued_at = timezone.now()
    expires_at = issued_at + timedelta(days=PARTICIPANT_LINK_VALIDITY_DAYS)
    with transaction.atomic():
        links = ParticipantLink.objects.bulk_create(
            ParticipantLink(
                gathering=gathering,
                token=tokens.generate_participant_token(),
                expires_at=expires_at,
            )
            for _ in range(count)
        )
        gathering.total_issued_participant_links += count
        gathering.save(update_fields=["total_issued_participant_links"])
    return gathering, links


def list_participant_links(
    organizer: AbstractBaseUser, gathering_id: object
) -> tuple[Gathering, list[ParticipantLink]]:
    """``listParticipantLinks``: every link issued for this gathering, 発行順."""
    gathering = _get_owned_gathering(organizer, gathering_id)
    return gathering, list(gathering.participant_links.all())


def recopy_participant_link(
    organizer: AbstractBaseUser, gathering_id: object, link_id: object
) -> ParticipantLink:
    """``recopyParticipantLink``: re-obtain the same token/URL, unless revoked."""
    gathering = _get_owned_gathering(organizer, gathering_id)
    link = _get_participant_link(gathering, link_id)
    if link.revoked:
        raise ParticipantLinkRevokedError
    return link


def revoke_participant_link(
    organizer: AbstractBaseUser, gathering_id: object, link_id: object
) -> tuple[Gathering, ParticipantLink]:
    """``revokeParticipantLink``: only accepted while ``hasResponded`` is false."""
    gathering = _get_owned_gathering(organizer, gathering_id)
    link = _get_participant_link(gathering, link_id)
    if link.has_responded:
        raise ParticipantLinkAlreadyAnsweredError
    if not link.revoked:
        with transaction.atomic():
            link.revoked = True
            link.save(update_fields=["revoked"])
            gathering.total_revoked_participant_links += 1
            gathering.save(update_fields=["total_revoked_participant_links"])
    return gathering, link


@dataclass(frozen=True)
class CandidateDateTally:
    """One ``CandidateDate`` plus its GOING/MAYBE/NOT_GOING counts."""

    candidate_date: CandidateDate
    going_count: int
    maybe_count: int
    not_going_count: int


def candidate_dates_with_tallies(gathering: Gathering) -> list[CandidateDateTally]:
    """``Gathering.candidateDates``, ordered goingCount descending.

    The tie-break (implementation-chosen, the contract does not fix one) is
    creation order: ``Gathering.candidate_dates`` is already ordered by
    ``created_at`` ascending (``CandidateDate.Meta.ordering``), and Python's
    ``list.sort`` is stable (including under ``reverse=True``), so members
    tied on ``going_count`` keep that creation order.
    """
    candidate_dates = list(gathering.candidate_dates.all())
    counts: dict[uuid.UUID, Counter] = defaultdict(Counter)
    responses = ScheduleResponse.objects.filter(candidate_date__gathering=gathering).values_list(
        "candidate_date_id", "status"
    )
    for candidate_date_id, status in responses:
        counts[candidate_date_id][status] += 1

    tallies = [
        CandidateDateTally(
            candidate_date=candidate_date,
            going_count=counts[candidate_date.id][ScheduleResponseStatus.GOING],
            maybe_count=counts[candidate_date.id][ScheduleResponseStatus.MAYBE],
            not_going_count=counts[candidate_date.id][ScheduleResponseStatus.NOT_GOING],
        )
        for candidate_date in candidate_dates
    ]
    tallies.sort(key=lambda tally: tally.going_count, reverse=True)
    return tallies


def response_summary(gathering: Gathering) -> tuple[int, int]:
    """``(respondedParticipantCount, anonymousRespondedParticipantCount)``.

    A participant slot counts as "responded" once it has submitted at least
    one schedule response for *any* candidate date (product-brief.md §2);
    this is a different denominator from any single ``CandidateDate``'s own
    tally. A revoked link is never counted here by construction --
    ``revoke_participant_link`` only ever succeeds while ``has_responded`` is
    false.
    """
    responded_link_ids = set(
        ScheduleResponse.objects.filter(candidate_date__gathering=gathering)
        .values_list("participant_link_id", flat=True)
        .distinct()
    )
    if not responded_link_ids:
        return 0, 0
    anonymous_count = ParticipantLink.objects.filter(
        id__in=responded_link_ids, display_name__isnull=True
    ).count()
    return len(responded_link_ids), anonymous_count


_PopulationSource = tuple[Sequence[NormalizedCandidate], Origin]


def resolve_population_source() -> _PopulationSource | None:
    """The private population every open-shop computation in a request shares.

    Reads ``acceptance_state.gathering_population_source()`` first (adr/0037
    decision 3: the acceptance seam governs this same population); outside
    the acceptance profile (or before any mode is selected within it) this
    falls back to one real production fetch, exactly like
    ``dining_radar.web.views.candidate_proposals``'s own
    ``active_mode()``-gated fallback. Callers computing more than one
    candidate date's open-shop figures in the same request (see
    ``dining_radar.gathering.serializers.serialize_participant_view``) must
    call this once and reuse the result, rather than triggering one real
    provider fetch per candidate date. ``None`` means "no population could be
    determined" (a production provider outage,
    ``CandidateSourceUnavailableError``) -- callers treat that as an empty
    population (``openShopCount=0``) rather than a request failure: this
    contract defines no error response for previewOpenShopsForCandidateDate /
    ParticipantScheduleQuestion.openShopCount beyond 401/404, so an honest
    "0 shops confirmed open right now" is a defensible filling of this
    unspecified edge case (mirrors ``dining_radar.web.views``'s own
    documented precedent for an out-of-contract failure mode), not a
    resolution of a genuine contract conflict.
    """
    source = acceptance_state.gathering_population_source()
    if source is not None:
        return source
    try:
        return fetch_real_candidates()
    except CandidateSourceUnavailableError:
        return None


def open_shop_population_for_candidate_date(
    candidate_date: CandidateDate, source: object = _SENTINEL
) -> list[NormalizedCandidate]:
    """The nearest-first, default-filtered, weekday-open population for one date.

    ``source`` defaults to a fresh ``resolve_population_source()`` call; pass
    an already-resolved source (or explicit ``None``) to avoid a repeated
    provider fetch when computing more than one candidate date in the same
    request.
    """
    if source is _SENTINEL:
        source = resolve_population_source()
    if source is None:
        return []
    candidates, origin = source
    weekday = timezone.localtime(candidate_date.start_at).weekday()
    return open_shop_population(candidates, origin, weekday)


def preview_open_shops_for_candidate_date(
    organizer: AbstractBaseUser, gathering_id: object, candidate_date_id: object
) -> tuple[CandidateDate, list[NormalizedCandidate]]:
    """``previewOpenShopsForCandidateDate``. Never advances gathering phase."""
    gathering = _get_owned_gathering(organizer, gathering_id)
    candidate_date = _get_candidate_date(gathering, candidate_date_id)
    return candidate_date, open_shop_population_for_candidate_date(candidate_date)


def _get_participant_link_by_token(token: str) -> ParticipantLink:
    try:
        return ParticipantLink.objects.select_related("gathering").get(token=token)
    except ParticipantLink.DoesNotExist as error:
        raise LinkNotFoundError from error


def _authorize_participant_link(link: ParticipantLink) -> None:
    """Raise the correct 410/429 error; consumes a pending rate-limit seed.

    Checked in this order -- revoked, then expired, then rate-limited -- so
    a token that is both revoked/expired *and* separately rate-limit-seeded
    (never produced by any single documented TDR-GTH scenario, but not
    otherwise prevented) reports the more durable state rather than
    consuming the one-shot rate-limit flag for a request that would have
    failed with 410 anyway.
    """
    if link.revoked:
        raise LinkRevokedError
    if timezone.now() >= link.expires_at:
        raise LinkExpiredError
    if link.rate_limited_once:
        link.rate_limited_once = False
        link.save(update_fields=["rate_limited_once"])
        raise LinkRateLimitedError


def get_participant_view(token: str) -> ParticipantLink:
    """``getParticipantView``."""
    link = _get_participant_link_by_token(token)
    _authorize_participant_link(link)
    return link


def set_schedule_response(token: str, candidate_date_id: object, status: str) -> ParticipantLink:
    """``setScheduleResponse``. Rejected once the gathering is FINALIZED."""
    link = _get_participant_link_by_token(token)
    _authorize_participant_link(link)
    gathering = link.gathering
    if gathering.phase == GatheringPhase.FINALIZED:
        raise GatheringFinalizedError
    candidate_date = _get_candidate_date(gathering, candidate_date_id)
    ScheduleResponse.objects.update_or_create(
        participant_link=link,
        candidate_date=candidate_date,
        defaults={"status": status},
    )
    return link


def set_participant_display_name(token: str, display_name: str) -> ParticipantLink:
    """``setParticipantDisplayName``. Never gated by gathering phase (D5)."""
    link = _get_participant_link_by_token(token)
    _authorize_participant_link(link)
    link.display_name = display_name
    link.save(update_fields=["display_name"])
    return link


def participant_schedule_status(
    link: ParticipantLink, candidate_date: CandidateDate
) -> ScheduleResponseStatus | None:
    """This participant's own recorded answer for one candidate date, or ``None``."""
    response = ScheduleResponse.objects.filter(
        participant_link=link, candidate_date=candidate_date
    ).first()
    return None if response is None else response.status


# --- test-support-api.yaml seams (acceptance-only; guarded by callers) -----


def reset_gathering_scheduling_state() -> None:
    """``resetGatheringSchedulingAcceptanceState``.

    Deletes every ``Gathering`` (cascading to its ``CandidateDate``,
    ``ParticipantLink``, and ``ScheduleResponse`` rows) created through the
    public boundary during acceptance testing. Never touches an organizer
    account, candidate-search acceptance state, or any other domain.
    """
    Gathering.objects.all().delete()


def seed_expired_participant_link(token: str) -> None:
    """``seedExpiredParticipantLink``. Rejects an unknown token like the public API would."""
    try:
        link = ParticipantLink.objects.get(token=token)
    except ParticipantLink.DoesNotExist as error:
        raise LinkNotFoundError from error
    link.expires_at = timezone.now() - timedelta(seconds=1)
    link.save(update_fields=["expires_at"])


def seed_rate_limited_participant_link(token: str) -> None:
    """``seedRateLimitedParticipantLink``. Rejects an unknown token like the public API would."""
    try:
        link = ParticipantLink.objects.get(token=token)
    except ParticipantLink.DoesNotExist as error:
        raise LinkNotFoundError from error
    link.rate_limited_once = True
    link.save(update_fields=["rate_limited_once"])
