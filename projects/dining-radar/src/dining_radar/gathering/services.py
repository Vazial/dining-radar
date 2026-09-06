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

from dining_radar.recommendation.pipeline import (
    NormalizedCandidate,
    Origin,
    distance_meters,
    open_shop_population,
)
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
    ShopVoteStatus,
    ShopVoteSubmission,
    ShortlistedShop,
)

# adr/0035 decision 4: "有効期限90日" -- a deliberately weakly-justified value
# (ADR-0035's own words), recorded once here at issuance time (ParticipantLink
# .expires_at) so a later change to this constant never retroactively changes
# an already-issued link's own expiry.
PARTICIPANT_LINK_VALIDITY_DAYS = 90

# SetShortlistedShopsRequest.shopIds: "minItems: 1, maxItems: 5" (adr/0040;
# the lower bound confirmed by human decision P2, 2026-09-03, adr/0041).
SHORTLIST_MIN_SHOPS = 1
SHORTLIST_MAX_SHOPS = 5

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


class GatheringNotInSelectingShopPhaseError(Exception):
    """``GATHERING_NOT_IN_SELECTING_SHOP_PHASE`` (adr/0040): still SCHEDULING."""


class ShopVotingNotStartedError(Exception):
    """``SHOP_VOTING_NOT_STARTED`` (adr/0040): ``shortlistedShops`` is empty."""


class InvalidShopSelectionError(Exception):
    """``INVALID_SHOP_SELECTION`` (adr/0040): the submitted shop id(s) are not valid."""


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
    """``issueParticipantLinks``: issue ``count`` new, distinct tokens.

    Rejected once the gathering is FINALIZED (adr/0040) -- reuses
    ``GatheringFinalizedError``/``GATHERING_FINALIZED`` rather than a new
    code, per explicit human instruction. Contrast with
    ``recopy_participant_link``/``revoke_participant_link`` below, which
    remain available after FINALIZED (P4, adr/0041).
    """
    gathering = _get_owned_gathering(organizer, gathering_id)
    if gathering.phase == GatheringPhase.FINALIZED:
        raise GatheringFinalizedError
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
) -> tuple[CandidateDate, list[NormalizedCandidate], Origin | None]:
    """``previewOpenShopsForCandidateDate``. Never advances gathering phase.

    Also returns the private search origin the population was computed from
    (``None`` only on a provider outage) so the caller can project each
    ``OpenShopPreviewItem.location``/``walkingTimeMinutes`` (adr/0044) --
    resolved once here and reused for every item, rather than re-resolving
    per item.
    """
    gathering = _get_owned_gathering(organizer, gathering_id)
    candidate_date = _get_candidate_date(gathering, candidate_date_id)
    source = resolve_population_source()
    population = open_shop_population_for_candidate_date(candidate_date, source)
    origin = source[1] if source is not None else None
    return candidate_date, population, origin


def shop_lookup_for_gathering(
    gathering: Gathering, source: object = _SENTINEL
) -> dict[str, NormalizedCandidate]:
    """Maps a shop id (``NormalizedCandidate.provider_page_url``) to its live entry.

    Reuses the exact same population ``previewOpenShopsForCandidateDate``
    exposed for the confirmed candidate date (adr/0040/adr/0041) -- every
    display field ``ShortlistedShop``/``ParticipantShopVoteOption``/
    ``LiveProjectedShop`` expose is refetched from this population on every
    read, never persisted (ADR-0034 decision 6). Returns an empty mapping
    while ``confirmed_candidate_date`` is unset (SCHEDULING never has a
    shortlist to look up).
    """
    if gathering.confirmed_candidate_date_id is None:
        return {}
    population = open_shop_population_for_candidate_date(gathering.confirmed_candidate_date, source)
    return {candidate.provider_page_url: candidate for candidate in population}


