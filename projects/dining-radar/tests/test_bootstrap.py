import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

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
