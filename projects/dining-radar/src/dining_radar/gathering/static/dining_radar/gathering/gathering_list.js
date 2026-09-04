/**
 * Organizer gathering-list screen behaviour (organizerGatheringList,
 * contracts/gathering-scheduling-browser-interface.yaml, adr/0038).
 *
 * Fills the gap the human found in production ("幹事画面への入口が無い",
 * Entry.dc.html E-1/E-1b) -- the organizer's entry point after sign-in.
 * Uses the same JS-executing render / el()-builder / fetch conventions
 * gathering.js already established for organizerDashboard (renderModel).
 *
 * securityObservations.organizerGatheringList: stateChangingOperations is
 * empty -- this screen only ever performs a read (GET /gatherings) and
 * plain-link navigation, so no CSRF token is needed or sent here.
 */
(function () {
  "use strict";

  var root = document.getElementById("gathering-list-app");
  if (!root) {
    return;
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

  function requestJson(method, url) {
    return fetch(url, { method: method, credentials: "same-origin" }).then(function (response) {
      return response.json().then(function (body) {
        return { status: response.status, body: body };
      });
    });
  }

  // product-brief.md §2's three-phase state machine (adr/0038 D10: the
  // persisted DRAFT phase never existed).
  var PHASE_LABELS = {
    SCHEDULING: "日程を聞き中",
    SELECTING_SHOP: "店を選び中",
    FINALIZED: "確定",
  };

  // contracts/gathering-scheduling-browser-interface.yaml's
  // unavailableControls.allowedPurposes lists gathering-create-open and
  // gathering-list-item-open explicitly, so both declare
  // data-gathering-control-purpose even though a plain <a> is used
  // (mirrors candidate-search-browser-interface.yaml's own precedent of
  // declaring a purpose on a navigation-only element when the contract
  // names it).
  function renderCreateOpen() {
    return el(
      "a",
      {
        href: "/gatherings/new/",
        "data-testid": "gathering-create-open",
        "data-gathering-control-purpose": "gathering-create-open",
        "class": "gathering-btn gathering-btn-primary",
      },
      ["会をつくる"]
    );
  }

  function confirmedCandidateDateStartAt(gathering) {
    if (!gathering.confirmedCandidateDateId) {
      return null;
    }
    var matches = gathering.candidateDates.filter(function (candidateDate) {
      return candidateDate.id === gathering.confirmedCandidateDateId;
    });
    return matches.length > 0 ? matches[0].startAt : null;
  }

  // Entry.dc.html E-1: a gathering with zero issued links reads "まだリンクを
  // 発行していません" instead of the responded/active-link counters (there is
  // nothing yet to count).
  function renderLinkSummary(gathering) {
    if (gathering.totalIssuedParticipantLinks === 0) {
      return "まだリンクを発行していません";
    }
    return (
      "回答 " +
      gathering.respondedParticipantCount +
      " / 有効なリンク " +
      gathering.activeParticipantLinkCount
    );
  }

  function renderItem(gathering) {
    var confirmedStartAt = confirmedCandidateDateStartAt(gathering);
    var attrs = {
      "data-testid": "gathering-list-item",
      "data-gathering-id": gathering.id,
      // adr/0042: closes ADR-0040 未決事項2's audit-flagged gap -- this
      // list previously had no machine-observable attribute for the
      // gathering's own name.
      "data-gathering-title": gathering.title,
      "data-gathering-phase": gathering.phase,
      "data-responded-count": gathering.respondedParticipantCount,
      "data-active-issued-links": gathering.activeParticipantLinkCount,
      "class": "gathering-list-item",
    };
    if (confirmedStartAt) {
      attrs["data-confirmed-candidate-date"] = confirmedStartAt;
    }

    var openLink = el(
      "a",
      {
        href: "/gatherings/" + gathering.id + "/",
        "data-testid": "gathering-list-item-open",
        "data-gathering-control-purpose": "gathering-list-item-open",
        "class": "gathering-btn",
      },
      ["開く"]
    );

    return el("li", attrs, [
      el("span", { "class": "gathering-list-item-title" }, [gathering.title]),
      el("span", { "class": "gathering-list-item-phase" }, [
        PHASE_LABELS[gathering.phase] || gathering.phase,
      ]),
      el("span", { "class": "gathering-list-item-summary" }, [
        confirmedStartAt
          ? confirmedStartAt + " に決定"
          : "候補日 " + gathering.candidateDates.length + "つ",
      ]),
      el("span", { "class": "gathering-list-item-links" }, [renderLinkSummary(gathering)]),
      openLink,
    ]);
  }

  function render(gatherings) {
    root.innerHTML = "";
    root.appendChild(el("div", { "class": "gathering-list-header" }, [renderCreateOpen()]));

    // browserControlSurface.organizerGatheringList.requiredTestIds lists
    // `list: gathering-list` alongside `createOpen` -- the same grouping
    // organizerDashboard.requiredTestIds uses for gathering-candidate-date-
    // list, which this screen's own sibling implementation (gathering.js)
    // already renders unconditionally regardless of item count. "required"
    // means this container itself is always present on this screen; only
    // its own gathering-list-item children have the "zero-or-more" cardinality
    // (list.item.cardinality). An earlier revision returned before building
    // this element at all when the response was empty -- confirmed wrong by
    // orchestrator's合流 measurement (get_by_test_id("gathering-list") not
    // attached on TDR-GTH-22/23, both of which reach this screen while
    // empty): `gathering-list-empty`'s own presenceRule only says it is
    // present when the response is empty and that no gathering-list-item
    // exists then -- it says nothing about gathering-list's own absence, so
    // the two coexist (an empty <ul> plus the guidance) exactly the way
    // list.orderingInvariant/empty.containsCreateOpen already imply two
    // independent, co-existing observations rather than a mutually
    // exclusive pair.
    root.appendChild(
      el(
        "ul",
        { "data-testid": "gathering-list", "class": "gathering-list" },
        gatherings.map(renderItem)
      )
    );

    if (gatherings.length === 0) {
      // Entry.dc.html E-1b: the "no gathering yet" guidance carries its own
      // second gathering-create-open instance, in addition to the header's
      // (browserControlSurface.organizerGatheringList.createOpen.cardinality).
      root.appendChild(
        el("div", { "data-testid": "gathering-list-empty", "class": "gathering-list-empty" }, [
          el("p", {}, ["まだ会がありません"]),
          el("p", { "class": "gathering-list-empty-hint" }, [
            "会をつくると、候補日を出して、回答リンクを1本ずつ配れるようになります。",
          ]),
          renderCreateOpen(),
        ])
      );
    }
  }

  requestJson("GET", "/gatherings").then(function (result) {
    if (result.status === 200) {
      render(result.body.gatherings);
    }
  });
})();
