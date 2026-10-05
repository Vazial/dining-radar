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
      "no-unused-vars": [
        "error",
        {
          caughtErrors: "none",
        },
      ],
    },
  },
];
