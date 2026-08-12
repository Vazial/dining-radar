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

    # Unauthenticated / CSRF -----------------------------------------------

    def test_unauthenticated_request_is_a_safe_401(self):
        anonymous_client = Client(enforce_csrf_checks=True)

        response = anonymous_client.post(
            reverse("web:candidate-proposals"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTHENTICATION_REQUIRED")

    def test_missing_csrf_token_is_a_safe_403(self):
        response = self.client.post(
            reverse("web:candidate-proposals"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    # Malformed request -----------------------------------------------

    def test_malformed_json_body_is_a_safe_403(self):
        response = self.client.post(
            reverse("web:candidate-proposals"),
            data="not-json",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "REQUEST_REJECTED")

    def test_unexpected_top_level_key_is_a_safe_403(self):
        response = self.post_proposal({"filters": {}, "extra": "not-allowed"})

        self.assertEqual(response.status_code, 403)

    def test_public_request_rejects_the_acceptance_only_random_seed(self):
        response = self.post_proposal({"randomSeed": 42})

        self.assertEqual(response.status_code, 403)

    def test_unexpected_filter_key_is_a_safe_403(self):
        response = self.post_proposal({"filters": {"genres": [], "notAFilter": True}})

        self.assertEqual(response.status_code, 403)

    def test_non_list_genres_is_a_safe_403(self):
        response = self.post_proposal({"filters": {"genres": "和食"}})

        self.assertEqual(response.status_code, 403)

    def test_non_string_genre_item_is_a_safe_403(self):
        response = self.post_proposal({"filters": {"genres": [123]}})

        self.assertEqual(response.status_code, 403)

    def test_non_boolean_include_izakaya_bar_is_a_safe_403(self):
        response = self.post_proposal({"filters": {"includeIzakayaBar": "true"}})

        self.assertEqual(response.status_code, 403)

    def test_unknown_budget_tier_literal_is_a_safe_403(self):
        response = self.post_proposal({"filters": {"budgetTiers": ["NOT_A_REAL_TIER"]}})

        self.assertEqual(response.status_code, 403)

    def test_empty_filters_object_is_accepted(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal({"filters": {}})

        self.assertEqual(response.status_code, 200)

    def test_omitted_filters_key_is_accepted(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal({})

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

    def test_normal_with_pool_initial_proposal_excludes_the_default_excluded_genre(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("居酒屋", [c["genre"] for c in payload["candidates"]])
        self.assertFalse(payload["izakayaBarFallbackApplied"])
        self.assertNotIn("居酒屋", payload["availableGenres"])
        self.assertEqual(
            payload["providerCredit"],
            {
                "text": "Powered by ホットペッパーグルメ Webサービス",
                "url": "http://webservice.recruit.co.jp/",
            },
        )

    def test_normal_with_pool_initial_proposal_has_at_most_five_candidates(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal()

        self.assertLessEqual(len(response.json()["candidates"]), 5)

    def test_default_exclusion_visible_mode_makes_both_filter_outcomes_observable(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.DEFAULT_EXCLUSION_VISIBLE,
            random_seed=7,
        )

        default_payload = self.post_proposal().json()
        included_payload = self.post_proposal({"filters": {"includeIzakayaBar": True}}).json()
        excluded_by_genre = {
            row["genre"]: row["defaultExcluded"] for row in default_payload["populationAttributes"]
        }

        self.assertTrue(default_payload["candidates"])
        self.assertTrue(
            all(
                not excluded_by_genre[candidate["genre"]]
                for candidate in default_payload["candidates"]
            )
        )
        self.assertTrue(
            any(
                excluded_by_genre[candidate["genre"]]
                for candidate in included_payload["candidates"]
            )
        )

    def test_card_payment_caution_visible_mode_displays_both_payment_states(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.CARD_PAYMENT_CAUTION_VISIBLE,
            random_seed=7,
        )

        payload = self.post_proposal().json()
        payment_values = {candidate["cardPaymentAvailable"] for candidate in payload["candidates"]}

        self.assertIn(False, payment_values)
        self.assertTrue(True in payment_values or None in payment_values)

    def test_include_izakaya_bar_filter_reaches_the_default_excluded_genre(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal({"filters": {"includeIzakayaBar": True}})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("居酒屋", payload["availableGenres"])

    def test_genre_filter_narrows_to_the_requested_genre(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)
        available = self.post_proposal().json()["availableGenres"]
        self.assertTrue(available)
        chosen_genre = available[0]

        response = self.post_proposal({"filters": {"genres": [chosen_genre]}})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["candidates"])
        self.assertTrue(all(c["genre"] == chosen_genre for c in payload["candidates"]))

    def test_non_smoking_only_filter_excludes_confirmed_none_candidates(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal({"filters": {"nonSmokingOnly": True}})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("NONE", [c["nonSmokingStatus"] for c in payload["candidates"]])

    def test_card_payment_only_filter_excludes_confirmed_false_candidates(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal({"filters": {"cardPaymentOnly": True}})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn(False, [c["cardPaymentAvailable"] for c in payload["candidates"]])

    def test_budget_tiers_filter_excludes_confirmed_non_matching_tiers(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)

        response = self.post_proposal({"filters": {"budgetTiers": ["LOW"]}})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        tiers = [c["dinnerBudgetTier"] for c in payload["candidates"]]
        self.assertTrue(all(tier in (None, "LOW") for tier in tiers))

    def test_izakaya_bar_only_mode_falls_through_instead_of_an_empty_result(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY)

        response = self.post_proposal()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["candidates"])
        self.assertTrue(payload["izakayaBarFallbackApplied"])
        self.assertTrue(all(c["genre"] == "居酒屋" for c in payload["candidates"]))

    def test_no_results_mode_returns_a_successful_empty_candidates_result(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS)

        response = self.post_proposal()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "candidates": [],
                "izakayaBarFallbackApplied": False,
                "availableGenres": [],
                "populationAttributes": [],
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

        response = self.post_proposal({"filters": {"genres": ["和食"]}})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "PROVIDER_UNAVAILABLE")

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

    # Randomness determinism seam (adr/0020 decision 4) -------------------

    def test_random_seed_pins_a_reproducible_candidate_set(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL, random_seed=7
        )

        first = self.post_proposal().json()["candidates"]
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL, random_seed=7
        )
        second = self.post_proposal().json()["candidates"]

        self.assertEqual(first, second)


class CandidateResponseSchemaTests(TestCase):
    """Structural checks on the serialized candidate shape."""

    def setUp(self):
        cache.clear()
        self.addCleanup(acceptance_state.reset_mode)
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_POOL)
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
        candidates = payload["candidates"]
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
                    "capacityTier",
                    "nonSmokingStatus",
                    "cardPaymentAvailable",
                    "dinnerBudgetTier",
                    "location",
                    "providerPageUrl",
                },
            )
            self.assertEqual(set(candidate["location"]), {"latitude", "longitude"})
            self.assertIsInstance(candidate["location"]["latitude"], (int, float))
            self.assertIsInstance(candidate["location"]["longitude"], (int, float))

        self.assertEqual(
            set(payload),
            {
                "candidates",
                "izakayaBarFallbackApplied",
                "availableGenres",
                "populationAttributes",
                "providerCredit",
            },
        )
