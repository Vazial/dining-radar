/**
 * Signed-link participant-answer screen behaviour.
 *
 * Implements browserControlSurface.participantAnswer from
 * contracts/gathering-scheduling-browser-interface.yaml against the public
 * contracts/gathering-scheduling-api.yaml /participant-links/{token}*
 * endpoints. No organizerSession cookie and no CSRF token are used or
 * required (this contract's own securityObservations.participantAnswer
 * rationale: the token itself, supplied in the URL, is the sole credential).
 *
 * Human decision 2026-08-31: matches the approved screen skeleton
 * (E:\AWS\dsg-out\party\Answer.dc.html, "B｜参加者の回答") as a one-question-
 * at-a-time wizard, not the developer's earlier discretionary choice of
 * rendering every candidate date simultaneously. Per this contract's own
 * scheduleQuestion.cardinality note ("This contract does not fix whether
 * every CandidateDate renders simultaneously or progressively... It
 * requires only that whichever candidate dates are currently reachable in
 * the DOM each expose exactly one gathering-schedule-question... and that
 * gathering-participant-progress always reflects the true total regardless
 * of how many are currently rendered"), progressive disclosure is
 * contract-conformant. "Currently reachable" here means every candidate
 * date already answered (rendered as a compact "done" card, matching
 * Answer.dc.html's .card.done) plus the first still-unanswered one
 * (rendered as the full interactive "open" card) -- candidate dates beyond
 * that are folded into the "このあと聞かれること" summary panel and are
 * not built as DOM nodes at all.
 *
 * Design-vs-DSL judgment call (see this slice's developer report for the
 * full reasoning): Answer.dc.html's .card.done mockup omits the
 * 行ける/たぶん/むり buttons entirely for an already-answered date. This
 * script keeps them present (compact-styled) on every done card instead,
 * because product-brief.md §2 promises an answer is changeable at any
 * time with no exception once a later date is reached, TDR-GTH-06/15
 * exercise exactly that (re-answering, or rate-limiting on, a date that is
 * no longer the wizard's "current" one), and
 * tests/acceptance/dsl/gathering_scheduling_browser.py's own
 * answer_schedule_question/attempt_answer_schedule_question_expecting_rate_limit
 * locate a response option *scoped inside* the target date's own
 * gathering-schedule-question element regardless of its done/open visual
 * state -- there is no separate "reopen an answered date" affordance
 * anywhere in this contract or the approved screens for the DSL to drive
 * instead. Omitting the buttons on a done card, as the mockup literally
 * draws it, would make an already-answered date unanswerable a second time
 * from this screen, contradicting the always-changeable promise.
 *
 * Per rateLimitedScheduleResponse (this contract): a 429 from any
 * participant-facing call must retain every previously rendered
 * data-your-response/gathering-schedule-tally value, showing
 * gathering-participant-link-error *in addition to*, not instead of, the
 * last successfully loaded view -- state.view is therefore only ever
 * replaced on a *successful* response; a failure only sets state.errorCode
 * (see render()).
 *
 * 2026-09-04 addition (adr/0042, contract v0.5): the approval-voting
 * surface (shopVoteQuestion, Vote.dc.html B-2) and the finalized view
 * (finalizedView, Final.dc.html B-3). Once ParticipantView.decision becomes
 * non-null, finalizedView **replaces** scheduleQuestion/shopVoteQuestion/
 * progress/nameControl's open+submit entirely rather than coexisting with
 * them (this contract's own replacesQuestionSurfaces/noOperations clauses)
 * -- render() branches on `state.view.decision` before building anything
 * else.
 *
 * 2026-09-05 addition (adr/0044/0045/0046, contract v0.7.0): shopVoteQuestion
 * moved from a single toggling checkbox to a three-tier
 * WANT_TO_GO/OK_TO_GO/NOT_GOING selection (voteOptions), mirroring
 * scheduleQuestion.responseOptions' own three-sibling-button shape exactly.
 * Still **no pending state of its own** -- each activation immediately calls
 * setShopVotes with this shop's new status plus every other currently-
 * rendered shop's own currently-held vote (Vote.dc.html: "選ぶとその場で
 * 保存されます", no separate submit button) -- see selectShopVote below. Also
 * added: a shared map (shopVoteMap, gathering-shop-vote-map) showing every
 * rendered shop's pin plus the private search origin (adr/0045), and 5
 * per-shop detail fields (walking time / capacity / non-smoking / dinner
 * budget / provider page link, adr/0044). finalizedView's decision.shopVote
 * (renamed from decision.approvedShop) now carries one entry per shop among
 * the finalized shortlist, including one this participant never answered
 * (status: null, "答えないまま締まりました" -- adr/0046 open item 3,
 * 2026-09-05 human chat decision).
 *
 * 2026-09-06 addition (adr/0047, TDR-GTH-42, contract v0.8.0): this screen's
 * getParticipantView call had no error handling at all -- an unrecognized
 * response (a network failure that never reached the server, a body this
 * client could not parse, or a response carrying none of linkError's four
 * recognized ProblemResponse codes) left requestJson's promise chain
 * rejected with nothing caught, so applyResult/render never ran and the
 * page stayed exactly as the server template first rendered it (an empty
 * mount point) -- no question, no error surface, no explanation, matching
 * this ADR's own bug report exactly. requestJson below now never rejects
 * (a transport-level failure or an unparsable body resolves to a sentinel
 * result instead of throwing); loadView -- the initial getParticipantView
 * call only, matching this ADR's own scope and seedParticipantLinkServerError's
 * own scope (it seeds only the next getParticipantView call, not
 * setScheduleResponse/setShopVotes/setParticipantDisplayName) -- classifies
 * that result into exactly one of validLinkOutcome/invalidLinkOutcome/
 * unexpectedLoadFailureOutcome and sets state.loadFailure accordingly.
 * render() branches on state.loadFailure before building anything else,
 * the same way it already branches on state.view.decision for
 * finalizedView, so gathering-participant-load-error is the *only* element
 * this screen ever renders in that state (unexpectedLoadFailureOutcome's
 * own absent list). Human ruling (2026-09-06 chat): a short notice only,
 * no retry control -- reopening the link (a fresh page load) is the only
 * way to try again.
 */
