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

    renderLocal();

    return {
      container: container,
      destroy: function () {
        window.removeEventListener("pointerup", onWindowPointerUp);
        window.removeEventListener("pointercancel", onWindowPointerCancel);
      },
    };
  }

  // browserControlSurface.organizerGatheringCreate.submit.disabledState:
  // disabled while the name is empty, or fewer than 1 calendar day currently
  // has data-selected="true" (ADR-0035 decision 1's ">=1 candidate date"
  // requirement, mirrored client-side -- the API itself remains the
  // authoritative enforcement).
  function canSubmit() {
    return Boolean(state.title) && Object.keys(state.selectedIsos).length > 0;
  }

  function refreshSubmitDisabled() {
    var submitButton = root.querySelector('[data-testid="gathering-create-submit"]');
    if (submitButton) {
      submitButton.disabled = !canSubmit();
    }
  }

  function submit() {
    if (!canSubmit()) {
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
          // organizerGatheringCreate.submit.requiredOutcome (fixed
          // 2026-09-12, ADR-0054 decision 2): the newly created gathering's
          // own dashboard, so the organizer proceeds directly to issuing
          // participant links.
          window.location.href = "/gatherings/" + result.body.id + "/";
        } else if (
          result.status === 409 &&
          result.body &&
          result.body.code === "DUPLICATE_CANDIDATE_DATE"
        ) {
          // adr/0038/adr/0051: the screen remains, the name and every
          // calendar day's data-selected intact -- state.title/
          // state.selectedIsos are untouched, so the re-render below
          // reproduces every value exactly.
          state.duplicateError = true;
          state.notInFutureError = false;
          render();
        } else if (
          result.status === 409 &&
          result.body &&
          result.body.code === "CANDIDATE_DATE_NOT_IN_FUTURE"
        ) {
          state.notInFutureError = true;
          state.duplicateError = false;
          render();
        }
      }
    );
  }

  function cancel() {
    // organizerGatheringCreate has exactly one parent, this screen's own
    // gathering list (ADR-0054 decision 7) -- "戻る" always goes there,
    // regardless of how this screen was reached.
    window.location.href = "/gatherings/";
  }

  function render() {
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
      refreshSubmitDisabled();
    });

    var submitButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-submit",
        "data-gathering-control-purpose": "gathering-create-submit",
        disabled: !canSubmit(),
        "class": "gathering-btn gathering-btn-primary",
      },
      ["会をつくる"]
    );
    submitButton.addEventListener("click", submit);

    var calendar = buildCandidateDateCalendar({
      calendarTestId: "gathering-create-candidate-date-calendar",
      dayTestId: "gathering-create-candidate-date-day",
      dayPurpose: "gathering-create-candidate-date-day-select",
      monthPrevTestId: "gathering-create-candidate-date-month-previous",
      monthNextTestId: "gathering-create-candidate-date-month-next",
      monthNavPurpose: "gathering-create-candidate-date-month-navigate",
      removeSelectedTestId: "gathering-create-candidate-date-remove-selected",
      removeSelectedPurpose: "gathering-create-candidate-date-remove-selected",
      selectedIsos: state.selectedIsos,
      onChange: refreshSubmitDisabled,
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

    var children = [
      el("label", { "class": "gathering-field" }, ["会の名前", nameInput]),
      el("label", { "class": "gathering-field-label" }, ["候補日（複数選択できます）"]),
      calendar.container,
    ];
    if (state.duplicateError) {
      children.push(el("p", { "class": "gathering-create-error" }, ["同じ日時の候補日は既に追加されています。"]));
    }
    if (state.notInFutureError) {
      children.push(el("p", { "class": "gathering-create-error" }, ["明日以降の日付を選んでください。"]));
    }
    children.push(el("div", { "class": "gathering-create-actions" }, [submitButton, cancelButton]));

    root.appendChild(el("div", { "class": "gathering-create-form" }, children));
  }

  // contracts/candidate-search-browser-interface.yaml's gatheringEntry
  // section (ADR-0054 decision 1): candidate-gathering-entry itself is
  // plain, server-rendered HTML (organizer_gathering_create.html) and
  // therefore already present before this script runs. Only the badge --
  // which mirrors gathering-scheduling-api.yaml's getInProgressGatheringCount
  // -- is built here, once fetched (duplicated verbatim from
  // web/static/dining_radar/web/candidate.js's own loadGatheringEntryBadge;
  // no shared module system exists in this codebase).
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

  render();
  loadGatheringEntryBadge();
})();
