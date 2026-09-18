/**
 * Organizer-dashboard screen behaviour.
 *
 * Implements browserControlSurface.organizerDashboard from
 * contracts/gathering-scheduling-browser-interface.yaml against the public
 * contracts/gathering-scheduling-api.yaml endpoints, using the same
 * JS-executing render / el()-builder / fetch conventions
 * web/static/dining_radar/web/candidate.js already established for
 * candidate-search (ADR-0009 decision 4, this contract's own renderModel).
 *
 * State kept client-side only, never sent to or reflected by the public
 * API (adr/0035 decision 1 item 1, "同時決め"):
 *   - tentativeSelectedId: the one gathering-candidate-date the organizer is
 *     currently cross-checking against shop availability.
 *   - openShopPreview: the last-fetched CandidateDateOpenShopPreview for
 *     that same date, or null.
 * confirmDate's own requiredOutcome explicitly leaves both unaffected, so
 * this script never clears either one as a side effect of a successful
 * confirm-date call.
 *
 * 2026-09-04 addition (adr/0042, contract v0.5): shop shortlisting/approval-
 * voting/finalization. One piece of state is client-side pending selection
 * only:
 *   - finalizeSelectedShopId: the one shopId currently selected by the
 *     gathering-finalize-shop-select radio group, before gathering-finalize-
 *     open is activated.
 *
 * **2026-09-13 (ADR-0054/ADR-0055/ADR-0056, human decision, 実機フィード
 * バック第2段)**: this round's changes, in one place --
 *   - The candidate-date calendar (addCandidateDateForm.calendar) no longer
 *     vendors flatpickr -- see buildCandidateDateCalendar below (the same
 *     "案B｜表" hand-built component gathering_create.js's own copy uses;
 *     duplicated, not imported, per this file's existing no-shared-module
 *     convention).
 *   - candidateDateList.removeCandidateDate (ADR-0056 decision 2): a
 *     previously-added, not-yet-confirmed candidate date can now be taken
 *     back.
 *   - shortlistedShopVotes now shows each shop's name/walking-time/map/
 *     provider-page-link (ADR-0055 decision 5 / ADR-0056 decision 5,
 *     reversing this file's own 2026-09-05 exclusion), fixes
 *     data-current-leader for the 0-vote and tied cases (ADR-0055 decision
 *     6). A same-round addition, an 「あとから入りました」badge computed
 *     client-side (ADR-0056 decision 6), was itself retired 2026-09-17
 *     (ADR-0062 decision 1, board D1) -- see this section's own further
 *     history below.
 *   - finalizeSubmit is replaced by a 4-part open/confirm-dialog/confirm/
 *     cancel flow, the same shape deleteGathering already used (ADR-0054
 *     decision 5).
 *   - participantLinkList.item.revoke is now present only for an unanswered,
 *     unrevoked row (ADR-0055 decision 2, overturning this contract's own
 *     disable-at-the-boundary convention for this one control) and the
 *     panel gains a "発行はおわり" badge once FINALIZED (ADR-0056 decision
 *     11).
 *   - organizerDashboard.responseTable (ADR-0056 decision 1) is new: one row
 *     per participant link, one cell per candidate date that link answered.
 *     Reads ParticipantLinkSummary.scheduleResponses -- **not yet populated
 *     by this deployment's backend** (gathering-scheduling-api.yaml v0.12.0
 *     requires the field, but the Python side of this round is being
 *     implemented in parallel); this file reads `link.scheduleResponses ||
 *     []` defensively so the table renders correctly (as all-empty rows)
 *     until that lands, rather than throwing.
 *
 * **2026-09-17 (ADR-0062, human decision, board D1〜D4)**: shortlistedShopVotes
 * .list.item.detailFields grows five fields (walking time/genre/capacity/
 * non-smoking/dinner-budget) and drops its 「あとから入りました」badge;
 * shortlistedShopVotes now fills its own pane (gth-shop-stage) with the
 * shared map full-bleed and the shop list floating over it, and the confirm/
 * finalize actions move to a bottom-of-pane bar (gth-bottom-bar); the
 * finalize-confirm dialog's 3-row before/after table is replaced by a
 * 2-element confirmSummary (date/shop only), rendered as a viewport-centered
 * modal; and finalizedSummary.decisionBanner gains the decided shop's own
 * name/map/provider-page link while shortlistedShopVotes.list/item stop
 * being present once FINALIZED.
 *
 * data-issued-link-url (participantLinkCopy.requiredOutcome /
 * participantLinkList.item.recopy.requiredOutcome) is likewise tracked in
 * `state` (headerIssuedLinkUrl / recopiedLinkUrls) rather than mutated
 * directly on the clicked DOM node: `render()` fully rebuilds the DOM
 * (`root.innerHTML = ""`) on every state change, including the one
 * triggered by the same issue/recopy action's own follow-up refresh, which
 * previously destroyed the node the attribute had just been set on before
 * a poll could observe it (real-browser measurement, 2026-08-31: Playwright
 * repeatedly re-resolved the test id to a freshly built <button> that never
 * carried the attribute). Baking the value into the element's initial
 * attributes at build time, from state, means every rebuild reproduces it
 * instead of losing it.
 */
