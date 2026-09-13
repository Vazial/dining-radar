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
  // Human decision 2026-08-26 added 5 ("徒歩5分もあってもいいかも"); the
  // filter-side 5 preset is the developer's own extension for the same
  // change, not itself asked for by the human -- see the mirrored Python
  // constant's own comment.
  var WALKING_TIME_MAX_PRESETS_MINUTES = [5, 10, 15, 20, 30];
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

  // adr/0030 decision 1 + human decision 2026-08-26: every non-accent ring
  // now shares one dash pattern/opacity (see the CSS rule for
  // [data-testid="candidate-walking-radius-ring"] in home.html) -- the
  // earlier per-band dash/opacity step-down (solid -> dotted, innermost to
  // outermost) read as "それぞれ線が違います" on a real device once each
  // ring already carries its own legible minute label. The ring matching
  // the currently applied walking-time-max filter (if any) still gets a
  // distinct accent style via the CSS "--accent" modifier classes below.
  var WALKING_RADIUS_RING_BASE_WEIGHT = 1.8;
  var WALKING_RADIUS_RING_CASING_EXTRA_WEIGHT = 3;
  var WALKING_RADIUS_RING_ACCENT_WEIGHT = 2.4;
  // Nudge margin (pixels) a ring's label is kept inside the visible map
  // container by, so a label is never clipped flush against the edge.
  var WALKING_RADIUS_RING_LABEL_MARGIN_PX = 20;
  // Real-device report (2026-08-26): a ring's minute label was rendered
  // directly behind a candidate-map-marker pin, hiding it. Designer's own
  // spec only says "put the label on top of the line" -- no rule for
  // avoiding a marker, so this developer-chosen placement strategy tries a
  // small set of points around each ring's own circumference (clockwise
  // degrees from due north, the previous fixed position, tried first so a
  // label only moves when it actually needs to) and picks the first one
  // that does not overlap any candidate/origin marker or an already-placed
  // ring label, falling back to the original north position if every
  // candidate collides (a slightly crowded label still beats none at all).
  var WALKING_RADIUS_RING_LABEL_ANGLES_DEG = [0, 45, -45, 90, -90, 135, -135, 180];
  // Conservative estimated half-extents (pixels) used only for this
  // collision check, not for actual layout -- generous enough to cover the
  // widest label text ("30分" at this chip's font-size/padding) without
  // measuring the real (not-yet-attached) DOM element.
  var WALKING_RADIUS_RING_LABEL_HALF_WIDTH_PX = 30;
  var WALKING_RADIUS_RING_LABEL_HALF_HEIGHT_PX = 14;
  // Candidate/origin marker icon half-sizes (iconSize is 44/28px square,
  // anchored at its own center -- see initializeMap below), used the same
  // way.
  var CANDIDATE_MAP_MARKER_HALF_SIZE_PX = 22;
  var CANDIDATE_ORIGIN_MARKER_HALF_SIZE_PX = 14;

  // Leaflet's fitBounds `padding` option applies one [x,y] pair
  // symmetrically to every edge; `paddingTopLeft`/`paddingBottomRight`
  // accept an asymmetric box instead. adr/0033's mobile map-primary-touch
  // deck still overlaps the bottom of its own map by design (human decision
  // 2026-08-29), so this asymmetric padding biases the fitted view toward
  // the map's own upper region, clear of the deck's own measured height,
  // whenever a deck is actually present -- adr/0049 decision4 retired the
  // desktop deck this used to also account for (isTwoColumnLayout's map
  // column has no overlay at all, so mapWrapperEl there never contains a
  // .candidate-deck element and this naturally falls back to the plain,
  // symmetric 24px padding below without any mode check needed here). This
  // is a best-effort mitigation, not a guarantee -- a wide-enough candidate
  // spread can still place a marker or a ring under the deck regardless of
  // padding (see activeContext.md for this project's own real-device
  // measurement of how well it holds up).
  function mapPrimaryFitPaddingOptions() {
    var deckEl = mapWrapperEl ? mapWrapperEl.querySelector(".candidate-deck") : null;
    var deckHeight = deckEl ? deckEl.getBoundingClientRect().height : 0;
    return {
      paddingTopLeft: window.L.point(24, 24),
      paddingBottomRight: window.L.point(24, deckHeight > 0 ? deckHeight + 64 : 24),
    };
  }

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

  // adr/0049 decision 1: gathering mode. This contract does not fix the
  // exact navigation mechanism into this mode (gatheringMode's own
  // description) -- a URL query parameter is this implementation's choice,
  // read once at module load and carried unchanged on every later
  // applyFilters/searchAgain request while this screen stays in gathering
  // mode (requestProposal below attaches it whenever non-null).
  function readGatheringIdFromUrl() {
    var params = new URLSearchParams(window.location.search);
    var value = params.get("gatheringId");
    return value ? value : null;
  }
  var gatheringModeId = readGatheringIdFromUrl();
  // The most recent response's gatheringContext (null outside gathering
  // mode, or before any proposal has loaded) -- renderResult/renderCard
  // read this to decide whether to render gatheringMode's band/cardToggle
  // at all (their own presenceRule: present exactly when non-null).
  var currentGatheringContext = null;
  // This render's Candidate objects keyed by candidateRef -- lets
  // toggleCardGatheringShortlist read each currently-displayed card's own
  // shopId without a dedicated DOM attribute (mirrors cardElementsByRef's
  // own by-ref lookup convention).
  var currentCandidatesByRef = {};

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

  // There is exactly one Leaflet map instance throughout a render.
  // selectedCandidateRef mirrors the currently selected candidate outside of
  // selectCandidate's own DOM bookkeeping; latLngByRef lets a later re-center
  // (selectMarker's deckVisibility) re-use a candidate's coordinates without
  // re-deriving them. orderedCardElements/cardsContainerEl support the
  // mobile deck's own sliding-window paging (recomputeDeckWindow) without
  // ever cloning a candidate-card element.
  var selectedCandidateRef = null;
  var latLngByRef = {};
  var orderedCardElements = [];
  var cardsContainerEl = null;
  var mapWrapperEl = null;

  // adr/0049 decision 4 (2026-09-08 human decision: "微妙。右に地図で一覧左
  // とかじゃなかったっけ") retired adr/0031's desktop map-primary,
  // button-paged deck in favor of a plain two-column list-and-map layout --
  // isTwoColumnLayout (renamed from isMapPrimaryLayout) and
  // isMapPrimaryTouchLayout (adr/0033's mobile map-primary-touch deck,
  // human decision 2026-08-29, unchanged by this revision) remain mutually
  // exclusive, render-time flags renderResult sets once per response
  // (adr/0032 decision3: no live-resize mode switching) that selectCandidate
  // (defined before renderResult in this file, hence these module-scope
  // variables rather than local ones) also needs to decide whether to page
  // the mobile deck to reveal a newly selected candidate (deckVisibility,
  // adr/0033 decision5 -- trivially satisfied while isTwoColumnLayout holds,
  // since every card is already visible at once). deckWindowStart/
  // deckWindowSize track the mobile deck's own sliding window state (1-based,
  // see recomputeDeckWindow); the *El variables are renderDeck's own built
  // elements (only ever populated while isMapPrimaryTouchLayout holds, since
  // renderResult calls renderDeck only in that branch now), reset on every
  // renderResult call the same way cardsContainerEl/mapWrapperEl already are
  // above. deckSwipeState tracks an in-progress pointer gesture on
  // candidate-deck-swipe-surface (mapPrimaryTouchLayout only; see
  // attachSwipeGesture below).
  var isTwoColumnLayout = false;
  var isMapPrimaryTouchLayout = false;
  var deckWindowStart = 1;
  var deckWindowSize = 1;
  var deckViewportEl = null;
  var deckPositionEl = null;
  var deckPeekEl = null;
  var deckSwipeState = null;

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
    // adr/0049 decision 1: every request carries the same gatheringId while
    // this screen remains in gathering mode (gatheringMode's own
    // description: "every applyFilters/searchAgain ... carries that same
    // gatheringId").
    if (gatheringModeId) {
      body.gatheringId = gatheringModeId;
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
    // browserActions.selectMarker's deckVisibility (adr/0033 decision5):
    // while isMapPrimaryTouchLayout holds, the newly selected candidate's
    // own card must be inside the deck's visible window immediately after
    // selection, regardless of whether selection came from a card click
    // (already visible, since only visible cards are clickable outside the
    // deck's clipped overflow) or a marker click/keydown (may name a
    // candidate currently outside the window). Applying this
    // unconditionally, not only for the marker path, keeps one shared rule
    // rather than branching on the caller. recomputeDeckWindow itself is a
    // no-op while isTwoColumnLayout holds (deckViewportEl stays null then),
    // which is exactly deckVisibility's "trivially satisfied" clause for
    // that mode -- every card is already visible in the unpaged list.
    recomputeDeckWindow(candidateRef);
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

    // Design realignment (human real-device report 2026-08-25, E:\AWS    // dsg-out\Main.dc.html's own .card markup): the id row originally
    // carried the badge, the shop name itself, and the walking-time
    // estimate as a trailing chip, all on one line -- not just the badge
    // with genre trailing it. Genre moves to its own plain-text line (no
    // chip) directly above the description, and walking time moves out of
    // the facts grid entirely, leaving the facts grid exactly the
    // four/three items the design's own 2-column grid shows.
    //
    // Human real-device report, deck round (2026-08-29): at the deck's
    // fixed 16.25rem card width, cramming badge+name+chip onto one row
    // left the shop name -- "この画面で一番大事な情報" per the human's own
    // chat decision -- as little as ~75-79% of its needed width even for
    // the synthetic population's own longest name, and far worse for real
    // names ("ドラゴンレッドリバー DRAGON RED RIVER" etc). Human decision
    // (2026-08-29 chat, choosing among three costed options) moved the
    // walking-time chip out of the id row and onto the genre line for
    // every fixed-width deck card (adr/0033 later the same day gave both
    // render modes' cards this same narrow, fixed width, so the fix that
    // started scoped to >=64rem carried unchanged to mobile too). adr/0049
    // decision4 (2026-09-08 human decision) retired the desktop deck's own
    // fixed-width card in favor of isTwoColumnLayout's plain list column
    // (E:\AWS\dsg-out\party\Deck.dc.html's own board, whose card markup
    // restores the chip to the id row now that the column is wide enough
    // that cramming does not recur -- board's own `.top`/`.genre` split).
    // isMapPrimaryTouchLayout's own deck card is unchanged by this
    // revision (still fixed-width, still narrow, per DeckPhone.dc.html) --
    // this is therefore a per-mode placement choice again, not the single
    // shared one adr/0033 settled on, and isTwoColumnLayout is read once
    // per render before renderCard is ever called (renderResult, above),
    // so it is decided once per render, not per card.
    var walkChip = el(
      "span",
      {
        "data-testid": "candidate-card-walking-time",
        "data-field-label": "徒歩",
        "data-value-state": "provided",
        "class": "candidate-walk-chip",
      },
      // adr/0025 decision 2: always provided (never "情報なし" -- walking
      // time is always computable from the response's own searchOrigin and
      // this candidate's location), so no rawValueAttribute is declared --
      // the visible value and the raw response number are the same value,
      // unlike totalSeats/nonSmokingStatus/dinnerBudgetTier's coarse-label
      // translations below. The leading "約" is the required estimate-
      // wording signal (candidate-search-browser-interface.yaml's
      // walkingTimeEstimateWording): this is an estimate, not a measured
      // route. Contract only fixes this element's own testid/field-label/
      // value-state/text and content-only wording -- not which row it
      // lives in or that it be a dt/dd fieldRow pair (placement is left an
      // implementation choice, per that same Must's own text) -- so a
      // standalone chip carries the same attributes fieldRow would have,
      // relocatable without touching any of them.
      ["徒歩 約" + candidate.walkingTimeMinutes + "分"]
    );

    var idRowChildren = [
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
    ];
    if (isTwoColumnLayout) {
      idRowChildren.push(walkChip);
    }
    var idRow = el("div", { "class": "candidate-card-id-row" }, idRowChildren);
    card.appendChild(idRow);

    var genreText = el(
      "p",
      { "data-testid": "candidate-card-genre", "data-field-label": "ジャンル", "data-value-state": "provided", "class": "candidate-genre-text" },
      [candidate.genre]
    );
    // isTwoColumnLayout already placed walkChip in the id row above (a
    // plain genre line, matching Deck.dc.html's board); isMapPrimaryTouchLayout
    // keeps sharing genre and the walking-time chip on one row (see the
    // walkChip comment above) so its own narrow id row can give the shop
    // name essentially the whole card width (home.html's own
    // .candidate-deck-viewport [data-testid="candidate-card-name"]
    // flex-grow rule) instead of splitting it with the chip.
    var genreRowChildren = isTwoColumnLayout ? [genreText] : [genreText, walkChip];
    card.appendChild(el("div", { "class": "candidate-genre-row" }, genreRowChildren));

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
    //
    // The 2026-09-01 D-fix 案B height-equalization reserved box (a hidden
    // placeholder occupying this same space on every card, so the PC deck's
    // side-by-side cards' bottom edges lined up regardless of which ones
    // showed the caution) is retired along with the PC deck itself
    // (adr/0049 decision4's own "D-fix 1・D-fix 2の前提消滅": isTwoColumnLayout's
    // cards stack in a single column, not side by side, so there is no
    // shared row of bottom edges left to line up). isMapPrimaryTouchLayout
    // never used this reservation either (its own deck shows one card at a
    // time).
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

    // adr/0049 decision 1: gatheringMode.cardToggle -- present on every
    // candidate-card exactly when response.gatheringContext is non-null.
    if (currentGatheringContext) {
      var toggle = renderGatheringCardToggle(candidate);
      card.appendChild(toggle);
      // ADR-0057 decision 3: cardToggle.lastShopNotice -- present on this
      // same card exactly when its own cardToggle carries
      // data-gathering-toggle-disabled-reason="last-shop". Shares
      // syncGatheringCardLastShopNotice with the post-toggle update below
      // so the initial render and every later update place this element
      // identically (immediately after cardToggle).
      syncGatheringCardLastShopNotice(
        card,
        toggle,
        toggle.getAttribute("data-gathering-toggle-disabled-reason")
      );
    }

    cardElementsByRef[candidate.candidateRef] = card;
    return card;
  }

  // adr/0049 decision 8 (case 1, "limit-reached"): this card is not
  // currently shortlisted and the gathering has already reached its 5-shop
  // cap. ADR-0057 decision 1 (case 2, "last-shop", 2026-09-13 human ruling
  // "押せない見た目にして理由を出す"): this card *is* currently shortlisted
  // and is the gathering's last remaining shortlisted shop --
  // setShortlistedShops' minItems: 1 (P2, adr/0041) would reject the empty
  // list an activation would otherwise submit. The two cases are mutually
  // exclusive (they require opposite isShortlisted values), so at most one
  // ever applies to a given card. Returns null when the toggle is enabled.
  //
  // tests/js_unit/gathering_card_toggle_disabled_reason.test.js loads this
  // exact block verbatim (delimited by the start/end markers below, mirrors
  // participant.js's own request-sequencer extraction precedent, ADR-0014)
  // to pin this boundary logic without a full jsdom layer.
  // gathering-card-toggle-disabled-reason:start
  function gatheringCardToggleDisabledReason(isShortlisted) {
    if (
      !isShortlisted &&
      currentGatheringContext.shortlistedShopCount >= currentGatheringContext.maxShortlistedShops
    ) {
      return "limit-reached";
    }
    if (isShortlisted && currentGatheringContext.shortlistedShopCount <= 1) {
      return "last-shop";
    }
    return null;
  }
  // gathering-card-toggle-disabled-reason:end

  function renderGatheringCardToggle(candidate) {
    var isShortlisted = candidate.isShortlisted === true;
    var disabledReason = gatheringCardToggleDisabledReason(isShortlisted);
    var attrs = {
      type: "button",
      "data-testid": "candidate-card-gathering-toggle",
      "data-candidate-control-category": "button",
      "data-candidate-control-purpose": "candidate-card-gathering-toggle",
      "data-gathering-shortlisted": isShortlisted ? "true" : "false",
      "class": "candidate-gathering-toggle" + (isShortlisted ? " candidate-gathering-toggle--on" : ""),
    };
    // ADR-0057 decision 2: data-gathering-toggle-disabled-reason is present
    // (with exactly one of "limit-reached"/"last-shop") only while the
    // toggle is disabled -- absent (not merely empty) otherwise, since `el`
    // skips any attribute whose value is null/undefined/false.
    attrs["data-gathering-toggle-disabled-reason"] = disabledReason || false;
    var button = el(
      "button",
      attrs,
      [isShortlisted ? "この会に入れました" : "この会に入れる"]
    );
    if (disabledReason) {
      button.disabled = true;
    }
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      toggleCardGatheringShortlist(candidate.candidateRef);
    });
    return button;
  }

  // ADR-0057 decision 3: gatheringMode.cardToggle.lastShopNotice
  // (testId candidate-card-gathering-last-shop-notice, formControl: false).
  // A non-interactive, non-`<button>` element -- were it somehow made
  // interactive, activating it is not a recognized input and produces no
  // public operation or state change, so it stays outside
  // unavailableControls.allCandidateScreenFormControlsMustDeclarePurpose's
  // scan (no data-candidate-control-purpose/category here), the same
  // precedent gatheringEntry.entry.requirement and
  // candidate-gathering-mode-band's navigation paragraph already document.
  // The visible text is for the organizer alone (this contract's own
  // content-only-Must, reviewer-prose-forbidden pattern) -- it conveys that
  // at least one shop always stays in the gathering; the exact wording is
  // an implementation choice the contract does not fix.
  function renderGatheringCardLastShopNotice() {
    return el(
      "p",
      {
        "data-testid": "candidate-card-gathering-last-shop-notice",
        "class": "candidate-gathering-toggle-last-shop-notice",
      },
      ["最低1件は残します"]
    );
  }

  // ADR-0057 decision 3 (2026-09-13 human ruling): the notice sits "そばに"
  // (beside) the toggle it explains -- shared by both the initial render
  // (renderCard, immediately after this same card's own cardToggle is first
  // appended) and every later toggleCardGatheringShortlist update, so a
  // card that loads with exactly 1 shortlisted shop and a card that drops
  // to 1 after a later toggle always end up with identical DOM order
  // (cardToggle immediately followed by its own lastShopNotice, if any),
  // rather than each path picking its own placement mechanism that could
  // silently drift apart. `toggleEl` must already be attached to `cardEl`
  // before this is called.
  function syncGatheringCardLastShopNotice(cardEl, toggleEl, disabledReason) {
    var existingNotice = cardEl.querySelector(
      '[data-testid="candidate-card-gathering-last-shop-notice"]'
    );
    if (disabledReason === "last-shop") {
      if (!existingNotice) {
        toggleEl.insertAdjacentElement("afterend", renderGatheringCardLastShopNotice());
      }
    } else if (existingNotice) {
      existingNotice.remove();
    }
  }

  // adr/0049 decision 1 (toggleCardGatheringShortlist): the complete
  // replacement shopIds array is built from every currently-displayed
  // card's own data-gathering-shortlisted="true" state at the moment of
  // activation, with this card's shopId added (if it was "false") or
  // removed (if it was "true") -- this action never calls
  // candidate-search-api.yaml's own /candidate-proposals; it targets
  // gathering-scheduling-api.yaml's setShortlistedShops directly (this
  // contract's first browserAction whose publicOperation targets a
  // different contract's endpoint).
  function toggleCardGatheringShortlist(candidateRef) {
    if (!currentGatheringContext) {
      return;
    }
    var shopIds = [];
    var thisShopId = null;
    orderedCardElements.forEach(function (cardEl) {
      var toggleEl = cardEl.querySelector('[data-testid="candidate-card-gathering-toggle"]');
      if (!toggleEl) {
        return;
      }
      var ref = cardEl.getAttribute("data-candidate-ref");
      var shopId = currentCandidatesByRef[ref] ? currentCandidatesByRef[ref].shopId : null;
      var isOn = toggleEl.getAttribute("data-gathering-shortlisted") === "true";
      if (ref === candidateRef) {
        thisShopId = shopId;
        isOn = !isOn;
      }
      if (isOn && shopId) {
        shopIds.push(shopId);
      }
    });
    if (thisShopId === null) {
      return;
    }
    fetch("/gatherings/" + encodeURIComponent(currentGatheringContext.gatheringId) + "/shortlisted-shops", {
      method: "PUT",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify({ shopIds: shopIds }),
    })
      .then(function (response) {
        return response.status === 200 ? response.json() : null;
      })
      .then(function (gathering) {
        // errorOutcome: a rejected call leaves cardToggle/band unchanged --
        // this contract fixes no distinct visible error surface beyond that
        // no-op-on-failure guarantee, so a null (non-200) response here is
        // silently ignored.
        if (!gathering) {
          return;
        }
        var updatedShopIds = {};
        (gathering.shortlistedShops || []).forEach(function (shop) {
          updatedShopIds[shop.shopId] = true;
        });
        currentGatheringContext = {
          gatheringId: currentGatheringContext.gatheringId,
          title: currentGatheringContext.title,
          confirmedCandidateDate: currentGatheringContext.confirmedCandidateDate,
          shortlistedShopCount: (gathering.shortlistedShops || []).length,
          maxShortlistedShops: currentGatheringContext.maxShortlistedShops,
        };
        // ADR-0056 decision 7: data-shortlist-limit-reached is "true"
        // exactly when shortlistedShopCount >= maxShortlistedShops, the
        // same boundary gatheringCardToggleDisabledReason already computes
        // per card, exposed once at the band level.
        var limitReached =
          currentGatheringContext.shortlistedShopCount >= currentGatheringContext.maxShortlistedShops;
        var band = root.querySelector('[data-testid="candidate-gathering-mode-band"]');
        if (band) {
          band.setAttribute(
            "data-gathering-shortlisted-count",
            String(currentGatheringContext.shortlistedShopCount)
          );
          band.setAttribute(
            "data-gathering-max-shortlisted",
            String(currentGatheringContext.maxShortlistedShops)
          );
          band.setAttribute("data-shortlist-limit-reached", limitReached ? "true" : "false");
          // Keep the band's own visible face (ADR-0054 decision 4's "数が
          // 読めること自体が合図" design) and its returnToGatheringFromBand
          // href in lockstep with renderGatheringModeBand's own state
          // computation above -- band.href does not change (this is still
          // the same gathering), only the modifier class and count text.
          band.classList.remove(
            "candidate-gathering-mode-band--empty",
            "candidate-gathering-mode-band--filled",
            "candidate-gathering-mode-band--full"
          );
          var countEl = band.querySelector(".candidate-gathering-mode-band-count");
          if (currentGatheringContext.shortlistedShopCount === 0) {
            band.classList.add("candidate-gathering-mode-band--empty");
            if (countEl) {
              countEl.textContent = "会にもどる";
            }
          } else {
            band.classList.add(
              limitReached
                ? "candidate-gathering-mode-band--full"
                : "candidate-gathering-mode-band--filled"
            );
            if (countEl) {
              countEl.textContent =
                String(currentGatheringContext.shortlistedShopCount) + "件を入れて会にもどる";
            }
          }
        }
        // This response's fresh gatheringContext (reassigned above) is what
        // gatheringCardToggleDisabledReason reads, so every currently-
        // displayed card's disabled state/reason/notice is recomputed here
        // -- not just the card whose toggle was activated -- since a single
        // shortlistedShopCount change (e.g. crossing 5, or dropping to 1)
        // can flip every other card's own boundary at once (ADR-0057,
        // adr/0049 decision 8).
        orderedCardElements.forEach(function (cardEl) {
          var toggleEl = cardEl.querySelector('[data-testid="candidate-card-gathering-toggle"]');
          if (!toggleEl) {
            return;
          }
          var ref = cardEl.getAttribute("data-candidate-ref");
          var shopId = currentCandidatesByRef[ref] ? currentCandidatesByRef[ref].shopId : null;
          var isOn = !!updatedShopIds[shopId];
          toggleEl.setAttribute("data-gathering-shortlisted", isOn ? "true" : "false");
          toggleEl.textContent = isOn ? "この会に入れました" : "この会に入れる";
          toggleEl.classList.toggle("candidate-gathering-toggle--on", isOn);
          var disabledReason = gatheringCardToggleDisabledReason(isOn);
          toggleEl.disabled = disabledReason !== null;
          if (disabledReason) {
            toggleEl.setAttribute("data-gathering-toggle-disabled-reason", disabledReason);
          } else {
            toggleEl.removeAttribute("data-gathering-toggle-disabled-reason");
          }
          // ADR-0057 decision 3: keep this card's lastShopNotice in
          // lockstep with its own toggle's disabledReason -- shares
          // syncGatheringCardLastShopNotice with renderCard's initial
          // render (see that call site's own comment) so both paths always
          // place this element identically.
          syncGatheringCardLastShopNotice(cardEl, toggleEl, disabledReason);
          // ADR-0056 decision 4: keep this candidateRef's marker in
          // lockstep with its card -- a card and its marker always agree.
          var markerEl = markerElementsByRef[ref];
          if (markerEl) {
            markerEl.setAttribute("data-gathering-shortlisted", isOn ? "true" : "false");
          }
        });
      })
      .catch(function () {});
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
        radiusPx: radiusPx,
        visible: visible,
      };
    });

    // Nudge an off-center label back into the visible map area (designer:
    // "画面外に出る輪は画面内へ寄せる"), inset by a margin so it never sits
    // flush against the edge.
    function clampLabelPointToContainer(point) {
      return window.L.point(
        Math.min(
          Math.max(point.x, WALKING_RADIUS_RING_LABEL_MARGIN_PX),
          containerSize.x - WALKING_RADIUS_RING_LABEL_MARGIN_PX
        ),
        Math.min(
          Math.max(point.y, WALKING_RADIUS_RING_LABEL_MARGIN_PX),
          containerSize.y - WALKING_RADIUS_RING_LABEL_MARGIN_PX
        )
      );
    }

    // A label at candidatePoint overlaps a keep-out entry when both axes'
    // gaps are smaller than the two boxes' combined half-extents -- a plain
    // axis-aligned rectangle overlap test, generous enough (see the two
    // *_HALF_*_PX constants above) to not need the label's real, not-yet-
    // attached DOM size.
    function labelPointCollides(candidatePoint, keepOutEntries) {
      return keepOutEntries.some(function (entry) {
        return (
          Math.abs(candidatePoint.x - entry.point.x) <
            WALKING_RADIUS_RING_LABEL_HALF_WIDTH_PX + entry.halfWidth &&
          Math.abs(candidatePoint.y - entry.point.y) <
            WALKING_RADIUS_RING_LABEL_HALF_HEIGHT_PX + entry.halfHeight
        );
      });
    }

    // Every candidate/origin marker's current on-screen position, used only
    // to steer ring labels away from them (see
    // WALKING_RADIUS_RING_LABEL_ANGLES_DEG's own comment above) -- markers
    // themselves are laid out separately by initializeMap, which always
    // populates latLngByRef before this function runs (both on initial
    // load and on every later re-layout).
    var labelKeepOutEntries = Object.keys(latLngByRef).map(function (ref) {
      return {
        point: map.latLngToContainerPoint(latLngByRef[ref]),
        halfWidth: CANDIDATE_MAP_MARKER_HALF_SIZE_PX,
        halfHeight: CANDIDATE_MAP_MARKER_HALF_SIZE_PX,
      };
    });
    labelKeepOutEntries.push({
      point: originPoint,
      halfWidth: CANDIDATE_ORIGIN_MARKER_HALF_SIZE_PX,
      halfHeight: CANDIDATE_ORIGIN_MARKER_HALF_SIZE_PX,
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
      var casingClassName =
        "candidate-walking-radius-ring-casing" +
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
        "candidate-walking-radius-ring-path" +
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

      // Try each candidate angle around this ring's own circumference (due
      // north first, matching the previous fixed position), clamped into
      // the visible map area the same way as before, until one does not
      // collide with a marker or an already-placed ring label. Falls back
      // to the plain north-clamped position (the old, unconditional
      // behavior) if every candidate collides.
      var clampedPoint = null;
      for (var angleIndex = 0; angleIndex < WALKING_RADIUS_RING_LABEL_ANGLES_DEG.length; angleIndex++) {
        var angleRad = (WALKING_RADIUS_RING_LABEL_ANGLES_DEG[angleIndex] * Math.PI) / 180;
        var rawPoint = window.L.point(
          originPoint.x + ring.radiusPx * Math.sin(angleRad),
          originPoint.y - ring.radiusPx * Math.cos(angleRad)
        );
        var candidatePoint = clampLabelPointToContainer(rawPoint);
        if (!labelPointCollides(candidatePoint, labelKeepOutEntries)) {
          clampedPoint = candidatePoint;
          break;
        }
      }
      if (!clampedPoint) {
        clampedPoint = clampLabelPointToContainer(ring.northPoint);
      }
      labelKeepOutEntries.push({
        point: clampedPoint,
        halfWidth: WALKING_RADIUS_RING_LABEL_HALF_WIDTH_PX,
        halfHeight: WALKING_RADIUS_RING_LABEL_HALF_HEIGHT_PX,
      });
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

  // Re-fits the map to every candidate after a container resize (the map's
  // own box no longer changes shape on open/close -- there is no such state
  // left, adr/0033 -- so this now only ever runs from a genuine container
  // resize: window resize, mobile-toolbar dvh changes, orientation change,
  // or the deck's own ResizeObserver -- see initializeMap's ResizeObserver
  // below). Selecting a candidate never re-centers the map on its own (both
  // named renderModes only page the deck -- see selectCandidate above); the
  // map view always stays the fitBounds of every currently displayed
  // candidate.
  function refreshMapViewAndRings() {
    if (!leafletMap) {
      return;
    }
    leafletMap.invalidateSize();
    if (currentMapLatLngs.length > 0) {
      leafletMap.fitBounds(window.L.latLngBounds(currentMapLatLngs), mapPrimaryFitPaddingOptions());
    }
    layoutWalkingRadiusRings(leafletMap, walkingRadiusRingOrigin);
  }

  // adr/0033 decisions 2-3 (deckNavigation, browserActions.
  // pageDeckSwipeForward/Backward), narrowed to isMapPrimaryTouchLayout
  // only by adr/0049 decision4 (twoColumnLayout has no deck to page -- see
  // renderModes above): a sliding window, fixed at exactly one card wide
  // (Mobile.dc.html "可視窓が常に1件"), over the same ordered card list the
  // list column already renders (orderedCardElements) -- paging never
  // reorders, adds, or removes a data-candidate-ref
  // (deckNavigation.orderingInvariant), it only moves which already-ordered
  // card sits inside the window (contract's own "windowing/paging"
  // language).
  function deckTotal() {
    return orderedCardElements.length;
  }

  function deckMaxWindowStart(windowSize) {
    return Math.max(1, deckTotal() - windowSize + 1);
  }

  // contracts/candidate-search-browser-interface.yaml's deckNavigation.
  // position.presenceRule/valueShape (mapPrimaryTouchLayout only as of
  // adr/0049 decision4): 1-based visibleStart/visibleEnd/total decimal-
  // string attributes. visibleStart always equals visibleEnd (adr/0049
  // decision5's stopBehavior: the swipe surface always settles on exactly
  // one full card, never a partial one at either edge).
  function updateDeckPositionDisplay() {
    if (!deckPositionEl) {
      return;
    }
    var total = deckTotal();
    var visibleStart = total === 0 ? 0 : deckWindowStart;
    var visibleEnd = total === 0 ? 0 : Math.min(deckWindowStart + deckWindowSize - 1, total);
    deckPositionEl.setAttribute("data-deck-visible-start", String(visibleStart));
    deckPositionEl.setAttribute("data-deck-visible-end", String(visibleEnd));
    deckPositionEl.setAttribute("data-deck-total", String(total));
    deckPositionEl.textContent =
      total === 0
        ? ""
        : visibleStart === visibleEnd
          ? String(visibleStart) + " / " + String(total)
          : String(visibleStart) + "–" + String(visibleEnd) + " / " + String(total);
    if (cardsContainerEl) {
      // adr/0033: each card is exactly the swipe surface's own width
      // (home.html: `flex: 0 0 100%`), so a percentage offset stays exact
      // regardless of the surface's actual measured pixel width.
      var offsetPercent = (deckWindowStart - 1) * 100;
      cardsContainerEl.style.transform = "translateX(" + String(-offsetPercent) + "%)";
    }
    if (deckPeekEl) {
      // Orchestrator decision 2026-08-29 (Mobile.dc.html 論点1 案B): the
      // decorative peek sliver hints there is another card to swipe
      // forward to; hidden once the window has already reached the last
      // card, since there is nothing left to hint at.
      deckPeekEl.hidden = total === 0 || visibleEnd >= total;
    }
  }

  // Recomputes the deck's own visible window (called on initial render and
  // on every later selection), clamping the current window and, when
  // revealRef names a candidate currently outside it, moving the window to
  // include that candidate without changing card order
  // (browserActions.selectMarker's deckVisibility clause, adr/0033
  // decision5 -- a no-op while isTwoColumnLayout holds, since this
  // function returns immediately below whenever deckViewportEl is null,
  // which it always is under that mode: renderResult only calls renderDeck,
  // below, while isMapPrimaryTouchLayout holds).
  function recomputeDeckWindow(revealRef) {
    if (!deckViewportEl) {
      return;
    }
    // Mobile.dc.html: "可視窓が常に1件" -- the only render mode that still
    // builds a deck shows exactly one full-width card at a time, so the
    // window size is fixed at 1 rather than measured against the deck's
    // own pixel width.
    deckWindowSize = 1;
    var total = deckTotal();
    if (total === 0) {
      deckWindowStart = 1;
      updateDeckPositionDisplay();
      return;
    }

    if (revealRef) {
      var position = orderedCardElements.findIndex(function (card) {
        return card.getAttribute("data-candidate-ref") === revealRef;
      });
      if (position !== -1) {
        var position1 = position + 1;
        if (position1 < deckWindowStart) {
          deckWindowStart = position1;
        } else if (position1 > deckWindowStart + deckWindowSize - 1) {
          deckWindowStart = position1 - deckWindowSize + 1;
        }
      }
    }

    deckWindowStart = Math.max(1, Math.min(deckWindowStart, deckMaxWindowStart(deckWindowSize)));
    updateDeckPositionDisplay();
  }

  // pageDeckSwipeForward/Backward's own JS implementation
  // (attachSwipeGesture below) calls these two directly -- there is no
  // longer a button to call them (adr/0049 decision4 retired
  // mapPrimaryLayout's candidate-deck-previous/-next along with the rest of
  // the desktop deck; browserActions.pageDeckPrevious/Next, which those
  // buttons used to drive, are retired with them). The boundary check is on
  // the window's own data, so calling either function already at the
  // boundary is a no-op, which is exactly
  // browserActions.pageDeckSwipeForward/Backward's own boundaryOvershoot
  // requirement (adr/0033 decision3): it must not error, must not start a
  // public operation, and must leave start/end/total unchanged.
  function pageDeckNext() {
    if (!deckViewportEl || deckWindowStart + deckWindowSize - 1 >= deckTotal()) {
      return;
    }
    deckWindowStart = Math.min(deckMaxWindowStart(deckWindowSize), deckWindowStart + 1);
    updateDeckPositionDisplay();
  }

  function pageDeckPrevious() {
    if (!deckViewportEl || deckWindowStart <= 1) {
      return;
    }
    deckWindowStart = Math.max(1, deckWindowStart - 1);
    updateDeckPositionDisplay();
  }

  // adr/0033 decisions 2-3 (mapPrimaryTouchLayout, human decision
  // 2026-08-29): pages the deck with a horizontal pointer/touch drag that
  // begins inside candidate-deck-swipe-surface's own bounding box (the
  // floating card itself -- Mobile.dc.html 論点3's own "矩形の内側／外側"
  // split), entirely through this module's own Pointer Events handlers.
  // Leaflet's own pan/pinch handling is bound to the Leaflet map
  // container element, a sibling (not an ancestor) of this swipe surface
  // in the DOM (home.html: candidate-map and .candidate-deck are both
  // direct children of .candidate-map-wrapper) -- a gesture that starts
  // on the swipe surface is delivered to *this* element by the browser's
  // own hit-testing (whichever element is topmost at that screen point)
  // and never reaches Leaflet's handlers at all, so there is no
  // stopPropagation/preventDefault contest with Leaflet to resolve for
  // that split; a gesture that starts on the exposed map outside the
  // floating card's own rectangle never touches this element either way
  // and keeps panning/pinching the map exactly as before. preventDefault
  // below exists only to stop the browser's own default touch scrolling
  // once a drag is recognized as horizontal (home.html's own
  // `touch-action: pan-y` on this same element already limits what the
  // browser would otherwise try to interpret natively, so this is
  // belt-and-suspenders, not the primary mechanism).
  var SWIPE_THRESHOLD_PX = 40;
  var SWIPE_DIRECTION_SLOP_PX = 6;

  function attachSwipeGesture(surfaceEl) {
    function onPointerDown(event) {
      if (event.pointerType === "mouse" && event.button !== 0) {
        return;
      }
      deckSwipeState = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        dx: 0,
        horizontal: false,
      };
      if (surfaceEl.setPointerCapture) {
        try {
          surfaceEl.setPointerCapture(event.pointerId);
        } catch (error) {
          // Some synthetic/test pointer sources reject capture; the drag
          // still works via the move/up listeners below regardless.
        }
      }
    }

    function onPointerMove(event) {
      if (!deckSwipeState || event.pointerId !== deckSwipeState.pointerId) {
        return;
      }
      var dx = event.clientX - deckSwipeState.startX;
      var dy = event.clientY - deckSwipeState.startY;
      if (!deckSwipeState.horizontal) {
        if (Math.abs(dx) < SWIPE_DIRECTION_SLOP_PX && Math.abs(dy) < SWIPE_DIRECTION_SLOP_PX) {
          return;
        }
        if (Math.abs(dx) <= Math.abs(dy)) {
          // A vertical drag -- stop tracking it as a paging gesture and
          // let the page/browser handle it natively (e.g. scroll).
          deckSwipeState = null;
          return;
        }
        deckSwipeState.horizontal = true;
      }
      deckSwipeState.dx = dx;
      event.preventDefault();
    }

    function endGesture(event) {
      if (!deckSwipeState || event.pointerId !== deckSwipeState.pointerId) {
        deckSwipeState = null;
        return;
      }
      var dx = deckSwipeState.dx;
      deckSwipeState = null;
      if (Math.abs(dx) < SWIPE_THRESHOLD_PX) {
        return;
      }
      if (dx < 0) {
        pageDeckNext();
      } else {
        pageDeckPrevious();
      }
    }

    surfaceEl.addEventListener("pointerdown", onPointerDown);
    surfaceEl.addEventListener("pointermove", onPointerMove);
    surfaceEl.addEventListener("pointerup", endGesture);
    surfaceEl.addEventListener("pointercancel", endGesture);
  }

  // Builds the mobile map-primary-touch deck (adr/0033) -- around the same
  // candidate-proposal-cards element renderResult already built (never a
  // second/cloned card set). adr/0049 decision4 retired mapPrimaryLayout's
  // own desktop deck (button-paged, sharing this same scaffold) outright in
  // favor of isTwoColumnLayout's plain list column, so renderResult now
  // calls this function only while isMapPrimaryTouchLayout holds -- this is
  // no longer "common to both named renderModes", it is
  // mapPrimaryTouchLayout's own. The position counter
  // (candidate-deck-position) is a plain, non-interactive <span> (not
  // itself a control, so it needs no allowedPurposes entry -- adr/0031's
  // own text: "件数カウンタ自体は操作ではないためこの規則には掛からない").
  function renderDeck(cardsContainer) {
    deckPositionEl = el(
      "span",
      {
        "data-testid": "candidate-deck-position",
        "class": "candidate-deck-position",
        "aria-live": "polite",
        "aria-label": "表示中の候補の位置",
      },
      [""]
    );
    // deckViewportEl doubles as the swipe surface -- one element, not a
    // redundant extra wrapper -- since both the contract's own presenceRule
    // (present exactly once) and this file's existing overflow/gesture
    // needs are satisfied by the same box either way.
    deckViewportEl = el(
      "div",
      { "class": "candidate-deck-viewport", "data-testid": "candidate-deck-swipe-surface" },
      [cardsContainer]
    );
    attachSwipeGesture(deckViewportEl);
    deckPeekEl = el("div", { "class": "candidate-deck-peek", "aria-hidden": "true" }, []);
    var deck = el("div", { "class": "candidate-deck" }, [
      deckViewportEl,
      deckPeekEl,
      deckPositionEl,
    ]);
    return deck;
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
    // container is already connected to the live DOM by the time this runs
    // (root.appendChild(content) above, itself already attached, ran before
    // this function was called), so this initial fitBounds already measures
    // whichever real box the CSS gives the container right now: the
    // full-viewport-minus-chrome map-primary box, at every width now
    // (adr/0033 retired the earlier 88px closed band). Padding is the same
    // deck-aware mapPrimaryFitPaddingOptions at every width for the same
    // reason -- the deck (renderDeck) always floats over this box's own
    // bottom inset now, regardless of which of the two named renderModes
    // (button-paged or swipe-paged) this function's own caller, renderResult,
    // set before calling initializeMap -- see that assignment below.
    if (latLngs.length > 0) {
      map.fitBounds(window.L.latLngBounds(latLngs), mapPrimaryFitPaddingOptions());
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
      // ADR-0056 decision 4: mirrors cardToggle's own data-gathering-
      // shortlisted for this same candidateRef -- present on every marker
      // exactly when response.gatheringContext is non-null (gatheringMode),
      // absent on every marker otherwise. A card and its marker always
      // agree (renderGatheringCardToggle above computes the same value from
      // the same candidate.isShortlisted field).
      if (currentGatheringContext) {
        markerEl.setAttribute(
          "data-gathering-shortlisted",
          candidate.isShortlisted === true ? "true" : "false"
        );
      }
      markerEl.setAttribute("role", "button");
      markerEl.setAttribute("tabindex", "0");
      markerEl.setAttribute("data-candidate-control-category", "button");
      markerEl.setAttribute("data-candidate-control-purpose", "candidate-map-marker-selection");
      var markerVisual = markerEl.querySelector(".candidate-map-marker-visual");
      if (markerVisual) {
        markerVisual.textContent = String(index + 1);
      }
      markerEl.addEventListener("click", function () {
        // adr/0033 decision5 (Mobile.dc.html 論点3): tapping a pin is how
        // an organizer switches which candidate the deck shows -- the
        // deckVisibility requirement in selectCandidate above pages the
        // deck to reveal it under either named renderMode. revealCard=true
        // unconditionally now (previously `!mapSheetOpen`, which the
        // retired sheet mechanism made effectively always true anyway)
        // keeps this call's own observable behavior unchanged.
        selectCandidate(candidate.candidateRef, true);
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
        // adr/0033: the map is genuinely visible at every width now (no
        // more closed/invisible state to guard against, unlike the retired
        // 88px band this used to toggle tabindex=-1 for) -- always
        // keyboard-reachable, which
        // candidate-search-browser-interface.yaml's
        // displayOnlyOriginException explicitly tolerates either way.
        originMarkerEl.setAttribute("tabindex", "0");
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
    // `100dvh` (human decision 2026-08-22).
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

  // adr/0049 decision 1: the always-on, non-togglable "いまの条件" line
  // (band). Present exactly when response.gatheringContext is non-null; no
  // exception for the empty/no-results outcome (gatheringMode.band's own
  // presenceRule names only response.gatheringContext, not any other
  // render-state condition).
  //
  // ADR-0054 decision 4 / ADR-0056 decision 7 (2026-09-12 human ruling): the
  // band is also gatheringMode's *sole* return path back to the gathering --
  // no separate "戻る"/confirm control exists, because a shop already saves
  // the instant its toggle is activated (a later "confirm and return" would
  // falsely imply an unsaved state). Implemented as a plain `<a href>`
  // (browserActions.returnToGatheringFromBand's own "navigates to
  // gathering-scheduling-browser-interface.yaml's browserEntry.
  // organizerDashboard" requirement), not a `<button>` -- this keeps it
  // outside unavailableControls.allCandidateScreenFormControlsMustDeclare
  // Purpose's scan, mirroring candidate-gathering-entry's own precedent.
  // The band's own visible face changes with the count itself, so the
  // number reaching (or not reaching) the cap is the return signal: 0件=
  // white outline "会にもどる"; 1〜4件=filled "N件を入れて会にもどる";
  // 5件=a further, distinct fill color (ADR-0056 decision 7's own
  // data-shortlist-limit-reached mirrors this same boundary).
  function renderGatheringModeBand(context) {
    if (!context) {
      return null;
    }
    var limitReached = context.shortlistedShopCount >= context.maxShortlistedShops;
    var stateClass;
    var countText;
    if (context.shortlistedShopCount === 0) {
      stateClass = "candidate-gathering-mode-band--empty";
      countText = "会にもどる";
    } else if (limitReached) {
      stateClass = "candidate-gathering-mode-band--full";
      countText = String(context.shortlistedShopCount) + "件を入れて会にもどる";
    } else {
      stateClass = "candidate-gathering-mode-band--filled";
      countText = String(context.shortlistedShopCount) + "件を入れて会にもどる";
    }
    return el(
      "a",
      {
        href: "/gatherings/" + encodeURIComponent(context.gatheringId) + "/",
        "data-testid": "candidate-gathering-mode-band",
        "data-gathering-shortlisted-count": String(context.shortlistedShopCount),
        "data-gathering-max-shortlisted": String(context.maxShortlistedShops),
        "data-shortlist-limit-reached": limitReached ? "true" : "false",
        "class": "candidate-gathering-mode-band " + stateClass,
      },
      [
        el("span", { "class": "candidate-gathering-mode-band-condition" }, [
          formatGatheringConfirmedDate(context.confirmedCandidateDate) + "に開いている店",
        ]),
        el("span", { "class": "candidate-gathering-mode-band-count" }, [countText]),
      ]
    );
  }

  // A human-readable rendering of gatheringContext.confirmedCandidateDate
  // (an ISO-8601 date-time). This contract does not fix the exact wording/
  // date format (mirrors walkingTimeEstimateWording's own content-only
  // Musts) -- month/day + weekday is this implementation's choice.
  // Reads UTC accessors only, matching the shared-date-formatting
  // convention gathering.js/participant.js already establish for every
  // startAt/confirmedCandidateDate value (gathering-scheduling-api.yaml
  // tags every such instant as literal UTC on input --
  // dateTimeLocalValueToIso -- so display must read the same UTC
  // components back, not the viewing browser's own host timezone; see
  // gathering.js's own shared-date-formatting comment for the full TDR-
  // GTH-24-adjacent rationale this mirrors).
  function formatGatheringConfirmedDate(isoDateTime) {
    var date = new Date(isoDateTime);
    if (isNaN(date.getTime())) {
      return isoDateTime;
    }
    var weekday = ["日", "月", "火", "水", "木", "金", "土"][date.getUTCDay()];
    return (date.getUTCMonth() + 1) + "/" + date.getUTCDate() + " (" + weekday + ")";
  }

  function renderResult(body) {
    cardElementsByRef = {};
    orderedCardElements = [];
    selectedCandidateRef = null;
    cardsContainerEl = null;
    mapWrapperEl = null;
    // adr/0049 decision 1: this response's own gatheringContext -- null
    // outside gathering mode. renderCard reads this to decide whether to
    // render gatheringMode.cardToggle at all. currentCandidatesByRef lets
    // toggleCardGatheringShortlist below look up each currently-displayed
    // card's own Candidate.shopId without inventing a new DOM attribute.
    currentGatheringContext = body.gatheringContext || null;
    updateGatheringEntryActiveState();
    currentCandidatesByRef = {};
    (body.candidates || []).forEach(function (candidate) {
      currentCandidatesByRef[candidate.candidateRef] = candidate;
    });
    // adr/0033: reset every render, mirroring the resets above -- a fresh
    // proposal (search-again/apply-filters) always starts the mobile deck's
    // own window back at its first card, not wherever a previous response's
    // paging happened to leave it. These stay at their empty/null defaults
    // for the rest of this function whenever isTwoColumnLayout ends up
    // holding below, since renderDeck (the only place that populates them)
    // is then never called.
    deckWindowStart = 1;
    deckWindowSize = 1;
    deckViewportEl = null;
    deckPositionEl = null;
    deckPeekEl = null;
    deckSwipeState = null;
    root.innerHTML = "";

    // The filter bar is not part of this element: it lives outside the
    // response-driven region so it stays reachable across the success,
    // no-results, and problem outcomes alike (TDR-CS-05's "絞り込み条件を
    // 変更するよう案内される" needs the controls to survive an empty result).
    var content = el("section", { "data-testid": "candidate-proposal-content" }, []);

    var gatheringModeBand = renderGatheringModeBand(currentGatheringContext);
    if (gatheringModeBand) {
      content.appendChild(gatheringModeBand);
    }

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

    // data-map-sheet-open stays "false" unconditionally -- there is no
    // open/closed sheet state to model (retired by adr/0033) -- purely so
    // the >=64rem CSS block's own `:not([data-map-sheet-open="true"])`
    // -scoped selectors (unedited by this revision) keep matching exactly
    // as before -- see home.html's own comment on that block.
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
    var mapAttributionLink = el(
      "a",
      {
        "data-testid": "candidate-map-attribution",
        href: "https://www.openstreetmap.org/copyright",
        target: "_blank",
        rel: "noopener noreferrer",
      },
      ["© OpenStreetMap contributors"]
    );
    // Every width is one of exactly two mutually exclusive, exhaustive
    // named renderModes (contracts/candidate-search-browser-interface.yaml's
    // renderModes) -- isTwoColumnLayout (adr/0049 decision4, 2026-09-08
    // human decision: "微妙。右に地図で一覧左とかじゃなかったっけ", >=64rem, a
    // plain side-by-side list-and-map layout with no deck) or
    // isMapPrimaryTouchLayout (adr/0033, <64rem, a swipe-paged deck
    // overlaid on the map, unchanged by this revision). Both flags are read
    // once per render (matching this file's other one-shot,
    // render-time-only viewport reads; adr/0032 decision3 explicitly does
    // not require a live-resize mode switch) -- neither is re-evaluated on
    // a later browser-window resize across the 64rem boundary without a
    // fresh proposal response (search-again/filter apply both call
    // renderResult again, which re-reads them).
    isTwoColumnLayout = window.matchMedia && window.matchMedia("(min-width: 64rem)").matches;
    isMapPrimaryTouchLayout = !isTwoColumnLayout;

    var cardsContainer = el("div", { "data-testid": "candidate-proposal-cards" }, []);
    body.candidates.forEach(function (candidate, index) {
      var card = renderCard(candidate, index === 0, index);
      orderedCardElements.push(card);
      cardsContainer.appendChild(card);
    });
    cardsContainerEl = cardsContainer;
    selectedCandidateRef = body.candidates.length > 0 ? body.candidates[0].candidateRef : null;

    // adr/0049 decision4: isTwoColumnLayout places the card list in its own
    // column beside the map (no deck overlay -- every card is visible at
    // once, no paging needed); isMapPrimaryTouchLayout keeps decision5's
    // map-side rule (pins/rings only, never a duplicate detail panel -- full
    // detail stays in the deck's own cards) unchanged, with cardsContainer
    // moved inside the map wrapper's own deck overlay (renderDeck).
    var mapWrapper;
    if (isTwoColumnLayout) {
      mapWrapper = el("div", { "class": "candidate-map-wrapper" }, [mapContainer, mapAttributionLink]);
      mainLayout.appendChild(el("div", { "class": "candidate-list-column" }, [cardsContainer]));
      mainLayout.appendChild(mapWrapper);
    } else {
      mapWrapper = el("div", { "class": "candidate-map-wrapper" }, [
        mapContainer,
        renderDeck(cardsContainer),
        mapAttributionLink,
      ]);
      mainLayout.appendChild(mapWrapper);
    }
    mapWrapperEl = mapWrapper;

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
    recomputeDeckWindow();
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

  // ADR-0056 decision 8: candidate-gathering-entry.activeGathering --
  // data-active-gathering-id is present, with the current gathering's
  // opaque id as its exact string value, exactly when this screen was
  // reached in gathering mode (response.gatheringContext non-null);
  // absent -- the attribute itself missing, not merely empty -- on the
  // ordinary, non-gathering screen this same entry element also serves.
  // Independent of badge.presenceRule below (both live on the same
  // element but govern different things). Called synchronously from
  // renderResult (no network round trip of its own needed -- the value
  // already lives on currentGatheringContext).
  function updateGatheringEntryActiveState() {
    var entry = document.querySelector('[data-testid="candidate-gathering-entry"]');
    if (!entry) {
      return;
    }
    if (currentGatheringContext) {
      entry.setAttribute("data-active-gathering-id", currentGatheringContext.gatheringId);
    } else {
      entry.removeAttribute("data-active-gathering-id");
    }
  }

  // contracts/candidate-search-browser-interface.yaml's gatheringEntry
  // section (adr/0038): candidate-gathering-entry itself is plain,
  // server-rendered HTML (home.html) and therefore already present before
  // this script runs. Only the badge -- which mirrors
  // gathering-scheduling-api.yaml's getInProgressGatheringCount, a
  // different business contract's own resource -- is built here, once
  // fetched. Independent of the candidate-proposal request above: a
  // failure fetching one must never block or hide the other.
  function loadGatheringEntryBadge() {
    var entry = document.querySelector('[data-testid="candidate-gathering-entry"]');
    if (!entry) {
      return;
    }
    fetch("/gatherings/in-progress-count", { credentials: "same-origin" })
      .then(function (response) {
        return response.status === 200 ? response.json() : null;
      })
      .then(function (body) {
        if (!body) {
          return;
        }
        var count = body.inProgressGatheringCount;
        var badge = entry.querySelector('[data-testid="candidate-gathering-entry-badge"]');
        // presenceRule: present exactly when the count is greater than
        // zero; absent when it is zero (Handoff.dc.html: "0のときはバッジを
        // 出さない").
        if (count > 0) {
          if (!badge) {
            badge = el("span", { "data-testid": "candidate-gathering-entry-badge", "class": "candidate-gathering-entry-badge" }, []);
            entry.appendChild(badge);
          }
          badge.setAttribute("data-in-progress-gathering-count", String(count));
          badge.textContent = String(count);
        } else if (badge) {
          badge.remove();
        }
      })
      .catch(function () {});
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
      })
      // Real-measurement finding (this slice): firing this second fetch
      // concurrently with the initial /candidate-proposals request (rather
      // than after it settles) made an unrelated acceptance test's own
      // page.wait_for_load_state("networkidle") wait on -- and, in one
      // observed run, time out around -- a second in-flight request it had
      // never had to account for before this screen made any request
      // besides the proposal one on load. Sequencing this strictly after
      // the proposal request settles (success or failure) removes that
      // concurrency without changing what this call does or when a human
      // sees the badge appear in practice (it was already asynchronous).
      .finally(loadGatheringEntryBadge);
  });
})();
