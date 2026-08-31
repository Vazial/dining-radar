import ast
import os
import runpy
from pathlib import Path
from unittest.mock import patch

import yaml
from django.test import Client, SimpleTestCase, TestCase, override_settings

from dining_radar import settings_base

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "dining_radar"


class ApplicationStructureTests(SimpleTestCase):
    def test_render_blueprint_uses_the_agreed_free_stateless_topology(self):
        blueprint = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(blueprint["services"]), 1)

        service = blueprint["services"][0]
        self.assertEqual(service["type"], "web")
        self.assertEqual(service["runtime"], "python")
        self.assertEqual(service["plan"], "free")
        self.assertEqual(service["region"], "singapore")
        self.assertEqual(service["rootDir"], "projects/dining-radar")
        self.assertEqual(service["healthCheckPath"], "/healthz")
        self.assertEqual(service["autoDeployTrigger"], "checksPass")
        self.assertIn("--workers 1", service["startCommand"])

        env_vars = {item["key"]: item for item in service["envVars"]}
        self.assertTrue(env_vars["DJANGO_SECRET_KEY"]["generateValue"])
        for secret_name in (
            "DATABASE_URL",
            "HOTPEPPER_API_KEY",
            "HOTPEPPER_SEARCH_LATITUDE",
            "HOTPEPPER_SEARCH_LONGITUDE",
            "HOTPEPPER_SEARCH_RANGE",
            "DJANGO_BOOTSTRAP_ORGANIZER_USERNAME",
            "DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD",
        ):
            self.assertEqual(env_vars[secret_name], {"key": secret_name, "sync": False})

    def test_render_build_is_reproducible_and_checks_the_deployed_configuration(self):
        build_script = (PROJECT_ROOT / "build.sh").read_text(encoding="utf-8")

        commands = [
            "python -m pip install --disable-pip-version-check -e .",
            "python manage.py collectstatic --no-input",
            "python manage.py migrate --no-input",
            "python manage.py provision_organizer --if-configured",
            "python manage.py check --deploy",
        ]
        positions = [build_script.index(command) for command in commands]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD=", build_script)

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

    def test_gathering_layer_does_not_reach_the_adapter_layer_directly(self):
        """Mirrors the web layer's own adapter-boundary rule above.

        Unlike ``web``, ``gathering`` legitimately owns an ORM (its own
        persisted models -- the first this product has, ADR-0034 decision
        6), so this does not also forbid ``django.db`` the way the ``web``
        check above does. It still must never import
        ``dining_radar.integrations`` directly: provider communication is
        reached only through ``dining_radar.suggestions``
        (``hotpepper_source``/``acceptance_state``), the same boundary
        ``dining_radar.web`` observes for candidate-search.
        """
        forbidden_prefixes = ("dining_radar.integrations",)

        for source_file in (SOURCE_ROOT / "gathering").glob("*.py"):
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)

            with self.subTest(source_file=source_file.name):
                self.assertFalse(any(name.startswith(forbidden_prefixes) for name in imports))

    def test_recommendation_module_has_no_framework_or_provider_dependency(self):
        """ADR-0001 decision 3: recommendation is a pure Python pipeline."""
        forbidden_prefixes = ("django", "dining_radar.integrations", "dining_radar.records")

        for source_file in (SOURCE_ROOT / "recommendation").glob("*.py"):
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)

            with self.subTest(source_file=source_file.name):
                self.assertFalse(any(name.startswith(forbidden_prefixes) for name in imports))

    def test_session_and_csrf_cookie_policy_is_explicit_and_restrictive(self):
        self.assertTrue(settings_base.SESSION_COOKIE_SECURE)
        self.assertTrue(settings_base.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings_base.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings_base.CSRF_COOKIE_SECURE)
        self.assertEqual(settings_base.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings_base.SECURE_REFERRER_POLICY, "strict-origin-when-cross-origin")

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

    def test_render_runtime_requires_postgres_and_trusts_only_its_https_proxy_signal(self):
        base_environment = {
            "DJANGO_SECRET_KEY": "synthetic-runtime-secret-long-enough-for-deploy-checks",
            "RENDER": "true",
            "RENDER_EXTERNAL_HOSTNAME": "synthetic-service.onrender.com",
        }
        with (
            patch.dict(os.environ, base_environment, clear=True),
            self.assertRaisesRegex(RuntimeError, "DATABASE_URL must be configured"),
        ):
            runpy.run_module("dining_radar.settings", run_name="dining_radar._render_no_db")

        with patch.dict(
            os.environ,
            {
                **base_environment,
                "DATABASE_URL": "postgresql://synthetic:secret@db.invalid:5432/app",
            },
            clear=True,
        ):
            runtime = runpy.run_module(
                "dining_radar.settings", run_name="dining_radar._render_probe"
            )

        self.assertIn("synthetic-service.onrender.com", runtime["ALLOWED_HOSTS"])
        self.assertEqual(runtime["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(runtime["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(runtime["DATABASES"]["default"]["OPTIONS"]["sslmode"], "require")
        self.assertEqual(runtime["SECURE_HSTS_SECONDS"], 31_536_000)

    def test_env_example_documents_exactly_the_environment_variables_read_at_runtime(self):
        """A human must be able to configure this app without reading source.

        `env.example` (ADR-0040: no leading dot, so it sits outside the
        `.env*` deny/gitignore namespace and stays AI-maintainable) is the
        only place that surface is meant to be documented. This test closes
        the gap a human reviewer found before merge: `env.example` did not
        exist even though `integrations/hotpepper/config.py` already read
        five environment variables, so a human had to read implementation
        code to discover them. It also guards against the exact drift
        `meta/adr/0040` documents happening twice in reservation-frontend
        (a new variable added to source without a template update).
        """
        env_accessor_names = {"environ", "env"}

        def collect_env_var_names(tree: ast.AST) -> set[str]:
            names: set[str] = set()
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                ):
                    continue
                receiver = node.func.value
                reads_os_environ = (
                    isinstance(receiver, ast.Attribute)
                    and receiver.attr == "environ"
                    and isinstance(receiver.value, ast.Name)
                    and receiver.value.id == "os"
                )
                reads_environ_like_name = (
                    isinstance(receiver, ast.Name) and receiver.id in env_accessor_names
                )
                if not (reads_os_environ or reads_environ_like_name):
                    continue
                if not node.args:
                    continue
                first_argument = node.args[0]
                if isinstance(first_argument, ast.Constant) and isinstance(
                    first_argument.value, str
                ):
                    names.add(first_argument.value)
            return names

        read_at_runtime: set[str] = set()
        for source_file in SOURCE_ROOT.rglob("*.py"):
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
            read_at_runtime |= collect_env_var_names(tree)

        env_example_path = PROJECT_ROOT / "env.example"
        self.assertTrue(env_example_path.exists(), "projects/dining-radar/env.example must exist")

        documented: set[str] = set()
        for line in env_example_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            documented.add(stripped.split("=", 1)[0].strip())

        self.assertEqual(
            read_at_runtime - documented,
            set(),
            "env.example is missing (name, safe description) for an environment "
            "variable src/dining_radar reads at runtime",
        )
        self.assertEqual(
            documented - read_at_runtime,
            set(),
            "env.example documents a variable src/dining_radar no longer reads at runtime",
        )


class HealthCheckHttpsExemptionTests(TestCase):
    """Measured defect (activeContext.md 2026-08-12): Render's health check is
    sent directly to this service's port, carrying no X-Forwarded-Proto, and
    a 2xx *or* 3xx response alike counts as healthy. Under the unpatched
    production settings module, GET /healthz without that header earned a
    301 -- a response Render still calls healthy -- so the probe's own
    SELECT 1 (dining_radar.health) never ran and a suspended or broken
    database went undetected (adr/0021 decision 5, DEPLOYMENT.md section
    3.6). These tests load the real production settings module (the same
    ``runpy.run_module`` technique ``ApplicationStructureTests`` above uses)
    and then apply its exact computed SECURE_SSL_REDIRECT/
    SECURE_REDIRECT_EXEMPT values to a live request through
    dining_radar.urls, so the regression is caught at the HTTP boundary, not
    only as a module-level attribute. This is a plain ``TestCase`` (not
    ``SimpleTestCase`` like the class above) because /healthz genuinely
    queries the database (``SELECT 1``); pytest-django's already-migrated
    test database serves that query here, independent of the fake
    ``DATABASE_URL`` the production settings module computes (never
    connected to -- ``DATABASES`` itself is deliberately not among the
    computed values applied via ``override_settings`` below).
    """

    def _production_https_redirect_settings(self, run_name):
        environment = {
            "DJANGO_SECRET_KEY": "synthetic-runtime-secret-long-enough-for-deploy-checks",
            "RENDER": "true",
            "RENDER_EXTERNAL_HOSTNAME": "synthetic-service.onrender.com",
            "DATABASE_URL": "postgresql://synthetic:secret@db.invalid:5432/app",
        }
        with patch.dict(os.environ, environment, clear=True):
            runtime = runpy.run_module("dining_radar.settings", run_name=run_name)
        return {
            "SECURE_SSL_REDIRECT": runtime["SECURE_SSL_REDIRECT"],
            "SECURE_REDIRECT_EXEMPT": runtime["SECURE_REDIRECT_EXEMPT"],
        }

    def test_healthz_is_exempt_from_the_production_https_redirect(self):
        computed = self._production_https_redirect_settings("dining_radar._healthz_exempt_probe")
        self.assertTrue(computed["SECURE_SSL_REDIRECT"])
        self.assertEqual(computed["SECURE_REDIRECT_EXEMPT"], [r"^healthz$"])

        with override_settings(
            ROOT_URLCONF="dining_radar.urls",
            ALLOWED_HOSTS=["testserver"],
            **computed,
        ):
            response = Client().get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_other_protected_paths_still_redirect_to_https_under_the_healthz_exemption(self):
        computed = self._production_https_redirect_settings(
            "dining_radar._healthz_exemption_scope_probe"
        )

        with override_settings(
            ROOT_URLCONF="dining_radar.urls",
            ALLOWED_HOSTS=["testserver"],
            **computed,
        ):
            client = Client()
            for path in ("/", "/accounts/login/"):
                with self.subTest(path=path):
                    response = client.get(path)

                    self.assertEqual(response.status_code, 301)
                    self.assertTrue(response["Location"].startswith("https://"))
