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
own JSON operations (organizer Given-state construction, TDR-GTH-13's
fuzzing, and the two 409-boundary checks in TDR-GTH-10/20) go through
``self.page.context.request`` so they share the Playwright browser context's
cookies (the organizer session) without being a "browser click-through" --
exactly the profile's own notVerifiedHere note for TDR-GTH-13 sanctions
("API/boundary-level acceptance"). TDR-GTH-01 itself now drives
organizerGatheringCreate through the browser (reviewer audit Major#2), not
this API-direct path.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

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
# gathering-open-shop-preview-item / -name were retired 2026-09-09 (adr/0049
# decision 2, TDR-GTH-08 rewrite): this preview now carries a count only, no
# item sub-structure -- see assert_open_shop_preview_shows_expected_count
# below.

# organizerDashboard.shopSelectionEntry / shortlistedShopVotes / finalize
# (TDR-GTH-26/27/31-33/35/36/40/44/45, adr/0042/0044/0048/0049/0050). The
# separate shop-checklist screen (organizerDashboard.shortlistSelection,
# PickFive.dc.html) this section used to define was retired 2026-09-09
# (adr/0049 decision 1) -- shop selection now happens exclusively on
# candidate-search-browser-interface.yaml's gatheringMode, reached through
# shopSelectionEntry.open (SHORTLIST_OPEN below, unchanged test id, hoisted
# out of shortlistedShopVotes into its own section). This file reads
# gatheringMode's own test ids directly, mirroring the existing
# CANDIDATE_GATHERING_ENTRY precedent (TDR-GTH-25) -- not importing
# candidate_search_browser.py, keeping this slice's own module boundary.
SHOP_ID_ATTR = "data-shop-id"
SHORTLISTED_SHOP_LIST = "gathering-shortlisted-shop-list"
SHORTLISTED_SHOP_ITEM = "gathering-shortlisted-shop-item"
# Three-tier tally attributes (adr/0044, replacing the retired single
# data-approval-count): WANT_TO_GO_COUNT_ATTR/OK_TO_GO_COUNT_ATTR are new;
# NOT_GOING_COUNT_ATTR/RESPONDED_COUNT_ATTR below reuse the exact same
# attribute-name strings CandidateDate/ShortlistedShop already share.
WANT_TO_GO_COUNT_ATTR = "data-want-to-go-count"
OK_TO_GO_COUNT_ATTR = "data-ok-to-go-count"
# data-current-leader (adr/0050 decision 5): "true" for exactly the first
# item in shortlistedShopVotes.list's own orderingInvariant order.
CURRENT_LEADER_ATTR = "data-current-leader"
SHORTLIST_OPEN = "gathering-shortlist-open"
FINALIZE_SHOP_SELECT = "gathering-finalize-shop-select"
FINALIZE_SELECTED_ATTR = "data-finalize-selected"
FINALIZE_SUBMIT = "gathering-finalize-submit"

# candidate-search-browser-interface.yaml v1.8.0's gatheringMode (adr/0049
# decision 1): the consolidated shop-selection screen shopSelectionEntry.open
# navigates to. Read directly as raw test ids/attributes (see module-boundary
# note above) -- not imported from candidate_search_browser.py.
GATHERING_MODE_BAND = "candidate-gathering-mode-band"
GATHERING_MODE_SHORTLISTED_COUNT_ATTR = "data-gathering-shortlisted-count"
GATHERING_MODE_MAX_SHORTLISTED_ATTR = "data-gathering-max-shortlisted"
CANDIDATE_CARD = "candidate-card"
CANDIDATE_CARD_GATHERING_TOGGLE = "candidate-card-gathering-toggle"
CANDIDATE_GATHERING_SHORTLISTED_ATTR = "data-gathering-shortlisted"
# The subset of candidate-search-browser-interface.yaml's own, pre-existing
# card/map detail fields TDR-GTH-38 requires be visible from gatheringMode
# (adr/0044's map/detail requirement, now satisfied entirely by this other
# contract's unchanged card shape rather than a duplicate organizer-side
# rendering, adr/0049 decision 1).
CANDIDATE_MAP = "candidate-map"
CANDIDATE_CARD_WALKING_TIME = "candidate-card-walking-time"
CANDIDATE_CARD_TOTAL_SEATS = "candidate-card-total-seats"
CANDIDATE_CARD_NON_SMOKING = "candidate-card-non-smoking"
CANDIDATE_CARD_DINNER_BUDGET = "candidate-card-dinner-budget"
CANDIDATE_CARD_PROVIDER_PAGE_LINK = "candidate-card-provider-page-link"

# participantAnswer.shopVoteQuestion / finalizedView (TDR-GTH-28..30/34,
# adr/0042; restructured to three tiers, map/detail fields, and search-origin
# marker adr/0044/0045, TDR-GTH-37/39/41).
SHOP_VOTE_QUESTION = "gathering-shop-vote-question"
YOUR_VOTE_ATTR = "data-your-vote"
SHOP_VOTE_OPTION = "gathering-shop-vote-option"
VOTE_VALUE_ATTR = "data-vote-value"
SHOP_VOTE_TALLY = "gathering-shop-vote-tally"
PARTICIPANT_PROGRESS = "gathering-participant-progress"
PARTICIPANT_DECISION = "gathering-participant-decision"
YOUR_SCHEDULE_RESPONSE_ATTR = "data-your-schedule-response"
# gathering-participant-decision-shop-vote / data-vote-status were retired
# 2026-09-09 (adr/0050 decision 3, TDR-GTH-34 simplification): the finalized
# record no longer carries a per-shop breakdown, only yourScheduleResponse.
# RETIRED_PARTICIPANT_DECISION_SHOP_VOTE is kept only as a negative-assertion
# constant (see assert_participant_decision below), not as an observed field.
RETIRED_PARTICIPANT_DECISION_SHOP_VOTE = "gathering-participant-decision-shop-vote"
SHOP_VOTE_MAP = "gathering-shop-vote-map"
SHOP_VOTE_MAP_MARKER = "gathering-shop-vote-map-marker"
SEARCH_ORIGIN_MARKER = "gathering-search-origin-marker"
SHOP_VOTE_QUESTION_WALKING_TIME = "gathering-shop-vote-question-walking-time"
SHOP_VOTE_QUESTION_CAPACITY_TIER = "gathering-shop-vote-question-capacity-tier"
SHOP_VOTE_QUESTION_NON_SMOKING = "gathering-shop-vote-question-non-smoking"
SHOP_VOTE_QUESTION_DINNER_BUDGET = "gathering-shop-vote-question-dinner-budget"
SHOP_VOTE_QUESTION_PROVIDER_PAGE_LINK = "gathering-shop-vote-question-provider-page-link"

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
GATHERING_CREATE_CANCEL = "gathering-create-cancel"
GATHERING_ADD_CANDIDATE_DATE_FORM = "gathering-add-candidate-date-form"
GATHERING_ADD_CANDIDATE_DATE_SUBMIT = "gathering-add-candidate-date-submit"
GATHERING_ADD_CANDIDATE_DATE_CANCEL = "gathering-add-candidate-date-cancel"

# Candidate-date calendars (adr/0049 decision 3, adr/0051 decision 1): the
# row-based add/remove-row inputs both organizerGatheringCreate.
# candidateDateRow and addCandidateDateForm's single dateInput used to expose
# (gathering-create-candidate-date-row/-input/addRow/removeRow,
# gathering-add-candidate-date-input) are retired. Both screens now use a
# multi-select calendar of the same shape but with distinct, per-screen test
# ids (architect design judgment, adr/0051 decision 1: the two screens render
# separate DOM elements with different post-submit behavior, so one test id
# must not carry two different requiredOutcome contracts).
GATHERING_CREATE_CANDIDATE_DATE_CALENDAR = "gathering-create-candidate-date-calendar"
GATHERING_CREATE_CANDIDATE_DATE_DAY = "gathering-create-candidate-date-day"
GATHERING_ADD_CANDIDATE_DATE_CALENDAR = "gathering-add-candidate-date-calendar"
GATHERING_ADD_CANDIDATE_DATE_DAY = "gathering-add-candidate-date-day"
# Both calendars' day cells share the same attribute names (dayCell.attributes).
CALENDAR_DAY_DATE_ATTR = "data-date"
CALENDAR_DAY_SELECTED_ATTR = "data-selected"

# organizerDashboard.deleteGathering (adr/0050 decision 4, TDR-GTH-48): the
# organizer's explicit, irreversible, two-step gathering-deletion control.
GATHERING_DELETE_OPEN = "gathering-delete-open"
GATHERING_DELETE_CONFIRM_DIALOG = "gathering-delete-confirm-dialog"
GATHERING_DELETE_CONFIRM = "gathering-delete-confirm"
GATHERING_DELETE_CANCEL = "gathering-delete-cancel"

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
# unexpectedLoadFailureOutcome / loadFailure (browser-interface.yaml v0.8.0,
# adr/0047, TDR-GTH-42). No attribute is defined for this element -- unlike
# linkError's data-link-error-code, the contract fixes no failure taxonomy
# here, only that the element exists and every other participant surface
# does not.
PARTICIPANT_LOAD_ERROR = "gathering-participant-load-error"

# answerLater / peekResults (adr/0050 decision 1, 2026-09-08〜09 human
# decision: 「あとで答える」「結果をのぞく」を実際に動く操作にする -- both
# previously visual-only). Neither owns a dedicated TDR-GTH-4x scenario (the
# contract's own note: "no dedicated TDR-GTH-4x scenario names these two
# controls, but they are real, present controls... so they must still be
# declared"), so this suite verifies their requiredOutcome directly as a UI
# implementation detail, the same precedent TDR-GTH-43's ordering check and
# TDR-CS-02's desktop/mobile split already establish for contract Musts with
# no scenario of their own.
ANSWER_LATER = "gathering-participant-answer-later"
ANSWER_LATER_CONFIRMATION = "gathering-participant-answer-later-confirmation"
PEEK_RESULTS = "gathering-participant-peek-results"

# unavailableControls (both namespaces; gathering-scheduling-browser-interface.yaml).
# Mirrors candidate_search_browser.py's ALLOWED_CONTROL_PURPOSES /
# assert_map_has_no_forbidden_surfaces convention for the sibling contract.
GATHERING_CONTROL_PURPOSE_ATTR = "data-gathering-control-purpose"
# Verified 1:1 against gathering-scheduling-browser-interface.yaml v0.11.0's
# own unavailableControls.allowedPurposes list (26 entries, contract lines
# ~768-782) -- every entry below has a matching contract entry and vice
# versa. This is a full resync, not an incremental diff: v0.11.0 retired 4
# entries this set previously carried (gathering-create-add-candidate-date-
# row/-remove-candidate-date-row, adr/0051 decision 3's row-to-calendar
# swap; gathering-open-shop-select/-shortlist-submit, adr/0049 decision 1's
# shortlistSelection retirement) and added 7 (gathering-add-candidate-date-
# day-select, gathering-create-candidate-date-day-select, adr/0049 decision
# 3 / adr/0051 decision 3's calendars; gathering-delete-open/-confirm/
# -cancel, adr/0050 decision 4; gathering-participant-answer-later/
# -peek-results, adr/0050 decision 1).
GATHERING_ALLOWED_PURPOSES = {
    "gathering-add-candidate-date-open",
    "gathering-add-candidate-date-submit",
    "gathering-add-candidate-date-cancel",
    "gathering-add-candidate-date-day-select",
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
    "gathering-create-candidate-date-day-select",
    "gathering-create-submit",
    "gathering-create-cancel",
    # shopSelectionEntry (hoisted out of shortlistedShopVotes 2026-09-09,
    # adr/0049 decision 1) / finalize / participant shop-vote (adr/0042,
    # browser-interface v0.5's allowedPurposesNote2026_09_04).
    "gathering-shortlist-open",
    "gathering-finalize-shop-select",
    "gathering-finalize-submit",
    "gathering-shop-vote-select",
    # deleteGathering (adr/0050 decision 4, TDR-GTH-48).
    "gathering-delete-open",
    "gathering-delete-confirm",
    "gathering-delete-cancel",
    # answerLater / peekResults (adr/0050 decision 1) -- no dedicated
    # TDR-GTH-4x scenario names these two controls, but they are real,
    # present controls on participantAnswer once rendered, so they must
    # still be declared here for the cross-cutting purpose scan.
    "gathering-participant-answer-later",
    "gathering-participant-peek-results",
}
# unavailableControls.valueEntryControlTestIds (ADR-0039, v0.4): native
# input/textarea value-entry controls exempt from purpose declaration --
# but only because each is traced in browserControlSurface to exactly one
# operational control's requiredOutcome that consumes it. An unregistered
# native input remains subject to the general purpose requirement below
# (this is the point of ADR-0039's design: traceable exemption, not a
# blanket one -- see operationalControlScope in the contract).
# Verified 1:1 against v0.11.0's own valueEntryControlTestIds (contract line
# 714-715, 2 entries). gathering-create-candidate-date-input and
# gathering-add-candidate-date-input are retired 2026-09-09 (adr/0049
# decision 3, adr/0051 decision 3): both screens' calendar day cells are
# operational controls (each activation toggles pending selection), not
# value-entry controls, so they declare a *-day-select purpose in
# GATHERING_ALLOWED_PURPOSES above instead of appearing here.
GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS = {
    "gathering-create-name-input",
    "gathering-participant-name-input",
}
# operationalControlScope (ADR-0039) scopes the exemption to a native input
# "of type text/date/time/datetime-local/number" (or a textarea) -- reviewer
# audit Minor#4: the exemption check previously matched by tag name alone,
# so a registered test id reused on e.g. an <input type="checkbox"> would
# have wrongly been exempted. A bare <input> with no type attribute defaults
# to "text" per the HTML spec, hence its inclusion here.
GATHERING_VALUE_ENTRY_INPUT_TYPES = {"text", "date", "time", "datetime-local", "number"}
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

    def seed_participant_link_server_error(self, link: dict[str, str]) -> None:
        """test-support-api.yaml 1.5.4's seedParticipantLinkServerError
        (adr/0047 decision 4): makes the *next* getParticipantView call for
        this token return an HTTP 500 that matches none of linkError's four
        recognized ProblemResponse codes -- the state
        unexpectedLoadFailureOutcome (TDR-GTH-42) requires, and one the
        public boundary alone cannot produce (same exception class as
        seed_expired_participant_link/seed_rate_limited_participant_link
        above).
        """
        response = self.support.request(
            "POST",
            "/test-support/gathering-scheduling/participant-links/server-error",
            data=json.dumps({"token": link["token"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        assert_no_content(self.assertions, response, "seedParticipantLinkServerError")

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

    def capture_candidate_date_order(self) -> list[str]:
        return [date["id"] for date in self._read_candidate_dates()]

    def _expected_candidate_date_order(self, start_at_isos: list[str]) -> list[str]:
        return [self._candidate_date_id_by_start_at[iso] for iso in sorted(start_at_isos)]

    def assert_candidate_date_order_matches_start_at_order(self, start_at_isos: list[str]) -> None:
        """candidateDateList.orderingInvariant's tie-break (adr/0048, TDR-GTH-43):
        every candidate date here ties at goingCount 0 (nobody has answered
        yet), so the whole order collapses to startAt ascending. Checked
        against the chronological order of the exact ISO strings this
        scenario's own Given supplied -- not mere self-consistency against
        the API's own claimed order the way TDR-GTH-08/37's near-order
        checks work (this suite cannot recompute geography, but startAt is
        data this suite itself chose, so it can independently recompute the
        expected order).
        """
        self.assertions.assertEqual(
            self.capture_candidate_date_order(),
            self._expected_candidate_date_order(start_at_isos),
        )

    def assert_candidate_date_order_unchanged(self, before: list[str]) -> None:
        self.assertions.assertEqual(self.capture_candidate_date_order(), before)

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

    def _calendar_day_locator(self, calendar_day_test_id: str, iso: str) -> Locator:
        """Locates one calendar day cell by its data-date (YYYY-MM-DD, no time
        component -- both organizerGatheringCreate.calendar.dayCell and
        addCandidateDateForm.calendar.dayCell share this exact shape,
        adr/0049 decision 3 / adr/0051 decision 1). ``iso`` is a full
        RFC3339 CandidateDateInput.startAt string; only its date part is
        used to find the cell -- the calendar's own "12:00始まり" UI aid
        supplies the time-of-day server-side, so ``iso`` must itself carry
        12:00 for the resulting round trip to match (days_from_now_iso/
        next_weekday_iso above both default to hour=12 for this reason).
        """
        date_part = datetime.fromisoformat(iso).strftime("%Y-%m-%d")
        return self.page.locator(
            f'[data-testid="{calendar_day_test_id}"][{CALENDAR_DAY_DATE_ATTR}="{date_part}"]'
        )

    def _select_calendar_days(self, calendar_day_test_id: str, isos: list[str]) -> None:
        for iso in isos:
            cell = self._calendar_day_locator(calendar_day_test_id, iso)
            expect(cell).to_be_enabled()
            cell.click()
            expect(cell).to_have_attribute(CALENDAR_DAY_SELECTED_ATTR, "true")

    def _selected_calendar_day_dates(self, calendar_day_test_id: str) -> list[str]:
        selected = self.page.locator(
            f'[data-testid="{calendar_day_test_id}"][{CALENDAR_DAY_SELECTED_ATTR}="true"]'
        )
        return [
            selected.nth(index).get_attribute(CALENDAR_DAY_DATE_ATTR)
            for index in range(selected.count())
        ]

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

    def submit_add_candidate_date_form(self, candidate_date_isos: list[str]) -> CapturedApiResponse:
        """addCandidateDateForm.calendar/submit (adr/0049 decision 3): selects
        one calendar day per ISO date, then submits the batch addCandidateDates
        call -- replacing the retired single-input, singular-addCandidateDate
        flow. Accepts a list (even for a single date, TDR-GTH-02/24) so the
        same method drives TDR-GTH-46's own multi-date batch unchanged.
        """
        self._select_calendar_days(GATHERING_ADD_CANDIDATE_DATE_DAY, candidate_date_isos)
        response = self._capture_gathering_response(
            "candidate-dates",
            lambda: by_test_id(self.page, GATHERING_ADD_CANDIDATE_DATE_SUBMIT).click(),
        )
        if response.status == 201:
            self._created_candidate_date_isos.extend(candidate_date_isos)
            self._set_gathering(response.payload)
        return response

    def candidate_dates_snapshot(self) -> list[dict[str, object]]:
        return self._read_candidate_dates()

    def assert_candidate_dates_added_via_inline_form(
        self,
        response: CapturedApiResponse,
        before_dates: list[dict[str, object]],
        expected_phase: str,
        expected_new_count: int = 1,
    ) -> None:
        """addCandidateDateForm.submit.requiredOutcome's success branch
        (TDR-GTH-02/46): exactly ``expected_new_count`` new
        gathering-candidate-date elements appear, phase is unchanged, the
        form remains present ready for another entry (human decision
        2026-09-01, AddDate.dc.html 案A: "足したあとフォームは閉じない"), and
        every day cell resets to unselected (adr/0049 decision 3's own
        requiredOutcome text). Identifies "the new ones" as a before/after
        id-set diff (caller supplies a pre-submit candidate_dates_snapshot())
        rather than looking them up by the submitted startAt strings --
        deliberately avoiding the same class of fragility a prior audit
        flagged for candidate_date_id_at (byte-identity between what a
        client sends and what the server echoes back is not guaranteed).
        """
        self.assertions.assertEqual(response.status, 201)
        before_ids = {date["id"] for date in before_dates}
        after_ids = {date["id"] for date in self._read_candidate_dates()}
        new_ids = after_ids - before_ids
        self.assertions.assertEqual(
            len(new_ids),
            expected_new_count,
            f"expected exactly {expected_new_count} new candidate date(s), got {new_ids}",
        )
        self.assertions.assertEqual(self._read_gathering_phase_from_dom(), expected_phase)
        assert_present(self.assertions, self.page, GATHERING_ADD_CANDIDATE_DATE_FORM)
        self.assertions.assertEqual(
            self._selected_calendar_day_dates(GATHERING_ADD_CANDIDATE_DATE_DAY), []
        )

    def assert_duplicate_candidate_date_rejected_by_inline_form(
        self,
        response: CapturedApiResponse,
        candidate_date_isos: list[str],
        before_dates: list[dict[str, object]],
    ) -> None:
        """TDR-GTH-24/46 / addCandidateDateForm.submit.requiredOutcome's
        whole-batch DUPLICATE_CANDIDATE_DATE branch: no candidate date is
        added (dates unchanged from the pre-submit snapshot), the form stays
        present, and every day cell's data-selected is unchanged -- not one
        of them resets, even the ones that did not themselves collide
        (adr/0049 decision 3: "全部やるか全部やめるか").
        """
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "DUPLICATE_CANDIDATE_DATE")
        self.assertions.assertEqual(self._read_candidate_dates(), before_dates)
        assert_present(self.assertions, self.page, GATHERING_ADD_CANDIDATE_DATE_FORM)
        expected_selected = {
            datetime.fromisoformat(iso).strftime("%Y-%m-%d") for iso in candidate_date_isos
        }
        actual_selected = set(self._selected_calendar_day_dates(GATHERING_ADD_CANDIDATE_DATE_DAY))
        self.assertions.assertEqual(actual_selected, expected_selected)

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
                    "respondedCount": int(node.get_attribute(RESPONDED_COUNT_ATTR)),
                    "activeIssuedLinks": int(node.get_attribute(ACTIVE_ISSUED_LINKS_ATTR)),
                }
            )
        return result

    def assert_gathering_list_matches(self, expected: list[dict[str, object]]) -> None:
        """expected: DOM-order list of {"id", "phase", "confirmedCandidateDate",
        "respondedCount", "activeIssuedLinks"} (createdAt descending, 新しい順,
        organizerGatheringList.list.orderingInvariant). Checks all 5 of the
        contract's gathering-list-item attributes (reviewer audit Major#1:
        respondedCount/activeIssuedLinks were previously read nowhere in this
        slice, even though organizerDashboard's own denominatorAttributes
        already prove the same-named values elsewhere -- that does not
        substitute for checking this list's own, independently-projected
        attributes). This does not assert each gathering's title/name: the
        contract's gathering-list-item attributes define no machine-
        observable name field, so the .feature's "名前...が示される" clause
        cannot be verified here (see this slice's tester report).
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
            self.assertions.assertEqual(actual["respondedCount"], wanted["respondedCount"])
            self.assertions.assertEqual(actual["activeIssuedLinks"], wanted["activeIssuedLinks"])

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

    def select_gathering_create_candidate_date_days(self, isos: list[str]) -> None:
        """organizerGatheringCreate.calendar.dayCell.select (adr/0051 decision
        1): replaces the retired row-based candidateDateRow/addRow -- selects
        one calendar day per prepared ISO date on this screen's own,
        distinct calendar (not addCandidateDateForm's, per adr/0051's
        design judgment that the two screens do not share one test id).
        """
        self._select_calendar_days(GATHERING_CREATE_CANDIDATE_DATE_DAY, isos)

    def _extract_gathering_id_from_dashboard_url(self) -> str:
        match = re.search(r"/gatherings/([^/]+)/?$", self.page.url)
        return require(match, f"unexpected post-create URL shape: {self.page.url}").group(  # type: ignore[union-attr]
            1
        )

    def create_prepared_gathering_via_browser(self) -> None:
        """TDR-GTH-01, driven end-to-end through organizerGatheringCreate
        (browser-interface.yaml v0.4: "Supports TDR-GTH-01 (now browser-
        verifiable)") instead of createGathering direct-API -- reviewer audit
        Major#2. **Rewritten 2026-09-09 (adr/0051 decision 1)**: fills the
        name, then selects one calendar day per prepared date (replacing the
        retired per-row date inputs and addRow), then submits.

        Clicking submit here also navigates (this implementation's own
        choice, within the contract's own "does not fix the immediate
        post-submit destination screen" allowance) -- a real Playwright
        response body becomes unreadable once its page has navigated away
        (confirmed empirically: capturing the createGathering response the
        same way submit_add_candidate_date_form does raised "response body
        is not available for a response that was navigated away from").
        This reads the created gathering back through the public
        getGathering operation once the dashboard has rendered, instead.
        """
        title = require(self._prepared_title, "no gathering was prepared")
        dates = require(self._prepared_candidate_date_isos, "no candidate dates were prepared")
        self.open_gathering_create_from_header()
        self.fill_gathering_create_name(title)
        self.select_gathering_create_candidate_date_days(dates)
        by_test_id(self.page, GATHERING_CREATE_SUBMIT).click()
        wait_for_at_least_one(self.page, GATHERING_PHASE_INDICATOR)
        gathering_id = self._extract_gathering_id_from_dashboard_url()
        response = self._api("GET", f"/gatherings/{gathering_id}")
        self._assert_api_ok(response, 200, "getGathering (post-create readback)")
        assert_matches_openapi_schema(
            response.payload, GATHERING_API_CONTRACT, "#/components/schemas/Gathering"
        )
        self._created_candidate_date_isos.extend(dates)
        self._set_gathering(response.payload)
        self._created_gatherings.append(response.payload)

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

    # TDR-GTH-47 (new, adr/0049 decision 3 / adr/0051 decision 2): 明日以降
    # のみ, verified from organizerGatheringCreate (its own Given "幹事が会を
    # つくろうとしている") -- the calendar's day-cell disabledState is not
    # checked directly here: the contract does not fix the calendar's
    # rendered month range (organizerGatheringCreate.calendar.note), so
    # today's own date cell being present at all is not guaranteed. The
    # contract itself names CANDIDATE_DATE_NOT_IN_FUTURE's server-side
    # rejection "the authoritative enforcement" of this rule, so this
    # bypasses the (contract-optional) UI affordance the same way
    # TDR-GTH-20/23 already bypass a disabled control to prove server-side
    # enforcement. ---------------------------------------------------------

    def attempt_create_gathering_via_api_with_a_past_candidate_date(
        self, title: str, past_or_today_iso: str
    ) -> CapturedApiResponse:
        return self._api(
            "POST",
            "/gatherings",
            {"title": title, "candidateDates": [{"startAt": past_or_today_iso}]},
            csrf=True,
        )

    def assert_create_rejected_because_date_not_in_future(
        self, response: CapturedApiResponse
    ) -> None:
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "CANDIDATE_DATE_NOT_IN_FUTURE")

    # deleteGathering (TDR-GTH-48, adr/0050 decision 4) ----------------------

    def delete_gathering_via_dashboard(self) -> None:
        """deleteGathering's open-then-confirm two-step pattern (adr/0050
        decision 4, mirroring addCandidateDateForm's own open/submit shape).
        Calls the cross-cutting check while the confirm dialog is open --
        FR-030's repeated lesson: a new screen state (the dialog itself,
        carrying gathering-delete-confirm/-cancel) must be exercised, not
        only the pre- and post-delete dashboard states.
        """
        by_test_id(self.page, GATHERING_DELETE_OPEN).click()
        wait_for_at_least_one(self.page, GATHERING_DELETE_CONFIRM_DIALOG)
        self.assert_gathering_screen_has_no_forbidden_surfaces()
        by_test_id(self.page, GATHERING_DELETE_CONFIRM).click()

    def assert_gathering_absent_from_list(self, gathering_id: str) -> None:
        self.open_organizer_gathering_list()
        ids = {item["id"] for item in self._read_gathering_list_items()}
        self.assertions.assertNotIn(gathering_id, ids)

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

    def assert_open_shop_preview_shows_expected_count(self, expected_open_shop_count: int) -> None:
        """**Narrowed 2026-09-09 (adr/0049 decision 2, TDR-GTH-08 rewrite)**:
        this preview no longer carries a shop-name/item sub-structure --
        gathering-open-shop-preview-item and the OpenShopPreviewItem schema
        it projected are both retired. This checks the count only, plus the
        stronger prohibition the rewritten scenario now states explicitly
        ("店名やその他の店舗情報は示されない"): no shop-item element renders
        inside the preview at all.
        """
        response = require(self._current_open_shop_preview, "no open-shop preview was captured")
        self.assertions.assertEqual(response.status, 200)  # type: ignore[union-attr]
        payload = response.payload  # type: ignore[union-attr]
        self.assertions.assertEqual(payload["openShopCount"], expected_open_shop_count)
        self.assertions.assertNotIn("previewShops", payload)
        preview = assert_present(self.assertions, self.page, OPEN_SHOP_PREVIEW)
        self.assertions.assertEqual(
            preview.get_attribute(OPEN_SHOP_COUNT_ATTR), str(payload["openShopCount"])
        )

    def assert_open_shop_preview_shows_no_shop_details(self) -> None:
        preview = assert_present(self.assertions, self.page, OPEN_SHOP_PREVIEW)
        self.assertions.assertEqual(
            preview.locator('[data-testid="gathering-open-shop-preview-item"]').count(), 0
        )

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

    # Shortlist selection / D7 replace / finalize (organizer UI, TDR-GTH-26/27/
    # 31/32/33/35, adr/0042) -------------------------------------------------

    def create_selecting_shop_gathering(
        self, title: str, candidate_date_isos: list[str], confirm_index: int = 0
    ) -> str:
        """Given-state builder ("幹事が開催日を決めた「店を選び中」の会を持っている"):
        creates a SCHEDULING gathering (the same public-API path
        given_scheduling_gathering uses) and immediately confirms one of its
        candidate dates via confirm_candidate_date_via_api (already exercised
        by TDR-GTH-21). Unlike that existing helper, this one also updates
        self.gathering so callers immediately see confirmedCandidateDateId.
        Returns the confirmed candidate date's id.
        """
        self._create_gathering(title, candidate_date_isos)
        candidate_date_id = self.candidate_date_id_at(confirm_index)
        payload = self.confirm_candidate_date_via_api(self.gathering_id, candidate_date_id)
        self._set_gathering(payload)
        return candidate_date_id

    def refresh_gathering_from_api(self) -> dict:
        """Given-state technique for TDR-GTH-34: confirm_tentatively_selected_date
        (the UI-driven confirm action, reused unmodified from TDR-GTH-06/10/11)
        does not update self.gathering, so a scenario that confirms through the
        UI and then needs confirmedCandidateDateId for a further Given-state
        call (fetch_confirmed_date_open_shop_ids below) reads it back via the
        same getGathering operation TDR-GTH-01's browser flow already uses.
        """
        response = self._api("GET", f"/gatherings/{self.gathering_id}")
        self._assert_api_ok(response, 200, "getGathering (refresh)")
        self._set_gathering(response.payload)
        return response.payload

    def fetch_confirmed_date_open_shop_ids(self) -> list[str]:
        """Given-state technique. **Rewired 2026-09-09 (adr/0049 decision 1/2)**:
        previewOpenShopsForCandidateDate no longer returns a shop list (only
        openShopCount, decision 2) -- shop identity for the confirmed date now
        comes exclusively from candidate-search-api.yaml's own proposeCandidates
        called with this gathering's id (decision 1's gatheringId narrowing).
        This is a direct JSON call sharing the same authenticated session
        (mirrors this file's own _api convention for organizer Given-state,
        adr/0037 decision 1), not a browser click-through -- candidate-search-
        browser-interface.yaml's own screen is exercised separately by
        TDR-GTH-44/45 and TDR-CS-17..19. **Capped at 5** (candidate-search-
        api.yaml's own `candidates` maxItems: 5) -- for a confirmed date whose
        openShopCount exceeds 5 (Thursday/Friday/Saturday, 6 open), this
        returns only 5 of them; callers needing a shop from beyond that cap
        use fetch_shop_id_closed_only_on/fetch_a_shop_id_not_open_on
        below, which sidestep the cap via a second, temporary probe gathering
        confirmed on a day whose openShopCount is at or under 5 (complete,
        no sampling loss).
        """
        gathering = require(self.gathering, "no gathering exists")
        require(gathering["confirmedCandidateDateId"], "no candidate date is confirmed")  # type: ignore[index]
        response = self._api(
            "POST", "/candidate-proposals", {"gatheringId": self.gathering_id}, csrf=True
        )
        self._assert_api_ok(response, 200, "proposeCandidates (gathering mode, given-state)")
        return [candidate["shopId"] for candidate in response.payload["candidates"]]

    def set_shortlisted_shops_via_api(self, shop_ids: list[str]) -> dict:
        """Given-state builder for scenarios where setShortlistedShops itself is
        not the action under test (adr/0037 decision 1's public-API path).
        Also used as the WHEN step for D7 replace (TDR-GTH-31/32, adr/0049
        decision 1): the operation itself is unchanged by that decision (only
        the screen calling it moved to candidate-search-browser-interface.
        yaml's gatheringMode) -- see fetch_a_shop_id_not_open_on's own
        docstring for why this file drives that swap at the API boundary
        rather than through gatheringMode's own cardToggle.
        """
        response = self._api(
            "PUT",
            f"/gatherings/{self.gathering_id}/shortlisted-shops",
            {"shopIds": shop_ids},
            csrf=True,
        )
        self._assert_api_ok(response, 200, "setShortlistedShops (given-state)")
        self._set_gathering(response.payload)
        return response.payload

    def _probe_open_shop_ids_on(self, candidate_date_iso: str) -> set[str]:
        """Creates and confirms a throwaway probe gathering on ``candidate_date_iso``,
        then reads back its complete open-shop shopId set via
        fetch_confirmed_date_open_shop_ids above. Only used with a date whose
        GATHERING_OPEN_SHOP_WEEKDAY_MATCH openShopCount is <= 5 (the
        candidate-search-api.yaml display cap), so the returned set is always
        *complete* for that day -- no sampling loss, unlike a day with 6 open
        shops. Does not disturb self.gathering/self.gathering_id, or
        candidate_date_id_at's own index space (saves and restores all four
        -- **fixed**: an earlier version restored only gathering/gathering_id,
        leaving _created_candidate_date_isos/_candidate_date_id_by_start_at
        permanently shifted by this probe's own throwaway date. A caller that
        runs this probe *before* building its own gathering -- e.g. TDR-GTH-
        31/32's `a_shop_id_not_open_on` before `organizer_has_a_selecting_
        shop_gathering` -- would then have candidate_date_id_at(0) resolve to
        this probe's own candidate date instead of its own gathering's first
        one, confirming the wrong gathering's date and getting back
        CANDIDATE_DATE_NOT_FOUND; reproduced empirically before this fix),
        so callers can freely interleave this with their own gathering's own
        state regardless of call order.
        """
        saved_gathering, saved_gathering_id = self.gathering, self.gathering_id
        saved_isos = list(self._created_candidate_date_isos)
        saved_id_by_start_at = dict(self._candidate_date_id_by_start_at)
        self._create_gathering("会（一時プローブ）", [candidate_date_iso])
        candidate_date_id = self.candidate_date_id_at(-1)
        self.confirm_candidate_date_via_api(self.gathering_id, candidate_date_id)
        self._set_gathering(self._api("GET", f"/gatherings/{self.gathering_id}").payload)
        open_ids = set(self.fetch_confirmed_date_open_shop_ids())
        self.gathering, self.gathering_id = saved_gathering, saved_gathering_id
        self._created_candidate_date_isos = saved_isos
        self._candidate_date_id_by_start_at = saved_id_by_start_at
        return open_ids

    def fetch_shop_id_closed_only_on(self, closed_weekday: int, open_weekday: int) -> str:
        """Test-arrangement technique for TDR-GTH-27: GATHERING_OPEN_SHOP_
        WEEKDAY_MATCH's population is fixed at exactly 6 shops (test-support-
        api.yaml's own documented shape); this identifies one real shopId
        that is open on ``open_weekday`` but not on ``closed_weekday`` by
        diffing two *complete* (<=5-open, cap-safe) probe days' shopId sets
        -- both weekdays must themselves have openShopCount <= 5 for their
        probe sets to be complete (e.g. Monday=5 vs Wednesday=4, both under
        OPEN_SHOP_COUNT_BY_WEEKDAY's cap). Replaces the retired
        identify_a_shop_closed_on_the_confirmed_date, which read
        previewOpenShopsForCandidateDate's now-removed previewShops directly.

        **The diff is not guaranteed to be a singleton**: test-support-
        api.yaml documents only each weekday's total openShopCount, not
        which of the 6 fixed shops individually belong to which weekday --
        empirically, Monday(5)/Wednesday(4) yields two shops open on
        Wednesday but not Monday, not one (this method's own only caller
        needs *some* shop meeting the criterion, not a uniquely-identified
        one, so this no longer over-asserts a cardinality the contract
        never promised). Picks the lexicographically smallest candidate for
        determinism across runs.
        """
        open_ids = self._probe_open_shop_ids_on(next_weekday_iso(open_weekday))
        closed_ids = self._probe_open_shop_ids_on(next_weekday_iso(closed_weekday))
        candidates = open_ids - closed_ids
        self.assertions.assertGreaterEqual(
            len(candidates),
            1,
            f"expected at least one shop open on open_weekday but not closed_weekday, got none "
            f"(open={open_ids}, closed={closed_ids})",
        )
        return sorted(candidates)[0]

    def fetch_a_shop_id_not_open_on(self, excluded_weekday: int, included_weekday: int) -> str:
        """Test-arrangement technique for TDR-GTH-31/32 (D7 replace): identical
        diffing technique to fetch_shop_id_closed_only_on above, naming a real
        shopId that is open on ``included_weekday`` (where the scenario's own
        gathering is confirmed) but excluded from ``excluded_weekday``'s probe
        -- i.e. a shop guaranteed *not* to be one the scenario shortlists from
        an ``excluded_weekday`` probe's complete set, so it is safe to use as
        the "newly added, previously unselected" shop in a replace. This file
        drives the replace itself via set_shortlisted_shops_via_api (the API
        boundary), not gatheringMode's own per-card toggle: unlike TDR-GTH-26
        (which only ever needs <=5 known shops, safely within candidate-
        search-api.yaml's own 5-item display cap), D7 replace needs a 6th,
        currently-unlisted shop on a day with 6 open shops -- a quantity
        candidate-search-api.yaml's cap makes undiscoverable through the
        gatheringMode screen's own rendered cards in one deterministic call.
        """
        return self.fetch_shop_id_closed_only_on(excluded_weekday, included_weekday)

    def _read_shortlisted_shop_items(self) -> list[dict[str, object]]:
        nodes = wait_for_at_least_one(self.page, SHORTLISTED_SHOP_ITEM)
        result = []
        for index in range(nodes.count()):
            node = nodes.nth(index)
            result.append(
                {
                    "shopId": node.get_attribute(SHOP_ID_ATTR),
                    "wantToGoCount": int(node.get_attribute(WANT_TO_GO_COUNT_ATTR)),
                    "okToGoCount": int(node.get_attribute(OK_TO_GO_COUNT_ATTR)),
                    "notGoingCount": int(node.get_attribute(NOT_GOING_COUNT_ATTR)),
                    "respondedCount": int(node.get_attribute(RESPONDED_COUNT_ATTR)),
                    "currentLeader": node.get_attribute(CURRENT_LEADER_ATTR) == "true",
                }
            )
        return result

    def assert_shortlisted_shop_ids(self, expected_ids: list[str]) -> None:
        actual_ids = {item["shopId"] for item in self._read_shortlisted_shop_items()}
        self.assertions.assertEqual(actual_ids, set(expected_ids))

    def assert_shortlisted_shop_tally(
        self, shop_id: str, *, want_to_go: int, ok_to_go: int, not_going: int, responded: int
    ) -> None:
        """Fixed 2026-09-05 (adr/0044 decision 1/3): three-tier tally, replacing
        the retired single approvalCount. wantToGoCount + okToGoCount +
        notGoingCount must always equal respondedCount (gathering-scheduling-
        api.yaml's ShortlistedShop own invariant) -- checked here too, not
        only trusted.
        """
        items = {item["shopId"]: item for item in self._read_shortlisted_shop_items()}
        item = require(items.get(shop_id), f"shortlisted shop {shop_id} not shown")
        self.assertions.assertEqual(item["wantToGoCount"], want_to_go)  # type: ignore[index]
        self.assertions.assertEqual(item["okToGoCount"], ok_to_go)  # type: ignore[index]
        self.assertions.assertEqual(item["notGoingCount"], not_going)  # type: ignore[index]
        self.assertions.assertEqual(item["respondedCount"], responded)  # type: ignore[index]
        self.assertions.assertEqual(
            item["wantToGoCount"] + item["okToGoCount"] + item["notGoingCount"],  # type: ignore[operator]
            item["respondedCount"],
        )

    def assert_shortlisted_shop_list_is_ordered_by_combined_tier_descending(self) -> None:
        """TDR-GTH-40: 店は「行きたい」と「行ってもいい」の合計が多い順に並ぶ
        (adr/0044 decision 3, replacing the retired single wantToGoCount-only
        order an in-progress draft had used).
        """
        combined = [
            item["wantToGoCount"] + item["okToGoCount"]  # type: ignore[operator]
            for item in self._read_shortlisted_shop_items()
        ]
        self.assertions.assertEqual(combined, sorted(combined, reverse=True))

    def assert_shortlisted_shop_current_leader(self, shop_id: str) -> None:
        """data-current-leader (adr/0050 decision 5): "true" for exactly the
        shop that is first in this list's own orderingInvariant order;
        "false" for every other item.
        """
        items = self._read_shortlisted_shop_items()
        leaders = [item["shopId"] for item in items if item["currentLeader"]]
        self.assertions.assertEqual(leaders, [shop_id], f"expected exactly {shop_id} to lead")

    # shopSelectionEntry / candidate-search-browser-interface.yaml's
    # gatheringMode (TDR-GTH-38/44/45, adr/0049 decision 1) -----------------
    # organizerDashboard.shortlistSelection's own map/detail-field screen was
    # retired 2026-09-09 along with the rest of that section -- TDR-GTH-38's
    # "地図と店の情報" observation now lives entirely on candidate-search-
    # browser-interface.yaml's own, pre-existing card/map (unchanged by
    # adr/0049, which only adds the toggle+band on top of it). Read directly
    # as raw test ids (module-boundary note, top of file) rather than
    # importing candidate_search_browser.py.

    def open_shop_selection_entry(self) -> None:
        """shopSelectionEntry.open.requiredOutcome (adr/0049 decision 1):
        navigates from the organizer dashboard to candidate-search-browser-
        interface.yaml's gatheringMode.
        """
        by_test_id(self.page, SHORTLIST_OPEN).first.click()
        wait_for_at_least_one(self.page, GATHERING_MODE_BAND)

    def _read_gathering_mode_band(self) -> dict[str, int]:
        node = assert_present(self.assertions, self.page, GATHERING_MODE_BAND)
        return {
            "shortlisted": int(node.get_attribute(GATHERING_MODE_SHORTLISTED_COUNT_ATTR)),
            "max": int(node.get_attribute(GATHERING_MODE_MAX_SHORTLISTED_ATTR)),
        }

    def assert_gathering_mode_band_shows(
        self, *, shortlisted: int, max_shortlisted: int = 5
    ) -> None:
        band = self._read_gathering_mode_band()
        self.assertions.assertEqual(band["shortlisted"], shortlisted)
        self.assertions.assertEqual(band["max"], max_shortlisted)

    def select_first_n_candidates_into_gathering(self, n: int) -> list[str]:
        """gatheringMode.cardToggle's requiredOutcome (TDR-GTH-26/44), called
        while already on candidate-search-browser-interface.yaml's screen
        (open_shop_selection_entry above). Unlike this file's own retired
        shortlistSelection (pending-select-then-submit), each toggle calls
        setShortlistedShops immediately (adr/0049 decision 1) -- there is no
        separate submit step. Clicks the first ``n`` currently-rendered
        toggles in DOM order: gatheringMode's own contract correlates no
        known shopId to a card via any DOM attribute, so which shops end up
        selected is discovered afterward via the public getGathering
        readback, not chosen by name in advance (only safe for n <= 5, the
        confirmed date's OWN open-shop count only when that count is itself
        <= candidate-search-api.yaml's 5-item display cap -- e.g. Monday/
        Tuesday's 5, not Thursday's 6 -- so every rendered card really is
        one of that date's open shops with none held back by the cap).
        """
        toggles = wait_for_at_least_one(self.page, CANDIDATE_CARD_GATHERING_TOGGLE)
        for index in range(n):
            toggle = toggles.nth(index)
            expect(toggle).to_have_attribute(CANDIDATE_GATHERING_SHORTLISTED_ATTR, "false")
            toggle.click()
            expect(toggle).to_have_attribute(CANDIDATE_GATHERING_SHORTLISTED_ATTR, "true")
        gathering = self.refresh_gathering_from_api()
        selected = [shop["shopId"] for shop in gathering["shortlistedShops"]]
        self.assertions.assertEqual(len(selected), n)
        return selected

    def assert_gathering_mode_shows_map_and_shop_details(self) -> None:
        """TDR-GTH-38: candidate-search-browser-interface.yaml's own map and
        per-card detail fields (walking time, seating tier, non-smoking,
        dinner budget, provider page link) are unchanged by adr/0049 -- this
        checks their presence from gatheringMode, not this file's own
        (now-retired) shortlistSelection map/detail rendering. This only
        asserts presence (not exact values, e.g. provider-page href) --
        candidate_search_browser.py's own TDR-CS suite already checks those
        values against candidate-search-api.yaml's own response, and this
        file does not import that sibling module (module-boundary note).
        """
        assert_present(self.assertions, self.page, CANDIDATE_MAP)
        cards = wait_for_at_least_one(self.page, CANDIDATE_CARD)
        for index in range(cards.count()):
            card = cards.nth(index)
            assert_present(self.assertions, card, CANDIDATE_CARD_WALKING_TIME)
            assert_present(self.assertions, card, CANDIDATE_CARD_TOTAL_SEATS)
            assert_present(self.assertions, card, CANDIDATE_CARD_NON_SMOKING)
            assert_present(self.assertions, card, CANDIDATE_CARD_DINNER_BUDGET)
            assert_present(self.assertions, card, CANDIDATE_CARD_PROVIDER_PAGE_LINK)

    def toggle_off_the_first_shortlisted_candidate_card(self) -> None:
        """gatheringMode.cardToggle's own "press again to remove" behavior
        (TDR-GTH-44, adr/0049 decision 8): toggling a currently-"true" card
        removes it from the gathering's shortlist.
        """
        toggle = self.page.locator(
            f'[data-testid="{CANDIDATE_CARD_GATHERING_TOGGLE}"]'
            f'[{CANDIDATE_GATHERING_SHORTLISTED_ATTR}="true"]'
        ).first
        before = self._read_gathering_mode_band()["shortlisted"]
        toggle.click()
        expect(toggle).to_have_attribute(CANDIDATE_GATHERING_SHORTLISTED_ATTR, "false")
        self.assertions.assertEqual(self._read_gathering_mode_band()["shortlisted"], before - 1)

    def assert_unselected_candidate_card_toggle_is_disabled(self) -> None:
        """TDR-GTH-45 / TDR-CS-19 (adr/0049 decision 8): once
        shortlistedShopCount >= maxShortlistedShops (5), every not-yet-
        selected card's toggle carries the native disabled state -- boundary
        conditions disable, they do not remove the element (this contract's
        established convention, mirrored from deckNavigation.disabledState).
        """
        toggle = self.page.locator(
            f'[data-testid="{CANDIDATE_CARD_GATHERING_TOGGLE}"]'
            f'[{CANDIDATE_GATHERING_SHORTLISTED_ATTR}="false"]'
        ).first
        expect(toggle).to_be_disabled()

    def attempt_set_shortlisted_shops_via_api(self, shop_ids: list[str]) -> CapturedApiResponse:
        return self._api(
            "PUT",
            f"/gatherings/{self.gathering_id}/shortlisted-shops",
            {"shopIds": shop_ids},
            csrf=True,
        )

    def assert_rejected_as_invalid_shop_selection(self, response: CapturedApiResponse) -> None:
        """INVALID_SHOP_SELECTION (400) is shared by setShortlistedShops (an
        out-of-population or out-of-bounds-count shopIds list), setShopVotes,
        and finalizeGathering (either naming a shopId absent from the current
        shortlist) -- reviewer audit Major#3 asked for the two latter triggers
        and the count boundary, not only setShortlistedShops' population
        check TDR-GTH-27 already exercised.
        """
        self.assertions.assertEqual(response.status, 400)
        self.assertions.assertEqual(response.payload["code"], "INVALID_SHOP_SELECTION")

    def assert_rejected_because_not_selecting_shop_phase(
        self, response: CapturedApiResponse
    ) -> None:
        """GATHERING_NOT_IN_SELECTING_SHOP_PHASE (409): setShortlistedShops or
        finalizeGathering called while the gathering has not yet confirmed a
        candidate date (still SCHEDULING) -- reviewer audit Major#3.
        """
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(
            response.payload["code"], "GATHERING_NOT_IN_SELECTING_SHOP_PHASE"
        )

    def assert_rejected_because_shop_voting_not_started(
        self, response: CapturedApiResponse
    ) -> None:
        """SHOP_VOTING_NOT_STARTED (409): setShopVotes or finalizeGathering
        called while Gathering.shortlistedShops is still empty (the organizer
        has not called setShortlistedShops at least once yet) -- reviewer
        audit Major#3.
        """
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "SHOP_VOTING_NOT_STARTED")

    def attempt_finalize_via_api(self, shop_id: str) -> CapturedApiResponse:
        return self._api(
            "POST", f"/gatherings/{self.gathering_id}/finalize", {"shopId": shop_id}, csrf=True
        )

    def replace_shortlisted_shop(self, old_shop_id: str, new_shop_id: str) -> dict:
        """D7 replace (TDR-GTH-31/32). **Rewired 2026-09-09 (adr/0049 decision
        1)**: this file's own shortlistedShopVotes.replaceOpen picker
        (a pending-select-then-submit flow scoped to this dashboard) is
        retired along with the rest of organizerDashboard.shortlistSelection
        -- shop selection, including D7 replace, now happens exclusively on
        candidate-search-browser-interface.yaml's gatheringMode, reached via
        shopSelectionEntry.open. That screen's own contract exposes no
        shopId-to-card DOM correlation (gatheringMode.cardToggle), so this
        file drives the swap directly through setShortlistedShops (the same
        public operation gatheringMode's own cardToggle calls per-card,
        adr/0049 decision 1's cross-file requestBody note: "the complete
        replacement shopIds array") rather than through that screen's own
        per-card toggles -- see fetch_a_shop_id_not_open_on's own docstring
        for why (the 6th, currently-unlisted shop a replace needs is beyond
        candidate-search-api.yaml's 5-item display cap for a 6-open-shop day).
        """
        current = require(self.gathering, "no gathering exists")["shortlistedShops"]  # type: ignore[index]
        current_ids = [shop["shopId"] for shop in current]
        self.assertions.assertIn(old_shop_id, current_ids)
        new_ids = [new_shop_id if shop_id == old_shop_id else shop_id for shop_id in current_ids]
        return self.set_shortlisted_shops_via_api(new_ids)

    def select_shop_for_finalize(self, shop_id: str) -> None:
        item = self.page.locator(
            f'[data-testid="{SHORTLISTED_SHOP_ITEM}"][{SHOP_ID_ATTR}="{shop_id}"]'
        )
        by_test_id(item, FINALIZE_SHOP_SELECT).click()
        expect(by_test_id(item, FINALIZE_SHOP_SELECT)).to_have_attribute(
            FINALIZE_SELECTED_ATTR, "true"
        )

    def submit_finalize(self) -> None:
        by_test_id(self.page, FINALIZE_SUBMIT).click()
        expect(by_test_id(self.page, GATHERING_PHASE_INDICATOR)).to_have_attribute(
            GATHERING_PHASE_ATTR, "FINALIZED"
        )

    def assert_finalized_controls_are_absent(self) -> None:
        """FINALIZED局面で消える操作コントロールの一覧 (adr/0042 決定3): every
        operational control this contract scopes to SCHEDULING/SELECTING_SHOP
        becomes absent once FINALIZED -- only recopy remains reachable (P4,
        exercised separately by TDR-GTH-36).
        """
        assert_all_absent(
            self.assertions,
            self.page,
            [
                CONFIRM_DATE_SELECT,
                ADD_CANDIDATE_DATE_OPEN,
                SHORTLIST_OPEN,
                FINALIZE_SHOP_SELECT,
                FINALIZE_SUBMIT,
                PARTICIPANT_LINK_COPY,
                PARTICIPANT_LINK_REVOKE,
            ],
        )
        tentative_select_purpose = self.page.locator(
            f'[{GATHERING_CONTROL_PURPOSE_ATTR}="gathering-candidate-date-tentative-select"]'
        )
        self.assertions.assertEqual(tentative_select_purpose.count(), 0)

    def attempt_issue_participant_link_via_api(self) -> CapturedApiResponse:
        return self._api(
            "POST", f"/gatherings/{self.gathering_id}/participant-links", {"count": 1}, csrf=True
        )

    def assert_rejected_because_gathering_finalized(self, response: CapturedApiResponse) -> None:
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "GATHERING_FINALIZED")

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

    def first_reachable_schedule_question_candidate_date_id(self) -> str:
        return wait_for_at_least_one(self.page, SCHEDULE_QUESTION).first.get_attribute(
            CANDIDATE_DATE_ID_ATTR
        )

    def assert_first_reachable_schedule_question_matches_start_at_order(
        self, start_at_isos: list[str]
    ) -> None:
        """participantAnswer.scheduleQuestion.orderingInvariant (adr/0048,
        TDR-GTH-43): the reported production defect was this element
        intermittently not found at all, because the one-at-a-time render
        depends on scheduleQuestions' order being deterministic to reliably
        reach a specific candidate date's question first
        (gathering-scheduling-api.yaml's own scheduleQuestions description).
        Same independent-recomputation rationale as
        assert_candidate_date_order_matches_start_at_order above.
        """
        expected_first = self._expected_candidate_date_order(start_at_isos)[0]
        self.assertions.assertEqual(
            self.first_reachable_schedule_question_candidate_date_id(), expected_first
        )

    def assert_first_reachable_schedule_question_unchanged(self, before: str) -> None:
        self.assertions.assertEqual(
            self.first_reachable_schedule_question_candidate_date_id(), before
        )

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
        prohibition than organizerDashboard's own preview, which does show
        names. gathering-open-shop-preview-item/-name (the retired item
        sub-structure this check used to name explicitly, adr/0049 decision
        2) no longer exist anywhere in this contract at all -- checked here
        as literal test ids (not named constants) precisely because they no
        longer denote a real, defined observation surface.
        """
        question = self._schedule_question_locator(candidate_date_id)
        self.assertions.assertEqual(
            question.locator('[data-testid="gathering-open-shop-preview-item"]').count(), 0
        )
        self.assertions.assertEqual(
            self.page.locator('[data-testid="gathering-open-shop-preview-item"]').count(), 0
        )

    def assert_schedule_question_tally(
        self, candidate_date_id: str, *, going: int, maybe: int, not_going: int
    ) -> None:
        """scheduleQuestion.tally's presenceRule (adr/0050 decision 2, TDR-GTH-12):
        always present regardless of this question's own data-your-response
        -- `to_have_count(1)` below fails if the tally is missing, not only
        if its counts are wrong. Its own sibling
        assert_schedule_question_tally_absent (the pre-reversal "answer
        first, then see others" observation) is retired along with this
        Must's own reversal -- no scenario names an UNANSWERED question
        whose tally is absent any longer.
        """
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

    # answerLater / peekResults (adr/0050 decision 1) ------------------------

    def assert_answer_later_and_peek_results_present(self) -> None:
        """Both share one presenceRule: present exactly when
        ParticipantView.decision is null (the same phase scheduleQuestion/
        shopVoteQuestion render in)."""
        assert_all_present(self.assertions, self.page, [ANSWER_LATER, PEEK_RESULTS])

    def assert_answer_later_and_peek_results_absent(self) -> None:
        """Mirrors nameControl.open's own presenceRule once finalized --
        both controls disappear once ParticipantView.decision is non-null."""
        assert_all_absent(self.assertions, self.page, [ANSWER_LATER, PEEK_RESULTS])

    def activate_answer_later_and_verify_it_changes_no_state(
        self, candidate_date_id: str, expected_response: str
    ) -> None:
        """answerLater.requiredOutcome: reveals a confirmation surface with
        non-empty text and calls no public operation -- checked here as
        "the already-recorded answer is unchanged by activating it" (this
        suite has no network-interception convention in this file the way
        candidate_search_browser.py's _perform_without_candidate_request
        does; before/after DOM comparison of the one value this action could
        plausibly disturb is the equivalent proof for this contract).
        """
        by_test_id(self.page, ANSWER_LATER).click()
        confirmation = assert_present(self.assertions, self.page, ANSWER_LATER_CONFIRMATION)
        self.assertions.assertNotEqual(confirmation.inner_text().strip(), "")
        self.assert_schedule_question_your_response(candidate_date_id, expected_response)

    def activate_peek_results_and_verify_tallies_are_visible(self, candidate_date_id: str) -> None:
        """peekResults.requiredOutcome: makes every currently reachable
        gathering-schedule-tally/gathering-shop-vote-tally simultaneously
        visible in the DOM. scheduleQuestion.tally/shopVoteQuestion.tally
        are already unconditionally present as of adr/0050 decision 2 (this
        suite's own assert_schedule_question_tally/assert_shop_vote_tally
        already prove DOM presence elsewhere) -- this checks the property
        peekResults specifically adds: actual Playwright visibility (not
        merely DOM attachment), for whichever tallies are currently
        reachable, after activation.
        """
        by_test_id(self.page, PEEK_RESULTS).click()
        tally = self._schedule_question_locator(candidate_date_id).locator(
            f'[data-testid="{SCHEDULE_TALLY}"]'
        )
        expect(tally).to_be_visible()

    # unexpectedLoadFailureOutcome / loadFailure (TDR-GTH-42, adr/0047) -----

    def assert_participant_load_failure_notice_is_shown(self) -> None:
        """browserControlSurface.participantAnswer.loadFailure.requirement:
        gathering-participant-load-error is present and carries some visible
        text (the contract deliberately does not fix the exact Japanese
        wording, only its meaning -- "loading failed, reopening later may
        work" -- which is not itself mechanically checkable; see this
        round's report).
        """
        notice = assert_present(self.assertions, self.page, PARTICIPANT_LOAD_ERROR)
        self.assertions.assertNotEqual(notice.inner_text().strip(), "")

    def assert_participant_load_failure_hides_questions(self) -> None:
        """TDR-GTH-42 Then#2: "日程や店についての設問は示されない" --
        unexpectedLoadFailureOutcome.absent lists both
        gathering-schedule-question and gathering-shop-vote-question.
        """
        assert_all_absent(self.assertions, self.page, [SCHEDULE_QUESTION, SHOP_VOTE_QUESTION])

    def assert_participant_load_failure_has_no_retry_control(self) -> None:
        """TDR-GTH-42 Then#3: "やり直すための操作は示されない" ==
        browserControlSurface.participantAnswer.loadFailure.noRetryControl
        (human ruling 2026-09-06, presented alongside a rejected "add a
        retry button" alternative): no purpose-declared control exists at
        all. This is a stronger, scenario-specific check than
        assert_gathering_screen_has_no_forbidden_surfaces' general "every
        present control declares an allowed purpose" scan -- that scan would
        only catch a retry control that omits data-gathering-control-purpose
        entirely, not one that borrows an existing allowed purpose (e.g.
        gathering-participant-link-recopy's) to slip past it. This instead
        asserts the fact the contract actually states: the loadFailure
        screen carries *no* operational control, full stop.
        """
        self.assertions.assertEqual(self.page.locator(GATHERING_FORM_CONTROL_SELECTOR).count(), 0)

    def assert_participant_load_failure_is_exclusive_of_other_outcomes(self) -> None:
        """browserEntry.participantAnswer.unexpectedLoadFailureOutcome
        (adr/0047): validLinkOutcome, invalidLinkOutcome, and this outcome
        are declared mutually exclusive and, together with each element's
        own presenceRule, exhaustive -- opening a participant link always
        yields exactly one of the three. This asserts every element the
        other two outcomes require is absent whenever loadFailure applies:
        the header and name-open control (validLinkOutcome/
        invalidLinkOutcome), linkError itself (invalidLinkOutcome), and the
        finalized decision summary (a fourth, decision-dependent surface
        this contract's presenceRule chain could otherwise leave standing).
        Mirrors assert_participant_link_error's own absence list for the
        sibling invalidLinkOutcome, extended to cover the additional
        surfaces this newer, broader exclusion names.
        """
        assert_all_absent(
            self.assertions,
            self.page,
            [
                PARTICIPANT_HEADER,
                PARTICIPANT_NAME_OPEN,
                PARTICIPANT_LINK_ERROR,
                PARTICIPANT_DECISION,
            ],
        )

    def assert_participant_load_failure_discloses_no_technical_detail(self) -> None:
        """loadFailure.requirement's disclosure discipline (adr/0047): "It
        must not disclose any technical or internal detail -- an HTTP
        status code, an exception message or stack trace, a request/trace
        identifier, a hostname, or any of
        profiles.localAcceptance.syntheticDisclosureCanaries' values". The
        canary-value half of this is already exercised by
        assert_gathering_screen_has_no_forbidden_surfaces (reused by every
        TDR-GTH-42 test alongside this call); this method exercises the
        remainder, which no existing gathering-scheduling check covers.
        The HTTP-status check is necessarily a heuristic (a bare 3-digit
        4xx/5xx-shaped number in the visible text) rather than a proof that
        no status code could ever leak in some other format -- the
        contract's own wording ("an HTTP status code") does not define a
        stricter observable than this.
        """
        notice = assert_present(self.assertions, self.page, PARTICIPANT_LOAD_ERROR)
        visible_text = notice.inner_text()
        self.assertions.assertNotRegex(visible_text, r"\b[45]\d{2}\b")
        forbidden_substrings = [
            "Traceback",
            "traceback",
            "Exception",
            "exception",
            "stack trace",
            "Stack Trace",
            "trace-id",
            "traceId",
            "trace_id",
            "request-id",
            "requestId",
            "request_id",
            "correlation-id",
        ]
        for forbidden in forbidden_substrings:
            self.assertions.assertNotIn(forbidden, visible_text)
        host = urlparse(self.base_url).hostname
        if host:
            self.assertions.assertNotIn(host, visible_text)

    # Shop-vote / finalized-decision (participant UI, TDR-GTH-28/29/30/34/37/
    # 39/41, adr/0042/0044/0045 -- three-tier vote, near-first stable order,
    # map/detail fields, search-origin marker) -------------------------------

    def _shop_vote_question_locator(self, shop_id: str) -> Locator:
        return self.page.locator(
            f'[data-testid="{SHOP_VOTE_QUESTION}"][{SHOP_ID_ATTR}="{shop_id}"]'
        )

    def answer_shop_vote_question(self, shop_id: str, status: str) -> None:
        """gathering-shop-vote-select's requiredOutcome (adr/0044, restructured
        2026-09-05 from a single toggling checkbox to three sibling options,
        mirroring scheduleQuestion.responseOptions' own shape): calls
        setShopVotes immediately on every activation (no separate submit
        control, Vote.dc.html's "選ぶとその場で保存されます").
        """
        question = self._shop_vote_question_locator(shop_id)
        expect(question).to_be_attached()
        option = question.locator(
            f'[data-testid="{SHOP_VOTE_OPTION}"][{VOTE_VALUE_ATTR}="{status}"]'
        )
        option.click()
        expect(question).to_have_attribute(YOUR_VOTE_ATTR, status)

    def answer_shop_vote_questions(self, votes: dict[str, str]) -> None:
        for shop_id, status in votes.items():
            self.answer_shop_vote_question(shop_id, status)

    def assert_shop_vote_your_vote(self, shop_id: str, expected: str) -> None:
        expect(self._shop_vote_question_locator(shop_id)).to_have_attribute(
            YOUR_VOTE_ATTR, expected
        )

    def assert_shop_vote_tally(
        self, shop_id: str, *, want_to_go: int, ok_to_go: int, not_going: int, responded: int
    ) -> None:
        """Fixed 2026-09-05 (adr/0044): three-tier tally, replacing the retired
        single data-approval-count -- mirrors this same shop's organizer-
        facing ShortlistedShop tally exactly (gathering-scheduling-api.yaml's
        own invariant). wantToGoCount + okToGoCount + notGoingCount must
        always equal respondedCount, same invariant its twin
        assert_shortlisted_shop_tally already checks here too, not only
        trusted (reviewer audit Minor#1). **presenceRule reversed 2026-09-09
        (adr/0050 decision 2, TDR-GTH-29)**: always present regardless of
        this question's own data-your-vote -- `to_have_count(1)` below fails
        if the tally is missing. Its own sibling
        assert_shop_vote_tally_absent (the pre-reversal observation) is
        retired along with this Must's own reversal.
        """
        question = self._shop_vote_question_locator(shop_id)
        tally = question.locator(f'[data-testid="{SHOP_VOTE_TALLY}"]')
        expect(tally).to_have_count(1)
        actual_want_to_go = tally.get_attribute(WANT_TO_GO_COUNT_ATTR)
        actual_ok_to_go = tally.get_attribute(OK_TO_GO_COUNT_ATTR)
        actual_not_going = tally.get_attribute(NOT_GOING_COUNT_ATTR)
        actual_responded = tally.get_attribute(RESPONDED_COUNT_ATTR)
        self.assertions.assertEqual(actual_want_to_go, str(want_to_go))
        self.assertions.assertEqual(actual_ok_to_go, str(ok_to_go))
        self.assertions.assertEqual(actual_not_going, str(not_going))
        self.assertions.assertEqual(actual_responded, str(responded))
        self.assertions.assertEqual(
            int(require(actual_want_to_go, "want-to-go count missing"))
            + int(require(actual_ok_to_go, "ok-to-go count missing"))
            + int(require(actual_not_going, "not-going count missing")),
            int(require(actual_responded, "responded count missing")),
        )

    def attempt_set_schedule_response_via_api(
        self, link: dict[str, str], candidate_date_id: str, status: str
    ) -> CapturedApiResponse:
        return self._api(
            "PUT",
            f"/participant-links/{link['token']}/responses/{candidate_date_id}",
            {"status": status},
        )

    def attempt_set_shop_votes_via_api(
        self, link: dict[str, str], votes: dict[str, str]
    ) -> CapturedApiResponse:
        """votes: shopId -> ShopVoteStatus (adr/0044's SetShopVotesRequest.votes,
        replacing the retired boolean approvedShopIds array).
        """
        return self._api(
            "PUT",
            f"/participant-links/{link['token']}/shop-votes",
            {"votes": [{"shopId": shop_id, "status": status} for shop_id, status in votes.items()]},
        )

    def fetch_participant_view_via_api(self, link: dict[str, str]) -> dict:
        """Full getParticipantView payload -- used by TDR-GTH-37/39 to compare
        the DOM against the API's own claimed shopVoteQuestions order/fields
        without assuming a page reload changes anything this contract does
        not otherwise require.
        """
        response = self._api("GET", f"/participant-links/{link['token']}")
        self._assert_api_ok(response, 200, "getParticipantView")
        return response.payload

    # Map / shop-detail fields (TDR-GTH-39, adr/0044) and the search-origin
    # marker (TDR-GTH-41, adr/0045) ------------------------------------------

    def assert_shop_vote_question_list_shows_map_and_shop_details(
        self, link: dict[str, str]
    ) -> None:
        """TDR-GTH-39: shopVoteMap (gathering-shop-vote-map) shows one marker
        per currently rendered gathering-shop-vote-question, correlated by
        data-shop-id, and every question exposes the detail-field test ids
        the contract requires. Same "presence only, except providerPageLink's
        href" convention as assert_open_shop_list_shows_map_and_shop_details
        (this contract does not fix a data-value-state attribute here either).
        """
        nodes = wait_for_at_least_one(self.page, SHOP_VOTE_QUESTION)
        participant_view = self.fetch_participant_view_via_api(link)
        options_by_id = {
            option["shopId"]: option for option in participant_view["shopVoteQuestions"]
        }
        assert_present(self.assertions, self.page, SHOP_VOTE_MAP)
        marker_nodes = wait_for_at_least_one(self.page, SHOP_VOTE_MAP_MARKER)
        marker_ids = [
            marker_nodes.nth(index).get_attribute(SHOP_ID_ATTR)
            for index in range(marker_nodes.count())
        ]
        question_ids = [
            nodes.nth(index).get_attribute(SHOP_ID_ATTR) for index in range(nodes.count())
        ]
        # Reviewer audit Major#1 (same fix as
        # assert_open_shop_list_shows_map_and_shop_details above): sorted-list
        # equality plus an explicit no-duplicates check, matching
        # candidate_search_browser.py's assert_cards_and_map_show_current_
        # proposal precedent -- a set comparison alone would pass even if a
        # marker were duplicated while a different shop's marker were missing.
        self.assertions.assertEqual(sorted(marker_ids), sorted(question_ids))
        self.assertions.assertEqual(len(marker_ids), len(set(marker_ids)))
        for index in range(nodes.count()):
            question = nodes.nth(index)
            shop_id = question.get_attribute(SHOP_ID_ATTR)
            assert_present(self.assertions, question, SHOP_VOTE_QUESTION_WALKING_TIME)
            assert_present(self.assertions, question, SHOP_VOTE_QUESTION_CAPACITY_TIER)
            assert_present(self.assertions, question, SHOP_VOTE_QUESTION_NON_SMOKING)
            assert_present(self.assertions, question, SHOP_VOTE_QUESTION_DINNER_BUDGET)
            link_node = assert_present(
                self.assertions, question, SHOP_VOTE_QUESTION_PROVIDER_PAGE_LINK
            )
            expected_option = require(
                options_by_id.get(shop_id), f"shop {shop_id} not in participant view"
            )
            self.assertions.assertEqual(
                link_node.get_attribute("href"),
                expected_option["providerPageUrl"],  # type: ignore[index]
            )

    def assert_shop_vote_map_shows_search_origin_marker(self) -> None:
        """TDR-GTH-41 (adr/0045): 地図には検索基点の位置も示される. This contract
        does not fix which data attribute, if any, carries the coordinate
        value (mirrors candidate-origin-marker's own precedent) -- presence
        alone is the Must.
        """
        assert_present(self.assertions, self.page, SHOP_VOTE_MAP)
        assert_present(self.assertions, self.page, SEARCH_ORIGIN_MARKER)

    # Near-order stability (TDR-GTH-37, adr/0044) ----------------------------

    def capture_shop_vote_question_order(self) -> list[str]:
        nodes = wait_for_at_least_one(self.page, SHOP_VOTE_QUESTION)
        return [nodes.nth(index).get_attribute(SHOP_ID_ATTR) for index in range(nodes.count())]

    def assert_shop_vote_question_order_matches_participant_view(
        self, link: dict[str, str]
    ) -> None:
        """TDR-GTH-37's own "近い順である" clause is checked the same way
        TDR-GTH-08's own near-order clause already is: self-consistency
        against the API's own claimed order (gathering-scheduling-api.yaml's
        ParticipantView.shopVoteQuestions, itself nearest-first by contract),
        not an independent geographic recomputation -- this suite cannot read
        src/** or the synthetic population's coordinates, the same
        structural limit already recorded for TDR-GTH-08 (activeContext.md).
        """
        participant_view = self.fetch_participant_view_via_api(link)
        expected_ids = [option["shopId"] for option in participant_view["shopVoteQuestions"]]
        self.assertions.assertEqual(self.capture_shop_vote_question_order(), expected_ids)

    def assert_shop_vote_question_order_unchanged(self, before: list[str]) -> None:
        """TDR-GTH-37's own "投票しても変わらない" clause -- fully verifiable
        without needing the population's real coordinates, unlike the
        near-order clause above.
        """
        self.assertions.assertEqual(self.capture_shop_vote_question_order(), before)

    # Finalized decision (TDR-GTH-34, adr/0041/0044/0046) --------------------

    def _read_participant_decision(self) -> dict[str, object]:
        """**Simplified 2026-09-09 (adr/0050 decision 3, TDR-GTH-34)**: no
        longer reads a per-shop breakdown -- gathering-participant-decision-
        shop-vote and decision.yourShopVotes/ParticipantDecisionShopVote are
        all retired. See assert_participant_decision_has_no_shop_breakdown
        below for the accompanying negative assertion.
        """
        node = assert_present(self.assertions, self.page, PARTICIPANT_DECISION)
        return {
            "confirmedCandidateDate": node.get_attribute(GATHERING_CONFIRMED_CANDIDATE_DATE_ATTR),
            "shopId": node.get_attribute(SHOP_ID_ATTR),
            "yourScheduleResponse": node.get_attribute(YOUR_SCHEDULE_RESPONSE_ATTR),
        }

    def assert_participant_decision(
        self,
        *,
        confirmed_candidate_date: str,
        shop_id: str,
        your_schedule_response: str,
    ) -> None:
        decision = self._read_participant_decision()
        self.assertions.assertEqual(decision["confirmedCandidateDate"], confirmed_candidate_date)
        self.assertions.assertEqual(decision["shopId"], shop_id)
        self.assertions.assertEqual(decision["yourScheduleResponse"], your_schedule_response)

    def assert_participant_decision_has_no_shop_breakdown(self) -> None:
        """TDR-GTH-34's simplified Then ("店ごとの回答の一覧は示されない",
        adr/0050 decision 3): the retired per-shop test id must not appear
        anywhere on the page -- checked as a literal string (not a named
        constant) precisely because it no longer denotes a real, defined
        observation surface in this contract.
        """
        self.assertions.assertEqual(
            self.page.locator(f'[data-testid="{RETIRED_PARTICIPANT_DECISION_SHOP_VOTE}"]').count(),
            0,
        )

    def assert_participant_question_surfaces_are_replaced(self) -> None:
        """replacesQuestionSurfaces (adr/0042): once ParticipantView.decision is
        non-null, the per-candidate-date/per-shop breakdowns are fully replaced
        by the flat decision summary above -- this is also how "他の参加者の
        回答や投票は示されない" (TDR-GTH-34) is enforced structurally, not only
        by decision.yourShopVotes' own content.
        """
        assert_all_absent(
            self.assertions,
            self.page,
            [SCHEDULE_QUESTION, SHOP_VOTE_QUESTION, PARTICIPANT_PROGRESS],
        )

    def assert_participant_name_controls_are_absent(self) -> None:
        """nameControl.open/submit's own presenceRule ("Absent once
        ParticipantView.decision is non-null") and adr/0042 決定4's
        "名前を変える操作も置かない" -- not covered by
        assert_participant_question_surfaces_are_replaced above, which checks
        only the schedule/vote/progress surfaces (reviewer audit Major#2).
        """
        assert_all_absent(
            self.assertions, self.page, [PARTICIPANT_NAME_OPEN, PARTICIPANT_NAME_SUBMIT]
        )

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
        GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS *and* its tag/type shape
        matches the contract's own scoping -- a native input whose `type` is
        one of GATHERING_VALUE_ENTRY_INPUT_TYPES (text/date/time/datetime-
        local/number, defaulting to "text" when the attribute is absent), or
        a textarea (reviewer audit Minor#4: the type check was originally
        missing, so a registered test id reused on e.g. an
        <input type="checkbox"> would have wrongly been exempted). The
        exemption never applies to select/checkbox/radio/combobox/listbox/
        range/slider/spinbutton/button or an interactive ARIA role -- those
        keep the general requirement. Any other matched control -- including
        an unregistered native input this contract does not know about --
        still must declare a purpose from GATHERING_ALLOWED_PURPOSES, so a
        silently-added, untracked input is still caught (this is the point
        of ADR-0039's traceability condition, not a blanket input
        exemption).
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
            if tag_name == "input":
                # A native <input> with no explicit type attribute defaults
                # to "text" per the HTML spec.
                input_type = (control.get_attribute("type") or "text").lower()
                is_exempt_shape = input_type in GATHERING_VALUE_ENTRY_INPUT_TYPES
            else:
                is_exempt_shape = tag_name == "textarea"
            is_registered_value_entry_control = (
                test_id in GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS and is_exempt_shape
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
