import { afterEach, describe, expect, it, vi } from "vitest";
import { boot, candidate, cleanup, jsonResponse, proposalBody } from "./harness.js";

afterEach(cleanup);

const many = (n) =>
  Array.from({ length: n }, (_, i) =>
    candidate({
      candidateRef: `c${i + 1}`,
      shopId: `s${i + 1}`,
      name: `店${i + 1}`,
      providerPageUrl: `https://example.test/${i + 1}`,
    })
  );

const bootDeck = (n = 3, extra = {}) =>
  boot({ twoColumn: false, fetch: () => jsonResponse(200, proposalBody({ candidates: many(n), ...extra })) });

let pointerId = 1;
function pointer(el, type, x, y, init = {}) {
  const { button = 0, ...rest } = init;
  const event = new MouseEvent(type, { clientX: x, clientY: y, bubbles: true, cancelable: true, button });
  Object.assign(event, { pointerId, pointerType: "touch", ...rest });
  el.dispatchEvent(event);
  return event;
}

function swipe(surface, dx, dy = 0) {
  pointer(surface, "pointerdown", 100, 100);
  pointer(surface, "pointermove", 100 + dx, 100 + dy);
  pointer(surface, "pointerup", 100 + dx, 100 + dy);
}

const position = (page) => page.byTestId("candidate-deck-position");

describe("deck scaffold", () => {
  it("builds the position counter, swipe surface and peek", async () => {
    const page = await bootDeck(3);
    const pos = position(page);
    expect(pos.tagName).toBe("SPAN");
    expect(pos.getAttribute("aria-live")).toBe("polite");
    expect(pos.getAttribute("aria-label")).toBe("表示中の候補の位置");
    expect(pos.className).toBe("candidate-deck-position");
    expect(pos.textContent).toBe("1 / 3");
    expect(pos.getAttribute("data-deck-visible-start")).toBe("1");
    expect(pos.getAttribute("data-deck-visible-end")).toBe("1");
    expect(pos.getAttribute("data-deck-total")).toBe("3");
    const surface = page.byTestId("candidate-deck-swipe-surface");
    expect(surface.className).toBe("candidate-deck-viewport");
    expect(surface.firstChild).toBe(page.byTestId("candidate-proposal-cards"));
    const peek = page.q(".candidate-deck-peek");
    expect(peek.getAttribute("aria-hidden")).toBe("true");
    expect(peek.hidden).toBe(false);
    expect(page.byTestId("candidate-proposal-cards").style.transform).toBe("translateX(0%)");
    expect(Array.from(page.q(".candidate-deck").children).map((n) => n.className)).toEqual([
      "candidate-deck-viewport",
      "candidate-deck-peek",
      "candidate-deck-position",
    ]);
  });
});

