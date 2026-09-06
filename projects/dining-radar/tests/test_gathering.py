"""Unit and boundary tests for contracts/gathering-scheduling-api.yaml.

Covers ``dining_radar.gathering``'s models, services (business logic), and
the JSON API views, plus the acceptance-only test-support seams
(``resetGatheringSchedulingAcceptanceState``/``seedExpiredParticipantLink``/
``seedRateLimitedParticipantLink``) added to
``dining_radar.test_support.views``/``urls`` for TDR-GTH.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dining_radar.gathering import serializers, services
from dining_radar.gathering.models import (
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
from dining_radar.suggestions import acceptance_state

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GATHERING_JS = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "gathering.js"
)
GATHERING_CREATE_JS = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "gathering_create.js"
)
GATHERING_LIST_JS = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "gathering_list.js"
)
PARTICIPANT_JS = (
    PROJECT_ROOT
    / "src"
    / "dining_radar"
    / "gathering"
    / "static"
    / "dining_radar"
    / "gathering"
    / "participant.js"
)


def csrf_token_from(response) -> str:
    matched = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', response.content)
    assert matched is not None
    return matched.group(1).decode("ascii")


class GatheringOrganizerTestCase(TestCase):
    """Shared fixture: one authenticated organizer with a CSRF-ready client."""

    def setUp(self):
        self.addCleanup(acceptance_state.reset_mode)
        acceptance_state.reset_mode()
        self.password = "Synthetic-passphrase-123!"
        self.user = get_user_model().objects.create_user(
            username="gathering-organizer", password=self.password
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-gathering-organizer", password=self.password
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        page = self.client.get(
            reverse("gathering:organizer-dashboard", kwargs={"gathering_id": uuid.uuid4()})
        )
        self.csrf_token = csrf_token_from(page)

    def post_json(self, url: str, body: dict, *, client=None) -> object:
        return (client or self.client).post(
            url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def put_json(self, url: str, body: dict, *, client=None) -> object:
        return (client or self.client).put(
            url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def create_gathering_via_api(self, title="第7回 社内ランチ会", candidate_dates=None) -> dict:
        candidate_dates = candidate_dates or [
            {"startAt": "2026-09-02T12:00:00+09:00"},
            {"startAt": "2026-09-03T12:30:00+09:00"},
        ]
        response = self.post_json(
            reverse("gathering:gatherings"),
            {"title": title, "candidateDates": candidate_dates},
        )
        assert response.status_code == 201, response.content
        return response.json()


# --- models -----------------------------------------------------------------


class GatheringModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="model-organizer")

    def test_active_participant_link_count_nets_out_revocations(self):
        gathering = Gathering.objects.create(organizer=self.user, title="test")
        gathering.total_issued_participant_links = 5
        gathering.total_revoked_participant_links = 2

        self.assertEqual(gathering.active_participant_link_count, 3)

    def test_has_responded_is_false_until_a_schedule_response_exists(self):
        gathering = Gathering.objects.create(organizer=self.user, title="test")
        candidate_date = CandidateDate.objects.create(gathering=gathering, start_at=timezone.now())
        link = ParticipantLink.objects.create(
            gathering=gathering,
            token="token-a",
            expires_at=timezone.now() + timedelta(days=90),
        )

        self.assertFalse(link.has_responded)

        ScheduleResponse.objects.create(
            participant_link=link,
            candidate_date=candidate_date,
            status=ScheduleResponseStatus.GOING,
        )

        self.assertTrue(link.has_responded)


# --- services: gathering lifecycle -------------------------------------------


class CreateGatheringServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer")

    def test_creates_in_scheduling_phase_with_every_candidate_date(self):
        gathering = services.create_gathering(
            self.user, "会", [timezone.now(), timezone.now() + timedelta(days=1)]
        )

        self.assertEqual(gathering.phase, GatheringPhase.SCHEDULING)
        self.assertEqual(gathering.candidate_dates.count(), 2)
        self.assertIsNone(gathering.confirmed_candidate_date_id)

    def test_issues_no_participant_links(self):
        gathering = services.create_gathering(self.user, "会", [timezone.now()])

        self.assertEqual(gathering.total_issued_participant_links, 0)

    def test_rejects_two_entries_sharing_the_exact_same_start_at(self):
        start_at = timezone.now()

        with self.assertRaises(services.DuplicateCandidateDateError):
            services.create_gathering(self.user, "会", [start_at, start_at])

    def test_rejecting_duplicate_start_ats_creates_no_gathering(self):
        start_at = timezone.now()

        with self.assertRaises(services.DuplicateCandidateDateError):
            services.create_gathering(self.user, "会", [start_at, start_at])

        self.assertEqual(Gathering.objects.count(), 0)


class AddCandidateDateServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-2")
        self.gathering = services.create_gathering(self.user, "会", [timezone.now()])

    def test_adds_a_candidate_date_while_scheduling(self):
        _gathering, candidate_date = services.add_candidate_date(
            self.user, self.gathering.id, timezone.now() + timedelta(days=2)
        )

        self.assertEqual(self.gathering.candidate_dates.count(), 2)
        self.assertIn(candidate_date, self.gathering.candidate_dates.all())

    def test_rejected_once_the_gathering_has_moved_past_scheduling(self):
        candidate_date = self.gathering.candidate_dates.first()
        services.confirm_candidate_date(self.user, self.gathering.id, candidate_date.id)

        with self.assertRaises(services.GatheringNotInSchedulingPhaseError):
            services.add_candidate_date(self.user, self.gathering.id, timezone.now())

    def test_unknown_gathering_id_is_not_found(self):
        with self.assertRaises(services.GatheringNotFoundError):
            services.add_candidate_date(self.user, uuid.uuid4(), timezone.now())

    def test_another_organizers_gathering_is_not_found(self):
        other_user = get_user_model().objects.create_user(username="svc-other-organizer")

        with self.assertRaises(services.GatheringNotFoundError):
            services.add_candidate_date(other_user, self.gathering.id, timezone.now())

    def test_rejects_a_start_at_already_on_this_gathering(self):
        existing = self.gathering.candidate_dates.first()

        with self.assertRaises(services.DuplicateCandidateDateError):
            services.add_candidate_date(self.user, self.gathering.id, existing.start_at)

    def test_duplicate_rejection_does_not_add_a_candidate_date(self):
        existing = self.gathering.candidate_dates.first()
        before_count = self.gathering.candidate_dates.count()

        with self.assertRaises(services.DuplicateCandidateDateError):
            services.add_candidate_date(self.user, self.gathering.id, existing.start_at)

        self.assertEqual(self.gathering.candidate_dates.count(), before_count)


class ConfirmCandidateDateServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-3")
        self.gathering = services.create_gathering(
            self.user, "会", [timezone.now(), timezone.now() + timedelta(days=1)]
        )
        self.candidate_dates = list(self.gathering.candidate_dates.all())

    def test_advances_to_selecting_shop_and_sets_the_confirmed_date(self):
        target = self.candidate_dates[0]

        gathering = services.confirm_candidate_date(self.user, self.gathering.id, target.id)

        self.assertEqual(gathering.phase, GatheringPhase.SELECTING_SHOP)
        self.assertEqual(gathering.confirmed_candidate_date_id, target.id)

    def test_rejects_a_candidate_date_from_a_different_gathering(self):
        other_gathering = services.create_gathering(self.user, "別の会", [timezone.now()])
        foreign_date = other_gathering.candidate_dates.first()

        with self.assertRaises(services.CandidateDateNotFoundError):
            services.confirm_candidate_date(self.user, self.gathering.id, foreign_date.id)

    def test_only_one_candidate_date_may_ever_be_confirmed(self):
        first, second = self.candidate_dates
        services.confirm_candidate_date(self.user, self.gathering.id, first.id)

        with self.assertRaises(services.GatheringNotInSchedulingPhaseError):
            services.confirm_candidate_date(self.user, self.gathering.id, second.id)


class CandidateDateTalliesServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-4")
        self.gathering = services.create_gathering(
            self.user, "会", [timezone.now(), timezone.now() + timedelta(days=1)]
        )
        self.low, self.high = self.gathering.candidate_dates.all()

    def _link(self):
        return ParticipantLink.objects.create(
            gathering=self.gathering,
            token=f"token-{uuid.uuid4()}",
            expires_at=timezone.now() + timedelta(days=90),
        )

    def test_orders_going_count_descending(self):
        ScheduleResponse.objects.create(
            participant_link=self._link(),
            candidate_date=self.high,
            status=ScheduleResponseStatus.GOING,
        )
        ScheduleResponse.objects.create(
            participant_link=self._link(),
            candidate_date=self.high,
            status=ScheduleResponseStatus.GOING,
        )
        ScheduleResponse.objects.create(
            participant_link=self._link(),
            candidate_date=self.low,
            status=ScheduleResponseStatus.GOING,
        )

        tallies = services.candidate_dates_with_tallies(self.gathering)

        self.assertEqual(
            [tally.candidate_date.id for tally in tallies], [self.high.id, self.low.id]
        )
        self.assertEqual(tallies[0].going_count, 2)
        self.assertEqual(tallies[1].going_count, 1)

    def test_ties_keep_creation_order(self):
        tallies = services.candidate_dates_with_tallies(self.gathering)

        self.assertEqual(
            [tally.candidate_date.id for tally in tallies], [self.low.id, self.high.id]
        )

    def test_counts_every_status_independently(self):
        link_going = self._link()
        link_maybe = self._link()
        link_not_going = self._link()
        ScheduleResponse.objects.create(
            participant_link=link_going,
            candidate_date=self.low,
            status=ScheduleResponseStatus.GOING,
        )
        ScheduleResponse.objects.create(
            participant_link=link_maybe,
            candidate_date=self.low,
            status=ScheduleResponseStatus.MAYBE,
        )
        ScheduleResponse.objects.create(
            participant_link=link_not_going,
            candidate_date=self.low,
            status=ScheduleResponseStatus.NOT_GOING,
        )

        tallies = {
            tally.candidate_date.id: tally
            for tally in services.candidate_dates_with_tallies(self.gathering)
        }

        low_tally = tallies[self.low.id]
        self.assertEqual(
            (low_tally.going_count, low_tally.maybe_count, low_tally.not_going_count), (1, 1, 1)
        )


class ResponseSummaryServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-5")
        self.gathering = services.create_gathering(self.user, "会", [timezone.now()])
        self.candidate_date = self.gathering.candidate_dates.first()

    def _link(self, display_name=None):
        return ParticipantLink.objects.create(
            gathering=self.gathering,
            token=f"token-{uuid.uuid4()}",
            expires_at=timezone.now() + timedelta(days=90),
            display_name=display_name,
        )

    def test_zero_when_nobody_has_responded(self):
        self._link()  # issued but never answers

        self.assertEqual(services.response_summary(self.gathering), (0, 0))

    def test_counts_distinct_responded_links_and_the_anonymous_subset(self):
        named = self._link(display_name="たなか")
        anonymous = self._link(display_name=None)
        ScheduleResponse.objects.create(
            participant_link=named,
            candidate_date=self.candidate_date,
            status=ScheduleResponseStatus.GOING,
        )
        ScheduleResponse.objects.create(
            participant_link=anonymous,
            candidate_date=self.candidate_date,
            status=ScheduleResponseStatus.MAYBE,
        )

        self.assertEqual(services.response_summary(self.gathering), (2, 1))

    def test_a_link_with_multiple_responses_is_counted_once(self):
        other_date = CandidateDate.objects.create(
            gathering=self.gathering, start_at=timezone.now() + timedelta(days=1)
        )
        link = self._link()
        ScheduleResponse.objects.create(
            participant_link=link,
            candidate_date=self.candidate_date,
            status=ScheduleResponseStatus.GOING,
        )
        ScheduleResponse.objects.create(
            participant_link=link, candidate_date=other_date, status=ScheduleResponseStatus.MAYBE
        )

        # self._link() defaults to a nameless link, so it is also counted
        # in the anonymous subset -- the point under test is only that the
        # *responded* count stays 1 despite two responses from one link.
        self.assertEqual(services.response_summary(self.gathering), (1, 1))


class ParticipantLinkLifecycleServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-6")
        self.gathering = services.create_gathering(self.user, "会", [timezone.now()])
        self.candidate_date = self.gathering.candidate_dates.first()

    def test_issue_participant_links_increments_lifetime_and_active_counts(self):
        gathering, links = services.issue_participant_links(self.user, self.gathering.id, 3)

        self.assertEqual(len(links), 3)
        self.assertEqual(gathering.total_issued_participant_links, 3)
        self.assertEqual(gathering.active_participant_link_count, 3)
        self.assertEqual(len({link.token for link in links}), 3)

    def test_issued_link_validity_period_is_ninety_days(self):
        _gathering, links = services.issue_participant_links(self.user, self.gathering.id, 1)
        link = links[0]

        expected = link.issued_at + timedelta(days=services.PARTICIPANT_LINK_VALIDITY_DAYS)
        self.assertAlmostEqual(link.expires_at.timestamp(), expected.timestamp(), delta=1)
        self.assertEqual(services.PARTICIPANT_LINK_VALIDITY_DAYS, 90)

    def test_recopy_returns_the_same_link_unless_revoked(self):
        _gathering, links = services.issue_participant_links(self.user, self.gathering.id, 1)
        link = links[0]

        recopied = services.recopy_participant_link(self.user, self.gathering.id, link.id)

        self.assertEqual(recopied.token, link.token)

    def test_recopy_a_revoked_link_is_refused(self):
        _gathering, links = services.issue_participant_links(self.user, self.gathering.id, 1)
        link = links[0]
        services.revoke_participant_link(self.user, self.gathering.id, link.id)

        with self.assertRaises(services.ParticipantLinkRevokedError):
            services.recopy_participant_link(self.user, self.gathering.id, link.id)

    def test_recopy_an_already_answered_link_is_allowed(self):
        _gathering, links = services.issue_participant_links(self.user, self.gathering.id, 1)
        link = links[0]
        ScheduleResponse.objects.create(
            participant_link=link,
            candidate_date=self.candidate_date,
            status=ScheduleResponseStatus.GOING,
        )

        recopied = services.recopy_participant_link(self.user, self.gathering.id, link.id)

        self.assertEqual(recopied.id, link.id)

    def test_revoke_reduces_active_count_and_marks_revoked(self):
        gathering, links = services.issue_participant_links(self.user, self.gathering.id, 2)
        link = links[0]

        gathering, revoked_link = services.revoke_participant_link(
            self.user, self.gathering.id, link.id
        )

        self.assertTrue(revoked_link.revoked)
        self.assertEqual(gathering.total_revoked_participant_links, 1)
        self.assertEqual(gathering.active_participant_link_count, 1)

    def test_revoke_an_already_answered_link_is_refused(self):
        _gathering, links = services.issue_participant_links(self.user, self.gathering.id, 1)
        link = links[0]
        ScheduleResponse.objects.create(
            participant_link=link,
            candidate_date=self.candidate_date,
            status=ScheduleResponseStatus.GOING,
        )

        with self.assertRaises(services.ParticipantLinkAlreadyAnsweredError):
            services.revoke_participant_link(self.user, self.gathering.id, link.id)

    def test_list_participant_links_is_ordered_by_issuance(self):
        services.issue_participant_links(self.user, self.gathering.id, 1)
        services.issue_participant_links(self.user, self.gathering.id, 1)

        _gathering, links = services.list_participant_links(self.user, self.gathering.id)

        self.assertEqual(len(links), 2)
        self.assertLessEqual(links[0].issued_at, links[1].issued_at)


# --- services: gathering list / in-progress count (adr/0038) ----------------


class ListGatheringsServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-list")
        self.other_user = get_user_model().objects.create_user(username="svc-organizer-list-other")

    def test_empty_when_the_organizer_has_no_gathering(self):
        self.assertEqual(services.list_gatherings(self.user), [])

    def test_ordered_by_created_at_descending(self):
        # Two calls in the same test can land within the same microsecond
        # on a fast in-memory test database, making created_at a tie this
        # assertion cannot distinguish -- force distinct values explicitly
        # (bypassing auto_now_add, which only governs the initial INSERT)
        # rather than relying on real wall-clock spacing between calls.
        now = timezone.now()
        first = services.create_gathering(self.user, "1つめ", [now])
        second = services.create_gathering(self.user, "2つめ", [now])
        Gathering.objects.filter(pk=first.pk).update(created_at=now - timedelta(seconds=1))
        Gathering.objects.filter(pk=second.pk).update(created_at=now)

        result = services.list_gatherings(self.user)

        self.assertEqual([gathering.id for gathering in result], [second.id, first.id])

    def test_includes_a_finalized_gathering(self):
        gathering = services.create_gathering(self.user, "会", [timezone.now()])
        gathering.phase = GatheringPhase.FINALIZED
        gathering.save(update_fields=["phase"])

        result = services.list_gatherings(self.user)

        self.assertEqual([g.id for g in result], [gathering.id])

    def test_never_includes_another_organizers_gathering(self):
        services.create_gathering(self.other_user, "他人の会", [timezone.now()])

        self.assertEqual(services.list_gatherings(self.user), [])


class CountInProgressGatheringsServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-count")
        self.other_user = get_user_model().objects.create_user(username="svc-organizer-count-other")

    def test_zero_when_the_organizer_has_no_gathering(self):
        self.assertEqual(services.count_in_progress_gatherings(self.user), 0)

    def test_counts_scheduling_and_selecting_shop(self):
        services.create_gathering(self.user, "日程を聞き中", [timezone.now()])
        selecting = services.create_gathering(self.user, "店を選び中", [timezone.now()])
        selecting.phase = GatheringPhase.SELECTING_SHOP
        selecting.save(update_fields=["phase"])

        self.assertEqual(services.count_in_progress_gatherings(self.user), 2)

    def test_excludes_finalized(self):
        gathering = services.create_gathering(self.user, "確定", [timezone.now()])
        gathering.phase = GatheringPhase.FINALIZED
        gathering.save(update_fields=["phase"])

        self.assertEqual(services.count_in_progress_gatherings(self.user), 0)

    def test_never_counts_another_organizers_gathering(self):
        services.create_gathering(self.other_user, "他人の会", [timezone.now()])

        self.assertEqual(services.count_in_progress_gatherings(self.user), 0)


# --- services: participant-facing access -------------------------------------


class ParticipantAccessServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-7")
        self.gathering = services.create_gathering(self.user, "会", [timezone.now()])
        self.candidate_date = self.gathering.candidate_dates.first()
        _gathering, links = services.issue_participant_links(self.user, self.gathering.id, 1)
        self.link = links[0]

    def test_unknown_token_is_not_found(self):
        with self.assertRaises(services.LinkNotFoundError):
            services.get_participant_view("does-not-exist")

    def test_expired_link_is_rejected(self):
        services.seed_expired_participant_link(self.link.token)

        with self.assertRaises(services.LinkExpiredError):
            services.get_participant_view(self.link.token)

    def test_revoked_link_is_rejected(self):
        _gathering, revoked = services.revoke_participant_link(
            self.user, self.gathering.id, self.link.id
        )
        self.assertTrue(revoked.revoked)

        with self.assertRaises(services.LinkRevokedError):
            services.get_participant_view(self.link.token)

    def test_rate_limited_link_is_rejected_exactly_once(self):
        services.seed_rate_limited_participant_link(self.link.token)

        with self.assertRaises(services.LinkRateLimitedError):
            services.get_participant_view(self.link.token)

        # A one-shot flag: the *next* request must succeed again.
        services.get_participant_view(self.link.token)

    def test_server_error_seeded_link_is_rejected_exactly_once(self):
        """adr/0047: ``seedParticipantLinkServerError`` mirrors
        ``seedRateLimitedParticipantLink``'s one-shot shape, but only for
        ``getParticipantView`` (this seam's own scope)."""
        services.seed_participant_link_server_error(self.link.token)

        with self.assertRaises(services.ParticipantLinkServerErrorSeededError):
            services.get_participant_view(self.link.token)

        # A one-shot flag: the *next* request must succeed again.
        services.get_participant_view(self.link.token)

    def test_server_error_seed_takes_priority_over_a_durable_link_state(self):
        """The seeded one-shot failure fires even for a token that is also
        durably expired -- it is consumed first, so the durable state only
        surfaces on the *next* call (mirrors _authorize_participant_link's
        own revoked-before-expired-before-rate-limited ordering rationale:
        each check is independent and does not suppress the others)."""
        services.seed_expired_participant_link(self.link.token)
        services.seed_participant_link_server_error(self.link.token)

        with self.assertRaises(services.ParticipantLinkServerErrorSeededError):
            services.get_participant_view(self.link.token)

        with self.assertRaises(services.LinkExpiredError):
            services.get_participant_view(self.link.token)

    def test_set_schedule_response_records_the_answer(self):
        services.set_schedule_response(
            self.link.token, self.candidate_date.id, ScheduleResponseStatus.GOING
        )

        self.assertTrue(
            ScheduleResponse.objects.filter(
                participant_link=self.link, candidate_date=self.candidate_date
            ).exists()
        )

    def test_set_schedule_response_can_change_a_prior_answer(self):
        services.set_schedule_response(
            self.link.token, self.candidate_date.id, ScheduleResponseStatus.GOING
        )
        services.set_schedule_response(
            self.link.token, self.candidate_date.id, ScheduleResponseStatus.NOT_GOING
        )

        response = ScheduleResponse.objects.get(
            participant_link=self.link, candidate_date=self.candidate_date
        )
        self.assertEqual(response.status, ScheduleResponseStatus.NOT_GOING)
        self.assertEqual(
            ScheduleResponse.objects.filter(
                participant_link=self.link, candidate_date=self.candidate_date
            ).count(),
            1,
        )

    def test_set_schedule_response_rejected_once_finalized(self):
        self.gathering.phase = GatheringPhase.FINALIZED
        self.gathering.save(update_fields=["phase"])

        with self.assertRaises(services.GatheringFinalizedError):
            services.set_schedule_response(
                self.link.token, self.candidate_date.id, ScheduleResponseStatus.GOING
            )

    def test_set_participant_display_name_is_never_gated_by_phase(self):
        self.gathering.phase = GatheringPhase.FINALIZED
        self.gathering.save(update_fields=["phase"])

        link = services.set_participant_display_name(self.link.token, "たなか")

        self.assertEqual(link.display_name, "たなか")

    def test_display_name_does_not_affect_previously_recorded_answers(self):
        services.set_schedule_response(
            self.link.token, self.candidate_date.id, ScheduleResponseStatus.GOING
        )

        services.set_participant_display_name(self.link.token, "たなか")

        response = ScheduleResponse.objects.get(
            participant_link=self.link, candidate_date=self.candidate_date
        )
        self.assertEqual(response.status, ScheduleResponseStatus.GOING)


# --- services: test-support seams --------------------------------------------


class TestSupportSeamServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc-organizer-8")

    def test_reset_removes_every_gathering_and_cascades(self):
        gathering = services.create_gathering(self.user, "会", [timezone.now()])
        services.issue_participant_links(self.user, gathering.id, 1)

        services.reset_gathering_scheduling_state()

        self.assertEqual(Gathering.objects.count(), 0)
        self.assertEqual(CandidateDate.objects.count(), 0)
        self.assertEqual(ParticipantLink.objects.count(), 0)

    def test_reset_does_not_touch_organizer_accounts(self):
        services.reset_gathering_scheduling_state()

        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_seed_expired_participant_link_rejects_an_unknown_token(self):
        with self.assertRaises(services.LinkNotFoundError):
            services.seed_expired_participant_link("unknown-token")

    def test_seed_rate_limited_participant_link_rejects_an_unknown_token(self):
        with self.assertRaises(services.LinkNotFoundError):
            services.seed_rate_limited_participant_link("unknown-token")

    def test_seed_participant_link_server_error_rejects_an_unknown_token(self):
        with self.assertRaises(services.LinkNotFoundError):
            services.seed_participant_link_server_error("unknown-token")


# --- open-shop preview (shares test-support-api.yaml's population seam) -----


class OpenShopPreviewServiceTests(GatheringOrganizerTestCase):
    def test_preview_uses_the_gathering_open_shop_weekday_match_acceptance_mode(self):
        gathering_payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-07T12:00:00+09:00"}]  # a Monday
        )
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.GATHERING_OPEN_SHOP_WEEKDAY_MATCH
        )

        gathering = Gathering.objects.get(id=gathering_payload["id"])
        candidate_date = gathering.candidate_dates.first()

        candidate_date_obj, population, origin = services.preview_open_shops_for_candidate_date(
            self.user, gathering.id, candidate_date.id
        )

        self.assertEqual(candidate_date_obj.id, candidate_date.id)
        self.assertEqual(len(population), 5)  # Monday: only the 月 candidate excluded
        self.assertIsNotNone(origin)

    def test_preview_never_advances_the_gathering_phase(self):
        gathering_payload = self.create_gathering_via_api()
        gathering = Gathering.objects.get(id=gathering_payload["id"])
        candidate_date = gathering.candidate_dates.first()
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.GATHERING_OPEN_SHOP_WEEKDAY_MATCH
        )

        services.preview_open_shops_for_candidate_date(self.user, gathering.id, candidate_date.id)

        gathering.refresh_from_db()
        self.assertEqual(gathering.phase, GatheringPhase.SCHEDULING)


