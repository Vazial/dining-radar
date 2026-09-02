"""Browser/API DSL for the TDR-GTH gathering-scheduling acceptance scenarios.

Per adr/0037 decision 1, gathering/candidate-date/participant-link/schedule-
response Given state is built by calling gathering-scheduling-api.yaml's own
public operations directly -- not through a dedicated test-support seam --
because every one of those resources is reachable through the public
boundary. test-support-api.yaml adds seams only for link expiry and link
rate-limiting (states real elapsed time/request volume cannot reach
deterministically) and for the synthetic open-shop population TDR-GTH shares
with TDR-CS.

Per gathering-scheduling-browser-interface.yaml's renderModel, both
organizerDashboard and participantAnswer are JS-capable surfaces verified the
same way candidate-search-browser-interface.yaml verifies TDR-CS (Playwright),
not TDR-AUTH's plain-HTTP DSL. Direct calls to gathering-scheduling-api.yaml's
own JSON operations (organizer Given-state construction, TDR-GTH-01's
creation, TDR-GTH-13's fuzzing, and the two 409-boundary checks in
TDR-GTH-10/20) go through ``self.page.context.request`` so they share the
Playwright browser context's cookies (the organizer session) without being a
"browser click-through" -- exactly the profile's own notVerifiedHere note for
TDR-GTH-01/TDR-GTH-13 sanctions ("API/boundary-level acceptance").
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.test import SimpleTestCase
from playwright.sync_api import Locator, Page, Response, expect

from tests.acceptance.dsl.authentication_browser import AuthenticationBrowserDsl
from tests.acceptance.dsl.browser_mechanics import HttpBrowser, assert_no_content
from tests.acceptance.dsl.js_browser_mechanics import (
    CapturedApiResponse,
    assert_absent,
    assert_all_absent,
    assert_all_present,
    assert_present,
    build_captured_response,
    by_test_id,
    csrf_token,
    require,
    wait_for_at_least_one,
)
from tests.acceptance.dsl.openapi_schema import assert_matches_openapi_schema

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GATHERING_API_CONTRACT = PROJECT_ROOT / "contracts" / "gathering-scheduling-api.yaml"

# organizerDashboard test ids / attributes (gathering-scheduling-browser-interface.yaml)
GATHERING_PHASE_INDICATOR = "gathering-phase-indicator"
GATHERING_PHASE_ATTR = "data-gathering-phase"
RESPONDED_SUMMARY = "gathering-responded-summary"
RESPONDED_COUNT_ATTR = "data-responded-count"
ANONYMOUS_RESPONDED_COUNT_ATTR = "data-anonymous-responded-count"
UNANSWERED_SUMMARY = "gathering-unanswered-summary"
TOTAL_ISSUED_LINKS_ATTR = "data-total-issued-links"
REVOKED_LINKS_ATTR = "data-revoked-links"
ACTIVE_ISSUED_LINKS_ATTR = "data-active-issued-links"
UNANSWERED_COUNT_ATTR = "data-unanswered-count"
CANDIDATE_DATE_LIST = "gathering-candidate-date-list"
CANDIDATE_DATE = "gathering-candidate-date"
CANDIDATE_DATE_ID_ATTR = "data-candidate-date-id"
GOING_COUNT_ATTR = "data-going-count"
MAYBE_COUNT_ATTR = "data-maybe-count"
NOT_GOING_COUNT_ATTR = "data-not-going-count"
CONFIRMED_ATTR = "data-confirmed"
TENTATIVE_SELECTED_ATTR = "data-tentative-selected"
ADD_CANDIDATE_DATE_OPEN = "gathering-add-candidate-date-open"
PARTICIPANT_LINK_COPY = "gathering-participant-link-copy"
ISSUED_LINK_URL_ATTR = "data-issued-link-url"
PARTICIPANT_LINK_LIST = "gathering-participant-link-list"
PARTICIPANT_LINK_ITEM = "gathering-participant-link-item"
PARTICIPANT_LINK_ID_ATTR = "data-participant-link-id"
ISSUED_AT_ATTR = "data-issued-at"
HAS_RESPONDED_ATTR = "data-has-responded"
REVOKED_ATTR = "data-revoked"
PARTICIPANT_NAMED_ATTR = "data-participant-named"
PARTICIPANT_LINK_RECOPY = "gathering-participant-link-recopy"
PARTICIPANT_LINK_REVOKE = "gathering-participant-link-revoke"
CONFIRM_DATE_SELECT = "gathering-confirm-date-select"
OPEN_SHOP_PREVIEW = "gathering-open-shop-preview"
OPEN_SHOP_COUNT_ATTR = "data-open-shop-count"
OPEN_SHOP_PREVIEW_ITEM = "gathering-open-shop-preview-item"
OPEN_SHOP_PREVIEW_ITEM_NAME = "gathering-open-shop-preview-item-name"

# organizerGatheringList / organizerGatheringCreate test ids / attributes
# (gathering-scheduling-browser-interface.yaml v0.3, adr/0038).
GATHERING_LIST = "gathering-list"
GATHERING_LIST_ITEM = "gathering-list-item"
GATHERING_ID_ATTR = "data-gathering-id"
GATHERING_CONFIRMED_CANDIDATE_DATE_ATTR = "data-confirmed-candidate-date"
GATHERING_LIST_ITEM_OPEN = "gathering-list-item-open"
GATHERING_LIST_EMPTY = "gathering-list-empty"
GATHERING_CREATE_OPEN = "gathering-create-open"
GATHERING_CREATE_NAME_INPUT = "gathering-create-name-input"
GATHERING_CREATE_SUBMIT = "gathering-create-submit"
GATHERING_ADD_CANDIDATE_DATE_FORM = "gathering-add-candidate-date-form"
GATHERING_ADD_CANDIDATE_DATE_INPUT = "gathering-add-candidate-date-input"
GATHERING_ADD_CANDIDATE_DATE_SUBMIT = "gathering-add-candidate-date-submit"

# candidate-search-browser-interface.yaml v1.7.0's gatheringEntry section
# (adr/0038). TDR-GTH-25 crosses into the candidate-search screen's own entry
# point; this file reads its raw test ids/attributes directly rather than
# importing candidate_search_browser.py, keeping this slice's own module
# boundary (the sibling DSL is not touched).
CANDIDATE_GATHERING_ENTRY = "candidate-gathering-entry"
CANDIDATE_GATHERING_ENTRY_BADGE = "candidate-gathering-entry-badge"
IN_PROGRESS_GATHERING_COUNT_ATTR = "data-in-progress-gathering-count"

# participantAnswer test ids / attributes
PARTICIPANT_HEADER = "gathering-participant-header"
PARTICIPANT_NAME_STATUS = "gathering-participant-name-status"
SCHEDULE_QUESTION = "gathering-schedule-question"
YOUR_RESPONSE_ATTR = "data-your-response"
RESPONSE_OPTION = "gathering-schedule-response-option"
RESPONSE_VALUE_ATTR = "data-response-value"
SCHEDULE_TALLY = "gathering-schedule-tally"
PARTICIPANT_NAME_OPEN = "gathering-participant-name-open"
PARTICIPANT_NAME_INPUT = "gathering-participant-name-input"
PARTICIPANT_NAME_SUBMIT = "gathering-participant-name-submit"
PARTICIPANT_LINK_ERROR = "gathering-participant-link-error"
LINK_ERROR_CODE_ATTR = "data-link-error-code"

# unavailableControls (both namespaces; gathering-scheduling-browser-interface.yaml).
# Mirrors candidate_search_browser.py's ALLOWED_CONTROL_PURPOSES /
# assert_map_has_no_forbidden_surfaces convention for the sibling contract.
GATHERING_CONTROL_PURPOSE_ATTR = "data-gathering-control-purpose"
GATHERING_ALLOWED_PURPOSES = {
    "gathering-add-candidate-date-open",
    "gathering-add-candidate-date-submit",
    "gathering-add-candidate-date-cancel",
    "gathering-participant-link-copy",
    "gathering-candidate-date-tentative-select",
    "gathering-confirm-date-select",
    "gathering-schedule-response-select",
    "gathering-participant-name-open",
    "gathering-participant-name-submit",
    "gathering-participant-link-recopy",
    "gathering-participant-link-revoke",
    # organizerGatheringList / organizerGatheringCreate (adr/0038 addendum,
    # browser-interface v0.3) -- this set previously matched only v0.2's
    # allowedPurposes and did not cover the entry-screen additions, so the
    # cross-cutting check below never scanned these controls.
    "gathering-create-open",
    "gathering-list-item-open",
    "gathering-create-add-candidate-date-row",
    "gathering-create-remove-candidate-date-row",
    "gathering-create-submit",
    "gathering-create-cancel",
}
# unavailableControls.valueEntryControlTestIds (ADR-0039, v0.4): native
# input/textarea value-entry controls exempt from purpose declaration --
# but only because each is traced in browserControlSurface to exactly one
# operational control's requiredOutcome that consumes it. An unregistered
# native input remains subject to the general purpose requirement below
# (this is the point of ADR-0039's design: traceable exemption, not a
# blanket one -- see operationalControlScope in the contract).
GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS = {
    "gathering-create-name-input",
    "gathering-create-candidate-date-input",
    "gathering-add-candidate-date-input",
    "gathering-participant-name-input",
}
GATHERING_FORBIDDEN_PURPOSES = {"manual-ordering", "secondary-condition"}
GATHERING_FORBIDDEN_TEST_IDS = ["candidate-origin-marker", "candidate-map", "private-search-origin"]
GATHERING_FORM_CONTROL_SELECTOR = ", ".join(
    [
        "select",
        "input:not([type='hidden'])",
        "textarea",
        "button",
        "[role='checkbox']",
        "[role='radio']",
        "[role='range']",
        "[role='combobox']",
        "[role='listbox']",
        "[role='slider']",
        "[role='spinbutton']",
    ]
)

# disclosureObservations (both namespaces). Reuses the exact canary strings
# candidate-search-browser-interface.yaml/authentication-browser-interface.yaml
# already define -- this contract's own profiles.localAcceptance.
# syntheticDisclosureCanaries note: "a single shared set of forbidden strings
# applies across every TDR-* browser contract".
GATHERING_PRIVATE_ORIGIN_CANARY = "synthetic-private-origin-never-disclose.invalid"
GATHERING_PROVIDER_INTERNALS_CANARY = "synthetic-provider-internals-never-disclose"
GATHERING_DISCLOSURE_FORBIDDEN_TEST_IDS = [
    "private-search-origin",
    "candidate-origin-marker",
    "candidate-map-marker",
]

# test-support-api.yaml 1.5.0's GATHERING_OPEN_SHOP_WEEKDAY_MATCH mode (adr/0037 decision 3):
# exact known openShopCount per weekday (Python's date.weekday(): Monday=0 ... Sunday=6).
OPEN_SHOP_COUNT_BY_WEEKDAY = {0: 5, 1: 5, 2: 4, 3: 6, 4: 6, 5: 6, 6: 5}


def next_weekday_iso(weekday: int, hour: int = 12) -> str:
    """The next future occurrence (never "today") of ``weekday`` as an RFC3339 string,
    for CandidateDateInput.startAt.
    """
    now = datetime.now(UTC)
    days_ahead = (weekday - now.weekday()) % 7 or 7
    target = (now + timedelta(days=days_ahead)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return target.isoformat()


def days_from_now_iso(days: int, hour: int = 12) -> str:
    target = (datetime.now(UTC) + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return target.isoformat()


class GatheringSchedulingBrowserDsl:
    def __init__(self, assertions: SimpleTestCase, page: Page, base_url: str) -> None:
        self.assertions = assertions
        self.page = page
        self.base_url = base_url.rstrip("/")
        self._auth_seam = AuthenticationBrowserDsl(assertions, base_url)
        self.support = HttpBrowser(base_url)
        self._csrf_token: str | None = None
        self.gathering: dict | None = None
        self.gathering_id: str | None = None
        self._created_gatherings: list[dict] = []
        self._created_candidate_date_isos: list[str] = []
        self._candidate_date_id_by_start_at: dict[str, str] = {}
        self._prepared_title: str | None = None
        self._prepared_candidate_date_isos: list[str] | None = None
        self._issued_order: list[dict[str, str]] = []
        self._current_open_shop_preview: CapturedApiResponse | None = None

    # Given seams (test-support-api.yaml) -----------------------------------

    def reset_authentication_state(self) -> None:
        self._auth_seam.reset_authentication_state()

    def enable_organizer(self, account_ref: str, identifier: str, password: str) -> None:
        self._auth_seam.set_active_organizer(account_ref, identifier, password)

    def reset_gathering_scheduling_state(self) -> None:
        response = self.support.request("DELETE", "/test-support/gathering-scheduling-state")
        assert_no_content(self.assertions, response, "gathering-scheduling state reset")

    def reset_candidate_state(self) -> None:
        response = self.support.request("DELETE", "/test-support/candidate-proposals/state")
        assert_no_content(self.assertions, response, "candidate-proposal state reset")

    def set_gathering_open_shop_population(self) -> None:
        """adr/0037 decision 3: TDR-GTH-08/09 share candidate-search's own population
        seam rather than a dedicated gathering endpoint.
        """
        response = self.support.request(
            "PUT",
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "GATHERING_OPEN_SHOP_WEEKDAY_MATCH"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, "GATHERING_OPEN_SHOP_WEEKDAY_MATCH state set")

    def seed_expired_participant_link(self, link: dict[str, str]) -> None:
        response = self.support.request(
            "POST",
            "/test-support/gathering-scheduling/participant-links/expire",
            data=json.dumps({"token": link["token"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, "seedExpiredParticipantLink")

    def seed_rate_limited_participant_link(self, link: dict[str, str]) -> None:
        response = self.support.request(
            "POST",
            "/test-support/gathering-scheduling/participant-links/rate-limit",
            data=json.dumps({"token": link["token"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, "seedRateLimitedParticipantLink")

    # Sign-in (shared root entry point, same as candidate_search_browser.py) -

    def sign_in(self, identifier: str, password: str) -> None:
        self.page.goto(f"{self.base_url}/")
        by_test_id(self.page, "auth-login-identifier").fill(identifier)
        by_test_id(self.page, "auth-password").fill(password)
        by_test_id(self.page, "auth-sign-in-submit").click()
        assert_present(self.assertions, self.page, "authenticated-application-shell")
        self.page.wait_for_load_state("networkidle")
        self._csrf_token = csrf_token(self.page)

    # Direct public-API calls (organizer Given-state, TDR-GTH-01/10/13/20) ---

    def _api(
        self, method: str, path: str, json_body: dict | None = None, *, csrf: bool = False
    ) -> CapturedApiResponse:
        headers: dict[str, str] = {}
        data: bytes | None = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(json_body).encode("utf-8")
        if csrf:
            headers["X-CSRFToken"] = require(
                self._csrf_token, "organizer must sign in before a CSRF-protected request"
            )
        response = self.page.context.request.fetch(
            f"{self.base_url}{path}", method=method, headers=headers, data=data
        )
        return build_captured_response(response)

    def _assert_api_ok(
        self, response: CapturedApiResponse, expected_status: int, context: str
    ) -> None:
        self.assertions.assertEqual(response.status, expected_status, f"{context}: {response.body}")

    def _set_gathering(self, payload: dict) -> None:
        self.gathering = payload
        self.gathering_id = payload["id"]
        for candidate_date in payload["candidateDates"]:
            self._candidate_date_id_by_start_at[candidate_date["startAt"]] = candidate_date["id"]

    def candidate_date_id_at(self, index: int) -> str:
        iso = self._created_candidate_date_isos[index]
        return self._candidate_date_id_by_start_at[iso]

    # createGathering ---------------------------------------------------

    def prepare_new_gathering(self, title: str, candidate_date_isos: list[str]) -> None:
        """Given: 幹事が会の名前と2つ以上の候補日を用意している (TDR-GTH-01).

        Purely local state -- createGathering itself is the scenario's own
        When, not this Given.
        """
        self._prepared_title = title
        self._prepared_candidate_date_isos = list(candidate_date_isos)

    def create_prepared_gathering(self) -> None:
        """When: 幹事が会をつくる (TDR-GTH-01). browser-interface.yaml's own
        notVerifiedHere marks this scenario API/boundary-level acceptance --
        no creation screen is approved yet (Organizer.dc.html shows only the
        post-creation dashboard) -- so this calls createGathering directly.
        """
        title = require(self._prepared_title, "no gathering was prepared")
        dates = require(self._prepared_candidate_date_isos, "no candidate dates were prepared")
        self._create_gathering(title, dates)  # type: ignore[arg-type]

    def given_scheduling_gathering(self, title: str, candidate_date_isos: list[str]) -> None:
        """Given-state builder for every other TDR-GTH scenario needing an
        already-existing SCHEDULING-phase gathering (adr/0037 decision 1:
        public-API Given construction, since no approved creation screen
        exists to drive through the browser).
        """
        self._create_gathering(title, candidate_date_isos)

    def _create_gathering(self, title: str, candidate_date_isos: list[str]) -> None:
        response = self._api(
            "POST",
            "/gatherings",
            {"title": title, "candidateDates": [{"startAt": iso} for iso in candidate_date_isos]},
            csrf=True,
        )
        self._assert_api_ok(response, 201, "createGathering")
        self._created_candidate_date_isos.extend(candidate_date_isos)
        self._set_gathering(response.payload)
        self._created_gatherings.append(response.payload)

    def given_multiple_scheduling_gatherings(
        self, specs: list[tuple[str, list[str]]]
    ) -> list[dict]:
        """Given-state builder for TDR-GTH-21/25 ("幹事が複数の会を持っている" /
        "幹事が進行中の会をいくつか持っている"): creates each gathering in turn
        through the same public-API path given_scheduling_gathering already
        uses (adr/0037 decision 1), returning each payload in creation order.
        """
        result: list[dict] = []
        for title, candidate_date_isos in specs:
            self.given_scheduling_gathering(title, candidate_date_isos)
            result.append(self._created_gatherings[-1])
        return result

    def confirm_candidate_date_via_api(self, gathering_id: str, candidate_date_id: str) -> dict:
        """Given-state construction only (adr/0037 decision 1): TDR-GTH-21 needs
        at least one already-confirmed gathering to exercise gathering-list-
        item's data-confirmed-candidate-date presence branch. The confirm
        action's own behavior is already covered by TDR-GTH-10/11's own
        tests, so this reaches SELECTING_SHOP directly through the public API
        rather than through organizerDashboard's confirm control.
        """
        response = self._api(
            "POST",
            f"/gatherings/{gathering_id}/confirm-date",
            {"candidateDateId": candidate_date_id},
            csrf=True,
        )
        self._assert_api_ok(response, 200, "confirmCandidateDate (given-state)")
        return response.payload

    # Then: TDR-GTH-01 -----------------------------------------------------

    def assert_gathering_created_in_scheduling_phase(self) -> None:
        gathering = require(self.gathering, "no gathering was created")
        self.assertions.assertEqual(gathering["phase"], "SCHEDULING")  # type: ignore[index]

    def assert_prepared_candidate_dates_all_registered(self) -> None:
        gathering = require(self.gathering, "no gathering was created")
        registered = {date["startAt"] for date in gathering["candidateDates"]}  # type: ignore[index]
        expected = set(
            require(self._prepared_candidate_date_isos, "no candidate dates were prepared")
        )
        self.assertions.assertEqual(registered, expected)

    def assert_no_candidate_date_is_confirmed_on_gathering(self) -> None:
        gathering = require(self.gathering, "no gathering was created")
        self.assertions.assertIsNone(gathering["confirmedCandidateDateId"])  # type: ignore[index]

    # Organizer dashboard navigation and reads ------------------------------

    def open_organizer_dashboard(self) -> None:
        self.page.goto(f"{self.base_url}/gatherings/{self.gathering_id}/")
        wait_for_at_least_one(self.page, GATHERING_PHASE_INDICATOR)

    def _candidate_date_locator(self, candidate_date_id: str) -> Locator:
        return self.page.locator(
            f'[data-testid="{CANDIDATE_DATE}"][{CANDIDATE_DATE_ID_ATTR}="{candidate_date_id}"]'
        )

    def _read_gathering_phase_from_dom(self) -> str:
        node = assert_present(self.assertions, self.page, GATHERING_PHASE_INDICATOR)
        return node.get_attribute(GATHERING_PHASE_ATTR)

    def _read_candidate_dates(self) -> list[dict[str, object]]:
        nodes = wait_for_at_least_one(self.page, CANDIDATE_DATE)
        result = []
        for index in range(nodes.count()):
            node = nodes.nth(index)
            result.append(
                {
                    "id": node.get_attribute(CANDIDATE_DATE_ID_ATTR),
                    "going": int(node.get_attribute(GOING_COUNT_ATTR)),
                    "maybe": int(node.get_attribute(MAYBE_COUNT_ATTR)),
                    "notGoing": int(node.get_attribute(NOT_GOING_COUNT_ATTR)),
                    "confirmed": node.get_attribute(CONFIRMED_ATTR) == "true",
                }
            )
        return result

    def _read_responded_summary(self) -> dict[str, int]:
        node = assert_present(self.assertions, self.page, RESPONDED_SUMMARY)
        return {
            "respondedCount": int(node.get_attribute(RESPONDED_COUNT_ATTR)),
            "anonymousRespondedCount": int(node.get_attribute(ANONYMOUS_RESPONDED_COUNT_ATTR)),
        }

    def _read_unanswered_summary(self) -> dict[str, int]:
        node = assert_present(self.assertions, self.page, UNANSWERED_SUMMARY)
        return {
            "totalIssuedLinks": int(node.get_attribute(TOTAL_ISSUED_LINKS_ATTR)),
            "revokedLinks": int(node.get_attribute(REVOKED_LINKS_ATTR)),
            "activeIssuedLinks": int(node.get_attribute(ACTIVE_ISSUED_LINKS_ATTR)),
            "unansweredCount": int(node.get_attribute(UNANSWERED_COUNT_ATTR)),
        }

    def _read_participant_link_items(self) -> list[dict[str, object]]:
        nodes = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ITEM)
        result = []
        for index in range(nodes.count()):
            node = nodes.nth(index)
            result.append(
                {
                    "id": node.get_attribute(PARTICIPANT_LINK_ID_ATTR),
                    "issuedAt": node.get_attribute(ISSUED_AT_ATTR),
                    "hasResponded": node.get_attribute(HAS_RESPONDED_ATTR) == "true",
                    "revoked": node.get_attribute(REVOKED_ATTR) == "true",
                    "named": node.get_attribute(PARTICIPANT_NAMED_ATTR) == "true",
                }
            )
        return result

    # Then: organizer dashboard summaries and candidate-date list ----------

    def assert_gathering_phase(self, expected_phase: str) -> None:
        self.assertions.assertEqual(self._read_gathering_phase_from_dom(), expected_phase)

    def assert_no_candidate_date_confirmed(self) -> None:
        dates = self._read_candidate_dates()
        self.assertions.assertTrue(all(not date["confirmed"] for date in dates))

    def assert_candidate_date_list_is_ordered_by_going_count_descending(self) -> None:
        going_counts = [date["going"] for date in self._read_candidate_dates()]
        self.assertions.assertEqual(going_counts, sorted(going_counts, reverse=True))

    def assert_candidate_date_tally(
        self, candidate_date_id: str, *, going: int, maybe: int, not_going: int
    ) -> None:
        dates = {date["id"]: date for date in self._read_candidate_dates()}
        date = require(
            dates.get(candidate_date_id), f"candidate date {candidate_date_id} not shown"
        )
        self.assertions.assertEqual(date["going"], going)  # type: ignore[index]
        self.assertions.assertEqual(date["maybe"], maybe)  # type: ignore[index]
        self.assertions.assertEqual(date["notGoing"], not_going)  # type: ignore[index]

    def assert_responded_summary(self, *, responded: int, anonymous: int) -> None:
        summary = self._read_responded_summary()
        self.assertions.assertEqual(summary["respondedCount"], responded)
        self.assertions.assertEqual(summary["anonymousRespondedCount"], anonymous)

    def assert_unanswered_summary(
        self, *, total_issued: int, revoked: int, active_issued: int, unanswered: int
    ) -> None:
        summary = self._read_unanswered_summary()
        self.assertions.assertEqual(summary["totalIssuedLinks"], total_issued)
        self.assertions.assertEqual(summary["revokedLinks"], revoked)
        self.assertions.assertEqual(summary["activeIssuedLinks"], active_issued)
        self.assertions.assertEqual(summary["unansweredCount"], unanswered)

    def capture_unanswered_summary(self) -> dict[str, int]:
        return self._read_unanswered_summary()

    def assert_unanswered_summary_equals(self, expected: dict[str, int]) -> None:
        self.assertions.assertEqual(self._read_unanswered_summary(), expected)

    def assert_unanswered_summary_reflects_one_revocation(self, before: dict[str, int]) -> None:
        """D2 amendment (ADR-0036 decision 7, TDR-GTH-18): revoking one unanswered
        link must decrement the denominator by exactly 1, computed as
        activeParticipantLinkCount - respondedParticipantCount -- never from
        data-total-issued-links directly (that would reintroduce the
        pre-amendment bug of still counting a revoked link as outstanding).
        """
        after = self._read_unanswered_summary()
        self.assertions.assertEqual(after["totalIssuedLinks"], before["totalIssuedLinks"])
        self.assertions.assertEqual(after["revokedLinks"], before["revokedLinks"] + 1)
        self.assertions.assertEqual(after["activeIssuedLinks"], before["activeIssuedLinks"] - 1)
        self.assertions.assertEqual(after["unansweredCount"], before["unansweredCount"] - 1)
        responded = self._read_responded_summary()["respondedCount"]
        self.assertions.assertEqual(
            after["unansweredCount"], after["activeIssuedLinks"] - responded
        )

    # Add-candidate-date (organizer, inline form) ----------------------------
    # gathering-scheduling-browser-interface.yaml v0.3 (adr/0038) defines
    # gathering-add-candidate-date-form as the surface addCandidateDateOpen
    # reveals, resolving reviewer audit Major#1 (the positive outcome of
    # addCandidateDateOpen.requiredOutcome was previously undefined and thus
    # unverifiable from the browser). TDR-GTH-02 is rewritten below to drive
    # this form end-to-end instead of the prior two-stage (no-side-effect
    # click + direct API POST) construction; TDR-GTH-24 reuses the same
    # submit path for its duplicate-rejection branch.

    def _fill_candidate_date_time_input(self, base_test_id: str, iso: str) -> None:
        """Fills a candidate-date input whose exact shape this contract leaves
        open (one merged date-time input, or a date input plus a sibling
        `-time-input`-suffixed time input -- organizerGatheringCreate.
        candidateDateRow.note / addCandidateDateForm.note, adr/0038). Detects
        the two-input shape by the unambiguous suffixed test id; otherwise
        treats the base input as accepting the full merged value.
        """
        dt = datetime.fromisoformat(iso)
        time_input = self.page.locator(f'[data-testid="{base_test_id}-time-input"]')
        base_input = by_test_id(self.page, base_test_id)
        if time_input.count() > 0:
            base_input.fill(dt.strftime("%Y-%m-%d"))
            time_input.fill(dt.strftime("%H:%M"))
        else:
            base_input.fill(dt.strftime("%Y-%m-%dT%H:%M"))

    def open_add_candidate_date_form(self) -> None:
        """addCandidateDateOpen.requiredOutcome: reveals
        gathering-add-candidate-date-form inline within
        gathering-candidate-date-list, without itself mutating gathering
        state (TDR-GTH-02's Given/first Then: opening the entry point alone
        must not add a candidate date or change the phase).
        """
        before_phase = self._read_gathering_phase_from_dom()
        before_dates = self._read_candidate_dates()
        by_test_id(self.page, ADD_CANDIDATE_DATE_OPEN).click()
        assert_present(self.assertions, self.page, GATHERING_ADD_CANDIDATE_DATE_FORM)
        self.assertions.assertEqual(self._read_gathering_phase_from_dom(), before_phase)
        self.assertions.assertEqual(self._read_candidate_dates(), before_dates)

    def submit_add_candidate_date_form(self, candidate_date_iso: str) -> CapturedApiResponse:
        self._fill_candidate_date_time_input(GATHERING_ADD_CANDIDATE_DATE_INPUT, candidate_date_iso)
        response = self._capture_gathering_response(
            "candidate-dates",
            lambda: by_test_id(self.page, GATHERING_ADD_CANDIDATE_DATE_SUBMIT).click(),
        )
        if response.status == 201:
            self._created_candidate_date_isos.append(candidate_date_iso)
            self._set_gathering(response.payload)
        return response

    def candidate_dates_snapshot(self) -> list[dict[str, object]]:
        return self._read_candidate_dates()

    def assert_candidate_date_added_via_inline_form(
        self,
        response: CapturedApiResponse,
        before_dates: list[dict[str, object]],
        expected_phase: str,
    ) -> None:
        """addCandidateDateForm.submit.requiredOutcome's success branch
        (TDR-GTH-02): exactly one new gathering-candidate-date appears, phase
        is unchanged, and the form remains present ready for another entry
        (human decision 2026-09-01, AddDate.dc.html 案A: "足したあとフォームは
        閉じない"). Identifies "the new one" as a before/after id-set diff
        (caller supplies a pre-submit candidate_dates_snapshot()) rather than
        looking it up by the submitted startAt string -- deliberately
        avoiding the same class of fragility a prior audit flagged for
        candidate_date_id_at (byte-identity between what a client sends and
        what the server echoes back is not guaranteed, and here the value
        additionally round-trips through a real browser date-input widget
        before ever reaching the API).
        """
        self.assertions.assertEqual(response.status, 201)
        before_ids = {date["id"] for date in before_dates}
        after_ids = {date["id"] for date in self._read_candidate_dates()}
        new_ids = after_ids - before_ids
        self.assertions.assertEqual(
            len(new_ids), 1, f"expected exactly one new candidate date, got {new_ids}"
        )
        self.assertions.assertEqual(self._read_gathering_phase_from_dom(), expected_phase)
        assert_present(self.assertions, self.page, GATHERING_ADD_CANDIDATE_DATE_FORM)

    def assert_duplicate_candidate_date_rejected_by_inline_form(
        self,
        response: CapturedApiResponse,
        candidate_date_iso: str,
        before_dates: list[dict[str, object]],
    ) -> None:
        """TDR-GTH-24 / addCandidateDateForm.submit.requiredOutcome's
        DUPLICATE_CANDIDATE_DATE branch: no candidate date is added (dates
        unchanged from the pre-submit snapshot), the form stays present, and
        the entered value remains intact (adr/0038).
        """
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "DUPLICATE_CANDIDATE_DATE")
        self.assertions.assertEqual(self._read_candidate_dates(), before_dates)
        assert_present(self.assertions, self.page, GATHERING_ADD_CANDIDATE_DATE_FORM)
        dt = datetime.fromisoformat(candidate_date_iso)
        time_input = self.page.locator(
            f'[data-testid="{GATHERING_ADD_CANDIDATE_DATE_INPUT}-time-input"]'
        )
        base_input = by_test_id(self.page, GATHERING_ADD_CANDIDATE_DATE_INPUT)
        if time_input.count() > 0:
            self.assertions.assertEqual(base_input.input_value(), dt.strftime("%Y-%m-%d"))
            self.assertions.assertEqual(time_input.input_value(), dt.strftime("%H:%M"))
        else:
            self.assertions.assertEqual(base_input.input_value(), dt.strftime("%Y-%m-%dT%H:%M"))

    # organizerGatheringList (TDR-GTH-21/22, adr/0038) -----------------------

    def open_organizer_gathering_list(self) -> None:
        self.page.goto(f"{self.base_url}/gatherings/")
        wait_for_at_least_one(self.page, GATHERING_LIST)

    def _read_gathering_list_items(self) -> list[dict[str, object]]:
        nodes = self.page.locator(f'[data-testid="{GATHERING_LIST_ITEM}"]')
        result = []
        for index in range(nodes.count()):
            node = nodes.nth(index)
            result.append(
                {
                    "id": node.get_attribute(GATHERING_ID_ATTR),
                    "phase": node.get_attribute(GATHERING_PHASE_ATTR),
                    "confirmedCandidateDate": node.get_attribute(
                        GATHERING_CONFIRMED_CANDIDATE_DATE_ATTR
                    ),
                }
            )
        return result

    def assert_gathering_list_matches(self, expected: list[dict[str, object]]) -> None:
        """expected: DOM-order list of {"id", "phase", "confirmedCandidateDate"}
        (createdAt descending, 新しい順,
        organizerGatheringList.list.orderingInvariant). This does not assert
        each gathering's title/name: the contract's gathering-list-item
        attributes (data-gathering-id/-phase/-confirmed-candidate-date/
        -responded-count/-active-issued-links) define no machine-observable
        name field, so the .feature's "名前...が示される" clause cannot be
        verified here (see this slice's tester report).
        """
        wait_for_at_least_one(self.page, GATHERING_LIST_ITEM)
        items = self._read_gathering_list_items()
        self.assertions.assertEqual(len(items), len(expected))
        for actual, wanted in zip(items, expected, strict=True):
            self.assertions.assertEqual(actual["id"], wanted["id"])
            self.assertions.assertEqual(actual["phase"], wanted["phase"])
            self.assertions.assertEqual(
                actual["confirmedCandidateDate"], wanted["confirmedCandidateDate"]
            )

    def open_gathering_from_list(self, gathering_id: str) -> None:
        item = self.page.locator(
            f'[data-testid="{GATHERING_LIST_ITEM}"][{GATHERING_ID_ATTR}="{gathering_id}"]'
        )
        by_test_id(item, GATHERING_LIST_ITEM_OPEN).click()
        wait_for_at_least_one(self.page, GATHERING_PHASE_INDICATOR)

    def assert_dashboard_is_shown_for(self, gathering_id: str, expected_phase: str) -> None:
        """TDR-GTH-21's Then ("その会のダッシュボードが表示される") requires the
        *specific* gathering's dashboard, not merely *a* dashboard -- checked
        via the URL's gatheringId (browserEntry.organizerDashboard.
        startUrlTemplate) in addition to the rendered phase.
        """
        self.assertions.assertIn(gathering_id, self.page.url)
        self.assertions.assertEqual(self._read_gathering_phase_from_dom(), expected_phase)

    def assert_gathering_list_is_empty(self) -> None:
        assert_present(self.assertions, self.page, GATHERING_LIST_EMPTY)
        assert_absent(self.assertions, self.page, GATHERING_LIST_ITEM)

    def activate_create_open_from_empty_state(self) -> None:
        """TDR-GTH-22's "その案内から会をつくる操作を選ぶ": scoped to the
        createOpen instance *inside* gathering-list-empty
        (organizerGatheringList.empty.containsCreateOpen), distinct from the
        persistent header instance createOpen.cardinality also guarantees.
        """
        empty_state = assert_present(self.assertions, self.page, GATHERING_LIST_EMPTY)
        create_open_in_empty_state = empty_state.locator(f'[data-testid="{GATHERING_CREATE_OPEN}"]')
        expect(create_open_in_empty_state).to_have_count(1)
        create_open_in_empty_state.click()

    def assert_gathering_create_screen_is_shown(self) -> None:
        wait_for_at_least_one(self.page, GATHERING_CREATE_NAME_INPUT)

    # organizerGatheringCreate (TDR-GTH-23, adr/0038) ------------------------

    def open_gathering_create_from_header(self) -> None:
        """TDR-GTH-23's entry route: the always-present header instance of
        createOpen (createOpen.cardinality), distinct from TDR-GTH-22's
        empty-state instance.
        """
        self.open_organizer_gathering_list()
        by_test_id(self.page, GATHERING_CREATE_OPEN).first.click()
        self.assert_gathering_create_screen_is_shown()

    def fill_gathering_create_name(self, title: str) -> None:
        by_test_id(self.page, GATHERING_CREATE_NAME_INPUT).fill(title)

    def assert_gathering_create_submit_is_disabled(self) -> None:
        expect(by_test_id(self.page, GATHERING_CREATE_SUBMIT)).to_be_disabled()

    def attempt_create_gathering_via_api_with_no_candidate_dates(
        self, title: str
    ) -> CapturedApiResponse:
        """TDR-GTH-23's server-side boundary check, bypassing the disabled
        submit control the same way TDR-GTH-20 bypasses a disabled UI control
        to prove the server itself enforces the rule (CreateGatheringRequest.
        candidateDates minItems: 1, adr/0035 decision 1 / D10).
        """
        return self._api("POST", "/gatherings", {"title": title, "candidateDates": []}, csrf=True)

    def assert_create_rejected_because_no_candidate_dates(
        self, response: CapturedApiResponse
    ) -> None:
        """No ProblemResponse.code names this specific validation failure
        (gathering-scheduling-api.yaml's enum has no
        CANDIDATE_DATE_REQUIRED-shaped value); REQUEST_REJECTED (400) is the
        contract's only defined response shape for a rejected createGathering
        request that is not GATHERING_NOT_FOUND/DUPLICATE_CANDIDATE_DATE, so
        this is the most specific check available.
        """
        self.assertions.assertEqual(response.status, 400)
        self.assertions.assertEqual(response.payload["code"], "REQUEST_REJECTED")

    def assert_no_gathering_exists_with_title(self, title: str) -> None:
        response = self._api("GET", "/gatherings")
        self._assert_api_ok(response, 200, "listGatherings")
        titles = [gathering["title"] for gathering in response.payload["gatherings"]]
        self.assertions.assertNotIn(title, titles)

    # candidate-search screen's gatheringEntry (TDR-GTH-25,
    # candidate-search-browser-interface.yaml v1.7.0, adr/0038) ------------

    def set_lunch_candidate_screen_available(self) -> None:
        """TDR-GTH-25 needs the candidate-search screen itself to render
        successfully to reach candidate-gathering-entry
        (authenticatedInitialOutcome.present). Uses the same test-support-
        api.yaml seam set_gathering_open_shop_population already uses,
        mirroring candidate_search_browser.py's own NORMAL_WITH_WEIGHTED_
        SAMPLING Given without importing that sibling module.
        """
        response = self.support.request(
            "PUT",
            "/test-support/candidate-proposals/state",
            data=json.dumps({"mode": "NORMAL_WITH_WEIGHTED_SAMPLING"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, "NORMAL_WITH_WEIGHTED_SAMPLING state set")

    def open_lunch_candidate_screen(self) -> None:
        self.page.goto(f"{self.base_url}/")
        wait_for_at_least_one(self.page, CANDIDATE_GATHERING_ENTRY)

    def assert_in_progress_gathering_count_badge(self, expected_count: int) -> None:
        if expected_count > 0:
            badge = wait_for_at_least_one(self.page, CANDIDATE_GATHERING_ENTRY_BADGE)
            self.assertions.assertEqual(
                badge.first.get_attribute(IN_PROGRESS_GATHERING_COUNT_ATTR), str(expected_count)
            )
        else:
            assert_absent(self.assertions, self.page, CANDIDATE_GATHERING_ENTRY_BADGE)

    def open_gathering_entry_from_candidate_screen(self) -> None:
        by_test_id(self.page, CANDIDATE_GATHERING_ENTRY).click()

    def assert_gathering_list_screen_is_shown(self) -> None:
        wait_for_at_least_one(self.page, GATHERING_LIST)

    # Issue / list / recopy / revoke participant links (organizer UI) ------

    def _token_from_url(self, url: str) -> str:
        match = re.search(r"/participant-links/([^/]+)/?$", url)
        return require(match, f"issued link url has unexpected shape: {url}").group(1)  # type: ignore[union-attr]

    def issue_participant_link_from_dashboard(self) -> dict[str, str]:
        """1クリック=1本 (D8, ADR-0036決定4). participantLinkCopy.requiredOutcome."""
        before = self._read_unanswered_summary()
        button = assert_present(self.assertions, self.page, PARTICIPANT_LINK_COPY)
        button.click()
        expect(button).to_have_attribute(ISSUED_LINK_URL_ATTR, re.compile(r".+"))
        url = button.get_attribute(ISSUED_LINK_URL_ATTR)
        after = self._read_unanswered_summary()
        self.assertions.assertEqual(after["totalIssuedLinks"], before["totalIssuedLinks"] + 1)
        self.assertions.assertEqual(after["activeIssuedLinks"], before["activeIssuedLinks"] + 1)
        issued = {"token": self._token_from_url(url), "url": url}
        self._issued_order.append(issued)
        return issued

    def issue_n_participant_links_from_dashboard(self, count: int) -> list[dict[str, str]]:
        return [self.issue_participant_link_from_dashboard() for _ in range(count)]

    def issue_participant_link_via_api(self) -> dict[str, str]:
        """Given-state builder for scenarios not about the issuing UI itself."""
        response = self._api(
            "POST", f"/gatherings/{self.gathering_id}/participant-links", {"count": 1}, csrf=True
        )
        self._assert_api_ok(response, 201, "issueParticipantLinks")
        issued_links = response.payload["issuedLinks"]
        self.assertions.assertEqual(len(issued_links), 1)
        link = issued_links[0]
        issued = {"token": self._token_from_url(link["url"]), "url": link["url"]}
        self._issued_order.append(issued)
        return issued

    def assert_issued_links_are_distinct(self, links: list[dict[str, str]]) -> None:
        tokens = [link["token"] for link in links]
        urls = [link["url"] for link in links]
        self.assertions.assertEqual(len(tokens), len(set(tokens)))
        self.assertions.assertEqual(len(urls), len(set(urls)))
        for token, url in zip(tokens, urls, strict=True):
            self.assertions.assertTrue(token)
            self.assertions.assertIn(token, url)

    def assert_participant_link_list_matches(self, expected: list[dict[str, object]]) -> None:
        """expected: issuance-order list of {"hasResponded": bool, "named": bool}
        (optionally "revoked"). TDR-GTH-16 only requires 名無しを含む
        distinguishability, not exact display-name text (item.requirement note).
        """
        items = self._read_participant_link_items()
        self.assertions.assertEqual(len(items), len(expected))
        issued_ats = [item["issuedAt"] for item in items]
        self.assertions.assertEqual(issued_ats, sorted(issued_ats))
        for actual, wanted in zip(items, expected, strict=True):
            self.assertions.assertEqual(actual["hasResponded"], wanted["hasResponded"])
            self.assertions.assertEqual(actual["named"], wanted["named"])
            if "revoked" in wanted:
                self.assertions.assertEqual(actual["revoked"], wanted["revoked"])

    def recopy_participant_link_at(self, index: int) -> str:
        item = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ITEM).nth(index)
        recopy = by_test_id(item, PARTICIPANT_LINK_RECOPY)
        expect(recopy).to_be_enabled()
        recopy.click()
        expect(recopy).to_have_attribute(ISSUED_LINK_URL_ATTR, re.compile(r".+"))
        return recopy.get_attribute(ISSUED_LINK_URL_ATTR)

    def revoke_participant_link_at(self, index: int) -> None:
        item = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ITEM).nth(index)
        revoke = by_test_id(item, PARTICIPANT_LINK_REVOKE)
        expect(revoke).to_be_enabled()
        revoke.click()
        expect(item).to_have_attribute(REVOKED_ATTR, "true")

    def assert_revoke_control_disabled_at(self, index: int) -> None:
        item = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ITEM).nth(index)
        expect(by_test_id(item, PARTICIPANT_LINK_REVOKE)).to_be_disabled()

    def attempt_revoke_participant_link_via_api(self, index: int) -> CapturedApiResponse:
        """TDR-GTH-20's own contract note: the server must reject this even though
        this contract's disabledState should make it unreachable through the
        control -- so this bypasses the disabled UI control deliberately.
        """
        link_id = self._read_participant_link_items()[index]["id"]
        return self._api(
            "POST",
            f"/gatherings/{self.gathering_id}/participant-links/{link_id}/revoke",
            None,
            csrf=True,
        )

    def assert_revoke_rejected_because_already_answered(
        self, response: CapturedApiResponse
    ) -> None:
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "PARTICIPANT_LINK_ALREADY_ANSWERED")

    def assert_recopied_url_matches_original(self, recopied_url: str, original_url: str) -> None:
        self.assertions.assertEqual(recopied_url, original_url)

    # Tentative selection / preview / confirm (organizer UI) ----------------

    def _capture_gathering_response(
        self, url_fragment: str, trigger: Callable[[], None]
    ) -> CapturedApiResponse:
        def predicate(response: Response) -> bool:
            return url_fragment in response.url

        with self.page.expect_response(predicate) as info:
            trigger()
        return build_captured_response(info.value)

    def tentatively_select_candidate_date(self, candidate_date_id: str) -> None:
        node = self._candidate_date_locator(candidate_date_id)
        self._current_open_shop_preview = self._capture_gathering_response(
            "open-shop-preview", lambda: node.click()
        )
        expect(node).to_have_attribute(TENTATIVE_SELECTED_ATTR, "true")

    def assert_open_shop_preview_shows_expected_count_and_order(
        self, expected_open_shop_count: int
    ) -> None:
        response = require(self._current_open_shop_preview, "no open-shop preview was captured")
        self.assertions.assertEqual(response.status, 200)  # type: ignore[union-attr]
        payload = response.payload  # type: ignore[union-attr]
        self.assertions.assertEqual(payload["openShopCount"], expected_open_shop_count)
        preview = assert_present(self.assertions, self.page, OPEN_SHOP_PREVIEW)
        self.assertions.assertEqual(
            preview.get_attribute(OPEN_SHOP_COUNT_ATTR), str(payload["openShopCount"])
        )
        expected_names = [shop["name"] for shop in payload["previewShops"]]
        if expected_names:
            items = wait_for_at_least_one(self.page, OPEN_SHOP_PREVIEW_ITEM)
        else:
            items = by_test_id(self.page, OPEN_SHOP_PREVIEW_ITEM)
        dom_names = [
            by_test_id(items.nth(index), OPEN_SHOP_PREVIEW_ITEM_NAME).inner_text().strip()
            for index in range(items.count())
        ]
        self.assertions.assertEqual(dom_names, expected_names)

    def confirm_tentatively_selected_date(self) -> None:
        by_test_id(self.page, CONFIRM_DATE_SELECT).click()
        expect(by_test_id(self.page, GATHERING_PHASE_INDICATOR)).to_have_attribute(
            GATHERING_PHASE_ATTR, "SELECTING_SHOP"
        )

    def attempt_confirm_candidate_date_via_api(self, candidate_date_id: str) -> CapturedApiResponse:
        return self._api(
            "POST",
            f"/gatherings/{self.gathering_id}/confirm-date",
            {"candidateDateId": candidate_date_id},
            csrf=True,
        )

    def assert_confirm_rejected_because_not_in_scheduling_phase(
        self, response: CapturedApiResponse
    ) -> None:
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "GATHERING_NOT_IN_SCHEDULING_PHASE")

    # Participant browser actions --------------------------------------------

    def open_participant_link(self, link: dict[str, str]) -> None:
        self.page.goto(f"{self.base_url}/participant-links/{link['token']}/")

    def _schedule_question_locator(self, candidate_date_id: str) -> Locator:
        return self.page.locator(
            f'[data-testid="{SCHEDULE_QUESTION}"][{CANDIDATE_DATE_ID_ATTR}="{candidate_date_id}"]'
        )

    def answer_schedule_question(self, candidate_date_id: str, status: str) -> None:
        question = self._schedule_question_locator(candidate_date_id)
        expect(question).to_be_attached()
        option = question.locator(
            f'[data-testid="{RESPONSE_OPTION}"][{RESPONSE_VALUE_ATTR}="{status}"]'
        )
        option.click()
        expect(question).to_have_attribute(YOUR_RESPONSE_ATTR, status)

    def answer_first_schedule_question(self, status: str) -> str:
        question = wait_for_at_least_one(self.page, SCHEDULE_QUESTION).first
        candidate_date_id = question.get_attribute(CANDIDATE_DATE_ID_ATTR)
        self.answer_schedule_question(candidate_date_id, status)
        return candidate_date_id

    def given_participant_link_with_one_answer(
        self, status: str = "GOING"
    ) -> tuple[dict[str, str], str]:
        link = self.issue_participant_link_via_api()
        self.open_participant_link(link)
        candidate_date_id = self.answer_first_schedule_question(status)
        return link, candidate_date_id

    def attach_display_name(self, name: str) -> None:
        by_test_id(self.page, PARTICIPANT_NAME_OPEN).click()
        field = wait_for_at_least_one(self.page, PARTICIPANT_NAME_INPUT)
        field.fill(name)
        by_test_id(self.page, PARTICIPANT_NAME_SUBMIT).click()
        expect(by_test_id(self.page, PARTICIPANT_NAME_STATUS)).to_have_attribute(
            PARTICIPANT_NAMED_ATTR, "true"
        )

    def _read_schedule_tally_or_none(self, candidate_date_id: str) -> dict[str, str] | None:
        tally = self._schedule_question_locator(candidate_date_id).locator(
            f'[data-testid="{SCHEDULE_TALLY}"]'
        )
        if tally.count() == 0:
            return None
        return {
            "going": tally.get_attribute("data-going-count"),
            "maybe": tally.get_attribute("data-maybe-count"),
            "notGoing": tally.get_attribute("data-not-going-count"),
        }

    def capture_current_answer_state(
        self, candidate_date_ids: list[str]
    ) -> dict[str, dict[str, object]]:
        """rateLimitedScheduleResponse.priorAnswersRetained (TDR-GTH-15) requires
        every previously recorded data-your-response *and* gathering-schedule-tally
        value to survive a rejected request -- both are captured here, not just
        data-your-response.
        """
        return {
            candidate_date_id: {
                "yourResponse": self._schedule_question_locator(candidate_date_id).get_attribute(
                    YOUR_RESPONSE_ATTR
                ),
                "tally": self._read_schedule_tally_or_none(candidate_date_id),
            }
            for candidate_date_id in candidate_date_ids
        }

    def assert_answer_state_unchanged(self, before: dict[str, dict[str, object]]) -> None:
        after = self.capture_current_answer_state(list(before.keys()))
        self.assertions.assertEqual(after, before)

    def attempt_answer_schedule_question_expecting_rate_limit(
        self, candidate_date_id: str, status: str
    ) -> None:
        question = self._schedule_question_locator(candidate_date_id)
        option = question.locator(
            f'[data-testid="{RESPONSE_OPTION}"][{RESPONSE_VALUE_ATTR}="{status}"]'
        )
        option.click()
        error = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ERROR)
        self.assertions.assertEqual(error.get_attribute(LINK_ERROR_CODE_ATTR), "LINK_RATE_LIMITED")

    # TDR-GTH-13: API-level fuzzing (notVerifiedHere -- no browser click-through) -

    def attempt_get_participant_view_with_guessed_token(self) -> CapturedApiResponse:
        guessed_token = "guessed-" + secrets.token_urlsafe(24)
        return self._api("GET", f"/participant-links/{guessed_token}")

    def assert_access_denied_without_disclosure(self, response: CapturedApiResponse) -> None:
        self.assertions.assertEqual(response.status, 404)
        self.assertions.assertEqual(response.payload["code"], "LINK_NOT_FOUND")
        assert_matches_openapi_schema(
            response.payload, GATHERING_API_CONTRACT, "#/components/schemas/ProblemResponse"
        )
        real_title = require(self.gathering, "no real gathering exists to check against")["title"]  # type: ignore[index]
        self.assertions.assertNotIn(real_title, response.body)

    # Then: participant-facing observations ---------------------------------

    def assert_participant_is_nameless(self) -> None:
        expect(by_test_id(self.page, PARTICIPANT_NAME_STATUS)).to_have_attribute(
            PARTICIPANT_NAMED_ATTR, "false"
        )

    def assert_participant_is_named(self) -> None:
        expect(by_test_id(self.page, PARTICIPANT_NAME_STATUS)).to_have_attribute(
            PARTICIPANT_NAMED_ATTR, "true"
        )

    def assert_schedule_question_your_response(self, candidate_date_id: str, expected: str) -> None:
        expect(self._schedule_question_locator(candidate_date_id)).to_have_attribute(
            YOUR_RESPONSE_ATTR, expected
        )

    def assert_schedule_question_open_shop_count(
        self, candidate_date_id: str, expected: int
    ) -> None:
        expect(self._schedule_question_locator(candidate_date_id)).to_have_attribute(
            OPEN_SHOP_COUNT_ATTR, str(expected)
        )

    def assert_schedule_question_no_shop_details(self, candidate_date_id: str) -> None:
        """D6 (2026-08-30): "店名やその他の店舗情報は示されない" -- a stronger
        prohibition than organizerDashboard's own preview, which does show names.
        """
        question = self._schedule_question_locator(candidate_date_id)
        self.assertions.assertEqual(
            question.locator(f'[data-testid="{OPEN_SHOP_PREVIEW_ITEM}"]').count(), 0
        )
        assert_absent(self.assertions, self.page, OPEN_SHOP_PREVIEW_ITEM)
        assert_absent(self.assertions, self.page, OPEN_SHOP_PREVIEW_ITEM_NAME)

    def assert_schedule_question_tally_absent(self, candidate_date_id: str) -> None:
        question = self._schedule_question_locator(candidate_date_id)
        self.assertions.assertEqual(
            question.locator(f'[data-testid="{SCHEDULE_TALLY}"]').count(), 0
        )

    def assert_schedule_question_tally(
        self, candidate_date_id: str, *, going: int, maybe: int, not_going: int
    ) -> None:
        question = self._schedule_question_locator(candidate_date_id)
        tally = question.locator(f'[data-testid="{SCHEDULE_TALLY}"]')
        expect(tally).to_have_count(1)
        self.assertions.assertEqual(tally.get_attribute("data-going-count"), str(going))
        self.assertions.assertEqual(tally.get_attribute("data-maybe-count"), str(maybe))
        self.assertions.assertEqual(tally.get_attribute("data-not-going-count"), str(not_going))

    def assert_participant_header_phase(self, expected: str) -> None:
        header = assert_present(self.assertions, self.page, PARTICIPANT_HEADER)
        self.assertions.assertEqual(header.get_attribute(GATHERING_PHASE_ATTR), expected)

    def assert_participant_link_error(self, code: str) -> None:
        """invalidLinkOutcome.absent (browser-interface.yaml): all three of
        gathering-participant-header, gathering-schedule-question, and
        gathering-participant-name-open must be absent -- not only the first two.
        """
        error = assert_present(self.assertions, self.page, PARTICIPANT_LINK_ERROR)
        self.assertions.assertEqual(error.get_attribute(LINK_ERROR_CODE_ATTR), code)
        assert_all_absent(
            self.assertions,
            self.page,
            [PARTICIPANT_HEADER, SCHEDULE_QUESTION, PARTICIPANT_NAME_OPEN],
        )

    def assert_valid_participant_view_is_shown(self) -> None:
        assert_all_present(self.assertions, self.page, [PARTICIPANT_HEADER, SCHEDULE_QUESTION])
        assert_absent(self.assertions, self.page, PARTICIPANT_LINK_ERROR)

    # Cross-cutting: unavailableControls / disclosureObservations -----------
    # (both organizerDashboard and participantAnswer; whichever screen is
    # currently loaded on self.page).

    def assert_gathering_screen_has_no_forbidden_surfaces(self) -> None:
        """unavailableControls.forbiddenTestIds/allowedPurposes/forbiddenPurposes
        and disclosureObservations.bodyMustNotContain/bodyMustNotExposeTestIds,
        checked against whichever gathering screen is currently loaded. Mirrors
        candidate_search_browser.py's ALLOWED_CONTROL_PURPOSES purpose-coverage
        check and assert_map_has_no_forbidden_surfaces disclosure check for the
        sibling contract -- neither had a gathering-scheduling counterpart
        before this fix. Especially relevant where a gathering screen reuses
        candidate-search's own private population (open-shop preview/count,
        TDR-GTH-08/09): this is what proves that population never leaks its
        map/origin surfaces into a gathering screen (adr/0034 decision 6).

        Purpose-declaration scanning follows unavailableControls.
        operationalControlScope (ADR-0039, v0.4): a matched control is exempt
        only when its test id is registered in
        GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS *and* its tag is a native
        input/textarea (the exemption is scoped to value-entry controls, not
        select/checkbox/radio/combobox/listbox/range/slider/spinbutton/button
        or an interactive ARIA role -- those keep the general requirement).
        Any other matched control -- including an unregistered native input
        this contract does not know about -- still must declare a purpose
        from GATHERING_ALLOWED_PURPOSES, so a silently-added, untracked input
        is still caught (this is the point of ADR-0039's traceability
        condition, not a blanket input exemption).
        """
        assert_all_absent(self.assertions, self.page, GATHERING_FORBIDDEN_TEST_IDS)
        assert_all_absent(self.assertions, self.page, GATHERING_DISCLOSURE_FORBIDDEN_TEST_IDS)
        body = self.page.content()
        self.assertions.assertNotIn(GATHERING_PRIVATE_ORIGIN_CANARY, body)
        self.assertions.assertNotIn(GATHERING_PROVIDER_INTERNALS_CANARY, body)

        forbidden_purpose_selector = ",".join(
            f'[{GATHERING_CONTROL_PURPOSE_ATTR}="{purpose}"]'
            for purpose in GATHERING_FORBIDDEN_PURPOSES
        )
        self.assertions.assertEqual(self.page.locator(forbidden_purpose_selector).count(), 0)

        controls = self.page.locator(GATHERING_FORM_CONTROL_SELECTOR)
        for index in range(controls.count()):
            control = controls.nth(index)
            test_id = control.get_attribute("data-testid")
            tag_name = control.evaluate("element => element.tagName.toLowerCase()")
            is_registered_value_entry_control = (
                test_id in GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS
                and tag_name in {"input", "textarea"}
            )
            if is_registered_value_entry_control:
                continue
            purpose = control.get_attribute(GATHERING_CONTROL_PURPOSE_ATTR)
            self.assertions.assertIn(purpose, GATHERING_ALLOWED_PURPOSES)

    def assert_participant_token_not_persisted(self, link: dict[str, str]) -> None:
        """disclosureObservations.participantTokenHandling: the token must never
        be written to localStorage, a cookie, or any storage surviving page
        navigation other than the current URL itself.
        """
        token = link["token"]
        local_storage_dump = self.page.evaluate(
            "() => JSON.stringify(Object.entries(window.localStorage))"
        )
        self.assertions.assertNotIn(token, local_storage_dump)
        for cookie in self.page.context.cookies():
            self.assertions.assertNotIn(token, cookie.get("value", ""))
