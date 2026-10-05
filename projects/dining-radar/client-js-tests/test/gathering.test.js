import { afterEach, describe, expect, it, vi } from "vitest";
import { boot, candidate, cleanup, flush, jsonResponse, proposalBody } from "./harness.js";

afterEach(cleanup);

const context = (overrides = {}) => ({
  gatheringId: "g/1",
  title: "ランチ会",
  confirmedCandidateDate: "2026-09-18T03:00:00Z",
  shortlistedShopCount: 2,
  maxShortlistedShops: 5,
  ...overrides,
});

const cards = (flags) =>
  flags.map((isShortlisted, i) =>
    candidate({
      candidateRef: `c${i + 1}`,
      shopId: `s${i + 1}`,
      name: `店${i + 1}`,
      isShortlisted,
      providerPageUrl: `https://example.test/${i + 1}`,
      location: { latitude: 35.68 + i * 0.001, longitude: 139.7 },
    })
  );

async function bootGathering({ ctx = context(), flags = [true, false, true], put, extra = {}, url = "/?gatheringId=g%2F1", L, twoColumn } = {}) {
  const puts = [];
  const page = await boot({
    url,
    L,
    twoColumn,
    fetch: (u, init) => {
      if (u === "/candidate-proposals") {
        return jsonResponse(200, proposalBody({ candidates: cards(flags), gatheringContext: ctx, ...extra }));
      }
      if (init && init.method === "PUT") {
        puts.push({ url: u, init });
        return put ? put(puts.length) : jsonResponse(200, { shortlistedShops: [{ shopId: "s1" }, { shopId: "s2" }, { shopId: "s3" }] });
      }
      return jsonResponse(200, { inProgressGatheringCount: 0 });
    },
  });
  page.puts = puts;
  page.toggle = (n) => page.allByTestId("candidate-card-gathering-toggle")[n];
  return page;
}

describe("gathering band", () => {
  it("renders the status band with counts and the UTC-formatted date", async () => {
    const page = await bootGathering();
    const band = page.byTestId("candidate-gathering-mode-band");
    expect(band.tagName).toBe("DIV");
    expect(band.getAttribute("data-gathering-shortlisted-count")).toBe("2");
    expect(band.getAttribute("data-gathering-max-shortlisted")).toBe("5");
    expect(band.getAttribute("data-shortlist-limit-reached")).toBe("false");
    expect(band.className).toBe("candidate-gathering-mode-band");
    expect(band.querySelector(".candidate-gathering-mode-band-condition").textContent).toBe("9/18 (金)に開いている店");
    expect(band.querySelector(".candidate-gathering-mode-band-count").textContent).toBe("入れた店 2 / 5");
    expect(page.byTestId("candidate-proposal-content").firstChild).toBe(band);
  });

  it("marks the band full at the cap", async () => {
    const page = await bootGathering({ ctx: context({ shortlistedShopCount: 5 }), flags: [true, true, true] });
    const band = page.byTestId("candidate-gathering-mode-band");
    expect(band.getAttribute("data-shortlist-limit-reached")).toBe("true");
    expect(band.className).toBe("candidate-gathering-mode-band candidate-gathering-mode-band--full");
  });

  it("is absent outside gathering mode", async () => {
    const page = await boot();
    expect(page.byTestId("candidate-gathering-mode-band")).toBeNull();
  });

  it("is present even for an empty result", async () => {
    const page = await boot({
      fetch: () => jsonResponse(200, proposalBody({ candidates: [], gatheringContext: context() })),
    });
    expect(page.byTestId("candidate-gathering-mode-band")).not.toBeNull();
  });

  it("formats dates by UTC components and passes unparsable values through", async () => {
    const early = await bootGathering({ ctx: context({ confirmedCandidateDate: "2026-01-05T23:30:00Z" }) });
    expect(early.q(".candidate-gathering-mode-band-condition").textContent).toBe("1/5 (月)に開いている店");
    cleanup();
    const bad = await bootGathering({ ctx: context({ confirmedCandidateDate: "soon" }) });
    expect(bad.q(".candidate-gathering-mode-band-condition").textContent).toBe("soonに開いている店");
    cleanup();
    const sunday = await bootGathering({ ctx: context({ confirmedCandidateDate: "2026-02-01T00:00:00Z" }) });
    expect(sunday.q(".candidate-gathering-mode-band-condition").textContent).toBe("2/1 (日)に開いている店");
    cleanup();
    const saturday = await bootGathering({ ctx: context({ confirmedCandidateDate: "2026-03-07T12:00:00Z" }) });
    expect(saturday.q(".candidate-gathering-mode-band-condition").textContent).toBe("3/7 (土)に開いている店");
  });
});

