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
    return fetch(url, options).then(function (response) {
      return response.json().then(function (responseBody) {
        return { status: response.status, body: responseBody };
      });
    });
  }

  function participantUrl() {
    return "/participant-links/" + encodeURIComponent(token);
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

  function loadView() {
    requestJson("GET", participantUrl()).then(function (result) {
      applyResult(result);
    });
  }

  function answerScheduleQuestion(candidateDateId, status) {
    requestJson("PUT", participantUrl() + "/responses/" + candidateDateId, { status: status }).then(
      function (result) {
        applyResult(result);
      }
    );
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
      [titleRow, progressBar, renderNameControl()]
    );
  }

  function renderNameControl() {
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
        el("div", { class: "gth-done-date" }, [question.startAt]),
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
        el("div", { class: "gth-open-date" }, [question.startAt]),
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

  function render() {
    root.innerHTML = "";
    var children = [];
    if (state.view) {
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
      var nextPanel = renderNextPanel(remainingCount, state.view.phase);
      if (nextPanel) {
        body.push(nextPanel);
      }
      body.push(renderFooter());
      body.push(renderFinePrint());
      children.push(el("main", { class: "gth-body" }, body));
      children.push(renderProgress(total, answered));
    }
    if (state.errorCode) {
      children.push(renderError());
    }
    root.appendChild(el("div", { class: "gth-app" }, children));
  }

  loadView();
})();
