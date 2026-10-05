// Shared test harness: loads the shipped candidate.js, unmodified, into the
// jsdom global (ADR-0014). The file is an IIFE with module-private state, so
// every boot() resets the module registry and re-imports it for a fresh state.
import { vi } from "vitest";

const PAGE_HTML = `
<nav data-primary-nav-desktop>
  <details class="primary-nav-menu">
    <summary data-testid="candidate-primary-nav-menu-toggle">menu</summary>
    <a data-testid="candidate-primary-nav-menu-search" href="/">search</a>
    <a data-testid="candidate-primary-nav-menu-gathering" href="/gatherings/">gatherings</a>
    <span data-testid="candidate-primary-nav-menu-dot" hidden></span>
  </details>
</nav>
<nav data-primary-nav-mobile>
  <a data-testid="candidate-primary-nav-search" href="/">search</a>
  <a data-testid="candidate-primary-nav-gathering" href="/gatherings/">gatherings</a>
  <button data-testid="candidate-primary-nav-account" aria-expanded="false">account</button>
</nav>
<div data-primary-nav-mobile id="primary-nav-account-sheet" hidden>sheet</div>
<form><input type="hidden" name="csrfmiddlewaretoken" value="tok-123"></form>
<div id="candidate-filter-bar"></div>
<div id="candidate-app"></div>
`;

// Every listener candidate.js puts on `document` outlives the module that
// registered it, so record and remove them between boots.
const documentListeners = [];
const realAddEventListener = document.addEventListener.bind(document);
document.addEventListener = (type, listener, options) => {
  documentListeners.push([type, listener, options]);
  return realAddEventListener(type, listener, options);
};

export function cleanup() {
  documentListeners.splice(0).forEach(([type, listener, options]) => {
    document.removeEventListener(type, listener, options);
  });
  document.body.innerHTML = "";
  window.sessionStorage.clear();
  delete window.L;
  delete window.ResizeObserver;
  delete window.matchMedia;
  vi.useRealTimers();
  vi.restoreAllMocks();
}

export function jsonResponse(status, body) {
  return { status, json: () => Promise.resolve(body) };
}

export async function flush() {
  for (let i = 0; i < 12; i += 1) {
    await Promise.resolve();
  }
}

export function setViewport({ twoColumn }) {
  window.matchMedia = (query) => ({ matches: twoColumn, media: query });
}

/**
 * Boots candidate.js. `fetch` is a function (url, init) => response | Promise.
 * Returns helpers; the module's own DOMContentLoaded handler is fired unless
 * `ready: false`.
 */
export async function boot({
  html = PAGE_HTML,
  url = "/",
  twoColumn = false,
  noMatchMedia = false,
  L,
  ResizeObserver,
  fetch = () => jsonResponse(200, proposalBody()),
  ready = true,
} = {}) {
  vi.resetModules();
  document.body.innerHTML = html;
  window.history.replaceState({}, "", url);
  if (noMatchMedia) {
    delete window.matchMedia;
  } else {
    setViewport({ twoColumn });
  }
  if (L) {
    window.L = L;
  }
  if (ResizeObserver) {
    window.ResizeObserver = ResizeObserver;
  }
  const fetchMock = vi.fn((requestUrl, init) => Promise.resolve(fetch(requestUrl, init)));
  globalThis.fetch = fetchMock;
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  // "candidate-under-test" is a vite alias (see vitest.config.js) for the shipped file.
  await import("candidate-under-test");
  if (ready) {
    document.dispatchEvent(new Event("DOMContentLoaded"));
    await flush();
  }
  return {
    fetchMock,
    root: document.getElementById("candidate-app"),
    filterBar: document.getElementById("candidate-filter-bar"),
    q: (selector) => document.querySelector(selector),
    qa: (selector) => Array.from(document.querySelectorAll(selector)),
    byTestId: (id) => document.querySelector(`[data-testid="${id}"]`),
    allByTestId: (id) => Array.from(document.querySelectorAll(`[data-testid="${id}"]`)),
  };
}

