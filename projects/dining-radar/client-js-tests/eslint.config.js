import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["coverage/", "reports/", ".stryker-tmp/", ".mutation-input/", "node_modules/"] },
  js.configs.recommended,
  {
    // The test suite and tool configs: ES modules running under Node + jsdom.
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: { ...globals.node, ...globals.browser },
    },
  },
  {
    // The shipped script under test: a classic (non-module) browser script.
    files: ["**/web/candidate.js"],
    languageOptions: {
      ecmaVersion: 2017,
      sourceType: "script",
      globals: { ...globals.browser },
    },
    rules: {
      // `catch (error) {}` blocks in candidate.js are deliberate "never throws"
      // degradations (each carries a comment); the bound error is not used.
      // The four names below are write-only variables the lint found in the
      // shipped file. candidate.js is frozen for this slice (KEN-21 is changing
      // it), so they are named here rather than edited: remove each entry as the
      // variable is deleted from the source.
      "no-unused-vars": [
        "error",
        {
          caughtErrors: "none",
          varsIgnorePattern: "^(DISPLAY_CAP|selectedCandidateRef|isMapPrimaryTouchLayout|desktopNav)$",
        },
      ],
    },
  },
];
