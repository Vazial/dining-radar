import ast
import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from dining_radar import settings_base

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "dining_radar"


class ApplicationStructureTests(SimpleTestCase):
    def test_web_layer_does_not_reach_adapter_or_orm_layers_directly(self):
        forbidden_prefixes = ("dining_radar.integrations", "dining_radar.records")

        for source_file in (SOURCE_ROOT / "web").glob("*.py"):
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)

            with self.subTest(source_file=source_file.name):
                self.assertFalse(any(name.startswith(forbidden_prefixes) for name in imports))
                self.assertNotIn("django.db", imports)

    def test_session_and_csrf_cookie_policy_is_explicit_and_restrictive(self):
        self.assertTrue(settings_base.SESSION_COOKIE_SECURE)
        self.assertTrue(settings_base.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings_base.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings_base.CSRF_COOKIE_SECURE)
        self.assertEqual(settings_base.CSRF_COOKIE_SAMESITE, "Lax")

    def test_authentication_routes_do_not_offer_signup_or_email_reset(self):
        route_source = (SOURCE_ROOT / "authentication" / "urls.py").read_text(encoding="utf-8")

        self.assertNotIn("password_reset", route_source)
        self.assertNotIn("signup", route_source)

    def test_public_runtime_requires_a_secret_and_enables_https_redirect(self):
        runtime_environment = {
            "DJANGO_SECRET_KEY": "synthetic-runtime-secret",
            "DJANGO_ALLOWED_HOSTS": " first.invalid, second.invalid ",
        }
        with patch.dict(os.environ, runtime_environment, clear=True):
            runtime = runpy.run_module("dining_radar.settings", run_name="dining_radar._probe")

        self.assertEqual(runtime["SECRET_KEY"], "synthetic-runtime-secret")
        self.assertEqual(runtime["ALLOWED_HOSTS"], ["first.invalid", "second.invalid"])
        self.assertFalse(runtime["DEBUG"])
        self.assertTrue(runtime["SECURE_SSL_REDIRECT"])

    def test_public_runtime_rejects_a_missing_secret(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "DJANGO_SECRET_KEY must be configured"),
        ):
            runpy.run_module("dining_radar.settings", run_name="dining_radar._missing_secret_probe")
