import json
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from dining_radar.suggestions import acceptance_state


def csrf_token_from(response) -> str:
    matched = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', response.content)
    assert matched is not None
    return matched.group(1).decode("ascii")


class CandidateProposalsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(acceptance_state.reset_mode)
        acceptance_state.reset_mode()
        self.password = "Synthetic-passphrase-123!"
        self.user = get_user_model().objects.create_user(
            username="candidate-organizer", password=self.password
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        page = self.client.get(reverse("web:home"))
        self.csrf_token = csrf_token_from(page)

    def post_proposal(self, body: dict | None = None):
        return self.client.post(
            reverse("web:candidate-proposals"),
            data=json.dumps(body if body is not None else {}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    # Malformed request -----------------------------------------------

    def test_malformed_json_body_is_a_safe_400(self):
        response = self.client.post(
            reverse("web:candidate-proposals"),
            data="not-json",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "PROPOSAL_REPROPOSAL_KIND_INVALID")

    def test_unexpected_body_key_is_a_safe_400(self):
        response = self.post_proposal({"reproposalKind": "PROXIMITY", "extra": "not-allowed"})

        self.assertEqual(response.status_code, 400)

    def test_non_string_reproposal_kind_is_a_safe_400(self):
        response = self.post_proposal({"reproposalKind": 123})

        self.assertEqual(response.status_code, 400)

    def test_unknown_reproposal_kind_literal_is_a_safe_400(self):
        response = self.post_proposal({"reproposalKind": "NOT_A_REAL_KIND"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "PROPOSAL_REPROPOSAL_KIND_INVALID")

    # previouslyShownProviderPageUrls (adr/0017 decision 1) -------------

    def test_non_list_previously_shown_provider_page_urls_is_a_safe_400(self):
        response = self.post_proposal(
            {"reproposalKind": "PROXIMITY", "previouslyShownProviderPageUrls": "not-a-list"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "PROPOSAL_REPROPOSAL_KIND_INVALID")

    def test_non_string_item_in_previously_shown_provider_page_urls_is_a_safe_400(self):
        response = self.post_proposal(
            {"reproposalKind": "PROXIMITY", "previouslyShownProviderPageUrls": [123]}
        )

        self.assertEqual(response.status_code, 400)

    def test_empty_previously_shown_provider_page_urls_is_accepted(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )

        response = self.post_proposal(
            {"reproposalKind": "PROXIMITY", "previouslyShownProviderPageUrls": []}
        )

        self.assertEqual(response.status_code, 200)

    # Real provider path (no runtime credentials in tests) -------------

    def test_missing_provider_configuration_is_a_safe_503(self):
        response = self.post_proposal()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "code": "PROVIDER_UNAVAILABLE",
                "message": (
                    "Candidate proposals cannot be retrieved right now. Please try again later."
                ),
            },
        )

    # Rate limiting ------------------------------------------------------

    @override_settings(PROPOSAL_RATE_LIMIT_MAX_REQUESTS=1, PROPOSAL_RATE_LIMIT_WINDOW_SECONDS=45)
    def test_exceeding_the_request_rate_returns_429_with_retry_after(self):
        first = self.post_proposal()
        self.assertEqual(first.status_code, 503)  # counted, though the provider is unconfigured

        second = self.post_proposal()

        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["code"], "PROPOSAL_RATE_LIMITED")
        self.assertEqual(second["Retry-After"], "45")

    # Acceptance-seam-driven synthetic outcomes --------------------------

    def test_normal_with_repeat_initial_proposal_excludes_amenity_reference(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )

        response = self.post_proposal()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNotNone(payload["proposal"])
        self.assertLessEqual(len(payload["reProposalOptions"]), 3)
        offered_kinds = [option["kind"] for option in payload["reProposalOptions"]]
        self.assertNotIn("AMENITY_REFERENCE", offered_kinds)
        self.assertNotIn(payload["proposal"]["kind"], offered_kinds)
        self.assertEqual(
            payload["providerCredit"],
            {
                "text": "Powered by ホットペッパーグルメ Webサービス",
                "url": "http://webservice.recruit.co.jp/",
            },
        )

    def test_requesting_the_excluded_amenity_lens_is_deterministically_unavailable(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )
        self.post_proposal()

        response = self.post_proposal({"reproposalKind": "AMENITY_REFERENCE"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "PROPOSAL_REPROPOSAL_KIND_INVALID")

    def test_normal_with_repeat_reproposal_with_previously_shown_urls_has_new_and_repeated(
        self,
    ):
        # adr/0017 decision 1-2: the demotion this asserts is driven only by
        # the request's own previouslyShownProviderPageUrls, so it is sent
        # explicitly here (unlike the pre-adr/0017 seam, the server no
        # longer varies its response just because a reproposalKind is
        # present).
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )
        initial = self.post_proposal().json()
        initial_urls = [
            candidate["providerPageUrl"] for candidate in initial["proposal"]["candidates"]
        ]
        offered_kind = initial["reProposalOptions"][0]["kind"]

        response = self.post_proposal(
            {"reproposalKind": offered_kind, "previouslyShownProviderPageUrls": initial_urls}
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        reproposed_urls = {
            candidate["providerPageUrl"] for candidate in payload["proposal"]["candidates"]
        }
        self.assertTrue(reproposed_urls & set(initial_urls), "expected at least one repeated shop")
        self.assertTrue(reproposed_urls - set(initial_urls), "expected at least one new shop")

    def test_normal_with_repeat_reproposal_without_previously_shown_urls_leaves_ordering_unaffected(
        self,
    ):
        # test-support-api.yaml v0.5.0: "omitting or emptying that field
        # leaves ordering unaffected" -- resending the displayed kind with no
        # previouslyShownProviderPageUrls returns the identical candidate set
        # in the identical order.
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )
        initial = self.post_proposal().json()
        displayed_kind = initial["proposal"]["kind"]
        initial_urls = [
            candidate["providerPageUrl"] for candidate in initial["proposal"]["candidates"]
        ]

        response = self.post_proposal({"reproposalKind": displayed_kind})

        payload = response.json()
        reproposed_urls = [
            candidate["providerPageUrl"] for candidate in payload["proposal"]["candidates"]
        ]
        self.assertEqual(reproposed_urls, initial_urls)

    # adr/0015: default genre exclusion and IZAKAYA_BAR_INCLUDED ----------

    def test_normal_with_repeat_initial_proposal_excludes_the_default_excluded_genre(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )

        response = self.post_proposal()

        payload = response.json()
        self.assertEqual(payload["proposal"]["kind"], "PROXIMITY")
        self.assertNotIn("居酒屋", [c["genre"] for c in payload["proposal"]["candidates"]])
        offered_kinds = [option["kind"] for option in payload["reProposalOptions"]]
        self.assertIn("IZAKAYA_BAR_INCLUDED", offered_kinds)

    def test_selecting_izakaya_bar_included_lens_includes_the_default_excluded_genre(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )
        self.post_proposal()

        response = self.post_proposal({"reproposalKind": "IZAKAYA_BAR_INCLUDED"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["proposal"]["kind"], "IZAKAYA_BAR_INCLUDED")
        self.assertIn("居酒屋", [c["genre"] for c in payload["proposal"]["candidates"]])
        self.assertNotIn("ランチ営業しています", payload["proposal"]["rationale"])

    def test_izakaya_bar_only_mode_falls_through_instead_of_a_null_proposal(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY)

        response = self.post_proposal()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNotNone(payload["proposal"])
        self.assertEqual(payload["proposal"]["kind"], "IZAKAYA_BAR_INCLUDED")
        self.assertEqual(payload["reProposalOptions"], [])
        self.assertTrue(payload["proposal"]["candidates"])
        self.assertTrue(
            all(c["genre"] == "居酒屋" for c in payload["proposal"]["candidates"]),
        )

    def test_no_results_mode_returns_a_successful_null_proposal(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS)

        response = self.post_proposal()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "proposal": None,
                "reProposalOptions": [],
                "providerCredit": {
                    "text": "Powered by ホットペッパーグルメ Webサービス",
                    "url": "http://webservice.recruit.co.jp/",
                },
            },
        )

    def test_provider_unavailable_mode_returns_503_regardless_of_body(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.PROVIDER_UNAVAILABLE
        )

        response = self.post_proposal({"reproposalKind": "PROXIMITY"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "PROVIDER_UNAVAILABLE")

    def test_invalid_reproposal_kind_mode_returns_400(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.INVALID_REPROPOSAL_KIND
        )

        response = self.post_proposal({"reproposalKind": "PROXIMITY"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "PROPOSAL_REPROPOSAL_KIND_INVALID")

    def test_rate_limited_mode_returns_429_with_retry_after(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.RATE_LIMITED)

        response = self.post_proposal()

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "PROPOSAL_RATE_LIMITED")
        self.assertEqual(response["Retry-After"], "30")

    def test_acceptance_mode_bypasses_the_real_request_throttle(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS)

        with override_settings(
            PROPOSAL_RATE_LIMIT_MAX_REQUESTS=1, PROPOSAL_RATE_LIMIT_WINDOW_SECONDS=60
        ):
            first = self.post_proposal()
            second = self.post_proposal()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)


class CandidateResponseSchemaTests(TestCase):
    """Structural checks on the serialized candidate shape."""

    def setUp(self):
        cache.clear()
        self.addCleanup(acceptance_state.reset_mode)
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_REPEAT
        )
        self.password = "Synthetic-passphrase-123!"
        self.user = get_user_model().objects.create_user(
            username="candidate-schema-organizer", password=self.password
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        page = self.client.get(reverse("web:home"))
        self.csrf_token = csrf_token_from(page)

    def test_candidate_fields_match_the_public_contract_shape(self):
        response = self.client.post(
            reverse("web:candidate-proposals"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

        payload = response.json()
        candidates = payload["proposal"]["candidates"]
        self.assertTrue(candidates)
        candidate_refs = [candidate["candidateRef"] for candidate in candidates]
        self.assertEqual(len(candidate_refs), len(set(candidate_refs)))

        for candidate in candidates:
            self.assertEqual(
                set(candidate),
                {
                    "candidateRef",
                    "name",
                    "genre",
                    "description",
                    "regularHoliday",
                    "totalSeats",
                    "access",
                    "location",
                    "providerPageUrl",
                },
            )
            self.assertEqual(set(candidate["location"]), {"latitude", "longitude"})
            self.assertIsInstance(candidate["location"]["latitude"], (int, float))
            self.assertIsInstance(candidate["location"]["longitude"], (int, float))

        self.assertEqual(
            set(payload["proposal"]),
            {"conceptRef", "kind", "title", "rationale", "candidates"},
        )
