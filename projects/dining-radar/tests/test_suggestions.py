from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from dining_radar.recommendation.pipeline import NormalizedCandidate, Origin
from dining_radar.suggestions import acceptance_state
from dining_radar.suggestions.errors import CandidateSourceUnavailableError
from dining_radar.suggestions.hotpepper_source import fetch_real_candidates
from dining_radar.suggestions.rate_limit import ProposalThrottle
from dining_radar.suggestions.service import propose_candidates

ORIGIN = Origin(latitude=0.0, longitude=0.0)


def _candidate(provider_page_url="https://example.invalid/shop"):
    return NormalizedCandidate(
        name="架空食堂",
        genre="和食",
        description=None,
        business_hours=None,
        regular_holiday=None,
        total_seats=None,
        access=None,
        latitude=0.001,
        longitude=0.0,
        provider_page_url=provider_page_url,
    )


class ProposeCandidatesTests(SimpleTestCase):
    def test_initial_request_selects_the_first_priority_concept(self):
        result = propose_candidates(None, fetch_candidates=lambda: ([_candidate()], ORIGIN))

        self.assertIsNotNone(result.proposal)
        self.assertEqual(result.proposal.kind.value, "PROXIMITY")

    def test_initial_request_with_no_candidates_returns_a_null_proposal(self):
        result = propose_candidates(None, fetch_candidates=lambda: ([], ORIGIN))

        self.assertIsNone(result.proposal)
        self.assertEqual(result.reproposal_options, [])

    def test_reproposal_with_no_candidates_returns_a_null_proposal(self):
        result = propose_candidates("PROXIMITY", fetch_candidates=lambda: ([], ORIGIN))

        self.assertIsNone(result.proposal)

    def test_reproposal_with_an_unknown_enum_literal_raises_value_error(self):
        with self.assertRaises(ValueError):
            propose_candidates("NOT_A_REAL_KIND", fetch_candidates=lambda: ([_candidate()], ORIGIN))


class HotpepperSourceTests(SimpleTestCase):
    def test_missing_configuration_raises_candidate_source_unavailable(self):
        with self.assertRaises(CandidateSourceUnavailableError):
            fetch_real_candidates()


class _FakeRequest:
    def __init__(self, user):
        self.user = user
        self.META = {"REMOTE_ADDR": "127.0.0.1"}


class ProposalThrottleTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(PROPOSAL_RATE_LIMIT_MAX_REQUESTS=2, PROPOSAL_RATE_LIMIT_WINDOW_SECONDS=30)
    def test_is_limited_only_after_max_requests(self):
        user = MagicMock(pk=4242)
        throttle = ProposalThrottle(_FakeRequest(user))

        self.assertFalse(throttle.is_limited())
        throttle.record_request()
        self.assertFalse(throttle.is_limited())
        throttle.record_request()
        self.assertTrue(throttle.is_limited())

    def test_defaults_are_generous_when_unconfigured(self):
        user = MagicMock(pk=4343)
        throttle = ProposalThrottle(_FakeRequest(user))

        self.assertEqual(throttle.max_requests, 20)
        self.assertEqual(throttle.window_seconds, 60)


class AcceptanceStateGuardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(acceptance_state.reset_mode)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=False)
    def test_set_mode_is_unavailable_outside_the_acceptance_profile(self):
        with self.assertRaises(RuntimeError):
            acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS)

    @override_settings(ACCEPTANCE_TEST_SUPPORT=False)
    def test_active_mode_is_none_outside_the_acceptance_profile(self):
        self.assertIsNone(acceptance_state.active_mode())

    def test_active_mode_reflects_the_selected_mode(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.RATE_LIMITED)

        self.assertEqual(
            acceptance_state.active_mode(),
            acceptance_state.AcceptanceCandidateProposalMode.RATE_LIMITED,
        )

    def test_reset_mode_clears_the_selection(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS)

        acceptance_state.reset_mode()

        self.assertIsNone(acceptance_state.active_mode())