(function () {
  "use strict";

  var root = document.getElementById("gathering-participant-app");
  if (!root) {
    return;
  }

  var token = root.getAttribute("data-participant-token");

  var state = {
    view: null,
    errorCode: null,
    nameOpen: false,
    // adr/0047, TDR-GTH-42: true exactly when unexpectedLoadFailureOutcome
    // applies -- set only by loadView below, never by any other
    // participant-facing call (seedParticipantLinkServerError's own scope).
    loadFailure: false,
  };

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
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    // adr/0047: this promise chain must never reject -- a rejected promise
    // here previously left applyResult/render uncalled entirely (this
    // file's own module docstring history), which is exactly the blank-
    // page bug TDR-GTH-42 covers. A network-level failure (fetch itself
    // rejects) or an unparsable body (response.json() rejects, e.g.
    // seedParticipantLinkServerError's empty-or-non-conforming 500)
    // resolves to a sentinel result instead -- status: null marks "never
    // reached the server at all"; body: null marks "reached the server
    // but the body could not be parsed" (a real HTTP status is still
    // reported in that second case).
    return fetch(url, options)
      .then(function (response) {
        return response.json().then(
          function (responseBody) {
            return { status: response.status, body: responseBody };
          },
          function () {
            return { status: response.status, body: null };
          }
        );
      })
      .catch(function () {
        return { status: null, body: null };
      });
  }

  // --- shared-date-formatting BEGIN (identical copy in gathering.js; keep both in sync) ---
  // Every startAt/confirmedCandidateDate value this screen ever receives
  // from the public API was itself produced by tagging a raw
  // <input type="datetime-local"> value as a literal UTC instant
  // (gathering.js's dateTimeLocalValueToIso: `value + ":00Z"`). Formatting
  // it for display must read back the *same* UTC calendar/clock
  // components, not convert to the viewing browser's own host timezone
  // (toLocaleString()/getHours()/getDate()/getDay() etc. all use the
  // host's local timezone per the JS spec) -- doing so would silently turn
  // the organizer's typed "12:00" into a different wall-clock number on a
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

  function participantUrl() {
    return "/participant-links/" + encodeURIComponent(token);
  }

  // 2026-09-05 addition (adr/0044/0046): the coarse tier vocabularies also
  // used by web/static/dining_radar/web/candidate.js and by gathering.js's
  // own organizer-facing copy -- duplicated here (no shared module system
  // exists in this codebase; every other small utility, e.g. el()/
  // requestJson()/the date formatter above, is already duplicated the same
  // way).
  var CAPACITY_TIER_LABELS = { SMALL: "少なめ", MEDIUM: "標準", LARGE: "多め" };
  var NON_SMOKING_LABELS = { FULL: "全席禁煙", PARTIAL: "一部禁煙", NONE: "禁煙席なし" };
  var BUDGET_TIER_LABELS = { LOW: "低", MID: "中", HIGH: "高" };

  // adr/0044, TDR-GTH-39: the 5 detail fields shown per shop on this
  // screen's shopVoteQuestion (walking time / capacity / non-smoking /
  // dinner budget / provider page link) -- field-for-field the same
  // information gathering.js's own renderOpenShopDetailFields shows on the
  // organizer's shortlistSelection list, with this screen's own test-id
  // prefix.
  function renderShopVoteDetailFields(question) {
    return [
      el(
        "span",
        {
          "data-testid": "gathering-shop-vote-question-walking-time",
          class: "gth-shop-detail",
        },
        ["徒歩 約" + question.walkingTimeMinutes + "分"]
      ),
      el(
        "span",
        {
          "data-testid": "gathering-shop-vote-question-capacity-tier",
          class: "gth-shop-detail",
        },
        [question.capacityTier ? CAPACITY_TIER_LABELS[question.capacityTier] : "情報なし"]
      ),
      el(
        "span",
        {
          "data-testid": "gathering-shop-vote-question-non-smoking",
          class: "gth-shop-detail",
        },
        [question.nonSmokingStatus ? NON_SMOKING_LABELS[question.nonSmokingStatus] : "情報なし"]
      ),
      el(
        "span",
        {
          "data-testid": "gathering-shop-vote-question-dinner-budget",
          class: "gth-shop-detail",
        },
        [
          question.dinnerBudgetTier
            ? "予算感 " + BUDGET_TIER_LABELS[question.dinnerBudgetTier]
            : "情報なし",
        ]
      ),
      el(
        "a",
        {
          "data-testid": "gathering-shop-vote-question-provider-page-link",
          href: question.providerPageUrl,
          target: "_blank",
          rel: "noopener noreferrer",
          class: "gth-shop-link",
        },
        ["店のページを見る"]
      ),
    ];
  }

  // adr/0044/0045, TDR-GTH-39/41: the participant's shared map
  // (gathering-shop-vote-map/-marker), plus the private search origin
  // marker (gathering-search-origin-marker, adr/0045 -- the extension of
  // ADR-0025 decision 1's disclosure to this unauthenticated screen). This
  // map's own marker/origin test ids are distinct from both candidate.js's
  // (candidate-map-marker/candidate-origin-marker,
  // unavailableControls.forbiddenTestIds) and gathering.js's own organizer-
  // facing map (gathering-open-shop-map-marker) -- see this file's own
  // module docstring history for why a shared JS module is not used here.
  var shopVoteMapInstance = null;

  function initializeShopVoteMap(container, items, searchOrigin) {
    if (shopVoteMapInstance) {
      shopVoteMapInstance.remove();
      shopVoteMapInstance = null;
    }
    if (!window.L || !container) {
      return;
    }
    var map = window.L.map(container, { attributionControl: false });
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);
    var latLngs = items.map(function (item) {
      return [item.location.latitude, item.location.longitude];
    });
    var boundsLatLngs = latLngs.slice();
    if (searchOrigin) {
      boundsLatLngs.push([searchOrigin.latitude, searchOrigin.longitude]);
    }
    if (boundsLatLngs.length > 0) {
      map.fitBounds(window.L.latLngBounds(boundsLatLngs), { padding: [24, 24] });
    } else {
      map.setView([0, 0], 2);
    }
    items.forEach(function (item, index) {
      var icon = window.L.divIcon({
        className: "gathering-shop-vote-map-marker-icon",
        html: '<span class="gathering-shop-vote-map-marker-visual"></span>',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      // keyboard: false -- these pins are display-only (the actual vote is
      // cast via the three vote buttons below, not by clicking a pin); no
      // ADR-0020-decision-4(c)-style keyboard-operability requirement
      // exists for this screen's map.
      var marker = window.L.marker(latLngs[index], { icon: icon, keyboard: false });
      marker.addTo(map);
      var markerEl = marker.getElement();
      if (!markerEl) {
        return;
      }
      markerEl.setAttribute("data-testid", "gathering-shop-vote-map-marker");
      markerEl.setAttribute("data-shop-id", item.shopId);
    });
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
        alt: "検索基点",
      });
      originMarker.addTo(map);
      var originEl = originMarker.getElement();
      if (originEl) {
        originEl.setAttribute("data-testid", "gathering-search-origin-marker");
        originEl.setAttribute("aria-label", "検索基点");
      }
    }
    shopVoteMapInstance = map;
  }

  function applyResult(result, onSuccess) {
    if (result.status === 200) {
      state.view = result.body;
      state.errorCode = null;
      if (onSuccess) {
        onSuccess();
      }
    } else {
      state.errorCode = result.body && result.body.code ? result.body.code : "LINK_NOT_FOUND";
    }
    render();
  }

  // browserEntry.participantAnswer's own three, mutually exclusive,
  // exhaustive outcomes for opening a participant link (adr/0047):
  // validLinkOutcome (200), invalidLinkOutcome (one of these four
  // recognized ProblemResponse codes), or unexpectedLoadFailureOutcome
  // (every other case).
  var RECOGNIZED_LINK_ERROR_CODES = [
    "LINK_NOT_FOUND",
    "LINK_EXPIRED",
    "LINK_REVOKED",
    "LINK_RATE_LIMITED",
  ];

  function loadView() {
    requestJson("GET", participantUrl()).then(function (result) {
      if (result.status === 200) {
        state.view = result.body;
        state.errorCode = null;
        state.loadFailure = false;
      } else if (
        result.body &&
        RECOGNIZED_LINK_ERROR_CODES.indexOf(result.body.code) !== -1
      ) {
        // invalidLinkOutcome: linkError already covers this meaningful,
        // explicit rejection.
        state.view = null;
        state.errorCode = result.body.code;
        state.loadFailure = false;
      } else {
        // unexpectedLoadFailureOutcome (adr/0047, TDR-GTH-42): a
        // transport-level failure, an unparsable body, or a response
        // carrying none of linkError's four recognized codes.
        state.view = null;
        state.errorCode = null;
        state.loadFailure = true;
      }
      render();
    });
  }

  function answerScheduleQuestion(candidateDateId, status) {
    requestJson("PUT", participantUrl() + "/responses/" + candidateDateId, { status: status }).then(
      function (result) {
        applyResult(result);
      }
    );
  }

  function selectShopVote(shopId, status) {
    // shopVoteQuestion.voteOptions.requiredOutcome (adr/0044, three-tier):
    // immediately calls setShopVotes with a votes array containing
    // {shopId, status} for this shop plus this participant's currently-held
    // vote for every other currently-rendered shop -- not a pending/submit
    // model, unlike the organizer's shortlistSelection. Computed from the
    // *current* view so this activation sets exactly the targeted shop's
    // status and leaves every other shop's vote as-is; a shop with no
    // currently-held vote (yourVote still null/"not yet answered") is
    // omitted from the array entirely, not forced into any status
    // (SetShopVotesRequest's own "a shop omitted here is left not yet
    // answered" rule).
    var votes = (state.view.shopVoteQuestions || [])
      .map(function (question) {
        var value = question.shopId === shopId ? status : question.yourVote;
        if (value === null || value === undefined) {
          return null;
        }
        return { shopId: question.shopId, status: value };
      })
      .filter(function (entry) {
        return entry !== null;
      });
    requestJson("PUT", participantUrl() + "/shop-votes", { votes: votes }).then(function (result) {
      applyResult(result);
    });
  }

  function openNameControl() {
    state.nameOpen = true;
    render();
  }

  function submitDisplayName(displayName) {
    if (!displayName) {
      return;
    }
    requestJson("PUT", participantUrl() + "/display-name", { displayName: displayName }).then(
      function (result) {
        applyResult(result, function () {
          state.nameOpen = false;
        });
      }
    );
  }

  function renderHeader(answered, total) {
    var titleRow = el("div", { class: "gth-hd-row" }, [
      el("div", { class: "gth-title" }, [state.view.gatheringTitle]),
      el("div", { class: "gth-count" }, ["日程 " + answered + " / " + total]),
    ]);
    var progressPercent = total > 0 ? Math.round((answered / total) * 100) : 0;
    var progressBar = el("div", { class: "gth-progress" }, [
      el("i", { style: "width: " + progressPercent + "%" }, []),
    ]);
    return el(
      "header",
      { "data-testid": "gathering-participant-header", "data-gathering-phase": state.view.phase },
      [titleRow, progressBar, renderNameControl(true)]
    );
  }

  /**
   * Final.dc.html B-3's simpler header -- no per-date progress counter.
   * data-gathering-phase remains present unconditionally per this
   * contract's own headerAttributes.requirement, and
   * gathering-participant-name-status remains present too (only the
   * open/submit editing controls retire, nameControl.open/submit
   * .presenceRule below).
   */
  function renderFinalizedHeader() {
    var titleRow = el("div", { class: "gth-hd-row" }, [
      el("div", { class: "gth-title" }, [state.view.gatheringTitle]),
    ]);
    return el(
      "header",
      { "data-testid": "gathering-participant-header", "data-gathering-phase": state.view.phase },
      [titleRow, renderNameControl(false)]
    );
  }

  /**
   * @param allowEdit nameControl.open/submit.presenceRule (adr/0042):
   *   absent once ParticipantView.decision is non-null (Final.dc.html:
   *   "名前を変える操作も置かない"). gathering-participant-name-status
   *   itself always renders regardless.
   */
  function renderNameControl(allowEdit) {
    var named = state.view.displayName !== null;
    var status = el(
      "div",
      {
        "data-testid": "gathering-participant-name-status",
        "data-participant-named": named ? "true" : "false",
        class: "gth-who-name",
      },
      [named ? "回答者: " + state.view.displayName : "名前なしのまま"]
    );

    if (!allowEdit) {
      return el("div", { class: "gth-who" }, [status]);
    }

    var openButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-name-open",
        "data-gathering-control-purpose": "gathering-participant-name-open",
        class: "gth-who-action",
      },
      ["名前を付ける"]
    );
    openButton.addEventListener("click", openNameControl);

    var whoRow = el("div", { class: "gth-who" }, [status, openButton]);

    if (!state.nameOpen) {
      return whoRow;
    }

    var input = el(
      "input",
      { type: "text", "data-testid": "gathering-participant-name-input", class: "gth-name-input" },
      []
    );
    var submit = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-name-submit",
        "data-gathering-control-purpose": "gathering-participant-name-submit",
      },
      ["決定"]
    );
    submit.addEventListener("click", function () {
      submitDisplayName(input.value);
    });
    return el("div", {}, [whoRow, el("div", { class: "gth-name-form" }, [input, submit])]);
  }

  var RESPONSE_VALUES = ["GOING", "MAYBE", "NOT_GOING"];
  var RESPONSE_LABELS = { GOING: "行ける", MAYBE: "たぶん", NOT_GOING: "むり" };

  function responseOptionButtons(question, yourResponse, compact) {
    return RESPONSE_VALUES.map(function (value) {
      var option = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-schedule-response-option",
          "data-gathering-control-purpose": "gathering-schedule-response-select",
          "data-response-value": value,
          "aria-pressed": yourResponse === value ? "true" : "false",
          class: "gth-opt" + (compact ? " gth-opt--compact" : "") + (yourResponse === value ? " gth-opt--on" : ""),
        },
        [RESPONSE_LABELS[value]]
      );
      option.addEventListener("click", function () {
        answerScheduleQuestion(question.candidateDateId, value);
      });
      return option;
    });
  }

  function renderTally(question) {
    if (!question.tally) {
      return null;
    }
    return el(
      "div",
      {
        "data-testid": "gathering-schedule-tally",
        "data-going-count": question.tally.goingCount,
        "data-maybe-count": question.tally.maybeCount,
        "data-not-going-count": question.tally.notGoingCount,
        class: "gth-tally",
      },
      [
        el("span", {}, ["行ける ", el("b", {}, [String(question.tally.goingCount)])]),
        el("span", {}, ["たぶん ", el("b", {}, [String(question.tally.maybeCount)])]),
        el("span", {}, ["むり ", el("b", {}, [String(question.tally.notGoingCount)])]),
      ]
    );
  }

  /**
   * A previously-answered candidate date: Answer.dc.html's .card.done
   * (date + answer badge + tally + "答えたので、ほかの人の回答も見えています"),
   * with the response options kept present (compact) so the answer stays
   * changeable -- see this file's module docstring for why that departs
   * from the mockup's own drawing.
   */
  function renderDoneQuestionCard(question) {
    var yourResponse = question.yourResponse;
    var children = [
      el("div", { class: "gth-done-top" }, [
        el("div", { class: "gth-done-date" }, [formatGatheringDateTime(question.startAt)]),
        el("div", { class: "gth-done-badge" }, [RESPONSE_LABELS[yourResponse]]),
      ]),
    ];
    var tally = renderTally(question);
    if (tally) {
      children.push(tally);
    }
    children.push(
      el("div", { class: "gth-done-hint" }, ["答えたので、ほかの人の回答も見えています"])
    );
    children.push(
      el(
        "div",
        { class: "gth-done-options" },
        responseOptionButtons(question, yourResponse, true)
      )
    );

    return el(
      "div",
      {
        "data-testid": "gathering-schedule-question",
        "data-candidate-date-id": question.candidateDateId,
        "data-open-shop-count": question.openShopCount,
        "data-your-response": yourResponse,
        class: "gth-card gth-card--done",
      },
      children
    );
  }

  /**
   * The one currently-open question: Answer.dc.html's dashed-border .card
   * (question label, date, "この日に開いている店 N件" -- D6 -- the
   * "answer to see others" mask hint -- product-brief.md §2 -- and the
   * three full-size response options).
   */
  function renderOpenQuestionCard(question) {
    return el(
      "div",
      {
        "data-testid": "gathering-schedule-question",
        "data-candidate-date-id": question.candidateDateId,
        "data-open-shop-count": question.openShopCount,
        "data-your-response": "UNANSWERED",
        class: "gth-card gth-card--open",
      },
      [
        el("div", { class: "gth-open-label" }, ["この日、行けそう？"]),
        el("div", { class: "gth-open-date" }, [formatGatheringDateTime(question.startAt)]),
        el("div", { class: "gth-open-shop-count" }, [
          "この日に開いている店 ",
          el("b", {}, [String(question.openShopCount)]),
          "件",
        ]),
        el("div", { class: "gth-mask" }, ["ほかの人の回答は、あなたが答えると見えます"]),
        el(
          "div",
          { class: "gth-open-options" },
          responseOptionButtons(question, "UNANSWERED", false)
        ),
      ]
    );
  }

  /**
   * "このあと聞かれること" -- a count only (Answer.dc.html shows "日程 —
   * あと1つ", never a per-date list) for candidate dates beyond the one
   * open card. These dates have no gathering-schedule-question element in
   * the DOM at all until the participant reaches them (see this file's
   * module docstring).
   */
  function renderNextPanel(remainingCount, phase) {
    if (remainingCount <= 0) {
      return null;
    }
    return el("div", { class: "gth-next" }, [
      el("div", { class: "gth-next-heading" }, ["このあと聞かれること"]),
      el("div", { class: "gth-next-row" }, [
        el("span", {}, ["日程"]),
        el("span", {}, ["あと " + remainingCount + "つ"]),
      ]),
      el("div", { class: "gth-next-row" }, [
        el("span", {}, ["お店の投票"]),
        el(
          "span",
          { class: "gth-next-muted" },
          [phase === "SCHEDULING" ? "幹事が日を決めてから" : "開催日が決まりました"]
        ),
      ]),
    ]);
  }

  /**
   * The approval-voting surface (Vote.dc.html B-2, shopVoteQuestion).
   * Present exactly when ParticipantView.shopVoteQuestions is non-null and
   * decision is still null (render() only calls this from the non-decision
   * branch, so the decision check itself lives there).
   */
  var VOTE_VALUES = ["WANT_TO_GO", "OK_TO_GO", "NOT_GOING"];
  var VOTE_LABELS = { WANT_TO_GO: "行きたい", OK_TO_GO: "行ってもいい", NOT_GOING: "むり" };

  // shopVoteQuestion.voteOptions (adr/0044, restructured 2026-09-05):
  // mirrors responseOptionButtons above exactly -- three sibling buttons
  // sharing one operational purpose (gathering-shop-vote-select), each
  // immediately calling selectShopVote on activation.
  function voteOptionButtons(question) {
    return VOTE_VALUES.map(function (value) {
      var option = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-shop-vote-option",
          "data-gathering-control-purpose": "gathering-shop-vote-select",
          "data-vote-value": value,
          "aria-pressed": question.yourVote === value ? "true" : "false",
          class:
            "gth-opt gth-opt--compact" + (question.yourVote === value ? " gth-opt--on" : ""),
        },
        [VOTE_LABELS[value]]
      );
      option.addEventListener("click", function () {
        selectShopVote(question.shopId, value);
      });
      return option;
    });
  }

  function renderShopVoteTally(question) {
    if (question.tally === null || question.tally === undefined) {
      // product-brief.md §2's "answer first, then see others" rule, applied
      // per shop (TDR-GTH-29) -- absent exactly when yourVote is
      // "UNANSWERED".
      return null;
    }
    return el(
      "div",
      {
        "data-testid": "gathering-shop-vote-tally",
        "data-want-to-go-count": question.tally.wantToGoCount,
        "data-ok-to-go-count": question.tally.okToGoCount,
        "data-not-going-count": question.tally.notGoingCount,
        "data-responded-count": question.tally.respondedParticipantCount,
        class: "gth-vote-tally",
      },
      [
        el("span", {}, [VOTE_LABELS.WANT_TO_GO + " ", el("b", {}, [String(question.tally.wantToGoCount)])]),
        el("span", {}, [VOTE_LABELS.OK_TO_GO + " ", el("b", {}, [String(question.tally.okToGoCount)])]),
        el("span", {}, [VOTE_LABELS.NOT_GOING + " ", el("b", {}, [String(question.tally.notGoingCount)])]),
      ]
    );
  }

  function renderShopVoteQuestion(question) {
    var yourVoteValue = question.yourVote === null ? "UNANSWERED" : question.yourVote;
    var detailRow = el(
      "div",
      { class: "gth-shop-detail-row" },
      renderShopVoteDetailFields(question)
    );
    var children = [el("span", { class: "gth-vote-name" }, [question.name]), detailRow];
    children.push(el("div", { class: "gth-vote-options" }, voteOptionButtons(question)));
    var tally = renderShopVoteTally(question);
    if (tally) {
      children.push(tally);
    } else {
      children.push(el("span", { class: "gth-vote-mask" }, ["あなたが答えると票が見えます"]));
    }

    return el(
      "div",
      {
        "data-testid": "gathering-shop-vote-question",
        "data-shop-id": question.shopId,
        "data-your-vote": yourVoteValue,
        class: "gth-vote-row",
      },
      children
    );
  }

  function renderShopVoteSection() {
    if (!state.view.shopVoteQuestions) {
      return null;
    }
    // gathering-shop-vote-map (adr/0044/0045, TDR-GTH-39/41): one shared
    // map, appended to the live DOM by render() below before this map is
    // initialized (see initializeShopVoteMap's own module-docstring
    // precedent).
    var mapContainer = el(
      "div",
      { "data-testid": "gathering-shop-vote-map", class: "gth-shop-map" },
      []
    );
    var node = el(
      "div",
      { class: "gth-vote-section" },
      [el("div", { class: "gth-vote-heading" }, ["お店に投票してください"]), mapContainer].concat(
        state.view.shopVoteQuestions.map(renderShopVoteQuestion)
      )
    );
    return {
      node: node,
      mapContainer: mapContainer,
      items: state.view.shopVoteQuestions,
      searchOrigin: state.view.searchOrigin,
    };
  }

  // finalizedView.decision.shopVote's statusValues (adr/0044/0046): the
  // three real ShopVoteStatus values plus the null-to-sentinel "UNANSWERED"
  // ("答えないまま締まりました", adr/0046 open item 3, 2026-09-05 human chat
  // decision) -- the same null-to-sentinel convention
  // scheduleQuestion.yourResponseValues/shopVoteQuestion.yourVoteValues
  // already use.
  var VOTE_STATUS_LABELS = {
    WANT_TO_GO: "行きたい",
    OK_TO_GO: "行ってもいい",
    NOT_GOING: "むり",
    UNANSWERED: "答えないまま締まりました",
  };

  /**
   * Final.dc.html B-3 -- the decision plus this participant's own
   * retrospective record (P5, adr/0041/adr/0042; generalized to the
   * three-tier vote 2026-09-05, adr/0044; extended the same day to include
   * a never-answered shop, adr/0046). Never another participant's data
   * (decision.yourShopVotes is this participant's own votes only,
   * gathering-scheduling-api.yaml adr/0041/adr/0044).
   */
  function renderFinalizedView() {
    var decision = state.view.decision;
    var yourScheduleResponseValue =
      decision.yourScheduleResponse === null ? "UNANSWERED" : decision.yourScheduleResponse;

    var shopVoteEls = decision.yourShopVotes.map(function (entry) {
      var voteStatusValue = entry.status === null ? "UNANSWERED" : entry.status;
      return el(
        "div",
        {
          "data-testid": "gathering-participant-decision-shop-vote",
          "data-shop-id": entry.shop.shopId,
          "data-vote-status": voteStatusValue,
          class: "gth-final-shop-vote",
        },
        [
          el("span", { class: "gth-final-shop-vote-name" }, [entry.shop.name]),
          el("span", { class: "gth-final-shop-vote-status" }, [
            VOTE_STATUS_LABELS[voteStatusValue],
          ]),
        ]
      );
    });

    var decisionEl = el(
      "div",
      {
        "data-testid": "gathering-participant-decision",
        "data-confirmed-candidate-date": decision.confirmedCandidateDate,
        "data-shop-id": decision.shop.shopId,
        "data-your-schedule-response": yourScheduleResponseValue,
        class: "gth-final",
      },
      [
        el("div", { class: "gth-final-badge" }, ["決まりました"]),
        el("div", { class: "gth-final-when-lb" }, ["日時"]),
        el("div", { class: "gth-final-when" }, [
          formatGatheringDateTime(decision.confirmedCandidateDate),
        ]),
        el("div", { class: "gth-final-shop-lb" }, ["お店"]),
        el("div", { class: "gth-final-shop" }, [decision.shop.name]),
        el("div", { class: "gth-final-yours-lb" }, ["あなたの記録"]),
        el("div", { class: "gth-final-yours-row" }, [
          "この日へのあなたの回答: ",
          el("b", {}, [
            decision.yourScheduleResponse === null
              ? "未回答"
              : RESPONSE_LABELS[decision.yourScheduleResponse],
          ]),
        ]),
        el(
          "div",
          { class: "gth-final-approved" },
          [el("div", { class: "gth-final-approved-lb" }, ["店ごとのあなたの回答"])].concat(
            shopVoteEls
          )
        ),
        el("p", { class: "gth-fine" }, [
          "締まっているので変えられません。ほかの人が何を選んだかは出していません。",
        ]),
      ]
    );

    return el("div", { class: "gth-body" }, [decisionEl]);
  }

  function renderFooter() {
    // Answer.dc.html shows these two entry points ("あとで答える" /
    // "結果をのぞく") but defines no resulting operation for either in this
    // contract -- no allowedPurposes value corresponds to them and no
    // TDR-GTH scenario interacts with them. Rendered as plain, purposeless
    // <div>s (not <button>s) so they read as inert placeholders rather than
    // controls this contract does not actually wire up, mirroring this
    // project's existing precedent for a display-only entry point
    // (activeContext.md's candidate-map-open/-sheet-close judgment).
    return el("div", { class: "gth-foot" }, [
      el("div", { class: "gth-foot-btn" }, ["あとで答える"]),
      el("div", { class: "gth-foot-btn" }, ["結果をのぞく"]),
    ]);
  }

  function renderFinePrint() {
    return el("p", { class: "gth-fine" }, [
      "幹事から届いたリンクで開いています。ログインも名前も要りません。",
      el("br", {}, []),
      "名前はあとからでも付けられます。答えは何度でも変えられます。",
    ]);
  }

  function renderProgress(total, answered) {
    return el(
      "div",
      {
        "data-testid": "gathering-participant-progress",
        "data-total-candidate-dates": total,
        "data-answered-candidate-dates": answered,
        class: "gth-progress-status",
      },
      []
    );
  }

  function renderError() {
    return el(
      "div",
      { "data-testid": "gathering-participant-link-error", "data-link-error-code": state.errorCode },
      ["このリンクは使用できません。幹事に新しいリンクを依頼してください。"]
    );
  }

  /**
   * unexpectedLoadFailureOutcome's own required surface
   * (browserControlSurface.participantAnswer.loadFailure, adr/0047,
   * TDR-GTH-42). Its visible text conveys only that loading failed and
   * that reopening the link later may work -- never an HTTP status code,
   * an exception message, a request/trace identifier, or a hostname (this
   * function reads nothing from the failed response at all, so there is
   * nothing technical here to leak). No purpose-declared control is
   * rendered here -- human ruling 2026-09-06: the notice alone, no retry
   * button (loadFailure.noRetryControl).
   */
  function renderLoadFailure() {
    return el(
      "div",
      { "data-testid": "gathering-participant-load-error", class: "gth-load-error" },
      ["うまく読み込めませんでした。時間をおいて開き直してください。"]
    );
  }

  function render() {
    root.innerHTML = "";
    if (state.loadFailure) {
      // unexpectedLoadFailureOutcome's own absent list (adr/0047): every
      // other participant-facing element -- header, schedule question,
      // name-open, linkError, shop-vote question, decision -- stays
      // absent, mirroring the finalizedView branch's own dedicated-
      // branch style below rather than gating each element individually.
      root.appendChild(el("div", { class: "gth-app" }, [renderLoadFailure()]));
      return;
    }
    var children = [];
    var shopVoteMapPending = null;
    if (state.view) {
      if (state.view.decision) {
        // finalizedView (adr/0042): replaces scheduleQuestion/
        // shopVoteQuestion/progress and nameControl's open/submit entirely
        // (replacesQuestionSurfaces/noOperations) -- built from a
        // dedicated branch rather than gating each element individually.
        children.push(renderFinalizedHeader());
        children.push(renderFinalizedView());
      } else {
        var questions = state.view.scheduleQuestions;
        var total = questions.length;
        var firstUnansweredIndex = -1;
        for (var index = 0; index < questions.length; index += 1) {
          if (questions[index].yourResponse === null) {
            firstUnansweredIndex = index;
            break;
          }
        }
        var answered = firstUnansweredIndex === -1 ? total : firstUnansweredIndex;

        children.push(renderHeader(answered, total));

        var body = [];
        for (var doneIndex = 0; doneIndex < answered; doneIndex += 1) {
          body.push(renderDoneQuestionCard(questions[doneIndex]));
        }
        var remainingCount;
        if (firstUnansweredIndex === -1) {
          remainingCount = 0;
        } else {
          body.push(renderOpenQuestionCard(questions[firstUnansweredIndex]));
          remainingCount = total - firstUnansweredIndex - 1;
        }
        var shopVoteSection = renderShopVoteSection();
        if (shopVoteSection) {
          body.push(shopVoteSection.node);
          shopVoteMapPending = shopVoteSection;
        }
        var nextPanel = renderNextPanel(remainingCount, state.view.phase);
        if (nextPanel) {
          body.push(nextPanel);
        }
        body.push(renderFooter());
        body.push(renderFinePrint());
        children.push(el("main", { class: "gth-body" }, body));
        children.push(renderProgress(total, answered));
      }
    }
    if (state.errorCode) {
      children.push(renderError());
    }
    root.appendChild(el("div", { class: "gth-app" }, children));

    // The map container above must already be attached to the live DOM
    // before Leaflet initializes it (see initializeShopVoteMap's own
    // module-docstring precedent, gathering.js's initializeOpenShopMap).
    if (shopVoteMapPending) {
      initializeShopVoteMap(
        shopVoteMapPending.mapContainer,
        shopVoteMapPending.items,
        shopVoteMapPending.searchOrigin
      );
    }
  }

  loadView();
})();