def set_shortlisted_shops(
    organizer: AbstractBaseUser, gathering_id: object, shop_ids: Sequence[str]
) -> Gathering:
    """``setShortlistedShops`` ("この5件で投票する"/"5件を差し替える", adr/0040).

    Replaces the entire shortlist. A shop id already present keeps its
    ``added_at`` (and therefore its vote history, D7); a newly added shop id
    starts a fresh row with ``added_at`` set to now; a shop id present
    before but absent from ``shop_ids`` is dropped entirely (re-adding it
    later is a brand-new entry -- architect design judgment, simplicity).
    Never advances ``Gathering.phase`` (FR-028, settled by P6/adr/0041) --
    only sets ``votingStartedAt`` on the first successful call.
    """
    gathering = _get_owned_gathering(organizer, gathering_id)
    if gathering.phase == GatheringPhase.SCHEDULING:
        raise GatheringNotInSelectingShopPhaseError
    if gathering.phase == GatheringPhase.FINALIZED:
        raise GatheringFinalizedError
    if not (SHORTLIST_MIN_SHOPS <= len(shop_ids) <= SHORTLIST_MAX_SHOPS):
        raise InvalidShopSelectionError
    if len(set(shop_ids)) != len(shop_ids):
        raise InvalidShopSelectionError
    population_shop_ids = {
        candidate.provider_page_url
        for candidate in open_shop_population_for_candidate_date(gathering.confirmed_candidate_date)
    }
    if not set(shop_ids) <= population_shop_ids:
        raise InvalidShopSelectionError

    now = timezone.now()
    with transaction.atomic():
        existing = {shop.shop_id: shop for shop in gathering.shortlisted_shops.all()}
        requested = set(shop_ids)
        for shop_id, shop in existing.items():
            if shop_id not in requested:
                shop.delete()
        ShortlistedShop.objects.bulk_create(
            ShortlistedShop(gathering=gathering, shop_id=shop_id, added_at=now)
            for shop_id in shop_ids
            if shop_id not in existing
        )
        if gathering.voting_started_at is None:
            gathering.voting_started_at = now
            gathering.save(update_fields=["voting_started_at"])
    return gathering


def finalize_gathering(
    organizer: AbstractBaseUser, gathering_id: object, shop_id: str
) -> Gathering:
    """``finalizeGathering`` ("日と店を確定する", adr/0040). SELECTING_SHOP -> FINALIZED.

    Never auto-selects the top-voted shop (product-brief.md §2: votes are
    material for the decision, not the decision itself) -- ``shop_id`` must
    name one of the current ``shortlistedShops``.
    """
    gathering = _get_owned_gathering(organizer, gathering_id)
    if gathering.phase == GatheringPhase.SCHEDULING:
        raise GatheringNotInSelectingShopPhaseError
    current_shop_ids = set(gathering.shortlisted_shops.values_list("shop_id", flat=True))
    if not current_shop_ids:
        raise ShopVotingNotStartedError
    if gathering.phase == GatheringPhase.FINALIZED:
        raise GatheringFinalizedError
    if shop_id not in current_shop_ids:
        raise InvalidShopSelectionError
    gathering.phase = GatheringPhase.FINALIZED
    gathering.finalized_shop_id = shop_id
    gathering.save(update_fields=["phase", "finalized_shop_id"])
    return gathering


@dataclass(frozen=True)
class ShortlistedShopTally:
    """One ``ShortlistedShop`` plus its D7 per-shop three-tier vote tallies (adr/0044)."""

    shortlisted_shop: ShortlistedShop
    want_to_go_count: int
    ok_to_go_count: int
    not_going_count: int
    responded_participant_count: int