# --- services: shop shortlisting, approval voting, finalization (adr/0040) --

# The Monday candidate date this whole section shares: with
# GATHERING_OPEN_SHOP_WEEKDAY_MATCH active, exactly 5 of the 6 synthetic
# shops are open on a Monday (only the 月曜-closed one is excluded) --
# OpenShopPreviewServiceTests establishes the same fact above.
_A_MONDAY_START_AT = "2026-09-07T12:00:00+09:00"


def _want_to_go(*shop_ids: str) -> list[tuple[str, str]]:
    """``votes`` entries naming every ``shop_ids`` as WANT_TO_GO (adr/0044).

    A convenience shorthand for tests migrated from the retired boolean
    approve-any-number-of-shops model, where "approving" a shop is now most
    directly analogous to answering it WANT_TO_GO -- this helper does not
    itself assert anything about OK_TO_GO/NOT_GOING, which other tests below
    exercise directly with explicit ``(shop_id, status)`` tuples.
    """
    return [(shop_id, ShopVoteStatus.WANT_TO_GO.value) for shop_id in shop_ids]


def _backdate_shortlisted_shop(gathering: Gathering, shop_id: str, seconds: int = 1) -> None:
    """Force a deterministic "earlier" ``added_at`` for D7 ordering tests.

    Some of this suite's D7 assertions depend on one timestamp
    (``ShortlistedShop.added_at``) being strictly earlier than one computed
    by a later service call. Two back-to-back ``timezone.now()`` calls can
    compare equal on a coarse system clock (observed on Windows, whose
    default timer resolution can exceed 10ms) -- backdating the row
    directly via ``.update()`` (bypassing normal service flow) removes that
    flakiness without a real-time sleep or mocking the production clock.
    Safe to use only when nothing *earlier* in the same test needs to stay
    before this row's original timestamp -- pushing it back by a whole
    second could otherwise land before an even earlier same-test event.
    """
    ShortlistedShop.objects.filter(gathering=gathering, shop_id=shop_id).update(
        added_at=timezone.now() - timedelta(seconds=seconds)
    )


def _forward_date_shortlisted_shop(gathering: Gathering, shop_id: str, seconds: int = 1) -> None:
    """The opposite of ``_backdate_shortlisted_shop``: force this row's ``added_at``
    safely *after* every earlier same-test event, without disturbing any
    other row (e.g. a kept shop's own unaffected ``added_at``, D7).
    """
    ShortlistedShop.objects.filter(gathering=gathering, shop_id=shop_id).update(
        added_at=timezone.now() + timedelta(seconds=seconds)
    )


class GatheringSelectingShopServiceTestCase(TestCase):
    """Shared fixture: a SELECTING_SHOP gathering with 5 known-open shop ids."""

    def setUp(self):
        self.addCleanup(acceptance_state.reset_mode)
        acceptance_state.reset_mode()
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.GATHERING_OPEN_SHOP_WEEKDAY_MATCH
        )
        self.user = get_user_model().objects.create_user(username="svc-shortlist-organizer")
        gathering = services.create_gathering(
            self.user, "会", [datetime.fromisoformat(_A_MONDAY_START_AT)]
        )
        candidate_date = gathering.candidate_dates.first()
        self.gathering = services.confirm_candidate_date(self.user, gathering.id, candidate_date.id)
        population = services.open_shop_population_for_candidate_date(
            self.gathering.confirmed_candidate_date
        )
        self.open_shop_ids = [candidate.provider_page_url for candidate in population]
        assert len(self.open_shop_ids) == 5

    def issue_link(self) -> ParticipantLink:
        _gathering, links = services.issue_participant_links(self.user, self.gathering.id, 1)
        return links[0]

    def shop_lookup_and_origin(self):
        """A fresh ``(shop_lookup, origin)`` pair for the confirmed candidate date.

        ``participant_shop_vote_options``/``participant_decision_shop_votes``
        need both explicitly (services no longer resolves them internally --
        the caller resolves the population source once per request and
        reuses it, mirroring ``serializers.serialize_participant_view``'s
        own convention).
        """
        population_source = services.resolve_population_source()
        shop_lookup = services.shop_lookup_for_gathering(self.gathering, population_source)
        origin = population_source[1] if population_source is not None else None
        return shop_lookup, origin


class ShopLookupForGatheringServiceTests(GatheringSelectingShopServiceTestCase):
    def test_empty_before_a_candidate_date_is_confirmed(self):
        scheduling_gathering = services.create_gathering(self.user, "別の会", [timezone.now()])

        self.assertEqual(services.shop_lookup_for_gathering(scheduling_gathering), {})

    def test_keyed_by_shop_id_once_confirmed(self):
        lookup = services.shop_lookup_for_gathering(self.gathering)

        self.assertEqual(set(lookup), set(self.open_shop_ids))


