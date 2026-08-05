"""ADR-0010: Leaflet is vendored under ``static/`` and served same-origin.

The authenticated candidate-proposal screen must not load Leaflet's JS/CSS
from a third-party CDN (``https://unpkg.com`` or any other external origin).
Only the OSM tile server (already boundaried by ADR-0008) remains an external
contact point for the map UI.
"""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOME_TEMPLATE = PROJECT_ROOT / "src" / "dining_radar" / "web" / "templates" / "web" / "home.html"

_VENDORED_LEAFLET_ASSETS = (
    "dining_radar/web/vendor/leaflet/leaflet.js",
    "dining_radar/web/vendor/leaflet/leaflet.css",
    "dining_radar/web/vendor/leaflet/LICENSE",
    "dining_radar/web/vendor/leaflet/images/marker-icon.png",
    "dining_radar/web/vendor/leaflet/images/marker-icon-2x.png",
    "dining_radar/web/vendor/leaflet/images/marker-shadow.png",
    "dining_radar/web/vendor/leaflet/images/layers.png",
    "dining_radar/web/vendor/leaflet/images/layers-2x.png",
)


class LeafletVendoringSourceTests(SimpleTestCase):
    """Static checks against the template source (no request cycle needed)."""

    def test_home_template_does_not_reference_a_third_party_cdn(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn("unpkg.com", source)
        self.assertNotIn("cdn.jsdelivr.net", source)
        self.assertNotIn("cdnjs.cloudflare.com", source)

    def test_home_template_loads_leaflet_through_the_static_tag(self):
        source = HOME_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("{% static 'dining_radar/web/vendor/leaflet/leaflet.css' %}", source)
        self.assertIn("{% static 'dining_radar/web/vendor/leaflet/leaflet.js' %}", source)

    def test_vendored_leaflet_assets_are_discoverable_by_the_staticfiles_finders(self):
        for asset in _VENDORED_LEAFLET_ASSETS:
            with self.subTest(asset=asset):
                self.assertIsNotNone(
                    finders.find(asset), f"{asset} is not reachable by Django's staticfiles finders"
                )

    def test_vendored_leaflet_license_identifies_the_bsd_2_clause_terms(self):
        license_path = finders.find("dining_radar/web/vendor/leaflet/LICENSE")
        self.assertIsNotNone(license_path)

        license_text = Path(license_path).read_text(encoding="utf-8")
        self.assertIn("BSD 2-Clause License", license_text)


class LeafletVendoringRenderedPageTests(TestCase):
    """The authenticated screen's rendered HTML must carry the same-origin URLs."""

    def setUp(self):
        self.password = "Synthetic-passphrase-123!"
        self.user = get_user_model().objects.create_user(
            username="static-asset-organizer", password=self.password
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_rendered_home_page_references_the_same_origin_leaflet_assets(self):
        page = self.client.get(reverse("web:home"))
        body = page.content.decode("utf-8")

        self.assertIn("/static/dining_radar/web/vendor/leaflet/leaflet.css", body)
        self.assertIn("/static/dining_radar/web/vendor/leaflet/leaflet.js", body)

    def test_rendered_home_page_never_contacts_a_third_party_cdn_for_leaflet(self):
        page = self.client.get(reverse("web:home"))
        body = page.content.decode("utf-8")

        self.assertNotIn("unpkg.com", body)
        self.assertNotIn("cdn.jsdelivr.net", body)
        self.assertNotIn("cdnjs.cloudflare.com", body)