def shortlisted_shops_with_tallies(gathering: Gathering) -> list[ShortlistedShopTally]:
    """``Gathering.shortlistedShops``, ordered ``wantToGoCount + okToGoCount`` descending.

    Changed 2026-09-04 (adr/0044 decision 3, human decision: 行ける人が多い順
    means the sum of the two positive tiers, not either alone) from the
    retired single ``approvalCount`` descending.

    D7's per-shop denominator: a participant counts toward a given shop's
    ``respondedParticipantCount`` only if their most recent ``setShopVotes``
    submission was sent at or after that shop's own ``added_at`` **and**
    that submission's ``votes`` mapping actually names this shop -- a shop
    present in the mapping's key set but with no entry for this specific
    shop is "not yet answered" for this shop alone (SetShopVotesRequest's
    own per-shop, not per-submission, omission rule), so a participant may
    count toward one shop's denominator while not counting toward
    another's, even from the same submission. A shop just added by a
    shortlist replacement starts every count at 0 even if every participant
    already voted on the previous shortlist. The tie-break on an equal sum
    is ``added_at`` ascending (``ShortlistedShop.Meta.ordering``, preserved
    by Python's stable sort), mirroring ``candidate_dates_with_tallies``'s
    own creation-order tie-break.
    """
    shops = list(gathering.shortlisted_shops.all())
    submissions = list(
        ShopVoteSubmission.objects.filter(participant_link__gathering=gathering).values_list(
            "submitted_at", "votes"
        )
    )
    tallies = []
    for shop in shops:
        counts: Counter = Counter()
        responded = 0
        for submitted_at, votes in submissions:
            if submitted_at < shop.added_at:
                continue
            status = (votes or {}).get(shop.shop_id)
            if status is None:
                continue
            counts[status] += 1
            responded += 1
        tallies.append(
            ShortlistedShopTally(
                shortlisted_shop=shop,
                want_to_go_count=counts[ShopVoteStatus.WANT_TO_GO],
                ok_to_go_count=counts[ShopVoteStatus.OK_TO_GO],
                not_going_count=counts[ShopVoteStatus.NOT_GOING],
                responded_participant_count=responded,
            )
        )
    tallies.sort(key=lambda tally: tally.want_to_go_count + tally.ok_to_go_count, reverse=True)
    return tallies


def set_shop_votes(token: str, votes: Sequence[tuple[str, str]]) -> ParticipantLink:
    """``setShopVotes`` (三段階「行きたい／行ってもいい／むり」, adr/0040, moved to a
    three-tier model by adr/0044).

    Replaces this participant's entire per-shop answer set in one call (not
    a per-shop toggle); may be empty. A shop id omitted from ``votes``
    is left "not yet answered" (``yourVote: null``) for this participant --
    the same meaning omission already had under the prior boolean model.
    Rejected with ``ShopVotingNotStartedError`` while ``shortlistedShops``
    is empty, and with ``GatheringFinalizedError`` once ``phase`` is
    FINALIZED (reusing the existing code, adr/0040).
    """
    link = _get_participant_link_by_token(token)
    _authorize_participant_link(link)
    gathering = link.gathering
    current_shop_ids = set(gathering.shortlisted_shops.values_list("shop_id", flat=True))
    if not current_shop_ids:
        raise ShopVotingNotStartedError
    if gathering.phase == GatheringPhase.FINALIZED:
        raise GatheringFinalizedError
    shop_ids = [shop_id for shop_id, _status in votes]
    if len(set(shop_ids)) != len(shop_ids):
        raise InvalidShopSelectionError
    if not set(shop_ids) <= current_shop_ids:
        raise InvalidShopSelectionError
    ShopVoteSubmission.objects.update_or_create(
        participant_link=link, defaults={"votes": dict(votes)}
    )
    return link


def _shop_distance_or_none(
    shop: ShortlistedShop, shop_lookup: dict, origin: Origin | None
) -> float | None:
    """The shop's raw distance from ``origin``, or ``None`` if unresolvable.

    ``None`` covers two distinct causes this function does not distinguish
    further -- the private population source could not be resolved at all
    (``origin`` itself is ``None``, e.g. a provider outage), or this
    specific shop id is no longer present in a fresh refetch of the live
    population (ADR-0034 decision 6 never persists a shop's coordinates, so
    a shop's continued presence at all can change between reads). Both are
    genuinely rare, unmeasured edge cases no TDR-GTH scenario exercises;
    callers push a ``None`` distance to the end of the nearest-first order
    (developer discretion, FR-028 -- reported not resolved) rather than
    fabricate a plausible-looking distance.
    """
    if origin is None:
        return None
    candidate = shop_lookup.get(shop.shop_id)
    if candidate is None:
        return None
    return distance_meters(origin, candidate)


