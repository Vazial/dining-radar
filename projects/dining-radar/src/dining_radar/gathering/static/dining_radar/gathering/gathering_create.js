/**
 * Organizer gathering-creation screen behaviour (organizerGatheringCreate,
 * contracts/gathering-scheduling-browser-interface.yaml, adr/0038).
 *
 * Entry.dc.html E-2: a name and one or more candidate dates. D10
 * (2026-09-01 human decision): a gathering is created directly in
 * SCHEDULING -- there is no persisted draft phase to model here.
 *
 * **Replaced 2026-09-11 (adr/0051, 2026-09-09 human decision: 候補日は
 * カレンダーで複数選択する)**: the row-based add/remove-row
 * `<input type="datetime-local">` list this screen used to expose
 * (candidateDateRow, its own addRow/removeRow) is retired in favor of a
 * multi-select calendar of the same shape addCandidateDateForm.calendar
 * (gathering.js) already defines -- same day-cell attributes, same "明日
 * 以降のみ" disabled-day rule, same "12:00始まり" UI aid -- but as this
 * screen's own, distinct element (organizerGatheringCreate.calendar, its own
 * test id gathering-create-candidate-date-calendar / day cell
 * gathering-create-candidate-date-day, not shared with addCandidateDateForm.
 * calendar: the two screens' post-submit behavior differs, adr/0051
 * decision 1).
 *
 * **Replaced again 2026-09-13 (adr/0054 decision 3 / adr/0056 decision 3,
 * human decision)**: the vendored flatpickr library this calendar used to be
 * built on (vendor/flatpickr/, 68KB, MIT license) is retired -- the human
 * picked a hand-built "案B｜表" look after seeing it actually run
 * (scratchpad/cal/looks.html + script.js, adopted verbatim for the grid/
 * drag/range-selection mechanics below), and this removes two defects the
 * vendored library caused: the input element it always builds internally
 * (which had to be worked around to satisfy
 * unavailableControls.allGatheringScreenFormControlsMustDeclarePurpose) and,
 * as a side effect of that same workaround, a static year label that never
 * updated on month navigation (friction-log.md FR-033's own resolution: the
 * 3-simultaneous-month display this screen used to default to was itself
 * only there to satisfy a *test's* own batch-registration need across a
 * month boundary, not a real user's -- the product's own default must not be
 * chosen to make a test pass; a test that needs a later month should press
 * this screen's own month-navigation controls instead, exactly as ADR-0054
 * decision 3 records). See buildCandidateDateCalendar in this file (a
 * verbatim-shape duplicate of gathering.js's own copy -- no shared module
 * system exists in this codebase, the same reason el()/csrfToken()/
 * requestJson() are already duplicated across every screen script) for the
 * calendar itself.
 *
 * State kept client-side until a successful submit: `title` and
 * `selectedIsos` (a plain object, ISO date string "YYYY-MM-DD" -> true, one
 * entry per gathering-create-candidate-date-day currently carrying
 * data-selected="true").
 */
