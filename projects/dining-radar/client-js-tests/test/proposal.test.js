import { afterEach, describe, expect, it, vi } from "vitest";
import { boot, candidate, cleanup, flush, jsonResponse, proposalBody } from "./harness.js";

afterEach(cleanup);

const lastBody = (fetchMock, n = 0) => JSON.parse(fetchMock.mock.calls[n][1].body);

describe("initial request", () => {
  it("does nothing when the app root is absent", async () => {
    const page = await boot({ html: '<div id="candidate-filter-bar"></div>' });
    expect(page.fetchMock).not.toHaveBeenCalled();
  });

  it("POSTs an empty body with CSRF token, JSON headers and same-origin credentials", async () => {
    const page = await boot();
    const [url, init] = page.fetchMock.mock.calls[0];
    expect(url).toBe("/candidate-proposals");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers).toEqual({ "Content-Type": "application/json", "X-CSRFToken": "tok-123" });
    expect(init.body).toBe("{}");
  });

  it("sends an empty CSRF token when the form field is missing", async () => {
    const html = '<div id="candidate-filter-bar"></div><div id="candidate-app"></div>';
    const page = await boot({ html });
    expect(page.fetchMock.mock.calls[0][1].headers["X-CSRFToken"]).toBe("");
  });

  it("carries gatheringId from the URL on the initial and later requests", async () => {
    const page = await boot({ url: "/?gatheringId=g-9" });
    expect(lastBody(page.fetchMock, 0)).toEqual({ gatheringId: "g-9" });
    page.byTestId("candidate-search-again").click();
    await flush();
    expect(lastBody(page.fetchMock, 2).gatheringId).toBe("g-9");
  });

  it("omits gatheringId when the query parameter is empty", async () => {
    const page = await boot({ url: "/?gatheringId=" });
    expect(lastBody(page.fetchMock, 0)).toEqual({});
  });

  it("fetches the in-progress count only after the proposal request settles", async () => {
    const page = await boot();
    const urls = page.fetchMock.mock.calls.map((c) => c[0]);
    expect(urls).toEqual(["/candidate-proposals", "/gatherings/in-progress-count"]);
    expect(page.fetchMock.mock.calls[1][1]).toEqual({ credentials: "same-origin" });
  });

  it("shows a non-additive provider-unavailable problem when the first fetch rejects", async () => {
    const page = await boot({
      fetch: (url) => (url === "/candidate-proposals" ? Promise.reject(new Error("net")) : jsonResponse(500, {})),
    });
    const problem = page.byTestId("candidate-proposal-problem");
    expect(problem.getAttribute("data-problem-code")).toBe("PROVIDER_UNAVAILABLE");
    expect(problem.getAttribute("role")).toBe("alert");
    expect(page.byTestId("candidate-proposal-problem-guidance").textContent).toBe(
      "Candidate proposals cannot be retrieved right now. Please try again later."
    );
    expect(page.fetchMock.mock.calls[1][0]).toBe("/gatherings/in-progress-count");
  });
});

