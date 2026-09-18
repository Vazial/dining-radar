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
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.test import SimpleTestCase
from playwright.sync_api import Locator, Page, Response, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.acceptance.dsl.authentication_browser import AuthenticationBrowserDsl
from tests.acceptance.dsl.browser_mechanics import HttpBrowser, assert_no_content
from tests.acceptance.dsl.business_days import resolve_business_day_iso
from tests.acceptance.dsl.js_browser_mechanics import (
    CapturedApiResponse,
    assert_absent,
    assert_all_absent,
    assert_all_present,
    assert_clipboard_write_received,
    assert_present,
    build_captured_response,
    by_test_id,
    capture_candidate_proposal_response,
    clipboard_write_count,
    csrf_token,
    install_clipboard_write_monitor,
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
# issueDialog (ADR-0061決定1, 2026-09-17: 発行を「発行して小窓が開き、そこで
# コピー」の2段へ分割。participantLinkCopy自身はもうクリップボードへ書き込ま
# ない -- data-issued-link-urlはこの小窓自身に移った).
PARTICIPANT_LINK_ISSUE_DIALOG = "gathering-participant-link-issue-dialog"
PARTICIPANT_LINK_ISSUE_DIALOG_COPY = "gathering-participant-link-issue-dialog-copy"
PARTICIPANT_LINK_ISSUE_DIALOG_CLOSE = "gathering-participant-link-issue-dialog-close"
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
# shopVoteQuestion.tally.totalActiveParticipantCount (added gathering-
# scheduling-browser-interface.yaml 0.15.0 追補12, ADR-0056 decision 9,
# TDR-GTH-56): a per-participant-view constant (same value on every
# gathering-shop-vote-tally in one view), not a per-shop count -- mirrors
# ParticipantView.totalActiveParticipantCount exactly.
TOTAL_ACTIVE_PARTICIPANT_COUNT_ATTR = "data-total-active-participant-count"
# data-current-leader (adr/0050 decision 5): "true" for exactly the first
# item in shortlistedShopVotes.list's own orderingInvariant order. **Reused,
# same attribute name, on gathering-candidate-date (ADR-0060 decision 7,
# TDR-GTH-59..62) and participantAnswer.scheduleQuestion.tally (ADR-0060
# decision 8, TDR-GTH-63) -- a different, two-level goingCount-then-maybeCount
# cascade there, not this shop-side single-summed-value rule.**
CURRENT_LEADER_ATTR = "data-current-leader"
SHORTLIST_OPEN = "gathering-shortlist-open"
FINALIZE_SHOP_SELECT = "gathering-finalize-shop-select"
FINALIZE_SELECTED_ATTR = "data-finalize-selected"
# finalizeSubmit was split 2026-09-12 (ADR-0054 decision 5, human decision:
# the same open-then-confirm two-step pattern deleteGathering already
# establishes) into open/confirm-dialog/confirm/cancel -- the purpose
# gathering-finalize-submit itself was retired, not merely disabled or
# renamed (allowedPurposesNote2026_09_12). RETIRED_FINALIZE_SUBMIT is kept
# only as a negative-assertion literal (mirrors this file's own
# RETIRED_PARTICIPANT_DECISION_SHOP_VOTE treatment below), not as an
# observed surface.
RETIRED_FINALIZE_SUBMIT = "gathering-finalize-submit"
FINALIZE_OPEN = "gathering-finalize-open"
FINALIZE_CONFIRM_DIALOG = "gathering-finalize-confirm-dialog"
FINALIZE_CONFIRM = "gathering-finalize-confirm"
FINALIZE_CANCEL = "gathering-finalize-cancel"
FINALIZE_CHANGES_TABLE = "gathering-finalize-confirm-changes"
# changesTable.row/-before/-after (added gathering-scheduling-browser-
# interface.yaml 0.18.0 追補15) -- see
# assert_finalize_confirm_dialog_shows_changes_summary below for why this
# replaced a same-element "non-empty text somewhere" check.
FINALIZE_CHANGES_ROW = "gathering-finalize-confirm-changes-row"
FINALIZE_CHANGES_ROW_BEFORE = "gathering-finalize-confirm-changes-row-before"
FINALIZE_CHANGES_ROW_AFTER = "gathering-finalize-confirm-changes-row-after"
CHANGE_SUBJECT_ATTR = "data-change-subject"
FINALIZE_CHANGES_SUBJECT_VALUES = frozenset(
    {"participant-link-issuance", "participant-screen", "date-and-shop"}
)
# candidateDateList.removeCandidateDate (ADR-0056 decision 2, TDR-GTH-50/51).
CANDIDATE_DATE_REMOVE = "gathering-candidate-date-remove"
# gathering-shortlisted-shop-item's new fields (ADR-0055 decision 5 / ADR-0056
# decision 5/6, TDR-GTH-38/54/55).
SHOP_NAME_ATTR = "data-shop-name"
WALKING_TIME_MINUTES_ATTR = "data-walking-time-minutes"
ADDED_AFTER_VOTING_STARTED_ATTR = "data-added-after-voting-started"
SHORTLISTED_SHOP_MAP = "gathering-shortlisted-shop-map"
SHORTLISTED_SHOP_MAP_MARKER = "gathering-shortlisted-shop-map-marker"
SHORTLISTED_SHOP_PAGE_LINK = "gathering-shortlisted-shop-page-link"
# participantLinkList.issuanceClosed (ADR-0056 decision 11).
PARTICIPANT_LINK_ISSUANCE_CLOSED = "gathering-participant-link-issuance-closed"
# organizerDashboard.responseTable (ADR-0056 decision 1, TDR-GTH-49).
RESPONSE_TABLE = "gathering-response-table"
RESPONSE_TABLE_ROW = "gathering-response-table-row"
RESPONSE_TABLE_CELL = "gathering-response-table-cell"
RESPONSE_STATUS_ATTR = "data-response-status"
# Calendar month-navigation / remove-selected (ADR-0054 decision 3 / ADR-0056
# decision 3): each screen owns its own, distinct pair of test ids (the same
# "distinct test id per screen, shared input shape" design already governing
# each screen's own day-cell/calendar test ids, adr/0051 decision 1).
GATHERING_CREATE_MONTH_PREVIOUS = "gathering-create-candidate-date-month-previous"
GATHERING_CREATE_MONTH_NEXT = "gathering-create-candidate-date-month-next"
GATHERING_CREATE_REMOVE_SELECTED = "gathering-create-candidate-date-remove-selected"
GATHERING_ADD_MONTH_PREVIOUS = "gathering-add-candidate-date-month-previous"
GATHERING_ADD_MONTH_NEXT = "gathering-add-candidate-date-month-next"
GATHERING_ADD_REMOVE_SELECTED = "gathering-add-candidate-date-remove-selected"
_CALENDAR_MONTH_NEXT_BY_DAY_TEST_ID: dict[str, str] = {}  # populated below, after both day-cell
# test ids are defined (GATHERING_CREATE_CANDIDATE_DATE_DAY/GATHERING_ADD_CANDIDATE_DATE_DAY).

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
# candidate-search-again (adr/0024 decision 4's shownCandidateMemory replay,
# reused unchanged in gathering mode -- this file's own module-boundary
# note) -- used by TDR-GTH-45's shown-pool-priority technique below.
CANDIDATE_SEARCH_AGAIN = "candidate-search-again"
# TDR-GTH-38's own map/detail-field check was retired 2026-09-13 (ADR-0055
# decision 5 / ADR-0056 decision 5): the scenario now names organizerDashboard.
# shortlistedShopVotes' own map/detail fields directly (see
# SHORTLISTED_SHOP_MAP/-MAP_MARKER/-PAGE_LINK above), not gatheringMode's --
# the candidate-card detail-field test ids this section used to name are no
# longer read by this file at all (candidate_search_browser.py's own TDR-CS
# suite still owns them for that screen's own scenarios).

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
# gathering-participant-decision-shop-vote / data-vote-status were retired
# 2026-09-09 (adr/0050 decision 3, TDR-GTH-34 simplification): the finalized
# record no longer carries a per-shop breakdown. data-your-schedule-response
# was retired too, 2026-09-13 (ADR-0055 decision 7, TDR-GTH-34 simplified
# further) -- neither is kept as a named constant any longer (both are
# checked as literal attribute-name/test-id strings in their own negative
# assertions, precisely because they no longer denote real observation
# surfaces -- see assert_participant_decision_has_no_shop_breakdown and
# assert_participant_decision_has_no_own_response_attribute below).
RETIRED_PARTICIPANT_DECISION_SHOP_VOTE = "gathering-participant-decision-shop-vote"
# gathering-participant-decision's own new fields (ADR-0056 decision 10,
# TDR-GTH-52): the decided shop's location, walking-time estimate, and
# provider-page link, plus the two-marker map that shows them.
DECISION_WALKING_TIME_ATTR = "data-walking-time-minutes"
PARTICIPANT_DECISION_MAP = "gathering-participant-decision-map"
PARTICIPANT_DECISION_MAP_MARKER = "gathering-participant-decision-map-marker"
PARTICIPANT_DECISION_ORIGIN_MARKER = "gathering-participant-decision-origin-marker"
PARTICIPANT_DECISION_PROVIDER_PAGE_LINK = "gathering-participant-decision-page-link"
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
# organizerGatheringCreate.review (ADR-0060 decision 5): "つくる" is now
# open-then-confirm -- gathering-create-submit (unchanged test id/purpose)
# moves inside gathering-create-review-dialog, reachable only through
# gathering-create-review-open. gathering-create-candidate-date-remove-
# selected (unchanged test id/purpose too) moves into this same dialog,
# see GATHERING_CREATE_REMOVE_SELECTED below (already defined for the
# calendar day-cell mapping, now re-scoped to this dialog).
GATHERING_CREATE_REVIEW_OPEN = "gathering-create-review-open"
GATHERING_CREATE_REVIEW_DIALOG = "gathering-create-review-dialog"
GATHERING_CREATE_REVIEW_CANCEL = "gathering-create-review-cancel"
GATHERING_CREATE_REVIEW_MONTH_PREVIOUS = "gathering-create-review-month-previous"
GATHERING_CREATE_REVIEW_MONTH_NEXT = "gathering-create-review-month-next"
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
# data-holiday (ADR-0060 decision 2): "true"/"false", both calendars' dayCell.
CALENDAR_DAY_HOLIDAY_ATTR = "data-holiday"
# Populates the forward-declared dict above (ADR-0054 decision 3 / ADR-0056
# decision 3): which screen's own month-next control to activate when a
# given day-cell test id's target date is not yet on screen.
_CALENDAR_MONTH_NEXT_BY_DAY_TEST_ID.update(
    {
        GATHERING_CREATE_CANDIDATE_DATE_DAY: GATHERING_CREATE_MONTH_NEXT,
        GATHERING_ADD_CANDIDATE_DATE_DAY: GATHERING_ADD_MONTH_NEXT,
    }
)
_CALENDAR_MAX_MONTH_ADVANCES = 13
# Which screen's own removeSelected control observes that screen's day-cell
# selection state across every month at once (removeSelected.requirement,
# ADR-0056 decision 3: "regardless of which month is currently displayed") --
# used below instead of a single-month day-cell DOM snapshot, which only ever
# reflects whichever one month the calendar last paged to (TDR-GTH-46
# integration finding, orchestrator L4 run: a two-month-spanning batch's
# earlier-month selection silently dropped out of a same-month-only read).
# Each removeSelected instance also now carries its own data-date (contract
# 0.19.0, closing 独立監査 audit-gathering-redesign-steps.md's Minor finding:
# the prior month-rewind-and-revisit read this file used to correlate each
# instance to a date rested on an assumption -- a 13-navigation round trip
# always suffices -- this contract's monthNavigation does not guarantee a
# floor for; see _selected_calendar_days below, which replaces that routine).
_CALENDAR_REMOVE_SELECTED_BY_DAY_TEST_ID: dict[str, str] = {
    GATHERING_CREATE_CANDIDATE_DATE_DAY: GATHERING_CREATE_REMOVE_SELECTED,
    GATHERING_ADD_CANDIDATE_DATE_DAY: GATHERING_ADD_REMOVE_SELECTED,
}

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
# ADR-0059 decision 2 (2026-09-16): candidate-gathering-entry is now
# exclusive to renderModes.twoColumnLayout (it previously rendered
# viewport-independently, ADR-0054 decision 1) -- duplicated from
# candidate_search_browser.py's own DESKTOP_TWO_COLUMN_VIEWPORT rather than
# imported (this pair of DSL files' established precedent, see this
# section's own header comment above), chosen deliberately far from any
# plausible breakpoint for the same reason that file states.
CANDIDATE_SEARCH_DESKTOP_TWO_COLUMN_VIEWPORT = {"width": 1440, "height": 900}

# participantAnswer test ids / attributes
PARTICIPANT_HEADER = "gathering-participant-header"
PARTICIPANT_NAME_STATUS = "gathering-participant-name-status"
SCHEDULE_QUESTION = "gathering-schedule-question"
YOUR_RESPONSE_ATTR = "data-your-response"
RESPONSE_OPTION = "gathering-schedule-response-option"
RESPONSE_VALUE_ATTR = "data-response-value"
SCHEDULE_TALLY = "gathering-schedule-tally"
# respondentList (ADR-0061決定2, TDR-GTH-64): peer-to-peer visibility of each
# respondent's own name and answer for this candidate date.
RESPONDENT_LIST = "gathering-schedule-respondent-list"
RESPONDENT_ITEM = "gathering-schedule-respondent-item"
# progress (unchanged shape, now also read by the day-navigation Musts below).
TOTAL_CANDIDATE_DATES_ATTR = "data-total-candidate-dates"
ANSWERED_CANDIDATE_DATES_ATTR = "data-answered-candidate-dates"
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

# daySkip / dayPrevious / dayList (ADR-0061決定3, 2026-09-17 human decision:
# 「1日ずつ、答えると自動で次の日へ」). Replaces answerLater/peekResults
# (gathering-participant-answer-later/-peek-results and their confirmation
# echo), retired entirely the same round -- every prior answer already saves
# itself the moment it is submitted, so leaving mid-way needs no dedicated
# "answer later" control, and the schedule tally's own always-present
# visibility (adr/0050 decision 2) already made "peek results" moot. Neither
# daySkip/dayPrevious/dayList owns a dedicated TDR-GTH-6x scenario of its own
# (the contract's own note), so this suite verifies their requiredOutcome
# directly as a UI implementation detail, the same precedent TDR-GTH-43's
# ordering check and the retired answerLater/peekResults test already
# established for contract Musts with no scenario of their own.
DAY_SKIP = "gathering-participant-answer-skip"
DAY_PREVIOUS = "gathering-participant-answer-previous"
DAY_LIST = "gathering-participant-day-list"
DAY_LIST_ITEM = "gathering-participant-day-item"

# unavailableControls (both namespaces; gathering-scheduling-browser-interface.yaml).
# Mirrors candidate_search_browser.py's ALLOWED_CONTROL_PURPOSES /
# assert_map_has_no_forbidden_surfaces convention for the sibling contract.
GATHERING_CONTROL_PURPOSE_ATTR = "data-gathering-control-purpose"
# Verified 1:1 against gathering-scheduling-browser-interface.yaml v0.14.0's
# own unavailableControls.allowedPurposes list (33 entries, contract lines
# ~859-879) -- every entry below has a matching contract entry and vice
# versa. **Resynced 2026-09-13** (contracts/REVISION-PLAN.md 2節,
# allowedPurposesNote2026_09_12): v0.11.0 -> v0.14.0 retired 1 entry this
# set previously carried (gathering-finalize-submit, ADR-0054 decision 5 --
# replaced, not merely renamed, by the four-part open/confirm-dialog/
# confirm/cancel sequence below) and added 8 (gathering-create-candidate-
# date-month-navigate/gathering-add-candidate-date-month-navigate,
# gathering-create-candidate-date-remove-selected/gathering-add-candidate-
# date-remove-selected, ADR-0054 decision 3 / ADR-0056 decision 3's calendar
# month-paging and cross-month deselect; gathering-candidate-date-remove,
# ADR-0056 decision 2; gathering-finalize-open/gathering-finalize-confirm/
# gathering-finalize-cancel, ADR-0054 decision 5).
GATHERING_ALLOWED_PURPOSES = {
    "gathering-add-candidate-date-open",
    "gathering-add-candidate-date-submit",
    "gathering-add-candidate-date-cancel",
    "gathering-add-candidate-date-day-select",
    "gathering-add-candidate-date-month-navigate",
    "gathering-add-candidate-date-remove-selected",
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
    "gathering-create-candidate-date-month-navigate",
    "gathering-create-candidate-date-remove-selected",
    "gathering-candidate-date-remove",
    "gathering-create-submit",
    "gathering-create-cancel",
    # organizerGatheringCreate.review (ADR-0060 decision 5, 2026-09-16):
    # "つくる" is now open-then-confirm -- gathering-create-submit above keeps
    # its own purpose unchanged (only its DOM home moves), and these three are
    # new: opening the review dialog, paging its own month state, and
    # cancelling out of it without creating anything.
    "gathering-create-review-open",
    "gathering-create-review-month-navigate",
    "gathering-create-review-cancel",
    # shopSelectionEntry (hoisted out of shortlistedShopVotes 2026-09-09,
    # adr/0049 decision 1) / finalize (open-then-confirm, ADR-0054 decision
    # 5, 2026-09-12) / participant shop-vote (adr/0042, browser-interface
    # v0.5's allowedPurposesNote2026_09_04).
    "gathering-shortlist-open",
    "gathering-finalize-shop-select",
    "gathering-finalize-open",
    "gathering-finalize-confirm",
    "gathering-finalize-cancel",
    "gathering-shop-vote-select",
    # deleteGathering (adr/0050 decision 4, TDR-GTH-48).
    "gathering-delete-open",
    "gathering-delete-confirm",
    "gathering-delete-cancel",
    # daySkip / dayPrevious / dayList (ADR-0061決定3) -- replaces the retired
    # gathering-participant-answer-later/-peek-results entries below this
    # same set used to carry. gathering-participant-day-navigate is shared by
    # every gathering-participant-day-item, the same one-purpose-shared-by-
    # siblings pattern gathering-schedule-response-select already
    # establishes.
    "gathering-participant-answer-skip",
    "gathering-participant-answer-previous",
    "gathering-participant-day-navigate",
    # participantLinkCopy's issueDialog (ADR-0061決定1): the small window's
    # own two controls.
    "gathering-participant-link-issue-dialog-copy",
    "gathering-participant-link-issue-dialog-close",
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
# gathering-scheduling-browser-interface.yaml's own unavailableControls.
# crossFileSharedNavigation note (ADR-0059, 2026-09-16): candidate-search-
# browser-interface.yaml's gatheringEntry elements (menuToggle/menuPanel's
# two destinations on desktop, mobileBar's three children on mobile) are
# now unconditionally present on this file's own three organizer-facing
# screens too, but they declare *that* contract's own
# data-candidate-control-purpose attribute -- "neither" this file's own
# allGatheringScreenFormControlsMustDeclarePurpose scan "nor" its
# allowedPurposes registration applies to them (contract's own wording).
# assert_gathering_screen_has_no_forbidden_surfaces below skips any control
# carrying this attribute, mirroring that explicit carve-out -- candidate_
# search_browser.py's own ALLOWED_CONTROL_PURPOSES/allCandidateScreen...
# scan is the one place these elements' purposes are actually checked.
CANDIDATE_SEARCH_CONTROL_PURPOSE_ATTR = "data-candidate-control-purpose"
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


# ADR-0060 (decision 1/2/4, TDR-GTH-57/58): CandidateDateInput.startAt must
# now be a weekday that is not a Japan public holiday, enforced by both
# createGathering and addCandidateDates. This suite's own Given-state
# construction (GatheringSchedulingBrowserDsl.next_weekday_iso/
# days_from_now_iso/two_business_days_in_the_month_after_iso below, used by
# dozens of TDR-GTH-01..56 scenarios unrelated to this ADR) must not
# accidentally pick a real weekend/holiday date, or those scenarios would
# start failing purely from whichever real calendar date the suite happens to
# run on. **2026-09-18 tester task (orchestrator instruction)**: rather than
# reimplementing an approximation of Japan's public-holiday calendar inside
# test code to avoid that collision (this file's own prior approach, which
# risked silently drifting from whatever the product's bundled holiday data
# actually enforces), these three methods now resolve a candidate date by
# asking the product itself, through business_days.resolve_business_day_iso
# (createGathering's own observable 400 CANDIDATE_DATE_NOT_A_BUSINESS_DAY
# response) -- see that module's own docstring. They are instance methods
# (not free functions) because resolving requires a real, signed-in-organizer
# round trip; every call site already has ``self.dsl``/``self`` available at
# the point it previously called the free function.
_FIXED_HOLIDAYS_MD = [
    (1, 1),  # 元日
    (2, 11),  # 建国記念の日
    (2, 23),  # 天皇誕生日
    (4, 29),  # 昭和の日
    (5, 3),  # 憲法記念日
    (5, 4),  # みどりの日
    (5, 5),  # こどもの日
    (8, 11),  # 山の日
    (11, 3),  # 文化の日
    (11, 23),  # 勤労感謝の日
]


def next_fixed_public_holiday_on_weekday_iso(hour: int = 12) -> str:
    """次に来る、平日に当たる固定祝日 (TDR-GTH-58's Given: 「祝日にあたる平日の
    日付」). Restricted to this file's own _FIXED_HOLIDAYS_MD table (deliberately
    excludes the movable Happy-Monday/equinox holidays) -- this scenario only
    needs one concrete, independently-verifiable holiday date, and a fixed
    calendar date (元日など) is trivially correct for any year. Unlike
    next_weekday_iso/days_from_now_iso below, this one *deliberately* returns
    an actual holiday, unresolved -- it is TDR-GTH-58's own rejection subject,
    not Given-state this suite needs to avoid colliding with. Real calendar
    time only, never a faked server clock -- if a fixed holiday itself falls
    on a weekend, it is skipped (TDR-GTH-57 already covers weekends; this
    scenario is specifically about a holiday that is *also* a weekday).
    """
    today = datetime.now(UTC).date()
    year = today.year
    while True:
        for month, day in sorted(_FIXED_HOLIDAYS_MD):
            candidate = date(year, month, day)
            if candidate > today and candidate.weekday() < 5:
                return datetime(
                    candidate.year, candidate.month, candidate.day, hour, tzinfo=UTC
                ).isoformat()
        year += 1


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
        # ADR-0058 decision 1: participantLinkCopy/recopy must also write the
        # issued URL to the browser clipboard. Installed once, before this
        # page's first navigation, so it is present for every navigation this
        # DSL instance drives.
        install_clipboard_write_monitor(self.page)

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

    # Business-day candidate-date resolution (ADR-0060, business_days module's
    # own docstring) -- every TDR-GTH Given-state builder needing "some future
    # weekday" or "N days from now" candidate date goes through these three
    # methods, never a locally reimplemented holiday calendar. -------------

    def _probe_candidate_date_is_a_business_day(self, iso: str) -> bool:
        """Asks gathering-scheduling-api.yaml itself whether ``iso`` would be
        accepted as a CandidateDateInput.startAt, by actually creating a
        throwaway single-candidate-date gathering and immediately, permanently
        deleting it again (deleteGathering, adr/0050 decision 4) -- leaving no
        state behind for the real scenario under test to trip over. Any
        response other than 201 (accepted) or the documented 400
        CANDIDATE_DATE_NOT_A_BUSINESS_DAY (rejected) is a genuine, unrelated
        problem and fails immediately rather than being mistaken for "try the
        next day".
        """
        probe_title = f"__business-day-probe-{secrets.token_hex(8)}"
        response = self._api(
            "POST",
            "/gatherings",
            {"title": probe_title, "candidateDates": [{"startAt": iso}]},
            csrf=True,
        )
        if response.status == 201:
            cleanup = self._api("DELETE", f"/gatherings/{response.payload['id']}", None, csrf=True)
            self.assertions.assertEqual(
                cleanup.status, 204, f"business-day probe cleanup: {cleanup.body}"
            )
            return True
        if response.status == 400 and response.payload.get("code") == (
            "CANDIDATE_DATE_NOT_A_BUSINESS_DAY"
        ):
            return False
        self.assertions.fail(
            f"business-day probe for {iso} got an unexpected "
            f"{response.status} response: {response.body}"
        )
        raise AssertionError("unreachable")  # self.assertions.fail always raises

    def next_weekday_iso(self, weekday: int, hour: int = 12) -> str:
        """The next future occurrence (never "today") of ``weekday`` (Python's
        date.weekday(): Monday=0 ... Sunday=6) as an RFC3339 string, resolved
        to one gathering-scheduling-api.yaml will actually accept. For a
        weekday value 0-4 (Monday-Friday), advances a full week at a time past
        any occurrence the product itself rejects (step_days=7 preserves the
        same day-of-week, so callers keying OPEN_SHOP_COUNT_BY_WEEKDAY by this
        weekday are unaffected). Weekend values (5=Saturday, 6=Sunday) are
        returned unresolved -- TDR-GTH-57 deliberately needs an actual weekend
        date; it is that scenario's own rejection subject, not Given-state
        this suite needs to avoid colliding with.
        """
        now = datetime.now(UTC)
        days_ahead = (weekday - now.weekday()) % 7 or 7
        seed = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=0, second=0, microsecond=0
        )
        if weekday >= 5:
            return seed.isoformat()
        return resolve_business_day_iso(
            seed.isoformat(), self._probe_candidate_date_is_a_business_day, step_days=7
        )

    def days_from_now_iso(self, days: int, hour: int = 12) -> str:
        """``days`` calendar days from now for ``days <= 0`` (TDR-GTH-47 needs
        an exact "today", unresolved, to test CANDIDATE_DATE_NOT_IN_FUTURE
        regardless of which real weekday "today" happens to be -- it is that
        scenario's own rejection subject). For ``days >= 1``, resolved to one
        gathering-scheduling-api.yaml will actually accept, advancing one
        calendar day at a time past any the product itself rejects -- a
        1-day advance only ever moves a date later, so it cannot invert the
        relative order between two different ``days`` values this suite's own
        before/after-style assertions rely on (a real inversion would require
        every one of ``business_days.MAX_BUSINESS_DAY_ADVANCES`` consecutive
        days to be rejected, which fails loudly on its own).
        """
        seed = (datetime.now(UTC) + timedelta(days=days)).replace(
            hour=hour, minute=0, second=0, microsecond=0
        )
        if days <= 0:
            return seed.isoformat()
        return resolve_business_day_iso(
            seed.isoformat(), self._probe_candidate_date_is_a_business_day, step_days=1
        )

    def two_business_days_in_the_month_after_iso(
        self, reference_iso: str, hour: int = 12
    ) -> tuple[str, str]:
        """Two business days sharing one calendar month strictly after
        ``reference_iso``'s own month -- used by this suite's own
        review-dialog month-paging Must test
        (test_gth_create_review_dialog_pages_by_month_and_lets_the_organizer_
        remove_a_day) to guarantee two selected days land on the *same*
        dialog page while a third, earlier-month day lands on a different
        one. Walks the target month day by day, asking
        _probe_candidate_date_is_a_business_day the same way the two methods
        above do (never a locally reimplemented holiday calendar) until 2
        accepted days are found; bounded to that one month so a defect that
        rejected an entire month fails loudly instead of spilling into the
        next.
        """
        reference = datetime.fromisoformat(reference_iso)
        if reference.month == 12:
            first_of_target_month = reference.replace(
                year=reference.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            first_of_target_month = reference.replace(
                month=reference.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        found: list[str] = []
        cursor = first_of_target_month
        while len(found) < 2:
            if cursor.month != first_of_target_month.month:
                raise AssertionError(
                    f"could not find 2 accepted business days within {first_of_target_month:%Y-%m}"
                )
            candidate_iso = cursor.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()
            if self._probe_candidate_date_is_a_business_day(candidate_iso):
                found.append(candidate_iso)
            cursor = cursor + timedelta(days=1)
        return found[0], found[1]

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

    def given_scheduling_gathering_with_business_days(self, title: str, count: int) -> list[str]:
        """Same Given as given_scheduling_gathering above, for a caller that
        only needs ``count`` ascending business-day candidate dates and does
        not care about their exact values. **Rewritten 2026-09-18 (merge with
        feat/dining-radar-bundle-b-dates)**: reuses this file's own
        days_from_now_iso instance method (business_days.resolve_business_day_iso,
        ADR-0060) instead of a locally reimplemented holiday calendar -- each
        of the ``count`` seeds is spaced 7 calendar days apart, comfortably
        wider than business_days.MAX_BUSINESS_DAY_ADVANCES's own single-day-
        at-a-time resolution window, so resolution can never invert their
        ascending order. Returns the ascending ISO strings that were
        actually accepted.
        """
        candidate_isos = [self.days_from_now_iso(2 + 7 * index) for index in range(count)]
        self._create_gathering(title, candidate_isos)
        return candidate_isos

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
                    "currentLeader": node.get_attribute(CURRENT_LEADER_ATTR) == "true",
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

    def capture_candidate_date_order(self) -> list[str]:
        return [date["id"] for date in self._read_candidate_dates()]

    def _expected_candidate_date_order(self, start_at_isos: list[str]) -> list[str]:
        return [self._candidate_date_id_by_start_at[iso] for iso in sorted(start_at_isos)]

    def assert_candidate_date_order_matches_start_at_order(self, start_at_isos: list[str]) -> None:
        """candidateDateList.orderingInvariant (**changed 2026-09-16, ADR-0060
        decision 6, TDR-GTH-07**: startAt ascending is now the list's own
        primary and only key, replacing adr/0048's goingCount-descending-then-
        startAt-ascending rule -- this assertion's shape is unchanged, only
        what it means changed, from "the tie-break TDR-GTH-43 exercises" to
        "the ordering rule itself"). Checked against the chronological order
        of the exact ISO strings this scenario's own Given supplied -- not
        mere self-consistency against the API's own claimed order the way
        TDR-GTH-08/37's near-order checks work (this suite cannot recompute
        geography, but startAt is data this suite itself chose, so it can
        independently recompute the expected order).
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

    def assert_candidate_date_current_leaders(self, expected_leader_ids: set[str]) -> None:
        """candidateDateList.candidateDate's data-current-leader (ADR-0060
        decision 7, TDR-GTH-59..62): exactly ``expected_leader_ids`` carry
        data-current-leader="true" -- every other currently-present candidate
        date carries "false". Checked as a set-equality against every
        candidate date's own id, not a per-id lookup, so a currentLeader
        wrongly left "true" on an *unexpected* candidate date (over-marking)
        is caught the same way a missing one (under-marking) is.
        """
        actual_leader_ids = {
            date["id"] for date in self._read_candidate_dates() if date["currentLeader"]
        }
        self.assertions.assertEqual(actual_leader_ids, expected_leader_ids)

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

    # organizerDashboard.responseTable (ADR-0056 decision 1, TDR-GTH-49) -----

    def _read_response_table(self) -> dict[str, dict[str, str]]:
        """gathering-response-table's own row/cell shape: one row per
        ParticipantLinkSummary keyed by data-participant-link-id, one cell
        per *answered* candidate date keyed by data-candidate-date-id -- an
        unanswered candidate date has no cell at all (mirrors
        scheduleResponses' own "unanswered dates are not included" shape,
        gathering-scheduling-api.yaml).
        """
        rows = wait_for_at_least_one(self.page, RESPONSE_TABLE_ROW)
        result: dict[str, dict[str, str]] = {}
        for row_index in range(rows.count()):
            row = rows.nth(row_index)
            link_id = row.get_attribute(PARTICIPANT_LINK_ID_ATTR)
            cells = row.locator(f'[data-testid="{RESPONSE_TABLE_CELL}"]')
            result[link_id] = {
                cells.nth(cell_index).get_attribute(CANDIDATE_DATE_ID_ATTR): cells.nth(
                    cell_index
                ).get_attribute(RESPONSE_STATUS_ATTR)
                for cell_index in range(cells.count())
            }
        return result

    def assert_response_table_matches(self, expected: dict[str, dict[str, str]]) -> None:
        """expected: participant-link-id -> {candidate-date-id: status}.
        TDR-GTH-49's own core claim ("誰が・どの候補日に・何と答えたか"):
        keyed by the same data-participant-link-id
        participantLinkList.item.attributes already reads, so this suite can
        correlate the two lists' identical ParticipantLinkSummary rows by
        the actual link a caller issued and answered, not merely by DOM
        position.
        """
        assert_present(self.assertions, self.page, RESPONSE_TABLE)
        self.assertions.assertEqual(self._read_response_table(), expected)

    # organizerDashboard.candidateDateList.removeCandidateDate (ADR-0056
    # decision 2, TDR-GTH-50/51) --------------------------------------------

    def remove_candidate_date(self, candidate_date_id: str) -> None:
        """removeCandidateDate.presenceRule/requiredOutcome (TDR-GTH-50):
        present only for an unconfirmed candidate date while phase is
        SCHEDULING.
        """
        node = self._candidate_date_locator(candidate_date_id)
        remove_control = by_test_id(node, CANDIDATE_DATE_REMOVE)
        expect(remove_control).to_be_enabled()
        remove_control.click()

    def assert_candidate_date_absent(self, candidate_date_id: str) -> None:
        expect(self._candidate_date_locator(candidate_date_id)).to_have_count(0)

    def attempt_remove_candidate_date_via_api(self, candidate_date_id: str) -> CapturedApiResponse:
        """TDR-GTH-51's own contract note: removeCandidateDate.presenceRule
        already makes this control absent once phase leaves SCHEDULING, so
        this bypasses that absence the same way TDR-GTH-20/47 already bypass
        an unreachable UI control to prove the server itself enforces the
        rule.
        """
        return self._api(
            "DELETE",
            f"/gatherings/{self.gathering_id}/candidate-dates/{candidate_date_id}",
            None,
            csrf=True,
        )

    def assert_remove_candidate_date_control_absent(self, candidate_date_id: str) -> None:
        """removeCandidateDate.presenceRule (gathering-scheduling-browser-
        interface.yaml 0.18.0, TDR-GTH-51): once phase has left SCHEDULING
        (confirming a candidate date moves it there in the same operation),
        the removeCandidateDate control is absent entirely for that
        candidate date, not merely disabled -- the same
        absent-rather-than-disabled convention participantLinkList.item.
        revoke already established (ADR-0055 decision 2).
        """
        assert_absent(
            self.assertions,
            self._candidate_date_locator(candidate_date_id),
            CANDIDATE_DATE_REMOVE,
        )

    def assert_remove_candidate_date_rejected_because_not_in_scheduling_phase(
        self, response: CapturedApiResponse
    ) -> None:
        """removeCandidateDate's own named response for exactly this input
        shape, since gathering-scheduling-api.yaml v0.13.0 追補10 (retired
        the CANDIDATE_DATE_CONFIRMED code as unreachable: confirming a
        candidate date moves Gathering.phase off SCHEDULING in the same
        operation, and there is no operation that moves it back, so a
        removeCandidateDate call targeting the confirmed candidate date
        always fails GATHERING_NOT_IN_SCHEDULING_PHASE's own phase check
        first). gathering-scheduling-browser-interface.yaml 0.17.0 追補14
        (commit 4c99644) folded removeCandidateDate.presenceRule's own
        confirmed-candidate-date case into this same, reachable code for
        the identical reason. This assertion previously named
        CANDIDATE_DATE_CONFIRMED, which stopped being reachable from the
        public API in v0.13.0 (integration finding against this contract
        revision).
        """
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "GATHERING_NOT_IN_SCHEDULING_PHASE")

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

    def _advance_calendar_to_month_containing(self, calendar_day_test_id: str, iso: str) -> None:
        """monthNavigation.requiredOutcome (ADR-0054 decision 3 / ADR-0056
        decision 3): the calendar now shows one month at a time and must be
        paged forward to reach a day beyond the initially-displayed month --
        replacing the vendored flatpickr's own three-month-wide default this
        suite's Given dates used to rely on being visible without paging at
        all (FR-033: "テストを通すための選択だった"). The product's own
        default is no longer this suite's to bend to its own convenience
        (this round's own instruction) -- when a Given date happens to fall
        in a later month than the one showing, this suite pages forward
        itself instead. Bounded so a real defect (the cell never appearing
        at all) fails loudly instead of looping forever.
        """
        next_month_test_id = require(
            _CALENDAR_MONTH_NEXT_BY_DAY_TEST_ID.get(calendar_day_test_id),
            f"no month-next control registered for {calendar_day_test_id}",
        )
        cell = self._calendar_day_locator(calendar_day_test_id, iso)
        for _ in range(_CALENDAR_MAX_MONTH_ADVANCES):
            if cell.count() > 0:
                return
            by_test_id(self.page, next_month_test_id).click()
        date_part = datetime.fromisoformat(iso).strftime("%Y-%m-%d")
        self.assertions.fail(
            f"{calendar_day_test_id} cell for {date_part} did not appear within "
            f"{_CALENDAR_MAX_MONTH_ADVANCES} month-next activations"
        )

    def _select_calendar_days(self, calendar_day_test_id: str, isos: list[str]) -> None:
        """Sorts ``isos`` ascending before paging (independent audit
        audit-gathering-redesign-steps.md Minor 1): _advance_calendar_to_
        month_containing only pages forward, so an unsorted or descending
        ``isos`` would make an earlier date unreachable after a later one
        already paged past it. Every current caller already passes isos in
        ascending order, so this sort is defensive only -- it changes no
        caller's observed behavior today, but removes the silent dependency
        on callers maintaining that order themselves.
        """
        for iso in sorted(isos, key=lambda value: datetime.fromisoformat(value)):
            self._advance_calendar_to_month_containing(calendar_day_test_id, iso)
            cell = self._calendar_day_locator(calendar_day_test_id, iso)
            expect(cell).to_be_enabled()
            cell.click()
            expect(cell).to_have_attribute(CALENDAR_DAY_SELECTED_ATTR, "true")

    def _selected_calendar_days(self, calendar_day_test_id: str) -> set[str]:
        """removeSelected.attributes.date (contract 0.19.0, closing 独立監査
        audit-gathering-redesign-steps.md's Minor finding on TDR-GTH-46's
        fragility): each removeSelected instance now carries its own
        data-date, same value/format as dayCell.attributes.date, so the
        full cross-month selected-day set can be read directly from this
        list-like control -- no month navigation needed to verify. Replaces
        this file's previous _selected_calendar_day_count (cardinality
        only) + _rewind_calendar_to_earliest_month/per-date revisit combo
        (both removed): that combination was logically sound (count
        equality plus every expected date individually confirmed selected
        rules out both a missing and an extra selection) but its revisit
        half depended on a 13-navigation round trip always being enough to
        reach every month, an assumption this contract's monthNavigation
        does not guarantee a floor for (independent audit's own reading of
        the risk: not a false-pass risk, but a real implementation could be
        wrongly failed by it). Reading from removeSelected.attributes.date
        directly is immune to that risk and unaffected by the calendar's
        displayed month.
        """
        remove_selected_test_id = require(
            _CALENDAR_REMOVE_SELECTED_BY_DAY_TEST_ID.get(calendar_day_test_id),
            f"no remove-selected control registered for {calendar_day_test_id}",
        )
        items = self.page.locator(f'[data-testid="{remove_selected_test_id}"]')
        return {
            require(
                items.nth(index).get_attribute(CALENDAR_DAY_DATE_ATTR),
                f"{remove_selected_test_id} instance {index} has no {CALENDAR_DAY_DATE_ATTR}",
            )
            for index in range(items.count())
        }

    def _assert_selected_calendar_days_equal(
        self, calendar_day_test_id: str, isos: list[str]
    ) -> None:
        """Confirms the calendar's currently-selected-day set equals exactly
        ``isos`` (by date), read via _selected_calendar_days above -- a
        direct set-equality comparison against removeSelected's own
        data-date attributes, with no dependency on which month the
        calendar currently displays.
        """
        expected_dates = {datetime.fromisoformat(iso).strftime("%Y-%m-%d") for iso in isos}
        self.assertions.assertEqual(
            self._selected_calendar_days(calendar_day_test_id), expected_dates
        )

    def _assert_no_calendar_days_selected(self, calendar_day_test_id: str) -> None:
        """Cross-month equivalent of asserting every day cell reset to
        data-selected="false" -- see _selected_calendar_days above for why
        this reads removeSelected's own data-date attributes instead of a
        single month's day-cell snapshot.
        """
        self.assertions.assertEqual(self._selected_calendar_days(calendar_day_test_id), set())

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
        self._assert_no_calendar_days_selected(GATHERING_ADD_CANDIDATE_DATE_DAY)

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
        (adr/0049 decision 3: "全部やるか全部やめるか"). Reads the post-
        rejection selection via _assert_selected_calendar_days_equal, not a
        single-month day-cell DOM snapshot -- when candidate_date_isos spans
        more than one month, the calendar has already paged forward to the
        last one navigated to, so a same-month-only read silently drops the
        earlier month's still-selected day (orchestrator L4 run against this
        integration, TDR-GTH-46).
        """
        self.assertions.assertEqual(response.status, 409)
        self.assertions.assertEqual(response.payload["code"], "DUPLICATE_CANDIDATE_DATE")
        self.assertions.assertEqual(self._read_candidate_dates(), before_dates)
        assert_present(self.assertions, self.page, GATHERING_ADD_CANDIDATE_DATE_FORM)
        self._assert_selected_calendar_days_equal(
            GATHERING_ADD_CANDIDATE_DATE_DAY, candidate_date_isos
        )

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

    def open_gathering_create_review_dialog(self) -> None:
        """review.open.requiredOutcome (ADR-0060 decision 5): reveals
        gathering-create-review-dialog. Calls no public operation --
        createGathering has not been called yet.
        """
        by_test_id(self.page, GATHERING_CREATE_REVIEW_OPEN).click()
        wait_for_at_least_one(self.page, GATHERING_CREATE_REVIEW_DIALOG)

    def cancel_gathering_create_review_dialog(self) -> None:
        """review.cancel.requiredOutcome: closes the dialog without calling
        createGathering or changing any day cell's data-selected/the name
        input's value.
        """
        by_test_id(self.page, GATHERING_CREATE_REVIEW_CANCEL).click()
        assert_absent(self.assertions, self.page, GATHERING_CREATE_REVIEW_DIALOG)

    def remove_selected_gathering_create_review_item(self, iso: str) -> None:
        """review.dialog.item.requiredOutcome (ADR-0060 decision 5): removes
        the one gathering-create-candidate-date-remove-selected instance
        whose data-date matches ``iso`` -- only reachable while the dialog's
        own monthNavigation is currently displaying that day's month (the
        item's own presenceRule, narrowed from "regardless of which month"
        to this dialog's own month-scoped state).
        """
        date_part = datetime.fromisoformat(iso).strftime("%Y-%m-%d")
        item = self.page.locator(
            f'[data-testid="{GATHERING_CREATE_REMOVE_SELECTED}"][{CALENDAR_DAY_DATE_ATTR}="{date_part}"]'
        )
        expect(item).to_have_count(1)
        item.click()

    def advance_gathering_create_review_month(self, *, forward: bool) -> None:
        """review.dialog.monthNavigation.requiredOutcome: moves this dialog's
        own displayed month to the nearest adjacent month containing at
        least one still-selected day -- independent of
        organizerGatheringCreate.calendar's own month state.
        """
        if forward:
            test_id = GATHERING_CREATE_REVIEW_MONTH_NEXT
        else:
            test_id = GATHERING_CREATE_REVIEW_MONTH_PREVIOUS
        by_test_id(self.page, test_id).click()

    def confirm_gathering_create_review_dialog_via_browser(self) -> None:
        """review.dialog.confirm.requiredOutcome's own click, without waiting
        for a post-navigation readback -- kept separate from
        create_prepared_gathering_via_browser below so a rejection-branch
        caller (whole-batch DUPLICATE_CANDIDATE_DATE/CANDIDATE_DATE_NOT_IN_
        FUTURE/CANDIDATE_DATE_NOT_A_BUSINESS_DAY) can observe the dialog
        remaining present instead.
        """
        by_test_id(self.page, GATHERING_CREATE_SUBMIT).click()

    def create_prepared_gathering_via_browser(self) -> None:
        """TDR-GTH-01, driven end-to-end through organizerGatheringCreate
        (browser-interface.yaml v0.4: "Supports TDR-GTH-01 (now browser-
        verifiable)") instead of createGathering direct-API -- reviewer audit
        Major#2. **Rewritten 2026-09-09 (adr/0051 decision 1)**: fills the
        name, then selects one calendar day per prepared date (replacing the
        retired per-row date inputs and addRow), then submits. **Rewritten
        again 2026-09-16 (ADR-0060 decision 5)**: "つくる" no longer calls
        createGathering directly -- it opens gathering-create-review-dialog,
        whose own gathering-create-submit (same test id/purpose, moved DOM
        home) is what now actually creates the gathering.

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
        self.open_gathering_create_review_dialog()
        self.confirm_gathering_create_review_dialog_via_browser()
        self.await_and_read_back_created_gathering(dates)

    def await_and_read_back_created_gathering(self, created_date_isos: list[str]) -> dict:
        """Shared post-confirm tail (extracted 2026-09-16, ADR-0060 decision 5):
        waits for the post-create navigation, then reads the created gathering
        back through the public getGathering operation (see
        create_prepared_gathering_via_browser's own docstring for why -- a
        real Playwright response body becomes unreadable once its page has
        navigated away).
        """
        wait_for_at_least_one(self.page, GATHERING_PHASE_INDICATOR)
        gathering_id = self._extract_gathering_id_from_dashboard_url()
        response = self._api("GET", f"/gatherings/{gathering_id}")
        self._assert_api_ok(response, 200, "getGathering (post-create readback)")
        assert_matches_openapi_schema(
            response.payload, GATHERING_API_CONTRACT, "#/components/schemas/Gathering"
        )
        self._created_candidate_date_isos.extend(created_date_isos)
        self._set_gathering(response.payload)
        self._created_gatherings.append(response.payload)
        return response.payload

    def gathering_create_review_dialog_selected_days(self) -> set[str]:
        """review.dialog.item's own data-date (ADR-0060 decision 5): every
        gathering-create-candidate-date-remove-selected instance currently in
        the DOM -- scoped to whichever month this dialog's own monthNavigation
        is currently displaying (narrowed 2026-09-16 from the pre-ADR-0060
        "regardless of which month" cross-month read _selected_calendar_days
        above still performs for addCandidateDateForm's own, unmoved
        removeSelected).
        """
        items = self.page.locator(f'[data-testid="{GATHERING_CREATE_REMOVE_SELECTED}"]')
        return {
            require(
                items.nth(index).get_attribute(CALENDAR_DAY_DATE_ATTR),
                f"{GATHERING_CREATE_REMOVE_SELECTED} instance {index} has no "
                f"{CALENDAR_DAY_DATE_ATTR}",
            )
            for index in range(items.count())
        }

    def assert_gathering_create_review_open_is_disabled(self) -> None:
        """review.open.disabledState (**moved 2026-09-16 from gathering-
        create-submit's own disabledState, ADR-0060 decision 5**): this
        control, not confirm inside the dialog, now gates on an empty name
        or fewer than 1 selected day.
        """
        expect(by_test_id(self.page, GATHERING_CREATE_REVIEW_OPEN)).to_be_disabled()

    def assert_gathering_create_submit_is_disabled(self) -> None:
        """review.dialog.confirm.disabledState: gated on fewer than 1
        remaining gathering-create-candidate-date-remove-selected instance
        across every month the dialog can page to (every selected day was
        removed from within the dialog) -- distinct from review.open's own
        disabledState above, which gates reaching the dialog at all.
        """
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

    def _attempt_create_gathering_via_api(
        self, title: str, candidate_date_iso: str
    ) -> CapturedApiResponse:
        return self._api(
            "POST",
            "/gatherings",
            {"title": title, "candidateDates": [{"startAt": candidate_date_iso}]},
            csrf=True,
        )

    def attempt_create_gathering_via_api_with_a_past_candidate_date(
        self, title: str, past_or_today_iso: str
    ) -> CapturedApiResponse:
        return self._attempt_create_gathering_via_api(title, past_or_today_iso)

    def assert_create_rejected_because_date_not_in_future(
        self, response: CapturedApiResponse
    ) -> None:
        """gathering-scheduling-api.yaml's createGathering documents
        CANDIDATE_DATE_NOT_IN_FUTURE under its '400' response (shared with
        REQUEST_REJECTED, distinguished by `code`) -- 409 there is reserved
        for DuplicateCandidateDate only. **Fixed**: this assertion previously
        expected 409, which this same rejection can never carry.
        """
        self.assertions.assertEqual(response.status, 400)
        self.assertions.assertEqual(response.payload["code"], "CANDIDATE_DATE_NOT_IN_FUTURE")

    # TDR-GTH-57/58 (new, ADR-0060 decision 1/2/4): 土日・祝日は候補日にでき
    # ない. Bypasses the calendar entirely, the same technique as the
    # TDR-GTH-47 block just above -- a Saturday/Sunday/holiday day cell
    # carries the native disabled state (dayCell.disabledState) and can never
    # itself be clicked, so this suite proves the server-side rejection
    # directly (CANDIDATE_DATE_NOT_A_BUSINESS_DAY is "the authoritative
    # enforcement", gathering-scheduling-api.yaml's own CandidateDateInput.
    # startAt description). ---------------------------------------------------

    def attempt_create_gathering_via_api_with_a_weekend_candidate_date(
        self, title: str, weekend_iso: str
    ) -> CapturedApiResponse:
        return self._attempt_create_gathering_via_api(title, weekend_iso)

    def attempt_create_gathering_via_api_with_a_holiday_candidate_date(
        self, title: str, holiday_iso: str
    ) -> CapturedApiResponse:
        return self._attempt_create_gathering_via_api(title, holiday_iso)

    def assert_create_rejected_because_not_a_business_day(
        self, response: CapturedApiResponse
    ) -> None:
        """gathering-scheduling-api.yaml's createGathering documents
        CANDIDATE_DATE_NOT_A_BUSINESS_DAY under its '400' response (ADR-0060
        decision 4) -- one code for both a weekend (TDR-GTH-57) and a Japan
        public holiday (TDR-GTH-58), the same "one code, the client
        distinguishes the reason via disabledState/data-holiday" granularity
        CANDIDATE_DATE_NOT_IN_FUTURE already established for today-vs-past.
        """
        self.assertions.assertEqual(response.status, 400)
        self.assertions.assertEqual(response.payload["code"], "CANDIDATE_DATE_NOT_A_BUSINESS_DAY")

    # deleteGathering (TDR-GTH-48, adr/0050 decision 4) ----------------------

    def delete_gathering_via_dashboard(self) -> None:
        """deleteGathering's open-then-confirm two-step pattern (adr/0050
        decision 4, mirroring addCandidateDateForm's own open/submit shape).
        Calls the cross-cutting check while the confirm dialog is open --
        FR-030's repeated lesson: a new screen state (the dialog itself,
        carrying gathering-delete-confirm/-cancel) must be exercised, not
        only the pre- and post-delete dashboard states.

        **Fixed (intermittent net::ERR_ABORTED)**: deleteGathering.confirm.
        requiredOutcome (gathering-scheduling-browser-interface.yaml)
        deliberately leaves the immediate post-delete destination screen
        unspecified -- it fixes only that the gathering subsequently no
        longer appears in organizerGatheringList.list -- so this method must
        not assert or require any particular destination, including
        /gatherings/ itself. It only needs to not return control to its
        caller (assert_gathering_absent_from_list, which navigates to
        organizerGatheringList.list to observe the required outcome) while
        a navigation this same confirm click set in motion is still
        in-flight, because a second, independent navigation racing an
        in-flight one is exactly what Playwright surfaces as
        net::ERR_ABORTED / "interrupted by another navigation".

        page.expect_navigation() (registered *before* the click, per
        Playwright's own documented idiom for a click whose navigation is
        delayed behind an async network call) is what actually closes this
        race: two earlier attempts did not. Reading the DELETE response's
        body first (mirroring _capture_gathering_response below) failed
        deterministically -- not intermittently -- with "Response body is
        not available for a response that was navigated away from", because
        the screen's own client-side navigation had already reclaimed the
        network resource before Playwright's second round-trip
        (Network.getResponseBody) could land. Waiting only for the response
        *event* (no body read) followed by wait_for_load_state("load")
        narrowed the race but did not close it -- wait_for_load_state
        resolves immediately against the page's already-settled state if no
        navigation has started yet at the moment it is called, so it cannot
        by itself wait for a navigation that has not begun. expect_navigation
        avoids this because entering its `with` block subscribes to the
        frame's next navigation event before running the click, so whatever
        the confirm click triggers -- now or a moment later, once its DELETE
        call resolves -- is the exact same navigation this method waits on.
        If the click causes no navigation at all (not currently expected,
        given the confirm click here always triggers one, but not something
        this contract fixes either), expect_navigation times out and that is
        treated as "nothing to wait for", not a failure.
        """
        by_test_id(self.page, GATHERING_DELETE_OPEN).click()
        wait_for_at_least_one(self.page, GATHERING_DELETE_CONFIRM_DIALOG)
        self.assert_gathering_screen_has_no_forbidden_surfaces()
        try:
            with self.page.expect_navigation(wait_until="load"):
                by_test_id(self.page, GATHERING_DELETE_CONFIRM).click()
        except PlaywrightTimeoutError:
            pass

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
        """ADR-0059 decision 2: pins the desktop viewport before navigating,
        since candidate-gathering-entry (this method's own settle point) is
        no longer present under every render mode -- see
        CANDIDATE_SEARCH_DESKTOP_TWO_COLUMN_VIEWPORT above.
        """
        self.page.set_viewport_size(CANDIDATE_SEARCH_DESKTOP_TWO_COLUMN_VIEWPORT)
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
        """1クリック=1本 (D8, ADR-0036決定4). participantLinkCopy.requiredOutcome
        -> issueDialog (**changed 2026-09-17, ADR-0061決定1**: issuing now only
        opens a small window carrying the returned URL on its own
        data-issued-link-url; it no longer writes to the clipboard itself).

        Given-state builder reused by many scenarios that only need one
        issued link to exist (TDR-GTH-16/18/19/36 among others). **Per PR
        #196 audit Minor (ADR-0061 未決事項2)**: this helper no longer
        embeds the clipboard-write assertion -- a shared Given helper
        asserting an implementation detail only TDR-GTH-03/17 actually care
        about made every scenario that merely reuses this helper as a Given
        fail for clipboard reasons unrelated to what it was testing. The
        write itself is asserted by issue_participant_link_and_copy_via_dialog
        below (TDR-GTH-03) and recopy_participant_link_at (TDR-GTH-17),
        each specific to the scenario that actually names it.
        """
        before = self._read_unanswered_summary()
        button = assert_present(self.assertions, self.page, PARTICIPANT_LINK_COPY)
        button.click()
        dialog = assert_present(self.assertions, self.page, PARTICIPANT_LINK_ISSUE_DIALOG)
        expect(dialog).to_have_attribute(ISSUED_LINK_URL_ATTR, re.compile(r".+"))
        url = dialog.get_attribute(ISSUED_LINK_URL_ATTR)
        close = assert_present(self.assertions, self.page, PARTICIPANT_LINK_ISSUE_DIALOG_CLOSE)
        close.click()
        assert_absent(self.assertions, self.page, PARTICIPANT_LINK_ISSUE_DIALOG)
        after = self._read_unanswered_summary()
        self.assertions.assertEqual(after["totalIssuedLinks"], before["totalIssuedLinks"] + 1)
        self.assertions.assertEqual(after["activeIssuedLinks"], before["activeIssuedLinks"] + 1)
        issued = {"token": self._token_from_url(url), "url": url}
        self._issued_order.append(issued)
        return issued

    def issue_participant_link_and_copy_via_dialog(self) -> dict[str, str]:
        """TDR-GTH-03 「そのまま貼り付けて使える状態で得られる」: unlike the
        Given-only helper above, this actually presses issueDialog's own
        「リンクをコピー」(dialogCopy) and asserts the clipboard write it
        carries -- **the Must ADR-0058 originally placed on participantLinkCopy
        itself now lives here, moved by ADR-0061決定1** (not removed; the
        activation that must satisfy it changed).
        """
        before = self._read_unanswered_summary()
        button = assert_present(self.assertions, self.page, PARTICIPANT_LINK_COPY)
        writes_before = clipboard_write_count(self.page)
        button.click()
        dialog = assert_present(self.assertions, self.page, PARTICIPANT_LINK_ISSUE_DIALOG)
        expect(dialog).to_have_attribute(ISSUED_LINK_URL_ATTR, re.compile(r".+"))
        url = dialog.get_attribute(ISSUED_LINK_URL_ATTR)
        copy_button = assert_present(self.assertions, self.page, PARTICIPANT_LINK_ISSUE_DIALOG_COPY)
        copy_button.click()
        assert_clipboard_write_received(self.assertions, self.page, url, writes_before)
        close = assert_present(self.assertions, self.page, PARTICIPANT_LINK_ISSUE_DIALOG_CLOSE)
        close.click()
        assert_absent(self.assertions, self.page, PARTICIPANT_LINK_ISSUE_DIALOG)
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

    def read_participant_link_ids_in_order(self) -> list[str]:
        """The DOM order of gathering-participant-link-item's own
        data-participant-link-id (issuedAt ascending) -- used by TDR-GTH-49
        to correlate gathering-response-table's own rows back to a specific
        link this test itself issued and answered, by identity.
        """
        return [item["id"] for item in self._read_participant_link_items()]

    def recopy_participant_link_at(self, index: int) -> str:
        item = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ITEM).nth(index)
        recopy = by_test_id(item, PARTICIPANT_LINK_RECOPY)
        expect(recopy).to_be_enabled()
        writes_before = clipboard_write_count(self.page)
        recopy.click()
        expect(recopy).to_have_attribute(ISSUED_LINK_URL_ATTR, re.compile(r".+"))
        url = recopy.get_attribute(ISSUED_LINK_URL_ATTR)
        # TDR-GTH-17 "再コピーで得たリンクも、そのまま貼り付けて使える状態で得られる"
        # / ADR-0058 decision 1, including once phase is FINALIZED (TDR-GTH-36,
        # recopy.requiredOutcome's own note -- same helper, no separate scenario).
        # since_count matters here specifically: recopy returns the byte-identical
        # URL an earlier issue already wrote (TDR-GTH-17's "あらためて得られる"),
        # so a plain "was this text ever written" check cannot distinguish this
        # activation actually writing from it silently doing nothing.
        assert_clipboard_write_received(self.assertions, self.page, url, writes_before)
        return url

    def revoke_participant_link_at(self, index: int) -> None:
        item = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ITEM).nth(index)
        revoke = by_test_id(item, PARTICIPANT_LINK_REVOKE)
        expect(revoke).to_be_enabled()
        revoke.click()
        expect(item).to_have_attribute(REVOKED_ATTR, "true")

    def assert_revoke_control_absent_at(self, index: int) -> None:
        """participantLinkList.item.revoke's presenceRule, **overturned
        2026-09-12 (ADR-0055 decision 2, human decision "取り消すは未回答の
        行にだけ置く", TDR-GTH-20)**: an answered (or already-revoked) row no
        longer carries a *disabled* revoke control -- the element itself is
        absent from that row's DOM. Replaces this file's own retired
        assert_revoke_control_disabled_at, which encoded the now-overturned
        disable-at-the-boundary rule for this control specifically.
        """
        item = wait_for_at_least_one(self.page, PARTICIPANT_LINK_ITEM).nth(index)
        assert_absent(self.assertions, item, PARTICIPANT_LINK_REVOKE)

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
        use fetch_shop_id_closed_only_on (a second, temporary probe
        gathering confirmed on a day whose openShopCount is at or under 5,
        complete, no sampling loss) or, for a shop that is open on *this*
        confirmed date but merely excluded by the display cap,
        fetch_confirmed_date_open_shop_ids_with_a_spare below (adr/0052
        decision 3's shown-pool-priority technique, no probe gathering
        needed).
        """
        gathering = require(self.gathering, "no gathering exists")
        require(gathering["confirmedCandidateDateId"], "no candidate date is confirmed")  # type: ignore[index]
        response = self._api(
            "POST", "/candidate-proposals", {"gatheringId": self.gathering_id}, csrf=True
        )
        self._assert_api_ok(response, 200, "proposeCandidates (gathering mode, given-state)")
        return [candidate["shopId"] for candidate in response.payload["candidates"]]

    def fetch_confirmed_date_open_shop_ids_with_a_spare(self) -> tuple[list[str], str]:
        """Given-state technique for TDR-GTH-31/32 (D7 replace's "1 spare,
        not-yet-shortlisted" shop). **Replaces a retired weekday-probe
        technique** (a since-removed fetch_a_shop_id_not_open_on, built on
        fetch_shop_id_closed_only_on's two-probe-gathering diff) that
        identified a shop merely "not open on Monday" and assumed it would
        therefore also be absent from *this* confirmed Thursday's own
        display-cap sample -- true of the population (Thursday's own 6 shops
        are all open, so that assumption never held for population
        membership) but false of the *sample*: whether that probed shop
        actually survived Thursday's own unseeded 6-into-5 display-cap draw
        was incidental, not guaranteed, and reproduced empirically failing
        (the probed shop appeared in the confirmed date's own 5-shop sample,
        breaking the caller's assertNotIn).

        adr/0052 decision 3's shown-pool-priority technique fixes this
        deterministically instead: round 1 is fetch_confirmed_date_open_shop
        _ids' own single proposeCandidates call (this confirmed date's
        population, capped at 5 of 6 open shops); round 2 replays round 1's
        own providerPageUrl values as shownProviderPageUrls, which
        candidate-search-api.yaml's own shownPoolPriority invariant
        guarantees draws every not-yet-shown candidate first regardless of
        randomSeed -- since the confirmed date's population has exactly 1
        not-yet-shown shop after round 1 (6 total minus the 5 shown), round
        2 is guaranteed (not merely likely) to include it. No probe
        gathering, no weekday assumption -- both rounds run against this
        same, already-confirmed gathering. Returns (round 1's 5 shopIds, the
        guaranteed-spare 6th shopId).
        """
        gathering = require(self.gathering, "no gathering exists")
        require(gathering["confirmedCandidateDateId"], "no candidate date is confirmed")  # type: ignore[index]
        round1 = self._api(
            "POST", "/candidate-proposals", {"gatheringId": self.gathering_id}, csrf=True
        )
        self._assert_api_ok(round1, 200, "proposeCandidates (gathering mode, round 1)")
        round1_candidates = round1.payload["candidates"]
        round1_shop_ids = [candidate["shopId"] for candidate in round1_candidates]
        shown_provider_urls = [candidate["providerPageUrl"] for candidate in round1_candidates]
        round2 = self._api(
            "POST",
            "/candidate-proposals",
            {"gatheringId": self.gathering_id, "shownProviderPageUrls": shown_provider_urls},
            csrf=True,
        )
        self._assert_api_ok(round2, 200, "proposeCandidates (gathering mode, round 2)")
        spare_ids = [
            candidate["shopId"]
            for candidate in round2.payload["candidates"]
            if candidate["shopId"] not in round1_shop_ids
        ]
        self.assertions.assertEqual(
            len(spare_ids),
            1,
            f"expected exactly one shop beyond the display cap, got {spare_ids} "
            f"(round1={round1_shop_ids})",
        )
        return round1_shop_ids, spare_ids[0]

    def set_shortlisted_shops_via_api(self, shop_ids: list[str]) -> dict:
        """Given-state builder for scenarios where setShortlistedShops itself is
        not the action under test (adr/0037 decision 1's public-API path).
        Also used as the WHEN step for D7 replace (TDR-GTH-31/32, adr/0049
        decision 1): the operation itself is unchanged by that decision (only
        the screen calling it moved to candidate-search-browser-interface.
        yaml's gatheringMode) -- see replace_shortlisted_shop's own docstring
        for why this file drives that swap at the API boundary rather than
        through gatheringMode's own cardToggle.
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
        27's `shop_id_closed_only_on` before `organizer_has_a_scheduling_
        gathering` -- would then have candidate_date_id_at(0) resolve to
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
        open_ids = self._probe_open_shop_ids_on(self.next_weekday_iso(open_weekday))
        closed_ids = self._probe_open_shop_ids_on(self.next_weekday_iso(closed_weekday))
        candidates = open_ids - closed_ids
        self.assertions.assertGreaterEqual(
            len(candidates),
            1,
            f"expected at least one shop open on open_weekday but not closed_weekday, got none "
            f"(open={open_ids}, closed={closed_ids})",
        )
        return sorted(candidates)[0]

    def _read_shortlisted_shop_items(self) -> list[dict[str, object]]:
        nodes = wait_for_at_least_one(self.page, SHORTLISTED_SHOP_ITEM)
        result = []
        for index in range(nodes.count()):
            node = nodes.nth(index)
            result.append(
                {
                    "shopId": node.get_attribute(SHOP_ID_ATTR),
                    "name": node.get_attribute(SHOP_NAME_ATTR),
                    "walkingTimeMinutes": int(node.get_attribute(WALKING_TIME_MINUTES_ATTR)),
                    "wantToGoCount": int(node.get_attribute(WANT_TO_GO_COUNT_ATTR)),
                    "okToGoCount": int(node.get_attribute(OK_TO_GO_COUNT_ATTR)),
                    "notGoingCount": int(node.get_attribute(NOT_GOING_COUNT_ATTR)),
                    "respondedCount": int(node.get_attribute(RESPONDED_COUNT_ATTR)),
                    "currentLeader": node.get_attribute(CURRENT_LEADER_ATTR) == "true",
                    "addedAfterVotingStarted": node.get_attribute(ADDED_AFTER_VOTING_STARTED_ATTR)
                    == "true",
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

    def assert_shortlisted_shop_list_shows_map_and_shop_details(self) -> None:
        """TDR-GTH-38, rewritten 2026-09-13 (ADR-0055 decision 5 / ADR-0056
        decision 5, human decision "投票タリー画面にも地図・店の情報を出
        す"): the scenario now names the organizer's own vote-tally view
        (shortlistedShopVotes), not shopSelectionEntry/gatheringMode
        (candidate-search-browser-interface.yaml) which this scenario used
        to open before ADR-0049 retired the organizer's own shop-picking
        screen entirely -- this reverses the 2026-09-05 exclusion this same
        section's own description names ("a designer decision this contract
        reflects, not an oversight" -- ADR-0055 decision 5 finds that
        explanation was itself in error). Cross-checks name/walking-time/
        provider-page-link against gathering-scheduling-api.yaml's own
        getGathering response (not just DOM self-consistency), mirroring
        assert_shop_vote_question_list_shows_map_and_shop_details's
        equivalent cross-check on the participant side.
        """
        gathering = self.refresh_gathering_from_api()
        shops_by_id = {shop["shopId"]: shop for shop in gathering["shortlistedShops"]}
        items = self._read_shortlisted_shop_items()
        self.assertions.assertTrue(items)
        marker_nodes = wait_for_at_least_one(self.page, SHORTLISTED_SHOP_MAP_MARKER)
        marker_ids = [
            marker_nodes.nth(index).get_attribute(SHOP_ID_ATTR)
            for index in range(marker_nodes.count())
        ]
        item_ids = [item["shopId"] for item in items]
        # Reviewer audit Major#1 precedent (assert_shop_vote_question_list_
        # shows_map_and_shop_details above): sorted-list equality plus an
        # explicit no-duplicates check, not a set comparison alone.
        self.assertions.assertEqual(sorted(marker_ids), sorted(item_ids))
        self.assertions.assertEqual(len(marker_ids), len(set(marker_ids)))
        for item in items:
            shop = require(
                shops_by_id.get(item["shopId"]),
                f"shop {item['shopId']} missing from getGathering's shortlistedShops",
            )
            self.assertions.assertEqual(item["name"], shop["name"])
            self.assertions.assertEqual(item["walkingTimeMinutes"], shop["walkingTimeMinutes"])
            node = self.page.locator(
                f'[data-testid="{SHORTLISTED_SHOP_ITEM}"][{SHOP_ID_ATTR}="{item["shopId"]}"]'
            )
            link = assert_present(self.assertions, node, SHORTLISTED_SHOP_PAGE_LINK)
            self.assertions.assertEqual(link.get_attribute("href"), shop["providerPageUrl"])

    def assert_no_shortlisted_shop_is_current_leader(self) -> None:
        """data-current-leader (**corrected 2026-09-12, ADR-0055 decision 6,
        human decision "票を入れた瞬間に嘘の最有力が出る"**, overturning the
        original always-first-item rule this file's own retired
        assert_shortlisted_shop_current_leader enforced): every item whose
        data-responded-count is "0" carries data-current-leader="false"
        regardless of DOM position (TDR-GTH-54).
        """
        items = self._read_shortlisted_shop_items()
        self.assertions.assertTrue(items, "no shortlisted shop is present to check")
        self.assertions.assertTrue(
            all(item["respondedCount"] == 0 for item in items),
            "this assertion only applies while every shortlisted shop is unanswered",
        )
        self.assertions.assertFalse(any(item["currentLeader"] for item in items))

    def assert_shortlisted_shop_current_leaders_are(self, expected_leader_ids: set[str]) -> None:
        """data-current-leader's tie handling (ADR-0055 decision 6, TDR-GTH-55):
        every item sharing the highest wantToGoCount + okToGoCount among
        items with a non-zero data-responded-count is "true" (a tie
        produces more than one "true" item, all of them); every other item
        is "false". Replaces this file's own retired
        assert_shortlisted_shop_current_leader, whose "exactly one shopId
        leads" shape cannot express a tie at all.
        """
        items = self._read_shortlisted_shop_items()
        leaders = {item["shopId"] for item in items if item["currentLeader"]}
        self.assertions.assertEqual(leaders, expected_leader_ids)

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

    def toggle_one_not_yet_shortlisted_candidate_card_and_return_ref(self) -> str:
        """gatheringMode.cardToggle's requiredOutcome (TDR-GTH-44, ADR-0057's
        2026-09-13 Given rewrite: "すでに別の1件を会に入れている" -- this
        screen may already show one shortlisted card when this is called,
        so the target must be found by its own data-gathering-shortlisted
        attribute rather than assumed to be at a fixed index (unlike
        select_first_n_candidates_into_gathering above, whose n<=5 callers
        all start from an empty shortlist).

        Scoped *within* the target card (mirrors candidate_search_browser.
        py's identical toggle_a_not_yet_shortlisted_card_and_return_ref,
        this pair of DSL files' established precedent for reading a card's
        own data-candidate-ref rather than assuming index stability) so the
        caller can later toggle the *same* card back off by ref even once a
        second card is also shortlisted (see
        toggle_off_candidate_card_by_ref below) -- an index- or
        attribute-filtered locator would retarget once this click flips
        this card's own attribute, matching a different still-"true" card
        instead (the exact bug select_first_n_candidates_into_gathering's
        sibling toggle_off_the_first_shortlisted_candidate_card, which this
        replaces, was written to avoid for a single-shortlisted-card case
        that no longer applies here now that the Given itself always
        shortlists one first).
        """
        cards = wait_for_at_least_one(self.page, CANDIDATE_CARD)
        target_index = next(
            index
            for index in range(cards.count())
            if cards.nth(index)
            .locator(f'[data-testid="{CANDIDATE_CARD_GATHERING_TOGGLE}"]')
            .get_attribute(CANDIDATE_GATHERING_SHORTLISTED_ATTR)
            == "false"
        )
        card = cards.nth(target_index)
        candidate_ref = card.get_attribute("data-candidate-ref")
        before = self._read_gathering_mode_band()["shortlisted"]
        toggle = card.locator(f'[data-testid="{CANDIDATE_CARD_GATHERING_TOGGLE}"]')
        toggle.click()
        expect(toggle).to_have_attribute(CANDIDATE_GATHERING_SHORTLISTED_ATTR, "true")
        self.assertions.assertEqual(self._read_gathering_mode_band()["shortlisted"], before + 1)
        return candidate_ref

    def toggle_off_candidate_card_by_ref(self, candidate_ref: str) -> None:
        """Removes the specific card identified by ``candidate_ref`` (returned
        by toggle_one_not_yet_shortlisted_candidate_card_and_return_ref
        above) from the gathering's shortlist -- targeting by
        data-candidate-ref rather than "the first shortlisted card" so this
        removes the shop TDR-GTH-44's own When just added, not the Given's
        pre-existing shortlisted shop (mirrors candidate_search_browser.py's
        identical toggle_off_card_by_candidate_ref for the sibling TDR-CS-20
        scenario on this same screen).
        """
        card = self.page.locator(
            f'[data-testid="{CANDIDATE_CARD}"][data-candidate-ref="{candidate_ref}"]'
        )
        toggle = card.locator(f'[data-testid="{CANDIDATE_CARD_GATHERING_TOGGLE}"]')
        expect(toggle).to_have_attribute(CANDIDATE_GATHERING_SHORTLISTED_ATTR, "true")
        before = self._read_gathering_mode_band()["shortlisted"]
        toggle.click()
        expect(toggle).to_have_attribute(CANDIDATE_GATHERING_SHORTLISTED_ATTR, "false")
        self.assertions.assertEqual(self._read_gathering_mode_band()["shortlisted"], before - 1)

    def search_again_on_shop_selection_entry(self) -> None:
        """ADR-0052 decision 3's shown-pool-priority technique, driven
        through the browser (TDR-GTH-45's own "6th, not-yet-selected shop"
        need, the same one adr/0052 names). **Fixed**: this scenario's
        confirmed Thursday population has 6 open shops against the 5-item
        display cap, so opening shopSelectionEntry draws its own independent
        random 5-of-6 sample -- generally *not* the same 5 a separate, prior
        setShortlistedShops call already shortlisted (two unrelated draws
        from the same population), so whether a not-yet-shortlisted 6th shop
        is even rendered to test disabledState against was previously
        incidental, not guaranteed (reproduced empirically: failed roughly
        2 of 3 runs with "no [data-gathering-shortlisted=false] element
        found" when the two independent draws happened to coincide).
        Clicking candidate-search-again replays this screen's own already-
        accumulated shownCandidateMemory (candidate-search-browser-
        interface.yaml's adr/0024 decision 4 mechanism, reused unchanged in
        gathering mode) -- since the up-to-5 shops this test's own prior
        organizer_selects_first_n_candidates_into_gathering call rendered
        (and therefore already recorded as "shown") are exactly the ones it
        also shortlisted, candidate-search-api.yaml's shownPoolPriority
        invariant guarantees this replay surfaces the confirmed date's one
        not-yet-shown (and therefore not-yet-shortlisted) 6th shop
        deterministically, not merely probably.
        """
        capture_candidate_proposal_response(
            self.page, lambda: by_test_id(self.page, CANDIDATE_SEARCH_AGAIN).click()
        )

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
        per-card toggles -- see fetch_confirmed_date_open_shop_ids_with_a_
        spare's own docstring for why (the 6th, currently-unlisted shop a
        replace needs is beyond candidate-search-api.yaml's 5-item display
        cap for a 6-open-shop day).
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

    def open_finalize_confirmation(self) -> None:
        """shortlistedShopVotes.finalizeOpen.requiredOutcome (ADR-0054 decision
        5, human decision: the same open-then-confirm two-step pattern this
        contract already establishes for deleteGathering, replacing the
        retired single-activation finalizeSubmit, TDR-GTH-53): reveals
        gathering-finalize-confirm-dialog without itself calling
        finalizeGathering.

        Calls the cross-cutting check while the confirm dialog is open --
        the same FR-030 lesson delete_gathering_via_dashboard already
        applies to gathering-delete-confirm-dialog (this file's own
        precedent). Independent audit (audit-gathering-redesign-steps.md
        Major 2) found gathering-finalize-confirm-dialog -- a new DOM
        shape this round introduced (gathering-finalize-confirm-changes-
        row/-row-before/-row-after) -- had never once been scanned while
        open, including by TDR-GTH-53 itself, the one scenario that opens
        it directly. Placed here rather than only in TDR-GTH-53 so every
        caller of finalize_via_dashboard (TDR-GTH-33/34/35/36) gains the
        same coverage without duplicating the call at each call site.
        """
        before_phase = self._read_gathering_phase_from_dom()
        by_test_id(self.page, FINALIZE_OPEN).click()
        wait_for_at_least_one(self.page, FINALIZE_CONFIRM_DIALOG)
        self.assert_gathering_screen_has_no_forbidden_surfaces()
        self.assertions.assertEqual(self._read_gathering_phase_from_dom(), before_phase)

    def assert_finalize_confirm_dialog_shows_changes_summary(self) -> None:
        """finalizeConfirmDialog.changesTable.row (gathering-scheduling-
        browser-interface.yaml 0.18.0 追補15, TDR-GTH-53): **replaces the
        previous same-element "non-empty text somewhere" check**, which
        could not tell "there are three rows" or "each row is the row it
        claims to be" from a single blob of text (this slice's own prior
        tester report flagged this as a gap; 0.18.0 closed it with a
        row-level testId/attribute this suite can now correlate against,
        the same way organizerDashboard.responseTable's row/cell test ids
        already work). Confirms exactly three gathering-finalize-confirm-
        changes-row elements exist, their data-change-subject values equal
        exactly the three subjectValues (no duplicates, so set equality
        proves full coverage), and each row contains exactly one -before
        and one -after element with non-empty visible text.
        """
        changes = assert_present(self.assertions, self.page, FINALIZE_CHANGES_TABLE)
        rows = changes.locator(f'[data-testid="{FINALIZE_CHANGES_ROW}"]')
        expect(rows).to_have_count(3)
        subjects = [
            rows.nth(index).get_attribute(CHANGE_SUBJECT_ATTR) for index in range(rows.count())
        ]
        self.assertions.assertEqual(
            len(subjects), len(set(subjects)), f"duplicate subject: {subjects}"
        )
        self.assertions.assertEqual(set(subjects), set(FINALIZE_CHANGES_SUBJECT_VALUES))
        for index in range(rows.count()):
            row = rows.nth(index)
            before = row.locator(f'[data-testid="{FINALIZE_CHANGES_ROW_BEFORE}"]')
            after = row.locator(f'[data-testid="{FINALIZE_CHANGES_ROW_AFTER}"]')
            expect(before).to_have_count(1)
            expect(after).to_have_count(1)
            self.assertions.assertNotEqual(before.inner_text().strip(), "")
            self.assertions.assertNotEqual(after.inner_text().strip(), "")

    def confirm_finalize(self) -> None:
        """shortlistedShopVotes.finalizeConfirm.requiredOutcome (ADR-0054
        decision 5): only this control actually calls finalizeGathering."""
        by_test_id(self.page, FINALIZE_CONFIRM).click()
        expect(by_test_id(self.page, GATHERING_PHASE_INDICATOR)).to_have_attribute(
            GATHERING_PHASE_ATTR, "FINALIZED"
        )
        assert_absent(self.assertions, self.page, FINALIZE_CONFIRM_DIALOG)

    def cancel_finalize(self) -> None:
        """shortlistedShopVotes.finalizeCancel.requiredOutcome (ADR-0054
        decision 5): closes the dialog without calling finalizeGathering;
        the organizer's pending finalizeSelect choice survives (TDR-GTH-53's
        own re-open-and-confirm path relies on this).
        """
        before_phase = self._read_gathering_phase_from_dom()
        by_test_id(self.page, FINALIZE_CANCEL).click()
        assert_absent(self.assertions, self.page, FINALIZE_CONFIRM_DIALOG)
        self.assertions.assertEqual(self._read_gathering_phase_from_dom(), before_phase)

    def finalize_via_dashboard(self) -> None:
        """End-to-end open-then-confirm helper for scenarios that do not
        themselves examine the confirmation dialog (TDR-GTH-33/34/35/36) --
        replaces this file's own retired single-click submit_finalize.
        """
        self.open_finalize_confirmation()
        self.confirm_finalize()

    def assert_finalized_controls_are_absent(self) -> None:
        """FINALIZED局面で消える操作コントロールの一覧 (adr/0042 決定3, updated
        2026-09-12 for the finalize-open/-confirm-dialog split, ADR-0054
        decision 5, and the new removeCandidateDate control, ADR-0056
        decision 2): every operational control this contract scopes to
        SCHEDULING/SELECTING_SHOP becomes absent once FINALIZED -- only
        recopy remains reachable (P4, exercised separately by TDR-GTH-36).
        Mirrors shortlistedShopVotes.finalizeConfirm.requiredOutcome's own
        exact enumeration of what becomes absent on a successful confirm.
        """
        assert_all_absent(
            self.assertions,
            self.page,
            [
                CONFIRM_DATE_SELECT,
                ADD_CANDIDATE_DATE_OPEN,
                CANDIDATE_DATE_REMOVE,
                SHORTLIST_OPEN,
                FINALIZE_SHOP_SELECT,
                FINALIZE_OPEN,
                FINALIZE_CONFIRM_DIALOG,
                RETIRED_FINALIZE_SUBMIT,
                PARTICIPANT_LINK_COPY,
                PARTICIPANT_LINK_REVOKE,
            ],
        )
        tentative_select_purpose = self.page.locator(
            f'[{GATHERING_CONTROL_PURPOSE_ATTR}="gathering-candidate-date-tentative-select"]'
        )
        self.assertions.assertEqual(tentative_select_purpose.count(), 0)

    def assert_participant_link_issuance_closed_badge_is_shown(self) -> None:
        """participantLinkList.issuanceClosed (ADR-0056 decision 11): present
        exactly when phase is FINALIZED -- a positive signal that issuance
        ending was on purpose, distinct from participantLinkCopy's own mere
        absence (which by itself looked like it might be a bug, per the
        contract's own rationale).
        """
        assert_present(self.assertions, self.page, PARTICIPANT_LINK_ISSUANCE_CLOSED)

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

    def _day_list_item_locator(self, candidate_date_id: str) -> Locator:
        return self.page.locator(
            f'[data-testid="{DAY_LIST_ITEM}"][{CANDIDATE_DATE_ID_ATTR}="{candidate_date_id}"]'
        )

    def _ensure_schedule_question_reachable(self, candidate_date_id: str) -> None:
        """scheduleQuestion.cardinality (**changed 2026-09-17, ADR-0061決定3**):
        exactly one gathering-schedule-question is reachable at a time --
        the simultaneous-render alternative this contract permitted through
        2026-09-16 is gone. Jumps there via dayList's own requiredOutcome
        (「日の一覧から日へ飛ぶ」, calls no public operation, changes no
        data-your-response value) when candidate_date_id is not already the
        currently-reachable one -- deterministic regardless of which date
        auto-advance or a fresh page load happened to leave reachable.
        """
        if self.first_reachable_schedule_question_candidate_date_id() == candidate_date_id:
            return
        day_item = self._day_list_item_locator(candidate_date_id)
        expect(day_item).to_have_count(1)
        day_item.click()
        self.assertions.assertEqual(
            self.first_reachable_schedule_question_candidate_date_id(), candidate_date_id
        )

    def answer_schedule_question(self, candidate_date_id: str, status: str) -> None:
        self._ensure_schedule_question_reachable(candidate_date_id)
        question = self._schedule_question_locator(candidate_date_id)
        option = question.locator(
            f'[data-testid="{RESPONSE_OPTION}"][{RESPONSE_VALUE_ATTR}="{status}"]'
        )
        option.click()
        # responseOptions.requiredOutcome's own auto-advance (ADR-0061決定3)
        # may already have moved the currently-reachable date on to the next
        # one by the time this assertion runs, so this candidate date's own
        # gathering-schedule-question is no longer a reliable read target.
        # dayList's own per-date item (data-your-response) is the surface
        # this contract guarantees stays queryable "regardless of which
        # single date is currently the reachable gathering-schedule-question"
        # -- see assert_schedule_question_your_response below, which shares
        # this same ground truth.
        expect(self._day_list_item_locator(candidate_date_id)).to_have_attribute(
            YOUR_RESPONSE_ATTR, status
        )

    def answer_first_schedule_question(self, status: str) -> str:
        """Answers whichever gathering-schedule-question is currently
        reachable (scheduleQuestion.cardinality, ADR-0061決定3: exactly one
        at a time) -- for a participant who has just opened their link with
        nothing answered yet, this is the first candidate date in
        orderingInvariant order.
        """
        candidate_date_id = self.first_reachable_schedule_question_candidate_date_id()
        self.answer_schedule_question(candidate_date_id, status)
        return candidate_date_id

    def first_reachable_schedule_question_candidate_date_id(self) -> str:
        return wait_for_at_least_one(self.page, SCHEDULE_QUESTION).first.get_attribute(
            CANDIDATE_DATE_ID_ATTR
        )

    def navigate_to_day_via_day_list(self, candidate_date_id: str) -> None:
        """dayList.item.requiredOutcome (「日の一覧から日へ飛ぶ」, ADR-0061決定3):
        public entry point for scenarios that name this navigation directly,
        reusing the same ensure-reachable mechanics answer_schedule_question
        above uses implicitly.
        """
        self._ensure_schedule_question_reachable(candidate_date_id)

    def skip_currently_reachable_schedule_question(self) -> str:
        """daySkip.requiredOutcome (「とばす」, ADR-0061決定3): advances past
        the currently reachable candidate date without answering it. Returns
        the skipped date's own id so a caller can assert its
        data-your-response stayed whatever it already was.
        """
        skipped = self.first_reachable_schedule_question_candidate_date_id()
        by_test_id(self.page, DAY_SKIP).click()
        return skipped

    def go_to_previous_schedule_question(self) -> None:
        """dayPrevious.requiredOutcome (「前の日」, ADR-0061決定3)."""
        by_test_id(self.page, DAY_PREVIOUS).click()

    def assert_day_previous_is_disabled(self) -> None:
        """dayPrevious.disabledState: disabled exactly when the currently
        reachable candidate date is the first in orderingInvariant order.
        """
        expect(by_test_id(self.page, DAY_PREVIOUS)).to_be_disabled()

    def assert_currently_reachable_schedule_question_is(
        self, expected_candidate_date_id: str
    ) -> None:
        self.assertions.assertEqual(
            self.first_reachable_schedule_question_candidate_date_id(), expected_candidate_date_id
        )

    def assert_schedule_progress(self, *, total: int, answered: int) -> None:
        """progress.requirement (gathering-participant-progress): total
        equals the count of ParticipantView.scheduleQuestions, answered
        equals the count among them whose yourResponse is non-null.
        """
        node = assert_present(self.assertions, self.page, PARTICIPANT_PROGRESS)
        self.assertions.assertEqual(node.get_attribute(TOTAL_CANDIDATE_DATES_ATTR), str(total))
        self.assertions.assertEqual(
            node.get_attribute(ANSWERED_CANDIDATE_DATES_ATTR), str(answered)
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
        """Reads the tally from the *currently reachable* gathering-schedule-
        question for this date (ADR-0061決定3: only one is ever reachable at
        once) -- navigates there via dayList first if it is not already the
        one on screen, since the tally lives inside scheduleQuestion, not
        dayList's own per-date item.
        """
        self._ensure_schedule_question_reachable(candidate_date_id)
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
        data-your-response. data-your-response itself is read from dayList's
        own per-date item (see assert_schedule_question_your_response below
        for why that is the ground truth this contract guarantees regardless
        of which single date is currently reachable, ADR-0061決定3).
        """
        return {
            candidate_date_id: {
                "yourResponse": self._day_list_item_locator(candidate_date_id).get_attribute(
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
        self._ensure_schedule_question_reachable(candidate_date_id)
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
        """Reads dayList's own per-date item (data-your-response), not the
        (possibly currently-unreachable, ADR-0061決定3) scheduleQuestion
        element directly -- dayList.item.requirement guarantees "one item
        per CandidateDate ... regardless of which single date is currently
        the reachable gathering-schedule-question", the surface this
        contract actually guarantees is queryable for a date that is not the
        one presently on screen.
        """
        expect(self._day_list_item_locator(candidate_date_id)).to_have_attribute(
            YOUR_RESPONSE_ATTR, expected
        )

    def assert_schedule_question_has_no_open_shop_count(self, candidate_date_id: str) -> None:
        """**Rewritten 2026-09-13 (ADR-0055 decision 1, human decision
        "参加者の画面から『この日に開いている店N件』を消す", gathering-
        scheduling.feature's TDR-GTH-09 rewritten to a negative
        assertion)**: gathering-scheduling-api.yaml removed
        ParticipantScheduleQuestion.openShopCount at v0.11.0;
        gathering-scheduling-browser-interface.yaml 0.18.0 追補15 closed the
        resulting contradiction (this contract had kept requiring an
        attribute equal a value that no longer existed) by requiring this
        element carry **no** data-open-shop-count attribute at all, for
        every reachable gathering-schedule-question regardless of
        data-your-response. Replaces the retired
        assert_schedule_question_open_shop_count, which asserted the
        attribute equalled a specific count -- checked here as a literal
        attribute-name string (not OPEN_SHOP_COUNT_ATTR, which
        organizerDashboard's own gathering-open-shop-preview, TDR-GTH-08,
        still legitimately carries unchanged) precisely because it no
        longer denotes a real observation surface on this element.
        """
        self._ensure_schedule_question_reachable(candidate_date_id)
        node = self._schedule_question_locator(candidate_date_id)
        self.assertions.assertIsNone(node.get_attribute("data-open-shop-count"))

    def assert_schedule_question_no_shop_details(self, candidate_date_id: str) -> None:
        """D6 (2026-08-30): "店名やその他の店舗情報は示されない" -- a stronger
        prohibition than organizerDashboard's own preview, which does show
        names. gathering-open-shop-preview-item/-name (the retired item
        sub-structure this check used to name explicitly, adr/0049 decision
        2) no longer exist anywhere in this contract at all -- checked here
        as literal test ids (not named constants) precisely because they no
        longer denote a real, defined observation surface.
        """
        self._ensure_schedule_question_reachable(candidate_date_id)
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
        self._ensure_schedule_question_reachable(candidate_date_id)
        question = self._schedule_question_locator(candidate_date_id)
        tally = question.locator(f'[data-testid="{SCHEDULE_TALLY}"]')
        expect(tally).to_have_count(1)
        self.assertions.assertEqual(tally.get_attribute("data-going-count"), str(going))
        self.assertions.assertEqual(tally.get_attribute("data-maybe-count"), str(maybe))
        self.assertions.assertEqual(tally.get_attribute("data-not-going-count"), str(not_going))

    def assert_schedule_question_respondents(
        self, candidate_date_id: str, expected: list[dict[str, object]]
    ) -> None:
        """scheduleQuestion.respondentList.item (TDR-GTH-64, ADR-0061決定2):
        one entry per participant who has answered this candidate date
        (this viewer's own entry included if the viewer itself has
        answered), each carrying its own response value and whether it is
        named. DOM order is not fixed by this contract, so this compares as
        an unordered multiset -- not the exact visible name text either
        (this contract does not require it to be machine-asserted, the same
        latitude participantLinkList.item.requirement already takes,
        TDR-GTH-16's own "名無しを含む" distinguishability, not text
        equality).
        """
        self._ensure_schedule_question_reachable(candidate_date_id)
        question = self._schedule_question_locator(candidate_date_id)
        items = question.locator(f'[data-testid="{RESPONDENT_ITEM}"]')
        expect(items).to_have_count(len(expected))
        actual = sorted(
            (
                items.nth(index).get_attribute(RESPONSE_VALUE_ATTR),
                items.nth(index).get_attribute(PARTICIPANT_NAMED_ATTR),
            )
            for index in range(items.count())
        )
        expected_pairs = sorted(
            (entry["response"], "true" if entry["named"] else "false") for entry in expected
        )
        self.assertions.assertEqual(actual, expected_pairs)

    def assert_schedule_question_current_leader(
        self, candidate_date_id: str, expected: bool
    ) -> None:
        """scheduleQuestion.tally's data-current-leader (ADR-0060 decision 8,
        TDR-GTH-63): mirrors gathering-candidate-date's own data-current-
        leader for this same candidate date -- no separate API field, this
        participant-side value is computed from the same
        ParticipantView.scheduleQuestions goingCount/maybeCount this suite's
        organizer-side assertion already reads from CandidateDate.

        **Merge fixup (bundle C, ADR-0061決定3)**: navigates there via
        _ensure_schedule_question_reachable first -- scheduleQuestion.
        cardinality now allows only one candidate date's question reachable
        at a time, so this candidate date's own tally is not necessarily the
        one already on screen.
        """
        self._ensure_schedule_question_reachable(candidate_date_id)
        question = self._schedule_question_locator(candidate_date_id)
        tally = question.locator(f'[data-testid="{SCHEDULE_TALLY}"]')
        expect(tally).to_have_count(1)
        self.assertions.assertEqual(
            tally.get_attribute(CURRENT_LEADER_ATTR), "true" if expected else "false"
        )

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

    def assert_shop_vote_tally_total_active_participant_count(
        self, shop_id: str, expected: int
    ) -> None:
        """shopVoteQuestion.tally.totalActiveParticipantCount (gathering-
        scheduling-browser-interface.yaml 0.15.0 追補12, ADR-0056 decision
        9, TDR-GTH-56): data-total-active-participant-count mirrors
        ParticipantView.totalActiveParticipantCount exactly -- the count of
        issued-and-not-revoked participant links, not the count of every
        link ever issued (Given-state callers should issue at least one
        link that is then revoked, so the two counts differ and this
        assertion cannot pass by accident against the wrong denominator).
        Does not change regardless of how many votes this shop itself has
        gathered (a per-participant-view constant, unlike the other four
        tally attributes assert_shop_vote_tally checks).
        """
        tally = self._shop_vote_question_locator(shop_id).locator(
            f'[data-testid="{SHOP_VOTE_TALLY}"]'
        )
        expect(tally).to_have_attribute(TOTAL_ACTIVE_PARTICIPANT_COUNT_ATTR, str(expected))

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
        all retired. **Simplified further 2026-09-13 (ADR-0055 decision 7,
        TDR-GTH-34)**: yourScheduleResponse/data-your-schedule-response is
        fully removed too -- not merely read as null. **Extended 2026-09-12
        (ADR-0056 decision 10, TDR-GTH-52)**: data-walking-time-minutes is
        new. See assert_participant_decision_has_no_shop_breakdown and
        assert_participant_decision_has_no_own_response_attribute below for
        the accompanying negative assertions.
        """
        node = assert_present(self.assertions, self.page, PARTICIPANT_DECISION)
        return {
            "confirmedCandidateDate": node.get_attribute(GATHERING_CONFIRMED_CANDIDATE_DATE_ATTR),
            "shopId": node.get_attribute(SHOP_ID_ATTR),
            "walkingTimeMinutes": node.get_attribute(DECISION_WALKING_TIME_ATTR),
        }

    def assert_participant_decision(
        self,
        *,
        confirmed_candidate_date: str,
        shop_id: str,
    ) -> None:
        decision = self._read_participant_decision()
        self.assertions.assertEqual(decision["confirmedCandidateDate"], confirmed_candidate_date)
        self.assertions.assertEqual(decision["shopId"], shop_id)

    def assert_participant_decision_has_no_own_response_attribute(self) -> None:
        """**Removed 2026-09-13 (ADR-0055 decision 7, human decision
        "あなたの回答は見れても別に意味ないかも" 再確認, TDR-GTH-34)**:
        data-your-schedule-response no longer exists anywhere on
        gathering-participant-decision at all -- checked as a literal
        attribute-name string (not a named constant) precisely because it no
        longer denotes a real, defined observation surface (mirrors this
        file's own assert_participant_decision_has_no_shop_breakdown
        treatment of a fully-retired sibling surface).
        """
        node = assert_present(self.assertions, self.page, PARTICIPANT_DECISION)
        self.assertions.assertIsNone(node.get_attribute("data-your-schedule-response"))

    def assert_participant_decision_shows_shop_location_details(
        self, *, shop_id: str, walking_time_minutes: int, provider_page_url: str
    ) -> None:
        """TDR-GTH-52 (new, ADR-0056 decision 10): decided shop location and
        walking-time/provider-page-link, cross-checked against
        gathering-scheduling-api.yaml's own getParticipantView response
        rather than only self-consistency (mirrors this file's own
        assert_shop_vote_question_list_shows_map_and_shop_details
        precedent).
        """
        decision = self._read_participant_decision()
        self.assertions.assertEqual(decision["shopId"], shop_id)
        self.assertions.assertEqual(
            decision["walkingTimeMinutes"],
            str(walking_time_minutes),  # type: ignore[arg-type]
        )
        marker = assert_present(self.assertions, self.page, PARTICIPANT_DECISION_MAP_MARKER)
        self.assertions.assertEqual(marker.get_attribute(SHOP_ID_ATTR), shop_id)
        link = assert_present(self.assertions, self.page, PARTICIPANT_DECISION_PROVIDER_PAGE_LINK)
        self.assertions.assertEqual(link.get_attribute("href"), provider_page_url)

    def assert_participant_decision_map_shows_shop_and_origin_only(self) -> None:
        """gathering-participant-decision-map's own scope (ADR-0056 decision
        10, TDR-GTH-52): exactly the decided shop's own pin and this
        participant's search origin -- **no route line or walking-radius
        ring**.

        **Strengthened (independent audit audit-gathering-redesign-steps.md
        Major 1, contract 0.19.0 追補16)**: the candidate-walking-radius-ring
        absence check below only ever proved this map does not leak *that*
        one, unrelated contract's ring test id -- it could not detect an
        implementation drawing its own untagged route line/ring (e.g. a raw
        Leaflet Polyline/Circle carrying no test id at all). 0.19.0 closed
        this by adding data-overlay-marker-count/-line-count/-ring-count to
        gathering-participant-decision-map itself: the product's own running
        count of overlays it drew, independent of whether a given overlay
        kind additionally carries a test id. overlayMarkerCount MUST equal
        "2" (marker + originMarker, forbidding a third untagged marker);
        overlayLineCount/overlayRingCount MUST both equal "0" -- this is the
        DOM-observable form of "描かない" that the walking-radius-ring check
        alone could not provide. The walking-radius-ring check is kept
        alongside, not replaced by, this strengthened check (never weaken an
        existing assertion).
        """
        map_node = assert_present(self.assertions, self.page, PARTICIPANT_DECISION_MAP)
        self.assertions.assertEqual(
            map_node.locator('[data-testid="candidate-walking-radius-ring"]').count(), 0
        )
        self.assertions.assertEqual(map_node.get_attribute("data-overlay-marker-count"), "2")
        self.assertions.assertEqual(map_node.get_attribute("data-overlay-line-count"), "0")
        self.assertions.assertEqual(map_node.get_attribute("data-overlay-ring-count"), "0")
        assert_present(self.assertions, self.page, PARTICIPANT_DECISION_MAP_MARKER)
        assert_present(self.assertions, self.page, PARTICIPANT_DECISION_ORIGIN_MARKER)

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
        """replacesQuestionSurfaces (adr/0042). **Reversed back 2026-09-17
        (ADR-0061決定5, human decision "他の候補の店と票は出さない",
        reversing ADR-0055 decision 8 a second time)**: ADR-0055 decision 8
        (2026-09-12) had excluded gathering-shop-vote-question (and its own
        gathering-shop-vote-tally)/gathering-shop-vote-map from this list to
        resolve a self-contradiction this contract carried since 2026-09-09
        (this entry vs. TDR-GTH-34's own literal text -- see this slice's
        prior tester report). The human has now seen the finalized screen in
        its real board form and chosen to hide every other shop there, so
        this round restores the original list, this time keeping it (no more
        self-contradiction: TDR-GTH-34's text never changed). **Also adds
        gathering-participant-day-list** (new this round, ADR-0061決定3) to
        the schedule-question/progress pair that were already here.
        """
        assert_all_absent(
            self.assertions,
            self.page,
            [
                SCHEDULE_QUESTION,
                PARTICIPANT_PROGRESS,
                DAY_LIST,
                SHOP_VOTE_QUESTION,
                SHOP_VOTE_TALLY,
                SHOP_VOTE_MAP,
            ],
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

        **Fixed (tester diagnostic, 2026-09-17)**: crossFileSharedNavigation's
        own shared elements (candidate-search-browser-interface.yaml's
        gatheringEntry.menuToggle/menuPanel/.../auth-sign-out among them,
        unconditional on every screen this file covers since ADR-0059,
        2026-09-16) declare `data-candidate-control-purpose`, a different
        contract's own purpose attribute -- never this file's own
        `data-gathering-control-purpose`. This scan previously read this
        file's own attribute off every matched control regardless, so a
        shared-nav button (e.g. auth-sign-out) always read back `None` and
        failed the assertIn check below, on every screen this scan ran
        against once organizerDashboard's finalize confirmation (and every
        screen after it) started rendering that shared nav. The contract's
        own words license skipping them entirely here ("no entry for them is
        added here") -- this fix recognizes them by that other attribute's
        presence and skips them, rather than adding their purposes to this
        file's own GATHERING_ALLOWED_PURPOSES (which would wrongly imply this
        file's own contract declares them).
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
            if control.get_attribute(CANDIDATE_SEARCH_CONTROL_PURPOSE_ATTR) is not None:
                # crossFileSharedNavigation (ADR-0059) -- see this module's
                # own CANDIDATE_SEARCH_CONTROL_PURPOSE_ATTR comment above.
                continue
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
