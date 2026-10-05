import { afterEach, describe, expect, it } from "vitest";
import { boot, cleanup, flush, jsonResponse, proposalBody } from "./harness.js";

afterEach(cleanup);

const row = (overrides = {}) => ({
  genre: "和食",
  nonSmokingStatus: "FULL",
  cardPaymentAvailable: true,
  dinnerBudgetTier: "MID",
  walkingTimeBand: 10,
  defaultExcluded: false,
  ...overrides,
});

const POPULATION = [
  row(),
  row({ genre: "和食", nonSmokingStatus: "NONE" }),
  row({ genre: "洋食", cardPaymentAvailable: false, dinnerBudgetTier: "HIGH", walkingTimeBand: 20 }),
  row({ genre: "洋食", dinnerBudgetTier: null, walkingTimeBand: null }),
  row({ genre: "居酒屋", defaultExcluded: true, dinnerBudgetTier: undefined }),
];

async function bootPanel(body = {}, options = {}) {
  const calls = [];
  const page = await boot({
    ...options,
    fetch: (url, init) => {
      if (url !== "/candidate-proposals") return jsonResponse(404, {});
      calls.push(JSON.parse(init.body));
      const status = calls.length > 1 && options.failLater ? 500 : 200;
      return status === 200
        ? jsonResponse(200, proposalBody({ populationAttributes: POPULATION, availableGenres: ["和食", "洋食", "居酒屋"], ...body }))
        : jsonResponse(500, { code: "F", message: "later failure" });
    },
  });
  page.calls = calls;
  page.openPanel = () => {
    page.byTestId("candidate-filter-open").click();
  };
  page.chip = (id, value) =>
    page.allByTestId(id).find((el) => value === undefined || el.textContent === value);
  return page;
}

describe("filter summary and panel", () => {
  it("starts collapsed with the default summary", async () => {
    const page = await bootPanel();
    expect(page.filterBar.getAttribute("data-filter-expanded")).toBe("false");
    expect(page.filterBar.getAttribute("data-filter-dirty")).toBe("false");
    const open = page.byTestId("candidate-filter-open");
    expect(open.getAttribute("aria-expanded")).toBe("false");
    expect(open.querySelector(".candidate-filter-summary-text").textContent).toBe("居酒屋・バーを除く");
    expect(open.querySelector(".candidate-filter-summary-label").textContent).toBe("条件");
    expect(open.querySelector(".candidate-filter-caret").textContent).toBe("⌄");
    expect(open.querySelector(".candidate-filter-summary-icon").textContent).toBe("☷");
    expect(page.byTestId("candidate-filter-panel")).toBeNull();
    expect(page.byTestId("candidate-filter-pending-note")).toBeNull();
    const again = page.byTestId("candidate-search-again");
    expect(again.disabled).toBe(false);
    expect(again.querySelector(".candidate-search-again-icon").textContent).toBe("↻");
    expect(again.querySelector(".candidate-search-again-label").textContent).toBe("別の候補を出す");
    expect(again.querySelector(".visually-hidden").textContent).toBe("別の候補を出す");
  });

  it("toggles the panel from the summary button", async () => {
    const page = await bootPanel();
    page.openPanel();
    expect(page.filterBar.getAttribute("data-filter-expanded")).toBe("true");
    expect(page.byTestId("candidate-filter-open").getAttribute("aria-expanded")).toBe("true");
    expect(page.byTestId("candidate-filter-open").querySelector(".candidate-filter-caret").textContent).toBe("⌃");
    expect(page.byTestId("candidate-filter-panel")).not.toBeNull();
    expect(page.byTestId("candidate-budget-tier-note").textContent).toBe(
      "ディナー予算をもとにした目安です。ランチ価格を示すものではありません。"
    );
    expect(page.qa(".candidate-filter-row-label").map((n) => n.textContent)).toEqual(["ジャンル", "こだわり", "夜予算", "徒歩の上限"]);
    page.openPanel();
    expect(page.byTestId("candidate-filter-panel")).toBeNull();
  });

  it("renders the preset, budget and preference chips with their attributes", async () => {
    const page = await bootPanel();
    page.openPanel();
    const walking = page.allByTestId("candidate-filter-walking-time-max-option");
    expect(walking.map((n) => n.textContent)).toEqual(["5分以内", "10分以内", "15分以内", "20分以内", "30分以内"]);
    expect(walking.map((n) => n.getAttribute("data-walking-time-max-value"))).toEqual(["5", "10", "15", "20", "30"]);
    const tiers = page.allByTestId("candidate-filter-budget-tier-option");
    expect(tiers.map((n) => n.textContent)).toEqual(["低", "中", "高"]);
    expect(tiers.map((n) => n.getAttribute("data-budget-tier-value"))).toEqual(["LOW", "MID", "HIGH"]);
    const nonSmoking = page.byTestId("candidate-filter-non-smoking-only");
    expect(nonSmoking.textContent).toBe("禁煙席あり");
    expect(nonSmoking.getAttribute("data-candidate-control-purpose")).toBe("candidate-filter-non-smoking-toggle");
    expect(nonSmoking.getAttribute("data-candidate-control-category")).toBe("button");
    expect(nonSmoking.getAttribute("aria-pressed")).toBe("false");
    expect(nonSmoking.getAttribute("data-pressed")).toBe("false");
    expect(nonSmoking.className).toBe("candidate-chip");
    expect(nonSmoking.getAttribute("type")).toBe("button");
    const card = page.byTestId("candidate-filter-card-payment-only");
    expect(card.textContent).toBe("カード利用不可を除く");
    expect(card.getAttribute("data-candidate-control-purpose")).toBe("candidate-filter-card-payment-toggle");
    const izakaya = page.byTestId("candidate-filter-include-izakaya-bar");
    expect(izakaya.textContent).toBe("居酒屋等も含む");
    expect(izakaya.getAttribute("data-candidate-control-purpose")).toBe("candidate-filter-izakaya-bar-toggle");
    expect(izakaya.hasAttribute("data-genre-value")).toBe(false);
  });
});

