import json
import urllib.error

from django.test import SimpleTestCase

from dining_radar.integrations.hotpepper.client import fetch_shops, redact_query
from dining_radar.integrations.hotpepper.config import HotPepperConfig
from dining_radar.integrations.hotpepper.errors import (
    HotPepperCommunicationError,
    HotPepperConfigurationError,
    HotPepperResponseError,
)
from dining_radar.integrations.hotpepper.normalize import normalize_shops


class HotPepperConfigTests(SimpleTestCase):
    def test_reads_required_values_from_the_environment(self):
        config = HotPepperConfig.from_env(
            {
                "HOTPEPPER_API_KEY": "synthetic-key",
                "HOTPEPPER_SEARCH_LATITUDE": "35.0",
                "HOTPEPPER_SEARCH_LONGITUDE": "139.0",
            }
        )

        self.assertEqual(config.api_key, "synthetic-key")
        self.assertEqual(config.origin_latitude, 35.0)
        self.assertEqual(config.origin_longitude, 139.0)
        self.assertEqual(config.search_range, "3")
        self.assertTrue(config.base_url.startswith("https://"))

    def test_missing_api_key_raises_configuration_error(self):
        with self.assertRaisesRegex(HotPepperConfigurationError, "HOTPEPPER_API_KEY"):
            HotPepperConfig.from_env(
                {"HOTPEPPER_SEARCH_LATITUDE": "35.0", "HOTPEPPER_SEARCH_LONGITUDE": "139.0"}
            )

    def test_missing_coordinates_raise_configuration_error(self):
        with self.assertRaises(HotPepperConfigurationError):
            HotPepperConfig.from_env({"HOTPEPPER_API_KEY": "synthetic-key"})

    def test_non_numeric_coordinates_raise_configuration_error(self):
        with self.assertRaises(HotPepperConfigurationError):
            HotPepperConfig.from_env(
                {
                    "HOTPEPPER_API_KEY": "synthetic-key",
                    "HOTPEPPER_SEARCH_LATITUDE": "not-a-number",
                    "HOTPEPPER_SEARCH_LONGITUDE": "139.0",
                }
            )

    def test_non_https_base_url_is_rejected(self):
        with self.assertRaises(HotPepperConfigurationError):
            HotPepperConfig.from_env(
                {
                    "HOTPEPPER_API_KEY": "synthetic-key",
                    "HOTPEPPER_SEARCH_LATITUDE": "35.0",
                    "HOTPEPPER_SEARCH_LONGITUDE": "139.0",
                    "HOTPEPPER_API_BASE_URL": "http://insecure.invalid/",
                }
            )

    def test_custom_range_is_honored(self):
        config = HotPepperConfig.from_env(
            {
                "HOTPEPPER_API_KEY": "synthetic-key",
                "HOTPEPPER_SEARCH_LATITUDE": "35.0",
                "HOTPEPPER_SEARCH_LONGITUDE": "139.0",
                "HOTPEPPER_SEARCH_RANGE": "5",
            }
        )

        self.assertEqual(config.search_range, "5")


class RedactQueryTests(SimpleTestCase):
    def test_key_parameter_value_is_replaced(self):
        redacted = redact_query("https://example.invalid/?key=super-secret&lat=1")

        self.assertNotIn("super-secret", redacted)
        self.assertIn("key=REDACTED", redacted)
        self.assertIn("lat=1", redacted)

    def test_blank_query_values_are_preserved(self):
        redacted = redact_query("https://example.invalid/?key=super-secret&empty=&lat=1")

        self.assertIn("empty=", redacted)


class _FakeHttpResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        return False

    def read(self) -> bytes:
        return self._body


def _config():
    return HotPepperConfig.from_env(
        {
            "HOTPEPPER_API_KEY": "synthetic-key",
            "HOTPEPPER_SEARCH_LATITUDE": "35.0",
            "HOTPEPPER_SEARCH_LONGITUDE": "139.0",
        }
    )


