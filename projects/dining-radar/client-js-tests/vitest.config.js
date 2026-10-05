import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// The one file under test. Tests load it through the "candidate-under-test"
// alias so the mutation run (vitest.mutation.config.js) can point the very same
// tests at a byte-identical copy that Stryker is allowed to mutate.
const CANDIDATE_JS = fileURLToPath(
  new URL("../src/dining_radar/web/static/dining_radar/web/candidate.js", import.meta.url)
);

export default defineConfig({
  resolve: { alias: { "candidate-under-test": CANDIDATE_JS } },
  test: {
    environment: "jsdom",
    include: ["test/**/*.test.js"],
    coverage: {
      provider: "v8",
      // The file lives outside this package, so it must be named explicitly.
      // "**/web/candidate.js" deliberately does not match the mutation copy
      // (.mutation-input/candidate.js).
      include: ["**/web/candidate.js"],
      exclude: [],
      allowExternal: true,
      reportsDirectory: "coverage",
      reporter: ["text", "json-summary"],
      // ADR-0014 decision 5: branch coverage floor 90% (same as the Python side).
      thresholds: { branches: 90 },
    },
  },
});
