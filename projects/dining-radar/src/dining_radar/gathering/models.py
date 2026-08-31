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
