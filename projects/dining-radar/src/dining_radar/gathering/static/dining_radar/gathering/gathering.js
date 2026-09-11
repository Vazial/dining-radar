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
 *     submit is activated.
 * **2026-09-09 (adr/0049 decision 1), removed 2026-09-11**: this section
 * used to also describe shortlistPending (the retired inline shortlist-
 * picker's own pending checkbox state) -- shop selection itself now happens
 * entirely on candidate-search-browser-interface.yaml's gatheringMode
 * screen, reached via shopSelectionEntry.open/navigateToShopSelectionEntry
 * below; this dashboard keeps no client-side pending state for it at all.
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
 *
 * 2026-09-04 addition (human decision, same day as the adr/0042 slice --
 * "作りかけに見える。見て判断できるところまで作りこんでほしい"): visual
 * language pass. Every `el()` call below may now also carry a `class`
 * attribute -- purely presentational, built from the same designer tokens
 * `contracts/gathering-scheduling-browser-interface.yaml`'s referenced
 * canvases use (`E:\AWS\dsg-out\party\*.dc.html`) and already partially
 * adopted by web/static/dining_radar/web/candidate.js
 * (candidate-gathering-entry's #14614a/#c6cfc6/#17201b). **No test id, no
 * data-* attribute, and no data-gathering-control-purpose value changed or
 * was added/removed by this pass** -- every attribute a contract or test
 * observes is byte-for-byte the same as before. A handful of purely
 * decorative wrapper/heading elements (no test id, `gathering.css`'s
 * `.gth-pane`/`.gth-pane-head` etc.) were added around already-existing
 * controls to group them into panels the way the approved canvases draw
 * them; this changes *parent* nodes only, never the relative DOM order of
 * two elements that share a test id (orderingInvariant is unaffected) and
 * never how any element is located (tests locate by test id, not by exact
 * tree depth).
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
  // (no shared module system exists in this codebase; every other small
  // utility is already duplicated the same way, see this file's own
  // date-formatting block below). The sibling capacity/non-smoking/budget
  // tier label maps that used to live beside this one were removed
  // 2026-09-11 along with renderOpenShopDetailFields/shortlistSelection
  // (adr/0049 decision 1 -- see this file's shopSelectionEntry section).
  var VOTE_LABELS = { WANT_TO_GO: "行きたい", OK_TO_GO: "行ってもいい", NOT_GOING: "むり" };

  var state = {
    gathering: null,
    participantLinks: [],
    tentativeSelectedId: null,
    openShopPreview: null,
    addCandidateDateOpen: false,
    // **Replaced 2026-09-11 (adr/0049 decision 3): a single addCandidateDateValue
    // string became a multi-select calendar's own pending selection set.**
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
    // gathering-finalize-submit is activated.
    finalizeSelectedShopId: null,
    // adr/0050 decision 4, deleteGathering: whether gathering-delete-
    // confirm-dialog is currently revealed (client-side only -- opening it
    // calls no public operation).
    deleteConfirmOpen: false,
  };

  // adr/0049 decision 3: the vendored flatpickr instance backing
  // addCandidateDateForm.calendar (buildCandidateDateCalendar below). Built
  // during render()'s DOM-construction pass (pendingAddCandidateDateCalendar
  // holds the not-yet-initialized handle), then flatpickr() is called only
  // after root.appendChild() below -- the same "must already be attached to
  // the live DOM before initializing" precedent this file's own (now-retired)
  // initializeOpenShopMap established for Leaflet. activeAddCandidateDate
  // Calendar tracks the currently-live instance so the next render() (which
  // rebuilds the whole DOM via root.innerHTML = "") can destroy() it first,
  // the same destroy-before-recreate precedent that Leaflet map also used.
  var pendingAddCandidateDateCalendar = null;
  var activeAddCandidateDateCalendar = null;

  function csrfToken() {
    var field = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return field ? field.value : "";
  }

  // **Retired 2026-09-11 (adr/0049 decision 3)**: this function used to
  // convert a raw <input type="datetime-local"> value ("YYYY-MM-DDTHH:mm",
  // no timezone) into a fixed-UTC CandidateDateInput.startAt
  // (`value + ":00Z"`), deliberately never through
  // `new Date(value).toISOString()` -- a real host-timezone-dependent bug an
  // acceptance 合流 run surfaced (TDR-GTH-24, 2026-09-02): on a JST host,
  // that conversion silently shifted a submitted instant by 9 hours (a
  // timezone-less date-time literal is parsed as "the host system's own
  // local time zone", per the JS spec's Date Time String Format). The
  // datetime-local input itself is gone now (replaced by the multi-select
  // calendar's own day cells, buildCandidateDateCalendar/
  // calendarDayIsoToStartAtIso below), but that conversion's own lesson
  // carries forward unchanged: calendarDayIsoToStartAtIso builds its ISO
  // string directly from the calendar's own "YYYY-MM-DD" data-date digits
  // the identical way, so it inherits the same host-timezone independence
  // without reintroducing the retired bug.
  //
  // **Recorded trade-off, still unresolved (developer discretion -- FR-028,
  // carried over unchanged from this function's own retired version)**: the
  // calendar's "12:00始まり" default is tagged as literal UTC noon, not
  // Asia/Tokyo noon (this project's real user base is JST-only,
  // product-brief.md) -- an organizer's intended JST noon would need this
  // tag corrected by an architect/human decision no contract has made yet.

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

  // adr/0049 decision 3 (2026-09-09, 2026-09-08 human decision: 候補日は
  // カレンダーで複数選択する): the vendored flatpickr library (MIT license,
  // vendor/flatpickr/, same same-origin-serving convention Leaflet already
  // established, ADR-0010) backs addCandidateDateForm.calendar /
  // organizerGatheringCreate.calendar. This contract does not fix the
  // calendar's rendered month range, week-start convention, markup, or
  // specific library -- it fixes only the day-cell surface
  // (data-testid/data-date/data-selected/purpose) and the disabled-day rule
  // ("明日以降のみ"), both applied here directly to flatpickr's own day
  // <span> elements via its onDayCreate hook rather than replacing them.
  // flatpickr's own click delegation (bound once on its days container) is
  // deliberately never allowed to see these clicks (stopPropagation in
  // `activate` below) -- this developer's own click/keydown handlers are the
  // only thing that ever mutates data-selected or `selectedIsos`, keeping
  // flatpickr itself a pure calendar-grid/month-navigation renderer with no
  // opinion of its own about which days are selected (mode/onChange are
  // deliberately not used).
  //
  // `options`: { calendarTestId, dayTestId, purposeName, selectedIsos (a
  // plain object this function mutates in place, iso date string -> true),
  // onToggle (called after every toggle, with no arguments, so the caller
  // can refresh its own submit-button disabled state) }. Returns
  // { container, initialize, destroy } -- `container` (carrying
  // calendarTestId) must be attached to the live DOM (inside the tree
  // render() passes to root.appendChild) before `initialize()` runs.
  //
  // **The `<input>` flatpickr requires is deliberately never attached to
  // the document at all** (real-measurement finding, 2026-09-11: running
  // this suite's own cross-cutting `allGatheringScreenFormControlsMustDeclarePurpose`
  // scan -- which matches any live `input:not([type='hidden'])`, and
  // flatpickr's own `setupInputs()` unconditionally forces its managed
  // input's `type` to `"text"` even if constructed with `type="hidden"`,
  // so that attribute cannot be used to opt out -- found this anchor input
  // itself failing the scan, since it carries no
  // data-gathering-control-purpose and this contract's own closed
  // allowedPurposes list has no entry for "a vendored library's internal
  // bookkeeping input" and developer cannot extend tests/acceptance/**
  // to add one). Passing `inline: true` with `appendTo: container` (below)
  // makes flatpickr append its own rendered `.flatpickr-calendar` markup
  // into `container` directly, without ever inserting the input itself as
  // that container's sibling (its own source: "if (self.config.inline) {
  // if (!customAppend && self.element.parentNode) {...} else if
  // (self.config.appendTo !== undefined) { self.config.appendTo.
  // appendChild(self.calendarContainer); } }" -- customAppend is true
  // whenever appendTo is set). The detached input keeps working perfectly
  // well for flatpickr's own internal bookkeeping (day-grid construction,
  // month navigation, `.value`/`.classList`/`.setAttribute` all work
  // identically on a detached node) since this file's own click handlers
  // below never rely on flatpickr's own selection state or the input's
  // value in the first place (mode/onChange are deliberately not used) --
  // it is simply never queryable by Playwright, which only sees the live,
  // attached document tree.
  function buildCandidateDateCalendar(options) {
    var container = el("div", { "data-testid": options.calendarTestId }, []);
    var anchorInput = document.createElement("input");
    var todayIso = isoDateOf(new Date());
    var instance = null;

    function isoDateOf(date) {
      return date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate());
    }

    function onDayCreate(_selectedDates, _dateStr, _fpInstance, dayElem) {
      // With showMonths > 1, flatpickr pads each month's own grid with
      // "prevMonthDay"/"nextMonthDay" filler cells (visually hidden via its
      // own "hidden" class) so adjacent months' weekday columns line up --
      // every one of those filler cells represents the exact same calendar
      // date as a real, fully-interactive cell inside its own neighboring
      // month's grid. Tagging both would attach two elements to the same
      // data-date value (a real, measured strict-mode Playwright locator
      // violation, 2026-09-11) -- only the day's own home-month cell gets
      // this contract's attributes; the filler duplicate is left as
      // flatpickr's own plain, untagged placeholder.
      if (dayElem.classList.contains("prevMonthDay") || dayElem.classList.contains("nextMonthDay")) {
        return;
      }
      var iso = isoDateOf(dayElem.dateObj);
      dayElem.setAttribute("data-testid", options.dayTestId);
      dayElem.setAttribute("data-date", iso);
      dayElem.setAttribute("data-selected", options.selectedIsos[iso] ? "true" : "false");
      // dayCell.disabledState: "today or earlier by the server's clock" --
      // approximated client-side with the visiting browser's own clock (a UX
      // affordance only; CANDIDATE_DATE_NOT_IN_FUTURE remains the
      // authoritative server-side enforcement, unaffected by this).
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
          // 3 consecutive months, all their day cells simultaneously
          // present in the DOM (flatpickr's own showMonths option) --
          // dayCell has no contract-fixed cap on how many days ahead may be
          // selected (adr/0049 decision 3), and this contract's own DSL
          // locates a day cell purely by its data-date attribute with no
          // month-navigation step of its own, so every selectable day this
          // suite (or a real organizer) might pick across a single
          // multi-select session must already be rendered, not merely
          // reachable by clicking a next-month arrow first. 3 months
          // comfortably covers this suite's own widest spread (a same-batch
          // pairing of +3 and +20 days from today, TDR-GTH-46) with a full
          // month of margin.
          showMonths: 3,
          onDayCreate: onDayCreate,
        });
        // Real-measurement finding, 2026-09-11: flatpickr's own month
        // header unconditionally builds a genuine `<input class="cur-year">`
        // (createNumberInput, editable year-jump field) per visible month,
        // regardless of any config option -- unlike the month name itself
        // (a plain, non-interactive <span> once showMonths > 1, flatpickr's
        // own built-in behavior this file already relies on). This input
        // carries no data-gathering-control-purpose and this contract's own
        // closed allowedPurposes list has no entry for it (same reasoning
        // as the detached main anchor input above), so
        // allGatheringScreenFormControlsMustDeclarePurpose fails as soon as
        // this calendar renders unless it is removed. Replaced with a
        // plain, static text span showing the same year -- this developer
        // does not need year-jump input since every practically reachable
        // date already falls within the 3 simultaneously-rendered months
        // above; the one accepted trade-off is that this static span does
        // not itself update if the organizer clicks the prev/next-month
        // arrows past this initial 3-month window (those arrows and the
        // day grid they rebuild are otherwise fully unaffected -- only this
        // cosmetic year label goes stale in that one edge case).
        container.querySelectorAll(".numInputWrapper").forEach(function (wrapper) {
          var yearInput = wrapper.querySelector("input.cur-year");
          if (!yearInput) {
            return;
          }
          var replacement = document.createElement("span");
          replacement.className = "gth-calendar-year";
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

  // adr/0049 decision 1 (2026-09-09): shop selection is no longer a picker
  // rendered inline on this dashboard (the retired shortlistSelection/
  // PickFive.dc.html apparatus -- shortlistSelectionVisible/
  // fetchOpenShopListForShortlist/renderShortlistSelection/
  // renderOpenShopListItem/toggleShortlistPending/submitShortlist/
  // openShortlistReplace all lived here and were removed 2026-09-11). The
  // organizer now reaches shop selection exclusively through
  // shopSelectionEntry.open (renderShopSelectionEntry below), which
  // navigates to candidate-search-browser-interface.yaml's own gatheringMode
  // screen -- see this file's module docstring and the contract's own
  // 2026-09-09 追補8 for the removal rationale.

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
        return loadParticipantLinksOnly()
          .then(fetchOpenShopListForShortlist)
          .then(render);
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
    // had even reached the server -- the attribute already held the
    // *previous* activation's non-empty URL, and the acceptance DSL's
    // wildcard match (any non-empty value) cannot tell "still the old
    // value" apart from "the new value arrived". Clearing the tracked value
    // synchronously here, before the async request even starts, makes every
    // activation transition through an observable
    // absent-or-empty -> non-empty edge, not just the first ever
    // activation for this gathering.
    state.headerIssuedLinkUrl = null;
    render();
    requestJson("POST", gatheringUrl() + "/participant-links", { count: 1 }).then(function (result) {
      if (result.status !== 201) {
        return;
      }
      var issued = result.body.issuedLinks[0];
      // Tracked in state (see the module docstring) so the attribute
      // survives the render() rebuild loadParticipantLinksOnly() below
      // triggers, instead of being set on a DOM node that rebuild replaces.
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
    // Same before/after clear-then-set pattern as copyParticipantLink above,
    // and for the same real-measured reason: a second recopy of the same
    // link must not let the first recopy's leftover non-empty value satisfy
    // the acceptance check before this activation's own request completes.
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

  // adr/0049 decision 3: "12:00始まり" UI aid -- every calendar-selected day
  // becomes a CandidateDateInput at literal UTC noon (this contract does not
  // fix or require a way to edit each selected day's time-of-day separately
  // from this default).
  function calendarDayIsoToStartAtIso(dayIso) {
    return dayIso + "T12:00:00Z";
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
        // adr/0049 decision 3: whole-batch rejection -- the form remains
        // present with every day cell's data-selected unchanged, and no new
        // gathering-candidate-date appears.
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
  // yaml's gatheringMode, adr/0049 decision 1 -- navigateToShopSelectionEntry/
  // renderShopSelectionEntry below are this dashboard's only remaining
  // involvement in shop selection.)

  function navigateToShopSelectionEntry() {
    // shopSelectionEntry.open.requiredOutcome (adr/0049 decision 1): this
    // contract does not fix the exact navigation mechanism -- a URL query
    // parameter matching web/static/dining_radar/web/candidate.js's own
    // readGatheringIdFromUrl() is this implementation's choice (that file's
    // own module docstring makes the same choice from the other direction).
    window.location.href = "/?gatheringId=" + encodeURIComponent(gatheringId);
  }

  // shopSelectionEntry.open (adr/0049 decision 1): reused for both the
  // first-ever selection (votingStartedAt still null) and every later D7
  // replace (votingStartedAt non-null) -- the contract's own cardinality
  // note treats every instance sharing this test id as the same purpose
  // regardless of label, and this dashboard only ever renders one of the
  // two at a time (render()'s own phase/votingStartedAt branches below).
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
    // Client-side pending selection only (shortlistedShopVotes.list.item.
    // finalizeSelect.requiredOutcome) -- calls no public operation.
    state.finalizeSelectedShopId = shopId;
    render();
  }

  function finalizeGathering() {
    if (!state.finalizeSelectedShopId) {
      return;
    }
    requestJson("POST", gatheringUrl() + "/finalize", {
      shopId: state.finalizeSelectedShopId,
    }).then(function (result) {
      if (result.status === 200) {
        state.gathering = result.body;
        state.finalizeSelectedShopId = null;
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
    // deleteGathering.cancel.requiredOutcome: makes gathering-delete-
    // confirm-dialog absent without calling deleteGathering. The gathering
    // itself is unaffected.
    state.deleteConfirmOpen = false;
    render();
  }

  function confirmDeleteGathering() {
    requestJson("DELETE", gatheringUrl()).then(function (result) {
      if (result.status === 204) {
        // deleteGathering.confirm.requiredOutcome: this contract does not
        // fix the immediate post-delete destination screen -- the
        // organizer's own gathering list is the most useful next stop (the
        // same "no longer appears in organizerGatheringList.list" outcome
        // TDR-GTH-48 itself checks).
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
          { "data-testid": "gathering-delete-confirm-dialog", class: "gth-delete-dialog" },
          [
            el("p", { class: "gth-delete-dialog-text" }, [
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
    // tentativeSelectionAndPreview.trigger.presenceRuleForPurpose (adr/0042):
    // once phase is SELECTING_SHOP or FINALIZED, this element remains
    // present as a record but no longer accepts the tentative-select
    // activation -- represented here by dropping the purpose/role/tabindex
    // and the event listeners entirely, rather than leaving an inert
    // role="button" with no declared purpose (which would fail
    // unavailableControls.allGatheringScreenFormControlsMustDeclarePurpose).
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
    var node = el("div", attrs, [
      el("div", { class: "gth-date-top" }, [
        el("span", { class: "gth-date-value" }, [formatGatheringDateTime(candidateDate.startAt)]),
        candidateDate.isConfirmed ? el("span", { class: "gth-date-badge" }, ["決定"]) : null,
      ]),
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
    // **Replaced 2026-09-11 (adr/0049 decision 3, 2026-09-08 human decision:
    // 候補日はカレンダーで複数選択する)**: the single datetime-local input
    // this form used to expose is gone -- see buildCandidateDateCalendar
    // below and this file's module docstring history. The form still opens
    // inline within gathering-candidate-date-list and stays open across a
    // successful submit; only cancel makes it absent again (AddDate.dc.html
    // 案A, human decision 2026-09-01, unchanged by this round).
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
      purposeName: "gathering-add-candidate-date-day-select",
      selectedIsos: state.addCandidateDateSelectedIsos,
      onToggle: function () {
        submit.disabled = Object.keys(state.addCandidateDateSelectedIsos).length < 1;
      },
    });
    calendar.container.className = "gth-calendar";
    pendingAddCandidateDateCalendar = calendar;

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

  // **Narrowed 2026-09-09 (adr/0049 decision 2, 2026-09-08 human decision:
  // 日程を聞いている段階の店は件数だけ)**: this preview no longer carries
  // any item/list sub-structure -- gathering-open-shop-preview-item and the
  // OpenShopPreviewItem schema it projected were both retired the same day
  // (gathering-scheduling-api.yaml). data-open-shop-count is the only
  // observable value; no shop name or other shop attribute may appear
  // anywhere inside gathering-open-shop-preview (TDR-GTH-08: "店名やその他
  // の店舗情報は示されない").
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

  // --- adr/0049 decision 1: shortlistSelection (PickFive.dc.html 案A) was
  // retired 2026-09-09 and removed from this file 2026-09-11 -- see
  // renderShopSelectionEntry above and render()'s own SELECTING_SHOP branch
  // below for its replacement.

  // --- adr/0042: shortlistedShopVotes (Organizer.dc.html 状態②) ------------

  function renderShortlistedShopItem(shop, index) {
    var attrs = {
      "data-testid": "gathering-shortlisted-shop-item",
      "data-shop-id": shop.shopId,
      "data-want-to-go-count": shop.wantToGoCount,
      "data-ok-to-go-count": shop.okToGoCount,
      "data-not-going-count": shop.notGoingCount,
      "data-responded-count": shop.respondedParticipantCount,
      // adr/0050 decision 5 (architect technical judgment): "true" for
      // exactly the first item in this list's own orderingInvariant order
      // (wantToGoCount + okToGoCount descending, ties broken by distance
      // ascending then shopId ascending -- already the exact order
      // state.gathering.shortlistedShops arrives in, so index 0 is always
      // the leader). Independent of gathering-finalize-shop-select below.
      "data-current-leader": index === 0 ? "true" : "false",
      class: "gth-shop-row gth-shop-row--vote",
    };
    // TDR-GTH-40: the three-tier breakdown, denominator = respondedParticipantCount
    // (adr/0044 -- this section deliberately carries no map/detail fields,
    // see this file's own module docstring history and adr/0046 decision 2).
    var tallyRow = el("div", { class: "gth-shop-tally-row" }, [
      el("span", {}, [VOTE_LABELS.WANT_TO_GO + " ", el("b", {}, [String(shop.wantToGoCount)])]),
      el("span", {}, [VOTE_LABELS.OK_TO_GO + " ", el("b", {}, [String(shop.okToGoCount)])]),
      el("span", {}, [VOTE_LABELS.NOT_GOING + " ", el("b", {}, [String(shop.notGoingCount)])]),
      el("span", {}, [String(shop.respondedParticipantCount) + "人中"]),
    ]);
    var children = [
      el("span", { class: "gth-shop-rank" }, [String(index + 1)]),
      el("div", { class: "gth-shop-body" }, [
        el("span", { class: "gth-shop-name" }, [shop.name]),
        tallyRow,
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

  function renderShortlistedShopVotes() {
    var phase = state.gathering.phase;
    var list = el(
      "div",
      { "data-testid": "gathering-shortlisted-shop-list", class: "gth-shop-list" },
      state.gathering.shortlistedShops.map(function (shop, index) {
        return renderShortlistedShopItem(shop, index);
      })
    );
    var paneChildren = [
      el("div", { class: "gth-pane-head" }, [
        "お店の候補",
        el("span", { class: "gth-pane-sub" }, [
          "並び: 「行きたい」＋「行ってもいい」の合計が多い順",
        ]),
      ]),
      list,
    ];

    // replaceOpen/finalizeSubmit: both present only while SELECTING_SHOP
    // (absent once FINALIZED, shortlistedShopVotes.replaceOpen.presenceRule /
    // finalizeSubmit.presenceRule).
    if (phase === "SELECTING_SHOP") {
      var actions = [renderShopSelectionEntry("店を絞りなおす", "gth-btn")];
      if (state.gathering.shortlistedShops.length > 0) {
        var finalizeSubmit = el(
          "button",
          {
            type: "button",
            "data-testid": "gathering-finalize-submit",
            "data-gathering-control-purpose": "gathering-finalize-submit",
            disabled: !state.finalizeSelectedShopId,
            class: "gth-btn gth-btn-primary",
          },
          ["日と店を確定する"]
        );
        finalizeSubmit.addEventListener("click", finalizeGathering);
        actions.push(finalizeSubmit);
      }
      paneChildren.push(el("div", { class: "gth-pane-actions" }, actions));
    }

    return el("div", { class: "gth-pane" }, paneChildren);
  }

  // --- adr/0042: finalizedSummary (Final.dc.html A③) -----------------------

  function renderFinalizedSummary() {
    var confirmed = state.gathering.candidateDates.filter(function (candidateDate) {
      return candidateDate.isConfirmed;
    })[0];
    // Display only: prefer the shortlisted shop's own live-projected name
    // over the raw opaque shopId, if it is still resolvable (shortlistedShops
    // remains present, unchanged, once FINALIZED -- shortlistedShopVotes.
    // presenceRule above). data-finalized-shop-id itself always carries the
    // raw Gathering.finalizedShopId value unchanged, regardless of this.
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

    // participantLinkList.item.revoke.presenceRule (adr/0042): absent once
    // phase is FINALIZED (P4) -- present (with its own pre-existing
    // disabledState) while SCHEDULING or SELECTING_SHOP.
    if (state.gathering.phase !== "FINALIZED") {
      var revokeButton = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-participant-link-revoke",
          "data-gathering-control-purpose": "gathering-participant-link-revoke",
          disabled: link.hasResponded || link.revoked,
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

  function render() {
    // destroy-before-recreate (this file's own former initializeOpenShopMap
    // precedent): root.innerHTML below discards the DOM node any live
    // flatpickr instance is attached to, so the instance itself must be torn
    // down first or it leaks (flatpickr keeps document-level listeners
    // alive otherwise).
    if (activeAddCandidateDateCalendar) {
      activeAddCandidateDateCalendar.destroy();
      activeAddCandidateDateCalendar = null;
    }
    pendingAddCandidateDateCalendar = null;
    root.innerHTML = "";
    if (!state.gathering) {
      return;
    }
    var phase = state.gathering.phase;

    // Human decision 2026-09-04 (real-measurement finding: the heading was
    // the generic "会の日程調整" title only, with no way to tell which
    // gathering is open from the screen itself -- Organizer.dc.html's own
    // header always shows the gathering's own name). This contract's
    // organizerDashboard section defines no test id for the gathering's
    // own name (unlike organizerGatheringList's data-gathering-title) --
    // rendered as a plain, purposeless <div> (no data-testid, no
    // data-gathering-control-purpose; `allowedPurposes` is a closed list
    // this developer cannot extend), the same style already established
    // for candidate-gathering-entry/candidate-map-open.
    // deleteGathering.open.presenceRule: "Present unconditionally, across
    // all three phases" -- rendered in the header row so it is reachable
    // from every phase without competing for space inside any one pane.
    var header = el("div", { class: "gth-header" }, [
      el("div", { class: "gth-header-row" }, [
        el("div", { class: "gth-title" }, [state.gathering.title]),
        renderDeleteGathering(),
      ]),
      renderPhaseIndicator(),
      el("div", { class: "gth-stats-row" }, [renderResponseSummary(), renderUnansweredSummary()]),
    ]);

    // adr/0038, addCandidateDateOpen.requiredOutcome: the revealed form
    // must sit inline *within* gathering-candidate-date-list (AddDate.dc.
    // html 案A "その場で開く"), not beside it -- so the open control/form
    // is appended as this list's own last child, after every
    // gathering-candidate-date row (orderingInvariant only constrains the
    // relative order of gathering-candidate-date-tagged children, which
    // this trailing, differently-tagged child does not disturb).
    // addCandidateDateOpen.presenceRule (adr/0042): present only while
    // SCHEDULING.
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

    // shopSelectionEntry.open (adr/0049 decision 1): before any shop has
    // ever been added (votingStartedAt still null), this entry button is
    // the dashboard's only shop-selection surface -- the retired
    // shortlistSelection picker this used to open inline is gone (see
    // renderShopSelectionEntry's own module-docstring history above).
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

    var linkPaneHeadChildren = [el("div", { class: "gth-pane-head" }, ["発行済みリンク"])];
    // participantLinkCopy.presenceRule (adr/0042): absent once FINALIZED (P4).
    if (phase !== "FINALIZED") {
      linkPaneHeadChildren.push(renderParticipantLinkCopy());
    }
    sections.push(
      el("div", { class: "gth-pane" }, [
        el("div", { class: "gth-pane-head-row" }, linkPaneHeadChildren),
        renderParticipantLinkList(),
      ])
    );

    root.appendChild(el("div", { class: "gth-dash" }, sections));

    // The calendar's anchor input above must already be attached to the
    // live DOM before flatpickr initializes it (the same "must already be
    // attached" precedent this file's own former initializeOpenShopMap
    // established for Leaflet).
    if (pendingAddCandidateDateCalendar) {
      pendingAddCandidateDateCalendar.initialize();
      activeAddCandidateDateCalendar = pendingAddCandidateDateCalendar;
    }
  }

  loadGathering();
})();
