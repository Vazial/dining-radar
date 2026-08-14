import json
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import clear_url_caches

from dining_radar.suggestions import acceptance_state

ACCEPTANCE_SETTINGS = {
    "ROOT_URLCONF": "dining_radar.acceptance_urls",
    "ACCEPTANCE_TEST_SUPPORT": True,
    "SESSION_COOKIE_SECURE": False,
}


@override_settings(**ACCEPTANCE_SETTINGS)
class AcceptanceTestSupportTests(TestCase):
    def setUp(self):
        clear_url_caches()

    def tearDown(self):
        clear_url_caches()

    def test_security_boundary_observes_the_effective_local_profile(self):
        response = self.client.get("/test-support/authentication/security-boundary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "profile": "acceptance",
                "transport": "HTTP_LOCAL_ONLY",
                "sessionCookie": {"secure": False, "httpOnly": True, "sameSite": "Lax"},
                "csrfProtectedOperations": [
                    "SIGN_IN",
                    "SIGN_OUT",
                    "CHANGE_PASSWORD",
                    "CANDIDATE_PROPOSAL",
                ],
                "credentialedArbitraryOriginCorsAllowed": False,
                "browserLocalStorageBearerTokenUsed": False,
            },
        )

    def test_synthetic_account_can_be_replaced_without_returning_credential_data(self):
        response = self.client.put(
            "/test-support/authentication/accounts/synthetic-account-a",
            data=json.dumps(
                {
                    "loginIdentifier": "synthetic-organizer-a",
                    "password": "synthetic-password-only",
                    "isActive": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

        account = get_user_model().objects.get(username="synthetic-organizer-a")
        self.assertTrue(account.is_active)
        self.assertTrue(account.check_password("synthetic-password-only"))

        replacement = self.client.put(
            "/test-support/authentication/accounts/synthetic-account-a",
            data=json.dumps(
                {
                    "loginIdentifier": "synthetic-organizer-renamed",
                    "password": "replacement-synthetic-password",
                    "isActive": False,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(replacement.status_code, 204)
        account.refresh_from_db()
        self.assertEqual(account.username, "synthetic-organizer-renamed")
        self.assertFalse(account.is_active)
        self.assertTrue(account.check_password("replacement-synthetic-password"))

    def test_throttle_seed_applies_to_the_next_browser_login_for_that_identifier(self):
        account = get_user_model().objects.create_user(
            username="synthetic-throttled-visitor", password="synthetic-password-only"
        )
        self.assertTrue(account.is_active)
        seed = self.client.post(
            "/test-support/authentication/login-throttle",
            data=json.dumps({"loginIdentifier": "synthetic-throttled-visitor"}),
            content_type="application/json",
        )
        self.assertEqual(seed.status_code, 204)

        browser = Client()
        response = browser.post(
            "/accounts/login/",
            {"username": "synthetic-throttled-visitor", "password": "synthetic-password-only"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="auth-sign-in-throttled"')

    def test_reset_removes_only_synthetic_accounts_and_acceptance_sessions(self):
        self.client.put(
            "/test-support/authentication/accounts/synthetic-account-a",
            data=json.dumps(
                {
                    "loginIdentifier": "synthetic-organizer-a",
                    "password": "synthetic-password-only",
                    "isActive": True,
                }
            ),
            content_type="application/json",
        )
        synthetic_account = get_user_model().objects.get(username="synthetic-organizer-a")
        external_account = get_user_model().objects.create_user(
            username="ordinary-test-user", password="other-synthetic-password"
        )
        browser = Client()
        browser.force_login(synthetic_account)

        response = self.client.delete("/test-support/authentication-state")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(get_user_model().objects.filter(pk=synthetic_account.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=external_account.pk).exists())
        self.assertEqual(browser.get("/").status_code, 302)


@override_settings(**ACCEPTANCE_SETTINGS)
class CandidateProposalAcceptanceStateTests(TestCase):
    def setUp(self):
        clear_url_caches()
        cache.clear()
        self.addCleanup(acceptance_state.reset_mode)

    def tearDown(self):
        clear_url_caches()

    def test_put_selects_a_synthetic_mode_the_public_api_then_observes(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NO_RESULTS"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(
            acceptance_state.active_mode(),
            acceptance_state.AcceptanceCandidateProposalMode.NO_RESULTS,
        )

    def test_put_accepts_every_documented_mode(self):
        for mode in acceptance_state.AcceptanceCandidateProposalMode:
            with self.subTest(mode=mode.value):
                response = self.client.put(
                    "/test-support/candidate-proposals/state",
                    data=json.dumps({"mode": mode.value}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 204)
                self.assertEqual(acceptance_state.active_mode(), mode)

    def test_put_accepts_zero_pending_match_and_fallback_preserves_filters_with_a_random_seed(self):
        for mode in ("ZERO_PENDING_MATCH", "FALLBACK_PRESERVES_FILTERS"):
            with self.subTest(mode=mode):
                response = self.client.put(
                    "/test-support/candidate-proposals/state",
                    data=json.dumps({"mode": mode, "randomSeed": 11}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 204)
                self.assertEqual(
                    acceptance_state.active_mode(),
                    acceptance_state.AcceptanceCandidateProposalMode(mode),
                )
                first = acceptance_state.active_random_source().random()
                second = acceptance_state.active_random_source().random()
                self.assertEqual(first, second)

    def test_put_rejects_an_unknown_mode(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NOT_A_REAL_MODE"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(acceptance_state.active_mode())

    def test_put_rejects_an_unexpected_extra_key(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NO_RESULTS", "extra": "value"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_delete_resets_the_selected_mode(self):
        acceptance_state.set_mode(acceptance_state.AcceptanceCandidateProposalMode.RATE_LIMITED)

        response = self.client.delete("/test-support/candidate-proposals/state")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertIsNone(acceptance_state.active_mode())

    # randomSeed (adr/0023 decision 4) -----------------------------------

    def test_put_accepts_a_random_seed_and_pins_a_deterministic_source(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NORMAL_WITH_WEIGHTED_SAMPLING", "randomSeed": 42}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 204)
        first = acceptance_state.active_random_source().random()
        second = acceptance_state.active_random_source().random()
        self.assertEqual(first, second)

    def test_put_without_a_random_seed_leaves_sampling_non_deterministic(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NORMAL_WITH_WEIGHTED_SAMPLING"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertIsInstance(acceptance_state.active_random_source(), random.Random)

    def test_put_rejects_a_non_integer_random_seed(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NORMAL_WITH_WEIGHTED_SAMPLING", "randomSeed": "not-an-int"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_put_rejects_a_boolean_random_seed(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NORMAL_WITH_WEIGHTED_SAMPLING", "randomSeed": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_delete_also_clears_the_pinned_random_seed(self):
        acceptance_state.set_mode(
            acceptance_state.AcceptanceCandidateProposalMode.NORMAL_WITH_WEIGHTED_SAMPLING,
            random_seed=42,
        )

        response = self.client.delete("/test-support/candidate-proposals/state")

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(cache.get(acceptance_state._CACHE_KEY_SEED))


@override_settings(
    ROOT_URLCONF="dining_radar.urls",
    ACCEPTANCE_TEST_SUPPORT=False,
    SESSION_COOKIE_SECURE=True,
)
class PublicApplicationTestSupportIsolationTests(TestCase):
    def test_test_support_routes_are_not_registered_in_the_standard_test_profile(self):
        response = self.client.get("/test-support/authentication/security-boundary")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False))

    def test_candidate_proposal_state_route_is_not_registered_in_the_standard_test_profile(self):
        response = self.client.put(
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NO_RESULTS"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