describe("genre presentation", () => {
  it("orders by count desc, then name length, then ja collation, scoped to non-excluded rows", async () => {
    const population = [
      row({ genre: "bb" }),
      row({ genre: "a" }),
      row({ genre: "a" }),
      row({ genre: "ccc" }),
      row({ genre: "dd" }),
      row({ genre: "hidden", defaultExcluded: true }),
    ];
    const page = await bootPanel({ populationAttributes: population, availableGenres: ["ccc", "dd", "bb", "a", "hidden", "none"] });
    page.openPanel();
    const labels = page.allByTestId("candidate-filter-genre-option").map((n) => n.textContent);
    // a(2) first; bb(1)/dd(1) tie -> same length -> collation; ccc(1) longer; hidden/none have 0
    expect(labels).toEqual(["a", "bb", "dd", "ccc"]);
    expect(page.byTestId("candidate-filter-genre-overflow").textContent).toBe("ほか 2件…");
  });

  it("counts excluded rows when the applied filters include izakaya/bar", async () => {
    const page = await bootPanel({
      populationAttributes: [row({ genre: "x", defaultExcluded: true }), row({ genre: "y" })],
      availableGenres: ["x", "y"],
    });
    // apply includeIzakayaBar so the response's scope covers excluded rows
    page.openPanel();
    page.byTestId("candidate-filter-include-izakaya-bar").click();
    page.byTestId("candidate-filter-apply").click();
    await flush();
    page.openPanel();
    expect(page.allByTestId("candidate-filter-genre-option").map((n) => n.getAttribute("data-genre-value"))).toEqual(["x", "y"]);
  });

  it("expands and collapses the hidden genres and keeps the toggle first", async () => {
    const genres = ["g1", "g2", "g3", "g4", "g5", "g6"];
    const page = await bootPanel({
      populationAttributes: genres.map((genre) => row({ genre })),
      availableGenres: genres,
    });
    page.openPanel();
    expect(page.allByTestId("candidate-filter-genre-option")).toHaveLength(4);
    const group = page.q(".candidate-genre-group");
    expect(group.firstChild.getAttribute("data-testid")).toBe("candidate-filter-genre-overflow");
    expect(group.firstChild.getAttribute("data-candidate-control-purpose")).toBe("candidate-filter-genre-overflow-toggle");
    expect(group.lastChild.className).toBe("candidate-filter-row-chips candidate-genre-scrollable");
    expect(group.lastChild.firstChild.getAttribute("data-testid")).toBe("candidate-filter-include-izakaya-bar");
    page.byTestId("candidate-filter-genre-overflow").click();
    expect(page.allByTestId("candidate-filter-genre-option")).toHaveLength(6);
    expect(page.byTestId("candidate-filter-genre-overflow").textContent).toBe("閉じる");
    page.byTestId("candidate-filter-genre-overflow").click();
    expect(page.allByTestId("candidate-filter-genre-option")).toHaveLength(4);
  });

  it("omits the overflow toggle when every genre fits", async () => {
    const page = await bootPanel();
    page.openPanel();
    expect(page.byTestId("candidate-filter-genre-overflow")).toBeNull();
    expect(page.q(".candidate-genre-group").children).toHaveLength(1);
  });

  it("shows no genre chips when the response lists none", async () => {
    const page = await boot({
      fetch: () => jsonResponse(200, { candidates: [], providerCredit: { url: "u", text: "t" } }),
    });
    page.byTestId("candidate-filter-open").click();
    expect(page.allByTestId("candidate-filter-genre-option")).toHaveLength(0);
  });
});