class FetchShopsTests(SimpleTestCase):
    def test_returns_the_parsed_json_body(self):
        payload = {"results": {"shop": []}}

        def opener(request, timeout):
            self.assertIn("key=", request.full_url)
            self.assertEqual(timeout, 8)
            return _FakeHttpResponse(json.dumps(payload).encode("utf-8"))

        result = fetch_shops(_config(), opener=opener)

        self.assertEqual(result, payload)

    def test_communication_failure_is_translated_without_leaking_the_key(self):
        def opener(request, timeout):
            raise urllib.error.URLError("boom")

        with self.assertRaises(HotPepperCommunicationError) as raised:
            fetch_shops(_config(), opener=opener)

        self.assertNotIn("synthetic-key", str(raised.exception))

    def test_malformed_json_body_raises_response_error(self):
        def opener(request, timeout):
            return _FakeHttpResponse(b"not-json")

        with self.assertRaises(HotPepperResponseError):
            fetch_shops(_config(), opener=opener)

    def test_non_object_json_body_raises_response_error(self):
        def opener(request, timeout):
            return _FakeHttpResponse(b"[]")

        with self.assertRaises(HotPepperResponseError):
            fetch_shops(_config(), opener=opener)


class NormalizeShopsTests(SimpleTestCase):
    def _raw_shop(self, **overrides):
        shop = {
            "name": "架空食堂",
            "genre": {"name": "和食"},
            "catch": "季節の定食が中心です。",
            "open": "11:00〜14:30",
            "close": "日曜",
            "capacity": "38",
            "lat": "35.1",
            "lng": "139.1",
            "urls": {"pc": "https://example.invalid/shop-a"},
            "non_smoking": "全面禁煙",
            "card": "利用可",
            "budget": {"code": "B003", "name": "3,001〜4,000円", "average": "3500"},
        }
        shop.update(overrides)
        return shop

    def test_normalizes_a_complete_shop(self):
        [candidate] = normalize_shops({"results": {"shop": [self._raw_shop()]}})

        self.assertEqual(candidate.name, "架空食堂")
        self.assertEqual(candidate.genre, "和食")
        self.assertEqual(candidate.description, "季節の定食が中心です。")
        # adr/0017 decision 7: business hours (the provider's `open` field)
        # is no longer part of NormalizedCandidate; normalize_shops must not
        # read it into anything this application still carries.
        self.assertFalse(hasattr(candidate, "business_hours"))
        # adr/0019 decision 6: access is no longer read at all.
        self.assertFalse(hasattr(candidate, "access"))
        self.assertEqual(candidate.regular_holiday, "日曜")
        self.assertEqual(candidate.total_seats, 38)
        self.assertEqual(candidate.non_smoking_status, "FULL")
        self.assertEqual(candidate.card_payment_available, True)
        self.assertEqual(candidate.budget_average, 4000.0)
        self.assertEqual(candidate.latitude, 35.1)
        self.assertEqual(candidate.longitude, 139.1)
        self.assertEqual(candidate.provider_page_url, "https://example.invalid/shop-a")

    def test_missing_optional_fields_become_none(self):
        raw = self._raw_shop(
            catch=None,
            open=None,
            close=None,
            capacity=None,
            non_smoking=None,
            card=None,
            budget=None,
        )

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIsNone(candidate.description)
        self.assertIsNone(candidate.regular_holiday)
        self.assertIsNone(candidate.total_seats)
        self.assertIsNone(candidate.non_smoking_status)
        self.assertIsNone(candidate.card_payment_available)
        self.assertIsNone(candidate.budget_average)

    def test_missing_name_raises_response_error(self):
        raw = self._raw_shop()
        del raw["name"]

        with self.assertRaises(HotPepperResponseError):
            normalize_shops({"results": {"shop": [raw]}})

    def test_missing_genre_raises_response_error(self):
        raw = self._raw_shop(genre=None)

        with self.assertRaises(HotPepperResponseError):
            normalize_shops({"results": {"shop": [raw]}})

    def test_missing_page_url_raises_response_error(self):
        raw = self._raw_shop(urls=None)

        with self.assertRaises(HotPepperResponseError):
            normalize_shops({"results": {"shop": [raw]}})

    def test_non_numeric_coordinates_raise_response_error(self):
        raw = self._raw_shop(lat="not-a-number")

        with self.assertRaises(HotPepperResponseError):
            normalize_shops({"results": {"shop": [raw]}})

    def test_missing_results_shop_raises_response_error(self):
        with self.assertRaises(HotPepperResponseError):
            normalize_shops({"results": {}})

    def test_results_shop_as_a_string_raises_response_error(self):
        with self.assertRaisesRegex(HotPepperResponseError, "was not a list"):
            normalize_shops({"results": {"shop": "not-a-list"}})

    def test_results_shop_as_a_non_iterable_raises_response_error(self):
        with self.assertRaisesRegex(HotPepperResponseError, "was not a list"):
            normalize_shops({"results": {"shop": 12345}})

    def test_a_shop_entry_that_is_not_an_object_raises_response_error(self):
        with self.assertRaisesRegex(HotPepperResponseError, "must be an object"):
            normalize_shops({"results": {"shop": ["not-an-object"]}})

    # total_seats numeric-typing branches -----------------------------------

    def test_capacity_supplied_as_an_int_is_read_directly(self):
        raw = self._raw_shop(capacity=38)

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.total_seats, 38)

    def test_capacity_supplied_as_a_bool_is_treated_as_missing(self):
        raw = self._raw_shop(capacity=True)

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIsNone(candidate.total_seats)

    # budget_average now reads budget.name, not budget.average (2026-08-10
    # field-survey correction) -----------------------------------------------

    def test_budget_average_reads_the_upper_bound_of_a_name_range(self):
        raw = self._raw_shop(budget={"name": "3,001〜4,000円"})

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.budget_average, 4000.0)

    def test_budget_average_reads_a_name_range_without_commas(self):
        raw = self._raw_shop(budget={"name": "1501～2000円"})

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.budget_average, 2000.0)

    def test_budget_average_reads_a_single_figure_name(self):
        raw = self._raw_shop(budget={"name": "5000円"})

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.budget_average, 5000.0)

    def test_budget_average_ignores_a_free_form_average_and_still_reads_name(self):
        # The exact field-survey shape this fix responds to: `average` mixes
        # more than one labeled figure and must not be guessed between, but
        # `name` alone is enough.
        raw = self._raw_shop(
            budget={"average": "通常平均：3000円 / 宴会平均：3500円", "name": "2,001〜3,000円"}
        )

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.budget_average, 3000.0)

    def test_budget_average_is_null_when_name_is_not_a_string(self):
        raw = self._raw_shop(budget={"name": None})

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIsNone(candidate.budget_average)

    def test_budget_average_is_null_when_name_names_no_figure(self):
        raw = self._raw_shop(budget={"name": "応相談"})

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIsNone(candidate.budget_average)

    # non_smoking classification (adr/0019 decision 9) ---------------------

    def test_non_smoking_full_when_the_text_contains_zenmen_kinen(self):
        raw = self._raw_shop(non_smoking="全面禁煙")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.non_smoking_status, "FULL")

    def test_non_smoking_partial_when_kinen_without_zenmen(self):
        raw = self._raw_shop(non_smoking="分煙（一部禁煙）")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.non_smoking_status, "PARTIAL")

    def test_non_smoking_none_for_a_known_negative_marker(self):
        raw = self._raw_shop(non_smoking="なし")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.non_smoking_status, "NONE")

    def test_non_smoking_unknown_text_is_left_null(self):
        raw = self._raw_shop(non_smoking="喫煙可の店内です")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIsNone(candidate.non_smoking_status)

    # card classification (adr/0019 decision 9) -----------------------------

    def test_card_true_when_the_text_contains_ka_without_fuka(self):
        raw = self._raw_shop(card="利用可")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIs(candidate.card_payment_available, True)

    def test_card_false_when_the_text_contains_fuka(self):
        raw = self._raw_shop(card="利用不可")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIs(candidate.card_payment_available, False)

    def test_card_unknown_text_is_left_null(self):
        raw = self._raw_shop(card="要確認")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIsNone(candidate.card_payment_available)

    # budget.name is read regardless of the (now-ignored) code/average siblings

    def test_budget_average_is_read_from_the_nested_budget_object(self):
        raw = self._raw_shop(budget={"average": "2800", "code": "B011", "name": "2,001〜3,000円"})

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertEqual(candidate.budget_average, 3000.0)

    def test_budget_average_is_null_when_budget_is_not_an_object(self):
        raw = self._raw_shop(budget="3000円くらい")

        [candidate] = normalize_shops({"results": {"shop": [raw]}})

        self.assertIsNone(candidate.budget_average)