(function () {
  "use strict";

  var root = document.getElementById("gathering-create-app");
  if (!root) {
    return;
  }

  var state = {
    title: "",
    selectedIsos: {},
    duplicateError: false,
    notInFutureError: false,
    // ADR-0060 decision 4: a weekend/Japan-public-holiday date rejected by
    // CANDIDATE_DATE_NOT_A_BUSINESS_DAY -- calendar disabling below already
    // prevents most such attempts client-side, but the server remains the
    // authoritative check.
    notABusinessDayError: false,
    // ADR-0060 decision 5: whether gathering-create-review-dialog is
    // currently revealed (client-side only -- opening it calls no public
    // operation).
    reviewOpen: false,
    // "YYYY-MM" -- which month of currently-selected days this dialog's own,
    // independent month paging is currently displaying (initial position:
    // the earliest month containing a currently-selected day).
    reviewViewMonthKey: null,
    // Set to "open"/"close" by openReview()/closeReview() below, consumed
    // once by render() to move keyboard focus into/out of the dialog on the
    // exact render that makes it present/absent -- distinct from the
    // generic focus-restore-across-rerender mechanism below, which only
    // ever restores focus to an element that still exists after a rebuild
    // (on first open there is nothing inside the dialog yet to restore to;
    // on close, the dialog's own controls are the ones being removed).
    pendingReviewFocus: null,
  };

  // The self-made calendar instance backing organizerGatheringCreate.
  // calendar -- torn down (its own window-level pointerup/pointercancel
  // listeners removed) before every render() rebuild, the same
  // destroy-before-recreate precedent gathering.js's own former Leaflet/
  // flatpickr handles already established.
  var activeCalendar = null;

  function csrfToken() {
    var field = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return field ? field.value : "";
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
    return fetch(url, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json().then(function (responseBody) {
        return { status: response.status, body: responseBody };
      });
    });
  }

  function pad2(value) {
    return value < 10 ? "0" + value : String(value);
  }

  // adr/0049 decision 3 / adr/0051: "12:00始まり" UI aid -- every
  // calendar-selected day becomes a CandidateDateInput at literal UTC noon
  // (this contract does not fix or require a way to edit each selected
  // day's time-of-day separately from this default). Building this directly
  // from the calendar's own "YYYY-MM-DD" data-date string, never through
  // `new Date(...).toISOString()`, keeps this host-timezone-independent --
  // the same real-measurement finding (2026-09-02, orchestrator合流 run)
  // that motivated the now-retired row-based input's own
  // dateTimeLocalValueToIso applies identically here.
  function calendarDayIsoToStartAtIso(dayIso) {
    return dayIso + "T12:00:00Z";
  }

  // --- holiday-data BEGIN (identical copy in gathering.js; keep both in
  // sync) ---
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
  // Verbatim shape duplicate of gathering.js's own copy -- see this file's
  // module docstring for why no shared module exists, and gathering.js's
  // own copy for the fuller design-rationale comments (kept there once,
  // not repeated twice, to avoid the two copies drifting on prose alone).
  //
  // `options`: { calendarTestId, dayTestId, dayPurpose, monthPrevTestId,
  // monthNextTestId, monthNavPurpose, removeSelectedTestId,
  // removeSelectedPurpose, selectedIsos (mutated in place), onChange
  // (called after any change to selectedIsos) }.
  // Returns { container, destroy }.
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

    // Repaint at most once per animation frame, touching only the cells
    // whose effective state actually changed -- a pointermove can fire many
    // times per frame, and rebuilding the whole grid on each one is what
    // made an earlier hand-built attempt feel like it was catching
    // (scratchpad/cal/script.js's own paintNow() comment, adopted verbatim).
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
            // Not capturable in this environment -- pointermove below still
            // works as long as the pointer stays over the grid itself.
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

      // ADR-0060 decision 5: organizerGatheringCreate's own calendar no
      // longer builds this picked-day sidebar at all -- that list moved
      // entirely into gathering-create-review-dialog, which pages it by
      // month independently of this calendar's own month
      // (options.hidePickedList, set by this screen's own call site only;
      // gathering.js's addCandidateDateForm.calendar is unaffected and
      // still passes no such option).
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

  // browserControlSurface.organizerGatheringCreate.review.open.disabledState
  // (ADR-0060 decision 5, moved 2026-09-16 from the retired single-
  // activation gathering-create-submit): disabled while the name is empty,
  // or fewer than 1 calendar day currently has data-selected="true"
  // (ADR-0035 decision 1's ">=1 candidate date" requirement, mirrored
  // client-side -- the API itself remains the authoritative enforcement).
  function canOpenReview() {
    return Boolean(state.title) && Object.keys(state.selectedIsos).length > 0;
  }

  function totalSelectedCount() {
    return Object.keys(state.selectedIsos).length;
  }

  function monthKeyOfIso(iso) {
    return iso.slice(0, 7); // "YYYY-MM"
  }

  // The distinct months among currently-selected days, ascending -- every
  // month in this list has at least one selected day by construction, which
  // is exactly what review.dialog.monthNavigation.requiredOutcome needs
  // ("a month with no selected day is skipped entirely, never shown").
  function sortedSelectedMonthKeys() {
    var seen = {};
    Object.keys(state.selectedIsos).forEach(function (iso) {
      seen[monthKeyOfIso(iso)] = true;
    });
    return Object.keys(seen).sort();
  }

  function formatMonthKeyLabel(monthKey) {
    var parts = monthKey.split("-");
    return parts[0] + "年 " + Number(parts[1]) + "月";
  }

  function formatSelectedDayLabel(iso) {
    var parts = iso.split("-").map(Number);
    var date = new Date(parts[0], parts[1] - 1, parts[2]);
    var WEEKDAY_LABELS = ["日", "月", "火", "水", "木", "金", "土"];
    return (date.getMonth() + 1) + "/" + date.getDate() + "（" + WEEKDAY_LABELS[date.getDay()] + "）";
  }

  function openReview() {
    if (!canOpenReview()) {
      return;
    }
    state.reviewOpen = true;
    state.duplicateError = false;
    state.notInFutureError = false;
    state.notABusinessDayError = false;
    // review.dialog.description: "Initial position is the earliest month
    // containing a currently-selected day."
    state.reviewViewMonthKey = sortedSelectedMonthKeys()[0] || null;
    state.pendingReviewFocus = "open";
    render();
  }

  function closeReview() {
    // review.dialog.cancel.requiredOutcome: makes the dialog absent, calls
    // no public operation, and changes neither the selected days nor the
    // name input's value.
    state.reviewOpen = false;
    state.pendingReviewFocus = "close";
    render();
  }

  function stepReviewMonth(amount) {
    var keys = sortedSelectedMonthKeys();
    var currentIndex = keys.indexOf(state.reviewViewMonthKey);
    var nextIndex = currentIndex + amount;
    if (nextIndex >= 0 && nextIndex < keys.length) {
      state.reviewViewMonthKey = keys[nextIndex];
      render();
    }
  }

  function removeSelectedInReview(iso) {
    delete state.selectedIsos[iso];
    var keys = sortedSelectedMonthKeys();
    if (keys.indexOf(state.reviewViewMonthKey) === -1) {
      // review.dialog.item.requiredOutcome: this contract does not fix this
      // dialog's behavior when the instance removed was the last one in the
      // currently-displayed month -- falling back to the earliest month
      // that still has a selected day (or `null` once none remain at all,
      // which confirm.disabledState below already gates on) is one
      // reasonable choice among the several the contract leaves open.
      state.reviewViewMonthKey = keys[0] || null;
    }
    render();
  }

  function confirmCreate() {
    if (totalSelectedCount() < 1) {
      return;
    }
    var candidateDates = Object.keys(state.selectedIsos)
      .sort()
      .map(function (iso) {
        return { startAt: calendarDayIsoToStartAtIso(iso) };
      });
    requestJson("POST", "/gatherings", { title: state.title, candidateDates: candidateDates }).then(
      function (result) {
        if (result.status === 201) {
          // review.dialog.confirm.requiredOutcome (ADR-0060 decision 5,
          // carrying forward the fixed 2026-09-12/ADR-0054 decision 2
          // destination): the newly created gathering's own dashboard, so
          // the organizer proceeds directly to issuing participant links.
          window.location.href = "/gatherings/" + result.body.id + "/";
        } else if (
          result.status === 409 &&
          result.body &&
          result.body.code === "DUPLICATE_CANDIDATE_DATE"
        ) {
          // review.dialog.confirm.requiredOutcome: the dialog remains
          // present, every selected day/removeSelected instance unchanged,
          // the name input's value intact -- state.title/state.selectedIsos
          // are untouched, so the re-render below reproduces every value
          // exactly.
          state.duplicateError = true;
          state.notInFutureError = false;
          state.notABusinessDayError = false;
          render();
        } else if (
          result.status === 400 &&
          result.body &&
          result.body.code === "CANDIDATE_DATE_NOT_IN_FUTURE"
        ) {
          state.notInFutureError = true;
          state.duplicateError = false;
          state.notABusinessDayError = false;
          render();
        } else if (
          // ADR-0060 decision 4 (2026-09-16): CANDIDATE_DATE_NOT_A_BUSINESS_DAY,
          // same 400 status as CANDIDATE_DATE_NOT_IN_FUTURE above.
          result.status === 400 &&
          result.body &&
          result.body.code === "CANDIDATE_DATE_NOT_A_BUSINESS_DAY"
        ) {
          state.notABusinessDayError = true;
          state.duplicateError = false;
          state.notInFutureError = false;
          render();
        }
      }
    );
  }

  // Minimal Tab-cycling focus trap while gathering-create-review-dialog is
  // present -- keeps keyboard focus from silently leaving the dialog onto
  // background controls (the outer calendar, the screen-level cancel
  // button) while it is open.
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

  function cancel() {
    // organizerGatheringCreate has exactly one parent, this screen's own
    // gathering list (ADR-0054 decision 7) -- "戻る" always goes there,
    // regardless of how this screen was reached.
    window.location.href = "/gatherings/";
  }

  // --- focus-restore-across-rerender BEGIN (identical copy in
  // gathering.js/participant.js; keep all three in sync) ---
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

  function refreshReviewOpenAndSummary() {
    var openButton = root.querySelector('[data-testid="gathering-create-review-open"]');
    if (openButton) {
      openButton.disabled = !canOpenReview();
    }
    var summaryCountNode = root.querySelector(".gathering-create-summary-count");
    if (summaryCountNode) {
      summaryCountNode.textContent = String(totalSelectedCount());
    }
  }

  // ADR-0060 decision 5: the review dialog. `null` while
  // state.reviewOpen is false (review.dialog.presenceRule).
  function renderReviewDialog() {
    if (!state.reviewOpen) {
      return null;
    }
    var monthKeys = sortedSelectedMonthKeys();
    var currentKey = state.reviewViewMonthKey;
    var currentIndex = monthKeys.indexOf(currentKey);
    var itemIsos = Object.keys(state.selectedIsos)
      .filter(function (iso) {
        return monthKeyOfIso(iso) === currentKey;
      })
      .sort();

    var items = itemIsos.map(function (iso) {
      var removeButton = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-create-candidate-date-remove-selected",
          "data-gathering-control-purpose": "gathering-create-candidate-date-remove-selected",
          "data-date": iso,
          "aria-label": formatSelectedDayLabel(iso) + " を外す",
          class: "gth-cal-picked-remove",
        },
        ["×"]
      );
      removeButton.addEventListener("click", function () {
        removeSelectedInReview(iso);
      });
      return el("div", { class: "gathering-review-item" }, [
        el("span", { class: "gathering-review-item-date" }, [formatSelectedDayLabel(iso)]),
        removeButton,
      ]);
    });

    var prevButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-review-month-previous",
        "data-gathering-control-purpose": "gathering-create-review-month-navigate",
        "aria-label": "前の月",
        disabled: currentIndex <= 0,
        class: "gth-cal-nav gth-cal-nav--prev",
      },
      ["‹"]
    );
    prevButton.addEventListener("click", function () {
      stepReviewMonth(-1);
    });
    var nextButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-review-month-next",
        "data-gathering-control-purpose": "gathering-create-review-month-navigate",
        "aria-label": "次の月",
        disabled: currentIndex === -1 || currentIndex >= monthKeys.length - 1,
        class: "gth-cal-nav gth-cal-nav--next",
      },
      ["›"]
    );
    nextButton.addEventListener("click", function () {
      stepReviewMonth(1);
    });
    // review.dialog.monthNavigation.requiredOutcome: "this contract does not
    // fix how this dialog indicates the current position among the months
    // with selected days (e.g. dots)" -- a rendering detail, not a Must.
    var dots = monthKeys.map(function (key, index) {
      return el(
        "span",
        {
          class: "gathering-review-dot" + (index === currentIndex ? " gathering-review-dot--current" : ""),
          "aria-hidden": "true",
        },
        []
      );
    });

    var totalCount = totalSelectedCount();
    var confirmButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-submit",
        "data-gathering-control-purpose": "gathering-create-submit",
        disabled: totalCount < 1,
        class: "gathering-btn gathering-btn-primary",
      },
      ["この" + totalCount + "件でつくる"]
    );
    confirmButton.addEventListener("click", confirmCreate);

    var cancelReviewButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-review-cancel",
        "data-gathering-control-purpose": "gathering-create-review-cancel",
        class: "gathering-btn",
      },
      ["やめる"]
    );
    cancelReviewButton.addEventListener("click", closeReview);

    var errorNodes = [];
    if (state.duplicateError) {
      errorNodes.push(
        el("p", { class: "gathering-create-error" }, ["同じ日時の候補日は既に追加されています。"])
      );
    }
    if (state.notInFutureError) {
      errorNodes.push(el("p", { class: "gathering-create-error" }, ["明日以降の日付を選んでください。"]));
    }
    if (state.notABusinessDayError) {
      errorNodes.push(
        el("p", { class: "gathering-create-error" }, ["土日・祝日は候補日として登録できません。"])
      );
    }

    var dialog = el(
      "div",
      {
        "data-testid": "gathering-create-review-dialog",
        role: "dialog",
        "aria-modal": "true",
        "aria-label": "候補日の確認",
        tabindex: "-1",
        class: "gathering-review-dialog",
      },
      [
        el("div", { class: "gathering-review-head" }, [
          prevButton,
          el("div", { class: "gathering-review-month" }, [currentKey ? formatMonthKeyLabel(currentKey) : ""]),
          nextButton,
        ]),
        el("div", { class: "gathering-review-dots" }, dots),
        el(
          "div",
          { class: "gathering-review-list" },
          items.length > 0 ? items : [el("p", { class: "gathering-review-empty" }, ["候補日 0件"])]
        ),
      ]
        .concat(errorNodes)
        .concat([el("div", { class: "gathering-review-footer" }, [confirmButton, cancelReviewButton])])
    );

    // モーダルは開いたらフォーカスを中へ、Esc で閉じる、閉じたら開いたボタン
    // へ戻す (keyboard operability): Esc closes without affecting selections;
    // Tab/Shift+Tab cycle within the dialog only while it is present.
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "Escape" || event.key === "Esc") {
        event.preventDefault();
        closeReview();
        return;
      }
      if (event.key === "Tab") {
        trapTabWithinDialog(event, dialog);
      }
    });

    return dialog;
  }

  function render() {
    var focusDescriptor = captureFocusDescriptor(root, document.activeElement);
    // destroy-before-recreate: this calendar's own window-level
    // pointerup/pointercancel listeners must be removed before the DOM node
    // they close over is discarded, or they leak (and would keep mutating a
    // detached calendar's own now-stale selectedIsos object forever).
    if (activeCalendar) {
      activeCalendar.destroy();
      activeCalendar = null;
    }
    root.innerHTML = "";

    var nameInput = el(
      "input",
      {
        type: "text",
        "data-testid": "gathering-create-name-input",
        placeholder: "例: 第8回 社内ランチ会",
        value: state.title || undefined,
        "class": "gathering-input",
      },
      []
    );
    nameInput.addEventListener("input", function () {
      state.title = nameInput.value;
      refreshReviewOpenAndSummary();
    });

    // ADR-0060 decision 5: this calendar no longer builds its own picked-day
    // sidebar list (hidePickedList) -- that list moved entirely into
    // gathering-create-review-dialog above, with its own month paging
    // independent of this outer calendar's own month.
    var calendar = buildCandidateDateCalendar({
      calendarTestId: "gathering-create-candidate-date-calendar",
      dayTestId: "gathering-create-candidate-date-day",
      dayPurpose: "gathering-create-candidate-date-day-select",
      monthPrevTestId: "gathering-create-candidate-date-month-previous",
      monthNextTestId: "gathering-create-candidate-date-month-next",
      monthNavPurpose: "gathering-create-candidate-date-month-navigate",
      hidePickedList: true,
      selectedIsos: state.selectedIsos,
      onChange: refreshReviewOpenAndSummary,
    });
    activeCalendar = calendar;

    var cancelButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-cancel",
        "data-gathering-control-purpose": "gathering-create-cancel",
        "class": "gathering-btn",
      },
      ["やめる"]
    );
    cancelButton.addEventListener("click", cancel);

    // ADR-0060 decision 9 (non-binding wording example): "候補日 N件" --
    // this contract does not fix this wording, only the underlying
    // selected-day count it is drawn from.
    var summary = el("div", { class: "gathering-create-summary" }, [
      "候補日 ",
      el("b", { class: "gathering-create-summary-count" }, [String(totalSelectedCount())]),
      " 件",
    ]);

    // ADR-0060 decision 5: this control now only opens
    // gathering-create-review-dialog -- createGathering itself is called by
    // that dialog's own confirm (gathering-create-submit, moved inside).
    var reviewOpenButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-review-open",
        "data-gathering-control-purpose": "gathering-create-review-open",
        disabled: !canOpenReview(),
        "class": "gathering-btn gathering-btn-primary gathering-btn-block",
      },
      ["会をつくる"]
    );
    reviewOpenButton.addEventListener("click", openReview);

    var children = [
      el("label", { "class": "gathering-field" }, ["会の名前", nameInput]),
      el("label", { "class": "gathering-field-label" }, ["候補日（複数選択できます）"]),
      calendar.container,
      el("div", { "class": "gathering-create-summary-row" }, [summary, cancelButton]),
      reviewOpenButton,
    ];

    root.appendChild(el("div", { "class": "gathering-create-form" }, children));

    var dialog = renderReviewDialog();
    if (dialog) {
      root.appendChild(dialog);
    }

    restoreFocusFromDescriptor(root, focusDescriptor);

    // Explicit open/close focus management -- distinct from the generic
    // restoreFocusFromDescriptor above, which can only restore focus to an
    // element that still exists after this rebuild (see state.
    // pendingReviewFocus's own comment at its declaration for why).
    if (state.pendingReviewFocus === "open") {
      var dialogNode = root.querySelector('[data-testid="gathering-create-review-dialog"]');
      if (dialogNode) {
        dialogNode.focus({ preventScroll: true });
      }
      state.pendingReviewFocus = null;
    } else if (state.pendingReviewFocus === "close") {
      var openButtonNode = root.querySelector('[data-testid="gathering-create-review-open"]');
      if (openButtonNode) {
        openButtonNode.focus({ preventScroll: true });
      }
      state.pendingReviewFocus = null;
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
  render();
  loadGatheringEntryBadge();
})();
