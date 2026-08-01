"""Local browser L4 runner for TDR-AUTH-01 through 05 and 07.

TDR-AUTH-06 is intentionally not run here: ADR-0007 assigns its local evidence
to L3 security/configuration checks and defers actual HTTPS transport to the
deployment slice.
"""

from __future__ import annotations

import os

from django.test import LiveServerTestCase

from tests.acceptance.dsl.authentication_browser import AuthenticationBrowserDsl
from tests.acceptance.steps.authentication_steps import AuthenticationSteps


class AuthenticationAcceptanceTests(LiveServerTestCase):
    """Each method mirrors one approved TDR-AUTH browser scenario."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._previous_base_url = os.environ.get("TDR_ACCEPTANCE_BASE_URL")
        os.environ["TDR_ACCEPTANCE_BASE_URL"] = cls.live_server_url

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._previous_base_url is None:
            os.environ.pop("TDR_ACCEPTANCE_BASE_URL", None)
        else:
            os.environ["TDR_ACCEPTANCE_BASE_URL"] = cls._previous_base_url
        super().tearDownClass()

    def setUp(self) -> None:
        self.dsl = AuthenticationBrowserDsl(self, os.environ["TDR_ACCEPTANCE_BASE_URL"])
        self.steps = AuthenticationSteps(self.dsl)
        self.steps.reset_authentication_state()

    def test_tdr_auth_01_unauthenticated_visitor_cannot_use_candidate_search(self) -> None:
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.visitor_opens_candidate_proposal_surface()
        self.steps.visitor_is_safely_guided_to_sign_in()
        self.steps.candidate_api_returns_authentication_required()

    def test_tdr_auth_02_active_organizer_signs_in_to_candidate_screen(self) -> None:
        self.steps.administrator_enables_organizer(
            "organizer-a", "synthetic-organizer-a", "synthetic-secret-a"
        )
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in("synthetic-organizer-a", "synthetic-secret-a")
        self.steps.organizer_has_authenticated_candidate_screen()

    def test_tdr_auth_03_public_signup_and_email_reset_are_not_available(self) -> None:
        self.steps.visitor_requests_public_account_operations()
        self.steps.public_account_operations_are_unavailable()

    def test_tdr_auth_04_organizer_can_sign_out_and_change_password(self) -> None:
        original_password = "synthetic-secret-before-change"
        new_password = "synthetic-secret-after-change"
        self.steps.administrator_enables_organizer(
            "organizer-a", "synthetic-organizer-a", original_password
        )
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in("synthetic-organizer-a", original_password)
        self.steps.organizer_has_authenticated_candidate_screen()
        self.steps.organizer_signs_out()
        self.steps.protected_candidate_access_is_no_longer_available()
        self.steps.organizer_signs_in("synthetic-organizer-a", original_password)
        self.steps.organizer_opens_password_change()
        self.steps.organizer_changes_password(original_password, new_password)
        self.steps.organizer_signs_out()
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in("synthetic-organizer-a", new_password)
        self.steps.organizer_has_authenticated_candidate_screen()

    def test_tdr_auth_05_deactivation_revokes_protected_access(self) -> None:
        password = "synthetic-secret-a"
        self.steps.administrator_enables_organizer("organizer-a", "synthetic-organizer-a", password)
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in("synthetic-organizer-a", password)
        self.steps.organizer_has_authenticated_candidate_screen()
        self.steps.administrator_deactivates_organizer(
            "organizer-a", "synthetic-organizer-a", password
        )
        self.steps.deactivated_organizer_loses_protected_access()

    def test_tdr_auth_07_throttle_and_generic_failure_do_not_disclose_account_state(self) -> None:
        disabled_identifier = "synthetic-disabled-organizer"
        disabled_password = "synthetic-disabled-secret"
        unknown_identifier = "synthetic-unknown-organizer"
        unknown_password = "synthetic-unknown-secret"
        self.steps.administrator_enables_organizer(
            "disabled-a", disabled_identifier, disabled_password
        )
        self.steps.administrator_deactivates_organizer(
            "disabled-a", disabled_identifier, disabled_password
        )
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in(unknown_identifier, unknown_password)
        unknown_failure = self.steps.visitor_has_generic_sign_in_failure(
            unknown_identifier, unknown_password
        )
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in(disabled_identifier, disabled_password)
        disabled_failure = self.steps.visitor_has_generic_sign_in_failure(
            disabled_identifier, disabled_password
        )
        self.assertEqual(unknown_failure, disabled_failure)
        self.steps.administrator_seeds_throttled_sign_in(unknown_identifier)
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in(unknown_identifier, unknown_password)
        unknown_throttled = self.steps.visitor_has_throttled_sign_in_failure(
            unknown_identifier, unknown_password
        )
        self.steps.administrator_seeds_throttled_sign_in(disabled_identifier)
        self.steps.visitor_has_no_active_organizer_session()
        self.steps.organizer_signs_in(disabled_identifier, disabled_password)
        disabled_throttled = self.steps.visitor_has_throttled_sign_in_failure(
            disabled_identifier, disabled_password
        )
        self.assertEqual(unknown_throttled, disabled_throttled)
