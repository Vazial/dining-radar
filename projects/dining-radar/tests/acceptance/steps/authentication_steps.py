"""Thin Gherkin-to-DSL mappings for TDR-AUTH-01 through TDR-AUTH-05 and 07."""

from __future__ import annotations

from tests.acceptance.dsl.authentication_browser import AuthenticationBrowserDsl


class AuthenticationSteps:
    def __init__(self, dsl: AuthenticationBrowserDsl) -> None:
        self.dsl = dsl

    def reset_authentication_state(self) -> None:
        self.dsl.reset_authentication_state()

    def visitor_has_no_active_organizer_session(self) -> None:
        self.dsl.open_entry()

    def visitor_opens_candidate_proposal_surface(self) -> None:
        self.dsl.open_candidate_proposal_api_without_session()

    def visitor_is_safely_guided_to_sign_in(self) -> None:
        self.dsl.assert_unauthenticated_entry()

    def candidate_api_returns_authentication_required(self) -> None:
        self.dsl.assert_candidate_api_requires_authentication()

    def administrator_enables_organizer(
        self, account_ref: str, identifier: str, password: str
    ) -> None:
        self.dsl.set_active_organizer(account_ref, identifier, password)

    def organizer_signs_in(self, identifier: str, password: str) -> None:
        self.dsl.sign_in(identifier, password)

    def organizer_has_authenticated_candidate_screen(self) -> None:
        self.dsl.assert_authenticated_candidate_screen_with_persistent_session()

    def visitor_requests_public_account_operations(self) -> None:
        self.dsl.exercise_unavailable_public_operations()

    def public_account_operations_are_unavailable(self) -> None:
        self.dsl.assert_public_account_operations_are_absent()

    def organizer_signs_out(self) -> None:
        self.dsl.sign_out()

    def protected_candidate_access_is_no_longer_available(self) -> None:
        self.dsl.assert_signed_out_and_protected_access_is_revoked()

    def organizer_opens_password_change(self) -> None:
        self.dsl.open_password_change()

    def organizer_changes_password(self, current_password: str, new_password: str) -> None:
        self.dsl.change_password(current_password, new_password)

    def administrator_deactivates_organizer(
        self, account_ref: str, identifier: str, password: str
    ) -> None:
        self.dsl.deactivate_organizer(account_ref, identifier, password)

    def deactivated_organizer_loses_protected_access(self) -> None:
        self.dsl.assert_protected_access_is_revoked()

    def visitor_has_generic_sign_in_failure(self, _identifier: str, password: str) -> str:
        return self.dsl.assert_generic_sign_in_failure(password)

    def administrator_seeds_throttled_sign_in(self, identifier: str) -> None:
        self.dsl.seed_throttled_sign_in(identifier)

    def visitor_has_throttled_sign_in_failure(self, _identifier: str, password: str) -> str:
        return self.dsl.assert_throttled_sign_in_failure(password)
