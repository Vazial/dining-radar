"use strict";

/**
 * Pins gathering.js's hideUnconfirmedCandidateDates (ADR-0073): while the
 * schedule tab of SELECTING_SHOP is open, every gathering-candidate-date card
 * whose data-confirmed is not "true" gets the hidden property, and the
 * confirmed card is left visible. Loads the shipped block verbatim (delimited
 * by the file's own ":start"/":end" markers), as
 * gathering_card_toggle_disabled_reason.test.js does.
 *
 * Run with: node --test tests/js_unit
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const GATHERING_JS_PATH = path.join(
  __dirname,
  "..",
  "..",
  "src",
  "dining_radar",
  "gathering",
  "static",
  "dining_radar",
  "gathering",
  "gathering.js"
);

const START_MARKER = "// hide-unconfirmed-candidate-dates:start";
const END_MARKER = "// hide-unconfirmed-candidate-dates:end";

function loadHideUnconfirmedCandidateDates() {
  const source = fs.readFileSync(GATHERING_JS_PATH, "utf8");
  const start = source.indexOf(START_MARKER);
  const end = source.indexOf(END_MARKER);
  assert.ok(start !== -1 && end > start, "marker block not found in gathering.js");
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(source.slice(start, end) + "\nthis.fn = hideUnconfirmedCandidateDates;", sandbox);
  return sandbox.fn;
}

function card(confirmed) {
  const attributes = { "data-confirmed": confirmed };
  return {
    hidden: false,
    attributes,
    getAttribute(name) {
      return attributes[name] === undefined ? null : attributes[name];
    },
  };
}

test("only the confirmed card stays visible", () => {
  const hide = loadHideUnconfirmedCandidateDates();
  const cards = [card("false"), card("true"), card("false")];
  hide(cards);
  assert.deepEqual(
    cards.map((c) => c.hidden),
    [true, false, true]
  );
});

test("hiding leaves data-* attributes unchanged", () => {
  const hide = loadHideUnconfirmedCandidateDates();
  const cards = [card("false"), card("true")];
  hide(cards);
  assert.deepEqual(
    cards.map((c) => c.attributes["data-confirmed"]),
    ["false", "true"]
  );
});

test("a card without data-confirmed is hidden", () => {
  const hide = loadHideUnconfirmedCandidateDates();
  const cards = [card(undefined)];
  hide(cards);
  assert.equal(cards[0].hidden, true);
});