describe("card toggle rendering", () => {
  it("renders state, labels and no disabled reason in the open case", async () => {
    const page = await bootGathering();
    const on = page.toggle(0);
    const off = page.toggle(1);
    expect(on.tagName).toBe("BUTTON");
    expect(on.getAttribute("type")).toBe("button");
    expect(on.getAttribute("data-gathering-shortlisted")).toBe("true");
    expect(on.textContent).toBe("この会に入れました");
    expect(on.className).toBe("candidate-gathering-toggle candidate-gathering-toggle--on");
    expect(on.getAttribute("data-candidate-control-category")).toBe("button");
    expect(on.getAttribute("data-candidate-control-purpose")).toBe("candidate-card-gathering-toggle");
    expect(on.disabled).toBe(false);
    expect(on.hasAttribute("data-gathering-toggle-disabled-reason")).toBe(false);
    expect(off.getAttribute("data-gathering-shortlisted")).toBe("false");
    expect(off.textContent).toBe("この会に入れる");
    expect(off.className).toBe("candidate-gathering-toggle");
    expect(page.byTestId("candidate-card-gathering-last-shop-notice")).toBeNull();
  });

  it("disables non-shortlisted toggles at the cap with limit-reached", async () => {
    const page = await bootGathering({ ctx: context({ shortlistedShopCount: 5 }), flags: [true, false, true] });
    expect(page.toggle(1).disabled).toBe(true);
    expect(page.toggle(1).getAttribute("data-gathering-toggle-disabled-reason")).toBe("limit-reached");
    expect(page.toggle(0).disabled).toBe(false);
    expect(page.byTestId("candidate-card-gathering-last-shop-notice")).toBeNull();
  });

  it("disables the last shortlisted shop with last-shop and shows the notice right after it", async () => {
    const page = await bootGathering({ ctx: context({ shortlistedShopCount: 1 }), flags: [true, false] });
    const toggle = page.toggle(0);
    expect(toggle.disabled).toBe(true);
    expect(toggle.getAttribute("data-gathering-toggle-disabled-reason")).toBe("last-shop");
    const notice = page.byTestId("candidate-card-gathering-last-shop-notice");
    expect(notice.textContent).toBe("最低1件は残します");
    expect(notice.tagName).toBe("P");
    expect(notice.className).toBe("candidate-gathering-toggle-last-shop-notice");
    expect(toggle.nextElementSibling).toBe(notice);
    expect(page.toggle(1).disabled).toBe(false);
  });

  it("treats a missing isShortlisted as not shortlisted", async () => {
    const page = await bootGathering({ flags: [undefined, "yes"] });
    expect(page.toggle(0).getAttribute("data-gathering-shortlisted")).toBe("false");
    expect(page.toggle(1).getAttribute("data-gathering-shortlisted")).toBe("false");
  });

  it("clicking the toggle does not select the card", async () => {
    const page = await bootGathering({ put: () => jsonResponse(500, {}) });
    page.toggle(1).click();
    expect(page.allByTestId("candidate-card")[1].getAttribute("data-selection-state")).toBe("unselected");
  });
});

