import importlib.util
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGE_PATH = PROJECT_ROOT / "manage.py"


def load_manage_module():
    spec = importlib.util.spec_from_file_location("dining_radar_manage", MANAGE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ManageBootstrapTests(SimpleTestCase):
    def test_plain_test_command_selects_the_isolated_acceptance_settings(self):
        manage = load_manage_module()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(sys, "argv", [str(MANAGE_PATH), "test"]),
            patch("django.core.management.execute_from_command_line"),
        ):
            manage.main()

            self.assertEqual(os.environ["DJANGO_SETTINGS_MODULE"], "dining_radar.settings_test")

    def test_non_test_command_keeps_the_public_runtime_settings_default(self):
        manage = load_manage_module()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(sys, "argv", [str(MANAGE_PATH), "check"]),
            patch("django.core.management.execute_from_command_line"),
        ):
            manage.main()

            self.assertEqual(os.environ["DJANGO_SETTINGS_MODULE"], "dining_radar.settings")

    def test_main_loads_the_projects_local_env_file_before_dispatching_the_command(self):
        """`main()` wires the loader to a fixed, predictable path.

        This never touches a real `.env.local` (Claude Code cannot Read,
        Edit, or Write any `.env*` path per `meta/adr/0040`); it only
        asserts the loader is invoked with the path a developer's
        `.env.local` would occupy next to `manage.py`.
        """
        manage = load_manage_module()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(sys, "argv", [str(MANAGE_PATH), "check"]),
            patch("django.core.management.execute_from_command_line"),
            patch.object(manage, "_load_local_env_file") as mock_loader,
        ):
            manage.main()

            mock_loader.assert_called_once_with(MANAGE_PATH.parent / ".env.local")

    def test_local_env_file_is_a_silent_no_op_when_absent(self):
        manage = load_manage_module()
        with TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "does-not-exist.local"
            with patch.dict(os.environ, {}, clear=True):
                manage._load_local_env_file(missing_path)

                self.assertEqual(dict(os.environ), {})

    def test_local_env_file_fills_unset_variables_without_overriding_the_real_environment(self):
        manage = load_manage_module()
        with TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture-local-config.txt"
            fixture_path.write_text(
                "\n".join(
                    [
                        "# a comment line is ignored",
                        "",
                        "DJANGO_SECRET_KEY=from-file",
                        'DJANGO_ALLOWED_HOSTS="quoted.invalid"',
                        "HOTPEPPER_SEARCH_LATITUDE='36.0'",
                        "malformed line without an equals sign",
                        "HOTPEPPER_API_KEY=from-file-key",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"DJANGO_SECRET_KEY": "already-set-wins"}, clear=True):
                manage._load_local_env_file(fixture_path)

                self.assertEqual(os.environ["DJANGO_SECRET_KEY"], "already-set-wins")
                self.assertEqual(os.environ["DJANGO_ALLOWED_HOSTS"], "quoted.invalid")
                self.assertEqual(os.environ["HOTPEPPER_SEARCH_LATITUDE"], "36.0")
                self.assertEqual(os.environ["HOTPEPPER_API_KEY"], "from-file-key")
                self.assertNotIn("malformed line without an equals sign", os.environ)


class DeploymentHealthCheckTests(TestCase):
    def test_health_check_confirms_database_readiness_without_provider_access(self):
        response = Client().get(reverse("health-check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(
            response.headers["Cache-Control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

    def test_health_check_returns_only_generic_unavailability_on_database_failure(self):
        with patch("dining_radar.health.connection.cursor", side_effect=DatabaseError("secret")):
            response = Client().get(reverse("health-check"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"unavailable")
        self.assertNotIn(b"secret", response.content)


class HealthCheckHostExemptionTests(TestCase):
    """A load balancer probes by IP, which no ALLOWED_HOSTS list can enumerate."""

    PROBE_HOST = "10.0.1.23:8000"

    def test_without_the_middleware_a_probe_by_ip_is_rejected_by_host_validation(self):
        response = Client().get(reverse("health-check"), HTTP_HOST=self.PROBE_HOST)

        self.assertEqual(response.status_code, 400)

    def test_the_middleware_answers_the_probe_by_ip_without_host_validation(self):
        middleware = ["dining_radar.health.HealthCheckMiddleware", *settings.MIDDLEWARE]
        with override_settings(MIDDLEWARE=middleware):
            response = Client().get("/healthz", HTTP_HOST=self.PROBE_HOST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_the_middleware_still_reports_database_failure_as_a_generic_503(self):
        middleware = ["dining_radar.health.HealthCheckMiddleware", *settings.MIDDLEWARE]
        with (
            override_settings(MIDDLEWARE=middleware),
            patch("dining_radar.health.connection.cursor", side_effect=DatabaseError("secret")),
        ):
            response = Client().get("/healthz", HTTP_HOST=self.PROBE_HOST)

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"secret", response.content)

    def test_livez_answers_a_probe_by_ip_without_touching_the_database(self):
        middleware = ["dining_radar.health.HealthCheckMiddleware", *settings.MIDDLEWARE]
        with (
            override_settings(MIDDLEWARE=middleware),
            patch("dining_radar.health.connection.cursor") as cursor,
        ):
            response = Client().get("/livez", HTTP_HOST=self.PROBE_HOST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        cursor.assert_not_called()

    def test_livez_stays_up_while_the_database_is_down(self):
        middleware = ["dining_radar.health.HealthCheckMiddleware", *settings.MIDDLEWARE]
        with (
            override_settings(MIDDLEWARE=middleware),
            patch("dining_radar.health.connection.cursor", side_effect=DatabaseError("secret")),
        ):
            response = Client().get("/livez", HTTP_HOST=self.PROBE_HOST)

        self.assertEqual(response.status_code, 200)

    def test_the_middleware_does_not_exempt_any_other_path_from_host_validation(self):
        middleware = ["dining_radar.health.HealthCheckMiddleware", *settings.MIDDLEWARE]
        with override_settings(MIDDLEWARE=middleware):
            response = Client().get("/", HTTP_HOST=self.PROBE_HOST)

        self.assertEqual(response.status_code, 400)
