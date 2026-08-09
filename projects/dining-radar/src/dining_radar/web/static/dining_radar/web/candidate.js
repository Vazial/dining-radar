/**
 * Candidate-proposal screen behaviour.
 *
 * Implements the browser control surface from
 * contracts/candidate-search-browser-interface.yaml against the public
 * contracts/candidate-search-api.yaml POST /candidate-proposals endpoint.
 * This file performs no persistence: the shown-candidate comparison state
 * (`shownProviderPageUrls`) lives only in this module's memory and is
 * cleared automatically on reload, tab close, or sign-out, because none of
 * those keep this JavaScript execution context alive (ADR-0008 decision 3).
 *
 * Per adr/0017, repeat demotion (ordering every new candidate before every
 * repeated one) is now computed server-side: on every re-proposal request
 * this module echoes `shownProviderPageUrls` back unchanged as
 * `previouslyShownProviderPageUrls`, and simply renders the response's
 * `proposal.candidates` in the order the server returned them, without
 * re-sorting locally. This module still tracks membership in
 * `shownProviderPageUrls` itself, purely to decide each rendered card's own
 * `data-repeat-status` badge.
 */
(function () {
  "use strict";

  var root = document.getElementById("candidate-app");
  if (!root) {
    return;
  }

  var overlay = document.getElementById("candidate-reproposal-overlay");
  var shownProviderPageUrls = new Set();
  var currentOptions = [];
  var currentProposalKind = null;
  var cardElementsByRef = {};
  var markerElementsByRef = {};
  var leafletMap = null;

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

  function requestProposal(reproposalKind) {
    // adr/0017 decision 1: a re-proposal request echoes back the exact
    // providerPageUrl values this server has already returned to this
    // browser this screen lifetime, unchanged and sourced only from this
    // module's own in-memory Set -- never from storage, a cookie, or the
    // URL. The initial request (reproposalKind omitted) sends an empty body,
    // since nothing has been shown yet.
    var body = {};
    if (reproposalKind) {
      body.reproposalKind = reproposalKind;
      body.previouslyShownProviderPageUrls = Array.from(shownProviderPageUrls);
    }
    return fetch("/candidate-proposals", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json().then(function (body) {
        return { status: response.status, body: body };
      });
    });
  }

  function fieldRow(label, testId, value, formatted, rawValueAttribute, unavailableText) {
    var provided = value !== null && value !== undefined && value !== "";
    var attrs = {
      "data-testid": testId,
      "data-field-label": label,
      "data-value-state": provided ? "provided" : "unavailable",
    };
    // Per ADR-0011 / candidate-search-browser-interface.yaml v0.2: a field
    // whose requiredFields entry declares rawValueAttribute (currently only
    // totalSeats) carries the returned value's canonical decimal string on
    // this same element when provided, kept exactly equal to the API value
    // even though the visible text (`formatted`) may add display formatting
    // (e.g. the "席" unit suffix) around it. The attribute is omitted when
    // unavailable, since data-value-state=unavailable already expresses that.
    if (provided && rawValueAttribute) {
      attrs[rawValueAttribute] = String(value);
    }
    return el("div", {}, [
      el("dt", {}, [label]),
      el(
        "dd",
        attrs,
        [
          provided
            ? formatted !== undefined
              ? formatted
              : String(value)
            : unavailableText !== undefined
              ? unavailableText
              : "情報なし",
        ]
      ),
    ]);
  }

  function selectCandidate(candidateRef) {
    Object.keys(cardElementsByRef).forEach(function (ref) {
      var state = ref === candidateRef ? "selected" : "unselected";
      cardElementsByRef[ref].setAttribute("data-selection-state", state);
      if (markerElementsByRef[ref]) {
        markerElementsByRef[ref].setAttribute("data-selection-state", state);
      }
    });
  }

  function renderCard(candidate, repeated, selected, index, isReproposalRound) {
    var card = el("article", {
      "data-testid": "candidate-card",
      "data-candidate-ref": candidate.candidateRef,
      "data-selection-state": selected ? "selected" : "unselected",
      "data-provider-page-href": candidate.providerPageUrl,
      "data-repeat-status": repeated ? "repeated" : "new",
      "data-candidate-control-category": "button",
      "data-candidate-control-purpose": "candidate-card-selection",
      role: "button",
      tabindex: "0",
    }, []);
    card.addEventListener("click", function () {
      selectCandidate(candidate.candidateRef);
    });
    card.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCandidate(candidate.candidateRef);
      }
    });

    // Identification row: the same number the map marker shows (so a card
    // and its marker are visually tied together), the genre as a small
    // chip, and -- only once a re-proposal has actually happened, since the
    // very first proposal has nothing to compare against -- whether this
    // shop is newly offered or was already shown this screen lifetime
    // (contract repeatPriority; the ordering itself is now computed
    // server-side, adr/0017).
    var idRow = el("div", { "class": "candidate-card-id-row" }, [
      el("span", { "class": "candidate-marker-badge", "aria-hidden": "true" }, [String(index + 1)]),
    ]);
    idRow.appendChild(
      el(
        "p",
        {
          "data-testid": "candidate-card-genre",
          "data-field-label": "ジャンル",
          "data-value-state": "provided",
          "class": "candidate-genre-chip",
        },
        [candidate.genre]
      )
    );
    if (isReproposalRound) {
      idRow.appendChild(
        el(
          "span",
          {
            "class": repeated ? "candidate-chip candidate-chip-repeated" : "candidate-chip candidate-chip-new",
          },
          [repeated ? "前回も候補でした" : "今回はじめて"]
        )
      );
    }
    card.appendChild(idRow);

    card.appendChild(
      el(
        "h3",
        {
          "data-testid": "candidate-card-name",
          "data-field-label": "店名",
          "data-value-state": "provided",
          "class": "candidate-shop-name",
        },
        [candidate.name]
      )
    );

    var facts = el("dl", { "class": "candidate-facts" }, []);
    facts.appendChild(
      fieldRow(
        "紹介",
        "candidate-card-description",
        candidate.description,
        undefined,
        undefined,
        "紹介文の登録はありません"
      )
    );
    facts.appendChild(fieldRow("定休日", "candidate-card-regular-holiday", candidate.regularHoliday));
    facts.appendChild(
      fieldRow(
        "総席数",
        "candidate-card-total-seats",
        candidate.totalSeats,
        candidate.totalSeats === null || candidate.totalSeats === undefined
          ? undefined
          : candidate.totalSeats + "席",
        "data-raw-value"
      )
    );
    facts.appendChild(fieldRow("アクセス", "candidate-card-access", candidate.access));
    card.appendChild(facts);

    var link = el(
      "a",
      {
        "data-testid": "candidate-card-provider-page-link",
        "data-field-label": "詳細",
        "data-value-state": "provided",
        "class": "candidate-detail-link",
        href: candidate.providerPageUrl,
        target: "_blank",
        rel: "noopener noreferrer",
      },
      ["メニューなどを確認"]
    );
    link.addEventListener("click", function (event) {
      event.stopPropagation();
    });
    card.appendChild(link);

    cardElementsByRef[candidate.candidateRef] = card;
    return card;
  }

  function initializeMap(container, candidates) {
    markerElementsByRef = {};
    if (leafletMap) {
      leafletMap.remove();
      leafletMap = null;
    }
    if (!window.L) {
      return;
    }

    var map = window.L.map(container, { attributionControl: false });
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);

    var latLngs = candidates.map(function (candidate) {
      return [candidate.location.latitude, candidate.location.longitude];
    });

    // Leaflet's Map#addLayer defers a layer's onAdd (and therefore marker
    // icon creation) until the map has an established view, via
    // Map#whenReady: https://leafletjs.com/reference.html#map-whenready.
    // A map created without initial center/zoom has no view until setView
    // or fitBounds runs, so it must happen before any marker is added below
    // -- otherwise marker.getElement() returns undefined for every
    // candidate and the whole per-marker attribute/handler block silently
    // never executes, even though the source lines below are unreachable
    // only at runtime (see friction-log: silent-runtime-only-dom-failure).
    if (latLngs.length > 0) {
      map.fitBounds(window.L.latLngBounds(latLngs), { padding: [24, 24] });
    } else {
      map.setView([0, 0], 2);
    }

    candidates.forEach(function (candidate, index) {
      // The interactive box (iconSize) is a 44px hit area -- Leaflet binds
      // its click/keyboard handling to this whole box, per
      // https://leafletjs.com/reference.html#icon-iconsize, so this is what
      // actually satisfies a >=44px touch target, not the visual size.
      // A visually smaller circle (.candidate-map-marker-visual, 36px, see
      // home.html) is centered inside it: on a map with several close
      // candidates, keeping the painted badge compact avoids the pins
      // themselves overlapping/obscuring each other, while the invisible
      // 44px box around each one still gives a comfortable tap/click
      // target (a common map-pin pattern; Leaflet's own 12px unstyled
      // default had neither property).
      // The number is not aria-hidden here (unlike the card's own repeat of
      // it, .candidate-marker-badge): the map marker button carries no
      // other text, so hiding it would leave the button's accessible name
      // empty for assistive technology, even though the visual circle is
      // deliberately smaller than the 44px hit box around it.
      var icon = window.L.divIcon({
        className: "candidate-map-marker-icon",
        html: '<span class="candidate-map-marker-visual"></span>',
        iconSize: [44, 44],
        iconAnchor: [22, 22],
      });
      var marker = window.L.marker(latLngs[index], { icon: icon, keyboard: true });
      marker.addTo(map);
      var markerEl = marker.getElement();
      if (!markerEl) {
        return;
      }
      markerEl.setAttribute("data-testid", "candidate-map-marker");
      markerEl.setAttribute("data-candidate-ref", candidate.candidateRef);
      markerEl.setAttribute("data-selection-state", index === 0 ? "selected" : "unselected");
      markerEl.setAttribute("role", "button");
      markerEl.setAttribute("tabindex", "0");
      markerEl.setAttribute("data-candidate-control-category", "button");
      markerEl.setAttribute("data-candidate-control-purpose", "candidate-map-marker-selection");
      var markerVisual = markerEl.querySelector(".candidate-map-marker-visual");
      if (markerVisual) {
        markerVisual.textContent = String(index + 1);
      }
      markerEl.addEventListener("click", function () {
        selectCandidate(candidate.candidateRef);
      });
      markerElementsByRef[candidate.candidateRef] = markerEl;
    });

    container.setAttribute("data-map-fit-state", "displayed-candidates");
    leafletMap = map;
  }

  function closeReproposalDialog() {
    overlay.hidden = true;
    overlay.innerHTML = "";
  }

  function renderReproposalDialog() {
    // adr/0016 decision 5: selecting an option itself performs the
    // re-proposal; there is no separate confirmation control (the removed
    // candidate-reproposal-submit / reproposal-submit purpose).
    var optionButtons = currentOptions.map(function (option) {
      var button = el(
        "button",
        {
          type: "button",
          "data-testid": "candidate-reproposal-option",
          "data-reproposal-kind": option.kind,
          "data-candidate-control-category": "button",
          "data-candidate-control-purpose": "reproposal-selection",
        },
        [el("strong", {}, [option.title]), el("p", {}, [option.rationale])]
      );
      button.addEventListener("click", function () {
        requestProposal(option.kind).then(function (result) {
          closeReproposalDialog();
          handleProposalResponse(result.status, result.body);
        });
      });
      return button;
    });

    var cancelButton = el(
      "button",
      {
        type: "button",
        "data-testid": "candidate-reproposal-cancel",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "reproposal-cancel",
      },
      ["閉じる"]
    );
    cancelButton.addEventListener("click", closeReproposalDialog);

    var dialog = el(
      "section",
      { "data-testid": "candidate-reproposal-dialog", role: "dialog", "aria-modal": "true" },
      [el("div", {}, optionButtons), cancelButton]
    );

    overlay.innerHTML = "";
    overlay.appendChild(dialog);
    overlay.hidden = false;
  }

  function renderProblem(code, message) {
    root.innerHTML = "";
    root.appendChild(
      el(
        "section",
        { "data-testid": "candidate-proposal-problem", "data-problem-code": code, role: "alert" },
        [el("p", { "data-testid": "candidate-proposal-problem-guidance" }, [message])]
      )
    );
  }

  function renderEmpty() {
    root.innerHTML = "";
    root.appendChild(
      el("section", { "data-testid": "candidate-no-results" }, [
        "この選び方に合うランチ候補が見つかりませんでした。",
      ])
    );
  }

  function renderProposal(proposal, providerCredit) {
    cardElementsByRef = {};
    currentProposalKind = proposal.kind;
    root.innerHTML = "";

    var content = el("section", { "data-testid": "candidate-proposal-content" }, []);

    // Concept banner: the current lens's heading and the re-proposal
    // starting point, kept together as one visual block (ADR-0012 skeleton
    // block 2: "現在の切り口の見出し＋再提案の起点").
    var conceptBanner = el("div", { "class": "candidate-concept-banner" }, [
      el("div", { "class": "candidate-concept-copy" }, [
        el("h2", { "data-testid": "candidate-concept-title" }, [proposal.title]),
        el("p", { "data-testid": "candidate-concept-rationale" }, [proposal.rationale]),
      ]),
    ]);

    // adr/0016 decision 2: a single always-available "try again" control
    // that resends the currently displayed proposal's own kind, relying
    // only on the existing current-screen repeat demotion (ADR-0008
    // decision 2). It is not one of the labeled reProposalOptions lenses
    // and does not open the re-proposal dialog.
    var tryAgainButton = el(
      "button",
      {
        type: "button",
        "data-testid": "candidate-reproposal-try-again",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "reproposal-try-again",
      },
      ["もう一度探す"]
    );
    tryAgainButton.addEventListener("click", function () {
      requestProposal(currentProposalKind).then(function (result) {
        handleProposalResponse(result.status, result.body);
      });
    });

    var reproposalButton = el(
      "button",
      {
        type: "button",
        "data-testid": "candidate-reproposal-open",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "reproposal-open",
      },
      ["別の選び方でもう一度探す"]
    );
    reproposalButton.addEventListener("click", renderReproposalDialog);

    var conceptActions = el("div", { "class": "candidate-concept-actions" }, [
      tryAgainButton,
      reproposalButton,
    ]);
    conceptBanner.appendChild(conceptActions);
    content.appendChild(conceptBanner);

    // Candidate map + card list, one visual block (ADR-0012 skeleton block
    // 3). PC: cards are the primary column, the map is a narrower sticky
    // column on the right (human-approved 2026-08-06). Narrow width: a
    // single column with the map placed above the cards via CSS
    // grid-template-areas only (see home.html) -- not the "order" property
    // and not a DOM reorder -- so this is a presentational change only and
    // does not alter keyboard/reader traversal order.
    var mainLayout = el("div", { "class": "candidate-main-layout" }, []);

    var mapContainer = el("div", {
      "data-testid": "candidate-map",
      "data-map-tile-provider": "openstreetmap-standard",
    }, []);
    var mapWrapper = el("div", { "class": "candidate-map-wrapper" }, [
      mapContainer,
      el(
        "a",
        {
          "data-testid": "candidate-map-attribution",
          href: "https://www.openstreetmap.org/copyright",
          target: "_blank",
          rel: "noopener noreferrer",
        },
        ["© OpenStreetMap contributors"]
      ),
    ]);

    var decorated = proposal.candidates.map(function (candidate) {
      return { candidate: candidate, repeated: shownProviderPageUrls.has(candidate.providerPageUrl) };
    });
    // Ordering (every new candidate precedes every repeated one; existing
    // candidates are never excluded, only demoted) is computed server-side
    // from the previouslyShownProviderPageUrls this module echoed back
    // (adr/0017); this module renders proposal.candidates in exactly the
    // order the response returned, without re-sorting locally.
    // A repeat/new badge is only meaningful once at least one earlier
    // proposal has been shown this screen lifetime; the very first
    // proposal has nothing to compare against.
    var isReproposalRound = shownProviderPageUrls.size > 0;
    decorated.forEach(function (entry) {
      shownProviderPageUrls.add(entry.candidate.providerPageUrl);
    });

    var cardsContainer = el("div", { "data-testid": "candidate-proposal-cards" }, []);
    decorated.forEach(function (entry, index) {
      cardsContainer.appendChild(
        renderCard(entry.candidate, entry.repeated, index === 0, index, isReproposalRound)
      );
    });
    // DOM order is cards-then-map (matching the PC reading order, where
    // cards are primary) on purpose: CSS grid-template-areas is what moves
    // the map above the cards at narrow widths, so this DOM order is what
    // keyboard/reader users encounter at every width, regardless of which
    // block is painted first.
    mainLayout.appendChild(cardsContainer);
    mainLayout.appendChild(mapWrapper);
    content.appendChild(mainLayout);

    content.appendChild(
      el(
        "a",
        {
          "data-testid": "candidate-provider-credit",
          href: providerCredit.url,
          target: "_blank",
          rel: "noopener noreferrer",
        },
        [providerCredit.text]
      )
    );

    root.appendChild(content);
    initializeMap(mapContainer, decorated.map(function (entry) { return entry.candidate; }));
  }

  function handleProposalResponse(status, body) {
    if (status === 200) {
      currentOptions = body.reProposalOptions || [];
      if (body.proposal === null) {
        renderEmpty();
      } else {
        renderProposal(body.proposal, body.providerCredit);
      }
      return;
    }
    currentOptions = [];
    renderProblem(body.code, body.message);
  }

  document.addEventListener("DOMContentLoaded", function () {
    requestProposal(null)
      .then(function (result) {
        handleProposalResponse(result.status, result.body);
      })
      .catch(function () {
        renderProblem(
          "PROVIDER_UNAVAILABLE",
          "Candidate proposals cannot be retrieved right now. Please try again later."
        );
      });
  });
})();
