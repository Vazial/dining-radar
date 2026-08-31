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
 */
(function () {
  "use strict";

  var root = document.getElementById("gathering-app");
  if (!root) {
    return;
  }

  var gatheringId = root.getAttribute("data-gathering-id");

  var state = {
    gathering: null,
    participantLinks: [],
    tentativeSelectedId: null,
    openShopPreview: null,
    addCandidateDateOpen: false,
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

  function loadGathering() {
    return requestJson("GET", gatheringUrl()).then(function (result) {
      state.gathering = result.body;
      return requestJson("GET", gatheringUrl() + "/participant-links");
    }).then(function (result) {
      state.participantLinks = result.body.participantLinks;
      render();
    });
  }

  function tentativelySelectCandidateDate(candidateDateId) {
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
        return loadParticipantLinksOnly();
      }
    });
  }

  function loadParticipantLinksOnly() {
    return requestJson("GET", gatheringUrl() + "/participant-links").then(function (result) {
      state.participantLinks = result.body.participantLinks;
      render();
    });
  }

  function copyParticipantLink(buttonEl) {
    requestJson("POST", gatheringUrl() + "/participant-links", { count: 1 }).then(function (result) {
      if (result.status !== 201) {
        return;
      }
      var issued = result.body.issuedLinks[0];
      buttonEl.setAttribute("data-issued-link-url", issued.url);
      if (window.navigator && window.navigator.clipboard) {
        window.navigator.clipboard.writeText(issued.url).catch(function () {});
      }
      state.gathering.totalIssuedParticipantLinks = result.body.totalIssuedParticipantLinks;
      state.gathering.activeParticipantLinkCount = result.body.activeParticipantLinkCount;
      loadParticipantLinksOnly();
    });
  }

  function recopyParticipantLink(linkId, buttonEl) {
    requestJson("POST", gatheringUrl() + "/participant-links/" + linkId + "/recopy").then(
      function (result) {
        if (result.status === 200) {
          buttonEl.setAttribute("data-issued-link-url", result.body.url);
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

  function submitAddCandidateDate(localDateTimeValue) {
    if (!localDateTimeValue) {
      return;
    }
    var startAt = new Date(localDateTimeValue).toISOString();
    requestJson("POST", gatheringUrl() + "/candidate-dates", { startAt: startAt }).then(
      function (result) {
        if (result.status === 201) {
          state.gathering = result.body;
          state.addCandidateDateOpen = false;
          render();
        }
      }
    );
  }

  function renderPhaseIndicator() {
    return el(
      "div",
      { "data-testid": "gathering-phase-indicator", "data-gathering-phase": state.gathering.phase },
      ["局面: " + state.gathering.phase]
    );
  }

  function renderResponseSummary() {
    return el(
      "div",
      {
        "data-testid": "gathering-responded-summary",
        "data-responded-count": state.gathering.respondedParticipantCount,
        "data-anonymous-responded-count": state.gathering.anonymousRespondedParticipantCount,
      },
      [
        state.gathering.respondedParticipantCount +
          "人が回答（うち" +
          state.gathering.anonymousRespondedParticipantCount +
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
      },
      [
        "有効なリンク " +
          state.gathering.activeParticipantLinkCount +
          "本 ・ まだ " +
          unansweredCount +
          "人が未回答",
      ]
    );
  }

  function renderCandidateDate(candidateDate) {
    var isTentative = state.tentativeSelectedId === candidateDate.id;
    var node = el(
      "div",
      {
        "data-testid": "gathering-candidate-date",
        "data-candidate-date-id": candidateDate.id,
        "data-going-count": candidateDate.goingCount,
        "data-maybe-count": candidateDate.maybeCount,
        "data-not-going-count": candidateDate.notGoingCount,
        "data-confirmed": candidateDate.isConfirmed ? "true" : "false",
        "data-tentative-selected": isTentative ? "true" : "false",
        "data-gathering-control-purpose": "gathering-candidate-date-tentative-select",
        role: "button",
        tabindex: "0",
      },
      [
        el("span", {}, [candidateDate.startAt]),
        el("span", {}, [
          " 行ける " +
            candidateDate.goingCount +
            " / たぶん " +
            candidateDate.maybeCount +
            " / むり " +
            candidateDate.notGoingCount,
        ]),
      ]
    );
    node.addEventListener("click", function () {
      tentativelySelectCandidateDate(candidateDate.id);
    });
    node.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        tentativelySelectCandidateDate(candidateDate.id);
      }
    });
    return node;
  }

  function renderAddCandidateDateOpen() {
    var openButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-add-candidate-date-open",
        "data-gathering-control-purpose": "gathering-add-candidate-date-open",
      },
      ["候補日を足す"]
    );
    openButton.addEventListener("click", openAddCandidateDate);

    var children = [openButton];
    if (state.addCandidateDateOpen) {
      var input = el("input", { type: "datetime-local" }, []);
      var submit = el("button", { type: "button" }, ["追加"]);
      submit.addEventListener("click", function () {
        submitAddCandidateDate(input.value);
      });
      children.push(el("div", {}, [input, submit]));
    }
    return el("div", {}, children);
  }

  function renderOpenShopPreviewItem(item) {
    return el("div", { "data-testid": "gathering-open-shop-preview-item" }, [
      el("span", { "data-testid": "gathering-open-shop-preview-item-name" }, [item.name]),
      el("span", { "data-testid": "gathering-open-shop-preview-item-genre" }, [item.genre]),
    ]);
  }

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
      },
      state.openShopPreview.previewShops.map(renderOpenShopPreviewItem)
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
      },
      ["この日にする"]
    );
    button.addEventListener("click", confirmDate);
    return button;
  }

  function renderParticipantLinkCopy() {
    var button = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-link-copy",
        "data-gathering-control-purpose": "gathering-participant-link-copy",
      },
      ["回答リンクをコピー"]
    );
    button.addEventListener("click", function () {
      copyParticipantLink(button);
    });
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
      },
      ["再コピー"]
    );
    recopyButton.addEventListener("click", function () {
      recopyParticipantLink(link.id, recopyButton);
    });

    var revokeButton = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-participant-link-revoke",
        "data-gathering-control-purpose": "gathering-participant-link-revoke",
        disabled: link.hasResponded || link.revoked,
      },
      ["失効"]
    );
    revokeButton.addEventListener("click", function () {
      revokeParticipantLink(link.id);
    });

    return el(
      "div",
      {
        "data-testid": "gathering-participant-link-item",
        "data-participant-link-id": link.id,
        "data-issued-at": link.issuedAt,
        "data-has-responded": link.hasResponded ? "true" : "false",
        "data-revoked": link.revoked ? "true" : "false",
        "data-participant-named": link.displayName === null ? "false" : "true",
      },
      [
        el("span", {}, [link.displayName === null ? "名無し" : link.displayName]),
        recopyButton,
        revokeButton,
      ]
    );
  }

  function renderParticipantLinkList() {
    return el(
      "div",
      { "data-testid": "gathering-participant-link-list" },
      state.participantLinks.map(renderParticipantLinkItem)
    );
  }

  function render() {
    root.innerHTML = "";
    if (!state.gathering) {
      return;
    }
    var candidateDateList = el(
      "div",
      { "data-testid": "gathering-candidate-date-list" },
      state.gathering.candidateDates.map(renderCandidateDate)
    );

    root.appendChild(
      el("div", {}, [
        renderPhaseIndicator(),
        renderResponseSummary(),
        renderUnansweredSummary(),
        candidateDateList,
        renderAddCandidateDateOpen(),
        renderOpenShopPreview(),
        renderConfirmDate(),
        renderParticipantLinkCopy(),
        renderParticipantLinkList(),
      ])
    );
  }

  loadGathering();
})();