describe("pending edits", () => {
  it("a genre chip marks the bar dirty, shows the pending note, revert and apply", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.chip("candidate-filter-genre-option", "和食").click();
    expect(page.filterBar.getAttribute("data-filter-dirty")).toBe("true");
    const pressed = page.chip("candidate-filter-genre-option", "和食");
    expect(pressed.getAttribute("aria-pressed")).toBe("true");
    expect(pressed.getAttribute("data-pressed")).toBe("true");
    expect(page.byTestId("candidate-filter-pending-note").textContent).toBe("変更中（まだ検索しません）");
    expect(page.byTestId("candidate-search-again").disabled).toBe(true);
    const actions = page.q(".candidate-filter-actions");
    expect(Array.from(actions.children).map((n) => n.getAttribute("data-testid"))).toEqual([
      "candidate-filter-revert",
      "candidate-filter-apply",
    ]);
    expect(page.byTestId("candidate-filter-revert").textContent).toBe("変更を戻す");
    expect(page.byTestId("candidate-filter-revert").getAttribute("data-candidate-control-purpose")).toBe("candidate-filter-revert");
    // the summary still shows the *applied* filters
    expect(page.q(".candidate-filter-summary-text").textContent).toBe("居酒屋・バーを除く");
    // toggling again removes the genre
    page.chip("candidate-filter-genre-option", "和食").click();
    expect(page.filterBar.getAttribute("data-filter-dirty")).toBe("false");
    expect(page.q(".candidate-filter-actions")).toBeNull();
    expect(page.byTestId("candidate-filter-apply")).toBeNull();
  });

  it("budget, preference, izakaya and walking chips edit pending state", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.chip("candidate-filter-budget-tier-option", "高").click();
    page.chip("candidate-filter-budget-tier-option", "低").click();
    page.byTestId("candidate-filter-non-smoking-only").click();
    page.byTestId("candidate-filter-card-payment-only").click();
    page.byTestId("candidate-filter-include-izakaya-bar").click();
    page.chip("candidate-filter-walking-time-max-option", "10分以内").click();
    expect(page.byTestId("candidate-filter-non-smoking-only").getAttribute("aria-pressed")).toBe("true");
    expect(page.byTestId("candidate-filter-card-payment-only").getAttribute("aria-pressed")).toBe("true");
    expect(page.byTestId("candidate-filter-include-izakaya-bar").getAttribute("aria-pressed")).toBe("true");
    expect(page.chip("candidate-filter-walking-time-max-option", "10分以内").getAttribute("aria-pressed")).toBe("true");
    expect(page.chip("candidate-filter-walking-time-max-option", "15分以内").getAttribute("aria-pressed")).toBe("false");
    // selecting another preset replaces; selecting the pressed one clears
    page.chip("candidate-filter-walking-time-max-option", "15分以内").click();
    expect(page.chip("candidate-filter-walking-time-max-option", "10分以内").getAttribute("aria-pressed")).toBe("false");
    page.chip("candidate-filter-walking-time-max-option", "15分以内").click();
    expect(page.chip("candidate-filter-walking-time-max-option", "15分以内").getAttribute("aria-pressed")).toBe("false");
    page.byTestId("candidate-filter-apply").click();
    return flush().then(() => {
      expect(page.calls[1].filters).toEqual({
        genres: [],
        includeIzakayaBar: true,
        nonSmokingOnly: true,
        cardPaymentOnly: true,
        budgetTiers: ["HIGH", "LOW"],
        walkingTimeMaxMinutes: null,
      });
    });
  });

  it("revert restores the applied filters", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.byTestId("candidate-filter-non-smoking-only").click();
    page.byTestId("candidate-filter-revert").click();
    expect(page.filterBar.getAttribute("data-filter-dirty")).toBe("false");
    expect(page.byTestId("candidate-filter-non-smoking-only").getAttribute("aria-pressed")).toBe("false");
  });

  it("is not dirty when the same genres are chosen in a different order", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.chip("candidate-filter-genre-option", "和食").click();
    page.chip("candidate-filter-genre-option", "洋食").click();
    page.byTestId("candidate-filter-apply").click();
    await flush();
    page.openPanel();
    page.chip("candidate-filter-genre-option", "和食").click();
    page.chip("candidate-filter-genre-option", "和食").click();
    // pending genres are [洋食, 和食] vs applied [和食, 洋食]: same set, so not dirty
    expect(page.filterBar.getAttribute("data-filter-dirty")).toBe("false");
  });

  it("detects a change in each individual filter field", async () => {
    const page = await bootPanel();
    page.openPanel();
    const dirty = () => page.filterBar.getAttribute("data-filter-dirty");
    const toggles = [
      () => page.byTestId("candidate-filter-include-izakaya-bar").click(),
      () => page.byTestId("candidate-filter-non-smoking-only").click(),
      () => page.byTestId("candidate-filter-card-payment-only").click(),
      () => page.chip("candidate-filter-walking-time-max-option", "5分以内").click(),
      () => page.chip("candidate-filter-budget-tier-option", "低").click(),
    ];
    for (const toggle of toggles) {
      toggle();
      expect(dirty()).toBe("true");
      toggle();
      expect(dirty()).toBe("false");
    }
  });
});

