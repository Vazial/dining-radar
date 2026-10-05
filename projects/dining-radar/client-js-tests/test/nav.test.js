import { afterEach, describe, expect, it } from "vitest";
import { boot, cleanup, flush, jsonResponse, proposalBody } from "./harness.js";

afterEach(cleanup);

const attr = (page, id, name) => page.byTestId(id).getAttribute(name);

describe("initializePrimaryNav render-mode pruning", () => {
  it("keeps the desktop menu and removes the mobile bar in two-column mode", async () => {
    const page = await boot({ twoColumn: true });
    expect(page.q("[data-primary-nav-desktop]")).not.toBeNull();
    expect(page.q("[data-primary-nav-mobile]")).toBeNull();
  });

  it("keeps the mobile bar and removes the desktop menu in touch mode", async () => {
    const page = await boot({ twoColumn: false });
    expect(page.q("[data-primary-nav-desktop]")).toBeNull();
    expect(page.qa("[data-primary-nav-mobile]")).toHaveLength(2);
  });

  it("treats a missing desktop menu as already pruned", async () => {
    const page = await boot({ twoColumn: false, html: '<div id="candidate-filter-bar"></div><div id="candidate-app"></div>' });
    expect(page.byTestId("candidate-filter-open")).not.toBeNull();
  });

  it("falls back to touch pruning when matchMedia is missing", async () => {
    const page = await boot({ noMatchMedia: true });
    expect(page.q("[data-primary-nav-desktop]")).toBeNull();
  });
});

describe("syncPrimaryNavGatheringLinks", () => {
  it("marks search current and leaves the gathering href alone outside gathering mode", async () => {
    const page = await boot({ twoColumn: true });
    expect(attr(page, "candidate-primary-nav-menu-search", "data-primary-nav-current")).toBe("true");
    expect(attr(page, "candidate-primary-nav-menu-gathering", "data-primary-nav-current")).toBe("false");
    expect(attr(page, "candidate-primary-nav-menu-gathering", "href")).toBe("/gatherings/");
    expect(page.byTestId("candidate-primary-nav-menu-gathering").hasAttribute("data-active-gathering-id")).toBe(false);
  });

  it("points the gathering links at the gathering from the URL before any response", async () => {
    const page = await boot({ twoColumn: false, url: "/?gatheringId=a%20b", ready: false });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    // synchronous part of initializePrimaryNav has already synced the links
    expect(attr(page, "candidate-primary-nav-gathering", "href")).toBe("/gatherings/a%20b/");
    expect(attr(page, "candidate-primary-nav-gathering", "data-primary-nav-current")).toBe("true");
    expect(attr(page, "candidate-primary-nav-search", "data-primary-nav-current")).toBe("false");
  });

  it("prefers the response's gatheringContext and records the active id on the menu entry", async () => {
    const page = await boot({
      twoColumn: true,
      url: "/?gatheringId=url-id",
      fetch: () =>
        jsonResponse(
          200,
          proposalBody({
            gatheringContext: {
              gatheringId: "ctx-id",
              confirmedCandidateDate: "2026-09-18T03:00:00Z",
              shortlistedShopCount: 1,
              maxShortlistedShops: 5,
            },
          })
        ),
    });
    expect(attr(page, "candidate-primary-nav-menu-gathering", "href")).toBe("/gatherings/ctx-id/");
    expect(attr(page, "candidate-primary-nav-menu-gathering", "data-active-gathering-id")).toBe("ctx-id");
    expect(attr(page, "candidate-primary-nav-menu-search", "data-primary-nav-current")).toBe("false");
  });
});

describe("in-progress badge", () => {
  const withCount = (count) => ({
    twoColumn: true,
    fetch: (url) => (url === "/candidate-proposals" ? jsonResponse(200, proposalBody()) : jsonResponse(200, { inProgressGatheringCount: count })),
  });

  it("shows the dot and count when gatherings are in progress", async () => {
    const page = await boot(withCount(3));
    const dot = page.byTestId("candidate-primary-nav-menu-dot");
    expect(dot.hidden).toBe(false);
    expect(dot.getAttribute("data-in-progress-gathering-count")).toBe("3");
  });

  it("hides the dot and drops the count attributes at zero", async () => {
    const page = await boot({
      ...withCount(0),
      html: undefined,
    });
    const dot = page.byTestId("candidate-primary-nav-menu-dot");
    expect(dot.hidden).toBe(true);
    expect(dot.hasAttribute("data-in-progress-gathering-count")).toBe(false);
  });

  it("sets and clears the mobile bar's count attribute", async () => {
    const shown = await boot({ ...withCount(2), twoColumn: false });
    expect(attr(shown, "candidate-primary-nav-gathering", "data-in-progress-gathering-count")).toBe("2");
    cleanup();
    const cleared = await boot({ ...withCount(0), twoColumn: false });
    expect(cleared.byTestId("candidate-primary-nav-gathering").hasAttribute("data-in-progress-gathering-count")).toBe(false);
  });

  it("removes a stale mobile count when it drops to zero", async () => {
    const html = `<a data-testid="candidate-primary-nav-gathering" data-in-progress-gathering-count="9"></a>
      <div id="candidate-filter-bar"></div><div id="candidate-app"></div>`;
    const page = await boot({ ...withCount(0), twoColumn: false, html });
    expect(page.byTestId("candidate-primary-nav-gathering").hasAttribute("data-in-progress-gathering-count")).toBe(false);
  });

  it("ignores a non-200 or failing count request", async () => {
    const non200 = await boot({
      twoColumn: true,
      fetch: (url) => (url === "/candidate-proposals" ? jsonResponse(200, proposalBody()) : jsonResponse(500, {})),
    });
    expect(non200.byTestId("candidate-primary-nav-menu-dot").hidden).toBe(true);
    cleanup();
    const failing = await boot({
      twoColumn: true,
      fetch: (url) => (url === "/candidate-proposals" ? jsonResponse(200, proposalBody()) : Promise.reject(new Error("net"))),
    });
    expect(failing.byTestId("candidate-primary-nav-menu-dot").hidden).toBe(true);
  });

  it("copes with a page that lacks the nav elements entirely", async () => {
    const html = '<div id="candidate-filter-bar"></div><div id="candidate-app"></div>';
    const page = await boot({ ...withCount(4), html });
    expect(page.byTestId("candidate-filter-open")).not.toBeNull();
  });
});

