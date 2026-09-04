/**
 * Organizer gathering-creation screen behaviour (organizerGatheringCreate,
 * contracts/gathering-scheduling-browser-interface.yaml, adr/0038).
 *
 * Entry.dc.html E-2: a name and one or more candidate dates. D10
 * (2026-09-01 human decision): a gathering is created directly in
 * SCHEDULING -- there is no persisted draft phase to model here.
 *
 * State kept client-side only until a successful submit: `title` and
 * `rows` (one entry per gathering-create-candidate-date-row, `value`
 * holding that row's raw <input type="datetime-local"> string). Rebuilding
 * the whole tree on add/remove-row keeps every row's already-typed value
 * (read from `row.value`, mutated by each input's own "input" listener)
 * rather than losing it -- the same reason gathering.js's
 * copyParticipantLink tracks data-issued-link-url in `state` instead of on
 * a DOM node a later render() rebuild would replace.
 */
(function () {
  "use strict";

  var root = document.getElementById("gathering-create-app");
  if (!root) {
    return;
  }

  var nextRowKey = 1;
  var state = {
    title: "",
    rows: [{ key: 0, value: "" }],
    duplicateError: false,
  };

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

  // browserControlSurface.organizerGatheringCreate.submit.disabledState:
  // disabled while the name is empty, or every row lacks a value (ADR-0035
  // decision 1's ">=1 candidate date" requirement, mirrored client-side --
  // the API itself remains the authoritative enforcement). A row with no
  // value simply is not sent (see submit() below); this is not the same as
  // requiring *every* row to be filled in.
  function canSubmit() {
    return (
      Boolean(state.title) &&
      state.rows.some(function (row) {
        return Boolean(row.value);
      })
    );
  }

  function refreshSubmitDisabled() {
    var submitButton = root.querySelector('[data-testid="gathering-create-submit"]');
    if (submitButton) {
      submitButton.disabled = !canSubmit();
    }
  }

  function addRow() {
    state.rows.push({ key: nextRowKey++, value: "" });
    render();
  }

  function removeRow(key) {
    state.rows = state.rows.filter(function (row) {
      return row.key !== key;
    });
    render();
  }

  // Same fixed-UTC tagging as gathering.js's own dateTimeLocalValueToIso,
  // and for the same reason -- see that function's comment for the full
  // account (real-measurement finding, 2026-09-02, orchestrator合流 run:
  // `new Date(value).toISOString()` silently shifted the submitted instant
  // by the host machine's own local-timezone offset instead of producing a
  // deterministic value) and the recorded organizer-intent trade-off this
  // developer is not positioned to resolve unilaterally (FR-028).
  function toStartAtIso(rawDateTimeLocalValue) {
    return rawDateTimeLocalValue + ":00Z";
  }

  function submit() {
    if (!canSubmit()) {
      return;
    }
    var candidateDates = state.rows
      .filter(function (row) {
        return Boolean(row.value);
      })
      .map(function (row) {
        return { startAt: toStartAtIso(row.value) };
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
          // adr/0038: the screen remains, every row's entered value
          // intact -- state.title/state.rows are untouched, so the
          // re-render below reproduces every value exactly.
          state.duplicateError = true;
          render();
        }
      }
    );
  }

  function cancel() {
    window.location.href = "/gatherings/";
  }

  function renderRow(row, total) {
    var input = el(
      "input",
      {
        type: "datetime-local",
        "data-testid": "gathering-create-candidate-date-input",
        value: row.value || undefined,
        "class": "gathering-input",
      },
      []
    );
    input.addEventListener("input", function () {
      row.value = input.value;
      refreshSubmitDisabled();
    });

    var children = [input];
    // Entry.dc.html E-2: the sole remaining row has no remove control
    // (ADR-0035 decision 1 / D10: a gathering cannot be created with zero
    // candidate dates); every other row does
    // (browserControlSurface.organizerGatheringCreate.candidateDateRow.
    // removeRow.presenceRule).
    if (total > 1) {
      var removeButton = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-create-remove-candidate-date-row",
          "data-gathering-control-purpose": "gathering-create-remove-candidate-date-row",
          "class": "gathering-btn gathering-btn-small",
        },
        ["削除"]
      );
      removeButton.addEventListener("click", function () {
        removeRow(row.key);
      });
      children.push(removeButton);
    }
    return el(
      "div",
      { "data-testid": "gathering-create-candidate-date-row", "class": "gathering-create-row" },
      children
    );
  }

  function render() {
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

    var rowsContainer = el(
      "div",
      { "class": "gathering-create-rows" },
      state.rows.map(function (row) {
        return renderRow(row, state.rows.length);
      })
    );

    var addRowButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-create-add-candidate-date-row",
        "data-gathering-control-purpose": "gathering-create-add-candidate-date-row",
        "class": "gathering-link-btn",
      },
      ["＋ 候補日を足す"]
    );
    addRowButton.addEventListener("click", addRow);

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
      el("label", { "class": "gathering-field-label" }, ["最初の候補日"]),
      rowsContainer,
      addRowButton,
    ];
    if (state.duplicateError) {
      children.push(el("p", { "class": "gathering-create-error" }, ["同じ日時の候補日は既に追加されています。"]));
    }
    children.push(el("div", { "class": "gathering-create-actions" }, [submitButton, cancelButton]));

    root.appendChild(el("div", { "class": "gathering-create-form" }, children));
  }

  render();
})();
