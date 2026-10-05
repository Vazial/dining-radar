import { afterEach, describe, expect, it } from "vitest";
import { boot, candidate, cleanup, jsonResponse, proposalBody } from "./harness.js";

afterEach(cleanup);

const withCandidates = (candidates, extra = {}) => ({
  fetch: () => jsonResponse(200, proposalBody({ candidates, ...extra })),
});

describe("renderCard", () => {
  it("renders every card attribute and the fact rows", async () => {
    const page = await boot({ twoColumn: true });
    const card = page.allByTestId("candidate-card")[0];
    const attrs = (name) => card.getAttribute(name);
    expect(attrs("data-candidate-ref")).toBe("c1");
    expect(attrs("data-selection-state")).toBe("selected");
    expect(attrs("data-card-payment-value-state")).toBe("provided");
    expect(attrs("data-candidate-control-category")).toBe("button");
    expect(attrs("data-candidate-control-purpose")).toBe("candidate-card-selection");
    expect(attrs("role")).toBe("button");
    expect(attrs("tabindex")).toBe("0");
    expect(card.tagName).toBe("ARTICLE");
    expect(page.allByTestId("candidate-card")[1].getAttribute("data-selection-state")).toBe("unselected");

    const name = card.querySelector('[data-testid="candidate-card-name"]');
    expect(name.tagName).toBe("H3");
    expect(name.textContent).toBe("店A");
    expect(name.getAttribute("data-field-label")).toBe("店名");
    expect(name.getAttribute("data-value-state")).toBe("provided");
    expect(card.querySelector(".candidate-marker-badge").textContent).toBe("1");
    expect(card.querySelector(".candidate-marker-badge").getAttribute("aria-hidden")).toBe("true");
    expect(page.allByTestId("candidate-card")[1].querySelector(".candidate-marker-badge").textContent).toBe("2");

    const genre = card.querySelector('[data-testid="candidate-card-genre"]');
    expect(genre.textContent).toBe("和食");
    expect(genre.getAttribute("data-field-label")).toBe("ジャンル");
    expect(genre.getAttribute("data-value-state")).toBe("provided");

    const desc = card.querySelector('[data-testid="candidate-card-description"]');
    expect(desc.textContent).toBe("説明A");
    expect(desc.getAttribute("data-field-label")).toBe("紹介");
    expect(desc.getAttribute("data-value-state")).toBe("provided");

    const rows = Array.from(card.querySelectorAll(".candidate-facts > div"));
    expect(rows.map((r) => r.querySelector("dt").textContent)).toEqual(["席数", "禁煙", "夜予算", "定休日"]);
    const dd = (id) => card.querySelector(`[data-testid="${id}"]`);
    expect(dd("candidate-card-total-seats").textContent).toBe("標準");
    expect(dd("candidate-card-total-seats").getAttribute("data-raw-value")).toBe("30");
    expect(dd("candidate-card-total-seats").getAttribute("data-field-label")).toBe("総席数");
    expect(dd("candidate-card-total-seats").getAttribute("data-value-state")).toBe("provided");
    expect(dd("candidate-card-non-smoking").textContent).toBe("全席禁煙");
    expect(dd("candidate-card-non-smoking").getAttribute("data-raw-value")).toBe("FULL");
    expect(dd("candidate-card-non-smoking").getAttribute("data-field-label")).toBe("禁煙対応");
    expect(dd("candidate-card-dinner-budget").textContent).toBe("中");
    expect(dd("candidate-card-dinner-budget").getAttribute("data-raw-value")).toBe("MID");
    expect(dd("candidate-card-dinner-budget").getAttribute("data-field-label")).toBe("ディナー予算感");
    expect(dd("candidate-card-regular-holiday").textContent).toBe("日曜");
    expect(dd("candidate-card-regular-holiday").hasAttribute("data-raw-value")).toBe(false);
    expect(dd("candidate-card-regular-holiday").getAttribute("data-field-label")).toBe("定休日");
    expect(rows[3].className).toBe("candidate-fact-row candidate-fact-row--candidate-card-regular-holiday");

    const link = card.querySelector('[data-testid="candidate-card-provider-page-link"]');
    expect(link.getAttribute("href")).toBe("https://example.test/a");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(link.getAttribute("data-field-label")).toBe("詳細");
    expect(link.getAttribute("data-value-state")).toBe("provided");
    expect(link.textContent).toBe("メニューなどを確認");
    expect(card.querySelector(".candidate-card-detail-footer").firstChild).toBe(link);
  });

  it("maps every coarse label enum", async () => {
    const page = await boot(
      withCandidates([
        candidate({ candidateRef: "a", capacityTier: "SMALL", nonSmokingStatus: "PARTIAL", dinnerBudgetTier: "LOW" }),
        candidate({ candidateRef: "b", capacityTier: "LARGE", nonSmokingStatus: "NONE", dinnerBudgetTier: "HIGH" }),
      ])
    );
    const text = (card, id) => card.querySelector(`[data-testid="${id}"]`).textContent;
    const [a, b] = page.allByTestId("candidate-card");
    expect([text(a, "candidate-card-total-seats"), text(a, "candidate-card-non-smoking"), text(a, "candidate-card-dinner-budget")]).toEqual(["少なめ", "一部禁煙", "低"]);
    expect([text(b, "candidate-card-total-seats"), text(b, "candidate-card-non-smoking"), text(b, "candidate-card-dinner-budget")]).toEqual(["多め", "禁煙席なし", "高"]);
  });

  it("marks missing fields unavailable and omits their raw-value attribute", async () => {
    const page = await boot(
      withCandidates([
        candidate({
          totalSeats: null,
          capacityTier: null,
          nonSmokingStatus: "",
          dinnerBudgetTier: undefined,
          regularHoliday: null,
          description: "",
          cardPaymentAvailable: null,
        }),
      ])
    );
    const card = page.byTestId("candidate-card");
    expect(card.getAttribute("data-card-payment-value-state")).toBe("unavailable");
    for (const id of ["candidate-card-total-seats", "candidate-card-non-smoking", "candidate-card-dinner-budget", "candidate-card-regular-holiday"]) {
      const dd = card.querySelector(`[data-testid="${id}"]`);
      expect(dd.getAttribute("data-value-state")).toBe("unavailable");
      expect(dd.hasAttribute("data-raw-value")).toBe(false);
      expect(dd.textContent).toBe("情報なし");
    }
    const desc = card.querySelector('[data-testid="candidate-card-description"]');
    expect(desc.getAttribute("data-value-state")).toBe("unavailable");
    expect(desc.textContent).toBe("紹介文の登録はありません");
  });

  it("treats a null and an undefined description as unavailable", async () => {
    for (const description of [null, undefined]) {
      const page = await boot(withCandidates([candidate({ description })]));
      expect(page.byTestId("candidate-card-description").getAttribute("data-value-state")).toBe("unavailable");
      cleanup();
    }
  });

  it("falls back to the raw value when a coarse label has no mapping", async () => {
    const page = await boot(withCandidates([candidate({ capacityTier: "HUGE" })]));
    // no label for the tier -> the visible text is the raw totalSeats value
    expect(page.byTestId("candidate-card-total-seats").textContent).toBe("30");
  });

  it("places the walking-time chip in the id row for two-column and the genre row for touch", async () => {
    const two = await boot({ twoColumn: true });
    const chipText = two.byTestId("candidate-card-walking-time");
    expect(chipText.textContent).toBe("徒歩 約7分");
    expect(chipText.getAttribute("data-field-label")).toBe("徒歩");
    expect(chipText.getAttribute("data-value-state")).toBe("provided");
    expect(chipText.parentElement.className).toBe("candidate-card-id-row");
    expect(chipText.parentElement.parentElement.querySelector(".candidate-genre-row").children).toHaveLength(1);
    cleanup();
    const touch = await boot({ twoColumn: false });
    const chip2 = touch.byTestId("candidate-card-walking-time");
    expect(chip2.parentElement.className).toBe("candidate-genre-row");
    expect(chip2.parentElement.children).toHaveLength(2);
    expect(chip2.parentElement.lastChild).toBe(chip2);
    expect(chip2.className).toBe("candidate-walk-chip");
  });

  it("shows the payment caution only for exactly false", async () => {
    const page = await boot(
      withCandidates([
        candidate({ candidateRef: "a", cardPaymentAvailable: false }),
        candidate({ candidateRef: "b", cardPaymentAvailable: null }),
        candidate({ candidateRef: "c", cardPaymentAvailable: true }),
      ])
    );
    const cautions = page.allByTestId("candidate-card-payment-caution");
    expect(cautions).toHaveLength(1);
    expect(cautions[0].textContent).toBe("クレジットカード非対応（支払い方法は要確認）");
    expect(cautions[0].getAttribute("data-card-payment-available")).toBe("false");
    expect(cautions[0].closest("article").getAttribute("data-candidate-ref")).toBe("a");
  });

  it("does not add the gathering toggle outside gathering mode", async () => {
    const page = await boot();
    expect(page.byTestId("candidate-card-gathering-toggle")).toBeNull();
  });
});

describe("selection", () => {
  it("click selects a card and its marker; links do not select", async () => {
    const page = await boot();
    const [a, b] = page.allByTestId("candidate-card");
    b.click();
    expect(a.getAttribute("data-selection-state")).toBe("unselected");
    expect(b.getAttribute("data-selection-state")).toBe("selected");
    expect(window.HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
    a.querySelector("a").click();
    expect(a.getAttribute("data-selection-state")).toBe("unselected");
  });

  it("Enter and Space select and reveal; other keys do not", async () => {
    const page = await boot();
    const [a, b] = page.allByTestId("candidate-card");
    const press = (el, key) => {
      const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
      el.dispatchEvent(event);
      return event;
    };
    expect(press(b, "a").defaultPrevented).toBe(false);
    expect(b.getAttribute("data-selection-state")).toBe("unselected");
    const enter = press(b, "Enter");
    expect(enter.defaultPrevented).toBe(true);
    expect(b.getAttribute("data-selection-state")).toBe("selected");
    expect(b.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "nearest", inline: "center" });
    expect(press(a, " ").defaultPrevented).toBe(true);
    expect(a.getAttribute("data-selection-state")).toBe("selected");
  });
});
