// L1 mutation gate for candidate.js (ADR-0014 decision 5): mutation score >= 80%.
//
// Real-browser-dependent exclusions (ADR-0014 decision 5 permits naming them):
// none are taken. The one genuinely browser-timing-dependent behaviour -- Leaflet's
// Map#addLayer deferring marker/ring element creation so Marker#getElement() /
// Path#getElement() can still return null -- is exercised as its own branch by the
// fake-Leaflet tests (test/map.test.js, "skips markers whose element Leaflet has
// not created yet" etc.), so the whole file is inside the gate. The real timing
// itself stays with the browser-driven acceptance tests (L4, ADR-0009) and the
// device measurement (L5). If a range ever has to be excluded, name it here as
// "<file>:<startLine>-<endLine>" in `mutate` with a comment giving the reason.
export default {
  testRunner: "vitest",
  // `related: false`: tests load candidate.js through a dynamic import (so each boot
  // gets a fresh module), which vitest's related-files filter cannot see; with it on,
  // every mutant would run zero tests and "survive".
  vitest: { configFile: "vitest.mutation.config.js", related: false },
  // A byte-identical copy made by scripts/prepare-mutation.js: Stryker can only
  // mutate files inside this package, and the shipped file must never be edited.
  mutate: [".mutation-input/candidate.js"],
  coverageAnalysis: "perTest",
  reporters: ["clear-text", "progress", "json"],
  jsonReporter: { fileName: "reports/mutation/mutation.json" },
  thresholds: { high: 90, low: 85, break: 80 },
  tempDirName: ".stryker-tmp",
};