export function candidate(overrides = {}) {
  return {
    candidateRef: "c1",
    shopId: "s1",
    name: "店A",
    genre: "和食",
    description: "説明A",
    walkingTimeMinutes: 7,
    totalSeats: 30,
    capacityTier: "MEDIUM",
    nonSmokingStatus: "FULL",
    dinnerBudgetTier: "MID",
    regularHoliday: "日曜",
    cardPaymentAvailable: true,
    providerPageUrl: "https://example.test/a",
    location: { latitude: 35.68, longitude: 139.7 },
    ...overrides,
  };
}

export function proposalBody(overrides = {}) {
  return {
    candidates: [
      candidate(),
      candidate({
        candidateRef: "c2",
        shopId: "s2",
        name: "店B",
        genre: "洋食",
        providerPageUrl: "https://example.test/b",
        location: { latitude: 35.69, longitude: 139.71 },
      }),
    ],
    providerCredit: { url: "https://credit.test/", text: "Powered by X" },
    searchOrigin: { latitude: 35.685, longitude: 139.705 },
    availableGenres: ["和食", "洋食", "中華"],
    populationAttributes: [],
    ...overrides,
  };
}

/**
 * A recording stand-in for Leaflet. It models only what candidate.js calls:
 * a linear projection (so ring geometry is deterministic) and elements that
 * Marker#getElement / Path#getElement would return once a real view exists.
 */
export function makeFakeL({ scale = 20000, withElements = true, size = { x: 400, y: 600 } } = {}) {
  const log = { circles: [], markers: [], maps: [], fits: [], views: [], tiles: 0 };
  const point = (x, y) => ({
    x,
    y,
    distanceTo: (other) => Math.hypot(x - other.x, y - other.y),
  });
  const project = (ll) => point(200 + (ll[1] - 139.705) * scale, 300 + (35.685 - ll[0]) * scale);
  const makeLayer = (kind, record) => {
    let element = null;
    const layer = {
      ...record,
      added: false,
      removed: false,
      addTo(map) {
        layer.added = true;
        layer.map = map;
        if (withElements) {
          element = document.createElement("div");
          element.innerHTML = record.icon ? record.icon.html : "";
          if (kind === "marker" && record.icon) {
            element.className = record.icon.className;
          }
        }
        return layer;
      },
      getElement: () => element,
      remove() {
        layer.removed = true;
      },
    };
    return layer;
  };
  const L = {
    log,
    point,
    latLng: (lat, lng) => [lat, lng],
    latLngBounds: (latLngs) => ({ latLngs }),
    divIcon: (options) => options,
    map: (container, options) => {
      const map = {
        container,
        options,
        removed: false,
        invalidated: 0,
        fitBounds: (bounds, opts) => {
          log.fits.push({ bounds, opts });
        },
        setView: (center, zoom) => {
          log.views.push({ center, zoom });
        },
        getSize: () => ({ ...size }),
        latLngToContainerPoint: project,
        containerPointToLatLng: (p) => [35.685 - (p.y - 300) / scale, 139.705 + (p.x - 200) / scale],
        invalidateSize: () => {
          map.invalidated += 1;
        },
        remove: () => {
          map.removed = true;
        },
      };
      log.maps.push(map);
      return map;
    },
    tileLayer: (templateUrl, options) => {
      log.tiles += 1;
      log.tileUrl = templateUrl;
      log.tileOptions = options;
      return { addTo: () => {} };
    },
    marker: (latLng, options) => {
      const layer = makeLayer("marker", { latLng, options, icon: options.icon });
      log.markers.push(layer);
      return layer;
    },
    circle: (latLng, options) => {
      const layer = makeLayer("circle", { latLng, options });
      log.circles.push(layer);
      return layer;
    },
  };
  return L;
}
