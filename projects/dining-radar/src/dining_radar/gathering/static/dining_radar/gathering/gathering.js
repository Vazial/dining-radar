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
 *     6), and carries data-added-after-voting-started (ADR-0056 decision 6,
 *     computed client-side from fields already present on the response --
 *     no API change needed for this organizer-facing half).
 *   - finalizeSubmit is replaced by a 4-part open/confirm-dialog/confirm/
 *     cancel flow, the same shape deleteGathering already used (ADR-0054
 *     decision 5), with a 3-row before/after table (ADR-0056 decision 11).
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
    headerIssuedLinkUrl: null,
    recopiedLinkUrls: {},
    // adr/0042: client-side pending radio selection for
    // shortlistedShopVotes.list.item.finalizeSelect, before
    // gathering-finalize-open is activated.
    finalizeSelectedShopId: null,
    // ADR-0054 decision 5 / ADR-0056 decision 11: whether
    // gathering-finalize-confirm-dialog is currently revealed (client-side
    // only -- opening it calls no public operation).
    finalizeConfirmOpen: false,
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

  function formatGatheringDate(isoString) {
    var date = new Date(isoString);
    var month = date.getUTCMonth() + 1;
    var day = date.getUTCDate();
    var weekday = WEEKDAY_LABELS_JA[date.getUTCDay()];
    return month + "/" + day + "（" + weekday + "）";
  }
  // --- shared-date-formatting END ---

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
    function selectable(iso) {
      return iso > todayIso;
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
      var isWeekend = date.getDay() === 0 || date.getDay() === 6;
      var isToday = iso === todayIso;
      var isSelected = effectiveSelected(iso);
      var classNames = ["gth-cal-day"];
      if (isWeekend) {
        classNames.push("gth-cal-day--weekend");
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
        class: classNames.join(" "),
      };
      if (enabled) {
        attrs["data-gathering-control-purpose"] = options.dayPurpose;
        attrs.role = "button";
        attrs.tabindex = "0";
      } else {
        attrs["aria-disabled"] = "true";
      }
      var cell = el("div", attrs, [String(date.getDate())]);
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

      var pickedRows = sortedSelectedIsos().map(function (iso) {
        var removeButton = el(
          "button",
          {
            type: "button",
            "data-testid": options.removeSelectedTestId,
            "data-gathering-control-purpose": options.removeSelectedPurpose,
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
    // Real-browser measurement (2026-08-31): a *second* activation of this
    // same control was passing contracts/gathering-scheduling-browser-
    // interface.yaml's own "data-issued-link-url becomes non-empty"
    // acceptance check *immediately*, before this activation's own request
    // had even reached the server. Clearing the tracked value synchronously
    // here, before the async request even starts, makes every activation
    // transition through an observable absent-or-empty -> non-empty edge.
    state.headerIssuedLinkUrl = null;
    render();
    requestJson("POST", gatheringUrl() + "/participant-links", { count: 1 }).then(function (result) {
      if (result.status !== 201) {
        return;
      }
      var issued = result.body.issuedLinks[0];
      state.headerIssuedLinkUrl = issued.url;
      if (window.navigator && window.navigator.clipboard) {
        window.navigator.clipboard.writeText(issued.url).catch(function () {});
      }
      state.gathering.totalIssuedParticipantLinks = result.body.totalIssuedParticipantLinks;
      state.gathering.activeParticipantLinkCount = result.body.activeParticipantLinkCount;
      loadParticipantLinksOnly();
    });
  }

  function recopyParticipantLink(linkId) {
    state.recopiedLinkUrls[linkId] = null;
    render();
    requestJson("POST", gatheringUrl() + "/participant-links/" + linkId + "/recopy").then(
      function (result) {
        if (result.status === 200) {
          state.recopiedLinkUrls[linkId] = result.body.url;
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
        render();
      } else if (
        result.status === 409 &&
        result.body &&
        result.body.code === "DUPLICATE_CANDIDATE_DATE"
      ) {
        state.addCandidateDateDuplicateError = true;
        state.addCandidateDateNotInFutureError = false;
        render();
      } else if (
        result.status === 409 &&
        result.body &&
        result.body.code === "CANDIDATE_DATE_NOT_IN_FUTURE"
      ) {
        state.addCandidateDateNotInFutureError = true;
        state.addCandidateDateDuplicateError = false;
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

  function openFinalizeGathering() {
    if (!state.finalizeSelectedShopId) {
      return;
    }
    state.finalizeConfirmOpen = true;
    render();
  }

  function cancelFinalizeGathering() {
    // finalizeCancel.requiredOutcome: makes the confirm dialog absent
    // without calling finalizeGathering. Every shop's own
    // data-finalize-selected is unaffected.
    state.finalizeConfirmOpen = false;
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

  function renderCandidateDate(candidateDate) {
    var isTentative = state.tentativeSelectedId === candidateDate.id;
    var isSchedulingPhase = state.gathering.phase === "SCHEDULING";
    var attrs = {
      "data-testid": "gathering-candidate-date",
      "data-candidate-date-id": candidateDate.id,
      "data-going-count": candidateDate.goingCount,
      "data-maybe-count": candidateDate.maybeCount,
      "data-not-going-count": candidateDate.notGoingCount,
      "data-confirmed": candidateDate.isConfirmed ? "true" : "false",
      "data-tentative-selected": isTentative ? "true" : "false",
      class: "gth-date" + (isSchedulingPhase ? " gth-date--pickable" : ""),
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

  function shopAddedAfterVotingStarted(shop) {
    if (!state.gathering.votingStartedAt) {
      return false;
    }
    return new Date(shop.addedAt).getTime() > new Date(state.gathering.votingStartedAt).getTime();
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
      // ADR-0056 decision 6: computed client-side from addedAt/
      // votingStartedAt, both already present on this response -- no API
      // change needed for this organizer-facing half.
      "data-added-after-voting-started": shopAddedAfterVotingStarted(shop) ? "true" : "false",
      class: "gth-shop-row gth-shop-row--vote",
    };
    if (leaders[shop.shopId]) {
      attrs.class += " gth-shop-row--leader";
    }
    var tallyRow = el("div", { class: "gth-shop-tally-row" }, [
      el("span", {}, [VOTE_LABELS.WANT_TO_GO + " ", el("b", {}, [String(shop.wantToGoCount)])]),
      el("span", {}, [VOTE_LABELS.OK_TO_GO + " ", el("b", {}, [String(shop.okToGoCount)])]),
      el("span", {}, [VOTE_LABELS.NOT_GOING + " ", el("b", {}, [String(shop.notGoingCount)])]),
      el("span", {}, [String(shop.respondedParticipantCount) + "人中"]),
    ]);
    var detailRow = el("div", { class: "gth-shop-detail-row" }, [
      el("span", { class: "gth-shop-detail" }, [String(shop.walkingTimeMinutes) + "分"]),
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
      ),
    ]);
    if (shopAddedAfterVotingStarted(shop)) {
      detailRow.insertBefore(
        el("span", { class: "gth-shop-added-after-badge" }, ["あとから入りました"]),
        detailRow.firstChild
      );
    }
    var children = [
      el("span", { class: "gth-shop-rank" }, [String(index + 1)]),
      el("div", { class: "gth-shop-body" }, [
        el("span", { class: "gth-shop-name" }, [shop.name]),
        tallyRow,
        detailRow,
      ]),
    ];
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
    var map = window.L.map(container, { attributionControl: false });
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

  function renderShortlistedShopVotes() {
    var phase = state.gathering.phase;
    var shops = state.gathering.shortlistedShops;
    var leaders = computeCurrentLeaderShopIds(shops);
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

    var paneChildren = [
      el("div", { class: "gth-pane-head" }, [
        "お店の候補",
        el("span", { class: "gth-pane-sub" }, [
          "並び: 「行きたい」＋「行ってもいい」の合計が多い順",
        ]),
      ]),
      mapContainer,
      list,
    ];

    if (phase === "SELECTING_SHOP") {
      var actions = [renderShopSelectionEntry("店を絞りなおす", "gth-btn")];
      if (shops.length > 0) {
        var finalizeOpen = el(
          "button",
          {
            type: "button",
            "data-testid": "gathering-finalize-open",
            "data-gathering-control-purpose": "gathering-finalize-open",
            disabled: !state.finalizeSelectedShopId,
            class: "gth-btn gth-btn-primary",
          },
          ["日と店を確定する"]
        );
        finalizeOpen.addEventListener("click", openFinalizeGathering);
        actions.push(finalizeOpen);
      }
      paneChildren.push(el("div", { class: "gth-pane-actions" }, actions));

      if (state.finalizeConfirmOpen) {
        paneChildren.push(renderFinalizeConfirmDialog(shops));
      }
    }

    return el("div", { class: "gth-pane" }, paneChildren);
  }

  // ADR-0054 decision 5 / ADR-0056 decision 11: the same open-then-confirm
  // shape deleteGathering already uses, with a 3-row before/after table
  // instead of persuasive prose (ADR-0055 decision 3's "no persuasive prose
  // in production screens" principle does not forbid a factual table).
  function renderFinalizeConfirmDialog(shops) {
    var confirmedDate = state.gathering.candidateDates.filter(function (candidateDate) {
      return candidateDate.isConfirmed;
    })[0];
    var selectedShop = shops.filter(function (shop) {
      return shop.shopId === state.finalizeSelectedShopId;
    })[0];
    var dateAndShopAfter =
      (confirmedDate ? formatGatheringDate(confirmedDate.startAt) : "―") +
      " ・ " +
      (selectedShop ? selectedShop.name : state.finalizeSelectedShopId);

    function changeRow(label, before, after) {
      return el("div", { class: "gth-changes-row" }, [
        el("span", { class: "gth-changes-label" }, [label]),
        el("span", { class: "gth-changes-before" }, [before]),
        el("span", { class: "gth-changes-arrow", "aria-hidden": "true" }, ["→"]),
        el("span", { class: "gth-changes-after" }, [after]),
      ]);
    }

    var changesTable = el(
      "div",
      { "data-testid": "gathering-finalize-confirm-changes", class: "gth-changes-table" },
      [
        changeRow("回答リンク", "発行・取り消しができる", "どちらもできなくなる"),
        changeRow("参加者の画面", "日程・投票に答えられる", "決定だけを見る"),
        changeRow("日と店", "未確定", dateAndShopAfter),
      ]
    );

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
      ["やめる"]
    );
    cancelButton.addEventListener("click", cancelFinalizeGathering);

    return el(
      "div",
      { "data-testid": "gathering-finalize-confirm-dialog", class: "gth-confirm-dialog gth-confirm-dialog--finalize" },
      [changesTable, el("div", { class: "gth-inline-form-row" }, [confirmButton, cancelButton])]
    );
  }

  // --- adr/0042: finalizedSummary (Final.dc.html A③) -----------------------

  function renderFinalizedSummary() {
    var confirmed = state.gathering.candidateDates.filter(function (candidateDate) {
      return candidateDate.isConfirmed;
    })[0];
    var finalizedShop = state.gathering.shortlistedShops.filter(function (shop) {
      return shop.shopId === state.gathering.finalizedShopId;
    })[0];
    return el(
      "div",
      {
        "data-testid": "gathering-decision-banner",
        "data-confirmed-candidate-date": confirmed ? confirmed.startAt : undefined,
        "data-finalized-shop-id": state.gathering.finalizedShopId,
        class: "gth-decision",
      },
      [
        el("span", { class: "gth-decision-badge" }, ["決まりました"]),
        el("div", { class: "gth-decision-body" }, [
          el("div", { class: "gth-decision-row" }, [
            el("span", { class: "gth-decision-label" }, ["日時"]),
            el("b", {}, [confirmed ? formatGatheringDateTime(confirmed.startAt) : "―"]),
          ]),
          el("div", { class: "gth-decision-row" }, [
            el("span", { class: "gth-decision-label" }, ["お店"]),
            el("b", {}, [finalizedShop ? finalizedShop.name : state.gathering.finalizedShopId]),
          ]),
        ]),
      ]
    );
  }

  function renderParticipantLinkCopy() {
    var button = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-link-copy",
        "data-gathering-control-purpose": "gathering-participant-link-copy",
        "data-issued-link-url": state.headerIssuedLinkUrl || undefined,
        class: "gth-btn gth-btn-primary",
      },
      ["回答リンクをコピー"]
    );
    button.addEventListener("click", copyParticipantLink);
    return button;
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
  function renderResponseTable() {
    var candidateDateStartAtById = {};
    state.gathering.candidateDates.forEach(function (candidateDate) {
      candidateDateStartAtById[candidateDate.id] = candidateDate.startAt;
    });
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
    return el(
      "div",
      { class: "gth-pane" },
      [el("div", { class: "gth-pane-head" }, ["誰が・どの日に答えたか"])].concat([
        el("div", { "data-testid": "gathering-response-table", class: "gth-response-table" }, rows),
      ])
    );
  }

  function render() {
    if (activeAddCandidateDateCalendar) {
      activeAddCandidateDateCalendar.destroy();
      activeAddCandidateDateCalendar = null;
    }
    if (activeShortlistedShopMap) {
      activeShortlistedShopMap.remove();
      activeShortlistedShopMap = null;
    }
    pendingShortlistedShopMap = null;
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

    var candidateDateListChildren = state.gathering.candidateDates.map(renderCandidateDate);
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

    if (state.gathering.votingStartedAt !== null) {
      sections.push(renderShortlistedShopVotes());
    }

    if (phase === "FINALIZED") {
      sections.push(renderFinalizedSummary());
    }

    // ADR-0056 decision 1: always present, alongside (not replacing) the
    // per-candidate-date tally above and the link-management list below.
    sections.push(renderResponseTable());

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
  }

  // contracts/candidate-search-browser-interface.yaml's gatheringEntry
  // section (ADR-0054 decision 1): candidate-gathering-entry itself is
  // plain, server-rendered HTML (organizer_dashboard.html) and therefore
  // already present before this script runs. Only the badge is built here,
  // once fetched (duplicated verbatim from
  // web/static/dining_radar/web/candidate.js's own loadGatheringEntryBadge).
  function loadGatheringEntryBadge() {
    var entry = document.querySelector('[data-testid="candidate-gathering-entry"]');
    if (!entry) {
      return;
    }
    fetch("/gatherings/in-progress-count", { credentials: "same-origin" })
      .then(function (response) {
        return response.status === 200 ? response.json() : null;
      })
      .then(function (body) {
        if (!body) {
          return;
        }
        var count = body.inProgressGatheringCount;
        var badge = entry.querySelector('[data-testid="candidate-gathering-entry-badge"]');
        if (count > 0) {
          if (!badge) {
            badge = el(
              "span",
              { "data-testid": "candidate-gathering-entry-badge", "class": "candidate-gathering-entry-badge" },
              []
            );
            entry.appendChild(badge);
          }
          badge.setAttribute("data-in-progress-gathering-count", String(count));
          badge.textContent = String(count);
        } else if (badge) {
          badge.remove();
        }
      })
      .catch(function () {});
  }

  loadGathering();
  loadGatheringEntryBadge();
})();
