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
 * **Superseded 2026-09-13 (integration round, human decision, 第2束の板
 * `E:\AWS\dsg-out\party\b2-schedule\Answer.dc.html`: "候補日 4つ" -- 4枚の
 * カードを同時に描く, "4つのうち2つ答えたところ" caption)**: the paragraph
 * below (2026-08-31, the *original* Answer.dc.html draft) chose a
 * one-question-at-a-time wizard; the human has since ruled on a later,
 * revised board that shows every candidate date's card simultaneously
 * instead, and a decided design is followed even where this contract's own
 * scheduleQuestion.cardinality note only *permits*, but does not *require*,
 * progressive disclosure ("this contract does not fix whether every
 * CandidateDate renders simultaneously or progressively... it requires
 * only that whichever candidate dates are currently reachable in the DOM
 * each expose exactly one gathering-schedule-question... and that
 * gathering-participant-progress always reflects the true total regardless
 * of how many are currently rendered"). Every candidate date is now
 * "currently reachable" at once -- render() below no longer computes a
 * single firstUnansweredIndex to gate which cards exist; it builds one
 * card per entry in ParticipantView.scheduleQuestions (its own order,
 * unchanged), classifying each independently as done (yourResponse
 * non-null, Answer.dc.html's `.card.done`) or open (yourResponse null,
 * `.card` without the `done` modifier) using the same
 * renderDoneQuestionCard/renderOpenQuestionCard functions the original
 * wizard already defined -- neither function's own per-card shape changes,
 * only how many of each render() now builds. The "このあと聞かれること"
 * summary panel (renderNextPanel, folding not-yet-reachable dates into a
 * count) is retired along with it: nothing is folded away any longer, so a
 * panel describing what remains folded has nothing left to describe (the
 * revised board carries no such panel either). The original paragraph
 * below is left unedited beneath this note (P-06: a decision is replaced,
 * not rewritten) since its own reasoning about *why* a wizard was once
 * chosen remains historically accurate context for this file.
 *
 * Human decision 2026-08-31 (superseded above): matches the approved screen
 * skeleton (E:\AWS\dsg-out\party\Answer.dc.html, "B｜参加者の回答") as a
 * one-question-at-a-time wizard, not the developer's earlier discretionary
 * choice of rendering every candidate date simultaneously. Per this
 * contract's own scheduleQuestion.cardinality note ("This contract does not
 * fix whether every CandidateDate renders simultaneously or
 * progressively... It requires only that whichever candidate dates are
 * currently reachable in the DOM each expose exactly one
 * gathering-schedule-question... and that gathering-participant-progress
 * always reflects the true total regardless of how many are currently
 * rendered"), progressive disclosure is contract-conformant. "Currently
 * reachable" here means every candidate date already answered (rendered as
 * a compact "done" card, matching Answer.dc.html's .card.done) plus the
 * first still-unanswered one (rendered as the full interactive "open"
 * card) -- candidate dates beyond that are folded into the "このあと聞かれ
 * ること" summary panel and are not built as DOM nodes at all.
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
 *
 * **2026-09-17 revision (ADR-0061, human decision, 実機フィードバック第2便・
 * 束C「参加者を呼ぶ・答える」), overturning three of the entries directly
 * above**:
 * - **scheduleQuestion.cardinality is now a Must, not merely an allowance**
 *   (decision 3): exactly one gathering-schedule-question is reachable in
 *   the DOM at a time -- the 2026-09-13 entry above's "every candidate date
 *   renders simultaneously" design is retired. state.currentCandidateDateId
 *   tracks which one; ensureCurrentCandidateDateId resolves a default
 *   (first not-yet-answered, or the last candidate date once every one is
 *   answered) only when this id is null or no longer present -- explicit
 *   navigation (daySkip/dayPrevious/dayList's own item, or
 *   answerScheduleQuestion's own auto-advance below) is never overridden by
 *   a later render(). renderDoneQuestionCard/renderOpenQuestionCard's own
 *   done-vs-open split is retired along with it -- only one function,
 *   renderCurrentQuestionCard, builds the one currently-reachable date now,
 *   response options always present and always-changeable regardless of
 *   whether it is already answered (the same TDR-GTH-06 reasoning the
 *   retired split already rested on).
 * - **answerLater/peekResults (結果をのぞく／あとで答える) and their
 *   confirmation surfaces are deleted entirely**, not merely re-scoped
 *   (decision 3, overturning adr/0050 decision 1 and adr/0055 decision 3):
 *   every answer already saves itself the moment it is submitted, so
 *   leaving mid-way at any candidate date is always safe without a
 *   dedicated control; every other participant's tally is already
 *   unconditionally visible (adr/0050 decision 2), so there is nothing left
 *   to "peek" at either. dayList (new, board's 「日の一覧」) now carries the
 *   "自分の答えの一覧" role answerLater's confirmation used to -- once every
 *   candidate date has a non-null yourResponse, this same list doubles as
 *   the "12件すべて答えました" completion state, no separate element.
 * - **respondentList is new** (decision 2, human decision: 束C レイアウト案
 *   F2「空いた所にだれが何と答えたかを名前つきで並べる」): each candidate
 *   date's own card now shows every respondent's self-reported name (or
 *   "名無し") alongside their answer, sourced from
 *   ParticipantScheduleQuestion.respondents (gathering-scheduling-api.yaml
 *   v0.17.0) -- the participant-to-participant mirror of what the organizer
 *   dashboard's own responseTable already shows (ADR-0056 decision 1). This
 *   widens the peer-to-peer visibility boundary adr/0050 decision 2 opened
 *   for aggregate counts to per-participant identity for the first time.
 * - **The live shop-vote tally no longer remains visible after
 *   finalization** (decision 5, reversing ADR-0055 decision 8 a second
 *   time, human decision: 「他の候補の店と票は出さない」): renderFinalizedView
 *   no longer calls renderShopVoteSection at all -- gathering-shop-vote-
 *   question/-tally/-map are all absent once ParticipantView.decision is
 *   non-null, restoring TDR-GTH-34's own "他の参加者の回答や投票、店ごとの
 *   回答の一覧は示されない" as a literal DOM absence again, not merely a
 *   suppressed set of buttons.
 *
 * **2026-09-18 coordinator report -- two corrections to the round directly
 * above**:
 * - **dayList's own presentation now matches the approved board exactly**
 *   (P-08/ADR-0013: an approved board fixes a screen's shape even where the
 *   contract's own prose leaves it open) -- the 2026-09-17 entry's own
 *   "rendered as a horizontally scrollable strip... without a separate
 *   open/close toggle" design is retired. renderDayListPanel (wide,
 *   c2r/D1-PcDay: a persistent left sidebar) and renderDayListSheet (narrow,
 *   c2/C2-a-SpDay's top-right 「日の一覧」button + c2/C2-a-SpList・c2r/D1-
 *   SpList's bottom sheet) now build the exact two board shapes, chosen
 *   once per render by matchMedia (isWideDayListLayout, the same "no live-
 *   resize switch" precedent candidate.js's isTwoColumnLayout already
 *   established) -- never both at once, so gathering-participant-day-list/
 *   -item's own cardinality never doubles. Both shapes share one row
 *   renderer (renderDayListRow) drawing the board's own 3 columns (「日｜
 *   ○△×の数｜あなた」), a leader badge, and the left-edge line, computed
 *   from the same leaders map computeScheduleQuestionLeaders already
 *   provides render() (no API change). The sheet keeps
 *   gathering-participant-day-list attached to the DOM regardless of
 *   whether it is visually open (dayList.presenceRule: "Present exactly
 *   when ParticipantView.decision is null" -- not "present exactly when
 *   the sheet is open") -- only a wrapping modifier class governs visual
 *   state. Opening moves focus into the sheet; Esc closes it and returns
 *   focus to the toggle button; Tab cycles within it while open (identical
 *   keyboard shape to gathering.js's own issue dialog, ADR-0061 decision
 *   1's precedent).
 * - **respondents' own order no longer depends on the database's
 *   unspecified default row order**: services.schedule_response_respondents
 *   now explicitly orders by the answering participant link's own
 *   issued_at/id (adr/0048's 発行順 basis) -- a Python-side fix, this file
 *   itself only ever displays whatever order the response already carries.
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
    // ADR-0061 decision 3 (2026-09-17, human decision: 「1日ずつ、答えると
    // 自動で次の日へ」): the one candidate date currently reachable in the
    // DOM (scheduleQuestion.cardinality's own Must -- exactly one
    // gathering-schedule-question at a time). null until ensureCurrent
    // CandidateDateId below resolves a default on the first successful
    // load; thereafter only daySkip/dayPrevious/dayList's own navigation or
    // responseOptions' own auto-advance ever change it -- render() itself
    // never silently overrides an explicit navigation, only fills in a
    // default when this id is null or no longer present among
    // ParticipantView.scheduleQuestions (e.g. a stale value from a
    // gathering whose candidate dates changed).
    currentCandidateDateId: null,
    // **2026-09-18 coordinator report**: dayList's own presentation must
    // match the approved board exactly (P-08/ADR-0013: an approved board
    // fixes the screen's shape even where the contract's own prose leaves
    // it open) -- c2r/D1-PcDay (wide: a persistent left panel, no open/
    // close) and c2/C2-a-SpDay + C2-a-SpList / c2r/D1-SpList (narrow: a
    // 「日の一覧」button, top right of the header, opens a bottom sheet).
    // Only meaningful in the narrow shape (renderDayListSheet below) --
    // always false in the wide shape, which never toggles.
    dayListSheetOpen: false,
    // Explicit open/close focus management for the sheet above -- distinct
    // from the generic restoreFocusFromDescriptor below, which can only
    // restore focus to an element that still exists after a rebuild (same
    // shape as gathering.js's own pendingIssueDialogFocus, ADR-0061
    // decision 1).
    pendingDayListSheetFocus: null,
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

    // browserControlSurface.participantAnswer.finalizedView.decision.map's
    // data-overlay-marker-count/-line-count/-ring-count (spec .spec/11-a,
    // closing 独立監査 audit-gathering-redesign-steps.md's Major 1). A
    // 2026-09-13 defect injection found that a running tally kept by this
    // module's own add-helpers (incremented only when *this* code called
    // them) can be bypassed by any code path that instead calls
    // `L.polyline(...).addTo(map)` / `L.circle(...).addTo(map)` /
    // `L.marker(...).addTo(map)` directly: the injected line/ring/marker
    // rendered on the map but the counter stayed at 0, so the check
    // stopped observing anything it claimed to observe. Reading counts
    // off `map.eachLayer` instead -- Leaflet's own public API for listing
    // every layer actually registered on the map -- counts whatever is
    // really drawn, independent of how it got there, and does not touch
    // the map library's internal DOM (this contract's scope forbids
    // coupling to that; `eachLayer` is API, not DOM).
    //
    // Classification below is `instanceof` against Leaflet's own exported
    // constructors, checked against this vendored leaflet.js's actual
    // extend() chain before writing this code (do not assume Leaflet's
    // class hierarchy):
    //   L.Layer
    //     L.Marker                      -- counted as "marker"
    //     L.Path
    //       L.CircleMarker              -- counted as "ring"
    //         L.Circle                  -- counted as "ring" (is-a
    //                                      CircleMarker)
    //       L.Polyline                  -- counted as "line"
    //         L.Polygon                 -- counted as "line" (is-a
    //                                      Polyline; still path segments
    //                                      drawn on the map, and this map
    //                                      must draw none, so a polygon
    //                                      must not slip through
    //                                      uncounted either)
    //     L.GridLayer
    //       L.TileLayer                 -- neither Marker nor Path;
    //                                      never counted (the base map
    //                                      tile layer added above is
    //                                      correctly excluded)
    // (L.Circle is a L.CircleMarker but never a L.Polyline -- the two
    // branches under L.Path are disjoint -- so "line" and "ring" never
    // double-count the same layer.)
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
    // Recount on every future add/remove, not just once below -- if this
    // map ever becomes mutable after first render, the attributes must
    // not go stale. Leaflet fires both events on `map` for any
    // addTo()/removeLayer() call, regardless of which code performs it.
    map.on("layeradd layerremove", refreshOverlayCountAttributes);

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
    // service and does not assert a walking path it cannot back with
    // real routing data.
    refreshOverlayCountAttributes();
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
        // responseOptions.requiredOutcome (ADR-0061 decision 3, human
        // decision: 「答えると自動で次の日へ」): if a next candidate date
        // exists in ParticipantScheduleQuestion order after this one, that
        // date becomes the currently reachable one immediately after this
        // call succeeds. Computed from the *response body's* own order
        // (scheduleQuestion.orderingInvariant, startAt ascending) --
        // decided before applyResult below overwrites state.view, but
        // applied to state.currentCandidateDateId directly so a late,
        // stale response (isStaleResponse below) never moves the
        // participant off whichever candidate date they have since
        // navigated to themselves.
        if (result.status === 200 && !isStaleResponse(sequence)) {
          var order = result.body.scheduleQuestions;
          var answeredIndex = order.findIndex(function (question) {
            return question.candidateDateId === candidateDateId;
          });
          if (answeredIndex !== -1 && answeredIndex + 1 < order.length) {
            state.currentCandidateDateId = order[answeredIndex + 1].candidateDateId;
          }
        }
        applyResult(sequence, result);
      }
    );
  }

  // daySkip ("とばす", ADR-0061 decision 3): moves to the next candidate
  // date in order without answering the current one. Calls no public
  // operation.
  function skipScheduleQuestion() {
    var order = (state.view && state.view.scheduleQuestions) || [];
    var currentIndex = order.findIndex(function (question) {
      return question.candidateDateId === state.currentCandidateDateId;
    });
    if (currentIndex !== -1 && currentIndex + 1 < order.length) {
      state.currentCandidateDateId = order[currentIndex + 1].candidateDateId;
    }
    render();
  }

  // dayPrevious ("前の日", ADR-0061 decision 3): moves to the immediately
  // preceding candidate date in order. Calls no public operation. Disabled
  // (see renderDayNav below) whenever the current candidate date is
  // already the first in order.
  function goToPreviousScheduleQuestion() {
    var order = (state.view && state.view.scheduleQuestions) || [];
    var currentIndex = order.findIndex(function (question) {
      return question.candidateDateId === state.currentCandidateDateId;
    });
    if (currentIndex > 0) {
      state.currentCandidateDateId = order[currentIndex - 1].candidateDateId;
    }
    render();
  }

  // dayList's own item ("日の一覧", ADR-0061 decision 3): jumps directly to
  // the candidate date whose data-candidate-date-id is candidateDateId.
  // Calls no public operation, does not change any data-your-response
  // value.
  function navigateToScheduleQuestion(candidateDateId) {
    state.currentCandidateDateId = candidateDateId;
    // Selecting a day from the narrow-layout sheet closes it (a presentation
    // choice, board's own C2-a-SpList: pressing a row goes to that day) --
    // a no-op in the wide layout, which never opens a sheet at all.
    if (state.dayListSheetOpen) {
      state.dayListSheetOpen = false;
      state.pendingDayListSheetFocus = "close";
    }
    render();
  }

  // 「日の一覧」(narrow layout only, board's C2-a-SpDay/c2r/D1-SpList): opens
  // the bottom sheet. Calls no public operation.
  function openDayListSheet() {
    state.dayListSheetOpen = true;
    state.pendingDayListSheetFocus = "open";
    render();
  }

  // The sheet's own 「閉じる」/「×」 or Esc: calls no public operation, does
  // not change any data-your-response value or state.currentCandidateDateId.
  function closeDayListSheet() {
    state.dayListSheetOpen = false;
    state.pendingDayListSheetFocus = "close";
    render();
  }

  // Minimal Tab-cycling focus trap while the narrow-layout day-list sheet is
  // open -- identical shape to gathering.js's own trapTabWithinDialog (no
  // shared module system exists in this codebase).
  function trapTabWithinDayListSheet(event, sheet) {
    var focusable = Array.prototype.slice.call(
      sheet.querySelectorAll("button:not([disabled]), [tabindex]:not([tabindex='-1'])")
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

  // Resolves state.currentCandidateDateId to a concrete, currently-present
  // candidate date -- called once per render() (idempotent: only changes
  // anything when the tracked id is null or no longer present among
  // scheduleQuestions). Defaults to the first not-yet-answered candidate
  // date (this contract's own cardinality note does not fix this initial
  // choice; the retired wizard's own firstUnansweredIndex precedent, this
  // file's module docstring history, is reused here), falling back to the
  // last candidate date in order once every date already has an answer.
  function ensureCurrentCandidateDateId(scheduleQuestions) {
    if (state.currentCandidateDateId !== null) {
      var stillPresent = scheduleQuestions.some(function (question) {
        return question.candidateDateId === state.currentCandidateDateId;
      });
      if (stillPresent) {
        return;
      }
    }
    var firstUnanswered = scheduleQuestions.filter(function (question) {
      return question.yourResponse === null;
    })[0];
    if (firstUnanswered) {
      state.currentCandidateDateId = firstUnanswered.candidateDateId;
    } else if (scheduleQuestions.length > 0) {
      state.currentCandidateDateId = scheduleQuestions[scheduleQuestions.length - 1].candidateDateId;
    } else {
      state.currentCandidateDateId = null;
    }
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

  /**
   * @param dayListToggle the narrow-layout 「日の一覧」button (board's C2-a-
   *   SpDay: top right of the header, opens the bottom sheet) -- `null` in
   *   the wide layout, which shows the day list as a persistent side panel
   *   instead and never needs a toggle (renderDayListPanel/renderDayList
   *   Sheet below, chosen once per render by isWideDayListLayout).
   */
  function renderHeader(answered, total, dayListToggle) {
    var countAndToggle = [el("div", { class: "gth-count" }, ["日程 " + answered + " / " + total])];
    if (dayListToggle) {
      countAndToggle.push(dayListToggle);
    }
    var titleRow = el("div", { class: "gth-hd-row" }, [
      el("div", { class: "gth-title" }, [state.view.gatheringTitle]),
      el("div", { class: "gth-hd-row-end" }, countAndToggle),
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

  // --- current-leader-cascade BEGIN (identical shape copy in gathering.js's
  // own computeCandidateDateLeaders; keep both in sync) ---
  // ADR-0060 decision 8 (2026-09-16, human decision: 参加者の画面にも有力の
  // 印を出す): the exact same two-level cascade
  // (candidateDateList.candidateDate's own data-current-leader,
  // gathering.js's computeCandidateDateLeaders) computed here from this
  // participant's own ParticipantView.scheduleQuestions array, which already
  // carries every candidate date's goingCount/maybeCount/notGoingCount --
  // no API change needed (mirrors data-added-after-voting-started's own
  // organizer/participant mirroring precedent, ADR-0056 decision 6).
  function computeScheduleQuestionLeaders(scheduleQuestions) {
    var responded = scheduleQuestions.filter(function (question) {
      var tally = question.tally;
      return tally.goingCount + tally.maybeCount + tally.notGoingCount > 0;
    });
    if (responded.length === 0) {
      return {};
    }
    var maxGoing = responded.reduce(function (max, question) {
      return question.tally.goingCount > max ? question.tally.goingCount : max;
    }, -Infinity);
    var tiedOnGoing = responded.filter(function (question) {
      return question.tally.goingCount === maxGoing;
    });
    var maxMaybe = tiedOnGoing.reduce(function (max, question) {
      return question.tally.maybeCount > max ? question.tally.maybeCount : max;
    }, -Infinity);
    var leaders = {};
    tiedOnGoing.forEach(function (question) {
      if (question.tally.maybeCount === maxMaybe) {
        leaders[question.candidateDateId] = true;
      }
    });
    return leaders;
  }
  // --- current-leader-cascade END ---

  function renderTally(question, leaders) {
    if (!question.tally) {
      return null;
    }
    var isLeader = Boolean(leaders && leaders[question.candidateDateId]);
    return el(
      "div",
      {
        "data-testid": "gathering-schedule-tally",
        "data-going-count": question.tally.goingCount,
        "data-maybe-count": question.tally.maybeCount,
        "data-not-going-count": question.tally.notGoingCount,
        "data-current-leader": isLeader ? "true" : "false",
        class: "gth-tally" + (isLeader ? " gth-tally--leader" : ""),
      },
      [
        el("span", {}, ["行ける ", el("b", {}, [String(question.tally.goingCount)])]),
        el("span", {}, ["たぶん ", el("b", {}, [String(question.tally.maybeCount)])]),
        el("span", {}, ["むり ", el("b", {}, [String(question.tally.notGoingCount)])]),
      ]
    );
  }

  /**
   * respondentList (ADR-0061 decision 2, testId
   * gathering-schedule-respondent-list/-item): one item per entry in this
   * candidate date's own respondents array -- a participant link that has
   * answered this date, including this viewer's own entry if this viewer
   * has answered. Always rendered (possibly with zero items), the same
   * "container always present, item cardinality zero-or-more" shape
   * gathering-participant-link-list already establishes. Display-only --
   * no purpose, no allowedPurposes entry (this contract's own
   * confirmationEchoNote precedent).
   */
  function renderRespondentList(question) {
    var items = (question.respondents || []).map(function (respondent) {
      var named = respondent.displayName !== null;
      return el(
        "div",
        {
          "data-testid": "gathering-schedule-respondent-item",
          "data-response-value": respondent.response,
          "data-participant-named": named ? "true" : "false",
          class: "gth-respondent-item",
        },
        [
          el("span", { class: "gth-respondent-response" }, [RESPONSE_LABELS[respondent.response]]),
          el("span", { class: "gth-respondent-name" }, [named ? respondent.displayName : "名無し"]),
        ]
      );
    });
    return el(
      "div",
      { "data-testid": "gathering-schedule-respondent-list", class: "gth-respondent-list" },
      items
    );
  }

  /**
   * The one currently-reachable candidate date (ADR-0061 decision 3:
   * scheduleQuestion.cardinality now requires exactly one at a time).
   * Response options stay present and always-changeable regardless of
   * whether this date is already answered (TDR-GTH-06's "answer is always
   * changeable" promise, this file's long-standing reasoning for keeping
   * these buttons present on an answered date -- see this file's module
   * docstring history). Below the tally (adr/0050 decision 2: always
   * visible, no "のぞく" gating any longer -- peekResults is retired,
   * decision 3) sits respondentList, the peer-facing name+answer pairs
   * decision 2 adds. **The "この日に開いている店 N件" count stays gone**
   * (ADR-0055 decision 1).
   */
  function renderCurrentQuestionCard(question, leaders) {
    var yourResponse = question.yourResponse;
    var children = [
      el("div", { class: "gth-open-label" }, ["この日、行けそう？"]),
      el("div", { class: "gth-open-date" }, [formatGatheringDateTime(question.startAt)]),
    ];
    if (yourResponse !== null) {
      // Non-binding confirmation text (this contract fixes no wording here,
      // the same "N件" latitude ADR-0060 decision 9 already takes) --
      // board's own "◯/◯は「行ける」にしました" note.
      children.push(
        el("div", { class: "gth-open-confirmed" }, [
          "この日は「" + RESPONSE_LABELS[yourResponse] + "」にしました",
        ])
      );
    }
    var tally = renderTally(question, leaders);
    if (tally) {
      children.push(tally);
    }
    children.push(renderRespondentList(question));
    children.push(
      el(
        "div",
        { class: "gth-open-options" },
        responseOptionButtons(question, yourResponse === null ? "UNANSWERED" : yourResponse, false)
      )
    );
    return el(
      "div",
      {
        "data-testid": "gathering-schedule-question",
        "data-candidate-date-id": question.candidateDateId,
        "data-your-response": yourResponse === null ? "UNANSWERED" : yourResponse,
        class: "gth-card gth-card--open",
      },
      children
    );
  }

  /**
   * daySkip/dayPrevious (ADR-0061 decision 3, board's 「とばす」/「前の日」,
   * bottom right/left). Neither calls a public operation.
   */
  function renderDayNav(order, currentIndex) {
    var previousButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-answer-previous",
        "data-gathering-control-purpose": "gathering-participant-answer-previous",
        disabled: currentIndex <= 0,
        class: "gth-daynav-btn",
      },
      ["‹ 前の日"]
    );
    previousButton.addEventListener("click", goToPreviousScheduleQuestion);
    var skipButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-answer-skip",
        "data-gathering-control-purpose": "gathering-participant-answer-skip",
        class: "gth-daynav-btn",
      },
      ["とばす ›"]
    );
    skipButton.addEventListener("click", skipScheduleQuestion);
    return el("div", { class: "gth-daynav-row" }, [previousButton, skipButton]);
  }

  // isWideDayListLayout is read once per render (identical convention to
  // candidate.js's own isTwoColumnLayout: window.matchMedia read once at
  // render time, no live-resize mode switch -- adr/0032 decision 3's own
  // precedent, reused here since this codebase has already settled that
  // question). 64rem is the same boundary candidate.js/gathering.js's own
  // primary-nav render-mode split already uses (developer discretion, not
  // fixed by any contract).
  var DAY_LIST_WIDE_LAYOUT_QUERY = "(min-width: 64rem)";

  function dayListHeading(total, answered) {
    // Once every candidate date has a non-null data-your-response, this
    // same heading carries the "12件すべて答えました" completion role the
    // retired answerLater confirmation used to (this contract requires no
    // separate completion element -- see this file's module docstring
    // history).
    return total > 0 && answered === total ? total + "件すべて答えました" : "日の一覧";
  }

  /**
   * dayList (ADR-0061 decision 3, board's 「日｜○△×の数｜あなた」 three-
   * column row, c2r/D1-PcDay・D1-SpList): one gathering-participant-day-item
   * per candidate date, shared verbatim by both layout shapes below (the
   * only difference between them is the shell each row sits inside, not
   * the row itself) -- the current day highlighted, a leading candidate
   * date's own leader badge and left-edge line (mirrors gathering.js's
   * gathering-candidate-date/data-current-leader precedent, computed here
   * from the same scheduleQuestions array, no API change).
   */
  function renderDayListRow(question, leaders) {
    var isCurrent = question.candidateDateId === state.currentCandidateDateId;
    var isLeader = Boolean(leaders && leaders[question.candidateDateId]);
    var yourResponse = question.yourResponse === null ? "UNANSWERED" : question.yourResponse;
    var dateChildren = [];
    if (isLeader) {
      dateChildren.push(el("span", { class: "gth-day-leader-badge" }, ["有力"]));
    }
    dateChildren.push(formatGatheringDateTime(question.startAt));
    var row = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-day-item",
        "data-gathering-control-purpose": "gathering-participant-day-navigate",
        "data-candidate-date-id": question.candidateDateId,
        "data-your-response": yourResponse,
        "data-current-leader": isLeader ? "true" : "false",
        class:
          "gth-day-row" +
          (isCurrent ? " gth-day-row--current" : "") +
          (isLeader ? " gth-day-row--leader" : ""),
      },
      [
        el("span", { class: "gth-day-col gth-day-col-date" }, dateChildren),
        el("span", { class: "gth-day-col gth-day-col-counts" }, [
          "○" +
            question.tally.goingCount +
            " △" +
            question.tally.maybeCount +
            " ×" +
            question.tally.notGoingCount,
        ]),
        el("span", { class: "gth-day-col gth-day-col-you" }, [
          question.yourResponse === null ? "未回答" : RESPONSE_LABELS[question.yourResponse],
        ]),
      ]
    );
    row.addEventListener("click", function () {
      navigateToScheduleQuestion(question.candidateDateId);
    });
    return row;
  }

  // The shared 3-column header labels ("日｜○△×の数｜あなた") both shapes
  // below show above their own row list -- board's own column heading, not
  // fixed by this contract (no test id, purely descriptive).
  function renderDayListColumnLabels() {
    return el("div", { class: "gth-day-panel-header" }, [
      el("span", {}, ["日"]),
      el("span", {}, ["○△×の数"]),
      el("span", {}, ["あなた"]),
    ]);
  }

  /**
   * Wide layout (board's c2r/D1-PcDay): a persistent left panel, no open/
   * close affordance at all -- gathering-participant-day-list is simply
   * always on screen alongside the current question card.
   */
  function renderDayListPanel(order, leaders, heading) {
    var list = el(
      "div",
      { "data-testid": "gathering-participant-day-list", class: "gth-day-list" },
      order.map(function (question) {
        return renderDayListRow(question, leaders);
      })
    );
    return el("aside", { class: "gth-day-panel" }, [
      el("div", { class: "gth-day-panel-heading" }, [heading]),
      renderDayListColumnLabels(),
      list,
    ]);
  }

  /**
   * Narrow layout (board's c2/C2-a-SpDay top-right 「日の一覧」button +
   * c2/C2-a-SpList・c2r/D1-SpList bottom sheet): gathering-participant-day-
   * list stays attached to the DOM at all times (dayList.presenceRule:
   * "Present exactly when ParticipantView.decision is null" -- unaffected
   * by whether the sheet is visually open), only the sheet's own open
   * modifier class (participant_answer.html's .gth-day-sheet--open) governs
   * whether it is actually visible/interactable; toggling it never removes
   * or rebuilds the list itself, only this wrapping shell.
   *
   * @returns {toggleButton, sheet} -- the caller places toggleButton in the
   *   header (top right) and sheet as a sibling of .gth-app.
   */
  function renderDayListSheet(order, leaders, heading) {
    var list = el(
      "div",
      { "data-testid": "gathering-participant-day-list", class: "gth-day-list" },
      order.map(function (question) {
        return renderDayListRow(question, leaders);
      })
    );
    // Neither test id below is fixed by the contract (dayList's own
    // description: "this contract fixes neither presentation, only the
    // elements below") -- added so ADR-0020 decision 4(c)/(e)'s keyboard-
    // reachability/44px gates can actually name and measure this entry
    // point, closing the same class of gap friction-log.md FR-035 named
    // for the retired footer's own controls (a real control with no
    // data-testid/data-gathering-control-purpose at all is invisible to
    // both gates, not merely excluded from them).
    var toggleButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-day-list-open",
        "data-gathering-control-purpose": "gathering-participant-day-list-open",
        class: "gth-day-sheet-open-btn",
      },
      ["日の一覧"]
    );
    toggleButton.addEventListener("click", openDayListSheet);

    var closeButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-day-list-close",
        "data-gathering-control-purpose": "gathering-participant-day-list-close",
        class: "gth-day-sheet-close",
        "aria-label": "閉じる",
      },
      ["×"]
    );
    closeButton.addEventListener("click", closeDayListSheet);

    var sheet = el(
      "div",
      {
        role: "dialog",
        "aria-modal": "true",
        "aria-label": "日の一覧",
        tabindex: "-1",
        class: "gth-day-sheet" + (state.dayListSheetOpen ? " gth-day-sheet--open" : ""),
      },
      [
        el("div", { class: "gth-day-sheet-head" }, [
          el("span", { class: "gth-day-sheet-title" }, [heading]),
          closeButton,
        ]),
        renderDayListColumnLabels(),
        list,
      ]
    );
    // シートは開いたらフォーカスを中へ、Esc で閉じてボタンへ戻す (identical
    // keyboard shape to gathering.js's own issue dialog, ADR-0061 decision
    // 1's own precedent): Esc closes; Tab/Shift+Tab cycle within the sheet
    // only while it is open.
    sheet.addEventListener("keydown", function (event) {
      if (!state.dayListSheetOpen) {
        return;
      }
      if (event.key === "Escape" || event.key === "Esc") {
        event.preventDefault();
        closeDayListSheet();
        return;
      }
      if (event.key === "Tab") {
        trapTabWithinDayListSheet(event, sheet);
      }
    });
    var scrim = el("div", { class: "gth-day-sheet-scrim" }, []);
    scrim.addEventListener("click", closeDayListSheet);
    var wrap = el(
      "div",
      { class: "gth-day-sheet-wrap" + (state.dayListSheetOpen ? " gth-day-sheet-wrap--open" : "") },
      [scrim, sheet]
    );
    return { toggleButton: toggleButton, sheet: wrap };
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

  /**
   * @param totalActiveParticipantCount ParticipantView.
   *   totalActiveParticipantCount (contract addendum 12, ADR-0056 decision
   *   9). **Fixed 2026-09-13 (integration round)**: this attribute existed
   *   on renderShopVoteBar's own sizing calculation already but had never
   *   been added to this tally element itself -- the contract requires it
   *   here (gathering-shop-vote-tally.data-total-active-participant-count),
   *   not merely somewhere on the page. The field is required (non-nullable)
   *   on ParticipantView as of gathering-scheduling-api.yaml v0.12.0, so
   *   this is never omitted the way renderShopVoteBar's own now-stale
   *   "may not exist yet" comment once allowed for.
   */
  function renderShopVoteTally(question, totalActiveParticipantCount) {
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
        "data-total-active-participant-count": totalActiveParticipantCount,
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
    var tally = renderShopVoteTally(question, totalActiveParticipantCount);
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
   * and a link to the shop's own page. **Changed back 2026-09-17 (ADR-0061
   * decision 5, human decision: 「他の候補の店と票は出さない」, reversing
   * ADR-0055 decision 8 a second time)**: this function no longer builds
   * the live shop-vote section at all -- gathering-shop-vote-question/
   * -tally/-map are all absent once finalized (replacesQuestionSurfaces),
   * so a finalized participant screen shows only this decision card, never
   * any other shop's information.
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

    return {
      node: el("div", { class: "gth-body" }, [decisionEl]),
      decisionMap: {
        container: decisionMapContainer,
        shop: decision.shop,
        searchOrigin: state.view.searchOrigin,
      },
    };
  }

  // renderPeekResultsButton/renderAnswerLaterButton/
  // closeAnswerLaterConfirmation/renderAnswerLaterOverlay ("結果をのぞく"/
  // "あとで答える" and their confirmation surface) are retired entirely
  // 2026-09-17 (ADR-0061 decision 3, human decision: overturning adr/0050
  // decision 1 and adr/0055 decision 3) -- see this file's module docstring
  // for why both are no longer needed: every answer already saves itself
  // the moment it is submitted (so leaving mid-way is always safe), and
  // every other participant's tally/respondentList is already unconditionally
  // visible (adr/0050 decision 2), so there is nothing left to "peek" at.
  // dayList (renderDayList above) now carries the "自分の答えの一覧" role
  // answerLater's confirmation used to.

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

  // --- focus-restore-across-rerender BEGIN (identical copy in
  // gathering.js/gathering_create.js; keep all three in sync) ---
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
    root.innerHTML = "";
    if (state.loadFailure) {
      // unexpectedLoadFailureOutcome's own absent list (adr/0047): every
      // other participant-facing element -- header, schedule question,
      // name-open, linkError, shop-vote question, decision -- stays
      // absent, mirroring the finalizedView branch's own dedicated-
      // branch style below rather than gating each element individually.
      root.appendChild(el("div", { class: "gth-app" }, [renderLoadFailure()]));
      restoreFocusFromDescriptor(root, focusDescriptor);
      return;
    }
    var children = [];
    var shopVoteMapPending = null;
    var decisionMapPending = null;
    // dayList's own two board-fixed shapes (2026-09-18 coordinator report):
    // dayListSidebarPending (wide, c2r/D1-PcDay) sits beside .gth-app;
    // dayListSheetPending (narrow, c2/C2-a-SpDay+SpList) sits as a sibling
    // after it. Exactly one of the two is ever set (isWideDayListLayout
    // below chooses once per render, never both) -- see renderDayListPanel/
    // renderDayListSheet's own docstrings for why each shape's own
    // dayList/day-item cardinality stays exactly one set regardless.
    var dayListSidebarPending = null;
    var dayListSheetPending = null;
    if (state.view) {
      if (state.view.decision) {
        // finalizedView (adr/0042): replaces scheduleQuestion/progress/
        // dayList and nameControl's open/submit entirely
        // (replacesQuestionSurfaces/noOperations) -- built from a dedicated
        // branch rather than gating each element individually.
        // **gathering-shop-vote-question/-tally/-map are also replaced**
        // (ADR-0061 decision 5, reversing ADR-0055 decision 8 a second
        // time) -- renderFinalizedView no longer returns a shopVoteSection
        // at all. Tear down any shop-vote Leaflet instance a prior render
        // (while decision was still null and voting had started) left
        // behind -- its own container is gone from the DOM once
        // root.innerHTML is cleared above, but the Leaflet instance itself
        // would otherwise linger, the same "destroy-before-recreate"
        // discipline initializeShopVoteMap/initializeDecisionMap already
        // apply to themselves.
        if (shopVoteMapInstance) {
          shopVoteMapInstance.remove();
          shopVoteMapInstance = null;
        }
        children.push(renderFinalizedHeader());
        var finalized = renderFinalizedView();
        children.push(finalized.node);
        decisionMapPending = finalized.decisionMap;
      } else {
        // ADR-0061 decision 3 (2026-09-17, human decision: 「1日ずつ、答える
        // と自動で次の日へ」): **supersedes the 2026-09-13 simultaneous-
        // render design this comment used to describe** --
        // scheduleQuestion.cardinality is now a Must ("exactly one at a
        // time"), not merely an allowance. ensureCurrentCandidateDateId
        // resolves a default only when needed (see its own docstring);
        // order is still startAt ascending (開催日の早い順, ADR-0060 decision
        // 6).
        var questions = state.view.scheduleQuestions;
        var total = questions.length;
        var answered = questions.filter(function (question) {
          return question.yourResponse !== null;
        }).length;
        // ADR-0060 decision 8: computed once per render from this same
        // array's own goingCount/maybeCount/notGoingCount (no API change).
        var leaders = computeScheduleQuestionLeaders(questions);

        ensureCurrentCandidateDateId(questions);
        var currentIndex = questions.findIndex(function (question) {
          return question.candidateDateId === state.currentCandidateDateId;
        });
        var currentQuestion = currentIndex !== -1 ? questions[currentIndex] : null;

        // isWideDayListLayout: read once per render (see
        // DAY_LIST_WIDE_LAYOUT_QUERY's own comment for why a live-resize
        // switch is not needed) -- chooses exactly one of dayList's two
        // board-fixed shapes; never both at once.
        var isWideDayListLayout =
          window.matchMedia && window.matchMedia(DAY_LIST_WIDE_LAYOUT_QUERY).matches;
        var heading = dayListHeading(total, answered);
        var dayListToggle = null;
        if (isWideDayListLayout) {
          dayListSidebarPending = renderDayListPanel(questions, leaders, heading);
        } else {
          var dayListSheetParts = renderDayListSheet(questions, leaders, heading);
          dayListToggle = dayListSheetParts.toggleButton;
          dayListSheetPending = dayListSheetParts.sheet;
        }

        children.push(renderHeader(answered, total, dayListToggle));

        var body = [];
        if (currentQuestion) {
          body.push(renderCurrentQuestionCard(currentQuestion, leaders));
          body.push(renderDayNav(questions, currentIndex));
        }
        var shopVoteSection = renderShopVoteSection(true);
        if (shopVoteSection) {
          body.push(shopVoteSection.node);
          shopVoteMapPending = shopVoteSection;
        }
        children.push(el("main", { class: "gth-body" }, body));
        children.push(renderProgress(total, answered));
      }
    }
    if (state.errorCode) {
      children.push(renderError());
    }
    var appEl = el("div", { class: "gth-app" }, children);
    if (dayListSidebarPending) {
      // Wide layout (c2r/D1-PcDay): the day panel sits beside .gth-app as a
      // persistent sidebar, never overlapping it.
      root.appendChild(
        el("div", { class: "gth-layout gth-layout--wide-day-list" }, [dayListSidebarPending, appEl])
      );
    } else {
      root.appendChild(appEl);
      if (dayListSheetPending) {
        // Narrow layout (c2/C2-a-SpDay+SpList): the sheet (scrim + dialog)
        // is a sibling of .gth-app, not a descendant of any of its rows --
        // its own fixed positioning is what makes it "重なる別の面" rather
        // than a layout participant, mirroring this file's own retired
        // answerLater overlay precedent.
        root.appendChild(dayListSheetPending);
      }
    }

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

    restoreFocusFromDescriptor(root, focusDescriptor);

    // Explicit open/close focus management for the narrow-layout day-list
    // sheet -- distinct from the generic restoreFocusFromDescriptor above,
    // which can only restore focus to an element that still exists after
    // this rebuild (identical shape to gathering.js's own
    // pendingIssueDialogFocus, ADR-0061 decision 1).
    if (state.pendingDayListSheetFocus === "open") {
      var sheetNode = root.querySelector(".gth-day-sheet");
      if (sheetNode) {
        sheetNode.focus({ preventScroll: true });
      }
      state.pendingDayListSheetFocus = null;
    } else if (state.pendingDayListSheetFocus === "close") {
      var sheetOpenButtonNode = root.querySelector(".gth-day-sheet-open-btn");
      if (sheetOpenButtonNode) {
        sheetOpenButtonNode.focus({ preventScroll: true });
      }
      state.pendingDayListSheetFocus = null;
    }
  }

  loadView();
})();
