import { afterEach, describe, expect, it, vi } from "vitest";
import { boot, candidate, cleanup, flush, jsonResponse, makeFakeL, proposalBody } from "./harness.js";

afterEach(cleanup);

const three = () => [
  candidate({ candidateRef: "c1", name: "A", location: { latitude: 35.68, longitude: 139.7 } }),
  candidate({ candidateRef: "c2", name: "B", location: { latitude: 35.69, longitude: 139.71 } }),
  candidate({ candidateRef: "c3", name: "C", location: { latitude: 35.7, longitude: 139.72 } }),
];

const withCards = (candidates, extra = {}) => ({
  fetch: () => jsonResponse(200, proposalBody({ candidates, ...extra })),
});

const candidateMarkers = (L) => L.log.markers.filter((m) => m.options.icon.className === "candidate-map-marker-icon");

describe("initializeMap without Leaflet", () => {
  it("renders cards without a map when window.L is absent", async () => {
    const page = await boot();
    expect(page.byTestId("candidate-map").getAttribute("data-map-fit-state")).toBeNull();
    expect(page.byTestId("candidate-map-marker")).toBeNull();
  });
});

describe("initializeMap", () => {
  it("creates one map with tiles, fits all candidates and sets the fit state", async () => {
    const L = makeFakeL();
    const page = await boot({ L, twoColumn: true });
    const map = L.log.maps[0];
    expect(map.container).toBe(page.byTestId("candidate-map"));
    expect(map.options).toEqual({ attributionControl: false });
    expect(L.log.tileUrl).toBe("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png");
    expect(L.log.tileOptions).toEqual({ maxZoom: 19 });
    expect(L.log.fits[0].bounds.latLngs).toEqual([
      [35.68, 139.7],
      [35.69, 139.71],
    ]);
    expect(page.byTestId("candidate-map").getAttribute("data-map-fit-state")).toBe("displayed-candidates");
  });

  it("uses the plain symmetric padding in two-column mode (no deck)", async () => {
    const L = makeFakeL();
    await boot({ L, twoColumn: true });
    const padding = L.log.fits[0].opts;
    expect([padding.paddingTopLeft.x, padding.paddingTopLeft.y]).toEqual([24, 24]);
    expect([padding.paddingBottomRight.x, padding.paddingBottomRight.y]).toEqual([24, 24]);
  });

  it("reserves the measured deck height in touch mode", async () => {
    const L = makeFakeL();
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function () {
      return { height: this.classList.contains("candidate-deck") ? 100 : 0 };
    });
    await boot({ L, twoColumn: false });
    const padding = L.log.fits[0].opts;
    expect([padding.paddingBottomRight.x, padding.paddingBottomRight.y]).toEqual([24, 164]);
    expect([padding.paddingTopLeft.x, padding.paddingTopLeft.y]).toEqual([24, 24]);
  });

  it("falls back to the plain bottom padding when the deck measures zero", async () => {
    const L = makeFakeL();
    await boot({ L, twoColumn: false });
    expect(L.log.fits[0].opts.paddingBottomRight.y).toBe(24);
  });

  it("builds marker elements with the contract attributes", async () => {
    const L = makeFakeL();
    await boot({ L, ...withCards(three()) });
    const markers = candidateMarkers(L);
    expect(markers).toHaveLength(3);
    expect(markers[0].options.keyboard).toBe(true);
    expect(markers[0].icon).toMatchObject({ className: "candidate-map-marker-icon", iconSize: [44, 44], iconAnchor: [22, 22] });
    markers.forEach((marker, index) => {
      const el = marker.getElement();
      expect(el.getAttribute("data-testid")).toBe("candidate-map-marker");
      expect(el.getAttribute("data-candidate-ref")).toBe(`c${index + 1}`);
      expect(el.getAttribute("data-selection-state")).toBe(index === 0 ? "selected" : "unselected");
      expect(el.getAttribute("role")).toBe("button");
      expect(el.getAttribute("tabindex")).toBe("0");
      expect(el.getAttribute("data-candidate-control-category")).toBe("button");
      expect(el.getAttribute("data-candidate-control-purpose")).toBe("candidate-map-marker-selection");
      expect(el.querySelector(".candidate-map-marker-visual").textContent).toBe(String(index + 1));
      expect(el.hasAttribute("data-gathering-shortlisted")).toBe(false);
    });
  });

  it("skips markers whose element Leaflet has not created yet", async () => {
    const L = makeFakeL({ withElements: false });
    const page = await boot({ L });
    expect(L.log.markers.length).toBeGreaterThan(0);
    expect(page.allByTestId("candidate-card")).toHaveLength(2);
    // still goes on to finish the map
    expect(page.byTestId("candidate-map").getAttribute("data-map-fit-state")).toBe("displayed-candidates");
  });

  it("selects the card and marker when a marker is clicked or activated by key", async () => {
    const L = makeFakeL();
    const page = await boot({ L, ...withCards(three()) });
    const markers = candidateMarkers(L).map((m) => m.getElement());
    markers[2].click();
    const cardsNow = page.allByTestId("candidate-card");
    expect(cardsNow.map((c) => c.getAttribute("data-selection-state"))).toEqual(["unselected", "unselected", "selected"]);
    expect(markers.map((m) => m.getAttribute("data-selection-state"))).toEqual(["unselected", "unselected", "selected"]);
    expect(cardsNow[2].scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "nearest", inline: "center" });
    const key = (el, k) => {
      const event = new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true });
      el.dispatchEvent(event);
      return event;
    };
    expect(key(markers[0], "x").defaultPrevented).toBe(false);
    expect(markers[0].getAttribute("data-selection-state")).toBe("unselected");
    expect(key(markers[0], "Enter").defaultPrevented).toBe(true);
    expect(markers[0].getAttribute("data-selection-state")).toBe("selected");
    expect(key(markers[1], " ").defaultPrevented).toBe(true);
    expect(markers[1].getAttribute("data-selection-state")).toBe("selected");
  });

  it("does not build a map for an empty result", async () => {
    const L = makeFakeL();
    await boot({ L, ...withCards([]) });
    expect(L.log.maps).toHaveLength(0);
  });

  it("draws a read-only origin marker with exact decimal strings", async () => {
    const L = makeFakeL();
    await boot({ L, ...withCards(three(), { searchOrigin: { latitude: 35.6812, longitude: 139.7671 } }) });
    const origin = L.log.markers.find((m) => m.options.icon.className === "candidate-origin-marker-icon");
    expect(origin.options).toMatchObject({ keyboard: true, alt: "検索基点" });
    expect(origin.icon).toMatchObject({ iconSize: [28, 28], iconAnchor: [14, 14] });
    expect(origin.latLng).toEqual([35.6812, 139.7671]);
    const el = origin.getElement();
    expect(el.getAttribute("data-testid")).toBe("candidate-origin-marker");
    expect(el.getAttribute("aria-label")).toBe("検索基点");
    expect(el.getAttribute("tabindex")).toBe("0");
    expect(el.getAttribute("data-origin-latitude")).toBe("35.6812");
    expect(el.getAttribute("data-origin-longitude")).toBe("139.7671");
  });

  it("omits the origin marker and rings when the response has no searchOrigin", async () => {
    const L = makeFakeL();
    await boot({ L, ...withCards(three(), { searchOrigin: null }) });
    expect(L.log.markers.some((m) => m.options.icon.className === "candidate-origin-marker-icon")).toBe(false);
    expect(L.log.circles).toHaveLength(0);
  });

  it("leaves the origin element untouched when Leaflet has not made it yet", async () => {
    const L = makeFakeL({ withElements: false });
    const page = await boot({ L });
    expect(page.byTestId("candidate-origin-marker")).toBeNull();
  });

  it("tears down the previous map and observer on re-render", async () => {
    const L = makeFakeL();
    const disconnect = vi.fn();
    const observe = vi.fn();
    const callbacks = [];
    class FakeResizeObserver {
      constructor(cb) {
        callbacks.push(cb);
      }
      observe(target) {
        observe(target);
      }
      disconnect() {
        disconnect();
      }
    }
    const page = await boot({ L, ResizeObserver: FakeResizeObserver });
    expect(observe).toHaveBeenCalledWith(page.byTestId("candidate-map"));
    expect(L.log.maps).toHaveLength(1);
    page.byTestId("candidate-search-again").click();
    await flush();
    expect(L.log.maps[0].removed).toBe(true);
    expect(L.log.maps).toHaveLength(2);
    expect(disconnect).toHaveBeenCalledTimes(1);
    expect(L.log.maps[1].removed).toBe(false);
  });

  it("re-fits and re-lays-out rings when the container is resized", async () => {
    const L = makeFakeL();
    const callbacks = [];
    class FakeResizeObserver {
      constructor(cb) {
        callbacks.push(cb);
      }
      observe() {}
      disconnect() {}
    }
    await boot({ L, ResizeObserver: FakeResizeObserver });
    const map = L.log.maps[0];
    const ringsBefore = L.log.circles.length;
    const fitsBefore = L.log.fits.length;
    callbacks[0]();
    expect(map.invalidated).toBe(1);
    expect(L.log.fits.length).toBe(fitsBefore + 1);
    expect(L.log.circles.length).toBeGreaterThan(ringsBefore);
    // previous ring layers were cleared
    expect(L.log.circles.slice(0, ringsBefore).every((c) => c.removed)).toBe(true);
  });

  it("works without ResizeObserver", async () => {
    const L = makeFakeL();
    const page = await boot({ L });
    expect(page.byTestId("candidate-map").getAttribute("data-map-fit-state")).toBe("displayed-candidates");
  });
});

