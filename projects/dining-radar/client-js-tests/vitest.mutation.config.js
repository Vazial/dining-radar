import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Used only by Stryker. scripts/prepare-mutation.js copies the shipped
// candidate.js here byte for byte; Stryker mutates the copy (its sandbox lives
// inside this package, so it cannot mutate files outside it) while the shipped
// file is never opened for writing.
export default defineConfig({
  resolve: {
    alias: {
      "candidate-under-test": fileURLToPath(new URL("./.mutation-input/candidate.js", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    include: ["test/**/*.test.js"],
  },
});
