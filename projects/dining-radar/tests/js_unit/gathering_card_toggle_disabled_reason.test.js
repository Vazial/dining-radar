"use strict";

/**
 * Pins candidate.js's gatheringMode.cardToggle boundary logic (ADR-0057,
 * 2026-09-13 human ruling "押せない見た目にして理由を出す"):
 * gatheringCardToggleDisabledReason(isShortlisted) reads the module's
 * currentGatheringContext closure variable and returns exactly one of
 * "limit-reached" (case 1, adr/0049 decision 8), "last-shop" (case 2,
 * ADR-0057 decision 1), or null (enabled).
 *
 * Mirrors tests/js_unit/participant_request_sequencer.test.js's own
 * precedent (ADR-0014): this test loads and executes, *verbatim*, the exact
 * block candidate.js itself ships (delimited by that file's own
 * "gathering-card-toggle-disabled-reason:start"/":end" comment markers) --
 * not a hand-copied reimplementation that could silently drift from the
 * real shipped logic. The extracted function reads an unqualified
 * `currentGatheringContext` identifier (a closure variable in the real
 * file); running it alone in a fresh vm context resolves that identifier
 * against the sandbox's own global object, so setting
 * `sandbox.currentGatheringContext` before each call is sufficient --
 * no jsdom/DOM globals are required (ADR-0014 decision 6: this is pure
 * boundary logic, not a DOM-API-calling-convention concern).
 *
 * Run with: node --test tests/js_unit
 * (Node >= 18 ships both `node:test` and `node:assert/strict` built in --
 * no install step.)
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const CANDIDATE_JS_PATH = path.join(
  __dirname,
  "..",
  "..",
  "src",
  "dining_radar",
  "web",
  "static",
  "dining_radar",
  "web",
  "candidate.js"
);

const START_MARKER = "// gathering-card-toggle-disabled-reason:start";
const END_MARKER = "// gathering-card-toggle-disabled-reason:end";

function loadGatheringCardToggleDisabledReasonFromCandidateJs() {
  const source = fs.readFileSync(CANDIDATE_JS_PATH, "utf8");
  const startIndex = source.indexOf(START_MARKER);
  const endIndex = source.indexOf(END_MARKER);
  assert.notEqual(
    startIndex,
    -1,
    "gathering-card-toggle-disabled-reason:start marker not found in candidate.js -- did the guard move or get renamed?"
  );
  assert.notEqual(
    endIndex,
    -1,
    "gathering-card-toggle-disabled-reason:end marker not found in candidate.js -- did the guard move or get renamed?"
  );
  assert.ok(startIndex < endIndex, "gathering-card-toggle-disabled-reason markers are out of order");
  const block = source.slice(startIndex, endIndex);
  const sandbox = { currentGatheringContext: null };
  vm.createContext(sandbox);
  vm.runInContext(
    block + "\nthis.gatheringCardToggleDisabledReason = gatheringCardToggleDisabledReason;",
    sandbox,
    { filename: "candidate.js (extracted gathering-card-toggle-disabled-reason block)" }
  );
  assert.equal(typeof sandbox.gatheringCardToggleDisabledReason, "function");
  return {
    gatheringCardToggleDisabledReason: sandbox.gatheringCardToggleDisabledReason,
    setGatheringContext: (context) => {
      sandbox.currentGatheringContext = context;
    },
  };
}

test("an unshortlisted card below the 5-shop cap is enabled", () => {
  const { gatheringCardToggleDisabledReason, setGatheringContext } =
    loadGatheringCardToggleDisabledReasonFromCandidateJs();
  setGatheringContext({ shortlistedShopCount: 3, maxShortlistedShops: 5 });
  assert.equal(gatheringCardToggleDisabledReason(false), null);
});

test("an unshortlisted card is disabled with limit-reached once the cap is hit", () => {
  const { gatheringCardToggleDisabledReason, setGatheringContext } =
    loadGatheringCardToggleDisabledReasonFromCandidateJs();
  setGatheringContext({ shortlistedShopCount: 5, maxShortlistedShops: 5 });
  assert.equal(gatheringCardToggleDisabledReason(false), "limit-reached");
});

test("an unshortlisted card is disabled with limit-reached even past the cap", () => {
  // Defensive: this contract-defined boundary is `>=`, not `===`, so a
  // hypothetical over-cap count must still read as limit-reached.
  const { gatheringCardToggleDisabledReason, setGatheringContext } =
    loadGatheringCardToggleDisabledReasonFromCandidateJs();
  setGatheringContext({ shortlistedShopCount: 6, maxShortlistedShops: 5 });
  assert.equal(gatheringCardToggleDisabledReason(false), "limit-reached");
});

test("a shortlisted card with more than one shop in the gathering is enabled", () => {
  const { gatheringCardToggleDisabledReason, setGatheringContext } =
    loadGatheringCardToggleDisabledReasonFromCandidateJs();
  setGatheringContext({ shortlistedShopCount: 2, maxShortlistedShops: 5 });
  assert.equal(gatheringCardToggleDisabledReason(true), null);
});

test("ADR-0057: a shortlisted card that is the gathering's last remaining shop is disabled with last-shop", () => {
  const { gatheringCardToggleDisabledReason, setGatheringContext } =
    loadGatheringCardToggleDisabledReasonFromCandidateJs();
  setGatheringContext({ shortlistedShopCount: 1, maxShortlistedShops: 5 });
  assert.equal(gatheringCardToggleDisabledReason(true), "last-shop");
});

test("the two disabled reasons are mutually exclusive at the shared boundary count of 1", () => {
  // At shortlistedShopCount === 1 (below maxShortlistedShops), the
  // unshortlisted case must remain enabled (not limit-reached) while the
  // shortlisted case is last-shop -- adr/0049 decision 8's sentence that a
  // shortlisted card "remains enabled regardless of the count" now holds
  // only down to a shortlistedShopCount of 2 (ADR-0057).
  const { gatheringCardToggleDisabledReason, setGatheringContext } =
    loadGatheringCardToggleDisabledReasonFromCandidateJs();
  setGatheringContext({ shortlistedShopCount: 1, maxShortlistedShops: 5 });
  assert.equal(gatheringCardToggleDisabledReason(false), null);
  assert.equal(gatheringCardToggleDisabledReason(true), "last-shop");
});