describe("walking radius rings", () => {
  const ringPaths = (L) => L.log.circles.filter((c) => c.options.className.startsWith("candidate-walking-radius-ring-path"));

  it("draws casing, ring path and label per visible preset plus the inner tint", async () => {
    const L = makeFakeL({ scale: 20000 });
    await boot({ L });
    const classes = L.log.circles.map((c) => c.options.className);
    expect(classes[0]).toBe("candidate-walking-radius-ring-inner-tint");
    expect(L.log.circles[0].options).toMatchObject({ stroke: false, fill: true, fillOpacity: 0.05, interactive: false });
    expect(L.log.circles[0].options.radius).toBeCloseTo((5 * 80) / 1.3, 6);
    const paths = ringPaths(L);
    expect(paths).toHaveLength(5);
    expect(paths.map((p) => p.options.radius)).toEqual([5, 10, 15, 20, 30].map((m) => (m * 80) / 1.3));
    expect(L.log.circles.filter((c) => c.options.className === "candidate-walking-radius-ring-casing")).toHaveLength(5);
    expect(paths[0].options).toMatchObject({ weight: 1.8, fill: false, interactive: false });
    const casing = L.log.circles.find((c) => c.options.className === "candidate-walking-radius-ring-casing");
    expect(casing.options.weight).toBeCloseTo(1.8 + 3, 6);
    const el = paths[1].getElement();
    expect(el.getAttribute("data-testid")).toBe("candidate-walking-radius-ring");
    expect(el.getAttribute("data-walking-radius-minutes")).toBe("10");
    expect(el.getAttribute("aria-label")).toBe("10分");
    const labels = L.log.markers.filter((m) => m.icon.className.startsWith("candidate-walking-radius-ring-label"));
    expect(labels.map((m) => m.getElement().querySelector(".candidate-walking-radius-ring-label-visual").textContent)).toEqual(["5分", "10分", "15分", "20分", "30分"]);
    expect(labels[0].icon).toMatchObject({ iconSize: [1, 1], iconAnchor: [0, 0], html: '<span class="candidate-walking-radius-ring-label-visual"></span>' });
    expect(labels[0].options).toMatchObject({ interactive: false, keyboard: false });
  });

  it("omits rings that do not cross the visible container and the tint when the innermost is hidden", async () => {
    const L = makeFakeL({ scale: 200000 }); // 5min ring ~ 2760px: farther than every corner
    await boot({ L });
    expect(L.log.circles).toHaveLength(0);
    cleanup();
    const small = makeFakeL({ scale: 2000 }); // all rings smaller than the nearest point (inside the box)
    await boot({ L: small });
    // origin at (200,300) inside the box: nearest=0 <= radius always; radius <= farthest -> all visible
    expect(small.log.circles.filter((c) => c.options.className.startsWith("candidate-walking-radius-ring-path"))).toHaveLength(5);
  });

  it("accents the ring matching the applied walking-time filter", async () => {
    const L = makeFakeL();
    const page = await boot({
      L,
      fetch: () => jsonResponse(200, proposalBody({ populationAttributes: [{ genre: "和食", walkingTimeBand: 10 }] })),
    });
    page.byTestId("candidate-filter-open").click();
    page.allByTestId("candidate-filter-walking-time-max-option")[1].click();
    page.byTestId("candidate-filter-apply").click();
    await flush();
    const latestMapCircles = L.log.circles.filter((c) => !c.removed);
    const accentPath = latestMapCircles.filter((c) => c.options.className === "candidate-walking-radius-ring-path candidate-walking-radius-ring-path--accent");
    expect(accentPath).toHaveLength(1);
    expect(accentPath[0].options.radius).toBeCloseTo((10 * 80) / 1.3, 6);
    expect(accentPath[0].options.weight).toBe(2.4);
    const accentCasing = latestMapCircles.filter((c) => c.options.className === "candidate-walking-radius-ring-casing candidate-walking-radius-ring-casing--accent");
    expect(accentCasing).toHaveLength(1);
    expect(accentCasing[0].options.weight).toBeCloseTo(2.4 + 3, 6);
    const accentLabels = L.log.markers.filter((m) => !m.removed && m.icon.className === "candidate-walking-radius-ring-label candidate-walking-radius-ring-label--accent");
    expect(accentLabels).toHaveLength(1);
    expect(accentLabels[0].getElement().textContent).toBe("10分");
  });

  it("tolerates rings and labels without elements", async () => {
    const L = makeFakeL({ withElements: false });
    await boot({ L });
    expect(ringPaths(L)).toHaveLength(5);
  });

  it("keeps labels inside the container margin and away from markers and other labels", async () => {
    const L = makeFakeL({ scale: 20000 });
    await boot({ L });
    const labels = L.log.markers.filter((m) => m.icon.className.startsWith("candidate-walking-radius-ring-label"));
    const toPx = (latLng) => ({ x: 200 + (latLng[1] - 139.705) * 20000, y: 300 + (35.685 - latLng[0]) * 20000 });
    const pts = labels.map((l) => toPx(l.latLng));
    pts.forEach((p) => {
      expect(p.x).toBeGreaterThanOrEqual(20 - 1e-6);
      expect(p.x).toBeLessThanOrEqual(380 + 1e-6);
      expect(p.y).toBeGreaterThanOrEqual(20 - 1e-6);
      expect(p.y).toBeLessThanOrEqual(580 + 1e-6);
    });
    // the first label starts due north of the origin (angle 0) on the ring's circumference
    const radiusPx = ((5 * 80) / 1.3 / 111320) * 20000;
    expect(pts[0].x).toBeCloseTo(200, 3);
    expect(pts[0].y).toBeCloseTo(300 - radiusPx, 3);
    // no two labels overlap by the collision box
    for (let i = 0; i < pts.length; i += 1) {
      for (let j = i + 1; j < pts.length; j += 1) {
        const overlap = Math.abs(pts[i].x - pts[j].x) < 60 && Math.abs(pts[i].y - pts[j].y) < 28;
        expect(overlap).toBe(false);
      }
    }
  });

  it("moves a label to another angle when the due-north spot is taken by a marker", async () => {
    const L = makeFakeL({ scale: 20000 });
    const radiusDeg = (5 * 80) / 1.3 / 111320;
    const blocker = candidate({ candidateRef: "c1", location: { latitude: 35.685 + radiusDeg, longitude: 139.705 } });
    await boot({ L, fetch: () => jsonResponse(200, proposalBody({ candidates: [blocker] })) });
    const first = L.log.markers.filter((m) => m.icon.className.startsWith("candidate-walking-radius-ring-label"))[0];
    const px = { x: 200 + (first.latLng[1] - 139.705) * 20000, y: 300 + (35.685 - first.latLng[0]) * 20000 };
    // 0 and 45 degrees both still overlap the marker's keep-out box; 90 degrees (due east) is clear
    const radiusPx = radiusDeg * 20000;
    expect(px.x).toBeCloseTo(200 + radiusPx, 3);
    expect(px.y).toBeCloseTo(300, 3);
  });

  it("falls back to the clamped north position when every angle collides", async () => {
    const L = makeFakeL({ scale: 20000, size: { x: 40, y: 40 } });
    await boot({ L, fetch: () => jsonResponse(200, proposalBody()) });
    const labels = L.log.markers.filter((m) => m.icon.className.startsWith("candidate-walking-radius-ring-label"));
    // a 40x40 container with a 20px margin leaves a single legal point: every label
    // collides with the previous ones, so each falls back to the clamped north position
    const px = labels.map((l) => ({ x: 200 + (l.latLng[1] - 139.705) * 20000, y: 300 + (35.685 - l.latLng[0]) * 20000 }));
    expect(labels.length).toBeGreaterThan(0);
    px.forEach((p) => {
      expect(p.x).toBeCloseTo(20, 3);
      expect(p.y).toBeCloseTo(20, 3);
    });
  });
});