describe("handleProposalResponse", () => {
  it("renders a non-200 first response as a replacing problem", async () => {
    const page = await boot({
      fetch: (url) =>
        url === "/candidate-proposals" ? jsonResponse(503, { code: "X1", message: "down" }) : jsonResponse(404, {}),
    });
    expect(page.root.children).toHaveLength(1);
    const problem = page.byTestId("candidate-proposal-problem");
    expect(problem.getAttribute("data-problem-code")).toBe("X1");
    expect(page.byTestId("candidate-proposal-problem-guidance").textContent).toBe("down");
    expect(page.byTestId("candidate-filter-open")).toBeNull();
  });

  it("retains the displayed proposal and replaces the prior problem on a later failure (TDR-CS-16)", async () => {
    let calls = 0;
    const page = await boot({
      fetch: (url) => {
        if (url !== "/candidate-proposals") return jsonResponse(404, {});
        calls += 1;
        return calls === 1 ? jsonResponse(200, proposalBody()) : jsonResponse(502, { code: `E${calls}`, message: `m${calls}` });
      },
    });
    page.byTestId("candidate-search-again").click();
    await flush();
    expect(page.allByTestId("candidate-card")).toHaveLength(2);
    expect(page.root.firstChild.getAttribute("data-testid")).toBe("candidate-proposal-problem");
    expect(page.root.firstChild.getAttribute("data-problem-code")).toBe("E2");
    page.byTestId("candidate-search-again").click();
    await flush();
    expect(page.allByTestId("candidate-proposal-problem")).toHaveLength(1);
    expect(page.byTestId("candidate-proposal-problem").getAttribute("data-problem-code")).toBe("E3");
    expect(page.allByTestId("candidate-card")).toHaveLength(2);
  });

  it("renders no-results guidance plus the revise-filters control, and opens the panel", async () => {
    const page = await boot({
      fetch: () => jsonResponse(200, proposalBody({ candidates: [] })),
    });
    const none = page.byTestId("candidate-no-results");
    expect(none.textContent).toContain("絞り込み条件に合うランチ候補が見つかりませんでした。絞り込み条件を変更してお試しください。");
    expect(page.byTestId("candidate-map")).toBeNull();
    const revise = page.byTestId("candidate-no-results-revise-filters");
    expect(revise.textContent).toBe("絞り込み条件を変更する");
    expect(revise.getAttribute("data-candidate-control-purpose")).toBe("candidate-no-results-open-filter");
    revise.click();
    expect(page.filterBar.getAttribute("data-filter-expanded")).toBe("true");
    expect(page.byTestId("candidate-filter-panel")).not.toBeNull();
    expect(document.activeElement).toBe(page.byTestId("candidate-filter-open"));
  });

  it("treats a missing candidates array like an empty one and tolerates missing lists", async () => {
    const page = await boot({
      fetch: () => jsonResponse(200, { providerCredit: { url: "u", text: "t" } }),
    });
    expect(page.byTestId("candidate-no-results")).not.toBeNull();
    expect(page.byTestId("candidate-filter-open")).not.toBeNull();
  });

  it("discloses the izakaya/bar fallback only when applied", async () => {
    const withFallback = await boot({
      fetch: () => jsonResponse(200, proposalBody({ izakayaBarFallbackApplied: true })),
    });
    expect(withFallback.byTestId("candidate-izakaya-bar-fallback-notice").textContent).toBe(
      "条件に合う候補がなかったため、居酒屋・バーなどランチ営業の実施を確認しづらい店舗も含めて表示しています。含まれた店舗が実際にランチ営業しているとは限らないため、営業時間は店舗ページでご確認ください。"
    );
    cleanup();
    const without = await boot();
    expect(without.byTestId("candidate-izakaya-bar-fallback-notice")).toBeNull();
  });

  it("renders the provider credit link", async () => {
    const page = await boot();
    const credit = page.byTestId("candidate-provider-credit");
    expect(credit.getAttribute("href")).toBe("https://credit.test/");
    expect(credit.getAttribute("target")).toBe("_blank");
    expect(credit.getAttribute("rel")).toBe("noopener noreferrer");
    expect(credit.textContent).toBe("Powered by X");
  });

  it("renders the map container and attribution", async () => {
    const page = await boot();
    const map = page.byTestId("candidate-map");
    expect(map.getAttribute("data-map-tile-provider")).toBe("openstreetmap-standard");
    const attribution = page.byTestId("candidate-map-attribution");
    expect(attribution.getAttribute("href")).toBe("https://www.openstreetmap.org/copyright");
    expect(attribution.getAttribute("target")).toBe("_blank");
    expect(attribution.getAttribute("rel")).toBe("noopener noreferrer");
    expect(attribution.textContent).toBe("© OpenStreetMap contributors");
    expect(page.q(".candidate-main-layout").getAttribute("data-map-sheet-open")).toBe("false");
  });
});

