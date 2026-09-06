"""Persisted models for the "gathering creation and scheduling" slice.

This is the first feature this product persists beyond Django's own
account/session state (ARCHITECTURE.md; ADR-0034 decision 6, product-brief.md
§7): a ``Gathering`` never stores provider-derived shop attributes (name,
genre, coordinates, hours, images) -- only data the gathering itself owns
(title, phase, candidate dates, participant links, schedule responses).
Field names mirror ``contracts/gathering-scheduling-api.yaml`` schemas where
a direct correspondence exists; see ``dining_radar.gathering.serializers``
for the exact wire projection.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class GatheringPhase(models.TextChoices):
    """``components.schemas.GatheringPhase`` (gathering-scheduling-api.yaml).

    The persisted DRAFT phase does not exist (see that contract's header
    comment) -- a gathering is created directly in SCHEDULING.
    """

    SCHEDULING = "SCHEDULING"
    SELECTING_SHOP = "SELECTING_SHOP"
    FINALIZED = "FINALIZED"


class ScheduleResponseStatus(models.TextChoices):
    """``components.schemas.ScheduleResponseStatus`` (gathering-scheduling-api.yaml)."""

    GOING = "GOING"
    MAYBE = "MAYBE"
    NOT_GOING = "NOT_GOING"


class ShopVoteStatus(models.TextChoices):
    """``components.schemas.ShopVoteStatus`` (gathering-scheduling-api.yaml, adr/0044).

    Deliberately a distinct enum from ``ScheduleResponseStatus`` above, both
    in values and in the display wording it carries (行きたい／行ってもいい／
    むり, not 行ける／たぶん／むり) -- a shop vote expresses preference for a
    shop, not schedule availability (ADR-0044 decision 1, 2026-09-04 human
    decision). Replaces the retired boolean approve-any-number-of-shops model
    this project shipped from adr/0040 until this decision; the prior
    ``ShopVoteSubmission.approved_shop_ids`` data is not migrated (human
    decision, ADR-0044 decision 5: production carried essentially no real
    votes under that model, so no conversion is worth designing).
    """

    WANT_TO_GO = "WANT_TO_GO"
    OK_TO_GO = "OK_TO_GO"
    NOT_GOING = "NOT_GOING"


class Gathering(models.Model):
    """One ランチ会. Owned by exactly one organizer (product-brief.md §5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gatherings"
    )
    title = models.CharField(max_length=200)
    phase = models.CharField(
        max_length=20, choices=GatheringPhase.choices, default=GatheringPhase.SCHEDULING
    )
    # Non-null exactly when phase is SELECTING_SHOP or FINALIZED
    # (Gathering.confirmedCandidateDateId). on_delete=SET_NULL: this contract
    # defines no operation that deletes an individual CandidateDate --
    # SET_NULL only ever matters for
    # resetGatheringSchedulingAcceptanceState's whole-gathering cascade
    # delete, where it avoids the collector ordering hazard a PROTECT
    # relation between two models in the same cascading delete would create.
    confirmed_candidate_date = models.ForeignKey(
        "CandidateDate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Lifetime counters (Gathering.totalIssuedParticipantLinks /
    # totalRevokedParticipantLinks, ADR-0036 decision 7): monotonically
    # non-decreasing, kept on the Gathering row itself (rather than derived
    # by counting ParticipantLink rows on every read) so a revoked link that
    # is later hard-deleted by some future maintenance task could never
    # silently change these audit totals -- this contract defines no delete
    # operation for either model, but the counters are designed to not
    # depend on that invariant holding forever.
    total_issued_participant_links = models.PositiveIntegerField(default=0)
    total_revoked_participant_links = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    # Gathering.votingStartedAt (adr/0040): null until the first successful
    # setShortlistedShops call, non-null and unchanged thereafter. Distinct
    # from `phase`, which stays SELECTING_SHOP while shortlisting/voting
    # happen -- this field is the sub-state adr/0040 introduced instead of a
    # fourth enum value (FR-028, settled by P6/adr/0041).
    voting_started_at = models.DateTimeField(null=True, blank=True)
    # Gathering.finalizedShopId (adr/0040): the opaque provider shop
    # identifier (same value space as ShortlistedShop.shop_id below) the
    # organizer chose via finalizeGathering. A plain string, not a foreign
    # key, for the same reason ShortlistedShop.shop_id is a plain string --
    # the shop itself is never a persisted row this product owns (ADR-0034
    # decision 6); only the *reference* to it is durable.
    finalized_shop_id = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    @property
    def active_participant_link_count(self) -> int:
        """``Gathering.activeParticipantLinkCount`` (ADR-0036 decision 7)."""
        return self.total_issued_participant_links - self.total_revoked_participant_links


class CandidateDate(models.Model):
    """One proposed date/time (``components.schemas.CandidateDate``)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gathering = models.ForeignKey(
        Gathering, on_delete=models.CASCADE, related_name="candidate_dates"
    )
    start_at = models.DateTimeField()
    # Not part of the public schema; used only for a stable creation-order
    # tie-break under Gathering.candidateDates' goingCount-descending sort
    # (the contract leaves the tie-break to implementation discretion).
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ParticipantLink(models.Model):
    """A signed, single-participant-slot access token (adr/0035 decision 4).

    ``id`` is the organizer-facing ``linkId`` (ParticipantLinkId parameter);
    ``token`` is the distinct, never-organizer-visible-in-bulk participant
    credential (ParticipantToken parameter, ADR-0036 decision 7). The two
    are deliberately different fields so a view can serialize one without
    ever risking the other.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gathering = models.ForeignKey(
        Gathering, on_delete=models.CASCADE, related_name="participant_links"
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    # ParticipantView.displayName / ParticipantLinkSummary.displayName: null
    # while this participant slot has not self-reported a name (D5).
    display_name = models.CharField(max_length=100, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    # adr/0035 decision 4: 90-day validity from issuance, a "根拠の薄い値"
    # (ADR-0035) recorded once here at issuance time so a later change to
    # the configured validity duration never silently changes an
    # already-issued link's own expiry (mirrors this contract's own
    # decision not to let seedExpiredParticipantLink depend on the
    # configured duration's numeric value at all).
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    # test-support-api.yaml's seedRateLimitedParticipantLink: a one-shot flag
    # consumed by the very next participant-facing request for this token,
    # regardless of which of the three participant-facing operations it is
    # (adr/0037). Never set by any public operation.
    rate_limited_once = models.BooleanField(default=False)

    class Meta:
        ordering = ["issued_at"]

    @property
    def has_responded(self) -> bool:
        """``ParticipantLinkSummary.hasResponded`` / revocation eligibility."""
        return self.schedule_responses.exists()


class ScheduleResponse(models.Model):
    """One participant's GOING/MAYBE/NOT_GOING answer for one candidate date."""

    participant_link = models.ForeignKey(
        ParticipantLink, on_delete=models.CASCADE, related_name="schedule_responses"
    )
    candidate_date = models.ForeignKey(
        CandidateDate, on_delete=models.CASCADE, related_name="schedule_responses"
    )
    status = models.CharField(max_length=10, choices=ScheduleResponseStatus.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["participant_link", "candidate_date"],
                name="one_schedule_response_per_link_and_date",
            )
        ]


class ShortlistedShop(models.Model):
    """One shop the organizer has shortlisted for approval voting (adr/0040).

    ``shop_id`` is the same opaque provider identifier
    ``dining_radar.gathering.services`` derives from
    ``NormalizedCandidate.provider_page_url`` (the natural, already-unique
    shop identity this codebase uses elsewhere, e.g.
    ``dining_radar.recommendation.pipeline._dedupe``) -- a plain string, not
    a foreign key, since the shop's display attributes are never persisted
    (ADR-0034 decision 6; only this reference is durable). Removing a shop
    from the shortlist deletes its row entirely (adr/0040 design judgment:
    re-adding the same shop id later is a brand-new entry, not a restore),
    which also removes any per-shop vote history tied to it -- a
    participant's ``ShopVoteSubmission`` stores raw shop ids, not a foreign
    key to this table, precisely so a submission survives its referenced
    shop being dropped and re-added under a new row/``added_at``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gathering = models.ForeignKey(
        Gathering, on_delete=models.CASCADE, related_name="shortlisted_shops"
    )
    shop_id = models.CharField(max_length=500)
    # ShortlistedShop.addedAt: reset to "now" whenever this shop id is newly
    # added or re-added after removal (adr/0040). The basis for D7's
    # per-shop denominator (respondedParticipantCount).
    added_at = models.DateTimeField()

    class Meta:
        ordering = ["added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["gathering", "shop_id"], name="one_shortlisted_row_per_gathering_and_shop"
            )
        ]


class ShopVoteSubmission(models.Model):
    """One participant's most recent, complete shop-vote submission (adr/0040/0044).

    ``setShopVotes`` replaces this participant's entire vote in one call (not
    a per-shop toggle, product-brief.md §2), so one row per
    ``ParticipantLink`` is enough -- there is no history of earlier
    submissions to keep. ``votes`` is a ``{shopId: ShopVoteStatus}`` mapping
    (adr/0044, replacing the retired boolean ``approved_shop_ids`` list --
    not migrated, per ADR-0044 decision 5) storing raw shop id strings as
    keys (not a many-to-many to ``ShortlistedShop``) so a submission remains
    valid even after the organizer removes and later re-adds the same shop
    id under a new ``ShortlistedShop`` row (see that model's own docstring).
    A shop id absent from this mapping means "not yet answered" for that
    shop specifically -- the same meaning absence from the prior
    ``approved_shop_ids`` list had, now made explicit per-shop rather than
    collapsing into a single boolean.
    """

    participant_link = models.OneToOneField(
        ParticipantLink, on_delete=models.CASCADE, related_name="shop_vote_submission"
    )
    votes = models.JSONField(default=dict)
    # Compared against ShortlistedShop.added_at to derive
    # ParticipantShopVoteOption.yourVote's "not yet answered" (null)
    # state (D7) -- updated (via auto_now) on every setShopVotes call,
    # including one that resubmits the same content.
    submitted_at = models.DateTimeField(auto_now=True)