class SetShortlistedShopsServiceTests(GatheringSelectingShopServiceTestCase):
    def test_rejected_while_still_scheduling(self):
        scheduling_gathering = services.create_gathering(self.user, "別の会", [timezone.now()])

        with self.assertRaises(services.GatheringNotInSelectingShopPhaseError):
            services.set_shortlisted_shops(
                self.user, scheduling_gathering.id, self.open_shop_ids[:1]
            )

    def test_rejected_once_finalized(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[:1])
        services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[0])

        with self.assertRaises(services.GatheringFinalizedError):
            services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[:1])

    def test_rejects_zero_shops(self):
        with self.assertRaises(services.InvalidShopSelectionError):
            services.set_shortlisted_shops(self.user, self.gathering.id, [])

    def test_rejects_more_than_five_shops(self):
        six_ids = [*self.open_shop_ids, "an-extra-shop-id"]

        with self.assertRaises(services.InvalidShopSelectionError):
            services.set_shortlisted_shops(self.user, self.gathering.id, six_ids)

    def test_rejects_a_duplicate_shop_id_in_the_same_request(self):
        with self.assertRaises(services.InvalidShopSelectionError):
            services.set_shortlisted_shops(
                self.user, self.gathering.id, [self.open_shop_ids[0], self.open_shop_ids[0]]
            )

    def test_rejects_a_shop_not_in_the_confirmed_dates_open_population(self):
        with self.assertRaises(services.InvalidShopSelectionError):
            services.set_shortlisted_shops(self.user, self.gathering.id, ["not-a-real-shop"])

    def test_rejects_a_shop_confirmed_closed_on_the_candidate_date(self):
        # TDR-GTH-27: a real shop id that exists in the synthetic population
        # but is excluded from open_shop_ids because it is confirmed closed
        # on this Monday (the 月曜 candidate) -- distinct from a wholly
        # unknown shop id.
        full_population, _origin = acceptance_state.gathering_population_source()
        closed_shop_id = next(
            candidate.provider_page_url
            for candidate in full_population
            if candidate.provider_page_url not in self.open_shop_ids
        )

        with self.assertRaises(services.InvalidShopSelectionError):
            services.set_shortlisted_shops(self.user, self.gathering.id, [closed_shop_id])

    def test_accepts_exactly_one_shop(self):
        gathering = services.set_shortlisted_shops(
            self.user, self.gathering.id, [self.open_shop_ids[0]]
        )

        shops = list(gathering.shortlisted_shops.all())
        self.assertEqual([shop.shop_id for shop in shops], [self.open_shop_ids[0]])

    def test_accepts_exactly_five_shops(self):
        gathering = services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids)

        self.assertEqual(gathering.shortlisted_shops.count(), 5)

    def test_first_successful_call_sets_voting_started_at(self):
        self.assertIsNone(self.gathering.voting_started_at)

        gathering = services.set_shortlisted_shops(
            self.user, self.gathering.id, self.open_shop_ids[:2]
        )

        self.assertIsNotNone(gathering.voting_started_at)

    def test_never_advances_the_gathering_phase(self):
        gathering = services.set_shortlisted_shops(
            self.user, self.gathering.id, self.open_shop_ids[:2]
        )

        self.assertEqual(gathering.phase, GatheringPhase.SELECTING_SHOP)

    def test_replacing_a_shop_that_stays_keeps_its_added_at(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        first_added_at = ShortlistedShop.objects.get(
            gathering=self.gathering, shop_id=self.open_shop_ids[0]
        ).added_at

        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:1])

        kept = ShortlistedShop.objects.get(gathering=self.gathering, shop_id=self.open_shop_ids[0])
        self.assertEqual(kept.added_at, first_added_at)

    def test_replacing_drops_a_shop_no_longer_selected(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])

        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:1])

        self.assertFalse(
            ShortlistedShop.objects.filter(
                gathering=self.gathering, shop_id=self.open_shop_ids[1]
            ).exists()
        )

    def test_a_newly_added_shop_gets_a_fresh_added_at(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:1])
        _backdate_shortlisted_shop(self.gathering, self.open_shop_ids[0])
        first_added_at = ShortlistedShop.objects.get(
            gathering=self.gathering, shop_id=self.open_shop_ids[0]
        ).added_at

        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])

        newly_added = ShortlistedShop.objects.get(
            gathering=self.gathering, shop_id=self.open_shop_ids[1]
        )
        self.assertGreater(newly_added.added_at, first_added_at)

    def test_re_adding_a_removed_shop_is_a_brand_new_entry(self):
        link = self.issue_link()
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[0]))
        first_id = ShortlistedShop.objects.get(
            gathering=self.gathering, shop_id=self.open_shop_ids[0]
        ).id

        # Remove it (replace with a different shop) then re-add it.
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[1]])
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        # Guard against the re-added row's fresh added_at tying with the
        # earlier vote's submitted_at on a coarse system clock (see
        # _forward_date_shortlisted_shop's own docstring).
        _forward_date_shortlisted_shop(self.gathering, self.open_shop_ids[0])

        re_added = ShortlistedShop.objects.get(
            gathering=self.gathering, shop_id=self.open_shop_ids[0]
        )
        self.assertNotEqual(re_added.id, first_id)
        tally = services.shortlisted_shops_with_tallies(self.gathering)[0]
        self.assertEqual(tally.want_to_go_count, 0)
        self.assertEqual(tally.ok_to_go_count, 0)
        self.assertEqual(tally.not_going_count, 0)
        self.assertEqual(tally.responded_participant_count, 0)


class FinalizeGatheringServiceTests(GatheringSelectingShopServiceTestCase):
    def test_rejected_while_still_scheduling(self):
        scheduling_gathering = services.create_gathering(self.user, "別の会", [timezone.now()])

        with self.assertRaises(services.GatheringNotInSelectingShopPhaseError):
            services.finalize_gathering(self.user, scheduling_gathering.id, self.open_shop_ids[0])

    def test_rejected_before_any_shop_has_been_shortlisted(self):
        with self.assertRaises(services.ShopVotingNotStartedError):
            services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[0])

    def test_rejected_once_already_finalized(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[0])

        with self.assertRaises(services.GatheringFinalizedError):
            services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[0])

    def test_rejects_a_shop_not_currently_shortlisted(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])

        with self.assertRaises(services.InvalidShopSelectionError):
            services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[1])

    def test_finalizes_and_advances_the_phase(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])

        gathering = services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[0])

        self.assertEqual(gathering.phase, GatheringPhase.FINALIZED)
        self.assertEqual(gathering.finalized_shop_id, self.open_shop_ids[0])

    def test_never_auto_selects_the_top_voted_shop(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        popular_link = self.issue_link()
        other_link = self.issue_link()
        services.set_shop_votes(popular_link.token, _want_to_go(self.open_shop_ids[0]))
        services.set_shop_votes(other_link.token, _want_to_go(self.open_shop_ids[0]))
        # open_shop_ids[1] has zero votes, yet the organizer may still choose it.

        gathering = services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[1])

        self.assertEqual(gathering.finalized_shop_id, self.open_shop_ids[1])


class SetShopVotesServiceTests(GatheringSelectingShopServiceTestCase):
    def test_rejected_before_any_shop_has_been_shortlisted(self):
        link = self.issue_link()

        with self.assertRaises(services.ShopVotingNotStartedError):
            services.set_shop_votes(link.token, [])

    def test_rejected_once_finalized(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()
        services.finalize_gathering(self.user, self.gathering.id, self.open_shop_ids[0])

        with self.assertRaises(services.GatheringFinalizedError):
            services.set_shop_votes(link.token, [])

    def test_rejects_a_duplicate_shop_id(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()

        with self.assertRaises(services.InvalidShopSelectionError):
            services.set_shop_votes(
                link.token, _want_to_go(self.open_shop_ids[0], self.open_shop_ids[0])
            )

    def test_rejects_a_shop_not_currently_shortlisted(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()

        with self.assertRaises(services.InvalidShopSelectionError):
            services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[1]))

    def test_empty_selection_is_a_valid_answer(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()

        services.set_shop_votes(link.token, [])

        submission = ShopVoteSubmission.objects.get(participant_link=link)
        self.assertEqual(submission.votes, {})

    def test_replaces_the_entire_vote_rather_than_toggling(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        link = self.issue_link()
        services.set_shop_votes(
            link.token, _want_to_go(self.open_shop_ids[0], self.open_shop_ids[1])
        )

        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[1]))

        submission = ShopVoteSubmission.objects.get(participant_link=link)
        self.assertEqual(submission.votes, {self.open_shop_ids[1]: ShopVoteStatus.WANT_TO_GO.value})

    def test_records_each_of_the_three_tiers(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:3])
        link = self.issue_link()

        services.set_shop_votes(
            link.token,
            [
                (self.open_shop_ids[0], ShopVoteStatus.WANT_TO_GO.value),
                (self.open_shop_ids[1], ShopVoteStatus.OK_TO_GO.value),
                (self.open_shop_ids[2], ShopVoteStatus.NOT_GOING.value),
            ],
        )

        submission = ShopVoteSubmission.objects.get(participant_link=link)
        self.assertEqual(
            submission.votes,
            {
                self.open_shop_ids[0]: ShopVoteStatus.WANT_TO_GO.value,
                self.open_shop_ids[1]: ShopVoteStatus.OK_TO_GO.value,
                self.open_shop_ids[2]: ShopVoteStatus.NOT_GOING.value,
            },
        )

    def test_a_shop_omitted_from_votes_is_left_not_yet_answered(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        link = self.issue_link()

        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[0]))

        shop_lookup, origin = self.shop_lookup_and_origin()
        options = {
            option.shortlisted_shop.shop_id: option
            for option in services.participant_shop_vote_options(link, shop_lookup, origin)
        }
        self.assertEqual(options[self.open_shop_ids[0]].your_vote, ShopVoteStatus.WANT_TO_GO.value)
        self.assertIsNone(options[self.open_shop_ids[1]].your_vote)

    def test_unknown_token_is_not_found(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])

        with self.assertRaises(services.LinkNotFoundError):
            services.set_shop_votes("does-not-exist", [])

    def test_revoked_link_is_rejected(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()
        services.revoke_participant_link(self.user, self.gathering.id, link.id)

        with self.assertRaises(services.LinkRevokedError):
            services.set_shop_votes(link.token, [])


class ShortlistedShopsWithTalliesServiceTests(GatheringSelectingShopServiceTestCase):
    def test_a_shop_with_no_votes_has_zero_tallies(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])

        tallies = services.shortlisted_shops_with_tallies(self.gathering)

        self.assertEqual(len(tallies), 1)
        self.assertEqual(tallies[0].want_to_go_count, 0)
        self.assertEqual(tallies[0].ok_to_go_count, 0)
        self.assertEqual(tallies[0].not_going_count, 0)
        self.assertEqual(tallies[0].responded_participant_count, 0)

    def test_counts_only_participants_whose_submission_answers_this_shop(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        wants_first = self.issue_link()
        wants_second = self.issue_link()
        services.set_shop_votes(wants_first.token, _want_to_go(self.open_shop_ids[0]))
        services.set_shop_votes(wants_second.token, _want_to_go(self.open_shop_ids[1]))

        tallies = {
            tally.shortlisted_shop.shop_id: tally
            for tally in services.shortlisted_shops_with_tallies(self.gathering)
        }

        self.assertEqual(tallies[self.open_shop_ids[0]].want_to_go_count, 1)
        self.assertEqual(tallies[self.open_shop_ids[0]].responded_participant_count, 1)
        self.assertEqual(tallies[self.open_shop_ids[1]].want_to_go_count, 1)
        self.assertEqual(tallies[self.open_shop_ids[1]].responded_participant_count, 1)

    def test_want_to_go_and_ok_to_go_are_counted_separately(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        wants = self.issue_link()
        ok_with = self.issue_link()
        not_going = self.issue_link()
        services.set_shop_votes(
            wants.token, [(self.open_shop_ids[0], ShopVoteStatus.WANT_TO_GO.value)]
        )
        services.set_shop_votes(
            ok_with.token, [(self.open_shop_ids[0], ShopVoteStatus.OK_TO_GO.value)]
        )
        services.set_shop_votes(
            not_going.token, [(self.open_shop_ids[0], ShopVoteStatus.NOT_GOING.value)]
        )

        tally = services.shortlisted_shops_with_tallies(self.gathering)[0]

        self.assertEqual(tally.want_to_go_count, 1)
        self.assertEqual(tally.ok_to_go_count, 1)
        self.assertEqual(tally.not_going_count, 1)
        self.assertEqual(tally.responded_participant_count, 3)

    def test_a_shop_omitted_from_a_submission_does_not_count_toward_its_tally(self):
        # A participant who answers shop[0] but leaves shop[1] unanswered in
        # the same setShopVotes call must not count toward shop[1]'s
        # respondedParticipantCount -- omission is per-shop, not per-request
        # (SetShopVotesRequest's own rule, distinct from the prior boolean
        # model's per-submission gating).
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        link = self.issue_link()
        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[0]))

        tallies = {
            tally.shortlisted_shop.shop_id: tally
            for tally in services.shortlisted_shops_with_tallies(self.gathering)
        }

        self.assertEqual(tallies[self.open_shop_ids[0]].responded_participant_count, 1)
        self.assertEqual(tallies[self.open_shop_ids[1]].responded_participant_count, 0)

    def test_d7_replaced_shop_keeps_its_own_tally(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        link = self.issue_link()
        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[0]))

        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:1])

        tallies = services.shortlisted_shops_with_tallies(self.gathering)
        self.assertEqual(tallies[0].want_to_go_count, 1)
        self.assertEqual(tallies[0].responded_participant_count, 1)

    def test_d7_newly_added_shop_starts_at_zero_even_if_everyone_already_voted(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()
        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[0]))

        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        # Guard against the newly added shop's added_at tying with the
        # earlier vote's submitted_at on a coarse system clock (see
        # _forward_date_shortlisted_shop's own docstring) -- shop[0] itself
        # is untouched by this call (kept, not recreated).
        _forward_date_shortlisted_shop(self.gathering, self.open_shop_ids[1])

        tallies = {
            tally.shortlisted_shop.shop_id: tally
            for tally in services.shortlisted_shops_with_tallies(self.gathering)
        }
        self.assertEqual(tallies[self.open_shop_ids[1]].want_to_go_count, 0)
        self.assertEqual(tallies[self.open_shop_ids[1]].responded_participant_count, 0)
        # The pre-existing shop's own tally is unaffected by the addition.
        self.assertEqual(tallies[self.open_shop_ids[0]].want_to_go_count, 1)
        self.assertEqual(tallies[self.open_shop_ids[0]].responded_participant_count, 1)

    def test_ordered_by_want_to_go_plus_ok_to_go_descending(self):
        # ADR-0044 decision 3: the sum of the two positive tiers, not either
        # alone -- an "OK with it" vote for shop[1] outranks a "want to go"
        # vote for shop[0] once shop[1] also has more total support.
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        wants_shop_0 = self.issue_link()
        ok_with_shop_1 = self.issue_link()
        also_wants_shop_1 = self.issue_link()
        services.set_shop_votes(
            wants_shop_0.token, [(self.open_shop_ids[0], ShopVoteStatus.WANT_TO_GO.value)]
        )
        services.set_shop_votes(
            ok_with_shop_1.token, [(self.open_shop_ids[1], ShopVoteStatus.OK_TO_GO.value)]
        )
        services.set_shop_votes(
            also_wants_shop_1.token, [(self.open_shop_ids[1], ShopVoteStatus.WANT_TO_GO.value)]
        )

        tallies = services.shortlisted_shops_with_tallies(self.gathering)

        self.assertEqual(tallies[0].shortlisted_shop.shop_id, self.open_shop_ids[1])
        self.assertEqual(tallies[0].want_to_go_count + tallies[0].ok_to_go_count, 2)
        self.assertEqual(tallies[1].shortlisted_shop.shop_id, self.open_shop_ids[0])
        self.assertEqual(tallies[1].want_to_go_count + tallies[1].ok_to_go_count, 1)