describe("match count and apply", () => {
  it("previews the count from the population and enables apply only when dirty with matches", async () => {
    const page = await bootPanel();
    page.openPanel();
    // the apply control only exists while the pending edit differs from the applied one
    expect(page.byTestId("candidate-filter-apply")).toBeNull();
    // default scope: excluded rows (居酒屋) are not counted -> 4 non-excluded rows
    page.byTestId("candidate-filter-card-payment-only").click();
    expect(page.byTestId("candidate-filter-apply").getAttribute("data-match-count")).toBe("3");
    page.byTestId("candidate-filter-card-payment-only").click();
    page.byTestId("candidate-filter-non-smoking-only").click();
    const apply = page.byTestId("candidate-filter-apply");
    expect(apply.getAttribute("data-match-count")).toBe("3");
    expect(apply.textContent).toBe("この条件で探す（対象3件）");
    expect(apply.disabled).toBe(false);
    expect(apply.getAttribute("data-candidate-control-purpose")).toBe("candidate-filter-apply");
  });

  it("applies each hard/soft filter exactly as the server predicate", async () => {
    const page = await bootPanel();
    page.openPanel();
    const count = () => page.byTestId("candidate-filter-apply").getAttribute("data-match-count");
    // genre filter
    page.chip("candidate-filter-genre-option", "洋食").click();
    expect(count()).toBe("2");
    // card payment: removes only exactly-false
    page.byTestId("candidate-filter-card-payment-only").click();
    expect(count()).toBe("1");
    page.byTestId("candidate-filter-card-payment-only").click();
    page.chip("candidate-filter-genre-option", "洋食").click();
    // budget: unknown tiers (null/undefined) are soft, others must match
    page.chip("candidate-filter-budget-tier-option", "高").click();
    expect(count()).toBe("2"); // HIGH洋食 + null-tier 洋食 (soft)
    page.chip("candidate-filter-budget-tier-option", "高").click();
    // walking time: hard filter, null band excluded
    page.chip("candidate-filter-walking-time-max-option", "10分以内").click();
    expect(count()).toBe("2"); // bands 10,10 ; band 20 and null excluded
    page.chip("candidate-filter-walking-time-max-option", "20分以内").click();
    expect(count()).toBe("3");
  });

  it("falls back to counting default-excluded rows when nothing else matches", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.chip("candidate-filter-genre-option", "居酒屋").click();
    // only the excluded 居酒屋 row matches -> fallback counts it
    expect(page.byTestId("candidate-filter-apply").getAttribute("data-match-count")).toBe("1");
    page.byTestId("candidate-filter-include-izakaya-bar").click();
    expect(page.byTestId("candidate-filter-apply").getAttribute("data-match-count")).toBe("1");
  });

  it("shows 該当なし and disables apply when nothing matches", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.chip("candidate-filter-walking-time-max-option", "5分以内").click();
    const apply = page.byTestId("candidate-filter-apply");
    expect(apply.getAttribute("data-match-count")).toBe("0");
    expect(apply.textContent).toBe("該当なし");
    expect(apply.disabled).toBe(true);
  });

  it("apply sends the pending filters, then commits them and closes the panel", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.chip("candidate-filter-genre-option", "和食").click();
    page.chip("candidate-filter-budget-tier-option", "中").click();
    page.chip("candidate-filter-walking-time-max-option", "15分以内").click();
    page.byTestId("candidate-filter-include-izakaya-bar").click();
    page.byTestId("candidate-filter-non-smoking-only").click();
    page.byTestId("candidate-filter-card-payment-only").click();
    page.byTestId("candidate-filter-apply").click();
    await flush();
    expect(page.calls[1].filters).toEqual({
      genres: ["和食"],
      includeIzakayaBar: true,
      nonSmokingOnly: true,
      cardPaymentOnly: true,
      budgetTiers: ["MID"],
      walkingTimeMaxMinutes: 15,
    });
    expect(page.filterBar.getAttribute("data-filter-expanded")).toBe("false");
    expect(page.filterBar.getAttribute("data-filter-dirty")).toBe("false");
    expect(page.q(".candidate-filter-summary-text").textContent).toBe(
      "和食・禁煙・カード利用不可を除く・ディナー予算 中・居酒屋等も含む・徒歩15分以内"
    );
  });

  it("a failed apply keeps the pending edits, the panel and the applied summary", async () => {
    const page = await bootPanel({}, { failLater: true });
    page.openPanel();
    page.byTestId("candidate-filter-non-smoking-only").click();
    page.byTestId("candidate-filter-apply").click();
    await flush();
    expect(page.filterBar.getAttribute("data-filter-expanded")).toBe("true");
    expect(page.q(".candidate-filter-summary-text").textContent).toBe("居酒屋・バーを除く");
    expect(page.byTestId("candidate-proposal-problem").getAttribute("data-problem-code")).toBe("F");
    expect(page.allByTestId("candidate-card")).toHaveLength(2);
    expect(page.byTestId("candidate-filter-non-smoking-only").getAttribute("aria-pressed")).toBe("true");
  });

  it("search again re-sends the applied filters", async () => {
    const page = await bootPanel();
    page.byTestId("candidate-search-again").click();
    await flush();
    expect(page.calls[1]).toEqual({ filters: expect.objectContaining({ genres: [], walkingTimeMaxMinutes: null }), shownProviderPageUrls: ["https://example.test/a", "https://example.test/b"] });
  });
});

