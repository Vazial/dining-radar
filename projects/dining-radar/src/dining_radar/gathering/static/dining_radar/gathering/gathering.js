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
    // adr/0038, addCandidateDateForm.presenceRule: retains the entered
    // value across a DUPLICATE_CANDIDATE_DATE rejection (the form stays
    // open, value intact, ready to correct); cleared on a successful
    // submit (a fresh entry for the next candidate date).
    addCandidateDateValue: "",
    addCandidateDateDuplicateError: false,
    headerIssuedLinkUrl: null,
    recopiedLinkUrls: {},
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
    // addCandidateDate.
    state.addCandidateDateOpen = false;
    state.addCandidateDateValue = "";
    state.addCandidateDateDuplicateError = false;
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
          // adr/0038, human decision 2026-09-01 (AddDate.dc.html 案A:
          // "足したあとフォームは閉じない"): addCandidateDateOpen stays
          // true -- only the entered value clears, ready for the next
          // entry.
          state.addCandidateDateValue = "";
          state.addCandidateDateDuplicateError = false;
          render();
        } else if (
          result.status === 409 &&
          result.body &&
          result.body.code === "DUPLICATE_CANDIDATE_DATE"
        ) {
          // adr/0038: the form remains present with the entered value
          // intact, and no new gathering-candidate-date appears.
          state.addCandidateDateValue = localDateTimeValue;
          state.addCandidateDateDuplicateError = true;
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

  function renderAddCandidateDateForm() {
    // adr/0038 (AddDate.dc.html 案A, human decision 2026-09-01): the form
    // opens inline within gathering-candidate-date-list and stays open
    // across a successful submit; only cancel makes it absent again.
    var input = el(
      "input",
      {
        type: "datetime-local",
        "data-testid": "gathering-add-candidate-date-input",
        value: state.addCandidateDateValue || undefined,
      },
      []
    );
    var submit = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-add-candidate-date-submit",
        "data-gathering-control-purpose": "gathering-add-candidate-date-submit",
      },
      ["足す"]
    );
    submit.addEventListener("click", function () {
      submitAddCandidateDate(input.value);
    });
    var cancel = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-add-candidate-date-cancel",
        "data-gathering-control-purpose": "gathering-add-candidate-date-cancel",
      },
      ["やめる"]
    );
    cancel.addEventListener("click", cancelAddCandidateDate);

    var children = [input, submit, cancel];
    if (state.addCandidateDateDuplicateError) {
      children.push(el("p", {}, ["この日時は既に追加されています。"]));
    }
    return el("div", { "data-testid": "gathering-add-candidate-date-form" }, children);
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
      children.push(renderAddCandidateDateForm());
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
        "data-issued-link-url": state.headerIssuedLinkUrl || undefined,
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
      },
      ["再コピー"]
    );
    recopyButton.addEventListener("click", function () {
      recopyParticipantLink(link.id);
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
    // adr/0038, addCandidateDateOpen.requiredOutcome: the revealed form
    // must sit inline *within* gathering-candidate-date-list (AddDate.dc.
    // html 案A "その場で開く"), not beside it -- so the open control/form
    // is appended as this list's own last child, after every
    // gathering-candidate-date row (orderingInvariant only constrains the
    // relative order of gathering-candidate-date-tagged children, which
    // this trailing, differently-tagged child does not disturb).
    var candidateDateList = el(
      "div",
      { "data-testid": "gathering-candidate-date-list" },
      state.gathering.candidateDates.map(renderCandidateDate).concat([renderAddCandidateDateOpen()])
    );

    root.appendChild(
      el("div", {}, [
        renderPhaseIndicator(),
        renderResponseSummary(),
        renderUnansweredSummary(),
        candidateDateList,
        renderOpenShopPreview(),
        renderConfirmDate(),
        renderParticipantLinkCopy(),
        renderParticipantLinkList(),
      ])
    );
  }

  loadGathering();
})();
