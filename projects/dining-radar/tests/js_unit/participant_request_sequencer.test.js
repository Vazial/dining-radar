"use strict";

/**
 * Pins the stale-response guard participant.js uses to fix the intermittent
 * acceptance failures where a write (e.g. setParticipantDisplayName) had
 * already succeeded server-side, yet the participant screen kept showing
 * the pre-write value (e.g. gathering-participant-name-status stuck at
 * "false") -- confirmed root cause: two participant-facing requests (e.g.
 * a schedule-response PUT and a display-name PUT fired shortly after it,
 * with no wait in between -- exactly what a real tap on a slow connection
 * can do) can have their *responses* arrive out of the order they were
 * *issued* in; participant.js previously let whichever response happened
 * to arrive last unconditionally overwrite state.view/render, even when it
 * carried data older than a request issued (and already applied) after it.
 *
 * This test loads and executes, *verbatim*, the exact guard block
 * participant.js itself ships (delimited by that file's own
 * "request-sequencer:start"/"request-sequencer:end" comment markers) --
 * not a hand-copied reimplementation that could silently drift from the
 * real shipped logic. No DOM/browser globals are required: the extracted
 * block touches nothing but a closure-local counter, so Node's own,
 * dependency-free assert + test modules are sufficient (no jsdom, no npm
 * project -- see this project's ADR-0014 for why a *full* JS unit-test
 * layer, jsdom included, is a separate, not-yet-implemented decision
 * scoped to candidate.js; this test deliberately stays inside what Node's
 * built-in tooling alone can already verify, rather than expanding that
 * decision's scope on its own).
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

const PARTICIPANT_JS_PATH = path.join(
  __dirname,
  "..",
  "..",
  "src",
  "dining_radar",
  "gathering",
  "static",
  "dining_radar",
  "gathering",
  "participant.js"
);

const START_MARKER = "// request-sequencer:start";
const END_MARKER = "// request-sequencer:end";

function loadRequestSequencerFromParticipantJs() {
  const source = fs.readFileSync(PARTICIPANT_JS_PATH, "utf8");
  const startIndex = source.indexOf(START_MARKER);
  const endIndex = source.indexOf(END_MARKER);
  assert.notEqual(
    startIndex,
    -1,
    "request-sequencer:start marker not found in participant.js -- did the guard move or get renamed?"
  );
  assert.notEqual(
    endIndex,
    -1,
    "request-sequencer:end marker not found in participant.js -- did the guard move or get renamed?"
  );
  assert.ok(startIndex < endIndex, "request-sequencer markers are out of order");
  const block = source.slice(startIndex, endIndex);
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(
    block + "\nthis.beginRequest = beginRequest; this.isStaleResponse = isStaleResponse;",
    sandbox,
    { filename: "participant.js (extracted request-sequencer block)" }
  );
  assert.equal(typeof sandbox.beginRequest, "function");
  assert.equal(typeof sandbox.isStaleResponse, "function");
  return { beginRequest: sandbox.beginRequest, isStaleResponse: sandbox.isStaleResponse };
}

test("a freshly begun request, with none issued after it, is never stale", () => {
  const { beginRequest, isStaleResponse } = loadRequestSequencerFromParticipantJs();
  const sequence = beginRequest();
  assert.equal(isStaleResponse(sequence), false);
});

test("an earlier-issued request becomes stale once a newer one is issued", () => {
  const { beginRequest, isStaleResponse } = loadRequestSequencerFromParticipantJs();
  const earlier = beginRequest();
  const later = beginRequest();
  assert.equal(
    isStaleResponse(earlier),
    true,
    "the earlier request's own eventual response must be recognized as stale"
  );
  assert.equal(
    isStaleResponse(later),
    false,
    "the most recently issued request's own eventual response must still apply"
  );
});

test("the confirmed bug scenario: an earlier request's late-arriving response must not win", () => {
  // Mirrors this project's own confirmed reproduction: a schedule-response
  // PUT is issued first, but a display-name PUT fired immediately
  // afterwards (no wait in between) gets *its* response back from the
  // server first; the schedule-response PUT's own response -- computed
  // before the display-name write happened -- arrives only afterwards.
  const { beginRequest, isStaleResponse } = loadRequestSequencerFromParticipantJs();
  const scheduleResponseSequence = beginRequest(); // issued first
  const displayNameSequence = beginRequest(); // issued second, but arrives first

  // displayName's callback runs first: not stale, its result is applied.
  assert.equal(isStaleResponse(displayNameSequence), false);

  // scheduleResponse's callback runs later, after a newer request
  // (displayName) has already been issued: it must be discarded rather
  // than overwrite displayName's already-applied, newer result.
  assert.equal(isStaleResponse(scheduleResponseSequence), true);
});

test("three interleaved requests: only the response for the last one issued ever applies", () => {
  const { beginRequest, isStaleResponse } = loadRequestSequencerFromParticipantJs();
  const first = beginRequest();
  const second = beginRequest();
  const third = beginRequest();
  assert.equal(isStaleResponse(first), true);
  assert.equal(isStaleResponse(second), true);
  assert.equal(isStaleResponse(third), false);
});