describe("filter summary text", () => {
  it("lists the budget tiers in canonical order", async () => {
    const page = await bootPanel();
    page.openPanel();
    for (const label of ["高", "低"]) page.chip("candidate-filter-budget-tier-option", label).click();
    page.byTestId("candidate-filter-apply").click();
    await flush();
    expect(page.q(".candidate-filter-summary-text").textContent).toBe("ディナー予算 低・高");
  });

  it("joins several genres with ・", async () => {
    const page = await bootPanel();
    page.openPanel();
    page.chip("candidate-filter-genre-option", "和食").click();
    page.chip("candidate-filter-genre-option", "洋食").click();
    page.byTestId("candidate-filter-apply").click();
    await flush();
    expect(page.q(".candidate-filter-summary-text").textContent).toBe("和食・洋食");
  });
});

describe("focus restoration", () => {
  it("keeps focus on the same chip across re-renders", async () => {
    const page = await bootPanel();
    page.openPanel();
    const genre = page.chip("candidate-filter-genre-option", "和食");
    genre.focus();
    genre.click();
    expect(document.activeElement.getAttribute("data-genre-value")).toBe("和食");
    const tier = page.chip("candidate-filter-budget-tier-option", "中");
    tier.focus();
    tier.click();
    expect(document.activeElement.getAttribute("data-budget-tier-value")).toBe("MID");
    const walk = page.chip("candidate-filter-walking-time-max-option", "20分以内");
    walk.focus();
    walk.click();
    expect(document.activeElement.getAttribute("data-walking-time-max-value")).toBe("20");
    const plain = page.byTestId("candidate-filter-non-smoking-only");
    plain.focus();
    plain.click();
    expect(document.activeElement.getAttribute("data-testid")).toBe("candidate-filter-non-smoking-only");
  });

  it("ignores focus that is outside the filter bar", async () => {
    const page = await bootPanel();
    page.openPanel();
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    outside.focus();
    page.byTestId("candidate-filter-non-smoking-only").click();
    expect(document.activeElement).toBe(outside);
  });
});