describe("swipe paging", () => {
  it("a left swipe pages forward and a right swipe pages back, updating transform, peek and counter", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    swipe(surface, -60);
    expect(position(page).textContent).toBe("2 / 3");
    expect(page.byTestId("candidate-proposal-cards").style.transform).toBe("translateX(-100%)");
    expect(page.q(".candidate-deck-peek").hidden).toBe(false);
    swipe(surface, -60);
    expect(position(page).textContent).toBe("3 / 3");
    expect(page.byTestId("candidate-proposal-cards").style.transform).toBe("translateX(-200%)");
    expect(page.q(".candidate-deck-peek").hidden).toBe(true);
    // overshoot at the end is a no-op
    swipe(surface, -60);
    expect(position(page).textContent).toBe("3 / 3");
    swipe(surface, 60);
    expect(position(page).textContent).toBe("2 / 3");
    swipe(surface, 60);
    swipe(surface, 60);
    expect(position(page).textContent).toBe("1 / 3");
    expect(position(page).getAttribute("data-deck-visible-start")).toBe("1");
  });

  it("ignores drags shorter than the 40px threshold", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    swipe(surface, -39);
    expect(position(page).textContent).toBe("1 / 3");
    swipe(surface, -40);
    expect(position(page).textContent).toBe("2 / 3");
  });

  it("does not start tracking a direction until movement exceeds the 6px slop", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    pointer(surface, "pointerdown", 100, 100);
    const small = pointer(surface, "pointermove", 105, 100);
    expect(small.defaultPrevented).toBe(false);
    const big = pointer(surface, "pointermove", 94, 100);
    expect(big.defaultPrevented).toBe(true);
    pointer(surface, "pointermove", 50, 100);
    pointer(surface, "pointerup", 50, 100);
    expect(position(page).textContent).toBe("2 / 3");
  });

  it("abandons a vertical drag and also a diagonal one that is not more horizontal", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    pointer(surface, "pointerdown", 100, 100);
    const vertical = pointer(surface, "pointermove", 110, 160);
    expect(vertical.defaultPrevented).toBe(false);
    pointer(surface, "pointerup", 10, 160);
    expect(position(page).textContent).toBe("1 / 3");
    pointer(surface, "pointerdown", 100, 100);
    pointer(surface, "pointermove", 160, 160); // |dx| == |dy| is not horizontal
    pointer(surface, "pointerup", 0, 160);
    expect(position(page).textContent).toBe("1 / 3");
  });

  it("keeps preventing default while a horizontal drag continues", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    pointer(surface, "pointerdown", 100, 100);
    pointer(surface, "pointermove", 80, 100);
    const later = pointer(surface, "pointermove", 60, 103);
    expect(later.defaultPrevented).toBe(true);
    pointer(surface, "pointerup", 0, 0);
    expect(position(page).textContent).toBe("2 / 3");
  });

  it("ignores moves/ups without a gesture and from a different pointer", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    expect(pointer(surface, "pointermove", 10, 10).defaultPrevented).toBe(false);
    pointer(surface, "pointerup", 10, 10);
    pointer(surface, "pointerdown", 100, 100, { pointerId: 7 });
    expect(pointer(surface, "pointermove", 20, 100, { pointerId: 8 }).defaultPrevented).toBe(false);
    pointer(surface, "pointermove", 20, 100, { pointerId: 7 });
    // an up from a different pointer cancels the gesture instead of paging
    pointer(surface, "pointerup", 20, 100, { pointerId: 8 });
    expect(position(page).textContent).toBe("1 / 3");
    // and the cancelled gesture cannot be resumed
    pointer(surface, "pointerup", 20, 100, { pointerId: 7 });
    expect(position(page).textContent).toBe("1 / 3");
  });

  it("pointercancel ends the gesture the same way as pointerup", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    pointer(surface, "pointerdown", 100, 100);
    pointer(surface, "pointermove", 40, 100);
    pointer(surface, "pointercancel", 40, 100);
    expect(position(page).textContent).toBe("2 / 3");
  });

  it("ignores a non-primary mouse button but accepts touch and primary mouse", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    pointer(surface, "pointerdown", 100, 100, { pointerType: "mouse", button: 2 });
    pointer(surface, "pointermove", 20, 100, { pointerType: "mouse" });
    pointer(surface, "pointerup", 20, 100, { pointerType: "mouse" });
    expect(position(page).textContent).toBe("1 / 3");
    pointer(surface, "pointerdown", 100, 100, { pointerType: "mouse", button: 0 });
    pointer(surface, "pointermove", 20, 100, { pointerType: "mouse" });
    pointer(surface, "pointerup", 20, 100, { pointerType: "mouse" });
    expect(position(page).textContent).toBe("2 / 3");
    // a touch pointer never has its button checked
    pointer(surface, "pointerdown", 100, 100, { pointerType: "touch", button: 5 });
    pointer(surface, "pointermove", 20, 100);
    pointer(surface, "pointerup", 20, 100);
    expect(position(page).textContent).toBe("3 / 3");
  });

  it("captures the pointer when supported and survives a rejecting capture", async () => {
    const page = await bootDeck(3);
    const surface = page.byTestId("candidate-deck-swipe-surface");
    surface.setPointerCapture = vi.fn();
    pointer(surface, "pointerdown", 100, 100, { pointerId: 4 });
    expect(surface.setPointerCapture).toHaveBeenCalledWith(4);
    pointer(surface, "pointerup", 100, 100, { pointerId: 4 });
    surface.setPointerCapture = vi.fn(() => {
      throw new Error("InvalidPointerId");
    });
    pointer(surface, "pointerdown", 100, 100);
    pointer(surface, "pointermove", 10, 100);
    pointer(surface, "pointerup", 10, 100);
    expect(position(page).textContent).toBe("2 / 3");
  });
});

describe("deck window on selection", () => {
  it("reveals the selected card by moving the window, both directions, without reordering", async () => {
    const page = await bootDeck(4);
    const refs = () => page.allByTestId("candidate-card").map((c) => c.getAttribute("data-candidate-ref"));
    const before = refs();
    page.allByTestId("candidate-card")[2].click();
    expect(position(page).textContent).toBe("3 / 4");
    page.allByTestId("candidate-card")[0].click();
    expect(position(page).textContent).toBe("1 / 4");
    page.allByTestId("candidate-card")[3].click();
    expect(position(page).textContent).toBe("4 / 4");
    expect(refs()).toEqual(before);
  });

  it("keeps the window when the selected card is already inside it", async () => {
    const page = await bootDeck(3);
    page.allByTestId("candidate-card")[0].click();
    expect(position(page).textContent).toBe("1 / 3");
  });

  it("does not page in two-column mode", async () => {
    const page = await boot({ twoColumn: true });
    page.allByTestId("candidate-card")[1].click();
    expect(page.byTestId("candidate-deck-position")).toBeNull();
  });

  it("a new response resets the window to the first card", async () => {
    const page = await bootDeck(3);
    swipe(page.byTestId("candidate-deck-swipe-surface"), -60);
    expect(position(page).textContent).toBe("2 / 3");
    page.byTestId("candidate-search-again").click();
    await vi.waitFor(() => expect(position(page).textContent).toBe("1 / 3"));
  });
});