describe("render modes", () => {
  it("two-column layout puts the card list beside the map without a deck", async () => {
    const page = await boot({ twoColumn: true });
    expect(page.q(".candidate-list-column [data-testid=candidate-proposal-cards]")).not.toBeNull();
    expect(page.q(".candidate-deck")).toBeNull();
    const wrapper = page.q(".candidate-map-wrapper");
    expect(Array.from(wrapper.children).map((n) => n.getAttribute("data-testid"))).toEqual([
      "candidate-map",
      "candidate-map-attribution",
    ]);
    expect(page.q(".candidate-main-layout").children[0].className).toBe("candidate-list-column");
  });

  it("touch layout wraps the cards in a deck inside the map wrapper", async () => {
    const page = await boot({ twoColumn: false });
    expect(page.q(".candidate-list-column")).toBeNull();
    const wrapper = page.q(".candidate-map-wrapper");
    expect(Array.from(wrapper.children).map((n) => n.getAttribute("data-testid") || n.className)).toEqual([
      "candidate-map",
      "candidate-deck",
      "candidate-map-attribution",
    ]);
    expect(page.byTestId("candidate-deck-swipe-surface")).not.toBeNull();
  });

  it("falls back to the touch layout when matchMedia is unavailable", async () => {
    const page = await boot({ noMatchMedia: true });
    expect(page.q(".candidate-deck")).not.toBeNull();
  });
});

describe("shownCandidateMemory", () => {
  const KEY = "dining-radar:shown-provider-page-urls";

  it("stores each shown providerPageUrl with a timestamp after a success", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    await boot();
    const stored = JSON.parse(window.sessionStorage.getItem(KEY));
    expect(stored).toEqual([
      { url: "https://example.test/a", storedAt: Date.now() },
      { url: "https://example.test/b", storedAt: Date.now() },
    ]);
  });

  it("sends surviving urls as shownProviderPageUrls and prunes expired entries from storage", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    const now = Date.now();
    const HOUR = 60 * 60 * 1000;
    window.sessionStorage.setItem(
      KEY,
      JSON.stringify([
        { url: "fresh", storedAt: now - 19 * HOUR },
        { url: "edge", storedAt: now - 20 * HOUR },
        { url: "old", storedAt: now - 21 * HOUR },
        { url: 5, storedAt: now },
        { url: "nots", storedAt: "x" },
        null,
      ])
    );
    const page = await boot({
      fetch: () => jsonResponse(200, proposalBody({ candidates: [] })),
    });
    expect(lastBody(page.fetchMock, 0).shownProviderPageUrls).toEqual(["fresh"]);
    // The stored set itself was pruned by the request, then the response added nothing.
    expect(JSON.parse(window.sessionStorage.getItem(KEY)).map((e) => e.url)).toEqual(["fresh"]);
  });

  it("clears the memory first when shownPoolExhausted is true, deduplicating by url", async () => {
    window.sessionStorage.setItem(KEY, JSON.stringify([{ url: "https://example.test/old", storedAt: Date.now() }]));
    await boot({
      fetch: () =>
        jsonResponse(
          200,
          proposalBody({
            shownPoolExhausted: true,
            candidates: [candidate(), candidate({ candidateRef: "c9", providerPageUrl: "https://example.test/a" })],
          })
        ),
    });
    const stored = JSON.parse(window.sessionStorage.getItem(KEY));
    expect(stored.map((e) => e.url)).toEqual(["https://example.test/a"]);
  });

  it("keeps earlier memory when the pool is not exhausted", async () => {
    window.sessionStorage.setItem(KEY, JSON.stringify([{ url: "https://example.test/old", storedAt: Date.now() }]));
    await boot();
    const urls = JSON.parse(window.sessionStorage.getItem(KEY)).map((e) => e.url);
    expect(urls).toEqual(["https://example.test/old", "https://example.test/a", "https://example.test/b"]);
  });

  it("degrades to no memory for corrupt JSON, non-arrays and empty values", async () => {
    for (const raw of ["{not json", '{"a":1}', ""]) {
      window.sessionStorage.setItem(KEY, raw);
      const page = await boot({ fetch: () => jsonResponse(200, proposalBody({ candidates: [] })) });
      expect(lastBody(page.fetchMock, 0)).toEqual({});
      cleanup();
    }
  });

  it("never throws when sessionStorage is unavailable", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    const page = await boot();
    expect(lastBody(page.fetchMock, 0)).toEqual({});
    expect(page.allByTestId("candidate-card")).toHaveLength(2);
  });
});
