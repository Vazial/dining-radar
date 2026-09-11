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
 * decision 1). The vendored flatpickr library (MIT license, vendor/
 * flatpickr/, same same-origin-serving convention Leaflet already
 * established, ADR-0010) backs both calendars -- see gathering.js's own
 * buildCandidateDateCalendar for the fuller rationale (duplicated here, not
 * imported: no shared module system exists in this codebase, the same
 * reason el()/csrfToken()/requestJson() are already duplicated across every
 * screen script).
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

  // The vendored flatpickr instance backing organizerGatheringCreate.
  // calendar -- same destroy-before-recreate / must-already-be-attached
  // precedents as gathering.js's own pendingAddCandidateDateCalendar /
  // activeAddCandidateDateCalendar (this file has only one calendar, so a
  // single pair of module-level handles is enough).
  var pendingCalendar = null;
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

  // Same day-cell surface as gathering.js's own buildCandidateDateCalendar
  // (duplicated, not imported -- see this file's module docstring). Only
  // the day/purpose test ids and the onToggle callback differ per call site.
  // The `<input>` flatpickr requires is deliberately never attached to the
  // document at all -- see gathering.js's own buildCandidateDateCalendar
  // for the full real-measurement rationale (duplicated here, not
  // imported). `appendTo: container` makes flatpickr render its calendar
  // markup into `container` without ever inserting this detached input as
  // its sibling.
  function buildCandidateDateCalendar(options) {
    var container = el("div", { "data-testid": options.calendarTestId }, []);
    var anchorInput = document.createElement("input");
    var todayIso = isoDateOf(new Date());
    var instance = null;

    function isoDateOf(date) {
      return date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate());
    }

    function onDayCreate(_selectedDates, _dateStr, _fpInstance, dayElem) {
      // Skip showMonths > 1's own cross-month filler cells -- see
      // gathering.js's own buildCandidateDateCalendar for the full
      // real-measurement rationale (duplicated here, not imported).
      if (dayElem.classList.contains("prevMonthDay") || dayElem.classList.contains("nextMonthDay")) {
        return;
      }
      var iso = isoDateOf(dayElem.dateObj);
      dayElem.setAttribute("data-testid", options.dayTestId);
      dayElem.setAttribute("data-date", iso);
      dayElem.setAttribute("data-selected", options.selectedIsos[iso] ? "true" : "false");
      if (iso <= todayIso) {
        return;
      }
      dayElem.setAttribute("data-gathering-control-purpose", options.purposeName);
      dayElem.setAttribute("role", "button");
      dayElem.setAttribute("tabindex", "0");
      var activate = function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (options.selectedIsos[iso]) {
          delete options.selectedIsos[iso];
        } else {
          options.selectedIsos[iso] = true;
        }
        dayElem.setAttribute("data-selected", options.selectedIsos[iso] ? "true" : "false");
        options.onToggle();
      };
      dayElem.addEventListener("click", activate);
      dayElem.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          activate(event);
        }
      });
    }

    return {
      container: container,
      initialize: function () {
        var tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        instance = window.flatpickr(anchorInput, {
          inline: true,
          appendTo: container,
          disableMobile: true,
          minDate: tomorrow,
          // 3 consecutive months, all simultaneously in the DOM -- see
          // gathering.js's own buildCandidateDateCalendar for the full
          // rationale (duplicated here, not imported).
          showMonths: 3,
          onDayCreate: onDayCreate,
        });
        // flatpickr's own month header always builds a genuine
        // `<input class="cur-year">` with no declared purpose -- removed
        // the same way gathering.js's own buildCandidateDateCalendar does
        // (see its own real-measurement comment for the full rationale).
        container.querySelectorAll(".numInputWrapper").forEach(function (wrapper) {
          var yearInput = wrapper.querySelector("input.cur-year");
          if (!yearInput) {
            return;
          }
          var replacement = document.createElement("span");
          replacement.className = "gathering-calendar-year";
          replacement.textContent = yearInput.value;
          wrapper.replaceWith(replacement);
        });
      },
      destroy: function () {
        if (instance) {
          instance.destroy();
          instance = null;
        }
      },
    };
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
          // This contract does not fix the immediate post-submit
          // destination screen; the new gathering's own dashboard is the
          // most useful next stop (it is where a link is first issued).
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
    window.location.href = "/gatherings/";
  }

  function render() {
    if (activeCalendar) {
      activeCalendar.destroy();
      activeCalendar = null;
    }
    pendingCalendar = null;
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
      purposeName: "gathering-create-candidate-date-day-select",
      selectedIsos: state.selectedIsos,
      onToggle: refreshSubmitDisabled,
    });
    calendar.container.className = "gathering-calendar";
    pendingCalendar = calendar;

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

    // The calendar's anchor input above must already be attached to the
    // live DOM before flatpickr initializes it (gathering.js's own
    // buildCandidateDateCalendar module docstring explains the full
    // Leaflet-precedent reasoning).
    if (pendingCalendar) {
      pendingCalendar.initialize();
      activeCalendar = pendingCalendar;
    }
  }

  render();
})();
