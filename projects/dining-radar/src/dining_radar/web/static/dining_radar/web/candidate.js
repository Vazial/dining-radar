/**
 * Candidate-proposal screen behaviour.
 *
 * Implements the browser control surface from
 * contracts/candidate-search-browser-interface.yaml against the public
 * contracts/candidate-search-api.yaml POST /candidate-proposals endpoint.
 *
 * Per adr/0020, the ConceptKind lens model (a re-proposal modal offering up
 * to three lenses, plus repeat demotion) is retired. This module instead
 * tracks one `currentFilters` object mirroring `CandidateFilters` and sends
 * it back unchanged for "try again" or updated for "change filters" -- both
 * are the same POST /candidate-proposals shape. The initial request omits
 * `filters` entirely (an empty body), per the contract's own
 * `CandidateProposalRequest` description. There is no shown-candidate
 * comparison state to track: adr/0020 decision 5 removes repeat demotion
 * outright (randomized pool sampling replaces it as the mechanism that keeps
 * responses from being identical every time).
 *
 * Per adr/0020 decision 10, the per-card dinnerBudgetTier label is the bare
 * tier word (低/中/高) only; the dinner-basis disclosure and yen-range
 * mapping live once in the static candidate-budget-tier-note element in
 * home.html, not here -- that element does not depend on any proposal
 * response, so it is server-rendered rather than produced by this script.
 */