(function () {
  "use strict";

  var root = document.getElementById("gathering-app");
  if (!root) {
    return;
  }

  var gatheringId = root.getAttribute("data-gathering-id");

  // ADR-0062 decision 4: this organizer's own configured search origin, for
  // finalizedSummary.decisionBanner.map's own origin marker only -- read
  // once at load from the same json_script embedding holiday_dates above
  // already uses (organizer_dashboard.html/services.organizer_search_origin
  // own docstring explain why). `null` (unresolvable, or the provider
  // population is currently unavailable) simply omits the origin marker
  // below rather than failing anything.
  var organizerSearchOriginNode = document.getElementById("gathering-search-origin");
  var organizerSearchOrigin = organizerSearchOriginNode
    ? JSON.parse(organizerSearchOriginNode.textContent)
    : null;

  // product-brief.md §2's three-phase state machine (adr/0038 D10) --
  // display labels only; the machine-observed data-gathering-phase
  // attribute always carries the raw enum value unchanged (ADR-0020
  // decision 4(d)'s spirit: never expose the enum itself as the only
  // visible text).
  var PHASE_LABELS = {
    SCHEDULING: "日程を聞き中",
    SELECTING_SHOP: "店を選び中",
    FINALIZED: "確定",
  };

  // 2026-09-05 addition (adr/0044/0046): three-tier shop-vote display labels,
  // also used by web/static/dining_radar/web/candidate.js -- duplicated here
  // (no shared module system exists in this codebase).
  var VOTE_LABELS = { WANT_TO_GO: "行きたい", OK_TO_GO: "行ってもいい", NOT_GOING: "むり" };

  // ADR-0062 decision 1 (2026-09-17, board D1): the same coarse tier
  // vocabularies participant.js's own renderShopVoteDetailFields already
  // uses for shopVoteQuestion.detailFields -- duplicated here (no shared
  // module system exists in this codebase) so this screen's own
  // shortlistedShopVotes.item.detailFields.capacityTier/nonSmokingStatus/
  // dinnerBudgetTier read identically to the participant-facing equivalent.
  var CAPACITY_TIER_LABELS = { SMALL: "少なめ", MEDIUM: "標準", LARGE: "多め" };
  var NON_SMOKING_LABELS = { FULL: "全席禁煙", PARTIAL: "一部禁煙", NONE: "禁煙席なし" };
  var BUDGET_TIER_LABELS = { LOW: "低", MID: "中", HIGH: "高" };

  // 2026-09-13 addition (ADR-0056 decision 1): schedule-response display
  // labels for organizerDashboard.responseTable -- the same three-value
  // vocabulary renderCandidateDate's own tally already uses ("行ける"/
  // "たぶん"/"むり"), reused here so the same status reads the same word
  // everywhere on this screen.
  var SCHEDULE_RESPONSE_LABELS = { GOING: "行ける", MAYBE: "たぶん", NOT_GOING: "むり" };

  var state = {
    gathering: null,
    participantLinks: [],
    tentativeSelectedId: null,
    openShopPreview: null,
    addCandidateDateOpen: false,
    // addCandidateDateSelectedIsos: { [isoDate]: true } -- every currently
    // pending-selected calendar day (gathering-add-candidate-date-day's own
    // data-selected="true" cells), keyed by "YYYY-MM-DD". Retained across a
    // DUPLICATE_CANDIDATE_DATE/CANDIDATE_DATE_NOT_IN_FUTURE rejection (the
    // form stays open, every selection intact, ready to correct); cleared on
    // a successful submit (a fresh entry for the next batch).
    addCandidateDateSelectedIsos: {},
    addCandidateDateDuplicateError: false,
    addCandidateDateNotInFutureError: false,
    // ADR-0060 decision 4: a weekend/Japan-public-holiday date rejected by
    // CANDIDATE_DATE_NOT_A_BUSINESS_DAY -- calendar disabling below already
    // prevents most such attempts client-side, but the server remains the
    // authoritative check (e.g. a stale-embedded-holiday-data edge case).
    addCandidateDateNotABusinessDayError: false,
    headerIssuedLinkUrl: null,
    recopiedLinkUrls: {},
    // ADR-0061 decision 1 (2026-09-17, human decision: 「発行で小窓が開き、
    // そこでコピー」): whether gathering-participant-link-issue-dialog is
    // currently revealed (client-side only -- opening/closing it calls no
    // public operation; the issue itself does, see copyParticipantLink).
    issueDialogOpen: false,
    // Whether the dialog's own "リンクをコピー" has been activated since
    // this dialog was last opened -- drives its non-binding "✓ コピーしま
    // した" label swap (this contract does not fix that visible text).
    issueDialogCopied: false,
    // Explicit open/close focus management for the dialog above -- distinct
    // from the generic restoreFocusFromDescriptor below, which can only
    // restore focus to an element that still exists after a rebuild (see
    // gathering_create.js's own pendingReviewFocus precedent, ADR-0060
    // decision 5).
    pendingIssueDialogFocus: null,
    // adr/0042: client-side pending radio selection for
    // shortlistedShopVotes.list.item.finalizeSelect, before
    // gathering-finalize-open is activated.
    finalizeSelectedShopId: null,
    // ADR-0054 decision 5 / ADR-0056 decision 11: whether
    // gathering-finalize-confirm-dialog is currently revealed (client-side
    // only -- opening it calls no public operation).
    finalizeConfirmOpen: false,
    // Explicit open/close focus management for gathering-finalize-confirm-
    // dialog -- the same pendingIssueDialogFocus precedent above, added
    // 2026-09-17 (ADR-0062 decision 3, board D3: 小窓は開いたらフォーカス
    // を中へ、Esc/もどるで閉じたら元のボタンへ戻す).
    pendingFinalizeConfirmFocus: null,
    // adr/0050 decision 4, deleteGathering: whether gathering-delete-
    // confirm-dialog is currently revealed (client-side only -- opening it
    // calls no public operation).
    deleteConfirmOpen: false,
  };

  // The self-made calendar instance backing addCandidateDateForm.calendar --
  // torn down (its own window-level pointerup/pointercancel listeners
  // removed) before every render() rebuild, the same destroy-before-recreate
  // precedent this file's own former Leaflet handle already established.
  var activeAddCandidateDateCalendar = null;

  // The Leaflet map instance backing shortlistedShopVotes' shared map
  // (gathering-shortlisted-shop-map) -- built once per render() that shows
  // it, torn down before the next.
  var activeShortlistedShopMap = null;

  // ADR-0062 decision 4 (2026-09-17): the Leaflet map instance backing
  // finalizedSummary.decisionBanner's own map (gathering-decision-shop-map)
  // -- the same destroy-before-recreate precedent as
  // activeShortlistedShopMap above.
  var activeDecisionMap = null;

  function csrfToken() {
    var field = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return field ? field.value : "";
  }

  // --- shared-date-formatting BEGIN (identical copy in participant.js; keep both in sync) ---
  // Every startAt/confirmedCandidateDate value this screen ever receives
  // from the public API was itself produced by tagging a calendar day's own
  // "YYYY-MM-DD" digits as a literal UTC instant
  // (calendarDayIsoToStartAtIso below: `dayIso + "T12:00:00Z"`). Formatting it for
  // display must read back the *same* UTC calendar/clock components, not
  // convert to the viewing browser's own host timezone
  // (toLocaleString()/getHours()/getDate()/getDay() etc. all use the host's
  // local timezone per the JS spec) -- doing so would silently turn the
  // organizer's typed "12:00" into a different wall-clock number on a
  // non-UTC host, the same class of bug TDR-GTH-24 already found in the
  // opposite (input) direction. Human decision 2026-09-04 (real-measurement
  // finding: dates rendered as the raw ISO string, unreadable): format as
  // "M/D (曜) HH:MM" (Organizer.dc.html/Answer.dc.html/Final.dc.html's own
  // display convention), reading every component from the Date object's
  // UTC accessors only.
  var WEEKDAY_LABELS_JA = ["日", "月", "火", "水", "木", "金", "土"];

  function pad2(value) {
    return value < 10 ? "0" + value : String(value);
  }

  function formatGatheringDateTime(isoString) {
    var date = new Date(isoString);
    var month = date.getUTCMonth() + 1;
    var day = date.getUTCDate();
    var weekday = WEEKDAY_LABELS_JA[date.getUTCDay()];
    var hours = pad2(date.getUTCHours());
    var minutes = pad2(date.getUTCMinutes());
    return month + "/" + day + " (" + weekday + ") " + hours + ":" + minutes;
  }
  // --- shared-date-formatting END ---

  // 2026-09-13 fix (integration round, GatheringDateTimeFormattingSourceTests.
  // test_gathering_js_and_participant_js_carry_the_identical_code): this
  // date-only ("M/D（曜）", no time) formatter is organizer-only -- every
  // organizer-facing date rendered as a single point in time
  // (gathering-candidate-date/gathering-decision-banner/the shortlisted-shop
  // map's date labels) already shows its own time via
  // gathering-schedule-question's own tally or an adjacent time chip
  // elsewhere on the same screen, so this file grew a second, date-only
  // formatter participant.js has no use for. It used to live *inside* the
  // shared-date-formatting BEGIN/END block that
  // GatheringDateTimeFormattingSourceTests requires be byte-identical
  // between this file and participant.js -- a previous round added it here
  // without adding a matching copy to participant.js, which broke that
  // test. Moving it below the shared block's own END marker (rather than
  // duplicating it, unused, into participant.js) keeps the guarded region
  // limited to code both files actually need, per this contract's own
  // "either move it out, or place it in both" allowance. Still reads
  // WEEKDAY_LABELS_JA from the shared block above (same IIFE scope) --
  // moving it below the block does not require moving that shared constant
  // too.
  function formatGatheringDate(isoString) {
    var date = new Date(isoString);
    var month = date.getUTCMonth() + 1;
    var day = date.getUTCDate();
    var weekday = WEEKDAY_LABELS_JA[date.getUTCDay()];
    return month + "/" + day + "（" + weekday + "）";
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (name) {
      var value = attrs[name];
      if (value === undefined || value === null || value === false) {
        return;
      }
      node.setAttribute(name, value === true ? "" : String(value));
    });
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) {
        return;
      }
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  function requestJson(method, url, body) {
    var options = {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
    };
    if (method !== "GET") {
      options.headers["X-CSRFToken"] = csrfToken();
    }
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    return fetch(url, options).then(function (response) {
      if (response.status === 204) {
        return { status: response.status, body: null };
      }
      return response.json().then(function (responseBody) {
        return { status: response.status, body: responseBody };
      });
    });
  }

  function gatheringUrl() {
    return "/gatherings/" + gatheringId;
  }

  // adr/0049 decision 3: "12:00始まり" UI aid -- every calendar-selected day
  // becomes a CandidateDateInput at literal UTC noon (this contract does not
  // fix or require a way to edit each selected day's time-of-day separately
  // from this default).
  function calendarDayIsoToStartAtIso(dayIso) {
    return dayIso + "T12:00:00Z";
  }

  // --- holiday-data BEGIN (identical copy in gathering_create.js; keep both
  // in sync) ---
  // ADR-0060 decisions 1/2/4: this screen's own calendar must disable the
  // exact same weekend/holiday days the server's own
  // CANDIDATE_DATE_NOT_A_BUSINESS_DAY rejection enforces (TDR-GTH-57/58).
  // Weekday-ness needs no data at all (a plain Date computation below), but
  // holiday-ness does -- rather than re-implementing this product's own
  // Japan-public-holiday rules a second time in JavaScript (risking drift
  // from dining_radar.gathering.holidays, the one place those rules are
  // allowed to live), this reads the exact same bundled dataset back from
  // this page's own rendered HTML, where the server embedded it via
  // Django's json_script filter (see this screen's own template).
  function readHolidayIsoSet() {
    var node = document.getElementById("gathering-holiday-dates");
    if (!node) {
      return {};
    }
    var set = {};
    try {
      JSON.parse(node.textContent || "[]").forEach(function (iso) {
        set[iso] = true;
      });
    } catch (error) {
      // Malformed/missing embedded data: every day renders as a non-holiday
      // client-side -- the server's own rejection remains the authoritative
      // enforcement regardless (disabledState here is a UX affordance only,
      // the same convention this calendar's "明日以降のみ" rule already
      // follows).
    }
    return set;
  }
  var HOLIDAY_ISO_SET = readHolidayIsoSet();
  // --- holiday-data END ---

  // --- self-made calendar (adr/0054 decision 3 / adr/0056 decision 3) -----
  // Replaces the vendored flatpickr library 2026-09-13 -- see this file's
  // module docstring. Adopts, near-verbatim, the "案B｜表" grid/drag/
  // range-selection mechanics a hand-built prototype the human actually
  // pressed and approved (scratchpad/cal/looks.html + script.js) already
  // established: a single shared drag-preview repaint queued at most once
  // per animation frame (so a fast pointermove across many cells never
  // rebuilds the grid more than once per frame), window-level pointerup/
  // pointercancel listeners (so a drag still commits even if the pointer
  // leaves the grid before release), and elementFromPoint-based hit-testing
  // during the drag (so the grid only needs to listen on itself, not on
  // every individual cell, to track which cell is currently under the
  // pointer).
  //
  // A plain click (pointerdown immediately followed by pointerup at the
  // same cell, no intervening pointermove) is a drag whose start and end
  // are the same day, so dayCell.select's single-day toggle
  // (TDR-GTH-01/46) falls out of the exact same code path as a genuine
  // range drag, rather than needing a second, parallel implementation.
  // Shift+click (rangeSelection's second accepted input method) reuses the
  // same commit path, anchored at the day most recently committed by any
  // previous click or drag.
  //
  // `options`: { calendarTestId, dayTestId, dayPurpose, monthPrevTestId,
  // monthNextTestId, monthNavPurpose, removeSelectedTestId,
  // removeSelectedPurpose, selectedIsos (a plain object this function
  // mutates in place, "YYYY-MM-DD" -> true), onChange (called with no
  // arguments after any change to selectedIsos, so the caller can refresh
  // e.g. its own submit button's disabled state) }.
  // Returns { container, destroy } -- destroy() must be called before this
  // container is discarded (removes this instance's own window-level
  // pointerup/pointercancel listeners).
  function buildCandidateDateCalendar(options) {
    var WEEKDAY_LABELS = ["日", "月", "火", "水", "木", "金", "土"];
    var todayDate = new Date();
    todayDate.setHours(0, 0, 0, 0);
    var todayIso = isoOfDate(todayDate);
    var viewMonth = new Date(todayDate.getFullYear(), todayDate.getMonth(), 1);
    var lastAnchorIso = null;
    var drag = null;
    var paintQueued = false;

    var container = el("div", { "data-testid": options.calendarTestId, class: "gth-cal" }, []);

    function isoOfDate(date) {
      return date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate());
    }
    function dateOfIso(iso) {
      var parts = iso.split("-");
      return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    }
    function addDaysIso(iso, amount) {
      var date = dateOfIso(iso);
      date.setDate(date.getDate() + amount);
      return isoOfDate(date);
    }
    // ADR-0060 decisions 1/2: weekend-ness needs no data (computed from the
    // cell's own Date); holiday-ness reads HOLIDAY_ISO_SET (module-level,
    // see holiday-data BEGIN/END above).
    function isWeekendIso(iso) {
      var day = dateOfIso(iso).getDay();
      return day === 0 || day === 6;
    }
    function isHolidayIso(iso) {
      return Boolean(HOLIDAY_ISO_SET[iso]);
    }
    function selectable(iso) {
      return iso > todayIso && !isWeekendIso(iso) && !isHolidayIso(iso);
    }
    function isInDragRange(iso) {
      var lo = drag.startIso < drag.endIso ? drag.startIso : drag.endIso;
      var hi = drag.startIso < drag.endIso ? drag.endIso : drag.startIso;
      return iso >= lo && iso <= hi;
    }
    function effectiveSelected(iso) {
      var on = Boolean(options.selectedIsos[iso]);
      if (drag && selectable(iso) && isInDragRange(iso)) {
        on = drag.mode === "add";
      }
      return on;
    }

    function monthCells() {
      var year = viewMonth.getFullYear();
      var month = viewMonth.getMonth();
      var firstWeekday = new Date(year, month, 1).getDay();
      var daysInMonth = new Date(year, month + 1, 0).getDate();
      var cells = [];
      for (var lead = 0; lead < firstWeekday; lead += 1) {
        cells.push(null);
      }
      for (var day = 1; day <= daysInMonth; day += 1) {
        cells.push(isoOfDate(new Date(year, month, day)));
      }
      while (cells.length % 7 !== 0) {
        cells.push(null);
      }
      return cells;
    }

    function outsideSelectedCount() {
      var count = 0;
      Object.keys(options.selectedIsos).forEach(function (iso) {
        var date = dateOfIso(iso);
        if (
          date.getFullYear() !== viewMonth.getFullYear() ||
          date.getMonth() !== viewMonth.getMonth()
        ) {
          count += 1;
        }
      });
      return count;
    }

    function sortedSelectedIsos() {
      return Object.keys(options.selectedIsos).sort();
    }

    function formatDayLabel(iso) {
      var date = dateOfIso(iso);
      return (date.getMonth() + 1) + "/" + date.getDate() + "（" + WEEKDAY_LABELS[date.getDay()] + "）";
    }

    function paintDragPreview() {
      if (paintQueued) {
        return;
      }
      paintQueued = true;
      window.requestAnimationFrame(function () {
        paintQueued = false;
        var cells = container.querySelectorAll('[data-testid="' + options.dayTestId + '"]');
        for (var index = 0; index < cells.length; index += 1) {
          var cell = cells[index];
          var iso = cell.getAttribute("data-date");
          var selected = effectiveSelected(iso);
          var nextValue = selected ? "true" : "false";
          if (cell.getAttribute("data-selected") !== nextValue) {
            cell.setAttribute("data-selected", nextValue);
          }
          cell.classList.toggle("gth-cal-day--selected", selected);
        }
      });
    }

    function beginDrag(iso, shiftKey) {
      if (!selectable(iso)) {
        return;
      }
      if (shiftKey && lastAnchorIso && selectable(lastAnchorIso)) {
        drag = { mode: "add", startIso: lastAnchorIso, endIso: iso };
      } else {
        drag = { mode: options.selectedIsos[iso] ? "remove" : "add", startIso: iso, endIso: iso };
      }
      paintDragPreview();
    }

    function extendDrag(iso) {
      if (!drag || !selectable(iso) || drag.endIso === iso) {
        return;
      }
      drag.endIso = iso;
      paintDragPreview();
    }

    function commitDrag() {
      if (!drag) {
        return;
      }
      var lo = drag.startIso < drag.endIso ? drag.startIso : drag.endIso;
      var hi = drag.startIso < drag.endIso ? drag.endIso : drag.startIso;
      for (var iso = lo; ; iso = addDaysIso(iso, 1)) {
        if (selectable(iso)) {
          if (drag.mode === "add") {
            options.selectedIsos[iso] = true;
          } else {
            delete options.selectedIsos[iso];
          }
        }
        if (iso === hi) {
          break;
        }
      }
      lastAnchorIso = drag.endIso;
      drag = null;
      renderLocal();
      if (options.onChange) {
        options.onChange();
      }
    }

    function onWindowPointerUp() {
      commitDrag();
    }
    function onWindowPointerCancel() {
      drag = null;
      paintDragPreview();
    }
    window.addEventListener("pointerup", onWindowPointerUp);
    window.addEventListener("pointercancel", onWindowPointerCancel);

    function dateUnderPoint(clientX, clientY) {
      var node = document.elementFromPoint(clientX, clientY);
      var cell = node && node.closest ? node.closest("[data-date]") : null;
      return cell ? cell.getAttribute("data-date") : null;
    }

    function stepMonth(amount) {
      viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + amount, 1);
      renderLocal();
    }

    function toggleOne(iso) {
      if (!selectable(iso)) {
        return;
      }
      if (options.selectedIsos[iso]) {
        delete options.selectedIsos[iso];
      } else {
        options.selectedIsos[iso] = true;
      }
      lastAnchorIso = iso;
      renderLocal();
      if (options.onChange) {
        options.onChange();
      }
    }

    function removeSelected(iso) {
      delete options.selectedIsos[iso];
      renderLocal();
      if (options.onChange) {
        options.onChange();
      }
    }

    function buildDayCell(iso) {
      var enabled = selectable(iso);
      var date = dateOfIso(iso);
      var isWeekend = isWeekendIso(iso);
      var isHoliday = isHolidayIso(iso);
      var isToday = iso === todayIso;
      var isSelected = effectiveSelected(iso);
      var classNames = ["gth-cal-day"];
      if (isWeekend) {
        classNames.push("gth-cal-day--weekend");
      }
      if (isHoliday) {
        classNames.push("gth-cal-day--holiday");
      }
      if (!enabled) {
        classNames.push("gth-cal-day--disabled");
      }
      if (isToday) {
        classNames.push("gth-cal-day--today");
      }
      if (isSelected) {
        classNames.push("gth-cal-day--selected");
      }
      var attrs = {
        "data-testid": options.dayTestId,
        "data-date": iso,
        "data-selected": isSelected ? "true" : "false",
        // ADR-0060 decision 2: always present, independent of weekend-ness.
        "data-holiday": isHoliday ? "true" : "false",
        class: classNames.join(" "),
      };
      if (enabled) {
        attrs["data-gathering-control-purpose"] = options.dayPurpose;
        attrs.role = "button";
        attrs.tabindex = "0";
      } else {
        attrs["aria-disabled"] = "true";
      }
      var dayChildren = [String(date.getDate())];
      if (isHoliday) {
        dayChildren.push(
          el("span", { class: "gth-cal-day-holiday-badge", "aria-hidden": "true" }, ["祝"])
        );
      }
      var cell = el("div", attrs, dayChildren);
      if (enabled) {
        cell.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleOne(iso);
          }
        });
      }
      return cell;
    }

    function wireGrid(grid) {
      grid.addEventListener("pointerdown", function (event) {
        var iso = dateUnderPoint(event.clientX, event.clientY);
        if (!iso || !selectable(iso)) {
          return;
        }
        event.preventDefault();
        if (grid.setPointerCapture) {
          try {
            grid.setPointerCapture(event.pointerId);
          } catch (error) {
            // Not capturable in this environment.
          }
        }
        beginDrag(iso, event.shiftKey);
      });
      grid.addEventListener("pointermove", function (event) {
        if (!drag) {
          return;
        }
        var iso = dateUnderPoint(event.clientX, event.clientY);
        if (iso) {
          extendDrag(iso);
        }
      });
    }

    function renderLocal() {
      container.innerHTML = "";

      var prevButton = el(
        "button",
        {
          type: "button",
          "data-testid": options.monthPrevTestId,
          "data-gathering-control-purpose": options.monthNavPurpose,
          "aria-label": "前の月",
          class: "gth-cal-nav gth-cal-nav--prev",
        },
        ["‹"]
      );
      prevButton.addEventListener("click", function () {
        stepMonth(-1);
      });
      var nextButton = el(
        "button",
        {
          type: "button",
          "data-testid": options.monthNextTestId,
          "data-gathering-control-purpose": options.monthNavPurpose,
          "aria-label": "次の月",
          class: "gth-cal-nav gth-cal-nav--next",
        },
        ["›"]
      );
      nextButton.addEventListener("click", function () {
        stepMonth(1);
      });
      var headChildren = [
        prevButton,
        el("div", { class: "gth-cal-month" }, [
          viewMonth.getFullYear() + "年 " + (viewMonth.getMonth() + 1) + "月",
        ]),
        nextButton,
      ];
      var outsideCount = outsideSelectedCount();
      if (outsideCount > 0) {
        headChildren.push(
          el("span", { class: "gth-cal-outside-badge" }, ["ほかの月にも " + outsideCount + "日"])
        );
      }
      container.appendChild(el("div", { class: "gth-cal-head" }, headChildren));

      var gridChildren = WEEKDAY_LABELS.map(function (label, index) {
        var classNames = ["gth-cal-weekday"];
        if (index === 0) {
          classNames.push("gth-cal-weekday--sun");
        }
        if (index === 6) {
          classNames.push("gth-cal-weekday--sat");
        }
        return el("div", { class: classNames.join(" ") }, [label]);
      });
      monthCells().forEach(function (iso) {
        if (!iso) {
          gridChildren.push(
            el("div", { class: "gth-cal-day gth-cal-day--off", "aria-hidden": "true" }, [])
          );
          return;
        }
        gridChildren.push(buildDayCell(iso));
      });
      var grid = el("div", { class: "gth-cal-grid" }, gridChildren);
      container.appendChild(el("div", { class: "gth-cal-scroll" }, [grid]));
      wireGrid(grid);

      // ADR-0060 decision 5 note: addCandidateDateForm.calendar (this file's
      // own call site below) is unaffected by that decision and never passes
      // hidePickedList -- this guard exists only so this function's body
      // stays a verbatim-shape duplicate of gathering_create.js's own copy,
      // whose call site does pass it.
      if (!options.hidePickedList) {
        var pickedRows = sortedSelectedIsos().map(function (iso) {
          var removeButton = el(
            "button",
            {
              type: "button",
              "data-testid": options.removeSelectedTestId,
              "data-gathering-control-purpose": options.removeSelectedPurpose,
              "data-date": iso,
              "aria-label": formatDayLabel(iso) + " を外す",
              class: "gth-cal-picked-remove",
            },
            ["×"]
          );
          removeButton.addEventListener("click", function () {
            removeSelected(iso);
          });
          return el("div", { class: "gth-cal-picked-row" }, [
            el("span", { class: "gth-cal-picked-date" }, [
              formatDayLabel(iso) + " ",
              el("span", { class: "gth-cal-picked-time" }, ["12:00"]),
            ]),
            removeButton,
          ]);
        });
        container.appendChild(
          el(
            "div",
            { class: "gth-cal-picked" },
            [
              el("div", { class: "gth-cal-picked-head" }, [
                el("span", {}, ["えらんだ日 ", el("b", {}, [String(sortedSelectedIsos().length)]), "日"]),
                el("span", { class: "gth-cal-picked-note" }, ["どれも 12:00 から"]),
              ]),
            ].concat(pickedRows)
          )
        );
      }
    }

    renderLocal();

    return {
      container: container,
      destroy: function () {
        window.removeEventListener("pointerup", onWindowPointerUp);
        window.removeEventListener("pointercancel", onWindowPointerCancel);
      },
    };
  }

  function loadGathering() {
    return requestJson("GET", gatheringUrl())
      .then(function (result) {
        state.gathering = result.body;
        return requestJson("GET", gatheringUrl() + "/participant-links");
      })
      .then(function (result) {
        state.participantLinks = result.body.participantLinks;
      })
      .then(function () {
        render();
      });
  }

  function tentativelySelectCandidateDate(candidateDateId) {
    if (state.gathering.phase !== "SCHEDULING") {
      // tentativeSelectionAndPreview.trigger.presenceRuleForPurpose: this
      // purpose is only activatable while phase is SCHEDULING -- the
      // element itself stays present as a record (renderCandidateDate
      // below), but no longer accepts this activation.
      return;
    }
    state.tentativeSelectedId = candidateDateId;
    render();
    requestJson("GET", gatheringUrl() + "/candidate-dates/" + candidateDateId + "/open-shop-preview")
      .then(function (result) {
        if (state.tentativeSelectedId === candidateDateId) {
          state.openShopPreview = result.body;
          render();
        }
      });
  }

  function confirmDate() {
    if (!state.tentativeSelectedId) {
      return;
    }
    requestJson("POST", gatheringUrl() + "/confirm-date", {
      candidateDateId: state.tentativeSelectedId,
    }).then(function (result) {
      if (result.status === 200) {
        // adr/0035 decision 1 item 1: tentativeSelectedId/openShopPreview are
        // deliberately left unchanged -- confirmDate's own requiredOutcome
        // says this call must not affect either.
        state.gathering = result.body;
        return loadParticipantLinksOnly().then(render);
      }
    });
  }

  function loadParticipantLinksOnly() {
    return requestJson("GET", gatheringUrl() + "/participant-links").then(function (result) {
      state.participantLinks = result.body.participantLinks;
      render();
    });
  }

  function copyParticipantLink() {
    // **Changed 2026-09-17 (ADR-0061 decision 1, human decision: 「発行で
    // 小窓が開き、そこでコピー」)**: this activation no longer writes to the
    // clipboard itself -- it only issues one new link and reveals
    // gathering-participant-link-issue-dialog, carrying the returned URL as
    // that dialog's own data-issued-link-url. The clipboard-write Must
    // ADR-0058 established for this activation moves to the dialog's own
    // copyIssuedLinkFromDialog below (not removed, only reassigned).
    //
    // Real-browser measurement (2026-08-31, still applicable): a *second*
    // activation of this same control was passing this contract's own
    // "data-issued-link-url becomes non-empty" acceptance check
    // *immediately*, before this activation's own request had even reached
    // the server. Clearing the tracked value synchronously here, before the
    // async request even starts, makes every activation transition through
    // an observable absent-or-empty -> non-empty edge.
    state.headerIssuedLinkUrl = null;
    render();
    requestJson("POST", gatheringUrl() + "/participant-links", { count: 1 }).then(function (result) {
      if (result.status !== 201) {
        return;
      }
      var issued = result.body.issuedLinks[0];
      state.headerIssuedLinkUrl = issued.url;
      state.issueDialogOpen = true;
      state.issueDialogCopied = false;
      state.pendingIssueDialogFocus = "open";
      state.gathering.totalIssuedParticipantLinks = result.body.totalIssuedParticipantLinks;
      state.gathering.activeParticipantLinkCount = result.body.activeParticipantLinkCount;
      loadParticipantLinksOnly();
    });
  }

  // gathering-participant-link-issue-dialog-copy ("リンクをコピー", ADR-0061
  // decision 1): **this is where the Must ADR-0058 established for
  // copyParticipantLink's own activation now lives** -- reassigned, not
  // retracted. Same silent-failure handling ADR-0058 established (FR-034:
  // no explanatory prose in shipped screens either way).
  function copyIssuedLinkFromDialog() {
    if (window.navigator && window.navigator.clipboard) {
      window.navigator.clipboard.writeText(state.headerIssuedLinkUrl).catch(function () {});
    }
    state.issueDialogCopied = true;
    render();
  }

  // gathering-participant-link-issue-dialog-close ("閉じる"/"×", ADR-0061
  // decision 1): calls no public operation, does not affect
  // data-issued-link-url or the issued-link counters -- only makes the
  // dialog absent.
  function closeIssueDialog() {
    state.issueDialogOpen = false;
    state.issueDialogCopied = false;
    state.pendingIssueDialogFocus = "close";
    render();
  }

  function recopyParticipantLink(linkId) {
    state.recopiedLinkUrls[linkId] = null;
    render();
    requestJson("POST", gatheringUrl() + "/participant-links/" + linkId + "/recopy").then(
      function (result) {
        if (result.status === 200) {
          state.recopiedLinkUrls[linkId] = result.body.url;
          if (window.navigator && window.navigator.clipboard) {
            window.navigator.clipboard.writeText(result.body.url).catch(function () {});
          }
          render();
        }
      }
    );
  }

  function revokeParticipantLink(linkId) {
    requestJson("POST", gatheringUrl() + "/participant-links/" + linkId + "/revoke").then(
      function (result) {
        if (result.status !== 200) {
          return;
        }
        state.gathering = result.body.gathering;
        var index = state.participantLinks.findIndex(function (link) {
          return link.id === linkId;
        });
        if (index !== -1) {
          state.participantLinks[index] = result.body.participantLink;
        }
        render();
      }
    );
  }

  // --- ADR-0056 decision 2: removeCandidateDate ---------------------------

  function removeCandidateDate(candidateDateId) {
    requestJson("DELETE", gatheringUrl() + "/candidate-dates/" + candidateDateId).then(
      function (result) {
        if (result.status === 200) {
          state.gathering = result.body;
          if (state.tentativeSelectedId === candidateDateId) {
            state.tentativeSelectedId = null;
            state.openShopPreview = null;
          }
          render();
        }
      }
    );
  }

  function openAddCandidateDate() {
    state.addCandidateDateOpen = true;
    render();
  }

  function cancelAddCandidateDate() {
    // browserControlSurface.organizerDashboard.candidateDateList.
    // addCandidateDateForm.cancel.requiredOutcome: makes the form absent
    // and the open control reachable again, without calling
    // addCandidateDates (discarding every pending calendar-day selection).
    state.addCandidateDateOpen = false;
    state.addCandidateDateSelectedIsos = {};
    state.addCandidateDateDuplicateError = false;
    state.addCandidateDateNotInFutureError = false;
    state.addCandidateDateNotABusinessDayError = false;
    render();
  }

  function submitAddCandidateDates() {
    var isos = Object.keys(state.addCandidateDateSelectedIsos).sort();
    if (isos.length < 1) {
      return;
    }
    var candidateDates = isos.map(function (iso) {
      return { startAt: calendarDayIsoToStartAtIso(iso) };
    });
    requestJson("POST", gatheringUrl() + "/candidate-dates:batch", {
      candidateDates: candidateDates,
    }).then(function (result) {
      if (result.status === 201) {
        state.gathering = result.body;
        // adr/0038/adr/0049, human decision 2026-09-01 (AddDate.dc.html 案A:
        // "足したあとフォームは閉じない"): addCandidateDateOpen stays true --
        // only the pending selections clear, ready for the next batch.
        state.addCandidateDateSelectedIsos = {};
        state.addCandidateDateDuplicateError = false;
        state.addCandidateDateNotInFutureError = false;
        state.addCandidateDateNotABusinessDayError = false;
        render();
      } else if (
        result.status === 409 &&
        result.body &&
        result.body.code === "DUPLICATE_CANDIDATE_DATE"
      ) {
        state.addCandidateDateDuplicateError = true;
        state.addCandidateDateNotInFutureError = false;
        state.addCandidateDateNotABusinessDayError = false;
        render();
      } else if (
        // 2026-09-16 fix (found while implementing ADR-0060): the server
        // answers CANDIDATE_DATE_NOT_IN_FUTURE with 400, not 409 -- this
        // branch's own `result.status === 409` guard had never matched in
        // production, leaving this error message unreachable.
        result.status === 400 &&
        result.body &&
        result.body.code === "CANDIDATE_DATE_NOT_IN_FUTURE"
      ) {
        state.addCandidateDateNotInFutureError = true;
        state.addCandidateDateDuplicateError = false;
        state.addCandidateDateNotABusinessDayError = false;
        render();
      } else if (
        // ADR-0060 decision 4 (2026-09-16): CANDIDATE_DATE_NOT_A_BUSINESS_DAY,
        // same 400 status as CANDIDATE_DATE_NOT_IN_FUTURE above.
        result.status === 400 &&
        result.body &&
        result.body.code === "CANDIDATE_DATE_NOT_A_BUSINESS_DAY"
      ) {
        state.addCandidateDateNotABusinessDayError = true;
        state.addCandidateDateDuplicateError = false;
        state.addCandidateDateNotInFutureError = false;
        render();
      }
    });
  }

  // --- adr/0042/adr/0049: approval voting / finalization -------------------
  // (shop shortlisting itself moved to candidate-search-browser-interface.
  // yaml's gatheringMode, adr/0049 decision 1.)

  function navigateToShopSelectionEntry() {
    window.location.href = "/?gatheringId=" + encodeURIComponent(gatheringId);
  }

  function renderShopSelectionEntry(label, className) {
    var button = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-shortlist-open",
        "data-gathering-control-purpose": "gathering-shortlist-open",
        class: className || "gth-btn gth-btn-primary gth-btn-block",
      },
      [label]
    );
    button.addEventListener("click", navigateToShopSelectionEntry);
    return button;
  }

  function selectFinalizeShop(shopId) {
    state.finalizeSelectedShopId = shopId;
    render();
  }

  // ADR-0055 decision 6: "true" for every item tied for the highest
  // wantToGoCount+okToGoCount among items that have at least one response,
  // "false" for everything else (including every item when no one has
  // answered any of them yet).
  function computeCurrentLeaderShopIds(shops) {
    var respondedShops = shops.filter(function (shop) {
      return shop.wantToGoCount + shop.okToGoCount + shop.notGoingCount > 0;
    });
    if (respondedShops.length === 0) {
      return {};
    }
    var maxScore = respondedShops.reduce(function (max, shop) {
      var score = shop.wantToGoCount + shop.okToGoCount;
      return score > max ? score : max;
    }, -Infinity);
    var leaders = {};
    respondedShops.forEach(function (shop) {
      if (shop.wantToGoCount + shop.okToGoCount === maxScore) {
        leaders[shop.shopId] = true;
      }
    });
    return leaders;
  }

  // --- current-leader-cascade BEGIN (identical shape copy in participant.js's
  // own computeScheduleQuestionLeaders; keep both in sync) ---
  // ADR-0060 decision 7 (2026-09-16, human decision: "○が多い日を優先。
  // 同票なら△が多いほう。それでも同票ならすべてつける"): a two-level
  // cascade, distinct from computeCurrentLeaderShopIds above's own single
  // summed score -- goingCount alone decides first; maybeCount is consulted
  // only to break a goingCount tie, never combined with it. A candidate date
  // with zero total responses is always excluded (same 0-response exclusion
  // as computeCurrentLeaderShopIds).
  function computeCandidateDateLeaders(candidateDates) {
    var responded = candidateDates.filter(function (candidateDate) {
      return candidateDate.goingCount + candidateDate.maybeCount + candidateDate.notGoingCount > 0;
    });
    if (responded.length === 0) {
      return {};
    }
    var maxGoing = responded.reduce(function (max, candidateDate) {
      return candidateDate.goingCount > max ? candidateDate.goingCount : max;
    }, -Infinity);
    var tiedOnGoing = responded.filter(function (candidateDate) {
      return candidateDate.goingCount === maxGoing;
    });
    var maxMaybe = tiedOnGoing.reduce(function (max, candidateDate) {
      return candidateDate.maybeCount > max ? candidateDate.maybeCount : max;
    }, -Infinity);
    var leaders = {};
    tiedOnGoing.forEach(function (candidateDate) {
      if (candidateDate.maybeCount === maxMaybe) {
        leaders[candidateDate.id] = true;
      }
    });
    return leaders;
  }
  // --- current-leader-cascade END ---

  function openFinalizeGathering() {
    if (!state.finalizeSelectedShopId) {
      return;
    }
    state.finalizeConfirmOpen = true;
    state.pendingFinalizeConfirmFocus = "open";
    render();
  }

  function cancelFinalizeGathering() {
    // finalizeCancel.requiredOutcome: makes the confirm dialog absent
    // without calling finalizeGathering. Every shop's own
    // data-finalize-selected is unaffected.
    state.finalizeConfirmOpen = false;
    state.pendingFinalizeConfirmFocus = "close";
    render();
  }

  function confirmFinalizeGathering() {
    if (!state.finalizeSelectedShopId) {
      return;
    }
    requestJson("POST", gatheringUrl() + "/finalize", {
      shopId: state.finalizeSelectedShopId,
    }).then(function (result) {
      if (result.status === 200) {
        state.gathering = result.body;
        state.finalizeSelectedShopId = null;
        state.finalizeConfirmOpen = false;
        render();
      }
    });
  }

  // --- adr/0050 decision 4: deleteGathering (Organizer.dc.html A-del) -----

  function openDeleteGathering() {
    state.deleteConfirmOpen = true;
    render();
  }

  function cancelDeleteGathering() {
    state.deleteConfirmOpen = false;
    render();
  }

  function confirmDeleteGathering() {
    requestJson("DELETE", gatheringUrl()).then(function (result) {
      if (result.status === 204) {
        // deleteGathering.confirm.requiredOutcome (ADR-0054 decision 6): the
        // organizer's own gathering list -- the only destination that still
        // makes sense once this specific gathering no longer exists.
        window.location.href = "/gatherings/";
      }
    });
  }

  function renderDeleteGathering() {
    var openButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-delete-open",
        "data-gathering-control-purpose": "gathering-delete-open",
        class: "gth-btn gth-btn-danger",
      },
      ["会を削除"]
    );
    openButton.addEventListener("click", openDeleteGathering);

    var children = [openButton];
    if (state.deleteConfirmOpen) {
      var confirmButton = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-delete-confirm",
          "data-gathering-control-purpose": "gathering-delete-confirm",
          class: "gth-btn gth-btn-danger",
        },
        ["削除する"]
      );
      confirmButton.addEventListener("click", confirmDeleteGathering);
      var cancelButton = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-delete-cancel",
          "data-gathering-control-purpose": "gathering-delete-cancel",
          class: "gth-btn",
        },
        ["やめる"]
      );
      cancelButton.addEventListener("click", cancelDeleteGathering);
      children.push(
        el(
          "div",
          { "data-testid": "gathering-delete-confirm-dialog", class: "gth-confirm-dialog gth-confirm-dialog--danger" },
          [
            el("p", { class: "gth-confirm-dialog-text" }, [
              "この会を削除すると元に戻せません。発行済みのリンクもすべて無効になります。",
            ]),
            el("div", { class: "gth-inline-form-row" }, [confirmButton, cancelButton]),
          ]
        )
      );
    }
    return el("div", { class: "gth-delete" }, children);
  }

  function renderPhaseIndicator() {
    return el(
      "div",
      {
        "data-testid": "gathering-phase-indicator",
        "data-gathering-phase": state.gathering.phase,
        class: "gth-phase",
      },
      [PHASE_LABELS[state.gathering.phase] || state.gathering.phase]
    );
  }

  function renderResponseSummary() {
    return el(
      "div",
      {
        "data-testid": "gathering-responded-summary",
        "data-responded-count": state.gathering.respondedParticipantCount,
        "data-anonymous-responded-count": state.gathering.anonymousRespondedParticipantCount,
        class: "gth-stat",
      },
      [
        el("b", {}, [String(state.gathering.respondedParticipantCount)]),
        "人が回答（うち",
        el("b", {}, [String(state.gathering.anonymousRespondedParticipantCount)]),
        "人は名前なし）",
      ]
    );
  }

  function renderUnansweredSummary() {
    var unansweredCount =
      state.gathering.activeParticipantLinkCount - state.gathering.respondedParticipantCount;
    return el(
      "div",
      {
        "data-testid": "gathering-unanswered-summary",
        "data-total-issued-links": state.gathering.totalIssuedParticipantLinks,
        "data-revoked-links": state.gathering.totalRevokedParticipantLinks,
        "data-active-issued-links": state.gathering.activeParticipantLinkCount,
        "data-unanswered-count": unansweredCount,
        class: "gth-stat",
      },
      [
        "有効なリンク ",
        el("b", {}, [String(state.gathering.activeParticipantLinkCount)]),
        "本 ・ まだ ",
        el("b", {}, [String(unansweredCount)]),
        "人が未回答",
      ]
    );
  }

  function renderCandidateDate(candidateDate, leaders) {
    var isTentative = state.tentativeSelectedId === candidateDate.id;
    var isSchedulingPhase = state.gathering.phase === "SCHEDULING";
    var isLeader = Boolean(leaders[candidateDate.id]);
    var attrs = {
      "data-testid": "gathering-candidate-date",
      "data-candidate-date-id": candidateDate.id,
      "data-going-count": candidateDate.goingCount,
      "data-maybe-count": candidateDate.maybeCount,
      "data-not-going-count": candidateDate.notGoingCount,
      "data-confirmed": candidateDate.isConfirmed ? "true" : "false",
      "data-tentative-selected": isTentative ? "true" : "false",
      // ADR-0060 decision 7: computed client-side (computeCandidateDateLeaders
      // above) from goingCount/maybeCount/notGoingCount, already present on
      // every CandidateDate -- no API change needed.
      "data-current-leader": isLeader ? "true" : "false",
      class:
        "gth-date" +
        (isSchedulingPhase ? " gth-date--pickable" : "") +
        (isLeader ? " gth-date--leader" : ""),
    };
    if (isSchedulingPhase) {
      attrs["data-gathering-control-purpose"] = "gathering-candidate-date-tentative-select";
      attrs.role = "button";
      attrs.tabindex = "0";
    }

    var topChildren = [
      el("span", { class: "gth-date-value" }, [formatGatheringDateTime(candidateDate.startAt)]),
      candidateDate.isConfirmed ? el("span", { class: "gth-date-badge" }, ["決定"]) : null,
    ];

    // ADR-0056 decision 2: present once per not-yet-confirmed candidate
    // date, only while SCHEDULING.
    var canRemove = isSchedulingPhase && !candidateDate.isConfirmed;
    if (canRemove) {
      var removeButton = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-candidate-date-remove",
          "data-gathering-control-purpose": "gathering-candidate-date-remove",
          "aria-label": "この候補日を削除",
          class: "gth-date-remove",
        },
        ["削除"]
      );
      removeButton.addEventListener("click", function (event) {
        // Stop this from also bubbling into the parent's own
        // tentative-select click handler below.
        event.stopPropagation();
        removeCandidateDate(candidateDate.id);
      });
      removeButton.addEventListener("keydown", function (event) {
        event.stopPropagation();
      });
      topChildren.push(removeButton);
    }

    var node = el("div", attrs, [
      el("div", { class: "gth-date-top" }, topChildren),
      el("div", { class: "gth-date-tally" }, [
        el("span", {}, ["行ける ", el("b", {}, [String(candidateDate.goingCount)])]),
        el("span", {}, ["たぶん ", el("b", {}, [String(candidateDate.maybeCount)])]),
        el("span", {}, ["むり ", el("b", {}, [String(candidateDate.notGoingCount)])]),
      ]),
    ]);
    if (isSchedulingPhase) {
      node.addEventListener("click", function () {
        tentativelySelectCandidateDate(candidateDate.id);
      });
      node.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          tentativelySelectCandidateDate(candidateDate.id);
        }
      });
    }
    return node;
  }

  function renderAddCandidateDateForm() {
    var submit = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-add-candidate-date-submit",
        "data-gathering-control-purpose": "gathering-add-candidate-date-submit",
        disabled: Object.keys(state.addCandidateDateSelectedIsos).length < 1,
        class: "gth-btn gth-btn-primary",
      },
      ["足す"]
    );
    submit.addEventListener("click", submitAddCandidateDates);

    var calendar = buildCandidateDateCalendar({
      calendarTestId: "gathering-add-candidate-date-calendar",
      dayTestId: "gathering-add-candidate-date-day",
      dayPurpose: "gathering-add-candidate-date-day-select",
      monthPrevTestId: "gathering-add-candidate-date-month-previous",
      monthNextTestId: "gathering-add-candidate-date-month-next",
      monthNavPurpose: "gathering-add-candidate-date-month-navigate",
      removeSelectedTestId: "gathering-add-candidate-date-remove-selected",
      removeSelectedPurpose: "gathering-add-candidate-date-remove-selected",
      selectedIsos: state.addCandidateDateSelectedIsos,
      onChange: function () {
        submit.disabled = Object.keys(state.addCandidateDateSelectedIsos).length < 1;
      },
    });
    activeAddCandidateDateCalendar = calendar;

    var cancel = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-add-candidate-date-cancel",
        "data-gathering-control-purpose": "gathering-add-candidate-date-cancel",
        class: "gth-btn",
      },
      ["やめる"]
    );
    cancel.addEventListener("click", cancelAddCandidateDate);

    var children = [
      calendar.container,
      el("div", { class: "gth-inline-form-row" }, [submit, cancel]),
    ];
    if (state.addCandidateDateDuplicateError) {
      children.push(el("p", { class: "gth-error" }, ["同じ日時の候補日は既に追加されています。"]));
    }
    if (state.addCandidateDateNotInFutureError) {
      children.push(el("p", { class: "gth-error" }, ["明日以降の日付を選んでください。"]));
    }
    if (state.addCandidateDateNotABusinessDayError) {
      children.push(el("p", { class: "gth-error" }, ["土日・祝日は候補日として登録できません。"]));
    }
    return el(
      "div",
      { "data-testid": "gathering-add-candidate-date-form", class: "gth-inline-form" },
      children
    );
  }

  function renderAddCandidateDateOpen() {
    var openButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-add-candidate-date-open",
        "data-gathering-control-purpose": "gathering-add-candidate-date-open",
        class: "gth-link-btn",
      },
      ["＋ 候補日を足す"]
    );
    openButton.addEventListener("click", openAddCandidateDate);

    var children = [openButton];
    if (state.addCandidateDateOpen) {
      children.push(renderAddCandidateDateForm());
    }
    return el("div", { class: "gth-add-date" }, children);
  }

  // ADR-0055 decision 1: participants no longer see "この日に開いている店
  // N件" at all; the organizer keeps it, but only for the one candidate
  // date currently tentatively selected -- not shown per candidate date at
  // once (this is a display-only narrowing; previewOpenShopsForCandidateDate
  // itself is unchanged, ADR-0049 decision 2).
  function renderOpenShopPreview() {
    if (!state.tentativeSelectedId || !state.openShopPreview) {
      return null;
    }
    return el(
      "div",
      {
        "data-testid": "gathering-open-shop-preview",
        "data-candidate-date-id": state.openShopPreview.candidateDateId,
        "data-open-shop-count": state.openShopPreview.openShopCount,
        class: "gth-preview",
      },
      [
        el("div", { class: "gth-preview-head" }, [
          "この日に開いている店 ",
          el("b", {}, [String(state.openShopPreview.openShopCount)]),
          "件",
        ]),
      ]
    );
  }

  function renderConfirmDate() {
    var button = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-confirm-date-select",
        "data-gathering-control-purpose": "gathering-confirm-date-select",
        disabled: !state.tentativeSelectedId,
        class: "gth-btn gth-btn-primary gth-btn-block",
      },
      ["この日にする"]
    );
    button.addEventListener("click", confirmDate);
    return button;
  }

  // --- adr/0042: shortlistedShopVotes (Organizer.dc.html 状態②) ------------
  // ADR-0055 decision 5 / ADR-0056 decision 5 (2026-09-12): this view now
  // also shows a shared map plus each shop's name/walking-time/provider-page
  // link -- reversing this file's own 2026-09-05 exclusion.
  //
  // ADR-0062 decision 1 (2026-09-17, board D1): this row's own
  // detailFields grow to the full ジャンル・席・禁煙・予算・徒歩の目安
  // five-field set below (mirroring participant.js's own
  // renderShopVoteDetailFields, except genre -- see this section's own
  // gathering-shortlisted-shop-genre span, required only on this screen).
  // The now-retired 「あとから入りました」badge (ADR-0056 decision 6) and
  // its own per-shop "added after voting started" helper function are
  // removed the same round.

  // **Fixed 2026-09-19 (board party2/d2/D1-a-* comparison, real-machine
  // finding)**: board D1 shows this row's five detailFields as one line,
  // joined by "・", each self-describing what it names ("席 標準"/"予算
  // 低"), not five space-separated bare words -- an earlier revision
  // rendered genre/capacityTier/dinnerBudgetTier without their own label,
  // indistinguishable from each other at a glance. genre/nonSmokingStatus
  // still carry no prefix (board: "和食"/"全席禁煙" alone -- the value
  // itself already names what it is); capacityTier/dinnerBudgetTier gain
  // "席 "/"予算 " (board's own literal wording -- not "予算感", this
  // file's own earlier prefix). "情報なし" for an absent value matches
  // this product's existing candidate-search-browser-interface.yaml
  // convention (web/static/dining_radar/web/candidate.js's own fieldRow
  // default) unchanged by this fix. testId/data attributes are unchanged
  // -- only visible text and DOM position move (developer discretion,
  // this contract fixes neither).
  function renderShortlistedShopDetailFields(shop) {
    var fields = [
      el(
        "span",
        { "data-testid": "gathering-shortlisted-shop-genre", class: "gth-shop-detail" },
        [shop.genre]
      ),
      el(
        "span",
        { "data-testid": "gathering-shortlisted-shop-walking-time", class: "gth-shop-detail" },
        ["徒歩 約" + shop.walkingTimeMinutes + "分"]
      ),
      el(
        "span",
        { "data-testid": "gathering-shortlisted-shop-capacity-tier", class: "gth-shop-detail" },
        ["席 " + (shop.capacityTier ? CAPACITY_TIER_LABELS[shop.capacityTier] : "情報なし")]
      ),
      el(
        "span",
        { "data-testid": "gathering-shortlisted-shop-non-smoking", class: "gth-shop-detail" },
        [shop.nonSmokingStatus ? NON_SMOKING_LABELS[shop.nonSmokingStatus] : "情報なし"]
      ),
      el(
        "span",
        { "data-testid": "gathering-shortlisted-shop-dinner-budget", class: "gth-shop-detail" },
        ["予算 " + (shop.dinnerBudgetTier ? BUDGET_TIER_LABELS[shop.dinnerBudgetTier] : "情報なし")]
      ),
    ];
    // "・" separators between fields only (board's own literal wording) --
    // aria-hidden, purely visual punctuation, not read out by a screen
    // reader between fields it already announces as separate elements.
    var withSeparators = [];
    fields.forEach(function (field, index) {
      if (index > 0) {
        withSeparators.push(
          el("span", { class: "gth-shop-detail-sep", "aria-hidden": "true" }, ["・"])
        );
      }
      withSeparators.push(field);
    });
    return withSeparators;
  }

  // Board D1's own vote presentation for this row: a fixed-length bar
  // (this shop's own respondedParticipantCount as the denominator -- D7's
  // per-shop denominator, item.attributes.respondedCount above, the same
  // basis this row's own tallyRow text used before this fix) plus ○N/△N/
  // ×N counts, not the "行きたい N" word-labeled line participant.js's
  // shopVoteQuestion uses elsewhere (a deliberate difference: board D1
  // draws this row this way, participant.js's own board draws that screen
  // differently -- this fix does not touch participant.js).
  function renderShortlistedShopVoteRow(shop) {
    var total = shop.respondedParticipantCount;
    function segment(count, modifierClass) {
      var width = total > 0 ? Math.max(0, Math.min(100, (count / total) * 100)) : 0;
      return el(
        "span",
        { class: "gth-shop-vote-bar-seg " + modifierClass, style: "width:" + width + "%" },
        []
      );
    }
    var bar = el("span", { class: "gth-shop-vote-bar" }, [
      segment(shop.wantToGoCount, "gth-shop-vote-bar-seg--want"),
      segment(shop.okToGoCount, "gth-shop-vote-bar-seg--ok"),
      segment(shop.notGoingCount, "gth-shop-vote-bar-seg--not"),
    ]);
    return el("div", { class: "gth-shop-vote-row" }, [
      bar,
      el("span", { class: "gth-shop-vote-count gth-shop-vote-count--want" }, [
        "○" + String(shop.wantToGoCount),
      ]),
      el("span", { class: "gth-shop-vote-count gth-shop-vote-count--ok" }, [
        "△" + String(shop.okToGoCount),
      ]),
      el("span", { class: "gth-shop-vote-count gth-shop-vote-count--not" }, [
        "×" + String(shop.notGoingCount),
      ]),
    ]);
  }

  function renderShortlistedShopItem(shop, index, leaders) {
    var attrs = {
      "data-testid": "gathering-shortlisted-shop-item",
      "data-shop-id": shop.shopId,
      "data-shop-name": shop.name,
      "data-walking-time-minutes": shop.walkingTimeMinutes,
      "data-want-to-go-count": shop.wantToGoCount,
      "data-ok-to-go-count": shop.okToGoCount,
      "data-not-going-count": shop.notGoingCount,
      "data-responded-count": shop.respondedParticipantCount,
      // ADR-0055 decision 6: 0 responses -> always "false"; otherwise
      // "true" for every item tied for the highest wantToGoCount+
      // okToGoCount (leaders, computed once per render by
      // computeCurrentLeaderShopIds).
      "data-current-leader": leaders[shop.shopId] ? "true" : "false",
      class: "gth-shop-row gth-shop-row--vote",
    };
    if (leaders[shop.shopId]) {
      attrs.class += " gth-shop-row--leader";
    }
    var detailRow = el(
      "div",
      { class: "gth-shop-detail-row" },
      renderShortlistedShopDetailFields(shop)
    );
    // **Fixed 2026-09-19**: board D1's own row order, left to right, is
    // [finalize-select radio][numbered rank][name+badge/vote/detail
    // body][page-link], radio/rank top-aligned with the body's own first
    // line (gth-shop-row's own align-items: flex-start, not the previous
    // center -- see that rule's own comment for why) -- an earlier
    // revision pushed the radio to the row's own trailing end (after
    // body) instead, leaving it detached from the row's visible content
    // on both narrow and wide layouts, and buried the page link inside
    // the wrapping detail line instead of this row's own right-hand
    // column.
    var children = [];
    if (state.gathering.phase === "SELECTING_SHOP") {
      var selected = state.finalizeSelectedShopId === shop.shopId;
      var radio = el(
        "input",
        {
          type: "radio",
          name: "gathering-finalize-shop",
          "data-testid": "gathering-finalize-shop-select",
          "data-gathering-control-purpose": "gathering-finalize-shop-select",
          "data-finalize-selected": selected ? "true" : "false",
          checked: selected,
          class: "gth-radio",
        },
        []
      );
      radio.addEventListener("click", function () {
        selectFinalizeShop(shop.shopId);
      });
      children.push(radio);
    }
    children.push(el("span", { class: "gth-shop-rank" }, [String(index + 1)]));
    children.push(
      el("div", { class: "gth-shop-body" }, [
        el("div", { class: "gth-shop-name-row" }, [
          el("span", { class: "gth-shop-name" }, [shop.name]),
          leaders[shop.shopId]
            ? el("span", { class: "gth-shop-leader-badge" }, ["いちばん人気"])
            : null,
        ]),
        renderShortlistedShopVoteRow(shop),
        detailRow,
      ])
    );
    children.push(
      el(
        "a",
        {
          "data-testid": "gathering-shortlisted-shop-page-link",
          href: shop.providerPageUrl,
          target: "_blank",
          rel: "noopener noreferrer",
          class: "gth-shop-link",
        },
        ["店のページを見る"]
      )
    );
    return el("div", attrs, children);
  }

  function initializeShortlistedShopMap(container, shops) {
    if (activeShortlistedShopMap) {
      activeShortlistedShopMap.remove();
      activeShortlistedShopMap = null;
    }
    if (!window.L || !container || shops.length === 0) {
      return;
    }
    // **Fixed 2026-09-19 (board comparison finding)**: Leaflet's own
    // default zoom control sits top-left, exactly where gth-shop-panel
    // also floats (ADR-0062 decision 1) -- covering this pane's own
    // "店の候補" heading. Moved to top-right (an empty corner on every
    // board frame, party2/d2/D1-a-*), the same corner this map's own
    // attribution credit would otherwise use if it were enabled (it is
    // not, per this file's existing attributionControl: false).
    var map = window.L.map(container, { attributionControl: false, zoomControl: false });
    window.L.control.zoom({ position: "topright" }).addTo(map);
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);
    var latLngs = shops.map(function (shop) {
      return [shop.location.latitude, shop.location.longitude];
    });
    map.fitBounds(window.L.latLngBounds(latLngs), { padding: [24, 24] });
    shops.forEach(function (shop, index) {
      var icon = window.L.divIcon({
        className: "gathering-shortlisted-shop-map-marker-icon",
        html: '<span class="gathering-shortlisted-shop-map-marker-visual"></span>',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      // keyboard: false -- these pins are display-only (organizerDashboard.
      // shortlistedShopVotes.list.item.detailFields.map scope note: "shops'
      // own relative position", not an interactive control of their own).
      var marker = window.L.marker(latLngs[index], { icon: icon, keyboard: false });
      marker.addTo(map);
      var markerEl = marker.getElement();
      if (!markerEl) {
        return;
      }
      markerEl.setAttribute("data-testid", "gathering-shortlisted-shop-map-marker");
      markerEl.setAttribute("data-shop-id", shop.shopId);
    });
    activeShortlistedShopMap = map;
  }

  var pendingShortlistedShopMap = null;

  // **Restructured 2026-09-17 (ADR-0062 decision 1, human decision, board
  // D1: 「地図いっぱい・一覧を浮かせる」)**: this pane's own map now fills
  // the pane (gth-shop-stage below is position:relative, the map is
  // position:absolute inset:0 within it), with the shop list rendered as a
  // panel floating over the map's own top-left corner on wide layouts (PC)
  // or rising from the bottom on narrow ones (mobile) -- board D1's own
  // "PCは左に浮かせた一覧パネル、スマホは下のシート" split, handled entirely
  // by organizer.css's own media query (this contract does not fix
  // renderModes for this file). Paying the cost board D1's own note names:
  // the panel's own footprint can hide pins directly underneath it.
  function renderShortlistedShopVotes() {
    var phase = state.gathering.phase;
    var shops = state.gathering.shortlistedShops;
    var leaders = computeCurrentLeaderShopIds(shops);
    var respondedCount = shops.reduce(function (max, shop) {
      return Math.max(max, shop.respondedParticipantCount);
    }, 0);
    var list = el(
      "div",
      { "data-testid": "gathering-shortlisted-shop-list", class: "gth-shop-list" },
      shops.map(function (shop, index) {
        return renderShortlistedShopItem(shop, index, leaders);
      })
    );
    var mapContainer = el(
      "div",
      { "data-testid": "gathering-shortlisted-shop-map", class: "gth-shop-map" },
      []
    );
    pendingShortlistedShopMap = { container: mapContainer, shops: shops };

    // **Fixed 2026-09-19 (real render-invariant finding, L5)**: board D1/D2
    // show exactly two children in gth-bottom-bar (status text + the one
    // primary button) -- shopSelectionEntry.open ("店を絞りなおす") never
    // appears there. An earlier revision added it to the bar as a third
    // child anyway; at narrow widths the two buttons alone left the status
    // text (no white-space:nowrap, unlike a button) only ~70px of flex
    // space, wrapping it across 8+ lines and inflating the bar to ~290px
    // tall -- three times this file's own reserved clearance below,
    // reproducing the exact defect this fix closes (a shop row's own
    // finalizeSelect radio hidden under the inflated bar). Moved into the
    // panel's own head row instead (shopSelectionEntry.open's own
    // presenceRule -- present throughout SELECTING_SHOP -- is unaffected,
    // only its position on screen changes, geometry this contract does not
    // fix).
    var panel = el("div", { class: "gth-shop-panel" }, [
      el("div", { class: "gth-pane-head-row" }, [
        el("div", { class: "gth-pane-head" }, [
          "店の候補 " + shops.length + "件",
          el("span", { class: "gth-pane-sub" }, ["回答 " + respondedCount + "人"]),
        ]),
        phase === "SELECTING_SHOP"
          ? renderShopSelectionEntry("店を絞りなおす", "gth-btn gth-btn-small")
          : null,
      ]),
      list,
    ]);

    var stageChildren = [mapContainer, panel];

    if (phase === "SELECTING_SHOP") {
      var selectedShop = shops.filter(function (shop) {
        return shop.shopId === state.finalizeSelectedShopId;
      })[0];
      var status = el("div", { class: "gth-bottom-bar-status" }, [
        selectedShop ? selectedShop.name + " を選んでいます" : "確定する店を選んでください",
      ]);
      var finalizeOpen = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-finalize-open",
          "data-gathering-control-purpose": "gathering-finalize-open",
          disabled: !state.finalizeSelectedShopId,
          class: "gth-btn gth-btn-primary",
        },
        ["この店で確定"]
      );
      finalizeOpen.addEventListener("click", openFinalizeGathering);
      // Board D2 (ADR-0062 decision 2, contract-unchanged: the existing
      // disabledState above already satisfies "選ぶ前は押せない", only the
      // bottom-bar position is new): 画面の下に貼り付けた帯.
      stageChildren.push(el("div", { class: "gth-bottom-bar" }, [status, finalizeOpen]));

      if (state.finalizeConfirmOpen) {
        // gth-modal-backdrop: a plain, purposeless scrim behind the
        // viewport-centered dialog (board D3) -- outside
        // forbiddenFormControlCategories' scan, no test id/purpose of its
        // own, the same precedent gathering_create.js's own review-dialog
        // scrim already establishes.
        stageChildren.push(el("div", { class: "gth-modal-backdrop" }, []));
        stageChildren.push(renderFinalizeConfirmDialog(shops));
      }
    }

    return el("div", { class: "gth-pane gth-pane--flush" }, [
      el("div", { class: "gth-shop-stage" }, stageChildren),
    ]);
  }

  // **Replaced 2026-09-17 (ADR-0062 decision 3, human decision, board D3:
  // 「日時とお店があればいい。参加者は書かなくていい」)**: the 3-row
  // before/after changes table this dialog used to show (ADR-0054 decision
  // 5 / ADR-0056 decision 11) is retired outright, its own test id along
  // with it -- replaced by confirmSummary, exactly two facts (date/shop),
  // neither carrying a "before" state (this dialog only ever opens from
  // SELECTING_SHOP, where "before" was always the fixed, uninformative
  // string "未確定"). Still the same open-then-confirm shape
  // deleteGathering already uses (ADR-0054 decision 5) -- only this
  // dialog's own inner content changes. Board D3: PC is a centered small
  // window (gth-confirm-dialog--modal below), mobile rises from the bottom
  // (handled entirely by organizer.css's own media query, no JS branch
  // needed -- this contract does not fix renderModes for this file).
  function renderFinalizeConfirmDialog(shops) {
    var confirmedDate = state.gathering.candidateDates.filter(function (candidateDate) {
      return candidateDate.isConfirmed;
    })[0];
    var selectedShop = shops.filter(function (shop) {
      return shop.shopId === state.finalizeSelectedShopId;
    })[0];

    function summaryRow(label, value) {
      return el("div", { class: "gth-confirm-summary-row" }, [
        el("span", { class: "gth-confirm-summary-label" }, [label]),
        el("span", { class: "gth-confirm-summary-value" }, [value]),
      ]);
    }

    var dateField = el(
      "div",
      {
        "data-testid": "gathering-finalize-confirm-date",
        "data-confirmed-candidate-date": confirmedDate ? confirmedDate.startAt : undefined,
      },
      [summaryRow("日時", confirmedDate ? formatGatheringDateTime(confirmedDate.startAt) : "―")]
    );
    var shopField = el(
      "div",
      {
        "data-testid": "gathering-finalize-confirm-shop",
        "data-shop-id": state.finalizeSelectedShopId,
        "data-shop-name": selectedShop ? selectedShop.name : undefined,
      },
      [summaryRow("お店", selectedShop ? selectedShop.name : state.finalizeSelectedShopId)]
    );
    var confirmSummary = el("div", { class: "gth-confirm-summary" }, [dateField, shopField]);

    var confirmButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-finalize-confirm",
        "data-gathering-control-purpose": "gathering-finalize-confirm",
        class: "gth-btn gth-btn-primary",
      },
      ["確定する"]
    );
    confirmButton.addEventListener("click", confirmFinalizeGathering);
    var cancelButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-finalize-cancel",
        "data-gathering-control-purpose": "gathering-finalize-cancel",
        class: "gth-btn",
      },
      // Board D3: 「もどる」/「確定する」 (this contract does not fix
      // either button's visible text -- gathering-finalize-cancel/
      // -confirm's own testId/purpose are unchanged).
      ["もどる"]
    );
    cancelButton.addEventListener("click", cancelFinalizeGathering);

    var dialog = el(
      "div",
      {
        "data-testid": "gathering-finalize-confirm-dialog",
        class: "gth-confirm-dialog gth-confirm-dialog--finalize gth-confirm-dialog--modal",
        role: "dialog",
        "aria-modal": "true",
        "aria-label": "この内容で確定しますか",
        tabindex: "-1",
      },
      [
        el("p", { class: "gth-confirm-dialog-title" }, ["この内容で確定しますか"]),
        confirmSummary,
        el("div", { class: "gth-inline-form-row" }, [cancelButton, confirmButton]),
      ]
    );

    // モーダルは開いたらフォーカスを中へ、Esc で閉じる、閉じたら発行ボタン
    // (gathering-finalize-open)へ戻す -- identical keyboard shape to
    // gathering-participant-link-issue-dialog (ADR-0061 decision 1) and
    // gathering-create-review-dialog (ADR-0060 decision 5): Esc cancels
    // without finalizing; Tab/Shift+Tab cycle within the dialog only while
    // it is present.
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "Escape" || event.key === "Esc") {
        event.preventDefault();
        cancelFinalizeGathering();
        return;
      }
      if (event.key === "Tab") {
        trapTabWithinDialog(event, dialog);
      }
    });

    return dialog;
  }

  // --- adr/0042: finalizedSummary (Final.dc.html A③) -----------------------
  // **Restructured 2026-09-17 (ADR-0062 decision 4, human decision, board
  // D4: PC案1「パネルに全部」・スマホ案2ベースで畳む、店を選び中と同じ骨組み
  // =地図いっぱい+浮かせたパネル)**: decisionBanner now carries the decided
  // shop's own name directly (data-finalized-shop-name) plus its own map
  // (gathering-decision-shop-map, mirroring participantAnswer.finalizedView
  // .decision.map's exact shape/scope) and provider-page link
  // (gathering-decision-shop-page-link) -- the same "参加者に先に開いた観測
  // 面を、後から幹事にも同じ形で開く" precedent ADR-0056 decision 10
  // established for the participant side.

  // Same overlay-counting technique as participant.js's own
  // initializeDecisionMap (module docstring there explains the full
  // rationale: map.eachLayer, not a hand-kept counter, so an untagged
  // marker/line/ring added by any future code path is still caught).
  function initializeOrganizerDecisionMap(container, shop, searchOrigin) {
    if (activeDecisionMap) {
      activeDecisionMap.remove();
      activeDecisionMap = null;
    }
    if (!window.L || !container) {
      return;
    }
    var map = window.L.map(container, { attributionControl: false });
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);
    var shopLatLng = [shop.location.latitude, shop.location.longitude];
    var boundsLatLngs = [shopLatLng];
    if (searchOrigin) {
      boundsLatLngs.push([searchOrigin.latitude, searchOrigin.longitude]);
    }
    map.fitBounds(window.L.latLngBounds(boundsLatLngs), { padding: [24, 24] });

    function countOverlaysByType() {
      var counts = { marker: 0, line: 0, ring: 0 };
      map.eachLayer(function (layer) {
        if (layer instanceof window.L.Marker) {
          counts.marker += 1;
        } else if (layer instanceof window.L.CircleMarker) {
          counts.ring += 1;
        } else if (layer instanceof window.L.Polyline) {
          counts.line += 1;
        }
      });
      return counts;
    }
    function refreshOverlayCountAttributes() {
      var counts = countOverlaysByType();
      container.setAttribute("data-overlay-marker-count", String(counts.marker));
      container.setAttribute("data-overlay-line-count", String(counts.line));
      container.setAttribute("data-overlay-ring-count", String(counts.ring));
    }
    map.on("layeradd layerremove", refreshOverlayCountAttributes);

    var shopIcon = window.L.divIcon({
      className: "gathering-shortlisted-shop-map-marker-icon",
      html: '<span class="gathering-shortlisted-shop-map-marker-visual"></span>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    });
    var shopMarker = window.L.marker(shopLatLng, { icon: shopIcon, keyboard: false });
    shopMarker.addTo(map);
    var shopMarkerEl = shopMarker.getElement();
    if (shopMarkerEl) {
      shopMarkerEl.setAttribute("data-testid", "gathering-decision-shop-map-marker");
      shopMarkerEl.setAttribute("data-shop-id", shop.shopId);
    }
    if (searchOrigin) {
      var originIcon = window.L.divIcon({
        className: "gathering-search-origin-marker-icon",
        html: '<span class="gathering-search-origin-marker-visual"></span>',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
      var originMarker = window.L.marker([searchOrigin.latitude, searchOrigin.longitude], {
        icon: originIcon,
        keyboard: false,
        alt: "集まる場所",
      });
      originMarker.addTo(map);
      var originEl = originMarker.getElement();
      if (originEl) {
        originEl.setAttribute("data-testid", "gathering-decision-shop-map-origin-marker");
        originEl.setAttribute("aria-label", "集まる場所");
      }
    }
    // No line between the two markers and no walking-radius ring
    // (ADR-0056 decision 10's rationale, applied here to the organizer's
    // own finalized map for the first time, ADR-0062 decision 4): this
    // product does not query a routing service and does not assert a
    // walking path it cannot back with real routing data.
    refreshOverlayCountAttributes();
    activeDecisionMap = map;
  }

  var pendingDecisionMap = null;

  function renderFinalizedSummary() {
    var confirmed = state.gathering.candidateDates.filter(function (candidateDate) {
      return candidateDate.isConfirmed;
    })[0];
    var finalizedShop = state.gathering.shortlistedShops.filter(function (shop) {
      return shop.shopId === state.gathering.finalizedShopId;
    })[0];
    var bodyChildren = [
      el("div", { class: "gth-decision-row" }, [
        el("span", { class: "gth-decision-label" }, ["日時"]),
        el("b", {}, [confirmed ? formatGatheringDateTime(confirmed.startAt) : "―"]),
      ]),
      el("div", { class: "gth-decision-row" }, [
        el("span", { class: "gth-decision-label" }, ["お店"]),
        el("b", {}, [finalizedShop ? finalizedShop.name : state.gathering.finalizedShopId]),
      ]),
    ];
    if (finalizedShop) {
      var mapContainer = el(
        "div",
        { "data-testid": "gathering-decision-shop-map", class: "gth-decision-map" },
        []
      );
      pendingDecisionMap = { container: mapContainer, shop: finalizedShop };
      bodyChildren.push(mapContainer);
      bodyChildren.push(
        el(
          "a",
          {
            "data-testid": "gathering-decision-shop-page-link",
            href: finalizedShop.providerPageUrl,
            target: "_blank",
            rel: "noopener noreferrer",
            class: "gth-shop-link",
          },
          ["店のページを見る"]
        )
      );
    } else {
      pendingDecisionMap = null;
    }
    return el(
      "div",
      {
        "data-testid": "gathering-decision-banner",
        "data-confirmed-candidate-date": confirmed ? confirmed.startAt : undefined,
        "data-finalized-shop-id": state.gathering.finalizedShopId,
        "data-finalized-shop-name": finalizedShop
          ? finalizedShop.name
          : state.gathering.finalizedShopId,
        class: "gth-decision",
      },
      [
        el("span", { class: "gth-decision-badge" }, ["決まりました"]),
        el("div", { class: "gth-decision-body" }, bodyChildren),
      ]
    );
  }

  // Minimal Tab-cycling focus trap while gathering-participant-link-issue-
  // dialog is present -- keeps keyboard focus from silently leaving the
  // dialog onto background controls while it is open (identical shape to
  // gathering_create.js's own trapTabWithinDialog for gathering-create-
  // review-dialog, ADR-0060 decision 5 -- no shared module system exists in
  // this codebase, the same reason el()/csrfToken()/requestJson() are
  // already duplicated per-file).
  function trapTabWithinDialog(event, dialog) {
    var focusable = Array.prototype.slice.call(
      dialog.querySelectorAll("button:not([disabled]), [tabindex]:not([tabindex='-1'])")
    );
    if (focusable.length === 0) {
      return;
    }
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  // gathering-participant-link-issue-dialog (ADR-0061 decision 1): the
  // small window that opens once copyParticipantLink issues a new link. `null`
  // while state.issueDialogOpen is false (issueDialog.presenceRule).
  function renderIssueDialog() {
    if (!state.issueDialogOpen) {
      return null;
    }
    var copyButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-link-issue-dialog-copy",
        "data-gathering-control-purpose": "gathering-participant-link-issue-dialog-copy",
        class: "gth-btn gth-btn-primary gth-btn-block",
      },
      // dialogCopy.requiredOutcome: this contract does not fix the visible
      // text a successful write may show -- the same non-binding wording
      // latitude this file's own "N件" precedent (ADR-0060 decision 9)
      // already takes.
      [state.issueDialogCopied ? "✓ コピーしました" : "リンクをコピー"]
    );
    copyButton.addEventListener("click", copyIssuedLinkFromDialog);

    var closeButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-link-issue-dialog-close",
        "data-gathering-control-purpose": "gathering-participant-link-issue-dialog-close",
        class: "gth-btn",
      },
      ["閉じる"]
    );
    closeButton.addEventListener("click", closeIssueDialog);

    var dialog = el(
      "div",
      {
        "data-testid": "gathering-participant-link-issue-dialog",
        "data-issued-link-url": state.headerIssuedLinkUrl || undefined,
        role: "dialog",
        "aria-modal": "true",
        "aria-label": "発行したリンク",
        tabindex: "-1",
        class: "gth-confirm-dialog gth-issue-dialog",
      },
      [
        el("p", { class: "gth-confirm-dialog-text gth-issue-dialog-url" }, [
          truncateIssuedLinkUrlForDisplay(state.headerIssuedLinkUrl),
        ]),
        el("div", { class: "gth-inline-form-row" }, [copyButton, closeButton]),
      ]
    );

    // モーダルは開いたらフォーカスを中へ、Esc で閉じる、閉じたら発行ボタンへ
    // 戻す (identical keyboard shape to gathering-create-review-dialog,
    // ADR-0060 decision 5): Esc closes without writing to the clipboard;
    // Tab/Shift+Tab cycle within the dialog only while it is present.
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "Escape" || event.key === "Esc") {
        event.preventDefault();
        closeIssueDialog();
        return;
      }
      if (event.key === "Tab") {
        trapTabWithinDialog(event, dialog);
      }
    });

    return dialog;
  }

  // This contract does not fix the visible text shown for "a URL の一部"
  // (issueDialog's own board note) -- a short, non-binding truncation so
  // the dialog does not have to lay out a full, potentially long URL.
  function truncateIssuedLinkUrlForDisplay(url) {
    if (!url) {
      return "";
    }
    if (url.length <= 46) {
      return url;
    }
    return url.slice(0, 26) + "…" + url.slice(-16);
  }

  function renderParticipantLinkCopy() {
    var button = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-link-copy",
        "data-gathering-control-purpose": "gathering-participant-link-copy",
        class: "gth-btn gth-btn-primary",
      },
      // **Changed 2026-09-17 (ADR-0061 decision 1)**: this contract does not
      // fix the visible text either, but "リンクを発行" reads accurately now
      // that this activation only issues a link and opens the dialog below,
      // rather than copying to the clipboard itself.
      ["リンクを発行"]
    );
    button.addEventListener("click", copyParticipantLink);

    var children = [button];
    var dialog = renderIssueDialog();
    if (dialog) {
      children.push(dialog);
    }
    return el("div", { class: "gth-issue" }, children);
  }

  function renderParticipantLinkItem(link) {
    var recopyButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-link-recopy",
        "data-gathering-control-purpose": "gathering-participant-link-recopy",
        disabled: link.revoked,
        "data-issued-link-url": state.recopiedLinkUrls[link.id] || undefined,
        class: "gth-btn gth-btn-small",
      },
      ["再コピー"]
    );
    recopyButton.addEventListener("click", function () {
      recopyParticipantLink(link.id);
    });

    var children = [
      el("span", { class: "gth-link-name" }, [link.displayName === null ? "名無し" : link.displayName]),
      el("div", { class: "gth-link-actions" }, [recopyButton]),
    ];

    // participantLinkList.item.revoke.presenceRule -- **changed 2026-09-12
    // (ADR-0055 decision 2)**: present only for a row whose data-has-
    // responded is "false" and data-revoked is "false", and only while
    // phase is SCHEDULING or SELECTING_SHOP. An answered or already-revoked
    // row no longer carries a disabled revoke control at all.
    var canRevoke = !link.hasResponded && !link.revoked && state.gathering.phase !== "FINALIZED";
    if (canRevoke) {
      var revokeButton = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-participant-link-revoke",
          "data-gathering-control-purpose": "gathering-participant-link-revoke",
          class: "gth-btn gth-btn-small",
        },
        ["失効"]
      );
      revokeButton.addEventListener("click", function () {
        revokeParticipantLink(link.id);
      });
      children[1].appendChild(revokeButton);
    }

    return el(
      "div",
      {
        "data-testid": "gathering-participant-link-item",
        "data-participant-link-id": link.id,
        "data-issued-at": link.issuedAt,
        "data-has-responded": link.hasResponded ? "true" : "false",
        "data-revoked": link.revoked ? "true" : "false",
        "data-participant-named": link.displayName === null ? "false" : "true",
        class: "gth-link-row",
      },
      children
    );
  }

  function renderParticipantLinkList() {
    return el(
      "div",
      { "data-testid": "gathering-participant-link-list", class: "gth-link-list" },
      state.participantLinks.map(renderParticipantLinkItem)
    );
  }

  // ADR-0056 decision 1: one row per participant link, one cell per
  // candidate date that link answered -- reads
  // ParticipantLinkSummary.scheduleResponses (v0.12.0). Read defensively
  // (`|| []`): this deployment's Python side of this round has not yet
  // populated the field (this file's own module docstring records the
  // coordination point), so an absent value renders as an all-empty row
  // rather than throwing.
  function renderResponseTable(leaders) {
    var candidateDateStartAtById = {};
    state.gathering.candidateDates.forEach(function (candidateDate) {
      candidateDateStartAtById[candidateDate.id] = candidateDate.startAt;
    });
    // ADR-0060 decision 7 (2026-09-16): header/headerCell make "column" a
    // real, orderable DOM concept for the first time -- DOM order equals
    // candidateDateList.orderingInvariant's own order (startAt ascending,
    // decision 6), which state.gathering.candidateDates already carries
    // (services.candidate_dates_with_tallies now sorts by startAt). The
    // header cell itself carries no data-current-leader -- callers read
    // that fact from the corresponding gathering-candidate-date element
    // instead (architect design judgment, avoids a second source of truth).
    var headerCells = state.gathering.candidateDates.map(function (candidateDate) {
      return el("span", {
        "data-testid": "gathering-response-table-header-cell",
        "data-candidate-date-id": candidateDate.id,
        class: "gth-response-header-cell" + (leaders[candidateDate.id] ? " gth-response-header-cell--leader" : ""),
      }, [formatGatheringDate(candidateDate.startAt)]);
    });
    var header = el(
      "div",
      { "data-testid": "gathering-response-table-header", class: "gth-response-header" },
      headerCells
    );
    // ADR-0060 decision 7: one instance per CandidateDate currently carrying
    // data-current-leader="true" -- zero when no one has responded yet,
    // more than one when tied.
    var leaderSummaryItems = state.gathering.candidateDates
      .filter(function (candidateDate) {
        return Boolean(leaders[candidateDate.id]);
      })
      .map(function (candidateDate) {
        return el("span", {
          "data-testid": "gathering-response-table-leader-summary",
          "data-candidate-date-id": candidateDate.id,
          class: "gth-response-leader-summary-item",
        }, [
          formatGatheringDate(candidateDate.startAt) + " 行ける " + candidateDate.goingCount + "/" +
            state.gathering.activeParticipantLinkCount,
        ]);
      });
    var leaderSummaryChildren = [el("span", { class: "gth-response-leader-summary-label" }, ["有力"])].concat(
      leaderSummaryItems.length > 0
        ? leaderSummaryItems
        : [el("span", { class: "gth-response-leader-summary-empty" }, ["まだありません"])]
    );
    var leaderSummary = el(
      "div",
      { class: "gth-response-leader-summary" },
      leaderSummaryChildren
    );
    var rows = state.participantLinks.map(function (link) {
      var responses = link.scheduleResponses || [];
      var cells = responses.map(function (entry) {
        var startAt = candidateDateStartAtById[entry.candidateDateId];
        var label = (startAt ? formatGatheringDate(startAt) + " " : "") +
          (SCHEDULE_RESPONSE_LABELS[entry.status] || "");
        return el(
          "span",
          {
            "data-testid": "gathering-response-table-cell",
            "data-candidate-date-id": entry.candidateDateId,
            "data-response-status": entry.status,
            class: "gth-response-cell gth-response-cell--" + entry.status.toLowerCase(),
          },
          [label]
        );
      });
      return el(
        "div",
        {
          "data-testid": "gathering-response-table-row",
          "data-participant-link-id": link.id,
          class: "gth-response-row",
        },
        [
          el("span", { class: "gth-response-row-name" }, [
            link.displayName === null ? "名無し" : link.displayName,
          ]),
          el(
            "div",
            { class: "gth-response-row-cells" },
            cells.length > 0 ? cells : [el("span", { class: "gth-response-row-empty" }, ["未回答"])]
          ),
        ]
      );
    });
    return el("div", { class: "gth-pane" }, [
      el("div", { class: "gth-pane-head" }, ["誰が・どの日に答えたか"]),
      leaderSummary,
      el(
        "div",
        { "data-testid": "gathering-response-table", class: "gth-response-table" },
        [header].concat(rows)
      ),
    ]);
  }

  // --- focus-restore-across-rerender BEGIN (identical copy in
  // participant.js/gathering_create.js; keep all three in sync) ---
  //
  // render() below fully rebuilds this screen's DOM on every state change
  // (`root.innerHTML = ""`), including rebuilds triggered by an in-flight
  // fetch's own follow-up response landing after the user has since moved
  // keyboard focus onto a freshly built control (real-browser measurement,
  // 2026-09-15: the organizer dashboard's tentativelySelectCandidateDate
  // issues an open-shop-preview request and renders immediately, then
  // renders again once that request resolves; when the user Tab'd to
  // "この日にする" and pressed Enter in between, the second render silently
  // dropped document.activeElement to <body> before Enter's own keydown
  // ever fired -- the button still existed, but as a brand-new DOM node the
  // browser had already un-focused). Every render()-driven screen in this
  // codebase duplicates this same small capture/restore pair around its own
  // rebuild (no shared module system exists here, the same reason
  // el()/csrfToken()/requestJson() are already duplicated per-file).
  //
  // The identity carried across a rebuild is deliberately not a live DOM
  // reference (the old node is gone) but this screen's own observable
  // contract surface: data-testid, plus whichever other data-* attributes
  // the same element actually carries (data-candidate-date-id/
  // data-participant-link-id/data-shop-id disambiguate the common case of
  // several same-data-testid rows; a control with none of those -- e.g.
  // this screen's single gathering-confirm-date-select button -- needs
  // none). Where even that full attribute set does not uniquely resolve (an
  // attribute-less control repeated verbatim, e.g. several identical
  // gathering-candidate-date-remove buttons), the position among same-
  // data-testid elements at capture time is kept as a last-resort
  // tiebreaker, since render() reproduces the same list order.
  function captureFocusDescriptor(container, activeElement) {
    if (!activeElement || !container.contains(activeElement)) {
      return null;
    }
    var testId = activeElement.getAttribute("data-testid");
    if (!testId) {
      return null;
    }
    var attrs = {};
    Array.prototype.forEach.call(activeElement.attributes, function (attribute) {
      if (attribute.name.indexOf("data-") === 0 && attribute.name !== "data-testid") {
        attrs[attribute.name] = attribute.value;
      }
    });
    var sameTestId = Array.prototype.slice.call(
      container.querySelectorAll('[data-testid="' + testId + '"]')
    );
    return { testId: testId, attrs: attrs, index: sameTestId.indexOf(activeElement) };
  }

  function findElementForFocusDescriptor(container, descriptor) {
    if (!descriptor) {
      return null;
    }
    var candidates = Array.prototype.slice.call(
      container.querySelectorAll('[data-testid="' + descriptor.testId + '"]')
    );
    var attrKeys = Object.keys(descriptor.attrs);
    // No disambiguating data-* attribute at all (a single unique control, or
    // several verbatim-identical ones): the position among same-data-testid
    // elements is the only signal available, and render() reproduces the
    // same list order. Otherwise, only an exact attribute match counts as
    // "the same element" -- falling back to position here could silently
    // hand focus to an unrelated sibling row once the originally-focused
    // one is actually gone (e.g. its own candidate date/shop/link was
    // removed), which is worse than not restoring focus at all.
    if (attrKeys.length === 0) {
      return candidates[descriptor.index] || null;
    }
    var exact = candidates.filter(function (candidate) {
      return attrKeys.every(function (key) {
        return candidate.getAttribute(key) === descriptor.attrs[key];
      });
    });
    return exact.length > 0 ? exact[0] : null;
  }

  function restoreFocusFromDescriptor(container, descriptor) {
    var target = findElementForFocusDescriptor(container, descriptor);
    if (!target || target.disabled || typeof target.focus !== "function") {
      return;
    }
    target.focus({ preventScroll: true });
  }
  // --- focus-restore-across-rerender END ---

  function render() {
    var focusDescriptor = captureFocusDescriptor(root, document.activeElement);
    if (activeAddCandidateDateCalendar) {
      activeAddCandidateDateCalendar.destroy();
      activeAddCandidateDateCalendar = null;
    }
    if (activeShortlistedShopMap) {
      activeShortlistedShopMap.remove();
      activeShortlistedShopMap = null;
    }
    if (activeDecisionMap) {
      activeDecisionMap.remove();
      activeDecisionMap = null;
    }
    pendingShortlistedShopMap = null;
    pendingDecisionMap = null;
    root.innerHTML = "";
    if (!state.gathering) {
      return;
    }
    var phase = state.gathering.phase;

    var header = el("div", { class: "gth-header" }, [
      el("div", { class: "gth-header-row" }, [
        el("div", { class: "gth-title" }, [state.gathering.title]),
        renderDeleteGathering(),
      ]),
      renderPhaseIndicator(),
      el("div", { class: "gth-stats-row" }, [renderResponseSummary(), renderUnansweredSummary()]),
    ]);

    var candidateDateLeaders = computeCandidateDateLeaders(state.gathering.candidateDates);
    var candidateDateListChildren = state.gathering.candidateDates.map(function (candidateDate) {
      return renderCandidateDate(candidateDate, candidateDateLeaders);
    });
    if (phase === "SCHEDULING") {
      candidateDateListChildren = candidateDateListChildren.concat([renderAddCandidateDateOpen()]);
    }
    var candidateDateList = el(
      "div",
      { "data-testid": "gathering-candidate-date-list", class: "gth-date-list" },
      candidateDateListChildren
    );

    var schedulePaneChildren = [
      el("div", { class: "gth-pane-head" }, ["日程"]),
      candidateDateList,
    ];
    if (phase === "SCHEDULING") {
      schedulePaneChildren.push(renderOpenShopPreview());
      schedulePaneChildren.push(renderConfirmDate());
    }
    var schedulePane = el("div", { class: "gth-pane" }, schedulePaneChildren);

    var sections = [header, schedulePane];

    if (phase === "SELECTING_SHOP" && state.gathering.votingStartedAt === null) {
      sections.push(
        el("div", { class: "gth-pane" }, [
          el("div", { class: "gth-pane-head" }, ["お店"]),
          renderShopSelectionEntry("開いている店から選ぶ"),
        ])
      );
    }

    // **Changed 2026-09-17 (ADR-0062 decision 4, human decision, board D4:
    // 「決まった店と集まる場所だけ」)**: shortlistedShopVotes.presenceRule
    // narrows from "votingStartedAt non-null, any phase" to "votingStartedAt
    // non-null AND finalizedShopId null" -- gathering-shortlisted-shop-list/
    // -item no longer remain present once FINALIZED as a frozen "vote
    // record" panel; see finalizedSummary.decisionBanner below for what
    // replaces that record.
    if (state.gathering.votingStartedAt !== null && state.gathering.finalizedShopId === null) {
      sections.push(renderShortlistedShopVotes());
    }

    if (phase === "FINALIZED") {
      sections.push(renderFinalizedSummary());
    }

    // ADR-0056 decision 1: always present, alongside (not replacing) the
    // per-candidate-date tally above and the link-management list below.
    sections.push(renderResponseTable(candidateDateLeaders));

    var linkPaneHeadChildren = [el("div", { class: "gth-pane-head" }, ["発行済みリンク"])];
    if (phase !== "FINALIZED") {
      linkPaneHeadChildren.push(renderParticipantLinkCopy());
    } else {
      // ADR-0056 decision 11: a short badge marking that issuance itself
      // has ended on purpose, distinct from participantLinkCopy's own
      // plain absence (which by itself carried no such signal).
      linkPaneHeadChildren.push(
        el(
          "span",
          { "data-testid": "gathering-participant-link-issuance-closed", class: "gth-badge-muted" },
          ["発行はおわり"]
        )
      );
    }
    sections.push(
      el("div", { class: "gth-pane" }, [
        el("div", { class: "gth-pane-head-row" }, linkPaneHeadChildren),
        renderParticipantLinkList(),
      ])
    );

    root.appendChild(el("div", { class: "gth-dash" }, sections));

    if (pendingShortlistedShopMap) {
      initializeShortlistedShopMap(
        pendingShortlistedShopMap.container,
        pendingShortlistedShopMap.shops
      );
    }
    if (pendingDecisionMap) {
      initializeOrganizerDecisionMap(
        pendingDecisionMap.container,
        pendingDecisionMap.shop,
        organizerSearchOrigin
      );
    }
    restoreFocusFromDescriptor(root, focusDescriptor);

    // Explicit open/close focus management for gathering-participant-link-
    // issue-dialog -- distinct from the generic restoreFocusFromDescriptor
    // above, which can only restore focus to an element that still exists
    // after this rebuild (identical shape to gathering_create.js's own
    // pendingReviewFocus, ADR-0060 decision 5).
    if (state.pendingIssueDialogFocus === "open") {
      var issueDialogNode = root.querySelector(
        '[data-testid="gathering-participant-link-issue-dialog"]'
      );
      if (issueDialogNode) {
        issueDialogNode.focus({ preventScroll: true });
      }
      state.pendingIssueDialogFocus = null;
    } else if (state.pendingIssueDialogFocus === "close") {
      var issueOpenButtonNode = root.querySelector(
        '[data-testid="gathering-participant-link-copy"]'
      );
      if (issueOpenButtonNode) {
        issueOpenButtonNode.focus({ preventScroll: true });
      }
      state.pendingIssueDialogFocus = null;
    }

    // Explicit open/close focus management for gathering-finalize-confirm-
    // dialog (ADR-0062 decision 3, board D3) -- the same shape as
    // gathering-participant-link-issue-dialog's own pendingIssueDialogFocus
    // just above.
    if (state.pendingFinalizeConfirmFocus === "open") {
      var finalizeConfirmDialogNode = root.querySelector(
        '[data-testid="gathering-finalize-confirm-dialog"]'
      );
      if (finalizeConfirmDialogNode) {
        finalizeConfirmDialogNode.focus({ preventScroll: true });
      }
      state.pendingFinalizeConfirmFocus = null;
    } else if (state.pendingFinalizeConfirmFocus === "close") {
      var finalizeOpenButtonNode = root.querySelector('[data-testid="gathering-finalize-open"]');
      if (finalizeOpenButtonNode) {
        finalizeOpenButtonNode.focus({ preventScroll: true });
      }
      state.pendingFinalizeConfirmFocus = null;
    }
  }

  // contracts/candidate-search-browser-interface.yaml's gatheringEntry
  // section: gatheringEntry.mobileBar's own children are plain,
  // server-rendered HTML (organizer_primary_nav.html) and therefore
  // already present before this script runs. Only mobileBarGathering's own
  // badgeCount attribute is set here, once fetched (duplicated verbatim
  // from web/static/dining_radar/web/candidate.js's own
  // loadGatheringEntryBadge; no shared module system exists in this
  // codebase). Unlike candidate-search's own chip, this screen never
  // builds candidate-gathering-entry at all -- ADR-0059 decision 2 removed
  // it from every one of gathering-scheduling-browser-interface.yaml's
  // organizer-facing screens (see organizer_primary_nav.html's own
  // comment).
  function loadGatheringEntryBadge() {
    fetch("/gatherings/in-progress-count", { credentials: "same-origin" })
      .then(function (response) {
        return response.status === 200 ? response.json() : null;
      })
      .then(function (body) {
        if (!body) {
          return;
        }
        var count = body.inProgressGatheringCount;
        var barGathering = document.querySelector('[data-testid="candidate-primary-nav-gathering"]');
        if (!barGathering) {
          return;
        }
        if (count > 0) {
          barGathering.setAttribute("data-in-progress-gathering-count", String(count));
        } else {
          barGathering.removeAttribute("data-in-progress-gathering-count");
        }
      })
      .catch(function () {});
  }

  // ADR-0059 decisions 1-2: renderModes.twoColumnLayout/
  // mapPrimaryTouchLayout are mutually exclusive -- exactly one of
  // [data-primary-nav-desktop] (the ≡ menu) and every
  // [data-primary-nav-mobile] node (the bottom bar and its own account
  // sheet) survives in the live DOM. Both are server-rendered
  // unconditionally in organizer_primary_nav.html; this removes whichever
  // one does not match the current viewport, once, at load (duplicated
  // verbatim from candidate.js's own initializePrimaryNav -- see that
  // function's own comment for the full renderModel/TDR-AUTH reasoning).
  // The nav lives outside #gathering-app (this file's own render() rebuild
  // root), so it is unaffected by, and never needs to cooperate with,
  // restoreFocusFromDescriptor above.
  function initializePrimaryNav() {
    var isTwoColumn = window.matchMedia && window.matchMedia("(min-width: 64rem)").matches;
    if (isTwoColumn) {
      document.querySelectorAll("[data-primary-nav-mobile]").forEach(function (node) {
        node.remove();
      });
    } else {
      var desktopNav = document.querySelector("[data-primary-nav-desktop]");
      if (desktopNav) {
        desktopNav.remove();
      }
    }

    var accountButton = document.querySelector('[data-testid="candidate-primary-nav-account"]');
    var accountSheet = document.getElementById("primary-nav-account-sheet");
    if (accountButton && accountSheet) {
      accountButton.addEventListener("click", function () {
        var willOpen = accountSheet.hasAttribute("hidden");
        if (willOpen) {
          accountSheet.removeAttribute("hidden");
        } else {
          accountSheet.setAttribute("hidden", "");
        }
        accountButton.setAttribute("aria-expanded", willOpen ? "true" : "false");
      });
    }
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" && event.key !== "Esc") {
        return;
      }
      var openMenu = document.querySelector(".primary-nav-menu[open]");
      if (openMenu) {
        openMenu.removeAttribute("open");
        var toggle = openMenu.querySelector('[data-testid="candidate-primary-nav-menu-toggle"]');
        if (toggle) {
          toggle.focus();
        }
      }
      if (accountSheet && !accountSheet.hasAttribute("hidden")) {
        accountSheet.setAttribute("hidden", "");
        if (accountButton) {
          accountButton.setAttribute("aria-expanded", "false");
          accountButton.focus();
        }
      }
    });
  }

  initializePrimaryNav();
  loadGathering();
  loadGatheringEntryBadge();
})();
