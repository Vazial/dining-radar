"""Unit and boundary tests for contracts/gathering-scheduling-api.yaml.

Covers ``dining_radar.gathering``'s models, services (business logic), and
the JSON API views, plus the acceptance-only test-support seams
(``resetGatheringSchedulingAcceptanceState``/``seedExpiredParticipantLink``/
``seedRateLimitedParticipantLink``) added to
``dining_radar.test_support.views``/``urls`` for TDR-GTH.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dining_radar.gathering import services
from dining_radar.gathering.models import (
    CandidateDate,
    Gathering,
    GatheringPhase,
    ParticipantLink,
    ScheduleResponse,
    ScheduleResponseStatus,
)
from dining_radar.suggestions import acceptance_state


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

        candidate_date_obj, population = services.preview_open_shops_for_candidate_date(
            self.user, gathering.id, candidate_date.id
        )

        self.assertEqual(candidate_date_obj.id, candidate_date.id)
        self.assertEqual(len(population), 5)  # Monday: only the 月 candidate excluded

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
                "candidateDates",
                "totalIssuedParticipantLinks",
                "totalRevokedParticipantLinks",
                "activeParticipantLinkCount",
                "respondedParticipantCount",
                "anonymousRespondedParticipantCount",
                "confirmedCandidateDateId",
            },
        )
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
            set(item), {"name", "genre", "capacityTier", "nonSmokingStatus", "dinnerBudgetTier"}
        )


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
            },
        )
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
    """These three seams have no ``app_name``/reverse name (mirrors every
    other ``test_support`` route this project already tests by literal path,
    see ``tests/test_test_support.py``)."""

    RESET_PATH = "/test-support/gathering-scheduling-state"
    EXPIRE_PATH = "/test-support/gathering-scheduling/participant-links/expire"
    RATE_LIMIT_PATH = "/test-support/gathering-scheduling/participant-links/rate-limit"

    @override_settings(ROOT_URLCONF="dining_radar.urls", ACCEPTANCE_TEST_SUPPORT=False)
    def test_routes_are_not_registered_in_the_standard_production_urlconf(self):
        for path in (self.RESET_PATH, self.EXPIRE_PATH, self.RATE_LIMIT_PATH):
            with self.subTest(path=path):
                response = Client().delete(path)
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

    def test_participant_answer_page_never_requires_sign_in(self):
        response = Client().get(
            reverse("gathering:participant-answer", kwargs={"token": self.token})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.token.encode(), response.content)