class ParticipantShopVoteOptionsServiceTests(GatheringSelectingShopServiceTestCase):
    def test_your_vote_is_none_before_voting(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()
        shop_lookup, origin = self.shop_lookup_and_origin()

        options = services.participant_shop_vote_options(link, shop_lookup, origin)

        self.assertEqual(len(options), 1)
        self.assertIsNone(options[0].your_vote)

    def test_your_vote_reflects_the_latest_submission(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        link = self.issue_link()
        services.set_shop_votes(
            link.token,
            [
                (self.open_shop_ids[0], ShopVoteStatus.WANT_TO_GO.value),
                (self.open_shop_ids[1], ShopVoteStatus.NOT_GOING.value),
            ],
        )
        shop_lookup, origin = self.shop_lookup_and_origin()

        options = {
            option.shortlisted_shop.shop_id: option
            for option in services.participant_shop_vote_options(link, shop_lookup, origin)
        }

        self.assertEqual(options[self.open_shop_ids[0]].your_vote, ShopVoteStatus.WANT_TO_GO.value)
        self.assertEqual(options[self.open_shop_ids[1]].your_vote, ShopVoteStatus.NOT_GOING.value)

    def test_ordered_nearest_first_and_stable_across_votes(self):
        # ADR-0044 decision 2: the participant-facing order is nearest-first
        # by distance from the search origin, and must not change when any
        # vote is cast (the production defect this decision fixes).
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids)
        link = self.issue_link()
        shop_lookup, origin = self.shop_lookup_and_origin()

        before = [
            option.shortlisted_shop.shop_id
            for option in services.participant_shop_vote_options(link, shop_lookup, origin)
        ]
        # The population itself is already nearest-first (see
        # open_shop_population's own ordering guarantee), so it is the
        # oracle this test compares against.
        self.assertEqual(before, self.open_shop_ids)

        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[-1]))
        after = [
            option.shortlisted_shop.shop_id
            for option in services.participant_shop_vote_options(link, shop_lookup, origin)
        ]
        self.assertEqual(after, before)

    def test_d7_a_shop_added_after_this_participants_last_vote_is_not_yet_answered(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, [self.open_shop_ids[0]])
        link = self.issue_link()
        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[0]))
        first_submitted_at = ShopVoteSubmission.objects.get(participant_link=link).submitted_at

        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:2])
        # Anchor every remaining timestamp in this test to
        # first_submitted_at with fixed offsets, rather than chaining more
        # real timezone.now() calls -- two back-to-back calls can tie on a
        # coarse system clock (observed on Windows), and this test needs
        # three distinct instants in a strict order (vote, shop added,
        # second vote).
        ShortlistedShop.objects.filter(
            gathering=self.gathering, shop_id=self.open_shop_ids[1]
        ).update(added_at=first_submitted_at + timedelta(seconds=1))

        shop_lookup, origin = self.shop_lookup_and_origin()
        options = {
            option.shortlisted_shop.shop_id: option
            for option in services.participant_shop_vote_options(link, shop_lookup, origin)
        }
        self.assertIsNone(options[self.open_shop_ids[1]].your_vote)

        # Voting again resolves the "not yet answered" state.
        services.set_shop_votes(link.token, _want_to_go(self.open_shop_ids[1]))
        ShopVoteSubmission.objects.filter(participant_link=link).update(
            submitted_at=first_submitted_at + timedelta(seconds=2)
        )
        resolved = {
            option.shortlisted_shop.shop_id: option
            for option in services.participant_shop_vote_options(link, shop_lookup, origin)
        }
        self.assertEqual(resolved[self.open_shop_ids[1]].your_vote, ShopVoteStatus.WANT_TO_GO.value)


class ShortlistedShopsNearestFirstServiceTests(GatheringSelectingShopServiceTestCase):
    """The unresolvable-shop fallback ordering (developer discretion, FR-028).

    Covers ``_shop_distance_or_none``'s two ``None``-returning branches: no
    resolved search origin at all (a provider outage), and a shop id no
    longer present in a fresh population refetch -- both genuinely rare
    edge cases no TDR-GTH scenario exercises (ADR-0034 decision 6's live
    projection is never persisted).
    """

    def test_every_shop_pushed_to_the_end_in_original_order_when_origin_is_none(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:3])
        shop_lookup, _origin = self.shop_lookup_and_origin()

        ordered = services.shortlisted_shops_nearest_first(self.gathering, shop_lookup, None)

        # Every shop is equally unresolvable (no origin to measure distance
        # from at all) -- Python's stable sort keeps the original
        # (added_at ascending) order among them, the same fallback order
        # this function's own docstring documents.
        self.assertEqual(
            [shop.shop_id for shop in ordered],
            [
                shop.shop_id
                for shop in ShortlistedShop.objects.filter(gathering=self.gathering).order_by(
                    "added_at"
                )
            ],
        )

    def test_a_shop_missing_from_the_lookup_sorts_after_every_resolvable_shop(self):
        services.set_shortlisted_shops(self.user, self.gathering.id, self.open_shop_ids[0:3])
        shop_lookup, origin = self.shop_lookup_and_origin()
        # Simulate open_shop_ids[1] having vanished from a fresh population
        # refetch (a real provider-side change between calls) without
        # touching the other two shops' own resolvable entries.
        incomplete_lookup = dict(shop_lookup)
        del incomplete_lookup[self.open_shop_ids[1]]

        ordered = services.shortlisted_shops_nearest_first(
            self.gathering, incomplete_lookup, origin
        )

        self.assertEqual(ordered[-1].shop_id, self.open_shop_ids[1])
        self.assertEqual(
            {shop.shop_id for shop in ordered[:-1]}, {self.open_shop_ids[0], self.open_shop_ids[2]}
        )


# --- JSON API: organizer endpoints -------------------------------------------


class CreateGatheringApiTests(GatheringOrganizerTestCase):
    def test_unauthenticated_request_is_a_safe_401(self):
        anonymous_client = Client(enforce_csrf_checks=True)

        response = anonymous_client.post(
            reverse("gathering:gatherings"),
            data=json.dumps(
                {"title": "会", "candidateDates": [{"startAt": "2026-09-01T00:00:00Z"}]}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTHENTICATION_REQUIRED")

    def test_missing_csrf_token_is_a_safe_400(self):
        response = self.client.post(
            reverse("gathering:gatherings"),
            data=json.dumps(
                {"title": "会", "candidateDates": [{"startAt": "2026-09-01T00:00:00Z"}]}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_creates_a_gathering_with_its_candidate_dates(self):
        payload = self.create_gathering_via_api(
            title="第7回 社内ランチ会",
            candidate_dates=[
                {"startAt": "2026-09-02T12:00:00+09:00"},
                {"startAt": "2026-09-03T12:30:00+09:00"},
            ],
        )

        self.assertEqual(payload["title"], "第7回 社内ランチ会")
        self.assertEqual(payload["phase"], "SCHEDULING")
        self.assertEqual(len(payload["candidateDates"]), 2)
        self.assertIsNone(payload["confirmedCandidateDateId"])

    def test_response_has_exactly_the_contract_shape(self):
        payload = self.create_gathering_via_api()

        self.assertEqual(
            set(payload),
            {
                "id",
                "title",
                "phase",
                "createdAt",
                "candidateDates",
                "totalIssuedParticipantLinks",
                "totalRevokedParticipantLinks",
                "activeParticipantLinkCount",
                "respondedParticipantCount",
                "anonymousRespondedParticipantCount",
                "confirmedCandidateDateId",
                "votingStartedAt",
                "shortlistedShops",
                "finalizedShopId",
            },
        )
        self.assertIsNone(payload["votingStartedAt"])
        self.assertEqual(payload["shortlistedShops"], [])
        self.assertIsNone(payload["finalizedShopId"])
        self.assertEqual(
            set(payload["candidateDates"][0]),
            {"id", "startAt", "goingCount", "maybeCount", "notGoingCount", "isConfirmed"},
        )

    def test_missing_candidate_dates_is_rejected(self):
        response = self.post_json(reverse("gathering:gatherings"), {"title": "会"})

        self.assertEqual(response.status_code, 400)

    def test_empty_candidate_dates_array_is_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"), {"title": "会", "candidateDates": []}
        )

        self.assertEqual(response.status_code, 400)

    def test_unexpected_property_is_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"),
            {
                "title": "会",
                "candidateDates": [{"startAt": "2026-09-01T00:00:00Z"}],
                "unexpected": True,
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_a_utc_offset_start_at_round_trips_through_the_same_instant(self):
        # Coordinator-reported concern (2026-09-02, tester defect-injection
        # measurement): a UTC-offset startAt might come back shifted by
        # TIME_ZONE's own +09:00 offset (settings_base.py's Asia/Tokyo) if
        # something along parse -> store -> serialize path silently treated
        # the value as naive-then-localized instead of an already-aware
        # instant. This pins the exact reported input/output pair.
        response = self.post_json(
            reverse("gathering:gatherings"),
            {
                "title": "会",
                "candidateDates": [{"startAt": "2026-09-22T12:00:00+00:00"}],
            },
        )

        self.assertEqual(response.status_code, 201)
        returned = response.json()["candidateDates"][0]["startAt"]
        returned_instant = datetime.fromisoformat(returned)
        expected_instant = datetime.fromisoformat("2026-09-22T12:00:00+00:00")
        self.assertEqual(returned_instant, expected_instant)
        # Not just the same instant under a different offset label (Django's
        # own equality already normalizes that) -- pinned to the exact
        # literal offset too, since a "same instant, relabelled" round trip
        # would still surprise a caller expecting its own input echoed back
        # unchanged.
        self.assertEqual(returned, "2026-09-22T12:00:00+00:00")

    def test_created_at_is_an_iso_datetime_close_to_now(self):
        before = timezone.now()

        payload = self.create_gathering_via_api()

        after = timezone.now()
        created_at = datetime.fromisoformat(payload["createdAt"])
        self.assertLessEqual(before, created_at)
        self.assertLessEqual(created_at, after)

    def test_duplicate_candidate_dates_within_the_same_request_are_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"),
            {
                "title": "会",
                "candidateDates": [
                    {"startAt": "2026-09-02T12:00:00+09:00"},
                    {"startAt": "2026-09-02T12:00:00+09:00"},
                ],
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "DUPLICATE_CANDIDATE_DATE")

    def test_duplicate_candidate_dates_reject_before_creating_a_partial_gathering(self):
        before_count = Gathering.objects.count()

        self.post_json(
            reverse("gathering:gatherings"),
            {
                "title": "会",
                "candidateDates": [
                    {"startAt": "2026-09-02T12:00:00+09:00"},
                    {"startAt": "2026-09-02T12:00:00+09:00"},
                ],
            },
        )

        self.assertEqual(Gathering.objects.count(), before_count)

    def test_same_instant_different_offset_representation_is_still_a_duplicate(self):
        # 2026-09-02T12:00:00+09:00 and 2026-09-02T03:00:00Z name the exact
        # same instant -- aware-datetime equality (and therefore this
        # duplicate check) normalizes across the offset, matching startAt's
        # own "exact same date-time" wording (adr/0038).
        response = self.post_json(
            reverse("gathering:gatherings"),
            {
                "title": "会",
                "candidateDates": [
                    {"startAt": "2026-09-02T12:00:00+09:00"},
                    {"startAt": "2026-09-02T03:00:00Z"},
                ],
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "DUPLICATE_CANDIDATE_DATE")


class GetGatheringApiTests(GatheringOrganizerTestCase):
    def test_unauthenticated_request_is_a_safe_401(self):
        payload = self.create_gathering_via_api()
        anonymous_client = Client()

        response = anonymous_client.get(
            reverse("gathering:gathering-detail", kwargs={"gathering_id": payload["id"]})
        )

        self.assertEqual(response.status_code, 401)

    def test_unknown_gathering_is_a_safe_404(self):
        response = self.client.get(
            reverse("gathering:gathering-detail", kwargs={"gathering_id": uuid.uuid4()})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "GATHERING_NOT_FOUND")

    def test_another_organizers_gathering_is_a_safe_404(self):
        payload = self.create_gathering_via_api()
        other_client = Client()
        other_client.force_login(self.other_user)

        response = other_client.get(
            reverse("gathering:gathering-detail", kwargs={"gathering_id": payload["id"]})
        )

        self.assertEqual(response.status_code, 404)

    def test_returns_the_gathering(self):
        payload = self.create_gathering_via_api(title="別の会")

        response = self.client.get(
            reverse("gathering:gathering-detail", kwargs={"gathering_id": payload["id"]})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "別の会")


class ListGatheringsApiTests(GatheringOrganizerTestCase):
    def test_unauthenticated_request_is_a_safe_401(self):
        response = Client().get(reverse("gathering:gatherings"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTHENTICATION_REQUIRED")

    def test_empty_array_when_the_organizer_has_no_gathering(self):
        response = self.client.get(reverse("gathering:gatherings"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"gatherings": []})

    def test_ordered_by_created_at_descending(self):
        # See ListGatheringsServiceTests.test_ordered_by_created_at_descending
        # for why created_at is forced apart explicitly rather than relying
        # on real wall-clock spacing between the two API calls.
        now = timezone.now()
        first = self.create_gathering_via_api(title="1つめ")
        second = self.create_gathering_via_api(title="2つめ")
        Gathering.objects.filter(pk=first["id"]).update(created_at=now - timedelta(seconds=1))
        Gathering.objects.filter(pk=second["id"]).update(created_at=now)

        response = self.client.get(reverse("gathering:gatherings"))

        titles = [gathering["title"] for gathering in response.json()["gatherings"]]
        self.assertEqual(titles, [second["title"], first["title"]])

    def test_each_item_has_exactly_the_gathering_contract_shape(self):
        self.create_gathering_via_api()

        response = self.client.get(reverse("gathering:gatherings"))

        item = response.json()["gatherings"][0]
        self.assertEqual(
            set(item),
            {
                "id",
                "title",
                "phase",
                "createdAt",
                "candidateDates",
                "totalIssuedParticipantLinks",
                "totalRevokedParticipantLinks",
                "activeParticipantLinkCount",
                "respondedParticipantCount",
                "anonymousRespondedParticipantCount",
                "confirmedCandidateDateId",
                "votingStartedAt",
                "shortlistedShops",
                "finalizedShopId",
            },
        )

    def test_never_returns_another_organizers_gathering(self):
        other_client = Client()
        other_client.force_login(self.other_user)
        self.create_gathering_via_api()

        response = other_client.get(reverse("gathering:gatherings"))

        self.assertEqual(response.json(), {"gatherings": []})


class InProgressGatheringCountApiTests(GatheringOrganizerTestCase):
    def test_unauthenticated_request_is_a_safe_401(self):
        response = Client().get(reverse("gathering:in-progress-count"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTHENTICATION_REQUIRED")

    def test_zero_when_the_organizer_has_no_gathering(self):
        response = self.client.get(reverse("gathering:in-progress-count"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"inProgressGatheringCount": 0})

    def test_counts_scheduling_and_selecting_shop_but_not_finalized(self):
        self.create_gathering_via_api()  # SCHEDULING
        selecting = self.create_gathering_via_api()
        selecting_gathering = Gathering.objects.get(id=selecting["id"])
        selecting_gathering.phase = GatheringPhase.SELECTING_SHOP
        selecting_gathering.save(update_fields=["phase"])
        finalized = self.create_gathering_via_api()
        finalized_gathering = Gathering.objects.get(id=finalized["id"])
        finalized_gathering.phase = GatheringPhase.FINALIZED
        finalized_gathering.save(update_fields=["phase"])

        response = self.client.get(reverse("gathering:in-progress-count"))

        self.assertEqual(response.json()["inProgressGatheringCount"], 2)

    def test_never_counts_another_organizers_gathering(self):
        other_client = Client()
        other_client.force_login(self.other_user)
        self.create_gathering_via_api()

        response = other_client.get(reverse("gathering:in-progress-count"))

        self.assertEqual(response.json(), {"inProgressGatheringCount": 0})


class AddCandidateDateApiTests(GatheringOrganizerTestCase):
    def test_adds_a_candidate_date(self):
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-01T00:00:00Z"}]
        )

        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": payload["id"]}),
            {"startAt": "2026-09-05T00:00:00Z"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["candidateDates"]), 2)

    def test_a_utc_offset_start_at_round_trips_through_the_same_instant(self):
        # Same coordinator-reported concern as
        # CreateGatheringApiTests.test_a_utc_offset_start_at_round_trips_
        # through_the_same_instant, pinned against addCandidateDate too
        # (a distinct code path -- services.add_candidate_date, not
        # services.create_gathering).
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-01-01T00:00:00Z"}]
        )

        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": payload["id"]}),
            {"startAt": "2026-09-22T12:00:00+00:00"},
        )

        self.assertEqual(response.status_code, 201)
        added = next(
            cd
            for cd in response.json()["candidateDates"]
            if cd["startAt"] != "2026-01-01T00:00:00+00:00"
        )
        self.assertEqual(added["startAt"], "2026-09-22T12:00:00+00:00")

    def test_rejected_after_confirming_a_date(self):
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-01T00:00:00Z"}]
        )
        gathering_id = payload["id"]
        candidate_date_id = payload["candidateDates"][0]["id"]
        self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": gathering_id}),
            {"candidateDateId": candidate_date_id},
        )

        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": gathering_id}),
            {"startAt": "2026-09-06T00:00:00Z"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_NOT_IN_SCHEDULING_PHASE")

    def test_malformed_start_at_is_rejected(self):
        payload = self.create_gathering_via_api()

        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": payload["id"]}),
            {"startAt": "not-a-date"},
        )

        self.assertEqual(response.status_code, 400)

    def test_duplicate_candidate_date_is_rejected(self):
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-05T00:00:00Z"}]
        )

        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": payload["id"]}),
            {"startAt": "2026-09-05T00:00:00Z"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "DUPLICATE_CANDIDATE_DATE")

    def test_duplicate_candidate_date_does_not_change_the_existing_candidate_dates(self):
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-05T00:00:00Z"}]
        )

        self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": payload["id"]}),
            {"startAt": "2026-09-05T00:00:00Z"},
        )

        response = self.client.get(
            reverse("gathering:gathering-detail", kwargs={"gathering_id": payload["id"]})
        )
        self.assertEqual(len(response.json()["candidateDates"]), 1)

    def test_duplicate_candidate_date_with_a_different_offset_is_still_rejected(self):
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-05T09:00:00+09:00"}]
        )

        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": payload["id"]}),
            {"startAt": "2026-09-05T00:00:00Z"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "DUPLICATE_CANDIDATE_DATE")


