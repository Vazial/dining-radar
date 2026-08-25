/**
 * Candidate-proposal screen behaviour.
 *
 * Implements the browser control surface from
 * contracts/candidate-search-browser-interface.yaml against the public
 * contracts/candidate-search-api.yaml POST /candidate-proposals endpoint.
 *
 * Per adr/0023, the ConceptKind lens model (a re-proposal modal offering up
 * to three lenses, plus repeat demotion) is retired. This module instead
 * tracks one `currentFilters` object mirroring `CandidateFilters` and sends
 * it back unchanged for "try again" or updated for "change filters" -- both
 * are the same POST /candidate-proposals shape. The initial request omits
 * `filters` entirely (an empty body), per the contract's own
 * `CandidateProposalRequest` description. adr/0023 decision 5 removed the
 * former repeat-demotion mechanism outright, relying on randomized selection
 * alone to keep responses from being identical every time; adr/0024 decision
 * 4 partially restores shown-candidate tracking, but on the browser side and
 * priority-only: `shownCandidateMemory` (a `sessionStorage`-held,
 * tab-lifetime-and-20-hour-bounded set of previously shown
 * `providerPageUrl` values, see `readShownCandidateMemory` /
 * `writeShownCandidateMemory` / `updateShownCandidateMemory` below) is sent
 * as `shownProviderPageUrls` on every request so the server can prioritize
 * (never exclude) not-yet-shown candidates.
 *
 * Per adr/0023 decision 10, the per-card dinnerBudgetTier label is the bare
 * tier word (低/中/高) only; the dinner-basis disclosure and yen-range
 * mapping live once in the static candidate-budget-tier-note element in
 * home.html, not here -- that element does not depend on any proposal
 * response, so it is server-rendered rather than produced by this script.
 *
 * Per adr/0025, the response also carries `searchOrigin` (the private search
 * origin's coordinates, for map display only) and each candidate's
 * `walkingTimeMinutes` (an estimate, never a measured route). This module
 * renders the origin as a read-only map marker plus a small set of
 * walking-time rings around it (WALKING_TIME_MAX_PRESETS_MINUTES below,
 * which must stay in exact agreement with
 * `dining_radar.recommendation.pipeline.WALKING_TIME_MAX_PRESET_MINUTES` --
 * see that constant's own docstring for why), and adds a hard
 * `walkingTimeMaxMinutes` filter alongside the existing ones. Unlike
 * `nonSmokingOnly`/`cardPaymentOnly`/`budgetTiers`, this filter has no
 * soft/unconfirmed case in `passesNonExclusionFilters` below, because
 * walking time is never unavailable (adr/0025 decision 3).
 *
 * Per human decision 2026-08-23 (TDR-CS-16), a fetch failure that follows an
 * already-displayed proposal must retain that proposal (cards, map, applied
 * filters, condition summary) rather than replace or clear it; the error is
 * shown in addition to, not instead of, what was already on screen. See
 * `hasDisplayedProposal` / `renderProblem` / `applyPendingFilters` below.
 */