(function () {
  "use strict";

  var root = document.getElementById("candidate-app");
  if (!root) {
    return;
  }

  var filterBar = document.getElementById("candidate-filter-bar");

  // adr/0019 (unchanged by adr/0020): visible labels for the coarse card
  // reference enums. These exact strings are the browser-interface
  // contract's own non-binding examples, reused verbatim.
  var CAPACITY_TIER_LABELS = { SMALL: "少なめ", MEDIUM: "標準", LARGE: "多め" };
  var NON_SMOKING_LABELS = { FULL: "全席禁煙", PARTIAL: "一部禁煙", NONE: "禁煙席なし" };
  // adr/0020 decision 10: the bare tier word only, used identically by the
  // card, the filter panel's budget-tier options, and (in home.html) the
  // screen-level candidate-budget-tier-note.
  var TIER_LABELS = { LOW: "低", MID: "中", HIGH: "高" };
  var BUDGET_TIERS = ["LOW", "MID", "HIGH"];
  // Genres shown before the "ほか N件…" overflow control. Real data carries
  // about ten genres, which cannot fit one row at 375px; four short labels plus the
  // overflow keeps the filter row's height fixed no matter how many the
  // provider returns.
  var GENRE_PREVIEW_COUNT = 4;
  // Mirrors recommendation.pipeline._DISPLAY_CAP, used only to phrase the
  // apply control honestly when more candidates match than can be displayed.
  var DISPLAY_CAP = 5;

  var currentFilters = defaultFilters();
  // The organizer's working copy. Editing a chip changes only this; nothing
  // is searched until the apply control is used, which is what the
  // "変更中（まだ検索しません）" note tells the reader.
  var pendingFilters = defaultFilters();
  var filterExpanded = false;
  var genreOverflowExpanded = false;
  var populationAttributes = [];
  var currentAvailableGenres = [];
  var cardElementsByRef = {};
  var markerElementsByRef = {};
  var leafletMap = null;

  function defaultFilters() {
    return {
      genres: [],
      includeIzakayaBar: false,
      nonSmokingOnly: false,
      cardPaymentOnly: false,
      budgetTiers: [],
    };
  }

  function cloneFilters(filters) {
    return {
      genres: filters.genres.slice(),
      includeIzakayaBar: filters.includeIzakayaBar,
      nonSmokingOnly: filters.nonSmokingOnly,
      cardPaymentOnly: filters.cardPaymentOnly,
      budgetTiers: filters.budgetTiers.slice(),
    };
  }

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

  function requestProposal(filters) {
    // The initial request (filters is null/undefined, nothing chosen yet)
    // sends an empty body -- CandidateProposalRequest's own description
    // ("Omit filters, or send it as {}, when opening the screen for the
    // first time"). Every later request ("try again" or "change filters")
    // sends the exact filters object currently in effect.
    var body = filters ? { filters: filters } : {};
    return fetch("/candidate-proposals", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json().then(function (responseBody) {
        return { status: response.status, body: responseBody };
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
    // Per ADR-0011 / candidate-search-browser-interface.yaml: a field whose
    // requiredFields entry declares rawValueAttribute carries the returned
    // value's canonical string on this same element when provided, kept
    // exactly equal to the API value even though the visible text
    // (`formatted`) may show a wholly different coarse label instead. The
    // attribute is omitted when unavailable, since data-value-state=
    // unavailable already expresses that.
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

  function selectCandidate(candidateRef, revealCard) {
    Object.keys(cardElementsByRef).forEach(function (ref) {
      var state = ref === candidateRef ? "selected" : "unselected";
      cardElementsByRef[ref].setAttribute("data-selection-state", state);
      if (markerElementsByRef[ref]) {
        markerElementsByRef[ref].setAttribute("data-selection-state", state);
      }
    });
    if (revealCard && cardElementsByRef[candidateRef]) {
      cardElementsByRef[candidateRef].scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }

  function renderCard(candidate, selected, index) {
    var card = el(
      "article",
      {
        "data-testid": "candidate-card",
        "data-candidate-ref": candidate.candidateRef,
        "data-selection-state": selected ? "selected" : "unselected",
        // adr/0020: unconditional on every card (unlike the conditional
        // payment-caution element below), so TDR-CS-13's ordering assertion
        // can distinguish cardPaymentAvailable=null from =true even though
        // neither shows the caution.
        "data-card-payment-value-state":
          candidate.cardPaymentAvailable === null ? "unavailable" : "provided",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-card-selection",
        role: "button",
        tabindex: "0",
      },
      []
    );
    card.addEventListener("click", function () {
      selectCandidate(candidate.candidateRef);
    });
    card.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCandidate(candidate.candidateRef, true);
      }
    });

    // Identification row: the same number the map marker shows (so a card
    // and its marker are visually tied together) and the genre as a small
    // chip.
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
        CAPACITY_TIER_LABELS[candidate.capacityTier],
        "data-raw-value"
      )
    );
    facts.appendChild(
      fieldRow(
        "禁煙対応",
        "candidate-card-non-smoking",
        candidate.nonSmokingStatus,
        NON_SMOKING_LABELS[candidate.nonSmokingStatus],
        "data-raw-value"
      )
    );
    // adr/0020 decision 10: the visible value is the bare tier word only
    // (no yen range, no "ディナー" wording) -- that disclosure lives once in
    // the static candidate-budget-tier-note element (home.html).
    facts.appendChild(
      fieldRow(
        "ディナー予算感",
        "candidate-card-dinner-budget",
        candidate.dinnerBudgetTier,
        TIER_LABELS[candidate.dinnerBudgetTier],
        "data-raw-value"
      )
    );
    card.appendChild(facts);

    // adr/0019 decision 5 (unchanged): present only when cardPaymentAvailable
    // is exactly false, stating only the confirmed fact -- never a "cash
    // only" claim.
    if (candidate.cardPaymentAvailable === false) {
      card.appendChild(
        el(
          "p",
          {
            "data-testid": "candidate-card-payment-caution",
            "data-card-payment-available": "false",
            "class": "candidate-payment-caution",
          },
          ["クレジットカードは利用できません"]
        )
      );
    }

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
    // or fitBounds runs, so it must happen before any marker is added below.
    if (latLngs.length > 0) {
      map.fitBounds(window.L.latLngBounds(latLngs), { padding: [24, 24] });
    } else {
      map.setView([0, 0], 2);
    }

    candidates.forEach(function (candidate, index) {
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
        selectCandidate(candidate.candidateRef, true);
      });
      markerElementsByRef[candidate.candidateRef] = markerEl;
    });

    container.setAttribute("data-map-fit-state", "displayed-candidates");
    leafletMap = map;
  }

  function setMembership(list, value, included) {
    var index = list.indexOf(value);
    if (included && index === -1) {
      list.push(value);
    } else if (!included && index !== -1) {
      list.splice(index, 1);
    }
  }

  function sameFilters(a, b) {
    return (
      a.includeIzakayaBar === b.includeIzakayaBar &&
      a.nonSmokingOnly === b.nonSmokingOnly &&
      a.cardPaymentOnly === b.cardPaymentOnly &&
      a.genres.slice().sort().join("|") === b.genres.slice().sort().join("|") &&
      a.budgetTiers.slice().sort().join("|") === b.budgetTiers.slice().sort().join("|")
    );
  }

  // Mirrors dining_radar.recommendation.pipeline.filter_candidates exactly,
  // including its soft-filter rule: a candidate whose value for an active
  // filter is unknown is NOT removed (adr/0020 decision 2 / TDR-CS-13). This
  // is the one place the server's predicate is duplicated in the browser; it
  // exists so a pending selection's match count can be shown before the
  // organizer commits it, without a provider request per toggle. If the two
  // ever disagree, the number on the apply control lies -- an acceptance test
  // must compare this count against the count the server actually returns.
  function countMatchingPopulation(filters) {
    var rows = populationAttributes;
    if (!filters.includeIzakayaBar) {
      rows = rows.filter(function (row) {
        return !row.defaultExcluded;
      });
    }
    if (filters.genres.length) {
      rows = rows.filter(function (row) {
        return filters.genres.indexOf(row.genre) !== -1;
      });
    }
    if (filters.nonSmokingOnly) {
      rows = rows.filter(function (row) {
        return row.nonSmokingStatus !== "NONE";
      });
    }
    if (filters.cardPaymentOnly) {
      rows = rows.filter(function (row) {
        return row.cardPaymentAvailable !== false;
      });
    }
    if (filters.budgetTiers.length) {
      rows = rows.filter(function (row) {
        return (
          row.dinnerBudgetTier === null ||
          row.dinnerBudgetTier === undefined ||
          filters.budgetTiers.indexOf(row.dinnerBudgetTier) !== -1
        );
      });
    }
    return rows.length;
  }

  function filterSummaryText(filters) {
    var parts = [];
    if (filters.genres.length) {
      parts.push(filters.genres.join("・"));
    }
    if (filters.nonSmokingOnly) {
      parts.push("禁煙");
    }
    if (filters.cardPaymentOnly) {
      parts.push("カード利用不可を除く");
    }
    if (filters.budgetTiers.length) {
      parts.push(
        "ディナー予算 " +
          BUDGET_TIERS.filter(function (tier) {
            return filters.budgetTiers.indexOf(tier) !== -1;
          })
            .map(function (tier) {
              return TIER_LABELS[tier];
            })
            .join("・")
      );
    }
    if (filters.includeIzakayaBar) {
      parts.push("居酒屋等も含む");
    }
    return parts.length ? parts.join("・") : "居酒屋・バーを除く";
  }

  // A pill-shaped toggle. `pressed` drives both the visual state and
  // aria-pressed, so the control reports its own state rather than relying on
  // colour alone.
  function chip(options) {
    var button = el(
      "button",
      {
        type: "button",
        "class": "candidate-chip",
        "data-testid": options.testId,
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": options.purpose,
        "aria-pressed": options.pressed ? "true" : "false",
        "data-pressed": options.pressed ? "true" : "false",
      },
      [options.label]
    );
    if (options.value !== undefined) {
      button.setAttribute(options.valueAttribute, options.value);
    }
    button.addEventListener("click", function () {
      options.onToggle(!options.pressed);
    });
    return button;
  }

  function chipRow(label, chips) {
    return el("div", { "class": "candidate-filter-row" }, [
      el("span", { "class": "candidate-filter-row-label" }, [label]),
      el("div", { "class": "candidate-filter-row-chips" }, chips),
    ]);
  }

  function genreChips() {
    // The provider order is not a presentation order. Surface the compact,
    // familiar labels first so the closed preview remains useful on a phone.
    var orderedGenres = currentAvailableGenres.slice().sort(function (left, right) {
      return left.length - right.length || left.localeCompare(right, "ja");
    });
    var visible = genreOverflowExpanded
      ? orderedGenres
      : orderedGenres.slice(0, GENRE_PREVIEW_COUNT);
    var chips = visible.map(function (genre) {
      return chip({
        testId: "candidate-filter-genre-option",
        purpose: "candidate-filter-genre-selection",
        label: genre,
        pressed: pendingFilters.genres.indexOf(genre) !== -1,
        value: genre,
        valueAttribute: "data-genre-value",
        onToggle: function (next) {
          setMembership(pendingFilters.genres, genre, next);
          renderFilterBar();
        },
      });
    });
    var hidden = orderedGenres.length - visible.length;
    if (hidden > 0 || genreOverflowExpanded) {
      var overflow = el(
        "button",
        {
          type: "button",
          "class": "candidate-chip candidate-chip-quiet",
          "data-testid": "candidate-filter-genre-overflow",
          "data-candidate-control-category": "button",
          "data-candidate-control-purpose": "candidate-filter-genre-overflow-toggle",
        },
        [genreOverflowExpanded ? "閉じる" : "ほか " + hidden + "件…"]
      );
      overflow.addEventListener("click", function () {
        genreOverflowExpanded = !genreOverflowExpanded;
        renderFilterBar();
      });
      chips.push(overflow);
    }
    return chips;
  }

  function applyControlLabel(matchCount) {
    if (matchCount === 0) {
      return "該当なし";
    }
    if (matchCount <= DISPLAY_CAP) {
      return matchCount + "件を表示";
    }
    return matchCount + "件中" + DISPLAY_CAP + "件を表示";
  }

  function applyPendingFilters() {
    currentFilters = cloneFilters(pendingFilters);
    filterExpanded = false;
    genreOverflowExpanded = false;
    renderFilterBar();
    requestProposal(currentFilters).then(function (result) {
      handleProposalResponse(result.status, result.body);
    });
  }

  function filterFocusTarget() {
    var active = document.activeElement;
    if (!active || !filterBar.contains(active)) {
      return null;
    }
    return {
      testId: active.getAttribute("data-testid"),
      genre: active.getAttribute("data-genre-value"),
      tier: active.getAttribute("data-budget-tier-value"),
    };
  }

  function restoreFilterFocus(target) {
    if (!target || !target.testId) {
      return;
    }
    var selector = '[data-testid="' + target.testId + '"]';
    if (target.genre) {
      selector += '[data-genre-value="' + target.genre + '"]';
    }
    if (target.tier) {
      selector += '[data-budget-tier-value="' + target.tier + '"]';
    }
    var control = filterBar.querySelector(selector);
    if (control) {
      control.focus();
    }
  }

  function renderFilterBar(restoreFocus) {
    var focusTarget = restoreFocus || filterFocusTarget();
    var dirty = !sameFilters(pendingFilters, currentFilters);
    filterBar.innerHTML = "";
    filterBar.setAttribute("data-filter-expanded", filterExpanded ? "true" : "false");
    filterBar.setAttribute("data-filter-dirty", dirty ? "true" : "false");

    var summaryTexts = [
      el("span", { "class": "candidate-filter-summary-text" }, [
        filterSummaryText(currentFilters),
      ]),
    ];
    if (dirty) {
      summaryTexts.push(
        el(
          "span",
          {
            "class": "candidate-filter-pending",
            "data-testid": "candidate-filter-pending-note",
          },
          ["変更中（まだ検索しません）"]
        )
      );
    }

    var summary = el(
      "button",
      {
        type: "button",
        "class": "candidate-filter-summary",
        "data-testid": "candidate-filter-toggle",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-filter-toggle",
        "aria-expanded": filterExpanded ? "true" : "false",
      },
      [
        el("span", { "class": "candidate-filter-summary-body" }, summaryTexts),
        el("span", { "class": "candidate-filter-caret", "aria-hidden": "true" }, [
          filterExpanded ? "⌃" : "⌄",
        ]),
      ]
    );
    summary.addEventListener("click", function () {
      filterExpanded = !filterExpanded;
      renderFilterBar();
    });

    var searchAgain = el(
      "button",
      {
        type: "button",
        "class": "candidate-search-again",
        "data-testid": "candidate-search-again",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-search-again",
      },
      ["もう一度探す"]
    );
    searchAgain.addEventListener("click", function () {
      requestProposal(currentFilters).then(function (result) {
        handleProposalResponse(result.status, result.body);
      });
    });
    searchAgain.disabled = dirty;

    filterBar.appendChild(
      el("div", { "class": "candidate-filter-head" }, [summary, searchAgain])
    );

    if (!filterExpanded) {
      return;
    }

    var panel = el(
      "div",
      { "class": "candidate-filter-panel", "data-testid": "candidate-filter-panel" },
      [
        chipRow("ジャンル", genreChips()),
        chipRow("こだわり", [
          chip({
            testId: "candidate-filter-non-smoking-only",
            purpose: "candidate-filter-non-smoking-toggle",
            label: "禁煙席あり",
            pressed: pendingFilters.nonSmokingOnly,
            onToggle: function (next) {
              pendingFilters.nonSmokingOnly = next;
              renderFilterBar();
            },
          }),
          chip({
            testId: "candidate-filter-card-payment-only",
            purpose: "candidate-filter-card-payment-toggle",
            label: "カード利用不可を除く",
            pressed: pendingFilters.cardPaymentOnly,
            onToggle: function (next) {
              pendingFilters.cardPaymentOnly = next;
              renderFilterBar();
            },
          }),
          chip({
            testId: "candidate-filter-include-izakaya-bar",
            purpose: "candidate-filter-izakaya-bar-toggle",
            label: "居酒屋等も含む",
            pressed: pendingFilters.includeIzakayaBar,
            onToggle: function (next) {
              pendingFilters.includeIzakayaBar = next;
              renderFilterBar();
            },
          }),
        ]),
        chipRow(
          "ディナー予算感",
          BUDGET_TIERS.map(function (tier) {
            return chip({
              testId: "candidate-filter-budget-tier-option",
              purpose: "candidate-filter-budget-tier-selection",
              label: TIER_LABELS[tier],
              pressed: pendingFilters.budgetTiers.indexOf(tier) !== -1,
              value: tier,
              valueAttribute: "data-budget-tier-value",
              onToggle: function (next) {
                setMembership(pendingFilters.budgetTiers, tier, next);
                renderFilterBar();
              },
            });
          })
        ),
      ]
    );

    var matchCount = countMatchingPopulation(pendingFilters);
    var apply = el(
      "button",
      {
        type: "button",
        "class": "candidate-filter-apply",
        "data-testid": "candidate-filter-apply",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-filter-apply",
        "data-match-count": String(matchCount),
      },
      [applyControlLabel(matchCount)]
    );
    if (matchCount === 0 || !dirty) {
      apply.disabled = true;
    }
    apply.addEventListener("click", applyPendingFilters);

    var actions = [apply];
    if (dirty) {
      var revert = el(
        "button",
        {
          type: "button",
          "class": "candidate-filter-revert",
          "data-testid": "candidate-filter-revert",
          "data-candidate-control-category": "button",
          "data-candidate-control-purpose": "candidate-filter-revert",
        },
        ["変更を戻す"]
      );
      revert.addEventListener("click", function () {
        pendingFilters = cloneFilters(currentFilters);
        renderFilterBar();
      });
      actions.unshift(revert);
    }
    panel.appendChild(el("div", { "class": "candidate-filter-actions" }, actions));
    // adr/0020 decision 10, revised on human instruction 2026-08-10: the
    // dinner-basis disclosure stays (TDR-CS-02 requires the organizer be able
    // to tell the figure is a dinner one) but the yen mapping is gone and the
    // note now lives inside the filter panel, next to the budget control it
    // qualifies, rather than occupying the top of the screen.
    panel.appendChild(
      el(
        "p",
        {
          "class": "candidate-budget-tier-note",
          "data-testid": "candidate-budget-tier-note",
        },
        ["ディナー予算をもとにした目安です。ランチ価格を示すものではありません。"]
      )
    );

    filterBar.appendChild(panel);
    restoreFilterFocus(focusTarget);
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

  function renderResult(body) {
    cardElementsByRef = {};
    root.innerHTML = "";

    // The filter bar is not part of this element: it lives outside the
    // response-driven region so it stays reachable across the success,
    // no-results, and problem outcomes alike (TDR-CS-05's "絞り込み条件を
    // 変更するよう案内される" needs the controls to survive an empty result).
    var content = el("section", { "data-testid": "candidate-proposal-content" }, []);

    // adr/0020 decision 6: disclose both that the default izakaya/bar
    // exclusion was set aside for this response and that included shops'
    // lunch service is not confirmed.
    if (body.izakayaBarFallbackApplied) {
      content.appendChild(
        el(
          "p",
          {
            "data-testid": "candidate-izakaya-bar-fallback-notice",
            "class": "candidate-fallback-notice",
          },
          [
            "条件に合う候補がなかったため、居酒屋・バーなどランチ営業の実施を確認しづらい" +
              "店舗も含めて表示しています。含まれた店舗が実際にランチ営業しているとは限らない" +
              "ため、営業時間は店舗ページでご確認ください。",
          ]
        )
      );
    }

    if (!body.candidates || body.candidates.length === 0) {
      content.appendChild(
        el("section", { "data-testid": "candidate-no-results" }, [
          "絞り込み条件に合うランチ候補が見つかりませんでした。絞り込み条件を変更してお試しください。",
        ])
      );
      root.appendChild(content);
      return;
    }

    var mainLayout = el("div", { "class": "candidate-main-layout" }, []);

    var mapContainer = el(
      "div",
      { "data-testid": "candidate-map", "data-map-tile-provider": "openstreetmap-standard" },
      []
    );
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

    var cardsContainer = el("div", { "data-testid": "candidate-proposal-cards" }, []);
    body.candidates.forEach(function (candidate, index) {
      cardsContainer.appendChild(renderCard(candidate, index === 0, index));
    });
    // DOM order is cards-then-map (matching the PC reading order, where
    // cards are primary) on purpose: CSS grid-template-areas is what moves
    // the map above the cards at narrow widths (see home.html), so this DOM
    // order is what keyboard/reader users encounter at every width.
    mainLayout.appendChild(cardsContainer);
    mainLayout.appendChild(mapWrapper);
    content.appendChild(mainLayout);

    content.appendChild(
      el(
        "a",
        {
          "data-testid": "candidate-provider-credit",
          href: body.providerCredit.url,
          target: "_blank",
          rel: "noopener noreferrer",
        },
        [body.providerCredit.text]
      )
    );

    root.appendChild(content);
    initializeMap(mapContainer, body.candidates);
  }

  function handleProposalResponse(status, body) {
    if (status === 200) {
      currentAvailableGenres = body.availableGenres || [];
      populationAttributes = body.populationAttributes || [];
      pendingFilters = cloneFilters(currentFilters);
      renderFilterBar();
      renderResult(body);
      return;
    }
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
