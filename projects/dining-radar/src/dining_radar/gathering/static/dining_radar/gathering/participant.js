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
 *
 * 2026-09-06 fix (intermittent acceptance failures, e.g. TDR-GTH-05/16:
 * gathering-participant-name-status observed "false" right after a
 * display-name submission that the server had already accepted): every
 * participant-facing call (loadView/answerScheduleQuestion/selectShopVote/
 * submitDisplayName) hands its own full ParticipantView back and this file
 * simply overwrote state.view with whichever response happened to *arrive*
 * last -- not whichever request was *issued* last. Confirmed directly
 * (throwaway Playwright repro, not committed): letting a schedule-response
 * PUT reach and be processed by the server immediately, but deliberately
 * delaying only the delivery of *its own response* back past a
 * display-name PUT fired right after it (no wait in between, the way a
 * real tap on a slow connection would), reproduced exactly this symptom --
 * the display-name write had already committed and the later PUT's own
 * response body did carry it, but the earlier-issued, later-arriving
 * schedule-response PUT's response (computed before the display-name
 * write happened) still unconditionally overwrote state.view once it
 * finally arrived, reverting gathering-participant-name-status back to
 * "false" with nothing left to correct it afterward. requestSequence/
 * beginRequest/isStaleResponse below are a generation counter: each call
 * records the sequence number in effect when *it* fires the request, and
 * its own .then callback discards the result instead of touching
 * state/render at all once a *newer* call has since been issued -- so the
 * response tied to whichever request was issued last always governs the
 * final render, regardless of which response happens to arrive last
 * (gathering.js's tentativelySelectCandidateDate already used this same
 * shape of guard, ad hoc, for one single call; this generalizes it to
 * every participant-facing write plus the initial load).
 *
 * 2026-09-13 revision (ADR-0054/0055/0056, human ruling 2026-09-12 chat,
 * 5-bucket redesign of the gathering screen group, buckets 2/4/5):
 * - **All three approval-seeking prose strings FR-034 named are deleted
 *   outright, with no replacement sentence** -- "ほかの人の回答も見えています"
 *   (both the done-card hint and the open-card mask, ADR-0055 decision 1
 *   context), "ここまでの回答は保存されています。またあとで、続きから答え
 *   られます。" (answerLater's old confirmation prose), and "幹事から届いた
 *   リンクで開いています。ログインも名前も要りません。名前はあとからでも
 *   付けられます。答えは何度でも変えられます。" (the screen's old fine
 *   print, renderFinePrint, removed along with the function itself).
 * - **openShopCount is gone**: gathering-scheduling-api.yaml v0.12.0 no
 *   longer sends it on ParticipantScheduleQuestion (ADR-0055 decision 1) --
 *   this file no longer reads question.openShopCount or renders
 *   data-open-shop-count/"この日に開いている店 N件" anywhere.
 * - **答え結果をのぞく／あとで答える no longer share a row** (FR-034's own
 *   repro: a `<p>` confirmation sibling squeezed both flex:1 buttons under
 *   44px wide). peekResults now renders at the very top of the scrollable
 *   body (renderPeekResultsButton); answerLater renders as the very last
 *   element (renderAnswerLaterButton) -- the two are never DOM siblings in
 *   the same flex row again.
 * - **answerLater's confirmation is an overlapping surface, not an inline
 *   sentence** (renderAnswerLaterOverlay): a fixed-position scrim+panel
 *   listing this participant's own already-recorded answers (schedule
 *   responses and shop votes), reproducing scheduleQuestion.attributes'/
 *   shopVoteQuestion.attributes' own data-candidate-date-id/data-your-
 *   response and data-shop-id/data-your-vote values verbatim (this
 *   contract's own "does not fix the markup used to reproduce these
 *   values" allowance) -- never a sentence asserting the answers are
 *   saved. Dismissed by activating the scrim (a plain, purposeless `<div>`
 *   click target, outside forbiddenFormControlCategories' scan).
 * - **The shop-vote tally now also renders a fixed-length bar**
 *   (renderShopVoteBar) sized against ParticipantView.
 *   totalActiveParticipantCount (ADR-0056 decision 9) rather than however
 *   many participants have voted on that shop so far, so a thinly-
 *   supported shop shows as a short bar even while voting is still in
 *   progress. Omitted entirely if the API has not yet started returning
 *   this field (this round's API work ships from a different developer in
 *   parallel).
 * - **"あとから入りました" (ADR-0056 decision 6) is a separate mark from
 *   "did I answer this shop"**: data-added-after-voting-started (mirrored
 *   verbatim from ParticipantShopVoteOption.addedAfterVotingStarted) drives
 *   only a small badge next to the shop name; a card's own border
 *   highlight (gth-vote-row--answered) is driven only by data-your-vote
 *   being non-"UNANSWERED" -- human ruling: "印は2つに分ける。札は『あとから
 *   入ったか』だけ、カードの縁は『自分が答えたか』だけ。1つの印に2つの意味を
 *   持たせない。"
 * - **finalizedView shows exactly 5 things, in this order** (いつ／どの店／
 *   どこにあるか／徒歩の目安／店のページへの線, ADR-0056 decision 10):
 *   data-your-schedule-response and its "あなたの日程への回答" row are
 *   deleted entirely (ADR-0055 decision 7, one step past adr/0050 decision
 *   3's earlier simplification), replaced by a map (gathering-participant-
 *   decision-map, showing only the decided shop's own pin and this
 *   participant's search origin -- **no line connecting them, no walking-
 *   radius ring**: this product never queries a routing service and does
 *   not assert path information it does not have) plus data-walking-time-
 *   minutes and a provider-page link.
 * - **The live shop-vote tally remains visible after finalization**
 *   (ADR-0055 decision 8: replacesQuestionSurfaces no longer names
 *   gathering-shop-vote-question) -- renderShopVoteSection/
 *   renderShopVoteQuestion take a showVoteOptions flag so the finalized
 *   branch can reuse the exact same map/tally/bar rendering with only the
 *   three vote buttons themselves suppressed (noOperations: no
 *   gathering-shop-vote-option once decision is non-null).
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
    // adr/0050 decision 1 (2026-09-09): answerLater/peekResults, both made
    // functional this round (previously "見た目だけの飾り", designer's own
    // words). Neither calls a public operation -- both are purely
    // client-side reveals.
    answerLaterConfirmationOpen: false,
    // Whether the currently-open (not-yet-answered) question's own tally
    // has been explicitly revealed. Every *done* question's tally stays
    // unconditionally visible regardless of this flag (adr/0050 decision 2
    // already settled that "約束は覆してもよい" for answered questions);
    // this flag only governs the one open question's tally/mask -- keeping
    // it hidden until the participant actively chooses to "のぞく" (peek)
    // is this developer's own reading of the verb, not fixed by the
    // contract (which "does not fix the visible layout of this overview").
    peekResultsActivated: false,
  };

  // request-sequencer:start -- Stale-response guard (this file's module
  // docstring, 2026-09-06 fix): every participant-facing request is
  // assigned the sequence number current at the moment *it* is issued; its
  // own callback compares that captured number against the *current*
  // value below (which only ever advances, never resets) and does nothing
  // at all once a newer request has since been issued -- discarding a
  // late, now-superseded response rather than letting it revert
  // state.view/render with older data than whatever the most recently
  // issued request's own eventual response will carry.
  //
  // tests/js_unit/participant_request_sequencer.test.js extracts and
  // executes this exact block verbatim (delimited by these
  // "request-sequencer:start"/"request-sequencer:end" comments) to pin
  // this behaviour with a real (Node-runnable, zero-dependency) unit test
  // -- not a hand-copied reimplementation that could silently drift from
  // what actually ships. Keep this block self-contained (no reference to
  // anything outside it) so that extraction keeps working.
  var requestSequence = 0;

  function beginRequest() {
    requestSequence += 1;
    return requestSequence;
  }

  function isStaleResponse(sequence) {
    return sequence !== requestSequence;
  }
  // request-sequencer:end

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

  // 2026-09-13 addition (ADR-0056 decision 10): finalizedView's own map,
  // showing exactly two points -- the decided shop's own pin and this
  // participant's search origin -- and nothing else. Deliberately does not
  // draw a line between them or a walking-radius ring (this file's own
  // module-docstring entry for this date explains why); reuses the same
  // marker visuals as initializeShopVoteMap above (a plain CSS choice, not
  // a shared test id -- gathering-participant-decision-map-marker/
  // -origin-marker are set as separate data-testid attributes below,
  // distinct from gathering-shop-vote-map-marker/gathering-search-origin-
  // marker per this contract's own forbiddenTestIds/distinct-element
  // notes).
  var decisionMapInstance = null;

  function initializeDecisionMap(container, shop, searchOrigin) {
    if (decisionMapInstance) {
      decisionMapInstance.remove();
      decisionMapInstance = null;
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
    var shopIcon = window.L.divIcon({
      className: "gathering-shop-vote-map-marker-icon",
      html: '<span class="gathering-shop-vote-map-marker-visual"></span>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    });
    var shopMarker = window.L.marker(shopLatLng, { icon: shopIcon, keyboard: false });
    shopMarker.addTo(map);
    var shopMarkerEl = shopMarker.getElement();
    if (shopMarkerEl) {
      shopMarkerEl.setAttribute("data-testid", "gathering-participant-decision-map-marker");
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
        alt: "検索基点",
      });
      originMarker.addTo(map);
      var originEl = originMarker.getElement();
      if (originEl) {
        originEl.setAttribute("data-testid", "gathering-participant-decision-origin-marker");
        originEl.setAttribute("aria-label", "検索基点");
      }
    }
    // No line between the two markers and no walking-radius ring
    // (ADR-0056 decision 10): this product does not query a routing
    // service and does not assert a walking path it cannot back with real
    // routing data.
    decisionMapInstance = map;
  }

  function applyResult(sequence, result, onSuccess) {
    if (isStaleResponse(sequence)) {
      return;
    }
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
    var sequence = beginRequest();
    requestJson("GET", participantUrl()).then(function (result) {
      if (isStaleResponse(sequence)) {
        return;
      }
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
    var sequence = beginRequest();
    requestJson("PUT", participantUrl() + "/responses/" + candidateDateId, { status: status }).then(
      function (result) {
        applyResult(sequence, result);
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
    var sequence = beginRequest();
    requestJson("PUT", participantUrl() + "/shop-votes", { votes: votes }).then(function (result) {
      applyResult(sequence, result);
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
    var sequence = beginRequest();
    requestJson("PUT", participantUrl() + "/display-name", { displayName: displayName }).then(
      function (result) {
        applyResult(sequence, result, function () {
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
   * (date + answer badge + tally), with the response options kept present
   * (compact) so the answer stays changeable -- see this file's module
   * docstring for why that departs from the mockup's own drawing.
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
        "data-your-response": yourResponse,
        class: "gth-card gth-card--done",
      },
      children
    );
  }

  /**
   * The one currently-open question: Answer.dc.html's dashed-border .card
   * (question label, date, and the three full-size response options).
   * **The "この日に開いている店 N件" count is gone** (ADR-0055 decision 1,
   * 2026-09-12 human decision -- a shop count did not help a participant
   * decide on a candidate date; gathering-scheduling-api.yaml v0.12.0 no
   * longer sends ParticipantScheduleQuestion.openShopCount at all).
   */
  function renderOpenQuestionCard(question) {
    var children = [
      el("div", { class: "gth-open-label" }, ["この日、行けそう？"]),
      el("div", { class: "gth-open-date" }, [formatGatheringDateTime(question.startAt)]),
    ];
    var tally = renderTally(question);
    if (tally) {
      // peekResults.requiredOutcome (adr/0050 decision 1): this one open
      // question's own tally stays hidden until the participant explicitly
      // activates gathering-participant-peek-results (renderPeekResultsButton
      // below) -- see this file's own state.peekResultsActivated comment for
      // why only the open question's tally is gated this way. **No
      // explanatory mask text here** (FR-034, ADR-0055: the retired
      // "ほかの人の回答も見えています" prose is deleted, not replaced --
      // the tally simply appears once revealed).
      children.push(
        el(
          "div",
          {
            class:
              "gth-open-tally-wrap" +
              (state.peekResultsActivated ? " gth-open-tally-wrap--revealed" : ""),
          },
          [tally]
        )
      );
    }
    children.push(
      el(
        "div",
        { class: "gth-open-options" },
        responseOptionButtons(question, "UNANSWERED", false)
      )
    );
    return el(
      "div",
      {
        "data-testid": "gathering-schedule-question",
        "data-candidate-date-id": question.candidateDateId,
        "data-your-response": "UNANSWERED",
        class: "gth-card gth-card--open",
      },
      children
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
    // adr/0050 decision 2 (2026-09-08/09 human decision): tally is always
    // present now, regardless of whether this participant has voted on this
    // shop yet (reverses the original "answer first, then see others" rule,
    // TDR-GTH-29).
    if (!question.tally) {
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

  // 2026-09-13 addition (ADR-0056 decision 9, 第4束裁定): the vote bar's own
  // total length is fixed to the gathering's total active participant
  // count, not however many participants have voted on this particular
  // shop so far -- a thinly-supported shop is visible as a short filled
  // bar rather than a bar scaled to a shrinking, per-shop denominator.
  // Rendered-geometry only, no new required test id (this contract does
  // not fix this bar's markup any more than it fixes scheduleQuestion's
  // own progress-bar rendering elsewhere on this screen). Omitted entirely
  // when totalActiveParticipantCount is not yet present on the response
  // (this round's API work ships from a different developer in parallel).
  function renderShopVoteBar(question, totalActiveParticipantCount) {
    if (!question.tally || !totalActiveParticipantCount) {
      return null;
    }
    function segment(count, modifierClass) {
      var width = Math.max(0, Math.min(100, (count / totalActiveParticipantCount) * 100));
      return el(
        "span",
        { class: "gth-vote-bar-seg " + modifierClass, style: "width:" + width + "%" },
        []
      );
    }
    return el("div", { class: "gth-vote-bar" }, [
      segment(question.tally.wantToGoCount, "gth-vote-bar-seg--want"),
      segment(question.tally.okToGoCount, "gth-vote-bar-seg--ok"),
      segment(question.tally.notGoingCount, "gth-vote-bar-seg--not"),
    ]);
  }

  /**
   * @param showVoteOptions false once ParticipantView.decision is non-null
   *   (noOperations: no gathering-shop-vote-option once finalized) -- the
   *   map/detail fields/tally/bar are otherwise identical and remain
   *   present (ADR-0055 decision 8: this element is not one
   *   replacesQuestionSurfaces names).
   * @param totalActiveParticipantCount ParticipantView.
   *   totalActiveParticipantCount, threaded through for renderShopVoteBar.
   */
  function renderShopVoteQuestion(question, showVoteOptions, totalActiveParticipantCount) {
    var yourVoteValue = question.yourVote === null ? "UNANSWERED" : question.yourVote;
    var addedAfterVotingStarted = !!question.addedAfterVotingStarted;
    var detailRow = el(
      "div",
      { class: "gth-shop-detail-row" },
      renderShopVoteDetailFields(question)
    );
    // ADR-0056 decision 6, human ruling: "印は2つに分ける。札は『あとから
    // 入ったか』だけ、カードの縁は『自分が答えたか』だけ。1つの印に2つの
    // 意味を持たせない。" The badge below reads only
    // addedAfterVotingStarted; the card's own border highlight
    // (gth-vote-row--answered below) reads only whether this participant
    // has answered (data-your-vote !== "UNANSWERED") -- neither derives
    // from, or substitutes for, the other.
    var nameRow = el("div", { class: "gth-vote-name-row" }, [
      el("span", { class: "gth-vote-name" }, [question.name]),
      addedAfterVotingStarted
        ? el("span", { class: "gth-vote-added-badge" }, ["あとから入りました"])
        : null,
    ]);
    var children = [nameRow, detailRow];
    if (showVoteOptions) {
      children.push(el("div", { class: "gth-vote-options" }, voteOptionButtons(question)));
    }
    var tally = renderShopVoteTally(question);
    if (tally) {
      children.push(tally);
    }
    var bar = renderShopVoteBar(question, totalActiveParticipantCount);
    if (bar) {
      children.push(bar);
    }

    return el(
      "div",
      {
        "data-testid": "gathering-shop-vote-question",
        "data-shop-id": question.shopId,
        "data-your-vote": yourVoteValue,
        "data-added-after-voting-started": addedAfterVotingStarted ? "true" : "false",
        class: "gth-vote-row" + (yourVoteValue !== "UNANSWERED" ? " gth-vote-row--answered" : ""),
      },
      children
    );
  }

  /**
   * @param showVoteOptions see renderShopVoteQuestion above; threaded
   *   through unchanged. The heading text itself also varies -- "お店に
   *   投票してください" implies an action this finalized reuse (render()'s
   *   decision branch) must not suggest is still available.
   */
  function renderShopVoteSection(showVoteOptions) {
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
    var totalActiveParticipantCount = state.view.totalActiveParticipantCount;
    var heading = showVoteOptions ? "お店に投票してください" : "お店ごとの票";
    var node = el(
      "div",
      { class: "gth-vote-section" },
      [el("div", { class: "gth-vote-heading" }, [heading]), mapContainer].concat(
        state.view.shopVoteQuestions.map(function (question) {
          return renderShopVoteQuestion(question, showVoteOptions, totalActiveParticipantCount);
        })
      )
    );
    return {
      node: node,
      mapContainer: mapContainer,
      items: state.view.shopVoteQuestions,
      searchOrigin: state.view.searchOrigin,
    };
  }

  /**
   * Final.dc.html B-3 -- the decision (adr/0040, extended by P5/adr/0041,
   * simplified by adr/0050 decision 3, then simplified once more by
   * ADR-0055 decision 7, 2026-09-12: "あなたの回答は見れても別に意味ない
   * かも" applies equally to the one remaining schedule-response line, so
   * it too is deleted -- data-your-schedule-response no longer exists
   * anywhere on this element). ADR-0056 decision 10 fixes what replaces it:
   * exactly 5 things, in this order -- when, which shop, where (a map with
   * the decided shop's pin and this participant's search origin, no
   * connecting line, no walking-radius ring), the walking-time estimate,
   * and a link to the shop's own page. The live shop-vote tally below this
   * decision card is a *separate* element this function does not build
   * (ADR-0055 decision 8: render()'s decision branch reuses
   * renderShopVoteSection(false), unaffected by finalization).
   */
  function renderFinalizedView() {
    var decision = state.view.decision;

    var decisionMapContainer = el(
      "div",
      { "data-testid": "gathering-participant-decision-map", class: "gth-final-map" },
      []
    );

    var decisionEl = el(
      "div",
      {
        "data-testid": "gathering-participant-decision",
        "data-confirmed-candidate-date": decision.confirmedCandidateDate,
        "data-shop-id": decision.shop.shopId,
        "data-walking-time-minutes": decision.shop.walkingTimeMinutes,
        class: "gth-final",
      },
      [
        el("div", { class: "gth-final-badge" }, ["決まりました"]),
        el("div", { class: "gth-final-when-lb" }, ["いつ"]),
        el("div", { class: "gth-final-when" }, [
          formatGatheringDateTime(decision.confirmedCandidateDate),
        ]),
        el("div", { class: "gth-final-shop-lb" }, ["どの店"]),
        el("div", { class: "gth-final-shop" }, [decision.shop.name]),
        el("div", { class: "gth-final-where-lb" }, ["どこにあるか"]),
        decisionMapContainer,
        el("div", { class: "gth-final-walking" }, [
          "徒歩 約" + decision.shop.walkingTimeMinutes + "分",
        ]),
        el(
          "a",
          {
            "data-testid": "gathering-participant-decision-page-link",
            href: decision.shop.providerPageUrl,
            target: "_blank",
            rel: "noopener noreferrer",
            class: "gth-shop-link",
          },
          ["店のページを見る"]
        ),
      ]
    );

    var children = [decisionEl];
    // ADR-0055 decision 8 (2026-09-12 human ruling: "確定後も参加者は店
    // ごとの票を見られるままにする") -- the live shop-vote tally/map/bar
    // remain, only the three vote buttons themselves are suppressed
    // (showVoteOptions: false, noOperations below).
    var shopVoteSection = renderShopVoteSection(false);
    if (shopVoteSection) {
      children.push(shopVoteSection.node);
    }

    return {
      node: el("div", { class: "gth-body" }, children),
      decisionMap: {
        container: decisionMapContainer,
        shop: decision.shop,
        searchOrigin: state.view.searchOrigin,
      },
      shopVoteSection: shopVoteSection,
    };
  }

  /**
   * 結果をのぞく (peekResults). Placed at the very top of the scrollable
   * body by render() below -- never a DOM sibling of answerLater's own row
   * again (FR-034's own repro of the opposite arrangement).
   */
  function renderPeekResultsButton() {
    var button = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-peek-results",
        "data-gathering-control-purpose": "gathering-participant-peek-results",
        class: "gth-peek-btn",
      },
      ["結果をのぞく"]
    );
    button.addEventListener("click", function () {
      state.peekResultsActivated = true;
      render();
    });
    return button;
  }

  /**
   * あとで答える (answerLater). Placed as the very last element of the
   * scrollable body by render() below. Activating it opens
   * renderAnswerLaterOverlay below -- calls no public operation, since
   * every answer already saved itself the moment it was submitted.
   */
  function renderAnswerLaterButton() {
    var button = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-answer-later",
        "data-gathering-control-purpose": "gathering-participant-answer-later",
        class: "gth-answer-later-btn",
      },
      ["あとで答える"]
    );
    button.addEventListener("click", function () {
      state.answerLaterConfirmationOpen = true;
      render();
    });
    return button;
  }

  function closeAnswerLaterConfirmation() {
    state.answerLaterConfirmationOpen = false;
    render();
  }

  /**
   * gathering-participant-answer-later-confirmation (ADR-0055 decision 3,
   * FR-034, 2026-09-12 human ruling): reproduces this participant's own
   * already-recorded answers verbatim -- never a sentence asserting they
   * are saved. Rendered as a fixed-position scrim+panel overlapping the
   * rest of the screen (第2束裁定: "確認は重なる別の面"), not inserted into
   * any existing row. Dismissed by activating the scrim itself (a plain,
   * purposeless `<div>`, outside forbiddenFormControlCategories' scan --
   * no new allowedPurposes entry needed).
   */
  function renderAnswerLaterOverlay() {
    if (!state.answerLaterConfirmationOpen || !state.view || state.view.decision) {
      return null;
    }
    var rows = [];
    (state.view.scheduleQuestions || []).forEach(function (question) {
      if (question.yourResponse === null) {
        return;
      }
      rows.push(
        el(
          "div",
          {
            class: "gth-overlay-row",
            "data-candidate-date-id": question.candidateDateId,
            "data-your-response": question.yourResponse,
          },
          [
            el("span", {}, [formatGatheringDateTime(question.startAt)]),
            el("span", {}, [RESPONSE_LABELS[question.yourResponse]]),
          ]
        )
      );
    });
    (state.view.shopVoteQuestions || []).forEach(function (question) {
      if (question.yourVote === null) {
        return;
      }
      rows.push(
        el(
          "div",
          {
            class: "gth-overlay-row",
            "data-shop-id": question.shopId,
            "data-your-vote": question.yourVote,
          },
          [el("span", {}, [question.name]), el("span", {}, [VOTE_LABELS[question.yourVote]])]
        )
      );
    });
    if (rows.length === 0) {
      rows.push(el("div", { class: "gth-overlay-empty" }, ["まだ回答がありません"]));
    }
    var panel = el(
      "div",
      {
        "data-testid": "gathering-participant-answer-later-confirmation",
        class: "gth-overlay-panel",
      },
      rows
    );
    panel.addEventListener("click", function (event) {
      event.stopPropagation();
    });
    var overlay = el("div", { class: "gth-overlay" }, [panel]);
    overlay.addEventListener("click", closeAnswerLaterConfirmation);
    return overlay;
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
    var decisionMapPending = null;
    if (state.view) {
      if (state.view.decision) {
        // finalizedView (adr/0042): replaces scheduleQuestion/progress and
        // nameControl's open/submit entirely (replacesQuestionSurfaces/
        // noOperations) -- built from a dedicated branch rather than gating
        // each element individually. **gathering-shop-vote-question is not
        // one of the replaced surfaces** (ADR-0055 decision 8) --
        // renderFinalizedView's own returned shopVoteSection carries it
        // through unaffected by finalization.
        children.push(renderFinalizedHeader());
        var finalized = renderFinalizedView();
        children.push(finalized.node);
        decisionMapPending = finalized.decisionMap;
        if (finalized.shopVoteSection) {
          shopVoteMapPending = finalized.shopVoteSection;
        }
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
        // 結果をのぞく sits at the very top of the scrollable body (第2束
        // 裁定); あとで答える (pushed below) sits at the very bottom -- the
        // two are never DOM siblings in the same row (FR-034).
        body.push(renderPeekResultsButton());
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
        var shopVoteSection = renderShopVoteSection(true);
        if (shopVoteSection) {
          body.push(shopVoteSection.node);
          shopVoteMapPending = shopVoteSection;
        }
        var nextPanel = renderNextPanel(remainingCount, state.view.phase);
        if (nextPanel) {
          body.push(nextPanel);
        }
        body.push(renderAnswerLaterButton());
        children.push(el("main", { class: "gth-body" }, body));
        children.push(renderProgress(total, answered));
      }
    }
    if (state.errorCode) {
      children.push(renderError());
    }
    root.appendChild(el("div", { class: "gth-app" }, children));

    // The map containers above must already be attached to the live DOM
    // before Leaflet initializes them (see initializeShopVoteMap's own
    // module-docstring precedent, gathering.js's initializeOpenShopMap).
    if (shopVoteMapPending) {
      initializeShopVoteMap(
        shopVoteMapPending.mapContainer,
        shopVoteMapPending.items,
        shopVoteMapPending.searchOrigin
      );
    }
    if (decisionMapPending) {
      initializeDecisionMap(
        decisionMapPending.container,
        decisionMapPending.shop,
        decisionMapPending.searchOrigin
      );
    }

    // gathering-participant-answer-later-confirmation (ADR-0055 decision 3):
    // an overlapping surface appended as a sibling of .gth-app, not a
    // descendant pushed into any of its rows -- its own fixed positioning
    // (participant_answer.html's .gth-overlay) is what makes it "重なる
    // 別の面" rather than a layout participant.
    var answerLaterOverlay = renderAnswerLaterOverlay();
    if (answerLaterOverlay) {
      root.appendChild(answerLaterOverlay);
    }
  }

  loadView();
})();
