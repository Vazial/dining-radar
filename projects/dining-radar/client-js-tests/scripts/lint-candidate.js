// ESLint 10 refuses to lint files outside the config's base directory, and the
// shipped candidate.js lives outside this package. Running the API with the
// parent directory as cwd (and this package's config) lints it in place, so the
// L1 lint covers the file under test without copying or editing it.
import { fileURLToPath } from "node:url";
import { ESLint } from "eslint";

const parent = fileURLToPath(new URL("../..", import.meta.url));
const eslint = new ESLint({
  cwd: parent,
  overrideConfigFile: fileURLToPath(new URL("../eslint.config.js", import.meta.url)),
});
const results = await eslint.lintFiles(["src/dining_radar/web/static/dining_radar/web/candidate.js"]);
const formatter = await eslint.loadFormatter("stylish");
const output = await formatter.format(results);
if (output) console.log(output);
const problems = results.reduce((n, r) => n + r.errorCount + r.warningCount, 0);
process.exit(problems > 0 ? 1 : 0);