class ConfirmDateApiTests(GatheringOrganizerTestCase):
    def test_confirms_and_advances_the_phase(self):
        payload = self.create_gathering_via_api()
        candidate_date_id = payload["candidateDates"][0]["id"]

        response = self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": payload["id"]}),
            {"candidateDateId": candidate_date_id},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["phase"], "SELECTING_SHOP")
        self.assertEqual(body["confirmedCandidateDateId"], candidate_date_id)
        confirmed = next(cd for cd in body["candidateDates"] if cd["id"] == candidate_date_id)
        self.assertTrue(confirmed["isConfirmed"])

    def test_unknown_candidate_date_is_a_safe_404(self):
        payload = self.create_gathering_via_api()

        response = self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": payload["id"]}),
            {"candidateDateId": str(uuid.uuid4())},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "CANDIDATE_DATE_NOT_FOUND")

    def test_only_one_candidate_date_may_ever_be_confirmed(self):
        payload = self.create_gathering_via_api()
        first_id = payload["candidateDates"][0]["id"]
        second_id = payload["candidateDates"][1]["id"]
        self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": payload["id"]}),
            {"candidateDateId": first_id},
        )

        response = self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": payload["id"]}),
            {"candidateDateId": second_id},
        )

        self.assertEqual(response.status_code, 409)


class OpenShopPreviewApiTests(GatheringOrganizerTestCase):
    def test_returns_the_preview_without_changing_phase(self):
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-07T12:00:00+09:00"}]  # Monday
        )
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.GATHERING_OPEN_SHOP_WEEKDAY_MATCH
        )
        candidate_date_id = payload["candidateDates"][0]["id"]

        response = self.client.get(
            reverse(
                "gathering:open-shop-preview",
                kwargs={"gathering_id": payload["id"], "candidate_date_id": candidate_date_id},
            )
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["candidateDateId"], candidate_date_id)
        self.assertEqual(body["openShopCount"], 5)
        self.assertLessEqual(len(body["previewShops"]), 10)

        get_gathering = self.client.get(
            reverse("gathering:gathering-detail", kwargs={"gathering_id": payload["id"]})
        )
        self.assertEqual(get_gathering.json()["phase"], "SCHEDULING")

    def test_preview_shop_item_has_exactly_the_contract_shape(self):
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-07T12:00:00+09:00"}]
        )
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.GATHERING_OPEN_SHOP_WEEKDAY_MATCH
        )
        candidate_date_id = payload["candidateDates"][0]["id"]

        response = self.client.get(
            reverse(
                "gathering:open-shop-preview",
                kwargs={"gathering_id": payload["id"], "candidate_date_id": candidate_date_id},
            )
        )

        item = response.json()["previewShops"][0]
        self.assertEqual(
            set(item),
            {
                "shopId",
                "name",
                "genre",
                "capacityTier",
                "nonSmokingStatus",
                "dinnerBudgetTier",
                "location",
                "walkingTimeMinutes",
                "providerPageUrl",
            },
        )
        self.assertTrue(item["shopId"])
        self.assertEqual(set(item["location"]), {"latitude", "longitude"})


# --- JSON API: shop shortlisting, approval voting, finalization (adr/0040) --


class GatheringSelectingShopApiTestCase(GatheringOrganizerTestCase):
    """Shared fixture: a SELECTING_SHOP gathering with 5 known-open shop ids, via HTTP."""

    def setUp(self):
        super().setUp()
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.GATHERING_OPEN_SHOP_WEEKDAY_MATCH
        )
        payload = self.create_gathering_via_api(
            candidate_dates=[{"startAt": "2026-09-07T12:00:00+09:00"}]  # a Monday
        )
        self.gathering_id = payload["id"]
        self.candidate_date_id = payload["candidateDates"][0]["id"]
        confirm_response = self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": self.gathering_id}),
            {"candidateDateId": self.candidate_date_id},
        )
        assert confirm_response.status_code == 200, confirm_response.content
        preview = self.client.get(
            reverse(
                "gathering:open-shop-preview",
                kwargs={
                    "gathering_id": self.gathering_id,
                    "candidate_date_id": self.candidate_date_id,
                },
            )
        ).json()
        self.open_shop_ids = [item["shopId"] for item in preview["previewShops"]]
        assert len(self.open_shop_ids) == 5

    def issue_token(self) -> str:
        response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            {"count": 1},
        )
        return response.json()["issuedLinks"][0]["token"]

    def put_shortlisted_shops(self, shop_ids) -> object:
        return self.put_json(
            reverse("gathering:shortlisted-shops", kwargs={"gathering_id": self.gathering_id}),
            {"shopIds": shop_ids},
        )

    def post_finalize(self, shop_id: str) -> object:
        return self.post_json(
            reverse("gathering:finalize", kwargs={"gathering_id": self.gathering_id}),
            {"shopId": shop_id},
        )

    @staticmethod
    def put_shop_votes(token: str, votes) -> object:
        """``votes``: a list of ``(shopId, status)`` tuples (adr/0044)."""
        return Client().put(
            reverse("gathering:shop-votes", kwargs={"token": token}),
            data=json.dumps(
                {"votes": [{"shopId": shop_id, "status": status} for shop_id, status in votes]}
            ),
            content_type="application/json",
        )

    def put_want_to_go(self, token: str, *shop_ids: str) -> object:
        return self.put_shop_votes(token, _want_to_go(*shop_ids))