def shortlisted_shops_nearest_first(
    gathering: Gathering, shop_lookup: dict, origin: Origin | None
) -> list[ShortlistedShop]:
    """``Gathering.shortlistedShops``, ordered nearest-first from ``origin`` (adr/0044 decision 2).

    Shared by ``participant_shop_vote_options`` (``ParticipantView.
    shopVoteQuestions``) and ``participant_decision_shop_votes``
    (``ParticipantView.decision.yourShopVotes``, which the contract requires
    to carry the same nearest-first order the shops had at the moment of
    finalization) so the two call sites can never silently diverge on the
    ordering basis. A shop's distance from the search origin depends only on
    its own location and the origin -- never on vote counts -- which is what
    lets this order stay stable as votes are cast (the production defect
    ADR-0044 fixes: the participant list had previously reused the
    organizer-facing, vote-count-ordered list instead). Python's stable sort
    keeps every unresolvable shop (``_shop_distance_or_none`` returning
    ``None``) at the end, in their original (``added_at`` ascending) order
    among themselves.
    """
    shops = list(gathering.shortlisted_shops.all())
    decorated = [(shop, _shop_distance_or_none(shop, shop_lookup, origin)) for shop in shops]
    decorated.sort(key=lambda pair: (pair[1] is None, pair[1] if pair[1] is not None else 0.0))
    return [shop for shop, _distance in decorated]


@dataclass(frozen=True)
class ParticipantShopVoteOption:
    """One shortlisted shop from one participant's own point of view (D7, adr/0044)."""

    shortlisted_shop: ShortlistedShop
    want_to_go_count: int
    ok_to_go_count: int
    not_going_count: int
    responded_participant_count: int
    your_vote: str | None


def participant_shop_vote_options(
    link: ParticipantLink, shop_lookup: dict, origin: Origin | None
) -> list[ParticipantShopVoteOption]:
    """``ParticipantView.shopVoteQuestions`` entries, ordered nearest-first (adr/0044 decision 2).

    ``your_vote`` is ``None`` ("まだ答えていません", D7) exactly when this
    participant has never submitted ``setShopVotes``, their most recent
    submission predates the shop's own ``added_at`` (a shop added by a later
    shortlist replacement, after this participant last voted), or that
    submission's ``votes`` mapping simply omits this shop id (this
    participant answered other shops but not this one yet).
    """
    tallies_by_shop_id = {
        tally.shortlisted_shop.shop_id: tally
        for tally in shortlisted_shops_with_tallies(link.gathering)
    }
    submission = ShopVoteSubmission.objects.filter(participant_link=link).first()
    options = []
    for shop in shortlisted_shops_nearest_first(link.gathering, shop_lookup, origin):
        tally = tallies_by_shop_id[shop.shop_id]
        if submission is None or submission.submitted_at < shop.added_at:
            your_vote = None
        else:
            your_vote = (submission.votes or {}).get(shop.shop_id)
        options.append(
            ParticipantShopVoteOption(
                shortlisted_shop=shop,
                want_to_go_count=tally.want_to_go_count,
                ok_to_go_count=tally.ok_to_go_count,
                not_going_count=tally.not_going_count,
                responded_participant_count=tally.responded_participant_count,
                your_vote=your_vote,
            )
        )
    return options


@dataclass(frozen=True)
class ParticipantDecisionShopVote:
    """One ``ParticipantDecisionShopVote`` entry (``ParticipantView.decision.yourShopVotes``)."""

    shortlisted_shop: ShortlistedShop
    status: str | None


def participant_decision_shop_votes(
    link: ParticipantLink, shop_lookup: dict, origin: Origin | None
) -> list[ParticipantDecisionShopVote]:
    """Every shop among ``Gathering.shortlistedShops`` at finalization, nearest-first.

    Includes a shop this participant never voted on (``status: None``,
    "答えないまま締まりました") -- changed 2026-09-05, human chat decision,
    adr/0046 open item 3: the prior revision omitted such a shop from this
    array entirely. Ordered the same way ``shopVoteQuestions`` was ordered
    (nearest-first, adr/0044) via the same ``shortlisted_shops_nearest_first``
    helper ``participant_shop_vote_options`` uses, so the two orderings can
    never diverge.
    """
    submission = ShopVoteSubmission.objects.filter(participant_link=link).first()
    votes = []
    for shop in shortlisted_shops_nearest_first(link.gathering, shop_lookup, origin):
        if submission is None or submission.submitted_at < shop.added_at:
            status = None
        else:
            status = (submission.votes or {}).get(shop.shop_id)
        votes.append(ParticipantDecisionShopVote(shortlisted_shop=shop, status=status))
    return votes


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
