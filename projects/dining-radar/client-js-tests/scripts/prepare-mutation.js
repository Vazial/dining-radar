// Copies the shipped candidate.js (read-only) into .mutation-input/ for Stryker.
import { copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const source = fileURLToPath(
  new URL("../../src/dining_radar/web/static/dining_radar/web/candidate.js", import.meta.url)
);
const target = fileURLToPath(new URL("../.mutation-input/candidate.js", import.meta.url));
mkdirSync(new URL("../.mutation-input/", import.meta.url), { recursive: true });
copyFileSync(source, target);