class SetShortlistedShopsApiTests(GatheringSelectingShopApiTestCase):
    def test_replaces_the_shortlist_and_returns_the_updated_gathering(self):
        response = self.put_shortlisted_shops(self.open_shop_ids[0:2])

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNotNone(body["votingStartedAt"])
        self.assertEqual(
            {shop["shopId"] for shop in body["shortlistedShops"]}, set(self.open_shop_ids[0:2])
        )
        self.assertEqual(body["phase"], "SELECTING_SHOP")

    def test_shortlisted_shop_item_has_exactly_the_contract_shape(self):
        response = self.put_shortlisted_shops([self.open_shop_ids[0]])

        item = response.json()["shortlistedShops"][0]
        self.assertEqual(
            set(item),
            {
                "shopId",
                "name",
                "genre",
                "capacityTier",
                "nonSmokingStatus",
                "dinnerBudgetTier",
                "location",
                "walkingTimeMinutes",
                "providerPageUrl",
                "addedAt",
                "wantToGoCount",
                "okToGoCount",
                "notGoingCount",
                "respondedParticipantCount",
            },
        )

    def test_rejected_while_still_scheduling(self):
        scheduling_payload = self.create_gathering_via_api()

        response = self.put_json(
            reverse(
                "gathering:shortlisted-shops", kwargs={"gathering_id": scheduling_payload["id"]}
            ),
            {"shopIds": [self.open_shop_ids[0]]},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_NOT_IN_SELECTING_SHOP_PHASE")

    def test_rejected_once_finalized(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        self.post_finalize(self.open_shop_ids[0])

        response = self.put_shortlisted_shops([self.open_shop_ids[0]])

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_FINALIZED")

    def test_zero_shops_is_a_safe_400(self):
        response = self.put_shortlisted_shops([])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SHOP_SELECTION")

    def test_more_than_five_shops_is_a_safe_400(self):
        response = self.put_shortlisted_shops([*self.open_shop_ids, "a-sixth-shop"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SHOP_SELECTION")

    def test_a_duplicate_shop_id_is_a_safe_400(self):
        response = self.put_shortlisted_shops([self.open_shop_ids[0], self.open_shop_ids[0]])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SHOP_SELECTION")

    def test_a_shop_not_in_the_open_population_is_a_safe_400(self):
        response = self.put_shortlisted_shops(["not-a-real-shop"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SHOP_SELECTION")

    def test_unauthenticated_is_a_safe_401(self):
        response = Client().put(
            reverse("gathering:shortlisted-shops", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"shopIds": [self.open_shop_ids[0]]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_missing_csrf_is_a_safe_400(self):
        response = self.client.put(
            reverse("gathering:shortlisted-shops", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"shopIds": [self.open_shop_ids[0]]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_unknown_gathering_is_a_safe_404(self):
        response = self.put_json(
            reverse("gathering:shortlisted-shops", kwargs={"gathering_id": uuid.uuid4()}),
            {"shopIds": [self.open_shop_ids[0]]},
        )

        self.assertEqual(response.status_code, 404)

    def test_non_list_shop_ids_is_a_safe_400(self):
        response = self.put_json(
            reverse("gathering:shortlisted-shops", kwargs={"gathering_id": self.gathering_id}),
            {"shopIds": "not-a-list"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_non_string_shop_id_is_a_safe_400(self):
        response = self.put_json(
            reverse("gathering:shortlisted-shops", kwargs={"gathering_id": self.gathering_id}),
            {"shopIds": [123]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_extra_key_is_rejected(self):
        response = self.put_json(
            reverse("gathering:shortlisted-shops", kwargs={"gathering_id": self.gathering_id}),
            {"shopIds": [self.open_shop_ids[0]], "extra": True},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")


class FinalizeGatheringApiTests(GatheringSelectingShopApiTestCase):
    def test_finalizes_and_returns_the_updated_gathering(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])

        response = self.post_finalize(self.open_shop_ids[0])

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["phase"], "FINALIZED")
        self.assertEqual(body["finalizedShopId"], self.open_shop_ids[0])

    def test_rejected_before_voting_started(self):
        response = self.post_finalize(self.open_shop_ids[0])

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "SHOP_VOTING_NOT_STARTED")

    def test_rejected_while_still_scheduling(self):
        scheduling_payload = self.create_gathering_via_api()

        response = self.post_json(
            reverse("gathering:finalize", kwargs={"gathering_id": scheduling_payload["id"]}),
            {"shopId": self.open_shop_ids[0]},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_NOT_IN_SELECTING_SHOP_PHASE")

    def test_rejected_once_already_finalized(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        self.post_finalize(self.open_shop_ids[0])

        response = self.post_finalize(self.open_shop_ids[0])

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_FINALIZED")

    def test_never_auto_selects_the_top_voted_shop(self):
        self.put_shortlisted_shops(self.open_shop_ids[0:2])
        popular = self.issue_token()
        self.put_want_to_go(popular, self.open_shop_ids[0])

        response = self.post_finalize(self.open_shop_ids[1])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["finalizedShopId"], self.open_shop_ids[1])

    def test_a_shop_not_currently_shortlisted_is_a_safe_400(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])

        response = self.post_finalize(self.open_shop_ids[1])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SHOP_SELECTION")

    def test_unauthenticated_is_a_safe_401(self):
        response = Client().post(
            reverse("gathering:finalize", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"shopId": self.open_shop_ids[0]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_missing_csrf_is_a_safe_400(self):
        response = self.client.post(
            reverse("gathering:finalize", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"shopId": self.open_shop_ids[0]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unknown_gathering_is_a_safe_404(self):
        response = self.post_json(
            reverse("gathering:finalize", kwargs={"gathering_id": uuid.uuid4()}),
            {"shopId": self.open_shop_ids[0]},
        )

        self.assertEqual(response.status_code, 404)

    def test_missing_shop_id_is_rejected(self):
        response = self.post_json(
            reverse("gathering:finalize", kwargs={"gathering_id": self.gathering_id}), {}
        )

        self.assertEqual(response.status_code, 400)

    def test_non_string_shop_id_is_rejected(self):
        response = self.post_json(
            reverse("gathering:finalize", kwargs={"gathering_id": self.gathering_id}),
            {"shopId": 123},
        )

        self.assertEqual(response.status_code, 400)


class SetShopVotesApiTests(GatheringSelectingShopApiTestCase):
    def test_records_the_vote_and_returns_the_updated_participant_view(self):
        self.put_shortlisted_shops(self.open_shop_ids[0:2])
        token = self.issue_token()

        response = self.put_shop_votes(
            token,
            [
                (self.open_shop_ids[0], "WANT_TO_GO"),
                (self.open_shop_ids[1], "NOT_GOING"),
            ],
        )

        self.assertEqual(response.status_code, 200)
        options = {o["shopId"]: o for o in response.json()["shopVoteQuestions"]}
        self.assertEqual(options[self.open_shop_ids[0]]["yourVote"], "WANT_TO_GO")
        self.assertEqual(options[self.open_shop_ids[1]]["yourVote"], "NOT_GOING")

    def test_a_shop_omitted_from_votes_stays_unanswered(self):
        self.put_shortlisted_shops(self.open_shop_ids[0:2])
        token = self.issue_token()

        response = self.put_want_to_go(token, self.open_shop_ids[0])

        options = {o["shopId"]: o for o in response.json()["shopVoteQuestions"]}
        self.assertEqual(options[self.open_shop_ids[0]]["yourVote"], "WANT_TO_GO")
        self.assertIsNone(options[self.open_shop_ids[1]]["yourVote"])
        self.assertIsNone(options[self.open_shop_ids[1]]["tally"])

    def test_shop_vote_question_has_exactly_the_contract_shape(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = self.put_want_to_go(token, self.open_shop_ids[0])

        question = response.json()["shopVoteQuestions"][0]
        self.assertEqual(
            set(question),
            {
                "shopId",
                "name",
                "genre",
                "capacityTier",
                "nonSmokingStatus",
                "dinnerBudgetTier",
                "location",
                "walkingTimeMinutes",
                "providerPageUrl",
                "yourVote",
                "tally",
            },
        )
        self.assertIsNotNone(question["tally"])
        self.assertEqual(
            set(question["tally"]),
            {"wantToGoCount", "okToGoCount", "notGoingCount", "respondedParticipantCount"},
        )

    def test_tally_is_null_before_this_participant_answers(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = Client().get(reverse("gathering:participant-view", kwargs={"token": token}))

        question = response.json()["shopVoteQuestions"][0]
        self.assertIsNone(question["yourVote"])
        self.assertIsNone(question["tally"])

    def test_null_shop_vote_questions_before_voting_started(self):
        token = self.issue_token()

        response = Client().get(reverse("gathering:participant-view", kwargs={"token": token}))

        self.assertIsNone(response.json()["shopVoteQuestions"])

    def test_answering_after_others_reveals_their_votes(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        first = self.issue_token()
        second = self.issue_token()
        self.put_want_to_go(first, self.open_shop_ids[0])

        before = (
            Client().get(reverse("gathering:participant-view", kwargs={"token": second})).json()
        )
        self.assertIsNone(before["shopVoteQuestions"][0]["tally"])

        self.put_shop_votes(second, [(self.open_shop_ids[0], "NOT_GOING")])
        after = Client().get(reverse("gathering:participant-view", kwargs={"token": second})).json()

        self.assertEqual(after["shopVoteQuestions"][0]["tally"]["respondedParticipantCount"], 2)

    def test_rejected_before_voting_started(self):
        token = self.issue_token()

        response = self.put_shop_votes(token, [])

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "SHOP_VOTING_NOT_STARTED")

    def test_rejected_once_finalized(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()
        self.post_finalize(self.open_shop_ids[0])

        response = self.put_shop_votes(token, [])

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_FINALIZED")

    def test_a_shop_not_currently_shortlisted_is_a_safe_400(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = self.put_want_to_go(token, self.open_shop_ids[1])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SHOP_SELECTION")

    def test_a_duplicate_shop_id_is_a_safe_400(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = self.put_shop_votes(
            token,
            [(self.open_shop_ids[0], "WANT_TO_GO"), (self.open_shop_ids[0], "NOT_GOING")],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_SHOP_SELECTION")

    def test_unknown_token_is_a_safe_404(self):
        response = self.put_shop_votes("does-not-exist", [])

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "LINK_NOT_FOUND")

    def test_revoked_link_is_a_safe_410(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()
        link_id = ParticipantLink.objects.get(token=token).id
        self.post_json(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": self.gathering_id, "link_id": link_id},
            ),
            {},
        )

        response = self.put_shop_votes(token, [])

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "LINK_REVOKED")

    def test_non_list_votes_is_a_safe_400(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = Client().put(
            reverse("gathering:shop-votes", kwargs={"token": token}),
            data=json.dumps({"votes": "not-a-list"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_a_votes_entry_missing_a_key_is_a_safe_400(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = Client().put(
            reverse("gathering:shop-votes", kwargs={"token": token}),
            data=json.dumps({"votes": [{"shopId": self.open_shop_ids[0]}]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_a_non_string_shop_id_in_votes_is_a_safe_400(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = Client().put(
            reverse("gathering:shop-votes", kwargs={"token": token}),
            data=json.dumps({"votes": [{"shopId": 123, "status": "WANT_TO_GO"}]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_an_invalid_status_value_is_a_safe_400(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = Client().put(
            reverse("gathering:shop-votes", kwargs={"token": token}),
            data=json.dumps({"votes": [{"shopId": self.open_shop_ids[0], "status": "MAYBE"}]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_extra_key_is_rejected(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()

        response = Client().put(
            reverse("gathering:shop-votes", kwargs={"token": token}),
            data=json.dumps({"votes": [], "extra": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)


class FinalizedParticipantViewApiTests(GatheringSelectingShopApiTestCase):
    """``ParticipantView.decision`` (adr/0040, extended P5/adr/0041) -- TDR-GTH-33/34/35/36."""

    def test_decision_is_null_before_finalization(self):
        token = self.issue_token()

        response = Client().get(reverse("gathering:participant-view", kwargs={"token": token}))

        self.assertIsNone(response.json()["decision"])

    def test_decision_shows_the_finalized_date_and_shop(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()
        self.post_finalize(self.open_shop_ids[0])

        response = Client().get(reverse("gathering:participant-view", kwargs={"token": token}))

        body = response.json()
        self.assertEqual(body["phase"], "FINALIZED")
        self.assertEqual(body["decision"]["shop"]["shopId"], self.open_shop_ids[0])

    def test_decision_has_exactly_the_contract_shape(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()
        self.post_finalize(self.open_shop_ids[0])

        response = Client().get(reverse("gathering:participant-view", kwargs={"token": token}))

        decision = response.json()["decision"]
        self.assertEqual(
            set(decision),
            {"confirmedCandidateDate", "shop", "yourScheduleResponse", "yourShopVotes"},
        )
        self.assertEqual(
            set(decision["shop"]),
            {
                "shopId",
                "name",
                "genre",
                "capacityTier",
                "nonSmokingStatus",
                "dinnerBudgetTier",
                "location",
                "walkingTimeMinutes",
                "providerPageUrl",
            },
        )
        self.assertEqual(set(decision["yourShopVotes"][0]), {"shop", "status"})

    def test_decision_includes_this_participants_own_schedule_response(self):
        token = self.issue_token()
        Client().put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        self.post_finalize(self.open_shop_ids[0])

        response = Client().get(reverse("gathering:participant-view", kwargs={"token": token}))

        self.assertEqual(response.json()["decision"]["yourScheduleResponse"], "GOING")

    def test_decision_includes_only_this_participants_own_shop_votes(self):
        self.put_shortlisted_shops(self.open_shop_ids[0:2])
        wants_both = self.issue_token()
        answers_none = self.issue_token()
        self.put_shop_votes(
            wants_both,
            [
                (self.open_shop_ids[0], "WANT_TO_GO"),
                (self.open_shop_ids[1], "OK_TO_GO"),
            ],
        )
        self.post_finalize(self.open_shop_ids[0])

        both_view = (
            Client().get(reverse("gathering:participant-view", kwargs={"token": wants_both})).json()
        )
        none_view = (
            Client()
            .get(reverse("gathering:participant-view", kwargs={"token": answers_none}))
            .json()
        )

        both_votes = {
            v["shop"]["shopId"]: v["status"] for v in both_view["decision"]["yourShopVotes"]
        }
        self.assertEqual(both_votes[self.open_shop_ids[0]], "WANT_TO_GO")
        self.assertEqual(both_votes[self.open_shop_ids[1]], "OK_TO_GO")
        # answers_none never voted on either shop, and never sees wants_both's
        # votes reflected in their own decision -- each participant's
        # yourShopVotes is derived solely from their own recorded votes
        # (adr/0041 decision 3), and every shop they never voted on is
        # still listed, with a null status (adr/0046, 2026-09-05).
        none_votes = {
            v["shop"]["shopId"]: v["status"] for v in none_view["decision"]["yourShopVotes"]
        }
        self.assertEqual(none_votes, {shop_id: None for shop_id in self.open_shop_ids[0:2]})
        # LiveProjectedShop carries no aggregate/other-participant field at all.
        self.assertEqual(
            set(both_view["decision"]["yourShopVotes"][0]["shop"]),
            {
                "shopId",
                "name",
                "genre",
                "capacityTier",
                "nonSmokingStatus",
                "dinnerBudgetTier",
                "location",
                "walkingTimeMinutes",
                "providerPageUrl",
            },
        )

    def test_a_shop_this_participant_never_answered_is_included_with_a_null_status(self):
        # adr/0046 open item 3 (2026-09-05 human chat decision): a
        # never-answered shop appears in yourShopVotes with status: null
        # ("答えないまま締まりました"), rather than being omitted entirely.
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        token = self.issue_token()
        self.post_finalize(self.open_shop_ids[0])

        response = Client().get(reverse("gathering:participant-view", kwargs={"token": token}))

        votes = response.json()["decision"]["yourShopVotes"]
        self.assertEqual(len(votes), 1)
        self.assertEqual(votes[0]["shop"]["shopId"], self.open_shop_ids[0])
        self.assertIsNone(votes[0]["status"])

    def test_finalized_link_rejects_new_schedule_responses_and_shop_votes(self):
        token = self.issue_token()
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        self.post_finalize(self.open_shop_ids[0])

        schedule_response = Client().put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )
        vote_response = self.put_shop_votes(token, [])

        self.assertEqual(schedule_response.status_code, 409)
        self.assertEqual(schedule_response.json()["code"], "GATHERING_FINALIZED")
        self.assertEqual(vote_response.status_code, 409)
        self.assertEqual(vote_response.json()["code"], "GATHERING_FINALIZED")

    def test_recopy_still_works_after_finalize(self):
        token = self.issue_token()
        link_id = ParticipantLink.objects.get(token=token).id
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        self.post_finalize(self.open_shop_ids[0])

        response = self.post_json(
            reverse(
                "gathering:participant-link-recopy",
                kwargs={"gathering_id": self.gathering_id, "link_id": link_id},
            ),
            {},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], token)

    def test_new_link_issuance_is_rejected_after_finalize(self):
        self.put_shortlisted_shops([self.open_shop_ids[0]])
        self.post_finalize(self.open_shop_ids[0])

        response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            {"count": 1},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_FINALIZED")


class ParticipantLinkApiTests(GatheringOrganizerTestCase):
    def test_issue_participant_links_returns_a_usable_token_and_url(self):
        payload = self.create_gathering_via_api()

        response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(len(body["issuedLinks"]), 1)
        self.assertTrue(body["issuedLinks"][0]["token"])
        self.assertIn(body["issuedLinks"][0]["token"], body["issuedLinks"][0]["url"])
        self.assertEqual(body["totalIssuedParticipantLinks"], 1)
        self.assertEqual(body["activeParticipantLinkCount"], 1)

    def test_issued_link_url_is_reachable_as_the_participant_page(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        token = issue_response.json()["issuedLinks"][0]["token"]

        page = Client().get(reverse("gathering:participant-answer", kwargs={"token": token}))

        self.assertEqual(page.status_code, 200)

    def test_list_participant_links_never_exposes_a_token(self):
        payload = self.create_gathering_via_api()
        self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )

        response = self.client.get(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]})
        )

        body = response.json()
        self.assertEqual(len(body["participantLinks"]), 1)
        self.assertEqual(
            set(body["participantLinks"][0]),
            {"id", "issuedAt", "hasResponded", "revoked", "displayName"},
        )
        self.assertNotIn("token", json.dumps(body))
        self.assertNotIn("url", json.dumps(body))

    def test_recopy_returns_the_original_token_and_does_not_change_counters(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        token = issue_response.json()["issuedLinks"][0]["token"]
        link_id = ParticipantLink.objects.get(token=token).id

        response = self.post_json(
            reverse(
                "gathering:participant-link-recopy",
                kwargs={"gathering_id": payload["id"], "link_id": link_id},
            ),
            {},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], token)

    def test_recopy_a_revoked_link_is_a_safe_409(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        link_id = ParticipantLink.objects.get(
            token=issue_response.json()["issuedLinks"][0]["token"]
        ).id
        self.post_json(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": payload["id"], "link_id": link_id},
            ),
            {},
        )

        response = self.post_json(
            reverse(
                "gathering:participant-link-recopy",
                kwargs={"gathering_id": payload["id"], "link_id": link_id},
            ),
            {},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "PARTICIPANT_LINK_REVOKED")

    def test_revoke_updates_the_denominators(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        link_id = ParticipantLink.objects.get(
            token=issue_response.json()["issuedLinks"][0]["token"]
        ).id

        response = self.post_json(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": payload["id"], "link_id": link_id},
            ),
            {},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["participantLink"]["revoked"])
        self.assertEqual(body["gathering"]["totalRevokedParticipantLinks"], 1)
        self.assertEqual(body["gathering"]["activeParticipantLinkCount"], 0)

    def test_revoke_an_already_answered_link_is_a_safe_409(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        token = issue_response.json()["issuedLinks"][0]["token"]
        candidate_date_id = payload["candidateDates"][0]["id"]
        Client().put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": token, "candidate_date_id": candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )
        link_id = ParticipantLink.objects.get(token=token).id

        response = self.post_json(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": payload["id"], "link_id": link_id},
            ),
            {},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "PARTICIPANT_LINK_ALREADY_ANSWERED")


# --- JSON API: participant endpoints -----------------------------------------


class ParticipantViewApiTests(GatheringOrganizerTestCase):
    def setUp(self):
        super().setUp()
        payload = self.create_gathering_via_api(title="参加者テストの会")
        self.gathering_id = payload["id"]
        self.candidate_date_id = payload["candidateDates"][0]["id"]
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            {"count": 1},
        )
        self.token = issue_response.json()["issuedLinks"][0]["token"]
        self.participant_client = Client()

    def test_unknown_token_is_a_safe_404(self):
        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": "does-not-exist"})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "LINK_NOT_FOUND")

    def test_valid_token_returns_the_view_without_a_session(self):
        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["gatheringTitle"], "参加者テストの会")
        self.assertIsNone(body["displayName"])
        # create_gathering_via_api's default fixture has two candidate dates.
        self.assertEqual(len(body["scheduleQuestions"]), 2)

    def test_response_has_exactly_the_contract_shape(self):
        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        body = response.json()
        self.assertEqual(
            set(body),
            {
                "gatheringTitle",
                "phase",
                "displayName",
                "scheduleQuestions",
                "confirmedCandidateDate",
                "shopVoteQuestions",
                "searchOrigin",
                "decision",
            },
        )
        self.assertIsNone(body["shopVoteQuestions"])
        self.assertIsNone(body["searchOrigin"])
        self.assertIsNone(body["decision"])
        question = body["scheduleQuestions"][0]
        self.assertEqual(
            set(question), {"candidateDateId", "startAt", "openShopCount", "yourResponse"}
        )

    def test_expired_link_is_a_safe_410_link_expired(self):
        Client().post(
            "/test-support/gathering-scheduling/participant-links/expire",
            data=json.dumps({"token": self.token}),
            content_type="application/json",
        )

        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "LINK_EXPIRED")

    def test_revoked_link_is_a_safe_410_link_revoked(self):
        link_id = ParticipantLink.objects.get(token=self.token).id
        self.post_json(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": self.gathering_id, "link_id": link_id},
            ),
            {},
        )

        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "LINK_REVOKED")

    def test_rate_limited_link_is_a_safe_429_with_retry_after(self):
        Client().post(
            "/test-support/gathering-scheduling/participant-links/rate-limit",
            data=json.dumps({"token": self.token}),
            content_type="application/json",
        )

        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "LINK_RATE_LIMITED")
        self.assertTrue(response.has_header("Retry-After"))

    def test_server_error_seeded_link_is_a_bare_500_with_no_body(self):
        """adr/0047, TDR-GTH-42: deliberately not a ``ProblemResponse`` --
        no ``code``, no ``message`` -- so this failure carries none of
        linkError's four recognized codes by construction, and the browser
        has nothing technical to accidentally surface from this response."""
        Client().post(
            "/test-support/gathering-scheduling/participant-links/server-error",
            data=json.dumps({"token": self.token}),
            content_type="application/json",
        )

        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content, b"")

    def test_server_error_seed_only_affects_the_next_getParticipantView_call(self):
        Client().post(
            "/test-support/gathering-scheduling/participant-links/server-error",
            data=json.dumps({"token": self.token}),
            content_type="application/json",
        )
        self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 200)

    def test_set_schedule_response_no_csrf_token_required(self):
        response = self.participant_client.put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        question = next(
            q for q in body["scheduleQuestions"] if q["candidateDateId"] == self.candidate_date_id
        )
        self.assertEqual(question["yourResponse"], "GOING")
        self.assertIn("tally", question)

    def test_tally_is_absent_before_answering(self):
        response = self.participant_client.get(
            reverse("gathering:participant-view", kwargs={"token": self.token})
        )

        question = response.json()["scheduleQuestions"][0]
        self.assertNotIn("tally", question)
        self.assertIsNone(question["yourResponse"])

    def test_schedule_response_can_be_changed(self):
        self.participant_client.put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )

        response = self.participant_client.put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "NOT_GOING"}),
            content_type="application/json",
        )

        question = next(
            q
            for q in response.json()["scheduleQuestions"]
            if q["candidateDateId"] == self.candidate_date_id
        )
        self.assertEqual(question["yourResponse"], "NOT_GOING")

    def test_schedule_response_rejected_once_finalized(self):
        gathering = Gathering.objects.get(id=self.gathering_id)
        gathering.phase = GatheringPhase.FINALIZED
        gathering.save(update_fields=["phase"])

        response = self.participant_client.put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "GATHERING_FINALIZED")

    def test_malformed_status_is_rejected(self):
        response = self.participant_client.put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "NOT_A_REAL_STATUS"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_set_display_name_attaches_a_name(self):
        response = self.participant_client.put(
            reverse("gathering:participant-display-name", kwargs={"token": self.token}),
            data=json.dumps({"displayName": "たなか"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["displayName"], "たなか")

    def test_display_name_survives_an_earlier_schedule_response(self):
        self.participant_client.put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )

        response = self.participant_client.put(
            reverse("gathering:participant-display-name", kwargs={"token": self.token}),
            data=json.dumps({"displayName": "たなか"}),
            content_type="application/json",
        )

        question = next(
            q
            for q in response.json()["scheduleQuestions"]
            if q["candidateDateId"] == self.candidate_date_id
        )
        self.assertEqual(question["yourResponse"], "GOING")

    def test_organizer_dashboard_reflects_the_participant_answer(self):
        self.participant_client.put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )

        response = self.client.get(
            reverse("gathering:gathering-detail", kwargs={"gathering_id": self.gathering_id})
        )

        body = response.json()
        self.assertEqual(body["respondedParticipantCount"], 1)
        self.assertEqual(body["anonymousRespondedParticipantCount"], 1)
        candidate_date = next(
            cd for cd in body["candidateDates"] if cd["id"] == self.candidate_date_id
        )
        self.assertEqual(candidate_date["goingCount"], 1)


# --- test-support: gathering-scheduling acceptance seams --------------------


class TestSupportGatheringApiTests(GatheringOrganizerTestCase):
    """These four seams have no ``app_name``/reverse name (mirrors every
    other ``test_support`` route this project already tests by literal path,
    see ``tests/test_test_support.py``)."""

    RESET_PATH = "/test-support/gathering-scheduling-state"
    EXPIRE_PATH = "/test-support/gathering-scheduling/participant-links/expire"
    RATE_LIMIT_PATH = "/test-support/gathering-scheduling/participant-links/rate-limit"
    SERVER_ERROR_PATH = "/test-support/gathering-scheduling/participant-links/server-error"

    @override_settings(ROOT_URLCONF="dining_radar.urls", ACCEPTANCE_TEST_SUPPORT=False)
    def test_routes_are_not_registered_in_the_standard_production_urlconf(self):
        paths = (self.RESET_PATH, self.EXPIRE_PATH, self.RATE_LIMIT_PATH, self.SERVER_ERROR_PATH)
        for path in paths:
            with self.subTest(path=path):
                response = Client().delete(path)
                self.assertEqual(response.status_code, 404)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=False)
    def test_server_error_seam_is_acceptance_only_even_under_the_acceptance_urlconf(self):
        """adr/0047's own instruction: guard this seam the same way the
        existing two guard themselves (``_acceptance_only``) -- a 404, not a
        204, when ``ACCEPTANCE_TEST_SUPPORT`` is off, regardless of which
        urlconf is mounted."""
        response = Client().post(
            self.SERVER_ERROR_PATH,
            data=json.dumps({"token": "unknown-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_reset_endpoint_deletes_every_gathering(self):
        self.create_gathering_via_api()

        response = Client().delete(self.RESET_PATH)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Gathering.objects.count(), 0)

    def test_seed_expired_participant_link_rejects_an_unknown_token(self):
        response = Client().post(
            self.EXPIRE_PATH,
            data=json.dumps({"token": "unknown-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_seed_expired_participant_link_expires_the_named_token(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        token = issue_response.json()["issuedLinks"][0]["token"]

        response = Client().post(
            self.EXPIRE_PATH,
            data=json.dumps({"token": token}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 204)
        link = ParticipantLink.objects.get(token=token)
        self.assertLess(link.expires_at, timezone.now())

    def test_seed_rate_limited_participant_link_rejects_an_unknown_token(self):
        response = Client().post(
            self.RATE_LIMIT_PATH,
            data=json.dumps({"token": "unknown-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_seed_rate_limited_participant_link_flags_the_named_token(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        token = issue_response.json()["issuedLinks"][0]["token"]

        response = Client().post(
            self.RATE_LIMIT_PATH,
            data=json.dumps({"token": token}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ParticipantLink.objects.get(token=token).rate_limited_once)

    def test_seed_participant_link_server_error_rejects_an_unknown_token(self):
        response = Client().post(
            self.SERVER_ERROR_PATH,
            data=json.dumps({"token": "unknown-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_seed_participant_link_server_error_flags_the_named_token(self):
        payload = self.create_gathering_via_api()
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": payload["id"]}),
            {"count": 1},
        )
        token = issue_response.json()["issuedLinks"][0]["token"]

        response = Client().post(
            self.SERVER_ERROR_PATH,
            data=json.dumps({"token": token}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ParticipantLink.objects.get(token=token).server_error_once)


# --- API error-branch coverage: unauthenticated / CSRF / malformed / 404 ----


class OrganizerEndpointGuardTests(GatheringOrganizerTestCase):
    """Every organizer write endpoint shares the same unauthenticated/CSRF/
    malformed-body/unknown-gathering guard shape (views.py's own documented
    "developer discretion" precedent for filling this contract's
    unspecified 400 gaps uniformly)."""

    def setUp(self):
        super().setUp()
        self.payload = self.create_gathering_via_api()
        self.gathering_id = self.payload["id"]
        self.candidate_date_id = self.payload["candidateDates"][0]["id"]

    def test_create_gathering_missing_title_is_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"),
            {"candidateDates": [{"startAt": "2026-09-01T00:00:00Z"}]},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_gathering_wrong_type_title_is_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"),
            {"title": 123, "candidateDates": [{"startAt": "2026-09-01T00:00:00Z"}]},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_gathering_candidate_date_missing_start_at_is_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"), {"title": "会", "candidateDates": [{}]}
        )
        self.assertEqual(response.status_code, 400)

    def test_create_gathering_naive_datetime_is_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"),
            {"title": "会", "candidateDates": [{"startAt": "2026-09-01T00:00:00"}]},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_gathering_non_string_start_at_is_rejected(self):
        response = self.post_json(
            reverse("gathering:gatherings"), {"title": "会", "candidateDates": [{"startAt": 12345}]}
        )
        self.assertEqual(response.status_code, 400)

    def test_create_gathering_malformed_json_body_is_a_safe_400(self):
        response = self.client.post(
            reverse("gathering:gatherings"),
            data="not-json",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_create_gathering_json_array_body_is_a_safe_400(self):
        response = self.client.post(
            reverse("gathering:gatherings"),
            data="[]",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )
        self.assertEqual(response.status_code, 400)

    def test_add_candidate_date_unauthenticated_is_a_safe_401(self):
        response = Client().post(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"startAt": "2026-09-01T00:00:00Z"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_add_candidate_date_missing_csrf_is_a_safe_400(self):
        response = self.client.post(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"startAt": "2026-09-01T00:00:00Z"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_add_candidate_date_unknown_gathering_is_a_safe_404(self):
        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": uuid.uuid4()}),
            {"startAt": "2026-09-01T00:00:00Z"},
        )
        self.assertEqual(response.status_code, 404)

    def test_add_candidate_date_extra_key_is_rejected(self):
        response = self.post_json(
            reverse("gathering:candidate-dates", kwargs={"gathering_id": self.gathering_id}),
            {"startAt": "2026-09-01T00:00:00Z", "extra": True},
        )
        self.assertEqual(response.status_code, 400)

    def test_open_shop_preview_unauthenticated_is_a_safe_401(self):
        response = Client().get(
            reverse(
                "gathering:open-shop-preview",
                kwargs={
                    "gathering_id": self.gathering_id,
                    "candidate_date_id": self.candidate_date_id,
                },
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_open_shop_preview_unknown_candidate_date_is_a_safe_404(self):
        response = self.client.get(
            reverse(
                "gathering:open-shop-preview",
                kwargs={"gathering_id": self.gathering_id, "candidate_date_id": uuid.uuid4()},
            )
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "CANDIDATE_DATE_NOT_FOUND")

    def test_list_participant_links_unauthenticated_is_a_safe_401(self):
        response = Client().get(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id})
        )
        self.assertEqual(response.status_code, 401)

    def test_list_participant_links_unknown_gathering_is_a_safe_404(self):
        response = self.client.get(
            reverse("gathering:participant-links", kwargs={"gathering_id": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)

    def test_issue_participant_links_unauthenticated_is_a_safe_401(self):
        response = Client().post(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"count": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_issue_participant_links_missing_csrf_is_a_safe_400(self):
        response = self.client.post(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"count": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_issue_participant_links_zero_count_is_rejected(self):
        response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            {"count": 0},
        )
        self.assertEqual(response.status_code, 400)

    def test_issue_participant_links_boolean_count_is_rejected(self):
        response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            {"count": True},
        )
        self.assertEqual(response.status_code, 400)

    def test_issue_participant_links_over_max_count_is_rejected(self):
        response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            {"count": 201},
        )
        self.assertEqual(response.status_code, 400)

    def test_issue_participant_links_unknown_gathering_is_a_safe_404(self):
        response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": uuid.uuid4()}),
            {"count": 1},
        )
        self.assertEqual(response.status_code, 404)

    def test_recopy_unauthenticated_is_a_safe_401(self):
        response = Client().post(
            reverse(
                "gathering:participant-link-recopy",
                kwargs={"gathering_id": self.gathering_id, "link_id": uuid.uuid4()},
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_recopy_missing_csrf_is_a_safe_400(self):
        response = self.client.post(
            reverse(
                "gathering:participant-link-recopy",
                kwargs={"gathering_id": self.gathering_id, "link_id": uuid.uuid4()},
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_recopy_unknown_gathering_is_a_safe_404(self):
        response = self.post_json(
            reverse(
                "gathering:participant-link-recopy",
                kwargs={"gathering_id": uuid.uuid4(), "link_id": uuid.uuid4()},
            ),
            {},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "GATHERING_NOT_FOUND")

    def test_recopy_unknown_link_is_a_safe_404(self):
        response = self.post_json(
            reverse(
                "gathering:participant-link-recopy",
                kwargs={"gathering_id": self.gathering_id, "link_id": uuid.uuid4()},
            ),
            {},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "PARTICIPANT_LINK_NOT_FOUND")

    def test_revoke_unauthenticated_is_a_safe_401(self):
        response = Client().post(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": self.gathering_id, "link_id": uuid.uuid4()},
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_revoke_missing_csrf_is_a_safe_400(self):
        response = self.client.post(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": self.gathering_id, "link_id": uuid.uuid4()},
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_revoke_unknown_gathering_is_a_safe_404(self):
        response = self.post_json(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": uuid.uuid4(), "link_id": uuid.uuid4()},
            ),
            {},
        )
        self.assertEqual(response.status_code, 404)

    def test_revoke_unknown_link_is_a_safe_404(self):
        response = self.post_json(
            reverse(
                "gathering:participant-link-revoke",
                kwargs={"gathering_id": self.gathering_id, "link_id": uuid.uuid4()},
            ),
            {},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "PARTICIPANT_LINK_NOT_FOUND")

    def test_confirm_date_unauthenticated_is_a_safe_401(self):
        response = Client().post(
            reverse("gathering:confirm-date", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"candidateDateId": self.candidate_date_id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_confirm_date_missing_csrf_is_a_safe_400(self):
        response = self.client.post(
            reverse("gathering:confirm-date", kwargs={"gathering_id": self.gathering_id}),
            data=json.dumps({"candidateDateId": self.candidate_date_id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_confirm_date_missing_candidate_date_id_is_rejected(self):
        response = self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": self.gathering_id}), {}
        )
        self.assertEqual(response.status_code, 400)

    def test_confirm_date_empty_candidate_date_id_is_rejected(self):
        response = self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": self.gathering_id}),
            {"candidateDateId": ""},
        )
        self.assertEqual(response.status_code, 400)

    def test_confirm_date_unknown_gathering_is_a_safe_404(self):
        response = self.post_json(
            reverse("gathering:confirm-date", kwargs={"gathering_id": uuid.uuid4()}),
            {"candidateDateId": self.candidate_date_id},
        )
        self.assertEqual(response.status_code, 404)


class ParticipantEndpointGuardTests(GatheringOrganizerTestCase):
    def setUp(self):
        super().setUp()
        self.payload = self.create_gathering_via_api()
        self.gathering_id = self.payload["id"]
        self.candidate_date_id = self.payload["candidateDates"][0]["id"]
        issue_response = self.post_json(
            reverse("gathering:participant-links", kwargs={"gathering_id": self.gathering_id}),
            {"count": 1},
        )
        self.token = issue_response.json()["issuedLinks"][0]["token"]

    def test_schedule_response_missing_status_is_rejected(self):
        response = Client().put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_schedule_response_extra_key_is_rejected(self):
        response = Client().put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING", "extra": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_schedule_response_unknown_token_is_a_safe_404(self):
        response = Client().put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": "does-not-exist", "candidate_date_id": self.candidate_date_id},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "LINK_NOT_FOUND")

    def test_schedule_response_unknown_candidate_date_is_a_safe_404(self):
        response = Client().put(
            reverse(
                "gathering:schedule-response",
                kwargs={"token": self.token, "candidate_date_id": uuid.uuid4()},
            ),
            data=json.dumps({"status": "GOING"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "CANDIDATE_DATE_NOT_FOUND")

    def test_display_name_missing_key_is_rejected(self):
        response = Client().put(
            reverse("gathering:participant-display-name", kwargs={"token": self.token}),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_display_name_too_long_is_rejected(self):
        response = Client().put(
            reverse("gathering:participant-display-name", kwargs={"token": self.token}),
            data=json.dumps({"displayName": "a" * 101}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_display_name_unknown_token_is_a_safe_404(self):
        response = Client().put(
            reverse("gathering:participant-display-name", kwargs={"token": "does-not-exist"}),
            data=json.dumps({"displayName": "たなか"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "LINK_NOT_FOUND")

    def test_display_name_expired_link_is_a_safe_410(self):
        Client().post(
            "/test-support/gathering-scheduling/participant-links/expire",
            data=json.dumps({"token": self.token}),
            content_type="application/json",
        )

        response = Client().put(
            reverse("gathering:participant-display-name", kwargs={"token": self.token}),
            data=json.dumps({"displayName": "たなか"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "LINK_EXPIRED")

    def test_organizer_dashboard_page_renders_the_authenticated_shell(self):
        response = self.client.get(
            reverse("gathering:organizer-dashboard", kwargs={"gathering_id": self.gathering_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-testid="authenticated-application-shell"', response.content)

    def test_organizer_dashboard_page_requires_sign_in(self):
        response = Client().get(
            reverse("gathering:organizer-dashboard", kwargs={"gathering_id": self.gathering_id})
        )

        self.assertEqual(response.status_code, 302)

    def test_organizer_gathering_list_page_renders_the_authenticated_shell(self):
        response = self.client.get(reverse("gathering:organizer-gathering-list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-testid="authenticated-application-shell"', response.content)

    def test_organizer_gathering_list_page_requires_sign_in(self):
        response = Client().get(reverse("gathering:organizer-gathering-list"))

        self.assertEqual(response.status_code, 302)

    def test_organizer_gathering_create_page_renders_the_authenticated_shell(self):
        response = self.client.get(reverse("gathering:organizer-gathering-create"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-testid="authenticated-application-shell"', response.content)

    def test_organizer_gathering_create_page_requires_sign_in(self):
        response = Client().get(reverse("gathering:organizer-gathering-create"))

        self.assertEqual(response.status_code, 302)

    def test_participant_answer_page_never_requires_sign_in(self):
        response = Client().get(
            reverse("gathering:participant-answer", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.token.encode(), response.content)


# --- serializers: the live-projection fallback (developer discretion, FR-028) --


class LiveProjectedShopFallbackSerializerTests(SimpleTestCase):
    """A shop id no longer present in a fresh open-shop population refetch.

    No TDR-GTH scenario exercises this (ADR-0034 decision 6's live
    projection is never persisted, so this can only arise from a real
    provider-side change between calls); see
    ``serializers._live_projected_display_fields``'s own docstring for the
    developer-discretion fallback this guards.
    """

    def test_falls_back_to_the_shop_id_when_missing_from_the_lookup(self):
        entry = serializers.serialize_live_projected_shop("missing-shop-id", {}, None)

        self.assertEqual(
            entry,
            {
                "shopId": "missing-shop-id",
                "name": "missing-shop-id",
                "genre": "",
                "capacityTier": None,
                "nonSmokingStatus": None,
                "dinnerBudgetTier": None,
                "location": {"latitude": 0.0, "longitude": 0.0},
                "walkingTimeMinutes": 0,
                "providerPageUrl": "missing-shop-id",
            },
        )


# --- participant load-failure notice (adr/0047, TDR-GTH-42) ----------------


class ParticipantLoadFailureSourceTests(SimpleTestCase):
    """Guards the fix for the bug adr/0047 documents: this screen's
    ``getParticipantView`` call had no error handling at all, so an
    unrecognized response (a network failure, an unparsable body, or a
    response carrying none of ``linkError``'s four recognized codes) left
    the page blank -- no question, no error surface, no explanation
    (this file's own module docstring history for the full account).

    ``tests/ui_invariants``/``tests/acceptance`` exercise the *rendered*
    behavior through a real browser; these source-level checks are the
    complement ``DateTimeLocalConversionSourceTests`` above already
    establishes as this project's convention for a bug a Django-test-client
    reproduction cannot see (a JS-only code path).
    """

    def test_request_json_never_lets_a_promise_reject(self):
        source = PARTICIPANT_JS.read_text(encoding="utf-8")
        self.assertIn(
            "function requestJson(method, url, body) {",
            source,
            "requestJson's own signature moved or was renamed",
        )
        # Both failure sources -- response.json() rejecting (an unparsable
        # body) and fetch() itself rejecting (a network-level failure) --
        # must be caught, not left to propagate as a rejected promise.
        self.assertIn("response.json().then(", source)
        self.assertIn(".catch(function () {", source)
        self.assertIn("return { status: null, body: null };", source)

    def test_load_view_classifies_every_outcome_before_the_recognized_link_error_codes(self):
        source = PARTICIPANT_JS.read_text(encoding="utf-8")
        self.assertIn("function loadView() {", source)
        self.assertIn("var RECOGNIZED_LINK_ERROR_CODES = [", source)
        for code in ("LINK_NOT_FOUND", "LINK_EXPIRED", "LINK_REVOKED", "LINK_RATE_LIMITED"):
            self.assertIn(f'"{code}",', source)
        self.assertIn("state.loadFailure = true;", source)
        self.assertIn("state.loadFailure = false;", source)

    def test_render_shows_only_the_load_error_element_and_nothing_else(self):
        """unexpectedLoadFailureOutcome's own absent list (adr/0047): every
        other participant-facing element must stay absent, so render()'s
        loadFailure branch must return before building any of them."""
        source = PARTICIPANT_JS.read_text(encoding="utf-8")
        render_index = source.index("function render() {")
        branch_index = source.index("if (state.loadFailure) {", render_index)
        return_index = source.index("return;", branch_index)
        children_index = source.index("var children = [];", render_index)
        self.assertLess(
            branch_index,
            children_index,
            "the loadFailure branch must be checked before any other surface is built",
        )
        self.assertLess(
            return_index,
            children_index,
            "the loadFailure branch must return before falling through to the rest of render()",
        )

    def test_load_error_surface_declares_no_operational_control(self):
        """Human ruling 2026-09-06 (loadFailure.noRetryControl): no
        purpose-declared control inside gathering-participant-load-error."""
        source = PARTICIPANT_JS.read_text(encoding="utf-8")
        function_index = source.index("function renderLoadFailure() {")
        function_end = source.index("\n  }", function_index)
        function_source = source[function_index:function_end]

        self.assertIn("gathering-participant-load-error", function_source)
        self.assertNotIn("data-gathering-control-purpose", function_source)
        self.assertNotIn("addEventListener", function_source)

    def test_load_error_visible_text_discloses_no_technical_detail(self):
        """adr/0047 decision 3: no HTTP status code, exception message,
        trace/request identifier, hostname, or synthetic disclosure canary
        anywhere in this element's own rendering code."""
        source = PARTICIPANT_JS.read_text(encoding="utf-8")
        function_index = source.index("function renderLoadFailure() {")
        function_end = source.index("\n  }", function_index)
        function_source = source[function_index:function_end]

        for forbidden in (
            "result.status",
            "result.body",
            "response.status",
            "trace",
            "Trace",
            "stack",
            "Stack",
            "hostname",
            # profiles.localAcceptance.syntheticDisclosureCanaries
            # (gathering-scheduling-browser-interface.yaml).
            "synthetic-private-origin-never-disclose.invalid",
            "synthetic-provider-internals-never-disclose",
        ):
            self.assertNotIn(
                forbidden,
                function_source,
                f"renderLoadFailure must not reference {forbidden!r}",
            )


# --- static source regressions (orchestrator合流 findings, 2026-09-02) ------


class DateTimeLocalConversionSourceTests(SimpleTestCase):
    """Guards the fix for a real host-timezone-dependent bug an acceptance
    合流 run surfaced (TDR-GTH-24): ``new Date(value).toISOString()`` parses
    a timezone-less ``<input type="datetime-local">`` value using the *host
    machine's own local timezone* (JS spec's Date Time String Format), which
    on a JST host silently shifted a submitted ``startAt`` by 9 hours. A
    Django-test-client reproduction (bypassing the browser entirely) never
    exercised this JS conversion and could not see the bug -- these checks
    stay at the source level instead, mirroring
    ``tests/test_static_assets.py``'s own established convention for
    candidate.js.
    """

    def test_gathering_js_no_longer_uses_host_timezone_dependent_conversion(self):
        source = GATHERING_JS.read_text(encoding="utf-8")

        self.assertNotIn("new Date(localDateTimeValue).toISOString()", source)
        self.assertIn("function dateTimeLocalValueToIso(value)", source)
        self.assertIn('return value + ":00Z";', source)
        self.assertIn("dateTimeLocalValueToIso(localDateTimeValue)", source)

    def test_gathering_create_js_no_longer_uses_host_timezone_dependent_conversion(self):
        source = GATHERING_CREATE_JS.read_text(encoding="utf-8")

        self.assertNotIn("new Date(rawDateTimeLocalValue).toISOString()", source)
        self.assertIn("function toStartAtIso(rawDateTimeLocalValue)", source)
        self.assertIn('return rawDateTimeLocalValue + ":00Z";', source)


class GatheringListAlwaysPresentSourceTests(SimpleTestCase):
    """Guards the fix for TDR-GTH-22/23's own 合流 failure: `gathering-list`
    (browserControlSurface.organizerGatheringList.requiredTestIds.list) must
    be present on this screen even when the organizer has zero gatherings --
    only `gathering-list-item` (its own children) has a zero-or-more
    cardinality, and `gathering-list-empty` is an additional sibling, not a
    replacement.
    """

    def test_gathering_list_element_is_built_before_the_empty_state_branch(self):
        source = GATHERING_LIST_JS.read_text(encoding="utf-8")

        list_build_index = source.index('"data-testid": "gathering-list",')
        empty_branch_index = source.index("if (gatherings.length === 0) {")
        self.assertLess(
            list_build_index,
            empty_branch_index,
            "gathering-list must be built unconditionally, before the "
            "gatherings.length === 0 branch that adds gathering-list-empty "
            "as an additional sibling",
        )


# --- date-display formatting (human 2026-09-04: raw ISO strings were unreadable) --

_DATE_FORMAT_SNIPPET_BEGIN = "// --- shared-date-formatting BEGIN"
_DATE_FORMAT_SNIPPET_END = "// --- shared-date-formatting END ---"
# The *code* starts at this stable marker, deliberately after the leading
# prose comment -- that comment's own wording differs by one clause between
# the two files (each names the *other* file as "the identical copy"), so
# comparing from here on excludes that intentional, cosmetic difference
# while still comparing every executable line verbatim. It also excludes
# the comment's own prose mention of the very method names
# (toLocaleString()/getHours()/etc.) the forbidden-accessor check below
# scans for -- that mention is deliberate documentation of what *not* to
# use, not a call site, so it must not itself trip that check.
_DATE_FORMAT_CODE_BEGIN = "var WEEKDAY_LABELS_JA ="


def _extract_date_format_snippet(source: str) -> str:
    start = source.index(_DATE_FORMAT_SNIPPET_BEGIN)
    end = source.index(_DATE_FORMAT_SNIPPET_END, start) + len(_DATE_FORMAT_SNIPPET_END)
    return source[start:end]


def _extract_date_format_code(source: str) -> str:
    snippet = _extract_date_format_snippet(source)
    return snippet[snippet.index(_DATE_FORMAT_CODE_BEGIN) :]


class GatheringDateTimeFormattingSourceTests(SimpleTestCase):
    """Guards the fix for a real readability gap human real-measurement found
    (2026-09-04): ``gathering-candidate-date``/``gathering-decision-banner``/
    ``gathering-schedule-question``/``gathering-participant-decision`` all
    rendered a raw ISO-8601 string (e.g. "2026-09-07T12:00:00+00:00")
    instead of a readable "M/D (曜) HH:MM" -- Organizer.dc.html/
    Answer.dc.html/Final.dc.html's own display convention.

    Every value this formatter reads was itself produced by tagging a raw
    ``<input type="datetime-local">`` value as a literal UTC instant
    (``dateTimeLocalValueToIso``/``toStartAtIso``, TDR-GTH-24's own fix) --
    formatting must read back the *same* UTC calendar/clock components, not
    the viewing browser's own host timezone (mirrors
    ``DateTimeLocalConversionSourceTests``'s own reasoning for the opposite,
    input, direction). Proof by construction: JS's ``getUTC*`` accessors are
    defined by spec to be host-timezone-independent, so verifying only
    those accessors are used is a complete proof of TZ-independence, not
    merely circumstantial evidence -- ``GatheringDateTimeFormattingExecution
    Tests`` below additionally proves this empirically by executing the
    real function under different ``TZ`` environment values.
    """

    def test_gathering_js_and_participant_js_carry_the_identical_code(self):
        gathering_code = _extract_date_format_code(GATHERING_JS.read_text(encoding="utf-8"))
        participant_code = _extract_date_format_code(PARTICIPANT_JS.read_text(encoding="utf-8"))

        self.assertEqual(
            gathering_code,
            participant_code,
            "gathering.js and participant.js must carry byte-identical "
            "copies of the shared formatter's own code (no shared-module "
            "system exists in this codebase; every other small utility -- "
            "el()/csrfToken()/requestJson() -- is already duplicated the "
            "same way). Only the leading prose comment's own "
            "self-reference ('identical copy in <the other file>') may "
            "differ between the two.",
        )

    def test_uses_only_utc_accessors_never_a_host_local_equivalent(self):
        for path in (GATHERING_JS, PARTICIPANT_JS):
            snippet = _extract_date_format_code(path.read_text(encoding="utf-8"))
            for required in (
                "getUTCMonth",
                "getUTCDate()",
                "getUTCDay()",
                "getUTCHours()",
                "getUTCMinutes()",
            ):
                self.assertIn(required, snippet, f"{path.name} is missing {required}")
            for forbidden in (
                "toLocaleString(",
                "toLocaleDateString(",
                "toLocaleTimeString(",
                ".getHours(",
                ".getMinutes(",
                ".getDate(",
                ".getMonth(",
                ".getDay(",
                ".getFullYear(",
            ):
                self.assertNotIn(
                    forbidden,
                    snippet,
                    f"{path.name} must never read a host-timezone-dependent "
                    f"component ({forbidden}) when formatting for display",
                )

    def test_every_display_call_site_goes_through_the_formatter(self):
        gathering_source = GATHERING_JS.read_text(encoding="utf-8")
        self.assertNotIn("[candidateDate.startAt]", gathering_source)
        self.assertNotIn("[confirmed ? confirmed.startAt", gathering_source)
        self.assertIn("formatGatheringDateTime(candidateDate.startAt)", gathering_source)
        self.assertIn("formatGatheringDateTime(confirmed.startAt)", gathering_source)

        participant_source = PARTICIPANT_JS.read_text(encoding="utf-8")
        self.assertNotIn("[question.startAt]", participant_source)
        self.assertNotIn("[decision.confirmedCandidateDate]", participant_source)
        self.assertIn("formatGatheringDateTime(question.startAt)", participant_source)
        self.assertIn(
            "formatGatheringDateTime(decision.confirmedCandidateDate)", participant_source
        )

    def test_dashboard_heading_shows_the_gathering_title(self):
        # Human 2026-09-04 real-measurement finding: the dashboard heading
        # was the generic "会の日程調整" title only, with no way to tell
        # which gathering is open from the screen itself. This contract's
        # organizerDashboard section defines no test id for the gathering's
        # own name (unlike organizerGatheringList's data-gathering-title),
        # so this is rendered as a plain, purposeless element -- no
        # data-testid, no data-gathering-control-purpose.
        source = GATHERING_JS.read_text(encoding="utf-8")
        self.assertIn('el("div", { class: "gth-title" }, [state.gathering.title])', source)


@unittest.skipUnless(shutil.which("node"), "Node.js is not on PATH in this environment")
class GatheringDateTimeFormattingExecutionTests(SimpleTestCase):
    """Executes the real, extracted formatter with Node.js under different
    ``TZ`` environment values, empirically proving the computed output never
    depends on the executing host's own timezone (in addition to the
    source-level proof above). Skipped, not failed, where Node.js is
    unavailable -- this project's CI does not provision Node.js explicitly
    (GitHub's ubuntu-latest runner images ship one already), and this test
    must not become a hard environment dependency for a presentational-only
    fix.
    """

    def _run_formatter(self, iso_value: str, tz: str) -> str:
        snippet = _extract_date_format_snippet(GATHERING_JS.read_text(encoding="utf-8"))
        script = snippet + "\nconsole.log(formatGatheringDateTime(" + json.dumps(iso_value) + "));"
        # encoding="utf-8" is required on Windows: subprocess.run(text=True)
        # otherwise decodes the child's stdout using the console's own
        # codepage (cp932 in this environment), which cannot represent the
        # Japanese weekday character node writes as UTF-8 bytes.
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "TZ": tz},
            timeout=30,
            check=True,
        )
        return result.stdout.strip()

    def test_a_monday_noon_utc_instant_formats_correctly(self):
        # 2026-09-07 is a real Monday (verified independently via Python's
        # own datetime.date(2026, 9, 7).weekday() == 0).
        formatted = self._run_formatter("2026-09-07T12:00:00+00:00", tz="UTC")

        self.assertEqual(formatted, "9/7 (月) 12:00")

    def test_output_is_identical_regardless_of_the_executing_hosts_own_timezone(self):
        iso_value = "2026-08-27T12:00:00+00:00"

        utc_result = self._run_formatter(iso_value, tz="UTC")
        jst_result = self._run_formatter(iso_value, tz="Asia/Tokyo")
        pacific_result = self._run_formatter(iso_value, tz="America/Los_Angeles")

        self.assertEqual(utc_result, jst_result)
        self.assertEqual(utc_result, pacific_result)
        # 2026-08-27 is a real Thursday.
        self.assertEqual(utc_result, "8/27 (木) 12:00")

    def test_midnight_utc_does_not_roll_to_the_previous_or_next_local_day(self):
        # The clearest possible demonstration: a UTC instant at the exact
        # boundary of a calendar day. A host-timezone-dependent formatter
        # (e.g. using getDate()/getDay() instead of getUTCDate()/getUTCDay())
        # would show a *different* calendar date here depending on whether
        # the host's own offset is positive or negative.
        iso_value = "2026-09-07T00:00:00+00:00"

        utc_result = self._run_formatter(iso_value, tz="UTC")
        ahead_of_utc = self._run_formatter(iso_value, tz="Asia/Tokyo")
        behind_utc = self._run_formatter(iso_value, tz="America/Los_Angeles")

        self.assertEqual(utc_result, "9/7 (月) 00:00")
        self.assertEqual(utc_result, ahead_of_utc)
        self.assertEqual(utc_result, behind_utc)
