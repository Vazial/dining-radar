import os
import re
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse


class OrganizerProvisioningCommandTests(TestCase):
    def test_if_configured_is_a_no_op_when_both_secrets_are_absent(self):
        output = StringIO()
        with patch.dict(os.environ, {}, clear=True):
            call_command("provision_organizer", "--if-configured", stdout=output)

        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertIn("nothing to do", output.getvalue())

    def test_configured_organizer_is_created_without_operator_privileges(self):
        environment = {
            "DJANGO_BOOTSTRAP_ORGANIZER_USERNAME": "deployment-organizer",
            "DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD": "Synthetic-deploy-passphrase-123!",
        }
        output = StringIO()
        with patch.dict(os.environ, environment, clear=True):
            call_command("provision_organizer", stdout=output)

        user = get_user_model().objects.get(username="deployment-organizer")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(environment["DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD"]))
        self.assertIn("created", output.getvalue())

    def test_existing_organizer_password_and_permissions_are_never_rewritten(self):
        user = get_user_model().objects.create_user(
            username="deployment-organizer",
            password="Existing-passphrase-123!",
            is_staff=True,
        )
        environment = {
            "DJANGO_BOOTSTRAP_ORGANIZER_USERNAME": user.username,
            "DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD": "Replacement-passphrase-456!",
        }
        with patch.dict(os.environ, environment, clear=True):
            call_command("provision_organizer")

        user.refresh_from_db()
        self.assertTrue(user.check_password("Existing-passphrase-123!"))
        self.assertTrue(user.is_staff)

    def test_partial_or_weak_bootstrap_configuration_is_rejected_without_echoing_secrets(self):
        with (
            patch.dict(
                os.environ,
                {"DJANGO_BOOTSTRAP_ORGANIZER_USERNAME": "deployment-organizer"},
                clear=True,
            ),
            self.assertRaisesRegex(CommandError, "Both DJANGO_BOOTSTRAP"),
        ):
            call_command("provision_organizer")

        with (
            override_settings(
                AUTH_PASSWORD_VALIDATORS=[
                    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}
                ]
            ),
            patch.dict(
                os.environ,
                {
                    "DJANGO_BOOTSTRAP_ORGANIZER_USERNAME": "deployment-organizer",
                    "DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD": "123",
                },
                clear=True,
            ),
            self.assertRaisesRegex(CommandError, "not acceptable") as error,
        ):
            call_command("provision_organizer")

        self.assertNotIn("123", str(error.exception))


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.password = "Synthetic-passphrase-123!"
        self.user = get_user_model().objects.create_user(
            username="organizer-synthetic", password=self.password
        )

    def csrf_token_from(self, response):
        matched = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', response.content)
        self.assertIsNotNone(matched)
        return matched.group(1).decode("ascii")

    def test_unauthenticated_visitors_are_redirected_before_the_shell_is_rendered(self):
        response = self.client.get(reverse("web:home"))

        self.assertRedirects(
            response,
            f"{reverse('authentication:login')}?next={reverse('web:home')}",
            fetch_redirect_response=False,
        )

    def test_authentication_pages_use_the_narrow_viewport_layout(self):
        login = self.client.get(reverse("authentication:login"))

        self.assertContains(login, 'name="viewport" content="width=device-width, initial-scale=1"')
        self.assertContains(login, 'class="app-shell"')
        self.assertContains(login, 'class="app-card"')

        self.client.force_login(self.user)
        home = self.client.get(reverse("web:home"))
        password_change = self.client.get(reverse("authentication:password_change"))

        self.assertContains(home, 'class="account-nav"')
        self.assertContains(password_change, 'class="app-shell"')

    def test_candidate_api_returns_safe_authentication_problem_for_anonymous_request(self):
        csrf_client = Client(enforce_csrf_checks=True)
        login_page = csrf_client.get(reverse("authentication:login"))
        csrf_token = self.csrf_token_from(login_page)

        response = csrf_client.post(
            reverse("web:candidate-proposals"),
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Sign in is required to view candidate proposals.",
            },
        )

    def test_manager_provisioned_active_account_can_sign_in(self):
        response = self.client.post(
            reverse("authentication:login"),
            {"username": self.user.username, "password": self.password},
        )

        self.assertRedirects(response, reverse("web:home"), fetch_redirect_response=False)
        self.assertIn(settings.SESSION_COOKIE_NAME, response.cookies)
        self.assertFalse(response.cookies[settings.SESSION_COOKIE_NAME]["secure"])
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]["httponly"])
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]["samesite"], "Lax")

        shell = self.client.get(reverse("web:home"))
        self.assertContains(shell, 'id="candidate-app"')
        self.assertContains(shell, 'data-testid="auth-individual-account-guidance"')
        self.assertContains(shell, 'data-auth-account-use="individual-only"')
        self.assertContains(shell, 'data-auth-credential-sharing="not-requested"')
        self.assertContains(shell, "管理者から案内された個別アカウント")
        self.assertNotContains(shell, "公開サインアップ")

    def test_public_signup_and_email_reset_routes_are_absent(self):
        self.assertEqual(self.client.get("/sign-up").status_code, 404)
        root_reset = self.client.get("/password-reset")
        self.assertEqual(root_reset.status_code, 404)
        self.assertNotContains(root_reset, "token", status_code=404)
        self.assertNotContains(root_reset, "resetToken", status_code=404)
        self.assertNotContains(root_reset, "email", status_code=404)
        self.assertEqual(self.client.get("/accounts/signup/").status_code, 404)
        self.assertEqual(self.client.get("/accounts/password_reset/").status_code, 404)

    def test_logout_is_csrf_protected_and_ends_access_to_the_shell(self):
        self.client.force_login(self.user)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        missing_token = csrf_client.post(reverse("authentication:logout"))
        self.assertEqual(missing_token.status_code, 403)

        page = csrf_client.get(reverse("web:home"))
        csrf_token = self.csrf_token_from(page)
        response = csrf_client.post(
            reverse("authentication:logout"), {"csrfmiddlewaretoken": csrf_token}
        )
        self.assertRedirects(
            response, reverse("authentication:login"), fetch_redirect_response=False
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(csrf_client.get(reverse("web:home")).status_code, 302)

    def test_authenticated_organizer_can_change_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("authentication:password_change"),
            {
                "old_password": self.password,
                "new_password1": "Changed-synthetic-passphrase-456!",
                "new_password2": "Changed-synthetic-passphrase-456!",
            },
        )

        self.assertRedirects(response, reverse("web:home"), fetch_redirect_response=False)
        self.client.logout()
        self.assertTrue(
            self.client.login(
                username=self.user.username, password="Changed-synthetic-passphrase-456!"
            )
        )

    def test_deactivated_account_loses_protected_access_on_its_next_request(self):
        self.client.force_login(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get(reverse("web:home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("authentication:login"), response["Location"])

    def test_cookie_authenticated_state_changes_require_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        rejected = csrf_client.post(
            reverse("web:candidate-proposals"), data="{}", content_type="application/json"
        )
        self.assertEqual(rejected.status_code, 403)

        page = csrf_client.get(reverse("web:home"))
        csrf_token = self.csrf_token_from(page)
        accepted_boundary = csrf_client.post(
            reverse("web:candidate-proposals"),
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted_boundary.status_code, 503)
        self.assertEqual(accepted_boundary.json()["code"], "PROVIDER_UNAVAILABLE")

    @override_settings(LOGIN_THROTTLE_MAX_FAILURES=2, LOGIN_THROTTLE_WINDOW_SECONDS=60)
    def test_failed_login_is_throttled_without_revealing_account_state(self):
        cache.clear()
        login_url = reverse("authentication:login")

        invalid_user = self.client.post(
            login_url, {"username": "not-an-account", "password": "wrong"}
        )
        disabled_user = get_user_model().objects.create_user(
            username="disabled-synthetic", password=self.password, is_active=False
        )
        invalid_disabled = self.client.post(
            login_url, {"username": disabled_user.username, "password": self.password}
        )
        self.assertContains(invalid_user, "正しいユーザー名とパスワードを入力してください")
        self.assertContains(invalid_disabled, "正しいユーザー名とパスワードを入力してください")

        self.client.post(login_url, {"username": self.user.username, "password": "wrong"})
        self.client.post(login_url, {"username": self.user.username, "password": "wrong"})
        throttled = self.client.post(
            login_url, {"username": self.user.username, "password": self.password}
        )

        self.assertEqual(throttled.status_code, 200)
        self.assertContains(throttled, "正しいユーザー名とパスワードを入力してください")
        self.assertIsInstance(throttled.wsgi_request.user, AnonymousUser)

    def test_no_cross_origin_credential_header_is_added(self):
        response = self.client.get(
            reverse("authentication:login"), HTTP_ORIGIN="https://other.invalid"
        )

        self.assertNotIn("Access-Control-Allow-Origin", response)
