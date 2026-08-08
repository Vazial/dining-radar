from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from dining_radar.recommendation.pipeline import (
    NormalizedCandidate,
    Origin,
    ReproposalKindUnavailableError,
)
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

    def test_reproposal_with_the_currently_displayed_kind_is_an_ordinary_request(self):
        # adr/0016 decision 3: a same-lens "try again" request is not a new
        # server code path -- it is an ordinary re-proposal request whose
        # reproposal_kind happens to equal the kind that was already
        # displayed. propose_candidates applies no special-casing for it.
        result = propose_candidates("PROXIMITY", fetch_candidates=lambda: ([_candidate()], ORIGIN))

        self.assertIsNotNone(result.proposal)
        self.assertEqual(result.proposal.kind.value, "PROXIMITY")


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


class ProposeWithOverrideAdr0015Tests(SimpleTestCase):
    """Direct unit coverage of the adr/0015 synthetic seams in acceptance_state.

    ``test_candidate_search.py`` covers the same behaviour through the public
    HTTP endpoint; these tests exercise ``propose_with_override`` itself so a
    change to the module's synthetic candidate sets or mode dispatch is
    caught here even if request/response wiring changes independently.
    """

    def test_izakaya_bar_only_mode_falls_through_to_izakaya_bar_included(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY, None
        )

        self.assertIsNotNone(result.proposal)
        self.assertEqual(result.proposal.kind.value, "IZAKAYA_BAR_INCLUDED")
        self.assertEqual(result.reproposal_options, [])
        self.assertTrue(result.proposal.candidates)
        self.assertTrue(all(c.genre == "居酒屋" for c in result.proposal.candidates))

    def test_izakaya_bar_only_mode_returns_the_same_closed_set_regardless_of_requested_kind(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY,
            "IZAKAYA_BAR_INCLUDED",
        )

        self.assertIsNotNone(result.proposal)
        self.assertEqual(result.proposal.kind.value, "IZAKAYA_BAR_INCLUDED")

    def test_izakaya_bar_only_mode_rejects_an_unbuildable_requested_kind(self):
        with self.assertRaises(ReproposalKindUnavailableError):
            acceptance_state.propose_with_override(
                acceptance_state.AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY, "PROXIMITY"
            )

    def test_normal_with_repeat_initial_search_excludes_the_default_excluded_genre_by_default(self):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT, None
        )

        self.assertEqual(result.proposal.kind.value, "PROXIMITY")
        self.assertNotIn("居酒屋", [c.genre for c in result.proposal.candidates])
        self.assertIn(
            "IZAKAYA_BAR_INCLUDED", [option.kind.value for option in result.reproposal_options]
        )

    def test_normal_with_repeat_izakaya_bar_included_selection_includes_the_excluded_candidate(
        self,
    ):
        result = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT,
            "IZAKAYA_BAR_INCLUDED",
        )

        self.assertEqual(result.proposal.kind.value, "IZAKAYA_BAR_INCLUDED")
        self.assertIn("居酒屋", [c.genre for c in result.proposal.candidates])

    def test_normal_with_repeat_same_lens_try_again_still_yields_new_and_repeated_candidates(
        self,
    ):
        # test-support-api.yaml v0.4.0 (adr/0016): NORMAL_WITH_REPEAT's
        # new-plus-repeated guarantee must also hold for a same-lens "try
        # again" request (resending the displayed proposal's own kind, not
        # a different offered kind), for TDR-CS-11. The seam's source
        # switches candidate sets on any non-None reproposal_kind, so this
        # documents that resending the same kind as the initial display
        # still lands on the second (repeat-plus-new) synthetic set rather
        # than being treated as equivalent to the initial (no-kind) request.
        initial = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT, None
        )
        displayed_kind = initial.proposal.kind.value

        again = acceptance_state.propose_with_override(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT, displayed_kind
        )

        self.assertEqual(again.proposal.kind.value, displayed_kind)
        initial_urls = {c.provider_page_url for c in initial.proposal.candidates}
        again_urls = {c.provider_page_url for c in again.proposal.candidates}
        self.assertTrue(initial_urls & again_urls, "expected at least one repeated candidate")
        self.assertTrue(again_urls - initial_urls, "expected at least one new candidate")