(function () {
  "use strict";

  var root = document.getElementById("candidate-app");
  if (!root) {
    return;
  }

  var filterBar = document.getElementById("candidate-filter-bar");

  // adr/0019 (unchanged by adr/0023): visible labels for the coarse card
  // reference enums. These exact strings are the browser-interface
  // contract's own non-binding examples, reused verbatim.
  var CAPACITY_TIER_LABELS = { SMALL: "少なめ", MEDIUM: "標準", LARGE: "多め" };
  var NON_SMOKING_LABELS = { FULL: "全席禁煙", PARTIAL: "一部禁煙", NONE: "禁煙席なし" };
  // adr/0023 decision 10: the bare tier word only, used identically by the
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
  // adr/0025 decision 3: mirrors
  // dining_radar.recommendation.pipeline.WALKING_TIME_MAX_PRESET_MINUTES
  // exactly -- the browser's offered walking-time-max options and the
  // server's PopulationAttribute.walkingTimeBand bucketing must agree on the
  // same preset set for countMatchingPopulation's local prediction to stay
  // correct (see that Python constant's own docstring for the full
  // reasoning; the API schema cannot enforce this agreement structurally).
  // Also reused to draw one walking-radius ring per preset around the
  // search-origin marker, smallest first (ring styling below relies on this
  // ascending order).
  var WALKING_TIME_MAX_PRESETS_MINUTES = [10, 15, 20, 30];
  // Mirrors recommendation.pipeline.WALKING_METERS_PER_MINUTE exactly (the
  // walking-speed convention Japan's real-estate fair-competition rules fix
  // for "徒歩1分" figures), used only to convert a preset minute count into
  // a ring radius in meters for display -- never to recompute a candidate's
  // own walkingTimeMinutes, which the server always supplies.
  var WALKING_METERS_PER_MINUTE = 80;
  // adr/0029 decision 1-2/4: mirrors
  // dining_radar.recommendation.pipeline.WALKING_DETOUR_FACTOR exactly. The
  // server's walking_time_minutes() (which every ring/card/filter figure is
  // ultimately derived from) multiplies a straight-line distance by this
  // factor before dividing by WALKING_METERS_PER_MINUTE; this module cannot
  // call that Python function directly, so it mirrors both constants here to
  // draw a ring radius that matches the server's own walking-time estimate
  // (this is the same manual cross-module synchronization responsibility
  // WALKING_TIME_MAX_PRESETS_MINUTES above already carries -- see
  // pipeline.walking_time_minutes's own docstring for the developer
  // obligation this creates).
  var WALKING_DETOUR_FACTOR = 1.3;
  // Used only to place a walking-radius ring's visible minute label at a
  // point on the ring's own circumference (due north of the search origin,
  // the same small-scale equirectangular approximation
  // recommendation.pipeline._distance uses server-side) -- never to compute
  // a ring's radius itself, which Leaflet's L.circle already accepts
  // directly in meters.
  var METERS_PER_DEGREE_LATITUDE = 111320;

  // adr/0030 decision 1 + designer's ring-legibility guidance: each ring's
  // dash pattern/opacity step down from solid (innermost, easiest to reach)
  // to dotted (outermost), so a reader can tell rings apart by look alone
  // even before reading a label. Indexed by position in
  // WALKING_TIME_MAX_PRESETS_MINUTES (ascending radius); the last entry
  // repeats for any preset beyond this table's length.
  var WALKING_RADIUS_RING_STYLE_BY_BAND_INDEX = [
    { className: "candidate-walking-radius-ring-path--band-0" },
    { className: "candidate-walking-radius-ring-path--band-1" },
    { className: "candidate-walking-radius-ring-path--band-2" },
    { className: "candidate-walking-radius-ring-path--band-3" },
  ];
  var WALKING_RADIUS_RING_BASE_WEIGHT = 1.8;
  var WALKING_RADIUS_RING_CASING_EXTRA_WEIGHT = 3;
  var WALKING_RADIUS_RING_ACCENT_WEIGHT = 2.4;
  // Nudge margin (pixels) a ring's label is kept inside the visible map
  // container by, so a label is never clipped flush against the edge.
  var WALKING_RADIUS_RING_LABEL_MARGIN_PX = 20;

  // Layers this module adds beyond candidate/origin markers (walking-radius
  // ring paths, their white casings, minute labels, and the innermost-band
  // tint) -- tracked so a later re-layout (map resize, e.g. opening/closing
  // the full-screen map sheet) can clear and redraw them against the map's
  // new size, and so a fresh initializeMap call starts from none.
  var walkingRadiusRingLayers = [];
  var walkingRadiusRingOrigin = null;
  var currentMapLatLngs = [];
  var originMarkerEl = null;

  // adr/0024 decision 4 item 8: shownCandidateMemory's sessionStorage key and
  // retention bound. 20 hours (not the regulatory ceiling of 24) leaves a
  // margin for clock skew and request round-trip time -- see
  // candidate-search-browser-interface.yaml's shownCandidateMemory.expiry.
  var SHOWN_CANDIDATE_MEMORY_KEY = "dining-radar:shown-provider-page-urls";
  var SHOWN_CANDIDATE_MEMORY_MAX_AGE_MS = 20 * 60 * 60 * 1000;

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
  // Tracks the ResizeObserver watching the current map container so a later
  // re-render (a fresh initializeMap call, e.g. after applying filters or
  // "search again") can disconnect it before the container it was observing
  // is discarded. See initializeMap's resize handling below for what this
  // covers beyond Leaflet's own built-in window-resize handling.
  var mapResizeObserver = null;
  // TDR-CS-16 (human decision 2026-08-23): whether a proposal has ever been
  // successfully displayed in this page load. While true, a later fetch
  // failure must retain the existing cards/map/filters rather than clear
  // them (see renderProblem's `additive` parameter and
  // applyPendingFilters/handleProposalResponse below).
  var hasDisplayedProposal = false;

  // Task 3 (designer): list-primary + 88px map ribbon + tap-to-open
  // full-screen map sheet, one Leaflet map instance throughout (the same
  // [data-testid="candidate-map"] element/instance is simply resized by CSS
  // -- see initializeMap's ResizeObserver and openMapSheet/closeMapSheet
  // below). mapSheetOpen tracks which of the two states the map is
  // currently in; selectedCandidateRef mirrors the currently selected
  // candidate outside of selectCandidate's own DOM bookkeeping so the sheet
  // knows who to show/center on; latLngByRef lets the sheet re-center
  // without re-deriving a candidate's coordinates. orderedCardElements/
  // cardsContainerEl/mapSheetPanelEl support moving the single selected
  // candidate-card element (never cloning/duplicating it -- see
  // syncMapSheetPanelToSelection) between the list and the sheet.
  var mapSheetOpen = false;
  var selectedCandidateRef = null;
  var latLngByRef = {};
  var orderedCardElements = [];
  var cardsContainerEl = null;
  var mapWrapperEl = null;
  var mapSheetPanelEl = null;
  var mapSheetCounterEl = null;
  // The element focus should return to when the sheet closes -- whichever
  // control opened it (the ribbon, or a marker tapped while it was
  // reachable) -- so closing the sheet does not strand keyboard focus on a
  // now-detached/moved element.
  var sheetCloseFocusTarget = null;

  function defaultFilters() {
    return {
      genres: [],
      includeIzakayaBar: false,
      nonSmokingOnly: false,
      cardPaymentOnly: false,
      budgetTiers: [],
      walkingTimeMaxMinutes: null,
    };
  }

  function cloneFilters(filters) {
    return {
      genres: filters.genres.slice(),
      includeIzakayaBar: filters.includeIzakayaBar,
      nonSmokingOnly: filters.nonSmokingOnly,
      cardPaymentOnly: filters.cardPaymentOnly,
      budgetTiers: filters.budgetTiers.slice(),
      walkingTimeMaxMinutes: filters.walkingTimeMaxMinutes,
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

  // adr/0024 decision 4 item 8 (shownCandidateMemory): reads sessionStorage's
  // raw {url, storedAt} entries, discarding anything malformed or older than
  // SHOWN_CANDIDATE_MEMORY_MAX_AGE_MS using the browser's own local clock.
  // Never throws -- a missing/unavailable sessionStorage (private browsing,
  // quota, a non-browser test harness) degrades to "no memory", which is
  // safe: it only ever makes the not-yet-shown partition larger, never
  // smaller (candidate-search-browser-interface.yaml's shownCandidateMemory
  // .expiry.rule).
  function readShownCandidateMemory() {
    var raw;
    try {
      raw = window.sessionStorage.getItem(SHOWN_CANDIDATE_MEMORY_KEY);
    } catch (error) {
      return [];
    }
    if (!raw) {
      return [];
    }
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      return [];
    }
    if (!Array.isArray(parsed)) {
      return [];
    }
    var now = Date.now();
    return parsed.filter(function (entry) {
      return (
        entry &&
        typeof entry.url === "string" &&
        typeof entry.storedAt === "number" &&
        now - entry.storedAt < SHOWN_CANDIDATE_MEMORY_MAX_AGE_MS
      );
    });
  }

  function writeShownCandidateMemory(entries) {
    try {
      window.sessionStorage.setItem(SHOWN_CANDIDATE_MEMORY_KEY, JSON.stringify(entries));
    } catch (error) {
      // sessionStorage unavailable: the not-yet-shown priority feature
      // silently degrades to "always empty memory", which never blocks a
      // proposal request.
    }
  }

  // requestRule (candidate-search-browser-interface.yaml shownCandidateMemory):
  // every request first prunes expired entries -- discarding them from the
  // stored set itself, not merely skipping them for this one read -- then
  // sends only the surviving url values.
  function currentShownProviderPageUrls() {
    var surviving = readShownCandidateMemory();
    writeShownCandidateMemory(surviving);
    return surviving.map(function (entry) {
      return entry.url;
    });
  }

  // updateRule: after a successful response, prune expired entries, clear
  // everything first if shownPoolExhausted is true (adr/0024 decision 4), then
  // add this response's candidates' providerPageUrl values with a fresh
  // storedAt, deduplicated by url (the newest storedAt wins).
  function updateShownCandidateMemory(body) {
    var surviving = body.shownPoolExhausted ? [] : readShownCandidateMemory();
    var byUrl = {};
    surviving.forEach(function (entry) {
      byUrl[entry.url] = entry;
    });
    var now = Date.now();
    (body.candidates || []).forEach(function (candidate) {
      byUrl[candidate.providerPageUrl] = { url: candidate.providerPageUrl, storedAt: now };
    });
    writeShownCandidateMemory(
      Object.keys(byUrl).map(function (url) {
        return byUrl[url];
      })
    );
  }

  function requestProposal(filters) {
    // The initial request (filters is null/undefined, nothing chosen yet)
    // sends an empty body -- CandidateProposalRequest's own description
    // ("Omit filters, or send it as {}, when opening the screen for the
    // first time"). Every later request ("try again" or "change filters")
    // sends the exact filters object currently in effect. Every request
    // additionally attaches the surviving shownCandidateMemory set as
    // shownProviderPageUrls, omitted when empty (adr/0024 decision 4) -- this
    // is what makes even the very first request after a same-tab reload
    // shown-state aware.
    var body = filters ? { filters: filters } : {};
    var shownProviderPageUrls = currentShownProviderPageUrls();
    if (shownProviderPageUrls.length > 0) {
      body.shownProviderPageUrls = shownProviderPageUrls;
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
      return response.json().then(function (responseBody) {
        return { status: response.status, body: responseBody };
      });
    });
  }

  function fieldRow(
    label,
    testId,
    value,
    formatted,
    rawValueAttribute,
    unavailableText,
    compactLabel
  ) {
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
    return el("div", { "class": "candidate-fact-row candidate-fact-row--" + testId }, [
      el("dt", {}, [compactLabel || label]),
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
    selectedCandidateRef = candidateRef;
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
    // Task 3: inside the full-screen map sheet, the sheet always shows
    // exactly the currently selected candidate (designer: "選択中の1店だけ
    // を残す") -- switching which pin is selected (or, outside the sheet,
    // which card) keeps the sheet's single-candidate panel in sync without
    // duplicating any candidate-card element (see syncMapSheetPanelToSelection).
    if (mapSheetOpen) {
      syncMapSheetPanelToSelection();
      refreshMapViewAndRings();
    }
  }

  function renderCard(candidate, selected, index) {
    var card = el(
      "article",
      {
        "data-testid": "candidate-card",
        "data-candidate-ref": candidate.candidateRef,
        "data-selection-state": selected ? "selected" : "unselected",
        // adr/0023: unconditional on every card (unlike the conditional
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

    // Design realignment (human real-device report 2026-08-25, E:\AWS    // dsg-out\Main.dc.html's own .card markup): the id row carries the
    // badge, the shop name itself, and the walking-time estimate as a
    // trailing chip, all on one line -- not just the badge with genre
    // trailing it. Genre moves to its own plain-text line (no chip)
    // directly above the description, and walking time moves out of the
    // facts grid entirely (into this row's chip), leaving the facts grid
    // exactly the four/three items the design's own 2-column grid shows.
    var idRow = el("div", { "class": "candidate-card-id-row" }, [
      el("span", { "class": "candidate-marker-badge", "aria-hidden": "true" }, [String(index + 1)]),
      el(
        "h3",
        {
          "data-testid": "candidate-card-name",
          "data-field-label": "店名",
          "data-value-state": "provided",
          "class": "candidate-shop-name",
        },
        [candidate.name]
      ),
      el("span", { "class": "candidate-card-id-row-spacer", "aria-hidden": "true" }, []),
      // adr/0025 decision 2: always provided (never "情報なし" -- walking
      // time is always computable from the response's own searchOrigin and
      // this candidate's location), so no rawValueAttribute is declared --
      // the visible value and the raw response number are the same value,
      // unlike totalSeats/nonSmokingStatus/dinnerBudgetTier's coarse-label
      // translations below. The leading "約" is the required estimate-
      // wording signal (candidate-search-browser-interface.yaml's
      // walkingTimeEstimateWording): this is an estimate, not a measured
      // route. Contract only fixes this element's own testid/field-label/
      // value-state/text -- not that it be a dt/dd fieldRow pair -- so a
      // standalone chip carries the same attributes fieldRow would have.
      el(
        "span",
        {
          "data-testid": "candidate-card-walking-time",
          "data-field-label": "徒歩",
          "data-value-state": "provided",
          "class": "candidate-walk-chip",
        },
        ["徒歩 約" + candidate.walkingTimeMinutes + "分"]
      ),
    ]);
    card.appendChild(idRow);

    card.appendChild(
      el("p", { "data-testid": "candidate-card-genre", "data-field-label": "ジャンル", "data-value-state": "provided", "class": "candidate-genre-text" }, [
        candidate.genre,
      ])
    );

    // Design realignment (E:\AWS\dsg-out\Main.dc.html): description is a
    // plain paragraph directly under genre, not a labelled fact row inside
    // the facts grid -- design shows no "紹介" heading at all, just the
    // text itself. fieldRow always renders a visible dt label, so this is
    // built directly instead; data-field-label/-value-state/rawValueAttribue-
    // equivalent absence match what fieldRow would have produced for this
    // same field (fieldRow's own "unavailable" fallback text is kept too).
    var descriptionProvided =
      candidate.description !== null && candidate.description !== undefined && candidate.description !== "";
    card.appendChild(
      el(
        "p",
        {
          "data-testid": "candidate-card-description",
          "data-field-label": "紹介",
          "data-value-state": descriptionProvided ? "provided" : "unavailable",
          "class": "candidate-description-text",
        },
        [descriptionProvided ? candidate.description : "紹介文の登録はありません"]
      )
    );

    var facts = el("dl", { "class": "candidate-facts" }, []);
    facts.appendChild(
      fieldRow(
        "総席数",
        "candidate-card-total-seats",
        candidate.totalSeats,
        CAPACITY_TIER_LABELS[candidate.capacityTier],
        "data-raw-value",
        undefined,
        "席数"
      )
    );
    facts.appendChild(
      fieldRow(
        "禁煙対応",
        "candidate-card-non-smoking",
        candidate.nonSmokingStatus,
        NON_SMOKING_LABELS[candidate.nonSmokingStatus],
        "data-raw-value",
        undefined,
        "禁煙"
      )
    );
    // adr/0023 decision 10: the visible value is the bare tier word only
    // (no yen range, no "ディナー" wording) -- that disclosure lives once in
    // the static candidate-budget-tier-note element (home.html).
    facts.appendChild(
      fieldRow(
        "ディナー予算感",
        "candidate-card-dinner-budget",
        candidate.dinnerBudgetTier,
        TIER_LABELS[candidate.dinnerBudgetTier],
        "data-raw-value",
        undefined,
        "夜予算"
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
          ["クレジットカード非対応（支払い方法は要確認）"]
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
    card.appendChild(
      el("div", { "class": "candidate-card-detail-footer" }, [
        fieldRow("定休日", "candidate-card-regular-holiday", candidate.regularHoliday),
        link,
      ])
    );

    cardElementsByRef[candidate.candidateRef] = card;
    return card;
  }

  function clearWalkingRadiusRingLayers() {
    walkingRadiusRingLayers.forEach(function (layer) {
      layer.remove();
    });
    walkingRadiusRingLayers = [];
  }

  // adr/0025 decision 1 (rings exist) + adr/0029 decisions 1/2/4 (their
  // radii use the detour-corrected walking-time estimate) +
  // contracts/candidate-search-browser-interface.yaml's walkingRadiusRings.
  // bandLabel (adr/0030 decision 1, every present ring must carry a visible/
  // accessible label matching its bandAttribute) + designer's ring-
  // legibility guidance (casing, per-band dash/opacity steps, an accent
  // ring for the applied walking-time-max filter, an innermost-band tint,
  // and skipping/nudging labels for rings that fall off the current map
  // view). Re-runs from scratch on every call (see clearWalkingRadiusRingLayers
  // above) so it can be called again whenever the map's own size or view
  // changes -- see initializeMap's ResizeObserver below, which is the only
  // caller today.
  function layoutWalkingRadiusRings(map, originLatLng) {
    clearWalkingRadiusRingLayers();
    if (!originLatLng || !window.L) {
      return;
    }

    var containerSize = map.getSize();
    var originPoint = map.latLngToContainerPoint(originLatLng);
    var selectedMinutes = currentFilters.walkingTimeMaxMinutes;

    var rings = WALKING_TIME_MAX_PRESETS_MINUTES.map(function (minutes, index) {
      var radiusMeters = (minutes * WALKING_METERS_PER_MINUTE) / WALKING_DETOUR_FACTOR;
      var northLatLng = window.L.latLng(
        originLatLng[0] + radiusMeters / METERS_PER_DEGREE_LATITUDE,
        originLatLng[1]
      );
      var northPoint = map.latLngToContainerPoint(northLatLng);
      var radiusPx = originPoint.distanceTo(northPoint);
      var nearestPoint = window.L.point(
        Math.max(0, Math.min(containerSize.x, originPoint.x)),
        Math.max(0, Math.min(containerSize.y, originPoint.y))
      );
      var nearestDistance = originPoint.distanceTo(nearestPoint);
      var corners = [
        window.L.point(0, 0),
        window.L.point(containerSize.x, 0),
        window.L.point(0, containerSize.y),
        window.L.point(containerSize.x, containerSize.y),
      ];
      var farthestDistance = corners.reduce(function (farthest, corner) {
        return Math.max(farthest, originPoint.distanceTo(corner));
      }, 0);
      // A ring's boundary crosses the currently visible container exactly
      // when the container's nearest point to the origin is within the
      // ring's radius and its farthest point is beyond it -- if the whole
      // container were inside the ring (farthest < radius), no part of the
      // ring's line would actually cross it, so it is treated the same as
      // "entirely outside" (designer's "1本も入らない輪は描かない").
      var visible = nearestDistance <= radiusPx && radiusPx <= farthestDistance;
      return {
        minutes: minutes,
        index: index,
        radiusMeters: radiusMeters,
        northPoint: northPoint,
        visible: visible,
      };
    });

    if (rings.length > 0 && rings[0].visible) {
      var tint = window.L.circle(originLatLng, {
        radius: rings[0].radiusMeters,
        className: "candidate-walking-radius-ring-inner-tint",
        stroke: false,
        fill: true,
        fillOpacity: 0.05,
        interactive: false,
      });
      tint.addTo(map);
      walkingRadiusRingLayers.push(tint);
    }

    rings.forEach(function (ring) {
      if (!ring.visible) {
        return;
      }
      var isSelected = selectedMinutes === ring.minutes;
      var styleEntry =
        WALKING_RADIUS_RING_STYLE_BY_BAND_INDEX[
          Math.min(ring.index, WALKING_RADIUS_RING_STYLE_BY_BAND_INDEX.length - 1)
        ];
      var casingBandClassName = styleEntry.className.replace(
        "-path--band-",
        "-casing--band-"
      );
      var casingClassName =
        "candidate-walking-radius-ring-casing " +
        casingBandClassName +
        (isSelected ? " candidate-walking-radius-ring-casing--accent" : "");
      var casing = window.L.circle(originLatLng, {
        radius: ring.radiusMeters,
        className: casingClassName,
        weight:
          (isSelected ? WALKING_RADIUS_RING_ACCENT_WEIGHT : WALKING_RADIUS_RING_BASE_WEIGHT) +
          WALKING_RADIUS_RING_CASING_EXTRA_WEIGHT,
        fill: false,
        interactive: false,
      });
      casing.addTo(map);
      walkingRadiusRingLayers.push(casing);

      var ringClassName =
        "candidate-walking-radius-ring-path " +
        styleEntry.className +
        (isSelected ? " candidate-walking-radius-ring-path--accent" : "");
      var ringLayer = window.L.circle(originLatLng, {
        radius: ring.radiusMeters,
        className: ringClassName,
        weight: isSelected ? WALKING_RADIUS_RING_ACCENT_WEIGHT : WALKING_RADIUS_RING_BASE_WEIGHT,
        fill: false,
        interactive: false,
      });
      ringLayer.addTo(map);
      walkingRadiusRingLayers.push(ringLayer);

      var labelText = String(ring.minutes) + "分";
      var ringEl = ringLayer.getElement();
      if (ringEl) {
        ringEl.setAttribute("data-testid", "candidate-walking-radius-ring");
        ringEl.setAttribute("data-walking-radius-minutes", String(ring.minutes));
        // adr/0030 decision 1's bandLabel Must: a non-empty visible or
        // accessible label whose leading digits equal bandAttribute. The
        // divIcon label below is the genuinely visible one; this aria-label
        // on the ring's own path element additionally satisfies the Must
        // through the ring element itself, belt-and-suspenders, in case a
        // reader never reaches a sibling map layer.
        ringEl.setAttribute("aria-label", labelText);
      }

      // Nudge an off-center label back into the visible map area (designer:
      // "画面外に出る輪は画面内へ寄せる") by clamping its default position
      // (due north of the origin, on the ring itself) into the container
      // rect, inset by a margin so it never sits flush against the edge.
      var clampedPoint = window.L.point(
        Math.min(
          Math.max(ring.northPoint.x, WALKING_RADIUS_RING_LABEL_MARGIN_PX),
          containerSize.x - WALKING_RADIUS_RING_LABEL_MARGIN_PX
        ),
        Math.min(
          Math.max(ring.northPoint.y, WALKING_RADIUS_RING_LABEL_MARGIN_PX),
          containerSize.y - WALKING_RADIUS_RING_LABEL_MARGIN_PX
        )
      );
      var labelIcon = window.L.divIcon({
        className:
          "candidate-walking-radius-ring-label" +
          (isSelected ? " candidate-walking-radius-ring-label--accent" : ""),
        html: '<span class="candidate-walking-radius-ring-label-visual"></span>',
        iconSize: [1, 1],
        iconAnchor: [0, 0],
      });
      var label = window.L.marker(map.containerPointToLatLng(clampedPoint), {
        icon: labelIcon,
        interactive: false,
        keyboard: false,
      });
      label.addTo(map);
      var labelEl = label.getElement();
      if (labelEl) {
        var labelVisual = labelEl.querySelector(".candidate-walking-radius-ring-label-visual");
        if (labelVisual) {
          labelVisual.textContent = labelText;
        }
      }
      walkingRadiusRingLayers.push(label);
    });
  }

  // Task 3 (designer): moves (never clones) the selected candidate's own
  // candidate-card element between the vertical list and the full-screen
  // sheet's single-candidate panel. There is never more than one DOM
  // element carrying a given data-candidate-ref's candidate-card at a
  // time -- contracts/candidate-search-browser-interface.yaml's
  // mapObservations.markerSet ("every candidate-card has exactly one
  // marker with same data-candidate-ref") is unaffected by *where in the
  // DOM* that one element currently lives. Restoring every ordered card to
  // the list first (rather than tracking only "the one currently in the
  // panel") is what keeps this correct regardless of how many times
  // selection changed while the sheet was open.
  function syncMapSheetPanelToSelection() {
    if (!mapSheetOpen || !mapSheetPanelEl || !cardsContainerEl) {
      return;
    }
    orderedCardElements.forEach(function (card) {
      cardsContainerEl.appendChild(card);
    });
    var selectedCard = selectedCandidateRef ? cardElementsByRef[selectedCandidateRef] : null;
    mapSheetPanelEl.innerHTML = "";
    if (selectedCard) {
      mapSheetPanelEl.appendChild(selectedCard);
      // Design realignment (E:\AWS\dsg-out\MapSheet.dc.html): a hint
      // line under the primary action, since there is no card deck here
      // to imply "there are more of these".
      mapSheetPanelEl.appendChild(
        el("p", { "class": "candidate-map-sheet-hint" }, ["ほかの店を見るには地図のピンをタップ"])
      );
    }
    // Design realignment (E:\AWS\dsg-out\MapSheet.dc.html's header bar):
    // "N / total" position counter, matching the design's own "1 / 5".
    if (mapSheetCounterEl) {
      var position = orderedCardElements.findIndex(function (card) {
        return card.getAttribute("data-candidate-ref") === selectedCandidateRef;
      });
      mapSheetCounterEl.textContent =
        position === -1 ? "" : String(position + 1) + " / " + String(orderedCardElements.length);
    }
  }

  // `inert` (feature-detected -- supported by every browser this project's
  // own Playwright harness exercises, activeContext.md records the exact
  // Chromium build; a no-op enhancement, never a hard dependency, on any
  // browser that lacks it) removes a whole subtree from the Tab order and
  // the accessibility tree, and -- unlike a CSS pointer-events rule --
  // does this regardless of what pointer-events/tabindex value any
  // descendant declares for itself. That "regardless of the descendant's
  // own declaration" property is exactly what home.html's own comment on
  // [data-testid="candidate-map"] explains was missing before: Leaflet's
  // vendored CSS sets pointer-events:auto explicitly on marker elements,
  // which no ancestor-level pointer-events:none (CSS inheritance) can
  // override on its own.
  function setInert(elements, isInert) {
    if (!("inert" in HTMLElement.prototype)) {
      return;
    }
    elements.forEach(function (element) {
      if (!element) {
        return;
      }
      if (isInert) {
        element.setAttribute("inert", "");
      } else {
        element.removeAttribute("inert");
      }
    });
  }

  // Excludes the list/filter bar/header from the Tab order and the
  // accessibility tree while the full-screen map sheet visually covers
  // them (task 3) -- without this, a keyboard user could still Tab into
  // controls a sighted user cannot currently see or reach.
  function setBackgroundInert(isInert) {
    var header = document.querySelector('header[data-testid="authenticated-application-shell"]');
    setInert([header, filterBar, cardsContainerEl], isInert);
  }

  // Human real-device report, second round (2026-08-25): the closed map
  // (opacity:0, per the fix above) was still answering real taps meant for
  // candidate-map-open and the cards underneath -- elementFromPoint
  // measurement confirmed a closed-state marker, not the button beneath
  // it, received the tap. Fixed by home.html's
  // `* { pointer-events: none !important; }` rule (CSS-only, no feature
  // detection needed, wins over Leaflet's own explicit pointer-events:auto
  // regardless of specificity because !important always does).
  //
  // Deliberately NOT fixed with `inert` on the whole map container, even
  // though that was tried first and did stop the stray taps: `inert`
  // disables keyboard reachability for its entire subtree with no way for
  // a descendant to opt back in (confirmed empirically -- an inert
  // ancestor makes Tab skip every descendant regardless of the
  // descendant's own tabindex, and even a direct .focus() call on a
  // descendant becomes a silent no-op). candidate-map-marker is one of
  // ADR-0020 decision 4(c)'s own gated control-surface elements --
  // test_c_candidate_map_marker_selection_is_keyboard_operable presses
  // Enter/Space on it *in this screen's default (closed) state*, with no
  // "open the sheet first" step -- so making it inert while closed
  // reddened that frozen test (developer may not weaken it). The origin
  // marker carries no such requirement (candidate-search-browser-
  // interface.yaml's displayOnlyOriginException explicitly tolerates
  // focusability either way), so setOriginMarkerTabbable below narrows
  // the keyboard fix to it alone, leaving candidate-map-marker's own
  // tabindex/keydown handler completely untouched. This is a real,
  // reported trade-off, not a silent partial fix -- see activeContext.md
  // for the full reasoning: candidate-map-marker itself stays Tab-
  // reachable (and, per its own existing keydown handler, Enter/Space-
  // activatable) even while genuinely invisible and closed, because the
  // alternative was breaking a frozen ADR-0020 gate.
  function setOriginMarkerTabbable(isTabbable) {
    if (!originMarkerEl) {
      return;
    }
    originMarkerEl.setAttribute("tabindex", isTabbable ? "0" : "-1");
  }

  // Human real-device report (2026-08-25): opening the sheet collapsed the
  // map to a 0-height box (candidate-map-wrapper's own children -- the map,
  // the open control, the close control, the sheet panel -- were laid out
  // by a column flexbox that sized the wrapper by its in-flow content;
  // toggling the map to position:fixed removed it from that flow, leaving
  // nothing in-flow to size the wrapper by). Fixed by making the map
  // element's own box constant at all times (always position:fixed, always
  // full-viewport width/height) so it never depends on the wrapper's own
  // sizing -- see [data-testid="candidate-map"]'s CSS in home.html. Closed
  // vs open is now purely an opacity/pointer-events toggle on that
  // constant-size box, not a box-model change, so a later resize is no
  // longer guaranteed to fire (the box's own rendered size does not
  // necessarily change between the two states) -- refreshMapViewAndRings is
  // therefore called directly here rather than only from the
  // ResizeObserver (which still exists, and still matters, for genuine
  // later resizes: window resize, mobile-toolbar dvh changes, orientation
  // change).
  function refreshMapViewAndRings() {
    if (!leafletMap) {
      return;
    }
    leafletMap.invalidateSize();
    if (mapSheetOpen && selectedCandidateRef && latLngByRef[selectedCandidateRef]) {
      leafletMap.setView(latLngByRef[selectedCandidateRef], Math.max(leafletMap.getZoom(), 16));
    } else if (currentMapLatLngs.length > 0) {
      leafletMap.fitBounds(window.L.latLngBounds(currentMapLatLngs), { padding: [24, 24] });
    }
    layoutWalkingRadiusRings(leafletMap, walkingRadiusRingOrigin);
  }

  function openMapSheet() {
    if (mapSheetOpen || !mapWrapperEl) {
      return;
    }
    mapSheetOpen = true;
    mapWrapperEl.closest(".candidate-main-layout").setAttribute("data-map-sheet-open", "true");
    // Human real-device report, third round (2026-08-25): with the sheet
    // open, the still-in-normal-flow candidate list (everything except the
    // one selected card, already moved into candidate-map-sheet-panel by
    // syncMapSheetPanelToSelection below) kept answering taps/painting on
    // top of the full-screen map -- elementFromPoint measurement confirmed
    // 4 of 5 markers were unreachable, hit by a candidate-card instead.
    // inert (setBackgroundInert, already called next) turned out not to
    // reliably stop this in the real page despite hasAttribute("inert")
    // reading true (measured directly; the mechanism this project already
    // trusted for keyboard exclusion did not reproduce the same protection
    // for elementFromPoint here, unlike an isolated reproduction). Setting
    // this same attribute on <body> lets home.html's CSS reach
    // header/#candidate-filter-bar/candidate-proposal-cards (none of which
    // are descendants of .candidate-main-layout) with the identical
    // visibility:hidden + `* { pointer-events: none !important; }`
    // combination already proven robust for the closed map itself.
    document.body.setAttribute("data-map-sheet-open", "true");
    setBackgroundInert(true);
    setOriginMarkerTabbable(true);
    syncMapSheetPanelToSelection();
    refreshMapViewAndRings();
    sheetCloseFocusTarget = document.activeElement;
    var closeControl = mapWrapperEl.querySelector(".candidate-map-sheet-back");
    if (closeControl) {
      closeControl.focus();
    }
  }

  function closeMapSheet() {
    if (!mapSheetOpen || !mapWrapperEl) {
      return;
    }
    mapSheetOpen = false;
    mapWrapperEl.closest(".candidate-main-layout").setAttribute("data-map-sheet-open", "false");
    document.body.removeAttribute("data-map-sheet-open");
    setBackgroundInert(false);
    setOriginMarkerTabbable(false);
    orderedCardElements.forEach(function (card) {
      cardsContainerEl.appendChild(card);
    });
    if (mapSheetPanelEl) {
      mapSheetPanelEl.innerHTML = "";
    }
    refreshMapViewAndRings();
    var openControl = mapWrapperEl.querySelector(".candidate-map-open");
    if (sheetCloseFocusTarget && document.contains(sheetCloseFocusTarget)) {
      sheetCloseFocusTarget.focus();
    } else if (openControl) {
      openControl.focus();
    }
    sheetCloseFocusTarget = null;
  }

  function initializeMap(container, candidates, searchOrigin) {
    markerElementsByRef = {};
    latLngByRef = {};
    if (mapResizeObserver) {
      mapResizeObserver.disconnect();
      mapResizeObserver = null;
    }
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
    currentMapLatLngs = latLngs;
    var originLatLng = searchOrigin ? [searchOrigin.latitude, searchOrigin.longitude] : null;

    // Leaflet's Map#addLayer defers a layer's onAdd (and therefore marker
    // icon creation) until the map has an established view, via
    // Map#whenReady: https://leafletjs.com/reference.html#map-whenready.
    // A map created without initial center/zoom has no view until setView
    // or fitBounds runs, so it must happen before any marker is added below.
    // The map container is always full-viewport-sized (task 3, human
    // decision 2026-08-25: closed vs open is an opacity toggle, not a box-
    // model change -- see [data-testid="candidate-map"]'s CSS in
    // home.html), so this initial fit already targets the real viewport
    // regardless of whether the sheet happens to be open yet.
    if (latLngs.length > 0) {
      map.fitBounds(window.L.latLngBounds(latLngs), { padding: [24, 24] });
    } else {
      map.setView([0, 0], 2);
    }

    candidates.forEach(function (candidate, index) {
      latLngByRef[candidate.candidateRef] = latLngs[index];
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
        // Task 3 (designer): inside the full-screen map sheet, tapping a
        // pin is how an organizer switches which single candidate the sheet
        // shows -- selectCandidate's own sync with the sheet (see below)
        // handles that; outside the sheet this is unchanged card/marker
        // selection.
        selectCandidate(candidate.candidateRef, !mapSheetOpen);
      });
      // ADR-0020 decision 4(c): Leaflet's `keyboard: true` option only makes
      // the marker's icon element focusable (tabIndex/role, see the vendored
      // leaflet.js Marker#_initIcon) -- it does not itself translate an
      // Enter/Space keypress into a "click" for a marker with no bound
      // popup, unlike a native <button>. Without this handler the marker was
      // Tab-reachable but not keyboard-activatable, mirroring the same
      // explicit Enter/Space handling the candidate card already has above.
      markerEl.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectCandidate(candidate.candidateRef);
        }
      });
      markerElementsByRef[candidate.candidateRef] = markerEl;
    });

    // adr/0025 decision 1: the private search origin marker. A read-only
    // display element -- see candidate-search-browser-interface.yaml's
    // displayOnlyOriginException: the exception is defined by behavior (no
    // click/keydown handler here changes any proposal request, displayed
    // candidate, marker, or condition summary), not by focusability, so
    // Leaflet's own keyboard:true default (which makes the icon
    // Tab-reachable, per ADR-0020's own finding for candidate markers) does
    // not disqualify this element from the exception. The walking-radius
    // rings (same exception) are laid out separately by
    // layoutWalkingRadiusRings below, which is also the function the
    // ResizeObserver re-runs on every later container resize.
    if (originLatLng) {
      var originIcon = window.L.divIcon({
        className: "candidate-origin-marker-icon",
        html: '<span class="candidate-origin-marker-visual"></span>',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
      var originMarker = window.L.marker(originLatLng, {
        icon: originIcon,
        keyboard: true,
        alt: "検索基点",
      });
      originMarker.addTo(map);
      originMarkerEl = originMarker.getElement();
      if (originMarkerEl) {
        originMarkerEl.setAttribute("data-testid", "candidate-origin-marker");
        originMarkerEl.setAttribute("aria-label", "検索基点");
        // Human real-device report, second round (2026-08-25): tabindex=-1
        // while the map is closed/invisible, so a keyboard user tabbing
        // through the page cannot land on it -- setOriginMarkerTabbable's
        // own comment explains why this element (not candidate-map-marker)
        // is the one this fix targets. openMapSheet restores tabindex=0.
        originMarkerEl.setAttribute("tabindex", mapSheetOpen ? "0" : "-1");
        // positionAttributes (candidate-search-browser-interface.yaml
        // mapObservations.searchOriginMarker, contractVersion 1.3.1,
        // FR-022(1)): the exact canonical decimal string of
        // response.searchOrigin.latitude/longitude, mirroring the
        // rawValueAttribute String(value) convention used elsewhere in
        // this file (see fieldRow above) so acceptance can assert the
        // marker's position derives from this response rather than a
        // fixture-baked constant.
        originMarkerEl.setAttribute(
          "data-origin-latitude",
          String(searchOrigin.latitude)
        );
        originMarkerEl.setAttribute(
          "data-origin-longitude",
          String(searchOrigin.longitude)
        );
      }
    }

    walkingRadiusRingOrigin = originLatLng;
    layoutWalkingRadiusRings(map, originLatLng);

    container.setAttribute("data-map-fit-state", "displayed-candidates");
    leafletMap = map;

    // Re-fit Leaflet's internal view (and re-lay-out the walking-radius
    // rings) whenever the map container's own size genuinely changes after
    // this initial render, even when that change carries no `window`
    // "resize" event. Leaflet's own default `trackResize: true` (candidate.js
    // never overrides it) already listens for `window` "resize" and calls
    // invalidateSize() on a plain browser-window resize, confirmed by
    // reading the vendored leaflet.js's own `_initEvents`. What that built-
    // in handler cannot see is a container-size change with no accompanying
    // `window` resize -- which this screen's own CSS produces when a mobile
    // browser's toolbar collapsing/reappearing while scrolling changes
    // `100dvh` (human decision 2026-08-22). Opening/closing the full-screen
    // map sheet (task 3) is deliberately *not* one of the size changes this
    // observer needs to catch any more: [data-testid="candidate-map"] is
    // always position:fixed and full-viewport-sized (human decision
    // 2026-08-25, fixing a real collapse-to-0-height defect the previous
    // box-model-toggling design had -- see refreshMapViewAndRings's own
    // comment), so openMapSheet/closeMapSheet call refreshMapViewAndRings
    // directly instead of depending on this observer to fire.
    if (window.ResizeObserver) {
      mapResizeObserver = new window.ResizeObserver(function () {
        refreshMapViewAndRings();
      });
      mapResizeObserver.observe(container);
    }
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
      a.walkingTimeMaxMinutes === b.walkingTimeMaxMinutes &&
      a.genres.slice().sort().join("|") === b.genres.slice().sort().join("|") &&
      a.budgetTiers.slice().sort().join("|") === b.budgetTiers.slice().sort().join("|")
    );
  }

  // Mirrors dining_radar.recommendation.pipeline.filter_candidates AND
  // apply_izakaya_bar_fallback exactly, including the soft-filter rule: a
  // candidate whose value for an active filter is unknown is NOT removed
  // (adr/0023 decision 2 / TDR-CS-13), and the default izakaya/bar-exclusion
  // fallback (adr/0023 decision 6 / TDR-CS-10): when includeIzakayaBar is
  // false, a candidate outside the default-excluded genre category is
  // preferred, but if excluding that category would leave nothing matching
  // the other active filters, the count falls back to counting
  // default-excluded rows too -- exactly mirroring what the server itself
  // would return for the same filters, so this pending-filter preview count
  // never disagrees with the response the organizer is about to receive.
  // This is the one place the server's predicate is duplicated in the
  // browser; it exists so a pending selection's match count can be shown
  // before the organizer commits it, without a provider request per toggle.
  // If the two ever disagree, the number on the apply control lies -- an
  // acceptance test must compare this count against the count the server
  // actually returns.
  //
  // adr/0025 decision 3: walkingTimeMaxMinutes is a *hard* filter, unlike
  // the soft ones above -- a row's walkingTimeBand is never "unconfirmed"
  // (walking time is always computable server-side), so a null band here
  // means "farther than every currently offered preset" and must always be
  // excluded when a limit is pending, exactly mirroring
  // pipeline.filter_candidates' walking_time_max_minutes branch.
  function passesNonExclusionFilters(filters, row) {
    if (filters.genres.length && filters.genres.indexOf(row.genre) === -1) {
      return false;
    }
    if (filters.nonSmokingOnly && row.nonSmokingStatus === "NONE") {
      return false;
    }
    if (filters.cardPaymentOnly && row.cardPaymentAvailable === false) {
      return false;
    }
    if (
      filters.budgetTiers.length &&
      row.dinnerBudgetTier !== null &&
      row.dinnerBudgetTier !== undefined &&
      filters.budgetTiers.indexOf(row.dinnerBudgetTier) === -1
    ) {
      return false;
    }
    if (
      filters.walkingTimeMaxMinutes !== null &&
      filters.walkingTimeMaxMinutes !== undefined &&
      (row.walkingTimeBand === null ||
        row.walkingTimeBand === undefined ||
        row.walkingTimeBand > filters.walkingTimeMaxMinutes)
    ) {
      return false;
    }
    return true;
  }

  function countMatchingPopulation(filters) {
    var matching = populationAttributes.filter(function (row) {
      return passesNonExclusionFilters(filters, row);
    });
    if (filters.includeIzakayaBar) {
      return matching.length;
    }
    var withoutDefaultExcluded = matching.filter(function (row) {
      return !row.defaultExcluded;
    });
    return withoutDefaultExcluded.length ? withoutDefaultExcluded.length : matching.length;
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
    if (filters.walkingTimeMaxMinutes !== null && filters.walkingTimeMaxMinutes !== undefined) {
      parts.push("徒歩" + filters.walkingTimeMaxMinutes + "分以内");
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

  // adr/0024 decision 1: each offered genre's population count, restricted to
  // defaultExcluded=false rows unless the response this population came from
  // had includeIzakayaBar=true -- the same scoping availableGenres itself
  // already uses (candidate-search-browser-interface.yaml's
  // genrePresentation.populationCountRule). currentFilters, not
  // pendingFilters, holds the includeIzakayaBar value that actually produced
  // this response.
  function genrePopulationCounts() {
    var scopeAll = currentFilters.includeIzakayaBar;
    var counts = {};
    populationAttributes.forEach(function (row) {
      if (!scopeAll && row.defaultExcluded) {
        return;
      }
      counts[row.genre] = (counts[row.genre] || 0) + 1;
    });
    return counts;
  }

  // genrePresentation.presentationOrder (adr/0024 decision 1):
  // descending-population-count-then-ascending-string-length-then-
  // ja-locale-collation. The tie-break (string length, then locale
  // collation) is unchanged from the prior sole ordering rule (adr/0023
  // decision 12) -- it only now applies after, not instead of, the count.
  function orderedAvailableGenres() {
    var counts = genrePopulationCounts();
    return currentAvailableGenres.slice().sort(function (left, right) {
      var countDifference = (counts[right] || 0) - (counts[left] || 0);
      if (countDifference !== 0) {
        return countDifference;
      }
      return left.length - right.length || left.localeCompare(right, "ja");
    });
  }

  function genreOptionChips(visibleGenres) {
    return visibleGenres.map(function (genre) {
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
  }

  // Human decision 2026-08-23 (design/wireframes/GenreRow.dc.html option
  // (c)): the overflow toggle -- the only entry point to hidden genres --
  // must stay reachable at a fixed position regardless of the row's own
  // horizontal scroll offset. A 390px measurement found it off-screen when
  // it instead trailed the scrollable row. See genreGroupRow below, which
  // places this outside (a DOM sibling of, not a descendant of) the
  // scrollable sub-container.
  function genreOverflowToggle(hiddenCount, expanded) {
    var overflow = el(
      "button",
      {
        type: "button",
        "class": "candidate-chip candidate-chip-quiet",
        "data-testid": "candidate-filter-genre-overflow",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-filter-genre-overflow-toggle",
      },
      [expanded ? "閉じる" : "ほか " + hiddenCount + "件…"]
    );
    overflow.addEventListener("click", function () {
      genreOverflowExpanded = !genreOverflowExpanded;
      renderFilterBar();
    });
    return overflow;
  }

  // adr/0024 decision 2: "居酒屋等も含む" moved from the "こだわり" row into
  // the "ジャンル" row (controlGrouping.genreGroup). It is present regardless
  // of genrePresentation's compact/preview/expanded state, is never counted
  // toward the genre option count, and is never a
  // candidate-filter-genre-overflow member -- so it is prepended before the
  // genre option chips (genreGroupRow's scrollable sub-container) rather
  // than folded into their preview/overflow logic. It is placed first
  // because it toggles the scope of genre matching itself
  // (rather than selecting an individual genre), which reads more naturally
  // ahead of the individual genre options, and keeps it within the
  // horizontally scrollable chip row's initially visible range on narrow
  // viewports. contracts/candidate-search-browser-interface.yaml's
  // controlGrouping.genreGroup only requires membership, not intra-group
  // order. Its allowedPurposes value (candidate-filter-izakaya-bar-toggle)
  // and data-candidate-control-category ("button") are unchanged; only its
  // DOM placement moves.
  function izakayaBarToggleChip() {
    return chip({
      testId: "candidate-filter-include-izakaya-bar",
      purpose: "candidate-filter-izakaya-bar-toggle",
      label: "居酒屋等も含む",
      pressed: pendingFilters.includeIzakayaBar,
      onToggle: function (next) {
        pendingFilters.includeIzakayaBar = next;
        renderFilterBar();
      },
    });
  }

  // Human decision 2026-08-23: a "how many will this match" preview appears
  // only here, on the apply control itself -- never as an always-visible
  // element. The wording must not read as a promise of how many candidate
  // cards this action will display -- the display cap stays DISPLAY_CAP
  // regardless of matchCount (candidate-search-browser-interface.yaml's
  // matchCountObservation.visibleCountWording explicitly forbids phrasing
  // like "○件表示されます"/"○件出ます"). "対象" reads as "this many match
  // the pending condition", not a display-count promise, so the same
  // wording is used regardless of whether matchCount exceeds DISPLAY_CAP.
  function applyControlLabel(matchCount) {
    if (matchCount === 0) {
      return "該当なし";
    }
    return "この条件で探す（対象" + matchCount + "件）";
  }

  // genrePresentation.presentationOrder's overflow toggle is rendered as
  // genreGroup's leading (first DOM) member; the genre option chips and
  // izakayaBarToggleChip() share a separate horizontally scrollable
  // sub-container (human decision 2026-08-23,
  // controlGrouping.genreGroup.overflowPlacement) so the toggle's own
  // position is unaffected by that container's own scroll offset.
  function genreGroupRow() {
    var orderedGenres = orderedAvailableGenres();
    var visible = genreOverflowExpanded
      ? orderedGenres
      : orderedGenres.slice(0, GENRE_PREVIEW_COUNT);
    var hidden = orderedGenres.length - visible.length;

    var scrollable = el(
      "div",
      { "class": "candidate-filter-row-chips candidate-genre-scrollable" },
      [izakayaBarToggleChip()].concat(genreOptionChips(visible))
    );

    var groupChildren = [];
    if (hidden > 0 || genreOverflowExpanded) {
      groupChildren.push(genreOverflowToggle(hidden, genreOverflowExpanded));
    }
    groupChildren.push(scrollable);

    return el("div", { "class": "candidate-filter-row" }, [
      el("span", { "class": "candidate-filter-row-label" }, ["ジャンル"]),
      el("div", { "class": "candidate-genre-group" }, groupChildren),
    ]);
  }

  // adr/0025 decision 3: walkingTimeMaxMinutes is its own filter condition
  // (walkingTimeGroup), never a member of genreGroup/preferenceGroup/
  // budgetGroup. A single-selection closed set over
  // WALKING_TIME_MAX_PRESETS_MINUTES: selecting a preset replaces any prior
  // selection; selecting the already-pressed preset again clears it back to
  // "no restriction" (pendingFilters.walkingTimeMaxMinutes = null), mirroring
  // how the other closed-vocabulary controls in this panel behave.
  function walkingTimeMaxChips() {
    return WALKING_TIME_MAX_PRESETS_MINUTES.map(function (minutes) {
      return chip({
        testId: "candidate-filter-walking-time-max-option",
        purpose: "candidate-filter-walking-time-max-selection",
        label: minutes + "分以内",
        pressed: pendingFilters.walkingTimeMaxMinutes === minutes,
        value: minutes,
        valueAttribute: "data-walking-time-max-value",
        onToggle: function (next) {
          pendingFilters.walkingTimeMaxMinutes = next ? minutes : null;
          renderFilterBar();
        },
      });
    });
  }

  // TDR-CS-16 (human decision 2026-08-23): the currently *applied* filters,
  // condition summary, and displayed candidates/map must remain unchanged
  // while this request is in flight and if it fails -- so, unlike the prior
  // implementation, currentFilters is committed and the panel is only
  // closed *after* a successful response, never optimistically beforehand.
  function applyPendingFilters() {
    var requestedFilters = cloneFilters(pendingFilters);
    requestProposal(requestedFilters).then(function (result) {
      if (result.status === 200) {
        currentFilters = requestedFilters;
        filterExpanded = false;
        genreOverflowExpanded = false;
      }
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
      walkingTimeMax: active.getAttribute("data-walking-time-max-value"),
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
    if (target.walkingTimeMax) {
      selector += '[data-walking-time-max-value="' + target.walkingTimeMax + '"]';
    }
    var control = filterBar.querySelector(selector);
    if (control) {
      control.focus();
    }
  }

  // adr/0030 decision 2 (human decision 2026-08-24): candidate-no-results'
  // guidance must carry its own pressable element, not only point at the
  // distant toolbar's candidate-filter-open, and activating it must produce
  // exactly openFilterPanel's requiredOutcome for the current pending/
  // applied state -- unlike candidate-filter-open's own summary toggle
  // (which opens or closes depending on filterExpanded's current value,
  // see below), this control only ever opens: candidate-no-results is only
  // ever rendered on a fresh response, before this button could have
  // toggled anything.
  function renderNoResultsReviseFiltersControl() {
    var button = el(
      "button",
      {
        type: "button",
        "class": "candidate-no-results-revise-filters",
        "data-testid": "candidate-no-results-revise-filters",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-no-results-open-filter",
      },
      ["絞り込み条件を変更する"]
    );
    button.addEventListener("click", function () {
      filterExpanded = true;
      renderFilterBar();
      restoreFilterFocus({ testId: "candidate-filter-open" });
    });
    return button;
  }

  function renderFilterBar(restoreFocus) {
    var focusTarget = restoreFocus || filterFocusTarget();
    var dirty = !sameFilters(pendingFilters, currentFilters);
    filterBar.innerHTML = "";
    filterBar.setAttribute("data-filter-expanded", filterExpanded ? "true" : "false");
    filterBar.setAttribute("data-filter-dirty", dirty ? "true" : "false");

    var summaryTexts = [
      el("span", { "class": "candidate-filter-summary-label" }, ["条件"]),
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
        "data-testid": "candidate-filter-open",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-filter-open",
        "aria-expanded": filterExpanded ? "true" : "false",
      },
      [
        el("span", { "class": "candidate-filter-summary-icon", "aria-hidden": "true" }, ["☷"]),
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
      [
        el("span", { "class": "candidate-search-again-icon", "aria-hidden": "true" }, ["↻"]),
        el("span", { "class": "candidate-search-again-label", "aria-hidden": "true" }, ["もう一度探す"]),
        el("span", { "class": "visually-hidden" }, ["もう一度探す"]),
      ]
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
        // adr/0024 decision 2: candidate-filter-include-izakaya-bar renders
        // inside this same "ジャンル" row/DOM group (controlGrouping.genreGroup),
        // prepended before the genre option chips. genreGroupRow (adr/0025 +
        // human decision 2026-08-23) additionally places the overflow
        // toggle outside that scrollable sub-container -- see its own
        // comment for why.
        genreGroupRow(),
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
        ]),
        chipRow(
          "夜予算",
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
        // adr/0025 decision 3: its own filter condition/DOM group, separate
        // from genreGroup, preferenceGroup, and budgetGroup above
        // (walkingTimeGroup in candidate-search-browser-interface.yaml).
        chipRow("徒歩の上限", walkingTimeMaxChips()),
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

    var actions = [];
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
      actions.push(apply);
    }
    if (actions.length > 0) {
      panel.appendChild(el("div", { "class": "candidate-filter-actions" }, actions));
    }
    // adr/0023 decision 10, revised on human instruction 2026-08-10: the
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

  // TDR-CS-16 (human decision 2026-08-23): when `additive` is true (a fetch
  // failure that follows an already-displayed proposal), the problem alert
  // renders in addition to, not instead of, the retained cards/map -- root
  // is never cleared, unlike the `empty` render state. When false (no prior
  // successful proposal exists to retain, e.g. the very first request on
  // page load), this is the original full-replace behavior.
  function renderProblem(code, message, additive) {
    var problem = el(
      "section",
      { "data-testid": "candidate-proposal-problem", "data-problem-code": code, role: "alert" },
      [el("p", { "data-testid": "candidate-proposal-problem-guidance" }, [message])]
    );
    if (additive) {
      var existing = root.querySelector('[data-testid="candidate-proposal-problem"]');
      if (existing) {
        existing.remove();
      }
      root.insertBefore(problem, root.firstChild);
      return;
    }
    root.innerHTML = "";
    root.appendChild(problem);
  }

  function renderResult(body) {
    cardElementsByRef = {};
    orderedCardElements = [];
    mapSheetOpen = false;
    selectedCandidateRef = null;
    cardsContainerEl = null;
    mapWrapperEl = null;
    mapSheetPanelEl = null;
    root.innerHTML = "";

    // The filter bar is not part of this element: it lives outside the
    // response-driven region so it stays reachable across the success,
    // no-results, and problem outcomes alike (TDR-CS-05's "絞り込み条件を
    // 変更するよう案内される" needs the controls to survive an empty result).
    var content = el("section", { "data-testid": "candidate-proposal-content" }, []);

    // adr/0023 decision 6: disclose both that the default izakaya/bar
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
          renderNoResultsReviseFiltersControl(),
        ])
      );
      root.appendChild(content);
      return;
    }

    // Task 3 (designer): list-primary + a real map (never a collapsed
    // placeholder button -- this is what keeps candidate-map/candidate-
    // origin-marker genuinely present on initial render, satisfying
    // authenticatedInitialOutcome.present without a contract change) +
    // tap-to-open full-screen map sheet, one Leaflet map instance
    // throughout. The map is not visually shown while closed (human
    // decision 2026-08-25) -- see [data-testid="candidate-map"]'s own CSS
    // in home.html for how.
    var mainLayout = el(
      "div",
      { "class": "candidate-main-layout", "data-map-sheet-open": "false" },
      []
    );

    var mapContainer = el(
      "div",
      { "data-testid": "candidate-map", "data-map-tile-provider": "openstreetmap-standard" },
      []
    );
    // Human decision 2026-08-25: the map is not shown at all while closed
    // (previously an always-visible 88px ribbon) -- this is now the sole
    // visible entry point into it. It, and the sheet's close control, only
    // ever change the *visible map viewport* (hidden <-> full-screen sheet)
    // -- never a proposal request, selection, filter, origin, or range --
    // the same behavioral property displayOnlyOriginException/Leaflet's own
    // zoom control already rely on (contracts/candidate-search-browser-
    // interface.yaml's locationRangeControlProhibition invariant; see this
    // file's own comment on the Leaflet zoom control CSS in home.html).
    // Deliberately built as a focusable <div> (tabindex, explicit
    // click/keydown handlers), not a <button> element -- exactly the
    // pattern candidate-origin-marker/candidate-walking-radius-ring
    // already use -- so it stays outside
    // allCandidateScreenFormControlsMustDeclarePurpose's closed
    // allowedPurposes list (that Must's own machineObservation only sweeps
    // literal <button>/<input>/<select>/<textarea>/interactive-ARIA-role
    // elements, per tests/acceptance/dsl/candidate_search_browser.py's
    // FORM_CONTROL_SELECTOR, which developer/tester may read but not edit)
    // rather than inventing a new purpose value this contract does not
    // define (developer cannot edit contracts/**).
    //
    // Both still carry a data-testid, though -- reviewer's independent
    // audit (reviews/audit-detour-ring-labels-skeleton.md, G2) found that
    // the sole entry point into the map had no machine-observable
    // identifier at all (not even a bare test id), so nothing would redden
    // if it broke. A test id alone (no data-candidate-control-purpose) is
    // the same style candidate-origin-marker already uses for a display-
    // only element outside the purpose regime, so this does not conflict
    // with the reasoning above. It does not, on its own, make this
    // control's presence/behavior a contract Must -- see activeContext.md
    // for what would still be missing for that.
    //
    // candidate-map-open (only -- not the close control below) additionally
    // carries role="button" (human decision 2026-08-25: the sole entry
    // point into the map should not be semantically un-button-like for
    // assistive technology just to dodge the purpose regime). Verified
    // this does not add it to that regime after all: FORM_CONTROL_
    // SELECTOR's role-based clauses are an explicit, closed list --
    // [role='checkbox'/'radio'/'range'/'combobox'/'listbox'/'slider'/
    // 'spinbutton'] -- and 'button' is not one of them, so this element
    // still does not match it. This is a narrower reading of the
    // contract's own machineObservation prose than what is actually
    // mechanically checked today ("...or element with an interactive ARIA
    // role..." reads as though it should include role="button"), which
    // developer is reporting rather than resolving -- see activeContext.md.
    var mapOpenButton = el(
      "div",
      {
        "data-testid": "candidate-map-open",
        "class": "candidate-map-open",
        role: "button",
        tabindex: "0",
        "aria-label": "地図を表示する",
      },
      [
        el("span", { "class": "candidate-map-open-icon", "aria-hidden": "true" }, ["🗺"]),
        el("span", { "class": "candidate-map-open-label" }, ["地図で見る"]),
      ]
    );
    mapOpenButton.addEventListener("click", function () {
      openMapSheet();
    });
    mapOpenButton.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openMapSheet();
      }
    });
    // Design realignment (human real-device report 2026-08-25,
    // E:\AWS\dsg-out\MapSheet.dc.html): a 52px header bar ("リストへ戻る"
    // + a position counter), not a floating circular X in the corner.
    // Keeps the existing candidate-map-sheet-close test id/purpose (same
    // close behavior, no data-candidate-control-purpose -- see this file's
    // own earlier comment for why) on the back-labelled element itself.
    var sheetCloseButton = el(
      "div",
      {
        "data-testid": "candidate-map-sheet-close",
        "class": "candidate-map-sheet-back",
        tabindex: "0",
        "aria-label": "地図を閉じてリストへ戻る",
      },
      [
        el("span", { "class": "candidate-map-sheet-back-icon", "aria-hidden": "true" }, ["←"]),
        el("span", {}, ["リストへ戻る"]),
      ]
    );
    sheetCloseButton.addEventListener("click", function () {
      closeMapSheet();
    });
    sheetCloseButton.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        closeMapSheet();
      }
    });
    mapSheetCounterEl = el(
      "span",
      { "class": "candidate-map-sheet-counter", "aria-live": "polite", "aria-label": "選択中の候補" },
      [""]
    );
    var mapSheetHeader = el("div", { "class": "candidate-map-sheet-header" }, [
      sheetCloseButton,
      mapSheetCounterEl,
    ]);
    mapSheetPanelEl = el("div", { "class": "candidate-map-sheet-panel" }, []);
    var mapWrapper = el("div", { "class": "candidate-map-wrapper" }, [
      mapContainer,
      mapOpenButton,
      mapSheetHeader,
      mapSheetPanelEl,
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
    mapWrapperEl = mapWrapper;

    var cardsContainer = el("div", { "data-testid": "candidate-proposal-cards" }, []);
    body.candidates.forEach(function (candidate, index) {
      var card = renderCard(candidate, index === 0, index);
      orderedCardElements.push(card);
      cardsContainer.appendChild(card);
    });
    cardsContainerEl = cardsContainer;
    selectedCandidateRef = body.candidates.length > 0 ? body.candidates[0].candidateRef : null;

    // DOM order is ribbon-then-list (the ribbon is the compact map preview
    // sitting above the list, task 3) -- CSS lays this out as a simple
    // vertical stack at every width (home.html), so this DOM order is what
    // keyboard/reader users encounter throughout.
    mainLayout.appendChild(mapWrapper);
    mainLayout.appendChild(cardsContainer);
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
    initializeMap(mapContainer, body.candidates, body.searchOrigin);
  }

  function handleProposalResponse(status, body) {
    if (status === 200) {
      hasDisplayedProposal = true;
      currentAvailableGenres = body.availableGenres || [];
      populationAttributes = body.populationAttributes || [];
      updateShownCandidateMemory(body);
      pendingFilters = cloneFilters(currentFilters);
      renderFilterBar();
      renderResult(body);
      return;
    }
    // TDR-CS-16: retain the existing display (cards, map, applied filters,
    // condition summary) whenever a proposal was already shown -- see
    // renderProblem's `additive` parameter.
    renderProblem(body.code, body.message, hasDisplayedProposal);
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
