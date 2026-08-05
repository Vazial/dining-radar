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
  var selectedReproposalKind = null;
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
    return fetch("/candidate-proposals", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(reproposalKind ? { reproposalKind: reproposalKind } : {}),
    }).then(function (response) {
      return response.json().then(function (body) {
        return { status: response.status, body: body };
      });
    });
  }

  function fieldRow(label, testId, value, formatted, rawValueAttribute) {
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
        [provided ? (formatted !== undefined ? formatted : String(value)) : "情報なし"]
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

  function renderCard(candidate, repeated, selected) {
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

    card.appendChild(
      el(
        "h3",
        { "data-testid": "candidate-card-name", "data-field-label": "店名", "data-value-state": "provided" },
        [candidate.name]
      )
    );
    card.appendChild(
      el(
        "p",
        { "data-testid": "candidate-card-genre", "data-field-label": "ジャンル", "data-value-state": "provided" },
        [candidate.genre]
      )
    );

    var facts = el("dl", {}, []);
    facts.appendChild(fieldRow("紹介", "candidate-card-description", candidate.description));
    facts.appendChild(fieldRow("営業時間", "candidate-card-business-hours", candidate.businessHours));
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
      var icon = window.L.divIcon({ className: "candidate-map-marker-icon", html: "" });
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
      markerEl.textContent = String(index + 1);
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
    selectedReproposalKind = null;

    var submitButton = el(
      "button",
      {
        type: "button",
        "data-testid": "candidate-reproposal-submit",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "reproposal-submit",
        disabled: true,
      },
      ["この切り口で再提案"]
    );
    submitButton.addEventListener("click", function () {
      if (!selectedReproposalKind) {
        return;
      }
      requestProposal(selectedReproposalKind).then(function (result) {
        closeReproposalDialog();
        handleProposalResponse(result.status, result.body);
      });
    });

    var optionButtons = currentOptions.map(function (option) {
      var button = el(
        "button",
        {
          type: "button",
          "data-testid": "candidate-reproposal-option",
          "data-reproposal-kind": option.kind,
          "data-candidate-control-category": "button",
          "data-candidate-control-purpose": "reproposal-selection",
          "aria-pressed": "false",
        },
        [el("strong", {}, [option.title]), el("p", {}, [option.rationale])]
      );
      button.addEventListener("click", function () {
        selectedReproposalKind = option.kind;
        optionButtons.forEach(function (candidateButton) {
          candidateButton.setAttribute("aria-pressed", candidateButton === button ? "true" : "false");
        });
        submitButton.removeAttribute("disabled");
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
      [el("div", {}, optionButtons), submitButton, cancelButton]
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
        "この切り口に合うランチ候補が見つかりませんでした。",
      ])
    );
  }

  function renderProposal(proposal, providerCredit) {
    cardElementsByRef = {};
    root.innerHTML = "";

    var content = el("section", { "data-testid": "candidate-proposal-content" }, []);

    content.appendChild(
      el("div", {}, [
        el("h2", { "data-testid": "candidate-concept-title" }, [proposal.title]),
        el("p", { "data-testid": "candidate-concept-rationale" }, [proposal.rationale]),
      ])
    );

    var reproposalButton = el(
      "button",
      {
        type: "button",
        "data-testid": "candidate-reproposal-open",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "reproposal-open",
      },
      ["別の切り口で再提案"]
    );
    reproposalButton.addEventListener("click", renderReproposalDialog);
    content.appendChild(reproposalButton);

    var mapContainer = el("div", {
      "data-testid": "candidate-map",
      "data-map-tile-provider": "openstreetmap-standard",
    }, []);
    content.appendChild(mapContainer);

    content.appendChild(
      el(
        "a",
        {
          "data-testid": "candidate-map-attribution",
          href: "https://www.openstreetmap.org/copyright",
          target: "_blank",
          rel: "noopener noreferrer",
        },
        ["© OpenStreetMap contributors"]
      )
    );

    var decorated = proposal.candidates.map(function (candidate) {
      return { candidate: candidate, repeated: shownProviderPageUrls.has(candidate.providerPageUrl) };
    });
    // Every new card precedes every repeated card; existing candidates are
    // never excluded (contracts/test-support-api.yaml NORMAL_WITH_REPEAT).
    decorated.sort(function (a, b) {
      if (a.repeated === b.repeated) {
        return 0;
      }
      return a.repeated ? 1 : -1;
    });
    decorated.forEach(function (entry) {
      shownProviderPageUrls.add(entry.candidate.providerPageUrl);
    });

    var cardsContainer = el("div", { "data-testid": "candidate-proposal-cards" }, []);
    decorated.forEach(function (entry, index) {
      cardsContainer.appendChild(renderCard(entry.candidate, entry.repeated, index === 0));
    });
    content.appendChild(cardsContainer);

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
