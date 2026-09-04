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
 * voting/finalization. Two more pieces of state are client-side pending
 * selection only, mirroring web/static/dining_radar/web/candidate.js's own
 * pending-filter convention (changePendingFilter: toggle now, apply only on
 * an explicit submit):
 *   - shortlistPending: { [shopId]: boolean } -- the checked state of
 *     gathering-open-shop-list-item's checkbox before gathering-shortlist-
 *     submit is activated. Never sent anywhere until that click.
 *   - finalizeSelectedShopId: the one shopId currently selected by the
 *     gathering-finalize-shop-select radio group, before gathering-finalize-
 *     submit is activated.
 * shortlistSelection.list reuses previewOpenShopsForCandidateDate (the same
 * endpoint tentativeSelectionAndPreview already calls) for the confirmed
 * candidate date -- gathering-scheduling-api.yaml's own 2026-09-03 header
 * comment documents this reuse.
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
    // adr/0042: the last-fetched CandidateDateOpenShopPreview for the
    // confirmed candidate date, reused as shortlistSelection.list's source
    // (same population previewOpenShopsForCandidateDate already exposes).
    openShopList: null,
    // adr/0042: client-side pending checked state for shortlistSelection's
    // checkboxes -- shopId -> boolean. Never sent to setShortlistedShops
    // until gathering-shortlist-submit is activated.
    shortlistPending: {},
    // adr/0042: whether shortlistSelection is shown while
    // Gathering.votingStartedAt is already non-null (a D7 replace, opened
    // via gathering-shortlist-open). Irrelevant while votingStartedAt is
    // null -- shortlistSelectionVisible() shows the list unconditionally
    // in that case (PickFive.dc.html's default first-time state).
    shortlistReplaceOpen: false,
    // adr/0042: client-side pending radio selection for
    // shortlistedShopVotes.list.item.finalizeSelect, before
    // gathering-finalize-submit is activated.
    finalizeSelectedShopId: null,
  };

  function csrfToken() {
    var field = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return field ? field.value : "";
  }

  // <input type="datetime-local">'s own value shape is always
  // "YYYY-MM-DDTHH:mm" (no seconds, no timezone -- this input type is
  // defined to carry no timezone information at all;
  // CandidateDateInput.startAt's format: date-time requires one). Building
  // the ISO string directly from these digits, tagged with a fixed UTC
  // offset, rather than routing the value through
  // `new Date(value).toISOString()`, removes a real dependency this screen
  // used to have on the *visiting browser's own host-OS timezone* to
  // interpret an otherwise timezone-less string (a timezone-less date-time
  // literal is parsed as "the host system's local time zone", per the
  // JS spec's Date Time String Format). Real-measurement finding
  // (2026-09-02, orchestrator合流 run): with the host machine's own local
  // zone at +09:00, `new Date("...T12:00").toISOString()` silently shifted
  // the submitted instant by 9 hours (12:00 became 03:00Z); a duplicate-
  // candidate-date resubmission of literally the same picked wall-clock
  // value then failed DUPLICATE_CANDIDATE_DATE's own instant-equality
  // check (gathering.services.add_candidate_date), not because that check
  // was wrong, but because the client was sending a different instant than
  // the one already stored. This function's own fixed-UTC tagging makes
  // the conversion deterministic regardless of the host machine's own
  // timezone.
  //
  // **Recorded trade-off, not resolved unilaterally (developer discretion
  // -- gathering-scheduling-browser-interface.yaml's own candidateDateRow/
  // addCandidateDateForm notes explicitly leave a merged date-time input's
  // timezone handling unfixed)**: the native datetime-local widget gives
  // the organizer no on-page indication of which timezone their typed/
  // picked wall-clock value will be interpreted as. Tagging it UTC here
  // means an organizer whose own intent is a JST wall-clock time (this
  // product's only real user base, product-brief.md) would need to add 9
  // hours themselves to get the instant they mean. A fixed Asia/Tokyo
  // interpretation (matching this project's own settings_base.TIME_ZONE)
  // would also be host-timezone-independent while matching real
  // organizers' likely intent, but choosing between the two is a product
  // decision no contract makes today -- flagged for architect/human review
  // (FR-028) rather than decided here.
  function dateTimeLocalValueToIso(value) {
    return value + ":00Z";
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

  // adr/0042: shortlistSelection is shown unconditionally while
  // votingStartedAt is still null (PickFive.dc.html's default first-time
  // state); once non-null, only while a D7 replace has been opened
  // (gathering-shortlist-open). Always absent outside SELECTING_SHOP.
  function shortlistSelectionVisible() {
    if (!state.gathering || state.gathering.phase !== "SELECTING_SHOP") {
      return false;
    }
    if (state.gathering.votingStartedAt === null) {
      return true;
    }
    return state.shortlistReplaceOpen === true;
  }

  function fetchOpenShopListForShortlist() {
    var candidateDateId = state.gathering.confirmedCandidateDateId;
    if (!candidateDateId) {
      return Promise.resolve();
    }
    return requestJson(
      "GET",
      gatheringUrl() + "/candidate-dates/" + candidateDateId + "/open-shop-preview"
    ).then(function (result) {
      if (result.status !== 200) {
        return;
      }
      state.openShopList = result.body;
      // D7 replace: pre-populate every item's pending checked state from
      // the *current* Gathering.shortlistedShops
      // (shortlistSelection.list.item.requirement, TDR-GTH-31/32).
      var currentShopIds = {};
      state.gathering.shortlistedShops.forEach(function (shop) {
        currentShopIds[shop.shopId] = true;
      });
      var pending = {};
      state.openShopList.previewShops.forEach(function (item) {
        pending[item.shopId] = !!currentShopIds[item.shopId];
      });
      state.shortlistPending = pending;
    });
  }

  function loadGathering() {
    return requestJson("GET", gatheringUrl())
      .then(function (result) {
        state.gathering = result.body;
        return requestJson("GET", gatheringUrl() + "/participant-links");
      })
      .then(function (result) {
        state.participantLinks = result.body.participantLinks;
        if (state.gathering.phase === "SELECTING_SHOP" && state.gathering.votingStartedAt === null) {
          return fetchOpenShopListForShortlist();
        }
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
    var startAt = dateTimeLocalValueToIso(localDateTimeValue);
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

  // --- adr/0042: shop shortlisting / approval voting / finalization -------

  function toggleShortlistPending(shopId) {
    // Client-side pending selection only (shortlistSelection.list.item.
    // select.requiredOutcome) -- calls no public operation.
    state.shortlistPending[shopId] = !state.shortlistPending[shopId];
    render();
  }

  function submitShortlist() {
    var shopIds = Object.keys(state.shortlistPending).filter(function (shopId) {
      return state.shortlistPending[shopId];
    });
    if (shopIds.length < 1) {
      return;
    }
    requestJson("PUT", gatheringUrl() + "/shortlisted-shops", { shopIds: shopIds }).then(
      function (result) {
        if (result.status === 200) {
          state.gathering = result.body;
          state.shortlistReplaceOpen = false;
          state.finalizeSelectedShopId = null;
          render();
        }
      }
    );
  }

  function openShortlistReplace() {
    // Refetch first, then reveal the list -- so the very first render of
    // shortlistSelection already carries the D7 pre-checked state from the
    // *current* shortlist (shortlistSelection.list.item.requirement),
    // rather than showing a stale/empty list for one frame.
    fetchOpenShopListForShortlist().then(function () {
      state.shortlistReplaceOpen = true;
      render();
    });
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
        state.shortlistReplaceOpen = false;
        render();
      }
    });
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
    };
    if (isSchedulingPhase) {
      attrs["data-gathering-control-purpose"] = "gathering-candidate-date-tentative-select";
      attrs.role = "button";
      attrs.tabindex = "0";
    }
    var node = el("div", attrs, [
      el("span", {}, [candidateDate.startAt]),
      el("span", {}, [
        " 行ける " +
          candidateDate.goingCount +
          " / たぶん " +
          candidateDate.maybeCount +
          " / むり " +
          candidateDate.notGoingCount,
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

  // --- adr/0042: shortlistSelection (PickFive.dc.html 案A) -----------------

  function renderOpenShopListItem(item) {
    var checked = !!state.shortlistPending[item.shopId];
    var checkbox = el(
      "input",
      {
        type: "checkbox",
        "data-testid": "gathering-open-shop-select",
        "data-gathering-control-purpose": "gathering-open-shop-select",
        checked: checked,
      },
      []
    );
    checkbox.addEventListener("click", function () {
      toggleShortlistPending(item.shopId);
    });
    return el(
      "div",
      {
        "data-testid": "gathering-open-shop-list-item",
        "data-shop-id": item.shopId,
        "data-shortlisted": checked ? "true" : "false",
      },
      [checkbox, el("span", {}, [item.name]), el("span", {}, [item.genre])]
    );
  }

  function renderShortlistSelection() {
    var previewShops = state.openShopList ? state.openShopList.previewShops : [];
    var list = el(
      "div",
      {
        "data-testid": "gathering-open-shop-list",
        "data-open-shop-count": state.openShopList ? state.openShopList.openShopCount : 0,
      },
      previewShops.map(renderOpenShopListItem)
    );

    var selectedCount = Object.keys(state.shortlistPending).filter(function (shopId) {
      return state.shortlistPending[shopId];
    }).length;
    var submit = el(
      "button",
      {
        type: "button",
        "data-testid": "gathering-shortlist-submit",
        "data-gathering-control-purpose": "gathering-shortlist-submit",
        disabled: selectedCount < 1,
      },
      ["この" + selectedCount + "件で投票する"]
    );
    submit.addEventListener("click", submitShortlist);

    return el("div", {}, [list, submit]);
  }

  // --- adr/0042: shortlistedShopVotes (Organizer.dc.html 状態②) ------------

  function renderShortlistedShopItem(shop) {
    var attrs = {
      "data-testid": "gathering-shortlisted-shop-item",
      "data-shop-id": shop.shopId,
      "data-approval-count": shop.approvalCount,
      "data-responded-count": shop.respondedParticipantCount,
    };
    var children = [
      el("span", {}, [shop.name]),
      el("span", {}, [shop.approvalCount + "人 / " + shop.respondedParticipantCount + "人中"]),
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
      { "data-testid": "gathering-shortlisted-shop-list" },
      state.gathering.shortlistedShops.map(renderShortlistedShopItem)
    );
    var children = [list];

    // replaceOpen/finalizeSubmit: both present only while SELECTING_SHOP
    // (absent once FINALIZED, shortlistedShopVotes.replaceOpen.presenceRule /
    // finalizeSubmit.presenceRule).
    if (phase === "SELECTING_SHOP") {
      var replaceOpen = el(
        "button",
        {
          type: "button",
          "data-testid": "gathering-shortlist-open",
          "data-gathering-control-purpose": "gathering-shortlist-open",
        },
        ["店を絞りなおす"]
      );
      replaceOpen.addEventListener("click", openShortlistReplace);
      children.push(replaceOpen);

      if (state.gathering.shortlistedShops.length > 0) {
        var finalizeSubmit = el(
          "button",
          {
            type: "button",
            "data-testid": "gathering-finalize-submit",
            "data-gathering-control-purpose": "gathering-finalize-submit",
            disabled: !state.finalizeSelectedShopId,
          },
          ["日と店を確定する"]
        );
        finalizeSubmit.addEventListener("click", finalizeGathering);
        children.push(finalizeSubmit);
      }
    }

    return el("div", {}, children);
  }

  // --- adr/0042: finalizedSummary (Final.dc.html A③) -----------------------

  function renderFinalizedSummary() {
    var confirmed = state.gathering.candidateDates.filter(function (candidateDate) {
      return candidateDate.isConfirmed;
    })[0];
    return el(
      "div",
      {
        "data-testid": "gathering-decision-banner",
        "data-confirmed-candidate-date": confirmed ? confirmed.startAt : undefined,
        "data-finalized-shop-id": state.gathering.finalizedShopId,
      },
      [
        "決まりました: " +
          (confirmed ? confirmed.startAt : "") +
          " ・ " +
          state.gathering.finalizedShopId,
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

    var children = [
      el("span", {}, [link.displayName === null ? "名無し" : link.displayName]),
      recopyButton,
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
        },
        ["失効"]
      );
      revokeButton.addEventListener("click", function () {
        revokeParticipantLink(link.id);
      });
      children.push(revokeButton);
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
      },
      children
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
    var phase = state.gathering.phase;

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
      { "data-testid": "gathering-candidate-date-list" },
      candidateDateListChildren
    );

    var children = [
      renderPhaseIndicator(),
      renderResponseSummary(),
      renderUnansweredSummary(),
      candidateDateList,
    ];

    if (phase === "SCHEDULING") {
      children.push(renderOpenShopPreview());
      children.push(renderConfirmDate());
    }

    if (shortlistSelectionVisible()) {
      children.push(renderShortlistSelection());
    }

    if (state.gathering.votingStartedAt !== null) {
      children.push(renderShortlistedShopVotes());
    }

    if (phase === "FINALIZED") {
      children.push(renderFinalizedSummary());
    }

    // participantLinkCopy.presenceRule (adr/0042): absent once FINALIZED (P4).
    if (phase !== "FINALIZED") {
      children.push(renderParticipantLinkCopy());
    }

    children.push(renderParticipantLinkList());

    root.appendChild(el("div", {}, children));
  }

  loadGathering();
})();
