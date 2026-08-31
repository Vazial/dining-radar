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

  function renderHeader() {
    return el(
      "div",
      { "data-testid": "gathering-participant-header", "data-gathering-phase": state.view.phase },
      [state.view.gatheringTitle]
    );
  }

  function renderNameControl() {
    var named = state.view.displayName !== null;
    var status = el(
      "div",
      {
        "data-testid": "gathering-participant-name-status",
        "data-participant-named": named ? "true" : "false",
      },
      [named ? "回答者: " + state.view.displayName : "名前なしのまま"]
    );

    var openButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-name-open",
        "data-gathering-control-purpose": "gathering-participant-name-open",
      },
      ["名前を付ける"]
    );
    openButton.addEventListener("click", openNameControl);

    var children = [status, openButton];
    if (state.nameOpen) {
      var input = el("input", { type: "text", "data-testid": "gathering-participant-name-input" }, []);
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
      children.push(el("div", {}, [input, submit]));
    }
    return el("div", {}, children);
  }

  var RESPONSE_VALUES = ["GOING", "MAYBE", "NOT_GOING"];
  var RESPONSE_LABELS = { GOING: "行ける", MAYBE: "たぶん", NOT_GOING: "むり" };

  function renderScheduleQuestion(question) {
    var yourResponse = question.yourResponse === null ? "UNANSWERED" : question.yourResponse;
    var children = [
      el("div", {}, [question.startAt]),
      el("div", {}, ["この日に開いている店 " + question.openShopCount + "件"]),
    ];

    RESPONSE_VALUES.forEach(function (value) {
      var option = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-schedule-response-option",
          "data-gathering-control-purpose": "gathering-schedule-response-select",
          "data-response-value": value,
          "aria-pressed": yourResponse === value ? "true" : "false",
        },
        [RESPONSE_LABELS[value]]
      );
      option.addEventListener("click", function () {
        answerScheduleQuestion(question.candidateDateId, value);
      });
      children.push(option);
    });

    if (question.tally) {
      children.push(
        el(
          "div",
          {
            "data-testid": "gathering-schedule-tally",
            "data-going-count": question.tally.goingCount,
            "data-maybe-count": question.tally.maybeCount,
            "data-not-going-count": question.tally.notGoingCount,
          },
          [
            "行ける " +
              question.tally.goingCount +
              " ・ たぶん " +
              question.tally.maybeCount +
              " ・ むり " +
              question.tally.notGoingCount,
          ]
        )
      );
    }

    return el(
      "div",
      {
        "data-testid": "gathering-schedule-question",
        "data-candidate-date-id": question.candidateDateId,
        "data-open-shop-count": question.openShopCount,
        "data-your-response": yourResponse,
      },
      children
    );
  }

  function renderProgress() {
    var total = state.view.scheduleQuestions.length;
    var answered = state.view.scheduleQuestions.filter(function (question) {
      return question.yourResponse !== null;
    }).length;
    return el(
      "div",
      {
        "data-testid": "gathering-participant-progress",
        "data-total-candidate-dates": total,
        "data-answered-candidate-dates": answered,
      },
      ["日程 " + answered + " / " + total]
    );
  }

  function renderError() {
    return el(
      "div",
      { "data-testid": "gathering-participant-link-error", "data-link-error-code": state.errorCode },
      ["このリンクは使用できません。"]
    );
  }

  function render() {
    root.innerHTML = "";
    var children = [];
    if (state.view) {
      children.push(renderHeader());
      children.push(renderNameControl());
      state.view.scheduleQuestions.forEach(function (question) {
        children.push(renderScheduleQuestion(question));
      });
      children.push(renderProgress());
    }
    if (state.errorCode) {
      children.push(renderError());
    }
    root.appendChild(el("div", {}, children));
  }

  loadView();
})();