describe("toggleCardGatheringShortlist", () => {
  it("PUTs the complete replacement list when adding and updates band, cards and nav", async () => {
    const page = await bootGathering({
      put: () => jsonResponse(200, { shortlistedShops: [{ shopId: "s1" }, { shopId: "s2" }, { shopId: "s3" }] }),
    });
    page.toggle(1).click();
    await flush();
    const { url, init } = page.puts[0];
    expect(url).toBe("/gatherings/g%2F1/shortlisted-shops");
    expect(init.method).toBe("PUT");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers).toEqual({ "Content-Type": "application/json", "X-CSRFToken": "tok-123" });
    expect(JSON.parse(init.body)).toEqual({ shopIds: ["s1", "s2", "s3"] });

    const band = page.byTestId("candidate-gathering-mode-band");
    expect(band.getAttribute("data-gathering-shortlisted-count")).toBe("3");
    expect(band.getAttribute("data-gathering-max-shortlisted")).toBe("5");
    expect(band.getAttribute("data-shortlist-limit-reached")).toBe("false");
    expect(band.classList.contains("candidate-gathering-mode-band--full")).toBe(false);
    expect(band.querySelector(".candidate-gathering-mode-band-count").textContent).toBe("入れた店 3 / 5");
    expect(page.toggle(1).getAttribute("data-gathering-shortlisted")).toBe("true");
    expect(page.toggle(1).textContent).toBe("この会に入れました");
    expect(page.toggle(1).classList.contains("candidate-gathering-toggle--on")).toBe(true);
    expect(page.toggle(1).disabled).toBe(false);
    // add shows the toast
    const toast = page.byTestId("candidate-gathering-shortlist-toast");
    expect(toast.querySelector("span").textContent).toBe("店2 を入れました・3 / 5");
    expect(toast.getAttribute("data-gathering-shortlisted-count")).toBe("3");
    expect(toast.getAttribute("data-gathering-max-shortlisted")).toBe("5");
    const back = page.byTestId("candidate-gathering-shortlist-toast-return");
    expect(back.getAttribute("href")).toBe("/gatherings/g%2F1/");
    expect(back.textContent).toBe("会にもどる");
  });

  it("removal sends the list without the shop, shows no toast and dismisses a lingering one", async () => {
    let n = 0;
    const page = await bootGathering({
      flags: [true, false, true],
      put: () => {
        n += 1;
        return n === 1
          ? jsonResponse(200, { shortlistedShops: [{ shopId: "s1" }, { shopId: "s2" }, { shopId: "s3" }] })
          : jsonResponse(200, { shortlistedShops: [{ shopId: "s2" }, { shopId: "s3" }] });
      },
    });
    page.toggle(1).click();
    await flush();
    expect(page.byTestId("candidate-gathering-shortlist-toast")).not.toBeNull();
    page.toggle(0).click();
    await flush();
    expect(JSON.parse(page.puts[1].init.body)).toEqual({ shopIds: ["s2", "s3"] });
    expect(page.byTestId("candidate-gathering-shortlist-toast")).toBeNull();
    expect(page.toggle(0).getAttribute("data-gathering-shortlisted")).toBe("false");
    expect(page.toggle(0).textContent).toBe("この会に入れる");
    expect(page.toggle(0).classList.contains("candidate-gathering-toggle--on")).toBe(false);
  });

  it("falls back to a generic shop label in the toast when the name is empty", async () => {
    const blank = await boot({
      url: "/?gatheringId=g1",
      fetch: (u, init) =>
        u === "/candidate-proposals"
          ? jsonResponse(200, proposalBody({ candidates: [{ ...cards([true, false])[1], name: "" }, cards([true, false])[0]], gatheringContext: context({ gatheringId: "g1" }) }))
          : init && init.method === "PUT"
            ? jsonResponse(200, { shortlistedShops: [{ shopId: "s1" }, { shopId: "s2" }] })
            : jsonResponse(200, { inProgressGatheringCount: 0 }),
    });
    blank.allByTestId("candidate-card-gathering-toggle")[0].click();
    await flush();
    expect(blank.byTestId("candidate-gathering-shortlist-toast").querySelector("span").textContent).toBe("店 を入れました・2 / 5");
  });

  it("recomputes every card's disabled state and notice after the count changes", async () => {
    const page = await bootGathering({
      ctx: context({ shortlistedShopCount: 4 }),
      flags: [true, true, true, true, false, false],
      put: () =>
        jsonResponse(200, {
          shortlistedShops: [{ shopId: "s1" }, { shopId: "s2" }, { shopId: "s3" }, { shopId: "s4" }, { shopId: "s5" }],
        }),
    });
    expect(page.toggle(4).disabled).toBe(false);
    page.toggle(4).click();
    await flush();
    const band = page.byTestId("candidate-gathering-mode-band");
    expect(band.getAttribute("data-shortlist-limit-reached")).toBe("true");
    expect(band.classList.contains("candidate-gathering-mode-band--full")).toBe(true);
    expect(page.toggle(5).disabled).toBe(true);
    expect(page.toggle(5).getAttribute("data-gathering-toggle-disabled-reason")).toBe("limit-reached");
    expect(page.toggle(4).disabled).toBe(false);
    expect(page.toggle(4).hasAttribute("data-gathering-toggle-disabled-reason")).toBe(false);
    // at the cap the toast stays (its auto-dismiss timer is never started)
    expect(page.byTestId("candidate-gathering-shortlist-toast")).not.toBeNull();
  });

  it("adds and removes the last-shop notice as the count crosses 1", async () => {
    let n = 0;
    const page = await bootGathering({
      ctx: context({ shortlistedShopCount: 2 }),
      flags: [true, true],
      put: () => {
        n += 1;
        return n === 1
          ? jsonResponse(200, { shortlistedShops: [{ shopId: "s2" }] })
          : jsonResponse(200, { shortlistedShops: [{ shopId: "s1" }, { shopId: "s2" }] });
      },
    });
    page.toggle(0).click();
    await flush();
    expect(page.allByTestId("candidate-card-gathering-last-shop-notice")).toHaveLength(1);
    expect(page.toggle(1).disabled).toBe(true);
    expect(page.toggle(1).getAttribute("data-gathering-toggle-disabled-reason")).toBe("last-shop");
    expect(page.toggle(1).nextElementSibling.getAttribute("data-testid")).toBe("candidate-card-gathering-last-shop-notice");
    // a re-sync while the notice already exists must not duplicate it
    page.toggle(0).click();
    await flush();
    expect(page.allByTestId("candidate-card-gathering-last-shop-notice")).toHaveLength(0);
    expect(page.toggle(1).disabled).toBe(false);
  });

  it("keeps an existing notice (no duplicate) when the card is still the last shop", async () => {
    const page = await bootGathering({
      ctx: context({ shortlistedShopCount: 1 }),
      flags: [true, false],
      put: () => jsonResponse(200, { shortlistedShops: [{ shopId: "s1" }] }),
    });
    expect(page.allByTestId("candidate-card-gathering-last-shop-notice")).toHaveLength(1);
    page.toggle(1).click();
    await flush();
    expect(page.allByTestId("candidate-card-gathering-last-shop-notice")).toHaveLength(1);
  });

  it("keeps markers in lockstep with their cards", async () => {
    const { makeFakeL } = await import("./harness.js");
    const L = makeFakeL();
    const page = await bootGathering({ L, flags: [true, false, true] });
    const markerFlags = () => L.log.markers.filter((m) => m.options.icon.className === "candidate-map-marker-icon").map((m) => m.getElement().getAttribute("data-gathering-shortlisted"));
    expect(markerFlags()).toEqual(["true", "false", "true"]);
    page.toggle(1).click();
    await flush();
    expect(markerFlags()).toEqual(["true", "true", "true"]);
  });

  it("ignores a non-200 response and a failed request without touching the DOM", async () => {
    const page = await bootGathering({ put: () => jsonResponse(409, {}) });
    page.toggle(1).click();
    await flush();
    expect(page.toggle(1).getAttribute("data-gathering-shortlisted")).toBe("false");
    expect(page.byTestId("candidate-gathering-shortlist-toast")).toBeNull();
    cleanup();
    const rejected = await bootGathering({ put: () => Promise.reject(new Error("net")) });
    rejected.toggle(1).click();
    await flush();
    expect(rejected.toggle(1).getAttribute("data-gathering-shortlisted")).toBe("false");
  });

  it("tolerates a gathering response without shortlistedShops", async () => {
    const page = await bootGathering({ put: () => jsonResponse(200, {}) });
    page.toggle(1).click();
    await flush();
    const band = page.byTestId("candidate-gathering-mode-band");
    expect(band.getAttribute("data-gathering-shortlisted-count")).toBe("0");
    expect(page.toggle(0).getAttribute("data-gathering-shortlisted")).toBe("false");
  });

  it("still updates the cards when the band or its count element is missing", async () => {
    const page = await bootGathering();
    page.byTestId("candidate-gathering-mode-band").querySelector(".candidate-gathering-mode-band-count").remove();
    page.toggle(1).click();
    await flush();
    expect(page.byTestId("candidate-gathering-mode-band").getAttribute("data-gathering-shortlisted-count")).toBe("3");
    page.byTestId("candidate-gathering-mode-band").remove();
    page.toggle(1).click();
    await flush();
    expect(page.toggle(1).getAttribute("data-gathering-shortlisted")).toBe("true");
  });

  it("does nothing outside gathering mode or for a vanished card", async () => {
    const page = await bootGathering();
    // a card element whose candidate ref is unknown is skipped in the shop id list
    page.allByTestId("candidate-card")[2].setAttribute("data-candidate-ref", "ghost");
    page.toggle(1).click();
    await flush();
    expect(JSON.parse(page.puts[0].init.body).shopIds).toEqual(["s1", "s2"]);
  });
});