describe("account sheet and keyboard handling", () => {
  it("toggles the mobile account sheet and aria-expanded", async () => {
    const page = await boot({ twoColumn: false });
    const button = page.byTestId("candidate-primary-nav-account");
    const sheet = document.getElementById("primary-nav-account-sheet");
    button.click();
    expect(sheet.hasAttribute("hidden")).toBe(false);
    expect(button.getAttribute("aria-expanded")).toBe("true");
    button.click();
    expect(sheet.getAttribute("hidden")).toBe("");
    expect(button.getAttribute("aria-expanded")).toBe("false");
  });

  it("does not wire the sheet when either element is missing", async () => {
    const html = `<button data-testid="candidate-primary-nav-account" aria-expanded="false"></button>
      <div id="candidate-filter-bar"></div><div id="candidate-app"></div>`;
    const page = await boot({ twoColumn: false, html });
    page.byTestId("candidate-primary-nav-account").click();
    expect(attr(page, "candidate-primary-nav-account", "aria-expanded")).toBe("false");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  });

  it("swallows clicks on the already-current search destination only", async () => {
    const page = await boot({ twoColumn: true });
    const click = (el) => {
      const event = new MouseEvent("click", { bubbles: true, cancelable: true });
      el.dispatchEvent(event);
      return event;
    };
    expect(click(page.byTestId("candidate-primary-nav-menu-search")).defaultPrevented).toBe(true);
    expect(click(page.byTestId("candidate-primary-nav-menu-gathering")).defaultPrevented).toBe(false);
    page.byTestId("candidate-primary-nav-menu-search").setAttribute("data-primary-nav-current", "false");
    expect(click(page.byTestId("candidate-primary-nav-menu-search")).defaultPrevented).toBe(false);
    expect(click(document.body).defaultPrevented).toBe(false);
    // a click whose target has no closest() (the document itself)
    const docEvent = new MouseEvent("click", { bubbles: true, cancelable: true });
    document.dispatchEvent(docEvent);
    expect(docEvent.defaultPrevented).toBe(false);
  });

  it("matches the mobile search destination too", async () => {
    const page = await boot({ twoColumn: false });
    const event = new MouseEvent("click", { bubbles: true, cancelable: true });
    page.byTestId("candidate-primary-nav-search").dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it("Escape closes the open desktop menu and returns focus to its toggle", async () => {
    const page = await boot({ twoColumn: true });
    const menu = page.q(".primary-nav-menu");
    menu.setAttribute("open", "");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(menu.hasAttribute("open")).toBe(false);
    expect(document.activeElement).toBe(page.byTestId("candidate-primary-nav-menu-toggle"));
  });

  it("accepts the legacy Esc key value and ignores other keys", async () => {
    const page = await boot({ twoColumn: true });
    const menu = page.q(".primary-nav-menu");
    menu.setAttribute("open", "");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    expect(menu.hasAttribute("open")).toBe(true);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Esc" }));
    expect(menu.hasAttribute("open")).toBe(false);
  });

  it("closes an open menu even without a toggle element", async () => {
    const html = `<details class="primary-nav-menu" open></details>
      <div id="candidate-filter-bar"></div><div id="candidate-app"></div>`;
    const page = await boot({ twoColumn: true, html });
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(page.q(".primary-nav-menu").hasAttribute("open")).toBe(false);
  });

  it("Escape closes the account sheet and focuses its button", async () => {
    const page = await boot({ twoColumn: false });
    const button = page.byTestId("candidate-primary-nav-account");
    const sheet = document.getElementById("primary-nav-account-sheet");
    button.click();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(sheet.hasAttribute("hidden")).toBe(true);
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(button);
  });

  it("Escape with nothing open does nothing", async () => {
    const page = await boot({ twoColumn: false });
    const sheet = document.getElementById("primary-nav-account-sheet");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(sheet.hasAttribute("hidden")).toBe(true);
    expect(document.activeElement).not.toBe(page.byTestId("candidate-primary-nav-account"));
  });

  it("closes an open sheet even if the account button is gone", async () => {
    const html = `<div id="primary-nav-account-sheet"></div><div id="candidate-filter-bar"></div><div id="candidate-app"></div>`;
    await boot({ twoColumn: false, html });
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(document.getElementById("primary-nav-account-sheet").hasAttribute("hidden")).toBe(true);
  });
});

describe("page-load sequencing", () => {
  it("waits for DOMContentLoaded before doing anything", async () => {
    const page = await boot({ ready: false });
    expect(page.fetchMock).not.toHaveBeenCalled();
    document.dispatchEvent(new Event("DOMContentLoaded"));
    await flush();
    expect(page.fetchMock).toHaveBeenCalled();
  });
});
