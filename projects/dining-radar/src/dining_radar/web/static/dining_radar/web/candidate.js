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

  // Task 2 (human decision 2026-08-26): fitBounds' padding is symmetric on
  // one axis at a time -- Leaflet's `padding: [x, y]` shrinks the box it
  // fits the given bounds into by x on the left+right and y on the top+
  // bottom -- and the open-viewport value below (24, applied to a full-
  // screen box hundreds of px tall) barely matters there. The closed band
  // is a fixed 88px tall (home.html's .candidate-map-wrapper), so the same
  // 24 on *both* axes there left only 88 - 24*2 = 40px of usable height,
  // forcing fitBounds to pick a far-more-zoomed-out level than the band's
  // actual ~350-400px width would need on its own -- since a single zoom
  // level has to satisfy both axes at once, that over-zoomed-out level
  // compressed every candidate's pixel distance from the others too,
  // reproducing the real-device report's "5つのピンが帯の中央で重なって
  // いる" (measured: pins clustered into a single ~15px blob instead of
  // spreading across the band). Real-device round 9 measurement:
  // MAP_BAND_FIT_PADDING_PX's asymmetric [16, 6] (16px left/right, only
  // 6px top/bottom) roughly doubles the usable-height budget (88 - 6*2 =
  // 76px) while still keeping candidates near the band's own left/right
  // edges from touching it -- letting the band's own wide-short aspect
  // ratio actually drive the zoom level instead of being dominated by its
  // small height. Applied only while the sheet is closed (refreshMapView
  // AndRings/initializeMap below both branch on mapSheetOpen); the open,
  // full-screen fitBounds path (reached only when no candidate is
  // selected to setView on) is unchanged from before this task.
  //
  // Measured limit of this fix, worth recording rather than silently
  // discovering again later: Leaflet's fitBounds floors to the nearest
  // whole zoom level (zoomSnap defaults to 1), so shrinking the top/bottom
  // value further than 6 (tried 2 directly against this same local demo)
  // did not change the outcome at all -- the extra few pixels of budget
  // were not enough to cross the next zoom-level threshold. Separately,
  // this local demo's own NORMAL_WITH_WEIGHTED_SAMPLING synthetic
  // candidates (acceptance_state.py's _synthetic_candidate) all fix
  // longitude=0.0 by that module's own deliberate, documented design (an
  // exact 1-D latitude-only distance formula for deterministic walking-
  // time boundaries) -- so every candidate this padding value was tuned
  // against is collinear north-south, and no padding choice can spread
  // them east-west. Production candidates (real provider data) are not
  // collinear, so this same fix spreads them on both axes there; against
  // this synthetic fixture specifically it only ever had the latitude
  // axis to work with, which the measurement above (roughly doubled
  // vertical marker spread, band-clustering visibly reduced though not
  // eliminated -- five candidates spaced ~20m apart cannot occupy
  // visually distinct positions inside an 88px-tall real-scale map view
  // no matter the zoom) already accounts for.
  var MAP_BAND_FIT_PADDING_PX = [16, 6];
  var MAP_OPEN_FIT_PADDING_PX = [24, 24];

  // Desktop map-primary layout (adr/0031; Desktop.dc.html decision7=案A/
  // decision8=案あ, human decision 2026-08-28, superseding the 2026-08-26
  // sticky-2-column reading this comment used to describe): at >=64rem the
  // map fills essentially the whole viewport-height area below the header/
  // filter bar (home.html `@media (min-width: 64rem)` -- kept in exact
  // agreement with this same "64rem" literal here, since CSS media queries
  // and JS matchMedia cannot share one source of truth), with the card deck
  // overlaid on its own bottom inset (see renderDeck/isMapPrimaryLayout
  // below), not the mobile-only 88px closed band MAP_BAND_FIT_PADDING_PX's
  // own comment describes. isCompactMapBand tells the two fitBounds call
  // sites below (initializeMap, refreshMapViewAndRings) which padding suits
  // the box actually on screen: the closed band's own asymmetric padding
  // only makes sense for that specific tiny, wide-short box, never for the
  // full-viewport map-primary box (see mapPrimaryFitPaddingOptions below for
  // its own, deck-aware padding) or for the mobile sheet itself (already
  // excluded by the `!mapSheetOpen` check, unchanged from before this task).
  function isCompactMapBand() {
    return !mapSheetOpen && !(window.matchMedia && window.matchMedia("(min-width: 64rem)").matches);
  }

  // adr/0031 decisions 1-3 (desktop map-primary deck paging). Card width/gap
  // mirror Desktop.dc.html decision9's dcard (250px design value, rounded
  // here to 16.25rem/260px, measured to leave the shop name enough room to
  // read past 2-3 characters before ellipsizing at this card's own font
  // size, see activeContext.md) and this file's own 0.75rem inter-card gap
  // -- mirrored here (not just in CSS) so the sliding-window transform math
  // below (recomputeDeckWindow) stays exact rather than approximated from a
  // measured width, the same manual-sync obligation this file already
  // carries for WALKING_TIME_MAX_PRESETS_MINUTES/WALKING_DETOUR_FACTOR
  // above. Update these two values in the same change that edits
  // .candidate-deck-viewport [data-testid="candidate-card"]'s own
  // width/flex-basis and .candidate-deck-viewport [data-testid="candidate-
  // proposal-cards"]'s own gap rule in home.html.
  var DECK_CARD_WIDTH_PX = 260;
  var DECK_CARD_GAP_PX = 12;

  // adr/0031 decision7 (Desktop.dc.html "デッキを地図の下部4割程度に収め、
  // 上部6割を開けておく" -- the map-primary deck overlaps the bottom of the
  // map by design, human decision 2026-08-28). Leaflet's fitBounds `padding`
  // option applies one [x,y] pair symmetrically to every edge; `paddingTopLeft`/
  // `paddingBottomRight` accept an asymmetric box instead, which is what
  // actually lets the fitted view bias toward the map's own upper region,
  // clear of the deck's own measured height, rather than the deck's bottom
  // inset squeezing every edge equally. This is a best-effort mitigation,
  // not a guarantee -- a wide-enough candidate spread can still place a
  // marker or a ring under the deck regardless of padding (Desktop.dc.html's
  // own "穴" section calls this unverified; see activeContext.md for this
  // slice's own real-device measurement of how well it holds up).
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

  // adr/0031 (desktop map-primary deck, Desktop.dc.html decision7=案A/
  // decision8=案あ). isMapPrimaryLayout mirrors mapSheetOpen's own role
  // above -- a render-time flag renderResult sets once per response
  // (adr/0032 decision3: no live-resize mode switching) that selectCandidate
  // (defined before renderResult in this file, hence this module-scope
  // variable rather than a local one) also needs to decide whether to page
  // the deck to reveal a newly selected candidate (deckVisibility, adr/0031
  // decision3). deckWindowStart/deckWindowSize track the sliding window's
  // own state (1-based, see recomputeDeckWindow); the four *El variables are
  // renderDeck's own built elements, reset on every renderResult call the
  // same way cardsContainerEl/mapWrapperEl already are above.
  var isMapPrimaryLayout = false;
  var deckWindowStart = 1;
  var deckWindowSize = 1;
  var deckViewportEl = null;
  var deckPreviousEl = null;
  var deckNextEl = null;
  var deckPositionEl = null;
  var deckResizeObserver = null;

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
    // adr/0031 decision3 (deckVisibility): while the map-primary deck holds,
    // the newly selected candidate's own card must be inside the deck's
    // visible window immediately after selection, regardless of whether
    // selection came from a card click (already visible, since only visible
    // cards are clickable outside the deck's clipped overflow) or a marker
    // click/keydown (may name a candidate currently outside the window).
    // Applying this unconditionally, not only for the marker path, keeps
    // one shared rule rather than branching on the caller.
    if (isMapPrimaryLayout) {
      recomputeDeckWindow(candidateRef);
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
    // badge, the shop name itself, and (list-primary/mobile only, see
    // below) the walking-time estimate as a trailing chip, all on one
    // line -- not just the badge with genre trailing it. Genre moves to
    // its own plain-text line (no chip) directly above the description,
    // and walking time moves out of the facts grid entirely, leaving the
    // facts grid exactly the four/three items the design's own 2-column
    // grid shows.
    //
    // Human real-device report, deck round (2026-08-29): at the deck's
    // fixed 16.25rem card width, cramming badge+name+chip onto one row
    // left the shop name -- "この画面で一番大事な情報" per the human's own
    // chat decision -- as little as ~75-79% of its needed width even for
    // the synthetic population's own longest name, and far worse for real
    // names ("ドラゴンレッドリバー DRAGON RED RIVER" etc). Human decision
    // (2026-08-29 chat, choosing among three costed options) moved the
    // walking-time chip out of the id row and onto the genre line,
    // *in the deck only* -- list-primary/mobile keeps the chip in the id
    // row exactly as before (unchanged pixel-for-pixel). isMapPrimaryLayout
    // is already read once per render before renderCard is ever called
    // (renderResult, above), so it is safe to branch on it here per card.
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
    if (!isMapPrimaryLayout) {
      idRowChildren.push(
        el("span", { "class": "candidate-card-id-row-spacer", "aria-hidden": "true" }, []),
        walkChip
      );
    }
    var idRow = el("div", { "class": "candidate-card-id-row" }, idRowChildren);
    card.appendChild(idRow);

    var genreText = el(
      "p",
      { "data-testid": "candidate-card-genre", "data-field-label": "ジャンル", "data-value-state": "provided", "class": "candidate-genre-text" },
      [candidate.genre]
    );
    if (isMapPrimaryLayout) {
      // Deck-only: genre and the walking-time chip share one row so the id
      // row above can give the shop name essentially the whole card width
      // (home.html's own .candidate-deck-viewport [data-testid="candidate-
      // card-name"] flex-grow rule) instead of splitting it with the chip.
      card.appendChild(el("div", { "class": "candidate-genre-row" }, [genreText, walkChip]));
    } else {
      card.appendChild(genreText);
    }

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

  // Human real-device report, second round (2026-08-25; still the reason
  // this fix is needed after task 2 made the closed map genuinely visible
  // again): the closed map was still answering real taps meant for
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
  // nothing in-flow to size the wrapper by). Fixed at the time by making the
  // map element's own box constant at all times (always position:fixed,
  // always full-viewport width/height) so it never depended on the
  // wrapper's own sizing. Task 2 (2026-08-26) reintroduces a box-model
  // change (position:absolute 88px band while closed <-> position:fixed
  // full-viewport while open -- see [data-testid="candidate-map"]'s CSS in
  // home.html) but keeps this fix's actual lesson: .candidate-map-wrapper
  // itself now carries an explicit, non-auto height (5.5rem) that does not
  // depend on the map or any other child, open or closed, so nothing can
  // collapse it the way the original flex-sized wrapper did. Because the
  // box genuinely resizes between the two states again, a later resize is
  // not guaranteed to be the *only* thing that changes its geometry --
  // refreshMapViewAndRings is therefore still called directly here rather
  // than relying solely on the ResizeObserver (which still exists, still
  // fires for this same change too, and still matters for genuine later
  // resizes: window resize, mobile-toolbar dvh changes, orientation
  // change).
  function refreshMapViewAndRings() {
    if (!leafletMap) {
      return;
    }
    leafletMap.invalidateSize();
    if (mapSheetOpen && selectedCandidateRef && latLngByRef[selectedCandidateRef]) {
      // animate: false -- layoutWalkingRadiusRings (called synchronously
      // below) derives each ring label's position from this view's pixel
      // geometry via containerPointToLatLng, then bakes that into a fixed
      // marker latLng. An animated setView only updates that pixel geometry
      // to its final state once the animation's zoomend/moveend fires,
      // after this call already returned -- so an animated call here baked
      // a label position from a mid-animation, not the final, view, which
      // could later re-project somewhere far off (confirmed empirically:
      // one label rendered above the visible viewport entirely). Snapping
      // immediately keeps the label geometry and the final rendered view in
      // agreement.
      leafletMap.setView(latLngByRef[selectedCandidateRef], Math.max(leafletMap.getZoom(), 16), {
        animate: false,
      });
    } else if (currentMapLatLngs.length > 0) {
      // mapSheetOpen is false in every real call to this branch (the sibling
      // branch above already claims every case where the sheet is open and
      // a candidate is selected, which is always true once any candidate
      // exists -- see selectedCandidateRef's own initialization). Reading
      // isCompactMapBand() here anyway, rather than hardcoding the closed-
      // band padding, keeps this branch correct for the zero-candidate edge
      // case too, and for the invariant that follows from
      // MAP_BAND_FIT_PADDING_PX's own comment: whichever box is actually on
      // screen right now gets its own matching padding -- isCompactMapBand's
      // own comment covers why the full-viewport map-primary box also takes
      // the "open" padding by default, further biased toward the deck-clear
      // upper region via mapPrimaryFitPaddingOptions when isMapPrimaryLayout
      // holds (adr/0031 decision7).
      leafletMap.fitBounds(
        window.L.latLngBounds(currentMapLatLngs),
        isMapPrimaryLayout
          ? mapPrimaryFitPaddingOptions()
          : { padding: isCompactMapBand() ? MAP_BAND_FIT_PADDING_PX : MAP_OPEN_FIT_PADDING_PX }
      );
    }
    layoutWalkingRadiusRings(leafletMap, walkingRadiusRingOrigin);
  }

  // adr/0031 decisions 2-3 (deckNavigation, browserActions.pageDeckPrevious/
  // pageDeckNext): a fixed-size sliding window over the same ordered card
  // list the mobile list already renders (orderedCardElements) -- paging
  // never reorders, adds, or removes a data-candidate-ref
  // (deckNavigation.orderingInvariant), it only moves which already-ordered
  // cards sit inside the window (contract's own "windowing/paging"
  // language). Window size adapts to the deck viewport's own measured
  // width (recomputeDeckWindow), not a fixed card count, so it naturally
  // shows fewer cards on a narrower desktop window and more on a wider one
  // -- DECK_CARD_WIDTH_PX/DECK_CARD_GAP_PX above are the same fixed
  // per-card footprint the CSS itself uses.
  function deckTotal() {
    return orderedCardElements.length;
  }

  function deckMaxWindowStart(windowSize) {
    return Math.max(1, deckTotal() - windowSize + 1);
  }

  // contracts/candidate-search-browser-interface.yaml's deckNavigation.
  // position.presenceRule/valueShape and disabledState: 1-based
  // visibleStart/visibleEnd/total decimal-string attributes, and native
  // `disabled` on candidate-deck-previous/-next exactly at the start/end
  // boundary (mirrors filterPanel.matchCountObservation.zeroState's own
  // disabled-not-absent convention, reused by reference in the contract).
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
    if (deckPreviousEl) {
      deckPreviousEl.disabled = visibleStart <= 1;
    }
    if (deckNextEl) {
      deckNextEl.disabled = visibleEnd >= total;
    }
    if (cardsContainerEl) {
      var offsetPx = (deckWindowStart - 1) * (DECK_CARD_WIDTH_PX + DECK_CARD_GAP_PX);
      cardsContainerEl.style.transform = "translateX(" + String(-offsetPx) + "px)";
    }
    // deckViewportEl's own CSS (`flex: 1 1 auto`) lets it grow past
    // deckWindowSize cards' combined width whenever the deck bar has more
    // room than exactly deckWindowSize cards need (e.g. deckWindowSize=4
    // leaves slack once 4 cards only need 1064px of a 1200px-wide
    // viewport) -- real-device measurement found this let a 5th,
    // uncounted card visibly peek in through that slack despite
    // overflow: hidden, contradicting the "1–4 / 5" counter next to it
    // (activeContext.md). Capping the viewport's own max-width to exactly
    // deckWindowSize cards' width removes that slack, so overflow: hidden
    // clips flush at the boundary the counter itself reports; any leftover
    // deck-bar space instead stays empty next to candidate-deck-next
    // rather than partially revealing an uncounted card.
    if (deckViewportEl) {
      var deckWidthPx = total === 0 ? 0 : deckWindowSize * DECK_CARD_WIDTH_PX + (deckWindowSize - 1) * DECK_CARD_GAP_PX;
      deckViewportEl.style.maxWidth = deckWidthPx + "px";
    }
  }

  // Recomputes how many cards currently fit the deck viewport's own
  // measured width (called on initial render and on every later viewport
  // resize via the ResizeObserver renderDeck attaches -- adr/0032 decision3
  // only exempts *render-mode* switching, listPrimaryLayout<->
  // mapPrimaryLayout, from a live-resize requirement, not this in-mode
  // window-size recalculation), clamping the current window and, when
  // revealRef names a candidate currently outside it, moving the window to
  // include that candidate without changing card order (browserActions.
  // selectMarker's deckVisibility clause, adr/0031 decision3).
  function recomputeDeckWindow(revealRef) {
    if (!isMapPrimaryLayout || !deckViewportEl) {
      return;
    }
    var total = deckTotal();
    if (total === 0) {
      deckWindowSize = 1;
      deckWindowStart = 1;
      updateDeckPositionDisplay();
      return;
    }
    // updateDeckPositionDisplay (called at the end of this function, and by
    // every earlier call to it) caps deckViewportEl's own max-width to
    // exactly deckWindowSize cards' width (see that function's own
    // comment). Measuring clientWidth against that constrained box on a
    // later call -- e.g. a real window resize firing the ResizeObserver
    // renderDeck attaches -- would read back a stale, self-imposed limit
    // instead of the deck bar's actual currently-available width, getting
    // permanently stuck at whatever window size the previous measurement
    // produced. Releasing the cap first restores the CSS `flex: 1 1 auto`
    // sizing this measurement needs.
    deckViewportEl.style.maxWidth = "none";
    var viewportWidth = deckViewportEl.clientWidth;
    var fit = Math.floor((viewportWidth + DECK_CARD_GAP_PX) / (DECK_CARD_WIDTH_PX + DECK_CARD_GAP_PX));
    deckWindowSize = Math.max(1, Math.min(fit, total));

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

  function pageDeckNext() {
    if (!isMapPrimaryLayout || !deckNextEl || deckNextEl.disabled) {
      return;
    }
    deckWindowStart = Math.min(deckMaxWindowStart(deckWindowSize), deckWindowStart + 1);
    updateDeckPositionDisplay();
  }

  function pageDeckPrevious() {
    if (!isMapPrimaryLayout || !deckPreviousEl || deckPreviousEl.disabled) {
      return;
    }
    deckWindowStart = Math.max(1, deckWindowStart - 1);
    updateDeckPositionDisplay();
  }

  // adr/0031 (Desktop.dc.html decision7=案A/decision8=案あ, human decision
  // 2026-08-28): builds the desktop map-primary deck -- previous/next
  // paging buttons (allowedPurposes candidate-deck-page-previous/-next,
  // adr/0031 decision1) and the position counter (candidate-deck-position,
  // decision2) -- around the same candidate-proposal-cards element
  // renderResult already built (never a second/cloned card set). Only
  // called while isMapPrimaryLayout is true (renderModes.mapPrimaryLayout,
  // adr/0031 decision4); mirrors mapOpenButton/mapSheetHeader's own
  // one-shot render-time gating in renderResult below. The position
  // counter is a plain, non-interactive <span> (not itself a control, so
  // it needs no allowedPurposes entry -- adr/0031's own text: "件数カウン
  // タ自体は操作ではないためこの規則には掛からない") and, deliberately, a
  // sibling of deckViewportEl rather than a child of it, so its own
  // negative top offset (home.html) is not clipped by the viewport's
  // overflow: hidden.
  function renderDeck(cardsContainer) {
    deckPreviousEl = el(
      "button",
      {
        type: "button",
        "class": "candidate-deck-nav candidate-deck-nav--previous",
        "data-testid": "candidate-deck-previous",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-deck-page-previous",
        "aria-label": "前の候補を表示",
      },
      ["‹"]
    );
    deckPreviousEl.addEventListener("click", function () {
      pageDeckPrevious();
    });
    deckNextEl = el(
      "button",
      {
        type: "button",
        "class": "candidate-deck-nav candidate-deck-nav--next",
        "data-testid": "candidate-deck-next",
        "data-candidate-control-category": "button",
        "data-candidate-control-purpose": "candidate-deck-page-next",
        "aria-label": "次の候補を表示",
      },
      ["›"]
    );
    deckNextEl.addEventListener("click", function () {
      pageDeckNext();
    });
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
    deckViewportEl = el("div", { "class": "candidate-deck-viewport" }, [cardsContainer]);
    var deck = el("div", { "class": "candidate-deck" }, [
      deckPreviousEl,
      deckViewportEl,
      deckNextEl,
      deckPositionEl,
    ]);
    if (window.ResizeObserver) {
      if (deckResizeObserver) {
        deckResizeObserver.disconnect();
      }
      deckResizeObserver = new window.ResizeObserver(function () {
        recomputeDeckWindow();
      });
      deckResizeObserver.observe(deckViewportEl);
    }
    return deck;
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
    // container is already connected to the live DOM by the time this runs
    // (root.appendChild(content) above, itself already attached, ran before
    // this function was called), so this initial fitBounds already measures
    // whichever real box the CSS gives the container right now: task 2's
    // closed-state 88px band by default at narrow widths (mainLayout's own
    // data-map-sheet-open starts "false" -- see the mainLayout comment
    // above), the full-viewport map-primary box at >=64rem (also
    // data-map-sheet-open="false" -- decision 6 leaves no control that could
    // ever flip it at this width), or the full-viewport open-state box on
    // the rare initial render where the mobile sheet is somehow already
    // open. Either way this fit targets the box Leaflet will actually paint
    // into, not a stale or assumed one -- see [data-testid="candidate-map"]'s
    // CSS in home.html for all three boxes. Padding matches whichever of
    // those boxes this fit is targeting -- see isCompactMapBand's own
    // comment for why the map-primary box also takes the open, full-viewport
    // mobile sheet's padding by default, further deck-biased via
    // mapPrimaryFitPaddingOptions when isMapPrimaryLayout holds (this
    // function's own caller, renderResult, always sets isMapPrimaryLayout
    // before calling initializeMap -- see that assignment below).
    if (latLngs.length > 0) {
      map.fitBounds(
        window.L.latLngBounds(latLngs),
        isMapPrimaryLayout
          ? mapPrimaryFitPaddingOptions()
          : { padding: isCompactMapBand() ? MAP_BAND_FIT_PADDING_PX : MAP_OPEN_FIT_PADDING_PX }
      );
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
    // map sheet (task 3, box model changed again by task 2's 2026-08-26
    // closed-state band -- see [data-testid="candidate-map"]'s CSS in
    // home.html) does genuinely resize this same container, so this
    // observer's own callback fires for that too; openMapSheet/
    // closeMapSheet also call refreshMapViewAndRings directly regardless,
    // rather than depending solely on the observer -- both call sites
    // agree on the same idempotent function, so the redundancy costs
    // nothing (see refreshMapViewAndRings's own comment for why an
    // animated setView here would be wrong either way).
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
    // adr/0031: reset every render, mirroring the resets above -- a fresh
    // proposal (search-again/apply-filters) always starts the deck's own
    // window back at its first card, not wherever a previous response's
    // paging happened to leave it.
    deckWindowStart = 1;
    deckWindowSize = 1;
    deckViewportEl = null;
    deckPreviousEl = null;
    deckNextEl = null;
    deckPositionEl = null;
    if (deckResizeObserver) {
      deckResizeObserver.disconnect();
      deckResizeObserver = null;
    }
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
    // throughout. While closed, task 2 (human decision 2026-08-26) shows
    // this same instance clipped to an 88px band rather than hiding it --
    // see [data-testid="candidate-map"]'s own CSS in home.html for how.
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
    // candidate-map-open (human decision 2026-08-25, redesigned
    // 2026-08-26 by task 2 to show the closed map itself as an 88px band
    // instead of hiding it entirely) is the sole visible entry point into
    // the map. It, and the sheet's close control, only ever change the
    // *visible map viewport* (compact band <-> full-screen sheet)
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
    // Real-device report (2026-08-26): this project's own designer/
    // wireframe conventions (.claude/agents/designer.md, meta/templates/
    // wireframe.md) forbid emoji as icon stand-ins -- this control's icon
    // used to be a literal map emoji. Replaced with the same inline-SVG
    // line icon designer's own canvas already uses for a map-expand
    // control (E:\AWS\dsg-out\Main.dc.html's 44px "expand to full screen"
    // corner-arrows glyph over its own map ribbon -- the same literal path
    // data, generalized from a fixed accent color to currentColor so it
    // follows this element's own text color instead of hardcoding one).
    // innerHTML is used only for this fixed, developer-authored SVG markup
    // (never user/candidate data), so it carries no injection risk despite
    // el() itself only supporting plain HTML elements (document.
    // createElement does not create SVG nodes).
    var mapOpenIcon = el(
      "span",
      { "class": "candidate-map-open-icon", "aria-hidden": "true" },
      []
    );
    mapOpenIcon.innerHTML =
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M9 4H4v5M15 20h5v-5M20 9V4h-5M4 15v5h5"></path></svg>';
    // Task 2 (human decision 2026-08-26, Main.dc.html lines 76-109): the
    // closed-state band shows a "N件の位置" pill (top-left) and this same
    // expand icon in its own 44x44 badge (top-right), not a centered
    // text+icon bar -- both are purely decorative (home.html gives them
    // pointer-events: none), since the *whole* band is candidate-map-open's
    // own hit area now, not just this smaller visual. The pill's count is
    // body.candidates.length -- the same population this map's markers are
    // drawn from (see the loop above), so it can never disagree with what
    // is actually pinned. No visible "地図で見る" text label survives this
    // redesign; aria-label below still carries the control's accessible
    // name for assistive technology.
    var mapOpenPill = el(
      "span",
      { "class": "candidate-map-open-pill", "aria-hidden": "true" },
      [String(body.candidates.length) + "件の位置"]
    );
    var mapOpenExpand = el(
      "span",
      { "class": "candidate-map-open-expand", "aria-hidden": "true" },
      [mapOpenIcon]
    );
    var mapOpenButton = el(
      "div",
      {
        "data-testid": "candidate-map-open",
        "class": "candidate-map-open",
        role: "button",
        tabindex: "0",
        "aria-label": "地図を表示する",
      },
      [mapOpenPill, mapOpenExpand]
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
    // adr/0031 (Desktop.dc.html decision7=案A/decision8=案あ, human decision
    // 2026-08-28, superseding decision6's 2026-08-26 "permanent side
    // column" reading this comment used to describe): at >=64rem the map
    // fills essentially the whole area below the header/filter bar
    // (renderModes.mapPrimaryLayout), with the card deck (renderDeck)
    // overlaid on the map's own bottom inset instead of living beside it as
    // a separate column -- so the mobile-only ribbon-open control,
    // full-screen-sheet header/back bar, and the sheet's own single-
    // candidate info panel (decision5: the map side carries pins/rings
    // only, never a duplicate detail panel -- full detail stays in the
    // deck's own cards) still do not belong in the DOM at all at this
    // width, not merely hidden by CSS -- there is nothing left for them to
    // open/close/summarize, unchanged from decision6's original reasoning.
    // isMapPrimaryLayout is read once per render (matching this file's
    // other one-shot, render-time-only viewport reads, e.g.
    // isCompactMapBand; adr/0032 decision3 explicitly does not require a
    // live-resize mode switch); it is not re-evaluated on a later
    // browser-window resize across the 64rem boundary without a fresh
    // proposal response (search-again/filter apply both call renderResult
    // again, which re-reads it) -- candidate.js has no other DOM-rebuilding
    // resize handling today (only the map's own ResizeObserver, which
    // resizes the existing map, and the deck's own ResizeObserver, which
    // only recomputes the deck's window size, neither of which rebuilds
    // the surrounding controls), and adding one only for this edge case
    // was judged not worth the risk of a new resize-driven re-render
    // regression against this same screen's already-elaborate open/close
    // history (see the mapSheetOpen/openMapSheet/closeMapSheet comments
    // above). mapOpenButton/mapSheetHeader/mapSheetPanelEl are still built
    // unconditionally above (openMapSheet/closeMapSheet/
    // syncMapSheetPanelToSelection keep referencing them by variable/class,
    // and they never run at this width regardless, since nothing can ever
    // set mapSheetOpen=true here) -- only whether they are appended into
    // the live DOM differs.
    isMapPrimaryLayout = window.matchMedia && window.matchMedia("(min-width: 64rem)").matches;

    var cardsContainer = el("div", { "data-testid": "candidate-proposal-cards" }, []);
    body.candidates.forEach(function (candidate, index) {
      var card = renderCard(candidate, index === 0, index);
      orderedCardElements.push(card);
      cardsContainer.appendChild(card);
    });
    cardsContainerEl = cardsContainer;
    selectedCandidateRef = body.candidates.length > 0 ? body.candidates[0].candidateRef : null;

    var mapWrapperChildren = [mapContainer];
    if (isMapPrimaryLayout) {
      // adr/0031 decision3: the deck is the sole place candidate detail
      // renders at this width (decision5) -- cardsContainer moves inside
      // the map wrapper's own deck overlay instead of being appended as
      // mainLayout's own second child (the listPrimaryLayout branch below).
      mapWrapperChildren.push(renderDeck(cardsContainer));
    } else {
      mapWrapperChildren.push(mapOpenButton, mapSheetHeader, mapSheetPanelEl);
    }
    mapWrapperChildren.push(mapAttributionLink);
    var mapWrapper = el("div", { "class": "candidate-map-wrapper" }, mapWrapperChildren);
    mapWrapperEl = mapWrapper;

    // DOM order is ribbon-then-list (the ribbon is the compact map preview
    // sitting above the list, task 3) at listPrimaryLayout widths -- CSS
    // lays this out as a simple vertical stack (home.html), so this DOM
    // order is what keyboard/reader users encounter there. At
    // mapPrimaryLayout widths cardsContainer is not a second mainLayout
    // child at all -- it already moved inside mapWrapper's own deck above.
    mainLayout.appendChild(mapWrapper);
    if (!isMapPrimaryLayout) {
      mainLayout.appendChild(cardsContainer);
    }
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
    if (isMapPrimaryLayout) {
      recomputeDeckWindow();
    }
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