describe("shortlist toast timing", () => {
  it("auto-dismisses after 4 seconds below the cap and replaces a previous toast", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const page = await bootGathering();
    page.toggle(1).click();
    await vi.advanceTimersByTimeAsync(0);
    await flush();
    expect(page.allByTestId("candidate-gathering-shortlist-toast")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(3999);
    expect(page.allByTestId("candidate-gathering-shortlist-toast")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(page.allByTestId("candidate-gathering-shortlist-toast")).toHaveLength(0);
  });

  it("a second addition replaces the toast and restarts the timer", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    let n = 0;
    const page = await bootGathering({
      flags: [true, false, false],
      put: () => {
        n += 1;
        return jsonResponse(200, {
          shortlistedShops: n === 1 ? [{ shopId: "s1" }, { shopId: "s2" }] : [{ shopId: "s1" }, { shopId: "s2" }, { shopId: "s3" }],
        });
      },
    });
    page.toggle(1).click();
    await vi.advanceTimersByTimeAsync(0);
    await flush();
    await vi.advanceTimersByTimeAsync(3000);
    page.toggle(2).click();
    await vi.advanceTimersByTimeAsync(0);
    await flush();
    expect(page.allByTestId("candidate-gathering-shortlist-toast")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(3000);
    expect(page.allByTestId("candidate-gathering-shortlist-toast")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(page.allByTestId("candidate-gathering-shortlist-toast")).toHaveLength(0);
  });
});
